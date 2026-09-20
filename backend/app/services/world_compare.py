"""Сопоставимые ряды world-понятия: члены, пиры карточки, российский блок.

``concept_members`` — единая выборка стран с данными по curated-понятию
(national → listed eurostat → unlisted eurostat → прочее). Жила в
``api.world``; вынесена, чтобы российская мета не импортировала роутер.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.eurostat_listing import normalize_frequency
from app.data.world_concept_national import national_codes_for_concept
from app.data.world_concept_russia import (
    concept_slug_for_russia_code,
    russia_link_for_concept,
)
from app.data.world_concepts import (
    CONCEPT_BY_SLUG,
    concept_for_indicator,
    concept_public_name,
    concept_public_unit,
)
from app.models import WorldCountry, WorldIndicator
from app.services.locale import get_locale
from app.services.world_rank_values import (
    YOY_KIND_INDEX_MINUS_100,
    YOY_KIND_LEVEL,
    money_unit_compatible,
    rank_yoy_kind,
    ranking_display_name,
    ranking_public_unit,
    ranking_value_mode,
)

MONEY_COMPARE_CONCEPTS = frozenset({
    "gdp-volume-quarterly",
    "gdp-volume-annual",
    "gdp-usd",
    "gdp-per-capita-usd",
})

# Режим российской карточки, в котором единицы совпадают с концептом.
# Нет записи — блок не отдаём (fail-closed).
_COMPARE_VIEW_SPEC: dict[str, dict] = {
    "hicp-index": {
        "modes": ("inflation", "inflation-quarter", "inflation-year"),
        "default": "inflation",
        "peer_mode": "yoy-monthly",
    },
    "unemployment-rate": {
        "modes": (
            "level", "eop-quarter", "eop-year", "avg-quarter", "avg-year",
            "quarterly", "annual",
        ),
        "default": "level",
        "peer_mode": "level-monthly",
    },
    "population": {
        "modes": ("level",),
        "default": "level",
        "peer_mode": "level-annual",
    },
    "gdp-usd": {
        "modes": ("level",),
        "default": "level",
        "peer_mode": "level-annual",
    },
    "gdp-per-capita-usd": {
        "modes": ("level",),
        "default": "level",
        "peer_mode": "level-annual",
    },
    "budget-balance-gdp": {
        "modes": ("level",),
        "default": "level",
        "peer_mode": "level-annual",
    },
    "government-debt-gdp": {
        "modes": ("level",),
        "default": "level",
        "peer_mode": "level-annual",
    },
}

# Страны для SSR-перелинковки Россия ↔ мир. Канон пары — алфавит слагов.
_SSR_VS_COUNTRIES = ("germany", "united-states", "france", "china", "japan")


def concept_unit_compatible(concept, indicator: WorldIndicator) -> bool:
    if concept.slug not in MONEY_COMPARE_CONCEPTS:
        return True
    return money_unit_compatible(concept.measure, indicator.unit, indicator.unit_ru)


def concept_member_rank(indicator: WorldIndicator, national_codes: frozenset[str]) -> int:
    """National, listed eurostat, unlisted eurostat, other listed, other unlisted.

    Unlisted eurostat того же среза (national-passport suppress) должен
    выигрывать у listed IMF: японская безработица une_rt_m глубже годовой
    оценки фонда. Раньше равенство listed держалось на сортировке кодов.
    """
    if indicator.code in national_codes:
        return 0
    provider = str(indicator.provider or "").lower()
    listed = bool(indicator.is_listed)
    if provider == "eurostat":
        return 1 if listed else 2
    return 3 if listed else 4


async def concept_members(
    db: AsyncSession,
    concept,
) -> list[tuple[WorldCountry, WorldIndicator]]:
    # Не тянем всю таблицу world_indicators (после deep-expand — 100k+ строк):
    # listed + dataset_id понятия (+ явный national crosswalk). Unlisted
    # eurostat того же среза — только как fallback карты/рейтинга, когда у
    # активной страны нет listed-члена (national-passport suppress или
    # unlist после is_active=false). Каталог страны по-прежнему listed-only.
    allowed = {
        str(ds).lower()
        for ds in concept.dataset_ids
    }
    if concept.provider_dataset_ids:
        for ids in concept.provider_dataset_ids.values():
            allowed.update(str(ds).lower() for ds in ids)
    national_codes = national_codes_for_concept(concept.slug)
    allowed_list = sorted(allowed)
    listed_match = (
        or_(
            func.lower(WorldIndicator.dataset_id).in_(allowed_list),
            WorldIndicator.code.in_(sorted(national_codes)),
        )
        if national_codes
        else func.lower(WorldIndicator.dataset_id).in_(allowed_list)
    )
    rows = (
        await db.execute(
            select(WorldCountry, WorldIndicator)
            .join(WorldIndicator, WorldIndicator.country_id == WorldCountry.id)
            .where(
                WorldCountry.is_active.is_(True),
                or_(
                    and_(WorldIndicator.is_listed.is_(True), listed_match),
                    and_(
                        WorldIndicator.is_listed.is_(False),
                        WorldIndicator.points_count > 0,
                        WorldIndicator.history_end >= date(2020, 1, 1),
                        func.lower(WorldIndicator.dataset_id).in_(allowed_list),
                    ),
                ),
            )
            .order_by(WorldCountry.sort_order, WorldCountry.name_ru, WorldIndicator.code)
        )
    ).all()
    members: list[tuple[WorldCountry, WorldIndicator]] = []
    for country, indicator in rows:
        if indicator.code in national_codes:
            if concept_unit_compatible(concept, indicator):
                members.append((country, indicator))
            continue
        if (
            concept_for_indicator(indicator) == concept
            and concept_unit_compatible(concept, indicator)
        ):
            members.append((country, indicator))
    by_country: dict[int, tuple[WorldCountry, WorldIndicator]] = {}
    for country, indicator in members:
        prev = by_country.get(country.id)
        if prev is None or _compare_member_sort_key(
            indicator, national_codes,
        ) < _compare_member_sort_key(prev[1], national_codes):
            by_country[country.id] = (country, indicator)
    return list(by_country.values())


def _compare_member_sort_key(
    indicator: WorldIndicator,
    national_codes: frozenset[str],
) -> tuple:
    """Меньше = лучше: national → listed eurostat → свежий хвост → код."""
    end = indicator.history_end or date.min
    return (
        concept_member_rank(indicator, national_codes),
        -end.toordinal(),
        indicator.code or "",
    )


def choose_compare_indicator(
    indicators: list[WorldIndicator],
    concept,
    national_codes: frozenset[str],
) -> WorldIndicator | None:
    """Один ряд страны для compare/series: не 409, если есть преемник.

    National crosswalk важнее eurostat. Среди eurostat — listed, затем
    более поздний ``history_end`` (живой ``prc_hicp_minr`` бьёт замороженный
    ``prc_hicp_midx`` с тем же срезом корзины).
    """
    members = [
        indicator
        for indicator in indicators
        if concept_for_indicator(indicator) == concept
        or (
            indicator.code in national_codes
            and concept_unit_compatible(concept, indicator)
        )
    ]
    if not members:
        return None
    national = [item for item in members if item.code in national_codes]
    pool = national or members
    return min(pool, key=lambda item: _compare_member_sort_key(item, national_codes))


def _country_display_name(country: WorldCountry) -> str:
    if get_locale() == "en" and (country.name_en or "").strip():
        return country.name_en
    return country.name_ru


def peer_fetch_mode(concept, indicator: WorldIndicator) -> tuple[str, str | None]:
    """Мировой ?mode= для overlay на российской карточке + правка единиц.

    Для hicp индекс Евростата нужно перевести в изменение за год; ряды, которые
    уже в %, берём уровнем; китайский «тот же месяц = 100» — уровень минус 100.
    """
    freq = normalize_frequency(indicator.frequency) or "monthly"
    if concept.slug != "hicp-index":
        return f"level-{freq}", None
    kind = rank_yoy_kind(indicator)
    if kind == YOY_KIND_LEVEL:
        return f"yoy-{freq}", None
    if kind == YOY_KIND_INDEX_MINUS_100:
        return f"level-{freq}", "minus_100"
    return f"level-{freq}", None


async def russia_world_compare_payload(
    db: AsyncSession,
    indicator_code: str,
) -> dict | None:
    """Блок ``world_compare`` для меты российского индикатора, или None."""
    slug = concept_slug_for_russia_code(indicator_code)
    if not slug:
        return None
    concept = CONCEPT_BY_SLUG.get(slug)
    if concept is None or "compare" not in concept.enabled_surfaces:
        return None
    link = russia_link_for_concept(slug)
    spec = _COMPARE_VIEW_SPEC.get(slug)
    if link is None or spec is None:
        return None

    members = await concept_members(db, concept)
    rank_mode = ranking_value_mode(slug, members)
    loc = get_locale()
    peers = []
    for country, indicator in members:
        peer_mode, value_adjust = peer_fetch_mode(concept, indicator)
        peers.append({
            "country_code": country.code,
            "country_slug": country.slug,
            "country_name": _country_display_name(country),
            "country_name_en": country.name_en,
            "indicator_code": indicator.code,
            "frequency": normalize_frequency(indicator.frequency),
            "peer_mode": peer_mode,
            "value_adjust": value_adjust,
        })
    peers.sort(key=lambda item: (item["country_name"] or "").lower())

    scale = float(link.scale or 1.0)
    peer_value_scale = (1.0 / scale) if scale not in (0.0, 1.0) else 1.0
    return {
        "concept": {
            "slug": slug,
            "name": ranking_display_name(
                rank_mode, slug, concept_public_name(concept), locale=loc,
            ),
            "name_en": ranking_display_name(
                rank_mode, slug, concept_public_name(concept), locale="en",
            ),
            "unit": ranking_public_unit(
                rank_mode, concept_public_unit(concept), locale=loc,
            ),
            "value_kind": link.value_kind,
            "link_code": link.indicator_code,
            "compatible_modes": list(spec["modes"]),
            "default_mode": spec["default"],
            "peer_mode": spec["peer_mode"],
            "peer_value_scale": peer_value_scale,
        },
        "peers": peers,
    }


def russia_world_compare_ssr_links(indicator_code: str) -> list[tuple[str, str]] | None:
    """Пути SSR: рейтинг концепта и пары vs-Россия. None — концепта нет."""
    from app.services import site_paths as paths
    from app.services.seo_world_compare import world_vs_path

    slug = concept_slug_for_russia_code(indicator_code)
    if not slug:
        return None
    concept = CONCEPT_BY_SLUG.get(slug)
    if concept is None or "compare" not in concept.enabled_surfaces:
        return None
    if slug not in _COMPARE_VIEW_SPEC:
        return None
    links = [(paths.world_rating(slug), "rating")]
    for other in _SSR_VS_COUNTRIES:
        a, b = sorted((other, "russia"))
        links.append((world_vs_path(a, b, slug), "vs"))
    return links
