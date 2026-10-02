"""Geography declension/possessives stay bounded to actual full catalogue names."""
import pytest

from app.services.search_intent import match_score, parse_intent, phrase, strip_geography


def region(slug, ru, en=None, country="russia", kind="region"):
    return dict(key=f"{kind}:{country}:{slug}", kind=kind, slug=slug,
        name_ru=ru, name_en=en, country_slug=country)


GEOMETRY = [
    dict(key="country:russia", kind="country", slug="russia", name_ru="Россия",
        name_en="Russia", country_slug="russia", country_code="RU"),
    dict(key="country:united-states", kind="country", slug="united-states", name_ru="США",
        name_en="United States", country_slug="united-states", country_code="US"),
    region("voronezhskaya-oblast", "Воронежская область", "Voronezh Oblast"),
    region("nizhegorodskaya-oblast", "Нижегородская область", "Nizhny Novgorod Oblast"),
    region("primorskiy-kray", "Приморский край", "Primorsky Krai"),
    region("chechenskaya-respublika", "Чеченская Республика", "Chechen Republic"),
    region("kabardino-balkarskaya-respublika", "Кабардино-Балкарская Республика"),
    region("evreyskaya-ao", "Еврейская автономная область"),
    region("yamalo-nenetskiy-ao", "Ямало-Ненецкий автономный округ"),
    region("respublika-mariy-el", "Республика Марий Эл", "Republic of Mari El"),
    region("arhangelskaya-oblast", "Архангельская область", "Arkhangelsk Oblast"),
    region("arhangelskaya-oblast-bez-ao", "Архангельская область (без автономного округа)",
        "Arkhangelsk Oblast (excluding autonomous area)", kind="unsupported_region"),
    region("tyumenskaya-oblast", "Тюменская область", "Tyumen Oblast"),
    region("tyumenskaya-oblast-bez-ao", "Тюменская область (без автономных округов)",
        "Tyumen Oblast (excluding autonomous areas)", kind="unsupported_region"),
    region("wisconsin", "Висконсин", "Wisconsin", "united-states", "subnational_region"),
]


@pytest.mark.parametrize(("query", "slug"), [
    ("население в Воронежской области", "voronezhskaya-oblast"),
    ("население Воронежскую область", "voronezhskaya-oblast"),
    ("население Воронежской областью", "voronezhskaya-oblast"),
    ("население в Нижегородской области", "nizhegorodskaya-oblast"),
    ("население в Приморском крае", "primorskiy-kray"),
    ("население Приморского края", "primorskiy-kray"),
    ("население Приморскому краю", "primorskiy-kray"),
    ("население Приморским краем", "primorskiy-kray"),
    ("население Чеченской республики", "chechenskaya-respublika"),
    ("население Чеченской республике", "chechenskaya-respublika"),
    ("население Кабардино-Балкарской республики", "kabardino-balkarskaya-respublika"),
    ("население в Еврейской автономной области", "evreyskaya-ao"),
    ("население Ямало-Ненецкого автономного округа", "yamalo-nenetskiy-ao"),
    ("население Ямало-Ненецком автономном округе", "yamalo-nenetskiy-ao"),
    ("население в Республике Марий Эл", "respublika-mariy-el"),
    ("население Республики Марий Эл", "respublika-mariy-el"),
])
def test_actual_full_region_name_resolves_in_productive_cases(query, slug):
    intent = parse_intent(query, GEOMETRY)
    assert intent.regions == frozenset((f"region:russia:{slug}",))
    assert intent.countries == frozenset(("russia",))
    assert match_score(intent, code="native-population", names=("Population",)) is not None


@pytest.mark.parametrize(("query", "slug"), [
    ("население Архангельской области (без автономного округа)", "arhangelskaya-oblast-bez-ao"),
    ("население в Тюменской области (без автономных округов)", "tyumenskaya-oblast-bez-ao"),
])
def test_inflected_nested_remainder_never_becomes_inclusive_region(query, slug):
    intent = parse_intent(query, GEOMETRY)
    assert intent.regions == frozenset((f"unsupported_region:russia:{slug}",))
    assert intent.terms == (("population", "населен", "resident population"),)


@pytest.mark.parametrize("apostrophe", ["'", "’"])
@pytest.mark.parametrize(("place", "country", "expected_region"), [
    ("Russia", "russia", None),
    ("Wisconsin", "united-states", "subnational_region:united-states:wisconsin"),
    ("Mari El", "russia", "region:russia:respublika-mariy-el"),
    ("United States", "united-states", None),
])
def test_known_english_possessive_does_not_leave_required_s(place, country, expected_region, apostrophe):
    intent = parse_intent(place + apostrophe + "s population", GEOMETRY)
    assert intent.countries == frozenset((country,))
    assert intent.regions == frozenset((expected_region,)) if expected_region else not intent.regions
    assert ("s",) not in intent.terms
    assert match_score(intent, code="native-population", names=("Population",)) is not None


def test_unpunctuated_s_is_still_an_unknown_qualifier():
    intent = parse_intent("Russia s population", GEOMETRY)
    assert intent.countries == frozenset(("russia",))
    assert ("s",) in intent.terms
    assert match_score(intent, code="native-population", names=("Population",)) is None


@pytest.mark.parametrize("query", [
    "population Atlantis’s", "population fictional область", "population в Лунной области",
    "population Воронежский бюджет", "population Приморского района",
])
def test_unknown_place_and_adjective_without_known_administrative_head_stays_required(query):
    intent = parse_intent(query, GEOMETRY)
    assert not intent.countries and not intent.regions
    assert match_score(intent, code="native-population", names=("Population",)) is None


def test_unknown_qualifier_after_actual_case_is_not_ignored():
    intent = parse_intent("население в Воронежской области magical", GEOMETRY)
    assert intent.regions == frozenset(("region:russia:voronezhskaya-oblast",))
    assert ("magical",) in intent.terms
    assert match_score(intent, code="native-population", names=("Population",)) is None


def test_explicit_unsupported_suffix_without_catalogue_entity_stays_required():
    without_remainders = [item for item in GEOMETRY if item["kind"] != "unsupported_region"]
    intent = parse_intent("население Архангельской области (без автономного округа)", without_remainders)
    assert intent.regions == frozenset(("region:russia:arhangelskaya-oblast",))
    assert ("без",) in intent.terms
    assert match_score(intent, code="native-population", names=("Population",)) is None


def test_identical_full_case_span_keeps_true_catalogue_ambiguity():
    geometry = GEOMETRY + [region("second-entity", "Воронежская область", country="another-country")]
    intent = parse_intent("население Воронежской области", geometry)
    assert intent.regions == frozenset(("region:russia:voronezhskaya-oblast", "region:another-country:second-entity"))
    assert intent.countries == frozenset(("russia", "another-country"))


def test_possessive_country_internal_to_protected_literal_stays_literal():
    title = "Russia’s consumer sentiment index"
    content, countries, regions, _corrections = strip_geography(title + " Wisconsin", GEOMETRY, literal_content=title)
    assert countries == frozenset(("united-states",))
    assert regions == frozenset(("subnational_region:united-states:wisconsin",))
    assert phrase(content) == phrase(title)
    intent = parse_intent(title + " Wisconsin", GEOMETRY, literal_content=title)
    assert intent.terms == ((title.casefold(),),)


def test_possessive_does_not_reactivate_ordinary_iso_words():
    intent = parse_intent("let us’s population grow", GEOMETRY)
    assert not intent.countries
    assert ("s",) in intent.terms


@pytest.mark.parametrize("case_name", ["Нижней области", "Нижнюю область", "Нижней областью"])
def test_soft_adjective_case_requires_an_actual_entity_in_supplied_geometry(case_name):
    geometry = [region("synthetic-lower-oblast", "Нижняя область")]
    assert parse_intent("population " + case_name, geometry).regions == frozenset(("region:russia:synthetic-lower-oblast",))
    assert not parse_intent("population " + case_name, []).regions


@pytest.mark.parametrize(("name", "form", "slug"), [
    ("Германия", "Германией", "germany"),
    ("Франция", "Францию", "france"),
    ("Канада", "Канадой", "canada"),
    ("Польша", "Польшей", "poland"),
])
def test_single_word_country_cases_derive_only_actual_catalogue_name(name, form, slug):
    geometry = [dict(key=f"country:{slug}", kind="country", slug=slug,
        name_ru=name, country_slug=slug)]
    intent = parse_intent("population " + form, geometry)
    assert intent.countries == frozenset((slug,))
    assert match_score(intent, code="population", names=("Population",)) is not None
    assert not parse_intent("population " + form, []).countries


@pytest.mark.parametrize(("name", "form", "slug"), [
    ("Висконсин", "Висконсине", "wisconsin"),
    ("Вермонт", "Вермонта", "vermont"),
    ("Орегон", "Орегоном", "oregon"),
])
def test_actual_hard_consonant_us_state_cases_are_full_names(name, form, slug):
    geometry = [region(slug, name, country="united-states", kind="subnational_region")]
    intent = parse_intent("population " + form, geometry)
    assert intent.regions == frozenset((f"subnational_region:united-states:{slug}",))
    assert match_score(intent, code="population", names=("Population",)) is not None
    assert not parse_intent("population " + form, []).regions


@pytest.mark.parametrize(("name", "slug"), [
    ("Russian", "russia"), ("American", "united-states"), ("Americans", "united-states"),
    ("Canadian", "canada"), ("Australian", "australia"), ("Mexican", "mexico"),
])
def test_bounded_known_demonym_uses_only_an_actual_country(name, slug):
    geometry = [dict(key=f"country:{slug}", kind="country", slug=slug,
        name_en=slug, country_slug=slug)]
    intent = parse_intent(name + " population", geometry)
    assert intent.countries == frozenset((slug,))
    assert not intent.corrected
    assert not parse_intent(name + " population", []).countries
    title = name + " household income"
    assert not parse_intent(title, geometry, literal_content=title).countries
