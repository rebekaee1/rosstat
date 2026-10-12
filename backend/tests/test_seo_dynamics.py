"""Фраза «Динамика» в SSR-карточке показателя страны."""
from datetime import date

from app.services.display import format_number_ru
from app.services.seo_dynamics import dynamics_note


def _fmt(value):
    return format_number_ru(value)


def _label(d):
    return d.strftime("%Y-%m")


def _monthly(values, start=date(2025, 1, 1)):
    out = []
    for index, value in enumerate(values):
        month = start.month - 1 + index
        out.append((date(start.year + month // 12, month % 12 + 1, 1), float(value)))
    return out


def test_percent_unit_uses_points_and_year_ago_and_extremes():
    series = _monthly([2.0, 2.5, 3.0, 3.2, 3.1, 3.4, 3.0, 2.9, 2.8, 2.6, 2.7, 2.9, 3.7])
    text = dynamics_note(series, "monthly", unit="%", unit_sfx=" %", fmt=_fmt, label=_label)
    assert text.startswith("Динамика: к предыдущему периоду (2025-12, 2,9 %) — выше на 0,8 п.п.")
    assert "к тому же периоду годом ранее (2025-01, 2 %) — выше на 1,7 п.п." in text
    assert "минимум — 2 % (2025-01), максимум — 3,7 % (2026-01)" in text


def test_level_unit_uses_relative_change():
    series = _monthly([100, 110, 121])
    text = dynamics_note(series, "monthly", unit="млн евро", unit_sfx=" млн евро", fmt=_fmt, label=_label)
    assert "(2025-02, 110 млн евро) — выше на 10 %" in text
    assert "годом ранее" not in text


def test_annual_series_has_no_duplicate_year_ago_clause():
    series = [(date(2021 + i, 1, 1), float(v)) for i, v in enumerate([5, 4, 6, 3, 7])]
    text = dynamics_note(series, "annual", unit="%", unit_sfx=" %", fmt=_fmt, label=lambda d: str(d.year))
    assert text.count("—") >= 1
    assert "годом ранее" not in text
    assert "минимум — 3 % (2024), максимум — 7 % (2025)" in text


def test_english_and_unchanged_and_short_series():
    series = _monthly([4, 4, 4])
    text = dynamics_note(series, "monthly", unit="%", unit_sfx=" %", fmt=_fmt, label=_label, en=True)
    assert text == "Change: versus the previous period (2025-02, 4 %) — unchanged."
    assert dynamics_note(_monthly([1, 2]), "monthly", unit="%", fmt=_fmt, label=_label) == ""


def test_zero_base_and_absurd_growth_are_skipped():
    series = _monthly([0, 0, 5])
    assert dynamics_note(series, "monthly", unit="шт.", fmt=_fmt, label=_label) == ""
    # рост в сотни раз на единичной базе не публикуем как «динамику»
    assert dynamics_note(_monthly([5000, 1, 5000]), "monthly", unit="шт.", fmt=_fmt, label=_label) == ""
