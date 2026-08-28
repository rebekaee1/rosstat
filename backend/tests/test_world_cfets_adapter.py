"""Unit tests for CFETS China Money adapter (mocked HTTP)."""

from __future__ import annotations

import asyncio
from datetime import date
from unittest.mock import MagicMock

import pytest

from app.services.world_adapters.cfets_chinamoney import (
    CfetsChinamoneyAdapter,
    CfetsChinamoneyError,
    CfetsSeriesSpec,
    create_adapter,
    normalize_dataset_id,
    parse_ccpr_records,
    parse_cfets_date,
    parse_keyed_rate_records,
)
from app.services.world_source_adapter import WorldSeriesRef

CCPR_FIXTURE = {
    "head": {"rep_code": "200"},
    "data": {"searchlist": ["USD/CNY"], "pageTotal": 1},
    "records": [
        {"date": "2026-08-12", "values": ["6.7882"]},
        {"date": "2026-08-11", "values": ["6.7900"]},
        {"date": "2026-08-10", "values": [""]},
    ],
}

LPR_FIXTURE = {
    "head": {"rep_code": "200"},
    "data": {"totalPageNum": 1},
    "records": [
        {"1Y": "3.00", "5Y": "3.50", "showDateCN": "2026-07-20"},
        {"1Y": "3.10", "5Y": "3.60", "showDateCN": "2026-06-20"},
    ],
}


def _run(coro):
    return asyncio.run(coro)


def test_parse_helpers():
    assert normalize_dataset_id("CCPR") == "ccpr"
    assert parse_cfets_date("2026-08-12") == date(2026, 8, 12)
    assert parse_cfets_date("20 Jul 2026") == date(2026, 7, 20)
    with pytest.raises(CfetsChinamoneyError):
        normalize_dataset_id("fx")


def test_parse_ccpr_and_lpr():
    obs = parse_ccpr_records(CCPR_FIXTURE, series_id="USD/CNY")
    assert [o.period for o in obs] == [date(2026, 8, 11), date(2026, 8, 12)]
    assert obs[-1].value == pytest.approx(6.7882)
    lpr = parse_keyed_rate_records(LPR_FIXTURE, series_id="1Y")
    assert lpr[0].value == pytest.approx(3.10)
    assert lpr[-1].period == date(2026, 7, 20)


def test_fetch_series_mocked():
    session = MagicMock()
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = CCPR_FIXTURE
    response.text = ""
    session.get.return_value = response
    adapter = CfetsChinamoneyAdapter(
        [
            CfetsSeriesSpec(
                series_id="USD/CNY",
                dataset_id="ccpr",
                unit_code="CNY_PER_USD",
                frequency="daily",
            )
        ],
        session=session,
        date_from=date(2026, 8, 1),
    )
    ref = WorldSeriesRef(
        provider="cfets",
        dataset_id="ccpr",
        series_id="USD/CNY",
        country_code="CN",
        frequency="daily",
        unit_code="CNY_PER_USD",
    )
    payload = _run(adapter.fetch_series(ref, date_from=date(2026, 8, 1), date_to=date(2026, 8, 12)))
    assert len(payload.observations) == 2
    assert create_adapter().provider == "cfets"
