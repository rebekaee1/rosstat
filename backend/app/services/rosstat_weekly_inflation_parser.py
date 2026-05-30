"""ETL: Еженедельный ИПЦ → IndicatorData.

Источники (по приоритету):

1. HTML-бюллетени «Об оценке индекса потребительских цен с N по M месяца YYYY г»
   на `rosstat.gov.ru/storage/mediabank/<num>_<DD-MM-YYYY>.html`.
   Публикуются каждую неделю (обычно в среду) и содержат официальный
   агрегированный недельный ИПЦ. Это основной источник.

   **Важно**: Росстат начал публиковать **отдельные** еженедельные bulletin'ы
   только в 2023 году. До 2023 публиковались monthly «Об индексе
   потребительских цен в <месяц>» — других еженедельных документов нет
   (verified 2026-05-12 deep dive Wayback Machine CDX: 174 candidate URLs
   за 2021-2022-2023 → 0 weekly bulletin'ов за 2021, 0 за 2022, 1 за 2023-02-08).
   См. `docs/audits/weekly_inflation_research_2026-05.md`.

   Discovery (union стратегий, `_find_bulletin_urls`):
   - `_find_bulletin_urls_central_news` — пагинированный crawl
     `rosstat.gov.ru/central-news?page=1..N`. На сайте Росстата архив
     ограничен **с 2023-05-04** до today (раньше — Росстат удалил из ленты).
   - `ROSSTAT_SEARCH_URL` — поиск по слову «оценке индекса потребительских цен
     <месяц> <год>» (fallback / current-week edge cases / 2023-01..04
     не покрытые central-news).

2. Фоллбэк — `Nedel_ipc.xlsx` (~110 товаров, листы по годам) + `ipc_spr_MM-YYYY.xlsx`
   (веса). Взвешенное среднее по продовольственной корзине — приближение, поэтому
   используется только для дат **≥ `weekly_cutoff_date`** (config). Текущий
   cutoff = 2023-01-09 (первая неделя где есть данные в XLSX за 2023).
   До этой даты у Росстата вообще не было отдельных weekly публикаций;
   XLSX-приближение расходилось с bulletin до 0.1pp на 2023 (good enough)
   и до 3 pp на 2022 (заметные расхождения — bulletinов не было, не показываем).

HTML-источник имеет приоритет: если одна и та же дата есть в обеих коллекциях —
берётся значение из бюллетеня (оно совпадает с официальным Росстатом).
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from datetime import date, timedelta
from difflib import get_close_matches
from io import BytesIO
from typing import ClassVar

import openpyxl
import requests
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FetchLog, Indicator, IndicatorData
from app.services.base_parser import BaseParser
from app.services.http_client import create_session

logger = logging.getLogger(__name__)

NEDEL_IPC_URL = "https://rosstat.gov.ru/storage/mediabank/nedel_Ipc.xlsx"
NEDEL_IPC_URL_FALLBACK = "https://rosstat.gov.ru/storage/mediabank/Nedel_ipc.xlsx"
IPC_SPR_URL = "https://rosstat.gov.ru/storage/mediabank/ipc_spr_{mm}-{yyyy}.xlsx"

ROSSTAT_SEARCH_URL = "https://rosstat.gov.ru/search"
BULLETIN_URL_RE = re.compile(r"/storage/mediabank/\d+_\d{2}-\d{2}-\d{4}\.html?")

_MONTH_MAP = {
    "января": 1, "февраля": 2, "марта": 3, "апреля": 4,
    "мая": 5, "июня": 6, "июля": 7, "августа": 8,
    "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12,
}

_BULLETIN_RANGE_RE = re.compile(
    r"с\s+\d{1,2}\s+(?:[а-яё]+\s+)?по\s+(\d{1,2})\s+([а-яё]+)\s+(\d{4})\s*г",
    re.IGNORECASE,
)
_BULLETIN_VALUE_RE = re.compile(r"составил\s+(\d+[,.]?\d*)\s*%")

_HEADER_RE = re.compile(
    r"на\s+(\d{1,2})\s+("
    + "|".join(_MONTH_MAP.keys())
    + r")",
    re.IGNORECASE,
)


@dataclass
class WeeklyPoint:
    date: date
    value: float


def _parse_column_date(header: str, year: int) -> date | None:
    """Parse 'на 10 января **' → date(year, 1, 10)."""
    m = _HEADER_RE.search(header)
    if not m:
        return None
    day = int(m.group(1))
    month = _MONTH_MAP.get(m.group(2).lower())
    if month is None:
        return None
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _load_weights(session: requests.Session) -> dict[str, float]:
    """Download ipc_spr and extract per-product weights.

    Tries recent months (descending) to find the latest available file.
    Returns {product_name: weight}.
    """
    today = date.today()
    for month_offset in range(0, 6):
        m = today.month - month_offset
        y = today.year
        while m <= 0:
            m += 12
            y -= 1
        url = IPC_SPR_URL.format(mm=f"{m:02d}", yyyy=y)
        try:
            r = session.get(url, timeout=30, verify=False)
            if r.status_code == 200 and len(r.content) > 5000:
                break
        except requests.RequestException:
            continue
    else:
        logger.warning("Could not download ipc_spr for weights")
        return {}

    wb = openpyxl.load_workbook(BytesIO(r.content), data_only=True)
    sheet_name = None
    for sn in reversed(wb.sheetnames):
        if sn != "Содержание":
            sheet_name = sn
            break
    if not sheet_name:
        return {}

    ws = wb[sheet_name]
    weights: dict[str, float] = {}
    for ri in range(7, ws.max_row + 1):
        name = str(ws.cell(ri, 1).value or "").strip()
        w_raw = ws.cell(ri, 3).value
        if not name or w_raw is None:
            continue
        try:
            w = float(w_raw)
        except (ValueError, TypeError):
            continue
        if w > 0:
            weights[name] = w
    return weights


def _match_weight(name: str, weights: dict[str, float],
                  cache: dict[str, float | None]) -> float | None:
    """Find the weight for a weekly product name, caching fuzzy results."""
    if name in cache:
        return cache[name]
    w = weights.get(name)
    if w is not None:
        cache[name] = w
        return w
    close = get_close_matches(name, weights.keys(), n=1, cutoff=0.75)
    if close:
        w = weights[close[0]]
        cache[name] = w
        return w
    cache[name] = None
    return None


def _parse_weekly_xlsx(weekly_content: bytes, weights: dict[str, float]) -> list[WeeklyPoint]:
    """Parse Nedel_ipc.xlsx and compute weighted-average weekly CPI."""
    wb = openpyxl.load_workbook(BytesIO(weekly_content), data_only=True)
    points: list[WeeklyPoint] = []
    match_cache: dict[str, float | None] = {}

    for sheet_name in wb.sheetnames:
        if sheet_name == "Содержание":
            continue
        try:
            year = int(sheet_name)
        except ValueError:
            continue

        ws = wb[sheet_name]
        header_row = 4

        col_dates: list[tuple[int, date]] = []
        for ci in range(2, ws.max_column + 1):
            hdr = str(ws.cell(header_row, ci).value or "")
            d = _parse_column_date(hdr, year)
            if d:
                col_dates.append((ci, d))

        if not col_dates:
            continue

        products: list[tuple[int, str, float]] = []
        for ri in range(5, ws.max_row + 1):
            name = str(ws.cell(ri, 1).value or "").strip()
            if not name or name.startswith("*") or name.startswith("…"):
                continue
            w = _match_weight(name, weights, match_cache)
            if w is None:
                continue
            products.append((ri, name, w))

        for ci, d in col_dates:
            weighted_sum = 0.0
            weight_sum = 0.0
            for ri, name, w in products:
                raw = ws.cell(ri, ci).value
                if raw is None or raw == "…" or raw == "":
                    continue
                try:
                    val = float(str(raw).replace(",", ".").replace("\u2212", "-"))
                except (ValueError, TypeError):
                    continue
                if 95 < val < 110:
                    weighted_sum += w * val
                    weight_sum += w

            if weight_sum > 0:
                aggregate = weighted_sum / weight_sum
                points.append(WeeklyPoint(date=d, value=round(aggregate, 2)))

    points.sort(key=lambda p: p.date)
    return points


def _strip_html(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", text)


def _parse_bulletin_html(html: str) -> WeeklyPoint | None:
    """Extract (end_date, value) from a weekly CPI bulletin HTML."""
    text = _strip_html(html)
    m_range = _BULLETIN_RANGE_RE.search(text)
    m_val = _BULLETIN_VALUE_RE.search(text)
    if not m_range or not m_val:
        return None
    end_day = int(m_range.group(1))
    month = _MONTH_MAP.get(m_range.group(2).lower())
    year = int(m_range.group(3))
    if month is None:
        return None
    try:
        d = date(year, month, end_day)
    except ValueError:
        return None
    try:
        v = float(m_val.group(1).replace(",", "."))
    except ValueError:
        return None
    if not (95 < v < 110):
        return None
    return WeeklyPoint(date=d, value=round(v, 2))


CENTRAL_NEWS_URL = "https://rosstat.gov.ru/central-news"
CENTRAL_NEWS_MAX_PAGES = 70
_CPI_BULLETIN_TITLE_RE = re.compile(
    r"оценке\s+индекса\s+потребительских\s+цен", re.IGNORECASE,
)


def _find_bulletin_urls_central_news(
    session: requests.Session, year: int, max_pages: int = CENTRAL_NEWS_MAX_PAGES,
) -> list[str]:
    """Discover weekly CPI bulletin URLs via central-news pagination.

    Альтернатива `_find_bulletin_urls` (через rosstat search) — central-news
    crawl надёжнее: пагинированный список новостей с заголовками и стабильным
    layout, нет лимитов поискового API. Архив доступен с **2023-05-04** до
    последней публикации (на page=1). За пределы 2023-05 уходить нельзя:
    page=66+ возвращают пустую ленту (Росстат очистил).

    Останавливаемся когда:
    1. На странице нашли bulletin с годом меньше `year` (мы прошли границу)
    2. Страница пустая (mediabank-links нет)
    3. Достигли `max_pages`.
    """
    found: set[str] = set()
    for page in range(1, max_pages + 1):
        try:
            r = session.get(
                CENTRAL_NEWS_URL,
                params={"page": page},
                timeout=20,
                verify=False,
            )
            if r.status_code != 200:
                logger.warning(
                    "central-news page=%d HTTP %d", page, r.status_code,
                )
                continue
            text = r.text
            items = re.findall(
                r'href="(/storage/mediabank/\d+_\d{2}-\d{2}-\d{4}\.html)"\s*[^>]*>\s*([^<]{15,300})',
                text,
            )
            if not items:
                logger.info("central-news page=%d empty — stopping", page)
                break
            page_year_min = 9999
            page_year_max = 0
            page_added = 0
            for href, title in items:
                ym = re.search(r"-(\d{4})\.html$", href)
                if not ym:
                    continue
                bul_year = int(ym.group(1))
                page_year_min = min(page_year_min, bul_year)
                page_year_max = max(page_year_max, bul_year)
                if bul_year != year:
                    continue
                if not _CPI_BULLETIN_TITLE_RE.search(title):
                    continue
                found.add("https://rosstat.gov.ru" + href)
                page_added += 1
            logger.debug(
                "central-news page=%d: years=%d-%d, added=%d (cumulative=%d)",
                page, page_year_min, page_year_max, page_added, len(found),
            )
            if page_year_max < year:
                logger.info(
                    "central-news page=%d max_year=%d < %d — stopping crawl",
                    page, page_year_max, year,
                )
                break
        except requests.RequestException as exc:
            logger.warning(
                "central-news page=%d request failed: %s", page, exc,
            )
    return sorted(found)


def _find_bulletin_urls(session: requests.Session, year: int) -> list[str]:
    """Find weekly CPI bulletin URLs for `year`.

    Стратегия: central-news crawl (primary) + rosstat search (fallback).
    Объединение — set union. central-news вернёт всё что есть в архиве за
    год (2023-05-04 + → today), search закрывает edge cases когда новый
    bulletin ещё не на page=1 central-news, но уже индексирован поиском.
    """
    via_central = _find_bulletin_urls_central_news(session, year)
    logger.info(
        "Bulletin discovery for year=%d: central-news=%d urls", year, len(via_central),
    )

    via_search: set[str] = set()
    today = date.today()
    month_range = range(1, 13) if year < today.year else range(1, today.month + 1)
    for month in month_range:
        month_name = next(
            (name for name, num in _MONTH_MAP.items() if num == month), None,
        )
        if not month_name:
            continue
        q = f"оценке индекса потребительских цен {month_name} {year}"
        try:
            r = session.get(
                ROSSTAT_SEARCH_URL, params={"q": q}, timeout=30, verify=False,
            )
            if r.status_code != 200:
                continue
            for m in BULLETIN_URL_RE.finditer(r.text):
                path = m.group(0)
                if f"-{year}." in path:
                    via_search.add("https://rosstat.gov.ru" + path)
        except requests.RequestException as exc:
            logger.warning("Rosstat search failed for %s %d: %s", month_name, year, exc)

    logger.info(
        "Bulletin discovery for year=%d: search=%d urls, union total=%d",
        year, len(via_search), len(set(via_central) | via_search),
    )
    return sorted(set(via_central) | via_search)


_BULLETIN_PUB_DATE_RE = re.compile(r"/(\d+)_(\d{2})-(\d{2})-(\d{4})\.html$")


def _bulletin_pub_date(url: str) -> date | None:
    """Extract publication date from a bulletin URL.

    The publication date in the URL is **not** the same as the week-end date
    inside the bulletin (publication is typically Wed; week-end is Sun/Mon
    of the prior week). But it's close enough — week-end is within 7-10 days
    before publication. We use that for skip-heuristics in steady-state.
    """
    m = _BULLETIN_PUB_DATE_RE.search(url)
    if not m:
        return None
    try:
        return date(int(m.group(4)), int(m.group(3)), int(m.group(2)))
    except ValueError:
        return None


def fetch_bulletin_points(
    session: requests.Session,
    years: list[int],
    existing_dates: set[date] | None = None,
) -> list[WeeklyPoint]:
    """Fetch weekly CPI from Rosstat HTML bulletins for the given years.

    `existing_dates`: если задано, GET'ы для bulletin'ов с publication-датой
    `>= 14 days ранее max(existing_dates)` будут пропущены — их week-end
    точно уже в БД. Это снижает steady-state GET'ов от сотен до 1-3.
    """
    points: list[WeeklyPoint] = []
    seen_dates: set[date] = set()
    skip_pub_before: date | None = None
    if existing_dates:
        max_known = max(existing_dates)
        skip_pub_before = max_known - timedelta(days=14)
    skipped = 0
    for year in years:
        urls = _find_bulletin_urls(session, year)
        logger.info("Weekly CPI bulletins for %d: %d URLs", year, len(urls))
        for url in urls:
            if skip_pub_before is not None:
                pub = _bulletin_pub_date(url)
                if pub is not None and pub < skip_pub_before:
                    skipped += 1
                    continue
            try:
                r = session.get(url, timeout=30, verify=False)
                if r.status_code != 200:
                    continue
                html = r.content.decode("utf-8", errors="replace")
                pt = _parse_bulletin_html(html)
                if pt and pt.date not in seen_dates:
                    seen_dates.add(pt.date)
                    points.append(pt)
            except requests.RequestException as exc:
                logger.warning("Failed to fetch bulletin %s: %s", url, exc)
    if skipped:
        logger.info(
            "Weekly CPI: skipped %d bulletin GETs (pub_date < %s, week-end already in DB)",
            skipped, skip_pub_before,
        )
    points.sort(key=lambda p: p.date)
    return points


def fetch_weekly_cpi(
    existing_dates: set[date] | None = None,
    cutoff_date: date | None = None,
) -> list[WeeklyPoint]:
    """Fetch weekly CPI: HTML bulletins (primary) + XLSX (fallback/history).

    HTML values take precedence for overlapping dates — они совпадают с
    официальными Росстата, XLSX-взвешенное среднее — лишь приближение
    по продовольственной корзине.

    `cutoff_date`: если задано, отбрасываются точки **до** этой даты. Используется
    чтобы не подмешивать XLSX-approximation за годы, когда Росстат уже публиковал
    официальные HTML-бюллетени, но архив на rosstat.gov.ru не дотягивается
    глубоко в прошлое (текущий cutoff = 2023-01-09: первый bulletin доступный
    из central-news архива и rosstat search). Сверка XLSX-approximation 2022
    с monthly CPI показала расхождения до 3 pp (март 2022 — взвешенный food
    CPI занижает общий ИПЦ из-за скачка непродов/услуг). См.
    `docs/missed_data_audit.md::Nedel_ipc`.
    """
    session = create_session()
    try:
        session.verify = False

        today = date.today()
        # 2023 — первый год, в котором Росстат начал публиковать недельные
        # bulletin'ы «Об оценке индекса потребительских цен с N по M». До этого
        # были только monthly публикации «Об индексе потребительских цен в
        # <месяц> YYYY». Подтверждено deep dive 2026-05-12: Wayback Machine
        # CDX search для `rosstat.gov.ru/storage/mediabank/*.htm` 2021-2023
        # вернул 174 уникальных дат, 0 weekly-bulletin'ов за 2021, 0 за 2022,
        # 1 за 2023-02-08. См. `docs/audits/weekly_inflation_research_2026-05.md`.
        #
        # Steady-state оптимизация (2026-05-28): если в `existing_dates` уже
        # есть точка за прошлый год — backfill bulletin'ов 2023..(today.year-1)
        # точно сделан, повторять не нужно. Качаем только current year.
        # Это снижает 4-летний crawl × 12 search-запросов до 1-летнего ×
        # current_month-запросов в steady-state, ETL укладывается в <60с
        # вместо 5+ минут.
        BULLETIN_FIRST_YEAR = 2023
        last_year = today.year - 1
        steady_state = bool(
            existing_dates and any(d.year <= last_year for d in existing_dates)
        )
        if steady_state:
            bulletin_years = [today.year]
            logger.info(
                "Weekly CPI steady-state: %d existing points incl. %d-%d, "
                "fetching only current year %d",
                len(existing_dates or ()), BULLETIN_FIRST_YEAR, last_year, today.year,
            )
        else:
            bulletin_years = list(range(BULLETIN_FIRST_YEAR, today.year + 1))
            logger.info(
                "Weekly CPI cold-start: fetching backfill for years %s", bulletin_years,
            )

        bulletin_points = fetch_bulletin_points(session, bulletin_years, existing_dates)
        logger.info("Weekly CPI: parsed %d points from HTML bulletins", len(bulletin_points))

        # XLSX fallback нужен только при cold-start (нет данных в БД) — он
        # покрывает недели до cutoff_date, где HTML-бюллетеней не было.
        # В steady-state весь этот диапазон уже в БД, XLSX качать смысла нет.
        xlsx_points: list[WeeklyPoint] = []
        if steady_state:
            logger.info("Weekly CPI: skipping XLSX fallback in steady-state")
        else:
            for xlsx_url in (NEDEL_IPC_URL, NEDEL_IPC_URL_FALLBACK):
                logger.info("Downloading weekly XLSX: %s", xlsx_url)
                try:
                    r = session.get(xlsx_url, timeout=60)
                    if r.status_code != 200:
                        logger.warning("HTTP %d for %s", r.status_code, xlsx_url)
                        continue
                    weights = _load_weights(session)
                    if not weights:
                        logger.warning("No weights available — XLSX fallback skipped")
                        break
                    xlsx_points = _parse_weekly_xlsx(r.content, weights)
                    logger.info("Weekly CPI: parsed %d points from %s", len(xlsx_points), xlsx_url)
                    break
                except requests.RequestException as exc:
                    logger.warning("XLSX fetch failed for %s: %s", xlsx_url, exc)

        merged: dict[date, float] = {p.date: p.value for p in xlsx_points}
        for p in bulletin_points:
            merged[p.date] = p.value
        points = [WeeklyPoint(date=d, value=v) for d, v in sorted(merged.items())]
        logger.info(
            "Weekly CPI: merged %d points (HTML: %d, XLSX: %d)",
            len(points), len(bulletin_points), len(xlsx_points),
        )

        if cutoff_date:
            before = len(points)
            points = [p for p in points if p.date >= cutoff_date]
            logger.info(
                "Weekly CPI: cutoff_date=%s — %d → %d points",
                cutoff_date, before, len(points),
            )

        if existing_dates:
            points = [p for p in points if p.date not in existing_dates]
            logger.info("Weekly CPI: %d new points after filtering existing", len(points))

        return points
    finally:
        session.close()


class RosstatWeeklyCpiParser(BaseParser):
    parser_type: ClassVar[str] = "rosstat_weekly_cpi"

    async def _fetch_and_parse(
        self,
        db: AsyncSession,
        indicator: Indicator,
        cfg: dict,
        fetch_log: FetchLog,
    ) -> tuple[list, str]:
        cutoff_raw = cfg.get("weekly_cutoff_date")
        cutoff: date | None = None
        if cutoff_raw:
            try:
                cutoff = date.fromisoformat(str(cutoff_raw))
            except ValueError:
                logger.warning(
                    "Weekly CPI: invalid weekly_cutoff_date=%r, ignoring", cutoff_raw,
                )

        # Steady-state guard: проброс existing_dates позволяет парсеру пропускать
        # GET-запросы за bulletin'ы, week-end которых заведомо уже в БД, и
        # не качать XLSX-fallback / backfill за прошлые годы (см. fetch_weekly_cpi).
        existing_q = await db.execute(
            select(IndicatorData.date).where(IndicatorData.indicator_id == indicator.id)
        )
        existing_dates: set[date] = {row[0] for row in existing_q.all()}
        logger.info("Weekly CPI: %d existing points in DB", len(existing_dates))

        points = await asyncio.to_thread(
            fetch_weekly_cpi, existing_dates, cutoff,
        )
        return points, NEDEL_IPC_URL
