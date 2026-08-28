"""Единая точка построения публичных путей (ADR-0013, path-cut).

Все sitemap / SSR canonical / OG / IndexNow / legacy_redirects / перелинковка
обязаны ходить через этот модуль. Зеркало на фронте: `frontend/src/lib/sitePaths.js`.

Схема (решение владельца 2026-08-16): тип сущности назван явно, чтобы
показатели и регионы не делили одно пространство имён.

  /{country}
  /{country}/indicator/{code}[/{year}]
  /{country}/category/{slug}
  /russia/region[/{slug}[/{code}]]
  /russia/region-rating/{code}
  /russia/region-vs/{a}-vs-{b}
  /russia/today[/{code}]  /russia/calendar…  /russia/demographics
  /world  /world/rating/{concept}
"""

from __future__ import annotations

import re

# Канонический слаг России (не в world_countries — отдельный data plane).
RUSSIA = "russia"

# Первые сегменты, которые НЕ могут быть слагом страны (и для страховки —
# слагом региона). Расширять при добавлении корневых роутов платформы.
RESERVED_FIRST_SEGMENTS: frozenset[str] = frozenset({
    # Платформенные страницы
    "about",
    "methodology",
    "privacy",
    "terms",
    "calculator",
    "compare",
    "widgets",
    "login",
    "register",
    "account",
    "admin",
    # Мировой хаб и кросс-рейтинги (не карточка страны)
    "world",
    # Технические / edge
    "api",
    "assets",
    "og",
    "og-proxy",
    "embed",
    "health",
    "fonts",
    "feed.xml",
    "robots.txt",
    "llms.txt",
    "consent.js",
    "sitemap.xml",
    # Легаси-корни до path-cut (остаются зарезервированными, чтобы слаг
    # страны никогда не перехватил старый префиксный namespace)
    "indicator",
    "category",
    "today",
    "calendar",
    "demographics",
    "regions",
    "region",
    "region-rating",
    "region-vs",
})


def is_reserved_first_segment(segment: str) -> bool:
    """True, если сегмент нельзя использовать как слаг страны/региона."""
    if not segment:
        return True
    s = segment.lower().strip("/")
    if s in RESERVED_FIRST_SEGMENTS:
        return True
    if s.startswith("sitemap") and s.endswith(".xml"):
        return True
    return False


def home() -> str:
    """Главная: карта мира, рейтинг стран и каталог стран."""
    return "/"


def compare() -> str:
    """Сравнение показателей."""
    return "/compare"


def country(slug: str) -> str:
    """Карточка страны: /{slug}."""
    return f"/{_slug(slug)}"


def indicator(country_slug: str, code: str) -> str:
    """Показатель страны: /{country}/indicator/{code}."""
    return f"/{_slug(country_slug)}/indicator/{_code(code)}"


def indicator_year(country_slug: str, code: str, year: int | str) -> str:
    """Годовой лендинг: /{country}/indicator/{code}/{year}."""
    return f"{indicator(country_slug, code)}/{int(year)}"


def indicator_month(country_slug: str, code: str, year: int, month: int) -> str:
    """Месячный лендинг: /{country}/indicator/{code}/{year}-{mm}."""
    return f"{indicator(country_slug, code)}/{int(year)}-{int(month):02d}"


def category(country_slug: str, slug: str) -> str:
    """Категория (Россия и др. с каталогом): /{country}/category/{slug}."""
    return f"/{_slug(country_slug)}/category/{_slug(slug)}"


def russia_home() -> str:
    return country(RUSSIA)


def russia_indicator(code: str) -> str:
    return indicator(RUSSIA, code)


def russia_indicator_year(code: str, year: int | str) -> str:
    return indicator_year(RUSSIA, code, year)


def russia_category(slug: str) -> str:
    return category(RUSSIA, slug)


def russia_categories() -> str:
    """Хаб категорий России: /russia/category."""
    return f"/{RUSSIA}/category"


def region_hub() -> str:
    """Список регионов России: /russia/region."""
    return f"/{RUSSIA}/region"


def region_rating_hub() -> str:
    """Хаб рейтингов регионов: /russia/region-rating."""
    return f"/{RUSSIA}/region-rating"


def region(slug: str) -> str:
    return f"/{RUSSIA}/region/{_slug(slug)}"


def region_indicator(slug: str, code: str) -> str:
    return f"/{RUSSIA}/region/{_slug(slug)}/{_code(code)}"


def region_map(code: str) -> str:
    """Карта регионов по показателю: /russia/region/map/{code}."""
    return f"/{RUSSIA}/region/map/{_code(code)}"


def region_rating(code: str) -> str:
    return f"/{RUSSIA}/region-rating/{_code(code)}"


def region_vs(slug_a: str, slug_b: str) -> str:
    return f"/{RUSSIA}/region-vs/{_slug(slug_a)}-vs-{_slug(slug_b)}"


def today(code: str | None = None) -> str:
    base = f"/{RUSSIA}/today"
    return f"{base}/{_code(code)}" if code else base


def calendar(year: int | str | None = None, month: int | str | None = None) -> str:
    base = f"/{RUSSIA}/calendar"
    if year is None:
        return base
    y = int(year)
    if month is None:
        return f"{base}/{y}"
    return f"{base}/{y}/{int(month):02d}"


def demographics() -> str:
    return f"/{RUSSIA}/demographics"


def world_hub() -> str:
    """Снятая витрина мира: 301 на главную. Оставлено для карты легаси-URL."""
    return "/world"


def world_rating(concept: str | None = None) -> str:
    base = "/world/rating"
    return f"{base}/{_slug(concept)}" if concept else base


def world_rating_year(concept: str, year: int | str) -> str:
    """Канон года рейтинга: path-URL /world/rating/{concept}/{year}."""
    return f"{world_rating(concept)}/{int(year)}"


def og_indicator(country_slug: str, code: str, year: int | str | None = None) -> str:
    """Публичный путь OG-картинки показателя.

    year — год (2025) или «год-месяц» месячного лендинга («2025-07»);
    `_period` пропускает уже готовые строки вида YYYY-MM без потери валидации.
    """
    base = f"/og/{_slug(country_slug)}/{_code(code)}"
    if year is None:
        return f"{base}.png"
    return f"{base}/{_period(year)}.png"


def _period(year: int | str) -> str:
    if isinstance(year, int):
        return str(year)
    text = str(year).strip()
    if re.fullmatch(r"(?:19|20)\d{2}", text) or re.fullmatch(
        r"(?:19|20)\d{2}-\d{2}", text
    ):
        return text
    raise ValueError(f"bad og period: {year!r}")


def og_region(slug: str, code: str) -> str:
    return f"/og/{RUSSIA}/region/{_slug(slug)}/{_code(code)}.png"


def region_indicator_year(slug: str, code: str, year: int | str) -> str:
    """Годовой лендинг региона: /russia/region/{slug}/{code}/{year}."""
    return f"{region_indicator(slug, code)}/{int(year)}"


def og_region_year(slug: str, code: str, year: int | str) -> str:
    """OG-картинка годового лендинга региона."""
    return (
        f"/og/{RUSSIA}/region/{_slug(slug)}/{_code(code)}/{int(year)}.png"
    )


def og_region_rating(code: str) -> str:
    return f"/og/{RUSSIA}/region-rating/{_code(code)}.png"


def og_region_vs(slug_a: str, slug_b: str) -> str:
    return f"/og/{RUSSIA}/region-vs/{_slug(slug_a)}-vs-{_slug(slug_b)}.png"


def og_today() -> str:
    return f"/og/{RUSSIA}/today.png"


def og_country(slug: str) -> str:
    """OG карточки страны: /og/world/{slug}.png (не /og/{slug}.png —

    односегментный /og/{code}.png занят легаси-картинками макро-России).
    """
    return f"/og/world/{_slug(slug)}.png"


def og_world_rating(concept: str) -> str:
    return f"/og/world/rating/{_slug(concept)}.png"


def og_world_rating_year(concept: str, year: int | str) -> str:
    return f"/og/world/rating/{_slug(concept)}/{int(year)}.png"


def _slug(value: str) -> str:
    s = (value or "").strip().strip("/")
    if not s:
        raise ValueError("empty slug")
    return s


def _code(value: str) -> str:
    s = (value or "").strip().strip("/")
    if not s:
        raise ValueError("empty code")
    return s
