"""Telegram alerting for ETL failures and critical events."""

import logging
from html import escape
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"

# Антиспам повторяющихся технических алертов (state-Redis DB 1).
# Daily ETL + evening + late-Minfin иначе шлют один и тот же budget-*/coal
# по 2–3 раза в сутки; zero-parse — на каждый прогон.
_ETL_FAILURE_MUTE_TTL = 12 * 3600
_ZERO_PARSE_MUTE_TTL = 24 * 3600
STALENESS_MUTE_TTL = 6 * 24 * 3600  # хронический список — раз в неделю


async def alert_muted(alert_key: str, ttl_seconds: int) -> bool:
    """True = уже слали недавно, пропустить. False = можно слать (ключ поставлен).

    При недоступности Redis — fail-open (шлём): лучше шум, чем слепота.
    """
    try:
        from app.core.cache import get_state_redis

        r = await get_state_redis()
        key = f"fe:alerts:mute:{alert_key}"
        if await r.get(key):
            return True
        await r.set(key, "1", ex=ttl_seconds)
        return False
    except Exception:  # noqa: BLE001
        logger.warning("alert mute check failed for %s — sending anyway", alert_key)
        return False


async def send_telegram(
    message: str,
    chat_id: Optional[str] = None,
    reply_markup: Optional[dict] = None,
    kind: str = "alert",
) -> bool:
    """Send alert to Telegram (async, non-blocking). Returns True on success.

    `chat_id` переопределяет получателя; без него — primary `settings.telegram_chat_id`.
    `reply_markup` — inline-клавиатура (напр. меню бота под дайджестом).
    `kind` — семантика отправки для архива telegram_outbox (etl_alert / digest / …).
    Каждая отправка полностью архивируется в БД (`telegram_outbox`) — это
    «глаза» агента следующей сессии; архивация не влияет на доставку.
    """
    from app.services.telegram_outbox import archive_begin, archive_finish  # против цикла

    token = settings.telegram_bot_token
    cid = chat_id or settings.telegram_chat_id
    if not token or not cid:
        return False

    ok = False
    tg_message_id: Optional[int] = None
    error: Optional[str] = None
    payload: dict = {"chat_id": cid, "text": message, "parse_mode": "HTML"}
    if reply_markup:
        payload["reply_markup"] = reply_markup

    # Н-16: pending-запись ДО отправки — креш между send и архивом не оставляет дыру.
    row_id = await archive_begin(
        chat_id=str(cid), method="sendMessage", kind=kind, text=message, payload=payload,
    )
    try:
        url = _TELEGRAM_API.format(token=token)
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=payload)
        if resp.status_code != 200:
            error = f"HTTP {resp.status_code}: {resp.text[:200]}"
            logger.warning("Telegram alert failed: %s", error)
        else:
            ok = True
            try:
                tg_message_id = resp.json().get("result", {}).get("message_id")
            except Exception:
                pass
    except Exception as exc:
        error = str(exc)[:250]
        logger.warning("Telegram alert failed", exc_info=True)

    await archive_finish(row_id, ok=ok, telegram_message_id=tg_message_id, error=error)
    return ok


def digest_recipients() -> list[str]:
    """Получатели ежедневного дайджеста: primary + extra (config-driven, dedup).

    primary — `telegram_chat_id`; extra — comma-separated `telegram_digest_chat_ids`.
    Realtime-алерты (новый юзер/обратная связь) шлём только primary; дайджест —
    всем (звонок 2026-06-21: skrakan получает дайджест в 9:00 наравне с rebekaee1).
    """
    primary = settings.telegram_chat_id
    extra = [c.strip() for c in (settings.telegram_digest_chat_ids or "").split(",") if c.strip()]
    seen: set[str] = set()
    out: list[str] = []
    for cid in [primary, *extra]:
        if cid and cid not in seen:
            seen.add(cid)
            out.append(cid)
    return out


async def send_telegram_digest(message: str, reply_markup: Optional[dict] = None) -> dict[str, bool]:
    """Рассылка дайджеста всем получателям. Возвращает {chat_id: ok}.

    `reply_markup` — общее меню бота под отчётом, чтобы получатели (владелец +
    skrakan) могли сразу выгрузить CSV/раскрыть пользователей той же кнопкой.
    """
    return {
        cid: await send_telegram(message, chat_id=cid, reply_markup=reply_markup, kind="digest")
        for cid in digest_recipients()
    }


def interactive_authorized_ids() -> set[str]:
    """Кто вправе жать кнопки бота (меню, карточки, выгрузка CSV пользователей).

    Владелец (`telegram_chat_id`) + получатели отчёта (`telegram_digest_chat_ids`,
    напр. skrakan) + `pulse_chat_id`. Регистрации/обратная связь/пульс с 2026-07-06
    тоже уходят всем получателям дайджеста (указание владельца); технические
    realtime-алерты (ETL/5xx/аномалии) остаются только у владельца.
    """
    ids = set(digest_recipients())
    if settings.pulse_chat_id:
        ids.add(str(settings.pulse_chat_id))
    return {str(i) for i in ids if i}


async def notify_new_user(info: dict) -> None:
    """Мгновенное уведомление администратора о новой регистрации (ADR-0007 Phase 2).

    Никогда не роняет регистрацию: вызывать через try/except или fire-and-forget.
    Молчит, если realtime-алерты выключены (`telegram_realtime_alerts_enabled`) —
    данные всё равно есть в ежедневном дайджесте.
    """
    if not settings.telegram_realtime_alerts_enabled:
        return
    def esc(v) -> str:
        return escape(str(v)) if v not in (None, "") else "—"

    lines = [
        "🆕 <b>Новый пользователь</b>",
        f"Способ входа: {esc(info.get('method'))}",
        f"Email: {esc(info.get('email'))}",
        f"Телефон: {esc(info.get('phone'))}",
        f"Имя: {esc(info.get('display_name'))}",
        f"Рассылка: {'да' if info.get('newsletter') else 'нет'}",
        f"IP: {esc(info.get('ip'))}",
        f"User-Agent: {esc((info.get('user_agent') or '')[:120])}",
        f"ID: <code>{esc(info.get('user_id'))}</code>",
    ]
    # Всем получателям дайджеста (владелец + skrakan) — указание владельца 2026-07-06.
    for cid in digest_recipients():
        await send_telegram("\n".join(lines), chat_id=cid, kind="new_user")


async def notify_feedback(info: dict) -> None:
    """Мгновенная отправка обратной связи от авторизованного пользователя (ADR-0007 Phase 2)."""
    if not settings.telegram_realtime_alerts_enabled:
        return
    def esc(v) -> str:
        return escape(str(v)) if v not in (None, "") else "—"

    lines = [
        "💬 <b>Обратная связь</b>",
        f"Email: {esc(info.get('email'))}",
        f"Имя: {esc(info.get('display_name'))}",
        f"ID: <code>{esc(info.get('user_id'))}</code>",
        "",
        esc(info.get("message")),
    ]
    contact = info.get("contact")
    if contact:
        lines.insert(4, f"Контакт для ответа: {esc(contact)}")
    for cid in digest_recipients():
        await send_telegram("\n".join(lines), chat_id=cid, kind="feedback")


async def alert_forecast_issue(indicator_code: str, detail: str) -> None:
    """Прогнозный контур (Н-7/Н-8): нерезолвнутая стратегия, провал каскада."""
    msg = (
        f"🟡 <b>Forecast issue</b>\n"
        f"Indicator: <code>{escape(indicator_code)}</code>\n"
        f"{escape(detail[:300])}"
    )
    await send_telegram(msg, kind="forecast_issue")


async def alert_etl_failure(indicator_code: str, error: str) -> None:
    """Per-indicator ETL fail. Mute 12h на код — иначе late-Minfin/evening
    дублируют утренний fail тем же 503. В daily_update_job per-indicator
    не зовём: там достаточно summary со списком failed.
    """
    if await alert_muted(f"etl_failure:{indicator_code}", _ETL_FAILURE_MUTE_TTL):
        logger.info("ETL failure muted for %s", indicator_code)
        return
    msg = (
        f"🔴 <b>ETL Failed</b>\n"
        f"Indicator: <code>{escape(indicator_code)}</code>\n"
        f"Error: {escape(error[:200])}"
    )
    await send_telegram(msg, kind="etl_failure")


async def alert_zero_parse(indicator_code: str, existing_points: int) -> None:
    """Zero-parse regression (история есть, парсер вернул 0). Mute 24h на код."""
    if await alert_muted(f"zero_parse:{indicator_code}", _ZERO_PARSE_MUTE_TTL):
        logger.info("Zero-parse muted for %s", indicator_code)
        return
    await send_telegram(
        "🟡 <b>Zero-parse regression</b>\n"
        f"Indicator: <code>{escape(indicator_code)}</code>\n"
        f"Парсер вернул 0 точек при {existing_points} точках истории — "
        "вероятна смена layout источника.",
        kind="zero_parse",
    )


async def alert_etl_summary(
    total: int,
    updated: int,
    failed: list[str],
    duration_sec: Optional[float] = None,
) -> None:
    status = "🔴" if failed else "🟢"
    parts = [
        f"{status} <b>Daily ETL Complete</b>",
        f"Total: {total} | Updated: {updated} | Failed: {len(failed)}",
    ]
    if duration_sec is not None:
        parts.append(f"Duration: {duration_sec:.0f}s")
    if failed:
        parts.append(f"Failed: {escape(', '.join(failed))}")
    await send_telegram("\n".join(parts), kind="etl_summary")
