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
# Alias для pulse._seo_snapshot и прочих импортов; значение = settings.webmaster_host_id.
_HOST_ID = settings.webmaster_host_id


def _host_snapshot_key(host_id: str) -> str:
    if host_id == settings.webmaster_host_id:
        return _SNAPSHOT_KEY
    return f"{_SNAPSHOT_KEY}:{host_id}"


def _report_host_ids() -> list[str]:
    ids = [settings.webmaster_host_id]
    if settings.apex_locale_en:
        ru_id = settings.webmaster_host_id_for("ru.forecasteconomy.com")
        if ru_id not in ids:
            ids.append(ru_id)
    return ids


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
    except Exception:
        logger.exception("Indexing report: user fetch failed")
        return None

    redis = await get_state_redis()
    blocks: list[str] = ["<b>Индексация Яндекса — недельный отчёт</b>"]
    any_ok = False
    for host_id in _report_host_ids():
        block = await _host_report_block(client, user_id, host_id, redis)
        if block:
            any_ok = True
            blocks.append(block)
    if not any_ok:
        return None
    return "\n".join(blocks)


async def _host_report_block(client, user_id, host_id: str, redis) -> str | None:
    try:
        summary = (await client.summary(user_id, host_id)).data
    except Exception:
        logger.exception("Indexing report: summary fetch failed host=%s", host_id)
        return None

    searchable = summary.get("searchable_pages_count")
    excluded = summary.get("excluded_pages_count")
    sqi = summary.get("sqi")
    previous: dict = {}
    snap_key = _host_snapshot_key(host_id)
    try:
        raw = await redis.get(snap_key)
        if raw:
            previous = json.loads(raw)
    except Exception:
        logger.warning("Indexing report: previous snapshot unavailable host=%s", host_id)

    host_label = host_id.replace("https:", "").replace(":443", "")
    lines = [
        f"<b>{host_label}</b>",
        f"Страниц в поиске: <b>{searchable}</b>{_delta(searchable, previous.get('searchable'))}",
        f"Исключено из поиска: {excluded}{_delta(excluded, previous.get('excluded'))}",
        f"ИКС: {sqi}{_delta(sqi, previous.get('sqi'))}",
    ]
    problems = summary.get("site_problems") or {}
    if problems:
        pretty = ", ".join(f"{k}: {v}" for k, v in problems.items())
        lines.append(f"Проблемы сайта: {pretty}")
    try:
        history = (await client.indexing_history(user_id, host_id)).data
        totals = _http_breakdown(history)
        if totals:
            crawl = ", ".join(
                f"{code.replace('HTTP_', '')}: {n}" for code, n in sorted(totals.items()) if n
            )
            lines.append(f"Обход за период: {crawl}")
            errors = sum(n for code, n in totals.items()
                         if any(x in code for x in ("4XX", "5XX", "ERROR")))
            if errors > 100:
                lines.append(f"Роботу отдано {errors} ошибок — проверить деплой-окна и 404-карту")
    except Exception:
        logger.warning("Indexing report: indexing history unavailable host=%s", host_id, exc_info=True)
    try:
        await redis.set(snap_key, json.dumps(
            {"searchable": searchable, "excluded": excluded, "sqi": sqi}
        ))
    except Exception:
        logger.warning("Indexing report: snapshot save failed host=%s", host_id)
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
