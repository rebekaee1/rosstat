"""Кредиты физлицам и ипотека по регионам из DataService Банка России (реестр — ``app.data.cbr_household_credit``).

Пишет в ``region_monthly_data`` теми же механизмами, что помесячные ряды ЕМИСС: upsert с guard
``value <> excluded.value`` (ADR-0002) порциями, advisory-блокировка регионального контура, границы истории
в метаданных, публикация кэша после commit.

Регион в DataService — «measure» набора; запрос отдаёт один регион за все годы сразу (несколько регионов одним
запросом API не принимает — живая проверка 19.11.2026). Поэтому сначала спрашивается Россия (measure 22): если
последний месяц источника уже лежит в базе — набор пропускается целиком (одна страница вместо ~96). Иначе
идут все позиции набора, с года самой поздней сохранённой точки минус один (ревизии), а при пустой базе — с 2019
года. Сервер Timeweb DataService отвечает (200, 19.11.2026), обход не нужен.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import date
from math import isfinite
from typing import Callable

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import publish_committed_regional_changes
from app.data.cbr_household_credit import FIRST_YEAR, MEASURE_SLUGS, RUSSIA_MEASURE, SERIES, CreditSeries
from app.models import Region, RegionIndicator, RegionMonthlyPoint
from app.services.cbr_dataservice_parser import CBR_DATASERVICE_URL, _parse_ds_date
from app.services.emiss_regional_parser import _upsert_monthly_points, load_dimnames
from app.services.regional_storage import acquire_regional_write_lock, update_regional_year_bounds

logger = logging.getLogger(__name__)

_PAUSE_BETWEEN_REQUESTS = 0.25
_MEASURES_URL = CBR_DATASERVICE_URL.rsplit("/", 1)[0] + "/measures"


def _get_json(url: str, params: dict) -> dict | list:
    from app.services.http_client import create_session

    session = create_session()
    try:
        resp = session.get(url, params=params, timeout=60)
        resp.raise_for_status()
        return resp.json()
    finally:
        session.close()


async def fetch_measures(dataset: int, *, get_json: Callable = _get_json) -> list[tuple[int, str]]:
    payload = await asyncio.to_thread(get_json, _MEASURES_URL, {"datasetId": dataset})
    rows = payload.get("measure") if isinstance(payload, dict) else None
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"DataService {dataset}: пустой список регионов")
    return [(int(r["id"]), str(r.get("name") or "").strip()) for r in rows]


async def fetch_series(
    s: CreditSeries, measure: int, year_from: int, year_to: int, *, get_json: Callable = _get_json,
) -> dict[int, float]:
    """Один регион набора → {YYYYMM: значение} в единицах ряда региона."""
    payload = await asyncio.to_thread(get_json, CBR_DATASERVICE_URL, {
        "publicationId": s.publication, "datasetId": s.dataset, "measureId": measure,
        "y1": year_from, "y2": year_to,
    })
    return parse_series(s, payload)


def parse_series(s: CreditSeries, payload: dict) -> dict[int, float]:
    rows = payload.get("RawData") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        raise ValueError(f"DataService {s.dataset}: нет RawData")
    out: dict[int, float] = {}
    for row in rows:
        if (row.get("element_id") or row.get("colId")) != s.element:
            continue
        raw = row.get("obs_val")
        if raw is None:
            continue
        try:
            value = float(raw) / s.regional_divisor
        except (TypeError, ValueError):
            continue
        if not isfinite(value) or value < 0:
            continue
        if value == 0 and s.dataset == 48:
            continue  # срок «0» — за месяц в регионе не было ипотек в рублях; это пропуск, а не значение
        d = _parse_ds_date(row.get("dt", ""), row.get("date"), -1)
        if d is None:
            continue
        out[d.year * 100 + d.month] = round(value, 4)
    return out


def measure_slugs(measures: list[tuple[int, str]], dimnames: dict[str, str],
                  region_names: dict[str, str]) -> tuple[dict[int, str], list[str]]:
    """measure → slug региона; названия, которых нет в справочниках, — во второй список (не пишутся)."""
    by_name = {k.casefold(): v for k, v in dimnames.items()}
    by_name.update({k.casefold(): v for k, v in region_names.items()})
    out: dict[int, str] = {}
    unknown: list[str] = []
    for mid, name in measures:
        slug = MEASURE_SLUGS.get(mid) or (by_name.get(name.casefold()) if mid != RUSSIA_MEASURE else "russia")
        if slug:
            out[mid] = slug
        else:
            unknown.append(name)
    return out, unknown


async def run_series_update(
    db: AsyncSession, s: CreditSeries, *, get_json: Callable = _get_json, today: date | None = None,
    dimnames: dict[str, str] | None = None, pause: float = _PAUSE_BETWEEN_REQUESTS,
) -> dict[str, int]:
    today = today or date.today()
    indicator = (await db.execute(
        select(RegionIndicator).where(RegionIndicator.code == s.regional_code)
    )).scalar_one_or_none()
    if indicator is None:
        raise RuntimeError(f"DataService {s.dataset}: нет метаданных {s.regional_code} (сид регионов не прошёл)")
    regions = {slug: (rid, name) for slug, rid, name in (await db.execute(
        select(Region.slug, Region.id, Region.name))).all()}
    russia_id = regions.get("russia", (None,))[0]
    last_any = (await db.execute(
        select(func.max(RegionMonthlyPoint.month)).where(RegionMonthlyPoint.indicator_id == indicator.id)
    )).scalar_one_or_none()
    last_rf = (await db.execute(
        select(func.max(RegionMonthlyPoint.month)).where(
            RegionMonthlyPoint.indicator_id == indicator.id, RegionMonthlyPoint.region_id == russia_id)
    )).scalar_one_or_none()
    year_from = FIRST_YEAR if last_any is None else max(FIRST_YEAR, int(last_any) // 100 - 1)

    stats = {"requests": 1, "points": 0, "added": 0, "updated": 0, "skipped": 0, "unknown": 0}
    russia = await fetch_series(s, RUSSIA_MEASURE, year_from, today.year, get_json=get_json)
    if russia and last_rf is not None and max(russia) <= int(last_rf):
        stats["skipped"] = 1
        return stats  # нового месяца у ЦБ нет — регионы не спрашиваем

    measures = await fetch_measures(s.dataset, get_json=get_json)
    stats["requests"] += 1
    slugs, unknown = measure_slugs(
        measures, dimnames if dimnames is not None else load_dimnames(),
        {name: slug for slug, (_rid, name) in regions.items()},
    )
    stats["unknown"] = len(unknown)
    if unknown:
        logger.warning("cbr_regional_credit %s: нет в справочнике регионов: %s", s.dataset, unknown[:5])

    values: list[tuple[int, int, int, float]] = []
    for mid, slug in slugs.items():
        if slug not in regions:
            continue
        if mid == RUSSIA_MEASURE:
            points = russia
        else:
            await asyncio.sleep(pause)
            points = await fetch_series(s, mid, year_from, today.year, get_json=get_json)
            stats["requests"] += 1
        rid = regions[slug][0]
        values += [(indicator.id, rid, period, value) for period, value in points.items()]
    stats["points"] = len(values)
    try:
        await acquire_regional_write_lock(db)
        added, updated = await _upsert_monthly_points(db, values)
        changed_meta = await update_regional_year_bounds(db, {indicator.id}) if values else 0
        await db.commit()
    except BaseException:
        await db.rollback()
        raise
    stats["added"], stats["updated"] = added, updated
    if added or updated or changed_meta:
        await publish_committed_regional_changes()
    return stats


_ALERT_MUTE_S = 3 * 24 * 3600


async def cbr_regional_credit_job() -> dict[str, dict[str, int]]:
    """Точка входа планировщика: ряды по очереди, сбой одного не останавливает остальные."""
    from app.database import async_session

    started = time.monotonic()
    stats: dict[str, dict[str, int]] = {}
    failures: list[str] = []
    for s in SERIES:
        if not s.regional_code:
            continue
        try:
            async with async_session() as db:
                stats[s.regional_code] = await run_series_update(db, s)
        except Exception as exc:  # noqa: BLE001 — один ряд не должен ронять остальные
            logger.exception("cbr_regional_credit %s failed", s.regional_code)
            from app.services.alerting import exception_reason

            failures.append(f"{s.regional_code}: {exception_reason(exc, 160)}")
    logger.info("cbr_regional_credit_job done in %.1fs: %s", time.monotonic() - started, stats)
    if failures:
        from html import escape

        from app.services.alerting import alert_muted, send_telegram

        try:
            if not await alert_muted("cbr_regional_credit:failed", _ALERT_MUTE_S):
                await send_telegram(
                    "🔴 <b>Кредиты и ипотека по регионам (ЦБ) не обновились</b>\n" + escape("; ".join(failures)),
                    kind="etl_alert",
                )
        except Exception:  # noqa: BLE001 — алерт не должен маскировать результат
            pass
    return stats
