"""ETL: универсальный парсер REST API CBR DataService → IndicatorData.

Endpoint:
    https://www.cbr.ru/dataservice/data?publicationId={pub}&datasetId={ds}&measureId={measure}&y1={from}&y2={to}
Фильтрация по конкретному ряду — через `element_id` в коде после fetch'а.

Подходит для:
- Ипотечные ставки (publicationId=14, datasetId=29, element_id=36)
- Автокредиты (publicationId=14, datasetId=28, measureId=2, element_id=110)
- Ставки по депозитам ФЛ (publicationId=18, datasetId=37, measureId=2, element_id=7)
- Денежные агрегаты M0/M1/M2, портфельные задолженности по кредитам физ./юр.,
  средневзвешенные ставки по кредитам/депозитам разных сегментов и сроков,
  current account / portfolio investment / financial account из BoP.
- Всего ~16 индикаторов через единственный парсер.

Конфигурация хранится в `indicator.model_config_json`:
    {
      "dataservice": {
        "publicationId": 14,
        "datasetId": 29,
        "measureId": null,
        "element_id": 36
      },
      "backfill_from_year": 2017
    }

Trap (зафиксирован 2026-05): `element_id` критичен и не самообъясняющий —
он идентифицирует конкретный ряд внутри datasetId. На auto-loan-rate в начале
мая 2026 поле `element_id` было `6` вместо корректного `110` (другая length
автокредита), индикатор показывал ставку чужого продукта. Любая правка
`element_id` в seed_data.py требует прогона `daily_update_job` и
проверки 5-10 последних точек глазами на ожидаемый порядок величины.
Точный маппинг (pub/ds/measure/element) на каждый индикатор — см.
`docs/data_sources.md::ЦБ РФ — DataService JSON`.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime
from typing import ClassVar

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FetchLog, Indicator
from app.services.base_parser import BaseParser
from app.services.http_client import create_session
from app.config import settings as _settings

logger = logging.getLogger(__name__)

CBR_DATASERVICE_URL = f"{_settings.cbr_base_url.rstrip('/')}/dataservice/data"

MONTH_MAP = {
    "январь": 1, "февраль": 2, "март": 3, "апрель": 4,
    "май": 5, "июнь": 6, "июль": 7, "август": 8,
    "сентябрь": 9, "октябрь": 10, "ноябрь": 11, "декабрь": 12,
}


def _parse_ds_date(dt_str: str, iso_date: str | None, date_offset_months: int = -1) -> date | None:
    """Parse date from DataService response.

    date_offset_months: -1 for rate data (Feb = data for Jan), 0 for monetary (date is actual).
    """
    if iso_date:
        try:
            d = datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
            y, m = d.year, d.month
            m += date_offset_months
            while m <= 0:
                m += 12
                y -= 1
            while m > 12:
                m -= 12
                y += 1
            return date(y, m, 1)
        except (ValueError, TypeError):
            pass
    if dt_str:
        trimmed = dt_str.strip()
        parts = trimmed.lower().split()
        if len(parts) == 2:
            month_name, year_str = parts
            month = MONTH_MAP.get(month_name)
            if month:
                try:
                    return date(int(year_str), month, 1)
                except (ValueError, TypeError):
                    pass
        # DD.MM.YYYY format
        dot_parts = trimmed.split(".")
        if len(dot_parts) == 3:
            try:
                dd, mm, yy = int(dot_parts[0]), int(dot_parts[1]), int(dot_parts[2])
                return date(yy, mm, dd)
            except (ValueError, TypeError):
                pass
    return None


def fetch_dataservice(
    publication_id: int, dataset_id: int,
    measure_id: int | None, element_id: int | None,
    year_from: int, year_to: int,
    date_offset_months: int = -1,
) -> list[tuple[date, float]]:
    """Fetch from CBR DataService REST API."""
    params: dict = {
        "publicationId": publication_id,
        "datasetId": dataset_id,
        "y1": year_from,
        "y2": year_to,
    }
    if measure_id is not None:
        params["measureId"] = measure_id

    session = create_session()
    try:
        resp = session.get(CBR_DATASERVICE_URL, params=params, timeout=60)
        resp.raise_for_status()
        ct = resp.headers.get("content-type", "").lower()
        if "json" not in ct and resp.status_code == 200:
            logger.warning("DataService unexpected content-type: %s", resp.headers.get("content-type"))
        data = resp.json()
    finally:
        session.close()

    raw_data = data.get("RawData") or []
    results: list[tuple[date, float]] = []
    for row in raw_data:
        if element_id is not None:
            eid = row.get("element_id") or row.get("colId")
            if eid != element_id:
                continue
        val = row.get("obs_val")
        if val is None:
            continue
        dt = _parse_ds_date(row.get("dt", ""), row.get("date"), date_offset_months)
        if dt:
            results.append((dt, round(float(val), 4)))

    results.sort(key=lambda x: x[0])
    by_date: dict[date, float] = {}
    for d, v in results:
        by_date[d] = v
    return sorted(by_date.items())


class CbrDataServiceParser(BaseParser):
    parser_type: ClassVar[str] = "cbr_dataservice_json"

    async def _fetch_and_parse(
        self,
        db: AsyncSession,
        indicator: Indicator,
        cfg: dict,
        fetch_log: FetchLog,
    ) -> tuple[list, str]:
        ds_cfg = cfg.get("dataservice")
        if not ds_cfg:
            raise ValueError("Missing 'dataservice' in model_config_json")

        pub_id = ds_cfg["publicationId"]
        ds_id = ds_cfg["datasetId"]
        measure_id = ds_cfg.get("measureId")
        element_id = ds_cfg.get("element_id")
        date_offset = int(ds_cfg.get("date_offset_months", -1))
        year_from = int(cfg.get("backfill_from_year", 2017))
        year_to = date.today().year

        points = await asyncio.to_thread(
            fetch_dataservice, pub_id, ds_id, measure_id, element_id, year_from, year_to, date_offset,
        )

        value_divisor = float(cfg.get("value_divisor", 1))
        if value_divisor != 1:
            points = [(dt, round(val / value_divisor, 4)) for dt, val in points]

        return points, f"cbr.ru/dataservice/data?pub={pub_id}&ds={ds_id}&el={element_id}"
