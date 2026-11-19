"""Кредиты населению и ипотека из DataService Банка России (19.11.2026).

Фикстуры — живые ответы DataService 19.11.2026 (Россия и Воронежская область, 2025–2026 годы; список регионов
набора 45). Реестр — ``app.data.cbr_household_credit``, регионы — ``app.services.cbr_regional_credit_parser``.
"""
import asyncio
import json
from datetime import date
from pathlib import Path

import pytest

from app.data import cbr_household_credit as spec
from app.data.i18n.indicator_copy_en import INDICATOR_COPY_EN
from app.data.i18n.region_indicators_en import REGION_INDICATORS_EN
from app.data.indicator_seo import INDICATOR_SEO, INDICATOR_SEO_KEYWORDS
from app.services import cbr_regional_credit_parser as parser
from app.services.cbr_dataservice_parser import CbrDataServiceParser

FIXTURES = Path(__file__).parent / "fixtures" / "cbr_household_credit"
BY_FED = spec.SERIES_BY_FEDERAL


def fixture(ds: int, measure: int) -> dict:
    return json.loads((FIXTURES / f"data_ds{ds}_m{measure}_2025-2026.json").read_text())


# ── Реестр и карточки России ────────────────────────────────────────────────────────────────────

def test_federal_cards_use_the_existing_dataservice_parser():
    rows = list(spec.seed_indicators())
    assert [r["code"] for r in rows] == [
        "consumer-loans-issued", "consumer-credit-overdue", "mortgage-issued-count", "mortgage-issued",
        "mortgage-debt", "mortgage-overdue", "mortgage-term",
    ]
    assert {r["parser_type"] for r in rows} == {CbrDataServiceParser.parser_type}
    for r in rows:
        ds = r["model_config_json"]["dataservice"]
        assert ds["measureId"] == spec.RUSSIA_MEASURE and ds["date_offset_months"] == -1
        assert r["category"] == "Финансы" and r["frequency"] == "monthly" and r["source"] == "Банк России"
        assert INDICATOR_COPY_EN[r["code"]]["name"] and INDICATOR_COPY_EN[r["code"]]["methodology"]
        assert r["code"] in INDICATOR_SEO and r["code"] in INDICATOR_SEO_KEYWORDS


def test_consumer_credit_card_keeps_its_seed_and_gains_search_words():
    """Остаток кредитов физлицам уже есть (`consumer-credit`): новой карточки нет, конфиг тот же, что в seed_data."""
    import seed_data

    old = next(r for r in seed_data.INDICATORS if r["code"] == "consumer-credit")["model_config_json"]
    s = BY_FED["consumer-credit"]
    assert (old["dataservice"]["datasetId"], old["dataservice"]["element_id"]) == (s.dataset, s.element)
    assert old["value_divisor"] == s.divisor
    assert "закредитованность" in INDICATOR_SEO_KEYWORDS["consumer-credit"]
    codes = [r["code"] for r in seed_data.INDICATORS]
    assert len(codes) == len(set(codes))
    assert {"mortgage-issued", "mortgage-debt", "mortgage-term"} <= set(codes)


@pytest.mark.parametrize("code, ds, measure, period, value", [
    ("mortgage-issued", 45, 22, date(2026, 9, 1), 617.146),        # млрд руб. за сентябрь
    ("consumer-credit", 42, 22, date(2026, 9, 1), 37.6662),       # трлн руб. на 01.10.2026 = конец сентября
    ("consumer-credit-overdue", 43, 22, date(2026, 9, 1), 1806.733),
    ("mortgage-term", 48, 22, date(2026, 9, 1), 304.8),
])
def test_federal_points_match_the_source(monkeypatch, code, ds, measure, period, value):
    """Тот же разбор, что у cbr_dataservice_json: столбец «всего», сдвиг даты на месяц, делитель единицы."""
    from app.services import cbr_dataservice_parser as ds_parser

    class Resp:
        headers = {"content-type": "application/json"}
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return fixture(ds, measure)

    class Session:
        def get(self, *_a, **_k):
            return Resp()

        def close(self):
            pass

    monkeypatch.setattr(ds_parser, "create_session", lambda: Session())
    s = BY_FED[code]
    cfg = spec.dataservice_cfg(s)["dataservice"]
    points = ds_parser.fetch_dataservice(cfg["publicationId"], cfg["datasetId"], cfg["measureId"],
                                         cfg["element_id"], 2025, 2026, -1)
    got = dict(points)
    assert round(got[period] / s.divisor, 4) == value


# ── Регионы ──────────────────────────────────────────────────────────────────────────────────────

def test_regional_series_parse_month_and_unit():
    got = parser.parse_series(BY_FED["mortgage-issued"], fixture(45, 27))
    assert got[202609] == 7991.0 and got[202608] == 4349.0 and min(got) == 202501
    stock = parser.parse_series(BY_FED["consumer-credit"], fixture(42, 22))
    assert stock[202609] == 37666225.0 and stock[202501] == 34766820.0


def test_zero_term_is_a_gap_not_a_value():
    payload = {"RawData": [{"element_id": 36, "obs_val": 0.0, "dt": "Сентябрь 2026", "date": "2026-10-01T00:00:00"},
                           {"element_id": 36, "obs_val": 280.0, "dt": "Август 2026", "date": "2026-09-01T00:00:00"}]}
    assert parser.parse_series(BY_FED["mortgage-term"], payload) == {202608: 280.0}


def test_every_region_of_the_source_maps_to_a_catalogue_slug():
    from app.services.emiss_regional_parser import load_dimnames

    regions = json.loads((Path(__file__).parents[1] / "app/data/regional/regions.json").read_text())
    measures = [(int(r["id"]), r["name"]) for r in json.loads((FIXTURES / "measures_ds45.json").read_text())["measure"]]
    slugs, unknown = parser.measure_slugs(measures, load_dimnames(), {r["name"]: r["slug"] for r in regions})
    assert unknown == []
    assert len(slugs) == 96 and len(set(slugs.values())) == 96
    assert set(slugs.values()) <= {r["slug"] for r in regions}
    assert slugs[22] == "russia" and slugs[91] == "hanty-mansiyskiy-ao" and slugs[93] == "tyumenskaya-oblast-bez-ao"
    assert slugs[46] == "nenetskiy-ao" and slugs[45] == "arhangelskaya-oblast"


class _Result:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value

    def all(self):
        return self.value


class _Db:
    """Ответы в порядке запросов run_series_update: показатель, регионы, последний месяц ряда и России."""

    def __init__(self, last_any, last_rf):
        self.answers = [_Ind(), [("russia", 1, "Российская Федерация"), ("voronezhskaya-oblast", 2,
                                 "Воронежская область")], last_any, last_rf]

    async def execute(self, _stmt):
        return _Result(self.answers.pop(0))

    async def commit(self):
        pass

    async def rollback(self):
        pass


class _Ind:
    id = 7


def _wire(monkeypatch, written, published):
    async def upsert(db, values):
        written.extend(values)
        return len(values), 0

    async def noop(*_a, **_k):
        return 0

    async def publish():
        published.append(1)

    monkeypatch.setattr(parser, "_upsert_monthly_points", upsert)
    monkeypatch.setattr(parser, "acquire_regional_write_lock", noop)
    monkeypatch.setattr(parser, "update_regional_year_bounds", noop)
    monkeypatch.setattr(parser, "publish_committed_regional_changes", publish)


def test_first_run_loads_history_for_every_region(monkeypatch):
    calls, written, published = [], [], []
    measures = json.loads((FIXTURES / "measures_ds45.json").read_text())

    def get_json(url, params):
        calls.append(params)
        if url.endswith("/measures"):
            return measures
        return fixture(45, 22) if params["measureId"] == 22 else fixture(45, 27)

    _wire(monkeypatch, written, published)
    stats = asyncio.run(parser.run_series_update(
        _Db(None, None), BY_FED["mortgage-issued"], get_json=get_json, today=date(2026, 11, 19), pause=0,
        dimnames={"Воронежская область": "voronezhskaya-oblast"}))
    assert calls[0]["y1"] == 2019 and calls[0]["measureId"] == 22
    # Россия один раз (её ответ переиспользуется), Воронеж — свой запрос; остальные регионы не в базе теста.
    assert (7, 1, 202609, 617146.0) in written and (7, 2, 202609, 7991.0) in written
    assert stats["added"] == len(written) and published == [1]
    assert sum(1 for c in calls if c.get("measureId") == 22) == 1


def test_no_new_month_costs_one_request(monkeypatch):
    calls, written, published = [], [], []

    def get_json(url, params):
        calls.append(params)
        return fixture(45, 22)

    _wire(monkeypatch, written, published)
    stats = asyncio.run(parser.run_series_update(
        _Db(202609, 202609), BY_FED["mortgage-issued"], get_json=get_json, today=date(2026, 11, 19), pause=0))
    assert stats["skipped"] == 1 and len(calls) == 1 and calls[0]["y1"] == 2025
    assert written == [] and published == []


def test_regional_catalogue_rows_are_unique_translated_and_bridged():
    from app.services.seo_regional import MACRO_BY_TABLE

    rows = spec.artifact_rows()
    existing = json.loads((Path(__file__).parents[1] / "app/data/regional/indicators.json").read_text())
    assert len(rows) == 8
    assert not {r["code"] for r in rows} & {r["code"] for r in existing}
    assert not {r["table_code"] for r in rows} & {r["table_code"] for r in existing}
    for r in rows:
        assert r["section_num"] == 19 and r["frequency"] == "monthly"
        assert REGION_INDICATORS_EN[r["code"]]["name"]
        assert MACRO_BY_TABLE[r["table_code"]] == spec.SERIES_BY_REGIONAL[r["code"]].federal_code


def test_seed_appends_credit_rows():
    import seed_regional

    _regions, indicators = seed_regional.load_meta()
    by_code = {r["code"]: r for r in indicators}
    assert by_code["ipoteka-vydano-mes"]["section_name"] == "Финансы"
    assert by_code["kredity-fizlicam-dolg-mes"]["unit"] == "млн руб."


def test_monthly_page_texts_name_the_bank_of_russia():
    from app.services.seo_regional import _mt

    texts = spec.monthly_texts("ipoteka-vydano-mes", "ru")
    assert "Банка России" in _mt("faq_source_a", texts=texts)
    assert _mt("creator", texts=texts) == "Банк России"
    assert spec.monthly_texts("selhoz-cena-pshenica", "ru") is None
    assert spec.monthly_texts("ipoteka-vydano-mes", "en")["creator"] == "Bank of Russia"
