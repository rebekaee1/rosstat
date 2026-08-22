"""Единая схема хлебных крошек (ADR-0013).

Клиентское зеркало: `frontend/src/lib/breadcrumbs.js`.
Видимый nav и JSON-LD BreadcrumbList обязаны совпадать по числу и именам.
"""

from __future__ import annotations

from app.services import site_paths as paths

Crumb = tuple[str, str]  # (path, name)


def _en() -> bool:
    from app.services.locale import get_locale

    return get_locale() == "en"


def home() -> Crumb:
    return ("/", "Home" if _en() else "Главная")


def russia() -> Crumb:
    return (paths.russia_home(), "Russia" if _en() else "Россия")


def russia_categories() -> Crumb:
    return (paths.russia_categories(), "Categories" if _en() else "Категории")


def regions() -> Crumb:
    return (paths.region_hub(), "Regions" if _en() else "Регионы")


def region_ratings() -> Crumb:
    return (paths.region_rating_hub(), "Rankings" if _en() else "Рейтинг")


def world_ratings() -> Crumb:
    """Рейтинг стран. Ведёт на конкретный показатель: /world/rating без него — 301."""
    from app.services.seo_world import WORLD_RATING_DEFAULT_CONCEPT

    return (
        paths.world_rating(WORLD_RATING_DEFAULT_CONCEPT),
        "Country rankings" if _en() else "Рейтинг стран",
    )


def trail(*items: Crumb) -> list[Crumb]:
    return list(items)


def russia_home_trail() -> list[Crumb]:
    return trail(home(), russia())


def russia_categories_trail() -> list[Crumb]:
    return trail(home(), russia(), russia_categories())


def russia_category_trail(category_name: str, category_path: str) -> list[Crumb]:
    return trail(home(), russia(), russia_categories(), (category_path, category_name))


def russia_indicator_trail(
    category_name: str | None,
    category_path: str | None,
    indicator_name: str,
    indicator_path: str,
) -> list[Crumb]:
    items = [home(), russia()]
    if category_name and category_path:
        items.append((category_path, category_name))
    items.append((indicator_path, indicator_name))
    return items


def global_market_indicator_trail(
    category_name: str | None,
    category_path: str | None,
    indicator_name: str,
    indicator_path: str,
) -> list[Crumb]:
    """Мировой рыночный ряд: Главная / [категория] / показатель.

    Без узла «Россия» — ряд не относится к российской статистике, даже если
    URL лежит в общем каталоге `/russia/indicator/...`.
    """
    items = [home()]
    if category_name and category_path:
        items.append((category_path, category_name))
    items.append((indicator_path, indicator_name))
    return items


def russia_indicator_year_trail(
    category_name: str | None,
    category_path: str | None,
    indicator_name: str,
    indicator_path: str,
    year: int | str,
    year_path: str,
) -> list[Crumb]:
    items = russia_indicator_trail(
        category_name, category_path, indicator_name, indicator_path
    )
    items.append((year_path, str(year)))
    return items


def global_market_indicator_year_trail(
    category_name: str | None,
    category_path: str | None,
    indicator_name: str,
    indicator_path: str,
    year: int | str,
    year_path: str,
) -> list[Crumb]:
    items = global_market_indicator_trail(
        category_name, category_path, indicator_name, indicator_path
    )
    items.append((year_path, str(year)))
    return items


def regions_trail() -> list[Crumb]:
    return trail(home(), russia(), regions())


def region_trail(region_name: str, region_path: str) -> list[Crumb]:
    return trail(home(), russia(), regions(), (region_path, region_name))


def region_indicator_trail(
    region_name: str,
    region_path: str,
    indicator_name: str,
    indicator_path: str,
) -> list[Crumb]:
    return trail(
        home(),
        russia(),
        regions(),
        (region_path, region_name),
        (indicator_path, indicator_name),
    )


def region_rating_hub_trail() -> list[Crumb]:
    return trail(home(), russia(), regions(), region_ratings())


def region_rating_trail(indicator_name: str, rating_path: str) -> list[Crumb]:
    return trail(
        home(),
        russia(),
        regions(),
        region_ratings(),
        (rating_path, indicator_name),
    )


def region_vs_trail(label: str, vs_path: str) -> list[Crumb]:
    return trail(home(), russia(), regions(), (vs_path, label))


def today_trail() -> list[Crumb]:
    return trail(home(), russia(), (paths.today(), "Today" if _en() else "Сегодня"))


def today_indicator_trail(label: str, path: str) -> list[Crumb]:
    return trail(
        home(),
        russia(),
        (paths.today(), "Today" if _en() else "Сегодня"),
        (path, label),
    )


def calendar_trail() -> list[Crumb]:
    return trail(
        home(), russia(), (paths.calendar(), "Calendar" if _en() else "Календарь")
    )


def calendar_month_trail(label: str, month_path: str) -> list[Crumb]:
    return trail(
        home(),
        russia(),
        (paths.calendar(), "Calendar" if _en() else "Календарь"),
        (month_path, label),
    )


def demographics_trail() -> list[Crumb]:
    return trail(
        home(),
        russia(),
        (paths.demographics(), "Demographics" if _en() else "Демография"),
    )


def world_country_trail(country_name: str, country_path: str) -> list[Crumb]:
    return trail(home(), (country_path, country_name))


def world_indicator_trail(
    country_name: str,
    country_path: str,
    indicator_name: str,
    indicator_path: str,
) -> list[Crumb]:
    return trail(
        home(),
        (country_path, country_name),
        (indicator_path, indicator_name),
    )


def world_rating_hub_trail() -> list[Crumb]:
    return trail(home(), world_ratings())


def world_rating_trail(name: str, rating_path: str) -> list[Crumb]:
    return trail(home(), world_ratings(), (rating_path, name))


def tool_trail(name: str, path: str) -> list[Crumb]:
    """Платформенные инструменты: /compare, /calculator*."""
    return trail(home(), (path, name))
