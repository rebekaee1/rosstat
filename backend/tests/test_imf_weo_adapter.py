"""IMF WEO adapter: fixture parse, no live network."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from app.services.imf_weo_adapter import (
    WEO_NGDPD,
    WEO_NGDPDPC,
    ImfWeoAdapter,
    parse_imf_weo_sdmx,
    points_for_iso3,
    weo_data_url,
    weo_iso3_for,
    weo_max_observation_year,
)


_FIXTURE = Path(__file__).parent / "fixtures" / "imf_weo_ngdpd_usa.json"


def test_parse_imf_weo_fixture_applies_billion_scale():
    payload = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    parsed = parse_imf_weo_sdmx(payload)
    points = points_for_iso3(parsed, "USA", "NGDPD")
    assert points == [
        (date(1980, 1, 1), 2857.325),
        (date(2023, 1, 1), 27811.5),
        (date(2024, 1, 1), 29298.025),
        (date(2025, 1, 1), 30767.075),
    ]
    assert all(item.weo_code == "NGDPD" for item in parsed)
    assert all(item.scale == 9 for item in parsed)


def test_parse_imf_weo_per_capita_scale_zero():
    payload = {
        "data": {
            "dataSets": [
                {
                    "series": {
                        "0:0:0": {
                            "attributes": [0],
                            "observations": {"0": ["82536.09461"], "1": ["86173.365243"]},
                        }
                    }
                }
            ],
            "structures": [
                {
                    "dimensions": {
                        "series": [
                            {"id": "COUNTRY", "values": [{"id": "USA"}]},
                            {"id": "INDICATOR", "values": [{"id": "NGDPDPC"}]},
                            {"id": "FREQUENCY", "values": [{"id": "A"}]},
                        ],
                        "observation": {
                            "TIME_PERIOD": None
                        },
                    },
                    "attributes": {"series": [{"id": "SCALE", "values": [{"id": "0"}]}]},
                }
            ],
        }
    }
    payload["data"]["structures"][0]["dimensions"]["observation"] = [
        {"id": "TIME_PERIOD", "values": [{"value": "2023"}, {"value": "2024"}]}
    ]
    points = points_for_iso3(parse_imf_weo_sdmx(payload), "USA", "NGDPDPC")
    assert points[0] == (date(2023, 1, 1), 82536.09461)
    assert points[1] == (date(2024, 1, 1), 86173.365243)


def test_adapter_lists_only_requested_weo_countries():
    adapter = ImfWeoAdapter(country_codes=["US", "DE", "RU", "XK", "US"])
    refs = []

    async def _collect():
        async for dataset in adapter.list_datasets():
            async for ref in adapter.list_series(dataset):
                refs.append(ref)

    import asyncio

    asyncio.run(_collect())
    countries = {ref.country_code for ref in refs}
    assert countries == {"US", "DE", "RU"}
    assert {ref.series_id for ref in refs} == {WEO_NGDPD, WEO_NGDPDPC}
    assert all(ref.provider == "imf" and ref.dataset_id == "WEO" for ref in refs)
    assert all(ref.frequency == "annual" for ref in refs)


def test_parse_drops_medium_term_weo_projection_years():
    payload = {
        "data": {
            "dataSets": [
                {
                    "series": {
                        "0:0:0": {
                            "attributes": [0],
                            "observations": {
                                "0": ["30000"],
                                "1": ["99999"],
                            },
                        }
                    }
                }
            ],
            "structures": [
                {
                    "dimensions": {
                        "series": [
                            {"id": "COUNTRY", "values": [{"id": "USA"}]},
                            {"id": "INDICATOR", "values": [{"id": "NGDPDPC"}]},
                            {"id": "FREQUENCY", "values": [{"id": "A"}]},
                        ],
                    },
                    "attributes": {"series": [{"id": "SCALE", "values": [{"id": "0"}]}]},
                }
            ],
        }
    }
    payload["data"]["structures"][0]["dimensions"]["observation"] = [
        {"id": "TIME_PERIOD", "values": [{"value": "2024"}, {"value": "2100"}]}
    ]
    points = points_for_iso3(parse_imf_weo_sdmx(payload), "USA", "NGDPDPC")
    assert points == [(date(2024, 1, 1), 30000.0)]
    assert weo_max_observation_year(date(2026, 8, 22)) == 2026


def test_weo_key_order_and_iso_map():
    assert weo_iso3_for("US") == "USA"
    assert weo_iso3_for("DE") == "DEU"
    assert weo_iso3_for("RU") == "RUS"
    assert weo_iso3_for("XK") is None
    assert weo_data_url(["USA"], "NGDPD").endswith("/USA.NGDPD.A")
