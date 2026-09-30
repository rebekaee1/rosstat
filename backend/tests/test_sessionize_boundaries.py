"""F05 caller-level window boundary regressions on isolated SQLite.

Reference runs the actual sessionizer once over the same source observations;
chunked runs call actual run_rollups with three-day windows. No source/network,
application DB or analytics-engine substitution in product code.
"""
import asyncio
from datetime import datetime, timedelta

import pytest
from sqlalchemy import delete, select, text

from app.models import BehaviorEvent, BehaviorSession, FrontendEvent, ServerSession
from app.tasks import analytics_rollups as rollups
from app.services.analytics_period import msk_day_start_utc
from test_analytics2 import _run_with_db

NOW = datetime(2026, 9, 30, 12)
SINCE = msk_day_start_utc((NOW - timedelta(days=8)).date())
BOUNDARY = SINCE + timedelta(days=3)
FIELDS = tuple(column for column in ServerSession.__table__.columns
               if column.name not in {'id', 'computed_at'})


async def _sessions(maker):
    async with maker() as db:
        return [tuple(row) for row in (await db.execute(
            select(*FIELDS).order_by(ServerSession.visitor_id_hash, ServerSession.started_at)
        )).all()]


async def _temporary_tables(db):
    if db.bind.dialect.name == 'postgresql':
        query = "SELECT relname FROM pg_class WHERE relnamespace = pg_my_temp_schema() AND relname LIKE 'sessionize_%' AND relkind='r'"
    else:
        query = "SELECT name FROM sqlite_temp_master WHERE name LIKE 'sessionize_%' AND type='table'"
    return (await db.execute(text(query))).all()


def _fields(row):
    return dict(zip([column.name for column in FIELDS], row))


async def _put(maker, observations, goals=()):
    async with maker() as db:
        for minute, kind, page, params in observations:
            db.add(BehaviorEvent(visitor_id_hash='boundary-visitor', session_id_hash='client',
                                 occurred_at=BOUNDARY + timedelta(minutes=minute),
                                 event_type=kind, page=page, params_json=params))
        for minute, name in goals:
            db.add(FrontendEvent(session_id_hash='client', visitor_id_hash='boundary-visitor',
                                 occurred_at=BOUNDARY + timedelta(minutes=minute), event_name=name))
        await db.commit()


async def _continuous_then_chunked(maker, monkeypatch):
    async with maker() as db:
        await rollups.sessionize(db, SINCE)
    reference = await _sessions(maker)
    async with maker() as db:
        await db.execute(delete(ServerSession))
        await db.commit()
    monkeypatch.setattr(rollups, 'analytics_session', maker)
    monkeypatch.setattr(rollups, '_utcnow', lambda: NOW)
    await rollups.run_rollups(days=8)
    return reference, await _sessions(maker)


@pytest.mark.parametrize('gap', [4, 29, 30, 31])
def test_caller_three_day_windows_match_continuous_session_gap(monkeypatch, gap):
    async def scenario(maker):
        await _put(maker, [(-2, 'pageview', '/entry', {}),
                           (-2 + gap, 'pageview', '/next', {}),
                           (-1 + gap, 'dwell', '/next', {'active_ms': 20000, 'scroll_pct': 75})],
                   goals=[(-1 + gap, 'download_csv')])
        reference, chunked = await _continuous_then_chunked(maker, monkeypatch)
        assert len(reference) == (1 if gap < 30 else 2)
        assert chunked == reference
        first = _fields(chunked[0])
        assert first['started_at'] == BOUNDARY - timedelta(minutes=2)
        assert first['day'] == (BOUNDARY + timedelta(hours=3) - timedelta(minutes=2)).date()
        assert first['is_new_visitor'] is True and first['entry_page'] == '/entry'
        if gap < 30:
            assert first['pageviews'] == 2 and first['active_ms'] == 20000
            assert first['ended_at'] == BOUNDARY + timedelta(minutes=gap - 1)
            assert first['micro_goals'] == 1 and first['is_engaged'] is True
        else:
            second = _fields(chunked[1])
            assert second['is_new_visitor'] is False and second['micro_goals'] == 1
            assert first['pageviews'] == second['pageviews'] == 1
    _run_with_db(scenario)


def test_caller_keeps_pageviewless_dwell_tail_and_goals_across_window(monkeypatch):
    async def scenario(maker):
        await _put(maker, [(-2, 'pageview', '/entry', {}),
                           (40, 'dwell', '/entry', {'active_ms': 25000, 'scroll_pct': 80})],
                   goals=[(41, 'signup')])
        reference, chunked = await _continuous_then_chunked(maker, monkeypatch)
        assert len(reference) == 1
        row = dict(zip([column.name for column in FIELDS], reference[0]))
        assert row['ended_at'] == BOUNDARY + timedelta(minutes=40)
        assert row['active_ms'] == 25000 and row['macro_goals'] == 1
        assert chunked == reference
    _run_with_db(scenario)


def test_caller_backfill_rejoins_boundary_and_rerun_is_content_idempotent(monkeypatch):
    async def scenario(maker):
        await _put(maker, [(-20, 'pageview', '/entry', {}), (20, 'pageview', '/exit', {})])
        monkeypatch.setattr(rollups, 'analytics_session', maker)
        monkeypatch.setattr(rollups, '_utcnow', lambda: NOW)
        await rollups.run_rollups(days=8)
        assert len(await _sessions(maker)) == 2
        # Delayed middle point repairs a40min gap into two20min gaps.
        await _put(maker, [(0, 'pageview', '/middle', {})])
        await rollups.run_rollups(days=8)  # Repair over existing two persisted keys.
        repaired = await _sessions(maker)
        assert len(repaired) == 1
        assert _fields(repaired[0])['pageviews'] == 3
        assert _fields(repaired[0])['started_at'] == BOUNDARY - timedelta(minutes=20)
        assert _fields(repaired[0])['ended_at'] == BOUNDARY + timedelta(minutes=20)
        reference, chunked = await _continuous_then_chunked(maker, monkeypatch)
        assert len(reference) == 1
        assert chunked == reference
        await rollups.run_rollups(days=8)
        assert await _sessions(maker) == reference
    _run_with_db(scenario)


def test_fallback_portrait_is_session_aligned_and_future_portrait_does_not_leak(monkeypatch):
    async def scenario(maker):
        await _put(maker, [(-2, 'pageview', '/entry', {'ref': 'https://yandex.ru/search/', 'touch': True, 'vw': 320}),
                           (2, 'pageview', '/next', {})])
        async with maker() as db:
            db.add_all([
                BehaviorSession(session_id_hash='past', visitor_id_hash='boundary-visitor',
                                started_at=BOUNDARY - timedelta(minutes=10), device_type='mobile', touch=True),
                BehaviorSession(session_id_hash='future', visitor_id_hash='boundary-visitor',
                                started_at=BOUNDARY + timedelta(days=2), device_type='desktop',
                                screen_w=1366, screen_h=1366, cpu_cores=192),
            ])
            await db.commit()
        reference, chunked = await _continuous_then_chunked(maker, monkeypatch)
        assert chunked == reference
        row = _fields(chunked[0])
        assert row['channel'] == 'search' and row['device'] == 'mobile'
        assert row['bot_score'] == 0 and row['is_bot'] is False
    _run_with_db(scenario)


def test_matching_client_portrait_after_logical_end_cannot_supply_future_signals(monkeypatch):
    async def scenario(maker):
        await _put(maker, [(-2, 'pageview', '/entry', {'ref': 'https://www.google.com/search', 'touch': True, 'vw': 320}),
                           (2, 'click', '/entry', {'synthetic': False})])
        async with maker() as db:
            db.add(BehaviorSession(session_id_hash='client', visitor_id_hash='boundary-visitor',
                                   started_at=BOUNDARY + timedelta(hours=2), channel='ad',
                                   device_type='desktop', is_webdriver=True, cpu_cores=192))
            await db.commit()
        reference, chunked = await _continuous_then_chunked(maker, monkeypatch)
        assert chunked == reference and len(chunked) == 1
        row = _fields(chunked[0])
        assert row['channel'] == 'search' and row['device'] == 'mobile'
        assert row['bot_score'] == 0 and row['is_bot'] is False
    _run_with_db(scenario)


def test_simultaneous_events_and_goal_margin_preserve_literal_order_and_tiers(monkeypatch):
    async def scenario(maker):
        await _put(maker, [(-1, 'pageview', '/first', {'touch': True, 'vw': 320}),
                           (-1, 'pageview', '/second', {}),
                           (1, 'click', '/second', {'synthetic': True}),
                           (1, 'click', '/last', {'synthetic': False})],
                   goals=[(-6, 'signup'), (6, 'download_csv'), (7, 'signup')])
        reference, chunked = await _continuous_then_chunked(maker, monkeypatch)
        assert chunked == reference and len(chunked) == 1
        row = _fields(chunked[0])
        assert row['entry_page'] == '/first' and row['exit_page'] == '/last'
        assert row['pageviews'] == 2 and row['clicks'] == 2
        assert row['macro_goals'] == row['micro_goals'] == 1
        assert row['device'] == 'mobile' and row['bot_score'] == 0
    _run_with_db(scenario)


def test_whole_start_day_flood_count_survives_left_boundary_repair(monkeypatch):
    async def scenario(maker):
        await _put(maker, [(-1202 + 40 * n, 'pageview', f'/p{n}', {}) for n in range(31)]
                   + [(2, 'pageview', '/continued', {})])
        reference, chunked = await _continuous_then_chunked(maker, monkeypatch)
        assert chunked == reference and len(chunked) == 31
        assert [_fields(row)['bot_score'] for row in chunked] == [60] * 30 + [40]
        assert _fields(chunked[-1])['pageviews'] == 2
    _run_with_db(scenario)


def test_long_chain_spanning_multiple_windows_keeps_original_left_owner(monkeypatch):
    async def scenario(maker):
        async with maker() as db:
            points = [SINCE - timedelta(minutes=10) + timedelta(minutes=20 * n) for n in range(610)]
            db.add_all(BehaviorEvent(visitor_id_hash='long-chain', session_id_hash='long-client',
                                    event_type='pageview', page=f'/p{n}', occurred_at=ts)
                       for n, ts in enumerate(points))
            await db.commit()
        reference, chunked = await _continuous_then_chunked(maker, monkeypatch)
        assert chunked == reference and len(chunked) == 1
        row = _fields(chunked[0])
        assert row['started_at'] == points[0] and row['ended_at'] == points[-1]
        assert row['pageviews'] == 610 and row['duration_ms'] == 609 * 20 * 60 * 1000
    _run_with_db(scenario)


def test_empty_window_preserves_older_and_future_unrelated_rows_and_removes_stage(monkeypatch):
    async def scenario(maker):
        async with maker() as db:
            for label, ts in [('old', SINCE - timedelta(days=2)), ('future', NOW + timedelta(days=1))]:
                db.add(ServerSession(visitor_id_hash=label, started_at=ts, ended_at=ts,
                                     day=ts.date(), pageviews=1))
            await db.commit()
        before = await _sessions(maker)
        async with maker() as db:
            assert await rollups.sessionize(db, SINCE, until=BOUNDARY) == 0
            assert await _temporary_tables(db) == []
        assert await _sessions(maker) == before
    _run_with_db(scenario)


def test_failed_source_aggregation_rolls_back_and_cleans_temporary_stage(monkeypatch):
    async def scenario(maker):
        await _put(maker, [(-2, 'pageview', '/entry', {})])
        async with maker() as db:
            await rollups.sessionize(db, SINCE, until=BOUNDARY)
        before = await _sessions(maker)
        await _put(maker, [(2, 'dwell', '/entry', {'active_ms': 'invalid-int'})])
        async with maker() as db:
            with pytest.raises(ValueError):
                await rollups.sessionize(db, SINCE, until=BOUNDARY + timedelta(minutes=5))
            assert await _temporary_tables(db) == []
        assert await _sessions(maker) == before
    _run_with_db(scenario)


def test_failed_commit_restores_previous_logical_sessions(monkeypatch):
    async def scenario(maker):
        await _put(maker, [(-2, 'pageview', '/entry', {})])
        async with maker() as db:
            await rollups.sessionize(db, SINCE, until=BOUNDARY)
        before = await _sessions(maker)
        await _put(maker, [(2, 'pageview', '/exit', {})])
        async with maker() as db:
            real_commit = db.commit
            attempts = []

            async def failed_once():
                if not attempts:
                    assert await db.scalar(select(ServerSession.pageviews)) == 2
                    attempts.append('actual-written')
                    raise RuntimeError('injected facts commit failure')
                await real_commit()

            monkeypatch.setattr(db, 'commit', failed_once)
            with pytest.raises(RuntimeError, match='injected facts commit failure'):
                await rollups.sessionize(db, SINCE, until=BOUNDARY + timedelta(minutes=5))
        assert attempts == ['actual-written']
        assert await _sessions(maker) == before
    _run_with_db(scenario)
