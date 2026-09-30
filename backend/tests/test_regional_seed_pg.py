"""Regional startup reads/writes in an opted-in isolated PostgreSQL schema.

F01_TEST_DATABASE_URL is the existing test-only loopback fe_f01_* DSN. No
application database, real regional artifact, Redis or external source is used.
Each scenario creates and drops only its own random schema. SQL constraints,
COPY/upsert and transaction visibility are real; publication is an observed spy.
"""

from __future__ import annotations

import asyncio
import gzip
import importlib.util
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4
from urllib.parse import urlsplit

import pytest
from asyncpg.exceptions import UniqueViolationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from sqlalchemy.schema import CreateIndex, CreateSchema, CreateTable, DropSchema

from app.models import Region, RegionDataPoint, RegionIndicator, RegionMonthlyPoint
from app.services import emiss_regional_parser as emiss
from test_world_national_reconcile_pg import _validated_pg_url


@pytest.fixture
def isolated_pg_url():
    raw = os.environ.get("F01_TEST_DATABASE_URL")
    if not raw:
        pytest.skip("Set F01_TEST_DATABASE_URL to an isolated loopback fe_f01_* database")
    parts = urlsplit(raw)
    url = _validated_pg_url(raw)
    if url.port in {None, 5432} or parts.query or parts.fragment:
        pytest.fail("Regional test PostgreSQL requires explicit nondefault port and no query/fragment")
    return url


def _loader():
    path = Path(__file__).resolve().parents[1] / "seed_regional.py"
    spec = importlib.util.spec_from_file_location("regional_seed_pg_fixture", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@asynccontextmanager
async def _regional_database(url):
    schema = f"f03_test_{uuid4().hex}"
    engine = create_async_engine(
        url, poolclass=NullPool,
        connect_args={"server_settings": {"search_path": schema}},
    )
    created = False
    try:
        async with engine.begin() as conn:
            await conn.execute(CreateSchema(schema))
        created = True
        async with engine.begin() as conn:
            for model in (Region, RegionIndicator, RegionDataPoint, RegionMonthlyPoint):
                await conn.execute(CreateTable(model.__table__))
                for index in model.__table__.indexes:
                    await conn.execute(CreateIndex(index))
        yield async_sessionmaker(engine, expire_on_commit=False)
    finally:
        try:
            if created:
                async with engine.begin() as conn:
                    await conn.execute(DropSchema(schema, cascade=True))
        finally:
            await engine.dispose()


def _artifact(directory, *, annual, monthly=(), name="Fixture region"):
    directory.mkdir(exist_ok=True)
    regions = [{"slug": "fixture-region", "name": name, "kind": "region", "district": "fixture-district"}]
    indicators = [{
        "code": "fixture-fuel", "table_code": "14.1", "section_num": 14,
        "section_name": "Fixture", "name": "Fixture fuel", "unit": "руб./л",
        "source_sheet": "fixture official artifact", "year_min": 2024, "year_max": 2025,
    }]
    (directory / "regions.json").write_text(json.dumps(regions), encoding="utf-8")
    (directory / "indicators.json").write_text(json.dumps(indicators), encoding="utf-8")
    with gzip.open(directory / "data.csv.gz", "wt", encoding="utf-8") as stream:
        stream.write("code;region;year;value\n")
        stream.writelines(row + "\n" for row in annual)
    (directory / "fuel_points.csv").write_text(
        "code;region;period;value\n" + "".join(row + "\n" for row in monthly), encoding="utf-8",
    )


async def _snapshot(sessions):
    async with sessions() as db:
        regions = list((await db.execute(select(Region.id, Region.slug, Region.name).order_by(Region.id))).all())
        indicators = list((await db.execute(
            select(RegionIndicator.id, RegionIndicator.code, RegionIndicator.name, RegionIndicator.unit,
                   RegionIndicator.year_min, RegionIndicator.year_max).order_by(RegionIndicator.id)
        )).all())
        annual = list((await db.execute(
            select(RegionDataPoint.id, RegionDataPoint.year, RegionDataPoint.value).order_by(RegionDataPoint.year)
        )).all())
        monthly = list((await db.execute(
            select(RegionMonthlyPoint.id, RegionMonthlyPoint.month, RegionMonthlyPoint.value).order_by(RegionMonthlyPoint.month)
        )).all())
    return {"regions": regions, "indicators": indicators, "annual": annual, "monthly": monthly}


def _bind(monkeypatch, loader, sessions, directory):
    publications = []

    async def published(*namespaces):
        publications.append((namespaces, await _snapshot(sessions)))

    monkeypatch.setattr(loader, "async_session", sessions)
    monkeypatch.setattr(loader, "DATA_DIR", directory)
    monkeypatch.setattr(loader, "publish_committed_regional_changes", published, raising=False)
    return publications


def test_same_cardinality_annual_revision_refreshes_values(isolated_pg_url, tmp_path, monkeypatch):
    loader = _loader()

    async def scenario():
        async with _regional_database(isolated_pg_url) as sessions:
            publications = _bind(monkeypatch, loader, sessions, tmp_path / "artifact")
            _artifact(loader.DATA_DIR, annual=["fixture-fuel;fixture-region;2025;10"])
            await loader.seed_regional()
            before = await _snapshot(sessions)
            publications.clear()
            _artifact(loader.DATA_DIR, annual=["fixture-fuel;fixture-region;2025;20"])
            await loader.seed_regional()
            after = await _snapshot(sessions)
            assert [(year, float(value)) for _, year, value in after["annual"]] == [(2025, 20.0)]
            assert after["annual"][0][0] == before["annual"][0][0]
            assert len(publications) == 1
            assert publications[0][1] == after  # Independent reader sees committed content.

    asyncio.run(scenario())


def test_startup_preserves_extra_annual_history_and_live_monthly_conflicts(isolated_pg_url, tmp_path, monkeypatch):
    loader = _loader()

    async def scenario():
        async with _regional_database(isolated_pg_url) as sessions:
            _bind(monkeypatch, loader, sessions, tmp_path / "artifact")
            _artifact(loader.DATA_DIR, annual=["fixture-fuel;fixture-region;2025;10"],
                      monthly=["fixture-fuel;fixture-region;202607;70"])
            await loader.seed_regional()
            async with sessions() as db:
                region_id = await db.scalar(select(Region.id))
                indicator_id = await db.scalar(select(RegionIndicator.id))
                db.add(RegionDataPoint(indicator_id=indicator_id, region_id=region_id, year=1999, value=9))
                conflict = await db.scalar(select(RegionMonthlyPoint).where(RegionMonthlyPoint.month == 202607))
                conflict.value = 170  # Simulated later EMISS write; fixture never calls EMISS.
                db.add(RegionMonthlyPoint(indicator_id=indicator_id, region_id=region_id, month=202608, value=180))
                await db.commit()
            _artifact(loader.DATA_DIR, annual=["fixture-fuel;fixture-region;2025;20"],
                      monthly=["fixture-fuel;fixture-region;202607;71", "fixture-fuel;fixture-region;202609;90"])
            await loader.seed_regional()
            snapshot = await _snapshot(sessions)
            assert [(year, float(value)) for _, year, value in snapshot["annual"]] == [(1999, 9.0), (2025, 20.0)]
            assert [(month, float(value)) for _, month, value in snapshot["monthly"]] == [
                (202607, 170.0), (202608, 180.0), (202609, 90.0),
            ]
            assert snapshot["indicators"][0][-2:] == (1999, 2026)

    asyncio.run(scenario())


@pytest.mark.parametrize("failure", [
    "unknown-annual-ref", "invalid-annual-value", "invalid-month", "invalid-monthly-value",
    "duplicate-annual-key", "nonfinite-annual-value", "nonfinite-monthly-value",
])
def test_invalid_artifact_rolls_back_metadata_and_points(isolated_pg_url, tmp_path, monkeypatch, failure):
    loader = _loader()

    async def scenario():
        async with _regional_database(isolated_pg_url) as sessions:
            publications = _bind(monkeypatch, loader, sessions, tmp_path / "artifact")
            _artifact(loader.DATA_DIR, annual=["fixture-fuel;fixture-region;2025;10"],
                      monthly=["fixture-fuel;fixture-region;202607;70"])
            await loader.seed_regional()
            before = await _snapshot(sessions)
            publications.clear()
            annual = ["fixture-fuel;fixture-region;2025;20"]
            monthly = ["fixture-fuel;fixture-region;202607;71"]
            if failure == "unknown-annual-ref":
                annual.append("unknown-code;fixture-region;2026;30")
            elif failure == "invalid-annual-value":
                annual.append("fixture-fuel;fixture-region;2026;not-a-number")
            elif failure == "invalid-month":
                monthly.append("fixture-fuel;fixture-region;202613;80")
            elif failure == "invalid-monthly-value":
                monthly.append("fixture-fuel;fixture-region;202608;not-a-number")
            elif failure == "duplicate-annual-key":
                annual.append("fixture-fuel;fixture-region;2025;30")
            elif failure == "nonfinite-annual-value":
                annual.append("fixture-fuel;fixture-region;2026;NaN")
            else:
                monthly.append("fixture-fuel;fixture-region;202608;Infinity")
            _artifact(loader.DATA_DIR, annual=annual, monthly=monthly, name="Must roll back")
            with pytest.raises((ValueError, RuntimeError, UniqueViolationError)):
                await loader.seed_regional()
            assert await _snapshot(sessions) == before
            assert publications == []

    asyncio.run(scenario())


def test_missing_monthly_artifact_preserves_monthly_history(isolated_pg_url, tmp_path, monkeypatch):
    loader = _loader()

    async def scenario():
        async with _regional_database(isolated_pg_url) as sessions:
            publications = _bind(monkeypatch, loader, sessions, tmp_path / "artifact")
            _artifact(loader.DATA_DIR, annual=["fixture-fuel;fixture-region;2025;10"],
                      monthly=["fixture-fuel;fixture-region;202607;70"])
            await loader.seed_regional()
            before = await _snapshot(sessions)
            publications.clear()
            _artifact(loader.DATA_DIR, annual=["fixture-fuel;fixture-region;2025;20"])
            (loader.DATA_DIR / "fuel_points.csv").unlink()
            await loader.seed_regional()
            after = await _snapshot(sessions)
            assert after["monthly"] == before["monthly"]
            assert [(year, float(value)) for _, year, value in after["annual"]] == [(2025, 20.0)]
            assert after["indicators"][0][-2:] == (2025, 2026)
            assert len(publications) == 1 and publications[0][1] == after

    asyncio.run(scenario())


def test_commit_failure_rolls_back_written_metadata_and_both_point_layers(isolated_pg_url, tmp_path, monkeypatch):
    loader = _loader()

    async def scenario():
        async with _regional_database(isolated_pg_url) as sessions:
            publications = _bind(monkeypatch, loader, sessions, tmp_path / "artifact")
            _artifact(loader.DATA_DIR, annual=["fixture-fuel;fixture-region;2025;10"],
                      monthly=["fixture-fuel;fixture-region;202607;70"])
            await loader.seed_regional()
            before = await _snapshot(sessions)
            publications.clear()
            _artifact(loader.DATA_DIR, annual=["fixture-fuel;fixture-region;2025;20"],
                      monthly=["fixture-fuel;fixture-region;202608;80"], name="Must roll back")
            attempts = []

            @asynccontextmanager
            async def failing_sessions():
                async with sessions() as db:
                    async def fail_commit():
                        # All writes happened in the real PostgreSQL writer;
                        # an independent connection still sees only the old commit.
                        assert await db.scalar(select(Region.name)) == "Must roll back"
                        assert float(await db.scalar(select(RegionDataPoint.value))) == 20.0
                        assert float(await db.scalar(select(RegionMonthlyPoint.value).where(
                            RegionMonthlyPoint.month == 202608))) == 80.0
                        assert await _snapshot(sessions) == before
                        attempts.append("commit")
                        raise RuntimeError("injected before SQL commit")

                    monkeypatch.setattr(db, "commit", fail_commit)
                    yield db

            monkeypatch.setattr(loader, "async_session", failing_sessions)
            with pytest.raises(RuntimeError, match="injected before SQL commit"):
                await loader.seed_regional()
            assert attempts == ["commit"]
            assert await _snapshot(sessions) == before
            assert publications == []

    asyncio.run(scenario())


def test_concurrent_seed_and_emiss_keep_live_monthly_value_without_deadlock(isolated_pg_url, tmp_path, monkeypatch):
    """Real seed/EMISS writers overlap at the catalogue/monthly lock boundary."""
    loader = _loader()

    async def scenario():
        async with _regional_database(isolated_pg_url) as sessions:
            publications = _bind(monkeypatch, loader, sessions, tmp_path / "artifact")
            _artifact(loader.DATA_DIR, annual=["fixture-fuel;fixture-region;2025;10"],
                      monthly=["fixture-fuel;fixture-region;202607;70"])
            await loader.seed_regional()
            publications.clear()
            _artifact(loader.DATA_DIR, annual=["fixture-fuel;fixture-region;2025;20"],
                      monthly=["fixture-fuel;fixture-region;202701;90"], name="Revised metadata")
            path = loader.DATA_DIR / "indicators.json"
            indicators = json.loads(path.read_text(encoding="utf-8"))
            indicators[0]["name"] = "Revised indicator metadata"
            path.write_text(json.dumps(indicators), encoding="utf-8")

            staged, release_seed, emiss_ready = asyncio.Event(), asyncio.Event(), asyncio.Event()
            original_stage = loader._stage_points
            original_upsert = emiss._upsert_monthly_points
            original_lock = getattr(emiss, "acquire_regional_write_lock", None)

            async def pause_after_staging(db, table, *args):
                count = await original_stage(db, table, *args)
                if table == "regional_seed_monthly":
                    staged.set()  # Seed holds its real metadata row locks.
                    await release_seed.wait()
                return count

            async def signal_written(db, values):
                result = await original_upsert(db, values)
                emiss_ready.set()  # Old writer now holds the new monthly key.
                return result

            async def signal_lock_attempt(db):
                # Fixed writer signals before waiting for the shared SQL lock;
                # the seed can finish without a test-induced event deadlock.
                emiss_ready.set()
                assert original_lock is not None
                await original_lock(db)

            async def fetch(*args, **kwargs):
                return [("fixture-fuel", "fixture-region", 202701, 170)]

            async def live_update():
                async with sessions() as db:
                    return await emiss.run_emiss_regional_update(db, territory_ids=[], dimnames={})

            monkeypatch.setattr(loader, "_stage_points", pause_after_staging)
            monkeypatch.setattr(emiss, "_upsert_monthly_points", signal_written)
            monkeypatch.setattr(emiss, "acquire_regional_write_lock", signal_lock_attempt, raising=False)
            monkeypatch.setattr(emiss, "PRICE_FUELS", {"fixture": "fixture-fuel"})
            monkeypatch.setattr(emiss, "months_to_fetch", lambda existing: [(2027, 1)])
            monkeypatch.setattr(emiss, "fetch_month_points", fetch)
            monkeypatch.setattr(emiss, "_PAUSE_BETWEEN_REQUESTS", 0)
            monkeypatch.setattr(emiss, "publish_committed_regional_changes", loader.publish_committed_regional_changes)
            tasks = [asyncio.create_task(loader.seed_regional())]
            try:
                await asyncio.wait_for(staged.wait(), timeout=5)
                tasks.append(asyncio.create_task(live_update()))
                await asyncio.wait_for(emiss_ready.wait(), timeout=5)
                release_seed.set()
                _, stats = await asyncio.wait_for(asyncio.gather(*tasks), timeout=10)
                assert stats["added"] + stats["updated"] == 1
                snapshot = await _snapshot(sessions)
                assert [(year, float(value)) for _, year, value in snapshot["annual"]] == [(2025, 20.0)]
                assert [(month, float(value)) for _, month, value in snapshot["monthly"]] == [
                    (202607, 70.0), (202701, 170.0),
                ]
                assert snapshot["regions"][0][-1] == "Revised metadata"
                assert snapshot["indicators"][0][2] == "Revised indicator metadata"
                assert snapshot["indicators"][0][-2:] == (2025, 2027)
                assert len(publications) == 2
            finally:
                release_seed.set()
                for task in tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)

    asyncio.run(scenario())


def test_repeat_content_is_idempotent_without_replacing_rows(isolated_pg_url, tmp_path, monkeypatch):
    loader = _loader()

    async def scenario():
        async with _regional_database(isolated_pg_url) as sessions:
            publications = _bind(monkeypatch, loader, sessions, tmp_path / "artifact")
            _artifact(loader.DATA_DIR, annual=["fixture-fuel;fixture-region;2024;9", "fixture-fuel;fixture-region;2025;10"],
                      monthly=["fixture-fuel;fixture-region;202607;70"])
            await loader.seed_regional()
            before = await _snapshot(sessions)
            publications.clear()
            await loader.seed_regional()
            assert await _snapshot(sessions) == before
            assert publications == []

    asyncio.run(scenario())
