"""SEO-страницы роста трафика: sitemap-индекс, «сегодня», рейтинги регионов,
регион-vs-регион, месячные посадочные календаря + IndexNow-батчирование.

Рендеры с БД тестируются через герметичную SQLite-среду (fixture auth_env —
общая схема); маршруты — через monkeypatch рендеров (паттерн test_seo_og).
"""

import asyncio
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Единый реестр URL + sitemap
# ---------------------------------------------------------------------------

def test_today_specs_registry():
    from app.services.seo_today import TODAY_CODES, TODAY_SPECS

    assert len(TODAY_CODES) >= 8
    assert "usd-rub" in TODAY_SPECS and "key-rate" in TODAY_SPECS
    for code, spec in TODAY_SPECS.items():
        assert spec.code == code
        assert spec.query and spec.question.endswith("?")


def test_render_urlset_shape():
    from app.api.sitemap import _render_urlset
    from app.services.site_urls import SiteUrl

    xml = _render_urlset([
        SiteUrl("/russia/today", "2026-07-04", "daily", "0.9"),
        SiteUrl("/russia/region-rating/x", "2025-12-31", "monthly", "0.7"),
    ])
    assert xml.startswith('<?xml version="1.0"')
    assert "<urlset" in xml and xml.rstrip().endswith("</urlset>")
    assert "<loc>https://forecasteconomy.com/russia/today</loc>" in xml
    assert "<priority>0.7</priority>" in xml

    ru_xml = _render_urlset(
        [SiteUrl("/russia/today", "2026-07-04", "daily", "0.9")],
        origin="https://ru.forecasteconomy.com",
    )
    assert "<loc>https://ru.forecasteconomy.com/russia/today</loc>" in ru_xml
    assert "https://forecasteconomy.com/russia/today" not in ru_xml


def test_indexnow_batches_split(monkeypatch):
    """Список длиннее 10k должен разбиваться на несколько POST."""
    import app.services.indexnow as inx

    calls = []

    class _FakeResponse:
        status_code = 200
        text = ""

    class _FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, json=None):
            calls.append(len(json["urlList"]))
            return _FakeResponse()

    monkeypatch.setattr(inx.httpx, "AsyncClient", _FakeClient)
    monkeypatch.setattr(inx.settings, "indexnow_enabled", True)
    monkeypatch.setattr(inx.settings, "indexnow_key", "k" * 32)

    async def reserve(_host, _count):
        return True

    monkeypatch.setattr(inx, "reserve_daily_send_quota", reserve)

    paths = [f"/russia/region/x/i-{i}" for i in range(25_000)]
    ok = asyncio.run(inx.ping_urls(paths))
    assert ok is True
    assert calls == [10_000, 10_000, 5_000]


def test_indexnow_accepts_second_host_origin(monkeypatch):
    """Каркас второго хоста: origin/host уходят в payload, прод не трогаем."""
    import app.services.indexnow as inx

    captured = {}

    class _FakeResponse:
        status_code = 202
        text = ""

    class _FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, json=None):
            captured["payload"] = json
            return _FakeResponse()

    monkeypatch.setattr(inx.httpx, "AsyncClient", _FakeClient)
    monkeypatch.setattr(inx.settings, "indexnow_enabled", True)
    monkeypatch.setattr(inx.settings, "indexnow_key", "k" * 32)

    async def reserve(_host, _count):
        return True

    monkeypatch.setattr(inx, "reserve_daily_send_quota", reserve)

    ok = asyncio.run(
        inx.ping_urls(
            ["/russia/indicator/cpi"],
            origin="https://ru.forecasteconomy.com",
            host="ru.forecasteconomy.com",
        )
    )
    assert ok is True
    assert captured["payload"]["host"] == "ru.forecasteconomy.com"
    assert captured["payload"]["urlList"] == [
        "https://ru.forecasteconomy.com/russia/indicator/cpi"
    ]
    assert captured["payload"]["keyLocation"].startswith(
        "https://ru.forecasteconomy.com/"
    )


def test_indexnow_queue_debounce_skips_second_drain(monkeypatch):
    """Очередь в state-Redis: успешный drain ставит debounce 24ч на URL."""
    import fakeredis.aioredis
    import app.core.cache as cache_mod
    import app.services.indexnow as inx

    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)

    async def _get_state_redis():
        return redis

    monkeypatch.setattr(cache_mod, "get_state_redis", _get_state_redis)
    monkeypatch.setattr(inx.settings, "indexnow_enabled", True)
    monkeypatch.setattr(inx.settings, "indexnow_key", "k" * 32)

    posts = []

    class _FakeResponse:
        status_code = 200
        text = "ok"

    class _FakeClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, json=None):
            posts.append(json)
            return _FakeResponse()

    monkeypatch.setattr(inx.httpx, "AsyncClient", _FakeClient)

    async def scenario():
        queued = await inx.enqueue_paths(
            ["/russia/indicator/cpi", "/russia/indicator/cpi"],
            host=inx.settings.public_host,
        )
        sent = await inx.drain_indexnow_queue()
        await inx.enqueue_paths(
            ["/russia/indicator/cpi"],
            host=inx.settings.public_host,
        )
        sent_again = await inx.drain_indexnow_queue()
        return queued, sent, sent_again

    queued, sent, sent_again = asyncio.run(scenario())
    assert queued == 1
    assert sent == 1
    assert sent_again == 0
    assert len(posts) == 1
    assert posts[0]["urlList"] == [
        f"{inx.settings.public_origin.rstrip('/')}/russia/indicator/cpi"
    ]


def test_indexnow_daily_send_quota_is_atomic_global_across_hosts_and_utc_day(monkeypatch):
    import fakeredis.aioredis
    import app.core.cache as cache_mod
    import app.services.indexnow as inx

    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    now = [datetime(2026, 9, 24, 23, 59, tzinfo=timezone.utc)]

    async def _get_state_redis():
        return redis

    monkeypatch.setattr(cache_mod, "get_state_redis", _get_state_redis)
    monkeypatch.setattr(inx, "_utc_now", lambda: now[0])
    monkeypatch.setattr(inx.settings, "indexnow_daily_send_cap", 3)

    async def scenario():
        # Concurrent workers cannot reserve more than the remaining daily cap.
        results = await asyncio.gather(
            inx.reserve_daily_send_quota("forecasteconomy.com", 2),
            inx.reserve_daily_send_quota("ru.forecasteconomy.com", 2),
        )
        assert sorted(results) == [False, True]
        assert await inx.daily_send_remaining("forecasteconomy.com") == 1
        assert await inx.daily_send_remaining("ru.forecasteconomy.com") == 1
        assert not await inx.reserve_daily_send_quota("forecasteconomy.com", 2)
        assert await inx.reserve_daily_send_quota("ru.forecasteconomy.com", 1)
        now[0] = datetime(2026, 9, 25, 0, 0, tzinfo=timezone.utc)
        assert await inx.daily_send_remaining("forecasteconomy.com") == 3
        assert await inx.daily_send_remaining("ru.forecasteconomy.com") == 3
        mixed_hosts = ["forecasteconomy.com", "ru.forecasteconomy.com"]
        many = await asyncio.gather(*(
            inx.reserve_daily_send_quota(mixed_hosts[i % 2], 1)
            for i in range(50)
        ))
        assert sum(many) == 3
        assert await inx.daily_send_remaining("forecasteconomy.com") == 0
        assert await inx.daily_send_remaining("ru.forecasteconomy.com") == 0

    asyncio.run(scenario())


def test_indexnow_daily_send_ceiling_cannot_be_configured_above_30k(monkeypatch):
    import app.services.indexnow as inx

    monkeypatch.setattr(inx.settings, "indexnow_daily_send_cap", 50_000)
    assert inx.daily_send_cap() == 30_000


def test_manual_indexnow_apply_defaults_skip_large_us_history_and_obey_quota(monkeypatch):
    import importlib.util
    from pathlib import Path

    script_path = Path(__file__).resolve().parents[1] / "scripts" / "indexnow-ping-all.py"
    spec = importlib.util.spec_from_file_location("indexnow_ping_all", script_path)
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)

    grouped = {
        "core": ["/"],
        "world-indicators-1": ["/united-states/indicator/gdp"],
        "regional-years-1": ["/russia/region/a/gdp/2024"],
        "world-years-1": ["/germany/indicator/gdp/2024"],
        "world-region-years-1": ["/united-states/region/california/gdp/2024"],
    }
    selected, unknown = script.select_sections(grouped, None)
    assert not unknown
    assert selected == ["core", "world-indicators-1"]
    explicit, unknown = script.select_sections(grouped, ["world-region-years-1"])
    assert not unknown and explicit == ["world-region-years-1"]

    sent = []

    async def reject_quota(_host, _count):
        return False

    class FakeClient:
        async def post(self, *args, **kwargs):
            sent.append((args, kwargs))

    monkeypatch.setattr(script, "reserve_daily_send_quota", reject_quota)
    result = asyncio.run(
        script.ping_section(
            FakeClient(), ["/united-states/region/california/gdp/2024"],
            base="https://forecasteconomy.com", host="forecasteconomy.com",
        )
    )
    assert result == {-2: 1}
    assert sent == []


def test_indexnow_drain_obeys_daily_send_cap_and_resumes_next_utc_day(monkeypatch):
    import fakeredis.aioredis
    import app.core.cache as cache_mod
    import app.services.indexnow as inx

    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    now = [datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc)]
    posts = []

    async def _get_state_redis():
        return redis

    class _FakeResponse:
        status_code = 200
        text = "ok"

    class _FakeClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, json=None):
            posts.append(json)
            return _FakeResponse()

    monkeypatch.setattr(cache_mod, "get_state_redis", _get_state_redis)
    monkeypatch.setattr(inx, "_utc_now", lambda: now[0])
    monkeypatch.setattr(inx.httpx, "AsyncClient", _FakeClient)
    monkeypatch.setattr(inx.settings, "indexnow_enabled", True)
    monkeypatch.setattr(inx.settings, "indexnow_key", "k" * 32)
    monkeypatch.setattr(inx.settings, "indexnow_daily_send_cap", 2)

    async def scenario():
        host = inx.settings.public_host
        await inx.enqueue_paths([f"/indicator/{n}" for n in range(3)], host=host)
        sent_today = await inx.drain_indexnow_queue()
        blocked_today = await inx.drain_indexnow_queue()
        queued_today = await redis.scard(f"in:queue:{host}")
        now[0] = datetime(2026, 9, 25, 0, 0, tzinfo=timezone.utc)
        sent_tomorrow = await inx.drain_indexnow_queue()
        return sent_today, blocked_today, queued_today, sent_tomorrow

    assert asyncio.run(scenario()) == (2, 0, 1, 1)
    assert [len(post["urlList"]) for post in posts] == [2, 1]


def test_indexnow_drain_shares_daily_cap_between_apex_and_ru(monkeypatch):
    import fakeredis.aioredis
    import app.core.cache as cache_mod
    import app.services.indexnow as inx
    import app.services.locale as locale_mod

    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    now = [datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc)]
    posts = []

    async def _get_state_redis():
        return redis

    class _FakeResponse:
        status_code = 200
        text = "ok"

    class _FakeClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, json=None):
            posts.append(json)
            return _FakeResponse()

    monkeypatch.setattr(cache_mod, "get_state_redis", _get_state_redis)
    monkeypatch.setattr(inx, "_utc_now", lambda: now[0])
    monkeypatch.setattr(inx.httpx, "AsyncClient", _FakeClient)
    monkeypatch.setattr(inx.settings, "indexnow_enabled", True)
    monkeypatch.setattr(inx.settings, "indexnow_key", "k" * 32)
    monkeypatch.setattr(inx.settings, "indexnow_daily_send_cap", 4)
    monkeypatch.setattr(inx.settings, "apex_locale_en", True)
    monkeypatch.setattr(locale_mod, "ru_public_origin", lambda: "https://ru.forecasteconomy.com")

    async def scenario():
        apex = inx.settings.public_host
        ru = "ru.forecasteconomy.com"
        await inx.enqueue_paths([f"/apex/{n}" for n in range(10)], host=apex)
        await inx.enqueue_paths([f"/ru/{n}" for n in range(10)], host=ru)
        sent_today = await inx.drain_indexnow_queue(limit=4)
        remaining_apex = await redis.scard(f"in:queue:{apex}")
        remaining_ru = await redis.scard(f"in:queue:{ru}")
        await redis.delete(f"in:queue:{apex}")
        now[0] = datetime(2026, 9, 25, 0, 0, tzinfo=timezone.utc)
        sent_tomorrow = await inx.drain_indexnow_queue(limit=4)
        return sent_today, remaining_apex, remaining_ru, sent_tomorrow

    assert asyncio.run(scenario()) == (4, 8, 8, 4)
    assert [post["host"] for post in posts] == [
        inx.settings.public_host,
        "ru.forecasteconomy.com",
        "ru.forecasteconomy.com",
    ]
    assert [len(post["urlList"]) for post in posts] == [2, 2, 4]
    assert sum(len(post["urlList"]) for post in posts[:2]) == 4
    assert sum(len(post["urlList"]) for post in posts[2:]) == 4


def test_ping_full_site_delegates_to_static_sections(monkeypatch):
    """Полный пинг не тянет years-чанки: только ping_sections."""
    import app.services.indexnow as inx

    called = {}

    async def fake_ping_sections(db, *, origin=None, host=None):
        called["origin"] = origin
        called["host"] = host
        called["db"] = db
        return 12

    monkeypatch.setattr(inx, "ping_sections", fake_ping_sections)
    n = asyncio.run(
        inx.ping_full_site(
            object(),
            origin="https://ru.forecasteconomy.com",
            host="ru.forecasteconomy.com",
        )
    )
    assert n == 12
    assert called["host"] == "ru.forecasteconomy.com"
    assert called["origin"] == "https://ru.forecasteconomy.com"


def test_path_year_from_history_urls():
    import app.services.indexnow as inx

    assert inx.path_year("/russia/region/moskva/chislennost-naseleniya/2018") == 2018
    assert inx.path_year("/russia/indicator/cpi/2018-01") == 2018
    assert inx.path_year("/austria/indicator/at-x/1996") == 1996
    assert inx.path_year("/russia/region/moskva/chislennost-naseleniya") is None


def _history_env(monkeypatch, *, cap=3, apex=False):
    import fakeredis.aioredis
    import app.core.cache as cache_mod
    import app.services.indexnow as inx
    from app.services.site_urls import SiteUrl

    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)

    async def _get_state_redis():
        return redis

    chunks = {
        "regional-years-1": [
            SiteUrl("/russia/region/a/pop/2010", "2020-01-01", "yearly", "0.5"),
            SiteUrl("/russia/region/a/pop/2018", "2020-01-01", "yearly", "0.5"),
            SiteUrl("/russia/region/a/pop/2019", "2020-01-01", "yearly", "0.5"),
            SiteUrl("/russia/region/b/pop/2020", "2020-01-01", "yearly", "0.5"),
        ],
        "regional-years-2": [
            SiteUrl("/russia/region/c/pop/2005", "2020-01-01", "yearly", "0.5"),
            SiteUrl("/russia/region/c/pop/2021", "2020-01-01", "yearly", "0.5"),
            SiteUrl("/russia/region/d/pop/2022", "2020-01-01", "yearly", "0.5"),
        ],
    }

    async def fake_names(_db):
        return ["regional-years-1", "regional-years-2"]

    async def fake_resolve(_db, section):
        return chunks[section]

    async def fake_demand(_db, *, days=30, limit=150, host=None):
        return [("/russia/indicator/cpi", 10)]

    async def fake_item_counts(_db):
        return {"regional-years-": 7}

    monkeypatch.setattr(cache_mod, "get_state_redis", _get_state_redis)
    monkeypatch.setattr(inx, "_history_section_names", fake_names)
    monkeypatch.setattr("app.services.site_urls.resolve_section", fake_resolve)
    monkeypatch.setattr("app.services.site_urls.chunk_item_counts", fake_item_counts)
    monkeypatch.setattr(
        "app.services.demand_router.priority_recrawl_paths", fake_demand
    )
    monkeypatch.setattr(inx.settings, "indexnow_enabled", True)
    monkeypatch.setattr(inx.settings, "indexnow_key", "k" * 32)
    monkeypatch.setattr(inx.settings, "indexnow_history_daily_cap", cap)
    monkeypatch.setattr(inx.settings, "indexnow_history_year_min", 2018)
    monkeypatch.setattr(inx.settings, "apex_locale_en", apex)
    return redis, inx


def test_indexnow_history_prefers_fresh_years_and_respects_cap(monkeypatch):
    redis, inx = _history_env(monkeypatch, cap=3)

    async def scenario():
        stats = await inx.enqueue_history_urls(object())
        host = inx.settings.public_host
        queued = await redis.smembers(f"in:queue:{host}")
        return stats, queued

    stats, queued = asyncio.run(scenario())
    assert stats["queued"] == 3
    assert queued == {
        "/russia/indicator/cpi",
        "/russia/region/a/pop/2018",
        "/russia/region/a/pop/2019",
    }
    assert "/russia/region/a/pop/2010" not in queued
    assert stats["phase"] == 0


def test_indexnow_history_cursor_continues_next_day(monkeypatch):
    redis, inx = _history_env(monkeypatch, cap=3)

    async def scenario():
        await inx.enqueue_history_urls(object())
        await redis.delete(f"in:queue:{inx.settings.public_host}")
        stats = await inx.enqueue_history_urls(object())
        queued = await redis.smembers(f"in:queue:{inx.settings.public_host}")
        return stats, queued

    stats, queued = asyncio.run(scenario())
    assert "/russia/region/b/pop/2020" in queued
    assert "/russia/region/c/pop/2021" in queued
    assert "/russia/region/a/pop/2018" not in queued
    assert stats["queued"] == 3


def test_indexnow_history_legacy_phase_after_fresh(monkeypatch):
    redis, inx = _history_env(monkeypatch, cap=10)

    async def scenario():
        stats = await inx.enqueue_history_urls(object())
        queued = await redis.smembers(f"in:queue:{inx.settings.public_host}")
        return stats, queued

    stats, queued = asyncio.run(scenario())
    assert "/russia/region/a/pop/2018" in queued
    assert "/russia/region/a/pop/2010" in queued
    assert "/russia/region/c/pop/2005" in queued
    assert stats["queued"] == 8
    assert stats["phase"] == 2


def test_indexnow_history_skips_chunks_when_queue_backed_up(monkeypatch):
    redis, inx = _history_env(monkeypatch, cap=3)
    host = inx.settings.public_host

    async def scenario():
        await redis.sadd(f"in:queue:{host}", *[f"/pad/{i}" for i in range(5)])
        stats = await inx.enqueue_history_urls(object())
        members = await redis.smembers(f"in:queue:{host}")
        return stats, members

    stats, members = asyncio.run(scenario())
    assert stats["backed_up"] is True
    assert "/russia/region/a/pop/2018" not in members
    assert "/russia/indicator/cpi" in members


def test_indexnow_history_enqueues_both_hosts_after_cutover(monkeypatch):
    redis, inx = _history_env(monkeypatch, cap=12, apex=True)

    async def scenario():
        await inx.enqueue_history_urls(object())
        apex = await redis.smembers(f"in:queue:{inx.settings.public_host}")
        ru = await redis.smembers("in:queue:ru.forecasteconomy.com")
        return apex, ru

    apex, ru = asyncio.run(scenario())
    assert "/russia/region/a/pop/2018" in apex
    assert apex == ru


def test_indexnow_history_uses_all_registered_chunked_sections(monkeypatch):
    """Новая группа sitemap автоматически участвует в bounded-обходе."""
    import app.services.indexnow as inx
    import app.services.site_urls as site_urls

    names = [
        "core", "world-regions", "months-1", "world-indicators-1",
        "regional-1", "regional-years-1", "world-years-1", "future-1",
    ]

    async def fake_names(_db):
        return names

    monkeypatch.setattr(site_urls, "section_names", fake_names)
    monkeypatch.setitem(site_urls._CHUNKED_SOURCES, "future-", object())
    assert asyncio.run(inx._history_section_names(object())) == names[2:]


@pytest.mark.parametrize("old_phase", [0, 1, 2])
def test_indexnow_history_migrates_legacy_cursor_without_skipping_cards(
    monkeypatch, old_phase,
):
    """Старый offset/фаза/14-дневный отдых не пропускают добавленные карточки."""
    import json
    import app.services.indexnow as inx
    import app.services.site_urls as site_urls
    from app.services.display import today_msk

    select_sections = inx._history_section_names
    redis, inx = _history_env(monkeypatch, cap=3)

    async def fake_names(_db):
        return ["core", "world-indicators-1", "regional-1"]

    async def fake_resolve(_db, section):
        return [{"path": {
            "world-indicators-1": "/germany/indicator/gdp",
            "regional-1": "/russia/region/tulskaya-oblast/wages",
        }[section]}]

    monkeypatch.setattr(inx, "_history_section_names", select_sections)
    monkeypatch.setattr(site_urls, "section_names", fake_names)
    monkeypatch.setattr(site_urls, "resolve_section", fake_resolve)

    async def scenario():
        await redis.set(inx._HISTORY_CURSOR_KEY, json.dumps({
            "phase": old_phase, "i": 12, "skip": 625,
            "done_on": today_msk().isoformat(),
        }))
        stats = await inx.enqueue_history_urls(object())
        queued = await redis.smembers(f"in:queue:{inx.settings.public_host}")
        cursor = json.loads(await redis.get(inx._HISTORY_CURSOR_KEY))
        return stats, queued, cursor

    stats, queued, cursor = asyncio.run(scenario())
    assert stats["queued"] == 3
    assert not stats["resting"]
    assert queued == {
        "/russia/indicator/cpi", "/germany/indicator/gdp",
        "/russia/region/tulskaya-oblast/wages",
    }
    assert cursor["version"] == inx._HISTORY_CURSOR_VERSION


def test_indexnow_history_visits_all_chunk_types_with_cap_and_no_post(monkeypatch):
    """Два хоста получают все карточки/периоды малыми порциями, один раз за цикл."""
    import collections
    import json
    import app.services.indexnow as inx
    import app.services.site_urls as site_urls

    select_sections = inx._history_section_names
    redis, inx = _history_env(monkeypatch, cap=3, apex=True)
    chunks = {
        "months-1": ["/russia/indicator/cpi/2001-01", "/russia/indicator/cpi/2025-01"],
        "world-indicators-1": ["/germany/indicator/gdp", "/us/indicator/gdp"],
        "regional-1": ["/russia/region/tulskaya-oblast/wages"],
        "regional-years-1": ["/russia/region/tulskaya-oblast/wages/2024"],
        "world-years-1": ["/germany/indicator/gdp/2001", "/germany/indicator/gdp/2025"],
        "world-region-years-1": [
            "/united-states/region/california/gdp/2001",
            "/united-states/region/texas/gdp/2025",
        ],
    }

    async def fake_names(_db):
        return ["core", *chunks]

    async def fake_resolve(_db, section):
        return [{"path": path} for path in chunks[section]]

    async def fake_item_counts(_db):
        return {
            prefix: len(paths)
            for prefix, paths in (
                ("months-", chunks["months-1"]),
                ("world-indicators-", chunks["world-indicators-1"]),
                ("regional-", chunks["regional-1"]),
                ("regional-years-", chunks["regional-years-1"]),
                ("world-years-", chunks["world-years-1"]),
                ("world-region-years-", chunks["world-region-years-1"]),
            )
        }

    async def no_post(*args, **kwargs):
        pytest.fail("enqueue_history_urls must not send network requests")

    monkeypatch.setattr(inx, "_history_section_names", select_sections)
    monkeypatch.setattr(site_urls, "section_names", fake_names)
    monkeypatch.setattr(site_urls, "resolve_section", fake_resolve)
    monkeypatch.setattr(site_urls, "chunk_item_counts", fake_item_counts)
    monkeypatch.setattr(inx, "ping_urls", no_post)

    async def scenario():
        seen = collections.Counter()
        hosts = [inx.settings.public_host, "ru.forecasteconomy.com"]
        for _ in range(10):
            stats = await inx.enqueue_history_urls(object())
            queues = [await redis.smembers(f"in:queue:{host}") for host in hosts]
            assert queues[0] == queues[1]
            assert stats["queued"] <= 12
            assert len(queues[0]) <= 12
            seen.update(queues[0] - {"/russia/indicator/cpi"})
            for host in hosts:
                await redis.delete(f"in:queue:{host}")
            cursor = json.loads(await redis.get(inx._HISTORY_CURSOR_KEY))
            assert cursor["version"] == inx._HISTORY_CURSOR_VERSION
            if cursor["phase"] == 2:
                assert (await inx.enqueue_history_urls(object()))["resting"]
                return seen
        pytest.fail("bounded cursor did not finish its complete two-phase pass")

    seen = asyncio.run(scenario())
    assert seen == collections.Counter(path for paths in chunks.values() for path in paths)


def test_indexnow_history_proportionally_reserves_daily_share_for_us_state_years(monkeypatch):
    import fakeredis.aioredis
    import app.core.cache as cache_mod
    import app.services.indexnow as inx
    import app.services.site_urls as site_urls

    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    prefixes = [
        "months-", "world-indicators-", "regional-", "regional-years-",
        "world-years-", "world-region-years-",
    ]
    names = [f"{prefix}1" for prefix in prefixes]
    paths_by_section = {}
    counts = {}
    for prefix, name in zip(prefixes, names):
        size = 500 if prefix == "world-region-years-" else 100
        counts[prefix] = size
        if prefix == "months-":
            paths_by_section[name] = [
                f"/russia/indicator/cpi-{i}/2000-01" for i in range(size)
            ]
        elif prefix == "world-indicators-":
            paths_by_section[name] = [f"/germany/indicator/gdp-{i}" for i in range(size)]
        elif prefix == "regional-":
            paths_by_section[name] = [f"/russia/region/a/wage-{i}" for i in range(size)]
        elif prefix == "regional-years-":
            paths_by_section[name] = [
                f"/russia/region/a/wage-{i}/{2000 + i % 100}" for i in range(size)
            ]
        elif prefix == "world-years-":
            paths_by_section[name] = [
                f"/germany/indicator/gdp-{i}/{2000 + i % 100}" for i in range(size)
            ]
        else:
            paths_by_section[name] = [
                f"/united-states/region/california/gdp-{i}/{2000 + i % 100}"
                for i in range(size)
            ]

    async def _get_state_redis():
        return redis

    async def fake_names(_db):
        return names

    async def fake_resolve(_db, section):
        return [{"path": path} for path in paths_by_section[section]]

    async def fake_item_counts(_db):
        return counts

    async def no_demand(_db, *, days=30, limit=150, host=None):
        return []

    monkeypatch.setattr(cache_mod, "get_state_redis", _get_state_redis)
    monkeypatch.setattr(inx, "_history_section_names", fake_names)
    monkeypatch.setattr(site_urls, "resolve_section", fake_resolve)
    monkeypatch.setattr(site_urls, "chunk_item_counts", fake_item_counts)
    monkeypatch.setattr("app.services.demand_router.priority_recrawl_paths", no_demand)
    monkeypatch.setattr(inx.settings, "indexnow_enabled", True)
    monkeypatch.setattr(inx.settings, "indexnow_key", "k" * 32)
    monkeypatch.setattr(inx.settings, "indexnow_history_daily_cap", 300)
    monkeypatch.setattr(inx.settings, "apex_locale_en", False)

    async def scenario():
        stats = await inx.enqueue_history_urls(object())
        queued = await redis.smembers(f"in:queue:{inx.settings.public_host}")
        return stats, queued

    stats, queued = asyncio.run(scenario())
    assert len(queued) == 300
    assert stats["queued"] == 300
    assert stats["families"]["world-region-years-"] >= 140
    for prefix in prefixes[:-1]:
        assert stats["families"][prefix] >= 25


# ---------------------------------------------------------------------------
# Маршруты /seo/* (monkeypatch рендеров — без БД)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("path,renderer", [
    ("/seo/today", "render_today_hub_html"),
    ("/seo/region-rating/some-code", "render_region_rating_html"),
    ("/seo/regions/map/some-code", "render_regions_map_html"),
])
def test_seo_routes_no_args(client, monkeypatch, path, renderer):
    from app.api import seo_pages

    async def fake(*args, **kwargs):
        return 200, "<html><body>ok</body></html>"

    monkeypatch.setattr(seo_pages, renderer, fake)
    r = client.get(path)
    assert r.status_code == 200
    assert "ok" in r.text


def test_seo_regions_map_legacy_query_redirects(client):
    """Legacy share URL → канон /russia/region/map/{code}?year=."""
    r = client.get(
        "/seo/regions",
        params={"view": "map", "indicator": "uroven-bezrabotitsy", "year": "2015"},
        follow_redirects=False,
    )
    assert r.status_code == 301
    assert r.headers["location"].endswith(
        "/russia/region/map/uroven-bezrabotitsy?year=2015"
    )


def test_seo_region_vs_route_parses_pair(client, monkeypatch):
    from app.api import seo_pages

    seen = {}

    async def fake(slug_a, slug_b, db):
        seen["pair"] = (slug_a, slug_b)
        return 200, "<html><body>vs</body></html>"

    monkeypatch.setattr(seo_pages, "render_region_vs_html", fake)
    r = client.get("/seo/region-vs/moskva-vs-sankt-peterburg")
    assert r.status_code == 200
    # Жадный матч slug_a до последнего «-vs-» — оба реальных slug'а без «-vs-».
    assert seen["pair"] == ("moskva", "sankt-peterburg")


def test_seo_calendar_month_route(client, monkeypatch):
    from app.api import seo_pages

    async def fake(year, month, db):
        assert (year, month) == (2026, 7)
        return 200, "<html><body>calendar</body></html>"

    monkeypatch.setattr(seo_pages, "render_calendar_month_html", fake)
    assert client.get("/seo/calendar-month/2026/07").status_code == 200


# ---------------------------------------------------------------------------
# Рендеры с данными (герметичный SQLite)
# ---------------------------------------------------------------------------

@pytest.fixture
def seeded_env(auth_env):
    """Мини-датасет: индикатор, 12 регионов, региональный показатель, события."""
    from app.models import (
        EconomicEvent,
        Indicator,
        IndicatorData,
        Region,
        RegionDataPoint,
        RegionIndicator,
    )

    async def _seed():
        async with auth_env["session_maker"]() as s:
            usd = Indicator(
                code="usd-rub", name="Курс доллара США", unit="руб.",
                category="Валюты", source="Банк России", frequency="daily",
                parser_type="cbr_fx", is_active=True, is_listed=True,
            )
            s.add(usd)
            await s.flush()
            # Даты относительные: freshness-guard (В-4) не должен сработать
            # на свежесеянных данных независимо от текущей даты запуска.
            for i, v in enumerate([76.5, 77.0, 77.2]):
                s.add(IndicatorData(
                    indicator_id=usd.id,
                    date=date.today() - timedelta(days=2 - i),
                    value=v,
                ))

            # Умерший ETL: дневной ряд, последняя точка 30 дней назад (> SLA 7).
            gold = Indicator(
                code="gold-price", name="Цена золота", unit="руб./г",
                category="Товарные рынки", source="Банк России", frequency="daily",
                parser_type="cbr_metals", is_active=True, is_listed=True,
            )
            s.add(gold)
            await s.flush()
            for i, v in enumerate([7100.0, 7150.0]):
                s.add(IndicatorData(
                    indicator_id=gold.id,
                    date=date.today() - timedelta(days=31 - i),
                    value=v,
                ))

            rf = Region(slug="russia", name="Российская Федерация", kind="country", sort_order=0)
            s.add(rf)
            regions = []
            for i in range(12):
                r = Region(slug=f"region-{i}", name=f"Регион {i}", kind="region",
                           district_slug="cfo", sort_order=i + 1)
                regions.append(r)
                s.add(r)
            await s.flush()

            pop = RegionIndicator(
                code="chislennost-naseleniya", table_code="1.1", section_num=1,
                section_name="Население", name="Численность населения",
                unit="тыс. человек", is_listed=True,
            )
            s.add(pop)
            await s.flush()
            for i, r in enumerate(regions):
                for year in (2022, 2023):
                    s.add(RegionDataPoint(
                        indicator_id=pop.id, region_id=r.id, year=year,
                        value=1000 + i * 100 + (year - 2022) * 5,
                    ))
            s.add(RegionDataPoint(indicator_id=pop.id, region_id=rf.id,
                                  year=2023, value=146000))

            # События с полным provenance — SSR-календарь показывает только
            # source-bound строки (В-7: тот же фильтр, что и публичный API).
            for day in (4, 11, 18):
                s.add(EconomicEvent(
                    title=f"Публикация {day}", event_type="release",
                    source="rosstat", scheduled_date=date(2026, 7, day),
                    event_key=f"test-{day}", is_estimated=False,
                    date_confidence="official_explicit",
                    source_url="https://rosstat.gov.ru/calendar",
                    source_hash=f"hash-{day}",
                    last_seen_at=datetime(2026, 7, 1, 12, 0),
                ))
            await s.commit()

    asyncio.run(_seed())
    return auth_env


def test_render_today_pages(seeded_env):
    with TestClient(seeded_env["app"]) as tc:
        r = tc.get("/seo/today/usd-rub")
        assert r.status_code == 200
        assert "Курс доллара сегодня" in r.text
        assert "77,2" in r.text  # русская типографика, без английской точки
        assert 'canonical" href="https://forecasteconomy.com/russia/today/usd-rub"' in r.text

        hub = tc.get("/seo/today")
        assert hub.status_code == 200
        assert "Экономика России сегодня" in hub.text
        assert "/russia/today/usd-rub" in hub.text

        # React-гидратация: полный layout платформы (Navbar, ticker, графики)
        assert 'type="module"' in r.text or "/assets/" in r.text

        # 404 — не голый текст, а брендовая страница с навигацией
        nf = tc.get("/seo/today/no-such-code")
        assert nf.status_code == 404
        assert "<html" in nf.text and 'class="seo-topbar"' in nf.text
        assert "noindex" in nf.text


def test_today_freshness_guard(seeded_env):
    """В-4: устаревший ряд не продаётся как «сегодня» — честная рамка."""
    with TestClient(seeded_env["app"]) as tc:
        r = tc.get("/seo/today/gold-price")
        assert r.status_code == 200
        assert "Цена золота — последнее значение" in r.text
        assert "Последнее доступное значение" in r.text
        assert "Новых публикаций источника пока нет" in r.text
        # заголовок не обещает сегодняшнюю дату
        assert "Цена золота сегодня," not in r.text

        # свежий ряд по-прежнему в «сегодня»-рамке
        fresh = tc.get("/seo/today/usd-rub")
        assert "Курс доллара сегодня" in fresh.text
        assert "Новых публикаций источника пока нет" not in fresh.text


def test_is_stale_thresholds():
    from app.services.seo_today import is_stale

    today = date(2026, 7, 6)
    assert not is_stale("daily", today - timedelta(days=5), today)
    assert is_stale("daily", today - timedelta(days=8), today)
    assert not is_stale("weekly", today - timedelta(days=14), today)
    assert is_stale("weekly", today - timedelta(days=30), today)
    assert not is_stale("monthly", today - timedelta(days=60), today)
    assert is_stale("monthly", today - timedelta(days=90), today)
    # неизвестная частота — дефолт как monthly
    assert not is_stale(None, today - timedelta(days=60), today)


def test_render_region_rating(seeded_env):
    with TestClient(seeded_env["app"]) as tc:
        r = tc.get("/seo/region-rating/chislennost-naseleniya")
        assert r.status_code == 200
        # Население вне curated-полярности → нейтральная подача, не «рейтинг достижений».
        assert "сравнение регионов России" in r.text
        assert "Первые места" not in r.text
        assert "Наибольшие значения" in r.text
        assert "Регион 11" in r.text  # наибольшее значение
        assert "/russia/region/region-11/chislennost-naseleniya" in r.text
        assert "146" in r.text  # общероссийское значение упомянуто
        assert "/russia/region/map/chislennost-naseleniya" in r.text


def test_render_regions_map(seeded_env):
    with TestClient(seeded_env["app"]) as tc:
        r = tc.get("/seo/regions/map/chislennost-naseleniya")
        assert r.status_code == 200
        assert "на карте регионов России" in r.text
        assert 'canonical" href="https://forecasteconomy.com/russia/region/map/chislennost-naseleniya"' in r.text
        assert "/og/russia/region-rating/chislennost-naseleniya.png" in r.text
        assert "/russia/region-rating/chislennost-naseleniya" in r.text

        with_year = tc.get("/seo/regions/map/chislennost-naseleniya?year=2022")
        assert with_year.status_code == 200
        assert "2022" in with_year.text
        assert 'canonical" href="https://forecasteconomy.com/russia/region/map/chislennost-naseleniya?year=2022"' in with_year.text

        overview = tc.get("/seo/regions/map/overview")
        assert overview.status_code == 200
        assert "Карта регионов России" in overview.text


def test_render_region_vs(seeded_env):
    with TestClient(seeded_env["app"]) as tc:
        r = tc.get("/seo/region-vs/region-0-vs-region-1")
        assert r.status_code == 200
        assert "сравнение по ключевым показателям" in r.text
        assert "Численность населения" in r.text
        # canonical — упорядоченная пара
        assert 'canonical" href="https://forecasteconomy.com/russia/region-vs/region-0-vs-region-1"' in r.text


def test_render_calendar_month(seeded_env):
    with TestClient(seeded_env["app"]) as tc:
        r = tc.get("/seo/calendar-month/2026/07")
        assert r.status_code == 200
        assert "Календарь статистики: июль 2026" in r.text
        assert "Росстат" in r.text
        # месяц без событий → 404
        assert tc.get("/seo/calendar-month/2031/01").status_code == 404


def test_sitemap_sections(seeded_env):
    with TestClient(seeded_env["app"]) as tc:
        idx = tc.get("/sitemap.xml")
        assert idx.status_code == 200
        assert "<sitemapindex" in idx.text
        assert "/sitemap-core.xml" in idx.text
        assert "/sitemap-regional-1.xml" in idx.text

        core = tc.get("/sitemap-core.xml")
        assert core.status_code == 200
        assert "/russia/indicator/usd-rub" in core.text
        assert "/__honeypot__" not in core.text
        assert "links-exchange" not in core.text

        ratings = tc.get("/sitemap-ratings.xml")
        assert ratings.status_code == 200
        assert "/russia/region-rating/chislennost-naseleniya" in ratings.text

        maps = tc.get("/sitemap-maps.xml")
        assert maps.status_code == 200
        assert "/russia/region/map/chislennost-naseleniya" in maps.text

        assert tc.get("/sitemap-nope.xml").status_code == 404


def test_sitemap_core_omits_honeypot(seeded_env):
    """Ханипот не в карте: Яндекс ходит по sitemap, honeytrap банит с 1 хита."""
    with TestClient(seeded_env["app"]) as tc:
        core = tc.get("/sitemap-core.xml")
        assert core.status_code == 200
        assert "/__honeypot__" not in core.text
        assert "links-exchange" not in core.text


def test_sitemap_locs_follow_request_host(seeded_env, monkeypatch):
    """Host-aware sitemap: ru. Host → absolute loc on ru.; default Host → DOMAIN."""
    with TestClient(seeded_env["app"]) as tc:
        apex = tc.get("/sitemap.xml")
        assert apex.status_code == 200
        assert "https://forecasteconomy.com/sitemap-core.xml" in apex.text

        ru = tc.get(
            "/sitemap.xml",
            headers={"host": "ru.forecasteconomy.com"},
        )
        assert ru.status_code == 200
        assert "<sitemapindex" in ru.text
        assert "https://ru.forecasteconomy.com/sitemap-core.xml" not in ru.text
        assert "https://forecasteconomy.com/sitemap-core.xml" not in ru.text

        ru_core = tc.get(
            "/sitemap-core.xml",
            headers={"host": "ru.forecasteconomy.com"},
        )
        # Before cutover, neither the index nor direct child URLs advertise RU.
        assert ru_core.status_code == 404
        from app.config import settings
        monkeypatch.setattr(settings, "apex_locale_en", True)
        ru_core = tc.get("/sitemap-core.xml", headers={"host": "ru.forecasteconomy.com"})
        assert ru_core.status_code == 200
        assert "https://ru.forecasteconomy.com/russia/" in ru_core.text
        assert "https://forecasteconomy.com/russia/" not in ru_core.text


def test_rss_robots_llms_follow_request_host(seeded_env):
    """RSS / robots.txt / llms.txt absolute URLs follow request Host."""
    with TestClient(seeded_env["app"]) as tc:
        apex_feed = tc.get("/feed.xml")
        assert apex_feed.status_code == 200
        assert "https://forecasteconomy.com/feed.xml" in apex_feed.text
        assert "https://forecasteconomy.com/russia/indicator/" in apex_feed.text

        ru_feed = tc.get(
            "/feed.xml",
            headers={"host": "ru.forecasteconomy.com"},
        )
        assert ru_feed.status_code == 200
        assert "https://ru.forecasteconomy.com/feed.xml" in ru_feed.text
        assert "https://ru.forecasteconomy.com/russia/indicator/" in ru_feed.text
        assert "https://forecasteconomy.com/feed.xml" not in ru_feed.text

        apex_robots = tc.get("/robots.txt")
        assert apex_robots.status_code == 200
        assert "Host:" not in apex_robots.text
        assert "Sitemap: https://forecasteconomy.com/sitemap.xml" in apex_robots.text

        ru_robots = tc.get(
            "/robots.txt",
            headers={"host": "ru.forecasteconomy.com"},
        )
        assert ru_robots.status_code == 200
        assert "Host:" not in ru_robots.text
        assert "Sitemap: https://ru.forecasteconomy.com/sitemap.xml" in ru_robots.text
        assert "User-agent: MJ12bot\nDisallow: /" in ru_robots.text
        assert "User-agent: MJ12bot\nDisallow: /" in apex_robots.text

        apex_llms = tc.get("/llms.txt")
        assert apex_llms.status_code == 200
        assert "https://forecasteconomy.com/sitemap.xml" in apex_llms.text

        ru_llms = tc.get(
            "/llms.txt",
            headers={"host": "ru.forecasteconomy.com"},
        )
        assert ru_llms.status_code == 200
        assert "https://ru.forecasteconomy.com/sitemap.xml" in ru_llms.text
        assert "https://forecasteconomy.com/sitemap.xml" not in ru_llms.text


def test_seo_static_templates_match_frontend_public():
    """Backend templates stay byte-identical to frontend/public placeholders."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    for name in ("robots.txt", "llms.txt"):
        backend = (root / "backend/app/data/seo_static" / name).read_text(encoding="utf-8")
        frontend = (root / "frontend/public" / name).read_text(encoding="utf-8")
        assert backend == frontend, f"{name} drifted between backend and frontend"


def _robots_group(text: str, agent: str) -> str:
    """Тело одной секции User-agent до следующей секции или Clean-param."""
    start = text.index(f"User-agent: {agent}\n")
    rest = text[start:]
    end = len(rest)
    for marker in ("\nUser-agent:", "\nClean-param:", "\nSitemap:"):
        idx = rest.find(marker, 1)
        if idx != -1:
            end = min(end, idx)
    return rest[:end]


def test_robots_noindex_pages_stay_crawlable():
    """Каталог ~5 млн URL на хост обходится. noindex не экономит этот обход.

    Конечный набор /login /register /account остаётся открытым, чтобы робот
    прочитал noindex. /assets/ и /index.html не закрываем. /embed/ закрыт:
    виджеты масштабируются каталогом. Неканонические query закрыты у * и
    Googlebot (своя секция не наследует *). У Яндекса тех же query нет:
    склейка через Clean-param. ?year= — канон карты, открыт.
    """
    from pathlib import Path

    root = Path(__file__).resolve().parents[2] / "backend/app/data/seo_static"
    open_needles = (
        "Disallow: /login\n",
        "Disallow: /register\n",
        "Disallow: /account\n",
        "Disallow: /assets/\n",
        "Disallow: /index.html\n",
        "Disallow: /*?year=",
        "Disallow: /*?preview_locale",
    )
    query_firewall = (
        "Disallow: /compare?\n",
        "Disallow: /*?mode=\n",
        "Disallow: /*&mode=\n",
        "Disallow: /*?view=\n",
        "Disallow: /*&view=\n",
    )
    for name in ("robots.txt", "robots.en.txt"):
        text = (root / name).read_text(encoding="utf-8")
        star = _robots_group(text, "*")
        yandex = _robots_group(text, "Yandex")
        google = _robots_group(text, "Googlebot")
        for needle in open_needles:
            assert needle not in text, f"{name} still has {needle!r}"
        assert "Disallow: /embed/\n" in star
        assert "Disallow: /embed/\n" in yandex
        assert "Disallow: /embed/\n" in google
        for needle in query_firewall:
            assert needle in star, f"{name} * missing {needle!r}"
            assert needle in google, f"{name} Googlebot missing {needle!r}"
            assert needle not in yandex, f"{name} Yandex must not {needle!r}"
        assert "Disallow: /api/\n" in text
        assert "Disallow: /__honeypot__/\n" in text
        assert "Disallow: /russia/util/\n" in text
        assert "Allow: /\n" in text
        assert "Clean-param: codes /compare\n" in text
        assert "Clean-param: view\n" in text
        assert "mode&preview_locale" in text


def test_robots_mj12_disallow_on_ru_and_en_templates():
    """Apex EN cutover отдаёт robots.en.txt — MJ12 должен быть в обоих шаблонах."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[2] / "backend/app/data/seo_static"
    needle = "User-agent: MJ12bot\nDisallow: /"
    for name in ("robots.txt", "robots.en.txt"):
        text = (root / name).read_text(encoding="utf-8")
        assert needle in text, f"{name} missing MJ12bot Disallow"


def _unique_internal_beyond_nav(html: str) -> set[str]:
    """Внутренние href вне элементов <nav> (хлебные крошки)."""
    import re
    from html.parser import HTMLParser

    class _P(HTMLParser):
        def __init__(self):
            super().__init__()
            self.hrefs: list[str] = []
            self.nav: list[str] = []
            self._depth = 0

        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if tag == "nav":
                self._depth += 1
            if tag == "a" and "href" in attrs:
                h = attrs["href"].split("?", 1)[0]
                if h.startswith("/") and not h.startswith("//"):
                    self.hrefs.append(h)
                    if self._depth:
                        self.nav.append(h)

        def handle_endtag(self, tag):
            if tag == "nav" and self._depth:
                self._depth -= 1

    p = _P()
    p.feed(html)
    skip = {".png", ".js", ".css"}
    internal = [
        h for h in p.hrefs
        if not h.startswith("/assets") and not any(h.endswith(s) for s in skip)
    ]
    return set(internal) - set(p.nav)


def test_ssr_public_pages_have_deep_links_beyond_breadcrumbs(seeded_env):
    """Инвариант: серверный HTML публичной страницы — не тупик для бота.

    Порог: ≥ 5 уникальных внутренних ссылок вне <nav>-крошек.
    Обоснование: крошки дают 1–4 ссылки вверх по иерархии; меньше пяти
    «за пределами крошек» обычно значит, что страница замыкается на себя
    (кейс /russia/today/* и /russia/calendar/* до блока seo-platform-nav). Пять —
    минимум для выхода в соседние сущности или хабы платформы.
    """
    # Представители семейств SPA-SSR (+ pure year через отдельный путь не в seeded).
    paths = [
        "/seo/today",
        "/seo/today/usd-rub",
        "/seo/calendar-month/2026/07",
        "/seo/regions",
        "/seo/region/region-1",
        "/seo/region/region-1/chislennost-naseleniya",
        "/seo/region-rating/chislennost-naseleniya",
        "/seo/regions/map/chislennost-naseleniya",
    ]
    with TestClient(seeded_env["app"]) as tc:
        for path in paths:
            r = tc.get(path)
            assert r.status_code == 200, path
            beyond = _unique_internal_beyond_nav(r.text)
            assert len(beyond) >= 5, (
                f"{path}: только {len(beyond)} ссылок вне крошек "
                f"(нужно ≥ 5): {sorted(beyond)[:12]}"
            )
            # Кросс-семейный выход в хабы (блок seo-platform-nav или богатый контент).
            assert 'href="/russia/region"' in r.text or 'href="/russia/today"' in r.text, path
