"""
Загрузчик файлов с rosstat.gov.ru (canonical русский Rosstat).

Поддерживаемые источники:
  - Static XLSX/XLS bundles (`fetch_rosstat_static_xlsx`) — стабильные URL из
    `ROSSTAT_STATIC_URLS`.
  - Динамический IPI XLSX (`fetch_rosstat_ipi_current`) — `ind_baza_2023_*.xlsx`,
    переиздаётся ежемесячно.
  - Динамический OkPopul XLSX (`fetch_rosstat_okpopul`) — годовая публикация.
  - Socioeconomic-report PDF (`fetch_latest_socioeconomic_report_pdf`) —
    ежемесячный osn-{MM}-{YYYY}.pdf, источник для labor / PPI / housing
    (см. ADR-0004 path P).

SDDS-английский fetcher (`fetch_sdds_xlsx`) и `DATASET_URLS` удалены 2026-05-10
(ADR-0004 cleanup). Все индикаторы переключены на canonical русские источники.
"""

from __future__ import annotations

import logging
from datetime import datetime

import requests

from app.config import settings
from app.services.http_client import create_session

logger = logging.getLogger(__name__)

XLSX_MAGIC = b"PK\x03\x04"
XLS_MAGIC = b"\xd0\xcf\x11\xe0"  # OLE2 compound (legacy .xls binary)
PDF_MAGIC = b"%PDF"

_ROSSTAT_MEDIA = "https://rosstat.gov.ru/storage/mediabank"

ROSSTAT_STATIC_URLS: dict[str, str] = {
    "popul_components": "https://rosstat.gov.ru/storage/mediabank/Popul%20components_1990+.xlsx",
    "population_history": "https://rosstat.gov.ru/storage/mediabank/Popul_1897+.xlsx",
    # Канон на странице accounts: дефис `s-1995` (Q1-2026+). Старый
    # underscore `s_1995` ещё отдаёт 200, но без свежих кварталов (trap 2026-07).
    "gdp_quarterly": "https://rosstat.gov.ru/storage/mediabank/VVP_kvartal_s-1995-2026.xlsx",
    "gdp_use_quarterly": "https://rosstat.gov.ru/storage/mediabank/GDP-quarters-of-use-1995-4kv-2025.xls",
    "ipi_historical_2018": "https://rosstat.gov.ru/storage/mediabank/ind_baza_2018_12-2025.xlsx",
    "age_groups": "https://rosstat.gov.ru/storage/mediabank/demo14.xlsx",
}

_session: requests.Session | None = None


def _get_session() -> requests.Session:
    global _session
    if _session is None:
        _session = create_session()
        _session.verify = settings.rosstat_ca_cert
    return _session


def fetch_rosstat_static_xlsx(key: str) -> tuple[bytes, str]:
    """Download a static XLSX/XLS file from rosstat.gov.ru (non-SDDS).

    Accepts both .xlsx (PK zip magic) and legacy .xls (OLE2 compound magic).

    Returns (content_bytes, url).
    """
    url = ROSSTAT_STATIC_URLS.get(key)
    if not url:
        raise ValueError(f"Unknown Rosstat static file: {key}")

    session = _get_session()
    resp = session.get(url, timeout=settings.rosstat_request_timeout)
    if resp.status_code != 200:
        raise RuntimeError(f"Rosstat {key}: HTTP {resp.status_code}")
    ct = resp.headers.get("content-type", "")
    if "html" in ct.lower():
        logger.warning("Rosstat %s: got HTML content-type", key)
    if resp.content[:4] not in (XLSX_MAGIC, XLS_MAGIC):
        raise RuntimeError(f"Rosstat {key}: response is not XLSX/XLS")
    logger.info("Downloaded Rosstat %s: %d KB", key, len(resp.content) // 1024)
    return resp.content, url


def fetch_rosstat_ipi_current() -> tuple[bytes, str]:
    """Download current rosstat IPI XLSX `ind_baza_2023_{MM}-{YYYY}.xlsx`.

    Файл переиздаётся ежемесячно с новой публикацией Росстата (~15-20 числа за
    предыдущий месяц). URL содержит месяц и год последнего покрытого месяца.
    Пробуем последние 6 месяцев, возвращаем самый свежий.

    Когда rosstat переключится на следующую методологическую базу
    (`ind_baza_2028_*` или подобное), этот fetcher будет ломаться — обновить
    URL pattern в коде.
    """
    now = datetime.now()
    session = _get_session()

    for month_offset in range(6):
        cur = now.month - month_offset
        cur_year = now.year
        while cur <= 0:
            cur += 12
            cur_year -= 1

        url = f"{_ROSSTAT_MEDIA}/ind_baza_2023_{cur:02d}-{cur_year}.xlsx"
        try:
            resp = session.get(url, timeout=settings.rosstat_request_timeout)
            if resp.status_code != 200:
                logger.debug("Rosstat IPI %02d-%d: HTTP %d", cur, cur_year, resp.status_code)
                continue
            if resp.content[:4] != XLSX_MAGIC:
                logger.warning("Rosstat IPI %02d-%d: not XLSX", cur, cur_year)
                continue
            logger.info("Downloaded Rosstat IPI %02d-%d: %d KB", cur, cur_year, len(resp.content) // 1024)
            return resp.content, url
        except requests.RequestException as e:
            logger.warning("Rosstat IPI %02d-%d fetch error: %s", cur, cur_year, e)

    raise RuntimeError("Rosstat IPI: no current ind_baza_2023_*.xlsx file found in last 6 months")


def fetch_rosstat_okpopul() -> tuple[bytes, str]:
    """Download OkPopul_Comp{YYYY}_Site.xlsx — annual «оценка численности постоянного
    населения на 1 января» from rosstat русский. Tries current year, then year-1.

    Released ~Q1-Q2 each year and contains population on 1 января {YYYY} for РФ
    + components за предыдущий год.
    """
    now_year = datetime.now().year
    session = _get_session()

    for year in (now_year, now_year - 1):
        url = f"{_ROSSTAT_MEDIA}/OkPopul_Comp{year}_Site.xlsx"
        try:
            resp = session.get(url, timeout=settings.rosstat_request_timeout)
            if resp.status_code != 200:
                logger.debug("OkPopul %d: HTTP %d", year, resp.status_code)
                continue
            if resp.content[:4] != XLSX_MAGIC:
                logger.warning("OkPopul %d: not XLSX", year)
                continue
            logger.info("Downloaded OkPopul %d: %d KB", year, len(resp.content) // 1024)
            return resp.content, url
        except requests.RequestException as e:
            logger.warning("OkPopul %d fetch error: %s", year, e)

    raise RuntimeError(f"OkPopul: no file found for years {now_year} or {now_year - 1}")


def fetch_latest_socioeconomic_report_pdf() -> tuple[bytes, str]:
    """Download latest official Rosstat socioeconomic report PDF.

    The public document page can lag behind current uploads, while direct
    media files follow the stable osn-MM-YYYY.pdf naming pattern.
    """
    now = datetime.now()
    session = _get_session()

    attempts: list[tuple[int, int]] = []
    for month in range(now.month, 0, -1):
        attempts.append((now.year, month))
    for month in range(12, 0, -1):
        attempts.append((now.year - 1, month))

    for year, month in attempts:
        url = f"{_ROSSTAT_MEDIA}/osn-{month:02d}-{year}.pdf"
        try:
            resp = session.get(url, timeout=settings.rosstat_request_timeout)
            if resp.status_code != 200:
                logger.debug("Rosstat socioeconomic report %s: HTTP %d", url, resp.status_code)
                continue
            if resp.content[:4] != PDF_MAGIC:
                logger.warning("Rosstat socioeconomic report %s: response is not PDF", url)
                continue
            logger.info(
                "Downloaded Rosstat socioeconomic report %s: %d KB",
                url,
                len(resp.content) // 1024,
            )
            return resp.content, url
        except requests.RequestException as e:
            logger.warning("Rosstat socioeconomic report %s fetch error: %s", url, e)

    raise RuntimeError("Rosstat socioeconomic report PDF not found")
