"""Загрузка рядов BIS, Всемирного банка и МОТ в `world_indicators`/`world_data_points` (19.11.2026).

Описание рядов и разбор ответов — `world_intl_sources`. Здесь: запрос к издателю, запись рядов
стран каталога `world_countries` порциями, копия последних точек (ADR-0037), состояние набора и
журнал прогона. Повторный прогон идемпотентен; с пустой базы загружается вся история.

Национальный ряд важнее (ADR-0012): если у страны есть живой публичный национальный ряд того же
смысла (`world_concept_national`), международный ряд пишется, но не показывается в каталоге страны
(`is_listed=false`) — он остаётся запасом и сам станет публичным, если национальный ряд перестанет
обновляться (так 19.11 у Индии: ставка репо Резервного банка недоступна из-за рубежа).

Запуск вручную::

    docker compose exec backend python -m app.services.world_intl_ingest [bis|worldbank|ilo]
"""

from __future__ import annotations

import asyncio
import logging
import sys
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import bump_namespaces
from app.data.world_concept_national import NATIONAL_CONCEPT_INDICATOR_CODES
from app.database import async_session
from app.models import (
    WorldCountry,
    WorldDataPoint,
    WorldDatasetState,
    WorldIndicator,
    WorldIngestDatasetLog,
    WorldIngestRun,
)
from app.services.imf_weo_adapter import weo_iso3_for
from app.services.world_intl_sources import (
    BIS_DATASET,
    BIS_PROVIDER,
    BIS_URL,
    ILO_DATASET,
    ILO_PROVIDER,
    ILO_URL,
    SERIES,
    WB_DATASET,
    WB_PROVIDER,
    WB_URL,
    IntlSeries,
    bis_area,
    dedupe_points,
    ilo_request,
    indicator_code,
    parse_bis_csv,
    parse_ilo_csv,
    parse_wb_json,
)
from app.services.world_source_adapter import WorldSeriesRef

logger = logging.getLogger(__name__)

PROVIDERS = (BIS_PROVIDER, WB_PROVIDER, ILO_PROVIDER)
DATASET_BY_PROVIDER = {BIS_PROVIDER: BIS_DATASET, WB_PROVIDER: WB_DATASET, ILO_PROVIDER: ILO_DATASET}
# asyncpg: не больше 32 767 параметров на запрос; точка — 3 параметра.
POINTS_CHUNK = 5000
# Национальный ряд считается живым, если последняя точка не старше этого срока.
NATIONAL_FRESH_DAYS = 400
# Месячный международный ряд без точек за этот срок считается прекращённым.
MONTHLY_STALE_DAYS = 730
WB_COUNTRY_CHUNK = 40
TIMEOUT_SEC = 90


def _get_text(url: str) -> str:
    from app.services.http_client import create_session

    session = create_session(timeout=TIMEOUT_SEC)
    response = session.get(url, timeout=TIMEOUT_SEC, headers={"Accept": "text/csv, application/json"})
    response.raise_for_status()
    response.encoding = response.encoding or "utf-8"
    return response.text


def fetch_provider(provider: str, iso2_codes: list[str], *, today: date | None = None) -> dict[tuple[str, str], list]:
    """Сеть: {(суффикс ряда, ISO-2): точки} для стран каталога."""
    today = today or date.today()
    out: dict[tuple[str, str], list] = {}
    series = [item for item in SERIES if item.provider == provider]
    if provider == BIS_PROVIDER:
        areas = {bis_area(code): code for code in iso2_codes}
        by_area = parse_bis_csv(_get_text(BIS_URL.format(areas="+".join(sorted(areas)))))
        for area, points in by_area.items():
            if area in areas:
                out[(series[0].code_suffix, areas[area])] = points
        return out
    iso3_to_iso2 = {weo_iso3_for(code): code for code in iso2_codes if weo_iso3_for(code)}
    iso3_list = sorted(iso3_to_iso2)
    for item in series:
        if provider == WB_PROVIDER:
            for start in range(0, len(iso3_list), WB_COUNTRY_CHUNK):
                chunk = iso3_list[start:start + WB_COUNTRY_CHUNK]
                url = WB_URL.format(iso3=";".join(chunk), code=item.series_id, year=today.year)
                for iso3, points in parse_wb_json(_get_text(url)).items():
                    if iso3 in iso3_to_iso2:
                        out[(item.code_suffix, iso3_to_iso2[iso3])] = points
        elif provider == ILO_PROVIDER:
            indicator, classif = ilo_request(item)
            url = ILO_URL.format(indicator=indicator, iso3="+".join(iso3_list), classif=classif)
            parsed = parse_ilo_csv(_get_text(url), classif=classif, last_closed_year=today.year - 1)
            for iso3, points in parsed.items():
                if iso3 in iso3_to_iso2:
                    out[(item.code_suffix, iso3_to_iso2[iso3])] = points
    return out


async def _live_national_codes(db: AsyncSession, today: date) -> set[str]:
    """Коды национальных рядов crosswalk, которые публичны и обновлялись за `NATIONAL_FRESH_DAYS`."""
    codes = sorted({code for mapping in NATIONAL_CONCEPT_INDICATOR_CODES.values() for code in mapping.values()})
    if not codes:
        return set()
    rows = (await db.execute(
        select(WorldIndicator.code).where(
            WorldIndicator.code.in_(codes),
            WorldIndicator.is_listed.is_(True),
            WorldIndicator.points_count > 1,
            WorldIndicator.history_end >= today - timedelta(days=NATIONAL_FRESH_DAYS),
        )
    )).scalars().all()
    return set(rows)


def is_live(series: IntlSeries, points: list[tuple[date, float]], today: date) -> bool:
    """Месячный ряд, который издатель перестал вести, не заводится.

    У BIS ставки стран еврозоны заканчиваются 1998–2000 годом (дальше — ставка ЕЦБ, у BIS это отдельный ряд
    «еврозона»), у Хорватии — июлем 2022: карточка «Ключевая ставка» Германии с последним значением 1998 года
    вводит в заблуждение. Годовые ряды обследований (Джини, бедность) выходят раз в несколько лет — не отсекаются.
    """
    if series.frequency != "monthly" or not points:
        return bool(points)
    return points[-1][0] >= today - timedelta(days=MONTHLY_STALE_DAYS)


def listed_for(series: IntlSeries, iso2: str, live_national: set[str]) -> bool:
    """Международный ряд публичен, если у страны нет живого национального ряда того же смысла."""
    national = (NATIONAL_CONCEPT_INDICATOR_CODES.get(series.concept_slug) or {}).get(iso2.upper())
    return not (national and national in live_national)


async def _write_points(db: AsyncSession, indicator_id: int, points: list[tuple[date, float]]) -> int:
    touched = 0
    for start in range(0, len(points), POINTS_CHUNK):
        chunk = points[start:start + POINTS_CHUNK]
        stmt = pg_insert(WorldDataPoint).values(
            [{"indicator_id": indicator_id, "date": when, "value": value} for when, value in chunk]
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_world_data_point",
            set_={"value": stmt.excluded.value},
            where=WorldDataPoint.__table__.c.value.is_distinct_from(stmt.excluded.value),
        ).returning(WorldDataPoint.id)
        touched += len((await db.execute(stmt)).fetchall())
    keep = [when for when, _ in points]
    await db.execute(
        WorldDataPoint.__table__.delete().where(
            WorldDataPoint.indicator_id == indicator_id,
            WorldDataPoint.date.not_in(keep),
        )
    )
    return touched


async def upsert_series(
    db: AsyncSession,
    *,
    country: WorldCountry,
    series: IntlSeries,
    points: list[tuple[date, float]],
    is_listed: bool,
) -> int:
    """Карточка ряда и его точки; возвращает число новых/изменённых точек."""
    points = dedupe_points(points)
    if not points:
        return 0
    ref = WorldSeriesRef(
        provider=series.provider,
        dataset_id=series.dataset_id,
        series_id=series.series_id,
        country_code=country.code,
        frequency=series.frequency,
        unit_code=series.unit,
    )
    code = indicator_code(country.code, series)
    existing = (await db.execute(select(WorldIndicator).where(WorldIndicator.code == code))).scalar_one_or_none()
    desc = series.description_ru
    fields = {
        "code": code,
        "provider": series.provider,
        "dataset_id": series.dataset_id,
        "slice_json": {"series": series.series_id},
        "slice_hash": ref.slice_hash,
        "name_ru": series.name_ru,
        "name_en": series.name_en,
        "name_quality": "curated",
        "unit": series.unit,
        "unit_ru": series.unit_ru,
        "frequency": series.frequency,
        "category_ru": series.category_ru,
        "source": series.source_ru,
        "source_url": series.source_url,
        "description": desc,
        "methodology": series.methodology_ru,
        "is_listed": is_listed,
        "seo_title": f"{series.name_ru} — {country.name_ru}",
        "seo_description": desc,
        "seo_keywords": f"{series.name_ru} {country.name_ru}, " + series.keywords_ru.format(country=country.name_ru),
    }
    if existing is None:
        indicator = WorldIndicator(country_id=country.id, points_count=0, **fields)
        db.add(indicator)
        await db.flush()
    else:
        indicator = existing
        for key, value in fields.items():
            setattr(indicator, key, value)
        indicator.country_id = country.id
        await db.flush()
    touched = await _write_points(db, indicator.id, points)
    count, start, end = (await db.execute(
        select(func.count(WorldDataPoint.id), func.min(WorldDataPoint.date), func.max(WorldDataPoint.date))
        .where(WorldDataPoint.indicator_id == indicator.id)
    )).one()
    indicator.points_count = int(count or 0)
    indicator.history_start = start
    indicator.history_end = end
    from app.services.world_latest_points import sync_latest_points

    await sync_latest_points(db, [indicator.id])
    return touched


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def run_provider_ingest(provider: str, *, today: date | None = None) -> dict:
    """Один издатель: сеть → запись всех стран каталога одной транзакцией → состояние и журнал."""
    today = today or date.today()
    dataset_id = DATASET_BY_PROVIDER[provider]
    async with async_session() as db:
        run = WorldIngestRun(source=provider, is_shadow=False, started_at=_now(), datasets_selected=1)
        db.add(run)
        await db.commit()
        await db.refresh(run)
        run_id = run.id
        countries = {
            row.code: row for row in (await db.execute(select(WorldCountry))).scalars().all()
        }
        try:
            fetched = await asyncio.to_thread(fetch_provider, provider, sorted(countries), today=today)
            live_national = await _live_national_codes(db, today)
            series_rows = touched = 0
            for (suffix, iso2), points in sorted(fetched.items()):
                series = next(item for item in SERIES if item.code_suffix == suffix)
                country = countries.get(iso2)
                if country is None or not is_live(series, points, today):
                    continue
                touched += await upsert_series(
                    db, country=country, series=series, points=points,
                    is_listed=listed_for(series, iso2, live_national),
                )
                series_rows += 1
            if not series_rows:
                raise RuntimeError(f"{provider}: издатель не вернул ни одного ряда стран каталога")
            state = await db.get(WorldDatasetState, (provider, dataset_id))
            if state is None:
                state = WorldDatasetState(provider=provider, dataset_id=dataset_id)
                db.add(state)
            state.last_update_of_data = today
            state.status = "ok"
            state.last_success_at = _now()
            state.last_error = None
            db.add(WorldIngestDatasetLog(
                run_id=run_id, provider=provider, dataset_id=dataset_id, status="ok",
                source_updated_at=today, rows_fetched=touched,
            ))
            run = await db.get(WorldIngestRun, run_id)
            run.datasets_succeeded = 1
            run.status = "ok"
            run.completed_at = _now()
            await db.commit()
        except Exception as exc:  # noqa: BLE001 — журнал прогона и проброс
            error = str(exc)[:2000]
            logger.exception("world intl ingest failed: %s", provider)
            await db.rollback()
            async with async_session() as err_db:
                failed = await err_db.get(WorldIngestRun, run_id)
                if failed is not None:
                    failed.status = "failed"
                    failed.completed_at = _now()
                    failed.error_message = error
                    failed.datasets_failed = 1
                    err_db.add(WorldIngestDatasetLog(
                        run_id=run_id, provider=provider, dataset_id=dataset_id, status="error",
                        error_message=error,
                    ))
                    await err_db.commit()
            raise
    return {"provider": provider, "run_id": run_id, "series": series_rows, "points_touched": touched}


async def run_world_intl_ingest(providers: tuple[str, ...] = PROVIDERS) -> dict:
    """Ночная задача: издатели по очереди; сбой одного не останавливает остальных."""
    results: dict[str, object] = {}
    for provider in providers:
        try:
            results[provider] = await run_provider_ingest(provider)
        except Exception as exc:  # noqa: BLE001 — сбой одного издателя виден в журнале прогона
            results[provider] = {"error": str(exc)[:300]}
    await bump_namespaces("world", "world-catalog", "ssr-world")
    logger.info("world intl ingest: %s", results)
    return results


if __name__ == "__main__":
    chosen = tuple(arg for arg in sys.argv[1:] if arg in PROVIDERS) or PROVIDERS
    print(asyncio.run(run_world_intl_ingest(chosen)))
