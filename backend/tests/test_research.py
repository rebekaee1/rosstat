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
    r = client.get("/api/v1/research/ergodicity/download", follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"].startswith("/research/files/")
    client.get("/api/v1/research/ergodicity/download", follow_redirects=False)
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
