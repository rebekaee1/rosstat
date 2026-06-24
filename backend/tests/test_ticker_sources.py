"""Регрессии для live-тикера (MOEX ISS + CBR fallback).

Цель — зафиксировать поведение `fetch_all`, из-за которого тикер «мигал» на
проде: источники тянутся конкурентно и одно падение (brent/gold/MOEX FX) не
обнуляет остальные снапшоты, а недоступный MOEX FX подменяется курсом ЦБ.
"""
from __future__ import annotations

import asyncio

import pytest

from app.services.ticker_sources import moex_iss


def _run(coro):
    return asyncio.run(coro)


def test_fetch_all_uses_moex_when_available(monkeypatch):
    async def fake_fx(client, code, secid):
        return 90.0, 0.5

    async def fake_brent(client):
        return moex_iss.TickerSnapshot(
            code="brent", price=76.0, change_pct=-0.1,
            market_open=True, fetched_at=moex_iss.utcnow(), source="MOEX",
        )

    async def fake_gold(client):
        return moex_iss.TickerSnapshot(
            code="gold-rub-live", price=9000.0, change_pct=0.2,
            market_open=True, fetched_at=moex_iss.utcnow(), source="MOEX",
        )

    cbr_calls = {"n": 0}

    async def fake_cbr(client):
        cbr_calls["n"] += 1
        return {}

    monkeypatch.setattr(moex_iss, "_fetch_fx_one", fake_fx)
    monkeypatch.setattr(moex_iss, "_fetch_brent", fake_brent)
    monkeypatch.setattr(moex_iss, "_fetch_gold", fake_gold)
    monkeypatch.setattr(moex_iss, "_fetch_cbr_daily", fake_cbr)

    snaps = _run(moex_iss.fetch_all())
    by_code = {s.code: s for s in snaps}

    # 3 FX + brent + gold
    assert {"usd-rub-live", "eur-rub-live", "cny-rub-live", "brent", "gold-rub-live"} <= set(by_code)
    assert all(by_code[c].source == "MOEX" for c in ("usd-rub-live", "brent"))
    # CBR не дёргается, когда MOEX отдал все FX.
    assert cbr_calls["n"] == 0


def test_fetch_all_falls_back_to_cbr_when_moex_fx_dead(monkeypatch):
    async def dead_fx(client, code, secid):
        return None, None

    async def fake_brent(client):
        return None

    async def fake_gold(client):
        return None

    async def fake_cbr(client):
        # Ключи = CBR Valute ID из _FX_INSTRUMENTS.
        return {"R01235": (78.0, 0.1), "R01239": (85.0, -0.2), "R01375": (10.9, 0.0)}

    monkeypatch.setattr(moex_iss, "_fetch_fx_one", dead_fx)
    monkeypatch.setattr(moex_iss, "_fetch_brent", fake_brent)
    monkeypatch.setattr(moex_iss, "_fetch_gold", fake_gold)
    monkeypatch.setattr(moex_iss, "_fetch_cbr_daily", fake_cbr)

    snaps = _run(moex_iss.fetch_all())
    by_code = {s.code: s for s in snaps}

    assert by_code["usd-rub-live"].price == 78.0
    assert all(by_code[c].source == "ЦБ РФ" for c in ("usd-rub-live", "eur-rub-live", "cny-rub-live"))
    assert all(by_code[c].market_open is False for c in ("usd-rub-live", "eur-rub-live", "cny-rub-live"))


def test_fetch_all_survives_source_exceptions(monkeypatch):
    """Падение brent/gold не должно ронять весь тик (иначе тикер мигает)."""
    async def fake_fx(client, code, secid):
        return 90.0, 0.5

    async def boom_brent(client):
        raise RuntimeError("MOEX forts down")

    async def boom_gold(client):
        raise RuntimeError("MOEX selt down")

    async def fake_cbr(client):
        return {}

    monkeypatch.setattr(moex_iss, "_fetch_fx_one", fake_fx)
    monkeypatch.setattr(moex_iss, "_fetch_brent", boom_brent)
    monkeypatch.setattr(moex_iss, "_fetch_gold", boom_gold)
    monkeypatch.setattr(moex_iss, "_fetch_cbr_daily", fake_cbr)

    snaps = _run(moex_iss.fetch_all())
    by_code = {s.code: s for s in snaps}

    # FX выжили, несмотря на упавшие brent/gold.
    assert {"usd-rub-live", "eur-rub-live", "cny-rub-live"} <= set(by_code)
    assert "brent" not in by_code
    assert "gold-rub-live" not in by_code


def test_pull_job_uses_brent_db_fallback_when_moex_brent_missing(monkeypatch):
    """Когда MOEX не отдал Brent, воркер должен подставить его из БД."""
    from app.tasks import ticker_worker

    usd = moex_iss.TickerSnapshot(
        code="usd-rub-live", price=78.0, change_pct=0.1,
        market_open=False, fetched_at=moex_iss.utcnow(), source="ЦБ РФ",
    )
    brent_fb = moex_iss.TickerSnapshot(
        code="brent", price=76.25, change_pct=-0.5,
        market_open=False, fetched_at=moex_iss.utcnow(), source="Рыночные котировки",
    )

    async def fake_moex():
        return [usd]  # без brent

    async def fake_binance():
        return []

    async def fake_brent_fb():
        return brent_fb

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
    monkeypatch.setattr(ticker_worker, "_brent_db_fallback", fake_brent_fb)
    monkeypatch.setattr(ticker_worker, "get_redis", fake_get_redis)

    _run(ticker_worker.ticker_pull_job())

    assert "ticker:brent" in written
    assert "ticker:usd-rub-live" in written


def test_fetch_all_survives_fx_gather_failure(monkeypatch):
    """Если весь FX-gather упал — brent/gold всё равно отдаются."""
    async def boom_fx(client, code, secid):
        raise RuntimeError("connection reset")

    async def fake_brent(client):
        return moex_iss.TickerSnapshot(
            code="brent", price=76.0, change_pct=None,
            market_open=True, fetched_at=moex_iss.utcnow(), source="MOEX",
        )

    async def fake_gold(client):
        return None

    async def empty_cbr(client):
        return {}

    monkeypatch.setattr(moex_iss, "_fetch_fx_one", boom_fx)
    monkeypatch.setattr(moex_iss, "_fetch_brent", fake_brent)
    monkeypatch.setattr(moex_iss, "_fetch_gold", fake_gold)
    monkeypatch.setattr(moex_iss, "_fetch_cbr_daily", empty_cbr)

    snaps = _run(moex_iss.fetch_all())
    by_code = {s.code: s for s in snaps}
    assert "brent" in by_code
