"""Synthetic general role/control pairs; no holdout-code or answer fixtures."""
import pytest

from app.services.search_intent import parse_intent, match_score, nominal_variants
from app.services.search_units import unit_metadata


def keys(intent):
    return {group[0] for group in intent.terms}


@pytest.mark.parametrize(("prefix", "actual_name"), [
    ("бен", "Бензиновый поток резервуара"),
    ("ruo", "RUONIA Overnight reservoir pressure"),
    ("дене", "Денежный поток резервуара"),
    ("госу", "Государственный реестр резервуаров"),
    ("averag", "Average reservoir pressure"),
])
def test_actual_identity_prefix_is_distinct_from_fuzzy_unit_metadata(prefix, actual_name):
    intent = parse_intent(prefix, [])
    assert match_score(intent, names=(actual_name,)) is not None
    assert match_score(intent, code="native-" + actual_name.replace(" ", "-")) is not None
    assert match_score(intent, names=("Other series",), metadata=actual_name) is None
    assert match_score(parse_intent(prefix + " magical", []), names=(actual_name,)) is None
    assert match_score(intent, names=("Other series " + prefix + "ography",)) is not None


@pytest.mark.parametrize(("typo", "marker"), [
    ("montly", "search-freq-monthly"), ("percet", "search-unit-percent"),
    ("millio", "search-unit-million"), ("averag", "search-mode-avg"),
])
def test_typed_metadata_alone_cannot_repair_control_typo(typo, marker):
    intent = parse_intent("reservoir " + typo, [])
    assert marker not in keys(intent)
    assert match_score(intent, names=("Reservoir pressure",), metadata=marker) is None


@pytest.mark.parametrize(("role", "mode", "frequency"), [
    ("средняя за квартал", "avg", "quarterly"),
    ("quarter average", "avg", "quarterly"),
    ("к предыдущему кварталу", "pop", "quarterly"),
    ("over previous quarter", "pop", "quarterly"),
    ("к предыдущему месяцу", "pop", "monthly"),
    ("over previous month", "pop", "monthly"),
    ("к тому же месяцу прошлого года", "yoy", "monthly"),
    ("same month last year", "yoy", "monthly"),
])
def test_complete_temporal_role_has_independent_mode_and_frequency(role, mode, frequency):
    intent = parse_intent("reservoir pressure " + role + " 2024", [])
    assert intent.error is None and intent.year == 2024
    assert keys(intent) >= {"search-mode-" + mode, "search-freq-" + frequency}
    native = f"search-mode-{mode} search-freq-{frequency}"
    assert match_score(intent, names=("Reservoir pressure",), metadata=native) is not None
    assert match_score(intent, names=("Reservoir pressure",), metadata=f"search-mode-level search-freq-{frequency}") is None
    assert match_score(intent, names=("Reservoir pressure",), metadata=f"search-mode-{mode} search-freq-weekly") is None
    assert match_score(parse_intent("reservoir pressure " + role + " magical 2024", []),
        names=("Reservoir pressure",), metadata=native) is None


@pytest.mark.parametrize("period", ["q1", "first quarter", "квартал", "первый квартал", "today"])
def test_absolute_period_still_fails_closed_next_to_known_role(period):
    assert parse_intent("reservoir pressure average quarterly " + period + " 2024", []).error == "unsupported_period"


@pytest.mark.parametrize("unit", [
    "percentage points", "percent points", "процентных пунктах", "процентных пунктов", "п.п.",
])
def test_point_compound_is_a_native_unit_role_before_rate_rewrites(unit):
    intent = parse_intent("mortgage interest " + unit, [])
    assert "search-unit-percentage-point" in keys(intent)
    assert "search-unit-percent" not in keys(intent)
    assert match_score(intent, names=("Mortgage Interest Rate",), metadata="search-unit-percentage-point") is not None
    assert match_score(intent, names=("Mortgage Interest Rate",), metadata="search-unit-percent") is None
    mixed = parse_intent("mortgage interest " + unit + " %", [])
    assert keys(mixed) >= {"search-unit-percentage-point", "search-unit-percent"}
    assert match_score(mixed, names=("Mortgage Interest Rate",), metadata="search-unit-percentage-point") is None


def test_point_span_cannot_consume_a_separate_unknown_unit_qualifier():
    intent = parse_intent("mortgage interest percentage points magical", [])
    assert ("magical",) in intent.terms
    assert match_score(intent, names=("Mortgage Interest Rate",), metadata="search-unit-percentage-point") is None
    misspelt = parse_intent("mortgage interest percentage pints", [])
    assert "search-unit-percentage-point" not in keys(misspelt)
    assert match_score(misspelt, names=("Mortgage Interest Rate",), metadata="search-unit-percentage-point") is None


@pytest.mark.parametrize("word", ["процентов", "процентах", "процентом", "percentages"])
def test_exact_percent_inflection_is_one_quantity_role(word):
    intent = parse_intent("reservoir pressure " + word, [])
    assert intent.terms.count(("search-unit-percent",)) == 1
    assert (word,) not in intent.terms
    assert match_score(intent, names=("Reservoir pressure",), metadata="search-unit-percent") is not None
    assert match_score(intent, names=("Reservoir pressure",), metadata="search-unit-percentage-point") is None


@pytest.mark.parametrize("title", [
    "Threshold at 50% of median", "Reservoir threshold 50%", "% Reservoir threshold 50",
])
def test_percent_symbol_inside_authoritative_title_is_not_an_outside_unit(title):
    intent = parse_intent(title, [], literal_content=title)
    assert keys(intent) == {title.casefold()}
    assert match_score(intent, names=(title,)) is not None
    outside = parse_intent(title + " %", [], literal_content=title)
    assert "search-unit-percent" in keys(outside)
    assert match_score(outside, names=(title,)) is None


def test_atomic_literal_owns_its_temporal_tokens_and_external_role_survives():
    title = "Quarter average reservoir report"
    plain = parse_intent(title + " 2024", [], literal_content=title)
    assert plain.error is None and plain.year == 2024
    assert plain.terms == ((title.casefold(),),)
    qualified = parse_intent(title + " over previous month 2024", [], literal_content=title)
    assert keys(qualified) >= {title.casefold(), "search-mode-pop", "search-freq-monthly"}


def geo(name, slug="synthetic-compound"):
    return dict(key="region:russia:" + slug, kind="region", slug=slug,
        name_ru=name, country_slug="russia")


@pytest.mark.parametrize(("native_name", "inflected"), [
    ("Северная область — Лес", "Северной области — Лесе"),
    ("Северная область—Лес", "Северной области — Лесе"),
    ("Северная область — Лес", "Северной области — Леса"),
    ("Северная область — Лес", "Северной области — Лесу"),
    ("Северная область — Лес", "Северной областью — Лесом"),
    ("Северная область — Лес", "Северную область — Лес"),
    ("Северная область — Волга", "Северной области — Волге"),
    ("Северная область — Атрия", "Северной области — Атрии"),
])
def test_complete_known_dash_suffix_inflects_with_its_administrative_name(native_name, inflected):
    geometry = [geo(native_name)]
    intent = parse_intent("pressure " + inflected, geometry)
    assert intent.regions == frozenset(("region:russia:synthetic-compound",))
    assert intent.terms == (("pressure",),)
    assert not parse_intent("pressure " + inflected, []).regions
    assert match_score(parse_intent("pressure " + inflected + " magical", geometry), names=("Pressure",)) is None


@pytest.mark.parametrize("query", [
    "pressure Северной области — Горы", "pressure Северной области",
    "pressure Северной области — Леса дальнего", "pressure Северной области — Лесе magical",
])
def test_compound_place_requires_the_actual_complete_suffix(query):
    intent = parse_intent(query, [geo("Северная область — Лес")])
    assert match_score(intent, names=("Pressure",)) is None


def test_different_full_places_share_no_shortened_suffix_alias():
    geometry = [geo("Северная область — Лес", "forest"), geo("Северная область — Гора", "mountain")]
    intent = parse_intent("pressure Северной области — Лесе", geometry)
    assert intent.regions == frozenset(("region:russia:forest",))
    ambiguous = parse_intent("pressure Северной области — Лесе", geometry + [geo("Северная область — Лес", "forest2")])
    assert ambiguous.regions == frozenset(("region:russia:forest", "region:russia:forest2"))


def test_catalogue_exclusion_tail_is_preserved_verbatim():
    geometry = [geo("Северная область (без автономного округа)", "excluded")]
    intent = parse_intent("pressure Северной области (без автономного округа)", geometry)
    assert intent.regions == frozenset(("region:russia:excluded",))
    assert intent.terms == (("pressure",),)
    assert not parse_intent("pressure Северной области", geometry).regions


@pytest.mark.parametrize(("case_word", "native_word"), [
    ("болезнями", "болезни"), ("моделями", "модели"),
    ("организациями", "организации"), ("методами", "методы"),
])
def test_nominal_case_expands_one_required_group_to_actual_complete_words(case_word, native_word):
    intent = parse_intent("pressure " + case_word + " 2024", [])
    assert any(case_word in group and native_word in group for group in intent.terms)
    assert match_score(intent, names=("Pressure " + native_word,)) is not None
    assert match_score(intent, names=("Pressure " + native_word + "ография",)) is None
    assert match_score(intent, names=("Pressure",)) is None
    assert match_score(parse_intent("pressure " + case_word + " magical 2024", []),
        names=("Pressure " + native_word,)) is None


@pytest.mark.parametrize("unit_word", ["процентами", "кварталами", "месяцами", "миллионами"])
def test_nominal_fallback_cannot_turn_control_or_unit_forms_into_domain_facets(unit_word):
    intent = parse_intent("pressure " + unit_word, [])
    assert (unit_word,) in intent.terms
    assert nominal_variants(unit_word) == (unit_word,)
    assert match_score(intent, names=("Pressure",), metadata="search-unit-percent search-unit-usd search-freq-quarterly search-unit-million") is None


def test_complete_dollar_instrumental_alias_requires_actual_usd_unit():
    intent = parse_intent("pressure долларами", [])
    assert ("search-unit-usd",) in intent.terms
    assert ("долларами",) not in intent.terms
    assert match_score(intent, names=("Pressure",), metadata=unit_metadata("USD")) is not None
    assert match_score(intent, names=("Pressure",), metadata=unit_metadata("CAD")) is None
    assert match_score(intent, names=("Pressure",), metadata=unit_metadata(None)) is None
    assert match_score(intent, names=("Pressure USD dollars",)) is None
    assert match_score(parse_intent("pressure долларами magical", []), names=("Pressure",), metadata=unit_metadata("USD")) is None


def test_nominal_case_selects_a_complete_grammatical_form_not_two_arbitrary_suffixes():
    assert match_score(parse_intent("pressure болезнями", []), names=("Pressure болезны",)) is None
    assert match_score(parse_intent("pressure методами", []), names=("Pressure методи",)) is None
    assert match_score(parse_intent("pressure моделями", []), names=("Pressure моделя",)) is None
    assert match_score(parse_intent("pressure перевозками", []), names=("Pressure перевозки",)) is not None
    assert match_score(parse_intent("pressure перевозками", []), names=("Pressure перевозкы",)) is None


@pytest.mark.parametrize(("age", "marker"), [
    ("age 15–74", "search-dim-age-y15-74"),
    ("under 6 years", "search-dim-age-y-lt6"),
])
def test_bounded_age_role_preserves_an_independent_iso_observation_date(age, marker):
    intent = parse_intent("incidents " + age + " 2024-03", [])
    assert intent.error is None and intent.year == 2024 and intent.month == 3
    assert marker in keys(intent)
    assert match_score(intent, names=("Incidents",), metadata=marker) is not None
    assert match_score(intent, names=("Incidents",), metadata="search-dim-age-y15-64") is None
    assert match_score(parse_intent("incidents " + age + " magical 2024-03", []), names=("Incidents",), metadata=marker) is None


def test_unknown_age_range_and_intrinsic_literal_age_do_not_infer_a_dimension():
    unknown = parse_intent("incidents age 123 to 321 2024", [])
    assert not any(key.startswith("search-dim-age-") for key in keys(unknown))
    assert match_score(unknown, names=("Incidents",), metadata="search-dim-age-y15-74") is None
    title = "Incidents age 15–74 report"
    literal = parse_intent(title + " 2024", [], literal_content=title)
    assert literal.terms == ((title.casefold(),),)
    assert literal.year == 2024 and literal.error is None
