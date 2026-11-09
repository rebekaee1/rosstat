"""Журнал переписки публичного Telegram-бота (решение владельца 09.11.2026).

Владелец: «сохранять историю диалога… какой пользователь написал… и что ему отправляла LLM».
Пишем:
- каждое входящее (сообщение, нажатие кнопки, inline-запрос, изменение статуса) — с профилем Telegram и сырым update;
- каждый запрос к модели — модель, сообщения, ответ, статус, время, расход токенов.
Исходящие сообщения бота уже лежат целиком в telegram_outbox (kind bot_reply / notify).
Выгрузка для анализа — scripts/public-bot-dialogs.py. /stop удаляет записи чата (forget).

Запись никогда не роняет ответ человеку: ошибка журнала только логируется.
"""
from __future__ import annotations

import contextvars
import logging
from typing import Any

from sqlalchemy import delete

from app.database import async_session
from app.models import PublicBotDialog

logger = logging.getLogger(__name__)

# Чат текущего update: задаётся в handle_update, его видит _llm_call (asyncio копирует контекст в задачи).
current_chat: contextvars.ContextVar[str | None] = contextvars.ContextVar("public_bot_dialog_chat", default=None)

_MAX_TEXT = 8000


def _profile(user: dict | None) -> dict[str, Any]:
    u = user or {}
    return {"user_id": str(u["id"]) if u.get("id") is not None else None,
            "username": (u.get("username") or None) and u["username"][:64],
            "first_name": (u.get("first_name") or None) and u["first_name"][:128],
            "last_name": (u.get("last_name") or None) and u["last_name"][:128],
            "language_code": (u.get("language_code") or None) and u["language_code"][:16]}


def describe_update(upd: dict) -> dict[str, Any] | None:
    """update → поля записи журнала (без сохранения). None — нечего писать."""
    if "message" in upd:
        m = upd["message"]
        text = m.get("text") or m.get("caption")
        if text is None:
            for k in ("sticker", "photo", "voice", "video", "document", "audio", "video_note", "location", "contact"):
                if k in m:
                    text = f"[{k}]"
                    break
        return {"chat_id": str((m.get("chat") or {}).get("id", "")) or None, "kind": "message", "text": text,
                **_profile(m.get("from"))}
    if "callback_query" in upd:
        cq = upd["callback_query"]
        chat = ((cq.get("message") or {}).get("chat") or {}).get("id") or (cq.get("from") or {}).get("id")
        return {"chat_id": str(chat) if chat is not None else None, "kind": "callback", "text": cq.get("data"),
                **_profile(cq.get("from"))}
    if "inline_query" in upd:
        iq = upd["inline_query"]
        uid = (iq.get("from") or {}).get("id")
        return {"chat_id": str(uid) if uid is not None else None, "kind": "inline", "text": iq.get("query"),
                **_profile(iq.get("from"))}
    if "my_chat_member" in upd:
        mu = upd["my_chat_member"]
        status = ((mu.get("new_chat_member") or {}).get("status"))
        return {"chat_id": str((mu.get("chat") or {}).get("id", "")) or None, "kind": "member", "text": status,
                **_profile(mu.get("from"))}
    return None


async def log_update(upd: dict) -> None:
    try:
        d = describe_update(upd)
        if d is None:
            return
        if d.get("text"):
            d["text"] = d["text"][:_MAX_TEXT]
        async with async_session() as db:
            db.add(PublicBotDialog(direction="in", payload=upd, **d))
            await db.commit()
    except Exception:  # noqa: BLE001
        logger.warning("public bot dialog: входящее не записано", exc_info=True)


async def log_llm(*, model: str, messages: list[dict], answer: str | None, status: str,
                  latency_ms: int | None = None, usage: dict | None = None, kind: str = "answer") -> None:
    """Запрос к модели и её ответ. chat_id — из current_chat (None для рассылок вроде сводки недели)."""
    try:
        async with async_session() as db:
            db.add(PublicBotDialog(
                direction="llm", kind=kind, chat_id=current_chat.get(), text=(answer or "")[:_MAX_TEXT] or None,
                payload={"model": model, "status": status, "latency_ms": latency_ms, "usage": usage,
                         "messages": messages},
            ))
            await db.commit()
    except Exception:  # noqa: BLE001
        logger.warning("public bot dialog: запрос к модели не записан", exc_info=True)


async def forget(chat_id: str) -> None:
    try:
        async with async_session() as db:
            await db.execute(delete(PublicBotDialog).where(PublicBotDialog.chat_id == chat_id))
            await db.commit()
    except Exception:  # noqa: BLE001
        logger.warning("public bot dialog: журнал чата не удалён", exc_info=True)
