"""Tests for MinfinBudgetParser CSV parsing."""

from app.services.minfin_budget_parser import (
    MinfinBudgetParser,
    _parse_budget_csv,
    fetch_and_parse_budget,
)


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


def test_parse_budget_csv_skips_gap_months():
    """Пропуск месяца в накопленном CSV не должен списываться в один «месяц».

    Mar+Apr отсутствуют, есть Jan, Feb и May. May нельзя разложить в помесячное
    (cum[May]−cum[Feb] = Mar+Apr+May), поэтому точка May пропускается, а не
    превращается в ложный трёхмесячный «месяц».
    """
    csv_with_gap = """\
\ufeffГод,Месяц,"Доходы, всего",Нефтегазовые доходы,"Расходы, всего","Дефицит (-)/Профицит (+)"
2026,январь,2500.0,800.0,3000.0,-500.0
2026,февраль,5200.0,1700.0,5800.0,-600.0
2026,май,12000.0,3000.0,18000.0,-6000.0
"""
    points = _parse_budget_csv(csv_with_gap)
    months = [(p.date.month, p.value) for p in points]
    assert months == [(1, -500.0), (2, -100.0)]
    assert all(p.date.month != 5 for p in points), "месяц после пропуска не должен попадать в ряд"


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


def test_fetch_and_parse_budget_does_not_augment_from_press():
    """OpenData CSV-only: май после пропуска мар–апр не попадает в ряд."""
    points, _ = fetch_and_parse_budget("revenue")
    for p in points:
        assert p.value < 9000.0, (
            f"подозрительно большое помесячное значение {p.value} на {p.date}"
        )


def test_minfin_parser_replace_series_flag():
    assert MinfinBudgetParser.replace_series is True


def test_parse_budget_csv_revenue_target():
    csv = """\
\ufeffГод,Месяц,"Доходы, всего","Расходы, всего","Дефицит (-)/Профицит (+)"
2026,январь,2364.3,3993.3,-1628.9
2026,февраль,4767.4,8216.2,-3448.8
"""
    points = _parse_budget_csv(csv, target="revenue")
    assert [(p.date.month, p.value) for p in points] == [
        (1, 2364.3),
        (2, 2403.1),
    ]
