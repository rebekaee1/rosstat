"""Архивация исходящих Telegram-отправок в БД (директива владельца 2026-07-04).

Одна функция `archive()` — вызывается из ОБОИХ путей отправки
(`alerting.send_telegram` и `telegram_bot._api`) сразу после ответа Bot API.
Сохраняет всё: текст как отправлен, полезную нагрузку (клавиатуры/caption),
байты файлов, результат (ok/message_id/ошибка).

Зачем: агент следующей сессии (Cursor) должен видеть всё, что система
отправила людям, — тексты дайджестов, файлы CSV, алерты, — не спрашивая
владельца и не получая скриншоты. Чтение:

    select * from telegram_outbox order by sent_at desc limit 20;
    -- файл: select file_name, file_content from telegram_outbox where id=...

Никогда не роняет отправку: любая ошибка архивации только логируется —
уведомление важнее записи о нём.
"""
from __future__ import annotations

import logging
from typing import Any

from app.database import async_session
from app.models import TelegramOutbox

logger = logging.getLogger(__name__)

# Файлы больше лимита не пишем в БД (сейчас выгрузки — килобайты; при росте
# переносить в объектное хранилище, а не молча терять).
_MAX_FILE_BYTES = 5 * 1024 * 1024


def _clean_payload(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    # reply_markup и прочее храним как есть, но без дублирования text.
    if not payload:
        return None
    cleaned = {k: v for k, v in payload.items() if k not in ("chat_id", "text")}
    return cleaned or None


async def archive_begin(
    *,
    chat_id: str,
    method: str,
    kind: str = "generic",
    text: str | None = None,
    payload: dict[str, Any] | None = None,
    file_name: str | None = None,
    file_content: bytes | None = None,
) -> int | None:
    """Н-16: pending-запись ДО отправки — сбой/креш между send и архивом
    больше не оставляет дыру в «глазах агента». Возвращает id строки
    (None при сбое записи — отправка идёт дальше)."""
    try:
        error = None
        if file_content is not None and len(file_content) > _MAX_FILE_BYTES:
            error = f"[file {len(file_content)}B > limit, not stored]"
            file_content = None
        async with async_session() as db:
            row = TelegramOutbox(
                chat_id=str(chat_id),
                method=method,
                kind=kind,
                text=text,
                payload_json=_clean_payload(payload),
                file_name=file_name,
                file_content=file_content,
                ok=False,
                error=error or "pending",
            )
            db.add(row)
            await db.commit()
            return row.id
    except Exception:
        logger.warning("telegram_outbox archive_begin failed (send not affected)", exc_info=True)
        return None


async def archive_finish(
    row_id: int | None,
    *,
    ok: bool,
    telegram_message_id: int | None = None,
    error: str | None = None,
) -> None:
    """Обновить pending-запись результатом отправки. Не бросает исключений."""
    if row_id is None:
        return
    try:
        async with async_session() as db:
            row = await db.get(TelegramOutbox, row_id)
            if row is None:
                return
            row.ok = ok
            row.telegram_message_id = telegram_message_id
            row.error = (error or None) and str(error)[:300]
            await db.commit()
    except Exception:
        logger.warning("telegram_outbox archive_finish failed (send not affected)", exc_info=True)


async def archive(
    *,
    chat_id: str,
    method: str,
    kind: str = "generic",
    text: str | None = None,
    payload: dict[str, Any] | None = None,
    file_name: str | None = None,
    file_content: bytes | None = None,
    ok: bool = False,
    telegram_message_id: int | None = None,
    error: str | None = None,
) -> None:
    """Одношаговая запись (когда отправка уже состоялась). Не бросает исключений."""
    try:
        if file_content is not None and len(file_content) > _MAX_FILE_BYTES:
            error = (error or "") + f" [file {len(file_content)}B > limit, not stored]"
            file_content = None
        async with async_session() as db:
            db.add(TelegramOutbox(
                chat_id=str(chat_id),
                method=method,
                kind=kind,
                text=text,
                payload_json=_clean_payload(payload),
                file_name=file_name,
                file_content=file_content,
                ok=ok,
                telegram_message_id=telegram_message_id,
                error=(error or None) and str(error)[:300],
            ))
            await db.commit()
    except Exception:
        logger.warning("telegram_outbox archive failed (send not affected)", exc_info=True)
