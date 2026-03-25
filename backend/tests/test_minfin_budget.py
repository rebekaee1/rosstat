"""Tests for MinfinBudgetParser CSV parsing."""

from app.services.minfin_budget_parser import _parse_budget_csv


SAMPLE_CSV = """\
\ufeffГод,Месяц,"Доходы, всего",Нефтегазовые доходы,"Расходы, всего","Дефицит (-)/Профицит (+)"
2024,январь,2500.0,800.0,3000.0,-500.0
2024,февраль,5200.0,1700.0,5800.0,-600.0
2024,март,8100.0,2600.0,8000.0,100.0
2025,январь,2600.0,900.0,3200.0,-600.0
"""


def test_parse_budget_csv_monthly_values():
    points = _parse_budget_csv(SAMPLE_CSV)
    assert len(points) == 4

    jan24 = points[0]
    assert jan24.date.year == 2024 and jan24.date.month == 1
    assert jan24.value == -500.0

    feb24 = points[1]
    assert feb24.date.year == 2024 and feb24.date.month == 2
    assert feb24.value == -100.0  # -600 - (-500)

    mar24 = points[2]
    assert mar24.date.year == 2024 and mar24.date.month == 3
    assert mar24.value == 700.0  # 100 - (-600)

    jan25 = points[3]
    assert jan25.date.year == 2025 and jan25.date.month == 1
    assert jan25.value == -600.0


def test_parse_budget_csv_empty():
    points = _parse_budget_csv("Год,Месяц\n")
    assert len(points) == 0


def test_parse_budget_csv_fallback_columns():
    csv_no_deficit = """\
\ufeffГод,Месяц,"Доходы, всего","Расходы, всего"
2024,январь,2500.0,3000.0
2024,февраль,5200.0,5800.0
"""
    points = _parse_budget_csv(csv_no_deficit)
    assert len(points) == 2
    assert points[0].value == -500.0
    assert points[1].value == -100.0
