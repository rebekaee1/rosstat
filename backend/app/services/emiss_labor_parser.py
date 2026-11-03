"""EMISS national labour ETL via the existing proxy-aware dataGrid transport.

Each request fixes the geography, sex and year. Periods are columns, so monthly
and annual cells keep their own keys. Historical coverage starts at the first
year allowed for the series. After backfill, refresh the last stored year and
subsequent years for revisions. Source omissions never delete stored history.
"""

from datetime import date
from math import isfinite
from typing import ClassVar

from sqlalchemy import func, select

from app.data.emiss_labor import AGES, SERIES, LaborSeries
from app.models import IndicatorData
from app.services.base_parser import BaseParser
from app.services.emiss_regional_parser import MONTH_OIDS, _post_grid, parse_ru_float
from app.services.rosstat_labor_parser import DataPoint

_PERIODS = {
    "monthly": MONTH_OIDS,
    "quarterly": {"1540222": 1, "1540224": 4, "1540226": 7, "1540227": 10},
    "annual": {"1558883": 1},
}
_TERRITORIES = {
    "1688487": "Российская Федерация",
    "1849012": "Российская Федерация без учета новых субъектов (с 01.01.2023)",
}


async def fetch_year(series: LaborSeries, year: int) -> list[DataPoint]:
    territory = "1849012" if year >= 2023 else "1688487"
    if series.dataset == 43913 and year == 2023:
        territory = "1688487"
    periods = _PERIODS[series.frequency]
    row_dimension = "58335" if series.age else "57831"
    row_oid = series.age or territory
    row_label = AGES[series.age] if series.age else _TERRITORIES[territory]
    filters = [
        f"0_{series.dataset}", f"3_{year}", f"57831_{territory}",
        "30611_950473" if series.unit == "%" else "30611_950459",
        *(f"33560_{oid}" for oid in periods),
    ]
    if series.age:
        filters.append(f"58335_{series.age}")
    if series.education:
        filters.append(f"58349_{series.education}")
    if series.sex:
        filters.append(f"58328_{series.sex}")

    payload = await _post_grid(series.dataset, [
        ("lineObjectIds", row_dimension),
        ("columnObjectIds", "33560"),
        *(("selectedFilterIds", value) for value in filters),
    ])
    rows = payload.get("results")
    if not isinstance(rows, list):
        raise ValueError(f"ЕМИСС {series.dataset}/{year}: нет массива результатов")

    points = {}
    for row in rows:
        if str(row.get(f"dim{row_dimension}")).strip() not in {row_oid, row_label}:
            raise ValueError(f"ЕМИСС {series.dataset}/{year}: неожиданный разрез")
        for key, raw in row.items():
            month = periods.get(key.removeprefix("dim").split("_d", 1)[0])
            if month is None or raw in (None, "", "-", "—"):
                continue
            value = parse_ru_float(raw)
            if value is None or not isfinite(value) or value < 0 or (series.unit == "%" and value > 100):
                raise ValueError(f"ЕМИСС {series.dataset}/{year}: недопустимое значение")
            day = date(year, month, 1)
            if day in points and points[day] != value:
                raise ValueError(f"ЕМИСС {series.dataset}/{year}: конфликт значений за {day}")
            points[day] = value
    # Annual observations for the previous year can still be awaiting publication.
    last_required_year = date.today().year - (2 if series.frequency == "annual" else 1)
    if not points and year <= last_required_year:
        raise ValueError(f"ЕМИСС {series.dataset}/{year}: нет опубликованных точек")
    return [DataPoint(day, points[day]) for day in sorted(points)]


class EmissLaborParser(BaseParser):
    parser_type: ClassVar[str] = "rosstat_emiss_labor"

    async def _fetch_and_parse(self, db, indicator, cfg, fetch_log):
        series = SERIES[indicator.code]
        latest = await db.scalar(
            select(func.max(IndicatorData.date)).where(IndicatorData.indicator_id == indicator.id)
        )
        first_year = max(series.first_year, latest.year - 1) if latest else series.first_year
        points = []
        for year in range(first_year, date.today().year + 1):
            points.extend(await fetch_year(series, year))
        return points, series.source_url
