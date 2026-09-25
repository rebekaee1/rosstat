"""Yandex Webmaster: Clean-param, host language, no deprecated Host directive."""

from pathlib import Path

from app.services.locale import reset_locale, set_locale
from app.services.yandex_clean_param import (
    CONTENT_PARAMS,
    clean_param_lines,
    clean_param_names,
)

ROOT = Path(__file__).resolve().parents[2]
ROBOTS = (
    ROOT / "backend/app/data/seo_static/robots.txt",
    ROOT / "backend/app/data/seo_static/robots.en.txt",
    ROOT / "frontend/public/robots.txt",
)


def _clean_lines(text: str) -> list[str]:
    return [line for line in text.splitlines() if line.startswith("Clean-param:")]


def test_clean_param_rules_match_source_and_fit_yandex_limit():
    expected = clean_param_lines()
    assert expected
    names = clean_param_names()
    assert "ysclid" in names
    assert "openstat" in names
    assert "yrclid" in names
    assert names.isdisjoint(CONTENT_PARAMS)
    for path in ROBOTS:
        text = path.read_text(encoding="utf-8")
        assert _clean_lines(text) == expected, path.name
        assert "\nHost:" not in f"\n{text}"
        assert "Sitemap: __PUBLIC_ORIGIN__/sitemap.xml" in text


def test_website_inlanguage_is_iso_639_not_region():
    """Яндекс ждёт код языка ISO 639-1, как html lang и hreflang, без региона."""
    from app.services.seo_renderer import _site_json_ld

    token = set_locale("ru")
    try:
        website = next(
            node for node in _site_json_ld()["@graph"] if node["@type"] == "WebSite"
        )
        assert website["inLanguage"] == "ru"
    finally:
        reset_locale(token)

    token = set_locale("en")
    try:
        website = next(
            node for node in _site_json_ld()["@graph"] if node["@type"] == "WebSite"
        )
        assert website["inLanguage"] == "en"
    finally:
        reset_locale(token)
