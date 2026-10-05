"""Профиль страны: при нескольких источниках населения берётся один, а не пустое поле."""
from types import SimpleNamespace

from app.api import world


def _ind(code, provider, points):
    return SimpleNamespace(code=code, provider=provider, points_count=points)


def test_several_population_sources_pick_the_european_series_first(monkeypatch):
    monkeypatch.setattr(world, "national_codes_for_concept", lambda slug: set())
    monkeypatch.setattr(world, "concept_for_indicator", lambda ind: world.CONCEPT_BY_SLUG["population"])
    country = SimpleNamespace(code="DE")
    imf = _ind("de-weo-lp", "imf", 80)
    eurostat = _ind("de-demo-pjan", "eurostat", 60)
    assert world._population_indicator(country, [imf, eurostat]) is eurostat
    assert world._population_indicator(country, [imf]) is imf


def test_no_population_source_gives_none(monkeypatch):
    monkeypatch.setattr(world, "national_codes_for_concept", lambda slug: set())
    monkeypatch.setattr(world, "concept_for_indicator", lambda ind: None)
    assert world._population_indicator(SimpleNamespace(code="DE"), [_ind("x", "imf", 1)]) is None
