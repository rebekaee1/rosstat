"""Regression fixtures follow the actual Webmaster API response shapes."""
import asyncio
from types import SimpleNamespace

from app.services.webmaster_indexing_daily import (
    _all_sitemap_children, _events_counts, _history_for_day, _http_classes, _latest_value, _sitemap_error_count,
)
from app.services.webmaster_indexing_report import _http_breakdown
from app.services.bot_score import BOT_THRESHOLD, SessionSignals, score_session


def test_provider_history_keeps_http_keys_and_unknown():
    payload = {"indicators": {"HTTP_5XX": [{"date": "2026-09-03", "value": 396}, {"value": 114}],
                               "HTTP_2XX": [{"value": 20}]}}
    assert _http_classes(_http_breakdown(payload)) == (20, 0, 0, 510)
    assert _http_classes(_http_breakdown({"indicators": {}})) == (None,) * 4
    assert _http_classes(_http_breakdown({"indicators": {"HTTP_2XX": [{"value": 0}]}})) == (0,) * 4


def test_sparse_search_history_and_zero():
    assert _latest_value({"history": []}) is None
    assert _latest_value({"history": [{"date": "2026-09-07", "value": 18010},
                                       {"date": "2026-09-02", "value": 0}]}) == 18010
    assert _latest_value({"history": [{"value": 0}]}) == 0
    assert _events_counts({"indicators": {"APPEARED_IN_SEARCH": [{"value": 0}],
                                         "REMOVED_FROM_SEARCH": [{"value": 7}]}}) == (0, 7)
    assert _events_counts({"indicators": {}}) == (None, None)


def test_child_sitemap_errors_are_not_lost_and_pagination_uses_cursor():
    class Client:
        calls = []
        async def sitemap_children(self, uid, host, parent, **params):
            self.calls.append(params)
            rows = [{"sitemap_id": str(i), "errors_count": int(i == 100)} for i in range(100)]
            if params.get("from") == "99":
                rows = [{"sitemap_id": "100", "errors_count": 3}]
            return SimpleNamespace(data={"sitemaps": rows})
    client = Client()
    children = asyncio.run(_all_sitemap_children(client, "u", "h", {
        "sitemaps": [{"sitemap_id": "root", "children_count": 101}]}))
    assert len(children) == 101
    assert client.calls == [{"limit": 100}, {"limit": 100, "from": "99"}]
    assert _sitemap_error_count({"sitemaps": children}) == 3
    assert _sitemap_error_count({"sitemaps": [{"last_access_error": "HTTP_403"}]}) == 1


def test_absence_of_input_is_not_proof_of_automation():
    base = dict(pageviews=1, clicks=0, moves=0, active_ms=0, max_scroll_pct=0,
                synthetic_clicks=0, visitor_sessions=1)
    assert score_session(SessionSignals(**base)) < BOT_THRESHOLD
    for ua in ("meta-externalagent/1.1", "meta-externalfetcher/1.1", "ClaudeBot/1.0"):
        assert score_session(SessionSignals(**base, ua_raw=ua)) >= BOT_THRESHOLD


def test_history_interval_is_filtered_by_moscow_calendar_date():
    from datetime import date
    payload = {"indicators": {"HTTP_5XX": [
        {"date": "2026-09-03T16:00:00+03:00", "value": 396},
        {"date": "2026-09-03T20:00:00+03:00", "value": 114},
        {"date": "2026-09-03T21:01:00Z", "value": 999},
    ]}}
    assert _http_classes(_http_breakdown(_history_for_day(payload, date(2026, 9, 3)))) == (0, 0, 0, 510)
    assert _latest_value(_history_for_day({"history": [
        {"date": "2026-09-03T21:01:00Z", "value": 24859}]}, date(2026, 9, 3))) is None


def test_sync_requests_nonempty_day_interval(monkeypatch):
    from datetime import date
    import app.services.webmaster_indexing_daily as daily
    import app.services.yandex_webmaster_client as client_module

    class DB:
        writes = []
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def scalar(self, stmt): return None
        async def execute(self, stmt): self.writes.append(stmt.compile().params)
        async def commit(self): pass
    class Client:
        intervals = []
        async def user(self): return SimpleNamespace(data={"user_id": "u"})
        async def in_search_history(self, uid, host, **params):
            self.intervals.append(params)
            return SimpleNamespace(data={"history": [{"date": "2026-09-03T10:00:00+03:00", "value": 123}]})
        async def indexing_history(self, uid, host, **params):
            self.intervals.append(params)
            assert params["indexing_indicator"] == "DOWNLOADED"
            return SimpleNamespace(data={"indicators": {"HTTP_5XX": [{"date": "2026-09-03T20:00:00+03:00", "value": 510}]}})
        async def search_events_history(self, uid, host, **params):
            self.intervals.append(params)
            return SimpleNamespace(data={"indicators": {}})
    db, client = DB(), Client()
    monkeypatch.setattr(daily.settings, "yandex_webmaster_token", "test")
    monkeypatch.setattr(daily, "analytics_session", lambda: db)
    monkeypatch.setattr(daily, "_report_host_ids", lambda: ["https:example.com:443"])
    monkeypatch.setattr(client_module, "YandexWebmasterClient", lambda: client)
    asyncio.run(daily.sync_webmaster_indexing_daily(date(2026, 9, 3), alert=False, include_sitemaps=False))
    assert all(p["date_to"] == "2026-09-04" for p in client.intervals)
    assert [p["date_from"] for p in client.intervals] == ["2026-08-27", "2026-09-03", "2026-08-27"]
    assert db.writes[0]["in_search"] == 123
    assert db.writes[0]["crawled_5xx"] == 510
