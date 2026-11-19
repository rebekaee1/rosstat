"""Зона F ЕМИСС (19.11.2026): пенсии по видам 62164, итоги сева и уборки 34158/34165, платные услуги 57788,
турпоездки 62900.

Фикстуры — живые ответы dataGrid.do с Mac 19.11.2026 тем же запросом, что строят загрузчики, урезанные до России,
Москвы и одного-двух регионов (запросы строили сами ``fetch_dataset`` и ``fetch_year``).
Контрольные значения ниже — из этих ответов; Россия по 34165 за 2025 год совпала с ответом, скачанным 09.11.2026.
"""
import asyncio
import json
from datetime import date
from pathlib import Path

import pytest

from app.data import emiss_quarterly as Q
from app.data import emiss_regional_sets as R
from app.data.i18n.region_indicators_en import REGION_INDICATORS_EN
from app.services import emiss_quarterly_parser as QP
from app.services import emiss_regional_sets_parser as RP
from app.services.emiss_regional_parser import load_dimnames

FIXTURES = Path(__file__).parent / "fixtures" / "emiss_zone_f"
TODAY = date(2026, 11, 19)
DIMNAMES = load_dimnames()


def fixture(dataset, years):
    return json.loads((FIXTURES / f"dataGrid_{dataset}_{years}_2026-11-19.json").read_text(encoding="utf-8"))


def quarterly_points(ds, years):
    oids, dimnames = QP.dataset_territories(ds, [], DIMNAMES)
    return {(c, s, p): v for c, s, p, v in QP.parse_dataset_response(ds, fixture(ds.id, years), dimnames,
                                                                        today=TODAY)}


# --- 62164: пенсии по видам, квартальный слой -------------------------------------------------------------------

def test_pensions_by_kind_quarter_is_the_start_of_quarter_and_current_quarter_is_kept():
    got = quarterly_points(Q.PENSIONS_BY_KIND, "2021-2026")
    # «На 1 октября 2026» — IV квартал 2026: значение на начало квартала уже известно (19.11.2026).
    assert got[("pensiya-po-starosti", "russia", 20264)] == 27322.54
    assert got[("pensiya-po-starosti", "moskva", 20264)] == 28918.14
    assert got[("pensiya-po-starosti-nerabotayuschih", "russia", 20264)] == 27882.08
    assert got[("pensiya-po-invalidnosti", "russia", 20264)] == 17496.05
    assert got[("pensiya-socialnaya", "russia", 20264)] == 16568.24
    # Первый период набора — «на 1 октября 2021».
    assert min(p for (c, s, p) in got if s == "russia") == 20214
    # Межведомственный ОКАТО: Байконур не регион сайта и пропускается; Москва с хвостовым пробелом находится.
    assert {s for (_c, s, _p) in got} == {"russia", "moskva", "belgorodskaya-oblast"}
    assert not any(c == "pensiya-za-vyslugu-let" for (c, _s, _p) in got)


def test_pensions_request_uses_interagency_territories():
    seen = {}

    async def post(ds_id, params):
        seen["params"] = params
        return fixture(62164, "2021-2026")

    asyncio.run(QP.fetch_dataset(Q.PENSIONS_BY_KIND, range(2021, 2027), ["1688487"], DIMNAMES, today=TODAY,
                                 post_grid=post))
    filters = [v for k, v in seen["params"] if k == "selectedFilterIds"]
    assert "30628_978198" in filters  # Россия в межведомственном ОКАТО
    assert not any(f.startswith("57831_") for f in filters)
    assert {f for f in filters if f.startswith("33560_")} == {
        "33560_1540248", "33560_1540238", "33560_1540240", "33560_1540245"}
    assert ("lineObjectIds", "30628") in seen["params"]


# --- 34165/34158: итоги уборки и ярового сева, годовой слой ------------------------------------------------------

def test_harvest_takes_only_the_1_november_value():
    got = quarterly_points(Q.HARVEST, "2023-2027")
    assert got[("urozhay-zerno-1-noyabrya", "russia", 2025)] == 134535.21
    assert got[("urozhay-zerno-1-noyabrya", "voronezhskaya-oblast", 2025)] == 5687.41
    assert got[("urozhay-svekla-1-noyabrya", "voronezhskaya-oblast", 2025)] == 4278.93
    # На 19.11.2026 данных на 1 ноября 2026 ещё нет: промежуточная дата (1 сентября) не подставляется.
    assert not any(p == 2026 for (_c, _s, p) in got)


def test_spring_sowing_takes_1_june_and_drops_source_placeholders():
    got = quarterly_points(Q.SPRING_SOWING, "2023-2027")
    assert got[("yarovoy-sev-vsego-1-iyunya", "russia", 2026)] == 41947.29
    assert got[("yarovoy-sev-vsego-1-iyunya", "voronezhskaya-oblast", 2026)] == 1366.0
    assert got[("yarovoy-sev-kukuruza-1-iyunya", "voronezhskaya-oblast", 2026)] == 143.0
    assert got[("yarovoy-sev-pshenica-1-iyunya", "voronezhskaya-oblast", 2023)] == 97.85
    assert all(v < 100_000 for v in got.values())  # заглушка 1 000 000 на 1 апреля не попадает


def test_registry_codes_are_unique_new_and_translated():
    existing = json.loads((Path(__file__).parents[1] / "app/data/regional/indicators.json").read_text())
    known = {r["code"] for r in existing} | {r["table_code"] for r in existing}
    new = [s for ds in (Q.PENSIONS_BY_KIND, Q.HARVEST, Q.SPRING_SOWING) for s in ds.series]
    new_monthly = [s for rset in (R.SERVICES, R.TOURISM) for s in rset.series]
    codes = [s.code for s in new] + [s.code for s in new_monthly]
    assert len(codes) == len(set(codes)) == 14 + 13
    assert not set(codes) & known and not {s.table_code for s in new} & known
    all_codes = [s.code for _ds, s in Q.all_series()] + [r["code"] for r in R.artifact_rows()]
    assert len(all_codes) == len(set(all_codes))
    for code in codes:
        assert REGION_INDICATORS_EN[code]["name"] and REGION_INDICATORS_EN[code]["unit"]


# --- 57788 и 62900: помесячный слой ------------------------------------------------------------------------------

def monthly_points(rset, year):
    found, rejected = RP.parse_year(rset, fixture(rset.dataset, year), year, DIMNAMES)
    return {(c, s, p): v for c, s, p, v in found}, rejected


def test_paid_services_in_million_roubles_without_float_tails():
    got, rejected = monthly_points(R.SERVICES, 2026)
    assert rejected == 0
    assert got[("platnye-uslugi-mes", "russia", 202609)] == 1891143.2947
    assert got[("platnye-uslugi-mes", "moskva", 202609)] == 468674.1166
    assert got[("platnye-uslugi-medicinskie-mes", "russia", 202609)] == 185237.7229
    assert got[("platnye-uslugi-turagentstva-mes", "russia", 202607)] == 49159.7
    # «январь–сентябрь» и прочие нарастающие периоды не смешиваются с месяцами.
    assert max(p for (_c, _s, p) in got) == 202609 and min(p for (_c, _s, p) in got) == 202601


def test_tourism_year_to_date_with_own_territory_dimension():
    got, _rejected = monthly_points(R.TOURISM, 2025)
    assert got[("turpoezdki-s-nachala-goda", "russia", 202501)] == 6243.0
    assert got[("turpoezdki-s-nachala-goda", "russia", 202512)] == 92042.8
    assert ("turpoezdki-s-nachala-goda", "nenetskiy-ao", 202512) in got  # название без «(Архангельская область)»
    got26, _ = monthly_points(R.TOURISM, 2026)
    assert got26[("turpoezdki-s-nachala-goda", "russia", 202609)] == 74446.4
    params = RP.build_params(R.TOURISM, 2026, ["1688487"])
    filters = [v for k, v in params if k == "selectedFilterIds"]
    assert ("lineObjectIds", "3301") in params and "3301_1678127" in filters
    assert not any(f.startswith("57831_") for f in filters)
    assert "30611_950256" in filters


def test_services_request_keeps_common_okato_extras():
    params = RP.build_params(R.SERVICES, 2026, ["1688489"])
    filters = [v for k, v in params if k == "selectedFilterIds"]
    assert "57831_1688489" in filters and "57831_1688487" in filters  # Россия «старой» строкой
    assert "57939_1758073" in filters and "30611_950352" in filters


@pytest.fixture
def zone_f_client(auth_env):
    """Пенсия по старости (квартал) и урожай зерна (год) в регионе и России: карточка, профиль, карта."""
    from fastapi.testclient import TestClient

    from app.models import Region, RegionDataPoint, RegionIndicator, RegionQuarterlyPoint

    async def seed():
        async with auth_env["session_maker"]() as db:
            rf = Region(slug="russia", name="Российская Федерация", kind="country")
            msk = Region(slug="moskva", name="г. Москва", kind="region")
            bel = Region(slug="belgorodskaya-oblast", name="Белгородская область", kind="region")
            vrn = Region(slug="voronezhskaya-oblast", name="Воронежская область", kind="region")
            inds = {}
            for ds, s in Q.all_series():
                if s.code in ("pensiya-po-starosti", "urozhay-zerno-1-noyabrya"):
                    inds[s.code] = RegionIndicator(code=s.code, name=s.name_ru, unit=ds.unit_ru, note=ds.note_ru,
                                                   section_num=ds.section[0], section_name=ds.section[1],
                                                   table_code=s.table_code, is_listed=True)
            db.add_all([rf, msk, bel, vrn, *inds.values()])
            await db.flush()
            slugs = {"russia": rf, "moskva": msk, "belgorodskaya-oblast": bel, "voronezhskaya-oblast": vrn}
            for (code, slug, period), value in quarterly_points(Q.PENSIONS_BY_KIND, "2021-2026").items():
                if code in inds and slug in slugs:
                    db.add(RegionQuarterlyPoint(indicator_id=inds[code].id, region_id=slugs[slug].id,
                                                quarter=period, value=value))
            for (code, slug, period), value in quarterly_points(Q.HARVEST, "2023-2027").items():
                if code in inds and slug in slugs:
                    db.add(RegionDataPoint(indicator_id=inds[code].id, region_id=slugs[slug].id,
                                           year=period, value=value))
            await db.commit()

    asyncio.run(seed())
    with TestClient(auth_env["app"]) as client:
        yield client


def test_pension_card_and_harvest_card_are_visible(zone_f_client):
    det = zone_f_client.get("/api/v1/regions/moskva/i/pensiya-po-starosti").json()
    assert det["frequency"] == "quarterly"
    assert det["series"][-1] == {"year": 2026, "quarter": 4, "value": 28918.14, "label": "IV кв. 2026"}
    assert det["russia_series"][-1]["value"] == 27322.54

    heat = zone_f_client.get("/api/v1/regions/heatmap/pensiya-po-starosti").json()
    assert heat["quarter"] == 20264
    assert {v["slug"] for v in heat["values"]} == {"moskva", "belgorodskaya-oblast"}

    crop = zone_f_client.get("/api/v1/regions/voronezhskaya-oblast/i/urozhay-zerno-1-noyabrya").json()
    assert [p["year"] for p in crop["series"]] == [2023, 2024, 2025]
    assert crop["series"][-1]["value"] == 5687.41

    prof = zone_f_client.get("/api/v1/regions/voronezhskaya-oblast").json()
    names = {i["code"] for s in prof["sections"] for i in s["indicators"]}
    assert "urozhay-zerno-1-noyabrya" in names


# --- Поиск: запросы людей (боевой, 60 дней до 19.11.2026) и Яндекса («средняя пенсия …») ---------------------

@pytest.fixture
def search_client(auth_env):
    from fastapi.testclient import TestClient

    from app.models import Region, RegionDataPoint, RegionIndicator, RegionMonthlyPoint, RegionQuarterlyPoint

    async def seed():
        async with auth_env["session_maker"]() as db:
            regions = [Region(slug=slug, name=name, kind="region") for slug, name in (
                ("voronezhskaya-oblast", "Воронежская область"), ("omskaya-oblast", "Омская область"),
                ("moskva", "г. Москва"))]
            db.add_all(regions)
            q_inds, a_inds = [], []
            for ds, s in Q.all_series():
                if ds.id not in (62164, 34165, 34158):
                    continue
                ind = RegionIndicator(code=s.code, name=s.name_ru, unit=ds.unit_ru, table_code=s.table_code,
                                      section_num=ds.section[0], section_name=ds.section[1], is_listed=True)
                (q_inds if ds.layer == "quarterly" else a_inds).append(ind)
            m_inds = [RegionIndicator(code=r["code"], name=r["name"], table_code=r["table_code"],
                                      section_num=r["section_num"], section_name=r["section_name"], unit=r["unit"],
                                      is_listed=True)
                      for r in R.artifact_rows() if r["section_num"] in (6, 15)]
            db.add_all((*q_inds, *a_inds, *m_inds))
            await db.flush()
            for region in regions:
                for ind in q_inds:
                    db.add(RegionQuarterlyPoint(indicator_id=ind.id, region_id=region.id, quarter=20264, value=20000))
                for ind in a_inds:
                    db.add(RegionDataPoint(indicator_id=ind.id, region_id=region.id, year=2025, value=500))
                for ind in m_inds:
                    db.add(RegionMonthlyPoint(indicator_id=ind.id, region_id=region.id, month=202609, value=900))
            await db.commit()

    asyncio.run(seed())
    with TestClient(auth_env["app"]) as c:
        yield c


def _codes(client, q):
    response = client.get("/api/v1/search", params={"q": q})
    assert response.status_code == 200, response.text
    return [row.get("code") for row in response.json()["results"]]


@pytest.mark.parametrize(("q", "code"), [
    ("пенсия по старости омская область", "pensiya-po-starosti"),
    ("средняя пенсия по инвалидности", "pensiya-po-invalidnosti"),
    ("пенсия по потере кормильца", "pensiya-po-potere-kormiltsa"),
    ("социальная пенсия", "pensiya-socialnaya"),
    ("объём платных услуг населению", "platnye-uslugi-mes"),
    ("платные медицинские услуги москва", "platnye-uslugi-medicinskie-mes"),
    ("туристические поездки", "turpoezdki-s-nachala-goda"),
    ("сбор картофеля", "urozhay-kartofel-1-noyabrya"),
    ("урожай зерна воронежская область", "urozhay-zerno-1-noyabrya"),
    ("посевные площади кукурузы воронежская область", "yarovoy-sev-kukuruza-1-iyunya"),
])
def test_people_queries_find_new_series(search_client, q, code):
    found = _codes(search_client, q)
    assert code in found[:5], found


def test_monthly_sets_ssr_has_no_consumer_price_phrases(search_client, auth_env):
    """У помесячных наборов (платные услуги, турпоездки и ряды зоны E) нет фраз про потребительские цены."""
    from app.services.locale import reset_locale, set_locale
    from app.services.seo_regional import render_region_indicator_html

    async def render(locale):
        token = set_locale(locale)
        try:
            async with auth_env["session_maker"]() as db:
                return await render_region_indicator_html("moskva", "platnye-uslugi-mes", db)
        finally:
            reset_locale(token)

    status, html = asyncio.run(render("ru"))
    assert status == 200 and "Объём платных услуг населению за месяц" in html
    assert "потребительские цены" not in html and "среднероссийской ценой" not in html
    assert "оперативные данные" in html
    status, html = asyncio.run(render("en"))
    assert status == 200 and "consumer prices" not in html and "preliminary data" in html
