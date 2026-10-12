"""Проба живой базы индекса в скрипте rebase-world-eurostat.py (круг 13): страны по очереди, короткий таймаут, честное сообщение."""
import importlib.util
from pathlib import Path

import pytest
import requests

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "rebase-world-eurostat.py"


@pytest.fixture()
def script():
    spec = importlib.util.spec_from_file_location("rebase_world_eurostat_script", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _multi_period_payload(obs: dict[int, float]) -> dict:
    """unit (I15, I21) x time (2023, 2024, 2025): ключ = unit * 3 + time."""
    return {
        "id": ["unit", "geo", "time"], "size": [2, 1, 3],
        "dimension": {
            "unit": {"category": {"index": {"I15": 0, "I21": 1}}},
            "geo": {"category": {"index": {"DE": 0}}},
            "time": {"category": {"index": {"2023": 0, "2024": 1, "2025": 2}}},
        },
        "value": {str(k): v for k, v in obs.items()},
    }


def test_live_base_is_judged_by_the_latest_period_not_by_the_whole_window(script):
    # I15 кончилась в 2023 (ключ 0), I21 идёт до 2025 (ключи 3, 4, 5): окно из трёх лет не должно делать I15 живой
    payload = _multi_period_payload({0: 99.0, 3: 100.0, 4: 101.0, 5: 102.0})
    assert script.live_units_at_latest_period(payload) == {"I21"}
    # у обеих баз есть данные в последнем периоде: живы обе (переход базы не закончен)
    both = _multi_period_payload({2: 99.0, 5: 102.0})
    assert script.live_units_at_latest_period(both) == {"I15", "I21"}
    assert script.live_units_at_latest_period(_multi_period_payload({})) == set()


def _payload(geo: str, with_obs: bool) -> dict:
    """Минимальный JSON-stat: измерения unit (I15, I21) и geo, одно наблюдение у I21 или ни одного."""
    return {
        "id": ["unit", "geo", "time"], "size": [2, 1, 1],
        "dimension": {
            "unit": {"category": {"index": {"I15": 0, "I21": 1}}},
            "geo": {"category": {"index": {geo: 0}}},
            "time": {"category": {"index": {"2026-08": 0}}},
        },
        "value": {"1": 101.0} if with_obs else {},
    }


class _Resp:
    def __init__(self, data):
        self._data = data

    def raise_for_status(self):
        return None

    def json(self):
        return self._data


def test_probe_moves_to_next_country_when_big_three_have_no_observations(script, monkeypatch):
    calls = []

    def fake_get(url, timeout):
        geo = url.split("geo=")[1].split("&")[0]
        assert "lastTimePeriod=3" in url
        calls.append((geo, timeout))
        return _Resp(_payload(geo, with_obs=(geo == "ES")))

    monkeypatch.setattr(script.requests, "get", fake_get)
    members, live = script.probe_units("sts_rb_q")
    assert [g for g, _ in calls] == ["DE", "FR", "IT", "ES"]
    assert live == {"I21"} and "I15" in members
    assert all(t == script.PROBE_TIMEOUT_S == 25 for _, t in calls)
    assert script.PROBE_PERIODS == 3


def test_probe_says_no_observations_when_nobody_has_any_and_gives_up_when_source_is_silent(script, monkeypatch):
    monkeypatch.setattr(script.requests, "get", lambda url, timeout: _Resp(_payload("DE", with_obs=False)))
    with pytest.raises(RuntimeError, match="нет наблюдений"):
        script.probe_units("sts_x")

    attempts = []

    def silent(url, timeout):
        attempts.append(url)
        raise requests.ReadTimeout("cold")

    monkeypatch.setattr(script.requests, "get", silent)
    with pytest.raises(RuntimeError, match="проба не удалась"):
        script.probe_units("sts_y")
    assert len(attempts) == 3 * script.PROBE_ATTEMPTS          # три страны подряд без ответа, остальных не ждём
