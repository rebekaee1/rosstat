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


def test_js_error_query_excludes_resource_noise_before_loading_rows():
    from sqlalchemy import create_engine

    from app.models import BehaviorEvent

    engine = create_engine("sqlite://")
    BehaviorEvent.__table__.create(engine)
    with engine.begin() as conn:
        conn.execute(BehaviorEvent.__table__.insert(), [
            {"event_type": "js_error", "occurred_at": NOW, "params_json": {"kind": "error"}},
            {"event_type": "js_error", "occurred_at": NOW, "params_json": {"kind": "rejection"}},
            {"event_type": "js_error", "occurred_at": NOW, "params_json": {"kind": "resource"}},
            {"event_type": "js_error", "occurred_at": NOW - timedelta(minutes=16),
             "params_json": {"kind": "error"}},
            {"event_type": "pageview", "occurred_at": NOW, "params_json": {"kind": "error"}},
        ])
        rows = conn.execute(alerts._own_js_error_params_query(NOW)).scalars().all()
    engine.dispose()
    assert [row["kind"] for row in rows] == ["error", "rejection"]


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
            assert ex == alerts._alert_cooldown("memory_pressure") and nx is True
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


# --- 2026-10-04: меньше ложных алертов -------------------------------------


def test_traffic_drop_needs_two_hours_real_base_and_non_night():
    ok = dict(cur=10, base=100, prev_cur=20, prev_base=100, minutes_into_hour=40, msk_hour=14)
    assert alerts.traffic_drop_due(**ok)
    # 26 против 81 (32%) — но предыдущий час в норме: один плохой час не алерт.
    assert not alerts.traffic_drop_due(**{**ok, "cur": 26, "base": 81, "prev_cur": 90})
    # Неполный час (< 30 минут).
    assert not alerts.traffic_drop_due(**{**ok, "minutes_into_hour": 20})
    # Малая база (< 30) в любой из двух часов.
    assert not alerts.traffic_drop_due(**{**ok, "base": 29, "cur": 1})
    assert not alerts.traffic_drop_due(**{**ok, "prev_base": 29, "prev_cur": 1})
    # Ночью (МСК 00–07) база должна быть ≥ 100, и предыдущий час тоже.
    night = {**ok, "msk_hour": 3, "base": 60, "prev_base": 60}
    assert not alerts.traffic_drop_due(**night)
    assert alerts.traffic_drop_due(**{**night, "base": 120, "prev_base": 120})
    # 07:30 МСК: предыдущий час (06:00) ещё ночной.
    assert not alerts.traffic_drop_due(**{**ok, "msk_hour": 7, "prev_base": 60})
    # Ровно 40% — не падение.
    assert not alerts.traffic_drop_due(**{**ok, "cur": 40, "prev_cur": 40})


def test_traffic_drop_counts_only_human_pageviews():
    from datetime import date

    from sqlalchemy import create_engine

    from app.models import BehaviorEvent, ServerSession

    engine = create_engine("sqlite://")
    BehaviorEvent.__table__.create(engine)
    ServerSession.__table__.create(engine)
    hour = datetime(2026, 9, 27, 11)

    def pv(visitor, minute=5, etype="pageview"):
        return {"event_type": etype, "visitor_id_hash": visitor,
                "occurred_at": hour + timedelta(minutes=minute)}

    def session(visitor, **flags):
        return {"day": date(2026, 9, 27), "visitor_id_hash": visitor, "started_at": hour,
                "ended_at": hour, "is_bot": False, "bot_score": 0, "is_internal": False, **flags}

    with engine.begin() as conn:
        conn.execute(BehaviorEvent.__table__.insert(), [
            pv("human"), pv("human", 6), pv("farm"), pv("farm", 7), pv("farm", 8),
            pv("staff"), pv(None), pv("human", etype="click"),
            pv("human", minute=75),  # вне часа
        ])
        conn.execute(ServerSession.__table__.insert(), [
            session("human", is_bot=False, is_internal=False),
            session("farm", is_bot=True, bot_score=90),
            session("staff", is_internal=True),
        ])
        human = conn.execute(alerts.human_pageviews_query(hour, hour + timedelta(hours=1))).scalar()
    engine.dispose()
    assert human == 3  # human x2 + посетитель без id; бот и внутренний исключены


@pytest.mark.parametrize(
    "params",
    [
        {"kind": "error", "msg": "Uncaught TypeError: Failed to fetch dynamically imported module: "
                                 "https://forecasteconomy.com/assets/LiveTicker-AbC123.js",
         "src": "https://forecasteconomy.com/assets/index-1.js"},
        {"kind": "rejection", "msg": "error loading dynamically imported module"},
        {"kind": "rejection", "msg": "Importing a module script failed."},
        {"kind": "error", "msg": "Unable to preload CSS for /assets/Chart-1.css"},
        {"kind": "error", "msg": "Loading chunk 12 failed."},
        {"kind": "rejection", "msg": "Cannot read properties of undefined (reading 'default')",
         "stack": "TypeError at https://forecasteconomy.com/assets/index-1.js:1"},
    ],
)
def test_stale_tab_chunk_errors_do_not_count(params):
    assert alerts.js_error_counts_for_alert(params) is False


def test_real_own_js_error_still_counts():
    assert alerts.js_error_counts_for_alert({
        "kind": "error", "msg": "Uncaught TypeError: x is not a function",
        "src": "https://forecasteconomy.com/assets/index-1.js"}) is True


def test_alert_cooldowns_are_per_kind_and_keyed_by_prefix(monkeypatch):
    assert alerts._alert_cooldown("js_error_spike") == 3 * 3600
    assert alerts._alert_cooldown("webmaster_sitemap_errors:example.com") == 24 * 3600
    assert alerts._alert_cooldown("webmaster_crawl_drop:example.com") == 24 * 3600
    assert alerts._alert_cooldown("traffic_drop") == alerts._MUTE_TTL
    seen = {}

    class StateRedis:
        async def set(self, key, _value, *, ex, nx):
            seen[key] = ex
            return True

    async def state_redis():
        return StateRedis()

    monkeypatch.setattr("app.core.cache.get_state_redis", state_redis)
    asyncio.run(alerts._muted("js_error_spike"))
    assert seen["fe:alerts:mute:js_error_spike"] == 3 * 3600


def test_js_spike_repeats_at_most_every_three_hours(monkeypatch):
    class StateRedis:
        keys: dict = {}

        async def set(self, key, _value, *, ex, nx):
            if key in self.keys:
                return None
            self.keys[key] = ex
            return True

        async def delete(self, key):
            self.keys.pop(key, None)

    redis = StateRedis()

    async def state_redis():
        return redis

    send = AsyncMock(return_value=True)
    monkeypatch.setattr("app.core.cache.get_state_redis", state_redis)
    monkeypatch.setattr("app.services.alerting.send_telegram", send)
    results = [asyncio.run(alerts._alert("js_error_spike", "22 за 15 минут")) for _ in range(4)]
    assert results == [True, False, False, False]
    assert send.await_count == 1
    assert redis.keys["fe:alerts:mute:js_error_spike"] == 3 * 3600


def _memory_cycles(monkeypatch, ratios):
    """Прогон цикла _check_host_pressure по ряду замеров; возвращает тексты сообщений."""
    class StateRedis:
        keys: dict = {}

        async def set(self, key, value, *, ex=None, nx=False):
            if nx and key in self.keys:
                return None
            self.keys[key] = value
            return True

        async def get(self, key):
            return self.keys.get(key)

        async def delete(self, key):
            self.keys.pop(key, None)

    redis = StateRedis()

    async def state_redis():
        return redis

    class Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def scalar(self, _statement):
            return 0

    sent = []

    async def send(text, **_kwargs):
        sent.append(text)
        return True

    values = iter(ratios)
    monkeypatch.setattr("app.core.cache.get_state_redis", state_redis)
    monkeypatch.setattr("app.services.alerting.send_telegram", send)
    monkeypatch.setattr("app.services.process_metrics.memory_pressure_ratio", lambda: next(values))
    monkeypatch.setattr("app.database.pool_stats", lambda _pool: {"size": 1, "checkedout": 0})
    monkeypatch.setattr(alerts, "analytics_session", Session)
    for _ in ratios:
        asyncio.run(alerts._check_host_pressure())
    return sent


def test_memory_episode_gives_one_alert_and_one_recovery(monkeypatch):
    # 94% держится много циклов, колеблется вокруг порога, затем падает.
    sent = _memory_cycles(monkeypatch, [0.94, 0.95, 0.99, 0.84, 0.88, 0.80, 0.76, 0.60, 0.50])
    assert len(sent) == 2
    assert "94%" in sent[0] and "порог 85%" in sent[0]
    assert "восстановилась" in sent[1]


def test_memory_new_episode_within_cooldown_is_silent(monkeypatch):
    # Всплеск, восстановление и тут же новый всплеск: второй «превышено» не сыпется.
    sent = _memory_cycles(monkeypatch, [0.9, 0.7, 0.9, 0.92, 0.7])
    assert [("восстановилась" in text) for text in sent] == [False, True]


def test_memory_pressure_uses_working_set_without_page_cache():
    from app.services.process_metrics import _inactive_file_bytes

    assert _inactive_file_bytes("anon 5\ninactive_file 1000\nactive_file 7\n") == 1000
    assert _inactive_file_bytes("total_inactive_file 42\n") == 42
    assert _inactive_file_bytes("anon 5\n") == 0
