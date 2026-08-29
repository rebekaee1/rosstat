"""Census + IBGE population adapters: fixture parsing, no live network."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from app.services.br_pop_adapter import (
    IbgePopAdapter,
    parse_ibge_sidra_population,
)
from app.services.us_pop_adapter import (
    UsCensusPopAdapter,
    parse_census_pop_csv,
)

_FIXTURES = Path(__file__).parent / "fixtures"
_CENSUS_HIST = _FIXTURES / "census_popest_2020_alldata.csv"
_CENSUS_LATEST = _FIXTURES / "census_nst_est2025_alldata.csv"
_IBGE_ESTIMATES = _FIXTURES / "ibge_sidra_6579_br.json"
_IBGE_CENSUS = _FIXTURES / "ibge_sidra_1209_br.json"


def test_parse_census_fixtures_merges_vintages():
    text = _CENSUS_HIST.read_text(encoding="utf-8") + _CENSUS_LATEST.read_text(
        encoding="utf-8"
    )
    points = parse_census_pop_csv(text)
    # Оба винтажа: July estimates 2010-2020 и 2020-2025.
    assert date(2010, 7, 1) in points
    assert date(2019, 7, 1) in points
    assert date(2025, 7, 1) in points
    # Пересечение винтажей (2020) — побеждает свежий файл (последний wins).
    assert points[date(2020, 7, 1)] == 331449281
    # Конкретные официальные значения July 1 estimates.
    assert points[date(2024, 7, 1)] == 340110988
    assert points[date(2010, 7, 1)] == 309327663


def test_parse_quoted_sumlev_header_without_concat():
    points = parse_census_pop_csv(_CENSUS_HIST.read_text(encoding="utf-8"))
    assert points[date(2010, 7, 1)] == 309327663
    assert points[date(2020, 7, 1)] == 329484123


def test_parse_census_csv_skips_state_rows_and_garbage():
    text = (
        "SUMLEV,NAME,POPESTIMATE2023,POPESTIMATE2024\n"
        '"040","Alabama",5100000,5150000\n'
        '"010","United States",336755052,340110988\n'
    )
    assert parse_census_pop_csv(text) == {
        date(2023, 7, 1): 336755052,
        date(2024, 7, 1): 340110988,
    }
    assert parse_census_pop_csv("not a csv") == {}


def test_parse_census_2000_vintage_columns():
    text = (
        "SUMLEV,NAME,POPESTIMATE2000,POPESTIMATE2009\n"
        '"010","United States",282162411,306771529\n'
    )
    points = parse_census_pop_csv(text)
    assert points[date(2000, 7, 1)] == 282162411
    assert points[date(2009, 7, 1)] == 306771529


def test_parse_census_intercensal_july_only():
    text = (
        "YEAR,MONTH,TOT_POP\n"
        "2000,4,281424600\n"
        "2000,7,282162411\n"
        "2009,7,306771529\n"
        "2010,4,308745538\n"
        "2010,7,309349689\n"
    )
    points = parse_census_pop_csv(text)
    assert points == {
        date(2000, 7, 1): 282162411,
        date(2009, 7, 1): 306771529,
        date(2010, 7, 1): 309349689,
    }


def test_parse_ibge_fixtures_stitches_estimates_and_census():
    estimates = json.loads(_IBGE_ESTIMATES.read_text(encoding="utf-8"))
    census = json.loads(_IBGE_CENSUS.read_text(encoding="utf-8"))
    points = parse_ibge_sidra_population(estimates, census)
    # Оценки из таблицы 6579 (январская привязка).
    assert points[date(2021, 1, 1)] == 213317639
    assert points[date(2025, 1, 1)] == 213421037
    # Переписные годы дозаполняются переписью (2022) и не имеют дыр.
    assert points[date(2022, 1, 1)] == 203080756
    assert date(2023, 1, 1) not in points
    # До 1980 переписные точки отбрасываются (несопоставимая методология).
    assert date(1970, 1, 1) not in points
    assert date(1980, 1, 1) in points


def test_parse_ibge_payload_string_input():
    estimates = json.dumps(
        [
            {"D3C": "Ano", "V": "Valor"},
            {"D3C": "2024", "V": "212583750"},
        ]
    )
    census = "[]"
    assert parse_ibge_sidra_population(estimates, census) == {
        date(2024, 1, 1): 212583750
    }


def test_parse_ibge_skips_bad_rows():
    payload = [
        {"D3C": "Ano (Código)", "V": "Valor"},
        {"D3C": "2020", "V": "-5"},  # неположительное — мусор
        {"D3C": "20x4", "V": "100"},  # не год
        {"D3C": "2021", "V": "213317639"},
    ]
    assert parse_ibge_sidra_population(payload, []) == {
        date(2021, 1, 1): 213317639
    }


def test_adapter_contract_and_filters():
    async def _collect(adapter):
        return [s async for s in adapter.list_series(None)]

    us = UsCensusPopAdapter(
        fetch_csv=lambda url: (
            "YEAR,MONTH,TOT_POP\n2000,7,282162411\n2009,7,306771529\n2010,7,309349689\n"
            if "2000-2010" in url
            else _CENSUS_HIST.read_text(encoding="utf-8")
            if "2010-2020" in url
            else _CENSUS_LATEST.read_text(encoding="utf-8")
        )
    )
    ibge = IbgePopAdapter(
        fetch_json=lambda url: _IBGE_ESTIMATES.read_text(encoding="utf-8")
        if "6579" in url
        else _IBGE_CENSUS.read_text(encoding="utf-8")
    )
    assert us.provider == "census"
    assert ibge.provider == "ibge"
    assert us.public_source_name == "Бюро переписи населения США"
    assert ibge.public_source_name == (
        "Бразильский институт географии и статистики (IBGE)"
    )

    import asyncio

    us_series = asyncio.run(_collect(us))
    assert us_series[0].series_id == "us-population-census"
    assert us_series[0].country_code == "US"
    assert us_series[0].frequency == "annual"
    assert us_series[0].unit_code == "PERSONS"

    br_series = asyncio.run(_collect(ibge))
    assert br_series[0].series_id == "br-population-ibge"

    import asyncio

    payload = asyncio.run(
        us.fetch_series(us_series[0], date_from=date(2020, 1, 1))
    )
    assert payload.observations[0].period >= date(2020, 1, 1)
    assert payload.observations[-1].period == date(2025, 7, 1)
    assert payload.source_hash
    full_us = us.fetch_national_points()
    years = {period.year for period, _value in full_us}
    assert 2000 in years
    assert 2009 in years
    assert 2025 in years

    payload_br = asyncio.run(ibge.fetch_series(br_series[0]))
    assert payload_br.observations[0].period == date(1980, 1, 1)
    assert payload_br.observations[-1].period == date(2025, 1, 1)


def test_ibge_series_has_no_holes_since_1980():
    estimates = json.loads(_IBGE_ESTIMATES.read_text(encoding="utf-8"))
    census = json.loads(_IBGE_CENSUS.read_text(encoding="utf-8"))
    points = parse_ibge_sidra_population(estimates, census)
    years = {period.year for period in points}
    # Union: оценки 6579 + переписи ≥1980; 2023 официально не публикуется
    # (в год после переписи IBGE не даёт межпереписной оценки для Бразилии).
    assert years == {1980, 1991, 2000, 2010, 2021, 2022, 2024, 2025}
    assert 2023 not in years
