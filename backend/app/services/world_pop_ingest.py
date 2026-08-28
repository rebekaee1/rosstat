"""Census + IBGE population ingest → world_indicators (US/BR national series).

Не отдельный cron: вызывается вручную или из общего world ingest job (та же
точка, где подключён IMF WEO)::

    docker compose exec backend python -c \\
      "import asyncio; from app.services.world_pop_ingest import run_world_pop_ingest; \\
       print(asyncio.run(run_world_pop_ingest()))"

Пишет два национальных ряда в ``world_indicators``: ``us-population-census``
(provider ``census``, U.S. Census Bureau) и ``br-population-ibge``
(provider ``ibge``, IBGE). В карточки стран/рейтинг концепта population ряды
попадают через ``NATIONAL_CONCEPT_INDICATOR_CODES`` — та же схема, что у
``ca-population`` / ``uk-population``. Повторный прогон идемпотентен: даты,
отсутствующие во входе, вычищаются из рядов.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timezone
from typing import Callable, Sequence

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import bump_namespaces
from app.database import async_session
from app.models import (
    WorldCountry,
    WorldDataPoint,
    WorldDatasetState,
    WorldIndicator,
    WorldIngestDatasetLog,
    WorldIngestRun,
)
from app.services.br_pop_adapter import (
    DATASET_ID as BR_DATASET_ID,
    PROVIDER as BR_PROVIDER,
    PUBLIC_SOURCE_NAME as BR_SOURCE_NAME,
    PUBLIC_SOURCE_URL as BR_SOURCE_URL,
    PUBLIC_UNIT_RU as BR_UNIT_RU,
    IbgePopAdapter,
    make_ibge_series_ref,
)
from app.services.us_pop_adapter import (
    DATASET_ID as US_DATASET_ID,
    PROVIDER as US_PROVIDER,
    PUBLIC_SOURCE_NAME as US_SOURCE_NAME,
    PUBLIC_SOURCE_URL as US_SOURCE_URL,
    PUBLIC_UNIT_RU as US_UNIT_RU,
    UsCensusPopAdapter,
    make_census_series_ref,
)

logger = logging.getLogger(__name__)

# Публичные тексты карточек — без упоминания API/таблиц/файлов (методология).
_US_DESCRIPTION = (
    "Численность постоянного населения США на 1 июля соответствующего года по "
    "оценкам Бюро переписи населения США."
)
_US_METHODOLOGY = (
    "Показатель — оценочная численность постоянного населения страны на 1 июля. "
    "Оценки строятся на базе последней переписи населения и ежегодно "
    "актуализируются с учётом записей о рождениях, смертях и миграции; после "
    "каждой переписи весь ряд пересматривается задним числом. Источник: "
    "Бюро переписи населения США (Population Estimates Program)."
)
_US_KEYWORDS = (
    "население сша, население америки, численность населения сша, "
    "population of the united states, us population, перепись сша"
)
_BR_DESCRIPTION = (
    "Численность постоянного населения Бразилии по данным Бразильского "
    "института географии и статистики (IBGE): итоги переписей населения и "
    "ежегодные оценки между ними."
)
_BR_METHODOLOGY = (
    "Показатель — оценочная численность постоянного населения страны. "
    "В годы проведения переписи населения публикуется переписной итог; в "
    "остальные годы — оценка численности, рассчитанная на базе последней "
    "переписи с учётом записей о рождениях, смертях и миграции. После каждой "
    "переписи ряд пересматривается. Источник: Бразильский институт географии "
    "и статистики (IBGE)."
)
_BR_KEYWORDS = (
    "население бразилии, численность населения бразилии, бразилия население, "
    "population of brazil, brazil population, перепись бразилии"
)


def _population_meta(
    *,
    country_name_ru: str,
    unit_ru: str,
) -> dict[str, str]:
    return {
        "category_ru": "Население",
        "unit_ru": unit_ru,
        "name_ru": f"Население — {country_name_ru}",
    }


async def _country_by_code(db: AsyncSession, iso2: str) -> WorldCountry | None:
    return (
        await db.execute(
            select(WorldCountry).where(WorldCountry.code == iso2.upper())
        )
    ).scalar_one_or_none()


async def _upsert_population_series(
    db: AsyncSession,
    *,
    provider: str,
    dataset_id: str,
    code: str,
    series_id: str,
    country: WorldCountry,
    source_name: str,
    source_url: str,
    points: Sequence[tuple[date, float]],
    unit: str,
    unit_ru: str,
    description: str,
    methodology: str,
    seo_keywords: str,
    category_ru: str,
    make_ref: Callable[[], object],
) -> tuple[int, int]:
    """Записать один национальный ряд; вернуть (1, touched_points).

    Путь ``world_imf_ingest._upsert_world_series``: identity по
    provider × country × dataset × slice_hash, карточка обновляется
    curатед-полями, точки — ON CONFLICT DO UPDATE, лишние даты вычищаются.
    """
    if not points:
        return 0, 0
    ref = make_ref()
    existing = (
        await db.execute(
            select(WorldIndicator).where(
                WorldIndicator.provider == provider,
                WorldIndicator.country_id == country.id,
                WorldIndicator.dataset_id == dataset_id,
                WorldIndicator.slice_hash == ref.slice_hash,
            )
        )
    ).scalar_one_or_none()
    if existing is None:
        existing = (
            await db.execute(
                select(WorldIndicator).where(WorldIndicator.code == code)
            )
        ).scalar_one_or_none()
    hs, he = points[0][0], points[-1][0]
    name_ru = f"Население — {country.name_ru}"
    name_en = (
        "United States resident population"
        if provider == US_PROVIDER
        else "Brazil resident population"
    )
    seo_title = f"Население {country.name_ru} — статистика по годам"
    fields = {
        "code": code,
        "provider": provider,
        "dataset_id": dataset_id,
        "slice_json": {"series": series_id},
        "slice_hash": ref.slice_hash,
        "name_ru": name_ru,
        "name_en": name_en,
        "name_quality": "curated",
        "unit": unit,
        "unit_ru": unit_ru,
        "frequency": "annual",
        "category_ru": category_ru,
        "source": source_name,
        "source_url": source_url,
        "description": description,
        "methodology": methodology,
        "history_start": hs,
        "history_end": he,
        "points_count": len(points),
        "is_listed": True,
        "seo_title": seo_title,
        "seo_description": description,
        "seo_keywords": seo_keywords,
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


async def _mark_dataset_state(
    db: AsyncSession,
    *,
    provider: str,
    dataset_id: str,
    run_id: int,
    status: str,
    rows_fetched: int,
    error: str | None = None,
) -> None:
    if status == "ok":
        state = await db.get(WorldDatasetState, (provider, dataset_id))
        if state is None:
            state = WorldDatasetState(provider=provider, dataset_id=dataset_id)
            db.add(state)
        state.last_update_of_data = date.today()
        state.status = "ok"
        state.last_success_at = datetime.now(timezone.utc).replace(tzinfo=None)
        state.last_error = None
    db.add(
        WorldIngestDatasetLog(
            run_id=run_id,
            provider=provider,
            dataset_id=dataset_id,
            status=status,
            source_updated_at=date.today() if status == "ok" else None,
            rows_fetched=rows_fetched,
            error_message=error,
        )
    )


async def run_world_pop_ingest(
    *,
    country_codes: list[str] | None = None,
) -> dict[str, int]:
    """Загрузить население США и Бразилии в world_indicators.

    Ряды идемпотентны: повторный прогон перезаписывает значения и вычищает
    даты, которых во входе нет. Названия карточек формируются от публичного
    имени страны в БД; единица — человек.
    """
    started_at = datetime.now(timezone.utc).replace(tzinfo=None)
    async with async_session() as db:
        run = WorldIngestRun(source="world_pop", is_shadow=False, started_at=started_at)
        db.add(run)
        await db.commit()
        await db.refresh(run)
        run_id = run.id

        requested = (
            {code.strip().upper() for code in country_codes if code and code.strip()}
            if country_codes is not None
            else None
        )

        us_country = None
        br_country = None
        if requested is None or "US" in requested:
            us_country = await _country_by_code(db, "US")
        if requested is None or "BR" in requested:
            br_country = await _country_by_code(db, "BR")

        indicators = 0
        points_touched = 0
        failures: list[str] = []

        if us_country is not None:
            try:
                points = await asyncio.to_thread(
                    UsCensusPopAdapter().fetch_national_points
                )
                meta = _population_meta(
                    country_name_ru=us_country.name_ru, unit_ru=US_UNIT_RU
                )
                n_ind, n_pts = await _upsert_population_series(
                    db,
                    provider=US_PROVIDER,
                    dataset_id=US_DATASET_ID,
                    code="us-population-census",
                    series_id="us-population-census",
                    country=us_country,
                    source_name=US_SOURCE_NAME,
                    source_url=US_SOURCE_URL,
                    points=points,
                    unit="PERSONS",
                    unit_ru=US_UNIT_RU,
                    description=_US_DESCRIPTION,
                    methodology=_US_METHODOLOGY,
                    seo_keywords=_US_KEYWORDS,
                    category_ru=meta["category_ru"],
                    make_ref=lambda: make_census_series_ref(),
                )
                indicators += n_ind
                points_touched += n_pts
                await _mark_dataset_state(
                    db,
                    provider=US_PROVIDER,
                    dataset_id=US_DATASET_ID,
                    run_id=run_id,
                    status="ok",
                    rows_fetched=len(points),
                )
            except Exception as exc:  # noqa: BLE001
                failures.append("US")
                logger.exception("US Census population ingest failed")
                await db.rollback()
                await _mark_dataset_state(
                    db,
                    provider=US_PROVIDER,
                    dataset_id=US_DATASET_ID,
                    run_id=run_id,
                    status="error",
                    rows_fetched=0,
                    error=str(exc)[:2000],
                )
                await db.commit()

        if br_country is not None:
            try:
                points = await asyncio.to_thread(
                    IbgePopAdapter().fetch_national_points
                )
                meta = _population_meta(
                    country_name_ru=br_country.name_ru, unit_ru=BR_UNIT_RU
                )
                n_ind, n_pts = await _upsert_population_series(
                    db,
                    provider=BR_PROVIDER,
                    dataset_id=BR_DATASET_ID,
                    code="br-population-ibge",
                    series_id="br-population-ibge",
                    country=br_country,
                    source_name=BR_SOURCE_NAME,
                    source_url=BR_SOURCE_URL,
                    points=points,
                    unit="PERSONS",
                    unit_ru=BR_UNIT_RU,
                    description=_BR_DESCRIPTION,
                    methodology=_BR_METHODOLOGY,
                    seo_keywords=_BR_KEYWORDS,
                    category_ru=meta["category_ru"],
                    make_ref=lambda: make_ibge_series_ref(),
                )
                indicators += n_ind
                points_touched += n_pts
                await _mark_dataset_state(
                    db,
                    provider=BR_PROVIDER,
                    dataset_id=BR_DATASET_ID,
                    run_id=run_id,
                    status="ok",
                    rows_fetched=len(points),
                )
            except Exception as exc:  # noqa: BLE001
                failures.append("BR")
                logger.exception("IBGE population ingest failed")
                await db.rollback()
                await _mark_dataset_state(
                    db,
                    provider=BR_PROVIDER,
                    dataset_id=BR_DATASET_ID,
                    run_id=run_id,
                    status="error",
                    rows_fetched=0,
                    error=str(exc)[:2000],
                )
                await db.commit()

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        run = await db.get(WorldIngestRun, run_id)
        assert run is not None
        run.datasets_selected = 2
        run.datasets_succeeded = 2 - len(failures)
        run.datasets_failed = len(failures)
        run.status = "ok" if not failures else "partial"
        run.completed_at = now
        await db.commit()

    await bump_namespaces("world")
    return {
        "run_id": run_id,
        "indicators": indicators,
        "points_touched": points_touched,
        "failed": len(failures),
    }
