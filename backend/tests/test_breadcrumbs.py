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


def test_world_country_uses_strany():
    trail = b.world_country_trail("Германия", paths.country("germany"))
    assert [name for _, name in trail] == ["Главная", "Страны", "Германия"]
    assert trail[1][0] == paths.world_hub()


def test_breadcrumbs_en_home_and_countries():
    from app.services.locale import reset_locale, set_locale

    token = set_locale("en")
    try:
        trail = b.world_home_trail()
        assert [name for _, name in trail] == ["Home", "Countries"]
        assert b.home()[1] == "Home"
        assert b.countries()[1] == "Countries"
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
        assert [name for _, name in trail] == ["Home", "Countries", "Germany"]
        assert b.home()[1] == "Home"
        assert b.countries()[1] == "Countries"
        assert b.russia()[1] == "Russia"
    finally:
        reset_locale(token)
