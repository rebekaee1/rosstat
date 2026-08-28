"""Unit-тесты J6-подписей OG-постеров: единый контекст подписей, пилюля
годовой инфляции, годовое сравнение, EN-словарь итогов года. Без БД."""

from datetime import date

from app.api.sitemap import (
    _annual_summary_label_en,
    _inflation_pill,
    _og_annual_compare,
    _og_context,
    _og_monthly_subtitle,
    _og_weekly_subtitle,
)


def _monthly_rows(count, raw=106.0, start=date(2024, 9, 1)):
    """Ряд (значение CPI-индекса, дата) по возрастанию месяцев."""
    rows = []
    year, month = start.year, start.month
    for _ in range(count):
        rows.append((raw, date(year, month, 1)))
        month += 1
        if month == 13:
            year, month = year + 1, 1
    return rows


def _annual_pct_from_rows(rows):
    """Независимый пересчёт цепной годовой инфляции из последних 12 точек."""
    growth = 1.0
    for raw, _ in rows[-12:]:
        growth *= float(raw) / 100.0
    return (growth - 1.0) * 100.0


def test_cpi_full_window_monthly():
    rows = _monthly_rows(24)
    ctx = _og_context(
        "cpi", rows, unit="%", frequency="monthly",
        current_date=rows[-1][1], locale="ru",
    )
    assert ctx["subtitle"] == _og_monthly_subtitle("ru")
    assert "изменение за месяц" in ctx["subtitle"]

    expected = _annual_pct_from_rows(rows)  # для raw=106 это около 101%
    assert 100 < expected < 102  # 1.06^12 − 1, а не 106%
    assert ctx["context_pill"] == (
        f"Годовая инфляция \u2014 {expected:.1f}".replace(".", ",") + "%"
    )

    period = ctx["period_text"]
    assert period[0].isupper()
    assert "2026" in period
    assert ctx["unit_suffix"] == "%"


def test_cpi_full_window_weekly_subtitle():
    rows = _monthly_rows(14)
    ctx = _og_context(
        "cpi", rows, unit="%", frequency="weekly",
        current_date=rows[-1][1], locale="ru",
    )
    assert ctx["subtitle"] == _og_weekly_subtitle("ru")
    assert "за неделю" in ctx["subtitle"]
    assert ctx["context_pill"] is not None
    assert ctx["unit_suffix"] == "%"


def test_cpi_full_window_en_strings():
    rows = _monthly_rows(24)
    ctx = _og_context(
        "cpi", rows, unit="%", frequency="monthly",
        current_date=rows[-1][1], locale="en",
    )
    assert ctx["subtitle"] == _og_monthly_subtitle("en")
    assert "monthly change" in ctx["subtitle"]
    assert ctx["subtitle"].startswith("consumer price index")

    expected = _annual_pct_from_rows(rows)
    assert ctx["context_pill"].startswith("Annual inflation")
    assert ctx["context_pill"] == f"Annual inflation \u2014 {expected:.1f}%"

    # Фикс J6-согласованности: period_text следует локали — EN-постер
    # получает EN-месяц, RU — русский.
    assert ctx["period_text"] == "August 2026"
    assert ctx["unit_suffix"] == "%"


def test_non_cpi_row_no_pill():
    rows = _monthly_rows(20, raw=5000.0)
    ctx = _og_context(
        "gdp-nominal", rows, unit="млрд руб.", frequency="quarterly",
        current_date=date(2026, 7, 10), locale="ru",
    )
    assert ctx["context_pill"] is None
    assert ctx["subtitle"] is None
    assert ctx["unit_suffix"] is None
    assert ctx["period_text"][0].isupper()
    assert "2026" in ctx["period_text"]


def test_gdp_yoy_row_gets_no_inflation_pill():
    """Фактическое поведение: gdp-yoy не входит в CPI_INDEX_CODES, поэтому
    пилюли нет даже при полном окне — ряд сам является годовой метрикой,
    а отдельная логика для него в _og_context не заведена."""
    rows = [(2.3, d) for _, d in _monthly_rows(13)]
    ctx = _og_context(
        "gdp-yoy", rows, unit="%", frequency="monthly",
        current_date=date(2026, 8, 1), locale="ru",
    )
    assert ctx["context_pill"] is None
    assert ctx["subtitle"] is None
    assert ctx["unit_suffix"] == "%"
    assert ctx["period_text"] is not None


def test_cpi_short_window_no_pill():
    rows = _monthly_rows(12)  # меньше 13 точек — честную инфляцию не посчитать
    ctx = _og_context(
        "cpi", rows, unit="%", frequency="monthly",
        current_date=date(2026, 8, 5), locale="ru",
    )
    assert ctx["context_pill"] is None
    assert ctx["subtitle"] is None
    assert ctx["period_text"][0].isupper()
    assert "2026" in ctx["period_text"]

    # CPI-ряд даёт суффикс «%» даже с пустым unit: срезы корзины хранят индекс
    ctx_slice = _og_context(
        "cpi-food", rows, unit="", frequency="monthly",
        current_date=date(2026, 8, 5), locale="ru",
    )
    assert ctx_slice["unit_suffix"] == "%"


def test_og_annual_compare_locales_and_none_base():
    out_ru = _og_annual_compare(2026, 100.0, 106.0, locale="ru")
    assert out_ru.startswith("к 2025 году")
    assert out_ru.endswith("+6 %")

    out_en = _og_annual_compare(2026, 100.0, 106.0, locale="en")
    assert out_en == "vs 2025: +6.0%"

    # отрицательное сравнение: типографский минус приходит из format_number_ru
    out_neg = _og_annual_compare(2026, 200.0, 190.0, locale="ru")
    assert out_neg.endswith("\u22125 %")

    assert _og_annual_compare(2026, None, 106.0, locale="ru") is None
    assert _og_annual_compare(2026, 0.0, 106.0, locale="ru") is None  # база 0 — не делим
    assert _og_annual_compare(2026, 100.0, None, locale="en") is None


def test_annual_summary_label_en_known_and_passthrough():
    assert _annual_summary_label_en("Рост цен за год") == "Price growth over the year"
    assert _annual_summary_label_en("Итог за год (сумма)") == "Year total"
    assert _annual_summary_label_en("Значение на конец года") == "End-of-year value"
    assert _annual_summary_label_en("Среднее за год") == "Yearly average"
    # неизвестная подпись проходит насквозь без искажения
    assert _annual_summary_label_en("Итог за полугодие") == "Итог за полугодие"


def test_inflation_pill_sign_and_precision():
    assert _inflation_pill(6.02, locale="ru") == "Годовая инфляция \u2014 6,0%"
    assert _inflation_pill(6.02, locale="en") == "Annual inflation \u2014 6.0%"

    # Дефляция — с типографским минусом U+2212 в обеих локалях (fmt_yoy).
    assert _inflation_pill(-2.34, locale="ru") == "Годовая инфляция \u2014 \u22122,3%"
    assert _inflation_pill(-2.34, locale="en") == "Annual inflation \u2014 \u22122.3%"
