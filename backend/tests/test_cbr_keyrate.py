"""Парсер ключевой ставки ЦБ (официальный HTML)."""

from datetime import date

import pytest

from app.services.cbr_keyrate import (
    _next_business_day,
    assert_keyrate_response_plausible,
    parse_keyrate_html,
    parse_keyrate_press_release,
)


SAMPLE_HTML = """
<html><body><table>
<tr><td>20.03.2026</td><td>15,50</td></tr>
<tr><td>19.03.2026</td><td>15,50</td></tr>
<tr><td>01.01.2020</td><td>6,25</td></tr>
</table></body></html>
"""


def test_parse_keyrate_html_extracts_sorted_unique_dates():
    pts = parse_keyrate_html(SAMPLE_HTML)
    assert len(pts) == 3
    assert pts[0].date == date(2020, 1, 1)
    assert pts[0].value == 6.25
    assert pts[-1].date == date(2026, 3, 20)
    assert pts[-1].value == 15.5


def test_parse_keyrate_html_duplicate_date_last_wins():
    html = """
    <tr><td>10.03.2026</td><td>10,00</td></tr>
    <tr><td>10.03.2026</td><td>11,00</td></tr>
    """
    pts = parse_keyrate_html(html)
    assert len(pts) == 1
    assert pts[0].value == 11.0


def test_parse_keyrate_html_empty_raises():
    with pytest.raises(ValueError, match="No key rate rows"):
        parse_keyrate_html("<html></html>")


def test_assert_keyrate_response_plausible_rejects_short_html():
    with pytest.raises(ValueError, match="слишком короткий"):
        assert_keyrate_response_plausible("<html>x</html>", "https://www.cbr.ru/hd_base/KeyRate/")


def test_assert_keyrate_response_plausible_accepts_typical_page():
    # Минимальная длина + маркеры разметки (как на реальной странице UniDbQuery)
    filler = "x" * 3000
    html = f"<html><body>UniDbQuery ключев{filler}</body></html>"
    assert_keyrate_response_plausible(html, "https://www.cbr.ru/hd_base/KeyRate/")


# --- Пресс-релиз СД -------------------------------------------------------------


def test_press_release_lower_decision():
    """Реальный шаблон пресс-релиза от 24.04.2026 — снижение до 14,50%, эффект с 27.04 (пн)."""
    html = (
        "<title>Банк России принял решение снизить ключевую ставку на 50 б.п., "
        "до 14,50% годовых</title>"
        "<p>Совет директоров Банка России 24&nbsp;апреля 2026&nbsp;года принял решение "
        "снизить ставку.</p>" + "x" * 800
    )
    ann = parse_keyrate_press_release(html)
    assert ann is not None
    assert ann.rate == 14.5
    assert ann.decision_date == date(2026, 4, 24)
    assert ann.effective_date == date(2026, 4, 27)


def test_press_release_hold_decision():
    """Решение «сохранить ставку на уровне X%» — следующий рабочий день после решения."""
    html = (
        "<title>Банк России принял решение сохранить ключевую ставку на уровне 16,00% годовых</title>"
        "<p>Совет директоров Банка России 27 октября 2025 года принял решение.</p>" + "x" * 800
    )
    ann = parse_keyrate_press_release(html)
    assert ann is not None
    assert ann.rate == 16.0
    assert ann.decision_date == date(2025, 10, 27)
    # 27.10.2025 = понедельник → след. рабочий 28.10.2025 (вторник).
    assert ann.effective_date == date(2025, 10, 28)


def test_press_release_short_html_returns_none():
    assert parse_keyrate_press_release("") is None
    assert parse_keyrate_press_release("<html>x</html>") is None


def test_press_release_unknown_format_returns_none():
    """Если регэксп не сматчился (изменили шаблон) — None, не падаем."""
    html = "<html>" + "x" * 1000 + "</html>"
    assert parse_keyrate_press_release(html) is None


def test_next_business_day_handles_friday_to_monday():
    # 24.04.2026 — пятница.
    assert _next_business_day(date(2026, 4, 24)) == date(2026, 4, 27)
    # 27.04.2026 — понедельник, сл. вторник.
    assert _next_business_day(date(2026, 4, 27)) == date(2026, 4, 28)
    # Суббота → понедельник.
    assert _next_business_day(date(2026, 4, 25)) == date(2026, 4, 27)
