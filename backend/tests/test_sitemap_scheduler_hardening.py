"""Инцидент 2026-09-25/26: ошибки sitemap в Вебмастере и падения планировщика.

1. 90 836 «ошибок sitemap» на ru. = <lastmod> раньше 1970-01-01 (годовые
   страницы 1897…1969): Вебмастер считает каждую такую дату ошибкой файла.
2. webmaster_recrawl(_ru) падали по statement_timeout на count(*) мировых
   лет (~12 млн групп по 16 млн world_data_points): реестр переобхода
   теперь читается из опубликованной генерации, счётчики чанков — из stats.
3. sitemap_build, прерванный рестартом при деплое, не шлёт ложный алерт.
"""
import asyncio
from contextlib import asynccontextmanager
from datetime import date

import pytest

from app.services import sitemap_static as sm
from app.services.site_urls import SiteUrl


# --- 1. lastmod до Unix-эпохи ------------------------------------------------

def test_pre_epoch_lastmod_is_omitted():
    import app.services.site_urls as urls

    today = date(2026, 9, 26)
    assert urls.normalize_sitemap_lastmod("1969-12-01", today=today) is None
    assert urls.normalize_sitemap_lastmod("1897-01-01", today=today) is None
    assert urls.normalize_sitemap_lastmod("1930-01-01T00:00:00+03:00", today=today) is None
    assert urls.normalize_sitemap_lastmod("1970-01-01", today=today) == "1970-01-01"
    assert urls.normalize_sitemap_lastmod("1998-01-01", today=today) == "1998-01-01"


def test_urlset_and_section_lastmod_skip_pre_epoch_dates():
    from app.api.sitemap import _render_urlset
    import app.services.site_urls as urls

    rows = [
        SiteUrl("/united-states/region/idaho/bea-x/1948", "1948-01-01", "yearly", "0.4"),
        SiteUrl("/united-states/region/idaho/bea-x/1998", "1998-01-01", "yearly", "0.4"),
    ]
    xml = _render_urlset(rows, origin="https://ru.forecasteconomy.com")
    assert "1948-01-01" not in xml
    assert xml.count("<lastmod>") == 1
    assert "<lastmod>1998-01-01</lastmod>" in xml
    only_old = [SiteUrl("/x/1950", "1950-01-01", "yearly", "0.4")]
    assert urls.section_lastmod(only_old, today=date(2026, 9, 26)) is None


def test_fingerprint_follows_rendered_lastmod():
    """Шард с датой до 1970 обязан пересобраться: отпечаток = то, что в XML."""
    import app.services.site_urls as urls

    old = [SiteUrl("/x/1950", "1950-01-01", "yearly", "0.4")]
    omitted = [SiteUrl("/x/1950", None, "yearly", "0.4")]
    valid = [SiteUrl("/x/1950", "1990-01-01", "yearly", "0.4")]
    assert urls.section_fingerprint(old) == urls.section_fingerprint(omitted)
    assert urls.section_fingerprint(old) != urls.section_fingerprint(valid)


def test_pre_epoch_shard_is_rewritten_not_reused(tmp_path, monkeypatch):
    """Прошлая генерация с <lastmod>1950 не переиспользуется жёсткой ссылкой."""
    from app.config import settings
    import app.services.site_urls as urls

    monkeypatch.setattr(settings, "sitemap_dir", str(tmp_path))
    monkeypatch.setattr(settings, "apex_locale_en", True)
    monkeypatch.setattr(settings, "public_base_url", "https://forecasteconomy.com")

    @asynccontextmanager
    async def session():
        yield None

    async def sections(db):
        yield "world-years-1", [SiteUrl("/france/indicator/gdp/1950", "1950-12-01", "yearly", "0.4")]

    monkeypatch.setattr(sm, "analytics_session", session)
    monkeypatch.setattr(urls, "iter_url_sections", sections)
    first = asyncio.run(sm.build_static_sitemaps())
    # Симулируем генерацию, собранную старым кодом: в файле дата 1950 и
    # «старый» отпечаток по сырому lastmod.
    gen = tmp_path / "generations" / first["generation"]
    for host in ("forecasteconomy.com", "ru.forecasteconomy.com"):
        f = gen / host / "sitemap-world-years-1.xml"
        f.write_text(f.read_text().replace(
            "<changefreq>", "<lastmod>1950-12-01</lastmod>\n    <changefreq>", 1))
    stats_path = gen / sm.STATS_NAME
    import json
    stats = json.loads(stats_path.read_text())
    stats["section_digest"]["world-years-1"] = "legacy-raw-lastmod-digest"
    stats_path.write_text(json.dumps(stats))

    second = asyncio.run(sm.build_static_sitemaps())
    assert second["sections_rewritten"] == 1
    body = sm.section_file("world-years-1", "https://ru.forecasteconomy.com").read_text()
    assert "1950-12-01" not in body


# --- 2. Счётчики чанков и реестр переобхода без тяжёлых запросов --------------

@pytest.fixture
def published(tmp_path, monkeypatch):
    from app.config import settings
    import app.services.site_urls as urls

    monkeypatch.setattr(settings, "sitemap_dir", str(tmp_path))
    monkeypatch.setattr(settings, "apex_locale_en", True)
    monkeypatch.setattr(settings, "public_base_url", "https://forecasteconomy.com")

    @asynccontextmanager
    async def session():
        yield None

    async def sections(db):
        yield "core", [SiteUrl("/", "2026-09-10", "daily", "1.0"),
                       SiteUrl("/about?x=1&y=2", None, "monthly", "0.5")]
        yield "world-years-1", [SiteUrl(f"/france/indicator/gdp/{y}", f"{y}-12-01", "yearly", "0.4")
                                for y in (1960, 1990, 2000)]
        yield "world-years-2", [SiteUrl("/spain/indicator/gdp/2001", "2001-12-01", "yearly", "0.4")]
        yield "world-region-years-1", [SiteUrl("/united-states/region/idaho/x/2001", "2001-01-01", "yearly", "0.4")]
        yield "regional-years-1", [SiteUrl("/region/moskva/zz-series/2020", "2020-12-01", "yearly", "0.4")]

    monkeypatch.setattr(sm, "analytics_session", session)
    monkeypatch.setattr(urls, "iter_url_sections", sections)
    asyncio.run(sm.build_static_sitemaps())
    return tmp_path


class _NoDb:
    async def execute(self, *args, **kwargs):  # pragma: no cover - must not run
        raise AssertionError("chunk counts must come from the published generation")


def _no_cache(monkeypatch):
    async def cache_get(key):
        return None

    async def cache_set(key, value, ttl):
        return None

    monkeypatch.setattr("app.core.cache.cache_get", cache_get)
    monkeypatch.setattr("app.core.cache.cache_set", cache_set)


def test_chunk_counts_read_published_stats_without_db(published, monkeypatch):
    import app.services.site_urls as urls

    _no_cache(monkeypatch)
    counts = asyncio.run(urls.chunk_counts(_NoDb()))
    assert counts["world-years-"] == 2
    assert counts["world-region-years-"] == 1
    assert counts["regional-years-"] == 1
    # «regional-» не должен захватывать regional-years-N
    assert counts["regional-"] == 1  # max(1, 0)
    items = asyncio.run(urls.chunk_item_counts(_NoDb()))
    assert items["world-years-"] == 4
    assert items["regional-years-"] == 1
    assert items["regional-"] == 0


def test_chunk_counts_fallback_raises_statement_timeout(monkeypatch, tmp_path):
    """Без генерации — count в БД, но под своим потолком и с возвратом прежнего."""
    from app.config import settings
    import app.services.site_urls as urls

    monkeypatch.setattr(settings, "sitemap_dir", str(tmp_path))
    _no_cache(monkeypatch)
    calls = []

    class _Res:
        def __init__(self, value):
            self._v = value

        def scalar_one(self):
            return self._v

    class _Db:
        async def execute(self, stmt, params=None):
            text = str(stmt)
            if "current_setting" in text:
                calls.append(("get",))
                return _Res("30s")
            if "set_config" in text:
                calls.append(("set", params["v"]))
                return _Res(params["v"])
            calls.append(("count",))
            return _Res(25_000)

    counts = asyncio.run(urls.chunk_counts(_Db()))
    assert counts["world-years-"] == -(-25_000 // urls._CHUNKED_SOURCES["world-years-"].size)
    assert calls[0] == ("get",)
    assert calls[1] == ("set", str(urls._CHUNK_COUNT_STATEMENT_TIMEOUT_MS))
    assert calls[-1] == ("set", "30s")


def test_iter_published_paths_reads_loc_not_image_loc(published):
    paths = list(sm.iter_published_paths("https://ru.forecasteconomy.com"))
    assert paths[:2] == ["/", "/about?x=1&y=2"]
    assert "/france/indicator/gdp/1960" in paths
    assert not any(p.startswith("/og/") for p in paths)
    assert len(paths) == len(set(paths)) == 8
    assert sm.has_published_generation("https://ru.forecasteconomy.com")
    assert not sm.has_published_generation("https://attacker.example")
    assert list(sm.iter_published_paths("https://attacker.example")) == []


def test_scan_published_registry_selects_unsubmitted_in_order(published):
    from app.services.webmaster_recrawl import _scan_published_registry

    scan = _scan_published_registry(
        "https://ru.forecasteconomy.com",
        demand={"/spain/indicator/gdp/2001", "/not/in/registry"},
        already={"/", "/france/indicator/gdp/1960"},
        need=2,
    )
    assert scan["regular"] == ["/france/indicator/gdp/1990", "/france/indicator/gdp/2000"]
    assert scan["demand_found"] == {"/spain/indicator/gdp/2001"}
    assert scan["skipped"] == ["/about?x=1&y=2"]
    assert scan["eligible_total"] == 7


def test_recrawl_job_uses_published_registry_not_db_registry(published, monkeypatch):
    import app.services.site_urls as urls
    import app.services.webmaster_recrawl as wr
    from app.config import settings

    monkeypatch.setattr(settings, "yandex_webmaster_token", "t")
    monkeypatch.setattr(settings, "analytics_live_writes_enabled", True)

    async def forbidden(db, sections=None):
        raise AssertionError("DB registry must not be rebuilt when a generation exists")

    monkeypatch.setattr(urls, "collect_all_paths", forbidden)

    class _Resp:
        def __init__(self, data):
            self.data = data

    submitted = []

    class _Client:
        async def user(self):
            return _Resp({"user_id": 1})

        async def recrawl_quota(self, user_id, host_id):
            return _Resp({"quota_remainder": 3})

        async def submit_recrawl(self, user_id, host_id, url, approved=False):
            submitted.append(url)

    class _Redis:
        def __init__(self):
            self.members = {"/"}

        async def smembers(self, key):
            return set(self.members)

        async def sadd(self, key, *values):
            self.members.update(values)

        async def sismember(self, key, value):
            return value in self.members

        async def delete(self, key):
            self.members.clear()

        async def scard(self, key):
            return len(self.members)

    redis = _Redis()

    async def get_redis():
        return redis

    class _Session:
        async def commit(self):
            return None

    @asynccontextmanager
    async def session():
        yield _Session()

    async def demand(db, days, limit, host):
        return [("/region/moskva/zz-series/2020", 10)]

    monkeypatch.setattr(wr, "YandexWebmasterClient", _Client)
    monkeypatch.setattr(wr, "get_state_redis", get_redis)
    monkeypatch.setattr(wr, "async_session", session)
    monkeypatch.setattr("app.services.demand_router.priority_recrawl_paths", demand)

    result = asyncio.run(wr.recrawl_daily_job(
        origin="https://ru.forecasteconomy.com", host_id="h", submitted_key="k",
    ))
    assert submitted == [
        "https://ru.forecasteconomy.com/region/moskva/zz-series/2020",
        "https://ru.forecasteconomy.com/france/indicator/gdp/1960",
        "https://ru.forecasteconomy.com/france/indicator/gdp/1990",
    ]
    assert result["submitted"] == 3
    assert result["demand_priority"] == 1
    assert result["eligible"] == 7
    assert "/about?x=1&y=2" in redis.members  # неканон помечен без POST


# --- 3. Прерывание job рестартом не алертится ----------------------------------

def test_scheduler_listener_silent_during_shutdown(monkeypatch):
    import app.main as main

    sent = []

    async def fake_send(msg, kind=None):
        sent.append(msg)

    monkeypatch.setattr("app.services.alerting.send_telegram", fake_send)

    class _Event:
        job_id = "sitemap_build"
        exception = RuntimeError("cannot call PreparedStatement.fetch(): the underlying connection is closed")

    async def run():
        main._scheduler_event_listener(_Event())
        await asyncio.sleep(0)

    monkeypatch.setattr(main, "_shutting_down", True)
    asyncio.run(run())
    assert sent == []
    monkeypatch.setattr(main, "_shutting_down", False)
    monkeypatch.setattr(main.scheduler, "get_job", lambda job_id: None)
    asyncio.run(run())
    assert len(sent) == 1 and "sitemap_build" in sent[0]
