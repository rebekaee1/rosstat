"""ETL: Росстат еженедельные средние потребительские цены (абсолютные, руб.).

Источник: `rosstat.gov.ru/storage/mediabank/nedel_sred_cen.xlsx` — официальный
файл «Еженедельные средние потребительские цены (на конец периода)». Листы по
годам (2022, 2023, …, текущий). На каждом листе:

  row 0: «К содержанию»
  row 3: заголовки дат «на 12 января», «на 19 января», … (с col 1)
  row 4+: строки товаров, col 0 — наименование, далее значения по неделям.

В отличие от `rosstat_weekly_inflation_parser` (недельный ИПЦ, % к пред. неделе),
этот файл хранит **абсолютную цену** в рублях за единицу (л, кг, шт.). Тот же
parser обслуживает любую строку файла — целевая строка config-driven через
`model_config_json.product_label` (точное совпадение col 0, иначе подстрока).

Используется для топлива:
  fuel-ai92   «Бензин автомобильный марки АИ-92, л»
  fuel-ai95   «Бензин автомобильный марки АИ-95, л»
  fuel-diesel «Дизельное топливо, л»

Прогноз — `generic_ols` (короткий недельный тренд), как у `inflation-weekly`.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import date
from typing import ClassVar

import openpyxl
import requests
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FetchLog, Indicator
from app.services.base_parser import BaseParser
from app.services.data_validator import validate_points
from app.services.http_client import create_session
from app.services.rosstat_weekly_inflation_parser import _parse_column_date

logger = logging.getLogger(__name__)

WEEKLY_SRED_CEN_URL = "https://rosstat.gov.ru/storage/mediabank/nedel_sred_cen.xlsx"
_HEADER_ROW = 3  # 0-based: строка «на 12 января …»


@dataclass
class PricePoint:
    date: date
    value: float


def parse_weekly_price_xlsx(content: bytes, product_label: str) -> list[PricePoint]:
    """Parse nedel_sred_cen.xlsx → [(week_end_date, price)] for `product_label`.

    Совпадение строки: сначала точное (по col 0, без регистра/пробелов), затем
    подстрока. Берём первую подходящую строку на каждом листе-годе.
    """
    wb = openpyxl.load_workbook(io_bytes(content), data_only=True, read_only=True)
    target = product_label.strip().lower()
    out: dict[date, float] = {}
    try:
        for sheet_name in wb.sheetnames:
            try:
                year = int(sheet_name)
            except ValueError:
                continue
            ws = wb[sheet_name]
            rows = [list(r) for r in ws.iter_rows(values_only=True)]
            if len(rows) <= _HEADER_ROW:
                continue

            header = rows[_HEADER_ROW]
            col_dates: list[tuple[int, date]] = []
            for ci in range(1, len(header)):
                d = _parse_column_date(str(header[ci] or ""), year)
                if d:
                    col_dates.append((ci, d))
            if not col_dates:
                continue

            data_row = _find_product_row(rows, target)
            if data_row is None:
                continue

            for ci, d in col_dates:
                if ci >= len(data_row):
                    continue
                raw = data_row[ci]
                if raw is None or raw == "" or raw == "…":
                    continue
                try:
                    val = float(str(raw).replace(",", ".").replace("\u2212", "-"))
                except (ValueError, TypeError):
                    continue
                if val <= 0:
                    continue
                out[d] = round(val, 2)
    finally:
        wb.close()

    return [PricePoint(date=d, value=v) for d, v in sorted(out.items())]


def _find_product_row(rows: list[list], target: str) -> list | None:
    exact: list | None = None
    substr: list | None = None
    for row in rows:
        if not row or row[0] is None:
            continue
        name = str(row[0]).strip().lower()
        if name == target:
            exact = row
            break
        if substr is None and target in name:
            substr = row
    return exact if exact is not None else substr


def io_bytes(content: bytes):
    from io import BytesIO

    return BytesIO(content)


def fetch_weekly_price(product_label: str) -> tuple[list[PricePoint], str]:
    session = create_session()
    try:
        session.verify = False
        r = session.get(WEEKLY_SRED_CEN_URL, timeout=60)
        r.raise_for_status()
        points = parse_weekly_price_xlsx(r.content, product_label)
        return points, WEEKLY_SRED_CEN_URL
    finally:
        session.close()


class RosstatWeeklyPriceParser(BaseParser):
    parser_type: ClassVar[str] = "rosstat_weekly_price"

    async def _fetch_and_parse(
        self,
        db: AsyncSession,
        indicator: Indicator,
        cfg: dict,
        fetch_log: FetchLog,
    ) -> tuple[list, str]:
        product_label = str(cfg.get("product_label") or "").strip()
        if not product_label:
            fetch_log.error_message = "rosstat_weekly_price: model_config.product_label не задан"
            return [], WEEKLY_SRED_CEN_URL
        try:
            points, url = await asyncio.to_thread(fetch_weekly_price, product_label)
        except requests.RequestException as e:
            fetch_log.error_message = f"nedel_sred_cen.xlsx fetch failed: {e}"[:500]
            return [], WEEKLY_SRED_CEN_URL
        return points, url

    def _validate(self, points: list, cfg: dict) -> list:
        return validate_points(points, cfg)
