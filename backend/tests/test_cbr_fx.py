"""Tests for CbrFxParser XML parsing."""

import pytest
from datetime import date
from app.services.cbr_fx_parser import parse_fx_xml

SAMPLE_XML = """<?xml version="1.0" encoding="windows-1251"?>
<ValCurs ID="R01235" DateRange1="01.01.2024" DateRange2="05.01.2024" name="Foreign Currency Market Dynamic">
    <Record Date="02.01.2024" Id="R01235">
        <Nominal>1</Nominal>
        <Value>89,6883</Value>
    </Record>
    <Record Date="03.01.2024" Id="R01235">
        <Nominal>1</Nominal>
        <Value>90,1234</Value>
    </Record>
    <Record Date="04.01.2024" Id="R01235">
        <Nominal>1</Nominal>
        <Value>91,0000</Value>
    </Record>
</ValCurs>"""


def test_parse_fx_xml_basic():
    points = parse_fx_xml(SAMPLE_XML)
    assert len(points) == 3
    assert points[0] == (date(2024, 1, 2), 89.6883)
    assert points[1] == (date(2024, 1, 3), 90.1234)
    assert points[2] == (date(2024, 1, 4), 91.0)


def test_parse_fx_xml_sorted():
    points = parse_fx_xml(SAMPLE_XML)
    dates = [p[0] for p in points]
    assert dates == sorted(dates)


CNY_XML = """<?xml version="1.0" encoding="windows-1251"?>
<ValCurs ID="R01375" DateRange1="01.03.2024" DateRange2="01.03.2024" name="Foreign Currency Market Dynamic">
    <Record Date="01.03.2024" Id="R01375">
        <Nominal>10</Nominal>
        <Value>124,5670</Value>
    </Record>
</ValCurs>"""


def test_parse_fx_xml_cny_nominal():
    points = parse_fx_xml(CNY_XML)
    assert len(points) == 1
    assert points[0][1] == round(124.567 / 10, 4)


def test_parse_fx_xml_empty():
    xml = '<?xml version="1.0"?><ValCurs></ValCurs>'
    assert parse_fx_xml(xml) == []
