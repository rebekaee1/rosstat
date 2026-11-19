"""Банк России: максимальная ставка по вкладам 10 банков, инфляционные ожидания, ставки по регионам (19.11.2026).

Фикстуры — живые ответы cbr.ru с Mac 19.11.2026, урезанные: таблица декад ``avgprocstav`` (01.07.2009–19.11.2026),
ссылки страниц раздела и выпуска ``Infl_exp_26-10``, лист «Данные за все годы» файла ``Infl_exp_26-10.xlsx`` (нужные
блоки), DataService: территории наборов 34 и 39, данные ипотеки по России и НАО, вкладов по ЦФО (2019–2026).
Контроль по тексту выпуска Банка России за октябрь 2026: ожидаемая инфляция 13,2 % (сентябрь 14,2 %), наблюдаемая
14,5 %; таблица avgprocstav: I декада ноября 2026 — 13,305 %.
"""
import asyncio
import json
from datetime import date
from pathlib import Path

import pytest

from app.data import cbr_household_rates as spec
from app.data import cbr_regional_rates as rspec
from app.data.i18n.region_indicators_en import REGION_INDICATORS_EN
from app.services import cbr_household_rates_parser as hparser
from app.services import cbr_regional_rates_parser as rparser
from app.services.emiss_regional_parser import load_dimnames
from app.services.rosstat_cpi_parser import PARSER_REGISTRY

FX = Path(__file__).parent / "fixtures" / "cbr_household_rates"
RFX = Path(__file__).parent / "fixtures" / "cbr_regional_rates"
REGIONS = json.loads((Path(__file__).parents[1] / "app" / "data" / "regional" / "regions.json").read_text("utf-8"))


def _names() -> dict[str, str]:
    return {**load_dimnames(), **{r["name"]: r["slug"] for r in REGIONS}}


# ── Максимальная ставка по вкладам ───────────────────────────────────────────


def test_decade_table_parses_whole_history():
    points = hparser.parse_deposit_max_html((FX / "avgprocstav_2026-11-19.html").read_text("utf-8"))
    assert len(points) == 624
    assert (points[0].date, points[0].value) == (date(2009, 7, 11), 15.02)
    assert (points[-1].date, points[-1].value) == (date(2026, 11, 1), 13.305)
    by_date = {p.date: p.value for p in points}
    assert by_date[date(2026, 10, 21)] == 13.085 and by_date[date(2026, 1, 1)] == 15.102
    assert {p.date.day for p in points} == {1, 11, 21}


def test_decade_table_without_rows_is_empty():
    assert hparser.parse_deposit_max_html("<html><table class='data'><tr><th>Декада</th></tr></table></html>") == []


# ── Инфляционные ожидания ────────────────────────────────────────────────────


def test_latest_release_and_xlsx_link_are_found():
    assert hparser.latest_release_path((FX / "ie_links.html").read_text("utf-8")) == \
        "/analytics/dkp/inflationary_expectations/Infl_exp_26-10/"
    assert hparser.xlsx_href((FX / "ie2610_links.html").read_text("utf-8")) == \
        "/Collection/Collection/File/62471/Infl_exp_26-10.xlsx"
    assert hparser.latest_release_path("<a href='/x/'>нет</a>") is None


def test_expectations_file_gives_three_series_with_october_values():
    series = hparser.parse_expectations_xlsx((FX / "Infl_exp_26-10_trimmed.xlsx").read_bytes())
    assert set(series) == set(spec.SURVEY)
    expected = {p.date: p.value for p in series["inflation-expected"]}
    observed = {p.date: p.value for p in series["inflation-observed"]}
    sentiment = {p.date: p.value for p in series["consumer-sentiment"]}
    assert round(expected[date(2026, 10, 1)], 1) == 13.2 and round(expected[date(2026, 9, 1)], 1) == 14.2
    assert round(observed[date(2026, 10, 1)], 1) == 14.5
    assert 90 < sentiment[date(2026, 10, 1)] < 100
    assert min(sentiment) == date(2009, 12, 1)
    assert len(expected) == 163 and len(sentiment) == 164   # в одном раннем опросе вопроса не было


def test_expectations_file_without_sheet_is_an_error(tmp_path):
    import openpyxl

    wb = openpyxl.Workbook()
    path = tmp_path / "x.xlsx"
    wb.save(path)
    with pytest.raises(ValueError, match="нет листа"):
        hparser.parse_expectations_xlsx(path.read_bytes())


def test_federal_series_are_registered_seeded_and_translated():
    from app.data.i18n.indicator_copy_en import INDICATOR_COPY_EN
    from app.data.indicator_seo import INDICATOR_SEO, INDICATOR_SEO_BLOCKS, INDICATOR_SEO_KEYWORDS

    rows = {row["code"]: row for row in spec.seed_indicators()}
    assert set(rows) == {spec.DEPOSIT_MAX_CODE, *spec.SURVEY}
    for code, row in rows.items():
        assert row["parser_type"] in PARSER_REGISTRY
        assert row["model_config_json"]["forecast_steps"] == 0
        assert INDICATOR_COPY_EN[code]["name"] and INDICATOR_SEO[code]["seo_title"]
        assert INDICATOR_SEO_KEYWORDS[code] and len(INDICATOR_SEO_BLOCKS[code]) == 4
        assert "parser" not in row["methodology"].lower() and "xlsx" not in row["methodology"].lower()
    assert rows[spec.DEPOSIT_MAX_CODE]["frequency"] == "weekly"


@pytest.mark.parametrize(("q", "code"), [
    ("максимальная ставка по вкладам", spec.DEPOSIT_MAX_CODE),
    ("инфляционные ожидания", "inflation-expected"),
    ("наблюдаемая инфляция", "inflation-observed"),
    ("индекс потребительских настроений", "consumer-sentiment"),
])
def test_search_phrases_name_the_new_series(q, code):
    from app.services.search_intent import CONCEPTS

    hits = [terms for phrases, terms in CONCEPTS if q in phrases]
    assert hits and code in hits[0]


# ── Ставки по регионам ───────────────────────────────────────────────────────


def test_every_territory_of_mortgage_and_deposit_sets_has_a_site_region():
    slugs = {r["slug"] for r in REGIONS}
    for ds, count in ((34, 96), (39, 8)):
        measures = json.loads((RFX / f"measures_{ds}.json").read_text("utf-8"))["measure"]
        mapped = rparser.measure_slugs(measures, _names())
        assert len(measures) == count and len(mapped) == count
        assert set(mapped.values()) <= slugs and len(set(mapped.values())) == count
    mapped = rparser.measure_slugs(json.loads((RFX / "measures_34.json").read_text("utf-8"))["measure"], _names())
    assert mapped[22] == "russia" and mapped[45] == "arhangelskaya-oblast" and mapped[46] == "nenetskiy-ao"
    assert mapped[93] == "tyumenskaya-oblast-bez-ao"


def test_mortgage_and_deposit_rows_parse_by_month_name():
    series = rspec.datasets()[(15, 34)]
    raw = json.loads((RFX / "data_34_russia.json").read_text("utf-8"))["RawData"]
    rows = {(code, period): v for code, period, v in rparser.parse_rows(raw, series)}
    assert rows[("stavka-ipoteki", 202609)] == 8.61 and rows[("stavka-ipoteki", 202608)] == 10.08
    assert min(p for _c, p in rows) == 201901 and len(rows) == 93     # валютная ипотека (element 40) не берётся
    deposits = rspec.datasets()[(19, 39)]
    raw = json.loads((RFX / "data_39_cfo.json").read_text("utf-8"))["RawData"]
    rows = {(code, period): v for code, period, v in rparser.parse_rows(raw, deposits)}
    assert {c for c, _p in rows} == {"stavka-vkladov-do-1-goda", "stavka-vkladov-svyshe-1-goda"}
    assert rows[("stavka-vkladov-do-1-goda", 202601)] == 14.71 and rows[("stavka-vkladov-svyshe-1-goda", 202601)] == 13.73


def test_zero_and_unknown_rows_are_skipped():
    series = rspec.datasets()[(15, 34)]
    raw = [{"element_id": 36, "dt": "Май 2026", "obs_val": 0.0}, {"element_id": 40, "dt": "Май 2026", "obs_val": 5},
           {"element_id": 36, "dt": "2026", "obs_val": 9}, {"element_id": 36, "dt": "Май 2026", "obs_val": 9.5}]
    assert rparser.parse_rows(raw, series) == [("stavka-ipoteki", 202605, 9.5)]


def test_catalog_rows_and_english_copy():
    rows = rspec.indicator_rows()
    catalog = json.loads((Path(__file__).parents[1] / "app" / "data" / "regional" / "indicators.json").read_text("utf-8"))
    by_code = {r["code"]: r for r in catalog}
    for row in rows:
        assert by_code[row["code"]] == row
        assert row["table_code"].startswith("19.s") and row["frequency"] == "monthly"
        assert REGION_INDICATORS_EN[row["code"]]["name"] and REGION_INDICATORS_EN[row["code"]]["note"]
    own = {r["code"] for r in rows}
    assert not {r["table_code"] for r in rows} & {r["table_code"] for r in catalog if r["code"] not in own}


def _scenario(tmp_path, monkeypatch, get_json, *, preload: bool):
    from sqlalchemy import create_engine
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.models import Base, Region, RegionIndicator, RegionMonthlyPoint

    db_path = tmp_path / "rates.db"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    engine.dispose()
    written: list[tuple] = []

    async def fake_upsert(db, values):
        written.extend(values)
        return len(values), 0

    async def no_bounds(db, ids):
        return False

    monkeypatch.setattr(rparser, "_upsert_monthly_points", fake_upsert)
    monkeypatch.setattr(rparser, "acquire_regional_write_lock", lambda db: asyncio.sleep(0))
    monkeypatch.setattr(rparser, "update_regional_year_bounds", no_bounds)
    monkeypatch.setattr(rparser, "publish_committed_regional_changes", lambda: asyncio.sleep(0))

    async def run():
        eng = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
        maker = async_sessionmaker(eng, expire_on_commit=False)
        try:
            async with maker() as db:
                for r in REGIONS:
                    db.add(Region(slug=r["slug"], name=r["name"], kind=r["kind"]))
                for row in rspec.indicator_rows():
                    db.add(RegionIndicator(code=row["code"], table_code=row["table_code"], section_num=19,
                                           section_name="Финансы", name=row["name"]))
                await db.flush()
                if preload:
                    ids = (await db.execute(RegionIndicator.__table__.select())).all()
                    russia = (await db.execute(Region.__table__.select().where(Region.slug == "russia"))).first()
                    for row in ids:
                        db.add(RegionMonthlyPoint(indicator_id=row.id, region_id=russia.id, month=202608, value=9))
                await db.commit()
                return await rparser.run_cbr_regional_rates_update(
                    db, get_json=get_json, today=date(2026, 11, 19), pause_s=0)
        finally:
            await eng.dispose()

    return asyncio.run(run()), written


def _fake_source(asked):
    measures = {ds: json.loads((RFX / f"measures_{34 if ds == 34 else 39}.json").read_text("utf-8")) for ds in (34, 39, 32, 33)}
    russia = json.loads((RFX / "data_34_russia.json").read_text("utf-8"))
    cfo = json.loads((RFX / "data_39_cfo.json").read_text("utf-8"))

    def get_json(path, params):
        asked.append((path, dict(params)))
        if path == "measures":
            return measures[params["datasetId"]]
        if params["datasetId"] == 34:
            return russia if params["measureId"] == 22 else {"RawData": []}
        return cfo if params["datasetId"] == 39 and params["measureId"] == 23 else {"RawData": []}

    return get_json


def test_empty_base_loads_history_from_2019_for_every_territory(tmp_path, monkeypatch):
    asked: list = []
    stats, written = _scenario(tmp_path, monkeypatch, _fake_source(asked), preload=False)
    data = [p for path, p in asked if path == "data"]
    assert len(data) == 96 + 8 * 3 and {p["y1"] for p in data} == {2019}
    assert stats["requests"] == len(data) and stats["added"] == len(written) == 93 + 93 * 2


def test_filled_base_asks_last_and_current_year(tmp_path, monkeypatch):
    asked: list = []
    _stats, _written = _scenario(tmp_path, monkeypatch, _fake_source(asked), preload=True)
    assert {p["y1"] for path, p in asked if path == "data"} == {2025}


def test_failed_territory_keeps_others_and_raises(tmp_path, monkeypatch):
    asked: list = []
    good = _fake_source(asked)

    def flaky(path, params):
        if path == "data" and params.get("measureId") == 24:
            raise ConnectionError("timeout")
        return good(path, params)

    with pytest.raises(RuntimeError, match="не загружено запросов: 1"):
        _scenario(tmp_path, monkeypatch, flaky, preload=False)
