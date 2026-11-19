"""ЕМИСС 31074/31052/31481: ИПЦ и стоимость наборов по регионам помесячно (19.11.2026).

Фикстура — живые ответы dataGrid.do с Mac 19.11.2026 (2026 год — все четыре запроса, 2022 — главные индексы),
урезанные до России, Москвы и Липецкой области. Контроль: декабрь 2022 к декабрю 2021 совпадает с годовым рядом
сборника «Регионы России» (Россия 111,9, Липецкая 113,0, Москва 111,7 — ``regional/data.csv.gz``).
"""
import asyncio
import json
from datetime import date
from pathlib import Path

import pytest

from app.data import emiss_regional_cpi as spec
from app.data.i18n.region_indicators_en import REGION_INDICATORS_EN
from app.services import emiss_regional_cpi_parser as parser
from app.services.emiss_regional_parser import load_dimnames, load_territory_ids
from app.services.search_intent import parse_intent
from app.services.search_r7a import REGION_HEADLINES_R7A
from app.services.seo_regional import MACRO_BY_TABLE

FIXTURE = Path(__file__).parent / "fixtures" / "emiss_regional_cpi" / "dataGrid_2026-11-19.json"
INDICATORS = Path(__file__).parents[1] / "app" / "data" / "regional" / "indicators.json"
REQ = {r.name: r for r in parser.REQUESTS}


def live(name):
    return json.loads(FIXTURE.read_text(encoding="utf-8"))[name]


def points(name, req, year):
    return {(c, s, m): v for c, s, m, v in parser.parse_year(live(name), REQ[req], year, load_dimnames())}


@pytest.mark.parametrize(("name", "req", "year", "checks"), [
    ("cpi-headline_2026", "cpi-headline", 2026, {
        ("ipc-vse-za-god", "russia", 202609): 106.35, ("ipc-vse-za-god", "lipetskaya-oblast", 202609): 106.61,
        ("ipc-vse-k-mesyacu", "moskva", 202609): 100.06, ("ipc-vse-k-dekabryu", "russia", 202609): 105.04,
        ("ipc-bazovyy-za-god", "russia", 202609): 105.47,
    }),
    ("cpi-groups_2026", "cpi-groups", 2026, {
        ("ipc-benzin-za-god", "russia", 202609): 122.71, ("ipc-kommunalnye-za-god", "moskva", 202609): 101.67,
        ("ipc-svyaz-za-god", "lipetskaya-oblast", 202609): 103.85,
    }),
    ("fixed-set_2026", "fixed-set", 2026, {
        ("nabor-fiksirovannyy", "russia", 202609): 27181.25, ("nabor-fiksirovannyy", "moskva", 202609): 40272.28,
    }),
    ("food-set_2026", "food-set", 2026, {
        ("nabor-minimalnyy-produktov", "lipetskaya-oblast", 202609): 6758.44,
    }),
    # Декабрь к декабрю = годовой ИПЦ сборника (111,9 / 113,0 / 111,7); до 2023 Россия — «Российская Федерация».
    ("cpi-headline_2022", "cpi-headline", 2022, {
        ("ipc-vse-k-dekabryu", "russia", 202212): 111.94, ("ipc-vse-k-dekabryu", "lipetskaya-oblast", 202212): 112.96,
        ("ipc-vse-k-dekabryu", "moskva", 202212): 111.7,
    }),
])
def test_live_answer_parses_to_known_values(name, req, year, checks):
    got = points(name, req, year)
    for key, value in checks.items():
        assert got[key] == value
    months = {m for _c, _s, m in got}
    assert min(months) == year * 100 + 1
    assert max(months) == (202609 if year == 2026 else 202212)
    # Кварталы набора 31074 в ряды не попадают: 12 месяцев на 2022 год.
    assert len(months) == (9 if year == 2026 else 12)


def test_every_series_of_request_is_present_in_live_answer():
    for name, req in (("cpi-headline_2026", "cpi-headline"), ("cpi-groups_2026", "cpi-groups")):
        codes = {c for c, _s, _m in points(name, req, 2026)}
        assert codes == {s.code for s in REQ[req].series}


def test_request_selects_months_items_kinds_and_russia_by_year():
    terr = load_territory_ids()
    p2026 = parser.build_params(REQ["cpi-headline"], 2026, terr)
    p2022 = parser.build_params(REQ["cpi-headline"], 2022, terr)
    f26 = {v for k, v in p2026 if k == "selectedFilterIds"}
    f22 = {v for k, v in p2022 if k == "selectedFilterIds"}
    assert {"0_31074", "3_2026", "30611_950473", "58273_1707675", "58273_1788790", "57937_1704142",
            "57937_1707674", "57937_1704140", "57831_1849012", "33560_1540283", "33560_1540230"} <= f26
    assert "57831_1688487" not in f26 and "57831_1688487" in f22
    assert not any(v.startswith("33560_") and v[6:] in {"1540222", "1540224", "1540226", "1540227"} for v in f26)
    lines = [v for k, v in p2026 if k == "lineObjectIds"]
    assert lines == ["57831", "58273", "57937"]
    groups = {v for k, v in parser.build_params(REQ["cpi-groups"], 2026, terr) if k == "selectedFilterIds"}
    assert {"57937_1704140"} == {v for v in groups if v.startswith("57937_")}
    sets = parser.build_params(REQ["fixed-set"], 2026, terr)
    assert [v for k, v in sets if k == "lineObjectIds"] == ["57831"]
    assert ("selectedFilterIds", "30611_950351") in sets


def test_unparsed_answer_is_an_error_not_silence():
    rows = [{"dim57831": "Липецкая область", "dim58273": "Все товары и услуги", "dim57937": "К предыдущему месяцу",
             "unknown_key": "1,0"}]
    with pytest.raises(parser.EmissCpiFormatError):
        parser.parse_year({"results": rows}, REQ["cpi-headline"], 2026, load_dimnames())
    assert parser.parse_year({"results": []}, REQ["cpi-headline"], 2026, load_dimnames()) == []


def test_russia_without_new_regions_wins_when_both_present():
    key = "dim2023_1540283_d1_i1"
    base = {"dim58273": "Все товары и услуги", "dim57937": "К предыдущему месяцу"}
    rows = [{**base, "dim57831": "Российская Федерация без учета новых субъектов (с 01.01.2023)", key: "100,84"},
            {**base, "dim57831": "Российская Федерация", key: "100,9"}]
    got = parser.parse_year({"results": rows}, REQ["cpi-headline"], 2023, load_dimnames())
    assert got == [("ipc-vse-k-mesyacu", "russia", 202301, 100.84)]


@pytest.mark.parametrize(("loaded", "today", "years"), [
    (None, date(2026, 11, 19), list(range(2002, 2027))),
    (set(range(2002, 2027)), date(2026, 11, 19), [2026]),
    (set(range(2002, 2026)), date(2027, 1, 20), [2025, 2026, 2027]),
    # Сбой прошлого прогона на 2010 годе: год пуст — запрашивается снова вместе с хвостом.
    (set(range(2002, 2027)) - {2010}, date(2026, 11, 19), [2010, 2026]),
])
def test_plan_backfills_gaps_and_refreshes_tail(loaded, today, years):
    assert parser.years_to_fetch(REQ["cpi-headline"], loaded, today=today) == years


def test_food_set_history_starts_in_2001():
    assert parser.years_to_fetch(REQ["food-set"], None, today=date(2026, 11, 19))[0] == 2001


def test_catalog_rows_english_copy_and_macro_bridge():
    rows = {r["code"]: r for r in json.loads(INDICATORS.read_text(encoding="utf-8"))}
    assert len(spec.SERIES) == 37
    for s in spec.SERIES:
        row = rows[s.code]
        assert row["frequency"] == "monthly" and row["section_num"] == 20 and row["table_code"].startswith("20.c")
        assert len(row["name"]) <= 300 and len(row["unit"]) <= 120
        assert REGION_INDICATORS_EN[s.code]["name"] == s.name_en
    # Обычный текст для людей: без кодов витрин и слов парсера в названии.
    assert all("31074" not in s.name and "ЕМИСС" not in s.name for s in spec.SERIES)
    assert MACRO_BY_TABLE["20.1"] == "cpi"
    assert MACRO_BY_TABLE[rows["ipc-vse-za-god"]["table_code"]] == "cpi"
    assert MACRO_BY_TABLE[rows["ipc-uslugi-k-mesyacu"]["table_code"]] == "cpi-services"


def test_region_search_leads_to_fresh_monthly_series():
    assert REGION_HEADLINES_R7A["cpi"] == "ipc-vse-za-god"
    assert REGION_HEADLINES_R7A["набора продуктов"] == "nabor-minimalnyy-produktov"
    for query in ("индекс стоимости жизни", "индекс стоимости жизни самара", "фиксированный набор липецкая область"):
        assert parse_intent(query, []).terms[0][0] == "фиксированного набора"
    assert REGION_HEADLINES_R7A["фиксированного набора"] == "nabor-fiksirovannyy"


def test_run_update_plans_full_history_for_empty_base(tmp_path, monkeypatch):
    """Пустая база: метаданные есть, точек нет — каждый запрос идёт с первого года набора."""
    from sqlalchemy import create_engine
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.models import Base, RegionIndicator

    db_path = tmp_path / "cpi.db"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    engine.dispose()
    asked = []

    async def fake_fetch(req, year, territory_ids, dimnames, post_grid=None):
        asked.append((req.name, year))
        return []

    monkeypatch.setattr(parser, "fetch_year", fake_fetch)
    monkeypatch.setattr(parser, "_PAUSE_BETWEEN_REQUESTS", 0)
    monkeypatch.setattr(parser, "acquire_regional_write_lock", lambda db: asyncio.sleep(0))

    async def no_bounds(db, ids):
        return False

    monkeypatch.setattr(parser, "update_regional_year_bounds", no_bounds)

    async def scenario():
        eng = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
        maker = async_sessionmaker(eng, expire_on_commit=False)
        try:
            async with maker() as db:
                for row in spec.artifact_rows():
                    db.add(RegionIndicator(code=row["code"], table_code=row["table_code"], section_num=20,
                                           section_name="Цены и тарифы", name=row["name"]))
                await db.commit()
                return await parser.run_emiss_regional_cpi_update(
                    db, territory_ids=["1849012"], dimnames={}, today=date(2026, 11, 19))
        finally:
            await eng.dispose()

    stats = asyncio.run(scenario())
    assert stats == {"years": len(asked), "added": 0, "updated": 0, "unparsed": 0}
    assert asked.count(("food-set", 2001)) == 1
    assert {n for n, _y in asked} == {"cpi-headline", "cpi-groups", "fixed-set", "food-set"}
    assert len(asked) == 25 * 3 + 26


def test_network_failure_on_one_year_keeps_other_years_and_raises(tmp_path, monkeypatch):
    """Сбой fedstat на 2010 годе: остальные годы прогона идут дальше, в конце — ошибка для алерта."""
    from sqlalchemy import create_engine
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.models import Base, RegionIndicator

    db_path = tmp_path / "cpi-fail.db"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    engine.dispose()
    asked = []

    async def flaky(req, year, territory_ids, dimnames, post_grid=None):
        asked.append((req.name, year))
        if req.name == "cpi-headline" and year == 2010:
            raise RuntimeError("dataGrid.do?id=31074: RemoteDisconnected")
        return []

    monkeypatch.setattr(parser, "fetch_year", flaky)
    monkeypatch.setattr(parser, "_PAUSE_BETWEEN_REQUESTS", 0)
    monkeypatch.setattr(parser, "acquire_regional_write_lock", lambda db: asyncio.sleep(0))

    async def no_bounds(db, ids):
        return False

    monkeypatch.setattr(parser, "update_regional_year_bounds", no_bounds)

    async def scenario():
        eng = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
        maker = async_sessionmaker(eng, expire_on_commit=False)
        try:
            async with maker() as db:
                for row in spec.artifact_rows():
                    db.add(RegionIndicator(code=row["code"], table_code=row["table_code"], section_num=20,
                                           section_name="Цены и тарифы", name=row["name"]))
                await db.commit()
                return await parser.run_emiss_regional_cpi_update(
                    db, territory_ids=["1849012"], dimnames={}, today=date(2026, 11, 19))
        finally:
            await eng.dispose()

    with pytest.raises(RuntimeError, match="cpi-headline 2010"):
        asyncio.run(scenario())
    assert ("cpi-headline", 2011) in asked and ("food-set", 2026) in asked
