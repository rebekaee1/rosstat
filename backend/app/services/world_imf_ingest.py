"""IMF WEO ingest → world_indicators (+ российский overlay для RU).

Не отдельный cron: вызывается из ``world_eurostat_ingest_job`` (не shadow)
и вручную::

    docker compose exec backend python -c \\
      "import asyncio; from app.services.world_imf_ingest import run_imf_weo_ingest; \\
       print(asyncio.run(run_imf_weo_ingest(country_codes=['US','DE','RU'])))"

Страны: active ``world_countries`` + RU в каталог ``indicators``.
WorldCountry для России не создаём.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import bump_namespaces
from app.database import async_session
from app.models import (
    Indicator,
    WorldCountry,
    WorldDataPoint,
    WorldDatasetState,
    WorldIndicator,
    WorldIngestDatasetLog,
    WorldIngestRun,
)
from app.services.imf_weo_adapter import (
    DATASET_ID,
    PROVIDER,
    PUBLIC_SOURCE_NAME,
    PUBLIC_SOURCE_URL,
    WEO_SERIES,
    ImfWeoAdapter,
    make_weo_series_ref,
    weo_iso3_for,
    weo_methodology,
    world_indicator_code,
)
from app.services.upsert import bulk_upsert, prune_indicator_dates_not_in

logger = logging.getLogger(__name__)


async def _active_world_iso2(db: AsyncSession) -> list[str]:
    rows = (
        await db.execute(
            select(WorldCountry.code).where(WorldCountry.is_active.is_(True))
        )
    ).scalars().all()
    return [str(code).strip().upper() for code in rows if code]


async def _upsert_world_series(
    db: AsyncSession,
    *,
    country: WorldCountry,
    weo_code: str,
    points: list[tuple[date, float]],
) -> tuple[int, int]:
    if not points:
        return 0, 0
    meta = WEO_SERIES[weo_code]
    ref = make_weo_series_ref(country.code, weo_code)
    code = world_indicator_code(country.code, weo_code)
    existing = (
        await db.execute(
            select(WorldIndicator).where(
                WorldIndicator.provider == PROVIDER,
                WorldIndicator.country_id == country.id,
                WorldIndicator.dataset_id == DATASET_ID,
                WorldIndicator.slice_hash == ref.slice_hash,
            )
        )
    ).scalar_one_or_none()
    if existing is None:
        by_code = (
            await db.execute(select(WorldIndicator).where(WorldIndicator.code == code))
        ).scalar_one_or_none()
        existing = by_code
    hs, he = points[0][0], points[-1][0]
    desc = meta["desc_ru"].format(name=meta["name_ru"], unit=meta["unit_ru"])
    fields = {
        "code": code,
        "provider": PROVIDER,
        "dataset_id": DATASET_ID,
        "slice_json": {"weo_code": weo_code},
        "slice_hash": ref.slice_hash,
        "name_ru": meta["name_ru"],
        "name_en": meta["name_en"],
        "name_quality": "curated",
        "unit": meta["unit"],
        "unit_ru": meta["unit_ru"],
        "frequency": "annual",
        "category_ru": meta["category_ru"],
        "source": PUBLIC_SOURCE_NAME,
        "source_url": PUBLIC_SOURCE_URL,
        "description": desc,
        "methodology": weo_methodology(weo_code),
        "history_start": hs,
        "history_end": he,
        "points_count": len(points),
        "is_listed": True,
        "seo_title": f"{meta['name_ru']} — {country.name_ru}",
        "seo_description": desc,
        "seo_keywords": meta["keywords_ru"].format(
            name=meta["name_ru"], country=country.name_ru
        ),
    }
    if existing is None:
        indicator = WorldIndicator(country_id=country.id, **fields)
        db.add(indicator)
        await db.flush()
        indicator_id = indicator.id
    else:
        for key, value in fields.items():
            setattr(existing, key, value)
        existing.country_id = country.id
        await db.flush()
        indicator_id = existing.id

    values = [
        {"indicator_id": indicator_id, "date": dt, "value": value}
        for dt, value in points
    ]
    stmt = pg_insert(WorldDataPoint).values(values)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_world_data_point",
        set_={"value": stmt.excluded.value},
        where=(WorldDataPoint.__table__.c.value.is_distinct_from(stmt.excluded.value)),
    ).returning(WorldDataPoint.id)
    touched = len((await db.execute(stmt)).fetchall())
    source_dates = [dt for dt, _ in points]
    await db.execute(
        WorldDataPoint.__table__.delete().where(
            WorldDataPoint.indicator_id == indicator_id,
            WorldDataPoint.date.not_in(source_dates),
        )
    )
    count, history_start, history_end = (
        await db.execute(
            select(
                func.count(WorldDataPoint.id),
                func.min(WorldDataPoint.date),
                func.max(WorldDataPoint.date),
            ).where(WorldDataPoint.indicator_id == indicator_id)
        )
    ).one()
    target = await db.get(WorldIndicator, indicator_id)
    if target is not None:
        target.points_count = int(count or 0)
        target.history_start = history_start
        target.history_end = history_end
    return 1, touched


async def _upsert_russia_catalog(
    db: AsyncSession,
    *,
    weo_code: str,
    points: list[tuple[date, float]],
) -> int:
    if not points:
        return 0
    code = WEO_SERIES[weo_code]["russia_indicator_code"]
    indicator = (
        await db.execute(select(Indicator).where(Indicator.code == code))
    ).scalar_one_or_none()
    if indicator is None:
        logger.warning("IMF WEO Russia overlay skipped: seed row %s missing", code)
        return 0
    added, updated = await bulk_upsert(db, indicator.id, points)
    await prune_indicator_dates_not_in(db, indicator.id, points)
    return added + updated


async def run_imf_weo_ingest(
    *,
    country_codes: list[str] | None = None,
) -> dict[str, int]:
    """Загрузить NGDPD / NGDPDPC / GGXCNL_NGDP для active world countries и RU-overlay."""
    started_at = datetime.now(timezone.utc).replace(tzinfo=None)
    async with async_session() as db:
        run = WorldIngestRun(source=PROVIDER, is_shadow=False, started_at=started_at)
        db.add(run)
        await db.commit()
        await db.refresh(run)
        run_id = run.id

        active = await _active_world_iso2(db)
        requested = (
            {code.strip().upper() for code in country_codes if code and code.strip()}
            if country_codes is not None
            else None
        )
        world_iso2 = [code for code in active if requested is None or code in requested]
        include_ru = requested is None or "RU" in requested
        countries = {
            row.code: row
            for row in (
                await db.execute(
                    select(WorldCountry).where(WorldCountry.code.in_(world_iso2))
                )
            ).scalars().all()
        } if world_iso2 else {}

        iso2_targets = list(countries)
        if include_ru:
            iso2_targets.append("RU")
        iso3_list = []
        seen_iso3: set[str] = set()
        for iso2 in iso2_targets:
            iso3 = weo_iso3_for(iso2)
            if iso3 and iso3 not in seen_iso3:
                seen_iso3.add(iso3)
                iso3_list.append(iso3)

        adapter = ImfWeoAdapter(country_codes=iso2_targets)
        indicators = 0
        points_touched = 0
        russia_points = 0
        error: str | None = None
        try:
            for weo_code in WEO_SERIES:
                parsed = await asyncio.to_thread(adapter.fetch_weo_code, weo_code, iso3_list)
                by_iso3: dict[str, list[tuple[date, float]]] = {}
                for item in parsed:
                    by_iso3.setdefault(item.country_iso3, []).append((item.period, item.value))
                for series in by_iso3.values():
                    series.sort(key=lambda pair: pair[0])
                for iso2, country in countries.items():
                    iso3 = weo_iso3_for(iso2)
                    series = by_iso3.get(iso3 or "", [])
                    n_ind, n_pts = await _upsert_world_series(
                        db, country=country, weo_code=weo_code, points=series
                    )
                    indicators += n_ind
                    points_touched += n_pts
                if include_ru:
                    russia_points += await _upsert_russia_catalog(
                        db,
                        weo_code=weo_code,
                        points=by_iso3.get("RUS", []),
                    )
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            state = await db.get(WorldDatasetState, (PROVIDER, DATASET_ID))
            if state is None:
                state = WorldDatasetState(provider=PROVIDER, dataset_id=DATASET_ID)
                db.add(state)
            state.last_update_of_data = date.today()
            state.status = "ok"
            state.last_success_at = now
            state.last_error = None
            db.add(
                WorldIngestDatasetLog(
                    run_id=run_id,
                    provider=PROVIDER,
                    dataset_id=DATASET_ID,
                    status="ok",
                    source_updated_at=date.today(),
                    rows_fetched=points_touched + russia_points,
                )
            )
            run = await db.get(WorldIngestRun, run_id)
            assert run is not None
            run.datasets_selected = 1
            run.datasets_succeeded = 1
            run.datasets_failed = 0
            run.status = "ok"
            run.completed_at = now
            await db.commit()
        except Exception as exc:  # noqa: BLE001
            error = str(exc)[:2000]
            logger.exception("IMF WEO ingest failed")
            await db.rollback()
            async with async_session() as err_db:
                run = await err_db.get(WorldIngestRun, run_id)
                if run is not None:
                    run.status = "failed"
                    run.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
                    run.error_message = error
                    run.datasets_selected = 1
                    run.datasets_failed = 1
                    err_db.add(
                        WorldIngestDatasetLog(
                            run_id=run_id,
                            provider=PROVIDER,
                            dataset_id=DATASET_ID,
                            status="error",
                            error_message=error,
                        )
                    )
                    await err_db.commit()
            raise

    await bump_namespaces("world")
    return {
        "run_id": run_id,
        "countries": len(countries) + (1 if include_ru else 0),
        "indicators": indicators,
        "points_touched": points_touched,
        "russia_points": russia_points,
    }
