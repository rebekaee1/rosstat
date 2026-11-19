"""ЕМИСС 57606: цены производителей стали в России (19.11.2026).

Фикстура — живой ответ dataGrid.do с Mac 19.11.2026: три позиции, канал «Внутренний рынок», рубль за тонну,
2017–2026. Контрольные точки сверены вторым живым запросом с каналами в строках.
"""
import asyncio
import json
from datetime import date
from pathlib import Path

import pytest

from app.data.emiss_steel import KEYWORDS, SERIES, seed_indicators, seo_keywords, seo_meta
from app.data.i18n.indicator_copy_en import INDICATOR_COPY_EN
from app.data.indicator_seo import INDICATOR_SEO, INDICATOR_SEO_KEYWORDS
from app.data.legacy_redirects import resolve_legacy_indicator
from app.services import emiss_steel_parser
from app.services import site_paths as paths
from app.services.rosstat_cpi_parser import PARSER_REGISTRY
from app.services.search_language import measure_matches

FIXTURE = Path(__file__).parent / "fixtures" / "emiss_steel" / "dataGrid_57606_2026-11-19.json"
RF = "Российская Федерация"
RF_NEW = "Российская Федерация без учета новых субъектов (с 01.01.2023)"


def live_rows(code):
    rows = json.loads(FIXTURE.read_text(encoding="utf-8"))["results"]
    return [row for row in rows if row["dim57939"] == SERIES[code].label]


def run(monkeypatch, code, rows, years):
    seen = {}

    async def post(dataset, params):
        seen["dataset"], seen["params"] = dataset, params
        return {"results": rows}

    monkeypatch.setattr(emiss_steel_parser, "_post_grid", post)
    points = asyncio.run(emiss_steel_parser.fetch_series(SERIES[code], years))
    filters = {value for key, value in seen["params"] if key == "selectedFilterIds"}
    return {point.date: point.value for point in points}, seen["dataset"], filters


@pytest.mark.parametrize(("code", "checks"), [
    ("steel-hot-rolled", {date(2017, 1, 1): 34380.35, date(2022, 12, 1): 50095.7, date(2026, 9, 1): 54556.33}),
    ("steel-rebar", {date(2017, 1, 1): 27256.16, date(2023, 1, 1): 36295.74, date(2026, 9, 1): 52167.91}),
    ("steel-pipes", {date(2017, 1, 1): 34353.28, date(2022, 12, 1): 54198.82, date(2026, 9, 1): 57548.74}),
])
def test_live_answer_gives_whole_monthly_history(monkeypatch, code, checks):
    points, dataset, filters = run(monkeypatch, code, live_rows(code), range(2017, 2027))
    assert dataset == 57606
    assert len(points) == 117 and min(points) == date(2017, 1, 1) and max(points) == date(2026, 9, 1)
    for day, value in checks.items():
        assert points[day] == value
    assert {"0_57606", "30611_950351", "57956_1694829", "58601_1744136", f"57939_{SERIES[code].product}",
            "57831_1688487", "57831_1849012", "3_2017", "3_2026", "33560_1540283"} <= filters


def test_russia_before_2023_and_without_new_regions_after(monkeypatch):
    row = lambda territory, year, value: {"dim57939": SERIES["steel-pipes"].label, "dim57831": territory, "dim3": year,
                                          "dim1540283_d1_i1": value}
    rows = [row(RF, "2022", "50 000,5"), row(RF_NEW, "2022", "49000"), row(RF, "2023", "51000"), row(RF_NEW, "2023", "52000")]
    points, _, _ = run(monkeypatch, "steel-pipes", rows, range(2022, 2024))
    assert points == {date(2022, 1, 1): 50000.5, date(2023, 1, 1): 52000.0}


def test_foreign_product_unit_failure_and_old_empty_answer_are_errors(monkeypatch):
    other = {"dim57939": "Трубы круглого сечения прочие стальные", "dim57831": RF_NEW, "dim3": "2025", "dim1540283_d1_i1": "1"}
    with pytest.raises(ValueError, match="неожиданная строка"):
        run(monkeypatch, "steel-pipes", [other], range(2025, 2026))
    wrong_unit = {**other, "dim57939": SERIES["steel-pipes"].label, "dim1540283_d1_i1": "1204626,51"}
    with pytest.raises(ValueError, match="недопустимое значение"):
        run(monkeypatch, "steel-pipes", [wrong_unit], range(2025, 2026))
    with pytest.raises(ValueError, match="нет опубликованных точек"):
        run(monkeypatch, "steel-rebar", [], range(2017, 2027))
    points, _, _ = run(monkeypatch, "steel-rebar", [], range(date.today().year, date.today().year + 1))
    assert points == {}


def test_series_are_seeded_registered_translated_found_and_old_steel_leads_here():
    rows = {row["code"]: row for row in seed_indicators()}
    assert set(rows) == set(SERIES) == {"steel-hot-rolled", "steel-rebar", "steel-pipes"}
    assert PARSER_REGISTRY["rosstat_emiss_steel"] is emiss_steel_parser.EmissSteelParser
    for code, series in SERIES.items():
        row = rows[code]
        assert (row["frequency"], row["category"], row["unit"], row["is_active"]) == ("monthly", "Товарные рынки", "руб./т", True)
        assert INDICATOR_COPY_EN[code]["name"] == series.name_en and INDICATOR_COPY_EN[code]["unit"] == "RUB/t"
        assert INDICATOR_SEO_KEYWORDS[code] == seo_keywords()[code] and KEYWORDS in INDICATOR_SEO_KEYWORDS[code]
        assert INDICATOR_SEO[code] == seo_meta()[code]
        # Поиск «сталь» отличает цену стали от посуды из стали только по названию ряда.
        assert measure_matches((("steel",),), code=code, names=(series.name.lower(), series.name_en.lower()))
        for text in (row["description"], row["methodology"], INDICATOR_COPY_EN[code]["methodology"]):
            assert "57606" not in text and "ЕМИСС" not in text and "парсер" not in text
    assert "арматура" in seo_keywords()["steel-rebar"]
    assert resolve_legacy_indicator("steel") == paths.russia_indicator("steel-hot-rolled")
