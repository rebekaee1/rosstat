from app.services.calculation_engine import calculation_engine
from app.tasks.scheduler import _updated_source_codes


def test_weekly_cpi_segment_updates_reach_their_derived_modes() -> None:
    sources = _updated_source_codes(["inflation-weekly"])
    assert set(sources) == {
        "inflation-weekly",
        "inflation-weekly-food",
        "inflation-weekly-nonfood",
        "inflation-weekly-services",
    }
    dependents = set(calculation_engine.dependents_closure_topo(sources))
    assert {
        "cpi-food-period-weekly",
        "cpi-nonfood-period-weekly",
        "cpi-services-period-weekly",
    } <= dependents


def test_unrelated_source_is_not_expanded() -> None:
    assert _updated_source_codes(["capital-investment"]) == ["capital-investment"]
