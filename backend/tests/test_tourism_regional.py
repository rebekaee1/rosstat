"""Туризм по регионам (20.11.2026, зона t2): реестр, разбор сырья, ЕМИСС по названиям, снимок, SSR.

Фрагменты сырья — из файлов, скачанных 20.11.2026 (``.artifacts/tourism-2026-11-20``): ЕМИСС 62301 (ночёвки КСР
нарастающим итогом, Россия 2023: январь 16 924 942, январь–февраль 34 424 930), ЦБ ``imp_services_reg_26``
(«Поездки» России I кв. 2026 — 9 702,96 млн долл.), ФНС 1-НМ (Петербург то «г. Санкт-Петербург», то
«г.Санкт-Петербург»), Turpotok_2kv-2026 (Белгородская область 2025: январь–март 153 427, январь–июнь 671 545).
"""

import asyncio
import io
import json
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.data import tourism_regional as R
from app.services import tourism_regional_loader as L

TODAY = date(2026, 11, 20)


@pytest.fixture(scope="module")
def terr():
    return L.Territories()


# --- реестр -----------------------------------------------------------------------------------------------------


def test_registry_codes_tables_and_copy():
    codes = [s.code for s in R.SERIES]
    assert len(codes) == len(set(codes)) and all(len(c) <= 120 for c in codes)
    own = [s for s in R.SERIES if s.own_metadata]
    assert all(s.code.startswith("tour-") or s.code in R.RENAMED.values() for s in own)
    assert all(R.SERIES_BY_CODE[c].section[0] != 6 for c in R.RENAMED.values())
    tables = [s.table_code for s in own]
    assert len(tables) == len(set(tables)) and all(len(t) <= 20 for t in tables)
    assert all(s.name_ru and s.name_en and s.unit_ru and s.unit_en and s.note_ru and s.note_en for s in own)
    assert all(s.source in R.SOURCES for s in R.SERIES)
    # Квартальные карточки ищут соседей по «<раздел>.q%».
    assert all(s.table_code.split(".")[1].startswith("q") for s in own if s.layer == "quarterly")
    from app.data.i18n.region_indicators_en import REGION_INDICATORS_EN

    assert all(REGION_INDICATORS_EN[s.code]["name"] == s.name_en for s in own)


def test_extended_series_exist_in_yearbook_and_new_codes_do_not():
    rows = json.loads((L._DATA / "indicators.json").read_text(encoding="utf-8"))
    yearbook = {r["code"]: r["table_code"] for r in rows}
    for s in R.SERIES:
        if s.own_metadata:
            assert s.code not in yearbook
            assert s.table_code not in yearbook.values()
        else:
            assert yearbook[s.code] == s.table_code and s.min_year == 2025


# --- территории ---------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(("name", "slug", "spare"), [
    ("г.Санкт-Петербург", "sankt-peterburg", False),
    ("г. Санкт-Петербург", "sankt-peterburg", False),
    ("Централный федеральный округ", "cfo", False),
    ("город Москва ", "moskva", False),
    ("14   Белгородская область", "belgorodskaya-oblast", False),
    ("ЦЕНТРАЛЬНЫЙ ФЕДЕРАЛЬНЫЙ ОКРУГ", "cfo", False),
    ("Архангельская область (кроме Ненецкого автономного округа)", "arhangelskaya-oblast-bez-ao", False),
    ("Республика Марий-Эл", "respublika-mariy-el", False),
    ("Чувашская Республика - Чувашия", "chuvashskaya-respublika", False),
    ("Краснодарский край (с учетом ФТ «Сириус»)", "krasnodarskiy-kray", True),
    ("Российская Федерация без учета новых субъектов (с 01.01.2023)", "russia", False),
    ("ВСЕГО", "russia", False),
    ("Крымский федеральный округ", None, False),
    ("Не распределено по субъектам Российской Федерации3", None, False),
])
def test_territory_names(terr, name, slug, spare):
    assert terr.resolve(name) == (slug, spare)


def test_russia_row_priority_by_year():
    without_new = "Российская Федерация без учета новых субъектов (с 01.01.2023)"
    assert L.russia_rank(without_new, 2024) == 0 and L.russia_rank("Российская Федерация", 2024) == 1
    assert L.russia_rank("Российская Федерация", 2020) == 0 and L.russia_rank(without_new, 2020) == 1


# --- ЕМИСС: таблица и сетка ----------------------------------------------------------------------------------------

_CSV_62301 = """s_OKATO;EI;PERIOD;TIME;VALUE
Российская Федерация без учета новых субъектов (с 01.01.2023);единица;январь;2023;16924942
Российская Федерация без учета новых субъектов (с 01.01.2023);единица;январь-февраль;2023;34424930
Российская Федерация;единица;январь-февраль;2023;99
Краснодарский край;единица;январь;2023;2167307
Краснодарский край;единица;январь-март;2023;7481758
Белгородская область;единица;январь;2024;500
Белгородская область;единица;январь-февраль;2024;400
"""


def test_ytd_becomes_monthly_and_gaps_are_not_invented(terr):
    s = R.SERIES_BY_CODE["tour-ksr-nochevki-mes"]
    pts = {(slug, p): v for _c, slug, p, v in L.emiss_points([s], L.rows_from_csv(_CSV_62301), terr, today=TODAY)}
    assert pts[("russia", 202301)] == 16924.942
    assert pts[("russia", 202302)] == 17499.988  # строка «без учета новых» главнее с 2023 года
    assert pts[("krasnodarskiy-kray", 202301)] == 2167.307
    assert ("krasnodarskiy-kray", 202303) not in pts  # нет февраля — март не выдумывается
    assert ("belgorodskaya-oblast", 202402) not in pts  # отрицательная разность — оценка уточнилась
    assert pts[("belgorodskaya-oblast", 202401)] == 0.5


_CSV_31615 = """s_OKATO;s_uslug;EI;PERIOD;TIME;VALUE
Российская Федерация;Всего;единица;значение показателя за год;2022;12000
Российская Федерация без учета новых субъектов (с 01.01.2023);Всего;единица;значение показателя за год;2025;17535
Российская Федерация без учета новых субъектов (с 01.01.2023);Туроператорская;единица;значение показателя за год;2025;1200
Российская Федерация без учета новых субъектов (с 01.01.2023);Туроператорская;единица;январь-март;2025;5
"""


def test_yearbook_extension_starts_2025_and_kinds_are_separate(terr):
    total = R.SERIES_BY_CODE["turistskie-firmy-chislo-turistskih-firm"]
    ops = R.SERIES_BY_CODE["tour-turfirmy-turoperatory"]
    pts = L.emiss_points([total, ops], L.rows_from_csv(_CSV_31615), terr, today=TODAY)
    assert sorted(pts) == [("tour-turfirmy-turoperatory", "russia", 2025, 1200.0),
                           ("turistskie-firmy-chislo-turistskih-firm", "russia", 2025, 17535.0)]


def test_alternatives_and_total_like_leftovers():
    assert L._matches(("Всего", "туристские"), ["туристские", "Всего"])
    assert not L._matches(("Всего", "туристские"), ["туристские", "Заграничное (международное)"])
    assert L._matches(("Всего", "Всего"), ["Всего", "Всего"])
    assert not L._matches(("Всего", "Всего"), ["Всего", "туристские"])
    assert L._matches(("re:^санаторий", "re:^к соответствующему"),
                      ["Санаторий, день", "К соответствующему периоду предыдущего года"])


def _page(dataset: int, unit: str) -> str:
    return (
        "var x = {title: '\\u041d\\u0430\\u0431\\u043e\\u0440', unit: '" + unit + "', filters: {"
        f"0: {{title: 'Показатель', values: {{{dataset}: {{title: 'Ночёвки', order: 1}}}}}},"
        "3: {title: 'Год', values: {2025: {title: '2025'}, 2026: {title: '2026'}}},"
        "30611: {title: 'Единица измерения', values: {950458: {title: 'единица'}}},"
        "33560: {title: 'Период', values: {1540283: {title: 'январь'}, 1540294: {title: 'январь-февраль'},"
        " 1540222: {title: 'I квартал'}}},"
        "57831: {title: 'Классификатор объектов административно-территориального деления (ОКАТО)', values: {"
        " 1688487: {title: 'Российская Федерация'}, 1690000: {title: 'Краснодарский край'}}},"
        "}, left_columns: [57831], top_columns: [3, 33560]};"
    )


def test_live_emiss_resolves_oids_by_names(terr):
    s = R.SERIES_BY_CODE["tour-ksr-nochevki-mes"]
    sent = {}

    async def fetch_page(dataset):
        return _page(dataset, "единица")

    async def post_grid(dataset, params):
        sent["params"] = params
        return {"results": [{"dim57831": "Краснодарский край", "dim3": "2026",
                             "dim1540283_d1_i1": "1 000", "dim1540294_d1_i2": "2500,5"}]}

    pts = asyncio.run(L.fetch_emiss_dataset(62301, [s], [2026], terr, today=TODAY,
                                            fetch_page=fetch_page, post_grid=post_grid))
    assert pts == [("tour-ksr-nochevki-mes", "krasnodarskiy-kray", 202601, 1.0),
                   ("tour-ksr-nochevki-mes", "krasnodarskiy-kray", 202602, 1.5005)]
    selected = [v for k, v in sent["params"] if k == "selectedFilterIds"]
    assert "33560_1540283" in selected and "33560_1540294" in selected and "33560_1540222" not in selected
    assert "57831_1690000" in selected and "3_2026" in selected and "30611_950458" in selected


def test_live_emiss_refuses_other_unit(terr):
    s = R.SERIES_BY_CODE["tour-ksr-nochevki-mes"]

    async def fetch_page(dataset):
        return _page(dataset, "тысяча единиц")

    with pytest.raises(ValueError, match="масштаб"):
        asyncio.run(L.fetch_emiss_dataset(62301, [s], [2026], terr, today=TODAY, fetch_page=fetch_page,
                                          post_grid=lambda *a: None))


def test_grid_with_years_in_columns(terr):
    """Так скачаны речные пассажиры 62999: период — в строке, годы — в столбцах."""
    payload = {"results": [
        {"dim57663": "Всего", "dim57662": "туристские", "dim30611": "человек", "dim33560": "январь-май",
         "dim50387": "Российская Федерация", "dim2025_d1_i1": "55537"},
        {"dim57663": "Всего", "dim57662": "туристские", "dim30611": "человек", "dim33560": "январь-июнь",
         "dim50387": "Российская Федерация", "dim2025_d1_i1": "144327"},
        {"dim57663": "Всего", "dim57662": "туристские", "dim30611": "человек", "dim33560": "январь-апрель",
         "dim50387": "Российская Федерация", "dim2025_d1_i1": "0"},
    ]}
    rows = L.rows_from_grid(payload, territory_dim="50387", period_titles={})
    s = R.SERIES_BY_CODE["tour-rechnye-passazhiry-turisticheskie"]
    pts = {p: v for _c, _s, p, v in L.emiss_points([s], rows, terr, today=TODAY)}
    assert pts == {202505: 55.537, 202506: 88.79}


# --- не ЕМИСС ------------------------------------------------------------------------------------------------------


def _xlsx(rows) -> bytes:
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_cbr_travel_block_quarters_only(terr):
    content = _xlsx([
        ["Импорт отдельных видов услуг по субъектам Российской Федерации"], ["за 2026 год"], [],
        [None, "Импорт услуг, всего", None, None, "Поездки", None, None, None, None, None, "Прочие"],
        [None, None, None, None, "всего", None, None, "в том числе"],
        [None, None, None, None, None, None, None, "деловые", None, None],
        [None, "I квартал 2026 г.", "II квартал 2026 г.", "Январь - июнь 2026 г.",
         "I квартал 2026 г.", "II квартал 2026 г.", "Январь - июнь 2026 г.",
         "I квартал 2026 г.", "II квартал 2026 г.", "Январь - июнь 2026 г.", "I квартал 2026 г."],
        ["ВСЕГО", 20125.95, 25080.56, 45206.51, 9702.96, 13283.58, 22986.54, 325.22, 396.94, 722.15, 1],
        ["14   Белгородская область", 47.15, 64.02, 111.18, 37.83, 55.86, 93.69, 1.37, 1.6, 2.97, 1],
        ["Не распределено по субъектам Российской Федерации3", 1, 1, 2, 1, 1, 2, 1, 1, 2, 1],
    ])
    pts = {(c, s, p): v for c, s, p, v in L.cbr_points(content, "imp", terr)}
    assert pts[("tour-cbr-poezdki-import", "russia", 20261)] == 9702.96
    assert pts[("tour-cbr-poezdki-import", "belgorodskaya-oblast", 20262)] == 55.86
    assert pts[("tour-cbr-poezdki-import-delovye", "russia", 20262)] == 396.94
    assert len(pts) == 8


def test_cbr_all_zero_series_is_dropped():
    pts = [("x", "a", 20251, 0.0), ("x", "a", 20252, 0.0), ("x", "b", 20251, 0.0), ("x", "b", 20252, 0.3)]
    assert L.drop_zero_series(pts) == pts[2:]


def test_turpotok_annual_and_quarter_diff(terr):
    annual = _xlsx([["К содержанию"], ["Оценка туристского потока (годовые данные)*"], [], [None, "единица"],
                    [None, "2025**"], [None, "значение показателя за год"],
                    ["Российская Федерация", 170035535], ["Белгородская область", 964373]])
    import openpyxl

    wb = openpyxl.load_workbook(io.BytesIO(annual))
    wb.active.title = "1.1.2025"
    q = wb.create_sheet("2.1.2025")
    for r in ([None, "2025**"], [None, "январь-март", "январь-июнь", "январь-сентябрь", "январь-декабрь"],
              ["Белгородская область", 153427, 671545, 816072, 884991]):
        q.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    pts = {(c, s, p): v for c, s, p, v in L.turpotok_points(buf.getvalue(), terr)}
    assert pts[("tour-turpotok-poezdki", "russia", 2025)] == 170035.535
    assert pts[("tour-turpotok-poezdki-kv", "belgorodskaya-oblast", 20252)] == 518.118
    assert pts[("tour-turpotok-poezdki-kv", "belgorodskaya-oblast", 20254)] == 68.919


def test_fns_tax_names_glued_and_year_from_december(terr):
    rows = [(202511, "г. Санкт-Петербург", 892919.0), (202512, "г.Санкт-Петербург", 902067.0),
            (202512, "РОССИЙСКАЯ ФЕДЕРАЦИЯ", 5635253.0), (202601, "г. Москва", 0.0)]
    pts = {(c, s, p): v for c, s, p, v in L.fns_tax_points(rows, terr)}
    assert pts[("tour-nalog-s-nachala-goda", "sankt-peterburg", 202512)] == 902.067
    assert pts[("tour-nalog-za-god", "sankt-peterburg", 2025)] == 902.067
    assert pts[("tour-nalog-za-god", "russia", 2025)] == 5635.253
    assert pts[("tour-nalog-s-nachala-goda", "moskva", 202601)] == 0.0  # налога нет — честный ноль


def test_fsa_registry_snapshot_and_new_entries(terr):
    recs = [{"region": "Свердловская область", "status": "Действует", "registerRecordDate": "2024-03-01"},
            {"region": "Свердловская область", "status": "Прекращен", "registerRecordDate": "2025-01-01"},
            {"region": "Краснодарский край", "status": "Действует", "registerRecordDate": "2026-04-13"}]
    pts = {(c, s, p): v for c, s, p, v in L.fsa_points(recs, terr, today=TODAY)}
    assert pts[("tour-reestr-ksr", "sverdlovskaya-oblast", 202611)] == 1
    assert pts[("tour-reestr-ksr", "russia", 202611)] == 2
    assert pts[("tour-reestr-ksr-novye", "russia", 2025)] == 1
    assert ("tour-reestr-ksr-novye", "krasnodarskiy-kray", 2026) not in pts  # неполный год не пишется


def test_turagents_by_inn_region():
    pts = {(s, v) for _c, s, _p, v in L.turagent_points(["7707083893", "245728800316", "x", "9999999999"], 202611)}
    assert pts == {("moskva", 1), ("krasnoyarskiy-kray", 1), ("russia", 2)}


def test_sber_month_is_moscow_month(terr):
    text = ("indicator_id;kpi_id;period;value;obs_status;source;ref_area;freq;unit_measure;unit_mult\n"
            "x;1;2018-12-31T21:00:00.000Z;13;A;С;Орловская область;Месяц;% г/г;0\n"
            "x;1;2022-03-31T21:00:00.000Z;-4,5;A;С;Орловская область;Месяц;% г/г;0\n")
    assert L.sber_points(text, terr) == [
        ("tour-sber-vnutrennie-turisty", "orlovskaya-oblast", 201901, 13.0),
        ("tour-sber-vnutrennie-turisty", "orlovskaya-oblast", 202204, -4.5),
    ]


# --- снимок -------------------------------------------------------------------------------------------------------


def test_seed_matches_sources_and_registry():
    pts = {(c, s, p): v for c, s, p, v in L.read_seed()}
    regions = {r["slug"] for r in json.loads((L._DATA / "regions.json").read_text(encoding="utf-8"))}
    assert {c for c, _s, _p in pts} <= set(R.SERIES_BY_CODE) | set(R.price_tourism_codes().values())
    assert {s for _c, s, _p in pts} <= regions
    assert pts[("tour-ksr-nochevki", "russia", 2024)] == 383490.447
    assert pts[("kollektivnye-sredstva-razmescheniya-chislennost-razmeschennyh-lits", "russia", 2025)] == 92042.736
    assert ("kollektivnye-sredstva-razmescheniya-chislennost-razmeschennyh-lits", "russia", 2024) not in pts
    assert pts[("tour-turpotok-poezdki", "russia", 2025)] == 170035.535
    assert pts[("tour-cbr-poezdki-import", "russia", 20261)] == 9702.96
    assert pts[("tour-nalog-za-god", "russia", 2025)] == 5635.253
    # Наборы, не скачанные до бана fedstat, в снимке пусты — их догрузит живой прогон.
    # Сборник «Туризм в России» 2024 закрыл часть не скачанных наборов (санатории, номера высшей категории).
    pending = {s.code for s in R.SERIES if s.emiss is not None and not s.emiss.seed}
    from_book = {"tour-sanatorii-chislo", "tour-sanatorii-mesta", "tour-gostinicy-nomera-vysshey-kategorii"}
    assert pending & {c for c, _s, _p in pts} == from_book
    assert pts[("tour-gostinicy-nomera-vysshey-kategorii", "russia", 2023)] == 61018
    assert pts[("tour-kurortnyy-sbor", "sankt-peterburg", 2024)] == 747.068857
    assert ("tour-kurortnyy-sbor", "russia", 2025) not in pts
    assert pts[("tour-ksr-zagruzka-mest", "russia", 2024)] == 33.0
    assert pts[("ceni-sanatoriy", "russia", 202609)] == 6131.68


def test_plan_years_full_then_tail():
    annual = [R.SERIES_BY_CODE["tour-sanatorii-chislo"]]
    assert L.plan_years(annual, None, TODAY)[0][0] == 2002
    assert L.plan_years(annual, 2025, TODAY) == [[2024, 2025, 2026]]
    monthly = [R.SERIES_BY_CODE["tour-ksr-razmeshcheno-mes"]]
    assert L.plan_years(monthly, None, TODAY) == [[2023], [2024], [2025], [2026]]


# --- SSR ----------------------------------------------------------------------------------------------------------


@pytest.fixture
def tour_client(auth_env):
    from app.models import Region, RegionDataPoint, RegionIndicator, RegionMonthlyPoint, RegionQuarterlyPoint

    def ind(code):
        s = R.SERIES_BY_CODE[code]
        return RegionIndicator(code=s.code, name=s.name_ru, unit=s.unit_ru, note=s.note_ru, section_num=s.section[0],
                               section_name=s.section[1], table_code=s.table_code, is_listed=True,
                               source_note=R.source_note(s))

    async def seed():
        async with auth_env["session_maker"]() as db:
            rf = Region(slug="russia", name="Российская Федерация", kind="country")
            bel = Region(slug="belgorodskaya-oblast", name="Белгородская область", kind="region")
            q, a, m = ind("tour-cbr-poezdki-import"), ind("tour-nalog-za-god"), ind("tour-ksr-nochevki-mes")
            db.add_all([rf, bel, q, a, m])
            await db.flush()
            for reg, base in ((rf, 9000.0), (bel, 40.0)):
                for quarter, bump in ((20252, 0), (20261, 1), (20262, 2)):
                    db.add(RegionQuarterlyPoint(region_id=reg.id, indicator_id=q.id, quarter=quarter, value=base + bump))
                db.add(RegionDataPoint(region_id=reg.id, indicator_id=a.id, year=2025, value=base))
                for month in (202606, 202607):
                    db.add(RegionMonthlyPoint(region_id=reg.id, indicator_id=m.id, month=month, value=base + month % 10))
            await db.commit()

    asyncio.run(seed())
    with TestClient(auth_env["app"]) as client:
        yield client


def _render(auth_env, code, locale="ru"):
    from app.services.locale import reset_locale, set_locale
    from app.services.seo_regional import render_region_indicator_html

    async def run():
        token = set_locale(locale)
        try:
            async with auth_env["session_maker"]() as db:
                return await render_region_indicator_html("belgorodskaya-oblast", code, db)
        finally:
            reset_locale(token)

    return asyncio.run(run())


def test_ssr_names_real_source_not_yearbook(tour_client, auth_env):
    status, html = _render(auth_env, "tour-cbr-poezdki-import")
    assert status == 200 and "Банк России" in html and "Источник — Росстат" not in html
    status, html = _render(auth_env, "tour-cbr-poezdki-import", "en")
    assert status == 200 and "Bank of Russia" in html
    status, html = _render(auth_env, "tour-nalog-za-god")
    assert status == 200 and "ФНС России" in html and "Регионы России. Социально" not in html
    status, html = _render(auth_env, "tour-ksr-nochevki-mes")
    assert status == 200 and "Росстат (ЕМИСС)" in html
    status, html = _render(auth_env, "tour-ksr-nochevki-mes", "en")
    assert status == 200 and "Nights in hotels" in html


def test_api_detail_frequency(tour_client):
    det = tour_client.get("/api/v1/regions/belgorodskaya-oblast/i/tour-cbr-poezdki-import").json()
    assert det["frequency"] == "quarterly" and det["series"][-1]["value"] == 42.0
    det = tour_client.get("/api/v1/regions/belgorodskaya-oblast/i/tour-ksr-nochevki-mes/monthly").json()
    assert det["frequency"] == "monthly"


# --- доработка 20.11.2026: страны, реестр туроператоров, живые ФНС/Росстат, другие единицы ---------------------


def test_destinations_and_origins_are_series():
    dest = [s for s in R.SERIES if s.code.startswith("tour-turisty-turfirm-")]
    assert len(dest) == 39  # всего, по России, за рубеж + 36 стран
    assert R.SERIES_BY_CODE["tour-turisty-turfirm-greciya"].emiss.match == (("ГРЕЦИЯ",),)
    assert R.SERIES_BY_CODE["tour-inostrancy-turfirm-kitay"].emiss.dataset == 31598


def test_touroperators_by_ogrn_region():
    pts = {(s, v) for _c, s, _p, v in L.touroperator_points(["1230200045613", "1267700105364", "bad"], 202611)}
    assert pts == {("respublika-bashkortostan", 1), ("moskva", 1), ("russia", 2)}


def test_fns_archive_month():
    assert L.fns_zip_month("1nm010926reg.zip") == 202608
    assert L.fns_zip_month("1nm010126reg.zip") == 202512
    assert L.fns_zip_month("1nm01112025reg.zip") == 202510
    assert L.fns_zip_month("1nm01022025m_reg.zip") == 202501


def test_fns_archive_parsed_like_snapshot(terr):
    from pathlib import Path

    zpath = Path("/Users/iprofi/tradingeconomics/rosstat/.artifacts/tourism-2026-11-20/a5/raw/fns/1nm_reg/1nm010926reg.zip")
    if not zpath.exists():
        pytest.skip("архив 1-НМ 20.11.2026 есть только на Mac владельца")
    rows = L.fns_zip_rows(zpath.read_bytes(), 202608)
    pts = {(c, s, p): v for c, s, p, v in L.fns_tax_points(rows, terr)}
    seed = {(c, s, p): v for c, s, p, v in L.read_seed()}
    key = ("tour-nalog-s-nachala-goda", "russia", 202608)
    assert pts[key] == seed[key]


def test_other_page_unit_rescales(terr):
    s = R.SERIES_BY_CODE["obshchepit-oborot-mes"]

    async def fetch_page(dataset):
        return _page(dataset, "миллион рублей").replace("1540294: {title: 'январь-февраль'},", "")

    async def post_grid(dataset, params):
        return {"results": [{"dim57831": "Краснодарский край", "dim3": "2026", "dim1540283_d1_i1": "1500,5"}]}

    pts = asyncio.run(L.fetch_emiss_dataset(31258, [s], [2026], terr, today=TODAY,
                                            fetch_page=fetch_page, post_grid=post_grid))
    assert pts == [("obshchepit-oborot-mes", "krasnodarskiy-kray", 202601, 1500.5)]


def test_turpotok_link_on_rosstat_page():
    html = '<a href="/storage/mediabank/Turpotok_3kv-2026.xlsx">Оценка турпотока</a>'
    assert L._TURPOTOK_LINK.findall(html) == ["/storage/mediabank/Turpotok_3kv-2026.xlsx"]


# --- сборщик c4: курортный сбор, сборники, цены, расчёт загрузки -------------------------------------------------


def test_kurort_fee_rubles_to_millions_and_closed_2024(terr):
    text = ("год;регион;доход;исполнено_руб_конс_бюджет_субъекта\n"
            "2024;г. Санкт-Петербург;курортный сбор (эксперимент 2018–2024), КБК 1 15 08000 02;747068857.0\n"
            "2025;Краснодарский край;курортный сбор (эксперимент 2018–2024), КБК 1 15 08000 02;130489157\n"
            "2025;Краснодарский край;туристический налог;1\n")
    assert L.kurort_points(text, terr) == [("tour-kurortnyy-sbor", "sankt-peterburg", 2024, 747.068857)]


def test_tochno_alternatives_subsections_and_no_data(terr):
    rows = [
        {"indicator_name": "Число санаториев", "subsection": "Санатории", "object_name": "Российская Федерация",
         "year": "2024", "indicator_value": "1324.0"},
        {"indicator_name": "Число санаториев", "subsection": "Из них санатории для детей",
         "object_name": "Российская Федерация", "year": "2024", "indicator_value": "505.0"},
        {"indicator_name": "Объем платных услуг гостиниц и аналогичных средств размещения", "subsection": "CD",
         "object_name": "Алтайский край", "year": "2022", "indicator_value": "100"},
        {"indicator_name": "Объем платных услуг гостиниц и аналогичных услуг по предоставлению временного жилья",
         "subsection": "CD", "object_name": "Алтайский край", "year": "2022", "indicator_value": "101"},
        {"indicator_name": "Число организаций отдыха", "subsection": "CD", "object_name": "Алтайский край",
         "year": "2021", "indicator_value": "-77777777.0"},
    ]
    assert sorted(L.tochno_points(rows, terr)) == [
        ("tour-platnye-uslugi-gostinicy", "altayskiy-kray", 2022, 101.0),
        ("tour-sanatorii-detskie", "russia", 2024, 505.0),
        ("tour-sanatorii-v-uzkom-smysle", "russia", 2024, 1324.0),
    ]


def test_occupancy_is_labelled_calculation():
    pts = [("tour-ksr-nochevki", "russia", 2024, 383490.447), ("tour-ksr-mesta", "russia", 2024, 3186017.0)]
    assert L.occupancy_points(pts) == [("tour-ksr-zagruzka-mest", "russia", 2024, 33.0)]
    assert R.source_of("tour-ksr-zagruzka-mest")["ru"] == "расчёт по данным Росстата"


def test_price_file_subjects_only_and_codes(terr):
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "09(2026)"
    for r in (["Код территории", "Наименование территории", 1, 2, 3],
              [None, None, "Санаторий, день", "Поездка на отдых на Черноморское побережье России, поездка",
               "Говядина бескостная, кг"],
              [643, "Российская Федерация", 6131.68, 50000, 900],
              [14000000000, "Белгородская область", 5000, "-", 800],
              [14401000000, "Белгород", 5100, 1, 800]):
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    pts = sorted(p for p, _r in L.price_points(buf.getvalue(), terr))
    assert pts == [("ceni-poezdka-chernomore", "russia", 202609, 50000.0),
                   ("ceni-sanatoriy", "belgorodskaya-oblast", 202609, 5000.0),
                   ("ceni-sanatoriy", "russia", 202609, 6131.68)]


def test_tourism_in_russia_book_columns(terr):
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "R5t1"
    for r in (["◄К Разделу 5"], ["Число гостиниц …"], [],
              [None, "Число гостиниц", None, "Число номеров", None, "из них", None],
              [None, None, None, None, None, "высшей категории", None],
              [None, 2022, 2023, 2022, 2023, 2022, 2023],
              ["Российская Федерация", 13301, 14426, 485899, 528685, 59725, 61018]):
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    pts = {(c, p): v for c, _s, p, v in L.tur_rus_points(buf.getvalue(), terr)}
    assert pts == {("tour-gostinicy-chislo", 2022): 13301, ("tour-gostinicy-chislo", 2023): 14426,
                   ("tour-gostinicy-nomera", 2022): 485899, ("tour-gostinicy-nomera", 2023): 528685,
                   ("tour-gostinicy-nomera-vysshey-kategorii", 2022): 59725,
                   ("tour-gostinicy-nomera-vysshey-kategorii", 2023): 61018}


def test_stand_units_rescaled_and_js_escapes(terr):
    """Стенд 20.11.2026: 44041 — «квадратный метр», 62159 — «тысяча единиц»; в подписях страницы бывает «\\/»."""
    s = R.SERIES_BY_CODE["tour-ksr-ploshchad-nomerov"]
    page = L.parse_indicator_page(_page(1, "x").replace("'Ночёвки'", "'a\\/b \\u0420'"))
    assert page["filters"]["0"]["values"]["1"] == "a/b Р"
    assert dict(s.emiss.alt_units)["квадратный метр"] == 0.001
    assert dict(R.SERIES_BY_CODE["tour-ksr-nomera-klassificirovannye"].emiss.alt_units)["тысяча единиц"] == 1000.0
    assert R.SERIES_BY_CODE["tour-vds-turindustrii"].emiss.src_unit == "миллион рублей"
    assert R.SERIES_BY_CODE["tour-vds-turindustrii-dolya-vrp"].emiss.dataset == 62197


# --- добор g2: оценки регионов, Москва ---------------------------------------------------------------------------


def test_regional_flow_one_measure_per_region_and_breaks(terr):
    rows = [
        {"country_or_region": "Ставропольский край", "period": "2022", "origin": "всего туристов (индикатор ГП)",
         "value": "1975930"},
        {"country_or_region": "Ставропольский край", "period": "2023",
         "origin": "всего туристов (индикатор ГП, оценка Росстата)", "value": "2971133"},
        {"country_or_region": "Ставропольский край", "period": "2025",
         "origin": "всего посетителей (операторы связи, вкл. однодневных)", "value": "9000000"},
        {"country_or_region": "Ставропольский край", "period": "2023", "origin": "иностранцы", "value": "5000"},
        {"country_or_region": "Республика Крым", "period": "2025-12", "origin": "туристы", "value": "1"},
    ]
    pts, meta = L.regional_flow_points(rows, terr)
    assert pts == [("tour-turpotok-ocenka-regiona", "stavropolskiy-kray", 2022, 1975.93),
                   ("tour-turpotok-ocenka-regiona", "stavropolskiy-kray", 2023, 2971.133)]
    assert meta["stavropolskiy-kray"]["breaks"] == [2023]


def test_moscow_open_data_last_date_in_year():
    rows = [{"country_or_region": "Москва", "period": "2025", "origin": "всего", "indicator": "tourists_annual",
             "value": "26500000"},
            {"country_or_region": "Москва", "period": "2024-01-10", "origin": "все категории",
             "indicator": "classified_accommodation_objects", "value": "2000"},
            {"country_or_region": "Москва", "period": "2024-12-28", "origin": "все категории",
             "indicator": "classified_accommodation_objects", "value": "2102"}]
    assert sorted(L.moscow_points(rows)) == [("tour-moskva-reestr-obekty", "moskva", 2024, 2102.0),
                                             ("tour-turpotok-ocenka-regiona", "moskva", 2025, 26500.0)]


def test_regional_estimate_has_method_and_no_rating():
    assert "tour-turpotok-ocenka-regiona" in R.NOT_RANKED
    ru = R.region_method("tour-turpotok-ocenka-regiona", "stavropolskiy-kray", "ru")
    assert "2023" in ru and "разрывается" in ru
    en = R.region_method("tour-turpotok-ocenka-regiona", "stavropolskiy-kray", "en")
    assert en.startswith("Who is counted") and not any("а" <= ch <= "я" for ch in en.casefold())
    assert R.region_method("tour-ksr-mesta", "moskva") is None


def test_region_methods_public_text_for_every_region():
    import re

    methods = json.loads((L._DATA / "tourism_region_methods.json").read_text(encoding="utf-8"))
    slugs = {s for _c, s, _p in {(c, s, p) for c, s, p, _v in L.read_seed() if c == "tour-turpotok-ocenka-regiona"}}
    assert slugs <= set(methods) and len(slugs) == 18
    jargon = re.compile(r"\b(ГП|КСР|ИСР|СМИ|РФ|РК|РТ|РД|РА|МО|ЯО|ЛО|СПб|АО|ФО|ОКВЭД)\b")
    for slug in slugs:
        m = methods[slug]
        for lang in ("ru", "en"):
            assert m[f"who_{lang}"] and m[f"how_{lang}"], slug
            text = R.region_method("tour-turpotok-ocenka-regiona", slug, lang)
            assert not jargon.search(text), (slug, text)
            assert len(text) < 600, slug
        assert not re.search(r"[а-яё]", R.region_method("tour-turpotok-ocenka-regiona", slug, "en").casefold())



# --- круг наблюдателей 20.11.2026 -------------------------------------------------------------------------------


def test_source_urls_point_to_publication_or_emiss():
    for s in R.SERIES:
        if not s.own_metadata:
            continue
        url = R.source_url(s.code, "stavropolskiy-kray")
        assert url and url.startswith("http"), s.code
        assert "/statistics/turizm" not in url and "macro_itm/svs" not in url
        if s.emiss is not None:
            assert url == f"https://www.fedstat.ru/indicator/{s.emiss.dataset}"
    assert R.source_url("tour-turpotok-ocenka-regiona", "moskva") == "https://data.mos.ru/opendata/62056"


def test_tax_zero_statuses_and_no_minus_100(auth_env):
    from app.models import Region, RegionIndicator, RegionMonthlyPoint
    from app.services.tourism_regional_api import zero_statuses

    async def run():
        async with auth_env["session_maker"]() as db:
            regs = [Region(slug=s, name=s, kind="region") for s in ("moskva", "sankt-peterburg", "tomskaya-oblast")]
            ind = RegionIndicator(code="tour-nalog-s-nachala-goda", name="x", table_code="6.tm20", section_num=6,
                                  section_name="x")
            db.add_all([*regs, ind])
            await db.flush()
            db.add(RegionMonthlyPoint(indicator_id=ind.id, region_id=regs[1].id, month=202604, value=162.8))
            db.add(RegionMonthlyPoint(indicator_id=ind.id, region_id=regs[1].id, month=202605, value=0))
            await db.commit()
            values = [{"slug": "moskva", "raw": 0.0, "prev": 0.0}, {"slug": "sankt-peterburg", "raw": 0.0, "prev": 5.0},
                      {"slug": "tomskaya-oblast", "raw": 0.0}, {"slug": "x", "raw": 3.0, "prev": 0.0}]
            missing = [{"slug": "kurskaya-oblast"}]
            await zero_statuses(db, ind.code, ind.id, "monthly", 202605, values, missing)
            return values, missing

    values, missing = asyncio.run(run())
    assert [v.get("status") for v in values] == ["not_introduced", "no_receipts_yet", "zero_year", None]
    assert all("prev" not in v for v in values)
    assert missing == [{"slug": "kurskaya-oblast", "status": "no_data"}]


def test_occupancy_and_regional_estimates_not_ranked():
    assert {"tour-ksr-zagruzka-mest", "tour-turpotok-ocenka-regiona"} <= R.NOT_RANKED
    assert "31583" in R.SERIES_BY_CODE["tour-ksr-zagruzka-mest"].note_ru


def test_tourism_siblings_exclude_culture_and_sport():
    assert not R.is_tourism_sibling("chislo-sportivnyh-sooruzheniy-plavatelnye-basseyny", "6.2.4")
    assert not R.is_tourism_sibling("chislennost-zriteley-teatrov-i-chislo-posescheniy-muzeev", "6.1.1")
    assert R.is_tourism_sibling("kollektivnye-sredstva-razmescheniya-chislo-kollektivnyh-sredstv-razmescheniya", "6.7.1")
    assert R.is_tourism_sibling("turpoezdki-s-nachala-goda", "6.m1")
