"""Предлог места для страны: «в» / «во» / «на» в русских заголовках и описаниях (круг 13).

Единственный источник фразы — `country_in` / `in_place`. Тест фиксирует правильную
форму для всех стран каталога `world_countries` (55 на стенде 12.10.2026) и
проверяет правило «во» перед в/ф + согласная.
"""

from __future__ import annotations

import re

import pytest

from app.data.eurostat_titles_ru import (
    COUNTRY_PREPOSITIONAL,
    country_in,
    country_prepositional,
    in_place,
    place_preposition,
    public_description,
    public_seo_title,
)

# (slug, name_ru из world_countries, ожидаемая фраза). Эталон набран вручную, а не
# выведен функцией: ошибка в правиле не «подтянет» ожидание вместе с собой.
CATALOG_IN = [
    ("spain", "Испания", "в Испании"),
    ("sweden", "Швеция", "в Швеции"),
    ("germany", "Германия", "в Германии"),
    ("austria", "Австрия", "в Австрии"),
    ("france", "Франция", "во Франции"),
    ("italy", "Италия", "в Италии"),
    ("belgium", "Бельгия", "в Бельгии"),
    ("netherlands", "Нидерланды", "в Нидерландах"),
    ("czechia", "Чехия", "в Чехии"),
    ("finland", "Финляндия", "в Финляндии"),
    ("portugal", "Португалия", "в Португалии"),
    ("denmark", "Дания", "в Дании"),
    ("slovenia", "Словения", "в Словении"),
    ("cyprus", "Кипр", "на Кипре"),
    ("hungary", "Венгрия", "в Венгрии"),
    ("greece", "Греция", "в Греции"),
    ("luxembourg", "Люксембург", "в Люксембурге"),
    ("norway", "Норвегия", "в Норвегии"),
    ("ireland", "Ирландия", "в Ирландии"),
    ("croatia", "Хорватия", "в Хорватии"),
    ("poland", "Польша", "в Польше"),
    ("latvia", "Латвия", "в Латвии"),
    ("lithuania", "Литва", "в Литве"),
    ("romania", "Румыния", "в Румынии"),
    ("slovakia", "Словакия", "в Словакии"),
    ("estonia", "Эстония", "в Эстонии"),
    ("bulgaria", "Болгария", "в Болгарии"),
    ("malta", "Мальта", "на Мальте"),
    ("serbia", "Сербия", "в Сербии"),
    ("switzerland", "Швейцария", "в Швейцарии"),
    ("north-macedonia", "Северная Македония", "в Северной Македонии"),
    ("turkey", "Турция", "в Турции"),
    ("iceland", "Исландия", "в Исландии"),
    ("montenegro", "Черногория", "в Черногории"),
    ("bosnia", "Босния и Герцеговина", "в Боснии и Герцеговине"),
    ("united-states", "США", "в США"),
    ("albania", "Албания", "в Албании"),
    ("moldova", "Молдова", "в Молдове"),
    ("georgia", "Грузия", "в Грузии"),
    ("ukraine", "Украина", "в Украине"),
    ("kosovo", "Косово", "в Косово"),
    ("azerbaijan", "Азербайджан", "в Азербайджане"),
    ("armenia", "Армения", "в Армении"),
    ("united-kingdom", "Великобритания", "в Великобритании"),
    ("canada", "Канада", "в Канаде"),
    ("australia", "Австралия", "в Австралии"),
    ("brazil", "Бразилия", "в Бразилии"),
    ("china", "Китай", "в Китае"),
    ("new-zealand", "Новая Зеландия", "в Новой Зеландии"),
    ("mexico", "Мексика", "в Мексике"),
    ("japan", "Япония", "в Японии"),
    ("india", "Индия", "в Индии"),
    ("south-africa", "ЮАР", "в ЮАР"),
    ("south-korea", "Южная Корея", "в Южной Корее"),
    ("israel", "Израиль", "в Израиле"),
]


@pytest.mark.parametrize("slug,name_ru,expected", CATALOG_IN)
def test_country_in_every_catalog_country(slug, name_ru, expected):
    assert country_in(slug, name_ru) == expected


def test_catalog_list_has_55_countries_and_all_slugs_in_table():
    assert len(CATALOG_IN) == 55
    assert len({s for s, _, _ in CATALOG_IN}) == 55
    # слаг каталога без записи в таблице получил бы эвристику — для каталога нужна таблица
    assert {s for s, _, _ in CATALOG_IN} <= set(COUNTRY_PREPOSITIONAL)


def test_no_catalog_phrase_is_suspicious():
    """Сводка подозрительных: «в» перед в/ф+согласной, «в/во» без пары, именительный падеж."""
    cluster = re.compile(r"^[вфВФ][бвгджзйклмнпрстфхцчшщь]", re.I)
    bad: list[str] = []
    for slug, name_ru, _ in CATALOG_IN:
        phrase = country_in(slug, name_ru)
        prep, _, rest = phrase.partition(" ")
        if prep not in ("в", "во", "на"):
            bad.append(phrase)
        if prep == "в" and cluster.match(rest):
            bad.append(phrase)
        if prep == "во" and not cluster.match(rest):
            bad.append(phrase)
        # именительный падеж в предложной фразе — признак пропущенного склонения
        if rest == name_ru and name_ru not in ("ЮАР", "США", "Косово"):
            bad.append(phrase)
    assert bad == []


@pytest.mark.parametrize(
    "prep_form,expected",
    [
        ("Франции", "во"),
        ("Фландрии", "во"),
        ("Вьетнаме", "во"),
        ("Владивостоке", "во"),
        ("Венгрии", "в"),
        ("Финляндии", "в"),
        ("Вашингтоне", "в"),
        ("Германии", "в"),
        ("Кипре", "на"),
        ("Мальте", "на"),
        ("Республике Корея", "в"),
        ("Новой Зеландии", "в"),
    ],
)
def test_place_preposition_rules(prep_form, expected):
    assert place_preposition(prep_form) == expected
    assert in_place(prep_form) == f"{expected} {prep_form}"


def test_in_place_empty_and_unknown_country_fallback():
    assert in_place("") == ""
    assert in_place("   ") == ""
    # слаг вне таблицы: предложный падеж по названию, предлог по правилу
    assert country_in("vietnam", "Вьетнам") == "во Вьетнаме"
    assert country_in("mexico-x", "Мексика") == "в Мексике"
    assert country_in("rok", "Республика Корея") == "в Республике Корея"
    assert country_in("chile", "Чили") == "в Чили"
    assert country_in("belarus", "Беларусь") == "в Беларуси"
    assert country_prepositional("france", "Франция") == "Франции"


def test_public_title_and_description_use_in_phrase():
    title = public_seo_title(
        "Гармонизированный индекс потребительских цен, помесячно",
        country_prep="Франции",
        country_name_ru="Франция",
    )
    assert title == "Гармонизированный индекс потребительских цен во Франции — график и данные"
    desc = public_description(
        "Гармонизированный индекс потребительских цен, помесячно",
        "monthly",
        "индекс 2015=100",
        country_name_ru="Франция",
        country_prep="Франции",
    )
    assert "во Франции" in desc
    assert " в Франции" not in desc
    cyprus = public_seo_title("Безработица", country_prep="Кипре", country_name_ru="Кипр")
    assert cyprus == "Безработица на Кипре — график и данные"
