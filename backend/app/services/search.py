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
import string
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import and_, case, exists, literal, literal_column, or_, select, true, union_all, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import load_only
from sqlalchemy.sql.elements import False_

from app.data.global_market_indicators import COUNTRY_MARKET_INDICATOR_CODES, is_global_market_indicator, market_indicator_codes_for_country
from app.data.world_concept_national import national_codes_for_concept
from app.data.world_concepts import concept_for_indicator, concept_public_unit
from app.data.eurostat_listing import normalize_frequency
from app.data.eurostat_titles_ru import listing_category_ru
from app.data.world_indicator_titles_ru import title_override_for_code
from app.models import (
    Indicator, IndicatorData, Region, RegionDataPoint, RegionIndicator,
    RegionMonthlyPoint, SubnationalDataPoint, SubnationalIndicator,
    SubnationalRegion, WorldCountry, WorldDataPoint, WorldIndicator,
)
from app.services import site_paths as paths
from app.services.locale import get_locale
from app.services.search_intent import (
    SEARCH_VERSION, SearchIntent, complete_nominal_alternative, geo_aliases, literal_identifier, match_score, matching_alternatives, normalize, parse_intent, phrase, strip_geography,
)
from app.services.search_language import measure_matches, relevance_bonus, title_frequencies
from app.services.search_language_sql import measure_constraints, _pattern_clause
from app.services.search_units import UNIT_RULES, UNIT_EXCLUDES, DENOMINATOR_RULES, unit_metadata, denominator_metadata
from app.services.search_dimensions import dimension_constraints, dimension_metadata, native_dimension_labels, native_dimension_match_clause, native_dimension_text
from app.services.search_paths import russia_family_base, russia_search_path, russia_year_search_path, world_search_paths
from app.services.seo_i18n import localize_category_name, public_indicator_fields, region_display_name, region_indicator_copy
from app.services.world_subnational_ingest import country_has_subnational

_MAX_CANDIDATES = 500
_PERCENT_UNITS = ("PC", "PCT", "PERCENT", "RCH_A", "RCH_M", "RCH_MV12MAVR", "RCH_A_AVG", "RT1", "RT1-SCA",
    "PCH_SM", "PCH_PRE", "PCH_SAME", "PCH_M1", "PCPIPCH", "PCPIEPCH", "NGDP_RPCH", "NGDP_RPC")
_INTENT_CONCEPTS = {
    "cpi": "hicp-index", "unemployment": "unemployment-rate", "population": "population",
    "gdp-per-capita": "gdp-per-capita-usd", "gdp": "gdp-volume-quarterly",
}
_INFLATION_WORD = re.compile(r"инфляц|inflation")
# Запас над индексом цен (у индекса +20 за точное совпадение кода): годовая инфляция первая.
_ANNUAL_INFLATION_LEAD = 50
_REGION_HEADLINES = {
    "wage": "srednemesyachnaya-nominalnaya-nachislennaya-zarabotnaya-plata-rabotnikov-organizatsiy",
}
_RUSSIA_HEADLINES = {
    "housing": "housing-affordability-primary", "birth-count": "births", "cpi": "cpi", "gdp": "gdp-nominal", "wage": "wages-nominal", "unemployment": "unemployment",
    "key-rate": "key-rate", "fuel": "fuel", "fuel-ai95": "fuel-ai95", "fuel-ai92": "fuel-ai92",
    "fuel-diesel": "fuel-diesel", "pensioners": "pensioners",
    "exports": "exports", "imports": "imports", "gas-price": "natural-gas", "natural-gas": "natural-gas", "газ": "natural-gas",
    "trade-balance": "trade-balance", "wages-real": "wages-real", "wages-nominal": "wages-nominal", "gdp-nominal": "gdp-nominal", "gdp-real": "gdp-real",
    "mortgage-rate": "mortgage-rate", "credit-rate": "credit-rate", "cpi-food": "cpi-food",
    "government-debt": "public-debt", "budget-balance": "budget-balance",
    "reserves": "international-reserves", "mortality": "death-rate", "births": "birth-rate",
    "copper": "copper", "silver": "silver",
    "budget-expenditure": "budget-expenditure", "budget-revenue": "budget-revenue",
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
            native = next((item for item in family.modes if item.code == family.base and item.is_native), None)
            facets = f" {family.name} {mode.label} search-mode-{mode.group} search-freq-{mode.frequency}"
            if native is not None:
                facets += f" search-source-freq-{native.frequency}"
            # Only the registered terminal period_last operation establishes
            # end-of-period identity; a YoY pipeline may contain an earlier
            # period_last step without itself being a level at period end.
            if mode.pipeline and mode.pipeline[-1][0] == "period_last":
                facets += " search-mode-eop"
            if _family_price_evidence(family):
                facets += " search-subject-price"
            metadata[mode.code] = metadata.get(mode.code, "") + facets
    return metadata


def _family_price_evidence(family) -> bool:
    """Registered commodity price per physical quantity, never money alone."""
    unit = normalize(family.unit)
    monetary = re.search(r"(?:usd|eur|rub|руб|[$€])", unit)
    physical = re.search(r"/\s*(?:т|тонна|тонны|тонн|tonne|kg|кг|г|грамм|баррель|barrel|унция|унции|унций|ounce|млн\s*бте|mmbtu|л|литр)(?:\W|$)", unit)
    return family.category == "Товарные рынки" and bool(monetary and physical)


@lru_cache(maxsize=1)
def _registered_price_codes() -> frozenset[str]:
    """Derive every admissible price series from its actual family contract."""
    from app.data.view_model_families import FAMILIES
    return frozenset(mode.code for family in FAMILIES if _family_price_evidence(family)
        for mode in family.modes)


@lru_cache(maxsize=1)
def _bespoke_mode_metadata() -> dict[str, str]:
    """Exact canonical mode mappings establish bespoke change identities."""
    from app.data.legacy_redirects import _bespoke_mode_index
    groups = {"yoy": "yoy", "yoy-annual": "yoy", "qoq": "pop", "mom": "pop"}
    return {code: "search-mode-" + groups[mode] for (_parent, mode), code
        in _bespoke_mode_index().items() if mode in groups}


_NATIVE_PRICE_WORDS = ("price", "prices", "цена", "цены", "цен", "ценах", "ценам", "ценами")
_PRICE_VALUATION_PHRASES = ("current prices", "constant prices", "chained prices", "текущие цены", "текущих ценах", "постоянные цены", "постоянных ценах", "цепные цены", "цепных ценах")
_PRICE_SEPARATORS = string.punctuation + "—–≤≥‰€£¥№\t\n\r\v\f\u00a0\u202f"


@lru_cache(maxsize=2048)
def _native_price_metadata(*names: str | None) -> str:
    """A native price subject, distinct from GDP valuation at current prices."""
    text = phrase(" ".join(name or "" for name in names))
    for valuation in _PRICE_VALUATION_PHRASES:
        text = text.replace(valuation, " ")
    return "search-subject-price" if set(text.split()).intersection(_NATIVE_PRICE_WORDS) else ""


def _native_name_text(*columns, postgres: bool):
    """Fold bounded native name punctuation with parser-compatible word spans."""
    text = literal("")
    for column in columns:
        text = text + literal(" ") + func.coalesce(column, "")
    text = func.replace(func.lower(text), "ё", "е")
    if postgres:
        text = func.regexp_replace(text, r"[^a-zа-я0-9]+", " ", "g")
    else:
        for separator in _PRICE_SEPARATORS:
            text = func.replace(text, separator, " ")
        # Native name fields are bounded; ten halvings cover even a run of
        # 1024 separator spaces and mirror Python's whitespace folding.
        for _ in range(10):
            text = func.replace(text, "  ", " ")
    return literal(" ") + text + literal(" ")


def _native_price_constraint(*columns, postgres: bool):
    """Mirror complete price words in actual names before SQL candidate limits."""
    text = _native_name_text(*columns, postgres=postgres)
    for valuation in _PRICE_VALUATION_PHRASES:
        text = func.replace(text, valuation, " ")
    indexed = or_(*(column.ilike(pattern) for column in columns for pattern in ("%price%", "%цен%")))
    return and_(indexed, or_(*(text.like("% " + word + " %") for word in _NATIVE_PRICE_WORDS)))


def _intent_concept(intent: SearchIntent) -> str | None:
    terms = [term for term in intent.terms if not term[0].startswith("search-")]
    if len(terms) != 1:
        return None
    return _INTENT_CONCEPTS.get(terms[0][0])


def _intent_frequency(intent: SearchIntent) -> str | None:
    return next((alt.removeprefix("search-freq-") for term in intent.terms for alt in term
        if alt.startswith("search-freq-")), None)


@lru_cache(maxsize=2048)
def _unit_metadata(*units, native_currency: str | None = None) -> str:
    """Explicit percent intent checks actual units, never SEO/name text."""
    facets = unit_metadata(*units, native_currency=native_currency)
    if "search-unit-percentage-point" in facets:
        return facets
    for unit in units:
        raw = normalize(unit)
        if "%" in raw or "percent" in raw or "процент" in raw or raw.upper() in _PERCENT_UNITS or (raw.upper().startswith("PC_") and raw.upper() != "PC_PNT"):
            return ("search-unit-percent " + facets).strip()
    return facets


# Запрос «только страна» («Turkey», «Турция»): после самой страны человеку нужны её главные
# цифры, а не ряды в порядке кода (рождаемость по возрасту матери). Четыре понятия, как на
# странице страны: цены, ВВП, безработица, население.
_COUNTRY_HEADLINE_CONCEPTS = ("hicp-index", "gdp-usd", "unemployment-rate", "population")
_COUNTRY_HEADLINE_CODE_PATTERNS = (
    "%-weo-ngdpd", "%-weo-lur", "%-weo-lp", "%-weo-pcpipch",
    "%-prc_hicp_minr-total-%", "%-prc_hicp_minr-cp00-%", "%-prc_hicp_midx-total-%", "%-prc_hicp_midx-cp00-%",
    "%-une_rt_m-total-sa-t-pc-act", "%-demo_pjan-total-t-nr",
)


def _country_only(intent: SearchIntent) -> bool:
    return not intent.terms and bool(intent.countries) and not intent.regions


def _world_preference(intent: SearchIntent):
    """Catalogue headline identities, not a popularity prior."""
    if _country_only(intent):
        clauses = [WorldIndicator.code.like(pattern) for pattern in _COUNTRY_HEADLINE_CODE_PATTERNS]
        for slug in _COUNTRY_HEADLINE_CONCEPTS:
            codes = national_codes_for_concept(slug)
            if codes:
                clauses.append(WorldIndicator.code.in_(codes))
        return or_(*clauses)
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


def _country_headline_bonus(row) -> int:
    """Главный ряд страны для запроса «только страна»: национальный ряд, затем официальный Евростата, затем оценка МВФ."""
    for slug in _COUNTRY_HEADLINE_CONCEPTS:
        if row.code in national_codes_for_concept(slug):
            return 160
    try:
        resolved = concept_for_indicator(row)
    except ValueError:
        return 0
    if resolved is None or resolved.slug not in _COUNTRY_HEADLINE_CONCEPTS:
        return 0
    return 130 if str(getattr(row, "provider", "") or "").lower() == "imf" else 140


def _world_bonus(row, intent: SearchIntent) -> int:
    if _country_only(intent):
        return _country_headline_bonus(row)
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
            # IMF PCPIPCH (инфляция за год, %) относится к понятию «индекс цен»,
            # но сама уже в процентах: подпись понятия «index 2015=100» ей не подходит.
            from app.services.world_rank_values import YOY_KIND_PASSTHROUGH, rank_yoy_kind

            if rank_yoy_kind(row) != YOY_KIND_PASSTHROUGH:
                return concept_public_unit(concept) or ru
            from app.services.display import localize_unit

            label = localize_unit(ru, locale="en") if ru else ""
            if label and not any("а" <= ch.lower() <= "я" or ch in "ёЁ" for ch in label):
                return label
    from app.services.display import plain_unit_en

    label = plain_unit_en(unit_label_en_for_code(row.unit))
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


# 2**3 candidate queries at most; beyond that the single combined predicate is kept.
_MAX_DIMENSION_TERMS = 3


def _world_fact(intent: SearchIntent):
    return exists(select(1).where(WorldDataPoint.indicator_id == WorldIndicator.id,
        WorldDataPoint.value != literal_column("0"), _finite(WorldDataPoint.value),
        *_date_constraints(WorldDataPoint.date, intent)))


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _world_lexical(intent: SearchIntent, *, postgres: bool):
    """One combined predicate per required term (lexical OR native dimension)."""
    return [or_(lexical, dimension) if dimension is not None else lexical
            for lexical, dimension in _world_lexical_terms(intent, postgres=postgres)]


def _world_lexical_terms(intent: SearchIntent, *, postgres: bool):
    """Per required term: (lexical predicate, native-dimension predicate or None).

    The lexical part is trigram-indexable (code/name/SEO ILIKE). The dimension
    part reads JSON slice members and cannot use that index; one such branch
    inside an OR forces a scan of the whole catalogue. They are kept apart so
    `_world` can run indexable candidate queries and merge them.
    """
    # An unknown unfinished alphabetic qualifier has no semantic identity.
    # Scanning the large catalogue for its one/two-letter whole word can take
    # seconds while fabricating matches. Preserve short whole-query prefixes,
    # catalogue-supported literals, numeric denominators and typed aliases.
    if not intent.literal and len(intent.terms) > 1 and any(
        len(group) == 1 and re.fullmatch(r"[a-zа-я]{1,2}", group[0])
        for group in intent.terms
    ):
        return [(literal(False), None)]
    clauses = []
    for sourcegroup in intent.terms:
        alternatives = matching_alternatives(sourcegroup, literal=intent.literal)
        term_clauses = []
        native_alternatives = []
        for alternative in alternatives:
            nominal = complete_nominal_alternative(sourcegroup, alternatives, alternative)
            if alternative == "search-subject-price":
                term_clauses.append(_native_price_constraint(WorldIndicator.name_ru, WorldIndicator.name_en, postgres=postgres))
                continue
            if alternative in {"current-prices", "constant-prices"}:
                # A separate measure predicate uses actual names and native
                # units. Display/SEO text cannot establish a valuation basis.
                term_clauses.append(literal(True))
                continue
            if alternative.startswith("search-price-base-"):
                from app.services.search_units import price_base_unit_pattern, PRICE_BASE_UNIT_SEPARATORS
                year = alternative.removeprefix("search-price-base-")
                if not re.fullmatch(r"[12]\d{3}", year):
                    term_clauses.append(literal(False))
                    continue
                # A complete native unit label must establish the base by
                # itself; fragments in two different translations cannot join
                # into invented evidence ahead of the candidate budget.
                base_clauses = []
                for unit_column in (WorldIndicator.unit, WorldIndicator.unit_ru):
                    units = func.lower(func.coalesce(unit_column, ""))
                    for separator in PRICE_BASE_UNIT_SEPARATORS:
                        units = func.replace(units, separator, " ")
                    units = literal(" ") + units + literal(" ")
                    base_clauses.append(_pattern_clause(units, price_base_unit_pattern(int(year)), postgres=postgres))
                term_clauses.append(or_(*base_clauses))
                continue
            if alternative.startswith("search-dim-"):
                # A separate shared named-axis predicate below is mandatory.
                # The marker can never be satisfied by a title/code substring.
                term_clauses.append(literal(True))
                continue
            if alternative in DENOMINATOR_RULES:
                # The denominator belongs to the actual measure/unit, not SEO
                # or the native scale of a count. Promille is a people rate
                # only in controlled demographic measures, never every ratio.
                measure_text = func.lower(func.coalesce(WorldIndicator.name_ru, "") + literal(" ") +
                    func.coalesce(WorldIndicator.name_en, "") + literal(" ") +
                    func.coalesce(WorldIndicator.unit, "") + literal(" ") + func.coalesce(WorldIndicator.unit_ru, ""))
                measure_text = func.replace(func.replace(measure_text, "\u00a0", " "), "\u202f", " ")
                term_clauses.append(_pattern_clause(measure_text, DENOMINATOR_RULES[alternative], postgres=postgres))
                continue
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
            if alternative.startswith("search-unit-") and alternative.removeprefix("search-unit-") in UNIT_RULES:
                unit_key = alternative.removeprefix("search-unit-")
                unit_text = func.lower(func.coalesce(WorldIndicator.unit, "") + literal(" ") + func.coalesce(WorldIndicator.unit_ru, ""))
                unit_clause = _pattern_clause(unit_text, UNIT_RULES[unit_key], postgres=postgres)
                if unit_key == "percentage-point":
                    unit_clause = or_(unit_clause, unit_text.contains("п.п."))
                if unit_key in ("litre", "tonne"):
                    symbols = ("l", "л") if unit_key == "litre" else ("t", "т")
                    symbol_clauses = []
                    for column in (WorldIndicator.unit, WorldIndicator.unit_ru):
                        compact = func.lower(func.coalesce(column, ""))
                        if postgres:
                            compact = func.regexp_replace(compact, r"\s+", "", "g")
                            symbol_clauses.append(compact.op("~")(r"/(?:" + "|".join(symbols) + r")(?:\W|$)"))
                        else:
                            for space in (" ", "\t", "\n", "\r", "\v", "\f", "\u00a0", "\u202f"):
                                compact = func.replace(compact, space, "")
                            padded = compact + literal(" ")
                            symbol_clauses.append(or_(*(padded.contains("/" + symbol + end)
                                for symbol in symbols for end in (" ", "/", ".", ",", ";", ")", "-"))))
                        symbol_clauses.append(compact.in_(symbols))
                    unit_clause = or_(unit_clause, *symbol_clauses)
                if unit_key in UNIT_EXCLUDES:
                    unit_clause = and_(unit_clause, ~_pattern_clause(unit_text, UNIT_EXCLUDES[unit_key], postgres=postgres))
                term_clauses.append(unit_clause)
                continue
            if alternative.startswith("search-freq-"):
                frequency = alternative.removeprefix("search-freq-")
                aliases = {"annual": ("annual", "yearly", "A"), "monthly": ("monthly", "M"), "quarterly": ("quarterly", "Q"),
                    "weekly": ("weekly", "W"), "daily": ("daily", "D")}.get(frequency, (frequency,))
                term_clauses.append(WorldIndicator.frequency.in_(aliases))
                continue
            if alternative.startswith("search-source-freq-"):
                # World rows have no registered derivation/source-frequency
                # contract. An observation frequency cannot stand in for it.
                term_clauses.append(literal(False))
                continue
            if alternative.startswith("search-mode-"):
                mode = alternative.removeprefix("search-mode-")
                if mode == "level":
                    # A native value may be an unemployment/employment rate,
                    # not just an index. Level is the stored series identity;
                    # metadata names/measure still constrain the economic topic.
                    term_clauses.append(literal(True))
                    continue
                if mode == "eop":
                    names = (WorldIndicator.name_ru, WorldIndicator.name_en)
                    text = _native_name_text(*names, postgres=postgres)
                    phrases = ("end of period", "end of year", "end of quarter", "end of month",
                        "на конец года", "на конец квартала", "на конец месяца", "на конец периода")
                    indexed = or_(*(column.ilike(pattern) for column in names for pattern in ("%end%", "%конец%")))
                    term_clauses.append(and_(indexed, or_(*(text.like("% " + label + " %") for label in phrases))))
                    continue
                phrases = {"yoy": ("year-on-year", "annual rate of change", "изменение за год"),
                    "avg": ("average", "средн"), "pop": ("month-on-month", "quarter-on-quarter", "изменение за месяц"),
                    "eop": ("end of period", "end of year", "end of quarter", "end of month", "на конец года", "на конец квартала", "на конец месяца", "на конец периода"),
                    "level": ("index", "индекс")}.get(mode, ())
                term_clauses.extend(WorldIndicator.name_en.ilike(f"%{p}%") for p in phrases)
                term_clauses.extend(WorldIndicator.name_ru.ilike(f"%{p}%") for p in phrases)
                if mode != "eop":
                    term_clauses.append(WorldIndicator.code.ilike(f"%-{mode}%"))
                continue
            if intent.literal and normalize(alternative) == intent.literal:
                literal_pattern = "%" + "%".join(_escape_like(word) for word in phrase(alternative).split()) + "%"
                term_clauses.append(or_(*(column.ilike(literal_pattern, escape="\\") for column in
                    (WorldIndicator.code, WorldIndicator.name_ru, WorldIndicator.name_en))))
                continue
            needle = _escape_like(normalize(alternative))
            # A short whole query stays a prefix lookup. A short term inside a
            # qualified longer query (IPCA 12-month) must match anywhere; the
            # other required terms keep that candidate lookup bounded.
            prefix_only = len(needle) < 3 and len(intent.terms) == 1
            pattern = f"{needle}%" if prefix_only else f"%{needle}%"
            if " " in alternative:
                # SQL discovery accepts native separators (R&D, comma lists).
                # The scorer then requires the normalized phrase/typed measure;
                # this is not permission to drop a meaningful interior word.
                pattern = "%" + "%".join(_escape_like(word) for word in phrase(alternative).split()) + "%"
            columns = (WorldIndicator.code, WorldIndicator.name_ru, WorldIndicator.name_en, WorldIndicator.seo_keywords)
            native_alternatives.append((alternative, nominal))
            if "=" in alternative or (alternative.startswith("i") and alternative[1:].isdigit()):
                columns += (WorldIndicator.unit, WorldIndicator.unit_ru)
            for column in columns:
                if postgres and (nominal or (len(needle) < 3 and len(intent.terms) > 1 and len(alternatives) == 1)):
                    # An unfinished one/two-letter qualifier cannot match an
                    # interior syllable of hundreds of thousands of titles. The
                    # scorer also requires a whole token for such short terms.
                    term_clauses.append(column.op("~*")(r"(^|[^a-zа-я0-9])" + re.escape(needle) + r"([^a-zа-я0-9]|$)"))
                elif nominal:
                    # Hermetic SQLite has no regex operator. Mirror the exact
                    # noun boundary on stored title/code separator punctuation.
                    text = func.lower(func.coalesce(column, ""))
                    for separator in "-,.()/;—_:":
                        text = func.replace(text, separator, " ")
                    text = literal(" ") + text + literal(" ")
                    term_clauses.append(text.like("% " + needle + " %", escape="\\"))
                else:
                    term_clauses.append(column.ilike(pattern, escape="\\"))
            raw_singleton = len(sourcegroup) == 1 and alternative == sourcegroup[0]
            if postgres and (len(alternatives) == 1 or raw_singleton) and not nominal and len(needle) >= 5 and " " not in needle:
                for column in (WorldIndicator.name_ru, WorldIndicator.name_en):
                    term_clauses.append(literal(needle).op("<%")(column))
        dimension = native_dimension_match_clause(WorldIndicator.provider, WorldIndicator.slice_json,
            tuple(native_alternatives))
        lexical = or_(*term_clauses) if term_clauses else literal(False)
        clauses.append((lexical, None if isinstance(dimension, False_) else dimension))
    return clauses


def _world_mode_metadata(row) -> str:
    """Recognize official native measures without inferring a new derived row."""
    name = normalize(f"{row.name_ru} {row.name_en}")
    metadata = f"search-mode-level search-freq-{normalize_frequency(row.frequency) or row.frequency} {_native_price_metadata(row.name_ru, row.name_en)}"
    if any(label in name for label in ("year-on-year", "annual rate of change", "12-month accumulated", "изменение за год")) or "-yoy" in row.code:
        metadata += " search-mode-yoy"
    if any(label in name for label in ("month-on-month", "quarter-on-quarter", "изменение за месяц")):
        metadata += " search-mode-pop"
    if "average" in name or "средн" in name:
        metadata += " search-mode-avg"
    if any(" " + label + " " in " " + phrase(name) + " " for label in ("end of period", "end of year", "end of quarter", "end of month",
            "на конец года", "на конец квартала", "на конец месяца", "на конец периода")):
        metadata += " search-mode-eop"
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
    regions = list((await db.execute(select(Region).where(Region.kind.in_(("region", "district", "remainder"))))).scalars())
    for region in regions:
        geometry.append({"key": f"region:russia:{region.slug}", "kind": "unsupported_region" if region.kind == "remainder" else "region", "slug": region.slug,
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
    origin_countries = []
    if intent.countries and "russia" not in intent.countries:
        origin_countries = list((await db.execute(select(WorldCountry).where(
            WorldCountry.slug.in_(intent.countries), WorldCountry.is_active.is_(True)
        ))).scalars())
    rows = list((await db.execute(select(Indicator).where(Indicator.is_active.is_(True),
        exists(select(1).where(IndicatorData.indicator_id == Indicator.id, _finite(IndicatorData.value),
            *_date_constraints(IndicatorData.date, intent)))))).scalars())
    output = []
    for row in rows:
        market_country = None
        if intent.countries and "russia" not in intent.countries:
            # Запрос «только страна» не должен выкладывать все скрытые режимы
            # рыночного ряда (средние по неделям, годовые изменения): достаточно
            # самого ряда. С уточнением («Турция лира среднее за месяц») режимы нужны.
            sibling_modes = bool(intent.terms)
            if not any(row.code == base or (sibling_modes and row.code.startswith(base + "-")) for base in market_bases):
                # A registered global commodity may carry its origin in the
                # actual native title. Country membership cannot come from SEO,
                # storage in Russia, a code prefix or arbitrary category text.
                if not is_global_market_indicator(row.code):
                    continue
                title = " " + phrase(f"{row.name} {row.name_en or ''}") + " "
                origin = next((country for country in origin_countries if any(
                    name and " " + phrase(name) + " " in title
                    for name in (country.name_ru, country.name_en)
                ) or (country.code and re.search(r"(?<![A-Za-z0-9])" + re.escape(country.code) + r"(?![A-Za-z0-9])", f"{row.name} {row.name_en or ''}"))), None)
                if origin is None:
                    continue
                market_country = origin.slug
            else:
                market_country = next(iter(sorted(intent.countries)))
        en = public_indicator_fields(row.code, name_ru=row.name, name_en=row.name_en, unit_ru=row.unit, locale="en")
        ru = public_indicator_fields(row.code, name_ru=row.name, name_en=row.name_en, unit_ru=row.unit, locale="ru")
        score = match_score(intent, code=row.code, names=(row.name, row.name_en or "", en["name"] or ""),
            metadata=" ".join(filter(None, (row.category, row.seo_keywords, row.frequency, row.unit,
                f"search-freq-{normalize_frequency(row.frequency) or row.frequency}",
                _family_metadata().get(row.code) or "search-mode-level", _bespoke_mode_metadata().get(row.code), _native_price_metadata(row.name, row.name_en, en["name"]), _unit_metadata(row.unit, en["unit"]),
                denominator_metadata(row.name, row.name_en, en["name"], row.unit, en["unit"])))))
        price_names = ("price",) if row.code in _registered_price_codes() else ()
        if score is None or not measure_matches(intent.terms, code=row.code, names=(row.name, row.name_en, en["name"]) + price_names, unit_names=(row.unit, en["unit"])):
            continue
        content_terms = [term for term in intent.terms if not term[0].startswith("search-")]
        if len(content_terms) == 1:
            headline = _RUSSIA_HEADLINES.get(content_terms[0][0])
            parent = urlsplit(russia_search_path(row.code, intent)).path.rsplit("/", 1)[-1]
            family_headline = bool(headline and (row.code == headline or russia_family_base(row.code) == headline or parent == headline))
            if family_headline:
                score += 180
            # «Инфляция» читают как рост цен за год (6,34 %), а не как индекс к прошлому
            # месяцу (99,92 %): годовой ряд поднимается выше индекса. Запрос «ИПЦ» или
            # «индекс потребительских цен» просит именно индекс, там порядок прежний.
            if (content_terms[0][0] == "cpi" and row.code == "cpi-yoy"
                    and (_INFLATION_WORD.search(intent.query) or _INFLATION_WORD.search(intent.content))):
                score += _ANNUAL_INFLATION_LEAD + (0 if family_headline else 180)
        if market_country and _country_only(intent) and row.code in market_bases:
            # «Турция»: курс лиры (официальный курс ЦБ) идёт вместе с главными цифрами страны.
            score += 120
        base = russia_search_path(row.code, intent)
        if intent.month is not None and urlsplit(base).query:
            continue
        if intent.month is not None and row.frequency in ("annual", "yearly", "quarterly"):
            continue
        if intent.year is not None and intent.month is None:
            path = russia_year_search_path(row.code, intent, intent.year)
            if path is None:
                continue
            navigation = "document"
        else:
            path, navigation = _period_path(base, intent)
        market_issuer = next((country for country in COUNTRY_MARKET_INDICATOR_CODES
            if any(row.code == code or row.code.startswith(code + "-") for code in market_indicator_codes_for_country(country))), None)
        if is_global_market_indicator(row.code):
            origin = next((country for country in origin_countries if country.slug == market_country), None)
            country_name = (origin.name_en if locale == "en" else origin.name_ru) if origin else (("United States" if locale == "en" else "США") if market_issuer == "united-states" else ("Global markets" if locale == "en" else "Мировой рынок"))
        else:
            quoted_origin = next((country for country in origin_countries if country.slug == market_country), None)
            if market_country == "united-states":
                country_name = "United States" if locale == "en" else "США"
            elif quoted_origin is not None:
                # Официальный курс валюты страны к рублю (Турция → лира): страна ряда названа в запросе.
                country_name = quoted_origin.name_en if locale == "en" else quoted_origin.name_ru
            else:
                country_name = "Russia" if locale == "en" else "Россия"
        db.info.setdefault("fe_search_native_units", {})[f"ru:{row.code}"] = (row.unit, en["unit"])
        output.append({"key": f"ru:{row.code}", "kind": "russia", "code": row.code,
            "name": (en if locale == "en" else ru)["name"], "name_ru": ru["name"], "name_en": en["name"],
            "country_slug": market_country or market_issuer or "russia", "country_name": country_name,
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
    needle = _escape_like(intent.literal or intent.content)
    rank = case((WorldIndicator.code.ilike(_escape_like(intent.query), escape="\\"), 0),
        (WorldIndicator.code.ilike(needle, escape="\\"), 0),
        (WorldIndicator.name_ru.ilike(needle, escape="\\"), 1),
        (WorldIndicator.name_en.ilike(needle, escape="\\"), 1),
        (_world_preference(intent), 2), else_=3)

    def candidates(term_clauses):
        # All explicit geography and fact constraints precede candidate LIMIT.
        return select(WorldIndicator, rank.label("fe_rank")).options(load_only(*columns)).where(
            WorldIndicator.country_id.in_(selected), _world_fact(intent), *term_clauses,
            *dimension_constraints(intent.terms, WorldIndicator.provider, WorldIndicator.slice_json),
            *measure_constraints(intent.terms, WorldIndicator.code, (WorldIndicator.name_ru, WorldIndicator.name_en,
                native_dimension_text(WorldIndicator.provider, WorldIndicator.slice_json, intent.terms)), postgres=postgres,
                unit_columns=(WorldIndicator.unit, WorldIndicator.unit_ru))
        ).order_by(rank, WorldIndicator.is_listed.desc(), WorldIndicator.code).limit(budget + 1)

    terms = _world_lexical_terms(intent, postgres=postgres)
    dimension_terms = [index for index, (_lexical, dimension) in enumerate(terms) if dimension is not None]
    if not postgres or not dimension_terms or len(dimension_terms) > _MAX_DIMENSION_TERMS:
        statements = [candidates(_world_lexical(intent, postgres=postgres))]
    else:
        # A term holds through its lexical or its dimension predicate. Every
        # combination is its own AND query, so each can use the trigram index;
        # the union of the per-query top candidates contains the overall top.
        statements = []
        for mask in range(1 << len(dimension_terms)):
            use_dimension = {dimension_terms[bit] for bit in range(len(dimension_terms)) if mask >> bit & 1}
            statements.append(candidates([dimension if index in use_dimension else lexical
                for index, (lexical, dimension) in enumerate(terms)]))
    merged: dict[int, tuple[int, WorldIndicator]] = {}
    for statement in statements:
        for row, row_rank in (await db.execute(statement)).all():
            merged.setdefault(row.id, (row_rank, row))
    ordered = sorted(merged.values(), key=lambda item: (item[0], 0 if item[1].is_listed else 1, item[1].code))
    rows = [row for _rank, row in ordered[:budget + 1]]
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
                _world_mode_metadata(row), _unit_metadata(row.unit, row.unit_ru),
                dimension_metadata(row.provider, row.slice_json),
                denominator_metadata(row.name_ru, row.name_en, row.unit, row.unit_ru)))))
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
        db.info.setdefault("fe_search_native_units", {})[f"world:{country.slug}:{row.code}"] = (row.unit, row.unit_ru)
        output.append({"key": f"world:{country.slug}:{row.code}", "kind": "world", "code": row.code,
            "name": row.name_en or row.name_ru if locale == "en" else (title_override_for_code(row.code) or row.name_ru),
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
        score = match_score(definition_intent, code=row.code, names=(row.name, en["name"] or ""), metadata=f"{row.unit} {en['unit']} {row.section_name} search-mode-level {_native_price_metadata(row.name, en['name'])} {_unit_metadata(row.unit, en['unit'])} {denominator_metadata(row.name, en['name'], row.unit, en['unit'])}")
        if score is not None and measure_matches(intent.terms, code=row.code, names=(row.name, en["name"]), unit_names=(row.unit, en["unit"])):
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
        db.info.setdefault("fe_search_native_units", {})[f"region:{region.slug}:{row.code}"] = (row.unit, en["unit"])
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
            metadata=f"{row.unit} {row.unit_ru} {row.unit_en} {row.section_ru} {row.section_en} {row.frequency} search-mode-level search-freq-{normalize_frequency(row.frequency) or row.frequency} {_native_price_metadata(row.name_ru, row.name_en)} {_unit_metadata(row.unit, row.unit_ru, row.unit_en, native_currency='USD' if row.country_code == 'US' else None)} {denominator_metadata(row.name_ru, row.name_en, row.unit, row.unit_ru, row.unit_en)}")
        if score is not None and measure_matches(intent.terms, code=row.code, names=(row.name_ru, row.name_en), unit_names=(row.unit, row.unit_ru, row.unit_en)):
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
        db.info.setdefault("fe_search_native_units", {})[f"subnational:{geo['country_slug']}:{region.slug}:{row.code}"] = (row.unit, row.unit_ru, row.unit_en)
        output.append({"key": f"subnational:{geo['country_slug']}:{region.slug}:{row.code}", "kind": "subnational_indicator", "code": row.code,
            "name": row.name_en if locale == "en" else row.name_ru, "name_ru": row.name_ru, "name_en": row.name_en,
            "country_slug": geo["country_slug"], "region_slug": region.slug,
            "country_name": next((item["name_en"] if locale == "en" else item["name_ru"] for item in geometry if item["kind"] == "country" and item["country_slug"] == geo["country_slug"]), geo["country_slug"]),
            "region_name": region.name_en if locale == "en" else region.name_ru,
            "category": row.section_en if locale == "en" else row.section_ru, "frequency": row.frequency,
            "unit": row.unit_en or row.unit if locale == "en" else row.unit_ru or row.unit,
            "path": path, "navigation": navigation, "score": candidates[row.id]})
    return output, len(rows) > budget


def _native_title_span(raw: str, name: str) -> bool:
    """Prove native words and economic symbols without erasing unit identity.

    Commas, parentheses and ordinary title separators can differ. Percent,
    currency, ratio and index-base symbols remain part of an atomic title.
    """
    pattern = r"[a-zа-я0-9]+|[%‰$€£¥/=≤≥]"
    query_parts = re.findall(pattern, normalize(raw))
    name_parts = re.findall(pattern, normalize(name))
    return bool(name_parts) and any(query_parts[offset:offset + len(name_parts)] == name_parts
        for offset in range(len(query_parts) - len(name_parts) + 1))


async def _literal_title(db: AsyncSession, raw: str, geometry: list[dict]) -> str | None:
    """One bounded preflight preserves exact native titles before facet parsing.

    A title is protected only when its words and economic symbols occur in the query.
    Explicit outside geography/periods/units/qualifiers still remain mandatory.
    Technical identifiers are recognized by the parser; ordinary hyphenated
    names are identities only when an actual catalogue code establishes them.
    """
    code_tokens = tuple(dict.fromkeys(re.findall(r"(?<![a-z0-9_])[a-z][a-z0-9_]*(?:-[a-z0-9_]+)+(?![a-z0-9_])", normalize(raw))))
    if code_tokens:
        models = (Indicator, WorldIndicator, RegionIndicator, SubnationalIndicator)
        # Each exact-code predicate uses an indexed identity. One UNION read is
        # bounded by input tokens and never scans names or guesses an answer.
        bounded = [select(model.code.label("code")).where(model.code.in_(code_tokens)).limit(24).subquery()
            for model in models]
        rows = (await db.execute(union_all(*(select(part.c.code) for part in bounded)))).scalars().all()
        codes = set(rows)
        if len(codes) == 1:
            return next(iter(codes))
    if literal_identifier(raw, geometry):
        return None
    # Discover on the raw query first: geography, percent signs and dates may
    # be part of an actual native title. Outside spans are parsed afterwards.
    raw_phrase = phrase(raw)
    raw_words = raw_phrase.split()
    content = phrase(strip_geography(raw, geometry)[0])
    variants = [content]
    period_suffix = re.sub(r"(?:\s+(?:за|в|for|in))?\s+(?:1|2)\d{3}(?:\s+(?:год|года|году|year))?$", "", content)
    if period_suffix != content:
        variants.append(period_suffix)
    prefixes = [variant for variant in variants if len(variant) >= 24 and len(variant.split()) >= 4]
    from app.data.i18n.region_indicators_en import REGION_INDICATORS_EN
    translated = [item.get("name", "") for item in REGION_INDICATORS_EN.values()]
    translated_matches = [name for name in translated if name and len(phrase(name).split()) >= 2 and len(phrase(name)) >= 14
        and _native_title_span(raw, name)]
    if translated_matches:
        return max(translated_matches, key=lambda value: len(phrase(value)))
    # Anchored title prefixes give the catalogue's trigram indexes a bounded
    # discovery predicate. A separate whole-token span test prevents an unknown
    # qualifier from being erased by an approximate native-title match.
    windows = list(dict.fromkeys(" ".join(raw_words[i:i + size])
        for i in range(max(0, len(raw_words) - 1)) for size in (3, 4, 2)
        if len(raw_words[i:i + size]) == size and len(" ".join(raw_words[i:i + size])) >= (16 if size == 2 else 12)))
    windows = windows[:12] + [window for window in windows[-4:] if window not in windows[:12]]
    def title_patterns(value):
        # Keep the first word literal for trigram discovery. Explicit е/ё
        # spellings preserve a real first-word index anchor; later positions
        # may use one-character alternatives, followed by exact span proof.
        words = value.split()
        first = words[0]
        variants = {first}
        variants.update(first[:i] + "ё" + first[i + 1:] for i, char in enumerate(first) if char == "е")
        suffix = "%" + "%".join(_escape_like(word).replace("е", "_") for word in words[1:]) + "%"
        return [_escape_like(word) + suffix for word in sorted(variants)]
    patterns = list(dict.fromkeys(pattern for value in (*windows, *prefixes) for pattern in title_patterns(value)))
    if not patterns:
        return None
    tables = ((Indicator, Indicator.name, Indicator.name_en),
        (WorldIndicator, WorldIndicator.name_ru, WorldIndicator.name_en),
        (RegionIndicator, RegionIndicator.name, literal("")),
        (SubnationalIndicator, SubnationalIndicator.name_ru, SubnationalIndicator.name_en))
    queries = []
    for model, ru, en in tables:
        clauses = [or_(ru.ilike(pattern, escape="\\"), en.ilike(pattern, escape="\\")) for pattern in patterns]
        stmt = select(ru.label("ru"), en.label("en")).where(or_(*clauses))
        if model is Indicator:
            stmt = stmt.where(Indicator.is_active.is_(True))
        elif model is RegionIndicator:
            stmt = stmt.where(RegionIndicator.is_listed.is_(True))
        elif model is SubnationalIndicator:
            stmt = stmt.where(SubnationalIndicator.is_listed.is_(True))
        # LIMIT is inside the indexed discovery subquery. Only these bounded
        # rows undergo Python whole-span normalisation; no reverse native-name
        # predicate or per-name regex scans the entire world catalogue.
        if model is WorldIndicator:
            # A large OR of native-title windows can make PostgreSQL choose a
            # full catalogue scan even with LIMIT. Keep each discovery probe
            # independent so its literal trigram anchor remains indexable.
            leading = [" ".join(raw_words[:size]) for size in (3, 2)
                if len(raw_words[:size]) == size and len(" ".join(raw_words[:size])) >= (16 if size == 2 else 12)]
            supplemental = sorted(windows, key=lambda value: (-len(value.split()[0]), -len(value), value))
            probes = list(dict.fromkeys([*leading, *prefixes, *supplemental]))[:3]
            for value in probes:
                clauses = [or_(ru.ilike(pattern, escape="\\"), en.ilike(pattern, escape="\\"))
                    for pattern in title_patterns(value)]
                part = select(ru.label("ru"), en.label("en")).where(or_(*clauses)).limit(128).subquery()
                queries.append(select(part.c.ru, part.c.en))
        else:
            bounded = stmt.limit(128).subquery()
            queries.append(select(bounded.c.ru, bounded.c.en))
    rows = (await db.execute(union_all(*queries))).all()
    matches = [name for row in rows for name in row if name and len(phrase(name).split()) >= 2 and len(phrase(name)) >= 12
        and _native_title_span(raw, name)]
    matches.extend(prefix for row in rows for name in row if name for prefix in prefixes if phrase(name).startswith(prefix)
        and (not re.search(r"[%‰$€£¥/=≤≥]", name) or _native_title_span(raw, name)))
    return max(matches, key=lambda value: len(phrase(value)), default=None)


def _result_measure_names(item: dict, world_rows: dict) -> tuple[str, ...]:
    """Actual titles and exact official field labels establish a world measure.

    Only request-local fetched rows can provide field evidence. Categories, SEO
    and missing/unknown provider members cannot substitute for a measure.
    """
    names = (item.get("name_ru", ""), item.get("name_en", ""))
    if item.get("kind") != "world":
        return names + (("price",) if item.get("kind") == "russia"
            and item.get("code") in _registered_price_codes() else ())
    row = world_rows.get((item.get("country_slug"), item.get("code")))
    return names + (native_dimension_labels(row.provider, row.slice_json) if row is not None else ())


_REGIONAL_INDICATOR_KINDS = ("region_indicator", "subnational_indicator")
_PRICE_WORDS = re.compile(r"потребительск|инфляц|consumer price|inflation|\bcpi\b|hicp|ипц", re.I)
_ANNUAL_CHANGE_WORDS = re.compile(
    r"за год|за 12 месяц|год к году|годов\w+ (?:темп|рост|изменени)|12.month|year.over.year|annual (?:rate|change)|yoy",
    re.I,
)


def _annual_inflation_row(item: dict) -> bool:
    """Ряд цен, который уже показывает рост за год (а не индекс или месячный прирост)."""
    if item.get("kind") not in ("russia", "world"):
        return False
    text = " ".join(str(item.get(field) or "") for field in ("name_ru", "name_en", "unit"))
    code = str(item.get("code") or "")
    price = bool(_PRICE_WORDS.search(text)) or any(part in code for part in ("cpi", "hicp", "inflation"))
    annual = bool(_ANNUAL_CHANGE_WORDS.search(text)) or code.endswith(("-yoy", "-annual-rate", "-annual-change"))
    return price and annual


def _is_single_letter_query(raw: str) -> bool:
    """Запрос из одной буквы («п», «c»): человек ещё не договорил слово."""
    letters = re.findall(r"[a-zа-яё]", (raw or "").lower())
    return len(letters) == 1


def _result_sort_key(intent: SearchIntent, locale: str, raw: str = ""):
    """Порядок выдачи: сильнее совпадение выше; при равенстве региональные ряды ниже; на языке хоста выше.

    Запрос из одной буквы подходит едва ли не к каждому региональному ряду (прямые инвестиции по
    округам, цены по областям). Страны и основные показатели страны человеку нужнее, поэтому для такого
    запроса региональные ряды идут в конец независимо от счёта.
    """
    single_letter = _is_single_letter_query(raw)
    # Страна названа, регион нет («ВВП США»): ряды самой страны идут перед рядами её штатов и областей. Иначе сто
    # строк «ВРП Алабамы, Аляски…» с равным счётом заполняют выдачу, и национального ВВП в ней нет совсем.
    country_scope = bool(getattr(intent, "countries", None)) and not intent.regions

    def key(item: dict):
        regional_indicator = item["kind"] in _REGIONAL_INDICATOR_KINDS
        return (
            1 if (single_letter or country_scope) and not intent.regions and regional_indicator else 0,
            -item["score"],
            # При равном счёте годовая инфляция страны выше индекса цен и месячного прироста.
            0 if _annual_inflation_row(item) else 1,
            1 if not intent.regions and regional_indicator else 0,
            0 if (locale == "ru" and item.get("country_slug") == "russia") or (locale == "en" and item.get("country_slug") != "russia") else 1,
            item["key"],
        )

    return key


async def federated_search(db: AsyncSession, raw: str, *, limit: int = 50) -> dict:
    """One query contract with bounded SQL and truthful availability states."""
    empty = {"results": [], "total": 0, "has_more": False, "version": SEARCH_VERSION}
    if not phrase(raw):
        return empty
    if not re.search(r"[a-zа-я]", normalize(raw)):
        return {**empty, "reason": "unsupported_query"}
    geometry, countries = await _geometry(db)
    literal_title = await _literal_title(db, raw, geometry)
    intent = parse_intent(raw, geometry, literal_content=literal_title)
    fx_quoted_countries = {
        "usd-jpy": (frozenset(("united-states", "japan")), "japan"),
        "usd-rub": (frozenset(("united-states", "russia")), "russia"),
        "cny-rub": (frozenset(("china", "russia")), "russia"),
        "try-rub": (frozenset(("turkey", "russia")), "russia"),
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
    world_rows = db.info.get("fe_search_world_rows", {})
    results = [item for item in results if item["kind"] in ("country", "region", "subnational_region") or
        measure_matches(intent.terms, code=item.get("code", ""), names=_result_measure_names(item, world_rows),
            unit_names=db.info.get("fe_search_native_units", {}).get(item.get("key"), ()))]
    # Exact identities dominate; subject-specific inverse-frequency evidence only
    # breaks close lexical ties inside the already eligible candidate set.
    frequencies = title_frequencies(intent.terms, results)
    for item in results:
        if item["score"] < 900:
            item["score"] += relevance_bonus(intent.terms, names=(item.get("name_ru", ""), item.get("name_en", "")),
                frequencies=frequencies, count=len(results))
    results.sort(key=_result_sort_key(intent, locale, raw))
    seen, unique = set(), []
    for result in results:
        # Distinct slices can share canonical path but retain different code and
        # intent. Do not collapse them by URL and hide the requested variant.
        if result["key"] not in seen:
            unique.append(result)
            seen.add(result["key"])
    final, position = [], 0
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
