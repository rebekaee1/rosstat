"""Один региональный показатель по многим регионам — одна строка выдачи.

Без региона в запросе показатель («Средняя цена: яйца куриные») приходит строкой на каждый субъект:
десятки одинаковых названий по алфавиту. Здесь они сворачиваются в одну строку «Россия» со значением и
месяцем и списком регионов (``regional_group``): интерфейс показывает «ещё N регионов» и переход к каждому.
Порядок и состав остальных строк не меняются; если регион назван в запросе, строки остаются как есть.
"""

from __future__ import annotations

import logging
import re
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


# Свежесть (14.11.2026): у «Посевных площадей льна-долгунца» Воронежской области последнее значение 0,00 за 2010 год,
# а в выдаче он стоял выше рядов за 2024. Ряд со значением 0 и ряд, чьё последнее значение старше свежего в той же
# выдаче больше чем на STALE_YEARS лет, опускаются ниже — только между местами региональных строк со значением,
# порядок остальной выдачи и состав не меняются (ничего не выбрасывается).
STALE_YEARS = 3


def _latest_year(item: dict) -> int | None:
    latest = item.get("latest") or {}
    try:
        return int(str(latest.get("date") or "")[:4])
    except ValueError:
        return None


def demote_stale_region_rows(results: list[dict]) -> list[dict]:
    slots = [i for i, item in enumerate(results)
             if item.get("kind") == "region_indicator" and _latest_year(item) is not None]
    if len(slots) < 2:
        return results
    newest = max(_latest_year(results[i]) for i in slots)

    def stale(item: dict) -> bool:
        value = (item.get("latest") or {}).get("value")
        return value == 0 or newest - _latest_year(item) > STALE_YEARS

    rows = [results[i] for i in slots]
    ordered = [row for row in rows if not stale(row)] + [row for row in rows if stale(row)]
    if ordered == rows:
        return results
    out = list(results)
    for i, row in zip(slots, ordered):
        out[i] = row
    return out


# «Попробуйте, например» по разделу и региону (14.11.2026). Под «Ближайшим» для посевных площадей Воронежской
# области предлагались «Курс узбекского сума» и «Цены на яйца в Москве». Теперь — 2–3 других ряда того же раздела
# Росстата и региона: сначала из той же таблицы (общее начало `table_code`, «13.21» ближе к «13.21», чем «13.4»),
# только со свежим ненулевым значением (правило свежести выше). Без новых словарей.
SECTION_SUGGESTIONS = 3
_SECTION_CANDIDATES = 12
_SUGGESTION_NAME_MAX = 40


def _table_closeness(code_a: str | None, code_b: str | None) -> int:
    parts_a, parts_b = str(code_a or "").split("."), str(code_b or "").split(".")
    same = 0
    for left, right in zip(parts_a, parts_b):
        if left != right:
            break
        same += 1
    return same


async def section_suggestions(db: AsyncSession, item: dict, exclude: set[str], locale: str, *,
                              region_in_query: bool = False) -> list[dict[str, str]]:
    """2–3 соседа по разделу: `{"label", "query"}`. Запрос — всегда «название ряда + регион» (действие точное);
    подпись без региона, если регион уже назван в запросе (14.11.2026: на 390 px подсказка вставала в две строки)."""
    from app.data.i18n.region_indicators_en import REGION_INDICATORS_EN

    code, slug, place = item.get("code"), item.get("region_slug"), item.get("region_name")
    if not code or not slug or slug == "russia" or not place:
        return []
    base = (await db.execute(select(RegionIndicator.section_name, RegionIndicator.table_code)
                             .where(RegionIndicator.code == code))).first()
    if base is None:
        return []
    rows = (await db.execute(
        select(RegionIndicator.code, RegionIndicator.name, RegionIndicator.table_code)
        .where(RegionIndicator.section_name == base.section_name, RegionIndicator.is_listed.is_(True),
               RegionIndicator.code.notin_(exclude | {code}))
    )).all()

    def title(row) -> str:
        # Подсказка — короткий запрос: уточнение в скобках («(в весе после доработки)») не нужно, чтобы найти ряд,
        # и переносило подсказку на две строки на телефоне.
        name = (REGION_INDICATORS_EN.get(row.code) or {}).get("name") if locale == "en" else None
        return re.sub(r"\s*\([^)]*\)", "", name or row.name).strip()

    ranked = sorted((row for row in rows if len(title(row)) <= _SUGGESTION_NAME_MAX),
                    key=lambda row: (-_table_closeness(row.table_code, base.table_code), row.name, row.code))  # порядок один для ru и en
    found = []
    for row in ranked[:_SECTION_CANDIDATES]:
        latest = (await _latest_by_region(db, row.code, monthly=False, slugs=(slug,))).get(slug)
        if latest is None:
            latest = (await _latest_by_region(db, row.code, monthly=True, slugs=(slug,))).get(slug)
        if latest is not None:
            found.append((row, latest))
    shown_year = _latest_year(item)
    years = [int(latest[1][:4]) for _row, latest in found] + ([shown_year] if shown_year else [])
    if not years:
        return []
    newest = max(years)
    fresh = [row for row, latest in found if latest[0] != 0 and newest - int(latest[1][:4]) <= STALE_YEARS]
    return [{"label": title(row) if region_in_query else f"{title(row)} {place}", "query": f"{title(row)} {place}"}
            for row in fresh[:SECTION_SUGGESTIONS]]
