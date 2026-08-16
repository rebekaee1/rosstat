"""Locale resolver: language = host (+ optional header / preview), not ?lang=.

Target scheme (ADR-0013 §F), after cutover:
  ru.forecasteconomy.com → ru
  forecasteconomy.com (apex) → en

Until ``settings.apex_locale_en`` is True, production apex stays **ru** so a
premature deploy cannot flip Yandex's .com index to English. Explicit
``en.`` hosts, ``X-FE-Locale``, and ``?preview_locale=`` still opt into EN.

Local / staging: any host that is not an explicit ``en.`` / ``ru.`` prefix
defaults to **ru** (same as gated apex).

Request origin (canonical / sitemap ``<loc>`` / RSS / robots / llms /
OG absolute URLs) is also host-aware:
  Host ``ru.*`` → ``https://ru.{apex}``
  everything else → ``settings.public_origin`` (current prod path while
  cutover flag is off — one Russian sitemap on the configured DOMAIN).

No geo-IP locale.
"""

from __future__ import annotations

import re
from contextvars import ContextVar
from typing import Literal
from urllib.parse import parse_qs, urlsplit

from starlette.requests import Request

Locale = Literal["ru", "en"]

LOCALE_HEADER = "x-fe-locale"
PREVIEW_QUERY = "preview_locale"
PRODUCTION_APEX_HOSTS = frozenset({"forecasteconomy.com", "www.forecasteconomy.com"})

_PREVIEW_IN_URL = re.compile(
    rf"[?&]{PREVIEW_QUERY}=(en|ru)\b",
    re.IGNORECASE,
)

_locale_var: ContextVar[Locale] = ContextVar("fe_locale", default="ru")
_origin_var: ContextVar[str | None] = ContextVar("fe_request_origin", default=None)


def normalize_host(host: str | None) -> str:
    """Lowercase host without port."""
    if not host:
        return ""
    return host.split(",", 1)[0].strip().lower().split(":", 1)[0]


def apex_host() -> str:
    """Bare apex hostname (no www): forecasteconomy.com."""
    from app.config import settings

    return (settings.public_host or "forecasteconomy.com").removeprefix("www.")


def ru_public_origin() -> str:
    """Absolute origin of the Russian host (ru.{apex})."""
    return f"https://ru.{apex_host()}"


def en_public_origin() -> str:
    """Absolute origin of the English/apex host (settings.public_origin)."""
    from app.config import settings

    return settings.public_origin


def resolve_request_origin(host: str | None = None) -> str:
    """Absolute origin for canonical / sitemap loc from request Host.

    - ``ru.*`` → ``https://ru.{apex}`` (host-aware even before cutover)
    - ``en.*`` → apex ``public_origin``
    - apex / www / localhost / other → ``settings.public_origin``

    While ``apex_locale_en`` is False, production traffic on apex keeps the
    single-DOMAIN Russian sitemap path unchanged.
    """
    from app.config import settings

    h = normalize_host(host)
    apex = apex_host()
    if h.startswith("ru.") or h == f"ru.{apex}":
        return ru_public_origin()
    if h.startswith("en."):
        return en_public_origin()
    return settings.public_origin


def get_request_origin() -> str:
    """Origin bound for this request, else ``settings.public_origin``."""
    bound = _origin_var.get()
    if bound:
        return bound
    from app.config import settings

    return settings.public_origin


def set_request_origin(origin: str):
    """Bind absolute origin for SSR canonical / sitemap. Returns token."""
    return _origin_var.set(origin.rstrip("/"))


def reset_request_origin(token) -> None:
    _origin_var.reset(token)


def _normalize_locale_token(raw: str | None) -> Locale | None:
    token = (raw or "").strip().lower()
    if token in ("en", "ru"):
        return token  # type: ignore[return-value]
    return None


def apex_locale_en_enabled(explicit: bool | None = None) -> bool:
    """Whether production apex should serve English (cutover flag)."""
    if explicit is not None:
        return bool(explicit)
    from app.config import settings

    return bool(settings.apex_locale_en)


def preview_locale_from_referer(referer: str | None) -> Locale | None:
    """Extract ``preview_locale`` from a Referer URL (Vite proxy path)."""
    if not referer:
        return None
    m = _PREVIEW_IN_URL.search(referer)
    if m:
        return _normalize_locale_token(m.group(1))
    try:
        qs = parse_qs(urlsplit(referer).query)
        values = qs.get(PREVIEW_QUERY) or []
        if values:
            return _normalize_locale_token(values[0])
    except Exception:
        return None
    return None


def resolve_locale(
    *,
    host: str | None = None,
    header: str | None = None,
    preview: str | None = None,
    apex_locale_en: bool | None = None,
) -> Locale:
    """Resolve public UI/SEO locale from header, preview override, then host."""
    for candidate in (header, preview):
        loc = _normalize_locale_token(candidate)
        if loc is not None:
            return loc

    h = normalize_host(host)
    if h.startswith("ru."):
        return "ru"
    if h.startswith("en."):
        return "en"
    if h in PRODUCTION_APEX_HOSTS:
        return "en" if apex_locale_en_enabled(apex_locale_en) else "ru"
    return "ru"


def resolve_locale_from_request(request: Request) -> Locale:
    """Header → ``?preview_locale=`` → Referer preview → host.

    Localhost / non-apex without an explicit override stays ``ru``.
    Production apex stays ``ru`` until ``RUSTATS_APEX_LOCALE_EN=true``.
    """
    host = request.headers.get("x-forwarded-host") or request.headers.get("host")
    header = request.headers.get(LOCALE_HEADER)
    preview = request.query_params.get(PREVIEW_QUERY)
    if not preview:
        preview_from_ref = preview_locale_from_referer(request.headers.get("referer"))
        preview = preview_from_ref
    return resolve_locale(host=host, header=header, preview=preview)


def get_locale() -> Locale:
    return _locale_var.get()


def set_locale(locale: Locale):
    """Bind locale for the current async task (SSR render). Returns token."""
    return _locale_var.set(locale)


def reset_locale(token) -> None:
    _locale_var.reset(token)


def html_lang(locale: Locale | None = None) -> str:
    loc = locale or get_locale()
    return "en" if loc == "en" else "ru"


def og_locale(locale: Locale | None = None) -> str:
    loc = locale or get_locale()
    return "en_US" if loc == "en" else "ru_RU"


def og_locale_alternate(locale: Locale | None = None) -> str:
    loc = locale or get_locale()
    return "ru_RU" if loc == "en" else "en_US"


def in_language(locale: Locale | None = None) -> str:
    """schema.org inLanguage."""
    loc = locale or get_locale()
    return "en" if loc == "en" else "ru"
