"""Tests for the upsert helper — verify generated SQL and ADR-0002 data-preservation
boundary: empty/None payload from a parser must NEVER wipe existing DB content."""

import asyncio
from datetime import date
from unittest.mock import AsyncMock, MagicMock

from app.services.upsert import (
    _dedup_points,
    batch_upsert_stmt,
    bulk_upsert,
    upsert_indicator_data,
)


def test_upsert_generates_insert():
    stmt = upsert_indicator_data(1, date(2024, 1, 1), 100.5)
    compiled = stmt.compile()
    sql = str(compiled)
    assert "INSERT INTO indicator_data" in sql
    assert "ON CONFLICT" in sql


def _mock_session(initial_count: int = 0) -> AsyncMock:
    """Build a minimal mock AsyncSession that:
      - returns `initial_count` for the count() query (and same value at the end),
      - records every execute() call so the test can inspect what SQL ran.
    """
    session = MagicMock()
    count_result = MagicMock()
    count_result.scalar.return_value = initial_count
    upsert_result = MagicMock()
    upsert_result.fetchone.return_value = None  # treat all upserts as no-op rows
    execute_calls: list = []

    async def execute(stmt):
        execute_calls.append(stmt)
        s = str(stmt)
        if "count" in s.lower():
            return count_result
        return upsert_result

    session.execute = execute
    session.flush = AsyncMock()
    session._execute_calls = execute_calls
    return session


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro) if False else asyncio.run(coro)


def test_bulk_upsert_empty_list_is_noop():
    """Парсер вернул пустой список — никаких UPSERT в БД не уходит (ADR-0002)."""
    session = _mock_session(initial_count=5)
    added, updated = _run(bulk_upsert(session, indicator_id=1, points=[]))

    assert added == 0
    assert updated == 0
    # Только два count() в начале и в конце, ни одного UPSERT
    upsert_calls = [c for c in session._execute_calls if "INSERT" in str(c)]
    assert upsert_calls == []


def test_bulk_upsert_none_value_is_skipped():
    """ADR-0002: None из парсера НЕ должен приводить к UPSERT — точка пропускается."""
    session = _mock_session(initial_count=1)
    added, updated = _run(bulk_upsert(
        session, indicator_id=1,
        points=[(date(2024, 1, 1), None)],
    ))

    upsert_calls = [c for c in session._execute_calls if "INSERT INTO indicator_data" in str(c)]
    assert upsert_calls == [], "None value must NOT produce an UPSERT statement"
    assert added == 0


def test_bulk_upsert_valid_values_produce_upserts():
    """Нормальные значения порождают UPSERT (контроль, что guard не лишний)."""
    session = _mock_session(initial_count=0)
    _run(bulk_upsert(
        session, indicator_id=1,
        points=[(date(2024, 1, 1), 1.0), (date(2024, 2, 1), 2.0)],
    ))

    upsert_calls = [c for c in session._execute_calls if "INSERT INTO indicator_data" in str(c)]
    assert len(upsert_calls) == 2


def test_bulk_upsert_mixed_none_and_value():
    """Среди валидных точек один None — пропускается, остальные применяются."""
    session = _mock_session(initial_count=1)
    _run(bulk_upsert(
        session, indicator_id=1,
        points=[
            (date(2024, 1, 1), None),
            (date(2024, 2, 1), 2.0),
            (date(2024, 3, 1), 3.0),
        ],
    ))

    upsert_calls = [c for c in session._execute_calls if "INSERT INTO indicator_data" in str(c)]
    assert len(upsert_calls) == 2  # only the two non-None points


# --- П-1: batch upsert (Postgres path) ---------------------------------------

def test_batch_stmt_preserves_adr_0002_guard():
    """Батч-стейтмент обязан сохранить WHERE value <> excluded.value и вернуть
    маркер вставки (xmax = 0) — от него зависят счётчики added/updated (Р-2)."""
    from sqlalchemy.dialects import postgresql

    stmt = batch_upsert_stmt(1, [
        (date(2024, 1, 1), 1.0),
        (date(2024, 2, 1), 2.0),
    ])
    sql = str(stmt.compile(dialect=postgresql.dialect()))
    assert "ON CONFLICT" in sql
    assert "uq_indicator_date" in sql
    assert "value != excluded.value" in sql.replace("indicator_data.value", "value")
    assert "xmax = 0" in sql
    assert "RETURNING" in sql


def test_dedup_points_last_wins_and_drops_none():
    """Дубли дат в одном батче схлопываются (ON CONFLICT не может тронуть
    строку дважды в одном statement), None отфильтрован (ADR-0002)."""
    out = _dedup_points([
        (date(2024, 1, 1), 1.0),
        (date(2024, 1, 1), 9.0),   # дубль даты — берётся последнее значение
        (date(2024, 2, 1), None),  # None — пропуск
        (date(2024, 3, 1), 3.0),
    ])
    assert out == {date(2024, 1, 1): 9.0, date(2024, 3, 1): 3.0}


def test_bulk_upsert_pg_path_counts_from_returning():
    """PG-путь: added/updated считаются из RETURNING (xmax=0), count-запросов нет."""
    session = MagicMock()
    session.bind.dialect.name = "postgresql"
    execute_calls: list = []

    batch_result = MagicMock()
    # 2 вставки + 1 обновление; необновлённые строки в RETURNING не попадают
    batch_result.fetchall.return_value = [(True,), (True,), (False,)]

    async def execute(stmt):
        execute_calls.append(stmt)
        return batch_result

    session.execute = execute
    session.flush = AsyncMock()

    added, updated = _run(bulk_upsert(
        session, indicator_id=1,
        points=[
            (date(2024, 1, 1), 1.0),
            (date(2024, 2, 1), 2.0),
            (date(2024, 3, 1), 3.0),
            (date(2024, 4, 1), 4.0),  # без изменения — не в RETURNING
        ],
    ))
    assert added == 2
    assert updated == 1
    assert len(execute_calls) == 1, "4 точки должны уйти одним statement"
    assert "INSERT INTO indicator_data" in str(execute_calls[0])
