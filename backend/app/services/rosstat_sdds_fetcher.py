"""
Загрузчик SDDS XLSX-файлов с eng.rosstat.gov.ru.

SDDS (Special Data Dissemination Standard) — стандарт МВФ.
Файлы публикуются по паттерну:
  https://eng.rosstat.gov.ru/storage/mediabank/SDDS_{dataset}_{year}.xlsx

Год в URL обычно = текущий - 1 (файл за 2025 год содержит данные до начала 2026).
Пробуем сначала текущий год, потом год назад.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

import requests

from app.config import settings

logger = logging.getLogger(__name__)

XLSX_MAGIC = b"PK\x03\x04"

_BASE = "https://eng.rosstat.gov.ru/storage/mediabank"

DATASET_URLS: dict[str, str] = {
    "labor": "SDDS_labor%20market_{year}.xlsx",
    "gdp": "SDDS%20national%20accounts_{year}.xlsx",
    "population": "SDDS_population_{year}.xlsx",
    "ipi": "SDDS_industrial%20production%20index_{year}.xlsx",
    "housing": "SDDS_housing%20market%20price%20indices_{year}_.xlsx",
}

ROSSTAT_STATIC_URLS: dict[str, str] = {
    "popul_components": "https://rosstat.gov.ru/storage/mediabank/Popul%20components_1990+.xlsx",
    "age_groups": "https://rosstat.gov.ru/storage/mediabank/demo14.xlsx",
}

_session: requests.Session | None = None


def _get_session() -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update({
            "User-Agent": "Mozilla/5.0 (compatible; ForecastEconomy/1.0; +https://forecasteconomy.com)",
            "Accept-Language": "en-US,en;q=0.9",
        })
        _session.verify = settings.rosstat_ca_cert
    return _session


def fetch_sdds_xlsx(dataset: str) -> tuple[bytes, str]:
    """Download SDDS XLSX. Tries current year, then year - 1.

    Returns (content_bytes, final_url).
    Raises on total failure.
    """
    template = DATASET_URLS.get(dataset)
    if not template:
        raise ValueError(f"Unknown SDDS dataset: {dataset}")

    now_year = datetime.now().year
    session = _get_session()

    for year in (now_year, now_year - 1):
        url = f"{_BASE}/{template.format(year=year)}"
        try:
            resp = session.get(url, timeout=settings.rosstat_request_timeout)
            if resp.status_code != 200:
                logger.debug("SDDS %s %d: HTTP %d", dataset, year, resp.status_code)
                continue
            if resp.content[:4] != XLSX_MAGIC:
                logger.warning("SDDS %s %d: not XLSX (HTML error page?)", dataset, year)
                continue
            logger.info("Downloaded SDDS %s (%d): %d KB", dataset, year, len(resp.content) // 1024)
            return resp.content, url
        except requests.RequestException as e:
            logger.warning("SDDS %s %d fetch error: %s", dataset, year, e)

    raise RuntimeError(f"SDDS {dataset}: no file found for years {now_year} or {now_year - 1}")


def fetch_rosstat_static_xlsx(key: str) -> tuple[bytes, str]:
    """Download a static XLSX file from rosstat.gov.ru (non-SDDS).

    Returns (content_bytes, url).
    """
    url = ROSSTAT_STATIC_URLS.get(key)
    if not url:
        raise ValueError(f"Unknown Rosstat static file: {key}")

    session = _get_session()
    resp = session.get(url, timeout=settings.rosstat_request_timeout)
    if resp.status_code != 200:
        raise RuntimeError(f"Rosstat {key}: HTTP {resp.status_code}")
    if resp.content[:4] != XLSX_MAGIC:
        raise RuntimeError(f"Rosstat {key}: response is not XLSX")
    logger.info("Downloaded Rosstat %s: %d KB", key, len(resp.content) // 1024)
    return resp.content, url
