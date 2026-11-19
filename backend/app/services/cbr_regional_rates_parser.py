"""Ставки по вкладам и кредитам по регионам из DataService Банка России → ``region_monthly_data`` (19.11.2026).

Реестр рядов — ``app.data.cbr_regional_rates``. Запрос один на территорию и набор:
``/dataservice/data?publicationId&datasetId&measureId&y1&y2`` (без ``measureId`` ответ пустой); список территорий
набора — ``/dataservice/measures?datasetId``. Название территории сводится к slug сайта по справочнику ЕМИСС
(``emiss_dimnames.json``), таблице регионов и ``MEASURE_ALIASES``; незнакомое название пропускается с
предупреждением. Месяц берётся из ``dt`` («Сентябрь 2026»): поле ``date`` у ставок на месяц позже.
Значение 0 — кредитов не выдавали (так у валютной ипотеки), точка не пишется.

План: если хоть у одного ряда нет точек — вся история с 2019 года (≈120 запросов, пауза 0,3 с); иначе прошлый и
текущий год (ЦБ уточняет прошлые месяцы). Сбой одной территории не отменяет остальные; в конце прогона —
исключение для алерта. Запись — upsert ЕМИСС ``_upsert_monthly_points`` (порциями, guard ``value <> excluded``),
региональная блокировка, обновление границ лет, публикация кэша после commit.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import date
from typing import Callable

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.cache import publish_committed_regional_changes
from app.data import cbr_regional_rates as spec
from app.database import async_session
from app.models import Region, RegionIndicator, RegionMonthlyPoint
from app.services.cbr_dataservice_parser import MONTH_MAP
from app.services.emiss_regional_parser import _upsert_monthly_points, load_dimnames
from app.services.http_client import create_session
from app.services.regional_storage import acquire_regional_write_lock, update_regional_year_bounds

logger = logging.getLogger(__name__)

_PAUSE_S = 0.3
_ALERT_MUTE_S = 3 * 24 * 3600


def _get_json(path: str, params: dict) -> object:
    session = create_session()
    try:
        resp = session.get(f"{settings.cbr_base_url.rstrip('/')}/dataservice/{path}", params=params, timeout=60)
        resp.raise_for_status()
        return resp.json()
    finally:
        session.close()


def measure_slugs(measures: list[dict], names: dict[str, str]) -> dict[int, str]:
    """Территории набора → slug сайта; незнакомые названия — в журнал и мимо."""
    out: dict[int, str] = {}
    for m in measures:
        name = " ".join(str(m.get("name") or "").split())
        slug = spec.MEASURE_ALIASES.get(name) or names.get(name)
        if slug:
            out[int(m["id"])] = slug
        else:
            logger.warning("cbr_regional_rates: территория без slug: %s (%s)", name, m.get("id"))
    return out


def parse_month(dt: str) -> int | None:
    parts = (dt or "").strip().lower().split()
    if len(parts) == 2 and parts[0] in MONTH_MAP and parts[1].isdigit():
        return int(parts[1]) * 100 + MONTH_MAP[parts[0]]
    return None


def parse_rows(raw: list[dict], series: tuple[spec.RateSeries, ...]) -> list[tuple[str, int, float]]:
    """RawData одной территории → [(код ряда, YYYYMM, ставка)]; ноль и пустое пропускаются."""
    by_element = {s.element: s.code for s in series}
    out: dict[tuple[str, int], float] = {}
    for row in raw:
        code = by_element.get(row.get("element_id") or row.get("colId"))
        period = parse_month(str(row.get("dt") or ""))
        value = row.get("obs_val")
        if code is None or period is None or not isinstance(value, (int, float)) or not 0 < value < 100:
            continue
        out[(code, period)] = round(float(value), 4)
    return [(code, period, value) for (code, period), value in out.items()]


async def run_cbr_regional_rates_update(
    db: AsyncSession,
    *,
    get_json: Callable[[str, dict], object] | None = None,
    today: date | None = None,
    pause_s: float = _PAUSE_S,
) -> dict[str, int]:
    get = get_json or _get_json
    today = today or date.today()
    indicators = {
        ind.code: ind for ind in (await db.execute(
            select(RegionIndicator).where(RegionIndicator.code.in_([s.code for s in spec.SERIES]))
        )).scalars()
    }
    if len(indicators) < len(spec.SERIES):
        # Метаданные пишет seed_regional при старте; до него ряды ждут следующего прогона.
        logger.warning("cbr_regional_rates: нет метаданных %s",
                       sorted({s.code for s in spec.SERIES} - set(indicators)))
    regions = {slug: rid for slug, rid in (await db.execute(select(Region.slug, Region.id))).all()}
    names = {**load_dimnames(), **{name: slug for name, slug in (await db.execute(select(Region.name, Region.slug))).all()}}
    stats = {"requests": 0, "added": 0, "updated": 0}
    failed: list[str] = []
    for (pub, ds), series in spec.datasets().items():
        series = tuple(s for s in series if s.code in indicators)
        if not series:
            continue
        ids = [indicators[s.code].id for s in series]
        filled = (await db.execute(
            select(func.count(func.distinct(RegionMonthlyPoint.indicator_id)))
            .where(RegionMonthlyPoint.indicator_id.in_(ids))
        )).scalar() or 0
        year_from = spec.FIRST_YEAR if filled < len(ids) else today.year - 1
        try:
            measures = await asyncio.to_thread(get, "measures", {"datasetId": ds})
            territories = measure_slugs(list((measures or {}).get("measure") or []), names)
        except Exception as exc:  # noqa: BLE001 — один набор не отменяет остальные
            failed.append(f"{ds} measures: {exc}")
            continue
        for measure_id, slug in territories.items():
            if slug not in regions:
                continue
            try:
                payload = await asyncio.to_thread(get, "data", {
                    "publicationId": pub, "datasetId": ds, "measureId": measure_id,
                    "y1": year_from, "y2": today.year,
                })
            except Exception as exc:  # noqa: BLE001 — сбой территории: следующий прогон её повторит
                failed.append(f"{ds}/{measure_id}: {exc}")
                continue
            stats["requests"] += 1
            points = parse_rows(list((payload or {}).get("RawData") or []), series)
            values: dict[str, list[tuple[int, int, int, float]]] = {}
            for code, period, value in points:
                values.setdefault(code, []).append((indicators[code].id, regions[slug], period, value))
            if values:
                try:
                    await acquire_regional_write_lock(db)
                    added = updated = 0
                    for rows in values.values():
                        a, u = await _upsert_monthly_points(db, rows)
                        added, updated = added + a, updated + u
                    changed = await update_regional_year_bounds(db, {rows[0][0] for rows in values.values()})
                    await db.commit()
                except BaseException:
                    await db.rollback()
                    raise
                stats["added"] += added
                stats["updated"] += updated
                if added or updated or changed:
                    await publish_committed_regional_changes()
            if pause_s:
                await asyncio.sleep(pause_s)
    if failed:
        raise RuntimeError(f"не загружено запросов: {len(failed)} (остальные сохранены); первый: {failed[0]}")
    return stats


async def cbr_regional_rates_job() -> dict[str, int]:
    """Точка входа планировщика: ставки по вкладам и кредитам по регионам."""
    started = time.monotonic()
    try:
        async with async_session() as db:
            stats = await run_cbr_regional_rates_update(db)
        logger.info("cbr_regional_rates_job done in %.1fs: %s", time.monotonic() - started, stats)
        if stats["added"] or stats["updated"]:
            from app.services.alerting import send_telegram

            await send_telegram(
                "🏦 <b>Ставки по вкладам и кредитам по регионам обновлены</b> (Банк России)\n"
                f"Запросов: {stats['requests']}, новых точек: {stats['added']}, ревизий: {stats['updated']}",
                kind="etl_summary",
            )
        return stats
    except Exception as exc:
        logger.exception("cbr_regional_rates_job failed")
        from html import escape

        from app.services.alerting import alert_muted, exception_reason, send_telegram

        try:
            if not await alert_muted("cbr_regional_rates:failed", _ALERT_MUTE_S):
                await send_telegram(
                    "🔴 <b>Ставки по регионам (Банк России) не загрузились</b>\n"
                    f"Причина: {escape(exception_reason(exc, 300))}",
                    kind="etl_alert",
                )
        except Exception:  # noqa: BLE001 — алерт не должен маскировать исключение
            pass
        raise
