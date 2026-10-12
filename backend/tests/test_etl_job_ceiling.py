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
