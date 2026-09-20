"""API субнациональных регионов (ADR-0014): штаты / земли / провинции.

Префикс ``/api/v1/world/{country_slug}/regions``. Российский ``/api/v1/regions``
(ADR-0008) не трогаем. Паспорт страны — config-driven, без ``if country ==``.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import cache_get, cache_set, versioned_key
from app.database import get_db
from app.models import (
    SubnationalDataPoint,
    SubnationalIndicator,
    SubnationalRegion,
    WorldCountry,
    WorldDataPoint,
    WorldIndicator,
)
from app.services.api_i18n import api_detail
from app.services.locale import get_locale
from app.services.world_subnational_ingest import (
    country_has_subnational,
    expand_series_template,
    load_subnational_passport,
    period_key,
    period_label,
    period_start,
)

router = APIRouter(prefix="/world/{country_slug}/regions", tags=["world-subnational"])

_CACHE_TTL = 15 * 60


def _en() -> bool:
    return get_locale() == "en"


def _rname(region: SubnationalRegion) -> str:
    return region.name_en if _en() else region.name_ru


def _iname(ind: SubnationalIndicator) -> str:
    return ind.name_en if _en() else ind.name_ru


def _iunit(ind: SubnationalIndicator) -> str:
    if _en():
        return ind.unit_en or ind.unit
    return ind.unit_ru or ind.unit


def _section(ind: SubnationalIndicator) -> str:
    return ind.section_en if _en() else ind.section_ru


async def _country(db: AsyncSession, slug: str) -> WorldCountry:
    row = (
        await db.execute(
            select(WorldCountry).where(
                WorldCountry.slug == slug,
                WorldCountry.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    if row is None or not country_has_subnational(row.code):
        raise HTTPException(
            404,
            api_detail("Регионы этой страны не опубликованы", "No regions for this country"),
        )
    return row


async def _indicator(db: AsyncSession, country_code: str, code: str) -> SubnationalIndicator:
    row = (
        await db.execute(
            select(SubnationalIndicator).where(
                SubnationalIndicator.country_code == country_code,
                SubnationalIndicator.code == code,
                SubnationalIndicator.is_listed.is_(True),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(404, api_detail("Показатель не найден", "Indicator not found"))
    return row


async def _region(db: AsyncSession, country_code: str, slug: str) -> SubnationalRegion:
    row = (
        await db.execute(
            select(SubnationalRegion).where(
                SubnationalRegion.country_code == country_code,
                SubnationalRegion.slug == slug,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(404, api_detail("Регион не найден", "Region not found"))
    return row


def _kind_labels(country_code: str) -> dict[str, str]:
    passport = load_subnational_passport(country_code.lower())
    if _en():
        return {
            "kind": passport.region_kind_label_en,
            "kind_plural": passport.region_kind_label_en_plural,
            "default_indicator": passport.default_indicator,
            "map_id": passport.map_id,
        }
    return {
        "kind": passport.region_kind_label_ru,
        "kind_plural": passport.region_kind_label_ru_plural,
        "default_indicator": passport.default_indicator,
        "map_id": passport.map_id,
    }


def _rank_rows(rows: list[tuple], *, better_is_low: bool) -> list[dict]:
    numbered = [(slug, name, float(value)) for slug, name, value in rows if value is not None]
    numbered.sort(key=lambda item: item[2], reverse=not better_is_low)
    total = len(numbered)
    out = []
    for idx, (slug, name, value) in enumerate(numbered, 1):
        out.append({
            "slug": slug,
            "name": name,
            "value": round(value, 4),
            "rank": idx,
            "of": total,
        })
    return out


async def _rank_for_period(
    db: AsyncSession,
    indicator: SubnationalIndicator,
    period: date,
) -> list[dict]:
    peers = (
        await db.execute(
            select(
                SubnationalRegion.slug,
                SubnationalRegion.name_en,
                SubnationalRegion.name_ru,
                SubnationalDataPoint.value,
            )
            .join(SubnationalRegion, SubnationalRegion.id == SubnationalDataPoint.region_id)
            .where(
                SubnationalDataPoint.indicator_id == indicator.id,
                SubnationalDataPoint.period == period,
            )
        )
    ).all()
    named = [
        (slug, name_en if _en() else name_ru, value)
        for slug, name_en, name_ru, value in peers
    ]
    return _rank_rows(named, better_is_low=bool(indicator.better_is_low))


@router.get("")
async def list_regions(country_slug: str, db: AsyncSession = Depends(get_db)):
    cache_key = await versioned_key("world", f"subnat:hub:{country_slug}:{get_locale()}")
    cached = await cache_get(cache_key)
    if cached:
        return cached

    country = await _country(db, country_slug)
    labels = _kind_labels(country.code)
    regions = (
        await db.execute(
            select(SubnationalRegion)
            .where(SubnationalRegion.country_code == country.code)
            .order_by(SubnationalRegion.sort_order, SubnationalRegion.slug)
        )
    ).scalars().all()
    indicators = (
        await db.execute(
            select(SubnationalIndicator)
            .where(
                SubnationalIndicator.country_code == country.code,
                SubnationalIndicator.is_listed.is_(True),
            )
            .order_by(SubnationalIndicator.section_en, SubnationalIndicator.code)
        )
    ).scalars().all()
    sections: dict[str, list] = {}
    indicator_payload = []
    for ind in indicators:
        item = {
            "code": ind.code,
            "name": _iname(ind),
            "name_en": ind.name_en,
            "unit": _iunit(ind),
            "frequency": ind.frequency,
            "section": _section(ind),
            "better_is_low": bool(ind.better_is_low),
        }
        indicator_payload.append(item)
        sections.setdefault(_section(ind) or ("Topics" if _en() else "Темы"), []).append(item)
    payload = {
        "country": {
            "code": country.code,
            "slug": country.slug,
            "name": country.name_en if _en() else country.name_ru,
            "name_en": country.name_en,
        },
        "kind_label": labels["kind"],
        "kind_label_plural": labels["kind_plural"],
        "default_indicator": labels["default_indicator"],
        "map_id": labels["map_id"],
        "regions": [
            {
                "slug": r.slug,
                "name": _rname(r),
                "name_en": r.name_en,
                "kind": r.kind,
                "geo_code": r.geo_code,
            }
            for r in regions
        ],
        "indicators": indicator_payload,
        "sections": [
            {"num": idx, "name": name, "indicators": items}
            for idx, (name, items) in enumerate(sections.items(), 1)
        ],
        "totals": {
            "regions": len(regions),
            "indicators": len(indicator_payload),
        },
    }
    await cache_set(cache_key, payload, ttl=_CACHE_TTL)
    return payload


@router.get("/map/{code}")
async def map_values(
    country_slug: str,
    code: str,
    period: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    cache_key = await versioned_key(
        "world", f"subnat:map:{country_slug}:{code}:{period or 'last'}:{get_locale()}",
    )
    cached = await cache_get(cache_key)
    if cached:
        return cached

    country = await _country(db, country_slug)
    indicator = await _indicator(db, country.code, code)
    periods_raw = (
        await db.execute(
            select(SubnationalDataPoint.period)
            .where(SubnationalDataPoint.indicator_id == indicator.id)
            .distinct()
            .order_by(SubnationalDataPoint.period.desc())
        )
    ).scalars().all()
    if not periods_raw:
        raise HTTPException(404, api_detail("Нет данных по этому показателю", "No data for this indicator"))
    period_keys = []
    seen: set[str] = set()
    for p in periods_raw:
        key = period_key(p, indicator.frequency)
        if key not in seen:
            seen.add(key)
            period_keys.append(key)
    requested = period_start(period, indicator.frequency) if period else periods_raw[0]
    if requested is None:
        requested = periods_raw[0]
    # ближайший не позже запрошенного
    chosen = next((p for p in periods_raw if p <= requested), periods_raw[0])
    if indicator.frequency == "annual":
        chosen = next((p for p in periods_raw if p.year == requested.year), chosen)
    elif indicator.frequency == "monthly":
        chosen = next(
            (p for p in periods_raw if p.year == requested.year and p.month == requested.month),
            chosen,
        )
    elif indicator.frequency == "quarterly":
        chosen = next(
            (
                p for p in periods_raw
                if p.year == requested.year and (p.month - 1) // 3 == (requested.month - 1) // 3
            ),
            chosen,
        )

    rows = (
        await db.execute(
            select(
                SubnationalRegion.slug,
                SubnationalRegion.name_en,
                SubnationalRegion.name_ru,
                SubnationalDataPoint.value,
            )
            .join(SubnationalRegion, SubnationalRegion.id == SubnationalDataPoint.region_id)
            .where(
                SubnationalDataPoint.indicator_id == indicator.id,
                SubnationalDataPoint.period == chosen,
            )
        )
    ).all()
    named = [
        (slug, name_en if _en() else name_ru, value)
        for slug, name_en, name_ru, value in rows
    ]
    ranked = _rank_rows(named, better_is_low=bool(indicator.better_is_low))
    loc = get_locale()
    payload = {
        "indicator": {
            "code": indicator.code,
            "name": _iname(indicator),
            "unit": _iunit(indicator),
            "frequency": indicator.frequency,
            "better_is_low": bool(indicator.better_is_low),
        },
        "period": period_key(chosen, indicator.frequency),
        "period_label": period_label(chosen, indicator.frequency, loc),
        "periods": [
            {
                "key": key,
                "label": period_label(period_start(key, indicator.frequency) or chosen, indicator.frequency, loc),
            }
            for key in period_keys
        ],
        "values": ranked,
    }
    await cache_set(cache_key, payload, ttl=_CACHE_TTL)
    return payload


@router.get("/region/{slug}")
async def region_profile(country_slug: str, slug: str, db: AsyncSession = Depends(get_db)):
    cache_key = await versioned_key("world", f"subnat:profile:{country_slug}:{slug}:{get_locale()}")
    cached = await cache_get(cache_key)
    if cached:
        return cached

    country = await _country(db, country_slug)
    region = await _region(db, country.code, slug)
    labels = _kind_labels(country.code)
    indicators = (
        await db.execute(
            select(SubnationalIndicator)
            .where(
                SubnationalIndicator.country_code == country.code,
                SubnationalIndicator.is_listed.is_(True),
            )
            .order_by(SubnationalIndicator.section_en, SubnationalIndicator.code)
        )
    ).scalars().all()

    items = []
    loc = get_locale()
    for ind in indicators:
        last_two = (
            await db.execute(
                select(SubnationalDataPoint.period, SubnationalDataPoint.value)
                .where(
                    SubnationalDataPoint.indicator_id == ind.id,
                    SubnationalDataPoint.region_id == region.id,
                )
                .order_by(SubnationalDataPoint.period.desc())
                .limit(2)
            )
        ).all()
        last = last_two[0] if last_two else None
        prev = last_two[1] if len(last_two) > 1 else None
        rank = None
        of = None
        if last is not None:
            ranked = await _rank_for_period(db, ind, last[0])
            of = len(ranked)
            match = next((row for row in ranked if row["slug"] == region.slug), None)
            if match:
                rank = match["rank"]
        items.append({
            "code": ind.code,
            "name": _iname(ind),
            "label": _iname(ind),
            "unit": _iunit(ind),
            "frequency": ind.frequency,
            "section": _section(ind),
            "value": round(float(last[1]), 4) if last else None,
            "prev_value": round(float(prev[1]), 4) if prev else None,
            "year": last[0].year if last else None,
            "period": period_key(last[0], ind.frequency) if last else None,
            "period_label": period_label(last[0], ind.frequency, loc) if last else None,
            "rank": rank,
            "of": of,
            "better_is_low": bool(ind.better_is_low),
        })

    sections: dict[str, list] = {}
    for item in items:
        sections.setdefault(item["section"] or ("Topics" if _en() else "Темы"), []).append(item)

    payload = {
        "country": {
            "code": country.code,
            "slug": country.slug,
            "name": country.name_en if _en() else country.name_ru,
            "name_en": country.name_en,
        },
        "region": {
            "slug": region.slug,
            "name": _rname(region),
            "name_en": region.name_en,
            "kind": region.kind,
            "geo_code": region.geo_code,
        },
        "kind_label": labels["kind"],
        "kind_label_plural": labels["kind_plural"],
        "indicators": items,
        "sections": [
            {"num": idx, "name": name, "indicators": inds}
            for idx, (name, inds) in enumerate(sections.items(), 1)
        ],
        "catalog_total": len(items),
        "available_total": sum(1 for item in items if item["value"] is not None),
    }
    await cache_set(cache_key, payload, ttl=_CACHE_TTL)
    return payload


def _point_payload(period: date, value: float, frequency: str) -> dict:
    quarter = (period.month - 1) // 3 + 1
    return {
        "date": period.isoformat(),
        "value": round(float(value), 4),
        "year": period.year,
        "month": period.month,
        "quarter": quarter,
        "label": period_key(period, frequency),
    }


@router.get("/region/{slug}/{code}")
async def region_indicator(
    country_slug: str,
    slug: str,
    code: str,
    db: AsyncSession = Depends(get_db),
):
    cache_key = await versioned_key(
        "world", f"subnat:series:{country_slug}:{slug}:{code}:{get_locale()}",
    )
    cached = await cache_get(cache_key)
    if cached:
        return cached

    country = await _country(db, country_slug)
    region = await _region(db, country.code, slug)
    indicator = await _indicator(db, country.code, code)
    labels = _kind_labels(country.code)
    loc = get_locale()

    points = (
        await db.execute(
            select(SubnationalDataPoint.period, SubnationalDataPoint.value)
            .where(
                SubnationalDataPoint.indicator_id == indicator.id,
                SubnationalDataPoint.region_id == region.id,
            )
            .order_by(SubnationalDataPoint.period)
        )
    ).all()
    series = [_point_payload(p, v, indicator.frequency) for p, v in points]

    last = points[-1] if points else None
    ranked = await _rank_for_period(db, indicator, last[0]) if last is not None else []
    of = len(ranked)
    match = next((row for row in ranked if row["slug"] == region.slug), None)
    rank_position = match["rank"] if match else None
    rank_payload = None
    if rank_position is not None:
        rank_payload = {
            "position": rank_position,
            "total": of,
            "year": last[0].year,
            "rank_as_achievement": bool(indicator.better_is_low),
            "top": ranked[:5],
        }

    siblings = (
        await db.execute(
            select(SubnationalIndicator)
            .where(
                SubnationalIndicator.country_code == country.code,
                SubnationalIndicator.is_listed.is_(True),
                SubnationalIndicator.section_en == indicator.section_en,
                SubnationalIndicator.code != indicator.code,
            )
            .order_by(SubnationalIndicator.code)
        )
    ).scalars().all()

    national = None
    if indicator.national_code:
        wind = (
            await db.execute(
                select(WorldIndicator).where(WorldIndicator.code == indicator.national_code)
            )
        ).scalar_one_or_none()
        if wind is not None:
            npoints = (
                await db.execute(
                    select(WorldDataPoint.date, WorldDataPoint.value)
                    .where(WorldDataPoint.indicator_id == wind.id)
                    .order_by(WorldDataPoint.date)
                )
            ).all()
            national = {
                "code": wind.code,
                "name": country.name_en if _en() else country.name_ru,
                "series": [_point_payload(p, v, indicator.frequency) for p, v in npoints],
            }

    source_url = None
    if indicator.source_url_template:
        series_id = expand_series_template(
            indicator.series_template, geo=region.geo_code, fips=region.fips or "",
        )
        source_url = indicator.source_url_template.format(
            geo=region.geo_code, fips=region.fips or "", series_id=series_id,
        )

    payload = {
        "country": {
            "code": country.code,
            "slug": country.slug,
            "name": country.name_en if _en() else country.name_ru,
            "name_en": country.name_en,
        },
        "region": {
            "slug": region.slug,
            "name": _rname(region),
            "name_en": region.name_en,
            "kind": region.kind,
            "geo_code": region.geo_code,
        },
        "kind_label": labels["kind"],
        "kind_label_plural": labels["kind_plural"],
        "indicator": {
            "code": indicator.code,
            "name": _iname(indicator),
            "unit": _iunit(indicator),
            "frequency": indicator.frequency,
            "section": _section(indicator),
            "description": (indicator.description_en if _en() else indicator.description_ru) or "",
            "methodology": (indicator.methodology_en if _en() else indicator.methodology_ru) or "",
            "source": (indicator.source_en if _en() else indicator.source_ru) or "",
            "source_url": source_url,
            "better_is_low": bool(indicator.better_is_low),
            "national_code": indicator.national_code,
        },
        "series": series,
        "national": national,
        "siblings": [
            {"code": sib.code, "name": _iname(sib)}
            for sib in siblings
        ],
        "rank": rank_payload,
        "of": of,
        "last_value": round(float(last[1]), 4) if last else None,
        "last_period": period_key(last[0], indicator.frequency) if last else None,
        "last_period_label": period_label(last[0], indicator.frequency, loc) if last else None,
    }
    await cache_set(cache_key, payload, ttl=_CACHE_TTL)
    return payload
