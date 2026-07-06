"""Волна 4.5 (А-2/А-3): контракт серверных 301 для легаси- и unlisted-URL.

Инвариант: ранее известный роботу URL никогда не отвечает 404, если существует
канонический наследник — только 301. Тихая просадка SEO (ЭСКАЛАЦИЯ-зона
AGENTS.md) от удаления редиректа ловится этими тестами.
"""

from fastapi.testclient import TestClient

from app.data.legacy_redirects import (
    LEGACY_INDICATOR_REDIRECTS,
    resolve_legacy_indicator,
    resolve_unlisted_indicator,
)


class TestResolvers:
    def test_legacy_codes_resolve(self):
        assert resolve_legacy_indicator("inflation") == "/indicator/cpi"
        assert resolve_legacy_indicator("gasoline-ai92") == "/indicator/fuel-ai92"
        assert resolve_legacy_indicator("refinancing-rate") == "/indicator/key-rate"
        assert resolve_legacy_indicator("cpi") is None

    def test_legacy_targets_are_current_codes(self):
        """Цель 301 обязана существовать в seed — иначе редирект в новый 404."""
        import seed_data

        codes = {row["code"] for row in seed_data.INDICATORS}
        for target in LEGACY_INDICATOR_REDIRECTS.values():
            code = target.removeprefix("/indicator/").split("?")[0]
            assert code in codes, f"301-цель {target} не существует в seed"

    def test_unlisted_generic_siblings_resolve(self):
        assert resolve_unlisted_indicator("current-account-yoy") == \
            "/indicator/current-account?mode=yoy"
        assert resolve_unlisted_indicator("exports-yoy") == "/indicator/exports?mode=yoy"

    def test_bespoke_legacy_rows_resolve(self):
        """Ряды из старых sitemap, не покрытые generic-движком (dead-code-report)."""
        for code in ("unemployment-quarterly", "unemployment-annual",
                     "trade-balance-yoy-abs", "current-account-yoy-abs"):
            target = resolve_unlisted_indicator(code)
            assert target and target.startswith("/indicator/"), code

    def test_listed_and_variant_codes_do_not_redirect(self):
        """Живые карточки (base-коды семей, variant-члены) не редиректятся."""
        for code in ("cpi", "gdp-nominal", "unemployment", "fuel-ai92", "fuel-ai95"):
            assert resolve_legacy_indicator(code) is None, code
            assert resolve_unlisted_indicator(code) is None, code


class TestSsrRedirects:
    """Редиректы срабатывают до обращения к БД — TestClient без seed достаточно."""

    def _get(self, path: str):
        from app.main import app

        client = TestClient(app)
        return client.get(path, follow_redirects=False)

    def test_legacy_code_ssr_301(self):
        r = self._get("/seo/indicator/inflation")
        assert r.status_code == 301
        assert r.headers["location"].endswith("/indicator/cpi")

    def test_unlisted_sibling_ssr_301_not_404(self):
        r = self._get("/seo/indicator/current-account-yoy")
        assert r.status_code == 301
        assert "/indicator/current-account?mode=yoy" in r.headers["location"]

    def test_year_landing_of_legacy_code_301(self):
        r = self._get("/seo/indicator-year/gasoline-ai95/2023")
        assert r.status_code == 301
        assert r.headers["location"].endswith("/indicator/fuel-ai95/2023")
