"""One-shot: добавить точку реального ВВП за I кв. 2026 из официальной
предварительной оценки Росстата (публикация 15.05.2026).

Росстат опубликовал по I кв. 2026 только **индекс физического объёма ВВП**
= 99.8% к I кв. 2025 (т.е. −0.2% г/г) в составе оперативного релиза; полный
квартальный файл уровней (`VVP_kvartal_s_1995-*.xlsx`) на момент скрипта ещё
заканчивается Q4 2025. Уровень I кв. 2026 в постоянных ценах 2021 г.
реконструируется как `level(Q1 2025) * 0.998` — стандартная связка
индекс×база. Значение берётся из БД, не хардкодится.

Идемпотентность (ADR-0002): когда Росстат добавит Q1 2026 в файл уровней,
обычный ETL перезапишет точку официальным значением через
`on_conflict_do_update WHERE value <> excluded.value`. До тех пор файловый ETL
точку не трогает (в файле этой даты нет) — значит ручная оценка устойчива.

Только `gdp-real`: официальная оценка относится к физическому объёму. Для
`gdp-nominal` Росстат отдельной оценки не публиковал (нужен дефлятор) — её
не реконструируем, ждём официальный номинальный уровень.

Запуск (в backend-контейнере):
    docker compose exec backend python /app/scripts/insert-gdp-q1-2026-estimate.py
"""

from __future__ import annotations

import asyncio
from datetime import date

from sqlalchemy import select

from app.core.cache import cache_invalidate_indicator, close_redis
from app.database import async_session
from app.models import Indicator, IndicatorData
from app.services.calculation_engine import calculation_engine
from app.services.upsert import bulk_upsert

# Официальный предварительный индекс физобъёма ВВП, I кв. 2026 к I кв. 2025
# (Росстат, 15.05.2026): 99.8% → коэффициент к базе прошлого года.
Q1_2026_VOLUME_INDEX = 0.998
BASE_DATE = date(2025, 3, 1)   # I кв. 2025 (база)
TARGET_DATE = date(2026, 3, 1)  # I кв. 2026 (оценка)


async def main() -> None:
    async with async_session() as db:
        ind = (await db.execute(
            select(Indicator).where(Indicator.code == "gdp-real")
        )).scalar_one_or_none()
        if ind is None:
            raise SystemExit("gdp-real indicator not found")

        base = (await db.execute(
            select(IndicatorData.value)
            .where(IndicatorData.indicator_id == ind.id)
            .where(IndicatorData.date == BASE_DATE)
        )).scalar_one_or_none()
        if base is None:
            raise SystemExit(f"base point gdp-real @ {BASE_DATE} not found")

        estimate = round(float(base) * Q1_2026_VOLUME_INDEX, 1)
        added, updated = await bulk_upsert(db, ind.id, [(TARGET_DATE, estimate)])
        await db.commit()

        print(
            f"gdp-real {TARGET_DATE}: base({BASE_DATE})={base} × "
            f"{Q1_2026_VOLUME_INDEX} = {estimate}  (added={added}, updated={updated})"
        )

        # Каскад: derived (yoy/qoq/annual) должны отразить новую точку
        # (ADR-0002: derived[t] всегда = текущее состояние source[t]).
        changed = await calculation_engine.run_for_updated_sources(db, ["gdp-real"])
        await db.commit()
        print("derived recomputed:", [c for c in changed if c.startswith("gdp-real")])

    # Инвалидация кэша через сам клиент приложения (Redis под AUTH —
    # внешний redis-cli FLUSHALL без пароля бесшумно не сработает).
    for code in ("gdp-real", "gdp-real-yoy", "gdp-real-qoq", "gdp-real-annual"):
        await cache_invalidate_indicator(code)
    await close_redis()
    print("cache invalidated")


if __name__ == "__main__":
    asyncio.run(main())
