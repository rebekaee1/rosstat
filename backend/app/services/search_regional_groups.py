"""Один региональный показатель по многим регионам — одна строка выдачи.

Без региона в запросе показатель («Средняя цена: яйца куриные») приходит строкой на каждый субъект:
десятки одинаковых названий по алфавиту. Здесь они сворачиваются в одну строку «Россия» со значением и
месяцем и списком регионов (``regional_group``): интерфейс показывает «ещё N регионов» и переход к каждому.
Порядок и состав остальных строк не меняются; если регион назван в запросе, строки остаются как есть.
"""

from __future__ import annotations

import logging
from datetime import date

from sqlalchemy import and_, literal_column, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Region, RegionDataPoint, RegionIndicator, RegionMonthlyPoint
from app.services import site_paths as paths

logger = logging.getLogger(__name__)

# Полный список регионов со значениями — только у первых групп: полезно сразу, а ответ остаётся лёгким.
VALUED_GROUPS = 3
# Столицы в начале списка регионов: их ищут чаще всего.
_FIRST_SLUGS = ("moskva", "sankt-peterburg")


def _is_regional(item: dict) -> bool:
    return item.get("kind") == "region_indicator" and bool(item.get("region_slug"))


def group_regional_rows(rows: list[dict], *, has_regions: bool, locale: str) -> list[dict]:
    """Строки одного регионального показателя без названного региона → одна строка-группа на месте лучшей."""
    if has_regions:
        return rows
    members: dict[str, list[dict]] = {}
    for item in rows:
        if _is_regional(item):
            members.setdefault(item["code"], []).append(item)
    out, done = [], set()
    for item in rows:
        if not _is_regional(item) or len(members[item["code"]]) < 2:
            out.append(item)
            continue
        code = item["code"]
        if code in done:
            continue
        done.add(code)
        group = members[code]
        lead = dict(item)
        lead.update({
            "key": f"region-group:{code}",
            "region_slug": "russia",
            "region_name": "Russia" if locale == "en" else "Россия",
            "path": paths.region_rating(code),
            "navigation": "spa",
            "regional_group": {
                "count": len(group),
                "regions": _ordered_regions(group),
            },
        })
        out.append(lead)
    return out


def _ordered_regions(group: list[dict]) -> list[dict]:
    entries = [{"slug": item["region_slug"], "name": item.get("region_name") or item["region_slug"],
        "path": item["path"], "navigation": item.get("navigation", "spa")} for item in group]
    by_name = sorted(entries, key=lambda entry: str(entry["name"]).casefold())
    first = [entry for slug in _FIRST_SLUGS for entry in by_name if entry["slug"] == slug]
    return first + [entry for entry in by_name if entry not in first]


def _finite(column):
    return and_(column.is_not(None), column > literal_column("-1e30"), column < literal_column("1e30"))


async def _latest_by_region(db: AsyncSession, code: str, *, monthly: bool,
        slugs: tuple[str, ...] | None = None) -> dict[str, tuple[float, str]]:
    """Последнее значение показателя по каждому субъекту и по России: slug → (значение, дата)."""
    point = RegionMonthlyPoint if monthly else RegionDataPoint
    period_column = point.month if monthly else point.year
    indicator = select(RegionIndicator.id).where(RegionIndicator.code == code).scalar_subquery()

    def last(column):
        # Последняя конечная точка региона: одно чтение по индексу (показатель, регион, период).
        # Оконная функция читала все точки показателя ради одного значения на регион.
        return select(column).where(point.indicator_id == indicator, point.region_id == Region.id,
            _finite(point.value)).order_by(period_column.desc()).limit(1).scalar_subquery()

    query = select(Region.slug, last(period_column), last(point.value))
    if slugs:
        query = query.where(Region.slug.in_(slugs))
    rows = (await db.execute(query)).all()
    out = {}
    for slug, period, value in rows:
        if period is None:
            continue
        period = int(period)
        day = date(period // 100, period % 100, 1) if monthly else date(period, 1, 1)
        out[slug] = (float(value), day.isoformat())
    return out


async def attach_group_values(db: AsyncSession, results: list[dict]) -> None:
    """Значение и месяц у строки-группы («Россия») и у регионов её списка; при сбое строка остаётся без чисел."""
    valued = 0
    for item in results:
        group = item.get("regional_group")
        if not group or valued >= VALUED_GROUPS:
            continue
        valued += 1
        try:
            latest = await _latest_by_region(db, item["code"], monthly=item.get("frequency") == "monthly")
        except Exception:
            logger.warning("regional group values skipped", exc_info=True)
            continue
        russia = latest.get("russia")
        if russia:
            item["latest"] = {"value": round(russia[0], 4), "date": russia[1]}
        for entry in group["regions"]:
            found = latest.get(entry["slug"])
            if found:
                entry["value"], entry["date"] = round(found[0], 4), found[1]


# Явный регион в запросе («аренда квартиры спб»): число показываем у первых строк, как у группы.
VALUED_REGION_ROWS = 6


async def attach_region_row_values(db: AsyncSession, results: list[dict]) -> None:
    """Значение и месяц у строк одного региона с названным регионом; при сбое строка остаётся без чисел."""
    head = [item for item in results[:VALUED_REGION_ROWS]
        if _is_regional(item) and not item.get("regional_group") and not item.get("latest")]
    for item in head:
        try:
            found = (await _latest_by_region(db, item["code"], monthly=item.get("frequency") == "monthly",
                slugs=(item["region_slug"],))).get(item["region_slug"])
        except Exception:
            logger.warning("region row value skipped", exc_info=True)
            continue
        if found:
            item["latest"] = {"value": round(found[0], 4), "date": found[1]}
