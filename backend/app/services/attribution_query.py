"""Клик-id и UTM, которые нельзя терять на 301/307.

Яндекс кладёт фразу в ``ysclid`` / ``yclid``. Path-cut и locale-хост
выкидывали query — Метрика видела свой хост и ставила «прямой» / без фразы.

``etext`` — метка Директа/раздачи. Её нельзя вырезать до первого ``ym('hit')``.
``fe_attr`` — JS-читаемая кука на ``.forecasteconomy.com``: после 307 apex→ru.
первый hit на ``ru.`` всё ещё видит клик-id, даже если query срезали.
"""
from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlparse, urlsplit

from starlette.requests import Request
from starlette.responses import Response

from app.config import settings

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
    "etext",
)

ATTR_COOKIE_NAME = "fe_attr"
ATTR_COOKIE_MAX_AGE = 1800


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


def _own_hosts() -> tuple[str, ...]:
    host = (settings.public_host or "forecasteconomy.com").removeprefix("www.")
    return (host, f"ru.{host}", "localhost", "127.0.0.1")


def _is_own_host(hostname: str | None) -> bool:
    h = (hostname or "").lower().removeprefix("www.")
    if not h:
        return False
    return any(h == own or h.endswith("." + own) for own in _own_hosts())


def attribution_payload(request: Request | None) -> dict[str, str]:
    """Клик-id из query плюс внешний Referer как ``utm_referrer``."""
    if request is None:
        return {}
    incoming = dict(parse_qsl(incoming_query(request), keep_blank_values=True))
    out = {key: incoming[key] for key in ATTR_QUERY_KEYS if incoming.get(key)}
    if out.get("utm_referrer"):
        return out
    referer = (request.headers.get("referer") or "").strip()
    if not referer:
        return out
    try:
        host = (urlparse(referer).hostname or "").lower().removeprefix("www.")
    except ValueError:
        return out
    if host and not _is_own_host(host):
        out["utm_referrer"] = referer[:2000]
    return out


def attach_attribution_cookie(response: Response, request: Request | None) -> None:
    """Кука на общем домене, чтобы 307 apex→ru. не обнулил первый hit."""
    payload = attribution_payload(request)
    if not payload:
        return
    from app.security.auth import effective_auth_cookie_domain

    kw: dict = {
        "httponly": False,
        "secure": settings.auth_cookie_secure,
        "samesite": "lax",
        "path": "/",
        "max_age": ATTR_COOKIE_MAX_AGE,
    }
    domain = effective_auth_cookie_domain()
    if domain:
        kw["domain"] = domain
    response.set_cookie(ATTR_COOKIE_NAME, urlencode(payload)[:2000], **kw)
