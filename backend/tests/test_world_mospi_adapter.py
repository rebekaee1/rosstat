"""Unit tests for MoSPI Open API adapter (offline parsers)."""

from __future__ import annotations

from datetime import date

import pytest

from app.services.world_adapters.mospi_api import (
    MospiApiError,
    create_adapter,
    parse_indian_fy_quarter,
    parse_month_token,
    parse_mospi_rows,
    parse_plfs_annual_period,
)


def test_period_helpers():
    assert parse_month_token("January") == 1
    assert parse_month_token(7) == 7
    assert parse_indian_fy_quarter("2024-25", "Q1") == date(2024, 4, 1)
    assert parse_indian_fy_quarter("2024-25", "Q4") == date(2025, 1, 1)
    assert parse_plfs_annual_period("2023-24") == date(2023, 4, 1)


def test_parse_cpi_and_fx_rows():
    cpi_rows = [
        {
            "year": 2024,
            "month": "January",
            "state": "All India",
            "sector": "Combined",
            "group": "General",
            "subgroup": "General-Overall",
            "index": "188.5",
        },
        {
            "year": 2024,
            "month": "January",
            "state": "All India",
            "sector": "Combined",
            "group": "Food and Beverages",
            "subgroup": "Food and Beverages-Overall",
            "index": "190.0",
        },
    ]
    obs = parse_mospi_rows(
        cpi_rows,
        dataset_id="CPI",
        dims={
            "group_name": "General",
            "subgroup_name": "General-Overall",
            "sector_name": "Combined",
            "state_name": "All India",
        },
    )
    assert len(obs) == 1
    assert obs[0].period == date(2024, 1, 1)
    assert obs[0].value == pytest.approx(188.5)

    fx_rows = [
        {
            "year": "2025",
            "month": "July",
            "currency": "US Dollar",
            "value": "86.11",
        },
        {
            "year": "2025",
            "month": "July",
            "currency": "Euro",
            "value": "100.64",
        },
    ]
    fx = parse_mospi_rows(
        fx_rows,
        dataset_id="RBI",
        dims={"currency": "US Dollar"},
    )
    assert len(fx) == 1
    assert fx[0].value == pytest.approx(86.11)


def test_parse_rejects_empty_match():
    with pytest.raises(MospiApiError):
        parse_mospi_rows(
            [{"year": 2024, "month": "January", "group": "Food", "index": "1"}],
            dataset_id="CPI",
            dims={"group_name": "General", "sector_name": "Combined"},
        )


def test_create_adapter_default():
    adapter = create_adapter()
    assert adapter.provider == "mospi"


def test_open_api_pagination_never_exceeds_200_rows_per_request():
    calls = []

    class Session:
        def get(self, _url, *, params, timeout):
            calls.append((params, timeout))

            class Response:
                status_code = 200
                text = ""

                def json(self):
                    return {"data": [{"page": params["page"]}], "meta_data": {"totalPages": 101}}

            return Response()

    adapter = create_adapter()
    adapter._session = Session()
    rows = adapter._fetch_all_rows_sync("CPI", {})
    assert len(rows) == 100
    assert [p["page"] for p, _ in calls] == [str(i) for i in range(1, 101)]
    assert {p["limit"] for p, _ in calls} == {"200"}
