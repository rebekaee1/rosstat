"""ETL parser for ECB euro foreign exchange reference rates (EXR, daily).

Source: European Central Bank, Statistical Data Portal — SDMX 2.1 CSV,
no API key:
  GET https://data-api.ecb.europa.eu/service/data/EXR/D.{CCY}.EUR.SP00.A?format=csvdata

Key structure ``D.{CCY}.EUR.SP00.A``: daily frequency, currency CCY quoted
per 1 euro, spot rate, average series. ``D.USD.EUR.SP00.A`` therefore IS the
market-convention EUR/USD rate (US dollars per one euro).

Config (``model_config_json``):
  ecb_currency    — ISO code of the quoted currency, e.g. ``USD``
  backfill_from   — optional ISO date; earlier observations dropped

Response shape (verified live 2026-08-22):
  KEY,FREQ,CURRENCY,...,TIME_PERIOD,OBS_VALUE,...
  EXR.D.USD.EUR.SP00.A,D,USD,...,2026-08-21,1.1699,A,...

Only ``TIME_PERIOD`` and ``OBS_VALUE`` are consumed; rows with empty value
(non-TARGET days are simply absent) are skipped. Full history since 1999
arrives in one response (~7k rows), so each ETL run refetches the whole CSV
and relies on ADR-0002 idempotent upsert.

Publication cadence: every TARGET working day around 16:00 CET (17:00 MSK
summer, 18:00 MSK winter) — same-day value is available to the evening ETL,
unlike the Fed H.10 weekly package.

Reuse terms (verified 2026-08-22): ESCB statistics may be reused free of
charge, including commercially, provided the source is quoted and the data
are not modified — https://www.ecb.europa.eu/stats/ecb_statistics/governance_and_quality_framework/html/usage_policy.en.html
Public ``source`` field must credit the ECB. Rates are published «for
information purposes», so methodology texts must not present them as
transaction prices.

Cross rates (GBP/USD, USD/CNY) are NOT fetched here: the ECB quotes vs the
euro only. Crosses are derived series (``series_ratio`` op in
``derived_ops.py``) computed from two EXR legs — keeps the parser a pure
fetcher and the math in one tested place (ADR-0001).
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

_BASE_URL = "https://data-api.ecb.europa.eu/service/data/EXR"
_UA = "ForecastEconomy/1.0 (+https://forecasteconomy.com)"


def _fetch_exr_csv(currency: str) -> str:
    url = f"{_BASE_URL}/D.{currency}.EUR.SP00.A"
    with httpx.Client(
        timeout=60.0,
        headers={"User-Agent": _UA},
        follow_redirects=True,
    ) as client:
        response = client.get(url, params={"format": "csvdata"})
        response.raise_for_status()
        return response.text


def _parse_exr_csv(text: str, *, backfill_from: date | None = None) -> list[tuple[date, float]]:
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames or "TIME_PERIOD" not in reader.fieldnames:
        logger.warning("Unexpected ECB EXR CSV header: %r", reader.fieldnames)
        return []

    out: list[tuple[date, float]] = []
    for row in reader:
        raw_date = (row.get("TIME_PERIOD") or "").strip()
        raw_value = (row.get("OBS_VALUE") or "").strip()
        if not raw_date or not raw_value:
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


class EcbFxParser(BaseParser):
    parser_type: ClassVar[str] = "ecb_fx"
    # Полный снимок ряда: если ЕЦБ уберёт дату из выгрузки, она должна
    # исчезнуть и у нас — иначе карточка покажет значение, которого нет
    # в первоисточнике.
    replace_series: ClassVar[bool] = True

    async def _fetch_and_parse(
        self,
        db: AsyncSession,
        indicator: Indicator,
        cfg: dict,
        fetch_log: FetchLog,
    ) -> tuple[list, str]:
        currency = str(cfg.get("ecb_currency") or "").strip().upper()
        url = f"{_BASE_URL}/D.{currency}.EUR.SP00.A?format=csvdata" if currency else _BASE_URL
        if not currency:
            fetch_log.error_message = "ecb_currency missing in model_config_json"
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
            text = await asyncio.to_thread(_fetch_exr_csv, currency)
        except Exception as exc:
            fetch_log.error_message = f"ECB EXR {currency} fetch failed: {exc}"[:500]
            return [], url

        points = _parse_exr_csv(text, backfill_from=backfill_from)
        return points, url
