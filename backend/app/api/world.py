"""API мирового экономического блока (multi-provider).

Отдельный bounded context: world_countries / world_indicators / world_data_points.
Карточки склеивают частоты по card_key; режимы — составной ?mode={type}-{freq}.
Прогнозы изолированы в world_forecasts и проходят rolling-origin quality gate.
"""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import date
from statistics import median

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import cache_get, cache_set, versioned_key
from app.data.eurostat_listing import (
    dataset_stem,
    is_stale_history,
    normalize_frequency,
    variant_group_key,
)
from app.data.eurostat_titles_ru import listing_substance_score
from app.data.eurostat_units_ru import unit_suffix
from app.data.world_concepts import CONCEPT_BY_SLUG, WORLD_CONCEPTS, concept_for_indicator
from app.data.world_concept_national import national_codes_for_concept
from app.database import get_db
from app.models import (
    WorldCountry,
    WorldDataPoint,
    WorldForecast,
    WorldForecastValue,
    WorldIndicator,
)
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


async def _load_current_world_forecast(
    db: AsyncSession,
    indicator_id: int,
) -> tuple[WorldForecast, list[WorldForecastValue]] | None:
    forecast = (
        await db.execute(
            select(WorldForecast)
            .where(
                WorldForecast.world_indicator_id == indicator_id,
                WorldForecast.is_current.is_(True),
                WorldForecast.gate_status == "passed",
            )
            .order_by(WorldForecast.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if forecast is None:
        return None
    values = list((
        await db.execute(
            select(WorldForecastValue)
            .where(WorldForecastValue.forecast_id == forecast.id)
            .order_by(WorldForecastValue.date)
        )
    ).scalars().all())
    return (forecast, values) if values else None


async def _country_indicators(db: AsyncSession, country_id: int) -> list[WorldIndicator]:
    return list(
        (
            await db.execute(
                select(WorldIndicator).where(WorldIndicator.country_id == country_id)
            )
        ).scalars().all()
    )


async def _country_indicators_for_listing(
    db: AsyncSession, country_id: int,
) -> list[WorldIndicator]:
    """Listed + sibling-частоты тех же stem — без полной выгрузки 7k+ рядов страны.

    Полный `_country_indicators` на DE/FR/ES тянет тысячи ORM-объектов и на
    холодном кэше/рестарте backend давал Empty reply / таймаут фронта (15 с).
    """
    listed = list(
        (
            await db.execute(
                select(WorldIndicator).where(
                    WorldIndicator.country_id == country_id,
                    WorldIndicator.is_listed.is_(True),
                )
            )
        ).scalars().all()
    )
    if not listed:
        return await _country_indicators(db, country_id)

    stems = {dataset_stem(ind.dataset_id) for ind in listed if ind.dataset_id}
    stems.discard("")
    if not stems:
        return listed

    clauses = []
    for stem in stems:
        clauses.append(WorldIndicator.dataset_id == stem)
        clauses.append(WorldIndicator.dataset_id.like(f"{stem}\\_%", escape="\\"))

    return list(
        (
            await db.execute(
                select(WorldIndicator).where(
                    WorldIndicator.country_id == country_id,
                    or_(*clauses),
                )
            )
        ).scalars().all()
    )


def _compare_concepts():
    return [
        concept
        for concept in WORLD_CONCEPTS
        if "compare" in concept.enabled_surfaces
    ]


def _compare_series_payload(country: WorldCountry, indicator: WorldIndicator, concept) -> dict:
    return {
        "code": f"w:{country.slug}:{concept.slug}",
        "indicator_code": indicator.code,
        "country_slug": country.slug,
        "country_name": country.name_ru,
        "concept_slug": concept.slug,
        "concept_name": concept.name_ru,
        "frequency": normalize_frequency(indicator.frequency),
        "unit": concept.unit_ru,
    }


_AVERAGE_CONCEPTS = frozenset({"hicp-index", "unemployment-rate", "budget-balance-gdp"})


def _benchmark_value(concept_slug: str, values: list[float]) -> float:
    if concept_slug == "hicp-index":
        return float(median(values))
    return sum(values) / len(values)


def _benchmark_label(concept_slug: str, count: int) -> str:
    metric = "Медиана" if concept_slug == "hicp-index" else "Среднее"
    return f"{metric} по {count} странам с данными"


async def _concept_members(
    db: AsyncSession,
    concept,
) -> list[tuple[WorldCountry, WorldIndicator]]:
    # Не тянем всю таблицу world_indicators (после deep-expand — 100k+ строк):
    # только listed + dataset_id понятия (+ явный national crosswalk).
    allowed = {
        str(ds).lower()
        for ds in concept.dataset_ids
    }
    if concept.provider_dataset_ids:
        for ids in concept.provider_dataset_ids.values():
            allowed.update(str(ds).lower() for ds in ids)
    national_codes = national_codes_for_concept(concept.slug)
    rows = (
        await db.execute(
            select(WorldCountry, WorldIndicator)
            .join(WorldIndicator, WorldIndicator.country_id == WorldCountry.id)
            .where(
                WorldCountry.is_active.is_(True),
                WorldIndicator.is_listed.is_(True),
                or_(
                    func.lower(WorldIndicator.dataset_id).in_(sorted(allowed)),
                    WorldIndicator.code.in_(sorted(national_codes)),
                ) if national_codes else (
                    func.lower(WorldIndicator.dataset_id).in_(sorted(allowed))
                ),
            )
            .order_by(WorldCountry.sort_order, WorldCountry.name_ru, WorldIndicator.code)
        )
    ).all()
    members: list[tuple[WorldCountry, WorldIndicator]] = []
    for country, indicator in rows:
        if indicator.code in national_codes:
            members.append((country, indicator))
            continue
        if concept_for_indicator(indicator) == concept:
            members.append((country, indicator))
    # Одна страна — один ряд: national имеет приоритет над eurostat-дублем.
    by_country: dict[int, tuple[WorldCountry, WorldIndicator]] = {}
    for country, indicator in members:
        prev = by_country.get(country.id)
        if prev is None:
            by_country[country.id] = (country, indicator)
            continue
        prev_is_national = prev[1].code in national_codes
        cur_is_national = indicator.code in national_codes
        if cur_is_national and not prev_is_national:
            by_country[country.id] = (country, indicator)
        elif prev_is_national == cur_is_national:
            # Два eurostat match — страна неоднозначна, выкидываем оба.
            by_country.pop(country.id, None)
    return list(by_country.values())


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


@router.get("/compare/catalog")
async def world_compare_catalog(db: AsyncSession = Depends(get_db)):
    """Только курируемые и семантически совместимые фактические world-ряды."""
    cache_key = await versioned_key("world", "compare:catalog:v3")
    cached = await cache_get(cache_key)
    if cached:
        return cached

    concepts = {concept.slug: concept for concept in _compare_concepts()}
    allowed_datasets: set[str] = set()
    for concept in concepts.values():
        allowed_datasets.update(str(ds).lower() for ds in concept.dataset_ids)
        if concept.provider_dataset_ids:
            for ids in concept.provider_dataset_ids.values():
                allowed_datasets.update(str(ds).lower() for ds in ids)
    rows = (
        await db.execute(
            select(WorldCountry, WorldIndicator)
            .join(WorldIndicator, WorldIndicator.country_id == WorldCountry.id)
            .where(
                WorldCountry.is_active.is_(True),
                WorldIndicator.is_listed.is_(True),
                func.lower(WorldIndicator.dataset_id).in_(sorted(allowed_datasets)),
            )
            .order_by(WorldCountry.sort_order, WorldCountry.name_ru, WorldIndicator.code)
        )
    ).all()
    items = []
    for country, indicator in rows:
        concept = concept_for_indicator(indicator)
        if concept is None or concept.slug not in concepts:
            continue
        items.append(_compare_series_payload(country, indicator, concept))

    payload = {"items": items, "total": len(items)}
    await cache_set(cache_key, payload, ttl=_CACHE_TTL)
    return payload


@router.get("/compare/series/{country_slug}/{concept_slug}")
async def world_compare_series(
    country_slug: str,
    concept_slug: str,
    db: AsyncSession = Depends(get_db),
):
    """Фактический официальный ряд одной страны для curated compare concept."""
    concept = CONCEPT_BY_SLUG.get(concept_slug)
    if concept is None or "compare" not in concept.enabled_surfaces:
        raise HTTPException(404, "Понятие для сравнения не найдено")

    country = await _country_by_slug(db, country_slug)
    indicators = await _country_indicators(db, country.id)
    members = [
        indicator
        for indicator in indicators
        if concept_for_indicator(indicator) == concept
    ]
    if not members:
        raise HTTPException(404, "Для страны нет сопоставимого ряда")
    if len(members) > 1:
        raise HTTPException(409, "Неоднозначный состав ряда для сравнения")

    indicator = members[0]
    points = await _load_points(db, indicator.id)
    return {
        "meta": _compare_series_payload(country, indicator, concept),
        "data": [{"date": d.isoformat(), "value": value} for d, value in points],
    }


@router.get("/compare/snapshot/{concept_slug}")
async def world_compare_snapshot(
    concept_slug: str,
    db: AsyncSession = Depends(get_db),
):
    """Последние сопоставимые значения для карты и рейтинга стран."""
    concept = CONCEPT_BY_SLUG.get(concept_slug)
    if concept is None or "compare" not in concept.enabled_surfaces:
        raise HTTPException(404, "Понятие для сравнения не найдено")
    cache_key = await versioned_key("world", f"compare:snapshot:v2:{concept_slug}")
    cached = await cache_get(cache_key)
    if cached:
        return cached

    members = await _concept_members(db, concept)
    ids = [indicator.id for _, indicator in members]
    if not ids:
        return {"concept": concept_slug, "items": [], "average": None}
    ranked = (
        select(
            WorldDataPoint.indicator_id.label("indicator_id"),
            WorldDataPoint.date.label("date"),
            WorldDataPoint.value.label("value"),
            func.row_number().over(
                partition_by=WorldDataPoint.indicator_id,
                order_by=WorldDataPoint.date.desc(),
            ).label("rn"),
        )
        .where(WorldDataPoint.indicator_id.in_(ids))
        .subquery()
    )
    latest_rows = (
        await db.execute(
            select(ranked.c.indicator_id, ranked.c.date, ranked.c.value)
            .where(ranked.c.rn == 1)
        )
    ).all()
    latest_by_id = {
        indicator_id: (point_date, float(value))
        for indicator_id, point_date, value in latest_rows
    }
    items = []
    for country, indicator in members:
        latest = latest_by_id.get(indicator.id)
        if latest is None:
            continue
        point_date, value = latest
        items.append({
            "country_code": country.code,
            "country_slug": country.slug,
            "country_name": country.name_ru,
            "date": point_date.isoformat(),
            "value": value,
        })
    average = None
    if concept_slug in _AVERAGE_CONCEPTS and len(items) >= 3:
        average = round(
            _benchmark_value(concept_slug, [item["value"] for item in items]),
            4,
        )
    payload = {
        "concept": {
            "slug": concept.slug,
            "name": concept.name_ru,
            "unit": concept.unit_ru,
        },
        "items": items,
        "average": average,
        "average_label": (
            _benchmark_label(concept_slug, len(items))
            if average is not None else None
        ),
    }
    await cache_set(cache_key, payload, ttl=_CACHE_TTL)
    return payload


@router.get("/compare/map-series/{concept_slug}")
async def world_compare_map_series(
    concept_slug: str,
    db: AsyncSession = Depends(get_db),
):
    """Годовые срезы для карты: последнее опубликованное значение каждого года."""
    concept = CONCEPT_BY_SLUG.get(concept_slug)
    if concept is None or "compare" not in concept.enabled_surfaces:
        raise HTTPException(404, "Понятие для карты не найдено")
    cache_key = await versioned_key("world", f"compare:map-series:v2:{concept_slug}")
    cached = await cache_get(cache_key)
    if cached:
        return cached

    members = await _concept_members(db, concept)
    member_by_id = {
        indicator.id: (country, indicator)
        for country, indicator in members
    }
    ids = list(member_by_id)
    rows = (
        await db.execute(
            select(
                WorldDataPoint.indicator_id,
                WorldDataPoint.date,
                WorldDataPoint.value,
            )
            .where(WorldDataPoint.indicator_id.in_(ids))
            .order_by(WorldDataPoint.indicator_id, WorldDataPoint.date)
        )
    ).all() if ids else []

    values_by_year: dict[str, dict[str, dict]] = {}
    for indicator_id, point_date, raw_value in rows:
        member = member_by_id.get(indicator_id)
        if member is None:
            continue
        country, indicator = member
        year_values = values_by_year.setdefault(str(point_date.year), {})
        previous = year_values.get(country.code)
        if previous is not None and previous["date"] >= point_date.isoformat():
            continue
        year_values[country.code] = {
            "country_code": country.code,
            "country_slug": country.slug,
            "country_name": country.name_ru,
            "indicator_code": indicator.code,
            "date": point_date.isoformat(),
            "value": round(float(raw_value), 4),
        }

    years = sorted(int(year) for year, items in values_by_year.items() if items)
    benchmark_by_year: dict[str, dict] = {}
    if concept_slug in _AVERAGE_CONCEPTS:
        for year in years:
            items = list(values_by_year[str(year)].values())
            if len(items) < 3:
                continue
            benchmark_by_year[str(year)] = {
                "value": round(
                    _benchmark_value(concept_slug, [item["value"] for item in items]),
                    4,
                ),
                "label": _benchmark_label(concept_slug, len(items)),
                "countries_count": len(items),
            }

    payload = {
        "concept": {
            "slug": concept.slug,
            "name": concept.name_ru,
            "unit": concept.unit_ru,
            "period_method": "Последнее опубликованное значение в каждом календарном году",
        },
        "years": years,
        "values_by_year": values_by_year,
        "benchmark_by_year": benchmark_by_year,
    }
    await cache_set(cache_key, payload, ttl=_CACHE_TTL)
    return payload


@router.get("/compare/average/{concept_slug}")
async def world_compare_average_series(
    concept_slug: str,
    mode: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Невзвешенное среднее по странам только для совместимых rate/index concepts."""
    concept = CONCEPT_BY_SLUG.get(concept_slug)
    if concept is None or concept_slug not in _AVERAGE_CONCEPTS:
        raise HTTPException(404, "Средний межстрановой ряд для этого показателя недоступен")
    cache_key = await versioned_key("world", f"compare:average:v3:{concept_slug}:{mode or 'native'}")
    cached = await cache_get(cache_key)
    if cached:
        return cached

    members = await _concept_members(db, concept)
    by_date: dict[date, list[float]] = defaultdict(list)
    resolved_frequency = normalize_frequency(members[0][1].frequency) if members else None
    if mode:
        for country, indicator in members:
            _primary, by_freq, _all = await _card_context(db, country, indicator)
            native = normalize_frequency(indicator.frequency) or "monthly"
            try:
                parsed = parse_mode_token(mode, native_freq=native)
            except ValueError:
                continue
            series_by_code = {
                member.code: await _load_points(db, member.id)
                for member in by_freq.values()
            }
            signed = any(
                points and is_signed_or_zero_crossing(points)
                for points in series_by_code.values()
            )
            resolved = resolve_series_for_mode(parsed=parsed, by_freq=by_freq, signed=signed)
            if resolved is None:
                continue
            points = series_by_code.get(resolved.source_code)
            if points is None:
                source = await _indicator_by_code(db, country.id, resolved.source_code)
                points = await _load_points(db, source.id)
            try:
                transformed = apply_resolved(points, resolved)
            except ValueError:
                continue
            resolved_frequency = resolved.frequency
            for point_date, value in transformed:
                by_date[point_date].append(float(value))
    else:
        ids = [indicator.id for _, indicator in members]
        rows = (
            await db.execute(
                select(WorldDataPoint.date, WorldDataPoint.value)
                .where(WorldDataPoint.indicator_id.in_(ids))
                .order_by(WorldDataPoint.date)
            )
        ).all() if ids else []
        for point_date, value in rows:
            by_date[point_date].append(float(value))
    minimum_coverage = max(3, math.ceil(len(members) * 0.5))
    points = [
        {
            "date": point_date.isoformat(),
            "value": round(_benchmark_value(concept_slug, values), 4),
            "countries_count": len(values),
        }
        for point_date, values in sorted(by_date.items())
        if len(values) >= minimum_coverage
    ]
    payload = {
        "meta": {
            "code": f"w:average:{concept.slug}",
            "concept_slug": concept.slug,
            "concept_name": concept.name_ru,
            "country_name": (
                "Медиана по странам с данными"
                if concept_slug == "hicp-index"
                else "Среднее по странам с данными"
            ),
            "frequency": resolved_frequency,
            "unit": concept.unit_ru,
            "methodology": (
                "Медиана по странам с данными на каждую дату"
                if concept_slug == "hicp-index"
                else "Невзвешенное среднее по странам с данными на каждую дату"
            ),
        },
        "data": points,
    }
    await cache_set(cache_key, payload, ttl=_CACHE_TTL)
    return payload


@router.get("/countries/{slug}")
async def country_detail(slug: str, db: AsyncSession = Depends(get_db)):
    cache_key = await versioned_key("world", f"country:v3:{slug}")
    cached = await cache_get(cache_key)
    if cached:
        return cached

    country = await _country_by_slug(db, slug)
    all_inds = await _country_indicators_for_listing(db, country.id)
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
    prev_map: dict[int, float] = {}
    if listed:
        ids = [i.id for i in listed]
        ranked = (
            select(
                WorldDataPoint.indicator_id.label("indicator_id"),
                WorldDataPoint.date.label("date"),
                WorldDataPoint.value.label("value"),
                func.row_number().over(
                    partition_by=WorldDataPoint.indicator_id,
                    order_by=WorldDataPoint.date.desc(),
                ).label("rn"),
            )
            .where(WorldDataPoint.indicator_id.in_(ids))
            .subquery()
        )
        last_rows = (
            await db.execute(
                select(ranked.c.indicator_id, ranked.c.date, ranked.c.value, ranked.c.rn)
                .where(ranked.c.rn <= 2)
            )
        ).all()
        for iid, d, v, rn in last_rows:
            if rn == 1:
                last_map[iid] = (d, float(v))
            elif rn == 2:
                prev_map[iid] = float(v)

    by_cat: dict[str, list] = {}
    for ind in listed:
        key = indicator_card_key(ind)
        members = groups.get(key) or [ind]
        by_freq = members_by_freq(members)
        last = last_map.get(ind.id)
        prev_val = prev_map.get(ind.id)
        change = None
        if last is not None and prev_val is not None:
            change = round(float(last[1]) - float(prev_val), 4)
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
            "prev_value": round(prev_val, 4) if prev_val is not None else None,
            "change": change,
            "points_count": ind.points_count,
            "archived": is_stale_history(ind.history_end),
        }
        by_cat.setdefault(ind.category_ru or "Прочее", []).append(item)

    categories = [
        {"name": name, "count": len(items), "indicators": items}
        for name, items in sorted(by_cat.items(), key=lambda kv: kv[0])
    ]
    overview_candidates = []
    seen_concepts: set[str] = set()
    for concept in WORLD_CONCEPTS:
        matches = [
            indicator
            for indicator in all_inds
            if concept_for_indicator(indicator) == concept
        ]
        if len(matches) != 1 or concept.slug in seen_concepts:
            continue
        overview_candidates.append((concept, matches[0]))
        seen_concepts.add(concept.slug)

    overview_latest: dict[int, tuple[date, float]] = {}
    if overview_candidates:
        overview_ids = [indicator.id for _, indicator in overview_candidates]
        ranked = (
            select(
                WorldDataPoint.indicator_id.label("indicator_id"),
                WorldDataPoint.date.label("date"),
                WorldDataPoint.value.label("value"),
                func.row_number().over(
                    partition_by=WorldDataPoint.indicator_id,
                    order_by=WorldDataPoint.date.desc(),
                ).label("rn"),
            )
            .where(WorldDataPoint.indicator_id.in_(overview_ids))
            .subquery()
        )
        overview_rows = (
            await db.execute(
                select(ranked.c.indicator_id, ranked.c.date, ranked.c.value)
                .where(ranked.c.rn == 1)
            )
        ).all()
        overview_latest = {
            indicator_id: (point_date, float(value))
            for indicator_id, point_date, value in overview_rows
        }

    overview = []
    for concept, indicator in overview_candidates:
        latest = overview_latest.get(indicator.id)
        if latest is None:
            continue
        overview.append({
            "concept_slug": concept.slug,
            "name": concept.name_ru,
            "unit": concept.unit_ru,
            "indicator_code": indicator.code,
            "frequency": normalize_frequency(indicator.frequency),
            "date": latest[0].isoformat(),
            "value": round(latest[1], 4),
        })

    history_starts = [indicator.history_start for indicator in listed if indicator.history_start]
    history_ends = [indicator.history_end for indicator in listed if indicator.history_end]
    official_frequencies = sorted({
        normalize_frequency(indicator.frequency)
        for indicator in all_inds
        if normalize_frequency(indicator.frequency)
    })
    payload = {
        "country": _country_payload(country, sum(c["count"] for c in categories)),
        "categories": categories,
        "overview": overview,
        "coverage": {
            "history_start": min(history_starts).isoformat() if history_starts else None,
            "history_end": max(history_ends).isoformat() if history_ends else None,
            "frequencies": official_frequencies,
        },
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
    cache_key = await versioned_key("world", f"ind:v6:{slug}:{code}")
    cached = await cache_get(cache_key)
    if cached:
        return cached

    country = await _country_by_slug(db, slug)
    ind = await _indicator_by_code(db, country.id, code)
    primary, by_freq, all_inds = await _card_context(db, country, ind)
    # Карточка на витрине только если primary listed (unlisted = мусор/нули/дубль).
    # Иначе прямой URL обходил SSR-404 через SPA + этот API.
    if not primary.is_listed:
        raise HTTPException(404, "Индикатор не найден")

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

    peer_key = indicator_card_key(ind)[1:]
    peer_dataset_ids = {
        member.dataset_id
        for member in by_freq.values()
        if member.dataset_id
    } or {ind.dataset_id}
    peer_rows = (
        await db.execute(
            select(WorldCountry, WorldIndicator)
            .join(WorldIndicator, WorldIndicator.country_id == WorldCountry.id)
            .where(
                WorldCountry.is_active.is_(True),
                WorldIndicator.name_quality.in_(("curated", "composed")),
                WorldIndicator.provider == ind.provider,
                WorldIndicator.dataset_id.in_(peer_dataset_ids),
            )
            .order_by(WorldCountry.sort_order, WorldCountry.name_ru, WorldIndicator.code)
        )
    ).all()
    peer_members: dict[int, tuple[WorldCountry, list[WorldIndicator]]] = {}
    for peer_country, peer_indicator in peer_rows:
        if peer_country.id == country.id:
            continue
        if indicator_card_key(peer_indicator)[1:] != peer_key:
            continue
        entry = peer_members.setdefault(peer_country.id, (peer_country, []))
        entry[1].append(peer_indicator)
    peers = []
    for peer_country, members in peer_members.values():
        peer_primary = _primary_of_card(members)
        if peer_primary is None:
            continue
        peers.append({
            "country_code": peer_country.code,
            "country_slug": peer_country.slug,
            "country_name": peer_country.name_ru,
            "indicator_code": peer_primary.code,
            "frequency": normalize_frequency(peer_primary.frequency),
        })

    forecast_available = bool(await db.scalar(
        select(func.count(WorldForecast.id)).where(
            WorldForecast.world_indicator_id.in_(
                [member.id for member in by_freq.values()]
            ),
            WorldForecast.is_current.is_(True),
            WorldForecast.gate_status == "passed",
        )
    ))

    payload = {
        "country": _country_payload(country),
        "indicator": {
            "code": ind.code,
            "provider": ind.provider,
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
            "concept_slug": (
                concept.slug
                if (concept := concept_for_indicator(ind)) is not None
                and "compare" in concept.enabled_surfaces
                else None
            ),
        },
        "primary_code": primary.code,
        "frequencies": frequencies_payload(by_freq),
        "variants": variants,
        "modes": modes,
        "peers": peers,
        "forecast_available": forecast_available,
    }
    await cache_set(cache_key, payload, ttl=_CACHE_TTL)
    return payload


@router.get("/indicators/{slug}/{code}/data")
async def indicator_data(
    slug: str,
    code: str,
    mode: str = Query("level"),
    include_forecast: bool = Query(False),
    date_from: date | None = Query(None, alias="from"),
    date_to: date | None = Query(None, alias="to"),
    db: AsyncSession = Depends(get_db),
):
    cache_key = await versioned_key(
        "world",
        f"data:v4:{slug}:{code}:{mode}:{int(include_forecast)}:{date_from}:{date_to}",
    )
    cached = await cache_get(cache_key)
    if cached:
        return cached

    country = await _country_by_slug(db, slug)
    ind = await _indicator_by_code(db, country.id, code)
    _primary, by_freq, _all = await _card_context(db, country, ind)
    if not _primary.is_listed:
        raise HTTPException(404, "Индикатор не найден")

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

    forecast_payload = None
    if include_forecast:
        candidates = [source]
        candidates.extend(
            candidate
            for freq in ("monthly", "quarterly")
            if (candidate := by_freq.get(freq)) is not None
            and candidate.id != source.id
        )
        selected_actual_end = max((d for d, _ in transformed), default=None)
        seen_ids: set[int] = set()
        for candidate in candidates:
            if candidate.id in seen_ids:
                continue
            seen_ids.add(candidate.id)
            current = await _load_current_world_forecast(db, candidate.id)
            if current is None:
                continue
            forecast, forecast_values = current
            forecast_resolved = (
                resolved
                if candidate.id == source.id
                else resolve_series_for_mode(
                    parsed=parsed,
                    by_freq={normalize_frequency(candidate.frequency): candidate},
                    signed=signed,
                )
            )
            if forecast_resolved is None:
                continue
            candidate_actual = await _load_points(db, candidate.id)
            combined = [
                *candidate_actual,
                *((value.date, float(value.value)) for value in forecast_values),
            ]
            try:
                candidate_actual_transformed = apply_resolved(
                    candidate_actual,
                    forecast_resolved,
                )
                candidate_combined_transformed = apply_resolved(
                    combined,
                    forecast_resolved,
                )
            except ValueError:
                continue
            cutoff = max(
                filter(
                    None,
                    [
                        selected_actual_end,
                        max((d for d, _ in candidate_actual_transformed), default=None),
                    ],
                ),
                default=None,
            )
            forecast_points = [
                (d, v)
                for d, v in candidate_combined_transformed
                if cutoff is None or d > cutoff
            ]
            if not forecast_points:
                continue
            interval_by_date = {}
            if not forecast_resolved.aggregated and forecast_resolved.transform == "level":
                interval_by_date = {
                    value.date: {
                        "lower_bound": (
                            float(value.lower_bound)
                            if value.lower_bound is not None else None
                        ),
                        "upper_bound": (
                            float(value.upper_bound)
                            if value.upper_bound is not None else None
                        ),
                    }
                    for value in forecast_values
                }
            forecast_payload = {
                "model_name": forecast.model_name,
                "strategy": forecast.strategy,
                "quality": {
                    "mase": float(forecast.mase) if forecast.mase is not None else None,
                    "baseline_mase": (
                        float(forecast.baseline_mase)
                        if forecast.baseline_mase is not None else None
                    ),
                    "origins": forecast.origins,
                },
                "source_code": candidate.code,
                "derived": (
                    forecast_resolved.aggregated
                    or forecast_resolved.transform != "level"
                ),
                "points": [
                    {
                        "date": d.isoformat(),
                        "value": v,
                        **interval_by_date.get(d, {
                            "lower_bound": None,
                            "upper_bound": None,
                        }),
                    }
                    for d, v in forecast_points
                ],
            }
            break

    if date_from is not None:
        transformed = [(d, v) for d, v in transformed if d >= date_from]
        if forecast_payload:
            forecast_payload["points"] = [
                point for point in forecast_payload["points"]
                if date.fromisoformat(point["date"]) >= date_from
            ]
    if date_to is not None:
        transformed = [(d, v) for d, v in transformed if d <= date_to]
        if forecast_payload:
            forecast_payload["points"] = [
                point for point in forecast_payload["points"]
                if date.fromisoformat(point["date"]) <= date_to
            ]

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
        "forecast": forecast_payload,
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
