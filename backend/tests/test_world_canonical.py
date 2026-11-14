"""Основная версия одинаковых рядов стран мира: canonical, hreflang, sitemap (14.11.2026)."""

from __future__ import annotations

import re
from datetime import date
from types import SimpleNamespace

import pytest

from app.config import settings
from app.services import world_canonical as wc
from app.services.site_urls import SiteUrl
from tests.test_seo_world_year import CODE_MONTHLY, CODE_SIBLING_M, world_year_client  # noqa: F401

APEX, RU = "forecasteconomy.com", "ru.forecasteconomy.com"


def _row(rid, code, *, slug="denmark", country_id=1, slice_json=None, end=date(2026, 4, 1), start=date(1998, 4, 1),
         points=111, freq="quarterly", provider="eurostat", name="Уровень безработицы, %"):
    return SimpleNamespace(id=rid, country_id=country_id, slug=slug, code=code, name_ru=name, name_en="Unemployment",
                           slice_json=slice_json or {}, provider=provider, frequency=freq, points_count=points,
                           history_start=start, history_end=end)


def test_slice_signature_treats_missing_axis_as_total():
    a = {"age": "Y15-74", "sex": "T", "freq": "Q", "unit": "PC", "isced11": "TOTAL"}
    b = {"age": "Y15-74", "sex": "T", "freq": "Q", "unit": "PC", "citizen": "TOTAL"}
    assert wc.slice_signature(a) == wc.slice_signature(b) == frozenset({("unit", "PC")})
    assert wc.slice_signature({"unit": "PC", "sex": "F"}) != wc.slice_signature(a)


def test_only_fully_identical_groups_get_a_primary_and_rule_is_deterministic():
    lfs = [
        _row(1, "dk-lfsq_urgaed", slice_json={"unit": "PC", "isced11": "TOTAL"}),
        _row(2, "dk-lfsq_urgacob", slice_json={"unit": "PC", "c_birth": "TOTAL"}),
        _row(3, "dk-lfsq_urgan", slice_json={"unit": "PC", "citizen": "TOTAL"}, end=date(2026, 7, 1)),
    ]
    partial = [_row(4, "dk-a", name="Б", slice_json={"unit": "PC"}), _row(5, "dk-b", name="Б", slice_json={"unit": "PC"})]
    other = [_row(6, "dk-x", name="В", slice_json={"unit": "PC"}), _row(7, "dk-y", name="В", slice_json={"unit": "PC_ACT"})]
    groups = wc.candidate_groups(lfs + partial + other)
    assert sorted(len(g) for g in groups) == [2, 3]  # разные единицы — не одна группа
    digests = {1: "d", 2: "d", 3: "d", 4: "p", 5: "q"}
    mapping = wc.resolve_map(groups, digests, kept=set())
    # Самая свежая последняя точка — основная; остальные на неё.
    assert mapping == {"denmark": {"dk-lfsq_urgaed": "dk-lfsq_urgan", "dk-lfsq_urgacob": "dk-lfsq_urgan"}}
    # При равной свежести — длиннее история, затем больше точек, затем код.
    tie = [_row(8, "dk-b2", points=100), _row(9, "dk-a2", points=100)]
    assert wc.resolve_map([tie], {8: "z", 9: "z"}, set()) == {"denmark": {"dk-b2": "dk-a2"}}


def test_series_with_search_impressions_are_kept():
    lfs = [_row(1, "dk-a", slice_json={"unit": "PC"}), _row(2, "dk-b", slice_json={"unit": "PC"}, end=date(2025, 1, 1))]
    assert wc.resolve_map([lfs], {1: "d", 2: "d"}, kept={("denmark", "dk-b")}) == {}


def test_sitemap_drops_cards_and_years_of_non_primary_only():
    urls = [SiteUrl(p, "2026-01-01", "monthly", "0.4") for p in (
        "/denmark/indicator/dk-b", "/denmark/indicator/dk-b/2020", "/denmark/indicator/dk-a",
        "/denmark/indicator/dk-a/2020", "/denmark-vs-norway/population",
    )]
    kept = [u.path for u in wc.drop_from_sitemap(urls, {("denmark", "dk-b")})]
    assert kept == ["/denmark/indicator/dk-a", "/denmark/indicator/dk-a/2020", "/denmark-vs-norway/population"]


@pytest.fixture
def duplicate(monkeypatch):
    """Карточка CODE_MONTHLY объявлена неосновной версией CODE_SIBLING_M (проверка механики, не смысла)."""
    monkeypatch.setattr(settings, "apex_locale_en", True)
    monkeypatch.setattr(settings, "world_duplicate_canonical", True)
    monkeypatch.setattr(wc, "published_map", lambda: {"germany": {CODE_MONTHLY: CODE_SIBLING_M}})


def _links(html: str) -> tuple[list[str], dict[str, str]]:
    canonical = re.findall(r'<link rel="canonical" href="([^"]+)"', html)
    alts = dict(re.findall(r'<link rel="alternate" hreflang="([^"]+)" href="([^"]+)"', html))
    return canonical, alts


@pytest.mark.parametrize("host", [APEX, RU])
def test_non_primary_card_points_canonical_and_hreflang_to_primary(world_year_client, duplicate, host):  # noqa: F811
    locale = "en" if host == APEX else "ru"
    html = world_year_client.get(f"/seo/world/germany/{CODE_MONTHLY}", headers={"Host": host, "X-FE-Locale": locale}).text
    canonical, alts = _links(html)
    assert canonical == [f"https://{host}/germany/indicator/{CODE_SIBLING_M}"]  # та же языковая версия
    assert alts["ru"] == f"https://{RU}/germany/indicator/{CODE_SIBLING_M}"
    assert alts["en"] == alts["x-default"] == f"https://{APEX}/germany/indicator/{CODE_SIBLING_M}"
    primary = world_year_client.get(f"/seo/world/germany/{CODE_SIBLING_M}", headers={"Host": host, "X-FE-Locale": locale})
    assert primary.status_code == 200  # canonical ведёт на живую страницу
    assert _links(primary.text)[0] == [f"https://{host}/germany/indicator/{CODE_SIBLING_M}"]  # основная — сама себе


def test_non_primary_year_points_to_primary_year_only_if_it_exists(world_year_client, duplicate):  # noqa: F811
    headers = {"Host": APEX, "X-FE-Locale": "en"}
    html = world_year_client.get(f"/seo/world-indicator-year/germany/{CODE_MONTHLY}/2024", headers=headers).text
    assert _links(html)[0] == [f"https://{APEX}/germany/indicator/{CODE_SIBLING_M}/2024"]
    assert world_year_client.get(
        f"/seo/world-indicator-year/germany/{CODE_SIBLING_M}/2024", headers=headers).status_code == 200
    # У основной нет 2025 года — canonical свой.
    html = world_year_client.get(f"/seo/world-indicator-year/germany/{CODE_MONTHLY}/2025", headers=headers).text
    assert _links(html)[0] == [f"https://{APEX}/germany/indicator/{CODE_MONTHLY}/2025"]


def test_nightly_build_writes_map_and_leaves_non_primary_out_of_sitemap(tmp_path, monkeypatch):
    import asyncio
    import json
    from contextlib import asynccontextmanager

    import app.services.site_urls as urls
    from app.services import sitemap_static as sm

    monkeypatch.setattr(settings, "sitemap_dir", str(tmp_path))
    monkeypatch.setattr(settings, "apex_locale_en", True)
    monkeypatch.setattr(settings, "sitemap_priority_max_urls", 0)
    monkeypatch.setattr(settings, "public_base_url", "https://forecasteconomy.com")

    @asynccontextmanager
    async def session():
        yield None

    async def sections(db):
        yield "world-indicators-1", [
            SiteUrl("/denmark/indicator/dk-a", "2026-04-01", "monthly", "0.4"),
            SiteUrl("/denmark/indicator/dk-b", "2026-04-01", "monthly", "0.4"),
        ]
        yield "world-years-1", [
            SiteUrl("/denmark/indicator/dk-a/2020", "2020-12-01", "yearly", "0.4"),
            SiteUrl("/denmark/indicator/dk-b/2020", "2020-12-01", "yearly", "0.4"),
        ]

    async def no_chunks(db):
        return {}

    async def duplicate_map():
        return {"denmark": {"dk-b": "dk-a"}}

    monkeypatch.setattr(sm, "analytics_session", session)
    monkeypatch.setattr(sm, "_load_duplicate_map", duplicate_map)
    monkeypatch.setattr(urls, "iter_url_sections", sections)
    monkeypatch.setattr(urls, "chunk_counts", no_chunks)
    stats = asyncio.run(sm.build_static_sitemaps())
    assert stats["world_canonical_pairs"] == 1
    current = tmp_path / "current"
    shard = (current / "forecasteconomy.com" / "sitemap-world-years-1.xml").read_text()
    assert "/dk-a/2020" in shard and "/dk-b/" not in shard
    card = (current / "ru.forecasteconomy.com" / "sitemap-world-indicators-1.xml").read_text()
    assert "/dk-a<" in card and "/dk-b<" not in card
    published = json.loads((current / wc.CANONICAL_FILE).read_text())
    assert published == {"pairs": 1, "map": {"denmark": {"dk-b": "dk-a"}}}
    monkeypatch.setattr(wc, "_cache", {"checked": None, "key": None, "map": None})
    monkeypatch.setattr(settings, "world_duplicate_canonical", True)
    assert wc.primary_code("denmark", "dk-b") == "dk-a" and wc.primary_code("denmark", "dk-a") is None


def test_flag_off_keeps_self_canonical(world_year_client, duplicate, monkeypatch):  # noqa: F811
    monkeypatch.setattr(settings, "world_duplicate_canonical", False)
    monkeypatch.setattr(wc, "published_map", lambda: {"germany": {CODE_MONTHLY: CODE_SIBLING_M}})
    html = world_year_client.get(f"/seo/world/germany/{CODE_MONTHLY}", headers={"Host": APEX, "X-FE-Locale": "en"}).text
    assert _links(html)[0] == [f"https://{APEX}/germany/indicator/{CODE_MONTHLY}"]
