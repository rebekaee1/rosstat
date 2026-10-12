"""Главная русского хоста: стабильный блок «Популярные показатели» (круг 13, SEO)."""
import asyncio
from types import SimpleNamespace

from app.services import seo_renderer
from app.services.locale import reset_locale, set_locale


def _install(monkeypatch):
    from app.core import cache as cache_mod

    asked: list[tuple] = []

    async def fake_inds(db, codes):
        asked.append(tuple(codes))
        names = {"cpi": "Индекс потребительских цен", "usd-rub": "Курс доллара США", "eur-rub": "Курс евро",
                 "ruonia": "RUONIA", "fuel-diesel": "Дизельное топливо"}
        return [SimpleNamespace(code=c, name=names[c], name_en=names[c]) for c in codes if c in names]

    async def no_cache(_key):
        return None

    async def none_pair(*a, **k):
        return None, False

    async def key(ns, rest):
        return f"fe:{ns}:v0:{rest}"

    async def always(*a):
        return True

    async def assets():
        return seo_renderer._fallback_assets()

    async def countries(db):
        return (("/germany", "Германия"),)

    async def us(db):
        return (("/united-states/indicator/us-cpi-all", "CPI"),)

    monkeypatch.setattr(seo_renderer, "_indicators_by_codes", fake_inds)
    monkeypatch.setattr(seo_renderer, "get_app_assets", assets)
    monkeypatch.setattr(seo_renderer, "_home_country_links", countries)
    monkeypatch.setattr(seo_renderer, "_home_flagship_links_en", us)
    monkeypatch.setattr(cache_mod, "cache_get", no_cache)
    monkeypatch.setattr(cache_mod, "get_versioned_durable_world_countries", none_pair)
    monkeypatch.setattr(cache_mod, "versioned_key", key)
    monkeypatch.setattr(cache_mod, "fresh_world_catalog_key", lambda rest: key("world-catalog", rest))
    monkeypatch.setattr(cache_mod, "is_current_world_countries_key", always)
    return asked


def test_ru_home_has_popular_block_without_duplicating_flagships(monkeypatch):
    asked = _install(monkeypatch)
    token = set_locale("ru")
    try:
        html = asyncio.run(seo_renderer.render_home_html(None))
    finally:
        reset_locale(token)
    assert "<h2>Популярные показатели</h2>" in html
    block = html.split("<h2>Популярные показатели</h2>", 1)[1].split("</section>", 1)[0]
    assert 'href="/currencies/indicator/usd-rub"' in block
    assert 'href="/russia/indicator/ruonia"' in block
    # показатель, уже стоящий среди ключевых, во втором списке не повторяется
    assert 'href="/russia/indicator/cpi"' not in block
    assert asked[1] and "cpi" not in asked[1]


def test_en_home_has_no_popular_block(monkeypatch):
    asked = _install(monkeypatch)
    token = set_locale("en")
    try:
        html = asyncio.run(seo_renderer.render_home_html(None))
    finally:
        reset_locale(token)
    assert "Популярные показатели" not in html
    assert len(asked) == 1
