"""Production alerts distinguish app regressions from third-party noise."""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from app.services import analytics_alerts as alerts


NOW = datetime(2026, 9, 27, 12)


@pytest.mark.parametrize(
    "params, expected",
    [
        ({"kind": "error", "src": "https://forecasteconomy.com/assets/app.js"}, True),
        ({"kind": "rejection", "stack": "at https://forecasteconomy.com/app.js:1"}, True),
        ({"kind": "resource", "src": "https://forecasteconomy.com/assets/app.js"}, False),
        ({"kind": "error", "src": "https://mc.yandex.ru/metrika/tag.js"}, False),
        ({"kind": "rejection", "stack": "at https://yastatic.net/ads.js:1"}, False),
        ({"kind": "error", "src": "https://x.adfox.ru/a.js"}, False),
        ({"kind": "error", "src": "https://webvisor.com/a.js"}, False),
        ({"kind": "error", "src": "https://notadfox.ru/a.js"}, True),
        (None, False),
    ],
)
def test_js_error_alert_scope(params, expected):
    assert alerts.js_error_counts_for_alert(params) is expected


def test_memory_pressure_alerts_once_per_episode():
    assert alerts.memory_pressure_episode(0.86, sticky=False) == "alert"
    assert alerts.memory_pressure_episode(0.99, sticky=True) == "hold"
    assert alerts.memory_pressure_episode(0.80, sticky=True) == "hold"
    assert alerts.memory_pressure_episode(0.74, sticky=True) == "clear"
    assert alerts.memory_pressure_episode(0.86, sticky=False) == "alert"


def test_collection_silence_requires_real_45_minute_gap_and_live_traffic():
    assert not alerts.collection_silence_due(
        last_seen=NOW - timedelta(minutes=44), now=NOW,
        prev_hour_pageviews=20, probe_failed=False,
    )
    assert alerts.collection_silence_due(
        last_seen=NOW - timedelta(minutes=46), now=NOW,
        prev_hour_pageviews=20, probe_failed=False,
    )
    assert not alerts.collection_silence_due(
        last_seen=NOW - timedelta(minutes=46), now=NOW,
        prev_hour_pageviews=20, probe_failed=True,
    )
    assert not alerts.collection_silence_due(
        last_seen=None, now=NOW,
        prev_hour_pageviews=0, probe_failed=False,
    )


def test_failed_collection_probe_cannot_create_silence_alert(monkeypatch):
    class RedisDown:
        async def get(self, _key):
            raise ConnectionError("state redis unavailable")

    async def redis():
        return RedisDown()

    monkeypatch.setattr("app.core.cache.get_state_redis", redis)
    db = AsyncMock()
    db.scalar.side_effect = RuntimeError("statement timeout")
    last_seen, failed = asyncio.run(alerts._last_collection_seen(db, NOW))
    assert (last_seen, failed) == (None, True)
    db.rollback.assert_awaited_once()
    assert not alerts.collection_silence_due(
        last_seen=last_seen, now=NOW, prev_hour_pageviews=100, probe_failed=failed,
    )


def test_alert_reports_only_successful_delivery(monkeypatch):
    monkeypatch.setattr(alerts, "_muted", AsyncMock(return_value=False))
    clear = AsyncMock()
    monkeypatch.setattr(alerts, "_clear_mute", clear)
    send = AsyncMock(return_value=False)
    monkeypatch.setattr("app.services.alerting.send_telegram", send)
    assert not asyncio.run(alerts._alert("memory_pressure", "test"))
    clear.assert_awaited_once_with("memory_pressure")
    send.return_value = True
    assert asyncio.run(alerts._alert("memory_pressure", "test"))
    clear.assert_awaited_once()


def test_alert_mute_claim_is_atomic_and_failure_can_retry(monkeypatch):
    class StateRedis:
        def __init__(self):
            self.keys = set()

        async def set(self, key, _value, *, ex, nx):
            assert ex == alerts._MUTE_TTL and nx is True
            if key in self.keys:
                return None
            self.keys.add(key)
            return True

        async def delete(self, key):
            self.keys.discard(key)

    redis = StateRedis()

    async def state_redis():
        return redis

    monkeypatch.setattr("app.core.cache.get_state_redis", state_redis)
    assert not asyncio.run(alerts._muted("memory_pressure"))
    assert asyncio.run(alerts._muted("memory_pressure"))
    asyncio.run(alerts._clear_mute("memory_pressure"))
    assert not asyncio.run(alerts._muted("memory_pressure"))


def test_memory_episode_becomes_sticky_only_after_delivery(monkeypatch):
    class Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def scalar(self, _statement):
            return 0

    monkeypatch.setattr("app.services.process_metrics.memory_pressure_ratio", lambda: 0.9)
    monkeypatch.setattr("app.database.pool_stats", lambda _pool: {"size": 1, "checkedout": 0})
    monkeypatch.setattr(alerts, "analytics_session", Session)
    monkeypatch.setattr(alerts, "_memory_sticky", AsyncMock(return_value=False))
    set_sticky = AsyncMock()
    monkeypatch.setattr(alerts, "_set_memory_sticky", set_sticky)
    notify = AsyncMock(return_value=False)
    monkeypatch.setattr(alerts, "_alert", notify)

    asyncio.run(alerts._check_host_pressure())
    set_sticky.assert_not_awaited()
    notify.return_value = True
    asyncio.run(alerts._check_host_pressure())
    set_sticky.assert_awaited_once_with(True)
