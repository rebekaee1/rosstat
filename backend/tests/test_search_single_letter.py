"""БД6: запрос из одной буквы не открывается региональными рядами; страны и основные показатели выше."""

from __future__ import annotations

from types import SimpleNamespace

from app.services.search import _is_single_letter_query, _result_sort_key


def _row(kind, key, score, country="russia"):
    return {"kind": kind, "key": key, "score": score, "country_slug": country}


def test_single_letter_detection():
    assert _is_single_letter_query("п")
    assert _is_single_letter_query(" C ")
    assert _is_single_letter_query("ё")
    assert not _is_single_letter_query("пи")
    assert not _is_single_letter_query("usd")
    assert not _is_single_letter_query("1")
    assert not _is_single_letter_query("")


def test_regional_indicators_go_last_for_one_letter_even_with_a_higher_score():
    intent = SimpleNamespace(regions=frozenset())
    rows = [
        _row("region_indicator", "region:cfo:fdi", 90),
        _row("country", "country:de", 40, "germany"),
        _row("russia", "cpi", 41),
        _row("subnational_indicator", "sub:ca:pop", 80, "united-states"),
    ]
    ordered = sorted(rows, key=_result_sort_key(intent, "ru", "ф"))
    assert [r["key"] for r in ordered] == ["cpi", "country:de", "region:cfo:fdi", "sub:ca:pop"]


def test_longer_queries_keep_the_plain_score_order():
    intent = SimpleNamespace(regions=frozenset())
    rows = [
        _row("russia", "cpi", 41),
        _row("region_indicator", "region:cfo:fdi", 90),
    ]
    ordered = sorted(rows, key=_result_sort_key(intent, "ru", "фдн"))
    assert [r["key"] for r in ordered] == ["region:cfo:fdi", "cpi"]


def test_annual_inflation_beats_the_index_at_an_equal_score_only():
    from app.services.search import _annual_inflation_row

    index = {"kind": "world", "key": "a-index", "score": 86, "code": "de-cpi", "country_slug": "germany",
             "name_ru": "Индекс потребительских цен", "name_en": "Consumer price index", "unit": "индекс 2015=100"}
    annual = {"kind": "world", "key": "z-annual", "score": 86, "code": "de-cpi-annual-rate", "country_slug": "germany",
              "name_ru": "Потребительские цены", "name_en": "Annual rate of change in consumer prices", "unit": "%"}
    weaker_annual = {**annual, "key": "b-annual", "score": 80}
    gdp_change = {"kind": "world", "key": "c-gdp", "score": 86, "code": "de-gdp-yoy", "country_slug": "germany",
                  "name_ru": "ВВП", "name_en": "GDP annual change", "unit": "%"}
    assert _annual_inflation_row(annual) and not _annual_inflation_row(index)
    assert not _annual_inflation_row(gdp_change), "правило только про цены"
    intent = SimpleNamespace(regions=frozenset())
    ordered = sorted([index, weaker_annual, annual], key=_result_sort_key(intent, "en", "inflation germany"))
    # Равный счёт: годовая инфляция выше индекса; меньший счёт остаётся ниже.
    assert [r["key"] for r in ordered] == ["z-annual", "a-index", "b-annual"]


def test_a_named_region_keeps_its_indicators_in_front():
    intent = SimpleNamespace(regions=frozenset({"moskva"}))
    rows = [_row("russia", "cpi", 41), _row("region_indicator", "region:moskva:pop", 90)]
    ordered = sorted(rows, key=_result_sort_key(intent, "ru", "м"))
    assert ordered[0]["key"] == "region:moskva:pop"


def test_named_country_puts_its_own_rows_before_the_states_of_that_country():
    """Круг 10 (звонок 23): «ВВП США» открывалась ста строками штатов, национального ВВП в выдаче не было."""
    intent = SimpleNamespace(regions=frozenset(), countries=frozenset({"united-states"}))
    rows = [
        _row("subnational_indicator", "sub:al:gdp", 84, "united-states"),
        _row("subnational_indicator", "sub:ak:gdp", 84, "united-states"),
        _row("world", "world:us:gdp-nominal", 80, "united-states"),
        _row("world", "world:us:industry", 77, "united-states"),
    ]
    ordered = sorted(rows, key=_result_sort_key(intent, "ru", "ввп сша"))
    assert [r["key"] for r in ordered][:2] == ["world:us:gdp-nominal", "world:us:industry"]


def test_without_a_named_country_states_keep_the_plain_score_order():
    intent = SimpleNamespace(regions=frozenset(), countries=frozenset())
    rows = [_row("world", "w", 70, "united-states"), _row("subnational_indicator", "s", 84, "united-states")]
    ordered = sorted(rows, key=_result_sort_key(intent, "ru", "ввп"))
    assert ordered[0]["key"] == "s"


def test_a_named_state_still_leads_with_its_own_indicators():
    intent = SimpleNamespace(regions=frozenset({"california"}), countries=frozenset({"united-states"}))
    rows = [_row("world", "w", 70, "united-states"), _row("subnational_indicator", "s", 84, "united-states")]
    ordered = sorted(rows, key=_result_sort_key(intent, "ru", "ввп калифорния"))
    assert ordered[0]["key"] == "s"
