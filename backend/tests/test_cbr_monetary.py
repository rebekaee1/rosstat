"""Tests for CbrMonetaryParser HTML parsing."""

from datetime import date
from app.services.cbr_monetary_parser import parse_mb_html

SAMPLE_HTML = """
<html><body>
<table>
<tr><td>01.01.2024</td><td>17 624,3</td><td>99 500,1</td><td>5 200,0</td></tr>
<tr><td>01.02.2024</td><td>16 890,7</td><td>100 210,5</td><td>5 100,0</td></tr>
<tr><td>01.03.2024</td><td>17 100,0</td><td>101 300,0</td><td>5 300,0</td></tr>
</table>
</body></html>
"""


def test_parse_mb_html_basic():
    rows = parse_mb_html(SAMPLE_HTML)
    assert len(rows) == 3
    assert rows[0] == (date(2024, 1, 1), 17624.3, 99500.1, 5200.0)
    assert rows[1] == (date(2024, 2, 1), 16890.7, 100210.5, 5100.0)


def test_parse_mb_html_sorted():
    rows = parse_mb_html(SAMPLE_HTML)
    dates = [r[0] for r in rows]
    assert dates == sorted(dates)


def test_parse_mb_html_empty():
    html = "<html><body></body></html>"
    assert parse_mb_html(html) == []
