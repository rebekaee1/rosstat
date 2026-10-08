"""Круг 08.10.2026, волна 2, зона F: лира и тенге, поиск, главные цифры страны, календарь."""
from __future__ import annotations

import asyncio
import re
from datetime import date, timedelta

import pytest

from app.data.global_market_indicators import (
    GLOBAL_MARKET_INDICATOR_BASES,
    is_global_market_indicator,
    market_indicator_codes_for_country,
)
from app.data.indicator_seo import INDICATOR_SEO, INDICATOR_SEO_BLOCKS, INDICATOR_SEO_KEYWORDS
from app.data.i18n.indicator_copy_en import INDICATOR_COPY_EN
from app.data.view_model_families import FAMILY_BY_BASE
from app.data.world_indicator_titles_ru import public_indicator_name, title_override_for_code
from app.services import site_paths
from app.services.cbr_fx_parser import CURRENCY_MAP, parse_fx_xml
from app.services.search_intent import parse_intent
from seed_data import INDICATORS
from tests.test_search_federated import GEOMETRY

NEW_PAIRS = {"try-rub": "R01700J", "kzt-rub": "R01335"}
GEO = GEOMETRY + [dict(key="country:turkey", kind="country", slug="turkey", name_ru="Турция",
                       name_en="Turkey", country_slug="turkey", country_code="TR")]


# ---------------------------------------------------------------- курсы ЦБ: лира, тенге

def test_cbr_codes_are_the_official_ones():
    # Коды сверены с XML_valFull.asp Банка России 2026-10-08; из памяти не вставлять.
    for code, cbr_id in NEW_PAIRS.items():
        assert CURRENCY_MAP[code] == cbr_id
    assert CURRENCY_MAP["usd-rub"] == "R01235"


def test_nominal_ten_and_hundred_are_divided_into_rubles_per_unit():
    xml = """<?xml version="1.0" encoding="windows-1251"?>
<ValCurs ID="R01700J"><Record Date="09.10.2026" Id="R01700J"><Nominal>10</Nominal><Value>17,3777</Value></Record></ValCurs>"""
    assert parse_fx_xml(xml) == [(date(2026, 10, 9), 1.7378)]
    xml = xml.replace("R01700J", "R01335").replace(">10<", ">100<").replace("17,3777", "19,1030")
    assert parse_fx_xml(xml) == [(date(2026, 10, 9), 0.191)]


@pytest.mark.parametrize("code", sorted(NEW_PAIRS))
def test_new_pair_is_wired_everywhere(code):
    row = next(i for i in INDICATORS if i["code"] == code)
    assert row["parser_type"] == "cbr_fx_xml"
    assert row["frequency"] == "daily" and row["category"] == "Валюты" and row["unit"] == "руб."
    assert row["model_config_json"]["forecast_steps"] == 0
    assert "backfill_from" in row["model_config_json"]
    assert code in FAMILY_BY_BASE
    assert site_paths.is_currency_indicator(code)
    assert site_paths.is_currency_indicator(code + "-avg-month")
    assert site_paths.russia_indicator(code) == f"/currencies/indicator/{code}"
    # Российский официальный курс не становится мировым рыночным рядом.
    assert not is_global_market_indicator(code)
    assert code in INDICATOR_SEO and code in INDICATOR_SEO_KEYWORDS
    assert INDICATOR_COPY_EN[code]["name"].endswith("exchange rate")
    assert row["name_en"].endswith("Exchange Rate")


@pytest.mark.parametrize("code", sorted(NEW_PAIRS))
def test_new_pair_seo_blocks_are_public_language(code):
    forbidden = re.compile(r"R01\d{3}|XML_dynamic|currency_base|cbr\.ru/|bulk_upsert|parser|ADR-\d", re.I)
    blocks = INDICATOR_SEO_BLOCKS[code]
    assert len(blocks) == 8
    for block in blocks:
        assert len(block["body"]) > 80
        assert not forbidden.search(block["body"] + block["title"]), block["title"]
    row = next(i for i in INDICATORS if i["code"] == code)
    assert not forbidden.search(row["methodology"]) and "xml" not in row["methodology"].lower()
    # Прогноза на карточке нет, и текст этого не обещает.
    assert not any("прогнозная линия" in b["body"].lower() and "нет" not in b["body"].lower() for b in blocks)


def test_turkey_gets_the_lira_rate_on_its_page_but_germany_does_not():
    assert market_indicator_codes_for_country("turkey") == ("try-rub",)
    assert market_indicator_codes_for_country("germany") == ()
    # Пара не входит в реестр мировых рядов: в крошках остаётся «Россия».
    assert "try-rub" not in GLOBAL_MARKET_INDICATOR_BASES


# ---------------------------------------------------------------- поиск: слова и раскладка

@pytest.mark.parametrize("query,code", [
    ("лира", "try-rub"), ("курс лиры", "try-rub"), ("Курс турецкой лиры к рублю", "try-rub"),
    ("turkish lira", "try-rub"), ("тенге", "kzt-rub"), ("курс тенге", "kzt-rub"), ("tenge", "kzt-rub"),
])
def test_lira_and_tenge_are_known_words(query, code):
    intent = parse_intent(query, GEO)
    assert [group[0] for group in intent.terms] == [code], intent.terms
    assert intent.corrected is None


def test_lira_with_turkey_keeps_the_country():
    intent = parse_intent("лира Турция", GEO)
    assert intent.countries == frozenset(("turkey",))
    assert [group[0] for group in intent.terms] == ["try-rub"]


def test_layout_flip_needs_every_word_recognised():
    # «геккон штадфешщт» — «Turkey inflation» в чужой раскладке со случайной буквой: раньше
    # принималось из-за одного понятного слова и выводило «Ищем также: utrrjy inflation».
    garbage = parse_intent("геккон штадфешщт", GEO)
    assert garbage.corrected is None
    # Полностью распознанный запрос, как и раньше, исправляется.
    assert parse_intent("byakzwbz", GEO).corrected == "инфляция"
    assert parse_intent("ddg", GEO).corrected == "ввп"
    flipped = parse_intent("Егклун штадфешщт", GEO)
    assert flipped.corrected == "turkey inflation" and flipped.countries == frozenset(("turkey",))
    # Остаток из неизвестных слов после переворота — не исправление.
    assert parse_intent("Ебкун штадфешщт", GEO).corrected is None


# ---------------------------------------------------------------- названия рядов страны

def test_two_interest_rate_series_and_imf_inflation_get_distinct_names():
    day = public_indicator_name("Процентные ставки, %", "tr-ei_mfir_m-mf-ddi-rt-nap-nsa")
    three = public_indicator_name("Процентные ставки, %", "tr-ei_mfir_m-mf-3mi-rt-nap-nsa")
    assert day != three and "один день" in day and "три месяца" in three
    imf = public_indicator_name("Изменение потребительских цен за год", "tr-weo-pcpipch")
    assert imf == "Инфляция в среднем за год, оценка МВФ"
    # Остальные ряды не затронуты.
    assert title_override_for_code("tr-prc_hicp_minr-total-i15") is None
    assert public_indicator_name("Уровень безработицы", "tr-une_rt_m-x") == "Уровень безработицы"


# ---------------------------------------------------------------- главные цифры страны

def _seed_turkey(db_factory):
    from app.models import WorldCountry, WorldDataPoint, WorldIndicator

    async def run():
        async with db_factory() as db:
            tr = WorldCountry(code="TR", slug="turkey", name_ru="Турция", name_en="Turkey")
            db.add(tr)
            await db.flush()

            def row(code, dataset, unit, slice_json, provider="eurostat", freq="monthly", name="Ряд"):
                return WorldIndicator(
                    country_id=tr.id, code=code, provider=provider, dataset_id=dataset, slice_hash=code,
                    slice_json=slice_json, name_ru=name, name_en=name, unit=unit, frequency=freq,
                    is_listed=True, category_ru="Прочее", points_count=14,
                )

            rows = [
                row("tr-weo-ngdpd", "weo", "BN_USD", {"weo_code": "NGDPD"}, "imf", "annual", "ВВП в текущих ценах"),
                row("tr-nama_10_gdp-b1gq-clv15-meur", "nama_10_gdp", "CLV15_MEUR", {"na_item": "B1GQ"}, "eurostat", "annual", "ВВП в постоянных ценах"),
                row("tr-prc_hicp_midx-cp00-i15", "prc_hicp_midx", "I15", {"coicop": "CP00"}, "eurostat", "monthly", "ГИПЦ"),
                row("tr-une_rt_m-total-sa-t-pc-act", "une_rt_m", "PC_ACT", {"age": "TOTAL", "sex": "T", "s_adj": "SA"}, "eurostat", "monthly", "Безработица"),
                row("tr-demo_pjan-total-t-nr", "demo_pjan", "NR", {"age": "TOTAL", "sex": "T"}, "eurostat", "annual", "Население"),
            ]
            db.add_all(rows)
            await db.flush()
            for r in rows:
                if r.frequency == "monthly":
                    for index in range(14):
                        month = index % 12 + 1
                        year = 2025 + index // 12
                        db.add(WorldDataPoint(indicator_id=r.id, date=date(year, month, 1), value=100 + index))
                else:
                    for year in (2023, 2024, 2025):
                        db.add(WorldDataPoint(indicator_id=r.id, date=date(year, 1, 1), value=1000 + year))
            await db.commit()
            return tr, rows

    return asyncio.run(run())


def test_country_overview_order_and_price_basis(auth_env):
    from app.api.world import build_country_overview

    factory = auth_env["session_maker"]
    tr, rows = _seed_turkey(factory)

    async def run():
        async with factory() as db:
            return await build_country_overview(db, tr, rows)

    overview = asyncio.run(run())
    slugs = [item["concept_slug"] for item in overview]
    # Цены, ВВП в долларах, безработица, население — первые четыре; евро-ВВП после них.
    assert slugs[:4] == ["hicp-index", "gdp-usd", "unemployment-rate", "population"], slugs
    assert slugs.index("gdp-volume-annual") > 3
    prices = overview[0]
    assert prices["basis"] == "year_on_year_month"
    assert prices["basis_label"] == "к тому же месяцу прошлого года"
    assert "same month" in prices["basis_label_en"]
    assert "basis" not in overview[1]


def test_imf_inflation_chip_says_annual_average():
    from types import SimpleNamespace

    from app.api.world import _price_chip_basis

    imf = SimpleNamespace(provider="imf", frequency="annual")
    assert _price_chip_basis("hicp-index", imf)["basis"] == "annual_average"
    assert _price_chip_basis("hicp-index", imf)["basis_label"].endswith("оценка МВФ")
    monthly = SimpleNamespace(provider="eurostat", frequency="monthly")
    assert _price_chip_basis("hicp-index", monthly)["basis"] == "year_on_year_month"
    assert _price_chip_basis("hicp-index", SimpleNamespace(provider="eurostat", frequency="annual")) is None
    assert _price_chip_basis("population", monthly) is None


# ---------------------------------------------------------------- выдача: страна первой, лира, инфляция

@pytest.fixture
def circle_client(auth_env):
    from fastapi.testclient import TestClient

    from app.models import Indicator, IndicatorData, WorldCountry, WorldDataPoint, WorldIndicator

    factory = auth_env["session_maker"]
    tr, headline = _seed_turkey(factory)

    async def more():
        async with factory() as db:
            junk = [
                WorldIndicator(
                    country_id=tr.id, code=f"tr-bop-{index:03d}", provider="eurostat", dataset_id=f"bop{index}",
                    slice_hash=f"junk{index}", slice_json={}, name_ru="Число родившихся", name_en="Births",
                    unit="NR", frequency="annual", is_listed=True, category_ru="Население", points_count=3,
                )
                for index in range(130)
            ]
            db.add_all(junk)
            await db.flush()
            for row in junk:
                db.add(WorldDataPoint(indicator_id=row.id, date=date(2024, 1, 1), value=5))
            rubles = [
                Indicator(code="try-rub", name="Курс турецкой лиры", name_en="TRY/RUB Exchange Rate", unit="руб.", frequency="daily", is_listed=True),
                Indicator(code="try-rub-avg-month", name="Курс турецкой лиры — среднее за месяц", frequency="monthly", is_listed=False),
                Indicator(code="kzt-rub", name="Курс тенге", name_en="KZT/RUB Exchange Rate", unit="руб.", frequency="daily", is_listed=True),
                Indicator(code="cpi", name="Индекс потребительских цен на товары и услуги", unit="%", frequency="monthly", is_listed=True),
                Indicator(code="cpi-yoy", name="Индекс потребительских цен — год к году", unit="%", frequency="monthly", is_listed=False),
            ]
            db.add_all(rubles)
            await db.flush()
            for row in rubles:
                db.add(IndicatorData(indicator_id=row.id, date=date(2026, 8, 1), value=1.74 if "try" in row.code else 6.3))
            await db.commit()

    asyncio.run(more())
    with TestClient(auth_env["app"]) as client:
        yield client


def _search(client, q, **headers):
    response = client.get("/api/v1/search", params={"q": q, "limit": 50}, headers=headers or None)
    assert response.status_code == 200, response.text
    return response.json()


def test_country_only_query_puts_the_country_then_its_main_series_first(circle_client):
    body = _search(circle_client, "Turkey")
    codes = [row.get("code") or row["kind"] for row in body["results"]]
    assert body["results"][0]["kind"] == "country" and body["results"][0]["path"] == "/turkey"
    head = set(codes[1:7])
    # Четыре главных ряда и курс лиры выше сотни рядов «в порядке кода».
    assert {"tr-weo-ngdpd", "tr-prc_hicp_midx-cp00-i15", "tr-une_rt_m-total-sa-t-pc-act", "tr-demo_pjan-total-t-nr", "try-rub"} <= head, codes[:10]
    assert not any(code.startswith("tr-bop-") for code in codes[:6])
    # Скрытые режимы лиры в запрос «только страна» не попадают.
    assert "try-rub-avg-month" not in codes
    lira = next(row for row in body["results"] if row.get("code") == "try-rub")
    assert lira["country_name"] == "Турция" and lira["path"] == "/currencies/indicator/try-rub"


def test_lira_and_tenge_queries_find_the_rate(circle_client):
    first = _search(circle_client, "лира")["results"][0]
    assert first["code"] == "try-rub" and first["path"] == "/currencies/indicator/try-rub"
    assert _search(circle_client, "курс тенге")["results"][0]["code"] == "kzt-rub"
    assert _search(circle_client, "lira", **{"X-FE-Locale": "en"})["results"][0]["code"] == "try-rub"


def test_inflation_word_prefers_the_annual_series_over_the_index(circle_client):
    inflation = [row["code"] for row in _search(circle_client, "инфляция")["results"] if row["kind"] == "russia"]
    assert inflation[0] == "cpi-yoy", inflation
    cpi_word = [row["code"] for row in _search(circle_client, "ипц")["results"] if row["kind"] == "russia"]
    assert cpi_word[0] == "cpi", cpi_word


def test_search_enriches_the_first_twenty_four_rows(circle_client):
    rows = _search(circle_client, "Turkey")["results"][:24]
    series = [row for row in rows if row["kind"] in ("world", "russia")]
    assert len(series) >= 20
    assert all("latest" in row for row in series), [row["code"] for row in series if "latest" not in row]
    # Дальше двадцать четвёртой строки значение не считается (два ограниченных запроса).
    later = [row for row in _search(circle_client, "Turkey")["results"][24:] if row["kind"] in ("world", "russia")]
    assert later and all("latest" not in row for row in later)


# ---------------------------------------------------------------- календарь: ближайшее по показателю

def test_upcoming_filter_by_indicator_and_type(auth_env, auth_client):
    from datetime import datetime

    from app.models import EconomicEvent, Indicator
    from app.services.display import today_msk

    async def seed():
        async with auth_env["session_maker"]() as db:
            key = Indicator(code="key-rate", name="Ключевая ставка", unit="%", frequency="daily")
            cpi = Indicator(code="cpi", name="ИПЦ", unit="%", frequency="monthly")
            db.add_all([key, cpi])
            await db.flush()

            def event(indicator, days, kind, key_):
                return EconomicEvent(
                    title="Событие", event_type=kind, source="cbr", scheduled_date=today_msk() + timedelta(days=days),
                    status="scheduled", date_confidence="official_explicit", is_estimated=False,
                    source_url="https://www.cbr.ru/statistics/indcalendar/", event_key=key_, source_hash="a" * 64,
                    last_seen_at=datetime(2026, 9, 10), importance=3, indicator_id=indicator.id,
                )

            db.add_all([
                event(cpi, 1, "data_release", "cpi-1"),
                event(key, 2, "report", "key-report"),
                event(key, 5, "rate_decision", "key-decision"),
                event(key, 40, "rate_decision", "key-decision-2"),
            ])
            await db.commit()

    asyncio.run(seed())
    everything = auth_client.get("/api/v1/calendar/upcoming").json()["events"]
    assert {e["event_key"] for e in everything} == {"cpi-1", "key-report", "key-decision", "key-decision-2"}
    key_only = auth_client.get("/api/v1/calendar/upcoming", params={"indicator_code": "key-rate"}).json()["events"]
    assert {e["event_key"] for e in key_only} == {"key-report", "key-decision", "key-decision-2"}
    nxt = auth_client.get("/api/v1/calendar/upcoming", params={
        "indicator_code": "key-rate", "event_type": "rate_decision", "limit": 1}).json()["events"]
    assert [e["event_key"] for e in nxt] == ["key-decision"]
    assert auth_client.get("/api/v1/calendar/upcoming", params={"indicator_code": "Bad Code!"}).status_code == 422
