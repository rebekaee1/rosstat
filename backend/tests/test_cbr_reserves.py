"""Tests for CBR International Reserves HTML parser."""

from datetime import date

from app.services.cbr_reserves_parser import parse_reserves_html

SAMPLE_HTML = """
<table class="data">
  <tr>
    <th>Дата</th><th>Значение, млрд. долл. США</th>
  </tr>
  <tr>
    <td>04.04.2026</td><td>625,5</td>
  </tr>
  <tr>
    <td>28.03.2026</td><td>624,3</td>
  </tr>
  <tr>
    <td>21.03.2026</td><td>622,1</td>
  </tr>
</table>
"""


class TestParseReservesHtml:
    def test_basic(self):
        result = parse_reserves_html(SAMPLE_HTML)
        assert len(result) == 3
        assert result[0] == (date(2026, 3, 21), 622.1)
        assert result[1] == (date(2026, 3, 28), 624.3)
        assert result[2] == (date(2026, 4, 4), 625.5)

    def test_empty_table(self):
        html = "<table><tr><th>Дата</th></tr></table>"
        assert parse_reserves_html(html) == []

    def test_comma_decimal(self):
        html = "<table><tr><td>01.01.2026</td><td>1 234,56</td></tr></table>"
        result = parse_reserves_html(html)
        assert len(result) == 1
        assert result[0][1] == 1234.56
