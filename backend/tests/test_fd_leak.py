"""FD-leak regressions: adapter sessions, workbook.close, Eurostat Session, OG fonts, metrics."""

from __future__ import annotations

from app.services.world_adapters import close_http_resources
from app.services.world_bank_pink_sheet_parser import _parse_pink_sheet_monthly


def test_close_http_resources_closes_session_and_html():
    closed: list[object] = []

    class _Sess:
        def close(self):
            closed.append(self)

    class _Adapter:
        def __init__(self):
            self._session = _Sess()
            self._html_session = _Sess()

    close_http_resources(_Adapter())
    assert len(closed) == 2
    close_http_resources(None)


def test_close_http_resources_skips_shared_identity():
    closed: list[object] = []

    class _Sess:
        def close(self):
            closed.append(self)

    shared = _Sess()

    class _Adapter:
        def __init__(self):
            self._session = shared
            self._html_session = shared

    close_http_resources(_Adapter())
    assert closed == [shared]


def test_pink_sheet_parser_closes_workbook(monkeypatch):
    closed: list[bool] = []

    class _WS:
        def iter_rows(self, **_kwargs):
            return iter([])

    class _WB:
        sheetnames = ["Monthly Prices"]

        def __getitem__(self, _key):
            return _WS()

        def close(self):
            closed.append(True)

    import app.services.world_bank_pink_sheet_parser as wb_mod

    monkeypatch.setattr(wb_mod.openpyxl, "load_workbook", lambda *_a, **_k: _WB())
    assert _parse_pink_sheet_monthly(b"x", "Copper") == []
    assert closed == [True]


def test_eurostat_http_get_json_closes_ephemeral_session(monkeypatch, tmp_path):
    closed: list[bool] = []

    class _Resp:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"ok": True}

    class _Sess:
        def get(self, *_a, **_k):
            return _Resp()

        def close(self):
            closed.append(True)

    import app.services.eurostat_parser as ep

    monkeypatch.setattr(ep.requests, "Session", _Sess)
    monkeypatch.setattr(ep, "_cache_path", lambda _url: tmp_path / "missing.json")
    assert ep.http_get_json("https://example.test/x", use_cache=False) == {"ok": True}
    assert closed == [True]

    closed.clear()
    passed = _Sess()
    assert ep.http_get_json(
        "https://example.test/x", use_cache=False, session=passed
    ) == {"ok": True}
    assert closed == []


def test_og_font_cache_reuses_loaded_face():
    from app.services.og_image import _font

    first = _font(24)
    second = _font(24)
    assert first is second


def test_process_open_fds_is_non_negative():
    from app.services.process_metrics import fd_soft_limit, process_open_fds

    assert process_open_fds() >= 0
    assert fd_soft_limit() >= 0


def test_health_ready_reports_open_fds(auth_client):
    body = auth_client.get("/api/v1/health/ready").json()
    assert "open_fds" in body["checks"]
    assert body["checks"]["open_fds"].isdigit()


def test_metrics_exposes_open_fds_gauge(auth_client, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "metrics_token", "fd-test-token")
    response = auth_client.get("/api/v1/metrics", params={"token": "fd-test-token"})
    assert response.status_code == 200
    text = response.text
    assert "fe_process_open_fds " in text
    assert "fe_process_open_fds_limit " in text
