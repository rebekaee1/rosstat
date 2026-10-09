"""Разовое восстановление `user_signups` для уже зарегистрированных (круг 11, зона H).

До круга 11 язык сайта регистрации был только в тексте мгновенного сообщения
«Новый пользователь» в архиве `telegram_outbox` (строка «Версия сайта: …»,
идентификатор `ID: <code>…</code>`). Скрипт:

1. разбирает эти сообщения (только чтение, архив не меняется и не чистится);
2. создаёт строку `user_signups(source='backfill')` для каждого аккаунта, у которого её нет:
   язык, способ входа, рассылка — из сообщения; если сообщения нет, поля остаются пустыми
   (честная пустота, не угаданное значение);
3. добирает канал, устройство, посадочную страницу, страну, дни до регистрации и
   «что подтолкнуло» из первой сессии посетителя (`identity_links → behavior_sessions`).

Идемпотентно: повторный запуск ничего не дублирует. Боевую базу не нагружает: один проход
по `users`, архиву и `user_signups`, атрибуция пачками по 200.

Запуск:  docker compose exec backend python scripts/backfill-signup-attribution.py
Пробный прогон без записи:  ... --dry-run
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import func, select  # noqa: E402

from app.database import analytics_session  # noqa: E402
from app.models import UserSignup  # noqa: E402
from app.services.signup_attribution import (  # noqa: E402
    backfill_from_outbox,
    ensure_signup_attribution,
    refill_empty_attribution,
)


async def main(dry_run: bool) -> None:
    async with analytics_session() as db:
        if dry_run:
            total = await db.scalar(select(func.count()).select_from(UserSignup))
            print(f"Пробный прогон: сейчас в user_signups {total} строк; ничего не записано.")
            return
        stats = await backfill_from_outbox(db)
        print("Из архива Telegram:", stats)
    far_past = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=3650)
    total = 0
    while True:
        async with analytics_session() as db:
            done = await ensure_signup_attribution(db, since=far_past, limit=200, min_age=timedelta(0))
        total += done
        if done < 200:
            break
    async with analytics_session() as db:
        refilled = await refill_empty_attribution(db, since=far_past, limit=1000)
    print(f"Атрибуция из первой сессии: обработано {total}, добрано повторно {refilled}")
    async with analytics_session() as db:
        with_locale = await db.scalar(
            select(func.count()).select_from(UserSignup).where(UserSignup.site_locale.is_not(None)))
        all_rows = await db.scalar(select(func.count()).select_from(UserSignup))
    print(f"Итого строк: {all_rows}, из них с языком сайта: {with_locale}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="ничего не писать")
    args = parser.parse_args()
    asyncio.run(main(args.dry_run))
