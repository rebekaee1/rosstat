"""Backfill каналов привлечения для старых портретов сессий (этап 0б BI 2.1).

behavior_sessions.channel появился в середине дня 2026-07-06 — портреты,
записанные раньше, лежат с channel=NULL (93% на момент аудита), хотя
referrer/UTM/yclid у них сохранены. Дозаполняем классификатором
traffic_channel.classify_channel по уже имеющимся полям; после полного
пересчёта сессионизации (этап 3) каналы протекут в server_sessions.

Идемпотементно: трогает только строки с channel IS NULL.

Запуск: docker compose exec backend python scripts/backfill-behavior-channels.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.database import async_session  # noqa: E402
from app.models import BehaviorSession  # noqa: E402
from app.services.traffic_channel import classify_channel  # noqa: E402


async def main() -> None:
    async with async_session() as db:
        rows = (await db.execute(
            select(BehaviorSession).where(BehaviorSession.channel.is_(None))
        )).scalars().all()
        updated = 0
        for s in rows:
            channel = classify_channel(
                referrer=s.referrer, utm_source=s.utm_source,
                utm_medium=s.utm_medium, yclid=s.yclid,
            )
            if channel:
                s.channel = channel
                updated += 1
        await db.commit()
        print(f"Портретов без канала: {len(rows)}; дозаполнено: {updated}")


if __name__ == "__main__":
    asyncio.run(main())
