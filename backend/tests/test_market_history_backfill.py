"""Self-healing глубокой истории рыночных рядов (2026-08-05).

Карточки btc-usd/eth-usd стартовали с 2022 (backfill 1500 дней), brent — с 2015.
Парсеры теперь дозапрашивают окно [`backfill_from`, earliest) когда самая ранняя
точка БД позже желаемого пола; pre-Binance сегмент крипты добирается с Coinbase.
"""

from __future__ import annotations

import asyncio
from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from app.services import binance_btcusdt_parser as binance_mod
from app.services import brent_fred_parser as brent_mod


def _db_with_earliest(earliest: date | None):
    result_proxy = MagicMock()
    result_proxy.scalar.return_value = earliest
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result_proxy)
    return db


def _run(parser, db, code, cfg):
    indicator = SimpleNamespace(id=1, code=code)
    fetch_log = SimpleNamespace(error_message=None)
    return asyncio.run(parser._fetch_and_parse(db, indicator, cfg, fetch_log))


def test_binance_parser_backfills_pre_listing_history_from_coinbase(monkeypatch):
    binance_calls: list[tuple[date, date]] = []
    coinbase_calls: list[tuple[date, date]] = []

    def _fake_binance(symbol, start, end):
        binance_calls.append((start, end))
        if start < date(2022, 1, 1):
            # Binance отдаёт с даты листинга BTCUSDT
            return [(date(2017, 8, 17), 4285.0), (date(2022, 4, 12), 40000.0)]
        return [(date(2026, 8, 4), 100000.0)]

    def _fake_coinbase(symbol, start, end):
        assert symbol == "BTC-USD"
        coinbase_calls.append((start, end))
        # overlap на 2017-08-17 — должен проиграть Binance
        return [(date(2015, 7, 20), 280.0), (date(2017, 8, 17), 9999.0)]

    monkeypatch.setattr(binance_mod, "_fetch_binance_window", _fake_binance)
    monkeypatch.setattr(binance_mod, "_fetch_coinbase_window", _fake_coinbase)

    cfg = {
        "binance_symbol": "BTCUSDT",
        "backfill_from": "2015-07-20",
        "pre_binance": {"provider": "coinbase", "symbol": "BTC-USD"},
    }
    points, _ = _run(
        binance_mod.BinanceBtcUsdtParser(),
        _db_with_earliest(date(2022, 4, 13)),
        "btc-usd",
        cfg,
    )

    assert points[0] == (date(2015, 7, 20), 280.0)
    assert points[-1] == (date(2026, 8, 4), 100000.0)
    # Binance — канон на overlap
    assert (date(2017, 8, 17), 4285.0) in points
    assert (date(2017, 8, 17), 9999.0) not in points
    # история + свежий хвост
    assert binance_calls[0][0] >= date(2026, 7, 1)  # recent window
    assert (date(2015, 7, 20), date(2022, 4, 13)) in binance_calls
    # coinbase только до первой даты Binance
    assert coinbase_calls == [(date(2015, 7, 20), date(2017, 8, 17))]


def test_binance_parser_without_pre_source_heals_from_binance_only(monkeypatch):
    binance_calls: list[tuple[date, date]] = []

    def _fake_binance(symbol, start, end):
        binance_calls.append((start, end))
        return [(start, 1.0)]

    def _no_coinbase(symbol, start, end):  # pragma: no cover — не должно зваться
        raise AssertionError("coinbase не должен вызываться без pre_binance")

    monkeypatch.setattr(binance_mod, "_fetch_binance_window", _fake_binance)
    monkeypatch.setattr(binance_mod, "_fetch_coinbase_window", _no_coinbase)

    cfg = {"binance_symbol": "SOLUSDT", "backfill_from": "2020-08-11"}
    points, _ = _run(
        binance_mod.BinanceBtcUsdtParser(),
        _db_with_earliest(date(2022, 5, 17)),
        "sol-usd",
        cfg,
    )

    assert (date(2020, 8, 11), date(2022, 5, 17)) in binance_calls
    assert points[0][0] >= date(2020, 8, 11)


def test_binance_parser_no_heal_when_history_complete(monkeypatch):
    binance_calls: list[tuple[date, date]] = []

    def _fake_binance(symbol, start, end):
        binance_calls.append((start, end))
        return [(start, 1.0)]

    monkeypatch.setattr(binance_mod, "_fetch_binance_window", _fake_binance)

    cfg = {"binance_symbol": "BTCUSDT", "backfill_from": "2015-07-20"}
    points, _ = _run(
        binance_mod.BinanceBtcUsdtParser(),
        _db_with_earliest(date(2015, 7, 20)),
        "btc-usd",
        cfg,
    )

    # только свежее окно, исторический дозапрос не нужен
    assert len(binance_calls) == 1
    assert binance_calls[0][0] >= date.today() - timedelta(days=20)
    assert len(points) == 1


def test_brent_parser_heals_history_window(monkeypatch):
    yahoo_calls: list[tuple[date, date]] = []

    def _fake_yahoo(symbol, from_date, to_date):
        yahoo_calls.append((from_date, to_date))
        return {"chart": {"result": [{"timestamp": [], "indicators": {"quote": [{"close": []}]}}]}}

    monkeypatch.setattr(brent_mod, "_fetch_yahoo", _fake_yahoo)

    cfg = {"yahoo_symbol": "BZ=F", "backfill_from": "2007-07-30"}
    _run(
        brent_mod.BrentDailyFredParser(),
        _db_with_earliest(date(2015, 1, 2)),
        "brent",
        cfg,
    )

    assert len(yahoo_calls) == 2
    assert (date(2007, 7, 30), date(2015, 1, 2)) in yahoo_calls


def test_brent_parser_single_window_when_history_complete(monkeypatch):
    yahoo_calls: list[tuple[date, date]] = []

    def _fake_yahoo(symbol, from_date, to_date):
        yahoo_calls.append((from_date, to_date))
        return {"chart": {"result": [{"timestamp": [], "indicators": {"quote": [{"close": []}]}}]}}

    monkeypatch.setattr(brent_mod, "_fetch_yahoo", _fake_yahoo)

    cfg = {"yahoo_symbol": "BZ=F", "backfill_from": "2007-07-30"}
    _run(
        brent_mod.BrentDailyFredParser(),
        _db_with_earliest(date(2007, 7, 30)),
        "brent",
        cfg,
    )

    assert len(yahoo_calls) == 1
