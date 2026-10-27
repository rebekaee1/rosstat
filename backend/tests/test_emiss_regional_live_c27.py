"""Круг починки 27.10.2026: региональные цены на топливо (ЕМИСС 31448).

Цены стояли на 2026-07, алерт «парсер упал» приходил 25.09 и 25.10. Причины (проверены 27.10.2026):
живой ответ несёт в ``dim57831`` НАЗВАНИЕ территории, а справочник знал только oid; запрос шёл прямым
httpx мимо ETL-сессии, а fedstat отвечает адресу сервера прода 403.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from app.services.emiss_regional_parser import (
    EmissFormatError,
    _OKATO_PATH,
    fetch_month_points,
    load_dimnames,
    parse_grid_response,
)


def _live_row(name: str, ai92: str, ai95: str, dt: str) -> dict:
    """Форма строки живого ответа dataGrid.do (27.10.2026): dim57831 — название, ключи с `_d…_i…`."""
    return {
        "dim57831": name,
        "dim1709730_d111260500_i11677": ai92,
        "dim1709750_d111260503_i11677": ai95,
        "dim1755196_d111260515_i11677": dt,
    }


class TestLiveResponseShape:
    def test_live_names_map_to_slugs(self):
        payload = {"results": [
            _live_row("Российская Федерация без учета новых субъектов (с 01.01.2023)", "73,78", "80,08", "88,38"),
            _live_row("Центральный федеральный округ", "72,97", "79,06", "81,26"),
            _live_row("Белгородская область", "-", "78,10", "80,00"),
        ]}
        points = parse_grid_response(payload, year=2026, month=8, dimnames=load_dimnames())
        by = {(c, s): v for c, s, _p, v in points}
        assert by[("ceni-ai92", "russia")] == 73.78
        assert by[("ceni-dt", "cfo")] == 81.26
        assert ("ceni-ai92", "belgorodskaya-oblast") not in by  # «-» отброшено
        assert by[("ceni-ai95", "belgorodskaya-oblast")] == 78.1
        assert {p for _c, _s, p, _v in points} == {202608}

    def test_every_okato_slug_has_a_name_mapping(self):
        okato = json.loads(_OKATO_PATH.read_text(encoding="utf-8"))
        names = load_dimnames()
        slugs_by_name = {slug for key, slug in names.items() if not key.isdigit()}
        assert set(okato) <= slugs_by_name, sorted(set(okato) - slugs_by_name)

    def test_oid_keys_still_work(self):
        names = load_dimnames()
        assert names["1849012"] == "russia"

    def test_duplicate_russia_rows_do_not_duplicate_points(self):
        payload = {"results": [
            _live_row("Российская Федерация", "60,00", "-", "-"),
            _live_row("Российская Федерация без учета новых субъектов (с 01.01.2023)", "61,00", "-", "-"),
        ]}
        points = parse_grid_response(payload, year=2022, month=7, dimnames=load_dimnames())
        keys = [(c, s, p) for c, s, p, _v in points]
        assert len(keys) == len(set(keys)) == 1

    def test_rows_without_parsed_prices_raise_format_error(self):
        async def post_grid(indicator_id, params):
            return {"results": [{"dim57831": "Неизвестная территория", "dim1709730_d1_i1": "70,0"}]}

        with pytest.raises(EmissFormatError):
            asyncio.run(fetch_month_points(2026, 8, ["1849012"], {}, post_grid=post_grid))

    def test_empty_results_is_just_not_published_yet(self):
        async def post_grid(indicator_id, params):
            return {"results": []}

        assert asyncio.run(fetch_month_points(2026, 10, ["1849012"], {}, post_grid=post_grid)) == []


class _FakeResp:
    def __init__(self, status: int, payload=None):
        self.status_code = status
        self._payload = payload if payload is not None else {"results": []}

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests

            raise requests.HTTPError(f"{self.status_code}")

    def json(self):
        return self._payload


class _FakeSession:
    def __init__(self, statuses):
        self.statuses = list(statuses)
        self.calls = 0
        self.closed = False

    def post(self, url, data=None, headers=None, timeout=None):
        self.calls += 1
        return _FakeResp(self.statuses.pop(0))

    def close(self):
        self.closed = True


class TestPostGridViaEtlSession:
    def _patch(self, monkeypatch, statuses):
        import app.services.emiss_regional_parser as mod

        session = _FakeSession(statuses)
        monkeypatch.setattr(mod, "create_session", lambda timeout=60, **kw: session)
        monkeypatch.setattr(mod.time, "sleep", lambda s: None)
        return mod, session

    def test_403_is_not_retried_and_names_the_status(self, monkeypatch):
        mod, session = self._patch(monkeypatch, [403])
        with pytest.raises(RuntimeError) as err:
            mod._post_grid_sync(31448, b"x=1", {})
        assert "HTTP 403" in str(err.value)
        assert session.calls == 1 and session.closed

    def test_5xx_is_retried_then_succeeds(self, monkeypatch):
        mod, session = self._patch(monkeypatch, [503, 502, 200])
        assert mod._post_grid_sync(31448, b"x=1", {}) == {"results": []}
        assert session.calls == 3

    def test_persistent_5xx_gives_up_after_all_attempts(self, monkeypatch):
        mod, session = self._patch(monkeypatch, [500] * 4)
        with pytest.raises(RuntimeError):
            mod._post_grid_sync(31448, b"x=1", {})
        assert session.calls == 4


class TestJobAlerts:
    def _patch(self, monkeypatch, run):
        import app.services.alerting as alerting
        import app.services.emiss_regional_parser as mod

        sent: list[str] = []

        async def fake_send(message, **kwargs):
            sent.append(message)
            return True

        class _Ctx:
            async def __aenter__(self):
                return object()

            async def __aexit__(self, *a):
                return False

        monkeypatch.setattr(mod, "async_session", lambda: _Ctx())
        monkeypatch.setattr(mod, "run_emiss_regional_update", run)
        monkeypatch.setattr(alerting, "send_telegram", fake_send)
        return mod, alerting, sent

    def test_failure_alert_carries_reason_and_is_muted(self, monkeypatch):
        async def boom(db):
            raise RuntimeError("dataGrid.do?id=31448: HTTP 403")

        mod, alerting, sent = self._patch(monkeypatch, boom)
        mute = iter([False, True])

        async def fake_muted(key, ttl):
            return next(mute)

        monkeypatch.setattr(alerting, "alert_muted", fake_muted)
        for _ in range(2):
            with pytest.raises(RuntimeError):
                asyncio.run(mod.emiss_regional_job())
        assert len(sent) == 1
        assert "HTTP 403" in sent[0] and "Причина" in sent[0]

    def test_unparsed_months_raise_format_alert(self, monkeypatch):
        async def ok(db):
            return {"months": 3, "added": 0, "updated": 0, "unparsed": 2}

        mod, alerting, sent = self._patch(monkeypatch, ok)

        async def not_muted(key, ttl):
            return False

        monkeypatch.setattr(alerting, "alert_muted", not_muted)
        stats = asyncio.run(mod.emiss_regional_job())
        assert stats["unparsed"] == 2
        assert len(sent) == 1 and "не разобраны" in sent[0]
