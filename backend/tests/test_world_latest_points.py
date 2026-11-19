"""Копия последних двух точек мировых рядов для каталога страны (19.11.2026, ADR-0037).

Главное — ответ каталога с копией тот же, что без неё: и после обхода, и после правок загрузчика, и когда части рядов
в копии нет. Плюс жизненный цикл копии (заведение, пауза, проход, повтор) и миграция.
"""

from __future__ import annotations

import asyncio
import importlib.util
import io
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

_SERIES = {
    "de-prc_hicp_midx-cp00-i15": [(date(2026, 4, 1), 120.0), (date(2026, 5, 1), 121.5)],
    "de-une_rt_m-t-pc-act": [(date(2026, 4, 1), 3.4), (date(2026, 5, 1), 3.5)],
    # нули в конце, ненулевая точка раньше — ряд в каталоге
    "de-nrg_bal_c-gwh-total": [(date(2020, 1, 1), 5.0), (date(2021, 1, 1), 0.0), (date(2022, 1, 1), 0.0)],
    # одни нули — ряда в каталоге нет
    "de-ext_lt_zero-total": [(date(2021, 1, 1), 0.0), (date(2022, 1, 1), 0.0)],
    # точек нет — ряда в каталоге нет
    "de-sts_empty-total": [],
    # одна точка
    "de-gov_10dd_edpt1-gd-pc-gdp": [(date(2025, 1, 1), 62.4)],
    # дробное значение с шестью знаками — копия хранит его так же, как таблица точек
    "de-ert_eur_q-rate": [(date(2025, 10, 1), 1.123456), (date(2026, 1, 1), 1.098765)],
}


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@pytest.fixture(autouse=True)
def _fresh_state_cache():
    from app.services import world_latest_points as wlp

    wlp.reset_cache()
    yield
    wlp.reset_cache()


@pytest.fixture
def seeded(auth_env):
    from app.models import WorldCountry, WorldDataPoint, WorldIndicator

    async def _seed():
        async with auth_env["session_maker"]() as db:
            de = WorldCountry(code="DE", slug="germany", name_ru="Германия", name_en="Germany",
                              region_ru="Европа", sort_order=1)
            fr = WorldCountry(code="FR", slug="france", name_ru="Франция", name_en="France",
                              region_ru="Европа", sort_order=2)
            db.add_all([de, fr])
            await db.flush()
            ids = {}
            for n, (code, points) in enumerate(_SERIES.items()):
                dataset = code.split("-", 1)[1].rsplit("-", 1)[0].replace("-", "_")
                ind = WorldIndicator(
                    country_id=de.id, code=code, dataset_id=dataset, slice_json={}, slice_hash=f"h{n}",
                    name_ru=f"Показатель экономики Германии номер {n + 1}", name_en=f"Germany indicator {n + 1}",
                    name_quality="curated", unit="PC", unit_ru="%", frequency="monthly",
                    category_ru="Цены", source="Евростат",
                    history_start=points[0][0] if points else None,
                    history_end=points[-1][0] if points else None,
                    points_count=len(points), is_listed=True,
                )
                db.add(ind)
                await db.flush()
                ids[code] = ind.id
                db.add_all([WorldDataPoint(indicator_id=ind.id, date=d, value=v) for d, v in points])
            fr_ind = WorldIndicator(
                country_id=fr.id, code="fr-une_rt_m-t-pc-act", dataset_id="une_rt_m", slice_json={},
                slice_hash="hf", name_ru="Безработица во Франции", name_en="Unemployment in France",
                name_quality="curated", unit="PC", unit_ru="%", frequency="monthly", category_ru="Труд",
                source="Евростат", history_start=date(2026, 5, 1), history_end=date(2026, 5, 1),
                points_count=1, is_listed=True,
            )
            db.add(fr_ind)
            await db.flush()
            ids[fr_ind.code] = fr_ind.id
            db.add(WorldDataPoint(indicator_id=fr_ind.id, date=date(2026, 5, 1), value=7.3))
            await db.commit()
            return {"ids": ids, "de": de.id, "fr": fr.id}

    return asyncio.run(_seed())


def _fill(auth_env, monkeypatch, *, chunk: int = 2) -> list[dict]:
    """Завести копию и пройти её целиком (пауза после заведения пропущена через force)."""
    from app.config import settings
    from app.services import world_latest_points as wlp

    monkeypatch.setattr(settings, "world_latest_points_chunk", chunk)
    reports = [asyncio.run(wlp.sweep(max_chunks=100, session_maker=auth_env["session_maker"]))]
    reports.append(asyncio.run(wlp.sweep(max_chunks=100, force=True, session_maker=auth_env["session_maker"])))
    return reports


def _catalog(auth_env) -> dict:
    import app.api.world as w

    async def _build():
        async with auth_env["session_maker"]() as db:
            return await w._build_country_detail_payload("germany", db, "test:key")

    return asyncio.run(_build())


def _old_path(auth_env, ids: list[int]):
    import app.api.world as w
    from app.services.world_subnational_queries import latest_world_point_series

    async def _run():
        async with auth_env["session_maker"]() as db:
            return (await latest_world_point_series(db, ids, limit=2),
                    await w._ids_with_nonzero_signal(db, ids))

    return asyncio.run(_run())


def _read(auth_env, country_id: int, ids: list[int]):
    from app.services.world_latest_points import read_latest_points

    async def _run():
        async with auth_env["session_maker"]() as db:
            return await read_latest_points(db, country_id, ids)

    return asyncio.run(_run())


def test_reader_off_without_flag_or_fill(auth_env, seeded, monkeypatch):
    from app.config import settings

    ids = list(seeded["ids"].values())
    assert settings.world_latest_points_enabled is False
    assert _read(auth_env, seeded["de"], ids) is None
    monkeypatch.setattr(settings, "world_latest_points_enabled", True)
    # Флаг включён, но копия не заполнена — прежний путь.
    assert _read(auth_env, seeded["de"], ids) is None


def test_full_pass_equals_points_table(auth_env, seeded, monkeypatch):
    from app.config import settings

    reports = _fill(auth_env, monkeypatch)
    assert reports[0]["status"] == "started"
    assert reports[1]["status"] == "pass_done" and reports[1]["rows"] == len(seeded["ids"])
    monkeypatch.setattr(settings, "world_latest_points_enabled", True)
    de_ids = [i for code, i in seeded["ids"].items() if code.startswith("de-")]
    copy = _read(auth_env, seeded["de"], de_ids)
    recent, nonzero = _old_path(auth_env, de_ids)
    assert copy.recent == recent
    assert copy.nonzero == nonzero
    assert copy.missing == []
    # Строки другой страны в ответ не попадают; ряд другой страны для этой страны — «нет в копии».
    fr_id = seeded["ids"]["fr-une_rt_m-t-pc-act"]
    assert _read(auth_env, seeded["de"], [fr_id]).missing == [fr_id]


def test_country_catalog_same_with_and_without_copy(auth_env, seeded, monkeypatch):
    import app.api.world as w
    from app.config import settings

    before = _catalog(auth_env)
    _fill(auth_env, monkeypatch)
    monkeypatch.setattr(settings, "world_latest_points_enabled", True)
    asked: list[list[int]] = []
    real = w.latest_world_point_series

    async def spy(db, ids, *, limit=2):
        if limit == 2:
            asked.append(sorted(ids))
        return await real(db, ids, limit=limit)

    monkeypatch.setattr(w, "latest_world_point_series", spy)
    after = _catalog(auth_env)
    assert after == before
    assert asked == []  # последние точки целиком из копии
    codes = {item["code"] for cat in after["categories"] for item in cat["indicators"]}
    assert "de-nrg_bal_c-gwh-total" in codes
    assert "de-ext_lt_zero-total" not in codes and "de-sts_empty-total" not in codes


def test_missing_rows_fall_back_to_points_table(auth_env, seeded, monkeypatch):
    import app.api.world as w
    from app.config import settings
    from app.models import WorldLatestPoint

    before = _catalog(auth_env)
    _fill(auth_env, monkeypatch)
    gone = seeded["ids"]["de-une_rt_m-t-pc-act"]

    async def _drop():
        async with auth_env["session_maker"]() as db:
            await db.execute(sa.delete(WorldLatestPoint).where(WorldLatestPoint.indicator_id == gone))
            await db.commit()

    asyncio.run(_drop())
    monkeypatch.setattr(settings, "world_latest_points_enabled", True)
    asked: list[list[int]] = []
    real = w.latest_world_point_series

    async def spy(db, ids, *, limit=2):
        if limit == 2:
            asked.append(sorted(ids))
        return await real(db, ids, limit=limit)

    monkeypatch.setattr(w, "latest_world_point_series", spy)
    assert _catalog(auth_env) == before
    assert asked == [[gone]]


def test_loader_sync_keeps_copy_equal(auth_env, seeded, monkeypatch):
    """Загрузчик пишет новую точку, правит значение и удаляет точки — копия меняется в той же транзакции."""
    from app.config import settings
    from app.models import WorldDataPoint
    from app.services.world_latest_points import sync_latest_points

    _fill(auth_env, monkeypatch)
    une = seeded["ids"]["de-une_rt_m-t-pc-act"]
    zero = seeded["ids"]["de-ext_lt_zero-total"]
    empty = seeded["ids"]["de-sts_empty-total"]

    async def _load():
        async with auth_env["session_maker"]() as db:
            db.add(WorldDataPoint(indicator_id=une, date=date(2026, 6, 1), value=3.6))
            db.add(WorldDataPoint(indicator_id=zero, date=date(2023, 1, 1), value=2.0))
            db.add(WorldDataPoint(indicator_id=empty, date=date(2026, 1, 1), value=1.0))
            await sync_latest_points(db, [une, zero, empty])
            await db.commit()

    asyncio.run(_load())
    monkeypatch.setattr(settings, "world_latest_points_enabled", True)
    de_ids = [i for code, i in seeded["ids"].items() if code.startswith("de-")]
    copy = _read(auth_env, seeded["de"], de_ids)
    recent, nonzero = _old_path(auth_env, de_ids)
    assert copy.recent == recent and copy.nonzero == nonzero
    assert copy.recent[une][0] == (date(2026, 6, 1), 3.6)
    assert zero in copy.nonzero and empty in copy.nonzero

    async def _rollback_load():
        async with auth_env["session_maker"]() as db:
            await db.execute(sa.delete(WorldDataPoint).where(WorldDataPoint.indicator_id == une))
            await sync_latest_points(db, [une])
            await db.rollback()

    # Откат загрузки откатывает и строку копии.
    asyncio.run(_rollback_load())
    assert _read(auth_env, seeded["de"], [une]).recent[une][0] == (date(2026, 6, 1), 3.6)

    monkeypatch.setattr(settings, "world_latest_points_enabled", False)
    off = _catalog(auth_env)
    monkeypatch.setattr(settings, "world_latest_points_enabled", True)
    assert _catalog(auth_env) == off


def test_sync_is_noop_until_copy_started(auth_env, seeded):
    from app.models import WorldLatestPoint
    from app.services.world_latest_points import sync_latest_points

    async def _run():
        async with auth_env["session_maker"]() as db:
            await sync_latest_points(db, list(seeded["ids"].values()))
            await db.commit()
            return (await db.execute(sa.select(sa.func.count()).select_from(WorldLatestPoint))).scalar()

    assert asyncio.run(_run()) == 0


def test_sync_failure_drops_rows_and_keeps_load(auth_env, seeded, monkeypatch):
    from app.models import WorldLatestPoint
    from app.services import world_latest_points as wlp

    _fill(auth_env, monkeypatch)
    une = seeded["ids"]["de-une_rt_m-t-pc-act"]

    async def broken(db, pairs):
        raise RuntimeError("boom")

    monkeypatch.setattr(wlp, "_computed_rows", broken)

    async def _run():
        async with auth_env["session_maker"]() as db:
            await wlp.sync_latest_points(db, [une])
            await db.commit()
            return (await db.execute(sa.select(WorldLatestPoint.indicator_id).where(
                WorldLatestPoint.indicator_id == une))).scalar()

    assert asyncio.run(_run()) is None


def test_sweep_repairs_drift_removes_orphans_and_skips_unchanged(auth_env, seeded, monkeypatch):
    from app.models import WorldDataPoint, WorldIndicator, WorldLatestPoint
    from app.services import world_latest_points as wlp

    _fill(auth_env, monkeypatch)
    une = seeded["ids"]["de-une_rt_m-t-pc-act"]
    gdp = seeded["ids"]["de-gov_10dd_edpt1-gd-pc-gdp"]

    async def _drift():
        async with auth_env["session_maker"]() as db:
            # Мимо загрузчика: ручная правка значения и удаление ряда.
            await db.execute(sa.update(WorldDataPoint).where(WorldDataPoint.indicator_id == une,
                                                             WorldDataPoint.date == date(2026, 5, 1))
                             .values(value=9.9))
            await db.execute(sa.delete(WorldDataPoint).where(WorldDataPoint.indicator_id == gdp))
            await db.execute(sa.delete(WorldIndicator).where(WorldIndicator.id == gdp))
            await db.commit()

    asyncio.run(_drift())
    report = asyncio.run(wlp.sweep(max_chunks=100, force=True, session_maker=auth_env["session_maker"]))
    assert report["status"] == "pass_done"
    assert report["changed"] == 1  # только исправленная строка

    async def _rows():
        async with auth_env["session_maker"]() as db:
            return {r.indicator_id: r for r in (await db.execute(sa.select(WorldLatestPoint))).scalars().all()}

    rows = asyncio.run(_rows())
    assert gdp not in rows
    assert float(rows[une].last_value) == 9.9
    again = asyncio.run(wlp.sweep(max_chunks=100, force=True, session_maker=auth_env["session_maker"]))
    assert again["status"] == "pass_done" and again["changed"] == 0


def test_pass_lifecycle_waits_then_rests(auth_env, seeded, monkeypatch):
    from app.models import WorldLatestPointsState
    from app.services import world_latest_points as wlp

    sm = auth_env["session_maker"]
    assert asyncio.run(wlp.sweep(max_chunks=1, session_maker=sm))["status"] == "started"
    # Сразу после заведения обход ждёт, пока все загрузчики увидят копию.
    assert asyncio.run(wlp.sweep(max_chunks=1, session_maker=sm))["status"] == "waiting"

    async def _age(**fields):
        async with sm() as db:
            state = await db.get(WorldLatestPointsState, wlp.STATE_ID)
            for key, value in fields.items():
                setattr(state, key, value)
            await db.commit()

    asyncio.run(_age(maintained_since=_now() - timedelta(hours=1)))
    monkeypatch.setattr(wlp.settings, "world_latest_points_chunk", 1)
    first = asyncio.run(wlp.sweep(max_chunks=2, session_maker=sm))
    assert first["status"] == "pass" and first["chunks"] == 2
    # Пока проход не закончен, копия не используется.
    monkeypatch.setattr(wlp.settings, "world_latest_points_enabled", True)
    assert _read(auth_env, seeded["de"], list(seeded["ids"].values())) is None
    done = asyncio.run(wlp.sweep(max_chunks=100, session_maker=sm))
    assert done["status"] == "pass_done"
    assert _read(auth_env, seeded["de"], list(seeded["ids"].values())) is not None
    assert asyncio.run(wlp.sweep(max_chunks=100, session_maker=sm))["status"] == "fresh"
    asyncio.run(_age(pass_completed_at=_now() - timedelta(days=8)))
    assert asyncio.run(wlp.sweep(max_chunks=100, session_maker=sm))["status"] == "pass_done"


def test_job_is_noop_without_flag(auth_env, seeded, monkeypatch):
    from app.services import world_latest_points as wlp

    called = []

    async def fake_sweep(**kwargs):
        called.append(kwargs)
        return {"status": "fresh"}

    monkeypatch.setattr(wlp, "sweep", fake_sweep)
    asyncio.run(wlp.world_latest_points_job())
    assert called == []
    monkeypatch.setattr(wlp.settings, "world_latest_points_enabled", True)
    asyncio.run(wlp.world_latest_points_job())
    assert len(called) == 1


# --- Миграция -----------------------------------------------------------------------------------------------------

_MIGRATION = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "20261119_world_latest_points.py"


def _migration():
    spec = importlib.util.spec_from_file_location("m20261119_world_latest_points", _MIGRATION)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_migration_chain_and_postgres_sql():
    mod = _migration()
    assert mod.revision == "20261119_world_latest_points" and len(mod.revision) <= 32
    assert mod.down_revision == "20261119_points_autovacuum"
    buf = io.StringIO()
    ctx = MigrationContext.configure(dialect_name="postgresql", opts={"as_sql": True, "output_buffer": buf})
    with Operations.context(ctx):
        mod.upgrade()
    sql = buf.getvalue()
    assert "CREATE TABLE world_latest_points (" in sql and "CREATE TABLE world_latest_points_state (" in sql
    assert "ALTER TABLE world_latest_points SET (fillfactor = 80" in sql
    assert "INCLUDE (indicator_id, last_date, last_value, prev_date, prev_value, has_nonzero)" in sql
    # Только добавляет: основные таблицы не меняются.
    upper = sql.upper()
    assert upper.count("ALTER TABLE") == 1 and "WORLD_DATA_POINTS" not in upper and "TRIGGER" not in upper


def test_migration_sqlite_roundtrip():
    mod = _migration()
    engine = sa.create_engine("sqlite://")
    with engine.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            mod.upgrade()
        names = set(sa.inspect(conn).get_table_names())
        assert {"world_latest_points", "world_latest_points_state"} <= names
        with Operations.context(MigrationContext.configure(conn)):
            mod.downgrade()
        assert not ({"world_latest_points", "world_latest_points_state"} & set(sa.inspect(conn).get_table_names()))
