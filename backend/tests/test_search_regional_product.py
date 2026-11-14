"""«ВВП + регион России» — это ВРП; «ВРП на душу населения» — своё понятие (14.11.2026, нулевая выдача на боевом)."""
import pytest

from app.services.search_intent import parse_intent

GEOMETRY = [
    dict(key=f"country:{slug}", kind="country", slug=slug, country_slug=slug, country_code=code, name_ru=ru, name_en=en)
    for slug, code, ru, en in (("russia", "RU", "Россия", "Russia"), ("united-states", "US", "США", "United States"))
] + [
    dict(key="region:russia:moskva", kind="region", slug="moskva", country_slug="russia",
         name_ru="г. Москва", name_en="Moscow"),
    dict(key="region:russia:sverdlovskaya-oblast", kind="region", slug="sverdlovskaya-oblast", country_slug="russia",
         name_ru="Свердловская область", name_en="Sverdlovsk Oblast"),
    dict(key="region:russia:respublika-tatarstan", kind="region", slug="respublika-tatarstan", country_slug="russia",
         name_ru="Республика Татарстан", name_en="Republic of Tatarstan"),
    dict(key="subnational:united-states:california", kind="subnational_region", slug="california",
         country_slug="united-states", name_ru="Калифорния", name_en="California"),
]

GRP = "valovoy-regionalnyy-produkt"
GRP_PC = "valovoy-regionalnyy-produkt-na-dushu-naseleniya"


def concepts(query):
    intent = parse_intent(query, GEOMETRY)
    return {group[0] for group in intent.terms}, intent


@pytest.mark.parametrize("query", ["ввп москвы", "ввп свердловской области", "ввп свердловская область",
                                   "ввп татарстана", "ввп республики татарстан", "gdp sverdlovsk oblast"])
def test_gdp_with_russian_region_means_grp(query):
    keys, intent = concepts(query)
    assert keys == {GRP}, (query, intent.terms)
    assert intent.regions


@pytest.mark.parametrize("query", ["ввп на душу населения свердловская область", "врп на душу населения москва",
                                   "врп на душу населения", "валовой региональный продукт на душу населения"])
def test_per_capita_grp_is_its_own_concept(query):
    keys, intent = concepts(query)
    assert keys == {GRP_PC}, (query, intent.terms)
    assert intent.corrected is None  # не исправляется в «ввп на душу»


@pytest.mark.parametrize("query,expected", [
    ("ввп", {"gdp"}), ("ввп россии", {"gdp"}), ("ввп сша", {"gdp"}), ("ввп на душу населения", {"gdp-per-capita"}),
    ("врп москва", {GRP}),
])
def test_national_gdp_unchanged(query, expected):
    keys, _intent = concepts(query)
    assert keys == expected, query
