"""Unit-тесты построителя путей (зеркало sitePaths.js)."""

from app.services import site_paths as p


def test_country_and_indicator_paths():
    assert p.country("germany") == "/germany"
    assert p.indicator("germany", "nama_10_gdp") == "/germany/indicator/nama_10_gdp"
    assert p.indicator_year("russia", "cpi", 2024) == "/russia/indicator/cpi/2024"
    assert p.category("russia", "prices") == "/russia/category/prices"


def test_russia_region_tree():
    assert p.region_hub() == "/russia/region"
    assert p.region("tatarstan") == "/russia/region/tatarstan"
    assert p.region_indicator("tatarstan", "naselenie") == (
        "/russia/region/tatarstan/naselenie"
    )
    assert p.region_map("naselenie") == "/russia/region/map/naselenie"
    assert p.region_rating("naselenie") == "/russia/region-rating/naselenie"
    assert p.region_vs("a", "b") == "/russia/region-vs/a-vs-b"


def test_russia_hubs():
    assert p.today() == "/russia/today"
    assert p.today("cpi") == "/russia/today/cpi"
    assert p.calendar() == "/russia/calendar"
    assert p.calendar(2026, 8) == "/russia/calendar/2026/08"
    assert p.demographics() == "/russia/demographics"
    assert p.russia_categories() == "/russia/category"
    assert p.region_rating_hub() == "/russia/region-rating"


def test_world_hub_unchanged():
    assert p.world_hub() == "/world"
    assert p.world_rating("gdp") == "/world/rating/gdp"


def test_og_paths():
    assert p.og_indicator("russia", "cpi") == "/og/russia/cpi.png"
    assert p.og_indicator("germany", "x", 2020) == "/og/germany/x/2020.png"
    assert p.og_country("germany") == "/og/world/germany.png"
    assert p.og_region("tatarstan", "naselenie") == (
        "/og/russia/region/tatarstan/naselenie.png"
    )
    assert p.og_world_rating("gdp") == "/og/world/rating/gdp.png"
