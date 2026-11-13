"""Когда в базу пришла последняя строка сырья: дешёвые запросы вместо `max(ingested_at)` по всей таблице (13.11.2026).

У `raw_metrika_visits` и `behavior_events` нет индекса по `ingested_at`. `SELECT max(ingested_at)` читал таблицу
целиком: 2,6 с и 316 МБ по визитам Метрики (каждые 15 минут из `check_anomalies`), 10–19 с и 1,7 ГБ по событиям
поведения. По `pg_stat_statements` боевого (26.09–13.11.2026) эти два запроса дали 6,1 % всех чтений базы с диска.
Postgres живёт под потолком памяти 3 ГБ при базе 12 ГБ, поэтому каждое такое чтение вытесняет кэш публичных страниц
и поднимает «диск тормозит».

Обе функции отвечают на тот же вопрос по имеющимся индексам:
* визиты Метрики переписываются повторной выгрузкой, поэтому берётся `max(ingested_at)` за последние дни по индексу
  `visit_date`; выгрузка всегда затрагивает свежие даты, более старая строка не может быть самой поздней;
* события поведения только добавляются, поэтому время последней вставки — у строки с наибольшим `id`.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BehaviorEvent, RawMetrikaVisit

# Метрика отдаёт визиты с лагом до 2 суток, повторная выгрузка перечитывает последние дни. Две недели — запас:
# если за это окно строк нет, сырьё заведомо старше любого порога тревоги (36 ч).
METRIKA_FRESHNESS_WINDOW_DAYS = 14


async def latest_metrika_visit_ingest(db: AsyncSession, *, today: date | None = None) -> datetime | None:
    """Время последней записи повизитного сырья Метрики (None, если за окно ничего не пришло)."""
    since = (today or date.today()) - timedelta(days=METRIKA_FRESHNESS_WINDOW_DAYS)
    return await db.scalar(
        select(func.max(RawMetrikaVisit.ingested_at)).where(RawMetrikaVisit.visit_date >= since)
    )


async def latest_behavior_event_ingest(db: AsyncSession) -> datetime | None:
    """Время записи последнего события поведения (строка с наибольшим `id`)."""
    return await db.scalar(
        select(BehaviorEvent.ingested_at).order_by(BehaviorEvent.id.desc()).limit(1)
    )
