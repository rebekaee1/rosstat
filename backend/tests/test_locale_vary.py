"""Ответы API зависят от X-FE-Locale: в Vary он должен быть (иначе браузерный кэш смешивает RU и EN)."""
from starlette.responses import Response

from app.main import _merge_vary


def test_merge_vary_appends_without_losing_existing_values():
    r = Response(headers={"Vary": "Host, Cookie"})
    _merge_vary(r, "X-FE-Locale")
    assert r.headers["vary"] == "Host, Cookie, X-FE-Locale"


def test_merge_vary_is_idempotent_and_case_insensitive():
    r = Response(headers={"Vary": "x-fe-locale"})
    _merge_vary(r, "X-FE-Locale")
    assert r.headers["vary"] == "x-fe-locale"


def test_merge_vary_sets_header_when_missing_and_keeps_star():
    r = Response()
    _merge_vary(r, "X-FE-Locale")
    assert r.headers["vary"] == "X-FE-Locale"
    star = Response(headers={"Vary": "*"})
    _merge_vary(star, "X-FE-Locale")
    assert star.headers["vary"] == "*"
