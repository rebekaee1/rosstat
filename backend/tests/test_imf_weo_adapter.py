"""IMF WEO adapter: fixture parse, no live network."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from app.services.imf_weo_adapter import (
    WEO_GGXCNL_NGDP,
    WEO_GGXWDG_NGDP,
    WEO_NGDPD,
    WEO_NGDPDPC,
    ImfWeoAdapter,
    parse_imf_weo_sdmx,
    points_for_iso3,
    weo_data_url,
    weo_iso3_for,
    weo_max_observation_year,
    weo_methodology,
    weo_series_meta,
    world_indicator_code,
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
    assert {ref.series_id for ref in refs} == {
        WEO_NGDPD,
        WEO_NGDPDPC,
        WEO_GGXCNL_NGDP,
        WEO_GGXWDG_NGDP,
    }
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
    # Политика года поточной серии: последний закрытый год, не текущий.
    assert weo_max_observation_year(WEO_NGDPDPC, date(2026, 8, 22)) == 2025
    assert weo_max_observation_year(WEO_GGXWDG_NGDP, date(2026, 8, 22)) == 2025


def test_flow_series_does_not_get_running_year_observation():
    """Негативный: оценка незакрывшегося года не пишется наблюдением поточной серии.

    WEO публикует за текущий год оценку; для поточных показателей она не
    является закрытым календарным итогом и в шапку рейтинга попадать не
    должна (текущий год исключается, предыдущий включается). Годы
    динамические: тест остаётся верным в любом календарном году.
    """
    running_year = date.today().year
    last_closed_year = running_year - 1
    payload = {
        "data": {
            "dataSets": [
                {
                    "series": {
                        "0:0:0": {"attributes": [0], "observations": {"0": ["55.5"], "1": ["57.1"]}}
                    }
                }
            ],
            "structures": [
                {
                    "dimensions": {
                        "series": [
                            {"id": "COUNTRY", "values": [{"id": "USA"}]},
                            {"id": "INDICATOR", "values": [{"id": WEO_GGXWDG_NGDP}]},
                            {"id": "FREQUENCY", "values": [{"id": "A"}]},
                        ],
                        "observation": [
                            {
                                "id": "TIME_PERIOD",
                                "values": [
                                    {"value": str(last_closed_year)},
                                    {"value": str(running_year)},
                                ],
                            }
                        ],
                    },
                    "attributes": {"series": [{"id": "SCALE", "values": [{"id": "0"}]}]},
                }
            ],
        }
    }
    parsed = parse_imf_weo_sdmx(payload)
    points = points_for_iso3(parsed, "USA", WEO_GGXWDG_NGDP)
    assert points == [(date(last_closed_year, 1, 1), 55.5)]

    adapter = ImfWeoAdapter(
        country_codes=["US"], fetch_json=lambda _url: payload
    )
    fetched = adapter.fetch_weo_code(WEO_GGXWDG_NGDP, ["USA"])
    assert [(item.period, item.value) for item in fetched] == [
        (date(last_closed_year, 1, 1), 55.5)
    ]


def test_ggxwdg_debt_series_meta_public_copy():
    """Госдолг: проценты ВВП, RU-overlay-код, человеческие ключевые слова."""
    meta = weo_series_meta(WEO_GGXWDG_NGDP)
    assert meta["unit"] == "PC_GDP"
    assert meta["unit_ru"] == "% ВВП"
    assert meta["russia_indicator_code"] == "weo-government-debt-gdp"
    assert world_indicator_code("DE", WEO_GGXWDG_NGDP) == "de-weo-ggxwdg"
    methodology_ru = weo_methodology(WEO_GGXWDG_NGDP)
    assert "долг" in methodology_ru
    assert WEO_GGXWDG_NGDP not in methodology_ru  # без кодов серий в публичных текстах


def test_parse_ggxcnl_ngdp_scale_zero_percent_values():
    """Баланс бюджета: SCALE=0 — значения приходят сразу в процентах ВВП."""
    payload = {
        "data": {
            "dataSets": [
                {
                    "series": {
                        "0:0:0": {
                            "attributes": [0],
                            "observations": {"0": ["-2.39486"], "1": ["1.8"]},
                        }
                    }
                }
            ],
            "structures": [
                {
                    "dimensions": {
                        "series": [
                            {"id": "COUNTRY", "values": [{"id": "RUS"}]},
                            {"id": "INDICATOR", "values": [{"id": "GGXCNL_NGDP"}]},
                            {"id": "FREQUENCY", "values": [{"id": "A"}]},
                        ],
                    },
                    "attributes": {"series": [{"id": "SCALE", "values": [{"id": "0"}]}]},
                }
            ],
        }
    }
    payload["data"]["structures"][0]["dimensions"]["observation"] = [
        {"id": "TIME_PERIOD", "values": [{"value": "2024"}, {"value": "2025"}]}
    ]
    parsed = parse_imf_weo_sdmx(payload)
    points = points_for_iso3(parsed, "RUS", "GGXCNL_NGDP")
    assert points == [
        (date(2024, 1, 1), -2.39486),
        (date(2025, 1, 1), 1.8),
    ]
    assert all(item.scale == 0 for item in parsed)
    from app.services.imf_weo_adapter import WEO_GGXCNL_NGDP, weo_methodology

    meta = weo_series_meta(WEO_GGXCNL_NGDP)
    assert meta["unit"] == "PC_GDP"
    assert meta["unit_ru"] == "% ВВП"
    assert meta["russia_indicator_code"] == "weo-budget-balance-gdp"
    assert world_indicator_code("RU", WEO_GGXCNL_NGDP) == "ru-weo-ggxcnl"
    assert "ВВП" not in weo_methodology(WEO_GGXCNL_NGDP).replace(
        "валового внутреннего продукта", ""
    )
    assert "процентах от валового внутреннего продукта" in weo_methodology(
        WEO_GGXCNL_NGDP
    )
    assert weo_iso3_for("US") == "USA"
    assert weo_iso3_for("DE") == "DEU"
    assert weo_iso3_for("RU") == "RUS"
    assert weo_iso3_for("XK") is None
    assert weo_data_url(["USA"], "NGDPD").endswith("/USA.NGDPD.A")
