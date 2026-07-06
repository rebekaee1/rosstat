#!/usr/bin/env python3
"""Верификация П-2 (риск Р-1): инкрементальный derived-пересчёт эквивалентен полному.

Прогоняет ДВА сценария в транзакциях с ROLLBACK (БД не меняется):

  A. Полный rebuild: `_execute()` по всем DERIVED_SPECS в порядке реестра
     (как scripts/rebuild-all-derived.py) → снапшот всех derived-рядов.
  B. Инкрементальный: `run_for_updated_sources(все source-коды)` — замыкание
     зависимости в топологическом порядке → снапшот всех derived-рядов.

Затем байт-в-байт сверка снапшотов A и B. Расхождение = баг топологического
порядка (зависимый посчитался от stale-входа) → НЕ мерджить.

Запуск с хоста (порт из docker-compose):
    RUSTATS_DATABASE_URL=postgresql+asyncpg://rustats:rustats_dev@127.0.0.1:5434/rustats \
    PYTHONPATH=backend backend/.venv/bin/python scripts/verify-derived-incremental.py
или в контейнере:
    docker compose exec backend python /app/scripts/verify-derived-incremental.py
"""
from __future__ import annotations

import asyncio
import hashlib
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
for _candidate in (_HERE.parent / "backend", Path("/app")):
    if (_candidate / "app" / "database.py").exists():
        if str(_candidate) not in sys.path:
            sys.path.insert(0, str(_candidate))
        break

from sqlalchemy import select  # noqa: E402

from app.database import async_session  # noqa: E402
from app.models import Indicator, IndicatorData  # noqa: E402
from app.services.calculation_engine import (  # noqa: E402
    DERIVED_SPECS,
    _execute,
    calculation_engine,
)


async def _snapshot_derived(db) -> dict[str, str]:
    """code → sha256 канонизированного ряда (date:value построчно)."""
    codes = [s.dst_code for s in DERIVED_SPECS]
    out: dict[str, str] = {}
    for code in codes:
        ind_id = (await db.execute(
            select(Indicator.id).where(Indicator.code == code)
        )).scalar_one_or_none()
        if ind_id is None:
            out[code] = "<no-indicator>"
            continue
        rows = (await db.execute(
            select(IndicatorData.date, IndicatorData.value)
            .where(IndicatorData.indicator_id == ind_id)
            .order_by(IndicatorData.date)
        )).all()
        payload = "\n".join(f"{d.isoformat()}:{v}" for d, v in rows)
        out[code] = hashlib.sha256(payload.encode()).hexdigest()
    return out


async def _scenario_full() -> dict[str, str]:
    async with async_session() as db:
        for spec in DERIVED_SPECS:
            await _execute(db, spec)
        await db.flush()
        snap = await _snapshot_derived(db)
        await db.rollback()
        return snap


async def _scenario_incremental() -> dict[str, str]:
    all_sources = sorted({c for spec in DERIVED_SPECS for c in spec.src_codes})
    # cache_invalidate внутри run_for_updated_sources безвреден (кэш и так
    # переживёт), Redis может быть недоступен с хоста — глушим ошибки movement
    # через сам engine (он ловит исключения per-code, но invalidate вне try) —
    # поэтому подменяем на no-op на время прогона.
    import app.services.calculation_engine as ce

    orig = ce.cache_invalidate_indicator

    async def _noop(_code):
        return None

    ce.cache_invalidate_indicator = _noop
    try:
        async with async_session() as db:
            await calculation_engine.run_for_updated_sources(db, all_sources)
            await db.flush()
            snap = await _snapshot_derived(db)
            await db.rollback()
            return snap
    finally:
        ce.cache_invalidate_indicator = orig


async def main() -> int:
    print(f"Specs in registry: {len(DERIVED_SPECS)}")
    order = calculation_engine.dependents_closure_topo(
        sorted({c for spec in DERIVED_SPECS for c in spec.src_codes})
    )
    print(f"Incremental closure covers: {len(order)} derived (must equal registry)")
    if set(order) != {s.dst_code for s in DERIVED_SPECS}:
        print("FAIL: closure != registry")
        return 1

    print("Scenario A: full rebuild (registry order), rollback...")
    snap_full = await _scenario_full()
    print("Scenario B: incremental closure (topo order), rollback...")
    snap_incr = await _scenario_incremental()

    diff = {
        code for code in snap_full
        if snap_full[code] != snap_incr.get(code)
    }
    if diff:
        print(f"FAIL: {len(diff)} derived differ between full and incremental:")
        for code in sorted(diff):
            print(f"  {code}: full={snap_full[code][:12]} incr={snap_incr.get(code, '?')[:12]}")
        return 1
    print(f"OK: all {len(snap_full)} derived series identical byte-for-byte.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
