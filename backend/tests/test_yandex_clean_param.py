"""Yandex Clean-param stays aligned with the shipped robots.txt files."""

from pathlib import Path

from app.services.locale import reset_locale, set_locale
from app.services.seo_crawler import TRACKING_PARAMS
from app.services.yandex_clean_param import clean_param_lines, clean_param_names

ROOT = Path(__file__).resolve().parents[2]
ROBOTS = (
    ROOT / "backend/app/data/seo_static/robots.txt",
    ROOT / "backend/app/data/seo_static/robots.en.txt",
    ROOT / "frontend/public/robots.txt",
)


def test_clean_param_rules_match_templates_and_crawler():
    expected = clean_param_lines()
    names = clean_param_names()
    assert {"ysclid", "yrclid", "openstat", "view", "codes"} <= names
    assert "preview_locale" not in names
    assert "year" not in names
    assert "mode" not in names
    assert names - {"view", "codes"} == TRACKING_PARAMS
    assert "Clean-param: codes /compare" in expected
    for path in ROBOTS:
        text = path.read_text(encoding="utf-8")
        actual = [line for line in text.splitlines() if line.startswith("Clean-param:")]
        assert actual == expected, path
        assert not any(line.startswith("Host:") for line in text.splitlines()), path
        assert "Sitemap: __PUBLIC_ORIGIN__/sitemap.xml" in text, path


def test_content_changing_mode_cannot_return_to_global_clean_param(monkeypatch):
    import pytest
    import app.services.yandex_clean_param as rules

    monkeypatch.setattr(rules, "CLEAN_PARAM_RULES", (*rules.CLEAN_PARAM_RULES, "mode"))
    with pytest.raises(ValueError, match="content-changing Clean-param names.*mode"):
        rules.clean_param_names()


def test_website_language_matches_html_language():
    from app.services.seo_renderer import _site_json_ld

    for locale in ("ru", "en"):
        token = set_locale(locale)
        try:
            website = next(
                node for node in _site_json_ld()["@graph"]
                if node["@type"] == "WebSite"
            )
            assert website["inLanguage"] == locale
        finally:
            reset_locale(token)
