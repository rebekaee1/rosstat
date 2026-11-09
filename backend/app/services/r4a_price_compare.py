"""R4-A: цены двух регионов рядом, корзина ходовых товаров и зарплата в корзинах.

Только сравнение значений, без мест в рейтинге.
"""

from __future__ import annotations

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import cache_get, cache_set, versioned_key
from app.data.emiss_price_goods import PRICE_GROUPS, PRICE_GROUPS_EN, price_meta
from app.models import RegionDataPoint, RegionIndicator
from app.services.locale import get_locale
from app.services.seo_i18n import region_display_name
from app.services.seo_regional import _region

# Месячный набор семьи: код цены -> сколько единиц (кг, л, поездок) в месяц.
BASKET: tuple[tuple[str, float], ...] = (
    ("ceni-hleb-pshenichnyy", 8),
    ("ceni-moloko", 12),
    ("ceni-yaytsa", 4),
    ("ceni-kury", 4),
    ("ceni-govyadina-beskostnaya", 2),
    ("ceni-kartofel", 8),
    ("ceni-sahar", 2),
    ("ceni-ai95", 80),
    ("ceni-proezd-avtobus", 40),
    ("ceni-elektroenergiya", 2),
    ("ceni-internet", 1),
)
WAGE_TABLE = "3.4"
_MONTHS_RU = ("январь", "февраль", "март", "апрель", "май", "июнь",
              "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь")
_MONTHS_EN = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def _label(month: int) -> str:
    names = _MONTHS_EN if get_locale() == "en" else _MONTHS_RU
    return f"{names[month % 100 - 1]} {month // 100}"


def _pct(hi: float, lo: float) -> float | None:
    return round((hi - lo) / lo * 100, 1) if lo else None


# R10-B: снимок цен одного региона кэшируется отдельно от пары и общий для всех пар с этим регионом.
_SNAP_TTL = 6 * 3600
_flights: dict[str, "asyncio.Future"] = {}


async def _region_snapshot(db: AsyncSession, region) -> dict:
    """Последние цены и зарплата одного региона: {"prices": {код: [месяц, значение]}, "wage": {год: значение}}.

    Считается одним проходом по индексу (по одной точке на ряд) и только по рядам, которые Росстат ещё публикует.
    Параллельные запросы одного региона ждут общий расчёт, а не плодят одинаковые.
    """
    key = await versioned_key("regions", f"vs-prices-reg:v1:{region.id}:{region.slug}")
    cached = await cache_get(key)
    if isinstance(cached, dict) and "prices" in cached:
        return cached
    flight = _flights.get(key)
    if flight is not None:
        return await asyncio.shield(flight)
    flight = asyncio.get_running_loop().create_future()
    _flights[key] = flight
    try:
        snap = await _build_snapshot(db, region)
        await cache_set(key, snap, _SNAP_TTL)
        flight.set_result(snap)
        return snap
    except BaseException as exc:
        flight.set_exception(exc)
        flight.exception()  # помечаем прочитанным, чтобы не было предупреждения без ожидающих
        raise
    finally:
        _flights.pop(key, None)


async def _build_snapshot(db: AsyncSession, region) -> dict:
    inds = (await db.execute(
        select(RegionIndicator.id, RegionIndicator.code).where(RegionIndicator.code.like("ceni-%"))
    )).all()
    live = {}
    for iid, code in inds:
        meta = price_meta(code)
        if meta and not meta["is_discontinued"]:
            live[iid] = code
    prices: dict[str, list] = {}
    if live:
        from app.services.regional_monthly_latest import latest_monthly_points

        for (iid, _rid), pts in (await latest_monthly_points(db, list(live), [region.id], n=1)).items():
            prices[live[iid]] = [pts[0][0], pts[0][1]]
    wage: dict[str, float] = {}
    w_id = (await db.execute(
        select(RegionIndicator.id).where(RegionIndicator.table_code == WAGE_TABLE).limit(1)
    )).scalar()
    if w_id is not None:
        for year, value in (await db.execute(
            select(RegionDataPoint.year, RegionDataPoint.value)
            .where(RegionDataPoint.indicator_id == w_id, RegionDataPoint.region_id == region.id)
        )).all():
            wage[str(int(year))] = float(value)
    return {"prices": prices, "wage": wage}


def compose_pair(slug_a: str, slug_b: str, ra, rb, snap_a: dict, snap_b: dict) -> dict | None:
    """Сборка сравнения из двух готовых снимков (без обращения к базе)."""
    en = get_locale() == "en"
    latest = {}
    for code, pa in snap_a["prices"].items():
        pb = snap_b["prices"].get(code)
        if pb:
            latest[code] = (pa, pb)

    items = []
    for code, (pa, pb) in latest.items():
        meta = price_meta(code)
        if not meta or meta["is_discontinued"]:
            continue
        va, vb = pa[1], pb[1]
        cheaper = None if abs(va - vb) < 1e-9 else (slug_a if va < vb else slug_b)
        group = meta["price_group"]
        items.append({
            "code": code,
            "name": (meta.get("short_name_en") or meta["short_name"]) if en else meta["short_name"],
            "group": group,
            "group_label": PRICE_GROUPS_EN.get(group, group) if en else group,
            "a": va, "b": vb,
            "diff_pct": _pct(max(va, vb), min(va, vb)),
            "cheaper_slug": cheaper,
            "month": min(pa[0], pb[0]),
        })
    if not items:
        return None
    order = {g: n for n, g in enumerate(PRICE_GROUPS)}
    items.sort(key=lambda x: (order.get(x["group"], 99), x["name"]))
    month = max(x["month"] for x in items)

    by_code = {x["code"]: x for x in items}
    basket_items, total_a, total_b = [], 0.0, 0.0
    for code, qty in BASKET:
        it = by_code.get(code)
        if not it:
            continue
        ca, cb = it["a"] * qty, it["b"] * qty
        total_a += ca
        total_b += cb
        basket_items.append({"code": code, "name": it["name"], "qty": qty,
                             "a": round(ca, 2), "b": round(cb, 2),
                             "cheaper_slug": it["cheaper_slug"]})
    basket = None
    if len(basket_items) >= 5:
        cheaper = None if abs(total_a - total_b) < 1e-6 else (slug_a if total_a < total_b else slug_b)
        basket = {
            "items": basket_items,
            "total_a": round(total_a, 2), "total_b": round(total_b, 2),
            "diff_pct": _pct(max(total_a, total_b), min(total_a, total_b)),
            "cheaper_slug": cheaper,
        }

    wage = None
    if basket:
        wa_all, wb_all = snap_a["wage"], snap_b["wage"]
        common = max((int(y) for y in wa_all if y in wb_all), default=None)
        if common is not None:
            wa, wb = wa_all[str(common)], wb_all[str(common)]
            if wa > 0 and wb > 0 and total_a > 0 and total_b > 0:
                ka, kb = round(wa / total_a, 1), round(wb / total_b, 1)
                wage = {
                    "year": common, "a": wa, "b": wb,
                    "baskets_a": ka, "baskets_b": kb,
                    "better_slug": None if ka == kb else (slug_a if ka > kb else slug_b),
                }

    return {
        "region_a": {"slug": slug_a, "name": region_display_name(ra.slug, ra.name)},
        "region_b": {"slug": slug_b, "name": region_display_name(rb.slug, rb.name)},
        "month": month, "period_label": _label(month),
        "items": items, "basket": basket, "wage": wage,
        "cheaper_count": {
            "a": sum(1 for x in items if x["cheaper_slug"] == slug_a),
            "b": sum(1 for x in items if x["cheaper_slug"] == slug_b),
            "total": len(items),
        },
    }


async def build_price_compare_payload(slug_a: str, slug_b: str, db: AsyncSession) -> dict | None:
    if slug_a == slug_b:
        return None
    ra, rb = await _region(db, slug_a), await _region(db, slug_b)
    if not ra or not rb or ra.kind != "region" or rb.kind != "region":
        return None
    snap_a, snap_b = await _region_snapshot(db, ra), await _region_snapshot(db, rb)
    return compose_pair(slug_a, slug_b, ra, rb, snap_a, snap_b)
