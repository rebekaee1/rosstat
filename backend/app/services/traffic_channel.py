"""Классификация источника визита в канал привлечения.

Единая точка истины для «канала» во всех слоях (behavior_sessions,
server_sessions, rollup'ы, сверка с Метрикой). Приоритет сигналов повторяет
логику Метрики (last non-direct click доопределяется на уровне витрин):

1. Рекламные метки (yclid / utm_medium=cpc|cpm|paid) → ``ad``.
2. utm_source без рекламного medium → ``campaign`` (рассылки, посевы).
3. Referrer-домен: поисковик → ``search``, соцсеть/мессенджер → ``social``,
   свой домен → ``internal``, прочее → ``referral``.
4. Ничего → ``direct``.
"""
from __future__ import annotations

from urllib.parse import urlparse

_SEARCH_HOSTS = (
    "yandex.", "ya.ru", "google.", "bing.com", "duckduckgo.com", "mail.ru",
    "go.mail.ru", "rambler.ru", "nova.rambler.ru", "search.brave.com", "baidu.com",
)
_SOCIAL_HOSTS = (
    "vk.com", "vk.ru", "ok.ru", "t.me", "telegram.", "web.telegram.",
    "twitter.com", "x.com", "facebook.com", "instagram.com", "linkedin.com",
    "reddit.com", "youtube.com", "dzen.ru", "zen.yandex.", "pikabu.ru", "habr.com",
)
_OWN_HOSTS = ("forecasteconomy.com", "localhost", "127.0.0.1")
_AD_MEDIUMS = {"cpc", "cpm", "cpa", "paid", "ppc", "banner", "ad", "ads", "performance"}

CHANNELS = ("ad", "campaign", "search", "social", "referral", "internal", "direct")

# Человеческие имена поисковиков для витрин (этап 2 BI 2.1): host-префикс →
# ярлык. Порядок важен — go.mail.ru раньше mail.ru.
_ENGINE_NAMES: tuple[tuple[str, str], ...] = (
    ("yandex.", "Яндекс"), ("ya.ru", "Яндекс"),
    ("google.", "Google"), ("bing.com", "Bing"),
    ("duckduckgo.com", "DuckDuckGo"),
    ("go.mail.ru", "Поиск Mail.ru"), ("mail.ru", "Поиск Mail.ru"),
    ("nova.rambler.ru", "Рамблер"), ("rambler.ru", "Рамблер"),
    ("search.brave.com", "Brave"), ("baidu.com", "Baidu"),
)


def search_engine_name(host: str | None) -> str | None:
    """Имя поисковика по referrer-хосту; None — хост не поисковый."""
    if not host:
        return None
    h = host.lower().removeprefix("www.")
    for prefix, name in _ENGINE_NAMES:
        if h.startswith(prefix) or ("." + prefix) in ("." + h):
            return name
    return None


def referrer_host(referrer: str | None) -> str | None:
    if not referrer:
        return None
    try:
        host = urlparse(referrer).netloc.lower()
        return host.removeprefix("www.") or None
    except Exception:
        return None


def classify_channel(
    referrer: str | None = None,
    utm_source: str | None = None,
    utm_medium: str | None = None,
    yclid: str | None = None,
) -> str:
    medium = (utm_medium or "").strip().lower()
    if yclid or medium in _AD_MEDIUMS:
        return "ad"
    if (utm_source or "").strip():
        return "campaign"
    host = referrer_host(referrer)
    if not host:
        return "direct"
    if any(host == h or host.endswith("." + h) or host.startswith(h) for h in _OWN_HOSTS):
        return "internal"
    if any(host.startswith(h) or ("." + h) in ("." + host) for h in _SEARCH_HOSTS):
        return "search"
    if any(host == h or host.endswith("." + h) or host.startswith(h) for h in _SOCIAL_HOSTS):
        return "social"
    return "referral"
