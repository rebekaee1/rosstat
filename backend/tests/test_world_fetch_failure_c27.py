"""Круг починки 27.10.2026: сбой источника мировых данных — повтор и честный статус, не «смена layout».

* IMF WEO 23.10 03:11 UTC: шлюз трижды ответил 401 на публичный адрес; повтор с паузой.
* FRED 21–22.10: три ряда подряд дали «0 точек» без причины; пустой разбор повторяется, причина пишется.
* Сбой источника без точек → `failed`, алерт zero_parse не шлётся (`mark_fetch_failed`).
"""

from __future__ import annotations

import asyncio
from datetime import date
from types import SimpleNamespace

import httpx
import pytest

from app.models import FetchLog
from app.services import alerting
from app.services import base_parser as bp
from app.services import fred_parser as fred_mod
from app.services import imf_weo_adapter as imf_mod
from app.services.fred_parser import FredCsvParser
from app.services.imf_weo_parser import ImfWeoParser

_GOOD_CSV = "observation_date,DGS10\n2026-10-20,4.5\n2026-10-21,4.6\n"


# --- IMF: повтор разового 401 ---------------------------------------------------------------------


def _patch_imf_client(monkeypatch, handler):
    real = httpx.Client

    def factory(**kwargs):
        return real(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(imf_mod.httpx, "Client", factory)
    sleeps: list[float] = []
    monkeypatch.setattr(imf_mod, "_sleep", sleeps.append)
    return sleeps


def test_imf_single_401_is_retried_and_recovers(monkeypatch):
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(401, text="Unauthorized")
        return httpx.Response(200, json={"data": "ok"})

    sleeps = _patch_imf_client(monkeypatch, handler)
    assert imf_mod._fetch_weo_json("https://api.imf.org/x") == {"data": "ok"}
    assert calls["n"] == 2
    assert sleeps == [imf_mod._RETRY_DELAYS_S[0]]


def test_imf_persistent_401_raises_after_all_attempts(monkeypatch):
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(401, text="Unauthorized")

    sleeps = _patch_imf_client(monkeypatch, handler)
    with pytest.raises(httpx.HTTPStatusError) as err:
        imf_mod._fetch_weo_json("https://api.imf.org/x")
    assert "401" in str(err.value)
    assert calls["n"] == len(imf_mod._RETRY_DELAYS_S) + 1
    assert len(sleeps) == len(imf_mod._RETRY_DELAYS_S)


def test_imf_404_is_not_retried(monkeypatch):
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(404, text="nope")

    sleeps = _patch_imf_client(monkeypatch, handler)
    with pytest.raises(httpx.HTTPStatusError):
        imf_mod._fetch_weo_json("https://api.imf.org/x")
    assert calls["n"] == 1 and sleeps == []


def test_imf_transport_error_and_html_body_are_retried(monkeypatch):
    seq = iter(["boom", "html", "ok"])

    def handler(request):
        step = next(seq)
        if step == "boom":
            raise httpx.ConnectError("reset", request=request)
        if step == "html":
            return httpx.Response(200, text="<html>gateway</html>")
        return httpx.Response(200, json={"a": 1})

    sleeps = _patch_imf_client(monkeypatch, handler)
    assert imf_mod._fetch_weo_json("https://api.imf.org/x") == {"a": 1}
    assert len(sleeps) == 2


# --- BaseParser: сбой источника → failed, без zero_parse -------------------------------------------


class _FakeDB:
    def __init__(self, existing: int = 0):
        self.existing = existing

    async def commit(self):
        pass

    async def rollback(self):
        pass

    def add(self, obj):
        pass

    async def scalar(self, stmt):
        return self.existing


@pytest.fixture
def zero_alerts(monkeypatch):
    sent: list[tuple[str, int]] = []

    async def fake_zero_alert(code, existing):
        sent.append((code, existing))

    async def fake_noop(*args, **kwargs):
        return None

    monkeypatch.setattr(alerting, "alert_zero_parse", fake_zero_alert)
    monkeypatch.setattr(bp, "cache_invalidate_indicator", fake_noop)
    return sent


def _run(parser, cfg, existing=500):
    indicator = SimpleNamespace(id=1, code="weo-gdp-usd", model_config_json=cfg)
    fetch_log = FetchLog(indicator_id=1, status="running")
    asyncio.run(parser.run(_FakeDB(existing), indicator, fetch_log))
    return fetch_log


def test_imf_fetch_error_is_failed_with_reason_not_parsed_zero(monkeypatch, zero_alerts):
    def boom(self, weo_code, iso3_codes):
        raise httpx.HTTPStatusError(
            "Client error '401 Unauthorized'",
            request=httpx.Request("GET", "https://api.imf.org/x"),
            response=httpx.Response(401),
        )

    monkeypatch.setattr(imf_mod.ImfWeoAdapter, "fetch_weo_code", boom)
    fl = _run(ImfWeoParser(), {"weo_code": "NGDPD", "country_code": "RU"})
    assert fl.status == "failed"
    assert "401" in fl.error_message and "IMF WEO RUS NGDPD" in fl.error_message
    assert zero_alerts == []


def test_imf_genuinely_empty_response_is_still_parsed_zero(monkeypatch, zero_alerts):
    monkeypatch.setattr(imf_mod.ImfWeoAdapter, "fetch_weo_code", lambda self, c, i: [])
    fl = _run(ImfWeoParser(), {"weo_code": "NGDPD", "country_code": "RU"})
    assert fl.status == "parsed_zero"
    assert zero_alerts == [("weo-gdp-usd", 500)]


# --- FRED: пустой ответ повторяется, причина сохраняется ---------------------------------------------


def test_fred_empty_body_is_retried_then_recovers(monkeypatch):
    bodies = iter(["", "<html>Please verify</html>", _GOOD_CSV])
    monkeypatch.setattr(fred_mod, "_fetch_fred_csv", lambda sid: next(bodies))
    sleeps: list[float] = []
    points = fred_mod._fetch_fred_points("DGS10", sleep=sleeps.append)
    assert points == [(date(2026, 10, 20), 4.5), (date(2026, 10, 21), 4.6)]
    assert sleeps == list(fred_mod._EMPTY_RETRY_DELAYS_S)


def test_fred_persistent_garbage_is_failed_with_body_head(monkeypatch, zero_alerts):
    monkeypatch.setattr(fred_mod, "_fetch_fred_csv", lambda sid: "<html>Access denied</html>")
    monkeypatch.setattr(fred_mod.time, "sleep", lambda s: None)
    fl = _run(FredCsvParser(), {"fred_series_id": "DGS10"})
    assert fl.status == "failed"
    assert "Access denied" in fl.error_message and "DGS10" in fl.error_message
    assert zero_alerts == []


def test_fred_backfill_cut_to_nothing_is_not_a_failure(monkeypatch, zero_alerts):
    monkeypatch.setattr(fred_mod, "_fetch_fred_csv", lambda sid: _GOOD_CSV)
    fl = _run(FredCsvParser(), {"fred_series_id": "DGS10", "backfill_from": "2027-01-01"})
    # ряд не сломан: источник жив, просто нет точек новее backfill — прежняя логика zero-parse
    assert fl.status in {"parsed_zero", "no_new_data"}
    assert "failed" not in fl.status
