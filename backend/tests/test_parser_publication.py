"""Commit/publication regressions through real parser, SQL and API-reader seams.

SQLite uses a temporary file and separate sessions: an independent reader sees
only committed facts. Redis is fakeredis; no local stack or external service is
used. Forecast/network work is disabled by the fixture indicator configuration.
"""

import asyncio
from contextlib import asynccontextmanager
from datetime import date
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import fakeredis.aioredis
import pytest
from sqlalchemy import select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.indicators import get_indicator_data
from app.core import cache
from app.models import Base, FetchLog, Indicator, IndicatorData
from app.services import base_parser as bp
from app.services import upsert
from app.services import calculation_engine as ce
from app.tasks import scheduler


POINT_DATE = date(2026, 1, 1)


class RevisionParser(bp.BaseParser):
    parser_type = "publication_fixture"

    async def _fetch_and_parse(self, db, indicator, cfg, fetch_log):
        return [(POINT_DATE, 2.0)], "https://fixture.invalid/no-network"


@asynccontextmanager
async def publication_env(tmp_path, monkeypatch):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'publication.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(
            lambda sync: Base.metadata.create_all(
                sync, tables=[Indicator.__table__, IndicatorData.__table__, FetchLog.__table__],
            ),
        )
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(cache, "_redis", redis)
    monkeypatch.setattr(cache, "_ver_local", {})
    # PostgreSQL's named ON CONFLICT constraint is not SQLite syntax. Keep the
    # real bulk_upsert/counting path, adapting only that SQL dialect spelling.
    def sqlite_upsert(indicator_id, dt, val):
        statement = sqlite_insert(IndicatorData).values(indicator_id=indicator_id, date=dt, value=val)
        return statement.on_conflict_do_update(
            index_elements=["indicator_id", "date"],
            set_={"value": statement.excluded.value},
            where=IndicatorData.value != statement.excluded.value,
        ).returning(IndicatorData.id)

    monkeypatch.setattr(upsert, "upsert_indicator_data", sqlite_upsert)
    async with sessions() as db:
        indicator = Indicator(code="publication-source", name="Fixture", parser_type="publication_fixture", is_active=True, model_config_json={"forecast_steps": 0})
        db.add(indicator)
        await db.flush()
        db.add(IndicatorData(indicator_id=indicator.id, date=POINT_DATE, value=1.0))
        await db.commit()
    try:
        yield sessions, redis
    finally:
        await redis.aclose()
        await engine.dispose()


async def committed_value(sessions):
    async with sessions() as reader:
        return float(await reader.scalar(select(IndicatorData.value)))


async def api_value(sessions):
    async with sessions() as reader:
        response = await get_indicator_data(
            "publication-source", from_date=None, to_date=None, limit=100, db=reader,
        )
        payload = response if isinstance(response, dict) else response.model_dump()
        return payload["data"][0]["value"]


async def parser_inputs(writer):
    indicator = await writer.scalar(select(Indicator))
    fetch_log = FetchLog(indicator_id=indicator.id, status="running")
    writer.add(fetch_log)
    await writer.commit()
    return indicator, fetch_log


def test_parser_publishes_only_committed_facts_to_api_cache(tmp_path, monkeypatch):
    async def scenario():
        async with publication_env(tmp_path, monkeypatch) as (sessions, redis):
            assert await api_value(sessions) == 1.0  # Warm the old namespace.
            observed = []
            invalidate = cache.cache_invalidate_indicator

            async def publish_and_read(code):
                await invalidate(code)
                # The API reader is scheduled exactly after the generation bump.
                observed.append((await committed_value(sessions), await api_value(sessions)))

            monkeypatch.setattr(bp, "cache_invalidate_indicator", publish_and_read)

            class VisibilityParser(RevisionParser):
                async def _after_storage(self, db, indicator, cfg, fetch_log, *counts):
                    assert float(await db.scalar(select(IndicatorData.value))) == 2.0
                    assert await committed_value(sessions) == 1.0

            async with sessions() as writer:
                indicator, fetch_log = await parser_inputs(writer)
                await VisibilityParser().run(writer, indicator, fetch_log)
                assert fetch_log.status == "success"
                assert fetch_log.records_added == 0 and fetch_log.records_updated == 1

            assert await committed_value(sessions) == 2.0
            assert observed == [(2.0, 2.0)], "new cache generation must not contain old committed facts"
            assert await api_value(sessions) == 2.0
            assert await redis.get("fe:ver:publication-source") == "1"

    asyncio.run(scenario())


def test_source_commit_failure_never_publishes_rolled_back_value(tmp_path, monkeypatch):
    async def scenario():
        async with publication_env(tmp_path, monkeypatch) as (sessions, redis):
            async with sessions() as writer:
                indicator, fetch_log = await parser_inputs(writer)
                commit = writer.commit
                fail_next = True

                async def failed_source_commit():
                    nonlocal fail_next
                    if fail_next:
                        fail_next = False
                        raise RuntimeError("fixture source commit failed")
                    await commit()

                monkeypatch.setattr(writer, "commit", failed_source_commit)
                await RevisionParser().run(writer, indicator, fetch_log)
                assert fetch_log.status == "failed"
            assert await committed_value(sessions) == 1.0
            assert await redis.get("fe:ver:publication-source") is None
            async with sessions() as reader:
                assert await reader.scalar(select(FetchLog.status)) == "failed"

    asyncio.run(scenario())


@pytest.mark.parametrize("fallback", [False, True])
def test_cache_failure_preserves_commit_and_scheduler_changed(tmp_path, monkeypatch, fallback):
    async def scenario():
        async with publication_env(tmp_path, monkeypatch) as (sessions, _redis):
            class CacheFailureParser(RevisionParser):
                async def _fetch_and_parse(self, db, indicator, cfg, fetch_log):
                    if fallback:
                        bp.mark_fallback_used(fetch_log, "fixture fallback")
                    return await super()._fetch_and_parse(db, indicator, cfg, fetch_log)

            async def broken_cache(code):
                raise RuntimeError("fixture cache unavailable")

            monkeypatch.setattr(bp, "cache_invalidate_indicator", broken_cache)
            monkeypatch.setattr(scheduler, "async_session", sessions)
            monkeypatch.setattr(scheduler, "get_parser", lambda _: CacheFailureParser())
            changed, status = await scheduler.run_etl_for_indicator_status("publication-source")
            assert changed is True
            assert status == ("fallback_used" if fallback else "success")
            assert await committed_value(sessions) == 2.0
            async with sessions() as reader:
                log = await reader.scalar(select(FetchLog))
                assert log.records_updated == 1
                assert "cache" not in (log.error_message or "")

    asyncio.run(scenario())


async def derived_fixture(sessions):
    """Two actual dependent SQL writes; each observes its parent's fresh value."""
    async with sessions() as db:
        for code in ("fixture-derived", "fixture-cascade", "fixture-unchanged"):
            indicator = Indicator(code=code, name=code, parser_type="derived", is_active=True, model_config_json={"forecast_steps": 0})
            db.add(indicator)
            await db.flush()
            db.add(IndicatorData(indicator_id=indicator.id, date=POINT_DATE, value=1.0))
        await db.commit()
    engine = ce.CalculationEngine()

    def operation(source, target):
        async def write(db):
            source_value = await db.scalar(select(IndicatorData.value).join(Indicator).where(Indicator.code == source))
            target_id = await db.scalar(select(Indicator.id).where(Indicator.code == target))
            result = await db.execute(update(IndicatorData).where(IndicatorData.indicator_id == target_id).values(value=source_value * 2))
            return result.rowcount
        return write

    engine.register("fixture-derived", ["publication-source"], operation("publication-source", "fixture-derived"))
    engine.register("fixture-cascade", ["fixture-derived"], operation("fixture-derived", "fixture-cascade"))

    async def unchanged(_db):
        return 0

    engine.register("fixture-unchanged", ["publication-source"], unchanged)
    return engine


def test_standalone_engine_leaves_publication_to_commit_owner(tmp_path, monkeypatch):
    async def scenario():
        async with publication_env(tmp_path, monkeypatch) as (sessions, redis):
            engine = await derived_fixture(sessions)
            async with sessions() as writer:
                codes = await engine.run_for_updated_sources(writer, ["publication-source"])
                assert codes == ["fixture-derived", "fixture-cascade"]
                assert not await redis.keys("fe:ver:*")
                await writer.rollback()  # A preview caller owns rollback.
            async with sessions() as reader:
                rows = (await reader.scalars(select(IndicatorData.value))).all()
                assert rows == [1.0] * 4
            assert not await redis.keys("fe:ver:*")

    asyncio.run(scenario())


@pytest.mark.parametrize("hook_kind", ["minfin", "industrial"])
@pytest.mark.parametrize("commit_fails", [False, True])
def test_parser_derived_cascade_is_atomic_then_published(tmp_path, monkeypatch, hook_kind, commit_fails):
    async def scenario():
        from app.services import minfin_budget_parser, rosstat_ind_parser

        async with publication_env(tmp_path, monkeypatch) as (sessions, redis):
            engine = await derived_fixture(sessions)
            module = minfin_budget_parser if hook_kind == "minfin" else rosstat_ind_parser
            hook = (minfin_budget_parser.MinfinBudgetParser if hook_kind == "minfin" else rosstat_ind_parser.RosstatIndParser)._after_storage
            monkeypatch.setattr(module, "calculation_engine", engine)
            observed = []
            bump = cache.bump_namespaces

            async def bump_and_read(*namespaces):
                async with sessions() as reader:
                    values = (await reader.scalars(select(IndicatorData.value).join(Indicator).order_by(Indicator.id))).all()
                observed.append((namespaces[0], values))
                await bump(*namespaces)

            monkeypatch.setattr(cache, "bump_namespaces", bump_and_read)

            class HookParser(RevisionParser):
                _after_storage = hook

            async with sessions() as writer:
                indicator, fetch_log = await parser_inputs(writer)
                indicator.model_config_json = {"forecast_steps": 0, "quarterly_flow": True}
                if commit_fails:
                    commit = writer.commit
                    fail_next = True

                    async def failed_commit():
                        nonlocal fail_next
                        if fail_next:
                            fail_next = False
                            raise RuntimeError("fixture cascade commit failed")
                        await commit()

                    monkeypatch.setattr(writer, "commit", failed_commit)
                await HookParser().run(writer, indicator, fetch_log)
                assert fetch_log.status == ("failed" if commit_fails else "success")
            if commit_fails:
                assert not observed
                async with sessions() as reader:
                    assert (await reader.scalars(select(IndicatorData.value))).all() == [1.0] * 4
                return
            assert {code for code, _ in observed} == {"publication-source", "fixture-derived", "fixture-cascade"}
            assert all(values == [2.0, 4.0, 8.0, 1.0] for _, values in observed)
            assert await redis.get("fe:ver:fixture-unchanged") is None

    asyncio.run(scenario())


def test_seed_forecast_preparation_publishes_derived_after_commit(tmp_path, monkeypatch):
    async def scenario():
        import seed_data

        async with publication_env(tmp_path, monkeypatch) as (sessions, _redis):
            engine = await derived_fixture(sessions)
            observed = []
            bump = cache.bump_namespaces

            async def bump_and_read(*namespaces):
                async with sessions() as reader:
                    values = (await reader.scalars(select(IndicatorData.value).join(Indicator).order_by(Indicator.id))).all()
                observed.append((namespaces[0], values))
                await bump(*namespaces)

            async def disabled_forecast(*args, **kwargs):
                return None

            monkeypatch.setattr(ce, "calculation_engine", engine)
            monkeypatch.setattr(ce, "DERIVED_SPECS", [SimpleNamespace(src_codes=["publication-source"])])
            monkeypatch.setattr(seed_data, "async_session", sessions)
            monkeypatch.setattr(seed_data, "retrain_indicator_forecast", disabled_forecast)
            monkeypatch.setattr(cache, "bump_namespaces", bump_and_read)
            await seed_data.generate_forecasts()
            assert {code for code, _ in observed} == {"fixture-derived", "fixture-cascade"}
            assert all(values == [1.0, 2.0, 4.0, 1.0] for _, values in observed)

    asyncio.run(scenario())


def repair_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "repair_ppi_housing_2026.py"
    spec = importlib.util.spec_from_file_location("fixture_repair_publication", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("apply", [False, True])
def test_repair_caller_preview_or_committed_facts_before_later_failure(tmp_path, monkeypatch, apply):
    async def scenario():
        repair = repair_module()
        async with publication_env(tmp_path, monkeypatch) as (sessions, redis):
            engine = await derived_fixture(sessions)

            async def local_plan(*args):
                return {"publication-source": [(POINT_DATE, 2.0)]}

            async def later_failure(*args):
                raise RuntimeError("fixture later forecast stage failed")

            monkeypatch.setattr(repair, "async_session", sessions)
            monkeypatch.setattr(repair, "calculation_engine", engine)
            monkeypatch.setattr(repair, "SOURCE_CODES", ["publication-source"])
            monkeypatch.setattr(repair, "build_plan", local_plan)
            monkeypatch.setattr(repair, "retrain_and_invalidate", later_failure)
            args = SimpleNamespace(rollback_from=None, pdf_dir=None, apply=apply, backup_json=str(tmp_path / "rollback.json"))
            if apply:
                with pytest.raises(RuntimeError, match="later forecast"):
                    await repair.run(args)
                assert await committed_value(sessions) == 2.0
                assert await redis.get("fe:ver:publication-source") == "1"
                assert await redis.get("fe:ver:fixture-cascade") == "1"
            else:
                assert await repair.run(args) == 0
                assert await committed_value(sessions) == 1.0
                assert not await redis.keys("fe:ver:*")

    asyncio.run(scenario())


@pytest.mark.parametrize("primary_has_points", [False, True])
def test_weekly_primary_publishes_changed_siblings_after_commit(tmp_path, monkeypatch, primary_has_points):
    async def scenario():
        from app.services import rosstat_weekly_inflation_parser as weekly

        async with publication_env(tmp_path, monkeypatch) as (sessions, _redis):
            async with sessions() as db:
                source = await db.scalar(select(Indicator))
                source.code = "inflation-weekly"
                for code in weekly.WEEKLY_SEGMENT_CODES.values():
                    sibling = Indicator(code=code, name=code, is_active=True, model_config_json={"forecast_steps": 0})
                    db.add(sibling)
                    await db.flush()
                    db.add(IndicatorData(indicator_id=sibling.id, date=POINT_DATE, value=100.0))
                await db.commit()
            observed = []
            bump = cache.bump_namespaces

            async def bump_and_read(*namespaces):
                async with sessions() as reader:
                    values = (await reader.scalars(select(IndicatorData.value).where(IndicatorData.date == date(2026, 2, 1)))).all()
                observed.append((namespaces[0], values))
                await bump(*namespaces)

            monkeypatch.setattr(cache, "bump_namespaces", bump_and_read)

            class FixtureWeekly(weekly.RosstatWeeklyCpiParser):
                async def _fetch_and_parse(self, db, indicator, cfg, fetch_log):
                    self._segment_points = {"food": [weekly.WeeklyPoint(date(2026, 2, 1), 102.0)]}
                    points = [weekly.WeeklyPoint(date(2026, 2, 1), 101.0)] if primary_has_points else []
                    return points, "https://fixture.invalid/no-network"

            async with sessions() as writer:
                indicator = await writer.scalar(select(Indicator).where(Indicator.code == "inflation-weekly"))
                log = FetchLog(indicator_id=indicator.id, status="running")
                writer.add(log)
                await writer.commit()
                await FixtureWeekly().run(writer, indicator, log)
                assert log.status == "success"
            # Sibling changes also trigger the primary forecast hook, whose
            # generation must be published even when the primary fact is empty.
            expected_codes = {"inflation-weekly", "inflation-weekly-food"}
            assert {code for code, _ in observed} == expected_codes
            assert len(observed) == len(expected_codes)
            assert all(sorted(values) == ([101.0, 102.0] if primary_has_points else [102.0]) for _, values in observed)

    asyncio.run(scenario())


def test_deadline_after_commit_keeps_scheduler_changed_result(tmp_path, monkeypatch):
    async def scenario():
        async with publication_env(tmp_path, monkeypatch) as (sessions, _redis):
            entered = asyncio.Event()
            release = asyncio.Event()

            async def slow_publication(code):
                assert await committed_value(sessions) == 2.0
                entered.set()
                await release.wait()

            monkeypatch.setattr(bp, "cache_invalidate_indicator", slow_publication)
            monkeypatch.setattr(scheduler, "async_session", sessions)
            monkeypatch.setattr(scheduler, "get_parser", lambda _: RevisionParser())
            task = asyncio.create_task(scheduler._run_etl_with_timeout("publication-source", 0.1))
            await asyncio.wait_for(entered.wait(), 2)
            await asyncio.sleep(0.12)  # Deadline cancels the parser during shielded publication.
            release.set()
            assert await task == (True, "success")
            async with sessions() as reader:
                assert await reader.scalar(select(FetchLog.status)) == "success"

    asyncio.run(scenario())


def test_external_scheduler_cancellation_still_propagates_after_commit(tmp_path, monkeypatch):
    async def scenario():
        async with publication_env(tmp_path, monkeypatch) as (sessions, _redis):
            entered, release, finished = asyncio.Event(), asyncio.Event(), asyncio.Event()

            async def slow_publication(code):
                entered.set()
                await release.wait()
                finished.set()

            monkeypatch.setattr(bp, "cache_invalidate_indicator", slow_publication)
            monkeypatch.setattr(scheduler, "async_session", sessions)
            monkeypatch.setattr(scheduler, "get_parser", lambda _: RevisionParser())
            task = asyncio.create_task(scheduler._run_etl_with_timeout("publication-source", 60))
            await asyncio.wait_for(entered.wait(), 2)
            task.cancel()
            release.set()
            with pytest.raises(asyncio.CancelledError):
                await task
            assert finished.is_set()
            assert await committed_value(sessions) == 2.0
            async with sessions() as reader:
                assert await reader.scalar(select(FetchLog.status)) == "success"

    asyncio.run(scenario())


def test_deadline_before_commit_rolls_back_without_publication(tmp_path, monkeypatch):
    async def scenario():
        async with publication_env(tmp_path, monkeypatch) as (sessions, redis):
            entered = asyncio.Event()

            class UncommittedParser(RevisionParser):
                async def _after_storage(self, *args):
                    entered.set()
                    await asyncio.Event().wait()

            monkeypatch.setattr(scheduler, "async_session", sessions)
            monkeypatch.setattr(scheduler, "get_parser", lambda _: UncommittedParser())
            task = asyncio.create_task(scheduler._run_etl_with_timeout("publication-source", 0.1))
            await asyncio.wait_for(entered.wait(), 2)
            with pytest.raises(asyncio.TimeoutError):
                await task
            assert await committed_value(sessions) == 1.0
            assert not await redis.keys("fe:ver:*")
            async with sessions() as reader:
                assert await reader.scalar(select(FetchLog.status)) == "timeout"

    asyncio.run(scenario())


@pytest.mark.parametrize("pass_kind", ["daily", "late"])
def test_real_scheduler_pass_commits_derived_before_publication(tmp_path, monkeypatch, pass_kind):
    async def scenario():
        from app.services import alerting, indexnow

        async with publication_env(tmp_path, monkeypatch) as (sessions, _redis):
            engine = await derived_fixture(sessions)
            observed = []
            pinged = []
            bump = cache.bump_namespaces

            async def bump_and_read(*namespaces):
                async with sessions() as reader:
                    values = (await reader.scalars(select(IndicatorData.value).join(Indicator).order_by(Indicator.id))).all()
                observed.append((namespaces[0], values))
                await bump(*namespaces)

            async def broken_source_cache(_code):
                raise RuntimeError("fixture source cache failure after commit")

            async def no_external(*args, **kwargs):
                return []

            async def ping(codes):
                pinged.extend(codes)

            monkeypatch.setattr(cache, "bump_namespaces", bump_and_read)
            monkeypatch.setattr(bp, "cache_invalidate_indicator", broken_source_cache)
            monkeypatch.setattr(scheduler, "async_session", sessions)
            monkeypatch.setattr(scheduler, "get_parser", lambda _: RevisionParser())
            monkeypatch.setattr(scheduler, "calculation_engine", engine)
            monkeypatch.setattr(scheduler, "_running_locks", set())
            monkeypatch.setattr(scheduler, "_lock", asyncio.Lock())
            monkeypatch.setattr(scheduler, "_catch_up_empty_forecasts_safe", no_external)
            monkeypatch.setattr(scheduler, "_promote_past_events", no_external)
            monkeypatch.setattr(scheduler, "alert_etl_summary", no_external)
            monkeypatch.setattr(scheduler, "alert_etl_failure", no_external)
            monkeypatch.setattr(scheduler, "send_telegram", no_external)
            monkeypatch.setattr(alerting, "send_telegram", no_external)
            monkeypatch.setattr(indexnow, "ping_updated_indicators", ping)
            if pass_kind == "daily":
                await scheduler.daily_update_job()
            else:
                result = await scheduler.run_etl_for_parser_type("publication_fixture")
                assert result["updated"] == 1 and result["failed"] == 0
            assert {code for code, _ in observed} == {"fixture-derived", "fixture-cascade"}
            assert all(values == [2.0, 4.0, 8.0, 1.0] for _, values in observed)
            assert set(pinged) == {"publication-source", "fixture-derived", "fixture-cascade"}

    asyncio.run(scenario())
