"""Гео-блок скрейпа с ротацией IP (инцидент 2026-09-03, Сингапур).

Паттерн: тысячи визитов с Chrome/Windows, 1 страница, нулевая активность,
страна одна, IP каждый раз новый (SG днём 2026-09-03, PL вечером).
UA-фильтр nginx и fail2ban по IP это не ловят. Поисковики из списка
не режутся. Пустой `RUSTATS_SCRAPE_BLOCK_COUNTRIES` выключает блок.
"""
from __future__ import annotations

import re

from app.config import settings
from app.services.geoip import lookup as geo_lookup

# Совпадает с nginx $ssr_limit_key: поисковики и ИИ-краулеры.
_SEARCH_UA_RE = re.compile(
    r"yandex|googlebot|bingbot|mail\.ru|duckduckbot|applebot|gptbot|"
    r"petalbot|amazonbot|claudebot|perplexitybot|youbot",
    re.IGNORECASE,
)

_SKIP_PREFIXES = (
    "/api/v1/health",
    "/metrics",
    "/api/docs",
    "/api/redoc",
    "/api/openapi.json",
)


def blocked_country_codes() -> frozenset[str]:
    raw = (settings.scrape_block_countries or "").strip()
    if not raw:
        return frozenset()
    return frozenset(part.strip().upper() for part in raw.split(",") if part.strip())


def is_search_bot_ua(ua: str | None) -> bool:
    return bool(ua and _SEARCH_UA_RE.search(ua))


def should_block(*, ip: str, ua: str | None, path: str) -> str | None:
    """ISO-код страны, если режем. None — пропускаем."""
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
