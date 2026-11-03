import asyncio
from datetime import date

import pytest

from app.data.emiss_labor import SERIES
from app.services import emiss_labor_parser


@pytest.mark.parametrize(
    "code,year,territory,dimension,label,cells,expected",
    [
        (
            "unemployment-youth-women", 2026, "1849012", "58335", "15-24 лет",
            {"dim1540228_d123_i456": "11,1", "dim1540224_d123_i457": "8,6"},
            [(date(2026, 8, 1), 11.1)],
        ),
        (
            "registered-unemployment-share", 2023, "1688487", "57831", "Российская Федерация",
            {"dim1558883_d123_i456": "20,5", "dim1540222_d123_i457": "19"},
            [(date(2023, 1, 1), 20.5)],
        ),
        (
            "registered-unemployment-share-quarterly", 2020, "1688487", "57831", "Российская Федерация",
            {"dim1540226_d123_i456": "74,4", "dim1558883_d123_i457": "54,9"},
            [(date(2020, 7, 1), 74.4)],
        ),
    ],
)
def test_fetch_year_keeps_selected_period_and_territory(
    monkeypatch, code, year, territory, dimension, label, cells, expected
):
    series = SERIES[code]

    async def post(dataset, params):
        assert dataset == series.dataset
        assert ("lineObjectIds", dimension) in params
        assert ("columnObjectIds", "33560") in params
        filters = {value for key, value in params if key == "selectedFilterIds"}
        assert {part for part in filters if part.startswith("57831_")} == {f"57831_{territory}"}
        assert f"3_{year}" in filters
        if series.sex:
            assert {part for part in filters if part.startswith("58328_")} == {f"58328_{series.sex}"}
        return {"results": [{f"dim{dimension}": label, **cells}]}

    monkeypatch.setattr(emiss_labor_parser, "_post_grid", post)
    points = asyncio.run(emiss_labor_parser.fetch_year(series, year))
    assert [(point.date, point.value) for point in points] == expected
