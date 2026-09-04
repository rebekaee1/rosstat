"""Анти-скрейп: привязка сессии к IP-префиксу + опциональный гео-блок.

Ферма 2026-09-03/04: headless Chrome, ротация IP на каждый запрос
(SG → PL → CN/FR/BR). Гео-блок ловил только перечисленные страны — гидра
уходила в другие. Bind ломает кросс-IP сессию: кука HMAC(prefix, день)
с HTML/API не подходит запросу с другого /24 (IPv6 /48).

Правила bind:
- поисковики и соцкраулеры по UA не режутся;
- приватный/невалидный IP (тесты, localhost) — skip;
- куки нет — пропускаем и ставим (первый заход, SPA login);
- кука от другого префикса — 403 без перевыдачи (ретрай не легитимирует);
- пустой ``RUSTATS_SCRAPE_BLOCK_COUNTRIES`` выключает гео-слой.
"""
from __future__ import annotations

import hashlib
import hmac
import ipaddress
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from starlette.responses import Response

from app.config import settings
from app.services.geoip import lookup as geo_lookup

# Совпадает с nginx $ssr_limit_key плюс соцкраулеры OG и соседние Google/Amazon.
_SEARCH_UA_RE = re.compile(
    r"yandex|googlebot|googleother|google-inspectiontool|adsbot-google|"
    r"bingbot|mail\.ru|duckduckbot|applebot|gptbot|"
    r"petalbot|amazonbot|amzn-searchbot|claudebot|perplexitybot|youbot|"
    r"meta-externalagent|facebookexternalhit|twitterbot|telegrambot|"
    r"slackbot|linkedinbot|whatsapp|discordbot|vkshare",
    re.IGNORECASE,
)

# Cursor-вкладка и headless-ферма не должны писать behavior/events.
_NOISE_UA_RE = re.compile(r"HeadlessChrome|Cursor/", re.IGNORECASE)

_SKIP_PREFIXES = (
    "/api/v1/health",
    "/metrics",
    "/api/docs",
    "/api/redoc",
    "/api/openapi.json",
)

COOKIE_NAME = "fe_bind"
_COOKIE_MAX_AGE = 86_400
_HMAC_HEX_LEN = 16


def blocked_country_codes() -> frozenset[str]:
    raw = (settings.scrape_block_countries or "").strip()
    if not raw:
        return frozenset()
    return frozenset(part.strip().upper() for part in raw.split(",") if part.strip())


def is_search_bot_ua(ua: str | None) -> bool:
    return bool(ua and _SEARCH_UA_RE.search(ua))


def is_noise_client_ua(ua: str | None) -> bool:
    return bool(ua and _NOISE_UA_RE.search(ua))


def ip_network_prefix(ip: str) -> str | None:
    """IPv4 /24, IPv6 /48. None — не глобальный адрес (localhost, тесты)."""
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return None
    if not addr.is_global:
        return None
    if isinstance(addr, ipaddress.IPv4Address):
        net = ipaddress.ip_network(f"{addr}/24", strict=False)
        return str(net.network_address)
    net = ipaddress.ip_network(f"{addr}/48", strict=False)
    return str(net.network_address)


def _secret_bytes() -> bytes:
    raw = (settings.scrape_bind_secret or "").strip()
    if raw:
        return raw.encode("utf-8")
    return f"{settings.public_base_url}|fe_bind_v1".encode("utf-8")


def _ymd_utc(when: datetime | None = None) -> str:
    now = when or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return now.astimezone(timezone.utc).strftime("%Y%m%d")


def issue_token(ip: str, when: datetime | None = None) -> str | None:
    prefix = ip_network_prefix(ip)
    if prefix is None:
        return None
    ymd = _ymd_utc(when)
    digest = hmac.new(
        _secret_bytes(), f"{prefix}|{ymd}".encode("utf-8"), hashlib.sha256
    ).hexdigest()[:_HMAC_HEX_LEN]
    return f"{ymd}.{digest}"


def verify_token(token: str | None, ip: str, when: datetime | None = None) -> bool:
    if not token or "." not in token:
        return False
    prefix = ip_network_prefix(ip)
    if prefix is None:
        return False
    ymd, _, digest = token.partition(".")
    if len(ymd) != 8 or len(digest) != _HMAC_HEX_LEN:
        return False
    now = when or datetime.now(timezone.utc)
    allowed = {_ymd_utc(now), _ymd_utc(now - timedelta(days=1))}
    if ymd not in allowed:
        return False
    expected = hmac.new(
        _secret_bytes(), f"{prefix}|{ymd}".encode("utf-8"), hashlib.sha256
    ).hexdigest()[:_HMAC_HEX_LEN]
    return hmac.compare_digest(digest, expected)


def should_block(*, ip: str, ua: str | None, path: str) -> str | None:
    """ISO-код страны, если режем гео-слоем. None — пропускаем."""
    codes = blocked_country_codes()
    if not codes:
        return None
    path = path or "/"
    if any(path.startswith(p) for p in _SKIP_PREFIXES):
        return None
    if is_search_bot_ua(ua):
        return None
    geo = geo_lookup(ip)
    cc = (geo.get("country_code") or "").upper()
    if cc and cc in codes:
        return cc
    return None


def is_bind_protected_path(path: str) -> bool:
    path = path or "/"
    if not path.startswith("/api/"):
        return False
    return not any(path.startswith(p) for p in _SKIP_PREFIXES)


@dataclass(frozen=True)
class BindDecision:
    block: bool
    set_cookie: bool


def bind_decision(
    *, ip: str, ua: str | None, path: str, cookie: str | None
) -> BindDecision:
    if not settings.scrape_bind_enabled:
        return BindDecision(block=False, set_cookie=False)
    if is_search_bot_ua(ua):
        return BindDecision(block=False, set_cookie=False)
    if any((path or "/").startswith(p) for p in _SKIP_PREFIXES):
        return BindDecision(block=False, set_cookie=False)
    if ip_network_prefix(ip) is None:
        return BindDecision(block=False, set_cookie=False)
    if not is_bind_protected_path(path):
        return BindDecision(block=False, set_cookie=True)
    if not cookie:
        return BindDecision(block=False, set_cookie=True)
    if verify_token(cookie, ip):
        return BindDecision(block=False, set_cookie=True)
    return BindDecision(block=True, set_cookie=False)


def attach_bind_cookie(response: Response, ip: str) -> None:
    token = issue_token(ip)
    if not token:
        return
    from app.security.auth import effective_auth_cookie_domain

    kw: dict = {
        "httponly": True,
        "secure": settings.auth_cookie_secure,
        "samesite": "lax",
        "path": "/",
        "max_age": _COOKIE_MAX_AGE,
    }
    domain = effective_auth_cookie_domain()
    if domain:
        kw["domain"] = domain
    response.set_cookie(COOKIE_NAME, token, **kw)
