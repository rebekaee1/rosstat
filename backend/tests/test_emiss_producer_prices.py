"""ЕМИСС 57609, 57608, 57724, 57796, 63349: цены производителей и цены в строительстве России (19.11.2026).

Фикстуры — живые ответы dataGrid.do с Mac 19.11.2026 на те же запросы, что строит парсер (по одному на набор,
2017–2026, у 63349 — 2025–2026). Контрольные точки сверены со страницами показателей ЕМИСС.
"""
import asyncio
import json
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.data import emiss_producer_prices as registry
from app.data.emiss_producer_prices import DATASETS, SERIES, methodology, seed_indicators, seo_keywords, seo_meta
from app.data.i18n.indicator_copy_en import INDICATOR_COPY_EN
from app.data.indicator_seo import INDICATOR_SEO, INDICATOR_SEO_KEYWORDS
from app.services import emiss_producer_prices_parser as parser
from app.services.rosstat_cpi_parser import PARSER_REGISTRY

FIXTURES = Path(__file__).parent / "fixtures" / "emiss_producer_prices"
RF = "Российская Федерация"
RF_NEW = "Российская Федерация без учета новых субъектов (с 01.01.2023)"


def live_rows(dataset):
    return json.loads((FIXTURES / f"dataGrid_{dataset}_2026-11-19.json").read_text(encoding="utf-8"))["results"]


def points_of(code, rows=None, years=None):
    series = SERIES[code]
    years = years or range(series.spec.first_year, 2027)
    return {point.date: point.value for point in parser.parse_series(series, live_rows(series.dataset) if rows is None
                                                                     else rows, years)}


@pytest.mark.parametrize(("code", "count", "first", "checks"), [
    # Индекс 118,51 → +18,51 % за год; 2022 год — строка «Российская Федерация», 2023 — без новых субъектов.
    ("ppi-mining", 117, date(2017, 1, 1), {date(2017, 1, 1): 25.91, date(2026, 9, 1): 18.51}),
    ("ppi-petroleum-products", 117, date(2017, 1, 1), {date(2026, 9, 1): 26.55}),
    ("ppi-gasoline", 113, date(2017, 1, 1), {date(2026, 9, 1): -2.41}),
    ("ppi-diesel", 113, date(2017, 1, 1), {date(2026, 9, 1): 28.13}),
    ("ppi-crude-oil", 67, date(2021, 1, 1), {date(2021, 5, 1): 452.92, date(2026, 9, 1): 26.33}),
    ("ppi-construction", 116, date(2017, 1, 1), {date(2026, 8, 1): 7.19}),
    ("build-cost-housing", 21, date(2025, 1, 1), {date(2026, 9, 1): 13.42}),
    ("build-concrete", 117, date(2017, 1, 1), {date(2017, 1, 1): 4158.37, date(2026, 9, 1): 8199.05}),
    ("build-cement", 57, date(2022, 1, 1), {date(2026, 9, 1): 9730.2}),
    ("build-brick", 117, date(2017, 1, 1), {date(2026, 9, 1): 21786.74}),
])
def test_live_answers_give_monthly_history(code, count, first, checks):
    points = points_of(code)
    assert len(points) == count and min(points) == first, (len(points), min(points))
    for day, value in checks.items():
        assert points[day] == value


def test_every_series_has_history_up_to_the_last_published_month():
    for code, series in SERIES.items():
        points = points_of(code)
        latest = date(2026, 8, 1) if series.dataset == 57796 else date(2026, 9, 1)
        assert max(points) == latest, code
        assert min(points).year == series.start_year, code
        assert len(points) >= 15, code


def test_one_request_per_dataset_with_all_its_positions(monkeypatch):
    calls = []

    async def post(dataset, params):
        calls.append((dataset, params))
        return {"results": live_rows(dataset)}

    monkeypatch.setattr(parser, "_post_grid", post)
    parser._cache.clear()
    years = range(2017, 2027)
    for code in ("build-concrete", "build-brick", "build-timber"):
        asyncio.run(parser.fetch_series(SERIES[code], years))
    assert len(calls) == 1
    dataset, params = calls[0]
    filters = {value for key, value in params if key == "selectedFilterIds"}
    lines = [value for key, value in params if key == "lineObjectIds"]
    assert dataset == 57724 and lines == ["57939", "57956", "57831", "3"]
    assert {"0_57724", "30611_950351", "57939_1693127", "57939_1793407", "57956_1694826", "57956_1757957",
            "57831_1688487", "57831_1849012", "3_2017", "3_2026", "33560_1540283"} <= filters
    yoy = {value for key, value in parser.grid_params(DATASETS[57609], years) if key == "selectedFilterIds"}
    assert {"57937_1704141", "58601_1744136", "30611_950473", "57940_1692320"} <= yoy
    parser._cache.clear()


def test_russia_before_2023_and_without_new_regions_after():
    label = SERIES["ppi-energy"].label
    row = lambda territory, year, value: {"dim57940": label, "dim57831": territory, "dim3": year,
                                          "dim1540283_d1_i1": value}
    rows = [row(RF, "2022", "105,5"), row(RF_NEW, "2022", "104"), row(RF, "2023", "101"), row(RF_NEW, "2023", "98,2")]
    assert points_of("ppi-energy", rows, range(2022, 2024)) == {date(2022, 1, 1): 5.5, date(2023, 1, 1): -1.8}


def test_unit_row_of_another_unit_is_not_mixed_in():
    label = SERIES["build-cement"].label
    rows = [{"dim57939": label, "dim57956": "Тонна;^метрическая тонна (1000 кг)", "dim57831": RF_NEW, "dim3": "2024",
             "dim1540283_d1_i1": "8000"},
            {"dim57939": label, "dim57956": "Кубический метр", "dim57831": RF_NEW, "dim3": "2024",
             "dim1540283_d1_i1": "3000"}]
    assert points_of("build-cement", rows, range(2024, 2025)) == {date(2024, 1, 1): 8000.0}


def test_foreign_row_bad_value_and_empty_past_are_errors():
    other = {"dim57940": "Производство мебели", "dim57831": RF_NEW, "dim3": "2025", "dim1540283_d1_i1": "101"}
    with pytest.raises(ValueError, match="неожиданная строка"):
        points_of("ppi-wood", [other], range(2025, 2026))
    broken = {**other, "dim57940": SERIES["ppi-wood"].label, "dim1540283_d1_i1": "10405"}
    with pytest.raises(ValueError, match="недопустимое значение"):
        points_of("ppi-wood", [broken], range(2025, 2026))
    with pytest.raises(ValueError, match="нет опубликованных точек"):
        points_of("ppi-wood", [], range(2017, 2027))
    assert points_of("ppi-wood", [], range(date.today().year, date.today().year + 1)) == {}


def test_series_are_seeded_registered_translated_and_described_in_plain_words():
    rows = {row["code"]: row for row in seed_indicators()}
    assert set(rows) == set(SERIES) and len(SERIES) == 50
    assert PARSER_REGISTRY["rosstat_emiss_producer_prices"] is parser.EmissProducerPricesParser
    labels = {}
    for code, series in SERIES.items():
        # Ответ ЕМИСС называет позицию по имени: в одном наборе два ряда с одним именем смешались бы.
        assert labels.setdefault((series.dataset, series.label, series.unit_oid), code) == code
        row = rows[code]
        assert (row["frequency"], row["category"], row["is_active"]) == ("monthly", "Цены", True)
        assert row["unit"] == ("%" if series.spec.kind == "yoy" else series.unit)
        assert INDICATOR_COPY_EN[code]["name"] == series.name_en
        assert INDICATOR_COPY_EN[code]["methodology"] == methodology(series)[1]
        assert INDICATOR_SEO_KEYWORDS[code] == seo_keywords()[code]
        assert INDICATOR_SEO[code] == seo_meta()[code]
        for text in (row["description"], row["methodology"], *methodology(series)):
            assert str(series.dataset) not in text and "ЕМИСС" not in text and "парсер" not in text
    assert not {code for code in SERIES if code.startswith("steel")}, "сталь живёт в emiss_steel (57606)"
    assert "цена цемента" in seo_keywords()["build-cement"]
    assert "Ряд начинается с 2022 года" in rows["build-cement"]["methodology"]
    assert registry.KEYWORDS[57609] in INDICATOR_SEO_KEYWORDS["ppi-mining"]


# ── Поиск: то, что люди искали и не находили ──────────────────────────────────────────────────────

@pytest.fixture
def search_client(auth_env):
    from app.models import Indicator, IndicatorData

    async def seed():
        async with auth_env["session_maker"]() as db:
            rows = [Indicator(code="ppi", name="индекс цен производителей", name_en="Producer Price Index",
                              frequency="monthly", category="Финансы")]
            # SQLite не сворачивает регистр кириллицы: названия строчными, как в соседних тестах поиска.
            rows += [Indicator(code=code, name=series.name.lower(), name_en=series.name_en, frequency="monthly",
                               unit=series.unit, category="Цены", seo_keywords=seo_keywords()[code])
                     for code, series in SERIES.items()]
            db.add_all(rows)
            await db.flush()
            for row in rows:
                db.add(IndicatorData(indicator_id=row.id, date=date(2026, 9, 1), value=5))
            await db.commit()

    asyncio.run(seed())
    with TestClient(auth_env["app"]) as client:
        yield client


def found(client, q):
    response = client.get("/api/v1/search", params={"q": q})
    assert response.status_code == 200, response.text
    return [row.get("code") for row in response.json()["results"]]


@pytest.mark.parametrize(("q", "code"), [
    ("индексы цен производителей на строительную продукцию", "ppi-construction"),
    ("цена цемента", "build-cement"),
    ("щебень", "build-crushed-stone"),
    ("цена бетона", "build-concrete"),
    ("цена кирпича", "build-brick"),
    ("утеплитель", "build-insulation"),
    ("удорожание строительства", "build-cost-housing"),
    ("индексы цен по группам объектов капитального строительства", "build-cost-roads"),
    ("оптовая цена бензина", "ppi-gasoline"),
    ("цены производителей нефтепродукты", "ppi-petroleum-products"),
])
def test_people_find_new_series_by_their_words(search_client, q, code):
    codes = found(search_client, q)
    assert code in codes[:5], codes


@pytest.mark.parametrize("q", ["ицп по видам экономической деятельности",
                               "индексы цен производителей по видам экономической деятельности росстат"])
def test_producer_prices_by_activity_give_the_whole_activity_list(search_client, q):
    """Яндекс: «индексы цен производителей по видам экономической деятельности росстат» — все 14 видов, без товаров."""
    activities = {code for code, series in SERIES.items() if series.dataset == 57609}
    codes = found(search_client, q)
    assert set(codes) == activities, codes


def test_general_producer_price_query_still_leads_with_the_overall_index(search_client):
    assert found(search_client, "индекс цен производителей")[0] == "ppi"
