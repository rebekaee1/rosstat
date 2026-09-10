"""Bounded, monotone correction of known crawler identities in existing rollups."""
from datetime import date, datetime, time, timedelta

from sqlalchemy import select, update

from app.models import BehaviorSession, ServerSession
from app.services.bot_score import is_known_bot_ua


async def reclassify_known_crawlers_day(db, day: date, *, apply: bool = False) -> dict:
    """Never delete/re-sessionize or clear bot flags. Strict temporal identity join.

    A portrait from another session of the same visitor is insufficient evidence.
    Dry run rolls back, apply commits one MSK day, no notifications or raw IDs.
    """
    start = datetime.combine(day, time()) - timedelta(hours=3)
    end = start + timedelta(days=1)
    rows = (await db.execute(select(ServerSession.id, BehaviorSession.ua_raw).join(
        BehaviorSession,
        (BehaviorSession.visitor_id_hash == ServerSession.visitor_id_hash)
        & (BehaviorSession.started_at >= ServerSession.started_at)
        & (BehaviorSession.started_at <= ServerSession.ended_at),
    ).where(
        ServerSession.day == day,
        (ServerSession.is_bot.is_(False)) | (ServerSession.bot_score < 100),
        BehaviorSession.started_at >= start,
        # Portrait must belong to the actual session, even if it crosses midnight.
        ServerSession.started_at >= start, ServerSession.started_at < end,
    ))).all()
    ids = sorted({sid for sid, ua in rows if is_known_bot_ua(ua)})
    if len(ids) > 100_000:
        raise RuntimeError("day exceeds bounded repair limit; inspect before applying")
    if apply:
        for offset in range(0, len(ids), 1000):
            await db.execute(update(ServerSession).where(ServerSession.id.in_(ids[offset:offset + 1000]))
                             .values(is_bot=True, bot_score=100))
        await db.commit()
    else:
        await db.rollback()
    return {"day": day.isoformat(), "candidate_portraits": len(rows),
            "known_crawler_sessions": len(ids), "updated": len(ids) if apply else 0,
            "mode": "apply" if apply else "dry_run"}
