"""Счётчик публичных рядов по странам: материализованная таблица вместо COUNT по 280 тыс. строк (круг 12, SPEED3).

Проблема (журнал боевого 12.10.2026, 25 минут после выпуска): холодный рендер главной считает «сколько рядов у страны»
запросом `SELECT country_id, count(*) FROM world_indicators WHERE is_listed GROUP BY country_id`. План хороший
(index-only scan), но читает 90 МБ широкого покрывающего индекса `ix_world_indicators_listed_signal`; пока диск занят
чужими сканами, запрос занимает 15–30 с и упирается в `statement_timeout` (30 с): страница 504, пересчёт SWR
(`swr revalidate … -> 504`) не удаётся, кэш главной стареет.

Решение: таблица `world_country_listed_counts` (одна строка на страну, ≈ 55 строк) пересчитывается
* по расписанию (`world_listed_counts_job`, раз в 15 минут и сразу после запуска планировщика);
* после загрузок данных: `bump_namespaces("world-catalog")` вызывает `refresh_before_catalog_bump` ДО сброса кэша,
  поэтому новая версия кэша сразу строится по свежим числам.
Читатели (`listed_country_links`, `_world_rating_countries`) берут таблицу через `read_listed_counts`; результат
совпадает с прежним подзапросом (то же условие, тот же `GROUP BY`; страны без публичных рядов отсутствуют).
Если флаг выключен, таблицы нет, она пуста или не обновлялась дольше `world_listed_counts_max_age_seconds`,
`read_listed_counts` возвращает None, и читатель считает по-старому.

Пересчёт сам использует узкий индекс `ix_world_indicators_listed_country` (2 МБ), поэтому дёшев и без таблицы.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import WorldCountryListedCount, WorldIndicator

logger = logging.getLogger(__name__)

# Пересчёт ходит в фоне: ему можно дольше, чем публичному запросу (30 с).
REFRESH_STATEMENT_TIMEOUT_MS = 120_000
_ADVISORY_LOCK_KEY = 0x57C0_17ED  # произвольная константа: один пересчёт за раз


def _utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def read_listed_counts(db: AsyncSession) -> dict[int, int] | None:
    """{country_id: число публичных рядов} из материализованной таблицы либо None (считать по-старому).

    Читается в savepoint: отсутствие таблицы (выкладка раньше миграции) не отравляет транзакцию запроса.
    """
    if not settings.world_listed_counts_enabled:
        return None
    try:
        async with db.begin_nested():
            rows = (
                await db.execute(
                    select(
                        WorldCountryListedCount.country_id,
                        WorldCountryListedCount.listed_count,
                        WorldCountryListedCount.computed_at,
                    )
                )
            ).all()
    except Exception as exc:  # noqa: BLE001 — любой сбой чтения = путь без таблицы
        logger.warning("world listed counts table unavailable: %s", exc)
        return None
    if not rows:
        return None
    newest = max(row.computed_at for row in rows)
    max_age = timedelta(seconds=max(60, int(settings.world_listed_counts_max_age_seconds)))
    if newest is None or _utcnow_naive() - newest > max_age:
        logger.warning("world listed counts table is stale (newest %s): falling back to live count", newest)
        return None
    return {int(row.country_id): int(row.listed_count) for row in rows}


async def refresh_world_listed_counts(db: AsyncSession) -> dict[str, int]:
    """Пересчитать таблицу целиком в одной транзакции; вернуть {"countries": N, "rows_deleted": M}."""
    bind = db.get_bind()
    if bind.dialect.name == "postgresql":
        await db.execute(
            text("SELECT set_config('statement_timeout', :v, true)"), {"v": str(REFRESH_STATEMENT_TIMEOUT_MS)}
        )
        # Параллельные пересчёты (расписание и загрузка данных) ждут друг друга, а не спорят за вставку строк.
        await db.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": _ADVISORY_LOCK_KEY})
    counts = {
        int(country_id): int(n)
        for country_id, n in (
            await db.execute(
                select(WorldIndicator.country_id, func.count())
                # Голая колонка (не `IS TRUE`): предикат узкого и покрывающего partial-индексов.
                .where(WorldIndicator.is_listed)
                .group_by(WorldIndicator.country_id)
            )
        ).all()
    }
    existing = {
        int(row.country_id): row
        for row in (await db.execute(select(WorldCountryListedCount))).scalars().all()
    }
    now = _utcnow_naive()
    for country_id, n in counts.items():
        row = existing.pop(country_id, None)
        if row is None:
            db.add(WorldCountryListedCount(country_id=country_id, listed_count=n, computed_at=now))
        else:
            row.listed_count = n
            row.computed_at = now
    deleted = len(existing)
    for row in existing.values():
        await db.delete(row)
    await db.commit()
    return {"countries": len(counts), "rows_deleted": deleted}


async def _refresh_in_new_session() -> dict[str, int]:
    from app.database import async_session

    async with async_session() as db:
        return await refresh_world_listed_counts(db)


async def world_listed_counts_job() -> None:
    """Задача планировщика: no-op, пока флаг выключен."""
    if not settings.world_listed_counts_enabled:
        return
    result = await _refresh_in_new_session()
    logger.info("world listed counts refreshed: %s", result)


async def refresh_before_catalog_bump() -> None:
    """Вызывается из `bump_namespaces` при сбросе `world-catalog`, до смены версии кэша; ошибки не пробрасывает."""
    if not settings.world_listed_counts_enabled:
        return
    try:
        result = await _refresh_in_new_session()
        logger.info("world listed counts refreshed after catalogue change: %s", result)
    except Exception:  # noqa: BLE001 — сброс кэша важнее счётчика; расписание догонит
        logger.warning("world listed counts refresh after catalogue change failed", exc_info=True)
