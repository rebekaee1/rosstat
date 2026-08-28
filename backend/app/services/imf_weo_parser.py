"""Российский ETL-парсер IMF WEO — только overlay-ряды RU.

Мировой рейтинг пишет те же точки через ``world_imf_ingest``. Этот парсер
нужен daily ETL каталога ``indicators`` (``weo-gdp-usd`` /
``weo-gdp-per-capita-usd``). Одна страна: ISO ``RU`` / WEO ``RUS``.
Политика года наблюдений (поточные серии — только закрытые годы)
применяется внутри ``ImfWeoAdapter.fetch_weo_code`` по фактическому коду
серии; сюда отдельная обрезка не дублируется.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date
from typing import ClassVar

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FetchLog, Indicator
from app.services.base_parser import BaseParser
from app.services.imf_weo_adapter import (
    PUBLIC_SOURCE_URL,
    WEO_SERIES,
    weo_data_url,
    weo_iso3_for,
    ImfWeoAdapter,
    points_for_iso3,
)

logger = logging.getLogger(__name__)


class ImfWeoParser(BaseParser):
    parser_type: ClassVar[str] = "imf_weo"
    replace_series: ClassVar[bool] = True

    async def _fetch_and_parse(
        self,
        db: AsyncSession,
        indicator: Indicator,
        cfg: dict,
        fetch_log: FetchLog,
    ) -> tuple[list, str]:
        weo_code = str(cfg.get("weo_code") or "").strip().upper()
        iso2 = str(cfg.get("country_code") or "RU").strip().upper()
        iso3 = weo_iso3_for(iso2)
        url = weo_data_url([iso3], weo_code) if iso3 and weo_code else PUBLIC_SOURCE_URL
        if weo_code not in WEO_SERIES or iso3 is None:
            fetch_log.error_message = "weo_code/country_code missing or unsupported"
            return [], url

        adapter = ImfWeoAdapter(country_codes=[iso2])
        try:
            parsed = await asyncio.to_thread(adapter.fetch_weo_code, weo_code, [iso3])
        except Exception as exc:  # noqa: BLE001
            fetch_log.error_message = f"IMF WEO {iso3} {weo_code} fetch failed: {exc}"[:500]
            return [], url

        backfill_from: date | None = None
        raw_from = cfg.get("backfill_from")
        if raw_from:
            try:
                backfill_from = date.fromisoformat(str(raw_from)[:10])
            except ValueError:
                logger.warning("Invalid backfill_from %r for %s", raw_from, indicator.code)

        points = points_for_iso3(parsed, iso3, weo_code)
        if backfill_from is not None:
            points = [(dt, value) for dt, value in points if dt >= backfill_from]
        return points, url
