"""Durable журнал изменений server_sessions для репликации в ClickHouse (F05b).

Проблема: CH-копия server_sessions — ReplacingMergeTree с ключом
(visitor_id_hash, started_at). «Replacing insert» умеет только заменять строку
с тем же ключом: он не передаёт УДАЛЕНИЕ (после слияния сессий в PG прежний
ключ остаётся в CH призраком) и окно «последние 2 суток по started_at» не
видит правку более старой сессии (carry нового события к вчерашней/давней
сессии, repair бот-флага).

Контракт: каждая запись в server_sessions, которая создаёт/меняет/убирает
ключ, в ТОЙ ЖЕ транзакции кладёт ключ в `server_session_changes`
(upsert: `rev` растёт, строка одна на ключ). Журнал только говорит «этот ключ
надо перечитать»; истина — текущее состояние PG: строка есть → CH replacing
insert, строки нет → CH ALTER DELETE. Потребитель (`clickhouse_sync`) читает
пачку, применяет её в CH и подтверждает (`ack`) только записи с неизменившимся
`rev`. Курсора и committed-ceiling нет: запись, закоммиченная позже, просто
попадёт в следующую выборку. Повторная обработка идемпотентна.

Пишется только при RUSTATS_CLICKHOUSE_ENABLED=true (иначе журнал рос бы без
потребителя). После включения CH на ранее выключенной системе нужен полный
`resync()`: журнал не восстанавливает историю, он ведёт только будущие правки.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, MetaData, Table, and_, bindparam, delete, exists, func, literal, literal_column, or_, select, text, true, union
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.config import settings
from app.models import ServerSession, ServerSessionChange

KEY_COLUMNS = ("visitor_id_hash", "started_at")
# Колонки server_sessions, которые зеркалятся в CH (без суррогатного id, который
# пересоздаётся при каждом пересчёте окна). Меняется только вместе с
# clickhouse_sync._SERVER_SESSION_COLUMNS (тест test_session_change_log сверяет).
MIRRORED_COLUMNS = (
    "day", "visitor_id_hash", "user_id", "started_at", "duration_ms", "active_ms",
    "pageviews", "clicks", "max_scroll_pct", "entry_page", "exit_page", "channel",
    "device", "is_new_visitor", "is_engaged", "micro_goals", "macro_goals",
    "is_bot", "bot_score", "is_internal",
)
_COMPARED = tuple(c for c in MIRRORED_COLUMNS if c not in KEY_COLUMNS)
_LOG = ServerSessionChange.__table__


def enabled() -> bool:
    return bool(settings.clickhouse_enabled)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def snapshot_table(name: str) -> Table:
    """Временная таблица «как было» (ключ + зеркалируемые колонки)."""
    return Table(
        name, MetaData(),
        *(Column(c, ServerSession.__table__.c[c].type) for c in MIRRORED_COLUMNS),
        prefixes=["TEMPORARY"], postgresql_on_commit="DROP",
    )


async def snapshot(db, previous: Table, *conditions) -> None:
    """Скопировать подлежащие удалению строки server_sessions до DELETE."""
    await db.execute(previous.insert().from_select(
        list(MIRRORED_COLUMNS),
        select(*(ServerSession.__table__.c[c] for c in MIRRORED_COLUMNS)).where(*conditions),
    ))


async def _upsert_keys(db, keys, now: datetime | None = None) -> None:
    """INSERT … SELECT keys ON CONFLICT: новый ключ → rev=1, повторный → rev+1."""
    insert = pg_insert if db.bind.dialect.name == "postgresql" else sqlite_insert
    source = select(
        keys.c.visitor_id_hash, keys.c.started_at,
        literal_column("1"), literal(now or _utcnow(), DateTime()),
    ).where(true())  # SQLite: INSERT…SELECT…ON CONFLICT требует WHERE.
    statement = insert(_LOG).from_select(["visitor_id_hash", "started_at", "rev", "changed_at"], source)
    await db.execute(statement.on_conflict_do_update(
        index_elements=list(KEY_COLUMNS),
        set_={"rev": _LOG.c.rev + 1, "changed_at": statement.excluded.changed_at},
    ))


async def record_window_changes(db, previous: Table, stage: Table) -> None:
    """Сравнить «было» (previous) и «стало» (stage) и записать изменённые ключи.

    Исчезнувший ключ (слияние/сжатие сессии) и новый/изменённый ключ попадают
    в журнал; неизменившиеся пересчитанные строки — нет, поэтому ночной
    пересчёт хвоста не заливает журнал.
    """
    if db.bind.dialect.name == "postgresql":
        # Временные таблицы не анализируются автоматически: без статистики
        # планировщик плохо оценивает объединение двух окон по ключу.
        for table in (previous, stage):
            await db.execute(text(f"ANALYZE {table.name}"))
    same = and_(*(stage.c[c] == previous.c[c] for c in KEY_COLUMNS))
    gone = select(previous.c.visitor_id_hash, previous.c.started_at).where(
        ~exists(select(literal_column("1")).select_from(stage).where(same)).correlate(previous)
    )
    changed = select(stage.c.visitor_id_hash, stage.c.started_at).select_from(
        stage.outerjoin(previous, same)
    ).where(or_(
        previous.c.visitor_id_hash.is_(None),
        *(stage.c[c].is_distinct_from(previous.c[c]) for c in _COMPARED),
    ))
    await _upsert_keys(db, union(gone, changed).subquery("session_change_keys"))


async def mark_session_ids_changed(db, ids) -> None:
    """Отметить ключи строк server_sessions по id (точечные UPDATE: repair)."""
    ids = list(ids)
    if not ids or not enabled():
        return
    keys = select(ServerSession.visitor_id_hash, ServerSession.started_at).where(
        ServerSession.id.in_(ids)
    ).subquery("session_change_keys")
    await _upsert_keys(db, keys)


async def claim(db, limit: int) -> list[tuple[str, datetime, int]]:
    """Старейшие записи журнала. Без блокировок: обработка идемпотентна."""
    rows = (await db.execute(
        select(_LOG.c.visitor_id_hash, _LOG.c.started_at, _LOG.c.rev)
        .order_by(_LOG.c.changed_at, _LOG.c.visitor_id_hash, _LOG.c.started_at).limit(limit)
    )).all()
    return [(r.visitor_id_hash, r.started_at, r.rev) for r in rows]


async def ack(db, entries: list[tuple[str, datetime, int]]) -> None:
    """Удалить обработанные записи; изменившиеся после выборки (другой rev) остаются."""
    if not entries:
        return
    await db.execute(
        delete(_LOG).where(
            _LOG.c.visitor_id_hash == bindparam("b_visitor"),
            _LOG.c.started_at == bindparam("b_started"),
            _LOG.c.rev == bindparam("b_rev"),
        ),
        [{"b_visitor": v, "b_started": s, "b_rev": r} for v, s, r in entries],
    )
    await db.commit()


async def backlog(db) -> int:
    return int(await db.scalar(select(func.count()).select_from(_LOG)) or 0)
