"""SEO-страницы роста трафика: sitemap-индекс, «сегодня», рейтинги регионов,
регион-vs-регион, месячные посадочные календаря + IndexNow-батчирование.

Рендеры с БД тестируются через герметичную SQLite-среду (fixture auth_env —
общая схема); маршруты — через monkeypatch рендеров (паттерн test_seo_og).
"""

import asyncio
from datetime import date, datetime, timedelta

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


def test_sitemap_locs_follow_request_host(seeded_env):
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
