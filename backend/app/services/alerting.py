"""Telegram alerting for ETL failures and critical events."""

import logging
from html import escape
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


async def send_telegram(message: str) -> bool:
    """Send alert to Telegram (async, non-blocking). Returns True on success."""
    token = settings.telegram_bot_token
    chat_id = settings.telegram_chat_id
    if not token or not chat_id:
        return False

    try:
        url = _TELEGRAM_API.format(token=token)
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                url,
                json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"},
            )
        if resp.status_code != 200:
            logger.warning("Telegram alert failed: HTTP %d", resp.status_code)
            return False
        return True
    except Exception:
        logger.warning("Telegram alert failed", exc_info=True)
        return False


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
    await send_telegram("\n".join(lines))


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
    await send_telegram("\n".join(lines))


async def alert_etl_failure(indicator_code: str, error: str) -> None:
    msg = (
        f"🔴 <b>ETL Failed</b>\n"
        f"Indicator: <code>{escape(indicator_code)}</code>\n"
        f"Error: {escape(error[:200])}"
    )
    await send_telegram(msg)


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
    await send_telegram("\n".join(parts))
