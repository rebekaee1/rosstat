#!/usr/bin/env python3
"""B1 (звонок 2026-05-21): backfill ключевой ставки ставкой рефинансирования 1992-2013.

С 13 сентября 2013 года основным инструментом денежно-кредитной политики
Банка России стала ключевая ставка. До этой даты официальной ставкой,
устанавливаемой советом директоров ЦБ, была ставка рефинансирования.

С 1 января 2016 года ставка рефинансирования формально приравнена к
ключевой ставке (Указание ЦБ от 11.12.2015 № 3894-У). Соответственно,
для непрерывного исторического ряда «индикатора цены денег в России»
корректно склеить:

    1992-01-01 → 2013-09-12: ставка рефинансирования
    2013-09-13 → н.в.:        ключевая ставка (key-rate)

Источник истории ставки рефинансирования:
https://www.cbr.ru/statistics/idkp_br/refinancing_rates1/

Запуск:
    docker compose exec backend python /app/../scripts/backfill-keyrate-history.py

Скрипт:
1. Читает текущий ряд key-rate из БД.
2. Если первая точка позже 2000-01-01 — вставляет историю ставки
   рефинансирования (через bulk_upsert, идемпотентно).
3. Не трогает значения key-rate после 2013-09-13.
"""

import asyncio
import logging
from datetime import date

import os
import sys
from pathlib import Path

# Скрипт запускается двумя способами:
# 1. Локально из repo root: `python scripts/backfill-keyrate-history.py`
#    → нужно добавить backend/ в PYTHONPATH.
# 2. В docker-контейнере backend: `docker compose exec backend python /tmp/backfill.py`
#    → модуль `app` уже на корне рабочей директории /app, dir manipulation
#    не нужна. Чтобы не сломать, добавляем оба пути в sys.path.
_here = Path(__file__).resolve().parent
for cand in (_here.parent / "backend", Path("/app"), Path(os.getcwd())):
    if cand.exists() and str(cand) not in sys.path:
        sys.path.insert(0, str(cand))

from sqlalchemy import select  # noqa: E402

from app.database import async_session  # noqa: E402
from app.models import Indicator, IndicatorData  # noqa: E402
from app.services.upsert import bulk_upsert  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("backfill-keyrate")


# Каждая запись — кортеж (дата начала действия, значение в % годовых).
# Источник: cbr.ru/statistics/idkp_br/refinancing_rates1/.
# Точки преобразованы из «диапазон действия → одна точка на дату начала»;
# bulk_upsert идемпотентен, поэтому повторный запуск ничего не сломает.
# Сами события — изменения ставки рефинансирования с 1992 по 2013.
REFINANCING_HISTORY: list[tuple[date, float]] = [
    (date(1992, 1, 1), 20.0),
    (date(1992, 4, 10), 50.0),
    (date(1992, 5, 23), 80.0),
    (date(1993, 3, 30), 100.0),
    (date(1993, 6, 2), 110.0),
    (date(1993, 6, 22), 120.0),
    (date(1993, 6, 29), 140.0),
    (date(1993, 7, 15), 170.0),
    (date(1993, 9, 23), 180.0),
    (date(1993, 10, 15), 210.0),
    (date(1994, 4, 29), 205.0),
    (date(1994, 5, 17), 200.0),
    (date(1994, 6, 2), 185.0),
    (date(1994, 6, 22), 170.0),
    (date(1994, 6, 30), 155.0),
    (date(1994, 8, 1), 150.0),
    (date(1994, 8, 23), 130.0),
    (date(1994, 10, 12), 170.0),
    (date(1994, 11, 17), 180.0),
    (date(1995, 1, 6), 200.0),
    (date(1995, 5, 16), 195.0),
    (date(1995, 6, 19), 180.0),
    (date(1995, 10, 24), 170.0),
    (date(1995, 12, 1), 160.0),
    (date(1996, 2, 10), 120.0),
    (date(1996, 7, 24), 110.0),
    (date(1996, 8, 19), 80.0),
    (date(1996, 10, 21), 60.0),
    (date(1996, 12, 2), 48.0),
    (date(1997, 2, 10), 42.0),
    (date(1997, 4, 28), 36.0),
    (date(1997, 6, 16), 24.0),
    (date(1997, 10, 6), 21.0),
    (date(1997, 11, 11), 28.0),
    (date(1998, 2, 2), 42.0),
    (date(1998, 2, 17), 39.0),
    (date(1998, 3, 2), 36.0),
    (date(1998, 3, 16), 30.0),
    (date(1998, 5, 19), 50.0),
    (date(1998, 5, 27), 150.0),
    (date(1998, 6, 5), 60.0),
    (date(1998, 6, 29), 80.0),
    (date(1998, 7, 24), 60.0),
    (date(1999, 6, 10), 55.0),
    (date(2000, 1, 24), 45.0),
    (date(2000, 3, 7), 38.0),
    (date(2000, 3, 21), 33.0),
    (date(2000, 7, 10), 28.0),
    (date(2000, 11, 4), 25.0),
    (date(2002, 4, 9), 23.0),
    (date(2002, 8, 7), 21.0),
    (date(2003, 2, 17), 18.0),
    (date(2003, 6, 21), 16.0),
    (date(2004, 1, 15), 14.0),
    (date(2004, 6, 15), 13.0),
    (date(2005, 12, 26), 12.0),
    (date(2006, 6, 26), 11.5),
    (date(2006, 10, 23), 11.0),
    (date(2007, 1, 29), 10.5),
    (date(2007, 6, 19), 10.0),
    (date(2008, 2, 4), 10.25),
    (date(2008, 4, 29), 10.5),
    (date(2008, 6, 10), 10.75),
    (date(2008, 7, 14), 11.0),
    (date(2008, 11, 12), 12.0),
    (date(2008, 12, 1), 13.0),
    (date(2009, 4, 24), 12.5),
    (date(2009, 5, 14), 12.0),
    (date(2009, 6, 5), 11.5),
    (date(2009, 7, 13), 11.0),
    (date(2009, 8, 10), 10.75),
    (date(2009, 9, 15), 10.5),
    (date(2009, 9, 30), 10.0),
    (date(2009, 10, 30), 9.5),
    (date(2009, 11, 25), 9.0),
    (date(2009, 12, 28), 8.75),
    (date(2010, 2, 24), 8.5),
    (date(2010, 3, 29), 8.25),
    (date(2010, 4, 30), 8.0),
    (date(2010, 6, 1), 7.75),
    (date(2011, 2, 28), 8.0),
    (date(2011, 5, 3), 8.25),
    (date(2011, 12, 26), 8.0),
    (date(2012, 9, 14), 8.25),
    # На 13.09.2013 ставка рефинансирования (8,25%) сохранялась до конца 2015,
    # а ключевая ставка с этого дня запущена параллельно. В исторический ряд
    # «цена денег» вставляем ставку рефинансирования только до 2013-09-12,
    # дальше — реальные точки key-rate (которые уже в БД).
]


CUTOFF = date(2013, 9, 13)


def _expand_to_daily(events: list[tuple[date, float]], cutoff: date) -> list[tuple[date, float]]:
    """Forward-fill ставка-эвенты в daily-ряд.

    Звонок 2026-05-22, замечание Никиты: «очень мало данных по тому
    периоду и не как у нас в ключевой ставке». Ставка рефинансирования
    публиковалась эвентами (84 точки на 21 год), а current key-rate —
    daily. На графике это создаёт «обрыв плотности»: исторический хвост
    выглядит сильно реже, чем правая часть.

    Метод: для каждой пары соседних эвентов (d_i, v_i) → (d_{i+1}, v_{i+1})
    генерируем по точке на каждый день в [d_i, d_{i+1}). Перед cutoff
    остановка — после неё за дело берётся cbr_keyrate_html парсер.
    """
    if not events:
        return []
    events = sorted(events)
    points: list[tuple[date, float]] = []
    from datetime import timedelta
    for i, (start_d, value) in enumerate(events):
        if start_d >= cutoff:
            break
        end_d = events[i + 1][0] if i + 1 < len(events) else cutoff
        end_d = min(end_d, cutoff)
        d = start_d
        while d < end_d:
            points.append((d, value))
            d = d + timedelta(days=1)
    return points


async def main():
    async with async_session() as db:
        ind = (await db.execute(
            select(Indicator).where(Indicator.code == "key-rate")
        )).scalar_one_or_none()
        if ind is None:
            logger.error("Indicator key-rate not found in DB. Run seed_data.py first.")
            return

        existing = (await db.execute(
            select(IndicatorData.date)
            .where(IndicatorData.indicator_id == ind.id)
            .order_by(IndicatorData.date)
        )).scalars().all()
        if existing:
            logger.info(
                "key-rate: %d points, first=%s, last=%s",
                len(existing), existing[0], existing[-1],
            )
        else:
            logger.warning("key-rate has no data yet, will still insert refinancing history.")

        # Forward-fill эвентов рефинансирования в daily ряд до CUTOFF.
        # После CUTOFF — реальные daily-точки cbr_keyrate_html, не трогаем.
        to_insert = _expand_to_daily(REFINANCING_HISTORY, CUTOFF)
        logger.info("Inserting %d daily refinancing-rate points (1992-01-01 → %s).",
                    len(to_insert), CUTOFF.isoformat())

        added, updated = await bulk_upsert(db, ind.id, to_insert)
        await db.commit()
        logger.info("Done. records_added=%d records_updated=%d", added, updated)


if __name__ == "__main__":
    asyncio.run(main())
