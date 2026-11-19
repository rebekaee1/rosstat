"""Квартальный слой регионов (19.11.2026): разбор ответа ЕМИСС, API карточки, профиля, карты и SSR.

Строки ответа — из живого dataGrid.do 19.11.2026 (запрос с Mac): ключ ячейки ``dim<oid квартала>_d…_i…``,
год — в ``dim3``. Россия 2026: вторичный рынок, все типы квартир, III квартал — 149 231,93 ₽/м²;
прожиточный минимум 2027 года (плановый) в ответе есть и должен отрезаться.
"""

import asyncio
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.data.emiss_quarterly import (
    CITY_PRICES, HOUSING_PRICES, LIVING_MINIMUM, RUSSIA_LEGACY, RUSSIA_WITHOUT_NEW, all_series,
)
from app.models import Region, RegionIndicator, RegionQuarterlyPoint
from app.services.emiss_quarterly_parser import (
    EmissQuarterlyFormatError, current_quarter, parse_dataset_response, plan_years,
)
from app.services.locale import reset_locale, set_locale
from app.services.regional_quarterly import quarter_label

TODAY = date(2026, 11, 19)
DIMNAMES = {"Белгородская область": "belgorodskaya-oblast", "Архангельская область": "arhangelskaya-oblast"}


def _price_row(territory, market, flat, year, cells):
    row = {"dim57831": territory, "dim63148": market, "dim58849": flat, "dim3": str(year)}
    row.update({f"dim{oid}_d115140584_i{5133 + i}": v for i, (oid, v) in enumerate(cells)})
    return row


def test_housing_prices_russia_rows_and_future_quarter_cut():
    payload = {"results": [
        _price_row(RUSSIA_WITHOUT_NEW, "Вторичный рынок жилья", "Все типы квартир", 2026,
                   [("1540222", "143953,4"), ("1540224", "146469,57"), ("1540226", "149231,93")]),
        _price_row(RUSSIA_LEGACY, "Вторичный рынок жилья", "Все типы квартир", 2026, [("1540226", "150000")]),
        _price_row(RUSSIA_LEGACY, "Вторичный рынок жилья", "Все типы квартир", 2022, [("1540227", "105000,5")]),
        _price_row("Белгородская область", "Первичный рынок жилья", "Элитные квартиры", 2026,
                   [("1540226", "-"), ("1540227", "99999")]),  # IV квартал 2026 ещё не наступил
        _price_row("Неизвестная территория", "Вторичный рынок жилья", "Все типы квартир", 2026,
                   [("1540226", "1")]),
    ]}
    points = parse_dataset_response(HOUSING_PRICES, payload, DIMNAMES, today=TODAY)
    assert sorted(points) == [
        ("cena-m2-zhilya-vtorichnyy", "russia", 20224, 105000.5),
        ("cena-m2-zhilya-vtorichnyy", "russia", 20261, 143953.4),
        ("cena-m2-zhilya-vtorichnyy", "russia", 20262, 146469.57),
        ("cena-m2-zhilya-vtorichnyy", "russia", 20263, 149231.93),
    ]


def test_city_alias_is_lower_priority_than_own_subject_row():
    archangelsk = "Архангельская область (кроме Ненецкого автономного округа)"
    payload = {"results": [
        {"dim57831": archangelsk, "dim63148": "Вторичный рынок жилья", "dim3": "2026", "dim1540226_d1_i1": "90000"},
        {"dim57831": "Белгородская область", "dim63148": "Первичный рынок жилья", "dim3": "2026",
         "dim1540226_d1_i2": "112964,54"},
    ]}
    points = parse_dataset_response(CITY_PRICES, payload, DIMNAMES, today=TODAY)
    assert sorted(points) == [
        ("cena-m2-zhilya-centr-pervichnyy", "belgorodskaya-oblast", 20263, 112964.54),
        ("cena-m2-zhilya-centr-vtorichnyy", "arhangelskaya-oblast", 20263, 90000.0),
    ]


def test_living_minimum_annual_cuts_planned_year_and_continues_yearbook_from_2025():
    payload = {"results": [
        {"dim57831": RUSSIA_LEGACY, "dim58812": "Все население", "dim3": str(y), f"dim1558883_d46231625_i{y}": v}
        for y, v in ((2024, "15453"), (2025, "17733"), (2026, "18939"), (2027, "19500"))
    ] + [{"dim57831": RUSSIA_LEGACY, "dim58812": "Пенсионеры", "dim3": "2024", "dim1558883_d1_i1": "13290"}]}
    points = parse_dataset_response(LIVING_MINIMUM, payload, DIMNAMES, today=TODAY)
    assert sorted(points) == [
        ("prozhitochnyy-minimum-pensionery", "russia", 2024, 13290.0),
        ("velichina-prozhitochnogo-minimuma-ustanovlennaya-v-tselom-po-3-11", "russia", 2025, 17733.0),
        ("velichina-prozhitochnogo-minimuma-ustanovlennaya-v-tselom-po-3-11", "russia", 2026, 18939.0),
    ]


def test_rows_without_any_value_mean_format_change():
    payload = {"results": [{"dim57831": "Белгородская область", "dim63148": "x", "dim58849": "y", "dim3": "2026"}]}
    with pytest.raises(EmissQuarterlyFormatError):
        parse_dataset_response(HOUSING_PRICES, payload, DIMNAMES, today=TODAY)


def test_plan_full_history_then_tail_and_quarter_helpers():
    full = plan_years(HOUSING_PRICES, None, TODAY)
    assert full[0][0] == 2000 and full[-1][-1] == 2026 and sum(len(r) for r in full) == 27
    assert plan_years(HOUSING_PRICES, 2026, TODAY) == [range(2025, 2027)]
    assert plan_years(LIVING_MINIMUM, 2026, TODAY) == [range(2025, 2028)]
    assert current_quarter(TODAY) == 20264
    assert quarter_label(20263, "ru") == "III кв. 2026" and quarter_label(20263, "en") == "Q3 2026"
    codes = [s.code for _ds, s in all_series()]
    assert len(codes) == len(set(codes)) and all(len(c) <= 120 for c in codes)


@pytest.fixture
def quarterly_client(auth_env):
    async def seed():
        async with auth_env["session_maker"]() as db:
            rf = Region(slug="russia", name="Российская Федерация", kind="country")
            msk = Region(slug="moskva", name="г. Москва", kind="region")
            bel = Region(slug="belgorodskaya-oblast", name="Белгородская область", kind="region")
            ind = RegionIndicator(
                code="cena-m2-zhilya-vtorichnyy", name="Цена 1 м² жилья, вторичный рынок", unit="рублей за м²",
                section_num=20, section_name="Цены и тарифы", table_code="20.q2", is_listed=True,
            )
            db.add_all([rf, msk, bel, ind])
            await db.flush()
            for reg, base in ((rf, 140000.0), (msk, 480000.0), (bel, 100000.0)):
                for quarter, bump in ((20253, 0), (20262, 3000), (20263, 6000)):
                    db.add(RegionQuarterlyPoint(region_id=reg.id, indicator_id=ind.id, quarter=quarter,
                                                value=base + bump))
            await db.commit()

    asyncio.run(seed())
    with TestClient(auth_env["app"]) as client:
        yield client


def test_quarterly_detail_profile_and_heatmap(quarterly_client):
    det = quarterly_client.get("/api/v1/regions/belgorodskaya-oblast/i/cena-m2-zhilya-vtorichnyy").json()
    assert det["frequency"] == "quarterly"
    assert det["series"][-1] == {"year": 2026, "quarter": 3, "value": 106000.0, "label": "III кв. 2026"}
    assert [p["quarter"] for p in det["russia_series"]] == [3, 2, 3]
    assert det["rank"]["position"] == 2 and det["rank"]["total"] == 2
    assert det["rank"]["period_label"] == "III кв. 2026"

    prof = quarterly_client.get("/api/v1/regions/belgorodskaya-oblast").json()
    item = prof["sections"][0]["indicators"][0]
    assert item["quarter"] == 20263 and item["prev_quarter"] == 20262
    assert item["period_label"] == "III кв. 2026" and item["value"] == 106000.0

    heat = quarterly_client.get("/api/v1/regions/heatmap/cena-m2-zhilya-vtorichnyy").json()
    assert heat["quarter"] == 20263 and heat["period_label"] == "III кв. 2026"
    assert {v["slug"]: (v["raw"], v["prev"]) for v in heat["values"]} == {
        "moskva": (486000.0, 480000.0), "belgorodskaya-oblast": (106000.0, 100000.0),
    }


def test_quarterly_ssr_card_ru_and_en(quarterly_client, auth_env):
    from app.services.seo_regional import render_region_indicator_html

    async def render(locale):
        token = set_locale(locale)
        try:
            async with auth_env["session_maker"]() as db:
                return await render_region_indicator_html("belgorodskaya-oblast", "cena-m2-zhilya-vtorichnyy", db)
        finally:
            reset_locale(token)

    status, html = asyncio.run(render("ru"))
    assert status == 200
    assert "106 000 рублей за м² в III кв. 2026" in html
    assert "За год (к III кв. 2025) — рост на 6%" in html
    assert "По России в целом — 146 000 рублей за м²" in html
    status, html = asyncio.run(render("en"))
    assert status == 200 and "Q3 2026" in html and "Over the year" in html


def test_quarterly_pair_is_found_by_search_live_and_via_index(quarterly_client, auth_env):
    from sqlalchemy import select

    from app.services import search_index
    from app.services.locale import set_locale
    from app.services.search import federated_search

    maker = auth_env["session_maker"]

    async def run():
        set_locale("ru")
        query = "цена квадратного метра Белгородская область"
        async with maker() as db:
            live = await federated_search(db, query, limit=20)
        await search_index.refresh(force=True, session_maker=maker, release_after=0)
        search_index.reset_cache()
        async with maker() as db:
            indexed = await federated_search(db, query, limit=20)
            facts = (await db.execute(select((await search_index.active_index(db)).region_facts))).all()
        search_index.reset_cache()
        return live, indexed, facts

    live, indexed, facts = asyncio.run(run())
    keys = [r["key"] for r in live["results"]]
    assert "region:belgorodskaya-oblast:cena-m2-zhilya-vtorichnyy" in keys
    assert [r["key"] for r in indexed["results"]] == keys
    assert (2026, 106000.0) in {(f.last_year, float(f.last_year_value)) for f in facts if f.has_annual}
