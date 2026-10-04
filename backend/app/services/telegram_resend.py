"""Досылка недоставленных Telegram-сообщений из архива `telegram_outbox` (2026-10-04).

Повтор внутри `send_telegram` спасает от коротких сбоев сети; если Telegram
недоступен дольше потолка повтора (или процесс умер между `archive_begin` и
`archive_finish`), сообщение остаётся в архиве как `ok=false`. Эта задача
(APScheduler, каждые 5 мин, см. `main.py`) подбирает такие строки для важных
видов и отправляет заново.

Логическое сообщение = `kind + chat_id + sha1(text)`; архив не меняем.
- «Доставлено»: есть строка `ok=true` того же ключа, созданная не раньше первой
  неудачной попытки (прежний успех с тем же текстом — другое сообщение).
- Не трогаем строки моложе `telegram_resend_min_age_minutes` (отправка может
  быть ещё в полёте), старше окна `telegram_resend_window_hours`, файлы
  (`sendDocument`) и постоянные ошибки (HTTP 400/401/403/404 — чат неверный /
  бот заблокирован: повтор не поможет).
- На логическое сообщение — не больше `telegram_resend_max_tries` досылок
  (каждая неудачная досылка — новая строка архива с тем же ключом).
- За запуск — не больше `telegram_resend_max_per_run` отправок.
- Строки `pending` старше часа (процесс умер до `archive_finish`) получают
  итоговый статус `PENDING_FINAL_ERROR`, а не висят вечно.
"""
from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

from sqlalchemy import select, update

from app.config import settings
from app.database import async_session
from app.models import TelegramOutbox

logger = logging.getLogger(__name__)

RESEND_KINDS = (
    "digest", "pulse_digest", "new_user", "feedback",
    "etl_summary", "world_ingest_summary",
)
PENDING_ERROR = "pending"
PENDING_FINAL_ERROR = "interrupted: no delivery result recorded (pending > 1h)"
REDELIVERED_ERROR = "redelivered by resend job"
PENDING_STALE_AFTER = timedelta(hours=1)

_HTTP_ERROR_RE = re.compile(r"^HTTP (\d{3})")


@dataclass(frozen=True)
class OutboxRow:
    id: int
    sent_at: datetime
    chat_id: str
    kind: str
    text: str
    ok: bool
    error: str | None
    payload: dict | None = None


def logical_key(kind: str, chat_id: str, text: str) -> str:
    """Устойчивый ключ логического сообщения: kind + chat_id + hash(text)."""
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()
    return f"{kind}|{chat_id}|{digest}"


def is_permanent_failure(error: str | None) -> bool:
    """HTTP 4xx, кроме 408/429, — повтор ничего не изменит."""
    match = _HTTP_ERROR_RE.match(error or "")
    if not match:
        return False
    code = int(match.group(1))
    return 400 <= code < 500 and code not in (408, 429)


def plan_resend(
    rows: Iterable[OutboxRow],
    *,
    now: datetime,
    min_age: timedelta,
    max_tries: int,
    limit: int,
) -> list[tuple[OutboxRow, list[int]]]:
    """Чистая функция: какие сообщения слать. Возвращает [(последняя строка, id неудачных строк)].

    `rows` — отправки одного окна, любой порядок. Порядок результата — по id первой
    неудачной попытки (старые и чанки Пульса идут по порядку).
    """
    groups: dict[str, list[OutboxRow]] = {}
    for row in sorted(rows, key=lambda r: r.id):
        groups.setdefault(logical_key(row.kind, row.chat_id, row.text), []).append(row)

    plan: list[tuple[int, OutboxRow, list[int]]] = []
    for items in groups.values():
        failed = [r for r in items if not r.ok]
        if not failed:
            continue
        first_failed = failed[0]
        if any(r.ok and r.sent_at >= first_failed.sent_at for r in items):
            continue  # уже доставлено (в т.ч. прошлой досылкой)
        last = items[-1]
        if is_permanent_failure(failed[-1].error):
            continue
        if now - max(r.sent_at for r in items) < min_age:
            continue  # свежая отправка может быть ещё в полёте
        if len(failed) > max_tries:
            continue  # исходная отправка + max_tries досылок исчерпаны
        plan.append((first_failed.id, failed[-1], [r.id for r in failed]))

    plan.sort(key=lambda item: item[0])
    return [(row, ids) for _, row, ids in plan[:limit]]


async def finalize_stale_pending(db, *, now: datetime) -> int:
    """`pending` старше часа → итоговый статус (процесс не дошёл до archive_finish)."""
    res = await db.execute(
        update(TelegramOutbox)
        .where(
            TelegramOutbox.ok.is_(False),
            TelegramOutbox.error == PENDING_ERROR,
            TelegramOutbox.sent_at < now - PENDING_STALE_AFTER,
        )
        .values(error=PENDING_FINAL_ERROR)
    )
    return int(res.rowcount or 0)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def telegram_resend_job() -> dict[str, int]:
    """Периодическая досылка. Возвращает счётчики (для логов и тестов)."""
    stats = {"finalized": 0, "candidates": 0, "resent": 0, "failed": 0}
    if not (settings.telegram_bot_token and settings.telegram_chat_id):
        return stats
    from app.services.alerting import send_telegram  # против цикла импортов

    now = _utcnow()
    window = timedelta(hours=settings.telegram_resend_window_hours)
    try:
        async with async_session() as db:
            stats["finalized"] = await finalize_stale_pending(db, now=now)
            await db.commit()
            found = (await db.execute(
                select(
                    TelegramOutbox.id, TelegramOutbox.sent_at, TelegramOutbox.chat_id,
                    TelegramOutbox.kind, TelegramOutbox.text, TelegramOutbox.ok,
                    TelegramOutbox.error, TelegramOutbox.payload_json,
                )
                .where(
                    TelegramOutbox.method == "sendMessage",
                    TelegramOutbox.kind.in_(RESEND_KINDS),
                    TelegramOutbox.sent_at >= now - window,
                    TelegramOutbox.text.is_not(None),
                )
                .order_by(TelegramOutbox.id)
            )).all()
    except Exception:  # noqa: BLE001 — БД недоступна: досылка подождёт до следующего запуска
        logger.warning("telegram resend: outbox read failed", exc_info=True)
        return stats

    rows = [
        OutboxRow(
            id=r.id, sent_at=r.sent_at, chat_id=r.chat_id, kind=r.kind, text=r.text,
            ok=bool(r.ok), error=r.error, payload=r.payload_json,
        )
        for r in found
    ]
    plan = plan_resend(
        rows,
        now=now,
        min_age=timedelta(minutes=settings.telegram_resend_min_age_minutes),
        max_tries=settings.telegram_resend_max_tries,
        limit=settings.telegram_resend_max_per_run,
    )
    stats["candidates"] = len(plan)

    for row, failed_ids in plan:
        reply_markup: Any = (row.payload or {}).get("reply_markup")
        ok = await send_telegram(row.text, chat_id=row.chat_id,
                                 reply_markup=reply_markup, kind=row.kind)
        if not ok:
            stats["failed"] += 1
            continue
        stats["resent"] += 1
        try:  # прежние неудачные попытки получают понятную пометку
            async with async_session() as db:
                await db.execute(
                    update(TelegramOutbox)
                    .where(TelegramOutbox.id.in_(failed_ids), TelegramOutbox.ok.is_(False))
                    .values(error=REDELIVERED_ERROR)
                )
                await db.commit()
        except Exception:  # noqa: BLE001
            logger.warning("telegram resend: marking redelivered failed", exc_info=True)

    if any(stats.values()):
        logger.info("Telegram resend: %s", stats)
    return stats
