"""Additive presentation fields for the first search rows: latest stored value and a short trend.

Runs after retrieval and ranking, so it can never reorder, drop or add a candidate.
Only rows that stand for one stored series of their own (federal `Indicator` and
world `WorldIndicator`) are enriched; regional and territory rows are left as is.
The numbers are the series' own last stored points (no derived values, no
forecast), read in at most two bounded queries for the first few rows.
"""

from __future__ import annotations

from sqlalchemy import and_, func, literal_column, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Indicator, IndicatorData, WorldDataPoint

# Rows that get a value and a mini chart: what a person sees without pressing "more".
ENRICHED_ROWS = 8
# Points per mini chart: about a year of monthly data, enough to show a direction.
SPARK_POINTS = 12
_MIN_SPARK_POINTS = 3


def _finite(column):
    """Same bounds as the search fact gates: excludes PG NaN/Infinity."""
    return and_(column.is_not(None), column > literal_column("-1e30"), column < literal_column("1e30"))


async def _recent_points(db: AsyncSession, model, ids: list[int], points: int) -> dict[int, list[tuple]]:
    """Last `points` finite observations per series id, oldest first."""
    if not ids:
        return {}
    ranked = select(
        model.indicator_id.label("indicator_id"), model.date.label("date"), model.value.label("value"),
        func.row_number().over(partition_by=model.indicator_id, order_by=model.date.desc()).label("rn"),
    ).where(model.indicator_id.in_(ids), _finite(model.value)).subquery()
    rows = (await db.execute(
        select(ranked.c.indicator_id, ranked.c.date, ranked.c.value)
        .where(ranked.c.rn <= points).order_by(ranked.c.indicator_id, ranked.c.date)
    )).all()
    grouped: dict[int, list[tuple]] = {}
    for indicator_id, day, value in rows:
        grouped.setdefault(indicator_id, []).append((day, float(value)))
    return grouped


def _apply(item: dict, series: list[tuple] | None) -> None:
    if not series:
        return
    day, value = series[-1]
    item["latest"] = {"value": round(value, 4), "date": day.isoformat()}
    if len(series) >= _MIN_SPARK_POINTS:
        item["spark"] = [round(point, 4) for _day, point in series]


# Главное число для рядов цен: за год, а не за месяц. У индекса цен «100,4» или месячного
# прироста «−0,08 %» без базы читателю нечего понять, а инфляция за год понятна сразу.
# Поле `headline` аддитивно: `latest` остаётся как был (последняя точка самого ряда).
_FEDERAL_HEADLINE_YOY: dict[str, str] = {
    f"{base}{suffix}": yoy_code
    for base, yoy_code in (
        ("cpi", "cpi-yoy"),
        ("cpi-food", "cpi-food-yoy"),
        ("cpi-nonfood", "cpi-nonfood-yoy"),
        ("cpi-services", "cpi-services-yoy"),
    )
    for suffix in ("", "-period-monthly", "-period-weekly", "-qoq")
}


def _headline(value: float, day, code: str | None = None) -> dict:
    out = {"kind": "year_over_year", "value": round(value, 2), "unit": "%", "date": day.isoformat()}
    if code:
        out["code"] = code
    return out


def _months_back(day, months: int):
    from datetime import date as _date

    total = day.year * 12 + (day.month - 1) - months
    try:
        return _date(total // 12, total % 12 + 1, day.day)
    except ValueError:
        return None


def world_price_headline(indicator, series: list[tuple]) -> dict | None:
    """Инфляция за год для месячного ряда цен страны; None, если смысл ряда не сверен.

    Берётся только сверенное соответствие ряда понятию «потребительские цены» (каталог
    и ручной список национальных рядов). Прошлогоднюю точку ищем строго на 12 месяцев
    раньше, без подмены соседней: нет точки, нет числа.
    """
    from app.data.world_concept_national import (
        HICP_YOY_KIND_INDEX_MINUS_100,
        HICP_YOY_KIND_PASSTHROUGH,
        concept_slug_for_national_code,
        hicp_national_yoy_kind,
    )
    from app.data.world_concepts import concept_for_indicator

    if not series or str(getattr(indicator, "frequency", "") or "").lower() != "monthly":
        return None
    try:
        concept = concept_for_indicator(indicator)
    except ValueError:
        return None
    slug = concept.slug if concept is not None else concept_slug_for_national_code(
        str(getattr(indicator, "code", "") or ""))
    if slug != "hicp-index" or str(getattr(indicator, "provider", "") or "").lower() == "imf":
        return None
    last_day, last_value = series[-1]
    kind = hicp_national_yoy_kind(str(indicator.code))
    if kind == HICP_YOY_KIND_PASSTHROUGH:
        return _headline(last_value, last_day)
    if kind == HICP_YOY_KIND_INDEX_MINUS_100:
        return _headline(last_value - 100.0, last_day)
    target = _months_back(last_day, 12)
    prev = next((value for day, value in series if day == target), None)
    if target is None or prev is None or prev <= 0:
        return None
    return _headline((last_value / prev - 1.0) * 100.0, last_day)


async def attach_latest(db: AsyncSession, results: list[dict], *, rows: int = ENRICHED_ROWS, points: int = SPARK_POINTS) -> None:
    """Add `latest` ({value, date}) and `spark` (oldest to newest) to the first `rows` series rows, in place.

    Ряды цен получают ещё `headline` (инфляция за год): интерфейс показывает его главным числом, а
    значение `latest` (индекс или месячный прирост) оставляет мелким рядом.
    """
    head = [item for item in results[:rows] if item.get("code") and item.get("kind") in ("russia", "world")]
    if not head:
        return
    world_rows = db.info.get("fe_search_world_rows", {})
    world_ids: dict[tuple, int] = {}
    federal_codes: list[str] = []
    for item in head:
        if item["kind"] == "world":
            row = world_rows.get((item.get("country_slug"), item["code"]))
            if row is not None:
                world_ids[(item["country_slug"], item["code"])] = row.id
        else:
            federal_codes.append(item["code"])
    yoy_codes = sorted({_FEDERAL_HEADLINE_YOY[c] for c in federal_codes if c in _FEDERAL_HEADLINE_YOY})
    federal_ids: dict[str, int] = {}
    wanted_codes = list(dict.fromkeys(federal_codes + yoy_codes))
    if wanted_codes:
        federal_ids = {code: pk for pk, code in (await db.execute(
            select(Indicator.id, Indicator.code).where(Indicator.code.in_(wanted_codes)))).all()}
    # Для года назад у цен нужна одна точка сверх графика: 13 месячных значений.
    world_series = await _recent_points(db, WorldDataPoint, list(world_ids.values()), points + 1)
    federal_series = await _recent_points(
        db, IndicatorData, [federal_ids[c] for c in federal_codes if c in federal_ids], points)
    yoy_series = await _recent_points(
        db, IndicatorData, [federal_ids[c] for c in yoy_codes if c in federal_ids], 1)
    for item in head:
        if item["kind"] == "world":
            key = (item.get("country_slug"), item["code"])
            pk = world_ids.get(key)
            full = world_series.get(pk)
            _apply(item, full[-points:] if full else None)
            row = world_rows.get(key)
            headline = world_price_headline(row, full) if row is not None and full else None
            if headline:
                item["headline"] = headline
        else:
            pk = federal_ids.get(item["code"])
            _apply(item, federal_series.get(pk))
            yoy_code = _FEDERAL_HEADLINE_YOY.get(item["code"])
            yoy_points = yoy_series.get(federal_ids.get(yoy_code)) if yoy_code else None
            if yoy_points and item["code"] != yoy_code:
                day, value = yoy_points[-1]
                item["headline"] = _headline(value, day, yoy_code)
