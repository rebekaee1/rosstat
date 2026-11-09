"""R7-A: журналист районной газеты ищет по своему региону одной фразой, первая строка — про его показатель."""
import pytest

from app.services.search_intent import parse_intent
from app.services.search_r7a import REGION_HEADLINES_R7A, r7a_demotion


@pytest.mark.parametrize("query,first", [
    ("индекс потребительских цен самара", "cpi"),
    ("инфляция самара", "cpi"),
    ("прожиточный минимум детей", "прожиточн"),
    ("прожиточный минимум на душу населения", "прожиточн"),
    ("прожиточный минимум трудоспособного населения самарская область", "прожиточн"),
    ("браки самара", "брачност"),
    ("число разводов самарская область", "разводимост"),
    ("потребительская корзина самара", "набора продуктов"),
    ("стоимость квадратного метра самара", "рынке жилья"),
    ("сбережения самара", "вклады"),
    ("численность занятых самара", "employment-count"),
    ("номинальная зарплата самара", "wages-nominal"),
    ("население самара", "population"),
])
def test_local_words_reach_the_measure(query, first):
    terms = parse_intent(query, []).terms
    assert terms and terms[0][0] == first


def test_every_headline_key_is_a_concept_key():
    keys = {group[0] for group in parse_intent("инфляция", []).terms}
    assert "cpi" in keys and "cpi" in REGION_HEADLINES_R7A


def test_lookalike_rows_sink():
    assert r7a_demotion("Просроченная задолженность по заработной плате работникам", "номинальная зарплата самара") > 0
    assert r7a_demotion("Численность занятых, приходящихся на одного пенсионера", "численность занятых самара") > 0
    assert r7a_demotion("Численность занятых, приходящихся на одного пенсионера", "занятые на одного пенсионера") == 0
    assert r7a_demotion("Величина прожиточного минимума в IV квартале 2001-2020 гг", "прожиточный минимум") > 0
    assert r7a_demotion("Среднегодовая численность занятых", "численность занятых самара") == 0
