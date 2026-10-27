"""Потолок времени ежедневного ETL: зависший источник не держит выгрузку часами.

07.10.2026 выгрузка шла 33 100 с (rosstat.gov.ru не принимал соединения).
"""
import asyncio
from types import SimpleNamespace

from app.config import settings
from app.tasks import scheduler


def test_deadline_exceeded_respects_limit_and_zero(monkeypatch):
    monkeypatch.setattr(settings, "etl_job_max_seconds", 100)
    assert scheduler.etl_job_deadline_exceeded(0.0, now_monotonic=99.0) is False
    assert scheduler.etl_job_deadline_exceeded(0.0, now_monotonic=101.0) is True
    monkeypatch.setattr(settings, "etl_job_max_seconds", 0)
    assert scheduler.etl_job_deadline_exceeded(0.0, now_monotonic=10**9) is False


def test_daily_job_skips_rest_after_ceiling_and_names_them(monkeypatch):
    inds = [
        SimpleNamespace(code=c, parser_type="rosstat_demo") for c in ("a", "b", "c")
    ] + [SimpleNamespace(code="d", parser_type="derived")]

    class _Res:
        def scalars(self):
            return SimpleNamespace(all=lambda: inds)

    class _Sess:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def execute(self, *_a, **_k):
            return _Res()

    ran, summary = [], {}

    async def fake_run(code, timeout):
        ran.append(code)
        return False, "no_new_data"

    async def fake_summary(total, updated, failed, duration, *, degraded=None):
        summary.update(total=total, failed=failed, degraded=degraded)

    async def noop(*_a, **_k):
        return []

    # потолок «достигается» после первого индикатора
    calls = {"n": 0}

    def exceeded(started, now=None):
        calls["n"] += 1
        return calls["n"] > 1

    monkeypatch.setattr(scheduler, "async_session", lambda: _Sess())
    monkeypatch.setattr(scheduler, "_run_etl_with_timeout", fake_run)
    monkeypatch.setattr(scheduler, "etl_job_deadline_exceeded", exceeded)
    monkeypatch.setattr(scheduler, "alert_etl_summary", fake_summary)
    monkeypatch.setattr(scheduler, "_catch_up_empty_forecasts_safe", noop)
    monkeypatch.setattr(scheduler, "_promote_past_events", noop)

    asyncio.run(scheduler.daily_update_job())

    assert ran == ["a"]
    assert summary["degraded"]["deadline_skipped"] == ["b", "c"]
    assert summary["total"] == 3


# --- 2026-10-27: повтор после остывания предохранителя хоста ---


def _run_daily(monkeypatch, inds, fake_run, *, breaker_left=0.0, limit=7200):
    class _Res:
        def scalars(self):
            return SimpleNamespace(all=lambda: inds)

    class _Sess:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def execute(self, *_a, **_k):
            return _Res()

        async def commit(self):
            return None

        async def rollback(self):
            return None

    summary, slept = {}, []

    async def fake_summary(total, updated, failed, duration, *, degraded=None):
        summary.update(total=total, updated=updated, failed=list(failed))

    async def noop(*_a, **_k):
        return []

    async def fake_sleep(sec):
        slept.append(sec)

    import app.services.http_client as hc

    monkeypatch.setattr(settings, "etl_job_max_seconds", limit)
    monkeypatch.setattr(hc, "host_down_max_remaining", lambda: breaker_left)
    monkeypatch.setattr(scheduler, "async_session", lambda: _Sess())
    monkeypatch.setattr(scheduler, "_run_etl_with_timeout", fake_run)
    monkeypatch.setattr(scheduler, "alert_etl_summary", fake_summary)
    monkeypatch.setattr(scheduler, "_catch_up_empty_forecasts_safe", noop)
    monkeypatch.setattr(scheduler, "_promote_past_events", noop)
    monkeypatch.setattr(scheduler.asyncio, "sleep", fake_sleep)

    async def no_derived(*_a, **_k):
        return []

    import app.services.indexnow as indexnow

    monkeypatch.setattr(scheduler.calculation_engine, "run_for_updated_sources", no_derived)
    monkeypatch.setattr(scheduler, "publish_committed_indicator_changes", noop)
    monkeypatch.setattr(indexnow, "ping_updated_indicators", noop)
    asyncio.run(scheduler.daily_update_job())
    return summary, slept


def test_network_failure_is_retried_once_after_breaker_cools(monkeypatch):
    inds = [SimpleNamespace(code=c, parser_type="rosstat_demo") for c in ("a", "b")]
    attempts = {"a": 0, "b": 0}

    async def fake_run(code, timeout):
        attempts[code] += 1
        if code == "a" and attempts[code] == 1:
            raise RuntimeError("rosstat.gov.ru unreachable on all hops recently; skipping for 1198s more")
        return True, "success"

    summary, slept = _run_daily(monkeypatch, inds, fake_run, breaker_left=300.0)
    assert attempts == {"a": 2, "b": 1}
    assert summary["failed"] == [] and summary["updated"] == 2
    assert slept and slept[0] >= 300


def test_non_network_failure_is_not_retried(monkeypatch):
    inds = [SimpleNamespace(code="a", parser_type="rosstat_demo")]
    attempts = {"a": 0}

    async def fake_run(code, timeout):
        attempts[code] += 1
        raise ValueError("layout changed: column 'X' missing")

    summary, _ = _run_daily(monkeypatch, inds, fake_run)
    assert attempts["a"] == 1 and summary["failed"] == ["a"]


def test_network_retry_skipped_when_ceiling_leaves_no_room(monkeypatch):
    inds = [SimpleNamespace(code="a", parser_type="rosstat_demo")]
    attempts = {"a": 0}

    async def fake_run(code, timeout):
        attempts[code] += 1
        raise RuntimeError("Rosstat unreachable: all 3 requests failed on network")

    summary, slept = _run_daily(monkeypatch, inds, fake_run, breaker_left=1200.0, limit=600)
    assert attempts["a"] == 1 and summary["failed"] == ["a"] and slept == []


def test_still_failing_after_retry_stays_failed(monkeypatch):
    inds = [SimpleNamespace(code="a", parser_type="rosstat_demo")]
    attempts = {"a": 0}

    async def fake_run(code, timeout):
        attempts[code] += 1
        raise RuntimeError("rosstat.gov.ru unreachable on all hops recently")

    summary, _ = _run_daily(monkeypatch, inds, fake_run)
    assert attempts["a"] == 2 and summary["failed"] == ["a"]
