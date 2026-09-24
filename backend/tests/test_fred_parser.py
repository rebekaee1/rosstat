"""Unit tests for FRED graph CSV parser."""

from __future__ import annotations

import asyncio
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pandas as pd

from app.services import fred_parser as fred_mod
from app.services.fred_parser import FredCsvParser, _parse_eia_brent_table, _parse_fred_csv


_SAMPLE_CSV = """observation_date,DTWEXBGS
2006-01-02,101.4155
2006-01-03,.
2006-01-04,100.2288
2010-06-15,95.5
"""

_LEGACY_DATE_CSV = """DATE,DGS10
1962-01-02,4.06
1962-01-03,.
1962-01-04,4.01
"""


def test_parse_fred_csv_skips_dots_and_supports_backfill():
    points = _parse_fred_csv(_SAMPLE_CSV, backfill_from=date(2006, 1, 3))
    assert points == [
        (date(2006, 1, 4), 100.2288),
        (date(2010, 6, 15), 95.5),
    ]


def test_parse_fred_csv_accepts_legacy_date_header():
    points = _parse_fred_csv(_LEGACY_DATE_CSV)
    assert points == [
        (date(1962, 1, 2), 4.06),
        (date(1962, 1, 4), 4.01),
    ]


def test_eia_brent_workbook_dates_and_missing_values():
    table = pd.DataFrame([
        ["Back to Contents", "Data 1: Europe Brent Spot Price FOB"],
        ["Sourcekey", "RBRTE"],
        ["Date", "Europe Brent Spot Price FOB"],
        ["2026-09-21", 116.15],
        ["2026-09-22", 114.89],
        ["2026-09-23", None],
    ])
    assert _parse_eia_brent_table(table) == [
        (date(2026, 9, 21), 116.15),
        (date(2026, 9, 22), 114.89),
    ]


def test_brent_uses_direct_eia_workbook(monkeypatch):
    monkeypatch.setattr(fred_mod, "_fetch_eia_brent", lambda: [(date(2026, 9, 22), 114.89)])
    indicator = SimpleNamespace(id=1, code="brent")
    fetch_log = SimpleNamespace(error_message=None)
    points, url = asyncio.run(FredCsvParser()._fetch_and_parse(
        AsyncMock(), indicator, {"fred_series_id": "DCOILBRENTEU"}, fetch_log,
    ))
    assert points == [(date(2026, 9, 22), 114.89)]
    assert url == fred_mod._EIA_BRENT_XLS


def test_fred_parser_fetches_configured_series(monkeypatch):
    fetched: list[str] = []

    def _fake_fetch(series_id: str) -> str:
        fetched.append(series_id)
        return _SAMPLE_CSV

    monkeypatch.setattr(fred_mod, "_fetch_fred_csv", _fake_fetch)

    indicator = SimpleNamespace(id=1, code="usd-index")
    fetch_log = SimpleNamespace(error_message=None)
    cfg = {
        "fred_series_id": "DTWEXBGS",
        "backfill_from": "2006-01-01",
    }
    points, url = asyncio.run(
        FredCsvParser()._fetch_and_parse(AsyncMock(), indicator, cfg, fetch_log)
    )

    assert fetched == ["DTWEXBGS"]
    assert "id=DTWEXBGS" in url
    assert points[0] == (date(2006, 1, 2), 101.4155)
    assert (date(2006, 1, 3),) not in {(d,) for d, _ in points}
    assert points[-1] == (date(2010, 6, 15), 95.5)


def test_fred_parser_requires_series_id():
    indicator = SimpleNamespace(id=1, code="usd-index")
    fetch_log = SimpleNamespace(error_message=None)
    points, url = asyncio.run(
        FredCsvParser()._fetch_and_parse(AsyncMock(), indicator, {}, fetch_log)
    )
    assert points == []
    assert "fred_series_id" in (fetch_log.error_message or "")
    assert url.endswith("fredgraph.csv")
