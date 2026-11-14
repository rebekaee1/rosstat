"""Пустая выдача из-за слова, которого нет в названиях: «Ближайшее» без этого слова (14.11.2026).

Основная выдача остаётся пустой (ADR-0016: неизвестное уточнение не выбрасывается), подсказка — в `nearest`.
Фикстура — общий набор поиска (`test_search_federated.search_client`).
"""
from tests.test_search_federated import get, search_client  # noqa: F401 — фикстура


def test_gdp_of_a_russian_region_finds_grp(search_client):  # noqa: F811
    body = get(search_client, "ввп москвы")
    assert body["results"] and body["results"][0]["code"] == "valovoy-regionalnyy-produkt"


def test_unknown_word_keeps_main_results_empty_and_suggests_without_it(search_client):  # noqa: F811
    body = get(search_client, "валовой региональный продукт москвы структура")
    assert body["results"] == []
    near = body["nearest"]
    assert near["note"] == "without_word" and near["words"] == ["структура"]
    assert near["results"][0]["code"] == "valovoy-regionalnyy-produkt"


def test_single_generic_word_left_gives_no_suggestion(search_client):  # noqa: F811
    # После выброса «коэффициент» осталось бы одно понятие без региона — случайные ряды не подсказываем.
    body = get(search_client, "население коэффициент")
    assert body["results"] == [] and "nearest" not in body


def test_queries_with_results_are_untouched(search_client):  # noqa: F811
    body = get(search_client, "врп москва")
    assert body["results"] and "nearest" not in body
