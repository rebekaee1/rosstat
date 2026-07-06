"""Т-3: ловим дрейф «модели ↔ миграции».

Запускается в CI после `alembic upgrade head` на чистом Postgres: сравнивает
живую схему с `Base.metadata` через alembic autogenerate. Если модель получила
таблицу/колонку/индекс, а миграции нет (или наоборот) — CI красный.

Шумовые категории (изменение типа/server_default, которые autogenerate
регулярно даёт ложно на JSON/Numeric) не фейлят, только печатаются.
"""

from __future__ import annotations

import asyncio
import sys

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import settings
from app.models import Base

# Категории diff'а, означающие реальный дрейф структуры.
_FATAL = {
    "add_table", "remove_table",
    "add_column", "remove_column",
    "add_index", "remove_index",
    "add_constraint", "remove_constraint",
}


def _diff_kind(entry) -> str:
    # compare_metadata отдаёт кортежи ("add_column", None, "table", Column(...))
    # либо списки таких кортежей для модификаций.
    if isinstance(entry, list):
        entry = entry[0]
    return entry[0]


async def main() -> int:
    engine = create_async_engine(settings.database_url)
    try:
        async with engine.connect() as conn:
            def _compare(sync_conn):
                ctx = MigrationContext.configure(sync_conn)
                return compare_metadata(ctx, Base.metadata)

            diffs = await conn.run_sync(_compare)
    finally:
        await engine.dispose()

    fatal, noise = [], []
    for d in diffs:
        (fatal if _diff_kind(d) in _FATAL else noise).append(d)

    for d in noise:
        print(f"[noise] {d}")
    for d in fatal:
        print(f"[DRIFT] {d}")

    if fatal:
        print(f"\nFAILED: {len(fatal)} расхождений моделей с миграциями.")
        return 1
    print(f"OK: структурного дрейфа нет ({len(noise)} шумовых отличий).")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
