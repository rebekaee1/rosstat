"""Shared upsert helper for IndicatorData — on_conflict_do_update ensures revisions are captured.

This is the seam that enforces the ADR-0002 invariant: any source revision
(value change for an existing date) is automatically picked up at the next ETL.
The `where=(value != excluded.value)` guard makes repeated upserts of unchanged
points a no-op — `records_added`/`records_updated` only increment on real change.

See `docs/adr/0002-derived-always-reflects-source.md` for the full invariant
and its boundaries (pure-revision day limitation). The same idempotency holds
for every concrete parser (CBR / Минфин / Rosstat) — see parser docstrings
in `backend/app/services/*_parser.py`.
"""

import logging
import math
from datetime import date as _date
from datetime import timedelta as _timedelta

from sqlalchemy import delete, func, literal_column, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import IndicatorData

logger = logging.getLogger(__name__)

# Сторож данных (08.11.2026): единственная точка записи рядов, через неё идут все парсеры, derived и мировые ряды.
# 05.11.2026 парсер цен на топливо записал 31 неделю датами 0001-01-10… (лист «1» в файле Росстата), derived размножили
# их до 194 точек, годовые страницы падали с 500. Даты вне [DATE_MIN, сегодня + FUTURE_DAYS] и нечисловые значения
# (NaN, ±inf) в базу не пишутся; об отброшенном — алерт `data_guard` (в спокойном режиме уходит в утреннюю сводку).
DATE_MIN = _date(1800, 1, 1)
FUTURE_DAYS = 730
_GUARD_MUTE_SECONDS = 24 * 3600


def point_rejection(dt, val) -> str | None:
    """Почему точку нельзя писать (`None` — можно). Чистая функция, без базы."""
    if not isinstance(dt, _date):
        return "дата не распознана"
    if dt < DATE_MIN:
        return f"дата {dt.isoformat()} раньше {DATE_MIN.year} года"
    if dt > _date.today() + _timedelta(days=FUTURE_DAYS):
        return f"дата {dt.isoformat()} дальше двух лет вперёд"
    try:
        num = float(val)
    except (TypeError, ValueError):
        return "значение не число"
    if not math.isfinite(num):
        return "значение не конечное число"
    return None


# П-1: пачка на statement. 3 параметра на строку — с запасом под лимит
# asyncpg в 32767 bind-параметров.
_BATCH_CHUNK = 5000


def upsert_indicator_data(indicator_id: int, dt: _date, val: float):
    """INSERT … ON CONFLICT (indicator_id, date) DO UPDATE SET value = excluded.value
    only when value actually changed. Returns affected row via RETURNING."""
    stmt = pg_insert(IndicatorData).values(
        indicator_id=indicator_id, date=dt, value=val,
    )
    return stmt.on_conflict_do_update(
        constraint="uq_indicator_date",
        set_={"value": stmt.excluded.value},
        where=(IndicatorData.__table__.c.value != stmt.excluded.value),
    ).returning(IndicatorData.id)


def _split_point(point):
    """Accept either dataclass/NamedTuple with .date/.value or plain (date, value) tuple."""
    if hasattr(point, "date") and hasattr(point, "value"):
        return point.date, point.value
    if isinstance(point, (tuple, list)) and len(point) >= 2:
        return point[0], point[1]
    raise TypeError(f"Unsupported point shape for bulk_upsert: {type(point).__name__}")


async def prune_indicator_dates_not_in(
    db: AsyncSession,
    indicator_id: int,
    points: list,
    *,
    keep_after: _date | None = None,
) -> int:
    """Удалить точки индикатора, которых нет в свежем parse-output.

    Для источников с полным снимком ряда (Минфин OpenData CSV) — убирает
    устаревшие preliminary-точки из пресс-релизов, если парсер их больше
    не отдаёт.

    `keep_after`: точки с датой > keep_after не трогаются (снимок из резервного
    источника покрывает ряд только до этой даты — более свежие точки из
    основного источника удалять нельзя).
    """
    parsed_dates = {_split_point(p)[0] for p in points}
    if not parsed_dates:
        return 0
    conditions = [
        IndicatorData.indicator_id == indicator_id,
        IndicatorData.date.not_in(parsed_dates),
    ]
    if keep_after is not None:
        conditions.append(IndicatorData.date <= keep_after)
    result = await db.execute(delete(IndicatorData).where(*conditions))
    deleted = result.rowcount or 0
    if deleted:
        await db.flush()
    return deleted


def batch_upsert_stmt(indicator_id: int, rows: list[tuple[_date, float]]):
    """Multi-row INSERT … ON CONFLICT DO UPDATE (WHERE value <> excluded.value)
    RETURNING (xmax = 0): true = вставка, false = обновление существующей даты.

    Незатронутые WHERE-гардом строки в RETURNING не попадают — счётчики
    added/updated считают только реальные изменения (инвариант ADR-0002,
    Р-2: от них зависят каскады derived/forecast/cache-invalidate).
    """
    stmt = pg_insert(IndicatorData).values([
        {"indicator_id": indicator_id, "date": dt, "value": val}
        for dt, val in rows
    ])
    return stmt.on_conflict_do_update(
        constraint="uq_indicator_date",
        set_={"value": stmt.excluded.value},
        where=(IndicatorData.__table__.c.value != stmt.excluded.value),
    ).returning(literal_column("(xmax = 0)").label("inserted"))


def _dedup_points(points: list, rejected: list | None = None) -> dict[_date, float]:
    """Отфильтровать None (ADR-0002 boundary), отбросить невозможные точки (сторож данных) и схлопнуть
    дубли дат (last wins): ON CONFLICT в одном statement не может тронуть строку дважды.
    `rejected` — сюда кладутся (дата, значение, причина) отброшенных сторожем."""
    dedup: dict[_date, float] = {}
    for point in points:
        dt, val = _split_point(point)
        # ADR-0002 boundary: never overwrite an existing value with NULL/None.
        # An empty/None payload from a parser (e.g. source page changed shape,
        # got 502) must NOT silently wipe what's already in the DB.
        if val is None:
            continue
        reason = point_rejection(dt, val)
        if reason:
            if rejected is not None:
                rejected.append((dt, val, reason))
            continue
        dedup[dt] = val
    return dedup


async def _report_rejected(db: AsyncSession, indicator_id: int, rejected: list) -> None:
    """Лог и алерт `data_guard` (раз в сутки на ряд). Ошибки алерта не мешают записи."""
    from app.config import settings

    sample = ", ".join(f"{d!s}={v!r}" for d, v, _r in rejected[:3])
    logger.error("Сторож данных: ряд %s, отброшено %d точек (%s; %s)",
                 indicator_id, len(rejected), rejected[0][2], sample)
    if not (settings.telegram_bot_token and settings.telegram_chat_id):
        return
    try:
        from html import escape

        from app.models import Indicator
        from app.services.alerting import alert_muted, send_telegram

        code = (await db.execute(select(Indicator.code).where(Indicator.id == indicator_id))).scalar() or str(indicator_id)
        if await alert_muted(f"data_guard:{code}", _GUARD_MUTE_SECONDS):
            return
        first = rejected[0][2]
        await send_telegram(
            "🟡 <b>Сторож данных не пустил точки в базу</b>\n"
            f"Ряд <code>{escape(code)}</code>: отброшено {len(rejected)} — {escape(first)}"
            + (" и др." if len(rejected) > 1 else "") + ". Остальные точки записаны; источник, вероятно, сменил формат.",
            kind="data_guard",
        )
    except Exception:  # noqa: BLE001
        logger.warning("data_guard alert failed", exc_info=True)


async def bulk_upsert(db: AsyncSession, indicator_id: int, points: list) -> tuple[int, int]:
    """Upsert a list of points. Accepts objects with .date/.value OR (date, value) tuples.
    Returns (new_records, updated_records) — только РЕАЛЬНЫЕ изменения.

    П-1: на Postgres — chunked multi-row statement (2 SQL-обращения на 5000
    точек вместо 2N+2). На прочих диалектах (SQLite в тестах) — построчный
    путь с count-подсчётом, поведение идентично.
    """
    rejected: list = []
    dedup = _dedup_points(points, rejected)
    if rejected:
        await _report_rejected(db, indicator_id, rejected)
    if not dedup:
        return 0, 0

    dialect_name = getattr(getattr(getattr(db, "bind", None), "dialect", None), "name", "")
    if dialect_name != "postgresql":
        return await _bulk_upsert_row_by_row(db, indicator_id, dedup)

    added = updated = 0
    items = sorted(dedup.items())
    for i in range(0, len(items), _BATCH_CHUNK):
        chunk = items[i:i + _BATCH_CHUNK]
        result = await db.execute(batch_upsert_stmt(indicator_id, chunk))
        for (inserted,) in result.fetchall():
            if inserted:
                added += 1
            else:
                updated += 1
    await db.flush()
    return added, updated


async def _bulk_upsert_row_by_row(
    db: AsyncSession, indicator_id: int, dedup: dict[_date, float],
) -> tuple[int, int]:
    """Портируемый путь (не-Postgres): xmax недоступен — added выводится из
    count-разницы, как в исходной реализации."""
    count_before = (await db.execute(
        select(func.count(IndicatorData.id))
        .where(IndicatorData.indicator_id == indicator_id)
    )).scalar() or 0

    changed = 0
    for dt, val in sorted(dedup.items()):
        result = await db.execute(upsert_indicator_data(indicator_id, dt, val))
        if result.fetchone() is not None:
            changed += 1

    await db.flush()
    count_after = (await db.execute(
        select(func.count(IndicatorData.id))
        .where(IndicatorData.indicator_id == indicator_id)
    )).scalar() or 0

    records_added = count_after - count_before
    records_updated = changed - records_added
    return records_added, records_updated
