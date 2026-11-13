"""Росстат отвечает, но отдаёт старую копию сайта без файлов с данными (09.11.2026).

01-04.11.2026 rosstat.gov.ru стоял на заглушке «технические работы» (её ловит `http_client.SourceMaintenance`). Потом
заглушка ушла, но сайт вернулся из старой копии: свежая новость на /central-news — от 13.03.2026, страницы разделов
ссылаются на файлы февраля-марта, сами файлы отвечают 404 (`ind_baza_2018_12-2025.xlsx`, `demo21_2025.xlsx`,
`Popul_1897+.xlsx`), а `nedel_sred_cen.xlsx` отдаётся в версии 12.08.2022 с одним листом «1». ETL дважды в день
показывал «с ошибкой: 41» (каждый ряд — «файл не найден») и четыре «парсер вернул ноль, смена вёрстки?», хотя причина
одна и вне проекта.

Признак старой копии — дата самого свежего бюллетеня в ленте /central-news. Бюллетени (цены на топливо, недельная
инфляция) выходят каждую неделю; самый длинный обычный разрыв — январские праздники (около 12 дней). Если в ленте есть
датированные бюллетени, а самый свежий старше `STALE_AFTER_DAYS`, сайт считается недоступным по содержанию. Если лента
не открылась или дат в ней нет, утверждения нет (`None`): ошибка конкретного ряда остаётся ошибкой.

Причина содержит слово «unreachable»: по нему `tasks/scheduler` относит ряд к «источник недоступен», а
`rosstat_recovery_job` догружает ряд, когда сайт вернётся.

Частичное восстановление (13.11.2026). К 11.11 Росстат вернул раздел цен и свежую ленту: бюллетени стали PDF
(`172_11-11-2026.pdf`), `nedel_sred_cen.xlsx` обновлён 12.11. Промышленность, национальные счета и демография остались
из старой копии: страницы перечисляют файлы (`ind_baza_2018_12-2025.xlsx`, `demo14.xlsx`), а хранилище отвечает на них
404. Прежний признак искал в ленте только `.html`, дат не находил и молчал, поэтому 30 рядов снова считались ошибкой
проекта, а Пульс писал «это наш хвост». Теперь дата бюллетеня читается из `.html` и `.pdf`, а при свежей ленте
проверяются разделы: если страница раздела называет файлы, а большинство из выборки отвечает 404, причина —
«восстановлен частично» (`PARTIAL_MARK`). В этом случае недоступными считаются только ряды с ошибкой «файл не найден»:
остальные разделы работают, и их ошибки остаются ошибками. Проверка разделов тяжелее ленты (три страницы и до 15
запросов), поэтому её результат держится `SECTION_CACHE_SECONDS` и `force` его не сбрасывает.
"""
from __future__ import annotations

import logging
import re
import threading
import time
from datetime import date

logger = logging.getLogger(__name__)

CENTRAL_NEWS_URL = "https://rosstat.gov.ru/central-news"
STALE_AFTER_DAYS = 21
CACHE_SECONDS = 30 * 60

_BULLETIN_DATE_RE = re.compile(r"/storage/mediabank/\d+_(\d{2})-(\d{2})-(\d{4})\.(?:html?|pdf)", re.IGNORECASE)

# Разделы, из которых берут файлы месячные и годовые ряды Росстата.
SECTION_PAGES: tuple[tuple[str, str], ...] = (
    ("промышленность", "https://rosstat.gov.ru/enterprise_industrial"),
    ("национальные счета", "https://rosstat.gov.ru/statistics/accounts"),
    ("демография", "https://rosstat.gov.ru/folder/12781"),
)
SECTION_SAMPLE = 5
SECTION_MISSING_MIN = 4  # из SECTION_SAMPLE: единичная битая ссылка бывает и на здоровом сайте
SECTION_CACHE_SECONDS = 3 * 3600
PARTIAL_MARK = "восстановлен частично"
_SECTION_FILE_RE = re.compile(r"/storage/mediabank/([^\"'<>\s]+\.xlsx?)", re.IGNORECASE)
_MISSING_FILE_RE = re.compile(r"not found|HTTP 404|404 Client Error", re.IGNORECASE)

_sections_cached: tuple[float, str | None] | None = None

_lock = threading.Lock()
_cached: tuple[float, str | None] | None = None


def newest_bulletin_date(html: str) -> date | None:
    """Самая свежая дата бюллетеня из ссылок ленты (`/storage/mediabank/36_13-03-2026.html`)."""
    newest: date | None = None
    for day, month, year in _BULLETIN_DATE_RE.findall(html):
        try:
            d = date(int(year), int(month), int(day))
        except ValueError:
            continue
        if newest is None or d > newest:
            newest = d
    return newest


def stale_reason_from_html(html: str, *, today: date | None = None) -> str | None:
    """Текст причины, если лента явно старая; `None`, если свежая или дат нет."""
    newest = newest_bulletin_date(html)
    if newest is None:
        return None
    today = today or date.today()
    age = (today - newest).days
    if age <= STALE_AFTER_DAYS:
        return None
    return (
        f"rosstat.gov.ru unreachable: сайт отдаёт старую копию без файлов "
        f"(свежий бюллетень {newest:%d.%m.%Y}, {age} дн. назад)"
    )


def is_partial(reason: str | None) -> bool:
    """Причина относится к части разделов: недоступны только ряды с ошибкой «файл не найден»."""
    return bool(reason) and PARTIAL_MARK in reason


def is_missing_file_error(message: str | None) -> bool:
    """Текст ошибки ряда — «файла нет на сайте» (404, not found), а не разбор или сеть."""
    return bool(message) and bool(_MISSING_FILE_RE.search(message))


def sample_section_files(html: str, n: int = SECTION_SAMPLE) -> list[str]:
    """До `n` имён файлов раздела, равномерно по отсортированному списку (детерминированно, без повторов)."""
    names = sorted(set(_SECTION_FILE_RE.findall(html)))
    if len(names) <= n:
        return names
    step = len(names) / n
    return [names[int(i * step)] for i in range(n)]


def partial_reason_from_sections(results: list[tuple[str, int, int]]) -> str | None:
    """Причина по итогам выборки: `(раздел, файлов с 404, файлов проверено)`."""
    broken = [
        f"{label} ({missing} из {sampled} файлов — 404)"
        for label, missing, sampled in results
        if sampled >= SECTION_MISSING_MIN and missing >= SECTION_MISSING_MIN
    ]
    if not broken:
        return None
    return (
        f"rosstat.gov.ru unreachable: сайт {PARTIAL_MARK}, страницы разделов ссылаются на файлы, "
        f"которых нет: {'; '.join(broken)}"
    )


def _probe_sections(session) -> str | None:
    import requests

    from app.services.rosstat_sdds_fetcher import mediabank_url

    results: list[tuple[str, int, int]] = []
    for label, page_url in SECTION_PAGES:
        try:
            page = session.get(page_url, timeout=(10, 30))
        except requests.RequestException:
            continue
        if page.status_code != 200:
            continue
        missing = sampled = 0
        for name in sample_section_files(page.text):
            try:
                resp = session.get(mediabank_url(name), timeout=(10, 20), stream=True)
            except requests.RequestException:
                continue  # сеть не отличает «файла нет» от «не ответил» - в выборку не идёт
            sampled += 1
            missing += resp.status_code == 404
            resp.close()
        results.append((label, missing, sampled))
    return partial_reason_from_sections(results)


def _sections_reason(session) -> str | None:
    """Проверка разделов с собственным долгим кэшем: она тяжелее ленты и меняется раз в дни, а не минуты."""
    global _sections_cached
    with _lock:
        if _sections_cached is not None and time.monotonic() - _sections_cached[0] < SECTION_CACHE_SECONDS:
            return _sections_cached[1]
    reason = _probe_sections(session)
    with _lock:
        _sections_cached = (time.monotonic(), reason)
    return reason


def _reason_for(session) -> str | None:
    """Сначала лента (весь сайт из старой копии), при свежей ленте — разделы (восстановлен частично)."""
    import requests

    try:
        resp = session.get(CENTRAL_NEWS_URL, timeout=(10, 20))
    except requests.RequestException as exc:
        logger.info("Rosstat stale-copy probe: central-news did not answer (%s)", type(exc).__name__)
        return None
    if resp.status_code != 200:
        return None
    return stale_reason_from_html(resp.text) or _sections_reason(session)


def _probe() -> str | None:
    from app.config import settings
    from app.services.http_client import create_session

    session = create_session(timeout=20)
    session.verify = settings.rosstat_ca_cert
    try:
        return _reason_for(session)
    finally:
        session.close()


def stale_copy_reason(*, force: bool = False) -> str | None:
    """Причина «Росстат отдаёт старую копию» или `None`. Результат держится `CACHE_SECONDS` (один запрос на прогон ETL)."""
    global _cached
    with _lock:
        if not force and _cached is not None and time.monotonic() - _cached[0] < CACHE_SECONDS:
            return _cached[1]
    try:
        reason = _probe()
    except Exception:  # noqa: BLE001 - проверка не должна ронять ETL
        logger.warning("Rosstat stale-copy probe failed", exc_info=True)
        reason = None
    with _lock:
        _cached = (time.monotonic(), reason)
    if reason:
        logger.warning("Rosstat: %s", reason)
    return reason


def reset_cache() -> None:
    global _cached, _sections_cached
    with _lock:
        _cached = None
        _sections_cached = None
