"""Свежесть региональных строк выдачи (14.11.2026): ноль и давнее значение — ниже, но не выкидываются."""
from app.services.search_regional_groups import demote_stale_region_rows


def row(code, year=None, value=1.0, kind="region_indicator"):
    item = {"kind": kind, "code": code, "key": code}
    if year is not None:
        item["latest"] = {"value": value, "date": f"{year}-01-01"}
    return item


def codes(rows):
    return [r["code"] for r in rows]


def test_zero_and_old_rows_go_below_fresh_ones_within_regional_slots():
    rows = [row("potato", 2024), row("flax", 2010, 0.0), row("veg", 2024), row("crops", 2024),
            row("old", 2019, 5.0), row("barley", 2021)]
    out = demote_stale_region_rows(rows)
    assert codes(out) == ["potato", "veg", "crops", "barley", "flax", "old"]
    assert sorted(codes(out)) == sorted(codes(rows))  # ничего не выкинуто


def test_other_kinds_and_rows_without_value_keep_their_places():
    rows = [row("country", kind="country"), row("flax", 2010, 0.0), row("russia-cpi", kind="russia"),
            row("potato", 2024), row("unvalued")]
    out = demote_stale_region_rows(rows)
    assert codes(out) == ["country", "potato", "russia-cpi", "flax", "unvalued"]


def test_fresh_list_is_unchanged_and_three_years_is_not_stale():
    rows = [row("a", 2024), row("b", 2021), row("c", 2023)]
    assert demote_stale_region_rows(rows) is rows
    assert demote_stale_region_rows([row("only", 2001, 0.0)]) == [row("only", 2001, 0.0)]
