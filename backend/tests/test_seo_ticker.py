"""Бегущая строка курсов на чистых SSR-страницах: контейнер, скрипт и набор курсов по языку."""
from __future__ import annotations

from pathlib import Path

from app.services.locale import reset_locale, set_locale
from app.services.seo_renderer import _ssr_ticker


def test_ticker_container_ru_uses_russian_lane_and_reserves_height():
    token = set_locale("ru")
    try:
        html = _ssr_ticker()
    finally:
        reset_locale(token)
    assert 'id="seo-ticker"' in html
    assert 'data-lane="russia"' in html
    assert " hidden" not in html, "высота зарезервирована сразу, иначе страница сдвигается"
    assert "<noscript>" in html, "без JavaScript пустая строка скрывается"
    assert '<script src="/seo-ticker.js" defer></script>' in html


def test_ticker_container_en_uses_world_lane_and_english_label():
    token = set_locale("en")
    try:
        html = _ssr_ticker()
    finally:
        reset_locale(token)
    assert 'data-lane="world"' in html
    assert "Live exchange rates" in html


def test_ticker_script_matches_app_codes_and_never_breaks_the_page():
    src = (Path(__file__).resolve().parents[2] / "frontend/public/seo-ticker.js").read_text(encoding="utf-8")
    # Тот же набор курсов, что в приложении (backend/app/api/ticker.py).
    for code in ("usd-rub-live", "eur-rub-live", "cny-rub-live", "eur-usd", "gbp-usd", "usd-cny", "btc-usd", "brent", "gold-rub-live"):
        assert code in src
    assert "/api/v1/ticker/live" in src
    assert ".catch(" in src and "root.hidden = true" in src, "сбой запроса прячет строку и не ломает страницу"
    assert "innerHTML" in src and "esc(" in src, "значения подставляются только через экранирование"
