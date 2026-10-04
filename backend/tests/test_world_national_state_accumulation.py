"""Ошибка ряда набора не затирается успехом соседнего ряда того же набора.

`world_dataset_state` — одна строка на (provider, dataset_id), а у Китая набор
`hgyd` держит десятки рядов: падение industrial-production при успешных соседях
раньше исчезало из состояния и из сводки.
"""
from __future__ import annotations

import asyncio

from app.models import WorldDatasetState
from app.services.world_national_ingest import (
    CountryIngestStats,
    DatasetRunTracker,
    SeriesIngestResult,
    format_failed_series,
    touch_dataset_state,
)

PROVIDER, DATASET = "nbs", "hgyd"


async def _state(auth_env):
    async with auth_env["session_maker"]() as db:
        return await db.get(WorldDatasetState, (PROVIDER, DATASET))


async def _touch(auth_env, tracker, code, status, error=None):
    async with auth_env["session_maker"]() as db:
        async with db.begin():
            await touch_dataset_state(
                db, provider=PROVIDER, dataset_id=DATASET, status=status,
                error=error, tracker=tracker, series_code=code,
            )


def test_success_after_error_keeps_dataset_in_error(auth_env):
    async def run():
        tracker = DatasetRunTracker()
        await _touch(auth_env, tracker, "cn-industrial-production", "error", "HTTPError: 500")
        await _touch(auth_env, tracker, "cn-cpi", "ok")
        await _touch(auth_env, tracker, "cn-retail", "ok")
        return await _state(auth_env)

    state = asyncio.run(run())
    assert state.status == "error"
    assert "Ошибок рядов: 1 из 3" in state.last_error
    assert "cn-industrial-production: HTTPError: 500" in state.last_error
    assert state.last_success_at is not None  # соседние ряды набора загрузились


def test_error_after_success_is_also_error(auth_env):
    async def run():
        tracker = DatasetRunTracker()
        await _touch(auth_env, tracker, "cn-cpi", "ok")
        await _touch(auth_env, tracker, "cn-industrial-production", "error", "boom")
        await _touch(auth_env, tracker, "cn-retail", "ok")
        return await _state(auth_env)

    state = asyncio.run(run())
    assert state.status == "error"
    assert "Ошибок рядов: 1 из 3" in state.last_error


def test_all_series_ok_clears_previous_error(auth_env):
    async def run():
        first = DatasetRunTracker()
        await _touch(auth_env, first, "cn-cpi", "error", "boom")
        second = DatasetRunTracker()  # следующий прогон
        await _touch(auth_env, second, "cn-cpi", "ok")
        await _touch(auth_env, second, "cn-retail", "ok")
        return await _state(auth_env)

    state = asyncio.run(run())
    assert state.status == "ok"
    assert state.last_error is None


def test_series_recovered_within_run_is_no_longer_error():
    tracker = DatasetRunTracker()
    tracker.record(PROVIDER, DATASET, "cn-cpi", "boom")
    tracker.record(PROVIDER, DATASET, "cn-cpi", None)
    assert tracker.status(PROVIDER, DATASET) == "ok"
    assert tracker.error_text(PROVIDER, DATASET) is None


def test_error_text_lists_series_and_stays_within_limit():
    tracker = DatasetRunTracker()
    for n in range(40):
        tracker.record(PROVIDER, DATASET, f"cn-series-{n}", "E" * 400)
    text = tracker.error_text(PROVIDER, DATASET)
    assert text.startswith("Ошибок рядов: 40 из 40.")
    assert len(text) <= 2000
    assert "…и ещё" in text


def test_other_datasets_are_independent():
    tracker = DatasetRunTracker()
    tracker.record("nbs", "hgyd", "cn-a", "boom")
    tracker.record("nbs", "other", "cn-b", None)
    assert tracker.status("nbs", "hgyd") == "error"
    assert tracker.status("nbs", "other") == "ok"


def test_without_tracker_behaviour_is_unchanged(auth_env):
    async def run():
        async with auth_env["session_maker"]() as db:
            async with db.begin():
                await touch_dataset_state(
                    db, provider=PROVIDER, dataset_id=DATASET, status="error", error="x",
                )
        return await _state(auth_env)

    state = asyncio.run(run())
    assert state.status == "error" and state.last_error == "x"


def test_failed_series_property_and_format():
    stats = CountryIngestStats(country_code="CN", series_ok=2, series_err=2)
    stats.results = [
        SeriesIngestResult("cn-cpi", "nbs", "hgyd"),
        SeriesIngestResult("cn-industrial-production", "nbs", "hgyd", error="boom"),
        SeriesIngestResult("cn-retail", "nbs", "hgyd", error="HTTP 500"),
    ]
    assert stats.failed_series == [
        ("cn-industrial-production", "boom"), ("cn-retail", "HTTP 500"),
    ]
    assert format_failed_series({"cn": stats.failed_series}) == (
        "cn: cn-industrial-production, cn-retail"
    )
    many = {"cn": [(f"cn-{n}", "e") for n in range(20)]}
    text = format_failed_series(many, limit=5)
    assert text == "cn: cn-0, cn-1, cn-2, cn-3, cn-4 (ещё 15)"


def test_summary_names_failed_series_and_counts_them(auth_env, monkeypatch):
    """Сводка: «Ошибки» — поимённо ряды, счётчик «Ошибок» — число рядов, а не стран."""
    import app.core.cache as cache_mod
    import app.services.alerting as alerting
    import app.services.world_national_ingest as ingest_mod

    monkeypatch.setattr(ingest_mod, "async_session", auth_env["session_maker"])

    async def fake_ingest_country(db, country, *, dry_run):
        stats = CountryIngestStats(
            country_code="CN", series_ok=1, series_err=2, indicators_upserted=1,
        )
        stats.results = [
            SeriesIngestResult("cn-cpi", "nbs", "hgyd"),
            SeriesIngestResult("cn-industrial-production", "nbs", "hgyd", error="boom"),
            SeriesIngestResult("cn-retail", "nbs", "hgyd", error="boom"),
        ]
        return stats

    async def noop_bump(*_):
        return None

    alerts = []

    async def capture_alert(source, **kwargs):
        alerts.append(kwargs)

    monkeypatch.setattr(ingest_mod, "ingest_country", fake_ingest_country)
    monkeypatch.setattr(cache_mod, "bump_namespaces", noop_bump)
    monkeypatch.setattr(alerting, "alert_world_ingest_summary", capture_alert)

    async def run():
        result = await ingest_mod.run_national_core_ingest(country_codes=["cn"])
        async with auth_env["session_maker"]() as db:
            from app.models import WorldIngestRun

            run = await db.get(WorldIngestRun, result["run_id"])
            return result, run

    result, run = asyncio.run(run())
    assert alerts[0]["status"] == "partial"
    assert alerts[0]["failed"] == 2
    assert "cn: cn-industrial-production, cn-retail" in alerts[0]["details"]
    assert "series errors (2)" in (run.error_message or "")
