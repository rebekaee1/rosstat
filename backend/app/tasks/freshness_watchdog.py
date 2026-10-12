"""Сторож свежести: раз в сутки считает просроченные публичные ряды (круг 12).

Правила — `app.services.freshness`. Одно сгруппированное сообщение владельцу в
Telegram (источник · сколько рядов · примеры · причины), сводка для
`/api/v1/health/freshness` кладётся в state-Redis. Флаг
`RUSTATS_FRESHNESS_WATCHDOG_ENABLED` по умолчанию выключен. Повтор того же самого
сообщения — не чаще раза в неделю (`decide_send`), задача идёт раз в сутки.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.config import settings
from app.database import async_session
from app.services.alerting import send_telegram
from app.services.freshness import (
    collect_freshness,
    decide_send,
    format_message,
    load_last_sent,
    store_last_sent,
    store_summary,
)

logger = logging.getLogger(__name__)


async def freshness_watchdog_job() -> dict:
    """Собрать сводку, сохранить для health-ручки, при необходимости сообщить."""
    async with async_session() as db:
        report = await collect_freshness(db)
    summary = report.as_dict()
    await store_summary(summary)

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    previous = await load_last_sent()
    send, reason = decide_send(
        report, min_stale=int(settings.freshness_watchdog_min_stale), previous=previous, now=now,
    )
    logger.info(
        "Freshness watchdog: %d stale of %d series, %d source group(s); notify=%s (%s)",
        report.stale, report.total, len(report.stale_groups()), send, reason,
    )
    if send:
        delivered = await send_telegram(format_message(report, previous=previous), kind="freshness_watchdog")
        if delivered:
            await store_last_sent(report.signature(), now, digest=report.digest(), stale=report.stale)
    return {"stale": report.stale, "total": report.total, "notified": send, "reason": reason}
