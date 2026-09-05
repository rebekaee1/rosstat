"""Клик-id не должны пропадать на 301 и при срезанном ASGI query."""

from __future__ import annotations

from pathlib import Path

from starlette.requests import Request

from app.services.attribution_query import (
    click_ids_from_url,
    incoming_query,
    merge_attribution_query,
)


def _req(*, query="", original=None):
    headers = []
    if original:
        headers.append((b"x-original-uri", original.encode()))
    return Request({
        "type": "http",
        "method": "GET",
        "path": "/seo/indicator-year/imoex/2008",
        "query_string": query.encode(),
        "headers": headers,
    })


def test_incoming_query_prefers_original_uri():
    req = _req(original="/indicator/imoex/2008?ysclid=abc")
    assert incoming_query(req) == "ysclid=abc"


def test_merge_keeps_mode_and_adds_ysclid():
    req = _req(query="ysclid=abc")
    out = merge_attribution_query("/russia/indicator/cpi?mode=weekly", req)
    assert "mode=weekly" in out
    assert "ysclid=abc" in out


def test_merge_from_original_uri_when_asgi_query_empty():
    req = _req(original="/indicator/imoex/2008?ysclid=lor7sw5p9o")
    out = merge_attribution_query("/russia/indicator/imoex/2008", req)
    assert out == "/russia/indicator/imoex/2008?ysclid=lor7sw5p9o"


def test_click_ids_from_own_referrer():
    found = click_ids_from_url(
        "https://ru.forecasteconomy.com/indicator/imoex/2008?ysclid=x"
    )
    assert found["ysclid"] == "x"


def test_nginx_301s_keep_query():
    text = (Path(__file__).resolve().parents[2] / "frontend" / "nginx.conf").read_text()
    for i, line in enumerate(text.splitlines(), 1):
        if "return 301" in line and "$is_args$args" not in line:
            raise AssertionError(f"nginx.conf:{i} 301 режет query: {line.strip()}")
