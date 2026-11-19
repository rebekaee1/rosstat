"""Чтение квартального слоя регионов (``region_quarterly_data``, YYYYQ; 19.11.2026).

Один источник для API карточки, профиля региона, карты и SSR: подпись квартала, ряд пары «показатель × регион»
и последние кварталы многих пар. Квартальный ряд показывается на той же странице показателя, что и годовой;
отдельных адресов на квартал нет.
"""

from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import RegionQuarterlyPoint
from app.services.locale import get_locale

_ROMAN = {1: "I", 2: "II", 3: "III", 4: "IV"}


def quarter_label(quarter: int, locale: str | None = None) -> str:
    """20263 → «III кв. 2026» / «Q3 2026»."""
    year, q = divmod(int(quarter), 10)
    if (locale or get_locale()) == "en":
        return f"Q{q} {year}"
    return f"{_ROMAN[q]} кв. {year}"


def quarter_point(quarter: int, value: float) -> dict:
    """Точка ряда для API: тот же вид, что ждёт график регионов (``frequency='quarterly'``)."""
    return {"year": quarter // 10, "quarter": quarter % 10, "value": round(float(value), 4),
            "label": quarter_label(quarter)}


async def quarterly_rows(db: AsyncSession, indicator_id: int, region_id: int) -> list[tuple[int, float]]:
    """Ряд пары по возрастанию квартала; нет слоя — пустой список."""
    rows = (await db.execute(
        select(RegionQuarterlyPoint.quarter, RegionQuarterlyPoint.value)
        .where(RegionQuarterlyPoint.indicator_id == indicator_id, RegionQuarterlyPoint.region_id == region_id)
        .order_by(RegionQuarterlyPoint.quarter)
    )).all()
    return [(int(q), float(v)) for q, v in rows]


async def latest_quarterly_points(
    db: AsyncSession, indicator_ids: Iterable[int], region_ids: Iterable[int], *, n: int = 1,
) -> dict[tuple[int, int], list[tuple[int, float]]]:
    """(indicator_id, region_id) → до ``n`` последних (квартал YYYYQ, значение), от нового к старому.

    Слой маленький (≈0,1 млн строк на 19.11.2026): оконная функция по паре идёт по уникальному индексу.
    """
    ind = sorted({int(i) for i in indicator_ids})
    reg = sorted({int(r) for r in region_ids})
    if not ind or not reg:
        return {}
    p = RegionQuarterlyPoint
    rn = func.row_number().over(partition_by=(p.indicator_id, p.region_id), order_by=p.quarter.desc()).label("rn")
    sub = (select(p.indicator_id, p.region_id, p.quarter, p.value, rn)
           .where(p.indicator_id.in_(ind), p.region_id.in_(reg)).subquery())
    rows = (await db.execute(
        select(sub.c.indicator_id, sub.c.region_id, sub.c.quarter, sub.c.value)
        .where(sub.c.rn <= n).order_by(sub.c.indicator_id, sub.c.region_id, sub.c.quarter.desc())
    )).all()
    out: dict[tuple[int, int], list[tuple[int, float]]] = {}
    for iid, rid, quarter, value in rows:
        out.setdefault((int(iid), int(rid)), []).append((int(quarter), float(value)))
    return out
