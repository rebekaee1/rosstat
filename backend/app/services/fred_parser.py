"""ETL parser for FRED graph CSV (no API key).

Source: St. Louis Fed FRED public CSV export
  GET https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}

Series id comes from ``model_config_json["fred_series_id"]``. Optional
``backfill_from`` (ISO date) drops earlier observations after parse.

Response shape (verified live 2026-08-16):
  observation_date,<SERIES_ID>
  2006-01-02,101.4155
  …

Legacy header ``DATE`` is accepted as an alias. Missing values arrive as
``.`` — those rows are skipped.

Used by daily Fed/Treasury/EIA series redistributed on FRED
(``DTWEXBGS``, ``DGS10``, ``DCOILBRENTEU``, ``DHHNGSP``, …). Full history comes in one
response, so each ETL run fetches the whole CSV and relies on ADR-0002
idempotent upsert.

Не всякий ряд на FRED можно переопубликовать: у серий индексных провайдеров
(``SP500`` и другие серии S&P Dow Jones Indices, бывшие серии Wilshire) в
примечаниях стоит прямой запрет воспроизведения без письменного разрешения
правообладателя. Такие ряды в каталог не заводим.
"""
from __future__ import annotations

import asyncio
import csv
import io
import logging
from datetime import date
from typing import ClassVar

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FetchLog, Indicator
from app.services.base_parser import BaseParser

logger = logging.getLogger(__name__)

_BASE_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"
_UA = "ForecastEconomy/1.0 (+https://forecasteconomy.com)"


def _fetch_fred_csv(series_id: str) -> str:
    with httpx.Client(
        timeout=60.0,
        headers={"User-Agent": _UA},
        follow_redirects=True,
    ) as client:
        response = client.get(_BASE_URL, params={"id": series_id})
        response.raise_for_status()
        return response.text


def _parse_fred_csv(text: str, *, backfill_from: date | None = None) -> list[tuple[date, float]]:
    reader = csv.reader(io.StringIO(text))
    try:
        header = next(reader)
    except StopIteration:
        return []

    if not header:
        return []

    date_key = header[0].strip().lower()
    if date_key not in {"observation_date", "date"}:
        logger.warning("Unexpected FRED CSV header: %r", header)
        return []

    out: list[tuple[date, float]] = []
    for row in reader:
        if len(row) < 2:
            continue
        raw_date = row[0].strip()
        raw_value = row[1].strip()
        if not raw_date or raw_value in {"", "."}:
            continue
        try:
            d = date.fromisoformat(raw_date)
            value = float(raw_value)
        except ValueError:
            continue
        if backfill_from is not None and d < backfill_from:
            continue
        out.append((d, value))
    return out


class FredCsvParser(BaseParser):
    parser_type: ClassVar[str] = "fred_csv"
    # FRED отдаёт полный снимок ряда — даты вне ответа источника (например
    # хвост старого Yahoo-фида у brent) нужно срезать, иначе карточка смешивает
    # официальный спот и фьючерсное закрытие.
    replace_series: ClassVar[bool] = True

    async def _fetch_and_parse(
        self,
        db: AsyncSession,
        indicator: Indicator,
        cfg: dict,
        fetch_log: FetchLog,
    ) -> tuple[list, str]:
        series_id = str(cfg.get("fred_series_id") or "").strip()
        url = f"{_BASE_URL}?id={series_id}" if series_id else _BASE_URL
        if not series_id:
            fetch_log.error_message = "fred_series_id missing in model_config_json"
            return [], url

        backfill_from: date | None = None
        raw_from = cfg.get("backfill_from")
        if raw_from:
            try:
                backfill_from = date.fromisoformat(str(raw_from))
            except ValueError:
                logger.warning(
                    "Invalid backfill_from %r for %s — ignoring",
                    raw_from,
                    indicator.code,
                )

        try:
            text = await asyncio.to_thread(_fetch_fred_csv, series_id)
        except Exception as exc:
            fetch_log.error_message = f"FRED {series_id} fetch failed: {exc}"[:500]
            return [], url

        points = _parse_fred_csv(text, backfill_from=backfill_from)
        return points, url
