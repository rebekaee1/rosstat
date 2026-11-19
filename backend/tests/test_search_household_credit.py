"""Поиск и страницы рядов кредитов населению и ипотеки ЦБ (19.11.2026).

Запросы — пустые поиски людей из отчёта новых источников 19.11.2026 («задолженность домохозяйств», «закредитованность»,
«сведения о задолженности по кредитам физическим лицам») и показы Google («выдача ипотеки»; «ипотека по годам» пока пуст: «по годам» — фильтр годовых рядов, а ряды ЦБ месячные). Названия, коды
и ключевые слова — из реестра ``app.data.cbr_household_credit`` и ``indicator_seo``.
"""
import asyncio
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.data import cbr_household_credit as spec
from app.data.indicator_seo import INDICATOR_SEO_KEYWORDS


@pytest.fixture
def client(auth_env):
    from app.models import Indicator, IndicatorData, Region, RegionIndicator, RegionMonthlyPoint

    async def seed():
        async with auth_env["session_maker"]() as db:
            national = [
                Indicator(code="consumer-credit", name="Кредиты физическим лицам", name_en="Consumer Credit Outstanding",
                          frequency="monthly", unit="трлн руб.", category="Финансы",
                          seo_keywords=INDICATOR_SEO_KEYWORDS["consumer-credit"]),
                Indicator(code="mortgage-rate", name="Ставка по ипотеке", name_en="Mortgage Interest Rate",
                          frequency="monthly", unit="%", category="Ставки"),
                *(Indicator(code=r["code"], name=r["name"], name_en=r["name_en"], frequency="monthly", unit=r["unit"],
                            category="Финансы", seo_keywords=INDICATOR_SEO_KEYWORDS[r["code"]])
                  for r in spec.seed_indicators()),
            ]
            db.add_all(national)
            rf = Region(slug="russia", name="Российская Федерация", kind="country")
            vrn = Region(slug="voronezhskaya-oblast", name="Воронежская область", kind="region")
            mo = Region(slug="moskovskaya-oblast", name="Московская область", kind="region")
            regional = [RegionIndicator(code=r["code"], name=r["name"], table_code=r["table_code"],
                                        section_num=r["section_num"], section_name=r["section_name"], unit=r["unit"],
                                        note=r["note"], is_listed=True)
                        for r in spec.artifact_rows()]
            db.add_all([rf, vrn, mo, *regional])
            await db.flush()
            for row in national:
                db.add(IndicatorData(indicator_id=row.id, date=date(2026, 9, 1), value=100))
            for region, value in ((rf, 617146.0), (vrn, 7991.0), (mo, 50000.0)):
                for row in regional:
                    for month in (202608, 202609):
                        db.add(RegionMonthlyPoint(indicator_id=row.id, region_id=region.id, month=month,
                                                  value=value if month == 202609 else value / 2))
            await db.commit()

    asyncio.run(seed())
    with TestClient(auth_env["app"]) as c:
        yield c


def results(client, q):
    response = client.get("/api/v1/search", params={"q": q})
    assert response.status_code == 200, response.text
    return response.json()["results"]


def codes(client, q):
    return [row.get("code") for row in results(client, q)]


@pytest.mark.parametrize("q, code", [
    ("задолженность домохозяйств", "consumer-credit"),
    ("закредитованность", "consumer-credit"),
    ("просроченная задолженность по кредитам", "consumer-credit-overdue"),
    ("выдача ипотеки", "mortgage-issued"),
    ("задолженность по ипотеке", "mortgage-debt"),
    ("просрочка по ипотеке", "mortgage-overdue"),
    ("срок ипотеки", "mortgage-term"),
    ("количество ипотек", "mortgage-issued-count"),
])
def test_empty_searches_now_find_the_series(client, q, code):
    found = codes(client, q)
    assert code in found[:3], (q, found)


def test_mortgage_rate_query_still_leads_to_the_rate(client):
    assert codes(client, "ставка по ипотеке")[0] == "mortgage-rate"


def test_region_and_mortgage_find_the_regional_series(client):
    rows = results(client, "ипотека воронежская область")
    assert rows, rows
    regional = [r for r in rows if r.get("region_slug") == "voronezhskaya-oblast"]
    assert regional and regional[0]["code"].startswith("ipoteka-"), rows


def test_region_page_lists_monthly_credit_series(client):
    prof = client.get("/api/v1/regions/voronezhskaya-oblast").json()
    items = {i["code"]: i for s in prof["sections"] for i in s["indicators"]}
    assert items["ipoteka-vydano-mes"]["value"] == 7991.0 and items["ipoteka-vydano-mes"]["month"] == 202609

    mon = client.get("/api/v1/regions/voronezhskaya-oblast/i/ipoteka-vydano-mes/monthly").json()
    assert mon["frequency"] == "monthly" and mon["series"][-1]["value"] == 7991.0
    assert mon["russia_series"][-1]["value"] == 617146.0
    assert mon["indicator"]["macro_code"] == "mortgage-issued"
    # Соседи — сначала ряды ЦБ.
    assert all(s["code"] in spec.SERIES_BY_REGIONAL for s in mon["siblings"][:7])

    heat = client.get("/api/v1/regions/heatmap/ipoteka-vydano-mes").json()
    assert heat["month"] == 202609
    assert {v["slug"]: v["raw"] for v in heat["values"]} == {"voronezhskaya-oblast": 7991.0,
                                                             "moskovskaya-oblast": 50000.0}
