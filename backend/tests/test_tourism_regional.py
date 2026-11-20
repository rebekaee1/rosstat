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
    assert all(s.code.startswith("tour-") for s in own)
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
    assert {c for c, _s, _p in pts} <= set(R.SERIES_BY_CODE)
    assert {s for _c, s, _p in pts} <= regions
    assert pts[("tour-ksr-nochevki", "russia", 2024)] == 383490.447
    assert pts[("kollektivnye-sredstva-razmescheniya-chislennost-razmeschennyh-lits", "russia", 2025)] == 92042.736
    assert ("kollektivnye-sredstva-razmescheniya-chislennost-razmeschennyh-lits", "russia", 2024) not in pts
    assert pts[("tour-turpotok-poezdki", "russia", 2025)] == 170035.535
    assert pts[("tour-cbr-poezdki-import", "russia", 20261)] == 9702.96
    assert pts[("tour-nalog-za-god", "russia", 2025)] == 5635.253
    # Наборы, не скачанные до бана fedstat, в снимке пусты — их догрузит живой прогон.
    pending = {s.code for s in R.SERIES if s.emiss is not None and not s.emiss.seed}
    assert not pending & {c for c, _s, _p in pts}


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
