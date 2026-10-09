"""Разрезы событий для отчётов: язык сайта по адресу, группа страны (круг 11, зона H)."""
from __future__ import annotations

from urllib.parse import urlsplit

from app.services.locale import PRODUCTION_APEX_HOSTS, normalize_host
from app.services.signup_attribution import is_russia

UNKNOWN = "unknown"


def site_locale_from_url(url: str | None) -> str | None:
    """Язык сайта по хосту адреса события: ru.* = русский, en.* и apex = английский.

    До переключения apex на английский (`apex_locale_en`) apex отдаёт русскую версию,
    поэтому правило берётся из того же флага, что и язык страниц. Хосты разработки и
    неизвестные хосты дают None (честная пустота, а не угаданный язык).
    """
    if not url:
        return None
    try:
        host = normalize_host(urlsplit(str(url)).hostname or "")
    except ValueError:
        return None
    if not host:
        return None
    if host.startswith("ru."):
        return "ru"
    if host.startswith("en."):
        return "en"
    if host in PRODUCTION_APEX_HOSTS:
        from app.config import settings

        return "en" if settings.apex_locale_en else "ru"
    return None


def country_group(country: str | None, country_code: str | None = None) -> str:
    """«ru» — Россия, «foreign» — другая страна, «unknown» — страны нет."""
    flag = is_russia(country, country_code)
    if flag is None:
        return UNKNOWN
    return "ru" if flag else "foreign"


def surface_from_url(url: str | None) -> str | None:
    """Поверхность сайта по пути адреса события: где человек был, когда сработало событие.

    Нужна, пока события скачивания и упоров не несут параметр `surface` (его добавляют
    компоненты страниц): отчёты «выгрузки по поверхностям» работают и без него. Имена
    совпадают с теми, что предложены для параметра: indicator / world_indicator / region /
    rating / compare / country / calculator / embed и т.д.
    """
    if not url:
        return None
    try:
        path = urlsplit(str(url)).path or "/"
    except ValueError:
        return None
    parts = [p for p in path.strip("/").split("/") if p]
    if not parts:
        return "home"
    first = parts[0]
    second = parts[1] if len(parts) > 1 else ""
    if first == "compare":
        return "compare"
    if first == "world":
        return "rating" if second == "rating" else "world_home"
    if first in ("calculator", "calculators"):
        return "calculator"
    if first in ("widgets", "embed"):
        return "embed"
    if first == "russia":
        return {
            "indicator": "indicator", "region": "region", "region-rating": "rating",
            "region-vs": "region", "demographics": "demographics", "calendar": "calendar",
            "today": "today", "category": "category", "": "russia_home",
        }.get(second, "other")
    if first == "currencies":
        return "indicator" if second == "indicator" else "category"
    if first in ("forecasts", "methodology", "about"):
        return first
    if second == "indicator":
        return "world_indicator"
    if second in ("region", "regions"):
        return "region"
    if len(parts) == 1 and first not in ("login", "register", "account", "privacy", "terms"):
        return "country"
    return "other"
