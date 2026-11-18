"""Свежесть данных Вебмастера: перерыв 07.10–13.11.2026 не выдаётся за падение «в поиске».

Боевые числа 18.11.2026 (API Вебмастера, только чтение): apex 105 480 на 07.10 → 29 306 на 13.11,
ru. 9 543 → 27 365; между точками ни одной точки (аварии ЦОД Яндекса), история обхода стоит с 10.10.
"""
import asyncio
import json
from datetime import date

from app.services.webmaster_freshness import (
    freshness_lines,
    in_search_freshness,
    in_search_points,
    last_crawl_day,
)

TODAY = date(2026, 11, 18)

APEX_HISTORY = {"history": [
    {"date": "2026-10-02T10:00:05.489+03:00", "value": 74744},
    {"date": "2026-10-05T10:20:04.297+03:00", "value": 92887},
    {"date": "2026-10-07T10:00:09.495+03:00", "value": 105480},
    {"date": "2026-11-13T10:00:00.000+03:00", "value": 29306},
]}
CRAWL = {"indicators": {
    "HTTP_2XX": [{"date": "2026-10-09T00:00:00.000+03:00", "value": 5791},
                 {"date": "2026-10-10T00:00:00.000+03:00", "value": 4000}],
    "HTTP_5XX": [{"date": "2026-10-10T00:00:00.000+03:00", "value": None}],
}}


def test_gap_between_points_is_marked():
    fresh = in_search_freshness(APEX_HISTORY, TODAY)
    assert fresh == {
        "date": "2026-11-13", "value": 29306, "age_days": 5,
        "previous_date": "2026-10-07", "previous_value": 105480,
        "gap_days": 37, "data_gap": True,
    }


def test_regular_update_step_is_not_a_gap():
    fresh = in_search_freshness({"history": APEX_HISTORY["history"][:3]}, date(2026, 10, 8))
    assert fresh["gap_days"] == 2 and fresh["data_gap"] is False


def test_single_point_and_empty_history():
    one = in_search_freshness({"history": [{"date": "2026-11-13T10:00:00+03:00", "value": 0}]}, TODAY)
    assert one["value"] == 0 and one["data_gap"] is None and one["previous_date"] is None
    assert in_search_freshness({"history": []}, TODAY) is None
    assert in_search_freshness(None, TODAY) is None
    assert in_search_points({"history": [{"date": "bad", "value": 1}, {"value": 2}]}) == []


def test_last_crawl_day_ignores_null_points_and_list_shape():
    assert last_crawl_day(CRAWL) == date(2026, 10, 10)
    as_list = {"indicators": [{"indicator": "HTTP_2XX", "history": CRAWL["indicators"]["HTTP_2XX"]}]}
    assert last_crawl_day(as_list) == date(2026, 10, 10)
    assert last_crawl_day({"indicators": {}}) is None


def test_report_lines_name_both_dates_and_stale_crawl():
    lines = freshness_lines(in_search_freshness(APEX_HISTORY, TODAY), date(2026, 10, 10), TODAY)
    assert len(lines) == 2
    assert "13.11" in lines[0] and "07.10" in lines[0] and "37 дн." in lines[0]
    assert "не изменение за неделю" in lines[0]
    assert "10.10" in lines[1]


def test_report_lines_empty_when_fresh():
    fresh = in_search_freshness({"history": APEX_HISTORY["history"][:3]}, date(2026, 10, 8))
    assert freshness_lines(fresh, date(2026, 10, 7), date(2026, 10, 8)) == []


class _Resp:
    def __init__(self, data):
        self.data = data


class _Client:
    async def user(self):
        return _Resp({"user_id": "u1"})

    async def summary(self, user_id, host_id):
        return _Resp({"searchable_pages_count": 29306, "excluded_pages_count": 6078,
                      "sqi": 20, "site_problems": {}})

    async def search_events_samples(self, user_id, host_id, limit=100):
        return _Resp({"samples": []})

    async def in_search_history(self, user_id, host_id, **params):
        return _Resp(APEX_HISTORY)

    async def indexing_history(self, user_id, host_id, **params):
        return _Resp(CRAWL)


def _fake_analytics(monkeypatch, module):
    class FakeDB:
        async def scalar(self, *a, **kw):
            return None

        async def execute(self, *a, **kw):
            class _R:
                def all(self):
                    return []
            return _R()

    class _CM:
        async def __aenter__(self):
            return FakeDB()

        async def __aexit__(self, *a):
            return False

    monkeypatch.setattr(module, "analytics_session", lambda: _CM())


def test_pulse_snapshot_carries_freshness_and_gap(monkeypatch):
    from app.config import settings
    from app.services import pulse
    from app.services import yandex_webmaster_client as ywc

    monkeypatch.setattr(pulse.settings, "yandex_webmaster_token", "token")
    monkeypatch.setattr(settings, "apex_locale_en", True)
    monkeypatch.setattr(ywc, "YandexWebmasterClient", _Client)
    monkeypatch.setattr("app.services.sitemap_static.url_count_from_stats", lambda: 10_000_000)
    monkeypatch.setattr("app.services.display.today_msk", lambda: TODAY)
    _fake_analytics(monkeypatch, pulse)

    seo = asyncio.run(pulse._seo_snapshot(None))
    assert seo["available"] is True
    assert seo["in_search_freshness"]["previous_value"] == 105480
    assert seo["in_search_freshness"]["data_gap"] is True
    assert seo["yandex_data_gap"] is True
    assert set(seo["summary_by_host"]) == {"forecasteconomy.com", "ru.forecasteconomy.com"}
    for host in seo["summary_by_host"].values():
        assert host["in_search_freshness"]["date"] == "2026-11-13"
    assert pulse.memory_core({"date": "2026-11-17", "seo": seo})["seo_in_search_date"] == "2026-11-13"


def test_pulse_snapshot_survives_missing_history(monkeypatch):
    from app.services import pulse
    from app.services import yandex_webmaster_client as ywc

    class NoHistory(_Client):
        async def in_search_history(self, user_id, host_id, **params):
            raise RuntimeError("504")

    monkeypatch.setattr(pulse.settings, "yandex_webmaster_token", "token")
    monkeypatch.setattr(ywc, "YandexWebmasterClient", NoHistory)
    monkeypatch.setattr("app.services.sitemap_static.url_count_from_stats", lambda: 10_000_000)
    _fake_analytics(monkeypatch, pulse)

    seo = asyncio.run(pulse._seo_snapshot(None))
    assert seo["available"] is True and seo["searchable_pages"] == 29306
    assert seo["in_search_freshness"] is None and seo["yandex_data_gap"] is False


def test_weekly_report_signs_gap_instead_of_unchanged(monkeypatch):
    from app.services import webmaster_indexing_report as wir

    class Redis:
        def __init__(self):
            self.store = {wir._SNAPSHOT_KEY: json.dumps({"searchable": 105480, "excluded": 756, "sqi": 20})}

        async def get(self, key):
            return self.store.get(key)

        async def set(self, key, value):
            self.store[key] = value

    monkeypatch.setattr("app.services.display.today_msk", lambda: TODAY)
    text = asyncio.run(wir._host_report_block(_Client(), "u1", wir.settings.webmaster_host_id, Redis()))
    assert "Страниц в поиске: <b>29306</b> (-76174 за неделю)" in text
    assert "перерыв данных Яндекса 37 дн." in text
    assert "История обхода в Вебмастере остановилась 10.10" in text


def test_pulse_prompt_forbids_drop_across_gap():
    from app.services.pulse_report import _SYSTEM_PROMPT

    assert "data_gap=true" in _SYSTEM_PROMPT
    assert "не падение за день" in _SYSTEM_PROMPT
