"""Partner Statistics → partner_revenue: parse / fetch / mart."""
from __future__ import annotations

import asyncio
import os
import tempfile
from datetime import date, datetime, timezone

_SAMPLE_PAYLOAD = {
    "data": {
        "points": [
            {
                "dimensions": {"date": ["2026-07-10"]},
                "measures": [{"shows": 1200, "hits": 18, "partner_wo_nds": 12.34}],
            },
            {
                "dimensions": {"date": ["2026-07-11"]},
                "measures": [{"shows": 900, "hits": 11, "partner_wo_nds": 8.5}],
            },
        ]
    }
}


def test_parse_day_points():
    from app.services.yandex_partner_stats import _parse_day_points

    rows = _parse_day_points(_SAMPLE_PAYLOAD)
    assert len(rows) == 2
    assert rows[0]["day"] == date(2026, 7, 10)
    assert rows[0]["shows"] == 1200
    assert rows[0]["hits"] == 18
    assert rows[0]["revenue_rub"] == 12.34
    assert rows[1]["revenue_rub"] == 8.5


def test_parse_skips_bad_dates():
    from app.services.yandex_partner_stats import _parse_day_points

    rows = _parse_day_points({
        "data": {
            "points": [
                {"dimensions": {"date": ["not-a-date"]}, "measures": [{"shows": 1}]},
                {"dimensions": {}, "measures": [{"shows": 1}]},
            ]
        }
    })
    assert rows == []


def _with_temp_db(coro_factory):
    from sqlalchemy import create_engine
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.models import Base

    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        sync_engine = create_engine(f"sqlite:///{db_path}")
        Base.metadata.create_all(sync_engine)
        sync_engine.dispose()

        async def _main():
            engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
            maker = async_sessionmaker(engine, expire_on_commit=False)
            try:
                return await coro_factory(maker)
            finally:
                await engine.dispose()

        return asyncio.run(_main())
    finally:
        try:
            os.unlink(db_path)
        except OSError:
            pass


def test_mart_partner_revenue(monkeypatch):
    """Mart поверх ORM-строк (upsert — PostgreSQL dialect, в SQLite не гоняем)."""
    from app.models import PartnerRevenue
    from app.services.analytics_marts import mart_partner_revenue

    monkeypatch.setattr(
        "app.services.yandex_partner_stats.partner_configured",
        lambda: True,
    )

    async def scenario(maker):
        async with maker() as db:
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            db.add_all([
                PartnerRevenue(
                    day=date(2026, 7, 10), shows=100, hits=2,
                    revenue_rub=5.0, synced_at=now,
                ),
                PartnerRevenue(
                    day=date(2026, 7, 11), shows=200, hits=4,
                    revenue_rub=7.5, synced_at=now,
                ),
            ])
            await db.commit()
            mart = await mart_partner_revenue(db, 30)
            assert mart["configured"] is True
            assert mart["connected"] is True
            assert mart["total_shows"] == 300
            assert mart["total_hits"] == 6
            assert mart["total_revenue_rub"] == 12.5
            assert len(mart["days"]) == 2
            assert mart["note"] is None
        return True

    assert _with_temp_db(scenario) is True


def test_fetch_requires_token(monkeypatch):
    from app.services import yandex_partner_stats as mod

    monkeypatch.setattr(mod.settings, "yandex_partner_token", "")
    monkeypatch.setattr(mod.settings, "direct_api_token", "")

    assert asyncio.run(mod.fetch_partner_stats()) == []


def test_fetch_parses_http(monkeypatch):
    from app.services import yandex_partner_stats as mod

    monkeypatch.setattr(mod.settings, "yandex_partner_token", "test-token")

    class _Resp:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return _SAMPLE_PAYLOAD

    class _Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return None

        async def get(self, *a, **k):
            return _Resp()

    monkeypatch.setattr(mod.httpx, "AsyncClient", _Client)
    rows = asyncio.run(mod.fetch_partner_stats(period="7days"))
    assert len(rows) == 2
    assert rows[0]["revenue_rub"] == 12.34
