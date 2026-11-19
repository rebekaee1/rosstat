"""Малый и средний бизнес по регионам помесячно из реестра МСП ФНС → ``region_monthly_data`` (19.11.2026).

Реестр рядов — ``app.data.fns_msp``. Запись — общими средствами регионального контура, как у зарплат и цен ЕМИСС:
``_upsert_monthly_points`` (ON CONFLICT с guard ``value <> excluded.value``, порциями), региональная
advisory-блокировка и границы истории в одной транзакции, публикация кэша после commit.

Прогон: страница статистики → список дат сводок; запрашиваются даты, месяца которых ещё нет у ряда
``msp-chislo``, и две последние (ФНС уточняет сводку задним числом). Первая загрузка — вся история (124 запроса
с паузой 0,5 с, ~3 МБ ответов); дальше — 2–3 запроса в месяц. Одна сводка — все семь рядов сразу.

Незнакомое название территории считается в ``unknown_territories`` и не роняет прогон; ответ без строки России или
без единой точки — смена формата (``FnsMspFormatError``).
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from typing import Callable

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import publish_committed_regional_changes
from app.data.fns_msp import SERIES, STAT_JSON, STAT_PAGE, TERRITORY_ALIASES, TERRITORY_SKIP
from app.database import async_session
from app.models import Region, RegionIndicator, RegionMonthlyPoint
from app.services.emiss_regional_parser import _upsert_monthly_points, load_dimnames
from app.services.regional_storage import acquire_regional_write_lock, update_regional_year_bounds

logger = logging.getLogger(__name__)

_PAUSE_S = 0.5
_REVISE_LAST = 2
_ALERT_MUTE_S = 3 * 24 * 3600
_OPTION_RE = re.compile(r'<option value="(\d{2})\.(\d{2})\.(\d{4})"')


class FnsMspFormatError(ValueError):
    """Ответ ФНС пришёл, но разобрать его нельзя — смена формата."""


def parse_dates(page_html: str) -> list[str]:
    """Страница статистики → даты сводок «ДД.ММ.ГГГГ» по возрастанию."""
    seen = {(int(y), int(m), int(d)) for d, m, y in _OPTION_RE.findall(page_html)}
    return [f"{d:02d}.{m:02d}.{y}" for y, m, d in sorted(seen)]


def period_of(stat_date: str) -> int:
    d, m, y = stat_date.split(".")
    return int(y) * 100 + int(m)


def territory_slugs(dimnames: dict[str, str] | None = None) -> dict[str, str]:
    out = dict(dimnames if dimnames is not None else load_dimnames())
    out.update(TERRITORY_ALIASES)
    return out


def parse_summary(
    rows: list, period: int, slugs: dict[str, str],
) -> tuple[list[tuple[str, str, int, float]], set[str]]:
    """Ответ ``statistics-proc.json`` → [(код ряда, slug, YYYYMM, значение)] и незнакомые территории."""
    if not isinstance(rows, list) or not rows:
        raise FnsMspFormatError("ФНС МСП: пустой ответ")
    points: list[tuple[str, str, int, float]] = []
    unknown: set[str] = set()
    has_russia = False
    for row in rows:
        name = str(row.get("cnt_name") or "").strip()
        if row.get("cnt_level") == 2:
            slug, has_russia = "russia", True
        elif name in TERRITORY_SKIP:
            continue
        else:
            slug = slugs.get(name)
            if not slug:
                unknown.add(name)
                continue
        for series in SERIES:
            values = [row.get(f) for f in series.fields]
            if any(not isinstance(v, (int, float)) or isinstance(v, bool) for v in values):
                continue
            total = float(sum(values))
            # Работники: в первых сводках 2016 года поле нулевое — это «нет данных», а не ноль работников.
            if total <= 0 and series.code == "msp-rabotniki":
                continue
            points.append((series.code, slug, period, total))
    if not has_russia or not points:
        raise FnsMspFormatError(f"ФНС МСП {period}: нет строки России или ни одной точки")
    return points, unknown


def _fetch_page() -> str:
    from app.services.http_client import create_session

    session = create_session()
    try:
        r = session.get(STAT_PAGE, timeout=30)
        r.raise_for_status()
        return r.text
    finally:
        session.close()


def _fetch_summary(stat_date: str) -> list:
    from app.services.http_client import create_session

    session = create_session()
    try:
        r = session.post(STAT_JSON, data={"statDate": stat_date}, timeout=60)
        r.raise_for_status()
        return r.json()
    finally:
        session.close()


def dates_to_fetch(all_dates: list[str], have: set[int]) -> list[str]:
    """Даты без месяца в базе плюс последние ``_REVISE_LAST`` (уточнения задним числом)."""
    missing = [d for d in all_dates if period_of(d) not in have]
    tail = all_dates[-_REVISE_LAST:]
    return sorted(set(missing) | set(tail), key=period_of)


async def run_fns_msp_update(
    db: AsyncSession,
    *,
    fetch_page: Callable[[], str] | None = None,
    fetch_summary: Callable[[str], list] | None = None,
    pause_s: float = _PAUSE_S,
) -> dict[str, int]:
    fetch_page = fetch_page or _fetch_page
    fetch_summary = fetch_summary or _fetch_summary
    indicators = {
        ind.code: ind for ind in (await db.execute(
            select(RegionIndicator).where(RegionIndicator.code.in_([s.code for s in SERIES]))
        )).scalars()
    }
    stats = {"dates": 0, "added": 0, "updated": 0, "unknown_territories": 0, "failed": 0}
    anchor = indicators.get(SERIES[0].code)
    if anchor is None:
        # Метаданные приходят из indicators.json при старте (seed_regional): до него прогон пропускается.
        logger.warning("fns_msp: нет метаданных показателей, пропуск")
        return stats
    regions = {slug: rid for slug, rid in (await db.execute(select(Region.slug, Region.id))).all()}
    have = set((await db.execute(
        select(func.distinct(RegionMonthlyPoint.month)).where(RegionMonthlyPoint.indicator_id == anchor.id)
    )).scalars())
    all_dates = parse_dates(await asyncio.to_thread(fetch_page))
    if not all_dates:
        raise FnsMspFormatError("ФНС МСП: на странице нет списка дат сводок")
    slugs = territory_slugs()
    unknown_all: set[str] = set()
    for stat_date in dates_to_fetch(all_dates, have):
        try:
            rows = await asyncio.to_thread(fetch_summary, stat_date)
            points, unknown = parse_summary(rows, period_of(stat_date), slugs)
        except FnsMspFormatError as exc:
            logger.warning("fns_msp %s: %s", stat_date, exc)
            stats["failed"] += 1
            continue
        unknown_all |= unknown
        values = [
            (indicators[code].id, regions[slug], period, value)
            for code, slug, period, value in points
            if code in indicators and slug in regions
        ]
        try:
            await acquire_regional_write_lock(db)
            added, updated = await _upsert_monthly_points(db, values) if values else (0, 0)
            changed = await update_regional_year_bounds(db, {ind.id for ind in indicators.values()})
            await db.commit()
        except BaseException:
            await db.rollback()
            raise
        if added or updated or changed:
            await publish_committed_regional_changes()
        stats["dates"] += 1
        stats["added"] += added
        stats["updated"] += updated
        if pause_s:
            await asyncio.sleep(pause_s)
    stats["unknown_territories"] = len(unknown_all)
    if unknown_all:
        logger.warning("fns_msp: незнакомые территории %s", sorted(unknown_all)[:5])
    return stats


async def fns_msp_job() -> dict[str, int]:
    """Точка входа планировщика."""
    started = time.monotonic()
    try:
        async with async_session() as db:
            stats = await run_fns_msp_update(db)
        if stats["failed"] or stats["unknown_territories"]:
            from app.services.alerting import alert_muted, send_telegram

            if not await alert_muted("fns_msp:partial", _ALERT_MUTE_S):
                await send_telegram(
                    "🟡 <b>Малый бизнес по регионам (реестр МСП ФНС): обновлено не всё</b> — "
                    f"сводок без разбора: {stats['failed']}, незнакомых территорий: {stats['unknown_territories']}.",
                    kind="etl_alert",
                )
        logger.info("fns_msp_job done in %.1fs: %s", time.monotonic() - started, stats)
        return stats
    except Exception as exc:
        logger.exception("fns_msp_job failed")
        from html import escape

        from app.services.alerting import alert_muted, exception_reason, send_telegram

        try:
            if not await alert_muted("fns_msp:failed", _ALERT_MUTE_S):
                await send_telegram(
                    "🔴 <b>Загрузка малого бизнеса по регионам (реестр МСП ФНС) упала</b>\n"
                    f"Причина: {escape(exception_reason(exc, 300))}",
                    kind="etl_alert",
                )
        except Exception:  # noqa: BLE001 — алерт не должен маскировать исключение
            pass
        raise

