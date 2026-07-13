"""ETL: Минфин open data CSV → IndicatorData (monthly budget deficit/surplus).

Source: https://minfin.gov.ru/opendata/7710168360-fedbud_month/
Format: CSV (comma-separated, UTF-8 BOM), cumulative from year start.
Columns: Год, Месяц, Доходы всего, ..., Расходы всего, ..., Дефицит/Профицит, ...

Resilience (2026-07):
- Minfin-specific HTTP retries (stronger than global http_client defaults).
- Process-level short TTL cache of discovered CSV URL — three budget indicators
  share one catalog hit per ETL wave.
- Persist last-good CSV URL in state Redis; on catalog 503 fall back to it.
- Canonical CSV path is WITHOUT `/ru/` (`…/opendata/…/data-*.csv`). The
  `/ru/opendata/…/data-*.csv` variant returns 404.
"""

from __future__ import annotations

import asyncio
import csv
import io
import logging
import re
import threading
import time
from pathlib import Path
from dataclasses import dataclass
from datetime import date
from typing import ClassVar

from bs4 import BeautifulSoup
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from urllib3.util.retry import Retry

from app.models import FetchLog, Indicator, IndicatorData
from app.services.base_parser import BaseParser
from app.services.calculation_engine import calculation_engine
from app.services.http_client import create_session

logger = logging.getLogger(__name__)

CATALOG_URL = "https://minfin.gov.ru/opendata/7710168360-fedbud_month/"
# Упакованный снимок на случай блок/503 всего minfin.gov.ru с прод-IP.
_ARTIFACT_CSV = (
    Path(__file__).resolve().parent.parent / "data" / "minfin" / "fedbud_month.csv"
)
# New passport files use `data-YYYYMMDDTHHMM-structure-…T….csv`; older ones omit
# the `THHMM` segment. Accept both so discovery does not silently empty out.
_DATA_RE = re.compile(
    r"data-\d{8}(?:T\d{4})?-structure-\d{8}(?:T\d{4})?\.csv",
    re.IGNORECASE,
)
# `/ru/opendata/.../data-*.csv` → 404; strip the locale segment for file URLs.
_RU_OPENDATA_RE = re.compile(
    r"(https?://minfin\.gov\.ru)/ru(/opendata/)",
    re.IGNORECASE,
)

# 403/429/503 — один ответ в ProxyFallbackSession (direct → HTTP → Tor SOCKS),
# без urllib3-retry на ban-статусах (иначе минуты на 503 до hop).
# connect/read = 1: иначе hung-сокет × timeout=45–90 сжигает ETL_TIMEOUT 300с
# до artifact-fallback (ночные timeout 2026-07-12/13 при живом Tor днём).
_MINFIN_RETRY = Retry(
    total=1,
    connect=1,
    read=1,
    backoff_factor=0.5,
    status_forcelist=[408, 500, 502, 504],
    allowed_methods=["GET", "HEAD"],
    raise_on_status=False,
)

_CSV_URL_CACHE_TTL_SEC = 600  # process cache: one catalog hit for 3 indicators
_CSV_URL_STATE_KEY = "etl:minfin:fedbud_month:csv_url"
_CSV_URL_STATE_TTL_SEC = 60 * 60 * 24 * 90  # 90 days across restarts / 503 windows

_csv_url_lock = threading.Lock()
_csv_url_cache: tuple[float, str] | None = None

PRESS_LIST_URL = "https://minfin.gov.ru/ru/press-center/"
PRESS_TITLE_RE = re.compile(
    r"Предварительная\s+оценка\s+исполнения\s+федерального\s+бюджета\s+за\s+январь-",
    re.IGNORECASE,
)
PRESS_PERIOD_RE = re.compile(
    r"за\s+январь-([а-яё]+)\s+(\d{4})", re.IGNORECASE,
)

MONTH_MAP = {
    "январь": 1, "февраль": 2, "март": 3, "апрель": 4,
    "май": 5, "июнь": 6, "июль": 7, "август": 8,
    "сентябрь": 9, "октябрь": 10, "ноябрь": 11, "декабрь": 12,
}
# Genitive forms used inside "за январь-АПРЕЛЯ 2026" wording on press releases.
MONTH_GENITIVE_MAP = {
    "января": 1, "февраля": 2, "марта": 3, "апреля": 4,
    "мая": 5, "июня": 6, "июля": 7, "августа": 8,
    "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12,
}


@dataclass
class BudgetPoint:
    date: date
    value: float


def _create_minfin_session(*, timeout: int = 25):
    return create_session(timeout=timeout, retry=_MINFIN_RETRY)


def normalize_minfin_csv_url(url: str) -> str:
    """Canonicalise Minfin OpenData CSV URL: drop `/ru/` before `/opendata/`."""
    return _RU_OPENDATA_RE.sub(r"\1\2", url.strip())


def _persist_csv_url(url: str) -> None:
    try:
        from app.core.cache import get_state_redis_sync

        r = get_state_redis_sync()
        r.set(_CSV_URL_STATE_KEY, url, ex=_CSV_URL_STATE_TTL_SEC)
    except Exception as exc:
        logger.warning("Minfin: could not persist last-good CSV URL: %s", exc)


def _load_persisted_csv_url() -> str | None:
    try:
        from app.core.cache import get_state_redis_sync

        r = get_state_redis_sync()
        raw = r.get(_CSV_URL_STATE_KEY)
        if not raw:
            return None
        return normalize_minfin_csv_url(str(raw))
    except Exception as exc:
        logger.warning("Minfin: could not load last-good CSV URL: %s", exc)
        return None


def _invalidate_csv_url_cache() -> None:
    global _csv_url_cache
    with _csv_url_lock:
        _csv_url_cache = None


def _discover_csv_url_from_catalog(session) -> str:
    """Hit the catalog page and pick the lexicographically latest data-*.csv."""
    resp = session.get(CATALOG_URL, timeout=25)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    candidates: list[str] = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not _DATA_RE.search(href):
            continue
        if not href.startswith("http"):
            href = f"https://minfin.gov.ru{href}"
        candidates.append(normalize_minfin_csv_url(href))
    # Deduplicate after normalisation (page often lists the same file 2–3×).
    candidates = sorted(set(candidates), reverse=True)
    if not candidates:
        raise RuntimeError("Minfin: could not find data CSV link on catalog page")
    if len(candidates) > 1:
        logger.info(
            "Minfin: %d CSV candidates, picking latest: %s",
            len(candidates),
            candidates[0].rsplit("/", 1)[-1],
        )
    return candidates[0]


def _cache_get_csv_url() -> str | None:
    with _csv_url_lock:
        if _csv_url_cache is None:
            return None
        cached_at, cached_url = _csv_url_cache
        if time.monotonic() - cached_at >= _CSV_URL_CACHE_TTL_SEC:
            return None
        return cached_url


def _cache_set_csv_url(url: str) -> None:
    global _csv_url_cache
    with _csv_url_lock:
        _csv_url_cache = (time.monotonic(), url)


def _find_csv_url(*, force_catalog: bool = False) -> str:
    """Discover the latest Minfin budget CSV URL with cache + last-good fallback.

    Order:
    1. Process TTL cache (shared by budget-revenue/expenditure/deficit),
       unless `force_catalog=True`.
    2. Live catalog discovery (Minfin-strong retries).
    3. On catalog failure — last-good URL from state Redis (if any).
       Skipped when `force_catalog=True` (404 recovery must not re-use stale).
    """
    if not force_catalog:
        cached = _cache_get_csv_url()
        if cached:
            return cached

    session = _create_minfin_session(timeout=25)
    try:
        try:
            url = _discover_csv_url_from_catalog(session)
        except Exception as exc:
            if force_catalog:
                raise
            fallback = _load_persisted_csv_url()
            if fallback:
                logger.warning(
                    "Minfin catalog discovery failed (%s); "
                    "using persisted last-good CSV: %s",
                    exc,
                    fallback.rsplit("/", 1)[-1],
                )
                _cache_set_csv_url(fallback)
                return fallback
            raise
    finally:
        session.close()

    _cache_set_csv_url(url)
    _persist_csv_url(url)
    return url


def _find_col_index(header: list[str], target: str) -> int | None:
    """Find column index by partial match in header."""
    for i, col in enumerate(header):
        col_clean = col.strip().replace("\ufeff", "")
        if target in col_clean:
            return i
    return None


def _parse_budget_csv(content: str, target: str = "deficit") -> list[BudgetPoint]:
    """Parse Minfin budget CSV.

    target: "deficit" (default), "revenue", "expenditure"
    All columns are cumulative from year start → convert to monthly.
    """
    reader = csv.reader(io.StringIO(content))
    header = next(reader)

    col_idx = None
    if target == "deficit":
        col_idx = _find_col_index(header, "Дефицит")
    elif target == "revenue":
        col_idx = _find_col_index(header, "Доходы, всего")
    elif target == "expenditure":
        col_idx = _find_col_index(header, "Расходы, всего")
    else:
        raise ValueError(f"Unknown budget target: {target}")

    rows_by_year: dict[int, list[tuple[int, float]]] = {}
    for row in reader:
        if len(row) < 3:
            continue
        try:
            year = int(row[0].strip())
        except (ValueError, IndexError):
            continue
        month_str = row[1].strip().lower()
        month = MONTH_MAP.get(month_str)
        if not month:
            continue

        cumulative = None
        if col_idx is not None and col_idx < len(row):
            raw = row[col_idx].strip().replace("\u2212", "-").replace(",", ".")
            if raw and raw != "":
                try:
                    cumulative = float(raw)
                except ValueError:
                    pass
        if cumulative is None and target == "deficit":
            rev = _find_col_index(header, "Доходы, всего")
            exp = _find_col_index(header, "Расходы, всего")
            if rev is not None and exp is not None:
                try:
                    rev_raw = row[rev].strip().replace("\u2212", "-").replace(",", ".")
                    exp_raw = row[exp].strip().replace("\u2212", "-").replace(",", ".")
                    cumulative = float(rev_raw) - float(exp_raw)
                except (ValueError, IndexError):
                    continue
        if cumulative is None:
            continue

        rows_by_year.setdefault(year, []).append((month, cumulative))

    points: list[BudgetPoint] = []
    for year, month_data in sorted(rows_by_year.items()):
        # Накопленный с начала года → помесячный: monthly[M] = cum[M] − cum[M−1].
        # При ПРОПУСКЕ месяца предыдущий накопленный неизвестен, поэтому
        # cum[M] − cum[last<M] = сумма за все пропущенные месяцы, списанная в
        # один — артефакт (ложный «месяц» в 2-3 раза больше реального). Считаем
        # помесячное значение только когда непосредственно предыдущий месяц есть
        # в данных (или это январь — старт года). Иначе точку пропускаем.
        cum_by_month = {m: c for m, c in month_data}
        for month in sorted(cum_by_month):
            cumulative = cum_by_month[month]
            if month == 1:
                monthly = cumulative
            elif (month - 1) in cum_by_month:
                monthly = cumulative - cum_by_month[month - 1]
            else:
                logger.warning(
                    "Minfin budget CSV (%s): месяц %d-%02d без предыдущего месяца "
                    "в данных — пропускаем (нельзя выделить помесячное из накопленного)",
                    target, year, month,
                )
                continue
            points.append(BudgetPoint(date=date(year, month, 1), value=round(monthly, 1)))

    return points


def _parse_ru_int(raw: str) -> float | None:
    """Parse a Russian-formatted integer with non-breaking-space thousand sep.

    Accepts "11 721", "-5 877", "-3\xa0786", "12 885,3" etc.
    Returns None if conversion fails.
    """
    if not raw:
        return None
    cleaned = (
        raw.replace("\u00a0", "")
        .replace("\u2009", "")
        .replace("\u2212", "-")
        .replace(" ", "")
        .replace(",", ".")
    )
    try:
        return float(cleaned)
    except ValueError:
        return None


def _find_latest_preliminary_press_url() -> str | None:
    """Locate the most recent "Предварительная оценка исполнения федерального
    бюджета за январь-MM YYYY" press release URL on the Minfin press-centre.

    Returns None when no such release is currently linked from the listing —
    in that case the press fallback is silently disabled (CSV-only behaviour).
    """
    session = _create_minfin_session(timeout=25)
    try:
        resp = session.get(PRESS_LIST_URL, timeout=45)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for a in soup.find_all("a", href=True):
            text = (a.get_text() or "").strip()
            if PRESS_TITLE_RE.search(text):
                href = a["href"]
                if not href.startswith("http"):
                    href = f"https://minfin.gov.ru{href}"
                return href
        return None
    finally:
        session.close()


def _parse_press_release_cumulative(html: str) -> tuple[int, int, dict[str, float]] | None:
    """Extract the "янв-MM YYYY" cumulative row from a preliminary press release.

    Returns (year, end_month, {"revenue": …, "expenditure": …, "deficit": …})
    or None if the page doesn't match the expected format.

    Контракт source-страницы: одна `<table>` с заголовком вида
    `["", "янв-апр 2026 *", "янв-апр 2025", "%, г/г", "утверждено …"]` —
    строки `ДОХОДЫ`, `РАСХОДЫ`, `ДЕФИЦИТ % ВВП`. См. probe в этом коммите.
    """
    soup = BeautifulSoup(html, "html.parser")

    full_text = soup.get_text(" ", strip=True)
    period_m = PRESS_PERIOD_RE.search(full_text)
    if not period_m:
        return None
    month_word = period_m.group(1).lower()
    end_month = MONTH_GENITIVE_MAP.get(month_word) or MONTH_MAP.get(month_word)
    if not end_month:
        return None
    year = int(period_m.group(2))

    table = soup.find("table")
    if table is None:
        return None

    out: dict[str, float] = {}
    for row in table.find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in row.find_all(["td", "th"])]
        if len(cells) < 2:
            continue
        label = cells[0].upper().strip()
        value_cell = cells[1]
        # The deficit row mixes value and %-of-GDP in the same cell:
        # "-5 877 -2,5%" — take only the first numeric token.
        first_token = re.match(r"([\-\u2212]?\s*\d[\d\s\u00a0\u2009]*)", value_cell)
        if not first_token:
            continue
        value = _parse_ru_int(first_token.group(1))
        if value is None:
            continue

        # Match major rows. Exclude sub-rows ("НЕФТЕГАЗОВЫЕ", "НДС",
        # "государственные закупки") by requiring exact start of label.
        if label.startswith("ДОХОДЫ") and "ДОХОД" in label and "НЕФТ" not in label and "НДС" not in label:
            out["revenue"] = value
        elif label.startswith("РАСХОДЫ") and "ГОСУДАРСТВЕННЫЕ" not in label and "ЗАКУПКИ" not in label:
            out["expenditure"] = value
        elif label.startswith("ДЕФИЦИТ"):
            out["deficit"] = value

    if not {"revenue", "expenditure", "deficit"}.issubset(out):
        logger.warning(
            "Minfin press release: missing fields, got %s", sorted(out.keys()),
        )
        return None
    return year, end_month, out


def _augment_with_press_preliminary(
    points: list[BudgetPoint],
    target: str,
) -> tuple[list[BudgetPoint], str | None]:
    """Если в CSV нет данных за последний опубликованный пресс-релизом месяц —
    дополнить ряд preliminary-значением (вычисленным как cumulative − CSV-сумма).

    Returns (augmented_points, press_url_or_None). Если пресс-релиз ничего
    нового не привнёс — points возвращаются без изменений, url=None.

    Идемпотентность: при следующем ETL, когда OpenData CSV обновится,
    `bulk_upsert` перепишет preliminary-точку на финальную (см. ADR-0002:
    `ON CONFLICT DO UPDATE WHERE value <> excluded.value`).
    """
    if target not in ("deficit", "revenue", "expenditure"):
        return points, None
    if not points:
        return points, None

    try:
        press_url = _find_latest_preliminary_press_url()
    except Exception as exc:
        logger.warning("Minfin press release discovery failed: %s", exc)
        return points, None
    if not press_url:
        return points, None

    session = _create_minfin_session(timeout=25)
    try:
        resp = session.get(press_url, timeout=45)
        resp.raise_for_status()
        parsed = _parse_press_release_cumulative(resp.text)
    except Exception as exc:
        logger.warning("Minfin press release fetch/parse failed: %s", exc)
        return points, None
    finally:
        session.close()

    if not parsed:
        return points, None

    year, end_month, totals = parsed
    target_value = totals.get(target)
    if target_value is None:
        return points, None

    csv_year_points = [p for p in points if p.date.year == year and p.date.month <= end_month]
    if csv_year_points and any(p.date.month == end_month for p in csv_year_points):
        # CSV already covers the press-release month; nothing to do.
        return points, None

    csv_sum_prior = sum(p.value for p in csv_year_points)
    monthly_value = round(target_value - csv_sum_prior, 1)

    if monthly_value == 0.0 and target == "deficit":
        # Sanity: zero monthly deficit на пресс-релизе вероятнее всего
        # означает что мы ошиблись с парсингом, чем что бюджет за месяц
        # был ровно сбалансирован — лучше ничего не добавлять.
        logger.warning(
            "Minfin press preliminary: monthly %s for %d-%02d came out 0.0; "
            "press_total=%.1f, csv_prior_sum=%.1f — skipping",
            target, year, end_month, target_value, csv_sum_prior,
        )
        return points, None

    augmented = list(points)
    augmented.append(BudgetPoint(
        date=date(year, end_month, 1), value=monthly_value,
    ))
    augmented.sort(key=lambda p: p.date)
    logger.info(
        "Minfin press preliminary augmented %s with %d-%02d=%.1f "
        "(cumulative %.1f − csv_prior_sum %.1f); url=%s",
        target, year, end_month, monthly_value,
        target_value, csv_sum_prior, press_url,
    )
    return augmented, press_url


def fetch_and_parse_budget(target: str = "deficit") -> tuple[list[BudgetPoint], str]:
    """Download and parse the Minfin OpenData budget CSV (CSV-only).

    Только официальный OpenData CSV (финальные накопленные значения).
    Пресс-релиз «Предварительная оценка исполнения федерального бюджета»
    БОЛЬШЕ НЕ подмешивается: его накопленное за «янв-MM» при отстающем CSV
    давало ложный «месяц» = сумма нескольких пропущенных месяцев (артефакт
    ~10 трлн / дефицит −2,5 трлн). Когда OpenData CSV догоняет, ряд
    дозаполняется корректными помесячными значениями автоматически (daily ETL).
    Helpers `_find_latest_preliminary_press_url` / `_parse_press_release_cumulative`
    / `_augment_with_press_preliminary` оставлены для возможного будущего
    использования, но в пайплайне не вызываются.

    URL discovery: process TTL cache + state-Redis last-good fallback on 503
    (см. `_find_csv_url`). CSV path всегда без `/ru/`.

    Если весь minfin.gov.ru недоступен с прод-IP (стабильный 503 на весь хост —
    инцидент 2026-07), берём упакованный снимок
    `app/data/minfin/fedbud_month.csv` (обновлять с машины, где Минфин
    открывается: `curl …/data-*.csv -o backend/app/data/minfin/fedbud_month.csv`).
    """
    try:
        csv_url = normalize_minfin_csv_url(_find_csv_url())
        session = _create_minfin_session(timeout=40)
        try:
            resp = session.get(csv_url, timeout=40)
            # Rare: stale last-good or locale-prefixed URL → 404. Retry once after
            # force re-discover if we were on a fallback path.
            if resp.status_code == 404:
                logger.warning(
                    "Minfin CSV 404 at %s — invalidating cache and re-discovering",
                    csv_url.rsplit("/", 1)[-1],
                )
                _invalidate_csv_url_cache()
                csv_url = normalize_minfin_csv_url(_find_csv_url(force_catalog=True))
                resp = session.get(csv_url, timeout=40)
            resp.raise_for_status()
            resp.encoding = "utf-8"
            points = _parse_budget_csv(resp.text, target=target)
        finally:
            session.close()

        if points:
            _persist_csv_url(csv_url)
        return points, csv_url
    except Exception as exc:
        artifact = _ARTIFACT_CSV
        if not artifact.is_file():
            raise
        logger.warning(
            "Minfin network fetch failed (%s); using packaged artifact %s "
            "(прод-IP иногда получает 503 на весь minfin.gov.ru)",
            exc,
            artifact.name,
        )
        text = artifact.read_text(encoding="utf-8-sig")
        points = _parse_budget_csv(text, target=target)
        if not points:
            raise RuntimeError(
                f"Minfin artifact {artifact.name} parsed 0 points after network failure"
            ) from exc
        return points, f"artifact://{artifact.name}"


class MinfinBudgetParser(BaseParser):
    """ETL для Минфин CSV (deficit/revenue/expenditure).

    `replace_series=True`: БД = точный снимок CSV; preliminary-точки из старого
    пресс-fallback (артефакты ~10 трлн) удаляются при следующем ETL.

    Operational traps (см. enterprise_resilience.md / data_sources.md):
    1. In-place CSV content: Минфин обновляет content файла
       `data-YYYYMMDDTHHMM-structure-…csv` *in-place*, не меняя URL.
       Timestamp в имени = дата создания паспорта, не snapshot content.
       Контрмеры: 2× daily ETL + лог last_parsed vs last_db.
    2. Intermittent 503 on catalog: Minfin-specific Retry(total=8), process
       TTL cache of CSV URL (shared by 3 indicators), last-good URL in state
       Redis. Canonical CSV path NEVER uses `/ru/` (that path 404s).
    """

    parser_type: ClassVar[str] = "minfin_budget_csv"
    replace_series: ClassVar[bool] = True

    async def _after_storage(
        self,
        db: AsyncSession,
        indicator: Indicator,
        cfg: dict,
        fetch_log: FetchLog,
        pruned: int,
        records_added: int,
        records_updated: int,
    ) -> None:
        if not (pruned or records_added or records_updated):
            return
        derived = await calculation_engine.run_for_direct_dependents(
            db, [indicator.code],
        )
        if derived:
            logger.info(
                "Minfin budget '%s': refreshed %d view-mode sibling(s): %s",
                indicator.code, len(derived), ", ".join(derived[:8]),
            )

    async def _fetch_and_parse(
        self,
        db: AsyncSession,
        indicator: Indicator,
        cfg: dict,
        fetch_log: FetchLog,
    ) -> tuple[list, str]:
        budget_target = cfg.get("budget_target", "deficit")
        points, csv_url = await asyncio.to_thread(fetch_and_parse_budget, budget_target)

        last_db = (
            await db.execute(
                select(func.max(IndicatorData.date)).where(
                    IndicatorData.indicator_id == indicator.id
                )
            )
        ).scalar()
        last_parsed = max((p.date for p in points), default=None)
        logger.info(
            "Minfin budget '%s' (target=%s): parsed=%d points, last_parsed=%s, last_db=%s, csv=%s",
            indicator.code,
            budget_target,
            len(points),
            last_parsed,
            last_db,
            csv_url.rsplit("/", 1)[-1] if csv_url else "?",
        )
        if last_parsed and last_db and last_parsed > last_db:
            logger.warning(
                "Minfin budget '%s': source has newer data (%s) than DB (%s) — "
                "expected bulk_upsert to add at least 1 row; will verify post-upsert.",
                indicator.code,
                last_parsed,
                last_db,
            )
        return points, csv_url
