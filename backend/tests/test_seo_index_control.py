"""Блок «Индексация» недельного SEO-отчёта: выборка, лимиты, тренд, сбои."""
import asyncio
from datetime import date

import fakeredis.aioredis
import pytest

from app.services import seo_index_control as ic
from app.services import seo_weekly_report as report


def test_control_sample_is_fixed_twenty_urls_within_limit():
    urls = ic.control_urls()
    assert len(urls) == 20 == len(set(urls))
    assert urls[0] == "https://forecasteconomy.com"
    assert "https://ru.forecasteconomy.com/russia/calendar" in urls
    # 301-адреса, которые Google «не знает» по определению, в выборке не нужны
    assert not [u for u in urls if u.endswith("/calendar") and "/russia/" not in u]
    assert not [u for u in urls if u.endswith("/regions")]


def _report(url, state, verdict="PASS", google_canonical=None, user_canonical=None, crawl="2026-10-10T01:02:03Z"):
    return {"url": url, "result": {"inspectionResult": {"indexStatusResult": {
        "coverageState": state, "verdict": verdict, "lastCrawlTime": crawl,
        "googleCanonical": google_canonical, "userCanonical": user_canonical,
    }}}}


def test_parse_inspection_states():
    ok = ic.parse_inspection(_report("https://x/a", "Submitted and indexed"))
    assert ok["indexed"] and ok["crawled"] == "2026-10-10" and not ok["canonical_differs"]
    bad = ic.parse_inspection(_report("https://x/b", "Crawled - currently not indexed", "NEUTRAL"))
    assert not bad["indexed"]
    unknown = ic.parse_inspection(_report("https://x/c", "URL is unknown to Google"))
    assert not unknown["indexed"]
    dup = ic.parse_inspection(_report("https://x/d", "Duplicate, Google chose different canonical than user", "NEUTRAL", "https://x/e", "https://x/d"))
    assert dup["canonical_differs"] and not dup["indexed"]
    assert ic.parse_inspection({"url": "u"})["state"] == "unknown"


class _FakeClient:
    calls = 0

    def __init__(self, http):
        pass

    async def inspect_sample(self, site, urls):
        type(self).calls += 1
        assert len(urls) == 20
        return [
            _report(u, "Submitted and indexed" if u.startswith("https://forecasteconomy.com") else "Crawled - currently not indexed")
            for u in urls
        ]


@pytest.fixture
def state_redis(monkeypatch):
    server = fakeredis.aioredis.FakeRedis()

    async def get():
        return server

    monkeypatch.setattr("app.core.cache.get_state_redis", get)
    return server


def test_inspection_runs_once_per_day_and_compares_with_previous(state_redis):
    _FakeClient.calls = 0

    class Better(_FakeClient):
        async def inspect_sample(self, site, urls):
            return [_report(u, "Submitted and indexed") for u in urls]

    async def scenario():
        first = await ic.run_control_inspection(date(2026, 10, 5), client_factory=_FakeClient)
        again = await ic.run_control_inspection(date(2026, 10, 5), client_factory=_FakeClient)
        second = await ic.run_control_inspection(date(2026, 10, 12), client_factory=Better)
        return first, again, second

    first, again, second = asyncio.run(scenario())
    assert _FakeClient.calls == 1 and first["previous"] == []  # второй вызов в тот же день: без API
    assert again["current"] == first["current"]
    assert second["previous_day"] == "2026-10-05"
    text = "\n".join(ic.summarize_inspection(second))
    assert "ru.forecasteconomy.com: в индексе 10 из 10" in text
    assert "С 05.10: стало в индексе 10, выпало 0" in text
    first_text = "\n".join(ic.summarize_inspection(first))
    assert "ru.forecasteconomy.com: в индексе 0 из 10" in first_text
    assert "Crawled - currently not indexed — 10" in first_text
    assert "Предыдущей проверки нет" in first_text


def test_inspection_failure_does_not_break_report(state_redis):
    class Broken(_FakeClient):
        async def inspect_sample(self, site, urls):
            raise RuntimeError("quota")

    result = asyncio.run(ic.run_control_inspection(date(2026, 10, 12), client_factory=Broken))
    assert result == {"error": "URL Inspection недоступен (RuntimeError)"}
    assert ic.summarize_inspection(result) == ["Google, контрольная выборка: URL Inspection недоступен (RuntimeError)"]


def test_not_configured_is_reported_without_calls(state_redis, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "gsc_access_token", "")
    monkeypatch.setattr(settings, "gsc_credentials_file", "")
    result = asyncio.run(ic.run_control_inspection(date(2026, 10, 12)))
    assert "error" in result


def test_yandex_trend_and_bad_share():
    rows = [
        {"host": "https:ru.forecasteconomy.com:443", "day": date(2026, 10, 2), "in_search": 2645, "excluded": 6000,
         "crawled_2xx": 100, "crawled_3xx": 0, "crawled_4xx": 0, "crawled_5xx": 0},
        {"host": "https:ru.forecasteconomy.com:443", "day": date(2026, 10, 9), "in_search": 9543, "excluded": 6855,
         "crawled_2xx": 900, "crawled_3xx": 50, "crawled_4xx": 30, "crawled_5xx": 20},
    ]
    lines = ic.summarize_yandex_indexing(rows)
    assert lines[0] == "ru.forecasteconomy.com: в поиске 9 543 (+6 898 за неделю) на 09.10, исключено 6 855"
    assert lines[1] == "  обход за сутки 1 000, из них 4xx/5xx — 5.0%"


def test_report_contains_indexing_block():
    data = {
        "today": date(2026, 10, 12), "yandex": {}, "google": None, "sitemap": {}, "bots": {},
        "last_yandex_day": date(2026, 10, 11), "last_google_day": date(2026, 10, 11),
        "yandex_indexing": [{"host": "https:forecasteconomy.com:443", "day": date(2026, 10, 9), "in_search": 105480,
                             "excluded": 13307, "crawled_2xx": 15000, "crawled_3xx": 0, "crawled_4xx": 0, "crawled_5xx": 0}],
        "google_inspection": {"error": "учётные данные Search Console не настроены"},
    }
    text = report.format_seo_week(data)
    assert "<b>Индексация</b>" in text
    assert "forecasteconomy.com: в поиске 105 480 на 09.10, исключено 13 307" in text
    assert "контрольная выборка: учётные данные Search Console не настроены" in text
