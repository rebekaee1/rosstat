"""Аналитический пул изолирован от витрины."""
from app.database import analytics_engine, engine, pool_stats
from app.config import settings


def test_analytics_engine_is_separate():
    assert analytics_engine is not engine
    assert settings.analytics_db_pool_size == 2
    assert settings.db_statement_timeout_ms == 30_000
    assert settings.analytics_db_statement_timeout_ms == 60_000


def test_pool_stats_shape():
    public = pool_stats("public")
    analytics = pool_stats("analytics")
    assert set(public) == {"checkedout", "overflow", "size"}
    assert set(analytics) == {"checkedout", "overflow", "size"}
    # Пока никто не checkout'ит — public не исчерпан (инвариант витрины).
    assert public["checkedout"] == 0


def test_bi_routes_do_not_hold_public_db_depends():
    """Дашборд/срезы не берут get_db на время расчёта — иначе витрина ждёт пул."""
    import inspect

    from app.api.admin_bi import bi_dashboard, require_admin, slices_query

    assert "db" not in inspect.signature(require_admin).parameters
    assert "db" not in inspect.signature(bi_dashboard).parameters
    assert "db" not in inspect.signature(slices_query).parameters
