"""Инвариант path-cut: старый URL → ровно один 301 → финальный канон.

Покрывает слои:
1. `legacy_redirects` (semantic) — цели уже финальные (`/russia/…`, `/{slug}/indicator/…`);
2. SSR Location — относительный путь без хоста (nginx `absolute_redirect off`
   + backend `_permanent_redirect`); абсолютный канон только в HTML.
"""

from __future__ import annotations

from urllib.parse import urlparse

from fastapi.testclient import TestClient

from app.data.legacy_redirects import (
    LEGACY_INDICATOR_REDIRECTS,
    resolve_legacy_indicator,
    resolve_unlisted_indicator,
)
from app.services import site_paths as paths


def _assert_relative_location(location: str) -> str:
    """Location обязан быть относительным путём (`/…`), без схемы и хоста."""
    assert location, "пустой Location"
    assert location.startswith("/"), f"Location не относительный: {location!r}"
    assert "://" not in location, f"Location с хостом/схемой: {location!r}"
    parsed = urlparse(location)
    assert not parsed.scheme and not parsed.netloc, location
    return location


class TestFinalLegacyTargets:
    def test_all_legacy_indicator_targets_are_final(self):
        for code, target in LEGACY_INDICATOR_REDIRECTS.items():
            assert not target.startswith("/indicator/"), (code, target)
            assert not target.startswith("/category/"), (code, target)
            assert target.startswith("/russia/"), (code, target)

    def test_unlisted_and_bespoke_targets_are_final(self):
        samples = (
            "current-account-yoy",
            "exports-yoy",
            "unemployment-quarterly",
            "copper-avg-week",
            "steel-avg-year",
        )
        for code in samples:
            target = resolve_unlisted_indicator(code)
            assert target, code
            assert target.startswith("/russia/"), (code, target)
            assert "/indicator/" in target or "/category/" in target, (code, target)

    def test_legacy_resolves_match_site_paths(self):
        assert resolve_legacy_indicator("inflation") == paths.russia_indicator("cpi")
        assert resolve_legacy_indicator("steel") == paths.russia_category("commodities")


class TestSsrSingleHop:
    def _get(self, path: str, *, legacy: bool = False):
        from app.main import app

        headers = {"X-Path-Cut-Legacy": "1"} if legacy else None
        return TestClient(app).get(path, follow_redirects=False, headers=headers)

    def test_legacy_code_one_hop_to_russia_indicator(self):
        r = self._get("/seo/indicator/inflation")
        assert r.status_code == 301
        loc = _assert_relative_location(r.headers["location"])
        assert loc == paths.russia_indicator("cpi")
        assert resolve_legacy_indicator("cpi") is None
        assert resolve_unlisted_indicator("cpi") is None

    def test_unlisted_sibling_one_hop(self):
        r = self._get("/seo/indicator/exports-yoy")
        assert r.status_code == 301
        loc = _assert_relative_location(r.headers["location"])
        assert loc.startswith(paths.russia_indicator("exports"))
        assert "mode=" in loc

    def test_path_cut_legacy_header_canonicalizes_live_code(self):
        """Старый /indicator/cpi (через nginx + X-Path-Cut-Legacy) → /russia/…."""
        r = self._get("/seo/indicator/cpi", legacy=True)
        assert r.status_code == 301
        loc = _assert_relative_location(r.headers["location"])
        assert loc == paths.russia_indicator("cpi")

    def test_path_cut_legacy_world_country_relative(self):
        r = self._get("/seo/world/germany", legacy=True)
        assert r.status_code == 301
        loc = _assert_relative_location(r.headers["location"])
        assert loc == paths.country("germany")

    def test_world_rating_default_relative(self):
        r = self._get("/seo/world/rating")
        assert r.status_code == 301
        loc = _assert_relative_location(r.headers["location"])
        assert loc.startswith("/world/rating/")
