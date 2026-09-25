"""Пороги алертов: шум JS, эпизод памяти, тишина сбора без ложного таймаута."""

from datetime import datetime, timedelta

from app.services.analytics_alerts import (
    COLLECTION_SILENCE_AFTER,
    MEMORY_ALERT_RATIO,
    MEMORY_CLEAR_RATIO,
    collection_silence_due,
    js_error_counts_for_alert,
    memory_pressure_episode,
    _is_statement_timeout,
)


NOW = datetime(2026, 9, 25, 12, 0, 0)


def test_js_error_ignores_resource_and_metrika():
    assert js_error_counts_for_alert({"kind": "error", "msg": "x is not defined"})
    assert js_error_counts_for_alert({"kind": "rejection", "msg": "fail", "stack": "Error\n at /app.js:1"})
    assert not js_error_counts_for_alert({"kind": "resource", "src": "https://forecasteconomy.com/assets/a.js"})
    assert not js_error_counts_for_alert({
        "kind": "error",
        "src": "https://mc.yandex.ru/metrika/tag.js",
        "msg": "Script error.",
    })
    assert not js_error_counts_for_alert({
        "kind": "rejection",
        "stack": "at https://yastatic.net/s3/home/ad.js:1:1",
    })
    assert not js_error_counts_for_alert(None)
    assert not js_error_counts_for_alert({"msg": "legacy without kind"})


def test_memory_pressure_is_one_episode_not_a_metronome():
    assert MEMORY_ALERT_RATIO > 0.85
    assert MEMORY_CLEAR_RATIO < MEMORY_ALERT_RATIO
    assert memory_pressure_episode(0.99, sticky=False) == "alert"
    assert memory_pressure_episode(0.99, sticky=True) == "hold"
    assert memory_pressure_episode(0.88, sticky=True) == "hold"
    assert memory_pressure_episode(0.79, sticky=True) == "clear"
    assert memory_pressure_episode(0.93, sticky=False) == "alert"
    assert memory_pressure_episode(None, sticky=False) == "hold"


def test_collection_silence_threshold_and_timeout():
    assert COLLECTION_SILENCE_AFTER == timedelta(minutes=45)
    fresh = NOW - timedelta(minutes=10)
    stale = NOW - timedelta(minutes=50)
    assert not collection_silence_due(
        last_seen=fresh, now=NOW, prev_hour_pageviews=20, probe_failed=False,
    )
    assert collection_silence_due(
        last_seen=stale, now=NOW, prev_hour_pageviews=20, probe_failed=False,
    )
    assert not collection_silence_due(
        last_seen=stale, now=NOW, prev_hour_pageviews=20, probe_failed=True,
    )
    assert not collection_silence_due(
        last_seen=stale, now=NOW, prev_hour_pageviews=3, probe_failed=False,
    )
    assert collection_silence_due(
        last_seen=None, now=NOW, prev_hour_pageviews=20, probe_failed=False,
    )
    assert not collection_silence_due(
        last_seen=None, now=NOW, prev_hour_pageviews=20, probe_failed=True,
    )

    class QueryCanceledError(Exception):
        pass

    timeout = RuntimeError("wrap")
    timeout.__cause__ = QueryCanceledError("canceling statement due to statement timeout")
    assert _is_statement_timeout(timeout)
    assert not _is_statement_timeout(RuntimeError("connection refused"))
