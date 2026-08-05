"""API мирового экономического блока (Eurostat).

Отдельный bounded context: world_countries / world_indicators / world_data_points.
Карточки склеивают частоты по card_key; режимы — составной ?mode={type}-{freq}.
Прогнозов нет.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import cache_get, cache_set, versioned_key
from app.data.eurostat_listing import (
    is_stale_history,
    normalize_frequency,
    variant_group_key,
)
from app.data.eurostat_titles_ru import listing_substance_score
from app.data.eurostat_units_ru import unit_suffix
from app.database import get_db
from app.models import WorldCountry, WorldDataPoint, WorldIndicator
from app.services.world_view_modes import is_signed_or_zero_crossing
from app.services.world_cards import (
    apply_resolved,
    build_modes_matrix,
    build_variants,
    display_name,
    frequencies_payload,
    indicator_card_key,
    members_by_freq,
    mode_unit_for,
    parse_mode_token,
    pick_primary,
    resolve_series_for_mode,
)

router = APIRouter(prefix="/world", tags=["world"])

_CACHE_TTL = 600


def _fmt_date(d: date | None) -> str | None:
    return d.isoformat() if d else None


def _country_payload(c: WorldCountry, indicators_count: int | None = None) -> dict:
    out = {
        "code": c.code,
        "slug": c.slug,
        "name": c.name_ru,
        "name_en": c.name_en,
        "region": c.region_ru,
    }
    if indicators_count is not None:
        out["indicators_count"] = indicators_count
    return out


async def _country_by_slug(db: AsyncSession, slug: str) -> WorldCountry:
    row = (
        await db.execute(
            select(WorldCountry).where(
                WorldCountry.slug == slug,
                WorldCountry.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(404, "Страна не найдена")
    return row


async def _indicator_by_code(db: AsyncSession, country_id: int, code: str) -> WorldIndicator:
    row = (
        await db.execute(
            select(WorldIndicator).where(
                WorldIndicator.country_id == country_id,
                WorldIndicator.code == code,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(404, "Индикатор не найден")
    return row


async def _load_points(
    db: AsyncSession,
    indicator_id: int,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[tuple[date, float]]:
    q = (
        select(WorldDataPoint.date, WorldDataPoint.value)
        .where(WorldDataPoint.indicator_id == indicator_id)
        .order_by(WorldDataPoint.date)
    )
    if date_from is not None:
        q = q.where(WorldDataPoint.date >= date_from)
    if date_to is not None:
        q = q.where(WorldDataPoint.date <= date_to)
    rows = (await db.execute(q)).all()
    return [(d, float(v)) for d, v in rows]


async def _country_indicators(db: AsyncSession, country_id: int) -> list[WorldIndicator]:
    return list(
        (
            await db.execute(
                select(WorldIndicator).where(WorldIndicator.country_id == country_id)
            )
        ).scalars().all()
    )


def _card_members_map(
    inds: list[WorldIndicator],
) -> dict[tuple, list[WorldIndicator]]:
    groups: dict[tuple, list[WorldIndicator]] = defaultdict(list)
    for ind in inds:
        if (ind.name_quality or "") not in ("curated", "composed"):
            continue
        groups[indicator_card_key(ind)].append(ind)
    return groups


def _primary_of_card(
    members: list[WorldIndicator],
) -> WorldIndicator | None:
    return pick_primary(members, listing_substance_score)


@router.get("/countries")
async def list_countries(db: AsyncSession = Depends(get_db)):
    cache_key = await versioned_key("world", "countries")
    cached = await cache_get(cache_key)
    if cached:
        return cached

    counts_q = (
        select(
            WorldIndicator.country_id,
            func.count().label("cnt"),
        )
        .where(WorldIndicator.is_listed.is_(True))
        .group_by(WorldIndicator.country_id)
        .subquery()
    )
    rows = (
        await db.execute(
            select(WorldCountry, counts_q.c.cnt)
            .outerjoin(counts_q, WorldCountry.id == counts_q.c.country_id)
            .where(WorldCountry.is_active.is_(True))
            .order_by(WorldCountry.sort_order, WorldCountry.name_ru)
        )
    ).all()

    countries = [
        _country_payload(c, int(cnt or 0))
        for c, cnt in rows
        if (cnt or 0) > 0
    ]
    any_listed = any(c["indicators_count"] > 0 for c in countries)
    if not any_listed:
        all_counts = (
            await db.execute(
                select(WorldIndicator.country_id, func.count())
                .group_by(WorldIndicator.country_id)
            )
        ).all()
        cnt_map = {cid: n for cid, n in all_counts}
        countries = [
            _country_payload(c, int(cnt_map.get(c.id, 0)))
            for c, _ in rows
            if cnt_map.get(c.id, 0) > 0
        ]

    payload = {"countries": countries, "total": len(countries)}
    await cache_set(cache_key, payload, ttl=_CACHE_TTL)
    return payload


@router.get("/countries/{slug}")
async def country_detail(slug: str, db: AsyncSession = Depends(get_db)):
    cache_key = await versioned_key("world", f"country:{slug}")
    cached = await cache_get(cache_key)
    if cached:
        return cached

    country = await _country_by_slug(db, slug)
    all_inds = await _country_indicators(db, country.id)
    groups = _card_members_map(all_inds)

    # Только primary с is_listed (после repair — совпадает с pick_primary)
    listed = [i for i in all_inds if i.is_listed]
    # подстраховка: если is_listed ещё не прогнан — собрать primary на лету
    if not listed:
        for members in groups.values():
            primary = _primary_of_card(members)
            if primary is not None:
                listed.append(primary)

    last_map: dict[int, tuple[date, float]] = {}
    if listed:
        ids = [i.id for i in listed]
        sub = (
            select(
                WorldDataPoint.indicator_id,
                func.max(WorldDataPoint.date).label("md"),
            )
            .where(WorldDataPoint.indicator_id.in_(ids))
            .group_by(WorldDataPoint.indicator_id)
            .subquery()
        )
        last_rows = (
            await db.execute(
                select(
                    WorldDataPoint.indicator_id,
                    WorldDataPoint.date,
                    WorldDataPoint.value,
                ).join(
                    sub,
                    (WorldDataPoint.indicator_id == sub.c.indicator_id)
                    & (WorldDataPoint.date == sub.c.md),
                )
            )
        ).all()
        last_map = {iid: (d, float(v)) for iid, d, v in last_rows}

    by_cat: dict[str, list] = {}
    for ind in listed:
        key = indicator_card_key(ind)
        members = groups.get(key) or [ind]
        by_freq = members_by_freq(members)
        last = last_map.get(ind.id)
        freqs_sorted = [f for f in ("monthly", "quarterly", "annual") if f in by_freq]
        for f in sorted(by_freq.keys()):
            if f not in freqs_sorted:
                freqs_sorted.append(f)
        item = {
            "code": ind.code,
            "name_ru": display_name(ind.name_ru),
            "name": display_name(ind.name_ru),  # compat
            "unit_ru": ind.unit_ru or ind.unit,
            "unit": ind.unit_ru or ind.unit,
            "unit_suffix": unit_suffix(ind.unit_ru or ind.unit),
            "category_ru": ind.category_ru,
            "frequencies": freqs_sorted,
            "last_value": round(last[1], 4) if last else None,
            "last_date": _fmt_date(last[0]) if last else None,
            "points_count": ind.points_count,
            "archived": is_stale_history(ind.history_end),
        }
        by_cat.setdefault(ind.category_ru or "Прочее", []).append(item)

    categories = [
        {"name": name, "count": len(items), "indicators": items}
        for name, items in sorted(by_cat.items(), key=lambda kv: kv[0])
    ]
    payload = {
        "country": _country_payload(country, sum(c["count"] for c in categories)),
        "categories": categories,
    }
    await cache_set(cache_key, payload, ttl=_CACHE_TTL)
    return payload


async def _card_context(
    db: AsyncSession, country: WorldCountry, ind: WorldIndicator,
) -> tuple[WorldIndicator, dict[str, WorldIndicator], list[WorldIndicator]]:
    """(primary, by_freq, all_country_inds)."""
    all_inds = await _country_indicators(db, country.id)
    groups = _card_members_map(all_inds)
    key = indicator_card_key(ind)
    members = groups.get(key) or [ind]
    by_freq = members_by_freq(members)
    primary = _primary_of_card(members) or ind
    return primary, by_freq, all_inds


@router.get("/indicators/{slug}/{code}")
async def indicator_meta(slug: str, code: str, db: AsyncSession = Depends(get_db)):
    cache_key = await versioned_key("world", f"ind:{slug}:{code}")
    cached = await cache_get(cache_key)
    if cached:
        return cached

    country = await _country_by_slug(db, slug)
    ind = await _indicator_by_code(db, country.id, code)
    primary, by_freq, all_inds = await _card_context(db, country, ind)

    # точки primary — для знака ряда в матрице
    series_by_code: dict[str, list] = {}
    for freq_ind in by_freq.values():
        series_by_code[freq_ind.code] = await _load_points(db, freq_ind.id)

    unit = ind.unit_ru or ind.unit or ""
    modes = build_modes_matrix(
        by_freq=by_freq,
        series_by_code=series_by_code,
        unit=unit,
    )

    # variants: primary каждой карточки той же variant-группы
    vg = variant_group_key(country_id=ind.country_id, dataset_id=ind.dataset_id)
    variant_primaries: list[WorldIndicator] = []
    if vg is not None:
        groups = _card_members_map(all_inds)
        for members in groups.values():
            p = _primary_of_card(members)
            if p is None:
                continue
            if variant_group_key(country_id=p.country_id, dataset_id=p.dataset_id) == vg:
                variant_primaries.append(p)

    # текущий для variants — primary своей карточки
    variants = build_variants(primary, variant_primaries)

    payload = {
        "country": _country_payload(country),
        "indicator": {
            "code": ind.code,
            "name": display_name(ind.name_ru),
            "name_ru": display_name(ind.name_ru),
            "name_en": ind.name_en,
            "unit": unit,
            "unit_ru": unit,
            "unit_suffix": unit_suffix(unit),
            "frequency": normalize_frequency(ind.frequency),
            "category": ind.category_ru,
            "category_ru": ind.category_ru,
            "source": ind.source,
            "source_url": ind.source_url,
            "description": ind.description,
            "methodology": ind.methodology,
            "history_start": _fmt_date(ind.history_start),
            "history_end": _fmt_date(ind.history_end),
            "points_count": ind.points_count,
            "archived": is_stale_history(ind.history_end),
        },
        "primary_code": primary.code,
        "frequencies": frequencies_payload(by_freq),
        "variants": variants,
        "modes": modes,
    }
    await cache_set(cache_key, payload, ttl=_CACHE_TTL)
    return payload


@router.get("/indicators/{slug}/{code}/data")
async def indicator_data(
    slug: str,
    code: str,
    mode: str = Query("level"),
    date_from: date | None = Query(None, alias="from"),
    date_to: date | None = Query(None, alias="to"),
    db: AsyncSession = Depends(get_db),
):
    cache_key = await versioned_key(
        "world",
        f"data:{slug}:{code}:{mode}:{date_from}:{date_to}",
    )
    cached = await cache_get(cache_key)
    if cached:
        return cached

    country = await _country_by_slug(db, slug)
    ind = await _indicator_by_code(db, country.id, code)
    _primary, by_freq, _all = await _card_context(db, country, ind)

    native = normalize_frequency(ind.frequency) or "monthly"
    try:
        parsed = parse_mode_token(mode, native_freq=native)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    # знак — по любому официальному ряду карточки
    signed = False
    for fi in by_freq.values():
        pts = await _load_points(db, fi.id)
        if pts and is_signed_or_zero_crossing(pts):
            signed = True
            break

    resolved = resolve_series_for_mode(
        parsed=parsed, by_freq=by_freq, signed=signed,
    )
    if resolved is None:
        raise HTTPException(400, f"Режим «{parsed.id}» недоступен для этой карточки")

    source = await _indicator_by_code(db, country.id, resolved.source_code)
    base = await _load_points(db, source.id)
    try:
        transformed = apply_resolved(base, resolved)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    if date_from is not None:
        transformed = [(d, v) for d, v in transformed if d >= date_from]
    if date_to is not None:
        transformed = [(d, v) for d, v in transformed if d <= date_to]

    unit = source.unit_ru or source.unit or ""
    mode_unit = mode_unit_for(parsed, unit, signed)
    payload = {
        "mode": parsed.id,
        "source_code": resolved.source_code,
        "frequency": resolved.frequency,
        "unit_ru": mode_unit,
        "unit": mode_unit,
        "unit_suffix": unit_suffix(mode_unit),
        "aggregated": resolved.aggregated,
        "points": [{"date": d.isoformat(), "value": v} for d, v in transformed],
        "count": len(transformed),
        # compat
        "code": resolved.source_code,
    }
    await cache_set(cache_key, payload, ttl=_CACHE_TTL)
    return payload


@router.get("/search")
async def search_world(
    q: str = Query(..., min_length=1),
    country: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    needle = q.strip()
    if not needle:
        return {"results": [], "total": 0}

    stmt = (
        select(WorldIndicator, WorldCountry)
        .join(WorldCountry, WorldIndicator.country_id == WorldCountry.id)
        .where(
            WorldIndicator.is_listed.is_(True),
            WorldCountry.is_active.is_(True),
            or_(
                WorldIndicator.name_ru.ilike(f"%{needle}%"),
                WorldIndicator.name_en.ilike(f"%{needle}%"),
                WorldIndicator.code.ilike(f"%{needle}%"),
                WorldIndicator.seo_keywords.ilike(f"%{needle}%"),
                WorldCountry.name_ru.ilike(f"%{needle}%"),
            ),
        )
        .order_by(WorldIndicator.name_ru)
        .limit(limit)
    )
    if country:
        stmt = stmt.where(
            or_(WorldCountry.slug == country, WorldCountry.code == country.upper())
        )

    rows = (await db.execute(stmt)).all()
    results = [
        {
            "code": ind.code,
            "name": display_name(ind.name_ru),
            "name_ru": display_name(ind.name_ru),
            "country_slug": c.slug,
            "country_name": c.name_ru,
            "category": ind.category_ru,
            "frequency": normalize_frequency(ind.frequency),
        }
        for ind, c in rows
    ]
    return {"results": results, "total": len(results)}
