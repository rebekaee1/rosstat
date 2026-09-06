from app.services.yandex_metrika_reporting import HUMANS_ONLY, without_robots


def test_without_robots_alone():
    assert without_robots() == HUMANS_ONLY


def test_without_robots_and_existing_filter():
    assert without_robots("ym:s:trafficSource=='organic'") == (
        "(ym:s:trafficSource=='organic') AND ym:s:isRobot=='No'"
    )


def test_without_robots_does_not_duplicate():
    already = "ym:s:isRobot=='Yes'"
    assert without_robots(already) == already
