"""Tests for CbrRuoniaParser HTML parsing (transposed table)."""

from datetime import date
from app.services.cbr_ruonia_parser import parse_ruonia_html

SAMPLE_HTML = """
<html><body>
<table>
<tr><td>Дата ставки</td><td>01.03.2024</td><td>04.03.2024</td><td>05.03.2024</td></tr>
<tr><td>Ставка RUONIA, % годовых</td><td>15,34</td><td>15,28</td><td>15,12</td></tr>
<tr><td>Объем сделок RUONIA, млрд руб.</td><td>500,00</td><td>480,00</td><td>490,00</td></tr>
</table>
</body></html>
"""


def test_parse_ruonia_html_basic():
    points = parse_ruonia_html(SAMPLE_HTML)
    assert len(points) == 3
    assert points[0] == (date(2024, 3, 1), 15.34)
    assert points[1] == (date(2024, 3, 4), 15.28)
    assert points[2] == (date(2024, 3, 5), 15.12)


def test_parse_ruonia_html_sorted():
    points = parse_ruonia_html(SAMPLE_HTML)
    dates = [p[0] for p in points]
    assert dates == sorted(dates)


def test_parse_ruonia_html_empty():
    html = "<html><body><p>No data</p></body></html>"
    assert parse_ruonia_html(html) == []


def test_parse_ruonia_html_dedup():
    html = """
    <table>
    <tr><td>Дата</td><td>01.03.2024</td><td>01.03.2024</td></tr>
    <tr><td>Ставка</td><td>15,00</td><td>15,50</td></tr>
    </table>
    """
    points = parse_ruonia_html(html)
    assert len(points) == 1
    assert points[0][1] == 15.5
