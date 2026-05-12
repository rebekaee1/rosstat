"""ETL: ЦБ РФ — внешняя торговля **товарами** monthly → IndicatorData.

Источник: `https://www.cbr.ru/vfs/statistics/credit_statistics/trade/trade.xls`
Лист «Ежемесячные» содержит месячные значения экспорта/импорта/сальдо ФОБ
с **1997-01** до текущего месяца.

Структура листа:
- rows 0-3: заголовки/notes (skip)
- rows 4-6: merged column headers
- rows 7..N: data rows
- rows N+1..end: примечания/дата обновления (skip — start with non-numeric col 0)

Колонки (0-indexed):
- 0: Год (float, например 1997.0)
- 1: Месяц (russian short: 'Янв', 'Фев', 'Мар', 'Апр', 'Май', 'Июн',
       'Июл', 'Авг', 'Сен', 'Окт', 'Ноя', 'Дек')
- 2: Экспорт ФОБ Всего (млн $)
- 3: Экспорт ФОБ % к соотв. периоду пред. года
- 4-7: Экспорт по группам стран (дальнее зарубежье + СНГ, value+%)
- 8: Импорт ФОБ Всего (млн $)
- 9: Импорт ФОБ % к соотв. периоду пред. года
- 10-13: Импорт по группам
- 14: **Сальдо торгового баланса Всего (млн $)**
- 15-16: Сальдо по группам

Подход: парсер один, target определяется через `model_config_json.bop_target`:
- `exports-monthly` → col 2
- `imports-monthly` → col 8
- `trade-balance-monthly` → col 14

См. также quarterly counterpart `cbr_bop_parser.py` (другой файл, другой layout).
"""

from __future__ import annotations

import asyncio
import io
import logging
from dataclasses import dataclass
from datetime import date
from typing import ClassVar

import xlrd
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FetchLog, Indicator
from app.services.base_parser import BaseParser
from app.services.http_client import create_session

logger = logging.getLogger(__name__)

TRADE_GOODS_URL = (
    "https://www.cbr.ru/vfs/statistics/credit_statistics/trade/trade.xls"
)

_MONTH_RU = {
    "янв": 1, "фев": 2, "мар": 3, "апр": 4, "май": 5, "июн": 6,
    "июл": 7, "авг": 8, "сен": 9, "окт": 10, "ноя": 11, "дек": 12,
}

_TARGET_COL = {
    "exports-monthly": 2,
    "imports-monthly": 8,
    "trade-balance-monthly": 14,
}


@dataclass
class DataPoint:
    date: date
    value: float


def _parse_month(month_cell: object) -> int | None:
    """Map Russian short month name to 1-12. Tolerant к whitespace/case."""
    if not month_cell:
        return None
    s = str(month_cell).strip().lower()
    if not s:
        return None
    return _MONTH_RU.get(s[:3])


def _parse_year(year_cell: object) -> int | None:
    """Robust year extract from xlrd float/string."""
    try:
        y = int(float(year_cell))
    except (TypeError, ValueError):
        return None
    if y < 1990 or y > 2100:
        return None
    return y


def fetch_trade_goods_xls() -> tuple[bytes, str]:
    """Download `trade.xls` from CBR. Returns (content_bytes, final_url)."""
    session = create_session()
    try:
        resp = session.get(TRADE_GOODS_URL, timeout=90)
        resp.raise_for_status()
        if resp.content[:8] != b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
            raise ValueError("trade.xls: not a legacy XLS file (CFB header missing)")
        logger.info("Downloaded trade.xls: %d KB", len(resp.content) // 1024)
        return resp.content, TRADE_GOODS_URL
    finally:
        session.close()


def parse_trade_goods_monthly_xls(content: bytes, target: str) -> list[DataPoint]:
    """Parse trade.xls лист «Ежемесячные» для одного target.

    target: один из 'exports-monthly', 'imports-monthly', 'trade-balance-monthly'.
    """
    if target not in _TARGET_COL:
        raise ValueError(f"Unknown trade target: {target}")
    col = _TARGET_COL[target]

    wb = xlrd.open_workbook(file_contents=content)
    sheet = None
    for s in wb.sheets():
        if "ежемесяч" in s.name.lower():
            sheet = s
            break
    if sheet is None:
        raise ValueError("trade.xls: лист 'Ежемесячные' не найден")

    points: list[DataPoint] = []
    for ri in range(7, sheet.nrows):
        year = _parse_year(sheet.cell_value(ri, 0))
        month = _parse_month(sheet.cell_value(ri, 1))
        if year is None or month is None:
            continue
        raw = sheet.cell_value(ri, col)
        if raw is None or raw == "":
            continue
        try:
            val = float(raw)
        except (TypeError, ValueError):
            continue
        points.append(DataPoint(date=date(year, month, 1), value=round(val, 2)))

    points.sort(key=lambda p: p.date)
    logger.info(
        "trade.xls Ежемесячные '%s': %d points (%s → %s)",
        target,
        len(points),
        points[0].date if points else "?",
        points[-1].date if points else "?",
    )
    return points


class CbrTradeGoodsMonthlyParser(BaseParser):
    """ETL parser для месячной внешней торговли товарами (ЦБ trade.xls)."""

    parser_type: ClassVar[str] = "cbr_trade_goods_monthly"

    async def _fetch_and_parse(
        self,
        db: AsyncSession,
        indicator: Indicator,
        cfg: dict,
        fetch_log: FetchLog,
    ) -> tuple[list, str]:
        target = cfg.get("bop_target", indicator.code)
        content, final_url = await asyncio.to_thread(fetch_trade_goods_xls)
        points = await asyncio.to_thread(
            parse_trade_goods_monthly_xls, content, target,
        )
        return points, final_url
