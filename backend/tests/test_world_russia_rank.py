"""Россия в межстрановом рейтинге: единица и источник совпадают с карточкой."""

from __future__ import annotations

from datetime import date

import pytest

from app.data.world_concept_russia import RUSSIA_CONCEPT_LINKS, russia_link_for_concept
from app.services.world_rank_values import (
    world_rating_title,
    yearly_last_points,
)
from app.services.world_russia_rank import (
    _rank_mode_for_link,
    _scaled_series,
    russia_meta_for_concept,
)


def test_russia_links_cover_comparable_rating_concepts_only():
    assert set(RUSSIA_CONCEPT_LINKS) == {
        "unemployment-rate",
        "hicp-index",
        "population",
    }
    assert russia_link_for_concept("budget-balance-gdp") is None
    assert russia_link_for_concept("activity-rate") is None
    assert russia_link_for_concept("long-term-interest-rate") is None


def test_hicp_uses_cpi_yoy_without_second_yoy():
    link = russia_link_for_concept("hicp-index")
    assert link.indicator_code == "cpi-yoy"
    assert link.value_kind == "yoy_ready"
    assert _rank_mode_for_link(link, "yoy") == "level"


def test_population_scales_millions_to_persons():
    link = russia_link_for_concept("population")
    series = [(date(2025, 1, 1), 146.12)]
    scaled = _scaled_series(series, link)
    assert scaled[0][1] == pytest.approx(146_120_000.0)


def test_russia_notes_are_public_language():
    for slug, link in RUSSIA_CONCEPT_LINKS.items():
        meta = russia_meta_for_concept(slug)
        assert meta["eligible"] is True
        assert "парсер" not in link.note_ru.lower()
        assert "ADR" not in link.note_ru
        assert meta["note"] == link.note_ru
        assert (link.note_en or "").strip()
        assert "парсер" not in link.note_en.lower()
        assert "ADR" not in link.note_en


def test_russia_notes_en_locale():
    from app.services.locale import reset_locale, set_locale

    token = set_locale("en")
    try:
        for slug, link in RUSSIA_CONCEPT_LINKS.items():
            meta = russia_meta_for_concept(slug)
            assert meta["note"] == link.note_en
            assert "Росстат" not in meta["note"]
            assert not meta["note"].startswith("Для России")
            assert meta["country"]["name"] == "Russia"
    finally:
        reset_locale(token)


def test_world_rating_title_matches_ssr_contract():
    assert world_rating_title("unemployment-rate", "Уровень безработицы", 2026) == (
        "Рейтинг стран по уровню безработицы за 2026 год"
    )
    assert world_rating_title(
        "hicp-index",
        "Изменение потребительских цен за год",
        2025,
    ) == "Рейтинг стран по изменению потребительских цен за год, 2025"


@pytest.mark.parametrize(
    ("slug", "series", "concept_mode", "expected_year", "expected_value"),
    [
        (
            "hicp-index",
            # cpi-yoy уже YoY % — в рейтинг как level, без второго YoY.
            [
                (date(2025, 11, 1), 5.4),
                (date(2025, 12, 1), 5.6),
                (date(2026, 7, 1), 6.0),
            ],
            "yoy",
            2025,
            5.6,
        ),
        (
            "population",
            [(date(2025, 1, 1), 146.12)],
            "level",
            2025,
            146_120_000.0,
        ),
        (
            "unemployment-rate",
            [(date(2026, 5, 1), 2.3), (date(2026, 6, 1), 2.2)],
            "level",
            2026,
            2.2,
        ),
    ],
)
def test_russia_rank_value_equals_scaled_card_series(
    slug, series, concept_mode, expected_year, expected_value
):
    """Инвариант: значение РФ в годовом срезе = последний пункт ряда × scale."""
    link = russia_link_for_concept(slug)
    assert link is not None
    scaled = _scaled_series(series, link)
    mode = _rank_mode_for_link(link, concept_mode)
    by_year = yearly_last_points(scaled, mode)
    assert expected_year in by_year
    assert by_year[expected_year][1] == pytest.approx(expected_value)
    # Последняя точка всего ряда (как на карточке «текущее») после scale.
    assert scaled[-1][1] == pytest.approx(
        series[-1][1] * link.scale
    )


def test_world_rating_title_stable_across_years_and_concepts():
    """SSR и клиент строят один и тот же шаблон заголовка."""
    assert world_rating_title("population", "Численность населения", 2025) == (
        "Рейтинг стран по численности населения за 2025 год"
    )
    assert world_rating_title("activity-rate", "Уровень экономической активности", None) == (
        "Рейтинг стран по уровню экономической активности"
    )
