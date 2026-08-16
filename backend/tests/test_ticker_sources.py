"""Регрессии для live-тикера (MOEX ISS FX + ряды карточек для Brent/золота).

Цель — зафиксировать поведение `fetch_all` / `ticker_pull_job`: источники
тянутся конкурентно, одно падение FX не обнуляет остальные снапшоты, а
Brent/золото всегда берутся из рядов карточек (не с MOEX), иначе лента
противоречит витрине.
"""
from __future__ import annotations

import asyncio
import json
from datetime import date

import pytest

from app.services.ticker_sources import TickerSnapshot, moex_iss, utcnow


def _run(coro):
    return asyncio.run(coro)


def test_fetch_all_uses_moex_when_available(monkeypatch):
    async def fake_fx(client, code, secid):
        return 90.0, 0.5

    cbr_calls = {"n": 0}

    async def fake_cbr(client):
        cbr_calls["n"] += 1
        return {}

    monkeypatch.setattr(moex_iss, "_fetch_fx_one", fake_fx)
    monkeypatch.setattr(moex_iss, "_fetch_cbr_daily", fake_cbr)

    snaps = _run(moex_iss.fetch_all())
    by_code = {s.code: s for s in snaps}

    assert {"usd-rub-live", "eur-rub-live", "cny-rub-live"} <= set(by_code)
    assert "brent" not in by_code
    assert "gold-rub-live" not in by_code
    assert all(by_code[c].source == "MOEX" for c in ("usd-rub-live", "eur-rub-live", "cny-rub-live"))
    # CBR не дёргается, когда MOEX отдал все FX.
    assert cbr_calls["n"] == 0


def test_fetch_all_falls_back_to_cbr_when_moex_fx_dead(monkeypatch):
    async def dead_fx(client, code, secid):
        return None, None

    async def fake_cbr(client):
        # Ключи = CBR Valute ID из _FX_INSTRUMENTS.
        return {"R01235": (78.0, 0.1), "R01239": (85.0, -0.2), "R01375": (10.9, 0.0)}

    monkeypatch.setattr(moex_iss, "_fetch_fx_one", dead_fx)
    monkeypatch.setattr(moex_iss, "_fetch_cbr_daily", fake_cbr)

    snaps = _run(moex_iss.fetch_all())
    by_code = {s.code: s for s in snaps}

    assert by_code["usd-rub-live"].price == 78.0
    assert all(by_code[c].source == "ЦБ РФ" for c in ("usd-rub-live", "eur-rub-live", "cny-rub-live"))
    assert all(by_code[c].market_open is False for c in ("usd-rub-live", "eur-rub-live", "cny-rub-live"))


def test_fetch_all_survives_fx_exceptions(monkeypatch):
    """Падение одного FX-запроса не должно ронять весь тик."""
    async def mixed_fx(client, code, secid):
        if code == "eur-rub-live":
            raise RuntimeError("MOEX EUR down")
        return 90.0, 0.5

    async def fake_cbr(client):
        return {"R01239": (85.0, -0.2)}

    monkeypatch.setattr(moex_iss, "_fetch_fx_one", mixed_fx)
    monkeypatch.setattr(moex_iss, "_fetch_cbr_daily", fake_cbr)

    snaps = _run(moex_iss.fetch_all())
    by_code = {s.code: s for s in snaps}

    assert by_code["usd-rub-live"].source == "MOEX"
    assert by_code["eur-rub-live"].source == "ЦБ РФ"
    assert by_code["eur-rub-live"].price == 85.0


def test_pull_job_uses_card_series_for_brent_and_gold(monkeypatch):
    """Brent/золото всегда из рядов карточек; live-MOEX для них отбрасывается."""
    from app.tasks import ticker_worker

    usd = TickerSnapshot(
        code="usd-rub-live", price=78.0, change_pct=0.1,
        market_open=False, fetched_at=utcnow(), source="ЦБ РФ",
    )
    # Легаси: если MOEX всё же отдал brent — воркер обязан выкинуть.
    moex_brent = TickerSnapshot(
        code="brent", price=88.68, change_pct=0.5,
        market_open=True, fetched_at=utcnow(), source="MOEX",
    )
    brent_card = TickerSnapshot(
        code="brent", price=93.26, change_pct=-0.5,
        market_open=False, fetched_at=utcnow(), source="EIA",
        as_of_date=date(2026, 8, 14),
    )
    gold_card = TickerSnapshot(
        code="gold-rub-live", price=11886.6, change_pct=0.1,
        market_open=False, fetched_at=utcnow(), source="Банк России",
        as_of_date=date(2026, 8, 15),
    )

    async def fake_moex():
        return [usd, moex_brent]

    async def fake_binance():
        return []

    async def fake_series(indicator_code, ticker_code, source):
        if indicator_code == "brent":
            return brent_card
        if indicator_code == "gold-price":
            return gold_card
        return None

    written: dict[str, str] = {}

    class _FakePipe:
        def set(self, key, val, ex=None):
            written[key] = val

        async def execute(self):
            return None

    class _FakeRedis:
        def pipeline(self):
            return _FakePipe()

    async def fake_get_redis():
        return _FakeRedis()

    monkeypatch.setattr(ticker_worker, "moex_fetch_all", fake_moex)
    monkeypatch.setattr(ticker_worker, "binance_fetch_all", fake_binance)
    monkeypatch.setattr(ticker_worker, "_series_db_snapshot", fake_series)
    monkeypatch.setattr(ticker_worker, "get_redis", fake_get_redis)

    _run(ticker_worker.ticker_pull_job())

    assert "ticker:usd-rub-live" in written
    brent = json.loads(written["ticker:brent"])
    gold = json.loads(written["ticker:gold-rub-live"])
    assert brent["price"] == 93.26
    assert brent["source"] == "EIA"
    assert brent["market_open"] is False
    assert brent["as_of_date"] == "2026-08-14"
    assert gold["price"] == 11886.6
    assert gold["source"] == "Банк России"
    assert gold["as_of_date"] == "2026-08-15"


def test_snapshot_as_dict_omits_as_of_when_none():
    snap = TickerSnapshot(
        code="btc-usd", price=100.0, change_pct=1.0,
        market_open=True, fetched_at=utcnow(), source="Binance",
    )
    d = snap.as_dict()
    assert "as_of_date" not in d
    assert d["market_open"] is True


def test_fetch_all_survives_all_fx_failures(monkeypatch):
    """Если весь FX упал — fetch_all возвращает пустой список, не исключение."""
    async def boom_fx(client, code, secid):
        raise RuntimeError("connection reset")

    async def empty_cbr(client):
        return {}

    monkeypatch.setattr(moex_iss, "_fetch_fx_one", boom_fx)
    monkeypatch.setattr(moex_iss, "_fetch_cbr_daily", empty_cbr)

    snaps = _run(moex_iss.fetch_all())
    assert snaps == []
