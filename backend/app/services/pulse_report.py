"""LLM-отчёт «пульса» в Telegram (П9б, 2026-07-02).

Пайплайн: снапшот дня (`pulse.py`) + память прошлых дней → OpenRouter
(model = settings.openrouter_model) → человеческая сводка на русском →
Telegram-сообщение владельцу (`settings.pulse_chat_id`) с новым оформлением
Bot API: expandable blockquote для сырых цифр + inline-кнопки, которые
обрабатывает `telegram_bot.py` (getUpdates-поллер).

Контроль контекста: модели передаём полный снапшот ТОЛЬКО за отчётный день;
прошлые дни — компактная память (числовое ядро + однострочная сводка),
поэтому окно не растёт с историей. После отчёта сводка дня записывается
в память (TTL 30 дней) — так у системы есть «вчера» и тренд недели.
"""
from __future__ import annotations

import json
import logging
from datetime import date, timedelta
from html import escape

import httpx

from app.config import settings
from app.services import pulse
from app.services.telegram_bot import main_menu_keyboard, send_message

logger = logging.getLogger(__name__)

_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

_SYSTEM_PROMPT = """Ты — аналитик платформы forecasteconomy.com (экономическая статистика России).
Тебе дают JSON-снапшот активности за день и краткую память за прошлые дни.
Напиши сводку для владельца в Telegram на русском. Требования:
- 6–12 коротких строк, без воды и без маркетинга;
- сначала главное: что изменилось против прошлых дней (рост/спад, новые пользователи, аномалии);
- обязательно раздели аудиторию: зарегистрированные vs гости (поля audience, events.by_audience, events.downloads_by_audience) — сколько активных, чем отличается их поведение;
- обязательно отметь: ошибки фронта, упавшие ETL, запросы поиска без результатов (это пробелы каталога);
- если скачиваний нет — скажи прямо и напомни, что гостям скачивание закрыто (лимит 0), скачивают только зарегистрированные;
- числа пиши точно из данных, ничего не выдумывай;
- HTML-разметка Telegram: <b>жирный</b>, <i>курсив</i>, <code>код</code>. Никаких <ul>/<li>/markdown;
- эмодзи умеренно (1 на строку максимум).
Ответ — только текст сообщения, без преамбул."""


async def _llm_summary(snapshot: dict, memory: list[dict]) -> str | None:
    """Сводка дня через OpenRouter. None при любом сбое — отчёт уйдёт без LLM."""
    if not settings.openrouter_api_key:
        return None
    payload = {
        "model": settings.openrouter_model,
        "max_tokens": 900,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    "Память за прошлые дни (старые → новые):\n"
                    + json.dumps(memory, ensure_ascii=False)
                    + "\n\nСнапшот за отчётный день:\n"
                    + json.dumps(snapshot, ensure_ascii=False)
                ),
            },
        ],
    }
    try:
        async with httpx.AsyncClient(timeout=90) as client:
            resp = await client.post(
                _OPENROUTER_URL,
                json=payload,
                headers={
                    "Authorization": f"Bearer {settings.openrouter_api_key}",
                    "HTTP-Referer": "https://forecasteconomy.com",
                    "X-Title": "Forecast Economy Pulse",
                },
            )
        if resp.status_code != 200:
            logger.warning("OpenRouter HTTP %d: %s", resp.status_code, resp.text[:300])
            return None
        content = resp.json()["choices"][0]["message"]["content"].strip()
        return content or None
    except Exception:
        logger.warning("OpenRouter call failed", exc_info=True)
        return None


def _fallback_summary(snapshot: dict) -> str:
    """Детерминированная сводка, если LLM недоступен."""
    u = snapshot.get("users", {})
    ev = snapshot.get("events", {})
    etl = snapshot.get("etl", {})
    aud = snapshot.get("audience", {})
    by_aud = ev.get("by_audience", {})
    dl_aud = ev.get("downloads_by_audience", {})
    lines = [
        f"👤 Пользователи: всего {u.get('total', 0)}, новых {u.get('new', 0)}",
        f"🫂 Активны за день: зарег. {aud.get('authed_active', 0)}, "
        f"гостей {aud.get('guest_sessions', 0)}",
        f"⚡ Событий: {ev.get('total', 0)} "
        f"(зарег. {by_aud.get('authed', 0)} / гости {by_aud.get('guest', 0)})",
        f"📥 Скачиваний: {sum(ev.get('downloads', {}).values())} "
        f"(зарег. {dl_aud.get('authed', 0)} / гости {dl_aud.get('guest', 0)})",
        f"🛑 Ошибок фронта: {sum(ev.get('errors', {}).values())}",
        f"🏭 Упавших ETL-индикаторов: {len(etl.get('failed_indicator_ids', []))}",
        f"➕ Новых точек данных: {snapshot.get('data', {}).get('new_points', 0)}",
    ]
    return "\n".join(lines)


def _raw_digits_block(snapshot: dict) -> str:
    """Сырые цифры дня в expandable blockquote (новое оформление Bot API 7.10)."""
    ev = snapshot.get("events", {})
    parts: list[str] = []
    aud = snapshot.get("audience", {})
    by_aud = ev.get("by_audience", {})
    dl_aud = ev.get("downloads_by_audience", {})
    parts.append(
        "Аудитория: зарег. активных "
        f"{aud.get('authed_active', 0)}, гостевых сессий {aud.get('guest_sessions', 0)}; "
        f"события зарег/гость {by_aud.get('authed', 0)}/{by_aud.get('guest', 0)}; "
        f"скачивания зарег/гость {dl_aud.get('authed', 0)}/{dl_aud.get('guest', 0)}"
    )
    if ev.get("by_name"):
        top = ", ".join(f"{k}: {v}" for k, v in list(ev["by_name"].items())[:15])
        parts.append(f"События: {escape(top)}")
    if ev.get("top_indicators"):
        top = ", ".join(f"{k} ×{v}" for k, v in ev["top_indicators"].items())
        parts.append(f"Индикаторы: {escape(top)}")
    if ev.get("top_regions"):
        top = ", ".join(f"{k} ×{v}" for k, v in ev["top_regions"].items())
        parts.append(f"Регионы: {escape(top)}")
    if ev.get("search_top"):
        top = ", ".join(f"«{k}» ×{v}" for k, v in ev["search_top"].items())
        parts.append(f"Поиск: {escape(top)}")
    if ev.get("search_zero_results"):
        top = ", ".join(f"«{k}»" for k in ev["search_zero_results"])
        parts.append(f"Поиск без результатов: {escape(top)}")
    auth = snapshot.get("auth", {})
    if auth:
        parts.append("Auth: " + escape(", ".join(f"{k}: {v}" for k, v in auth.items())))
    if not parts:
        return ""
    return "<blockquote expandable>" + "\n".join(parts) + "</blockquote>"


async def send_pulse_report(report_date: date | None = None) -> bool:
    """Собрать (или взять готовый) снапшот дня, прогнать через LLM, отправить в ТГ."""
    if not (settings.telegram_bot_token and settings.pulse_chat_id):
        logger.info("Pulse report skipped: telegram not configured")
        return False

    d = report_date or (date.today() - timedelta(days=1))
    snapshot = await pulse.get_or_build_snapshot(d)
    memory = await pulse.load_memory(days=7, before=d)

    summary = await _llm_summary(snapshot, memory)
    body = summary or _fallback_summary(snapshot)

    msg_parts = [f"🛰 <b>Пульс платформы — {d.isoformat()}</b>", "", body]
    raw = _raw_digits_block(snapshot)
    if raw:
        msg_parts += ["", raw]
    text = "\n".join(msg_parts)

    ok = await send_message(
        settings.pulse_chat_id, text, reply_markup=main_menu_keyboard()
    )
    # память дня пишем даже при сбое отправки — снапшот уже посчитан
    await pulse.store_memory(d, pulse.memory_core(snapshot), summary or _fallback_summary(snapshot))
    return ok


async def pulse_snapshot_job() -> None:
    """Ежедневная фиксация снапшота (23:57 МСК) — чтобы день не потерялся."""
    try:
        snap = await pulse.build_snapshot(date.today())
        await pulse.store_snapshot(snap)
        logger.info("Pulse snapshot stored for %s", snap["date"])
    except Exception:
        logger.exception("Pulse snapshot job failed")


async def pulse_report_job() -> None:
    """Ежедневный LLM-отчёт за вчера (09:05 МСК)."""
    try:
        await send_pulse_report()
    except Exception:
        logger.exception("Pulse report job failed")
