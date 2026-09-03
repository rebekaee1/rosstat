"""Фильтр неканонических URL в sitemap / IndexNow / Webmaster recrawl.

Регрессия: unlisted view-mode siblings (301 → ?mode=) и /compare?* жгли
квоту переобхода (~150/день) → NOT_CANONICAL и просадка Searchable.
"""

from app.data.legacy_redirects import resolve_unlisted_indicator
from app.services.site_urls import (
    filter_recrawl_paths,
    is_recrawl_eligible,
    is_redirect_only_indicator,
)


class TestRedirectOnlyIndicator:
    def test_generic_sibling_is_redirect_only(self):
        assert is_redirect_only_indicator("current-account-yoy") is True
        assert is_redirect_only_indicator("exports-yoy") is True

    def test_bespoke_unlisted_is_redirect_only(self):
        assert is_redirect_only_indicator("unemployment-quarterly") is True
        assert is_redirect_only_indicator("trade-balance-yoy-abs") is True

    def test_legacy_renamed_is_redirect_only(self):
        assert is_redirect_only_indicator("inflation") is True
        assert is_redirect_only_indicator("gasoline-ai92") is True

    def test_canonical_cards_are_not_redirect_only(self):
        for code in ("cpi", "gdp-nominal", "unemployment", "fuel-ai92", "current-account"):
            assert is_redirect_only_indicator(code) is False, code


class TestRecrawlEligible:
    def test_canonical_paths_eligible(self):
        for path in (
            "/",
            "/compare",
            "/indicator/cpi",
            "/indicator/cpi/2024",
            "/region/moskva",
            "/region/moskva/uroven-bezrabotitsy",
            "/region-rating/uroven-bezrabotitsy",
            "/regions/map/uroven-bezrabotitsy",
            "/today/usd-rub",
            "/calendar/2026/07",
            "/region-vs/moskva-vs-sankt-peterburg",
        ):
            assert is_recrawl_eligible(path) is True, path

    def test_query_variants_not_eligible(self):
        for path in (
            "/compare?codes=cpi,gdp-nominal",
            "/compare?a=1",
            "/regions?view=map&indicator=x",
            "/regions/map/x?year=2015",
            "/indicator/cpi?mode=yoy",
        ):
            assert is_recrawl_eligible(path) is False, path

    def test_unlisted_sibling_bare_path_not_eligible(self):
        assert resolve_unlisted_indicator("current-account-yoy")
        assert is_recrawl_eligible("/indicator/current-account-yoy") is False
        assert is_recrawl_eligible("/indicator/exports-yoy") is False
        assert is_recrawl_eligible("/indicator/unemployment-quarterly") is False

    def test_filter_splits_eligible_and_skipped(self):
        paths = [
            "/indicator/cpi",
            "/indicator/current-account-yoy",
            "/compare?codes=cpi,key-rate",
            "/region/moskva",
            "/indicator/inflation",
        ]
        eligible, skipped = filter_recrawl_paths(paths)
        assert eligible == ["/indicator/cpi", "/region/moskva"]
        assert skipped == [
            "/indicator/current-account-yoy",
            "/compare?codes=cpi,key-rate",
            "/indicator/inflation",
        ]

    def test_honeypot_is_not_recrawl_eligible(self):
        assert is_recrawl_eligible("/__honeypot__/trap") is False
        assert is_recrawl_eligible("/russia/util/links-exchange") is False
