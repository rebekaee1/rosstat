"""ЕМИСС: распределение доходов и зарплат России (18.11.2026). Ответы повторяют живой dataGrid.do 18.11.2026."""
import asyncio
from datetime import date

import pytest

from app.data.emiss_income import KEYWORDS, SERIES, seed_indicators, seo_keywords
from app.data.i18n.indicator_copy_en import INDICATOR_COPY_EN
from app.services import emiss_income_parser
from app.services.rosstat_cpi_parser import PARSER_REGISTRY

RF = "Российская Федерация"
RF_NEW = "Российская Федерация без учета новых субъектов (с 01.01.2023)"


def run(monkeypatch, code, rows, years):
    series = SERIES[code]
    seen = {}

    async def post(dataset, params):
        seen["dataset"], seen["params"] = dataset, params
        return {"results": rows}

    monkeypatch.setattr(emiss_income_parser, "_post_grid", post)
    points = asyncio.run(emiss_income_parser.fetch_series(series, years))
    filters = {value for key, value in seen["params"] if key == "selectedFilterIds"}
    return [(point.date, point.value) for point in points], seen["dataset"], filters


def test_gini_takes_russia_before_2023_and_without_new_regions_after(monkeypatch):
    rows = [
        {"dim57831": RF, "dim3": "2022", "dim1558883_d40282549_i2187": "0,398"},
        {"dim57831": RF, "dim3": "2023", "dim1558883_d40282549_i2190": "0,404"},
        {"dim57831": RF_NEW, "dim3": "2023", "dim1558883_d106692272_i2179": "0,405"},
        {"dim57831": RF_NEW, "dim3": "2025", "dim1558883_d106692272_i2194": "0,422"},
    ]
    points, dataset, filters = run(monkeypatch, "income-gini", rows, range(2022, 2027))
    assert dataset == 31165
    assert points == [(date(2022, 1, 1), 0.398), (date(2023, 1, 1), 0.405), (date(2025, 1, 1), 0.422)]
    assert {"0_31165", "30611_1341910", "33560_1558883", "57831_1688487", "57831_1849012", "3_2022", "3_2026"} <= filters


def test_years_before_2023_published_only_without_new_regions_are_kept(monkeypatch):
    """Доли 20-процентных групп за 2011–2022 ЕМИСС отдаёт только строкой «без учета новых субъектов»."""
    rows = [
        {"dim57831": RF, "dim3": "2010", "dim1558883_d1_i1": "5,2"},
        {"dim57831": RF_NEW, "dim3": "2011", "dim1558883_d2_i2": "5,3"},
    ]
    points, _, _ = run(monkeypatch, "income-share-quintile-1", rows, range(2010, 2012))
    assert points == [(date(2010, 1, 1), 5.2), (date(2011, 1, 1), 5.3)]


def test_quintile_and_wage_decile_fix_their_group(monkeypatch):
    _, _, filters = run(monkeypatch, "income-share-quintile-5", [], range(2025, 2027))
    assert "58814_1750931" in filters and "30611_950473" in filters
    rows = [{"dim57831": RF_NEW, "dim3": "2025", "dim1540229_d1_i2": "315835"}]
    points, dataset, filters = run(monkeypatch, "wages-decile-10", rows, range(2025, 2027))
    assert dataset == 58031 and points == [(date(2025, 1, 1), 315835.0)]
    assert {"58334_1709528", "57940_1692933", "33560_1540229", "30611_950351"} <= filters


def test_unexpected_territory_and_bad_share_are_errors(monkeypatch):
    with pytest.raises(ValueError, match="неожиданная строка"):
        run(monkeypatch, "income-gini", [{"dim57831": "Москва", "dim3": "2024", "dim1558883_x": "0,4"}], range(2024, 2025))
    with pytest.raises(ValueError, match="недопустимое значение"):
        run(monkeypatch, "income-share-top10", [{"dim57831": RF, "dim3": "2020", "dim1558883_x": "130"}], range(2020, 2021))


def test_old_empty_answer_is_a_source_failure(monkeypatch):
    with pytest.raises(ValueError, match="нет опубликованных точек"):
        run(monkeypatch, "income-gini", [], range(1992, 2027))
    points, _, _ = run(monkeypatch, "income-gini", [], range(2026, 2027))
    assert points == []


def test_every_series_is_seeded_registered_translated_and_findable():
    rows = {row["code"]: row for row in seed_indicators()}
    assert set(rows) == set(SERIES) and len(rows) == 20
    assert PARSER_REGISTRY["rosstat_emiss_income"] is emiss_income_parser.EmissIncomeParser
    keywords = seo_keywords()
    for code, series in SERIES.items():
        assert rows[code]["frequency"] == "annual" and rows[code]["category"] == "Рынок труда"
        assert INDICATOR_COPY_EN[code]["name"] == series.name_en and INDICATOR_COPY_EN[code]["unit"]
        assert keywords[code].startswith(series.name) and KEYWORDS[series.topic] in keywords[code]
    assert "распределение доходов" in keywords["income-gini"] and "распределение зарплат" in keywords["wages-decile-1"]
