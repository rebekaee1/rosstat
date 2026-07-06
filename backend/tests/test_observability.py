"""Волна 1 (наблюдаемость): readiness (Н-1), staleness-SLA (Н-3),
5xx-счётчики (Н-13).

Всё герметично: auth_env (SQLite + fakeredis) для readiness, чистые функции —
без окружения.
"""

from datetime import date, timedelta

from fastapi.testclient import TestClient

from app.tasks.scheduler import STALENESS_SLA_DAYS, find_stale


# ---------------------------------------------------------------------------
# Н-1: /health/live тривиален, /health/ready проверяет зависимости
# ---------------------------------------------------------------------------

def test_health_live_trivial(client):
    assert client.get("/api/v1/health").json() == {"status": "ok"}
    assert client.get("/api/v1/health/live").json() == {"status": "ok"}


def test_health_ready_ok(auth_client):
    r = auth_client.get("/api/v1/health/ready")
    assert r.status_code == 200
    body = r.json()
    assert body["checks"]["db"] == "ok"
    assert body["checks"]["cache_redis"] == "ok"
    assert body["checks"]["state_redis"] == "ok"
    # свежих ETL-прогонов в пустой БД нет — это деградация, но не 503
    assert body["checks"]["etl_last_ok_age_hours"] == "never"


def test_health_ready_503_on_state_redis_down(auth_env, monkeypatch):
    """Отказ state-Redis (сессии, Н-12) — жёсткая зависимость: 503."""
    import app.core.cache as cache_mod

    class _Broken:
        async def ping(self):
            raise ConnectionError("down")

        async def aclose(self):  # close_redis() при shutdown TestClient
            pass

    monkeypatch.setattr(cache_mod, "_state_redis", _Broken())
    with TestClient(auth_env["app"]) as tc:
        r = tc.get("/api/v1/health/ready")
    assert r.status_code == 503
    assert r.json()["checks"]["state_redis"] == "fail"


# ---------------------------------------------------------------------------
# Н-3: staleness-SLA по частоте
# ---------------------------------------------------------------------------

def test_find_stale_respects_frequency_sla():
    today = date(2026, 7, 6)
    rows = [
        ("usd-rub", "daily", today - timedelta(days=2)),        # свежий
        ("gold-price", "daily", today - timedelta(days=10)),    # stale (SLA 7)
        ("cpi", "monthly", today - timedelta(days=50)),         # свежий (SLA 75)
        ("gdp-nominal", "quarterly", today - timedelta(days=200)),  # stale (SLA 150)
        ("empty-code", "monthly", None),                        # без точек — пропуск
        ("key-rate", "irregular", today - timedelta(days=300)),  # дефолт 550 — свежий
    ]
    stale = dict(find_stale(rows, today))
    assert set(stale) == {"gold-price", "gdp-nominal"}
    assert stale["gold-price"] == 10


def test_staleness_sla_covers_known_frequencies():
    assert set(STALENESS_SLA_DAYS) == {"daily", "weekly", "monthly", "quarterly", "annual"}
    # алерт-SLA не строже витринного (иначе страница честнее оператора)
    from app.services.seo_today import _STALE_AFTER_DAYS
    for freq, page_sla in _STALE_AFTER_DAYS.items():
        assert STALENESS_SLA_DAYS[freq] >= page_sla


# ---------------------------------------------------------------------------
# Н-13: серверные счётчики статусов
# ---------------------------------------------------------------------------

def test_http_status_counters_increment(client):
    from app.main import HttpStatusCounterMiddleware as M

    before_2xx = M.counters["2xx"]
    before_4xx = M.counters["4xx"]
    client.get("/api/v1/health")
    client.get("/api/v1/no-such-route")
    assert M.counters["2xx"] == before_2xx + 1
    assert M.counters["4xx"] == before_4xx + 1
