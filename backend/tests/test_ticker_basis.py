"""БД2/БД9: лента и страница курса называют источник своим именем и датой, числа не склеиваются."""

from __future__ import annotations

import asyncio
import json
from datetime import date

from app.services.ticker_sources import TickerSnapshot, source_kind, source_label, utcnow


def test_source_kind_by_short_label():
    assert source_kind("MOEX") == "market"
    assert source_kind("Binance") == "market"
    assert source_kind("ЦБ РФ") == "central_bank"
    assert source_kind("Банк России") == "central_bank"
    assert source_kind("ЕЦБ") == "ecb"
    assert source_kind("EIA") == "official"
    assert source_kind(None) == "official"


def test_source_label_is_exchange_or_cb_by_language():
    assert source_label("market", "MOEX", "ru") == "Биржа"
    assert source_label("market", "MOEX", "en") == "Exchange"
    assert source_label("central_bank", "Банк России", "ru") == "ЦБ"
    assert source_label("central_bank", "Банк России", "en") == "Central bank"
    # Прочие официальные ряды подписываются названием источника.
    assert source_label("official", "EIA", "ru") == "EIA"


def test_snapshot_dict_carries_kind_and_a_point_in_time():
    live = TickerSnapshot(
        code="usd-rub-live", price=85.81, change_pct=0.1, market_open=True,
        fetched_at=utcnow(), source="MOEX",
    ).as_dict()
    assert live["source_kind"] == "market"
    assert live["as_of"] == live["fetched_at"]
    daily = TickerSnapshot(
        code="gold-rub-live", price=11886.6, change_pct=0.2, market_open=False,
        fetched_at=utcnow(), source="Банк России", as_of_date=date(2026, 10, 3),
    ).as_dict()
    assert daily["source_kind"] == "central_bank"
    assert daily["as_of"] == "2026-10-03"


class _StubRedis:
    """Redis без сети: цикл событий TestClient не совпадает с циклом fakeredis."""

    def __init__(self):
        self.data: dict[str, str] = {}

    async def get(self, key):
        return self.data.get(key)

    async def mget(self, *keys):
        return [self.data.get(key) for key in keys]


def _put(monkeypatch, code: str, payload: dict):
    import app.api.ticker as ticker_api

    stub = _StubRedis()
    stub.data[f"ticker:{code}"] = json.dumps(payload)

    async def fake_get_redis():
        return stub

    monkeypatch.setattr(ticker_api, "get_redis", fake_get_redis)


def test_live_endpoint_adds_labels_to_old_snapshots(auth_env, monkeypatch):
    from fastapi.testclient import TestClient

    _put(monkeypatch, "usd-rub-live", {
        "code": "usd-rub-live", "price": 85.81, "change_pct": 0.1, "market_open": True,
        "fetched_at": "2026-10-05T09:00:00+00:00", "source": "MOEX",
    })
    with TestClient(auth_env["app"]) as tc:
        ru = tc.get("/api/v1/ticker/live?lane=russia")
        en = tc.get("/api/v1/ticker/live?lane=russia", headers={"X-FE-Locale": "en"})
    assert ru.headers["vary"] == "Host, x-fe-locale"
    snap = ru.json()["snapshots"][0]
    assert ru.json()["lane"] == "russia"
    assert snap["source_kind"] == "market" and snap["source_label"] == "Биржа"
    assert snap["as_of"] == "2026-10-05T09:00:00+00:00"
    assert en.json()["snapshots"][0]["source_label"] == "Exchange"


def _seed_usd_rub(session_maker):
    from app.models import Indicator, IndicatorData

    async def run():
        async with session_maker() as db:
            ind = Indicator(
                code="usd-rub", name="Доллар к рублю", unit="руб.", frequency="daily",
                source="Банк России", parser_type="cbr_fx", is_active=True, is_listed=True,
            )
            db.add(ind)
            await db.flush()
            db.add(IndicatorData(indicator_id=ind.id, date=date(2026, 10, 2), value=83.0))
            db.add(IndicatorData(indicator_id=ind.id, date=date(2026, 10, 3), value=83.48))
            await db.commit()

    asyncio.run(run())


def test_rate_basis_names_both_numbers_and_never_mixes_them(auth_env, monkeypatch):
    from fastapi.testclient import TestClient

    _seed_usd_rub(auth_env["session_maker"])
    _put(monkeypatch, "usd-rub-live", {
        "code": "usd-rub-live", "price": 85.81, "change_pct": 0.1, "market_open": True,
        "fetched_at": "2026-10-05T09:00:00+00:00", "source": "MOEX",
    })
    with TestClient(auth_env["app"]) as tc:
        body = tc.get("/api/v1/ticker/rates/usd-rub").json()
    assert body["pair"] == "usd-rub"
    cb = body["central_bank"]
    assert cb["price"] == 83.48 and cb["as_of"] == "2026-10-03"
    assert cb["source_kind"] == "central_bank" and cb["source_label"] == "ЦБ"
    market = body["market"]
    assert market["price"] == 85.81 and market["source_label"] == "Биржа"


def test_rate_basis_hides_a_central_bank_fallback_from_the_market_slot(auth_env, monkeypatch):
    from fastapi.testclient import TestClient

    _seed_usd_rub(auth_env["session_maker"])
    # Биржа недоступна: воркер подставил курс ЦБ. Это не рыночное число.
    _put(monkeypatch, "usd-rub-live", {
        "code": "usd-rub-live", "price": 83.48, "change_pct": 0.0, "market_open": False,
        "fetched_at": "2026-10-05T09:00:00+00:00", "source": "ЦБ РФ",
    })
    with TestClient(auth_env["app"]) as tc:
        body = tc.get("/api/v1/ticker/rates/usd-rub").json()
    assert body["market"] is None
    assert body["central_bank"]["price"] == 83.48


def test_rate_basis_rejects_unknown_pairs(auth_env):
    from fastapi.testclient import TestClient

    with TestClient(auth_env["app"]) as tc:
        assert tc.get("/api/v1/ticker/rates/btc-usd").status_code == 404
