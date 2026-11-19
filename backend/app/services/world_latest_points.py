"""Последние две точки мировых рядов — узкая копия для каталога страны (19.11.2026, ADR-0037).

Зачем. Холодный каталог европейской страны (`GET /world/countries/{slug}`) строился 20–30 с: для 8,5 тыс. рядов
он читал последние две точки из `world_data_points` (16,5 млн строк, 0,9 ГБ + индексы 1 ГБ при памяти базы 0,9 ГБ).
Значение лежит только в строке таблицы, поэтому каждый ряд — около двух случайных чтений с диска (боевой 19.11:
500 рядов Германии — 938 чтений, 1,87 с; диапазон 1 540 рядов — 18,4 с). Очистка таблицы этого не меняет.

Что здесь. `world_latest_points` — одна строка на мировой ряд: дата и значение последней и предпоследней точки и
отметка «есть ненулевая точка» (`has_nonzero`, то же условие, что `_ids_with_nonzero_signal`). Индекс по стране
покрывает все столбцы: каталог страны читает несколько десятков подряд идущих страниц индекса вместо тысяч страниц
таблицы точек. Ответ каталога тот же: строка хранит ровно то, что давали `latest_world_point_series(limit=2)` и
проверка ненулевой точки.

Свежесть — три механизма:

* **загрузчики** (`sync_latest_points`): каждый, кто пишет точки ряда, после пересчёта охвата ряда
  (`points_count`, `history_start/end`) пересчитывает и строку копии — в той же транзакции. Копия меняется вместе с
  точками, без окна устаревания. Работает, когда копия заведена (есть строка состояния), независимо от флага чтения;
* **обход** (`sweep`): задача планировщика проходит опубликованные ряды страна за страной частями по
  `world_latest_points_chunk` рядов и сверяет строки с таблицей точек. Первый полный проход заполняет копию, дальше
  обход повторяется раз в `world_latest_points_resweep_days` суток и чинит то, что прошло мимо загрузчиков (ручной SQL,
  удалённые ряды). Каждая часть — своя короткая транзакция; часть берёт исключительную рекомендательную блокировку
  без ожидания, загрузчики — разделяемую, поэтому обход не перезаписывает строку, которую загрузчик меняет в
  незакрытой транзакции, и не стоит в очереди перед загрузчиками (занято — часть откладывается до следующего запуска);
* **читатель** (`read_latest_points`) берёт копию, только если флаг `world_latest_points_enabled` включён и первый
  полный проход закончен. Рядов, которых в копии нет, читатель не угадывает: их последние точки каталог читает из
  таблицы точек, как раньше.

Выключение: флаг — каталог сразу читает таблицу точек. Остановить и загрузчики: удалить строку состояния
(`DELETE FROM world_latest_points_state`) — через `_STATE_TTL_SECONDS` процессы перестают писать в копию.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timezone

from sqlalchemy import delete, exists, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import WorldCountry, WorldDataPoint, WorldIndicator, WorldLatestPoint, WorldLatestPointsState

logger = logging.getLogger(__name__)

STATE_ID = 1
# Сколько процесс помнит «копия заведена / нет». Обход начинается не раньше чем через 2 таких срока после заведения
# копии: к первой части все загрузчики уже пишут в неё.
_STATE_TTL_SECONDS = 60.0
_ADVISORY_LOCK_KEY = 0x1A7E_5701  # загрузчики — разделяемая, часть обхода — исключительная
_CHUNK_STATEMENT_TIMEOUT_MS = 120_000
_TABLE = WorldLatestPoint.__table__

_state_cache: dict[str, object] = {"checked": float("-inf"), "maintained": False}


def reset_cache() -> None:
    """Забыть, заведена ли копия (тесты и сразу после заведения в этом же процессе)."""
    _state_cache["checked"] = float("-inf")
    _state_cache["maintained"] = False


def _utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _postgres(db: AsyncSession) -> bool:
    return db.get_bind().dialect.name == "postgresql"


def _insert(db: AsyncSession):
    if _postgres(db):
        from sqlalchemy.dialects.postgresql import insert
    else:
        from sqlalchemy.dialects.sqlite import insert
    return insert(_TABLE)


_PAYLOAD = ("country_id", "last_date", "last_value", "prev_date", "prev_value", "has_nonzero")


async def _upsert(db: AsyncSession, rows: list[dict]) -> int:
    """Записать строки копии; строку, где ничего не изменилось, не трогать (без лишних версий строк)."""
    if not rows:
        return 0
    changed = 0
    for start in range(0, len(rows), 1000):
        stmt = _insert(db).values(rows[start:start + 1000])
        stmt = stmt.on_conflict_do_update(
            index_elements=[_TABLE.c.indicator_id],
            set_={**{name: stmt.excluded[name] for name in _PAYLOAD}, "synced_at": stmt.excluded.synced_at},
            where=or_(*(_TABLE.c[name].is_distinct_from(stmt.excluded[name]) for name in _PAYLOAD)),
        )
        changed += int((await db.execute(stmt)).rowcount or 0)
    return changed


def _row(indicator_id: int, country_id: int, points: list[tuple[date, object]], has_nonzero: bool,
         now: datetime) -> dict:
    last = points[0] if points else (None, None)
    prev = points[1] if len(points) > 1 else (None, None)
    return {"indicator_id": indicator_id, "country_id": country_id, "last_date": last[0], "last_value": last[1],
            "prev_date": prev[0], "prev_value": prev[1], "has_nonzero": bool(has_nonzero), "synced_at": now}


async def _computed_rows(db: AsyncSession, pairs: list[tuple[int, int]]) -> list[dict]:
    """Строки копии для пар (ряд, страна) по таблице точек: две последние точки и «есть ненулевая точка».

    Значения — как в базе (Numeric), без перевода в float: читатель переводит их так же, как старый путь.
    """
    if not pairs:
        return []
    ids = [iid for iid, _ in pairs]
    if _postgres(db):
        from sqlalchemy import true

        from app.services.world_subnational_queries import _ids_subquery

        id_rows = _ids_subquery(sorted(set(ids)))
        pts = (select(WorldDataPoint.date, WorldDataPoint.value)
               .where(WorldDataPoint.indicator_id == id_rows.c.id)
               .order_by(WorldDataPoint.date.desc()).limit(2).lateral("pts"))
        tail_rows = (await db.execute(
            select(id_rows.c.id, pts.c.date, pts.c.value).select_from(id_rows.join(pts, true()))
            .order_by(id_rows.c.id, pts.c.date.desc()))).all()
    else:
        rn = func.row_number().over(partition_by=WorldDataPoint.indicator_id,
                                    order_by=WorldDataPoint.date.desc()).label("rn")
        ranked = (select(WorldDataPoint.indicator_id, WorldDataPoint.date, WorldDataPoint.value, rn)
                  .where(WorldDataPoint.indicator_id.in_(ids)).subquery())
        tail_rows = (await db.execute(
            select(ranked.c.indicator_id, ranked.c.date, ranked.c.value).where(ranked.c.rn <= 2)
            .order_by(ranked.c.indicator_id, ranked.c.date.desc()))).all()
    tails: dict[int, list[tuple[date, object]]] = defaultdict(list)
    for iid, point_date, value in tail_rows:
        tails[int(iid)].append((point_date, value))
    # Ненулевая точка в хвосте — ряд с ненулевой точкой; базу спрашиваем только о рядах с нулевым хвостом
    # (условие то же, что `_ids_with_nonzero_signal`: литерал 0 даёт частичный индекс ненулевых точек).
    nonzero = {iid for iid, points in tails.items() if any(value != 0 for _, value in points)}
    zero_tail = [iid for iid in tails if iid not in nonzero]
    for start in range(0, len(zero_tail), 1000):
        nonzero |= {int(r[0]) for r in (await db.execute(
            select(WorldDataPoint.indicator_id).where(
                WorldDataPoint.indicator_id.in_(zero_tail[start:start + 1000]),
                WorldDataPoint.value != text("0"),
            ).distinct())).all()}
    now = _utcnow_naive()
    return [_row(iid, country_id, tails.get(iid, []), iid in nonzero, now) for iid, country_id in pairs]


# --- Загрузчики -------------------------------------------------------------------------------------------------


async def _maintained(db: AsyncSession) -> bool:
    """Заведена ли копия (есть строка состояния). Память процесса — `_STATE_TTL_SECONDS`; сбой чтения = нет."""
    now = time.monotonic()
    if now - float(_state_cache["checked"]) < _STATE_TTL_SECONDS:
        return bool(_state_cache["maintained"])
    try:
        async with db.begin_nested():
            maintained = (await db.execute(
                select(WorldLatestPointsState.maintained_since).where(WorldLatestPointsState.id == STATE_ID)
            )).scalar_one_or_none() is not None
    except Exception as exc:  # noqa: BLE001 — таблицы ещё нет (код раньше миграции): копия не ведётся
        logger.debug("world latest points state unavailable: %s", type(exc).__name__)
        maintained = False
    _state_cache["checked"] = now
    _state_cache["maintained"] = maintained
    return maintained


async def sync_latest_points(db: AsyncSession, indicator_ids: list[int]) -> None:
    """Пересчитать строки копии для рядов, чьи точки только что записаны. Транзакция — вызывающего.

    Вызывать после записи и удаления точек ряда (там же, где пересчитывается охват ряда). Копия не заведена — ничего.
    Сбой не роняет загрузку: строки этих рядов удаляются, каталог читает их точки из таблицы точек, обход восстановит.
    """
    ids = sorted({int(i) for i in indicator_ids if i is not None})
    if not ids or not await _maintained(db):
        return
    try:
        async with db.begin_nested():
            if _postgres(db):
                # Ждём только часть обхода (секунды); загрузчики друг другу не мешают.
                await db.execute(text("SELECT pg_advisory_xact_lock_shared(:k)"), {"k": _ADVISORY_LOCK_KEY})
            pairs = [(int(iid), int(cid)) for iid, cid in (await db.execute(
                select(WorldIndicator.id, WorldIndicator.country_id).where(WorldIndicator.id.in_(ids)))).all()]
            await _upsert(db, await _computed_rows(db, pairs))
            gone = sorted(set(ids) - {iid for iid, _ in pairs})
            if gone:
                await db.execute(delete(_TABLE).where(_TABLE.c.indicator_id.in_(gone)))
    except Exception:  # noqa: BLE001 — копия не должна ронять загрузку данных
        logger.warning("world latest points sync failed for %d series; dropping their rows", len(ids), exc_info=True)
        try:
            async with db.begin_nested():
                await db.execute(delete(_TABLE).where(_TABLE.c.indicator_id.in_(ids)))
        except Exception:  # noqa: BLE001
            logger.error("world latest points: rows of %d series may be stale until the next sweep", len(ids))


# --- Читатель ---------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class LatestPoints:
    """Последние точки рядов из копии: как `latest_world_point_series(limit=2)` и множество рядов с ненулевой точкой.

    `missing` — ряды, которых в копии нет: их точки читаются из таблицы точек.
    """

    recent: dict[int, list[tuple[date, float]]]
    nonzero: set[int]
    missing: list[int]


async def read_latest_points(db: AsyncSession, country_id: int, indicator_ids: list[int]) -> LatestPoints | None:
    """Последние точки рядов страны из копии; None — копией пользоваться нельзя (флаг, не заполнена, нет таблицы).

    Чтение в savepoint: отсутствие таблиц не портит транзакцию каталога.
    """
    if not settings.world_latest_points_enabled:
        return None
    wanted = {int(i) for i in indicator_ids}
    t = _TABLE
    try:
        async with db.begin_nested():
            filled = (await db.execute(
                select(WorldLatestPointsState.filled_at).where(WorldLatestPointsState.id == STATE_ID)
            )).scalar_one_or_none()
            if filled is None:
                return None
            rows = (await db.execute(
                select(t.c.indicator_id, t.c.last_date, t.c.last_value, t.c.prev_date, t.c.prev_value,
                       t.c.has_nonzero).where(t.c.country_id == country_id))).all()
    except Exception as exc:  # noqa: BLE001 — любой сбой = прежний путь
        logger.warning("world latest points unavailable: %s", type(exc).__name__)
        return None
    recent: dict[int, list[tuple[date, float]]] = {}
    nonzero: set[int] = set()
    seen: set[int] = set()
    for iid, last_date, last_value, prev_date, prev_value, has_nonzero in rows:
        iid = int(iid)
        if iid not in wanted:
            continue
        seen.add(iid)
        if last_date is not None:
            points = [(last_date, float(last_value))]
            if prev_date is not None:
                points.append((prev_date, float(prev_value)))
            recent[iid] = points
            if has_nonzero:
                nonzero.add(iid)
    missing = [iid for iid in indicator_ids if int(iid) not in seen]
    return LatestPoints(recent=recent, nonzero=nonzero, missing=missing)


# --- Обход ------------------------------------------------------------------------------------------------------


async def _state(db: AsyncSession) -> WorldLatestPointsState | None:
    return await db.get(WorldLatestPointsState, STATE_ID)


async def _next_chunk(db: AsyncSession, country_id: int, after_id: int, size: int) -> list[int]:
    # Опубликованные ряды страны: узкий индекс `ix_world_indicators_listed_signal` (страна → id) без чтения строк.
    return [int(i) for i in (await db.execute(
        select(WorldIndicator.id).where(WorldIndicator.is_listed, WorldIndicator.country_id == country_id,
                                        WorldIndicator.id > after_id)
        .order_by(WorldIndicator.id).limit(size))).scalars().all()]


async def sweep_chunk(db: AsyncSession) -> dict:
    """Одна часть обхода в своей транзакции: сверить строки следующих рядов и сдвинуть курсор.

    Статусы: `busy` (загрузка держит блокировку — часть позже), `chunk`, `country_done`, `pass_done`, `idle`.
    """
    postgres = _postgres(db)
    if postgres:
        await db.execute(text("SELECT set_config('statement_timeout', :v, true)"),
                         {"v": str(_CHUNK_STATEMENT_TIMEOUT_MS)})
        await db.execute(text("SELECT set_config('lock_timeout', '5s', true)"))
        got = (await db.execute(text("SELECT pg_try_advisory_xact_lock(:k)"), {"k": _ADVISORY_LOCK_KEY})).scalar()
        if not got:
            await db.rollback()
            return {"status": "busy"}
    state = await _state(db)
    if state is None or state.cursor_country_id is None:
        await db.rollback()
        return {"status": "idle"}
    now = _utcnow_naive()
    country_id = int(state.cursor_country_id)
    ids = await _next_chunk(db, country_id, int(state.cursor_indicator_id or 0),
                            max(1, int(settings.world_latest_points_chunk)))
    if ids:
        changed = await _upsert(db, await _computed_rows(db, [(iid, country_id) for iid in ids]))
        state.cursor_indicator_id = ids[-1]
        state.rows_changed = int(state.rows_changed or 0) + changed
        state.last_run_at = now
        await db.commit()
        return {"status": "chunk", "country_id": country_id, "series": len(ids), "changed": changed}
    # Страна пройдена: строки удалённых рядов страны больше не нужны.
    await db.execute(delete(_TABLE).where(_TABLE.c.country_id == country_id, ~exists(
        select(1).where(WorldIndicator.id == _TABLE.c.indicator_id))))
    following = (await db.execute(select(func.min(WorldCountry.id)).where(WorldCountry.id > country_id))).scalar()
    state.last_run_at = now
    if following is not None:
        state.cursor_country_id, state.cursor_indicator_id = int(following), 0
        await db.commit()
        return {"status": "country_done", "country_id": country_id}
    # Проход закончен: строки стран, которых больше нет.
    await db.execute(delete(_TABLE).where(~exists(select(1).where(WorldCountry.id == _TABLE.c.country_id))))
    state.cursor_country_id, state.cursor_indicator_id = None, None
    state.pass_completed_at = now
    if state.filled_at is None:
        state.filled_at = now
    state.rows = int((await db.execute(select(func.count()).select_from(_TABLE))).scalar() or 0)
    await db.commit()
    return {"status": "pass_done", "rows": state.rows}


async def begin_pass(db: AsyncSession, *, force: bool = False) -> dict:
    """Завести копию (первый вызов) или начать новый проход, если пора. Отдельная короткая транзакция.

    Статусы: `started` (копия заведена — обход начнётся после паузы), `waiting`, `pass` (идёт проход), `fresh`.
    """
    state = await _state(db)
    now = _utcnow_naive()
    if state is None:
        db.add(WorldLatestPointsState(id=STATE_ID, maintained_since=now, rows_changed=0))
        await db.commit()
        reset_cache()
        return {"status": "started"}
    if (now - state.maintained_since).total_seconds() < 2 * _STATE_TTL_SECONDS and not force:
        await db.rollback()
        return {"status": "waiting"}
    if state.cursor_country_id is not None:
        await db.rollback()
        return {"status": "pass"}
    resweep = max(0, int(settings.world_latest_points_resweep_days)) * 86400
    if (state.pass_completed_at is not None and not force
            and (now - state.pass_completed_at).total_seconds() < resweep):
        await db.rollback()
        return {"status": "fresh"}
    first = (await db.execute(select(func.min(WorldCountry.id)))).scalar()
    if first is None:
        await db.rollback()
        return {"status": "fresh"}
    state.cursor_country_id, state.cursor_indicator_id = int(first), 0
    state.pass_started_at, state.rows_changed = now, 0
    await db.commit()
    return {"status": "pass"}


async def sweep(*, max_chunks: int, force: bool = False, session_maker=None, deadline_seconds: float | None = None,
                pause_seconds: float = 0.0) -> dict:
    """Начать проход при необходимости и пройти до `max_chunks` частей. Части — отдельные транзакции."""
    if session_maker is None:
        from app.database import async_session as session_maker
    async with session_maker() as db:
        begun = await begin_pass(db, force=force)
    if begun["status"] != "pass":
        return begun
    started = time.monotonic()
    report: dict = {"status": "pass", "chunks": 0, "series": 0, "changed": 0}
    for _ in range(max(0, max_chunks)):
        async with session_maker() as db:
            step = await sweep_chunk(db)
        if step["status"] in {"busy", "idle"}:
            report["status"] = step["status"]
            break
        report["chunks"] += 1
        report["series"] += int(step.get("series") or 0)
        report["changed"] += int(step.get("changed") or 0)
        if step["status"] == "pass_done":
            report.update(status="pass_done", rows=step.get("rows"))
            break
        if deadline_seconds is not None and time.monotonic() - started > deadline_seconds:
            break
        if pause_seconds:
            await asyncio.sleep(pause_seconds)
    report["seconds"] = round(time.monotonic() - started, 1)
    return report


async def world_latest_points_job() -> None:
    """Задача планировщика: no-op, пока `world_latest_points_enabled` выключен."""
    if not settings.world_latest_points_enabled:
        return
    report = await sweep(max_chunks=settings.world_latest_points_chunks_per_run,
                         deadline_seconds=settings.world_latest_points_run_seconds)
    if report.get("status") not in {"fresh", "waiting"}:
        logger.info("world latest points sweep: %s", report)


async def _cli(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Заполнить или сверить копию последних точек мировых рядов")
    parser.add_argument("--force", action="store_true", help="начать новый проход, даже если прошлый свежий")
    parser.add_argument("--pause", type=float, default=0.5, help="пауза между частями, с")
    args = parser.parse_args(argv)
    while True:
        report = await sweep(max_chunks=50, force=args.force, pause_seconds=args.pause)
        print(report, flush=True)
        status = report.get("status")
        if status in {"started", "waiting"}:
            # Копия только что заведена: ждём, пока все процессы-загрузчики начнут писать в неё.
            await asyncio.sleep(2 * _STATE_TTL_SECONDS + 1)
            continue
        if status == "busy":
            await asyncio.sleep(30)
            continue
        if status != "pass":
            return
        args.force = False


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(_cli())
