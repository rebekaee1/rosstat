"""ETL: CBR DataService aggregate parser — sums multiple DataService elements by date.

Used for indicators composed of several monetary components (e.g. total
individual deposits = transferable + term + FX deposits).

Config in indicator.model_config_json:
{
  "dataservice_components": [
    {"publicationId": 5, "datasetId": 6, "element_id": 16, "date_offset_months": 0},
    {"publicationId": 5, "datasetId": 7, "element_id": 22, "date_offset_months": 0},
    {"publicationId": 5, "datasetId": 8, "element_id": 26, "date_offset_months": 0},
  ],
  "backfill_from_year": 2010
}
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from datetime import date
from typing import ClassVar

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FetchLog, Indicator
from app.services.base_parser import BaseParser
from app.services.cbr_dataservice_parser import fetch_dataservice

logger = logging.getLogger(__name__)


class CbrDataServiceSumParser(BaseParser):
    parser_type: ClassVar[str] = "cbr_dataservice_sum"

    async def _fetch_and_parse(
        self,
        db: AsyncSession,
        indicator: Indicator,
        cfg: dict,
        fetch_log: FetchLog,
    ) -> tuple[list, str]:
        components = cfg.get("dataservice_components")
        if not components or not isinstance(components, list):
            raise ValueError("Missing 'dataservice_components' in model_config_json")

        year_from = int(cfg.get("backfill_from_year", 2010))
        year_to = date.today().year

        sums: dict[date, float] = defaultdict(float)
        for comp in components:
            date_offset = int(comp.get("date_offset_months", 0))
            comp_points = await asyncio.to_thread(
                fetch_dataservice,
                comp["publicationId"],
                comp["datasetId"],
                comp.get("measureId"),
                comp.get("element_id"),
                year_from,
                year_to,
                date_offset,
            )
            for dt, val in comp_points:
                sums[dt] += val

        points = [(dt, round(sums[dt], 2)) for dt in sorted(sums)]
        return points, f"cbr.ru/dataservice (sum of {len(components)} components)"
