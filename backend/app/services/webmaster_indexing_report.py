"""Еженедельный отчёт индексации Яндекса (А-5, Волна 4.5 CTO-аудита).

Метрика-компас ступени «10k визитов/день»: сколько страниц в поиске, сколько
исключено и какова динамика за неделю. До этого за воронкой индексации никто
не следил систематически — узнавали из ручных выгрузок Вебмастера.

Источники: Webmaster API `summary` (страницы в поиске / исключённые / ИКС /
проблемы сайта) + `indexing_history` (обход по HTTP-кодам за неделю — ловит
класс инцидента А-1 «роботу отдавали 502 в дни индексации»). Динамика —
против прошлого снапшота в state-Redis (переживает деплойный FLUSHDB).
"""

from __future__ import annotations

import json
import logging

from app.config import settings
from app.core.cache import get_state_redis
from app.services.yandex_webmaster_client import YandexWebmasterClient

logger = logging.getLogger(__name__)

_SNAPSHOT_KEY = "wm:index_report:last"
_HOST_ID = "https:forecasteconomy.com:443"


def _delta(current: int | None, previous: int | None) -> str:
    if current is None or previous is None:
        return ""
    diff = current - previous
    if diff == 0:
        return " (без изменений)"
    return f" ({'+' if diff > 0 else ''}{diff} за неделю)"


def _http_breakdown(history: dict) -> dict[str, int]:
    """Суммарные счётчики обхода по классам HTTP-кодов за период истории."""
    totals: dict[str, int] = {}
    for series in history.get("indicators", {}).values() if isinstance(history.get("indicators"), dict) else []:
        for point in series:
            code = str(point.get("indicator") or "")
            totals[code] = totals.get(code, 0) + int(point.get("value") or 0)
    # Альтернативный формат ответа: список серий.
    if not totals:
        for series in history.get("indicators", []) if isinstance(history.get("indicators"), list) else []:
            code = str(series.get("indicator") or "")
            for point in series.get("history", []) or []:
                totals[code] = totals.get(code, 0) + int(point.get("value") or 0)
    return totals


async def build_indexing_report() -> str | None:
    """Собрать текст отчёта; None — если токена нет или API недоступен."""
    if not settings.yandex_webmaster_token:
        return None

    client = YandexWebmasterClient()
    try:
        user = await client.user()
        user_id = user.data["user_id"]
        summary = (await client.summary(user_id, _HOST_ID)).data
    except Exception:
        logger.exception("Indexing report: summary fetch failed")
        return None

    searchable = summary.get("searchable_pages_count")
    excluded = summary.get("excluded_pages_count")
    sqi = summary.get("sqi")

    redis = await get_state_redis()
    previous: dict = {}
    try:
        raw = await redis.get(_SNAPSHOT_KEY)
        if raw:
            previous = json.loads(raw)
    except Exception:
        logger.warning("Indexing report: previous snapshot unavailable")

    lines = [
        "📈 <b>Индексация Яндекса — недельный отчёт</b>",
        f"Страниц в поиске: <b>{searchable}</b>{_delta(searchable, previous.get('searchable'))}",
        f"Исключено из поиска: {excluded}{_delta(excluded, previous.get('excluded'))}",
        f"ИКС: {sqi}{_delta(sqi, previous.get('sqi'))}",
    ]

    problems = summary.get("site_problems") or {}
    if problems:
        pretty = ", ".join(f"{k}: {v}" for k, v in problems.items())
        lines.append(f"Проблемы сайта: {pretty}")

    # Обход за неделю по HTTP-кодам: всплеск 4xx/5xx = мы сами мешаем роботу (А-1).
    try:
        history = (await client.indexing_history(user_id, _HOST_ID)).data
        totals = _http_breakdown(history)
        if totals:
            crawl = ", ".join(
                f"{code.replace('HTTP_', '')}: {n}" for code, n in sorted(totals.items()) if n
            )
            lines.append(f"Обход за период: {crawl}")
            errors = sum(n for code, n in totals.items()
                         if any(x in code for x in ("4XX", "5XX", "ERROR")))
            if errors > 100:
                lines.append(f"⚠️ Роботу отдано {errors} ошибок — проверить деплой-окна и 404-карту")
    except Exception:
        logger.warning("Indexing report: indexing history unavailable", exc_info=True)

    try:
        await redis.set(_SNAPSHOT_KEY, json.dumps(
            {"searchable": searchable, "excluded": excluded, "sqi": sqi}
        ))
    except Exception:
        logger.warning("Indexing report: snapshot save failed")

    return "\n".join(lines)


async def indexing_report_job() -> None:
    """Еженедельная job: отчёт → Telegram владельцу (архив в telegram_outbox)."""
    report = await build_indexing_report()
    if not report:
        logger.info("Indexing report skipped (no token or API unavailable)")
        return
    from app.services.alerting import send_telegram

    await send_telegram(report, kind="indexing_report")
    logger.info("Indexing report sent")
