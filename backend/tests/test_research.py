"""Раздел «Исследования»: каталог, счётчик скачиваний (раз в сутки с адреса), SSR и служебные списки путей."""
import pytest


def test_catalog_valid():
    from app.api.research import load_catalog
    cat = load_catalog()
    items = cat["items"]
    assert len(items) >= 21
    slugs = [i["slug"] for i in items]
    assert len(set(slugs)) == len(slugs)
    for i in items:
        assert i["file"].startswith("/research/files/") and i["file"].endswith(".pdf")
        assert i["cover"].startswith("/research/covers/")
        assert i["title"] and i["annotation"] and i["figures"] and i["conclusions"]
        assert i["authors"] == "Команда ForecastEconomy"


def test_files_exist():
    from pathlib import Path
    from app.api.research import load_catalog
    public = Path(__file__).resolve().parents[2] / "frontend" / "public"
    for i in load_catalog()["items"]:
        assert (public / i["file"].lstrip("/")).is_file(), i["file"]
        assert (public / i["cover"].lstrip("/")).is_file(), i["cover"]


def test_download_counts_once_per_day(auth_client):
    client = auth_client
    r = client.get("/api/v1/research/ergodicity/download", follow_redirects=False, headers={"referer": "https://ru.forecasteconomy.com/research"})
    assert r.status_code == 302
    assert r.headers["location"].startswith("/research/files/")
    client.get("/api/v1/research/ergodicity/download", follow_redirects=False, headers={"referer": "https://ru.forecasteconomy.com/research"})
    items = {i["slug"]: i for i in client.get("/api/v1/research").json()["items"]}
    assert items["ergodicity"]["downloads"] == 1
    assert items["fat-tails"]["downloads"] == 0


def test_download_unknown_404(auth_client):
    client = auth_client
    assert client.get("/api/v1/research/nope/download", follow_redirects=False).status_code == 404


def test_bots_not_counted(auth_client):
    client = auth_client
    client.get("/api/v1/research/fat-tails/download", follow_redirects=False, headers={"user-agent": "YandexBot/3.0"})
    items = {i["slug"]: i for i in client.get("/api/v1/research").json()["items"]}
    assert items["fat-tails"]["downloads"] == 0


def test_ssr_lists_reports():
    import asyncio
    from app.services.seo_research import render_research_html
    status, html = asyncio.run(render_research_html())
    assert status == 200
    assert "Исследования" in html
    assert "/api/v1/research/ergodicity/download" in html
    assert "Эргодичность и кредитное плечо" in html


def test_reserved_and_static():
    from app.services.site_paths import RESERVED_FIRST_SEGMENTS
    from app.services.seo_content import STATIC_PAGES
    assert "research" in RESERVED_FIRST_SEGMENTS
    assert any(p == "/research" for p, _, _ in STATIC_PAGES)


def test_download_source_rules():
    """09.11.2026: «с сайта» — только по Referer нашего хоста; метки bot/tg — ссылки Telegram; остальное direct."""
    from starlette.requests import Request

    from app.api.research import download_source

    def req(qs="", referer=None):
        headers = [(b"referer", referer.encode())] if referer else []
        return Request({"type": "http", "method": "GET", "path": "/", "query_string": qs.encode(), "headers": headers})

    assert download_source(req(referer="https://ru.forecasteconomy.com/research")) == "site"
    assert download_source(req(referer="https://forecasteconomy.com/research")) == "site"
    assert download_source(req("src=bot")) == "bot"
    assert download_source(req("src=tg")) == "tg"
    # метки site нет: ссылка со страницы с меткой досталась бы и обходчику
    assert download_source(req("src=site")) == "direct"
    assert download_source(req()) == "direct"
    assert download_source(req(referer="https://evil.example/forecasteconomy.com")) == "direct"


def test_farm_without_referer_not_in_public_count(auth_client):
    client = auth_client
    client.get("/api/v1/research/fat-tails/download", follow_redirects=False,
               headers={"user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/154.0 Safari/537.36"})
    client.get("/api/v1/research/fat-tails/download?src=tg", follow_redirects=False,
               headers={"user-agent": "Mozilla/5.0 (iPhone) Safari/604.1", "x-forwarded-for": "10.0.0.7"})
    data = client.get("/api/v1/research").json()
    items = {i["slug"]: i for i in data["items"]}
    assert items["fat-tails"]["downloads"] == 1  # только из канала; заход без перехода не считается


def test_digest_line_splits_sources(monkeypatch):
    import asyncio
    from datetime import date

    import app.api.research as research
    from app.tasks import analytics_scheduler

    async def fake(db, day):
        return {"site": 5, "tg": 2, "direct": 40}

    monkeypatch.setattr(research, "downloads_by_source", fake)
    line = asyncio.run(analytics_scheduler._research_download_lines(date(2026, 11, 9)))[0]
    assert "Скачали исследования вчера: 7" in line and "с сайта 5" in line and "из канала 2" in line
    assert "40 без перехода" in line
