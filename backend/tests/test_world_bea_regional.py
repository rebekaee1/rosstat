"""BEA regional catalog and official ZIP parsing invariants."""

from __future__ import annotations

import io
import zipfile

import pytest

from app.services.world_bea_regional import (
    archive_url, clean_geofips, extract_catalog_points, load_catalog,
    numeric_points, parse_number, parse_period,
)
from app.services.world_subnational_ingest import load_subnational_passport
from app.data.world_indicator_titles_ru import is_public_catalog_name


def test_bea_catalog_has_unique_country_state_pairs_and_source_identity():
    rows = load_catalog()
    assert len(rows) >= 1800
    assert len({row.code for row in rows}) == len(rows)
    assert len({row.national_code for row in rows}) == len(rows)
    assert {row.archive for row in rows} == {
        "SAGDP", "SAINC", "SQGDP", "SQINC", "SAPCE", "SARPP", "SASUMMARY",
    }
    assert all(row.name_ru and row.name_en and row.methodology_ru for row in rows)
    assert all(is_public_catalog_name(row.name_ru) for row in rows)
    assert all(row.source_url == archive_url(row.archive) for row in rows)


def test_bea_special_values_and_periods():
    assert clean_geofips(' "06000"') == "06000"
    assert parse_number("(NA)") is None
    assert parse_number("(D)") is None
    assert parse_number("1,234.5") == 1234.5
    assert parse_period("1929").isoformat() == "1929-01-01"
    assert parse_period("2026:Q2").isoformat() == "2026-04-01"
    assert parse_period("2026:Q5") is None
    assert numeric_points({"1997": "1.2", "1998": "(NA)", "1999": "2.5"}) == [
        (parse_period("1997"), 1.2), (parse_period("1999"), 2.5),
    ]


def _synthetic_summary_zip(line: str, *, start: int = 1998) -> bytes:
    geos = ["00000"] + [f"{r.fips}000" for r in load_subnational_passport("us").regions]
    header = "GeoFIPS,GeoName,LineCode,Description,Unit,1998,1999,2000\n"
    lines = [header]
    for geo in geos:
        first = "(NA)" if start > 1998 else "1"
        lines.append(f' "{geo}",Area,{line},Example,Dollars,{first},2,3\n')
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as bundle:
        bundle.writestr("SASUMMARY__ALL_AREAS_1998_2000.csv", "".join(lines))
    return out.getvalue()


def test_bea_extract_rejects_truncated_historical_floor():
    row = next(item for item in load_catalog() if item.archive == "SASUMMARY" and item.history_floor == "1998")
    payload = _synthetic_summary_zip(row.line, start=1999)
    states = {f"{r.fips}000" for r in load_subnational_passport("us").regions}
    with pytest.raises(ValueError, match="lost its national historical floor"):
        extract_catalog_points("SASUMMARY", payload, (row,), states)


def test_bea_extract_keeps_us_and_all_51_states():
    row = next(item for item in load_catalog() if item.archive == "SASUMMARY" and item.history_floor == "1998")
    payload = _synthetic_summary_zip(row.line)
    states = {f"{r.fips}000" for r in load_subnational_passport("us").regions}
    found = extract_catalog_points("SASUMMARY", payload, (row,), states)
    assert len(found[row.code]) == 52
    assert found[row.code]["06000"][0] == (parse_period("1998"), 1.0)


def test_bea_catalog_units_are_bilingual_without_cyrillic_en_storage():
    """Catalog stores official BEA English in ``unit`` and Russian in ``unit_ru``."""
    import re

    from app.services.world_bea_regional import load_catalog

    cyr = re.compile(r"[А-Яа-яЁё]")
    rows = load_catalog()
    assert len(rows) >= 1500
    shared_neutral = {"%", "п. п."}  # identical or already-latin on both locales
    for row in rows:
        assert row.unit and not cyr.search(row.unit), row.code
        assert row.unit_ru, row.code
        if row.unit_ru not in shared_neutral and row.unit_ru != "%":
            assert cyr.search(row.unit_ru), row.code
