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
from datetime import date, datetime
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


class RosstatUnreachable(RuntimeError):
    """Росстат не ответил ни на один запрос попытки (сеть/бан/предохранитель хоста), а не «файла нет».

    Раньше сетевой отказ глотался, и итог выглядел как «file not found (tried=...)»: вечерний ETL 27.10.2026 показал
    21 ошибку двух «разных» видов, хотя причина одна (rosstat.gov.ru недоступен на всех хопах).
    """


def mediabank_url(filename: str) -> str:
    return f"{_ROSSTAT_MEDIA}/{filename.lstrip('/')}"


def list_mediabank_filenames_from_page(
    page_url: str,
    *,
    session: requests.Session | None = None,
    net_failures: list[str] | None = None,
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
        if net_failures is not None:
            net_failures.append(page_url)
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
    net_failures: list[str] | None = None,
) -> tuple[bytes, str] | None:
    """Скачать mediabank-файл; принять .xlsx/.xls, отвергнуть HTML-заглушки."""
    sess = session or _get_session()
    url = mediabank_url(filename)
    try:
        resp = sess.get(url, timeout=settings.rosstat_request_timeout)
    except requests.RequestException as exc:
        logger.debug("Mediabank download failed for %s: %s", url, exc)
        if net_failures is not None:
            net_failures.append(url)
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
    net_failures: list[str] = []

    for page_url in catalog_urls:
        picked = pick_mediabank_filename(
            list_mediabank_filenames_from_page(page_url, session=sess, net_failures=net_failures),
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
        got = download_mediabank_bytes(name, session=sess, net_failures=net_failures)
        if got:
            content, url = got
            logger.info("Resolved Rosstat mediabank file %s (%d KB)", name, len(content) // 1024)
            return content, url

    # Каждый запрос попытки (страницы каталога и скачивания) закончился сетевым отказом: файл не искали по существу.
    if net_failures and len(net_failures) >= len(catalog_urls) + len(tried):
        raise RosstatUnreachable(
            f"Rosstat unreachable: all {len(net_failures)} requests failed on network "
            f"(patterns={name_patterns})"
        )
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


_GDP_USE_URL_TMPL = _ROSSTAT_MEDIA + "/GDP-quarters-of-use-1995_{quarter}kv-{year}.xls"
# Файл ВВП по использованию выходит спустя месяц-два после квартала; шести кварталов хватает с запасом.
_GDP_USE_LOOKBACK_QUARTERS = 6


def gdp_use_candidate_urls(today: date | None = None) -> list[str]:
    """Адреса файла «ВВП по использованию» от текущего квартала к прошлым, затем зафиксированный канон.

    Имя файла несёт номер последнего квартала (`..._2kv-2026.xls`), и Росстат кладёт новый файл рядом со старым,
    не заменяя его. Зашитый адрес `..._1kv-2026.xls` отдавал 200 и после выхода II квартала: ряды
    потребления, госрасходов и инвестиций стояли на квартал позади ВВП (28.10.2026: `2kv-2026` уже отдавался).
    """
    today = today or date.today()
    year, quarter = today.year, (today.month - 1) // 3 + 1
    urls: list[str] = []
    for _ in range(_GDP_USE_LOOKBACK_QUARTERS):
        urls.append(_GDP_USE_URL_TMPL.format(quarter=quarter, year=year))
        quarter -= 1
        if quarter == 0:
            quarter, year = 4, year - 1
    pinned = ROSSTAT_STATIC_URLS["gdp_use_quarterly"]
    if pinned not in urls:
        urls.append(pinned)
    return urls


def _fetch_first_available(candidates: list[str], label: str) -> tuple[bytes, str]:
    """Первый адрес из списка, отдающий 200 с XLS/XLSX; 404 и не-Excel пропускаются.

    Все запросы с сетевым отказом — RosstatUnreachable (файл не искали по существу),
    иначе RuntimeError «file not found».
    """
    session = _get_session()
    net_failures = 0
    for url in candidates:
        try:
            resp = session.get(url, timeout=settings.rosstat_request_timeout)
        except requests.RequestException as exc:
            logger.warning("Rosstat %s %s fetch error: %s", label, url, exc)
            net_failures += 1
            continue
        if resp.status_code != 200:
            logger.debug("Rosstat %s %s: HTTP %d", label, url, resp.status_code)
            continue
        if resp.content[:4] not in (XLSX_MAGIC, XLS_MAGIC):
            logger.warning("Rosstat %s %s: response is not XLSX/XLS", label, url)
            continue
        logger.info("Downloaded Rosstat %s %s: %d KB", label, url, len(resp.content) // 1024)
        return resp.content, url
    if net_failures == len(candidates):
        raise RosstatUnreachable(f"Rosstat unreachable: {label} requests failed on network")
    raise RuntimeError(f"Rosstat {label} file not found (tried {len(candidates)} candidates)")


def fetch_rosstat_gdp_use_latest(today: date | None = None) -> tuple[bytes, str]:
    """Скачать самый свежий файл «ВВП по использованию» (тот, чей квартал новее; 404 пропускаются)."""
    return _fetch_first_available(gdp_use_candidate_urls(today), "GDP-by-use")


_GDP_QUARTERLY_URL_TMPL = _ROSSTAT_MEDIA + "/VVP_kvartal_s-1995-{year}.xlsx"


def gdp_quarterly_candidate_urls(today: date | None = None) -> list[str]:
    """Адреса «ВВП по кварталам» VVP_kvartal_s-1995-{YYYY}.xlsx: следующий год, текущий, прошлый, затем канон.

    Имя несёт год последних кварталов (28.10.2026: `...-2026.xlsx` с данными по II кварталу, `...-2027.xlsx` — 404).
    Со сменой года Росстат может выложить файл под новым именем, а старый продолжит отдавать 200 без свежих кварталов:
    тот же класс сбоя, что у ВВП по использованию. Поэтому следующий год идёт первым.
    """
    today = today or date.today()
    urls = [_GDP_QUARTERLY_URL_TMPL.format(year=today.year + offset) for offset in (1, 0, -1)]
    pinned = ROSSTAT_STATIC_URLS["gdp_quarterly"]
    if pinned not in urls:
        urls.append(pinned)
    return urls


def fetch_rosstat_gdp_quarterly_latest(today: date | None = None) -> tuple[bytes, str]:
    """Скачать самый свежий файл «ВВП по кварталам» (имя с наибольшим годом из опубликованных)."""
    return _fetch_first_available(gdp_quarterly_candidate_urls(today), "GDP-quarterly")


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
    net_failures = 0

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
            net_failures += 1

    if net_failures == 6:
        raise RosstatUnreachable("Rosstat unreachable: IPI current-file requests failed on network")
    raise RuntimeError("Rosstat IPI: no current ind_baza_2023_*.xlsx file found in last 6 months")


def fetch_rosstat_okpopul() -> tuple[bytes, str]:
    """Download OkPopul_Comp{YYYY}_Site.xlsx — annual «оценка численности постоянного
    населения на 1 января» from rosstat русский. Tries current year, then year-1.

    Released ~Q1-Q2 each year and contains population on 1 января {YYYY} for РФ
    + components за предыдущий год.
    """
    now_year = datetime.now().year
    session = _get_session()
    net_failures = 0

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
            net_failures += 1

    if net_failures == 2:
        raise RosstatUnreachable("Rosstat unreachable: OkPopul requests failed on network")
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

    net_failures = 0
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
            net_failures += 1

    if net_failures == len(attempts):
        raise RosstatUnreachable("Rosstat unreachable: socioeconomic report requests failed on network")
    raise RuntimeError("Rosstat socioeconomic report PDF not found")
