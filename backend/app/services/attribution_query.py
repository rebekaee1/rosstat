"""Клик-id и UTM, которые нельзя терять на 301/307.

Яндекс кладёт фразу в ``ysclid`` / ``yclid``. Path-cut и locale-хост
выкидывали query — Метрика видела свой хост и ставила «прямой» / без фразы.
"""
from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlsplit

from starlette.requests import Request

ATTR_QUERY_KEYS = (
    "ysclid",
    "yclid",
    "gclid",
    "fbclid",
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "utm_referrer",
)


def incoming_query(request: Request | None) -> str:
    """Query браузера: nginx path-cut часто срезает ASGI query."""
    if request is None:
        return ""
    original = request.headers.get("x-original-uri") or ""
    _, _, raw = original.partition("?")
    if not raw:
        raw = request.url.query
    return raw


def merge_attribution_query(path: str, request: Request | None = None) -> str:
    """Дописать клик-id к Location, не затирая уже стоящие параметры (mode)."""
    dest_path, _, dest_q = path.partition("?")
    dest = dict(parse_qsl(dest_q, keep_blank_values=True))
    incoming = dict(parse_qsl(incoming_query(request), keep_blank_values=True))
    changed = False
    for key in ATTR_QUERY_KEYS:
        val = incoming.get(key)
        if val and key not in dest:
            dest[key] = val
            changed = True
    if not dest:
        return dest_path or path
    if not dest_q and not changed:
        return path
    return f"{dest_path}?{urlencode(dest)}"


def click_ids_from_url(url: str | None) -> dict[str, str]:
    if not url:
        return {}
    try:
        raw = urlsplit(url).query
    except ValueError:
        return {}
    found = dict(parse_qsl(raw, keep_blank_values=True))
    return {key: found[key] for key in ATTR_QUERY_KEYS if found.get(key)}
