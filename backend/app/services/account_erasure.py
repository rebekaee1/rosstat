"""Удаление аналитических следов аккаунта (152-ФЗ, круг 11, зона H).

До этого `DELETE /auth/account` убирал аккаунт, способы входа, согласия и аудит, но
`user_id` оставался в `frontend_events`, `behavior_events`, `behavior_sessions`,
`server_sessions`, `identity_links` — «полное удаление ПДн» формально не выполнялось.

Делаем в два этапа:
1. В самом запросе: удаляем `user_signups` и `identity_links` человека, обнуляем
   `frontend_events.user_id` (колонка с индексом, быстро) и кладём в `auth_audit`
   безличную отметку `analytics_erase_pending` с идентификатором удалённого
   аккаунта (аккаунта уже нет, идентификатор ничего не раскрывает; отметка
   стирается после уборки).
2. Ночью `process_pending_erasures`: обнуляем `user_id` в больших таблицах без
   индекса по этой колонке (`behavior_events`, `behavior_sessions`, `server_sessions`)
   окнами по первичному ключу или времени, чтобы каждый запрос укладывался в таймаут
   и не блокировал запись. Сырьё не удаляется (директива «копим»): обнуляется только
   связь события с человеком.
"""
from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Iterable

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AuthAudit,
    BehaviorEvent,
    BehaviorSession,
    FrontendEvent,
    IdentityLink,
    ServerSession,
    UserSignup,
)

logger = logging.getLogger(__name__)

PENDING_EVENT = "analytics_erase_pending"
DONE_EVENT = "analytics_erase_done"

# Размер окна по первичному ключу и по времени для ночной уборки.
ID_WINDOW = 500_000
TIME_WINDOW = timedelta(days=7)
MAX_IDS_PER_RUN = 100


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def erase_analytics_now(db: AsyncSession, user_id) -> None:
    """Быстрая часть удаления: вызывается из `delete_account` до commit().

    Строки добавляются в текущую транзакцию вызывающего кода; commit — на нём.
    """
    uid = user_id if isinstance(user_id, uuid.UUID) else uuid.UUID(str(user_id))
    await db.execute(delete(UserSignup).where(UserSignup.user_id == uid))
    await db.execute(delete(IdentityLink).where(IdentityLink.user_id == str(uid)))
    await db.execute(
        update(FrontendEvent).where(FrontendEvent.user_id == str(uid)).values(user_id=None)
    )
    db.add(AuthAudit(user_id=None, event=PENDING_EVENT, detail=str(uid)))


async def _null_by_id_windows(db: AsyncSession, model, ids: list[str], window: int = ID_WINDOW) -> int:
    """UPDATE ... SET user_id=NULL окнами по числовому PK (самое свежее окно — первым)."""
    top = await db.scalar(select(func.max(model.id)))
    if not top:
        return 0
    total = 0
    hi = int(top)
    while hi > 0:
        lo = max(0, hi - window)
        result = await db.execute(
            update(model)
            .where(model.id > lo, model.id <= hi, model.user_id.in_(ids))
            .values(user_id=None)
        )
        total += int(result.rowcount or 0)
        await db.commit()
        hi = lo
    return total


async def _null_sessions_by_time(db: AsyncSession, ids: list[str]) -> int:
    """behavior_sessions: PK — строка-хэш, поэтому окна по индексу `started_at`."""
    lowest = await db.scalar(select(func.min(BehaviorSession.started_at)))
    if lowest is None:
        return 0
    total = 0
    start = lowest
    end_all = _utcnow() + timedelta(days=1)
    while start < end_all:
        stop = start + TIME_WINDOW
        result = await db.execute(
            update(BehaviorSession)
            .where(BehaviorSession.started_at >= start, BehaviorSession.started_at < stop,
                   BehaviorSession.user_id.in_(ids))
            .values(user_id=None)
        )
        total += int(result.rowcount or 0)
        await db.commit()
        start = stop
    return total


async def process_pending_erasures(db: AsyncSession) -> dict[str, int]:
    """Ночная уборка: обнуляет `user_id` в больших аналитических таблицах.

    Идемпотентна. Отметки `analytics_erase_pending` после успеха переименовываются в
    `analytics_erase_done` с пустым `detail`: идентификатор из журнала исчезает.
    """
    rows = (await db.execute(
        select(AuthAudit).where(AuthAudit.event == PENDING_EVENT)
        .order_by(AuthAudit.ts.asc()).limit(MAX_IDS_PER_RUN)
    )).scalars().all()
    ids = [r.detail for r in rows if r.detail]
    if not ids:
        return {"pending": 0, "behavior_events": 0, "behavior_sessions": 0, "server_sessions": 0}
    stats = {"pending": len(ids)}
    stats["frontend_events"] = int((await db.execute(
        update(FrontendEvent).where(FrontendEvent.user_id.in_(ids)).values(user_id=None)
    )).rowcount or 0)
    await db.commit()
    stats["behavior_events"] = await _null_by_id_windows(db, BehaviorEvent, ids)
    stats["server_sessions"] = await _null_by_id_windows(db, ServerSession, ids)
    stats["behavior_sessions"] = await _null_sessions_by_time(db, ids)
    await db.execute(delete(IdentityLink).where(IdentityLink.user_id.in_(ids)))
    for row in rows:
        row.event = DONE_EVENT
        row.detail = None
    await db.commit()
    return stats


def erasure_ids_from_rows(rows: Iterable[AuthAudit]) -> list[str]:
    """Для тестов: идентификаторы ожидающих отметок."""
    return [r.detail for r in rows if r.event == PENDING_EVENT and r.detail]
