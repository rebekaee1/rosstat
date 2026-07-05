"""Telegram alerting for ETL failures and critical events."""

import logging
from html import escape
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


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
    from app.services.telegram_outbox import archive  # локальный импорт против цикла

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

    await archive(
        chat_id=str(cid), method="sendMessage", kind=kind, text=message,
        payload=payload, ok=ok, telegram_message_id=tg_message_id, error=error,
    )
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
    напр. skrakan) + `pulse_chat_id`. Realtime-алерты (регистрации/обратная связь)
    сюда НЕ относятся — они только у владельца. Так skrakan получает отчёт и может
    сам выгрузить CSV, но не завален мгновенными уведомлениями (звонок 2026-07-03).
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
    await send_telegram("\n".join(lines), kind="new_user")


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
    await send_telegram("\n".join(lines), kind="feedback")


async def alert_etl_failure(indicator_code: str, error: str) -> None:
    msg = (
        f"🔴 <b>ETL Failed</b>\n"
        f"Indicator: <code>{escape(indicator_code)}</code>\n"
        f"Error: {escape(error[:200])}"
    )
    await send_telegram(msg, kind="etl_failure")


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
