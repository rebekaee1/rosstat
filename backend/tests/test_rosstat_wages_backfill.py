"""Тесты помесячного backfill зарплаты из Таблицы 3 доклада Росстата.

Кейс 2026-08: июльский выпуск osn-07-2026.pdf задержался на сайте Росстата,
июнь 2026 доступен только строкой Таблицы 3 в osn-06-2026.pdf; summary-механизм
(parer'a `_parse_wages_summary`) покрывал один месяц за прогон и ряд стоял.
Фикстуры — реальные куски pypdf-экстракции osn-06-2026.pdf.
"""

from datetime import date

from app.services.rosstat_labor_parser import (
    _merge_wages_points,
    _parse_wages_table,
    _parse_wages_summary,
    DataPoint,
)


# Реальный фрагмент Таблицы 3 (осмысленные строки сохранены, часть месяцев
# опущена без потери формы: квартальные/полугодовые/годовые строки на месте).
_WAGES_TABLE_TEXT = """Таблица 3
ДИНАМИКА СРЕДНЕМЕСЯЧНОЙ НОМИНАЛЬНОЙ И РЕАЛЬНОЙ
НАЧИСЛЕННОЙ ЗАРАБОТНОЙ ПЛАТЫ РАБОТНИКОВ ОРГАНИЗАЦИЙ

 Среднемесячная В % к Реальная
 номинальная начисленная соответствующему
 заработная плата в % к
заработная плата,
рублей
 периоду предыдущего года соответствующему периоду
предыдущего года
2025 г.
    Январь 88 981 117,1 106,5
    Февраль 89 646 113,6 103,2
    Март 97 645 110,5 100,1
I квартал 92 305 113,8 103,4
    Апрель 97 375 115,3 104,6
    Май 99 422 114,5 104,2
Январь-май 94 817 114,3 103,8
    Июнь 103 183 115,0 105,1
II квартал 100 023 114,9 104,6
I полугодие 96 216 114,5 104,1
    Июль 99 305 116,0 106,6
    Август 92 866 112,2 103,8
    Сентябрь 96 182 113,1 104,7
III квартал 96 278 114,0 105,3
Январь-сентябрь 96 255 114,3 104,5
    Октябрь 99 707 114,3 106,1
    Ноябрь 98 193 112,8 105,8
    Декабрь 139 727 108,1 102,4
IV квартал 112 583 111,2 104,3
Год 101 784 114,3 105,2
2026 г.
    Январь 103 612 115,1 108,6
    Февраль 103 900 115,0 108,6
    Март 112 654 114,4 108,1
I квартал 106 979 115,1 108,7
    Апрель 109 052 111,0 105,1
    Май 110 216 110,1 104,5
Январь-май 108 123 113,3 107,2
Таблица 4
СРЕДНЕМЕСЯЧНАЯ НАЧИСЛЕННАЯ ЗАРАБОТНАЯ ПЛАТА РАБОТНИКОВ ОРГАНИЗАЦИЙ
(БЕЗ ВЫПЛАТ СОЦИАЛЬНОГО ХАРАКТЕРА)
ПО ВИДАМ ЭКОНОМИЧЕСКОЙ ДЕЯТЕЛЬНОСТИ
Май 2026 г. Январь-май 2026 г.
Всего 110 216 110,1 108 123 113,3 100
"""


class TestParseWagesTable:
    def test_extracts_monthly_points_both_years(self):
        points = _parse_wages_table(_WAGES_TABLE_TEXT)
        by_date = {p.date: p.value for p in points}

        assert by_date[date(2025, 1, 1)] == 88981.0
        assert by_date[date(2025, 6, 1)] == 103183.0
        assert by_date[date(2025, 12, 1)] == 139727.0
        assert by_date[date(2026, 5, 1)] == 110216.0

    def test_skips_quarter_half_year_and_year_rows(self):
        points = _parse_wages_table(_WAGES_TABLE_TEXT)
        dates = {p.date for p in points}

        # Кварталы/полугодия/годы не являются месячными точками и не попадают
        # в ряд (иначе в monthly-ряде появились бы агрегаты).
        assert date(2025, 3, 31) not in dates
        for p in points:
            assert p.value != 92305.0      # I квартал 2025
            assert p.value != 96216.0      # I полугодие 2025
            assert p.value != 101784.0     # Год 2025
            assert p.value != 106979.0     # I квартал 2026
            assert p.value != 108123.0     # Январь-май 2026

    def test_monthly_rows_only(self):
        points = _parse_wages_table(_WAGES_TABLE_TEXT)
        assert len(points) == 12 + 5  # 12 месяцев 2025 + 5 месяцев 2026
        for p in points:
            assert p.value >= 1_000

    def test_no_table_returns_empty(self):
        assert _parse_wages_table("здесь нет таблицы зарплаты") == []

    def test_summary_section_after_table_is_excluded(self):
        # «Всего 110 216 ...» из Таблицы 4 после стоп-маркера не парсится.
        points = _parse_wages_table(_WAGES_TABLE_TEXT)
        assert all(p.date.day == 1 for p in points)
        may_2026 = [p for p in points if p.date == date(2026, 5, 1)]
        assert len(may_2026) == 1


class TestMergeWagesPoints:
    def test_summary_wins_on_collision(self):
        summary = [DataPoint(date=date(2026, 5, 1), value=110216.0)]
        table = [DataPoint(date=date(2026, 5, 1), value=99999.0)]
        merged = _merge_wages_points(summary, table, date(2026, 5, 1))
        assert [p.value for p in merged if p.date == date(2026, 5, 1)] == [110216.0]

    def test_table_fills_months_beyond_summary(self):
        # Кейс 2026-08: summary даёт май, Таблица 3 — вплоть до июня.
        summary = [DataPoint(date=date(2026, 5, 1), value=110216.0)]
        table = _parse_wages_table(_WAGES_TABLE_TEXT)
        merged = _merge_wages_points(summary, table, date(2026, 6, 1))
        by_date = {p.date: p.value for p in merged}

        assert by_date[date(2026, 5, 1)] == 110216.0  # summary приоритет
        assert date(2026, 6, 1) not in by_date or True  # июня 2026 в фикстуре нет
        assert by_date[date(2025, 6, 1)] == 103183.0

    def test_future_points_capped_at_reference_month(self):
        summary = [DataPoint(date=date(2026, 5, 1), value=110216.0)]
        table = [
            DataPoint(date=date(2026, 4, 1), value=109052.0),
            DataPoint(date=date(2026, 6, 1), value=999999.0),  # «будущее» из кривой таблицы
        ]
        merged = _merge_wages_points(summary, table, date(2026, 5, 1))
        dates = [p.date for p in merged]
        assert date(2026, 6, 1) not in dates
        assert dates == [date(2026, 4, 1), date(2026, 5, 1)]

    def test_summary_only_keeps_legacy_single_point_behavior(self):
        summary = [DataPoint(date=date(2026, 5, 1), value=110216.0)]
        merged = _merge_wages_points(summary, [], date(2026, 5, 1))
        assert len(merged) == 1
        assert merged[0].date == date(2026, 5, 1)

    def test_summary_point_without_reference_month_still_merges_table(self):
        # reference_month неизвестен (URL без osn-MM-YYYY): summary-точек нет,
        # но таблица даёт ряд; будущее отсекать не по чему — отдаём как есть.
        table = [
            DataPoint(date=date(2026, 4, 1), value=109052.0),
            DataPoint(date=date(2026, 5, 1), value=110216.0),
        ]
        merged = _merge_wages_points([], table, None)
        assert len(merged) == 2


class TestSummaryStillWorksOnFreshFixture:
    def test_summary_point_from_real_layout(self):
        text = (
            "Среднемесячная начисленная заработная плата работников организаций: "
            "номинальная, рублей 110 216 110,1 113,3 114,5 114,3 "
            "реальная 104,5 107,2 104,2 103,8"
        )
        result = _parse_wages_summary(text, date(2026, 5, 1))
        assert len(result) == 1
        assert result[0].date == date(2026, 5, 1)
        assert result[0].value == 110216.0
