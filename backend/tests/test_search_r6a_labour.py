"""R6-A: бытовые слова про работу, доходы и пенсии приводят к своим показателям, а не к чужим."""
import pytest

from app.services.search_intent import parse_intent
from app.services.search_r6a import arrears_demotion


@pytest.mark.parametrize("query,first_alt", [
    ("прожиточный минимум", "прожиточн"),
    ("прожиточного минимума самарская область", "прожиточн"),
    ("безработные", "unemployment"),
    ("средняя пенсия", "sredniy-razmer-naznachennyh-pensiy"),
    ("размер пенсии", "sredniy-razmer-naznachennyh-pensiy"),
    ("рынок труда самара", "занятост"),
    ("средний доход", "среднедушев"),
    ("минимальная пенсия", "прожиточного минимума пенсионера"),    ("просрочка по зарплате", "просроченная задолженность по заработной плате"),
])
def test_everyday_words_reach_the_measure(query, first_alt):
    assert any(group[0] == first_alt for group in parse_intent(query, []).terms)


def test_mrot_is_not_any_minimum():
    terms = parse_intent("мрот", []).terms
    assert terms and "минималь" not in terms[0]


@pytest.mark.parametrize("city", ["тольятти", "сызрань", "энгельс", "набережные челны", "магнитогорск"])
def test_city_leads_to_its_region(city):
    assert parse_intent(f"зарплата {city}", []).terms[0][0] == "wage"


def test_arrears_sink_below_average_pay():
    assert arrears_demotion("Просроченная задолженность по заработной плате", "зарплата самара") > 0
    assert arrears_demotion("Просроченная задолженность по заработной плате", "долги по зарплате самара") == 0
    assert arrears_demotion("Медианная заработная плата", "зарплата самара") == 0
