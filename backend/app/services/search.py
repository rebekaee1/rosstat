"""Federated public search over bounded metadata and indexed world candidates.

Facts/explicit geography/periods gate candidates before limits. Russia and world
retain their bounded contexts and public eligibility rules. No external calls,
analytics writes, model training or new persistence.
"""

from __future__ import annotations

from datetime import date
from dataclasses import replace
from functools import lru_cache
import re
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import and_, case, exists, literal, literal_column, or_, select, true
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import load_only

from app.data.global_market_indicators import COUNTRY_MARKET_INDICATOR_CODES, is_global_market_indicator, market_indicator_codes_for_country
from app.data.world_concept_national import national_codes_for_concept
from app.data.world_concepts import concept_for_indicator, concept_public_unit
from app.data.eurostat_listing import normalize_frequency
from app.data.eurostat_titles_ru import listing_category_ru
from app.models import (
    Indicator, IndicatorData, Region, RegionDataPoint, RegionIndicator,
    RegionMonthlyPoint, SubnationalDataPoint, SubnationalIndicator,
    SubnationalRegion, WorldCountry, WorldDataPoint, WorldIndicator,
)
from app.services import site_paths as paths
from app.services.locale import get_locale
from app.services.search_intent import (
    SEARCH_VERSION, SearchIntent, geo_aliases, match_score, normalize, parse_intent, phrase,
)
from app.services.search_paths import russia_family_base, russia_search_path, world_search_paths
from app.services.seo_i18n import localize_category_name, public_indicator_fields, region_display_name, region_indicator_copy
from app.services.world_subnational_ingest import country_has_subnational

_MAX_CANDIDATES = 500
_PERCENT_UNITS = ("PC", "PCT", "PERCENT", "RCH_A", "RCH_M", "RCH_MV12MAVR", "RCH_A_AVG", "RT1", "RT1-SCA",
    "PCH_SM", "PCH_PRE", "PCH_SAME", "PCH_M1", "PCPIPCH", "PCPIEPCH", "NGDP_RPCH", "NGDP_RPC")
_INTENT_CONCEPTS = {
    "cpi": "hicp-index", "unemployment": "unemployment-rate", "population": "population",
    "gdp-per-capita": "gdp-per-capita-usd", "gdp": "gdp-volume-quarterly",
}
_REGION_HEADLINES = {
    "wage": "srednemesyachnaya-nominalnaya-nachislennaya-zarabotnaya-plata-rabotnikov-organizatsiy",
}
_RUSSIA_HEADLINES = {
    "cpi": "cpi", "gdp": "gdp-nominal", "wage": "wages-nominal", "unemployment": "unemployment",
    "key-rate": "key-rate", "fuel": "fuel", "fuel-ai95": "fuel-ai95", "fuel-ai92": "fuel-ai92",
    "fuel-diesel": "fuel-diesel", "pension": "pensioners",
    "exports": "exports", "imports": "imports",
}


@lru_cache(maxsize=1)
def _family_metadata() -> dict[str, str]:
    """Human mode vocabulary comes from existing materialized family rows."""
    from app.data.view_model_families import FAMILIES
    metadata: dict[str, str] = {}
    for family in FAMILIES:
        for mode in family.modes:
            # Annual YoY and period-on-period can share the same annual series;
            # keep both valid intents instead of overwriting the first group.
            metadata[mode.code] = metadata.get(mode.code, "") + f" {family.name} {mode.label} search-mode-{mode.group} search-freq-{mode.frequency}"
    return metadata


def _intent_concept(intent: SearchIntent) -> str | None:
    terms = [term for term in intent.terms if not term[0].startswith("search-")]
    if len(terms) != 1:
        return None
    return _INTENT_CONCEPTS.get(terms[0][0])


def _intent_frequency(intent: SearchIntent) -> str | None:
    return next((alt.removeprefix("search-freq-") for term in intent.terms for alt in term
        if alt.startswith("search-freq-")), None)


def _unit_metadata(*units) -> str:
    """Explicit percent intent checks actual units, never SEO/name text."""
    points = ("percentage point", "percent point", "процентных пункт", "процентные пункт", "п.п.")
    if any(normalize(unit).upper() == "PC_PNT" or any(value in normalize(unit) for value in points) for unit in units):
        return ""
    for unit in units:
        raw = normalize(unit)
        if "%" in raw or "percent" in raw or "процент" in raw or raw.upper() in _PERCENT_UNITS or (raw.upper().startswith("PC_") and raw.upper() != "PC_PNT"):
            return "search-unit-percent"
    return ""


def _world_preference(intent: SearchIntent):
    """Catalogue headline identities, not a popularity prior."""
    concept = _intent_concept(intent)
    clauses = []
    if concept:
        codes = national_codes_for_concept(concept)
        if codes:
            clauses.append(WorldIndicator.code.in_(codes))
    if concept == "hicp-index":
        clauses.extend((WorldIndicator.code.like("%-prc_hicp_midx-cp00-%"),
            WorldIndicator.code.like("%-prc_hicp_minr-cp00-%")))
    return or_(*clauses) if clauses else literal(False)


def _world_bonus(row, intent: SearchIntent) -> int:
    concept = _intent_concept(intent)
    if not concept:
        return 0
    if row.code in national_codes_for_concept(concept):
        return 160
    if concept == "hicp-index" and any(stem in row.code for stem in ("-prc_hicp_midx-cp00-", "-prc_hicp_minr-cp00-")):
        return 140
    resolved = concept_for_indicator(row)
    return 140 if resolved and resolved.slug == concept else 0


def _world_unit(row, locale: str) -> str:
    """Same concept/unit-class/public-label rules as the world catalogue."""
    ru = (row.unit_ru or row.unit or "").strip()
    if locale != "en":
        return ru
    from app.data.eurostat_listing import measure_class
    from app.data.eurostat_units_ru import unit_label_en_for_code
    from app.services.display import public_unit_en

    concept = concept_for_indicator(row)
    if concept:
        expected = (concept.provider_measures or {}).get(str(row.provider or "").lower(), concept.measure)
        if measure_class(row.unit, row.unit_ru) == expected:
            return concept_public_unit(concept) or ru
    label = (unit_label_en_for_code(row.unit) or "").strip()
    vague = {"rate", "number", "average", "person", "persons", "index", "ratio", "score", "total", "value", "unit", "percentage"}
    return label if label and label.lower() not in vague else public_unit_en(row.unit_ru, unit_storage=row.unit)


def _finite(column):
    # All fact columns have precision <=20. Bounds exclude PG NaN/Infinity and
    # are outside every representable finite economic value of these columns.
    return and_(column.is_not(None), column > literal_column("-1e30"), column < literal_column("1e30"))


def _date_constraints(column, intent: SearchIntent):
    if intent.year is None:
        return []
    year, month = intent.year, intent.month
    start = date(year, month or 1, 1)
    end = date(year + 1, 1, 1) if month is None or month == 12 else date(year, month + 1, 1)
    return [column >= start, column < end]


def _annual_fact(intent: SearchIntent):
    conditions = [RegionDataPoint.indicator_id == RegionIndicator.id,
        RegionDataPoint.region_id == Region.id, _finite(RegionDataPoint.value)]
    if intent.year is not None:
        conditions.append(RegionDataPoint.year == intent.year)
    if intent.month is not None:
        return literal(False)
    return exists(select(1).where(*conditions))


def _monthly_fact(intent: SearchIntent):
    conditions = [RegionMonthlyPoint.indicator_id == RegionIndicator.id,
        RegionMonthlyPoint.region_id == Region.id, _finite(RegionMonthlyPoint.value)]
    if intent.year is not None:
        if intent.month is None:
            conditions.extend((RegionMonthlyPoint.month >= intent.year * 100 + 1,
                RegionMonthlyPoint.month <= intent.year * 100 + 12))
        else:
            conditions.append(RegionMonthlyPoint.month == intent.year * 100 + intent.month)
    return exists(select(1).where(*conditions))


def _world_fact(intent: SearchIntent):
    return exists(select(1).where(WorldDataPoint.indicator_id == WorldIndicator.id,
        WorldDataPoint.value != literal_column("0"), _finite(WorldDataPoint.value),
        *_date_constraints(WorldDataPoint.date, intent)))


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _world_lexical(intent: SearchIntent, *, postgres: bool):
    clauses = []
    for alternatives in intent.terms:
        term_clauses = []
        for alternative in alternatives:
            if alternative == "search-unit-percent":
                percentage_points = or_(WorldIndicator.unit == "PC_PNT",
                    WorldIndicator.unit.ilike("%percentage point%"), WorldIndicator.unit.ilike("%percent point%"),
                    WorldIndicator.unit_ru.ilike("%процентных пункт%"), WorldIndicator.unit_ru.ilike("%процентные пункт%"),
                    WorldIndicator.unit_ru.ilike("%п.п.%"))
                term_clauses.append(and_(percentage_points.is_not(True), or_(WorldIndicator.unit.in_(_PERCENT_UNITS),
                    and_(WorldIndicator.unit.like("PC\\_%", escape="\\"), WorldIndicator.unit != "PC_PNT"),
                    WorldIndicator.unit.contains("%"), WorldIndicator.unit_ru.contains("%"),
                    WorldIndicator.unit.ilike("%percent%"), WorldIndicator.unit_ru.ilike("%процент%"))))
                continue
            if alternative.startswith("search-freq-"):
                frequency = alternative.removeprefix("search-freq-")
                aliases = {"annual": ("annual", "yearly", "A"), "monthly": ("monthly", "M"), "quarterly": ("quarterly", "Q"),
                    "weekly": ("weekly", "W"), "daily": ("daily", "D")}.get(frequency, (frequency,))
                term_clauses.append(WorldIndicator.frequency.in_(aliases))
                continue
            if alternative.startswith("search-mode-"):
                mode = alternative.removeprefix("search-mode-")
                if mode == "level":
                    # A native value may be an unemployment/employment rate,
                    # not just an index. Level is the stored series identity;
                    # metadata names/measure still constrain the economic topic.
                    term_clauses.append(literal(True))
                    continue
                phrases = {"yoy": ("year-on-year", "annual rate of change", "изменение за год"),
                    "avg": ("average", "средн"), "pop": ("month-on-month", "quarter-on-quarter", "изменение за месяц"),
                    "level": ("index", "индекс")}.get(mode, ())
                term_clauses.extend(WorldIndicator.name_en.ilike(f"%{p}%") for p in phrases)
                term_clauses.extend(WorldIndicator.name_ru.ilike(f"%{p}%") for p in phrases)
                term_clauses.append(WorldIndicator.code.ilike(f"%-{mode}%"))
                continue
            needle = _escape_like(normalize(alternative))
            # A short whole query stays a prefix lookup. A short term inside a
            # qualified longer query (IPCA 12-month) must match anywhere; the
            # other required terms keep that candidate lookup bounded.
            prefix_only = len(needle) < 3 and len(intent.terms) == 1
            pattern = f"{needle}%" if prefix_only else f"%{needle}%"
            columns = (WorldIndicator.code, WorldIndicator.name_ru, WorldIndicator.name_en, WorldIndicator.seo_keywords)
            if "=" in alternative or (alternative.startswith("i") and alternative[1:].isdigit()):
                columns += (WorldIndicator.unit, WorldIndicator.unit_ru)
            for column in columns:
                term_clauses.append(column.ilike(pattern, escape="\\"))
            if postgres and len(alternatives) == 1 and len(needle) >= 5 and " " not in needle:
                for column in (WorldIndicator.name_ru, WorldIndicator.name_en):
                    term_clauses.append(literal(needle).op("<%")(column))
        clauses.append(or_(*term_clauses))
    return clauses


def _world_mode_metadata(row) -> str:
    """Recognize official native measures without inferring a new derived row."""
    name = normalize(f"{row.name_ru} {row.name_en}")
    metadata = f"search-mode-level search-freq-{normalize_frequency(row.frequency) or row.frequency}"
    if any(label in name for label in ("year-on-year", "annual rate of change", "12-month accumulated", "изменение за год")) or "-yoy" in row.code:
        metadata += " search-mode-yoy"
    if any(label in name for label in ("month-on-month", "quarter-on-quarter", "изменение за месяц")):
        metadata += " search-mode-pop"
    if "average" in name or "средн" in name:
        metadata += " search-mode-avg"
    return metadata


def _period_path(base: str, intent: SearchIntent, *, world: bool = False, regional: bool = False) -> tuple[str, str]:
    if intent.year is None:
        return base, "spa"
    parts = urlsplit(base)
    # SSR-period+mode contracts currently do not support retaining arbitrary
    # modes; callers skip these candidates rather than dropping mode.
    segments = parts.path.strip("/").split("/")
    if len(segments) == 3 and segments[1] == "indicator":
        country, _indicator, code = segments
        if country in ("russia", "currencies"):
            path = paths.russia_indicator_year(code, intent.year) if intent.month is None else paths.russia_indicator_month(code, intent.year, intent.month)
        else:
            path = paths.indicator_year(country, code, intent.year) if intent.month is None else paths.indicator_month(country, code, intent.year, intent.month)
    elif len(segments) == 4 and segments[1] == "region" and intent.month is None:
        country, _region, region_slug, code = segments
        path = paths.region_indicator_year(region_slug, code, intent.year) if country == "russia" else paths.country_region_indicator_year(country, region_slug, code, intent.year)
    else:
        raise ValueError("unsupported search period destination")
    return urlunsplit(("", "", path, parts.query, "")), "document"


async def _geometry(db: AsyncSession) -> tuple[list[dict], dict[str, WorldCountry]]:
    countries = list((await db.execute(select(WorldCountry).where(WorldCountry.is_active.is_(True)))).scalars())
    by_slug = {item.slug: item for item in countries}
    geometry = [{"key": "country:russia", "kind": "country", "slug": "russia",
        "name_ru": "Россия", "name_en": "Russia", "country_slug": "russia", "country_code": "RU", "id": None}]
    for country in countries:
        if country.slug == "russia":
            continue
        geometry.append({"key": f"country:{country.slug}", "kind": "country", "slug": country.slug,
            "name_ru": country.name_ru, "name_en": country.name_en,
            "country_slug": country.slug, "country_code": country.code, "id": country.id})
    regions = list((await db.execute(select(Region).where(Region.kind.in_(("region", "district"))))).scalars())
    for region in regions:
        geometry.append({"key": f"region:russia:{region.slug}", "kind": "region", "slug": region.slug,
            "name_ru": region.name, "name_en": region_display_name(region.slug, region.name, locale="en"),
            "country_slug": "russia", "country_code": "RU", "id": region.id})
    subnational = list((await db.execute(select(SubnationalRegion))).scalars())
    by_code = {country.code: country for country in countries if country_has_subnational(country.code)}
    for region in subnational:
        country = by_code.get(region.country_code)
        if country:
            geometry.append({"key": f"region:{country.slug}:{region.slug}", "kind": "subnational_region", "slug": region.slug,
                "name_ru": region.name_ru, "name_en": region.name_en, "country_slug": country.slug,
                "country_code": country.code, "id": region.id})
    return geometry, by_slug


def _eligible_geo(item: dict, intent: SearchIntent) -> bool:
    return (not intent.countries or item["country_slug"] in intent.countries) and (
        not intent.regions or item["key"] in intent.regions)


async def _entities(db: AsyncSession, geometry: list[dict], intent: SearchIntent, locale: str) -> list[dict]:
    output = []
    if intent.year is not None:
        return output
    candidates = []
    for item in geometry:
        if not _eligible_geo(item, intent) or (not intent.terms and not intent.regions and item["kind"] != "country"):
            continue
        score = match_score(intent, code=item["slug"], names=geo_aliases(item))
        if score is None or (not intent.terms and not intent.countries):
            continue
        candidates.append((item, score))
    allowed = set()
    country_ids = [item["id"] for item, _score in candidates if item["kind"] == "country" and item["id"] is not None]
    if country_ids:
        rows = await db.execute(select(WorldIndicator.country_id).where(WorldIndicator.country_id.in_(country_ids),
            WorldIndicator.is_listed.is_(True), _world_fact(intent)).distinct())
        allowed.update(("country", item) for item in rows.scalars())
    if any(item["kind"] == "country" and item["country_slug"] == "russia" for item, _score in candidates):
        fact = exists(select(1).select_from(Indicator).where(Indicator.is_active.is_(True),
            exists(select(1).where(IndicatorData.indicator_id == Indicator.id, _finite(IndicatorData.value)))))
        if (await db.execute(select(fact))).scalar():
            allowed.add(("country", None))
    region_ids = [item["id"] for item, _score in candidates if item["kind"] == "region"]
    if region_ids:
        annual = select(RegionDataPoint.region_id).where(RegionDataPoint.region_id.in_(region_ids), _finite(RegionDataPoint.value))
        monthly = select(RegionMonthlyPoint.region_id).where(RegionMonthlyPoint.region_id.in_(region_ids), _finite(RegionMonthlyPoint.value))
        rows = await db.execute(annual.union(monthly))
        allowed.update(("region", item) for item in rows.scalars())
    subnational_ids = [item["id"] for item, _score in candidates if item["kind"] == "subnational_region"]
    if subnational_ids:
        rows = await db.execute(select(SubnationalDataPoint.region_id).join(SubnationalIndicator,
            SubnationalIndicator.id == SubnationalDataPoint.indicator_id).where(
            SubnationalDataPoint.region_id.in_(subnational_ids), SubnationalIndicator.is_listed.is_(True),
            _finite(SubnationalDataPoint.value)).distinct())
        allowed.update(("subnational_region", item) for item in rows.scalars())
    country_names = {item["country_slug"]: item["name_en"] if locale == "en" else item["name_ru"]
        for item in geometry if item["kind"] == "country"}
    for item, score in candidates:
        if (item["kind"], item["id"]) not in allowed:
            continue
        if item["kind"] == "country":
            path = paths.country(item["country_slug"])
        elif item["kind"] == "region":
            path = paths.region(item["slug"])
        else:
            path = paths.country_region(item["country_slug"], item["slug"])
        output.append({"key": item["key"], "kind": item["kind"], "name": item["name_en"] if locale == "en" else item["name_ru"],
            "name_ru": item["name_ru"], "name_en": item["name_en"], "country_slug": item["country_slug"],
            "region_slug": item["slug"] if item["kind"] != "country" else None,
            "country_name": country_names.get(item["country_slug"], item["country_slug"]),
            "path": path, "score": 950 if not intent.terms else score})
    return output


async def _russia(db: AsyncSession, intent: SearchIntent, locale: str) -> list[dict]:
    if intent.regions:
        return []
    market_bases = {base for country in intent.countries for base in market_indicator_codes_for_country(country)}
    if "united-states" in intent.countries and any(term[0] == "usd-rub" for term in intent.terms):
        market_bases.add("usd-rub")
    if intent.countries and "russia" not in intent.countries and not market_bases:
        return []
    rows = list((await db.execute(select(Indicator).where(Indicator.is_active.is_(True),
        exists(select(1).where(IndicatorData.indicator_id == Indicator.id, _finite(IndicatorData.value),
            *_date_constraints(IndicatorData.date, intent)))))).scalars())
    output = []
    for row in rows:
        market_country = None
        if intent.countries and "russia" not in intent.countries:
            if not any(row.code == base or row.code.startswith(base + "-") for base in market_bases):
                continue
            market_country = next(iter(sorted(intent.countries)))
        en = public_indicator_fields(row.code, name_ru=row.name, name_en=row.name_en, unit_ru=row.unit, locale="en")
        ru = public_indicator_fields(row.code, name_ru=row.name, name_en=row.name_en, unit_ru=row.unit, locale="ru")
        score = match_score(intent, code=row.code, names=(row.name, row.name_en or "", en["name"] or ""),
            metadata=" ".join(filter(None, (row.category, row.seo_keywords, row.frequency, row.unit,
                f"search-freq-{normalize_frequency(row.frequency) or row.frequency}",
                _family_metadata().get(row.code) or "search-mode-level", _unit_metadata(row.unit)))))
        if score is None:
            continue
        content_terms = [term for term in intent.terms if not term[0].startswith("search-")]
        if len(content_terms) == 1:
            headline = _RUSSIA_HEADLINES.get(content_terms[0][0])
            if headline and (row.code == headline or russia_family_base(row.code) == headline):
                score += 180
        base = russia_search_path(row.code, intent)
        if intent.year is not None and urlsplit(base).query:
            continue
        if intent.month is not None and row.frequency in ("annual", "yearly", "quarterly"):
            continue
        path, navigation = _period_path(base, intent)
        market_issuer = next((country for country in COUNTRY_MARKET_INDICATOR_CODES
            if any(row.code == code or row.code.startswith(code + "-") for code in market_indicator_codes_for_country(country))), None)
        if is_global_market_indicator(row.code):
            country_name = ("United States" if locale == "en" else "США") if market_country == "united-states" or market_issuer == "united-states" else ("Global markets" if locale == "en" else "Мировой рынок")
        else:
            country_name = ("United States" if locale == "en" else "США") if market_country == "united-states" else ("Russia" if locale == "en" else "Россия")
        output.append({"key": f"ru:{row.code}", "kind": "russia", "code": row.code,
            "name": (en if locale == "en" else ru)["name"], "name_ru": ru["name"], "name_en": en["name"],
            "country_slug": market_country or "russia", "country_name": country_name,
            "category": localize_category_name(row.category, locale=locale), "frequency": row.frequency, "unit": (en if locale == "en" else ru)["unit"],
            "path": path, "navigation": navigation, "score": score + (2 if row.is_listed else 0)})
    return output


async def _world(db: AsyncSession, intent: SearchIntent, countries: dict[str, WorldCountry], locale: str, budget: int) -> tuple[list[dict], bool]:
    if intent.regions or intent.countries == frozenset(("russia",)):
        return [], False
    # One-letter autocomplete stays in compact local/entity catalogues.
    if intent.terms and not intent.countries and all(len(alt) < 3 for term in intent.terms for alt in term):
        return [], False
    selected = [c.id for slug, c in countries.items() if not intent.countries or slug in intent.countries]
    if not selected:
        return [], False
    columns = (WorldIndicator.id, WorldIndicator.code, WorldIndicator.country_id, WorldIndicator.provider,
        WorldIndicator.dataset_id, WorldIndicator.slice_json, WorldIndicator.slice_hash, WorldIndicator.name_ru,
        WorldIndicator.name_en, WorldIndicator.unit, WorldIndicator.unit_ru, WorldIndicator.frequency,
        WorldIndicator.category_ru, WorldIndicator.seo_keywords, WorldIndicator.is_listed, WorldIndicator.points_count)
    postgres = db.get_bind().dialect.name == "postgresql"
    needle = _escape_like(intent.content)
    # All explicit geography and fact constraints precede candidate LIMIT.
    stmt = select(WorldIndicator).options(load_only(*columns)).where(
        WorldIndicator.country_id.in_(selected), _world_fact(intent), *_world_lexical(intent, postgres=postgres))
    stmt = stmt.order_by(case((WorldIndicator.code.ilike(_escape_like(intent.query), escape="\\"), 0),
        (WorldIndicator.code.ilike(needle, escape="\\"), 0),
        (WorldIndicator.name_ru.ilike(needle, escape="\\"), 1),
        (WorldIndicator.name_en.ilike(needle, escape="\\"), 1),
        (_world_preference(intent), 2), else_=3),
        WorldIndicator.is_listed.desc(), WorldIndicator.code).limit(budget + 1)
    rows = list((await db.execute(stmt)).scalars())
    clipped = len(rows) > budget
    by_id = {country.id: country for country in countries.values()}
    output = []
    for row in rows[:budget]:
        # Request-local metadata retained for batch canonical resolution of the
        # final ranked candidates; never serialized into the public response.
        db.info.setdefault("fe_search_world_rows", {})[(by_id[row.country_id].slug, row.code)] = row
        country = by_id[row.country_id]
        score = match_score(intent, code=row.code, names=(row.name_ru, row.name_en or ""),
            metadata=" ".join(filter(None, (row.category_ru, row.seo_keywords, row.frequency, row.unit, row.unit_ru,
                _world_mode_metadata(row), _unit_metadata(row.unit, row.unit_ru)))))
        if score is None:
            continue
        if intent.year is not None and not row.is_listed:
            # Hidden rows with signal are accessible through SPA/API, but the
            # standalone SSR period renderer requires a listed canonical row.
            continue
        # Hidden slices are reachable when data-backed. Canonical frequency
        # siblings use the same authoritative resolver as SSR.
        base = paths.indicator(country.slug, row.code)
        if intent.month is not None and row.frequency in ("annual", "yearly", "quarterly", "A", "Q"):
            continue
        path, navigation = _period_path(base, intent, world=True)
        output.append({"key": f"world:{country.slug}:{row.code}", "kind": "world", "code": row.code,
            "name": row.name_en or row.name_ru if locale == "en" else row.name_ru,
            "name_ru": row.name_ru, "name_en": row.name_en,
            "country_slug": country.slug, "country_name": country.name_en if locale == "en" else country.name_ru,
            "category": localize_category_name(listing_category_ru(row.dataset_id, row.category_ru, provider=row.provider), locale=locale),
            "frequency": row.frequency, "unit": _world_unit(row, locale),
            "path": path, "navigation": navigation, "score": score + _world_bonus(row, intent) + (2 if row.is_listed else 0)})
    return output, clipped


async def _regions(db: AsyncSession, intent: SearchIntent, geometry: list[dict], locale: str, budget: int) -> tuple[list[dict], bool]:
    selected = {item["id"]: item for item in geometry if item["kind"] == "region" and _eligible_geo(item, intent)}
    frequency = _intent_frequency(intent)
    if not selected or intent.month is not None or frequency not in (None, "annual", "monthly"):
        # There is no monthly regional period route. Annual period routes are
        # backed only by annual facts, while ordinary cards can show monthly.
        return [], False
    definitions = list((await db.execute(select(RegionIndicator).where(RegionIndicator.is_listed.is_(True)))).scalars())
    definition_intent = replace(intent, terms=tuple(term for term in intent.terms if not term[0].startswith("search-freq-")))
    candidates, copies = {}, {}
    for row in definitions:
        en = region_indicator_copy(row.code, name_ru=row.name, unit_ru=row.unit, section_ru=row.section_name, locale="en")
        score = match_score(definition_intent, code=row.code, names=(row.name, en["name"] or ""), metadata=f"{row.unit} {row.section_name} search-mode-level {_unit_metadata(row.unit, en['unit'])}")
        if score is not None:
            if len(intent.terms) == 1 and row.code == _REGION_HEADLINES.get(intent.terms[0][0]):
                score += 160
            candidates[row.id], copies[row.id] = score, en
    if not candidates:
        return [], False
    annual = literal(False) if frequency == "monthly" else _annual_fact(intent)
    monthly = literal(False) if frequency == "annual" else _monthly_fact(intent)
    usable = annual if intent.year is not None else or_(annual, monthly)
    stmt = select(Region, RegionIndicator, monthly.label("monthly"), annual.label("annual")).select_from(RegionIndicator).join(Region, true()).where(
        RegionIndicator.id.in_(candidates), Region.id.in_(selected), usable).order_by(
        case(candidates, value=RegionIndicator.id).desc(), Region.sort_order, RegionIndicator.code).limit(budget + 1)
    rows = (await db.execute(stmt)).all()
    output = []
    for region, row, has_monthly, has_annual in rows[:budget]:
        geo, en = selected[region.id], copies[row.id]
        base = paths.region_indicator(region.slug, row.code)
        path, navigation = _period_path(base, intent, regional=True)
        name = en["name"] if locale == "en" else row.name
        output.append({"key": f"region:{region.slug}:{row.code}", "kind": "region_indicator", "code": row.code,
            "name": name, "name_ru": row.name, "name_en": en["name"], "country_slug": "russia",
            "country_name": "Russia" if locale == "en" else "Россия", "region_slug": region.slug,
            "region_name": geo["name_en"] if locale == "en" else geo["name_ru"], "category": en["section"] if locale == "en" else row.section_name,
            "frequency": "monthly" if has_monthly and intent.year is None else "annual",
            "unit": en["unit"] if locale == "en" else row.unit, "path": path, "navigation": navigation,
            "score": candidates[row.id]})
    return output, len(rows) > budget


async def _subnational(db: AsyncSession, intent: SearchIntent, geometry: list[dict], locale: str, budget: int) -> tuple[list[dict], bool]:
    selected = {item["id"]: item for item in geometry if item["kind"] == "subnational_region" and _eligible_geo(item, intent)}
    if not selected or intent.month is not None:
        return [], False
    codes = {item["country_code"] for item in selected.values()}
    definitions = list((await db.execute(select(SubnationalIndicator).where(
        SubnationalIndicator.country_code.in_(codes), SubnationalIndicator.is_listed.is_(True)))).scalars())
    candidates = {}
    for row in definitions:
        score = match_score(intent, code=row.code, names=(row.name_ru, row.name_en),
            metadata=f"{row.unit} {row.unit_ru} {row.unit_en} {row.section_ru} {row.section_en} {row.frequency} search-mode-level search-freq-{normalize_frequency(row.frequency) or row.frequency} {_unit_metadata(row.unit, row.unit_ru, row.unit_en)}")
        if score is not None:
            candidates[row.id] = score
    if not candidates:
        return [], False
    fact = exists(select(1).where(SubnationalDataPoint.indicator_id == SubnationalIndicator.id,
        SubnationalDataPoint.region_id == SubnationalRegion.id, _finite(SubnationalDataPoint.value),
        *_date_constraints(SubnationalDataPoint.period, intent)))
    stmt = select(SubnationalRegion, SubnationalIndicator).select_from(SubnationalIndicator).join(
        SubnationalRegion, SubnationalRegion.country_code == SubnationalIndicator.country_code).where(
        SubnationalIndicator.id.in_(candidates), SubnationalRegion.id.in_(selected), fact).order_by(
        case(candidates, value=SubnationalIndicator.id).desc(), SubnationalRegion.sort_order, SubnationalIndicator.code).limit(budget + 1)
    rows = (await db.execute(stmt)).all()
    output = []
    for region, row in rows[:budget]:
        geo = selected[region.id]
        base = paths.country_region_indicator(geo["country_slug"], region.slug, row.code)
        path, navigation = _period_path(base, intent, regional=True)
        output.append({"key": f"subnational:{geo['country_slug']}:{region.slug}:{row.code}", "kind": "subnational_indicator", "code": row.code,
            "name": row.name_en if locale == "en" else row.name_ru, "name_ru": row.name_ru, "name_en": row.name_en,
            "country_slug": geo["country_slug"], "region_slug": region.slug,
            "country_name": next((item["name_en"] if locale == "en" else item["name_ru"] for item in geometry if item["kind"] == "country" and item["country_slug"] == geo["country_slug"]), geo["country_slug"]),
            "region_name": region.name_en if locale == "en" else region.name_ru,
            "category": row.section_en if locale == "en" else row.section_ru, "frequency": row.frequency,
            "unit": row.unit_en or row.unit if locale == "en" else row.unit_ru or row.unit,
            "path": path, "navigation": navigation, "score": candidates[row.id]})
    return output, len(rows) > budget


async def federated_search(db: AsyncSession, raw: str, *, limit: int = 50) -> dict:
    """One query contract with bounded SQL and truthful availability states."""
    empty = {"results": [], "total": 0, "has_more": False, "version": SEARCH_VERSION}
    if not phrase(raw):
        return empty
    if not re.search(r"[a-zа-я]", normalize(raw)):
        return {**empty, "reason": "unsupported_query"}
    geometry, countries = await _geometry(db)
    intent = parse_intent(raw, geometry)
    fx_quoted_countries = {
        "usd-jpy": (frozenset(("united-states", "japan")), "japan"),
        "usd-rub": (frozenset(("united-states", "russia")), "russia"),
        "cny-rub": (frozenset(("china", "russia")), "russia"),
    }
    for term in intent.terms:
        quoted = fx_quoted_countries.get(term[0])
        if quoted and intent.countries == quoted[0]:
            # Issuer mention is part of this actual quoted currency pair; the
            # result remains gated to the quoted-country data plane, never union.
            intent = replace(intent, countries=frozenset((quoted[1],)))
    summary = {"countries": sorted(intent.countries), "regions": sorted(intent.regions),
        "year": intent.year, "month": intent.month}
    if intent.error:
        return {**empty, "reason": intent.error, "intent": summary}
    if len(intent.countries) > 1:
        return {**empty, "reason": "ambiguous_geography", "intent": summary}
    if not intent.terms and not intent.countries:
        return {**empty, "reason": "unsupported_query", "intent": summary}
    locale = get_locale()
    budget = min(_MAX_CANDIDATES, max(100, limit * 4))
    entities = await _entities(db, geometry, intent, locale)
    russia = await _russia(db, intent, locale)
    world, world_clipped = await _world(db, intent, countries, locale, budget)
    regional, regions_clipped = await _regions(db, intent, geometry, locale, budget)
    subnational, sub_clipped = await _subnational(db, intent, geometry, locale, budget)
    results = entities + russia + world + regional + subnational
    results.sort(key=lambda item: (-item["score"],
        1 if not intent.regions and item["kind"] in ("region_indicator", "subnational_indicator") else 0,
        0 if (locale == "ru" and item.get("country_slug") == "russia") or (locale == "en" and item.get("country_slug") != "russia") else 1,
        item["key"]))
    seen, unique = set(), []
    for result in results:
        # Distinct slices can share canonical path but retain different code and
        # intent. Do not collapse them by URL and hide the requested variant.
        if result["key"] not in seen:
            unique.append(result)
            seen.add(result["key"])
    final, position = [], 0
    world_rows = db.info.get("fe_search_world_rows", {})
    while position < len(unique) and len(final) <= limit:
        batch = unique[position:position + limit + 1 - len(final)]
        position += len(batch)
        requested = [(item["country_slug"], world_rows[(item["country_slug"], item["code"])])
            for item in batch if item["kind"] == "world"]
        canonical_paths = await world_search_paths(db, requested)
        for result in batch:
            canonical = canonical_paths.get((result.get("country_slug"), result.get("code")))
            if canonical:
                if intent.year is not None and urlsplit(canonical).query:
                    continue
                result["path"], result["navigation"] = _period_path(canonical, intent, world=True)
            final.append(result)
    response = {"results": final[:limit], "total": min(len(final), limit),
        "has_more": len(final) > limit or world_clipped or regions_clipped or sub_clipped,
        "version": SEARCH_VERSION, "intent": summary}
    if intent.corrected:
        response["corrected_query"] = intent.corrected
    if not final:
        response["reason"] = "no_coverage"
    return response
