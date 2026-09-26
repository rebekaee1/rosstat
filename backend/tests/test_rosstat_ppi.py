"""Tests for Rosstat PPI parser (canonical русский Rosstat PDF).

Fixtures `tests/fixtures/rosstat_osn/osn-MM-2026_ppi.txt` — реальный pypdf-текст
из официальных докладов (строка summary-таблицы + начало подраздела «Индексы и
уровни цен производителей промышленных товаров»), включая разрывы слов pypdf
(«п ромышленных», «прои зводителей»).
"""

from datetime import date
from pathlib import Path

import pytest

from app.services.rosstat_ppi_parser import (
    PpiReading,
    chain_ppi_point,
    parse_ppi_mom_from_report,
    parse_ppi_reading_from_report,
    previous_month,
)

FIXTURES = Path(__file__).parent / "fixtures" / "rosstat_osn"


def _fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


# (файл, reference-месяц, MoM%, YoY% — первое число summary-строки, которое
# старый парсер ошибочно принимал за MoM)
OFFICIAL = [
    ("osn-02-2026_ppi.txt", date(2026, 2, 1), 100.5, 94.8),
    ("osn-03-2026_ppi.txt", date(2026, 3, 1), 102.0, 98.2),
    ("osn-04-2026_ppi.txt", date(2026, 4, 1), 106.1, 105.5),
    ("osn-05-2026_ppi.txt", date(2026, 5, 1), 102.5, 109.4),
    ("osn-06-2026_ppi.txt", date(2026, 6, 1), 99.9, 110.5),
    ("osn-07-2026_ppi.txt", date(2026, 7, 1), 97.5, 106.6),
]


@pytest.mark.parametrize("name,ref_month,mom,yoy", OFFICIAL)
def test_real_reports_give_mom_and_reference_month(name, ref_month, mom, yoy):
    reading = parse_ppi_reading_from_report(_fixture(name))
    assert reading == PpiReading(reference_month=ref_month, mom_pct=mom)
    # Регрессия 2026-09: первое число summary-строки — YoY, не MoM.
    assert reading.mom_pct != yoy


def test_june_and_july_2026_values():
    assert parse_ppi_mom_from_report(_fixture("osn-06-2026_ppi.txt")) == 99.9
    assert parse_ppi_mom_from_report(_fixture("osn-07-2026_ppi.txt")) == 97.5


def test_reference_month_comes_from_text_not_url():
    """osn-07-2026.pdf описывает ИЮЛЬ (раньше URL-конвенция давала июнь)."""
    reading = parse_ppi_reading_from_report(_fixture("osn-07-2026_ppi.txt"))
    assert reading.reference_month == date(2026, 7, 1)


def test_summary_row_alone_is_not_parsed():
    text = "Индекс цен производителей промышленных товаров  106,6 97,5 102,8 99,7"
    assert parse_ppi_reading_from_report(text) is None


def test_split_words_and_hyphenation():
    text = (
        "Индекс цен произво-\nдителей п ромышленных товаров  в декабре 202 5 г.\n"
        "относительно предыдущего месяца, по предварительным данным, "
        "составил 98,4 %, из него"
    )
    assert parse_ppi_reading_from_report(text) == PpiReading(date(2025, 12, 1), 98.4)


def test_no_match_returns_none():
    assert parse_ppi_reading_from_report("nothing relevant here") is None


def test_value_out_of_range_filtered():
    text = (
        "Индекс цен производителей промышленных товаров в июле 2026 г. "
        "относительно предыдущего месяца составил 500,0%"
    )
    assert parse_ppi_reading_from_report(text) is None


def test_previous_month_wraps_year():
    assert previous_month(date(2026, 1, 1)) == date(2025, 12, 1)
    assert previous_month(date(2026, 7, 1)) == date(2026, 6, 1)


def test_chain_rebuilds_2026_series_consistently_with_official_yoy():
    """Цепочка Feb..Jul от январского уровня совпадает с официальным YoY ±0.2 п.п."""
    value = 303.7  # 2026-01 (SDDS seed, не затронут старым багом)
    chained = {}
    for name, ref_month, _mom, _yoy in OFFICIAL:
        point = chain_ppi_point(value, parse_ppi_reading_from_report(_fixture(name)))
        assert point.date == ref_month
        chained[ref_month] = value = point.value
    assert chained[date(2026, 7, 1)] == pytest.approx(329.78, abs=0.02)
    # 2025-06 = 306.2, 2025-07 = 308.9 (история в БД); официальный YoY 110,5 / 106,6.
    assert chained[date(2026, 6, 1)] / 306.2 * 100 == pytest.approx(110.5, abs=0.2)
    assert chained[date(2026, 7, 1)] / 308.9 * 100 == pytest.approx(106.6, abs=0.2)
