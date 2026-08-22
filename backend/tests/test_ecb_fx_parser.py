"""Чистый разбор CSV ЕЦБ EXR — без сети."""

from datetime import date

from app.services.ecb_fx_parser import EcbFxParser, _parse_exr_csv

_CSV = """KEY,FREQ,CURRENCY,TIME_PERIOD,OBS_VALUE
EXR.D.USD.EUR.SP00.A,D,USD,1999-01-04,1.1789
EXR.D.USD.EUR.SP00.A,D,USD,2026-08-20,1.1650
EXR.D.USD.EUR.SP00.A,D,USD,2026-08-21,1.1699
EXR.D.USD.EUR.SP00.A,D,USD,2026-08-22,
"""


def test_parse_exr_skips_empty_and_honours_backfill():
    points = _parse_exr_csv(_CSV, backfill_from=date(2026, 8, 21))
    assert points == [(date(2026, 8, 21), 1.1699)]


def test_parse_exr_empty_without_time_period():
    assert _parse_exr_csv("FOO,BAR\n1,2\n") == []


def test_parser_type():
    assert EcbFxParser.parser_type == "ecb_fx"
    assert EcbFxParser.replace_series is True
