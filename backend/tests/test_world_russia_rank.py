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
        "gdp-usd",
        "gdp-per-capita-usd",
        "budget-balance-gdp",
    }
    assert russia_link_for_concept("government-debt-gdp") is None
    assert russia_link_for_concept("activity-rate") is None
    assert russia_link_for_concept("long-term-interest-rate") is None
    assert russia_link_for_concept("gdp-nominal") is None
    assert RUSSIA_CONCEPT_LINKS["gdp-usd"].indicator_code == "weo-gdp-usd"
    assert RUSSIA_CONCEPT_LINKS["gdp-per-capita-usd"].indicator_code == (
        "weo-gdp-per-capita-usd"
    )
    balance = RUSSIA_CONCEPT_LINKS["budget-balance-gdp"]
    assert balance.indicator_code == "weo-budget-balance-gdp"
    assert balance.source_ru == "Международный валютный фонд"
    assert "Минфина" in balance.note_ru
    assert "Ministry of Finance" in balance.note_en
    assert "budget-deficit" not in {
        link.indicator_code for link in RUSSIA_CONCEPT_LINKS.values()
    }
    assert "gdp-nominal" not in {
        link.indicator_code for link in RUSSIA_CONCEPT_LINKS.values()
    }


def test_weo_gdp_overlay_links_kept_but_ranking_is_national():
    """МВФ-ряды остаются связанными карточками; рейтинг gdp-usd — национальный.

    Значение России в рейтинге gdp-usd/gdp-per-capita-usd считает
    world_russia_rank по национальным рядам (Росстат × курс Банка России),
    link-механизм для этих концептов — резерв.
    """
    link = russia_link_for_concept("gdp-usd")
    assert link.indicator_code == "weo-gdp-usd"
    assert "gdp-nominal" not in link.indicator_code
    assert russia_link_for_concept("budget-deficit") is None
    balance = russia_link_for_concept("budget-balance-gdp")
    assert balance.source_ru == "Международный валютный фонд"
    assert balance.source_en == "International Monetary Fund"
    # Оверлей — ряд МВФ, а не российский бюджетный поток Минфина.
    assert balance.indicator_code == "weo-budget-balance-gdp"


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
            # EN-текст без необработанных русских вставок; имена ведомств
            # (Rosstat) — допустимая латынь.
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
    assert world_rating_title(
        "activity-rate",
        "Уровень экономической активности населения",
        None,
    ) == "Рейтинг стран по уровню экономической активности населения"


# --- национальный расчёт ВВП России (Росстат × курс Банка России) -----------


def test_gdp_usd_by_year_from_parts_national_calculation():
    """Чистый расчёт: млрд руб. / курс = млрд $; на душу — с населением."""
    from app.services.world_russia_rank import gdp_usd_by_year_from_parts

    gdp_rub = {2023: 171_505.0, 2024: 200_039.0, 2025: 214_261.1}
    usd_rub = {2023: 85.8116, 2024: 92.6567, 2025: 83.2108}
    population_mln = {2023: 146.45, 2024: 146.15, 2025: 146.12}

    gdp_usd, per_capita = gdp_usd_by_year_from_parts(
        gdp_rub, usd_rub, population_mln,
    )
    assert gdp_usd[2023] == pytest.approx(171_505.0 / 85.8116, rel=1e-4)
    assert gdp_usd[2024] == pytest.approx(200_039.0 / 92.6567, rel=1e-4)
    assert gdp_usd[2025] == pytest.approx(214_261.1 / 83.2108, rel=1e-4)
    assert per_capita[2024] == pytest.approx(
        gdp_usd[2024] * 1e9 / (146.15 * 1e6), rel=1e-3,
    )
    # Порядок величины: ~15 тыс. $ на человека для 2024.
    assert 13_000 < per_capita[2024] < 17_000
    # На душу считаются только годы со всеми тремя рядами; ВВП-USD при
    # отсутствии населения считается (год закрыт, курс есть).
    past_year = date.today().year - 1
    gdp_only, pc_empty = gdp_usd_by_year_from_parts(
        {past_year: 100.0}, {past_year: 90.0}, {},
    )
    assert past_year in gdp_only
    assert pc_empty == {}


def test_gdp_usd_method_excludes_running_year():
    """Только завершённые годы: незакрывшийся год в расчёт не попадает."""
    from app.services.world_russia_rank import gdp_usd_by_year_from_parts

    running_year = date.today().year
    gdp_usd, _per_capita = gdp_usd_by_year_from_parts(
        {running_year: 100.0, running_year - 1: 90.0},
        {running_year: 90.0, running_year - 1: 90.0},
        {},
    )
    assert running_year not in gdp_usd
    assert running_year - 1 in gdp_usd


def test_gdp_usd_concept_links_note_national_method():
    """Публичная примеча к рейтингу описывает национальный расчёт, не МВФ."""
    for slug in ("gdp-usd", "gdp-per-capita-usd"):
        link = russia_link_for_concept(slug)
        assert link is not None
        assert link.source_ru == "Росстат, Банк России"
        assert link.source_en == "Rosstat, Bank of Russia"
        assert "Росстата" in link.note_ru
        assert "Банка России" in link.note_ru
        assert "Rosstat" in link.note_en
        assert "Bank of Russia" in link.note_en
        # Внутренности в публичном тексте запрещены.
        assert "usd-rub-avg-year" not in link.note_ru
        assert "gdp-nominal" not in link.note_ru
        assert "WEO" not in link.note_ru
