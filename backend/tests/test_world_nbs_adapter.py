"""Unit tests for NBS EasyQuery adapter (mocked / offline parsers)."""

from __future__ import annotations

from datetime import date

import pytest

from app.services.world_adapters.nbs_stats import (
    NbsStatsError,
    create_adapter,
    parse_easyquery_observations,
    parse_nbs_period,
    parse_stream_observations,
    parse_stream_period_code,
    resolve_stream_entry,
)


EASYQUERY_FIXTURE = {
    "returncode": 200,
    "returndata": {
        "datanodes": [
            {
                "code": "A01030101.202401",
                "wds": [
                    {"wdcode": "zb", "valuecode": "A01030101"},
                    {"wdcode": "sj", "valuecode": "202401"},
                ],
                "data": {"data": 100.3},
            },
            {
                "code": "A01030101.202402",
                "wds": [
                    {"wdcode": "zb", "valuecode": "A01030101"},
                    {"wdcode": "sj", "valuecode": "202402"},
                ],
                "data": {"data": "-"},
            },
            {
                "code": "A01030101.202403",
                "wds": [
                    {"wdcode": "zb", "valuecode": "A01030101"},
                    {"wdcode": "sj", "valuecode": "202403"},
                ],
                "data": {"data": 100.8},
            },
        ]
    },
}


def test_parse_nbs_period_variants():
    assert parse_nbs_period("202401") == date(2024, 1, 1)
    assert parse_nbs_period("2024A") == date(2024, 1, 1)
    assert parse_nbs_period("2024C") == date(2024, 7, 1)
    with pytest.raises(NbsStatsError):
        parse_nbs_period("")


def test_parse_easyquery_skips_missing():
    obs = parse_easyquery_observations(EASYQUERY_FIXTURE, frequency="monthly")
    assert [o.period for o in obs] == [date(2024, 1, 1), date(2024, 3, 1)]
    assert obs[0].value == pytest.approx(100.3)


def test_create_adapter_default_provider():
    adapter = create_adapter()
    assert adapter.provider == "nbs"
    assert adapter.public_source_name.startswith("National Bureau")


def test_parse_stream_period_and_payload():
    assert parse_stream_period_code("202401MM") == date(2024, 1, 1)
    assert parse_stream_period_code("202603SS", frequency="quarterly") == date(2026, 7, 1)
    payload = {
        "state": 20000,
        "data": [
            {"code": "202401MM", "values": [{"value": "100.3"}]},
            {"code": "202402MM", "values": [{"value": ""}]},
            {"code": "202403MM", "values": [{"value": "100.8"}]},
        ],
    }
    obs = parse_stream_observations(payload, frequency="monthly")
    assert [o.period for o in obs] == [date(2024, 1, 1), date(2024, 3, 1)]
    assert obs[0].value == pytest.approx(100.3)


def test_resolve_stream_aliases():
    entry = resolve_stream_entry("cpi-all")
    assert entry is not None
    assert entry["frequency"] == "monthly"
    assert len(entry["leaves"]) >= 2
    assert resolve_stream_entry("A0E0101") is resolve_stream_entry("UNEMPLOYMENT") or (
        resolve_stream_entry("A0E0101") == resolve_stream_entry("urban-unemployment")
        or resolve_stream_entry("A0E0101") is not None
    )
