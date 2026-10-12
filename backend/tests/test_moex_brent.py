"""Коннектор живой нефти Brent с Мосбиржи (круг 13, R-BRENT): образцы ответа ISS от 12.10.2026, флаг, резерв на EIA.

Флаг `moex_brent_live_enabled` по умолчанию выключен: до договора с биржей на сайте остаётся недельный спот EIA.
"""
from __future__ import annotations

import asyncio
import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from app.config import Settings, settings
from app.services.ticker_sources import moex_brent
from app.tasks import ticker_worker

FIX = Path(__file__).parent / "fixtures" / "moex_brent"


def _load(name: str) -> dict:
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def _utc(y, mo, d, h, mi) -> datetime:
    return datetime(y, mo, d, h, mi, tzinfo=timezone.utc)


def test_flag_off_by_default():
    assert Settings().moex_brent_live_enabled is False
    assert settings.moex_brent_live_enabled is False


def test_nearest_contract_skips_expiry_day_and_other_assets():
    payload = _load("securities_list_2026-10-12.json")
    assert moex_brent.pick_nearest_contract(payload, date(2026, 10, 12)) == "BRX6"
    # В день экспирации ноябрьского контракта берём следующий.
    assert moex_brent.pick_nearest_contract(payload, date(2026, 11, 2)) == "BRZ6"
    assert moex_brent.pick_nearest_contract(payload, date(2027, 6, 1)) is None


def test_live_snapshot_from_saved_sample():
    # Сессия идёт: значение биржи 20:17:34 МСК, момент проверки 20:33 МСК (17:33 UTC).
    snap = moex_brent.build_snapshot(_load("BRX6_live_2026-10-12.json"), now=_utc(2026, 10, 12, 17, 33))
    assert snap is not None
    assert snap.code == "brent" and snap.source == "MOEX"
    assert snap.price == 106.57 and snap.market_open is True
    # Изменение за день: к предыдущей расчётной цене 104,62, а не к предыдущей сделке.
    assert snap.change_pct == pytest.approx(1.86, abs=0.01)
    assert snap.delay_minutes == 15
    assert snap.contract == "BR-11.26"
    d = snap.as_dict()
    assert d["source_kind"] == "market"
    assert d["as_of"] == "2026-10-12T17:17:34+00:00"
    assert d["delay_minutes"] == 15 and d["contract"] == "BR-11.26"


def test_closed_market_is_dated_session_value():
    # Выходные: последняя сессия в понедельник, проверка в субботу.
    snap = moex_brent.build_snapshot(_load("BRX6_live_2026-10-12.json"), now=_utc(2026, 10, 17, 9, 0))
    assert snap is not None
    assert snap.market_open is False
    assert snap.as_of_date == date(2026, 10, 12)
    assert snap.as_dict()["as_of"] == "2026-10-12"


def test_too_old_or_empty_gives_no_snapshot():
    sample = _load("BRX6_live_2026-10-12.json")
    assert moex_brent.build_snapshot(sample, now=_utc(2026, 10, 25, 9, 0)) is None
    empty = json.loads(json.dumps(sample))
    empty["marketdata"]["data"] = []
    assert moex_brent.build_snapshot(empty, now=_utc(2026, 10, 12, 17, 33)) is None
    no_price = json.loads(json.dumps(sample))
    cols = no_price["marketdata"]["columns"]
    row = no_price["marketdata"]["data"][0]
    row[cols.index("LAST")] = None
    row[cols.index("SETTLEPRICE")] = None
    assert moex_brent.build_snapshot(no_price, now=_utc(2026, 10, 12, 17, 33)) is None


def test_no_last_trade_uses_settle_price_as_closed_value():
    sample = _load("BRX6_live_2026-10-12.json")
    cols = sample["marketdata"]["columns"]
    row = sample["marketdata"]["data"][0]
    row[cols.index("LAST")] = None
    snap = moex_brent.build_snapshot(sample, now=_utc(2026, 10, 12, 17, 33))
    assert snap is not None and snap.price == 106.62 and snap.market_open is False


def test_configured_delay_is_a_floor_and_rounded_up():
    sample = _load("BRX6_live_2026-10-12.json")
    snap = moex_brent.build_snapshot(sample, now=_utc(2026, 10, 12, 17, 33), min_delay_minutes=20)
    assert snap.delay_minutes == 20
    cols = sample["marketdata"]["columns"]
    row = sample["marketdata"]["data"][0]
    row[cols.index("SYSTIME")] = "2026-10-12 20:47:35"  # факт 30 минут
    snap = moex_brent.build_snapshot(sample, now=_utc(2026, 10, 12, 17, 50))
    assert snap.delay_minutes == 30


class _Resp:
    def __init__(self, payload):
        self._p = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._p


def test_fetch_brent_two_requests_and_failure_returns_none(monkeypatch):
    moex_brent._contracts_cache = None
    calls = []

    async def fake_get(self, url, **kw):
        calls.append(url)
        if "BRX6" in url:
            return _Resp(_load("BRX6_live_2026-10-12.json"))
        return _Resp(_load("securities_list_2026-10-12.json"))

    import httpx
    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    monkeypatch.setattr(moex_brent, "utcnow", lambda: _utc(2026, 10, 12, 17, 33))
    snap = asyncio.run(moex_brent.fetch_brent())
    assert snap is not None and snap.price == 106.57
    assert len(calls) == 2
    # Список контрактов кэшируется: второй тик — один запрос.
    asyncio.run(moex_brent.fetch_brent())
    assert len(calls) == 3

    async def boom(self, url, **kw):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(httpx.AsyncClient, "get", boom)
    assert asyncio.run(moex_brent.fetch_brent()) is None


def test_worker_flag_off_never_calls_exchange(monkeypatch):
    monkeypatch.setattr(settings, "moex_brent_live_enabled", False)

    async def must_not_call(*a, **k):
        raise AssertionError("биржа вызвана при выключенном флаге")

    monkeypatch.setattr(moex_brent, "fetch_brent", must_not_call)
    assert asyncio.run(ticker_worker._moex_brent_live()) is None


def test_worker_flag_on_returns_snapshot_and_falls_back(monkeypatch):
    monkeypatch.setattr(settings, "moex_brent_live_enabled", True)
    snap = moex_brent.build_snapshot(_load("BRX6_live_2026-10-12.json"), now=_utc(2026, 10, 12, 17, 33))

    async def ok(delay):
        return snap

    monkeypatch.setattr(moex_brent, "fetch_brent", ok)
    assert asyncio.run(ticker_worker._moex_brent_live()) is snap

    async def broken(delay):
        raise RuntimeError("iss")

    monkeypatch.setattr(moex_brent, "fetch_brent", broken)
    assert asyncio.run(ticker_worker._moex_brent_live()) is None


def test_exchange_brent_goes_stale_in_days_not_in_twelve():
    from app.api.ticker import add_freshness

    now = _utc(2026, 10, 20, 12, 0)
    eia = {"code": "brent", "source": "EIA", "as_of_date": "2026-10-13"}
    add_freshness(eia, now)
    assert eia["stale"] is False  # 7 суток: недельный выпуск EIA
    moex = {"code": "brent", "source": "MOEX", "source_kind": "market", "as_of_date": "2026-10-13"}
    add_freshness(moex, now)
    assert moex["stale"] is True


def _run_job(monkeypatch, brent_live):
    """ticker_pull_job с подменёнными источниками; возвращает то, что записано в Redis."""
    from app.services.ticker_sources import TickerSnapshot, utcnow

    eia = TickerSnapshot(
        code="brent", price=93.26, change_pct=-0.5, market_open=False, fetched_at=utcnow(),
        source="EIA", as_of_date=date(2026, 10, 6),
    )
    written: dict[str, str] = {}

    class _Pipe:
        def set(self, key, val, ex=None):
            written[key] = val

        async def execute(self):
            return None

    class _Redis:
        def pipeline(self):
            return _Pipe()

    async def empty():
        return []

    async def series(indicator_code, ticker_code, source):
        return eia if indicator_code == "brent" else None

    async def live():
        return brent_live

    async def get_redis():
        return _Redis()

    monkeypatch.setattr(ticker_worker, "moex_fetch_all", empty)
    monkeypatch.setattr(ticker_worker, "binance_fetch_all", empty)
    monkeypatch.setattr(ticker_worker, "_series_db_snapshot", series)
    monkeypatch.setattr(ticker_worker, "_moex_brent_live", live)
    monkeypatch.setattr(ticker_worker, "get_redis", get_redis)
    asyncio.run(ticker_worker.ticker_pull_job())
    return json.loads(written["ticker:brent"])


def test_job_exchange_brent_replaces_eia_and_falls_back(monkeypatch):
    snap = moex_brent.build_snapshot(_load("BRX6_live_2026-10-12.json"), now=_utc(2026, 10, 12, 17, 33))
    out = _run_job(monkeypatch, snap)
    assert out["source"] == "MOEX" and out["delay_minutes"] == 15 and out["market_open"] is True
    out = _run_job(monkeypatch, None)
    assert out["source"] == "EIA" and out["as_of_date"] == "2026-10-06"
