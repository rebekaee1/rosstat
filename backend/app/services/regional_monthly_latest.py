"""Последние точки месячных рядов регионов через индекс (09.11.2026).

После заливки 13,1 млн точек цен ЕМИСС (2000–2026) запросы «вся история, потом взять последнюю» стали упираться в
диск: сравнение цен двух регионов (`r4a_price_compare`) падало по statement timeout 30 с, профиль региона на
холодном кэше отвечал 15,6 с. На стенде данных было мало, и этого не было видно.

Здесь на каждую пару (показатель, регион) читается не больше `n` последних месяцев индексом
`uq_region_monthly_point (indicator_id, region_id, month)`: LATERAL ... ORDER BY month DESC LIMIT n. Замер на проде
09.11.2026 (884 цены × 2 региона): 4,3 с на холодном диске, 20 мс на прогретом, вместо таймаута.
"""
from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_PG_SQL = text("""
    select p.indicator_id, r.region_id, last.month, last.value, last.rn
    from unnest(cast(:indicator_ids as integer[])) as p(indicator_id)
    cross join unnest(cast(:region_ids as integer[])) as r(region_id)
    cross join lateral (
        select t.month, t.value, row_number() over (order by t.month desc) as rn
        from (
            select d.month, d.value from region_monthly_data d
            where d.indicator_id = p.indicator_id and d.region_id = r.region_id
            order by d.month desc
            limit :n
        ) t
    ) last
""")


def _portable_query(ind: list[int], reg: list[int], n: int):
    """Тот же результат без LATERAL (SQLite тестов): номер строки в окне по паре."""
    from sqlalchemy import func, select

    from app.models import RegionMonthlyPoint as P

    rn = func.row_number().over(partition_by=(P.indicator_id, P.region_id), order_by=P.month.desc()).label("rn")
    sub = (select(P.indicator_id, P.region_id, P.month, P.value, rn)
           .where(P.indicator_id.in_(ind), P.region_id.in_(reg)).subquery())
    return select(sub.c.indicator_id, sub.c.region_id, sub.c.month, sub.c.value, sub.c.rn).where(sub.c.rn <= n)


async def latest_monthly_points(
    db: AsyncSession, indicator_ids: Iterable[int], region_ids: Iterable[int], *, n: int = 1,
) -> dict[tuple[int, int], list[tuple[int, float]]]:
    """(indicator_id, region_id) → до `n` последних (month YYYYMM, value), от нового к старому."""
    ind = sorted({int(i) for i in indicator_ids})
    reg = sorted({int(r) for r in region_ids})
    if not ind or not reg:
        return {}
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        rows = (await db.execute(_PG_SQL, {"indicator_ids": ind, "region_ids": reg, "n": int(n)})).all()
    else:
        rows = (await db.execute(_portable_query(ind, reg, int(n)))).all()
    out: dict[tuple[int, int], list[tuple[int, float]]] = {}
    for iid, rid, month, value, _rn in sorted(rows, key=lambda r: (r[0], r[1], r[4])):
        out.setdefault((int(iid), int(rid)), []).append((int(month), float(value)))
    return out
