"""Провалы поиска из гипотез Пульса, перепроверенные 19.11.2026 на копии боевого каталога.

Каждый запрос ниже на копии каталога боевого (19.11.2026, поисковый индекс включён) давал пустую или неверную
выдачу при существующих рядах. Названия и коды повторяют настоящий каталог. Чинится механизм, а не запрос:
словоформы (именительный множественного), целое слово названия региона, начало названия региона после пустой
выдачи, понятия словаря (ЭАН, евро/доллар, фертильность, рынок недвижимости, регистрируемая безработица),
недописанное слово, «по регионам», год без данных.

SQLite не сворачивает регистр кириллицы, поэтому мировые названия записаны строчными буквами.
"""
import asyncio
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.services.search_intent import nominal_variants, prefix_concept
from app.services.search_region_hint import region_prefix_keys

WEAR = "stepen-iznosa-osnovnyh-fondov"
SOWN = "posevnye-ploschadi-selskohozyaystvennyh-kultur"
BROADBAND = "chislennost-aktivnyh-abonentov-fiksirovannogo-i-mobilnogo-shirokopolosnogo"
FARM = "produktsiya-selskogo-hozyaystva"
TFR = "summarnyy-koeffitsient-rozhdaemosti"
REG_UNEMPLOYMENT = "uroven-bezrabotitsy-uroven-zaregistrirovannoy-bezrabotitsy"
UNEMPLOYMENT = "uroven-bezrabotitsy"
HOUSING_INDEX = "indeksy-tsen-na-pervichnom-rynke-zhilya"

REGIONS = (
    ("respublika-saha", "Республика Саха (Якутия)"), ("sahalinskaya-oblast", "Сахалинская область"),
    ("penzenskaya-oblast", "Пензенская область"), ("permskiy-kray", "Пермский край"),
    ("voronezhskaya-oblast", "Воронежская область"), ("respublika-mariy-el", "Республика Марий Эл"),
)


@pytest.fixture
def client(auth_env):
    from app.models import (Indicator, IndicatorData, Region, RegionDataPoint, RegionIndicator, WorldCountry,
                            WorldDataPoint, WorldIndicator)

    async def seed():
        async with auth_env["session_maker"]() as db:
            germany = WorldCountry(code="DE", slug="germany", name_ru="Германия", name_en="Germany")
            db.add(germany)
            await db.flush()
            gasoil = WorldIndicator(country_id=germany.id, code="de-nrg_ti_oil-total-o4640-ths-t",
                name_ru="импорт нефти и нефтепродуктов, тыс. тонн, газойль / дизель",
                name_en="imports of oil and petroleum products, thousand tonnes, gas oil / diesel",
                dataset_id="nrg_ti_oil", slice_hash="de-nrg_ti_oil-total-o4640-ths-t", unit="THS_T",
                frequency="annual", is_listed=True, category_ru="Энергетика")
            db.add(gasoil)
            national = [
                Indicator(code="fuel-diesel", name="Цена дизельного топлива", name_en="Diesel fuel price",
                          frequency="weekly", unit="руб./л"),
                Indicator(code="fuel-diesel-avg-month", name="Дизельное топливо — средняя за месяц",
                          name_en="Diesel fuel — monthly average", frequency="monthly", unit="руб./л", is_listed=False),
                Indicator(code="labor-force", name="Рабочая сила", name_en="Labor Force", frequency="monthly",
                          seo_keywords="рабочая сила, экономически активное население, рынок труда России"),
                Indicator(code="population", name="Численность населения", name_en="Population", frequency="annual"),
                Indicator(code="eur-usd", name="Курс евро к доллару", name_en="EUR/USD", frequency="daily"),
                Indicator(code="eur-rub", name="Курс евро", name_en="EUR/RUB", frequency="daily"),
                Indicator(code="usd-rub", name="Курс доллара", name_en="USD/RUB", frequency="daily"),
                Indicator(code="registered-unemployment-share", name="Доля зарегистрированных безработных",
                          name_en="Registered unemployment share", frequency="monthly"),
                Indicator(code="unemployment", name="Уровень безработицы", name_en="Unemployment rate",
                          frequency="monthly"),
                Indicator(code="housing-price-primary", name="Цены на первичное жильё",
                          name_en="Primary housing prices", frequency="quarterly"),
            ]
            db.add_all(national)
            regions = {slug: Region(slug=slug, name=name, kind="region") for slug, name in REGIONS}
            db.add_all(regions.values())

            def definition(code, name, table, unit):
                return RegionIndicator(code=code, name=name, table_code=table, section_num=1, section_name="Раздел",
                                       unit=unit)

            annual = [
                definition(WEAR, "Степень износа основных фондов", "9.1", "процент"),
                definition(SOWN, "Посевные площади сельскохозяйственных культур", "12.1", "тыс. га"),
                definition(BROADBAND, "Численность активных абонентов фиксированного и мобильного широкополосного "
                           "доступа к сети Интернет", "17.9", "единиц на 100 человек населения"),
                definition(FARM, "Продукция сельского хозяйства", "12.2", "млн рублей"),
                definition(TFR, "Суммарный коэффициент рождаемости", "2.4", "число детей"),
                definition(REG_UNEMPLOYMENT, "Уровень безработицы — уровень зарегистрированной безработицы", "3.5",
                           "процент"),
                definition(UNEMPLOYMENT, "Уровень безработицы", "3.4", "процент"),
                definition(HOUSING_INDEX, "Индексы цен на первичном рынке жилья", "20.7", "процент"),
            ]
            db.add_all(annual)
            await db.flush()
            db.add(WorldDataPoint(indicator_id=gasoil.id, date=date(2024, 1, 1), value=12))
            for row in national:
                db.add(IndicatorData(indicator_id=row.id, date=date(2024, 5, 1), value=100))
            for region in regions.values():
                for row in annual:
                    for year in (2000, 2024):
                        db.add(RegionDataPoint(indicator_id=row.id, region_id=region.id, year=year, value=50))
            await db.commit()

    asyncio.run(seed())
    # Словарь каталога для переписи живёт в памяти процесса шесть часов: здесь — каталог этого набора.
    from app.services import search_rewrite
    search_rewrite._vocabulary = None
    with TestClient(auth_env["app"]) as tc:
        yield tc


def get(client, q, **kwargs):
    response = client.get("/api/v1/search", params=dict(q=q, **kwargs))
    assert response.status_code == 200, response.text
    return response.json()


def codes(body):
    return [row.get("code") for row in body["results"]]


# ── Механизмы без базы ────────────────────────────────────────────────────────────────────────────

def test_nominative_plural_also_reads_genitive_plural():
    """«абоненты» ищет и «абонентов», «пользователи» — «пользователей», «строительные» — «строительных»."""
    assert "абонентов" in nominal_variants("абоненты")
    assert "пользователей" in nominal_variants("пользователи")
    assert "строительных" in nominal_variants("строительные")
    # Прежние формы на месте.
    assert nominal_variants("абонентов")[:2] == ("абонентов", "абоненты")


def test_whole_region_word_beats_prefix_of_another_region():
    """«саха» — слово названия Республики Саха (Якутия); с него же начинается «Сахалинская», но это начало."""
    geometry = [{"key": f"region:russia:{slug}", "kind": "region", "slug": slug, "name_ru": name, "name_en": ""}
                for slug, name in REGIONS]
    saha, sakhalin = "region:russia:respublika-saha", "region:russia:sahalinskaya-oblast"
    # Второе чтение (whole_word): целое слово сильнее начала.
    assert region_prefix_keys("саха", geometry, goods=False, minimum=3, whole_word=True) == frozenset({saha})
    # Первое чтение как раньше: без товара начало короче пяти букв не регион, с товаром — оба субъекта.
    assert region_prefix_keys("саха", geometry, goods=False) == frozenset()
    assert region_prefix_keys("саха", geometry, goods=True) == frozenset({saha, sakhalin})
    # Начало в три буквы — только когда его просит вызывающая сторона и субъект один.
    assert region_prefix_keys("пен", geometry, goods=False) == frozenset()
    assert region_prefix_keys("пен", geometry, goods=False, minimum=3) == frozenset({"region:russia:penzenskaya-oblast"})
    assert region_prefix_keys("пе", geometry, goods=False, minimum=3) == frozenset()


def test_prefix_concept_completes_only_unambiguous_unfinished_word():
    assert prefix_concept("дизе")[0] == "fuel-diesel"
    assert prefix_concept("курс") is None      # целое слово словаря, а не начало
    assert prefix_concept("диз") is None       # короче четырёх букв
    assert prefix_concept("строймате") is None


# ── Регион в запросе ──────────────────────────────────────────────────────────────────────────────

def test_short_region_name_word_with_indicator(client):
    """«степень износа, % саха» (Пульс 18.11: пусто) — Республика Саха (Якутия), а не сахар и не Сахалин."""
    body = get(client, "степень износа, % саха")
    assert body["results"], body
    assert {(row["code"], row.get("region_slug")) for row in body["results"]} == {(WEAR, "respublika-saha")}


def test_two_region_like_words_stay_unresolved():
    """Два слова, каждое похоже на начало субъекта, — не регион: «ростов износа пен» — ни Ростовская, ни Пензенская."""
    from app.services.search_intent import parse_intent, region_reading
    geometry = [{"key": f"region:russia:{slug}", "kind": "region", "slug": slug, "name_ru": name, "name_en": "",
                 "country_slug": "russia"} for slug, name in (*REGIONS, ("rostovskaya-oblast", "Ростовская область"))]
    intent = parse_intent("ростов износа пен", geometry)
    assert region_reading("ростов износа пен", intent, geometry) is None


def test_three_letter_region_prefix_after_empty_reading(client):
    """«степень износа, % пен» (гипотеза 384): обрезок названия ведёт к единственному субъекту."""
    body = get(client, "степень износа, % пен")
    assert body["results"] and body["results"][0]["region_slug"] == "penzenskaya-oblast", body


# ── Понятия словаря ───────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("q", ["эан", "экономически активное население"])
def test_economically_active_population_is_labour_force(client, q):
    found = codes(get(client, q))
    assert found and found[0] == "labor-force", found
    assert "population" not in found


@pytest.mark.parametrize("q", ["евро доллар", "евро к доллару", "eur/usd"])
def test_euro_dollar_pair(client, q):
    found = codes(get(client, q))
    assert found and found[0] == "eur-usd", found
    assert "eur-rub" not in found and "usd-rub" not in found


def test_misspelt_fertility_coefficient_with_region(client):
    """«коэффицент фертильности республика марий эл» (гипотеза 120) — суммарный коэффициент рождаемости региона."""
    body = get(client, "коэффицент фертильности республика марий эл")
    assert body["results"] and body["results"][0]["code"] == TFR, body
    assert body["results"][0]["region_slug"] == "respublika-mariy-el"


def test_real_estate_market_is_housing_market(client):
    """«рынок недвижимости» (гипотеза 224) — цены на жильё, а не пусто."""
    found = codes(get(client, "рынок недвижимости"))
    assert "housing-price-primary" in found and HOUSING_INDEX in found, found


@pytest.mark.parametrize("q", ["регистрируемая безработица", "безработица регистрируемая (россия)",
                               "зарегистрированная безработица"])
def test_registered_unemployment_national_and_regional(client, q):
    """Гипотеза 389: ряд России «Доля зарегистрированных безработных» первым, региональный — в выдаче."""
    found = codes(get(client, q))
    assert found and found[0] == "registered-unemployment-share", found
    assert REG_UNEMPLOYMENT in found
    assert "unemployment" not in found and UNEMPLOYMENT not in found


def test_gross_agricultural_output(client):
    """«валовая продукция сельского хозяйства» (гипотеза 285): так у Росстата называется «Продукция сельского хозяйства»."""
    body = get(client, "валовая продукция сельского хозяйства")
    assert codes(body) and codes(body)[0] == FARM, body
    assert body.get("corrected_query") == "продукция сельского хозяйства"


# ── Словоформы ────────────────────────────────────────────────────────────────────────────────────

def test_plural_subscribers_find_genitive_title(client):
    """«абоненты широкополосного доступа» (гипотеза 124): в названии ряда «абонентов»."""
    assert BROADBAND in codes(get(client, "абоненты широкополосного доступа"))


# ── Порядок выдачи ────────────────────────────────────────────────────────────────────────────────

def test_unfinished_word_puts_national_series_first(client):
    """«дизе» (гипотеза 320): цена дизеля России выше мирового ряда «газойль / дизель»; мировой ряд остаётся."""
    found = codes(get(client, "дизе"))
    assert found[0] == "fuel-diesel", found
    assert "de-nrg_ti_oil-total-o4640-ths-t" in found


def test_by_regions_puts_regional_series_first(client):
    """«безработица по регионам» (гипотеза 148): региональный ряд первым, национальный остаётся в выдаче."""
    found = codes(get(client, "безработица по регионам"))
    assert found[0] == UNEMPLOYMENT, found
    assert "unemployment" in found
    # Без «по регионам» порядок прежний: национальный ряд первым.
    assert codes(get(client, "безработица"))[0] == "unemployment"


# ── Год без данных ────────────────────────────────────────────────────────────────────────────────

def test_year_without_points_offers_series_without_year(client):
    """«… в 1980 году» (гипотеза 379): ряды с 2000 года. Основная выдача пуста, в «Ближайшем» — ряды без года."""
    body = get(client, "посевные площади воронежская область в 1980 году")
    assert body["results"] == [] and body["reason"] == "no_coverage"
    nearest = body.get("nearest")
    assert nearest and nearest["note"] == "without_word" and nearest["words"] == ["1980"], body
    assert nearest["results"][0]["code"] == SOWN and nearest["results"][0]["region_slug"] == "voronezhskaya-oblast"
    # Год с данными по-прежнему находит страницу года.
    row = get(client, "посевные площади воронежская область в 2000 году")["results"][0]
    assert row["path"] == f"/russia/region/voronezhskaya-oblast/{SOWN}/2000"
