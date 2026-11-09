"""R8-A: студент из Самары без денег ищет «сколько нужно на жизнь», «проезд», «мрот», «стипендия»."""
import pytest

from app.services.search_intent import parse_intent
from app.services.search_r7a import r7a_demotion
from app.services.search_r8a import nearest_plan, nearest_query


@pytest.mark.parametrize("query,first", [
    ("сколько нужно на жизнь самара", "прожиточн"),
    ("сколько нужно денег на жизнь в самаре", "прожиточн"),
    ("стоимость жизни самара", "прожиточн"),
    ("проезд в автобусе самара", "проезд в маршрутном такси"),
    ("проезд в общественном транспорте самара", "проезд в маршрутном такси"),
    ("билет на автобус самара", "проезд в маршрутном такси"),
    ("безработица среди молодежи самара", "unemployment"),
    ("безработица молодёжи самарская область", "unemployment"),
    ("студенты самара", "студентов"),
    ("проезд в городском автобусе самара", "проезд в маршрутном такси"),
    ("вузы самара", "студентов"),
])
def test_student_words_reach_the_measure(query, first):
    terms = parse_intent(query, []).terms
    assert terms and terms[0][0] == first


@pytest.mark.parametrize("query,note", [
    ("мрот самара", "mrot"), ("минимальная зарплата самара", "mrot"), ("минимальный размер оплаты труда", "mrot"),
    ("стипендия самара", "stipend"), ("размер стипендии", "stipend"),
    ("пособие по безработице самара", "benefit"),
    ("зарплата официантов самара", "profession"), ("подработка студенту самара", "profession"),
    ("где дешевле снять квартиру", "cheaper_rent"), ("где дешевле жить в россии", "cheaper"),
    ("самый дешевый город россии", "cheaper"), ("кредит студенту", "loan"), ("высшее образование самара", "higher_ed"),
])
def test_empty_questions_get_nearest_plan(query, note):
    plan = nearest_plan(query)
    assert plan and plan[0] == note and plan[1]


@pytest.mark.parametrize("query", ["прожиточный минимум самара", "гречка самара", "зарплата самара", "инфляция германии"])
def test_ordinary_queries_have_no_plan(query):
    assert nearest_plan(query) is None


def test_nearest_query_names_the_region():
    assert nearest_query("прожиточный минимум", "Самарская область") == "прожиточный минимум Самарская область"
    assert nearest_query("прожиточный минимум", None) == "прожиточный минимум"


def test_survey_row_sinks_below_the_headline():
    assert r7a_demotion("Итоги выборочных обследований — численность занятых", "численность занятых самара") > 0
    assert r7a_demotion("Итоги выборочных обследований — численность занятых", "итоги обследования занятость") == 0


def test_excursion_sinks_for_bus_fare():
    from app.services.search_r8a import r8a_demotion
    assert r8a_demotion("Средняя цена: экскурсия автобусная", "автобус самара") > 0
    assert r8a_demotion("Средняя цена: экскурсия автобусная", "экскурсия автобус") == 0


def test_cheapest_regions_come_first_for_where_cheaper():
    from app.services.search_r8a import short_region_name, sort_cheapest_first
    row = {"regional_group": {"regions": [{"slug": "a", "value": 61.0}, {"slug": "b", "value": None}, {"slug": "c", "value": 15.0}]}}
    sort_cheapest_first("где дешевле снять квартиру", [row])
    assert [r["slug"] for r in row["regional_group"]["regions"]] == ["c", "a", "b"]
    row2 = {"regional_group": {"regions": [{"slug": "a", "value": 61.0}, {"slug": "c", "value": 15.0}]}}
    sort_cheapest_first("аренда однокомнатной квартиры", [row2])
    assert [r["slug"] for r in row2["regional_group"]["regions"]] == ["a", "c"]
    assert short_region_name("velichina-prozhitochnogo-minimuma-ustanovlennaya-v-tselom-po-3-11", "ru", "x") == "Прожиточный минимум"
    assert short_region_name("other", "ru", "x") == "x"
