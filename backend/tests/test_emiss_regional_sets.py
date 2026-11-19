"""Помесячные региональные наборы ЕМИСС 57693, 34118, 57806, 31076 (19.11.2026).

Фикстуры — живые ответы dataGrid.do с Mac 19.11.2026 тем же запросом, что строит парсер, урезанные до России,
Москвы, Воронежской области и Краснодарского края. Контрольные значения России за сентябрь 2026 сверены вторым
живым запросом с другим набором измерений в строках (ОКЕИ и позиции; виды показателя и разделы).
"""
import asyncio
import json
from datetime import date
from pathlib import Path

import pytest

from app.data import emiss_regional_sets as sets
from app.data.i18n.region_indicators_en import REGION_INDICATORS_EN
from app.services import emiss_regional_sets_parser as parser
from app.services.emiss_regional_parser import MONTH_OIDS, load_dimnames, load_territory_ids

FIXTURES = Path(__file__).parent / "fixtures" / "emiss_regional_sets"
DIMNAMES = load_dimnames()


def fixture(dataset, year):
    return json.loads((FIXTURES / f"dataGrid_{dataset}_{year}_2026-11-19.json").read_text(encoding="utf-8"))


def points(rset, year):
    found, rejected = parser.parse_year(rset, fixture(rset.dataset, year), year, DIMNAMES)
    assert rejected == 0
    return {(code, slug, period): value for code, slug, period, value in found}


@pytest.mark.parametrize(("rset", "code", "value"), [
    (sets.AGRO_PRICES, "selhoz-cena-pshenica", 10185.32),
    (sets.AGRO_PRICES, "selhoz-cena-podsolnechnik", 31784.74),
    (sets.AGRO_PRICES, "selhoz-cena-moloko", 36742.03),
    (sets.AGRO_PRICES, "selhoz-cena-yayca", 6825.18),
    (sets.HOUSING, "vvod-zhilya-mes", 8243.8),
    (sets.HOUSING, "vvod-zhilya-mkd-mes", 2848.5),
    (sets.HOUSING, "vvod-zhilya-izhs-mes", 5271.7),
    (sets.INDUSTRY, "ipp-obrabotka-mes", 105.6),
    (sets.INDUSTRY, "ipp-dobycha-mes", 95.9),
    (sets.FREIGHT, "tarif-gruz-vse-mes", 108.48),
    (sets.FREIGHT, "tarif-gruz-zhd-mes", 114.68),
])
def test_russia_september_2026_matches_the_source(rset, code, value):
    assert points(rset, 2026)[(code, "russia", 202609)] == value


def test_regions_come_by_name_and_months_by_oid():
    got = points(sets.AGRO_PRICES, 2026)
    assert got[("selhoz-cena-pshenica", "voronezhskaya-oblast", 202609)] == 9797.44
    assert got[("selhoz-cena-pshenica", "krasnodarskiy-kray", 202609)] == 12933.05
    # Москва зерна не продаёт: строк нет, и это не ошибка.
    assert not any(slug == "moskva" for _code, slug, _p in got)
    assert {p % 100 for _c, _s, p in got} <= set(range(1, 10))


def test_russia_switches_to_the_series_without_new_regions_in_2023():
    got = points(sets.AGRO_PRICES, 2023)
    # Ноябрь 2023 — строка «Российская Федерация», декабрь — только «без учета новых субъектов».
    assert got[("selhoz-cena-moloko", "russia", 202311)] == 32018.84
    assert got[("selhoz-cena-moloko", "russia", 202312)] == 32730.3


def test_renamed_position_keeps_one_series():
    """Молоко, яйца, кукуруза: с 2024 года у Росстата новый oid под тем же названием — ряд один."""
    flat = [v for k, v in parser.build_params(sets.AGRO_PRICES, 2026, ["1849012"]) if k == "selectedFilterIds"]
    assert {"57939_1758171", "57939_1851174", "57939_1758179", "57939_1847175"} <= set(flat)
    got2023, got2026 = points(sets.AGRO_PRICES, 2023), points(sets.AGRO_PRICES, 2026)
    assert ("selhoz-cena-yayca", "russia", 202312) in got2023 and ("selhoz-cena-yayca", "russia", 202609) in got2026


def test_krasnodar_with_sirius_fills_only_missing_months():
    got = points(sets.HOUSING, 2026)
    # Обычная строка края идёт до апреля 2026, дальше месяцы есть только у строки «с учетом ФТ «Сириус»».
    assert got[("vvod-zhilya-mes", "krasnodarskiy-kray", 202604)] == 336.4
    assert got[("vvod-zhilya-mes", "krasnodarskiy-kray", 202609)] == 469.3
    prices = points(sets.AGRO_PRICES, 2026)
    # У цен обе строки идут параллельно (значения совпадают, сентябрь — только у обычной): ряд по обычной строке.
    assert prices[("selhoz-cena-pshenica", "krasnodarskiy-kray", 202608)] == 14700.66
    assert prices[("selhoz-cena-pshenica", "krasnodarskiy-kray", 202609)] == 12933.05


def test_request_selects_months_territories_and_fixed_filters():
    params = parser.build_params(sets.INDUSTRY, 2025, load_territory_ids())
    lines = [v for k, v in params if k == "lineObjectIds"]
    flat = [v for k, v in params if k == "selectedFilterIds"]
    assert lines == ["57940", "57831"] and ("columnObjectIds", "33560") in params
    assert {"0_57806", "3_2025", "30611_950473", "57937_1704141", "57831_1688487", "57831_1856621"} <= set(flat)
    assert {f"33560_{oid}" for oid in MONTH_OIDS} <= set(flat)
    assert not any(v.startswith("33560_15402") and v[6:] not in MONTH_OIDS for v in flat)


def test_out_of_bounds_values_are_counted_not_stored():
    payload = {"results": [{"dim58787": "Транспорт - все виды", "dim57831": "Воронежская область",
                            "dim1540283_d1_i1": "-5,0", "dim1540282_d1_i2": "105,3", "dim1540236_d1_i3": "-",
                            "dim1540230_d1_i4": "0"}]}
    found, rejected = parser.parse_year(sets.FREIGHT, payload, 2026, DIMNAMES)
    assert found == [("tarif-gruz-vse-mes", "voronezhskaya-oblast", 202602, 105.3)] and rejected == 1


def test_years_to_fetch_full_history_then_tail():
    rset = sets.HOUSING
    today = date(2026, 11, 19)
    assert parser.years_to_fetch(rset, {}, today) == range(2012, 2027)
    lasts = {s.code: 202609 for s in rset.series}
    assert parser.years_to_fetch(rset, lasts, today) == range(2025, 2027)
    lasts["vvod-zhilya-mkd-mes"] = None
    assert parser.years_to_fetch(rset, lasts, today) == range(2012, 2027)


def test_run_writes_through_injected_transport(monkeypatch):
    """Прогон набора: запрос на каждый год, точки — в upsert, кэш — после изменения."""
    calls, written = [], []

    async def post(dataset, params):
        year = int(next(v for k, v in params if k == "selectedFilterIds" and v.startswith("3_"))[2:])
        calls.append((dataset, year))
        return fixture(31076, 2026) if year == 2026 else {"results": []}

    async def upsert(db, values):
        written.extend(values)
        return len(values), 0

    async def noop(*_a, **_k):
        return 0

    class Result:
        def __init__(self, rows):
            self.rows = rows

        def scalars(self):
            return self.rows

        def all(self):
            return self.rows

    class Ind:
        def __init__(self, i, code):
            self.id, self.code = i, code

    inds = [Ind(i, s.code) for i, s in enumerate(sets.FREIGHT.series, start=1)]

    class Db:
        def __init__(self):
            self.n = 0

        async def execute(self, _stmt):
            self.n += 1
            if self.n == 1:
                return Result(inds)
            if self.n == 2:
                return Result([("russia", 10), ("voronezhskaya-oblast", 11), ("krasnodarskiy-kray", 12),
                               ("moskva", 13)])
            return Result([(i.id, 202508) for i in inds])

        async def commit(self):
            pass

        async def rollback(self):
            pass

    published = []

    async def publish():
        published.append(1)

    monkeypatch.setattr(parser, "_upsert_monthly_points", upsert)
    monkeypatch.setattr(parser, "acquire_regional_write_lock", noop)
    monkeypatch.setattr(parser, "update_regional_year_bounds", noop)
    monkeypatch.setattr(parser, "publish_committed_regional_changes", publish)
    monkeypatch.setattr(parser, "_PAUSE_BETWEEN_REQUESTS", 0)
    stats = asyncio.run(parser.run_set_update(Db(), sets.FREIGHT, post_grid=post, today=date(2026, 11, 19)))
    assert calls == [(31076, 2024), (31076, 2025), (31076, 2026)]
    assert stats == {"years": 3, "added": len(written), "updated": 0, "rejected": 0}
    assert (1, 10, 202609, 108.48) in written and published == [1]


def test_catalogue_rows_are_monthly_unique_and_translated():
    rows = sets.artifact_rows()
    codes = [r["code"] for r in rows]
    assert len(codes) == len(set(codes)) == 29
    existing = json.loads((Path(__file__).parents[1] / "app/data/regional/indicators.json").read_text())
    assert not set(codes) & {r["code"] for r in existing}
    assert not {r["table_code"] for r in rows} & {r["table_code"] for r in existing}
    assert all(r["frequency"] == "monthly" for r in rows)
    for code in codes:
        en = REGION_INDICATORS_EN[code]
        assert en["name"] and en["unit"] and en["section"]
    assert dict((r["code"], r["unit"]) for r in rows)["selhoz-cena-yayca"] == "рублей за 1000 штук"


def test_seed_appends_registry_rows():
    import seed_regional

    _regions, indicators = seed_regional.load_meta()
    by_code = {r["code"]: r for r in indicators}
    assert by_code["selhoz-cena-podsolnechnik"]["section_name"] == "Сельское хозяйство"
    assert by_code["vvod-zhilya-mes"]["section_num"] == 14


@pytest.fixture
def regions_client(auth_env):
    """Каталог регионов с тремя рядами наборов: профиль, помесячная страница, карта и соседи по набору."""
    from fastapi.testclient import TestClient

    from app.models import Region, RegionIndicator, RegionMonthlyPoint

    async def seed():
        async with auth_env["session_maker"]() as db:
            rf = Region(slug="russia", name="Российская Федерация", kind="country")
            vrn = Region(slug="voronezhskaya-oblast", name="Воронежская область", kind="region")
            krd = Region(slug="krasnodarskiy-kray", name="Краснодарский край", kind="region")
            rows = {r["code"]: r for r in sets.artifact_rows()}
            inds = [RegionIndicator(code=c, name=rows[c]["name"], unit=rows[c]["unit"],
                                    table_code=rows[c]["table_code"], section_num=rows[c]["section_num"],
                                    section_name=rows[c]["section_name"], is_listed=True)
                    for c in ("selhoz-cena-pshenica", "selhoz-cena-podsolnechnik", "vvod-zhilya-mes")]
            annual = RegionIndicator(code="indeksy-proizvodstva-produktsii-selskogo-hozyaystva-vsego",
                                     name="Индексы производства продукции сельского хозяйства — всего",
                                     unit="% к предыдущему году", table_code="13.2.1", section_num=13,
                                     section_name="Сельское хозяйство", is_listed=True)
            db.add_all([rf, vrn, krd, *inds, annual])
            await db.flush()
            got = {**points(sets.AGRO_PRICES, 2026), **points(sets.HOUSING, 2026)}
            by_slug = {"russia": rf, "voronezhskaya-oblast": vrn, "krasnodarskiy-kray": krd}
            by_code = {i.code: i for i in inds}
            for (code, slug, period), value in got.items():
                if code in by_code and slug in by_slug:
                    db.add(RegionMonthlyPoint(indicator_id=by_code[code].id, region_id=by_slug[slug].id,
                                              month=period, value=value))
            await db.commit()

    asyncio.run(seed())
    with TestClient(auth_env["app"]) as client:
        yield client


def test_region_pages_show_the_new_monthly_series(regions_client):
    prof = regions_client.get("/api/v1/regions/voronezhskaya-oblast").json()
    items = {i["code"]: i for s in prof["sections"] for i in s["indicators"]}
    assert items["selhoz-cena-pshenica"]["value"] == 9797.44 and items["selhoz-cena-pshenica"]["month"] == 202609
    assert items["vvod-zhilya-mes"]["period_label"] == "сентябрь 2026"

    mon = regions_client.get("/api/v1/regions/voronezhskaya-oblast/i/selhoz-cena-pshenica/monthly").json()
    assert mon["frequency"] == "monthly" and mon["series"][-1]["value"] == 9797.44
    assert mon["russia_series"][-1]["value"] == 10185.32
    # Соседи — сначала ряды того же набора, потом остальной раздел.
    assert [s["code"] for s in mon["siblings"]][:1] == ["selhoz-cena-podsolnechnik"]

    heat = regions_client.get("/api/v1/regions/heatmap/selhoz-cena-pshenica").json()
    assert heat["month"] == 202609
    assert {v["slug"]: v["raw"] for v in heat["values"]} == {"voronezhskaya-oblast": 9797.44,
                                                             "krasnodarskiy-kray": 12933.05}
