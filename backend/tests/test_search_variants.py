"""Круг 12, BACK2 (U14, U15): дубли и одинаковые названия в выдаче поиска."""
from types import SimpleNamespace

from app.services.search_variants import collapse_equivalent, disambiguate_titles


def _hicp_row(code, dataset, coicop):
    return SimpleNamespace(
        code=code, provider="eurostat", dataset_id=dataset, unit="I15", unit_ru="индекс 2015=100",
        slice_json={"unit": "I15", "coicop": coicop, "freq": "M"}, frequency="monthly")


def _item(code, score=230, **extra):
    base = {"key": f"world:turkey:{code}", "kind": "world", "code": code, "country_slug": "turkey",
        "name": "Гармонизированный индекс потребительских цен", "frequency": "monthly", "unit": "индекс (2015 = 100)",
        "score": score, "path": f"/turkey/indicator/{code}", "navigation": "spa"}
    base.update(extra)
    return base


def test_equivalent_eurostat_slices_collapse_into_primary_with_variants():
    rows = {
        ("turkey", "tr-prc_hicp_minr-total-i15"): _hicp_row("tr-prc_hicp_minr-total-i15", "prc_hicp_minr", "TOTAL"),
        ("turkey", "tr-prc_hicp_midx-cp00-i15"): _hicp_row("tr-prc_hicp_midx-cp00-i15", "prc_hicp_midx", "CP00"),
    }
    results = [_item("tr-prc_hicp_minr-total-i15"), _item("tr-prc_hicp_midx-cp00-i15"), _item("tr-other", score=80)]
    collapsed = collapse_equivalent(results, rows)
    assert [r["code"] for r in collapsed] == ["tr-prc_hicp_minr-total-i15", "tr-other"]
    assert [v["code"] for v in collapsed[0]["variants"]] == ["tr-prc_hicp_midx-cp00-i15"]
    assert collapsed[0]["variants"][0]["path"] == "/turkey/indicator/tr-prc_hicp_midx-cp00-i15"


def test_exact_matches_and_unknown_concepts_are_never_collapsed():
    rows = {("turkey", "a"): _hicp_row("a", "prc_hicp_midx", "CP00"), ("turkey", "b"): _hicp_row("b", "prc_hicp_minr", "TOTAL")}
    exact = [_item("a", score=1000), _item("b", score=1000)]
    assert len(collapse_equivalent(exact, rows)) == 2
    unknown = [_item("x"), _item("y")]
    assert len(collapse_equivalent(unknown, {})) == 2


def test_other_frequency_or_unit_stays_separate():
    rows = {("turkey", "m"): _hicp_row("m", "prc_hicp_midx", "CP00"), ("turkey", "q"): _hicp_row("q", "prc_hicp_midx", "CP00")}
    results = [_item("m"), _item("q", frequency="annual")]
    assert len(collapse_equivalent(results, rows)) == 2


def test_same_title_gets_period_and_unit_hints_in_russian():
    results = [
        _item("tr-a", unit="индекс (2015 = 100)"),
        _item("tr-b", unit="изменение за год", frequency="annual"),
        _item("tr-c", unit="изменение за год"),
    ]
    disambiguate_titles(results, {}, "ru")
    names = [r["name"] for r in results]
    assert len(set(names)) == 3
    assert names[1].endswith("(годовой ряд, изменение за год)")
    assert names[0].endswith("(индекс (2015 = 100))") or "2015" in names[0]


def test_same_title_gets_sex_and_age_labels_from_slice():
    rows = {
        ("germany", "de-u-f-gt25"): SimpleNamespace(slice_json={"sex": "F", "age": "Y_GE25"}),
        ("germany", "de-u-m-gt25"): SimpleNamespace(slice_json={"sex": "M", "age": "Y_GE25"}),
    }
    results = [
        {"key": "world:germany:de-u-f-gt25", "kind": "world", "code": "de-u-f-gt25", "country_slug": "germany",
         "name": "Уровень безработицы", "frequency": "monthly", "unit": "%"},
        {"key": "world:germany:de-u-m-gt25", "kind": "world", "code": "de-u-m-gt25", "country_slug": "germany",
         "name": "Уровень безработицы", "frequency": "monthly", "unit": "%"},
    ]
    disambiguate_titles(results, rows, "ru")
    assert results[0]["name"] == "Уровень безработицы (женщины)"
    assert results[1]["name"] == "Уровень безработицы (мужчины)"


def test_unique_titles_and_other_countries_are_untouched():
    one = [_item("tr-a"), _item("fr-a", country_slug="france", key="world:france:fr-a")]
    disambiguate_titles(one, {}, "ru")
    assert one[0]["name"] == one[1]["name"] == "Гармонизированный индекс потребительских цен"
