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

_BULLETIN_DATE_RE = re.compile(r"/storage/mediabank/\d+_(\d{2})-(\d{2})-(\d{4})\.html")

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


def _probe() -> str | None:
    import requests

    from app.config import settings
    from app.services.http_client import create_session

    session = create_session(timeout=20)
    session.verify = settings.rosstat_ca_cert
    try:
        resp = session.get(CENTRAL_NEWS_URL, timeout=(10, 20))
    except requests.RequestException as exc:
        logger.info("Rosstat stale-copy probe: central-news did not answer (%s)", type(exc).__name__)
        return None
    finally:
        session.close()
    if resp.status_code != 200:
        return None
    return stale_reason_from_html(resp.text)


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
    global _cached
    with _lock:
        _cached = None
