"""Парсер ключевой ставки ЦБ (официальный HTML)."""

from datetime import date

import pytest

from app.services.cbr_keyrate import assert_keyrate_response_plausible, parse_keyrate_html


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
