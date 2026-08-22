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
from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import cache_get, cache_set, versioned_key
from app.services.locale import get_locale
from app.data.eurostat_listing import (
    dataset_stem,
    is_stale_history,
    normalize_frequency,
    variant_group_key,
)
from app.data.eurostat_titles_ru import listing_substance_score
from app.data.eurostat_units_ru import unit_suffix
from app.data.world_concepts import (
    CONCEPT_BY_SLUG,
    WORLD_CONCEPTS,
    concept_for_indicator,
    concept_public_name,
    concept_public_unit,
)
from app.data.world_concept_national import national_codes_for_concept
from app.data.global_market_indicators import market_indicator_codes_for_country
from app.data.world_country_area import area_payload
from app.data.world_country_population import population_payload as curated_population_payload
from app.data.world_indicator_titles_ru import is_public_catalog_name
from app.database import get_db
from app.models import (
    Indicator,
    IndicatorData,
    WorldCountry,
    WorldDataPoint,
    WorldForecast,
    WorldForecastValue,
    WorldIndicator,
)
from app.services.world_view_modes import is_signed_or_zero_crossing
from app.services.world_rank_values import (
    latest_rank_point,
    money_unit_compatible,
    ranking_display_name,
    ranking_period_method,
    ranking_public_unit,
    ranking_value_mode,
    world_rating_title,
    yearly_last_points,
)
from app.services.world_russia_rank import (
    merge_russia_into_values_by_year,
    russia_latest_snapshot_item,
    russia_meta_for_concept,
)
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


def _country_display_name(c: WorldCountry) -> str:
    """Locale-facing country label (EN prefers name_en)."""
    if get_locale() == "en" and (c.name_en or "").strip():
        return c.name_en
    return c.name_ru


def _region_display(region_ru: str | None) -> str:
    from app.services.world_rank_values import world_region_display

    return world_region_display(region_ru)


def _indicator_display_name(ind: WorldIndicator) -> str:
    """Locale-facing indicator title for country catalog / card."""
    from app.data.legacy_redirects import strip_world_frequency_suffix

    if get_locale() == "en" and (ind.name_en or "").strip():
        from app.data.eurostat_dim_labels_en import append_en_slice_to_title

        base = strip_world_frequency_suffix(ind.name_en) or ind.name_en
        return append_en_slice_to_title(base, ind.slice_json)
    return display_name(ind.name_ru, ind.code)


def _indicator_public_unit(indicator: WorldIndicator) -> str:
    """Locale-facing unit for world indicator rows."""
    ru = (indicator.unit_ru or indicator.unit or "").strip()
    if get_locale() != "en":
        return ru
    concept = concept_for_indicator(indicator)
    if concept is not None:
        return concept_public_unit(concept) or ru
    from app.data.eurostat_units_ru import unit_label_en_for_code
    from app.services.display import localize_unit

    en_label = (unit_label_en_for_code(indicator.unit) or "").strip()
    vague = {
        "rate", "number", "average", "person", "persons", "index", "ratio",
        "score", "total", "value", "unit", "percentage",
    }
    if en_label and en_label.lower() not in vague:
        return en_label
    return localize_unit(ru, locale="en") or ru


def _country_payload(c: WorldCountry, indicators_count: int | None = None) -> dict:
    out = {
        "code": c.code,
        "slug": c.slug,
        "name": _country_display_name(c),
        "name_en": c.name_en,
        "region": _region_display(c.region_ru),
    }
    if indicators_count is not None:
        out["indicators_count"] = indicators_count
    return out


def _population_indicator(
    country: WorldCountry,
    indicators: list[WorldIndicator],
) -> WorldIndicator | None:
    """Ряд населения страны: national crosswalk, иначе курируемый concept."""
    concept = CONCEPT_BY_SLUG.get("population")
    if concept is None:
        return None
    national_codes = national_codes_for_concept(concept.slug)
    national_match = next(
        (ind for ind in indicators if ind.code in national_codes),
        None,
    )
    if national_match is not None:
        return national_match
    matches = [
        ind for ind in indicators
        if concept_for_indicator(ind) == concept
    ]
    if len(matches) != 1:
        return None
    return matches[0]


async def _load_population_indicator(
    db: AsyncSession,
    country: WorldCountry,
) -> WorldIndicator | None:
    """Точечная выборка ряда населения — без полной выгрузки индикаторов страны."""
    concept = CONCEPT_BY_SLUG.get("population")
    if concept is None:
        return None
    national_codes = national_codes_for_concept(concept.slug)
    allowed = {str(ds).lower() for ds in concept.dataset_ids}
    if concept.provider_dataset_ids:
        for ids in concept.provider_dataset_ids.values():
            allowed.update(str(ds).lower() for ds in ids)
    rows = list(
        (
            await db.execute(
                select(WorldIndicator).where(
                    WorldIndicator.country_id == country.id,
                    or_(
                        func.lower(WorldIndicator.dataset_id).in_(sorted(allowed)),
                        WorldIndicator.code.in_(sorted(national_codes)),
                    ) if national_codes else (
                        func.lower(WorldIndicator.dataset_id).in_(sorted(allowed))
                    ),
                )
            )
        ).scalars().all()
    )
    return _population_indicator(country, rows)


async def _population_payload(
    db: AsyncSession,
    country: WorldCountry,
) -> dict | None:
    """Последнее значение ряда населения; иначе курируемый справочник ведомства."""
    indicator = await _load_population_indicator(db, country)
    if indicator is not None:
        row = (
            await db.execute(
                select(WorldDataPoint.date, WorldDataPoint.value)
                .where(WorldDataPoint.indicator_id == indicator.id)
                .order_by(WorldDataPoint.date.desc())
                .limit(1)
            )
        ).first()
        if row is not None:
            point_date, value = row
            numeric = float(value)
            from app.services.seo_i18n import localize_territory_fact

            return localize_territory_fact({
                "value": int(numeric) if numeric.is_integer() else round(numeric, 4),
                "unit": _indicator_public_unit(indicator) or (
                    "persons" if get_locale() == "en" else "человек"
                ),
                "date": point_date.isoformat(),
                "year": point_date.year,
                "source": indicator.source,
                "source_url": indicator.source_url,
            })
    from app.services.seo_i18n import localize_territory_fact

    return localize_territory_fact(curated_population_payload(country.code))


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


async def _load_points_by_ids(
    db: AsyncSession,
    indicator_ids: list[int],
) -> dict[int, list[tuple[date, float]]]:
    if not indicator_ids:
        return {}
    rows = (
        await db.execute(
            select(
                WorldDataPoint.indicator_id,
                WorldDataPoint.date,
                WorldDataPoint.value,
            )
            .where(WorldDataPoint.indicator_id.in_(indicator_ids))
            .order_by(WorldDataPoint.indicator_id, WorldDataPoint.date)
        )
    ).all()
    out: dict[int, list[tuple[date, float]]] = defaultdict(list)
    for indicator_id, point_date, value in rows:
        out[indicator_id].append((point_date, float(value)))
    return out


async def _load_yearly_last_by_ids(
    db: AsyncSession,
    indicator_ids: list[int],
) -> dict[int, list[tuple[date, float]]]:
    """Последняя точка каждого календарного года — для карты/рейтинга в level.

    Не тянем миллионы месячных точек в Python: DISTINCT ON по году + индекс
    ``(indicator_id, date)``.
    """
    if not indicator_ids:
        return {}
    year_expr = func.extract("year", WorldDataPoint.date)
    rows = (
        await db.execute(
            select(
                WorldDataPoint.indicator_id,
                WorldDataPoint.date,
                WorldDataPoint.value,
            )
            .where(WorldDataPoint.indicator_id.in_(indicator_ids))
            .distinct(WorldDataPoint.indicator_id, year_expr)
            .order_by(
                WorldDataPoint.indicator_id,
                year_expr,
                WorldDataPoint.date.desc(),
            )
        )
    ).all()
    out: dict[int, list[tuple[date, float]]] = defaultdict(list)
    # DISTINCT ON вернул desc по дате внутри года; для yearly_last_points
    # сортируем по возрастанию даты.
    tmp: dict[int, list[tuple[date, float]]] = defaultdict(list)
    for indicator_id, point_date, value in rows:
        tmp[indicator_id].append((point_date, float(value)))
    for indicator_id, pts in tmp.items():
        out[indicator_id] = sorted(pts, key=lambda p: p[0])
    return out


async def _ids_with_nonzero_signal(
    db: AsyncSession, indicator_ids: list[int],
) -> set[int]:
    """id рядов с хотя бы одной ненулевой точкой (не «пустой ноль»)."""
    if not indicator_ids:
        return set()
    rows = (
        await db.execute(
            select(WorldDataPoint.indicator_id)
            .where(
                WorldDataPoint.indicator_id.in_(indicator_ids),
                WorldDataPoint.value != 0,
            )
            .distinct()
        )
    ).all()
    return {int(r[0]) for r in rows}


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

    Stem сравниваем без учёта регистра: у национальных провайдеров dataset_id
    часто в верхнем регистре (FM01, CPIAUCSL), а ``dataset_stem`` канонизирует
    в lower — иначе карточка страны обнулялась при ненулевом списке.
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
        clauses.append(func.lower(WorldIndicator.dataset_id) == stem)
        clauses.append(
            func.lower(WorldIndicator.dataset_id).like(f"{stem}\\_%", escape="\\")
        )

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


def _rating_concepts():
    return [
        concept
        for concept in WORLD_CONCEPTS
        if "rating" in concept.enabled_surfaces
    ]


def _compare_series_payload(country: WorldCountry, indicator: WorldIndicator, concept) -> dict:
    return {
        "code": f"w:{country.slug}:{concept.slug}",
        "indicator_code": indicator.code,
        "country_slug": country.slug,
        "country_name": _country_display_name(country),
        "concept_slug": concept.slug,
        "concept_name": concept_public_name(concept),
        "frequency": normalize_frequency(indicator.frequency),
        "unit": concept_public_unit(concept),
    }


_AVERAGE_CONCEPTS = frozenset({"hicp-index", "unemployment-rate", "budget-balance-gdp"})
_MONEY_COMPARE_CONCEPTS = frozenset({
    "gdp-volume-quarterly",
    "gdp-volume-annual",
    "gdp-usd",
    "gdp-per-capita-usd",
})


def _indicator_unit(indicator: WorldIndicator) -> str:
    return (indicator.unit_ru or indicator.unit or "").strip()


def _concept_unit_compatible(concept, indicator: WorldIndicator) -> bool:
    if concept.slug not in _MONEY_COMPARE_CONCEPTS:
        return True
    # Класс меры (CLV15_MEUR и т.п.), не дословный unit_ru: формулировки
    # «млн евро в постоянных ценах» и «в постоянных ценах 2015 года, млн евро»
    # — одна и та же сопоставимая единица.
    return money_unit_compatible(concept.measure, indicator.unit, indicator.unit_ru)


def _benchmark_value(concept_slug: str, values: list[float]) -> float:
    if concept_slug == "hicp-index":
        return float(median(values))
    return sum(values) / len(values)


def _benchmark_label(concept_slug: str, count: int) -> str:
    """Locale-facing average/median chip (snapshot / map-series / average)."""
    if get_locale() == "en":
        metric = "Median" if concept_slug == "hicp-index" else "Average"
        return f"{metric} across {count} countries with data"
    metric = "Медиана" if concept_slug == "hicp-index" else "Среднее"
    return f"{metric} по {count} странам с данными"


def _average_series_copy(concept_slug: str) -> dict[str, str]:
    """User-visible meta for /compare/average (legend + methodology)."""
    if get_locale() == "en":
        if concept_slug == "hicp-index":
            return {
                "country_name": "Median across countries with data",
                "methodology": "Median across countries with data on each date",
            }
        return {
            "country_name": "Average across countries with data",
            "methodology": "Unweighted average across countries with data on each date",
        }
    if concept_slug == "hicp-index":
        return {
            "country_name": "Медиана по странам с данными",
            "methodology": "Медиана по странам с данными на каждую дату",
        }
    return {
        "country_name": "Среднее по странам с данными",
        "methodology": "Невзвешенное среднее по странам с данными на каждую дату",
    }


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
            if _concept_unit_compatible(concept, indicator):
                members.append((country, indicator))
            continue
        if (
            concept_for_indicator(indicator) == concept
            and _concept_unit_compatible(concept, indicator)
        ):
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
            # Держим первый по стабильному order_by, чтобы страна не исчезала из среза.
            continue
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
    """Каталог стран: счётчик = то, что увидит посетитель на карточке страны.

    Считаем только ``is_listed`` с ненулевым сигналом и публичным русским
    именем. Страны с нулём после отсева скрываем — каталог не обещает пустые
    страницы.
    """
    # v4: EXISTS по listed-рядам вместо DISTINCT по всей world_data_points
    # (на полном датасете ~8M точек DISTINCT убивал воркеры → 504/500).
    cache_key = await versioned_key("world", f"countries:v4:{get_locale()}")
    cached = await cache_get(cache_key)
    if cached:
        return cached

    # Коррелированный EXISTS: индекс (indicator_id, date) → O(listed), не O(все точки).
    has_signal = (
        select(WorldDataPoint.indicator_id)
        .where(
            WorldDataPoint.indicator_id == WorldIndicator.id,
            WorldDataPoint.value != 0,
        )
        .correlate(WorldIndicator)
        .exists()
    )
    listed_rows = (
        await db.execute(
            select(
                WorldIndicator.country_id,
                WorldIndicator.id,
                WorldIndicator.code,
                WorldIndicator.name_ru,
            )
            .where(
                WorldIndicator.is_listed.is_(True),
                has_signal,
            )
        )
    ).all()
    counts: dict[int, int] = defaultdict(int)
    for country_id, _iid, code, name_ru in listed_rows:
        name = display_name(name_ru, code)
        if not is_public_catalog_name(name):
            continue
        counts[int(country_id)] += 1

    rows = list(
        (
            await db.execute(
                select(WorldCountry)
                .where(WorldCountry.is_active.is_(True))
                .order_by(WorldCountry.sort_order, WorldCountry.name_ru)
            )
        ).scalars().all()
    )

    countries = [
        _country_payload(c, counts[c.id])
        for c in rows
        if counts.get(c.id, 0) > 0
    ]
    if not countries:
        # Dev/empty DB: без сигнала показываем сырой listed-count.
        raw_counts = (
            await db.execute(
                select(WorldIndicator.country_id, func.count())
                .where(WorldIndicator.is_listed.is_(True))
                .group_by(WorldIndicator.country_id)
            )
        ).all()
        cnt_map = {int(cid): int(n) for cid, n in raw_counts}
        countries = [
            _country_payload(c, cnt_map[c.id])
            for c in rows
            if cnt_map.get(c.id, 0) > 0
        ]

    payload = {"countries": countries, "total": len(countries)}
    await cache_set(cache_key, payload, ttl=_CACHE_TTL)
    return payload


@router.get("/rating/concepts")
async def world_rating_concepts():
    """Курируемые понятия с поверхностью rating — список для UI рейтинга стран."""
    from app.services.seo_world import world_rating_default_sort
    from app.services.world_rank_values import (
        ranking_display_name,
        ranking_public_unit,
        ranking_value_mode,
    )

    concepts = _rating_concepts()
    # Для каталога рейтинга базы неизвестны до members; цены всегда yoy.
    payload_concepts = []
    for concept in concepts:
        mode = ranking_value_mode(concept.slug, [])
        public_name = ranking_display_name(
            mode, concept.slug, concept_public_name(concept),
        )
        public_unit = ranking_public_unit(mode, concept_public_unit(concept))
        payload_concepts.append({
            "slug": concept.slug,
            "name": public_name,
            "unit": public_unit,
            "value_mode": mode,
            "default_sort": world_rating_default_sort(concept.slug),
        })
    return {
        "concepts": payload_concepts,
        "total": len(payload_concepts),
    }


@router.get("/compare/catalog")
async def world_compare_catalog(db: AsyncSession = Depends(get_db)):
    """Только курируемые и семантически совместимые фактические world-ряды."""
    cache_key = await versioned_key("world", f"compare:catalog:v4:{get_locale()}")
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
    cache_key = await versioned_key(
        "world", f"compare:snapshot:v6:{concept_slug}:{get_locale()}"
    )
    cached = await cache_get(cache_key)
    if cached:
        return cached

    members = await _concept_members(db, concept)
    mode = ranking_value_mode(concept.slug, members)
    public_unit = ranking_public_unit(mode, concept_public_unit(concept))
    member_ids = [ind.id for _, ind in members]
    # level: годовой срез в SQL; yoy: нужна полная история для transform_yoy.
    series_by_id = (
        await _load_yearly_last_by_ids(db, member_ids)
        if mode == "level"
        else await _load_points_by_ids(db, member_ids)
    )
    items = []
    for country, indicator in members:
        latest = latest_rank_point(series_by_id.get(indicator.id, []), mode)
        if latest is None:
            continue
        point_date, value = latest
        items.append({
            "country_code": country.code,
            "country_slug": country.slug,
            "country_name": _country_display_name(country),
            "date": point_date.isoformat(),
            "value": round(value, 4),
            "unit": public_unit,
        })
    ru_item = await russia_latest_snapshot_item(
        db, concept.slug, concept_mode=mode, public_unit=public_unit,
    )
    if ru_item is not None:
        items.append(ru_item)
    russia_meta = russia_meta_for_concept(concept.slug)
    average = None
    if concept_slug in _AVERAGE_CONCEPTS and len(items) >= 3:
        average = round(
            _benchmark_value(concept_slug, [item["value"] for item in items]),
            4,
        )
    public_name = ranking_display_name(
        mode, concept.slug, concept_public_name(concept),
    )
    payload = {
        "concept": {
            "slug": concept.slug,
            "name": public_name,
            "unit": public_unit,
            "value_mode": mode,
            "period_method": ranking_period_method(mode),
            "russia": russia_meta,
            "title": world_rating_title(concept.slug, public_name, None),
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
    """Годовые срезы для карты: последнее сопоставимое значение каждого года."""
    concept = CONCEPT_BY_SLUG.get(concept_slug)
    if concept is None or "compare" not in concept.enabled_surfaces:
        raise HTTPException(404, "Понятие для карты не найдено")
    cache_key = await versioned_key(
        "world", f"compare:map-series:v6:{concept_slug}:{get_locale()}"
    )
    cached = await cache_get(cache_key)
    if cached:
        return cached

    members = await _concept_members(db, concept)
    mode = ranking_value_mode(concept.slug, members)
    public_unit = ranking_public_unit(mode, concept_public_unit(concept))
    member_ids = [ind.id for _, ind in members]
    series_by_id = (
        await _load_yearly_last_by_ids(db, member_ids)
        if mode == "level"
        else await _load_points_by_ids(db, member_ids)
    )

    values_by_year: dict[str, dict[str, dict]] = {}
    for country, indicator in members:
        for year, (point_date, value) in yearly_last_points(
            series_by_id.get(indicator.id, []), mode
        ).items():
            year_values = values_by_year.setdefault(str(year), {})
            year_values[country.code] = {
                "country_code": country.code,
                "country_slug": country.slug,
                "country_name": _country_display_name(country),
                "indicator_code": indicator.code,
                "date": point_date.isoformat(),
                "value": round(value, 4),
                "unit": public_unit,
            }

    russia_meta = await merge_russia_into_values_by_year(
        db,
        concept.slug,
        values_by_year,
        concept_mode=mode,
        public_unit=public_unit,
    )

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

    public_name = ranking_display_name(
        mode, concept.slug, concept_public_name(concept),
    )
    payload = {
        "concept": {
            "slug": concept.slug,
            "name": public_name,
            "unit": public_unit,
            "value_mode": mode,
            "period_method": ranking_period_method(mode),
            "russia": russia_meta,
            "title": world_rating_title(concept.slug, public_name, None),
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
    cache_key = await versioned_key(
        "world",
        f"compare:average:v3:{concept_slug}:{mode or 'native'}:{get_locale()}",
    )
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
    copy = _average_series_copy(concept_slug)
    payload = {
        "meta": {
            "code": f"w:average:{concept.slug}",
            "concept_slug": concept.slug,
            "concept_name": concept_public_name(concept),
            "country_name": copy["country_name"],
            "frequency": resolved_frequency,
            "unit": concept_public_unit(concept),
            "methodology": copy["methodology"],
        },
        "data": points,
    }
    await cache_set(cache_key, payload, ttl=_CACHE_TTL)
    return payload


async def _country_market_indicators(db: AsyncSession, slug: str) -> list[dict]:
    """Рыночные ряды общего каталога, привязанные к стране (может быть пусто)."""
    codes = market_indicator_codes_for_country(slug)
    if not codes:
        return []

    rows = (
        await db.execute(
            select(Indicator).where(
                Indicator.code.in_(codes),
                Indicator.is_active.is_(True),
            )
        )
    ).scalars().all()
    by_code = {row.code: row for row in rows}
    last_map: dict[int, tuple[date, float]] = {}
    if rows:
        ranked = (
            select(
                IndicatorData.indicator_id.label("indicator_id"),
                IndicatorData.date.label("date"),
                IndicatorData.value.label("value"),
                func.row_number().over(
                    partition_by=IndicatorData.indicator_id,
                    order_by=IndicatorData.date.desc(),
                ).label("rn"),
            )
            .where(IndicatorData.indicator_id.in_([row.id for row in rows]))
            .subquery()
        )
        last_rows = (
            await db.execute(
                select(ranked.c.indicator_id, ranked.c.date, ranked.c.value)
                .where(ranked.c.rn == 1)
            )
        ).all()
        last_map = {
            indicator_id: (point_date, float(value))
            for indicator_id, point_date, value in last_rows
        }

    from app.services.seo_i18n import indicator_copy_en, public_indicator_fields

    items: list[dict] = []
    for code in codes:
        indicator = by_code.get(code)
        if indicator is None:
            continue
        fields = public_indicator_fields(
            code,
            name_ru=indicator.name,
            name_en=indicator.name_en,
            unit_ru=indicator.unit,
        )
        en_name = (indicator_copy_en(code) or {}).get("name") or indicator.name_en or indicator.name
        last = last_map.get(indicator.id)
        items.append({
            "code": code,
            "name": fields["name"],
            "name_en": en_name,
            "unit": fields["unit"],
            "last_value": round(last[1], 4) if last else None,
            "last_date": _fmt_date(last[0]) if last else None,
            "frequency": indicator.frequency,
        })
    return items


@router.get("/countries/{slug}")
async def country_detail(slug: str, db: AsyncSession = Depends(get_db)):
    cache_key = await versioned_key("world", f"country:v10:{slug}:{get_locale()}")
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

    # Защита: all-zero не в каталоге страны (даже если is_listed ещё true).
    listed_signal = await _ids_with_nonzero_signal(db, [i.id for i in listed])
    listed = [i for i in listed if i.id in listed_signal]

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
        name = _indicator_display_name(ind)
        catalog_name = display_name(ind.name_ru, ind.code)
        if not is_public_catalog_name(catalog_name):
            # Нельзя осмысленно назвать по-русски — не обещаем в каталоге.
            continue
        primary_freq = normalize_frequency(ind.frequency) or (
            freqs_sorted[0] if freqs_sorted else None
        )
        unit = _indicator_public_unit(ind)
        item = {
            "code": ind.code,
            "name_ru": catalog_name,
            "name": name,  # compat / locale-facing
            "unit_ru": ind.unit_ru or ind.unit,
            "unit": unit,
            "unit_suffix": unit_suffix(unit),
            "category_ru": ind.category_ru,
            "category": ind.category_ru,
            "frequency": primary_freq,
            "frequencies": freqs_sorted,
            "last_value": round(last[1], 4) if last else None,
            "last_date": _fmt_date(last[0]) if last else None,
            "prev_value": round(prev_val, 4) if prev_val is not None else None,
            "change": change,
            "points_count": ind.points_count,
            "archived": is_stale_history(ind.history_end),
        }
        by_cat.setdefault(ind.category_ru or "Прочее", []).append(item)

    from app.services.seo_i18n import localize_category_name

    for items in by_cat.values():
        for item in items:
            raw_cat = item.get("category_ru") or "Прочее"
            item["category"] = localize_category_name(raw_cat)
            # category_ru stays the storage/api key (Russian); category is locale-facing.

    categories = [
        {
            "name": localize_category_name(name),
            "count": len(items),
            "indicators": items,
        }
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
        if latest is None or latest[1] == 0:
            continue
        overview.append({
            "concept_slug": concept.slug,
            "name": concept_public_name(concept),
            "unit": concept_public_unit(concept),
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
    area = area_payload(country.code)
    population = await _population_payload(db, country)
    payload = {
        "country": _country_payload(country, sum(c["count"] for c in categories)),
        "categories": categories,
        "overview": overview,
        "coverage": {
            "history_start": min(history_starts).isoformat() if history_starts else None,
            "history_end": max(history_ends).isoformat() if history_ends else None,
            "frequencies": official_frequencies,
        },
        "market_indicators": await _country_market_indicators(db, country.slug),
    }
    from app.services.seo_i18n import localize_territory_fact

    if area is not None:
        payload["area"] = localize_territory_fact(area)
    if population is not None:
        payload["population"] = population
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
    cache_key = await versioned_key(
        "world", f"ind:v11:{slug}:{code}:{get_locale()}"
    )
    cached = await cache_get(cache_key)
    if cached:
        return cached

    country = await _country_by_slug(db, slug)
    ind = await _indicator_by_code(db, country.id, code)
    primary, by_freq, all_inds = await _card_context(db, country, ind)
    # Витрина: listed. Срезы с реальным сигналом тоже открываем (variant-пикер),
    # все-нули / пустые unlisted — 404.
    if not primary.is_listed:
        signal_ids = await _ids_with_nonzero_signal(db, [ind.id, primary.id])
        if ind.id not in signal_ids and primary.id not in signal_ids:
            raise HTTPException(404, "Индикатор не найден")

    # точки primary — для знака ряда в матрице
    series_by_code: dict[str, list] = {}
    for freq_ind in by_freq.values():
        series_by_code[freq_ind.code] = await _load_points(db, freq_ind.id)

    unit = _indicator_public_unit(ind)
    modes = build_modes_matrix(
        by_freq=by_freq,
        series_by_code=series_by_code,
        unit=unit,
    )

    # variants: только ряды с ненулевым сигналом (нули не в пикере).
    vg = variant_group_key(country_id=ind.country_id, dataset_id=ind.dataset_id)
    variant_primaries: list[WorldIndicator] = []
    if vg is not None:
        groups = _card_members_map(all_inds)
        candidates: list[WorldIndicator] = []
        for members in groups.values():
            p = _primary_of_card(members)
            if p is None:
                continue
            if variant_group_key(country_id=p.country_id, dataset_id=p.dataset_id) != vg:
                continue
            candidates.append(p)
        signal = await _ids_with_nonzero_signal(db, [p.id for p in candidates])
        variant_primaries = [p for p in candidates if p.id in signal]

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
                WorldIndicator.is_listed.is_(True),
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
    peer_signal = await _ids_with_nonzero_signal(
        db, [(_primary_of_card(members) or members[0]).id for _, members in peer_members.values()],
    )
    for peer_country, members in peer_members.values():
        peer_primary = _primary_of_card(members)
        if peer_primary is None or peer_primary.id not in peer_signal:
            continue
        peers.append({
            "country_code": peer_country.code,
            "country_slug": peer_country.slug,
            "country_name": _country_display_name(peer_country),
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

    from app.services.seo_i18n import localize_category_name

    cat_disp = localize_category_name(ind.category_ru)
    payload = {
        "country": _country_payload(country),
        "indicator": {
            "code": ind.code,
            "provider": ind.provider,
            "name": _indicator_display_name(ind),
            "name_ru": display_name(ind.name_ru, ind.code),
            "name_en": ind.name_en,
            "unit": unit,
            "unit_ru": ind.unit_ru or ind.unit or "",
            "unit_suffix": unit_suffix(unit),
            "frequency": normalize_frequency(ind.frequency),
            "category": cat_disp,
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
        f"data:v4:{slug}:{code}:{mode}:{int(include_forecast)}:"
        f"{date_from}:{date_to}:{get_locale()}",
    )
    cached = await cache_get(cache_key)
    if cached:
        return cached

    country = await _country_by_slug(db, slug)
    ind = await _indicator_by_code(db, country.id, code)
    _primary, by_freq, _all = await _card_context(db, country, ind)
    if not _primary.is_listed:
        signal_ids = await _ids_with_nonzero_signal(db, [ind.id, _primary.id])
        if ind.id not in signal_ids and _primary.id not in signal_ids:
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

    concept = concept_for_indicator(source)
    unit = (
        concept_public_unit(concept)
        if concept is not None
        else _indicator_public_unit(source)
    )
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

    # LIKE-метасимволы в запросе — литералы, иначе «100%» совпадёт со всем.
    like_needle = (
        needle.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    )
    pattern = f"%{like_needle}%"
    code_match = WorldIndicator.code.ilike(pattern, escape="\\")
    name_match = or_(
        WorldIndicator.name_ru.ilike(pattern, escape="\\"),
        WorldIndicator.name_en.ilike(pattern, escape="\\"),
    )
    keywords_match = WorldIndicator.seo_keywords.ilike(pattern, escape="\\")
    country_match = or_(
        WorldCountry.name_ru.ilike(pattern, escape="\\"),
        WorldCountry.name_en.ilike(pattern, escape="\\"),
        WorldCountry.slug.ilike(pattern, escape="\\"),
        WorldCountry.code.ilike(pattern, escape="\\"),
    )
    # Код (`us-unemployment-rate`) выше длинных eurostat name_en-совпадений,
    # иначе «unemployment» тонет в сотнях EU-срезов до лимита.
    relevance = case(
        (code_match, 0),
        (name_match, 1),
        (keywords_match, 2),
        else_=3,
    )
    # Oversample: после отсева нулевого сигнала часть кандидатов отпадёт.
    candidate_limit = min(200, max(limit * 3, limit))

    stmt = (
        select(WorldIndicator, WorldCountry)
        .join(WorldCountry, WorldIndicator.country_id == WorldCountry.id)
        .where(
            WorldIndicator.is_listed.is_(True),
            WorldCountry.is_active.is_(True),
            or_(code_match, name_match, keywords_match, country_match),
        )
        .order_by(
            relevance,
            func.length(WorldIndicator.code),
            WorldIndicator.name_ru,
        )
        .limit(candidate_limit)
    )
    if country:
        stmt = stmt.where(
            or_(WorldCountry.slug == country, WorldCountry.code == country.upper())
        )

    rows = (await db.execute(stmt)).all()
    signal = await _ids_with_nonzero_signal(db, [ind.id for ind, _c in rows])
    from app.services.seo_i18n import localize_category_name

    results = [
        {
            "code": ind.code,
            "name": _indicator_display_name(ind),
            "name_ru": display_name(ind.name_ru, ind.code),
            "country_slug": c.slug,
            "country_name": _country_display_name(c),
            "category": localize_category_name(ind.category_ru),
            "frequency": normalize_frequency(ind.frequency),
        }
        for ind, c in rows
        if ind.id in signal
    ][:limit]
    return {"results": results, "total": len(results)}
