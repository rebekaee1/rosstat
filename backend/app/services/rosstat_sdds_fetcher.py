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
  - Discovery со страниц разделов (`list_mediabank_filenames_from_page` /
    `resolve_mediabank_file`) — устойчивый поиск публикаций, когда Росстат
    переименовывает файлы (демография, наука, кадры ВО).

SDDS-английский fetcher (`fetch_sdds_xlsx`) и `DATASET_URLS` удалены 2026-05-10
(ADR-0004 cleanup). Все индикаторы переключены на canonical русские источники.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from urllib.parse import unquote

import requests

from app.config import settings
from app.services.http_client import create_session

logger = logging.getLogger(__name__)

XLSX_MAGIC = b"PK\x03\x04"
XLS_MAGIC = b"\xd0\xcf\x11\xe0"  # OLE2 compound (legacy .xls binary)
PDF_MAGIC = b"%PDF"

_ROSSTAT_MEDIA = "https://rosstat.gov.ru/storage/mediabank"
_MEDIA_HREF_RE = re.compile(
    r"""(?:href|src)=["'](?:https?://[^"']+)?/storage/mediabank/([^"'?#]+\.(?:xlsx|xls))["']""",
    re.IGNORECASE,
)
_YEAR_IN_NAME_RE = re.compile(r"(?<!\d)(19|20)\d{2}(?!\d)")

ROSSTAT_STATIC_URLS: dict[str, str] = {
    "popul_components": "https://rosstat.gov.ru/storage/mediabank/Popul%20components_1990+.xlsx",
    "population_history": "https://rosstat.gov.ru/storage/mediabank/Popul_1897+.xlsx",
    # Канон на странице accounts: дефис `s-1995` (Q1-2026+). Старый
    # underscore `s_1995` ещё отдаёт 200, но без свежих кварталов (trap 2026-07).
    "gdp_quarterly": "https://rosstat.gov.ru/storage/mediabank/VVP_kvartal_s-1995-2026.xlsx",
    "gdp_use_quarterly": "https://rosstat.gov.ru/storage/mediabank/GDP-quarters-of-use-1995_1kv-2026.xls",
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


def mediabank_url(filename: str) -> str:
    return f"{_ROSSTAT_MEDIA}/{filename.lstrip('/')}"


def list_mediabank_filenames_from_page(
    page_url: str,
    *,
    session: requests.Session | None = None,
) -> list[str]:
    """Собрать имена файлов mediabank со страницы раздела Росстата.

    Росстат периодически меняет точное имя (Kadry_VO ↔ Kadry-VO, innov-mp_1 ↔
    Innov_mp_1). Устойчивый признак — ссылка на странице раздела, а не хардкод.
    """
    sess = session or _get_session()
    try:
        resp = sess.get(page_url, timeout=settings.rosstat_request_timeout)
    except requests.RequestException as exc:
        logger.warning("Rosstat catalog page %s fetch failed: %s", page_url, exc)
        return []
    if resp.status_code != 200:
        logger.warning("Rosstat catalog page %s: HTTP %d", page_url, resp.status_code)
        return []

    seen: set[str] = set()
    out: list[str] = []
    for match in _MEDIA_HREF_RE.finditer(resp.text):
        name = unquote(match.group(1)).strip()
        if not name or name in seen:
            continue
        seen.add(name)
        out.append(name)
    return out


def _filename_year(name: str) -> int:
    years = [int(m.group(0)) for m in _YEAR_IN_NAME_RE.finditer(name)]
    return max(years) if years else -1


def pick_mediabank_filename(
    filenames: list[str],
    patterns: list[str],
    *,
    prefer_max_year: bool = True,
) -> str | None:
    """Выбрать файл по одному из regex-шаблонов; при нескольких — с max годом в имени."""
    compiled = [re.compile(p, re.IGNORECASE) for p in patterns]
    hits: list[str] = []
    for name in filenames:
        if any(rx.search(name) for rx in compiled):
            hits.append(name)
    if not hits:
        return None
    if prefer_max_year:
        hits.sort(key=lambda n: (_filename_year(n), n), reverse=True)
    return hits[0]


def download_mediabank_bytes(
    filename: str,
    *,
    session: requests.Session | None = None,
) -> tuple[bytes, str] | None:
    """Скачать mediabank-файл; принять .xlsx/.xls, отвергнуть HTML-заглушки."""
    sess = session or _get_session()
    url = mediabank_url(filename)
    try:
        resp = sess.get(url, timeout=settings.rosstat_request_timeout)
    except requests.RequestException as exc:
        logger.debug("Mediabank download failed for %s: %s", url, exc)
        return None
    if resp.status_code != 200:
        return None
    ct = resp.headers.get("content-type", "")
    if "html" in ct.lower():
        logger.warning("Got HTML instead of spreadsheet from %s", url)
        return None
    magic = resp.content[:4]
    if magic not in (XLSX_MAGIC, XLS_MAGIC):
        return None
    return resp.content, url


def resolve_mediabank_file(
    *,
    catalog_urls: list[str],
    name_patterns: list[str],
    fallback_filenames: list[str] | None = None,
    session: requests.Session | None = None,
) -> tuple[bytes, str]:
    """Найти и скачать файл: сначала ссылки со страниц раздела, затем fallback-имена.

    Raises RuntimeError, если ни один кандидат не скачался.
    """
    sess = session or _get_session()
    candidates: list[str] = []
    seen: set[str] = set()

    for page_url in catalog_urls:
        picked = pick_mediabank_filename(
            list_mediabank_filenames_from_page(page_url, session=sess),
            name_patterns,
            prefer_max_year=True,
        )
        if picked and picked not in seen:
            seen.add(picked)
            candidates.append(picked)

    for name in fallback_filenames or []:
        if name not in seen:
            seen.add(name)
            candidates.append(name)

    tried: list[str] = []
    for name in candidates:
        tried.append(name)
        got = download_mediabank_bytes(name, session=sess)
        if got:
            content, url = got
            logger.info("Resolved Rosstat mediabank file %s (%d KB)", name, len(content) // 1024)
            return content, url

    raise RuntimeError(
        f"Rosstat mediabank file not found (patterns={name_patterns}, tried={tried})"
    )


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
