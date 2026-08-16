"""Единая схема хлебных крошек (ADR-0013).

Клиентское зеркало: `frontend/src/lib/breadcrumbs.js`.
Видимый nav и JSON-LD BreadcrumbList обязаны совпадать по числу и именам.
"""

from __future__ import annotations

from app.services import site_paths as paths

Crumb = tuple[str, str]  # (path, name)


def home() -> Crumb:
    return ("/", "Главная")


def russia() -> Crumb:
    return (paths.russia_home(), "Россия")


def russia_categories() -> Crumb:
    return (paths.russia_categories(), "Категории")


def regions() -> Crumb:
    return (paths.region_hub(), "Регионы")


def region_ratings() -> Crumb:
    return (paths.region_rating_hub(), "Рейтинг")


def countries() -> Crumb:
    """Хаб межстрановой статистики — публичная подпись «Страны»."""
    return (paths.world_hub(), "Страны")


def world_ratings() -> Crumb:
    return (paths.world_rating(), "Рейтинг")


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
    return trail(home(), russia(), (paths.today(), "Сегодня"))


def today_indicator_trail(label: str, path: str) -> list[Crumb]:
    return trail(home(), russia(), (paths.today(), "Сегодня"), (path, label))


def calendar_trail() -> list[Crumb]:
    return trail(home(), russia(), (paths.calendar(), "Календарь"))


def calendar_month_trail(label: str, month_path: str) -> list[Crumb]:
    return trail(home(), russia(), (paths.calendar(), "Календарь"), (month_path, label))


def demographics_trail() -> list[Crumb]:
    return trail(home(), russia(), (paths.demographics(), "Демография"))


def world_home_trail() -> list[Crumb]:
    return trail(home(), countries())


def world_country_trail(country_name: str, country_path: str) -> list[Crumb]:
    return trail(home(), countries(), (country_path, country_name))


def world_indicator_trail(
    country_name: str,
    country_path: str,
    indicator_name: str,
    indicator_path: str,
) -> list[Crumb]:
    return trail(
        home(),
        countries(),
        (country_path, country_name),
        (indicator_path, indicator_name),
    )


def world_rating_hub_trail() -> list[Crumb]:
    return trail(home(), countries(), world_ratings())


def world_rating_trail(name: str, rating_path: str) -> list[Crumb]:
    return trail(home(), countries(), world_ratings(), (rating_path, name))


def tool_trail(name: str, path: str) -> list[Crumb]:
    """Платформенные инструменты: /compare, /calculator*."""
    return trail(home(), (path, name))
