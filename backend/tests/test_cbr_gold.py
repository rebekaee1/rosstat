"""Tests for CBR Gold (precious metals) XML parser."""

from datetime import date

from app.services.cbr_gold_parser import parse_gold_xml

SAMPLE_XML = """<?xml version="1.0" encoding="windows-1251"?>
<Metall FromDate="20260401" ToDate="20260403" name="Precious metals quotations">
  <Record Date="01.04.2026" Code="1"><Buy>11831,31</Buy><Sell>11831,31</Sell></Record>
  <Record Date="01.04.2026" Code="2"><Buy>184,82</Buy><Sell>184,82</Sell></Record>
  <Record Date="01.04.2026" Code="3"><Buy>5015,54</Buy><Sell>5015,54</Sell></Record>
  <Record Date="01.04.2026" Code="4"><Buy>3735,53</Buy><Sell>3735,53</Sell></Record>
  <Record Date="02.04.2026" Code="1"><Buy>11945,30</Buy><Sell>11945,30</Sell></Record>
  <Record Date="02.04.2026" Code="2"><Buy>186,50</Buy><Sell>186,50</Sell></Record>
  <Record Date="03.04.2026" Code="1"><Buy>12100,00</Buy><Sell>12100,00</Sell></Record>
</Metall>"""


class TestParseGoldXml:
    def test_gold(self):
        result = parse_gold_xml(SAMPLE_XML, "1")
        assert len(result) == 3
        assert result[0] == (date(2026, 4, 1), 11831.31)
        assert result[1] == (date(2026, 4, 2), 11945.3)
        assert result[2] == (date(2026, 4, 3), 12100.0)

    def test_silver(self):
        result = parse_gold_xml(SAMPLE_XML, "2")
        assert len(result) == 2
        assert result[0] == (date(2026, 4, 1), 184.82)
        assert result[1] == (date(2026, 4, 2), 186.5)

    def test_platinum(self):
        result = parse_gold_xml(SAMPLE_XML, "3")
        assert len(result) == 1
        assert result[0] == (date(2026, 4, 1), 5015.54)

    def test_palladium(self):
        result = parse_gold_xml(SAMPLE_XML, "4")
        assert len(result) == 1
        assert result[0] == (date(2026, 4, 1), 3735.53)

    def test_empty(self):
        xml = '<?xml version="1.0"?><Metall></Metall>'
        assert parse_gold_xml(xml, "1") == []

    def test_sorted_output(self):
        result = parse_gold_xml(SAMPLE_XML, "1")
        dates = [r[0] for r in result]
        assert dates == sorted(dates)
