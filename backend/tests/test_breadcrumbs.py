"""Unit-тесты схемы хлебных крошек."""

from app.services import breadcrumbs as b
from app.services import site_paths as paths
from app.services.locale import reset_locale, set_locale


def test_russia_category_trail_has_hub():
    trail = b.russia_category_trail("Валюты", paths.russia_category("currencies"))
    assert [name for _, name in trail] == ["Главная", "Россия", "Категории", "Валюты"]
    assert trail[1][0] == paths.russia_home()
    assert trail[2][0] == paths.russia_categories()


def test_russia_indicator_trail():
    trail = b.russia_indicator_trail(
        "Цены", paths.russia_category("prices"), "ИПЦ", paths.russia_indicator("cpi"),
    )
    assert [name for _, name in trail] == ["Главная", "Россия", "Цены", "ИПЦ"]


def test_global_market_indicator_trail_skips_russia():
    trail = b.global_market_indicator_trail(
        "Индексы",
        paths.russia_category("indices"),
        "Доходность 10-летних гособлигаций США",
        paths.russia_indicator("ust-10y"),
    )
    assert [name for _, name in trail] == [
        "Главная",
        "Индексы",
        "Доходность 10-летних гособлигаций США",
    ]
    assert "Россия" not in [name for _, name in trail]


def test_world_country_trail_has_no_hub_node():
    """Витрина /world снята — карточка страны висит прямо на главной."""
    trail = b.world_country_trail("Германия", paths.country("germany"))
    assert [name for _, name in trail] == ["Главная", "Германия"]
    assert trail[1][0] == paths.country("germany")


def test_world_rating_crumb_points_at_concept_not_redirect():
    from app.services.seo_world import WORLD_RATING_DEFAULT_CONCEPT

    trail = b.world_rating_trail("Безработица", paths.world_rating("unemployment-rate"))
    assert [name for _, name in trail] == ["Главная", "Рейтинг стран", "Безработица"]
    assert trail[1][0] == paths.world_rating(WORLD_RATING_DEFAULT_CONCEPT)


def test_breadcrumbs_en_home_and_rating():
    from app.services.locale import reset_locale, set_locale

    token = set_locale("en")
    try:
        trail = b.world_rating_hub_trail()
        assert [name for _, name in trail] == ["Home", "Country rankings"]
        assert b.home()[1] == "Home"
    finally:
        reset_locale(token)


def test_region_rating_trail():
    trail = b.region_rating_trail("Население", paths.region_rating("naselenie"))
    assert [name for _, name in trail] == [
        "Главная", "Россия", "Регионы", "Рейтинг", "Население",
    ]
    assert trail[3][0] == paths.region_rating_hub()


def test_world_crumbs_en_locale():
    token = set_locale("en")
    try:
        trail = b.world_country_trail("Germany", paths.country("germany"))
        assert [name for _, name in trail] == ["Home", "Germany"]
        assert b.home()[1] == "Home"
        assert b.world_ratings()[1] == "Country rankings"
        assert b.russia()[1] == "Russia"
    finally:
        reset_locale(token)
