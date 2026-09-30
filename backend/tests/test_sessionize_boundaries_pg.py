"""Opt-in F05 PostgreSQL equivalence; private schemas, real SQL window/COPY-free rollups.

Only F01_TEST_DATABASE_URL at loopback/nondefault port/fe_f01_* is accepted.
No production, Redis or external analytics source. Python fixtures are tiny.
"""
import asyncio
import os
from contextlib import asynccontextmanager
from datetime import timedelta
from urllib.parse import urlsplit
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from sqlalchemy.schema import CreateIndex, CreateSchema, CreateTable, DropSchema

from app.models import (BehaviorEvent, BehaviorSession, DailyGoal, DailyPage, DailyTraffic,
                        EmailCredential, FrontendEvent, IdentityLink, MetrikaGoal, OAuthIdentity,
                        RawMetrikaVisit, ServerSession, User)
from app.tasks import analytics_rollups as rollups
from test_sessionize_boundaries import BOUNDARY, NOW, SINCE, _continuous_then_chunked, _fields, _put, _sessions
from test_world_national_reconcile_pg import _validated_pg_url
import test_sessionize_boundaries as boundary_contracts


def _pg_url():
    raw = os.environ.get('F01_TEST_DATABASE_URL')
    if not raw:
        pytest.skip('Set explicit isolated F01_TEST_DATABASE_URL for PostgreSQL acceptance')
    url = _validated_pg_url(raw)
    parts = urlsplit(raw)
    if url.port in {None, 5432} or parts.query or parts.fragment:
        raise ValueError('F05 requires isolated PostgreSQL nondefault port without query/fragment')
    return url


@asynccontextmanager
async def _analytics_database(url):
    schema = 'f05_test_' + uuid4().hex
    engine = create_async_engine(url, poolclass=NullPool,
        connect_args={'server_settings': {'search_path': schema, 'statement_timeout': '60000'}})
    created = False
    try:
        async with engine.begin() as connection:
            await connection.execute(CreateSchema(schema))
        created = True
        async with engine.begin() as connection:
            for model in (User, EmailCredential, OAuthIdentity, IdentityLink, BehaviorEvent, BehaviorSession,
                          FrontendEvent, ServerSession, RawMetrikaVisit, MetrikaGoal, DailyTraffic, DailyGoal, DailyPage):
                await connection.execute(CreateTable(model.__table__))
                for index in model.__table__.indexes:
                    await connection.execute(CreateIndex(index))
        yield async_sessionmaker(engine, expire_on_commit=False)
    finally:
        try:
            if created:
                async with engine.begin() as connection:
                    await connection.execute(DropSchema(schema, cascade=True))
        finally:
            await engine.dispose()


@pytest.mark.parametrize('case', ['gap29', 'gap30', 'dwell-tail', 'late-bridge'])
def test_real_pg_caller_windows_repair_content_and_keep_session_ownership(monkeypatch, case):
    url = _pg_url()

    async def scenario():
        async with _analytics_database(url) as maker:
            if case.startswith('gap'):
                gap = int(case[3:])
                await _put(maker, [(-2, 'pageview', '/entry', {'touch': True, 'vw': 320}),
                                   (-2 + gap, 'pageview', '/exit', {})])
            elif case == 'dwell-tail':
                await _put(maker, [(-2, 'pageview', '/entry', {}),
                                   (40, 'dwell', '/entry', {'active_ms': 20000, 'scroll_pct': 75})],
                           goals=[(-7, 'download_csv'), (45, 'signup'), (46, 'signup')])
            else:
                await _put(maker, [(-20, 'pageview', '/entry', {}), (20, 'pageview', '/exit', {})])
                monkeypatch.setattr(rollups, 'analytics_session', maker)
                monkeypatch.setattr(rollups, '_utcnow', lambda: NOW)
                await rollups.run_rollups(days=8)
                assert len(await _sessions(maker)) == 2
                await _put(maker, [(0, 'pageview', '/middle', {})])
                await rollups.run_rollups(days=8)
                actual = await _sessions(maker)
                assert len(actual) == 1 and _fields(actual[0])['pageviews'] == 3
            reference, actual = await _continuous_then_chunked(maker, monkeypatch)
            assert actual == reference
            expected_n = 2 if case == 'gap30' else 1
            assert len(actual) == expected_n
            first = _fields(actual[0])
            assert first['entry_page'] == '/entry' and first['is_new_visitor'] is True
            assert first['started_at'] == BOUNDARY - timedelta(minutes=20 if case == 'late-bridge' else 2)
            if case == 'gap29':
                assert first['pageviews'] == 2 and first['device'] == 'mobile'
            if case == 'dwell-tail':
                assert first['active_ms'] == 20000 and first['max_scroll_pct'] == 75
                assert first['micro_goals'] == first['macro_goals'] == 1
                assert first['ended_at'] == BOUNDARY + timedelta(minutes=40)
            await rollups.run_rollups(days=8)
            assert await _sessions(maker) == actual
    asyncio.run(scenario())


@pytest.mark.parametrize('contract', [
    'test_fallback_portrait_is_session_aligned_and_future_portrait_does_not_leak',
    'test_matching_client_portrait_after_logical_end_cannot_supply_future_signals',
    'test_simultaneous_events_and_goal_margin_preserve_literal_order_and_tiers',
    'test_whole_start_day_flood_count_survives_left_boundary_repair',
    'test_long_chain_spanning_multiple_windows_keeps_original_left_owner',
    'test_empty_window_preserves_older_and_future_unrelated_rows_and_removes_stage',
    'test_failed_source_aggregation_rolls_back_and_cleans_temporary_stage',
    'test_failed_commit_restores_previous_logical_sessions',
])
def test_real_pg_literal_edge_contracts_and_atomic_cleanup(monkeypatch, contract):
    """Reuse literal expectations through a real-PG DB seam, never SQLite SQL."""
    url = _pg_url()

    def run_with_pg(scenario):
        async def run():
            async with _analytics_database(url) as maker:
                await scenario(maker)
        asyncio.run(run())

    monkeypatch.setattr(boundary_contracts, '_run_with_db', run_with_pg)
    getattr(boundary_contracts, contract)(monkeypatch)
