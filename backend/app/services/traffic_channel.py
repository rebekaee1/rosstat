"""Классификация источника визита в канал привлечения.

Единая точка истины для «канала» во всех слоях (behavior_sessions,
server_sessions, rollup'ы, сверка с Метрикой). Приоритет сигналов повторяет
логику Метрики (last non-direct click доопределяется на уровне витрин):

1. Рекламные метки (yclid / etext / utm_medium=cpc|cpm|paid) → ``ad``.
2. ``ysclid`` (клик из поиска Яндекса) → ``search``.
3. Известный ИИ-ассистент (ChatGPT / Алиса / Perplexity) → ``referral``.
   Не поиск: Алиса живёт на ``alice.yandex.ru``, не в выдаче.
4. utm_source без рекламного medium → ``campaign`` (рассылки, посевы).
5. ``utm_referrer`` / referrer-домен: поисковик → ``search``, соцсеть →
   ``social``, свой домен → ``internal``, прочее → ``referral``.
   Кабинеты Яндекса (oauth / webmaster / metrika / ads) — не поиск.
   Клик-id с собственного referrer (path-cut) достаются из query.
6. Ничего → ``direct``.
"""
from __future__ import annotations

from urllib.parse import urlparse

from app.services.attribution_query import click_ids_from_url

_SEARCH_HOSTS = (
    "yandex.", "ya.ru", "google.", "bing.com", "duckduckgo.com",
    "go.mail.ru", "rambler.ru", "nova.rambler.ru", "search.brave.com", "baidu.com",
)
# Хост начинается с yandex., но это не выдача: вход, Вебмастер, кабинет, Алиса.
_YANDEX_SERVICE_PREFIXES = (
    "oauth.yandex.",
    "passport.yandex.",
    "webmaster.yandex.",
    "metrika.yandex.",
    "partner.yandex.",
    "ads.yandex.",
    "mail.yandex.",
    "disk.yandex.",
    "calendar.yandex.",
    "alice.yandex.",
    "dialogs.yandex.",
    "dialog.yandex.",
)
# Почта Mail.ru — не поиск. Раньше матчилась по суффиксу mail.ru.
_NOT_SEARCH_HOSTS = (
    "e.mail.ru",
    "light.mail.ru",
    "touch.mail.ru",
    "account.mail.ru",
    "auth.mail.ru",
)

# Человеческие имена для пирога. Нейро Яндекса отдельной метки не шлёт —
# остаётся внутри поиска Яндекса, выдумать нельзя.
_ASSISTANT_HOSTS: tuple[tuple[str, str], ...] = (
    ("chatgpt.com", "ChatGPT"),
    ("chat.openai.com", "ChatGPT"),
    ("openai.com", "ChatGPT"),
    ("perplexity.ai", "Perplexity"),
    ("alice.yandex.", "Алиса"),
    ("gemini.google.com", "Gemini"),
    ("claude.ai", "Claude"),
    ("you.com", "You.com"),
    ("copilot.microsoft.com", "Copilot"),
)
_ASSISTANT_UTM = {
    "chatgpt.com": "ChatGPT",
    "openai": "ChatGPT",
    "chat.openai.com": "ChatGPT",
    "perplexity": "Perplexity",
    "perplexity.ai": "Perplexity",
}
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


def _is_yandex_service_host(host: str) -> bool:
    h = host.lower().removeprefix("www.")
    return any(h == p.rstrip(".") or h.startswith(p) for p in _YANDEX_SERVICE_PREFIXES)


def _is_mail_web_host(host: str) -> bool:
    h = host.lower().removeprefix("www.")
    return any(h == p or h.endswith("." + p) for p in _NOT_SEARCH_HOSTS)


def _is_search_host(host: str | None) -> bool:
    if not host:
        return False
    h = host.lower().removeprefix("www.")
    if _is_yandex_service_host(h) or _is_mail_web_host(h):
        return False
    return any(h.startswith(s) or ("." + s) in ("." + h) for s in _SEARCH_HOSTS)


def assistant_name(
    *,
    referrer: str | None = None,
    utm_source: str | None = None,
    utm_referrer: str | None = None,
    host: str | None = None,
) -> str | None:
    """Человеческое имя ИИ-источника или None, если это не ассистент."""
    src = (utm_source or "").strip().lower()
    if src in _ASSISTANT_UTM:
        return _ASSISTANT_UTM[src]
    hosts = [host, referrer_host(utm_referrer), referrer_host(referrer)]
    for candidate in hosts:
        if not candidate:
            continue
        h = candidate.lower().removeprefix("www.")
        for prefix, name in _ASSISTANT_HOSTS:
            if h == prefix.rstrip(".") or h.startswith(prefix) or h.endswith("." + prefix.rstrip(".")):
                return name
    return None


def search_engine_name(host: str | None) -> str | None:
    """Имя поисковика по referrer-хосту; None — хост не поисковый."""
    if not host or not _is_search_host(host):
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
    ysclid: str | None = None,
    utm_referrer: str | None = None,
    etext: str | None = None,
) -> str:
    salvaged = click_ids_from_url(referrer)
    salvaged.update(click_ids_from_url(utm_referrer))
    yclid = yclid or salvaged.get("yclid")
    ysclid = ysclid or salvaged.get("ysclid")
    utm_referrer = utm_referrer or salvaged.get("utm_referrer")
    etext = etext or salvaged.get("etext")
    medium = (utm_medium or "").strip().lower()
    if yclid or etext or medium in _AD_MEDIUMS:
        return "ad"
    if ysclid:
        return "search"
    if assistant_name(
        referrer=referrer, utm_source=utm_source, utm_referrer=utm_referrer,
    ):
        return "referral"
    if (utm_source or "").strip():
        return "campaign"
    stamped_host = referrer_host(utm_referrer)
    if stamped_host:
        if _is_search_host(stamped_host):
            return "search"
        if any(
            stamped_host == h or stamped_host.endswith("." + h) or stamped_host.startswith(h)
            for h in _SOCIAL_HOSTS
        ):
            return "social"
        if not any(
            stamped_host == h or stamped_host.endswith("." + h) or stamped_host.startswith(h)
            for h in _OWN_HOSTS
        ):
            return "referral"
    host = referrer_host(referrer)
    if not host:
        return "direct"
    if any(host == h or host.endswith("." + h) or host.startswith(h) for h in _OWN_HOSTS):
        return "internal"
    if _is_search_host(host):
        return "search"
    if any(host == h or host.endswith("." + h) or host.startswith(h) for h in _SOCIAL_HOSTS):
        return "social"
    return "referral"
