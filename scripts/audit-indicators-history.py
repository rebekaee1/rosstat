#!/usr/bin/env python3
"""B3 (звонок 2026-05-21): аудит исторической глубины всех индикаторов.

Запуск:
    docker compose exec backend python /tmp/audit.py > /tmp/audit.txt

Скрипт пробегает по всем активным индикаторам, для каждого считает
(count, first_date, last_date), выводит markdown-таблицу, отсортированную
по first_date. Результат — кандидаты на расширение истории, отсортированные
по возрастанию доступной глубины.
"""

import asyncio
import os
import sys
from pathlib import Path

_here = Path(__file__).resolve().parent
for cand in (_here.parent / "backend", Path("/app"), Path(os.getcwd())):
    if cand.exists() and str(cand) not in sys.path:
        sys.path.insert(0, str(cand))

from sqlalchemy import select, func  # noqa: E402

from app.database import async_session  # noqa: E402
from app.models import Indicator, IndicatorData  # noqa: E402


async def main():
    async with async_session() as db:
        rows = (await db.execute(
            select(
                Indicator.code,
                Indicator.name,
                Indicator.frequency,
                Indicator.category,
                Indicator.is_listed,
                func.count(IndicatorData.id),
                func.min(IndicatorData.date),
                func.max(IndicatorData.date),
            )
            .select_from(Indicator)
            .outerjoin(IndicatorData, IndicatorData.indicator_id == Indicator.id)
            .where(Indicator.is_active.is_(True))
            .group_by(Indicator.code, Indicator.name, Indicator.frequency,
                      Indicator.category, Indicator.is_listed)
        )).all()

    rows = sorted(rows, key=lambda r: (r[6] is None, r[6] or 9999))

    print(f"# Audit: историческая глубина {len(rows)} индикаторов")
    print()
    print(f"Дата запуска: {asyncio.get_event_loop().time():.0f} (UTC epoch)")
    print()
    print("| Код | Категория | Частота | Listed | Точек | C даты | По дату |")
    print("|-----|-----------|---------|--------|------:|--------|---------|")

    for code, name, freq, cat, listed, cnt, mn, mx in rows:
        listed_mark = "✓" if listed else "—"
        first = mn.isoformat() if mn else "—"
        last = mx.isoformat() if mx else "—"
        print(f"| `{code}` | {cat or ''} | {freq} | {listed_mark} | {cnt} | {first} | {last} |")

    print()
    print("## Кандидаты на backfill (история короче 2010)")
    print()
    deep_threshold = "2010-01-01"
    candidates = [r for r in rows if r[6] and r[6].isoformat() > deep_threshold and r[4]]
    print(f"Всего: {len(candidates)}")
    for code, name, freq, cat, _listed, cnt, mn, _mx in candidates:
        print(f"  - `{code}` ({cat}, {freq}) — {cnt} точек с {mn.isoformat()}")


if __name__ == "__main__":
    asyncio.run(main())
