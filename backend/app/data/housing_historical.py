"""Исторический seed для индексов цен на рынке жилья (1998-2014).

Источник:
- https://rosstat.gov.ru/free_doc/new_site/prices/housing/tab9.htm — первичный рынок
- https://rosstat.gov.ru/free_doc/new_site/prices/housing/tab8.htm — вторичный рынок

Обе таблицы — **архивные**, заморожены Росстатом 10.02.2020 (заголовок
страницы «Обновлено 10.02.2020»). Дальнейшие обновления Росстат перенёс
в socioeconomic-report PDF и mediabank xlsx, без публичной consolidated
архивной таблицы. Поэтому здесь — immutable snapshot годовых индексов
1998-2019 (% к предыдущему году, «на конец периода», т.е. Q4 → Q4),
строка «Все квартиры».

Для backfill в БД используется только 1998-2014: с 2015 у нас есть
полный квартальный ряд от парсера `rosstat_housing`. Backward chain
от anchor 2015-Q4 даёт chained level каждой исторической точки.
"""

from __future__ import annotations

from dataclasses import dataclass


# YoY %, на конец года (2015 → 2014 → ... → 1998).
# Источник: Rosstat tab9.htm (PRIMARY) и tab8.htm (SECONDARY), снимок 10.02.2020.
# WAYBACK: web.archive.org/web/20250317212400/https://rosstat.gov.ru/free_doc/new_site/prices/housing/tab9.htm
PRIMARY_YOY_PCT: dict[int, float] = {
    1998: 156.9, 1999: 146.3, 2000: 113.1, 2001: 125.1, 2002: 122.5,
    2003: 118.8, 2004: 118.5, 2005: 117.5, 2006: 147.7, 2007: 123.4,
    2008: 110.3, 2009: 92.4,  2010: 100.3, 2011: 106.7, 2012: 110.7,
    2013: 104.8, 2014: 105.7, 2015: 99.7,  2016: 99.6,  2017: 101.0,
    2018: 106.3, 2019: 108.0,
}

SECONDARY_YOY_PCT: dict[int, float] = {
    1998: 191.3, 1999: 129.6, 2000: 116.3, 2001: 132.0, 2002: 125.3,
    2003: 118.8, 2004: 124.1, 2005: 118.0, 2006: 154.4, 2007: 120.6,
    2008: 115.3, 2009: 89.0,  2010: 102.7, 2011: 105.8, 2012: 112.1,
    2013: 103.6, 2014: 105.1, 2015: 96.8,  2016: 97.0,  2017: 98.4,
    2018: 104.1, 2019: 103.8,
}

# Год, до которого делаем backfill (1998-Q4 включительно).
HISTORICAL_START_YEAR = 1998

# Год, с которого в БД уже есть свежий quarterly ряд (anchor для chain).
# 2015-Q1 = первая точка в индикаторах housing-price-primary / -secondary;
# 2015-Q4 = точка, от которой делаем backward chain.
ANCHOR_YEAR = 2015


@dataclass(frozen=True)
class HistoricalBackfillSpec:
    indicator_code: str
    yoy_table: dict[int, float]


SPECS = (
    HistoricalBackfillSpec("housing-price-primary", PRIMARY_YOY_PCT),
    HistoricalBackfillSpec("housing-price-secondary", SECONDARY_YOY_PCT),
)


def build_historical_levels(
    anchor_q4_level: float,
    yoy_table: dict[int, float],
    *,
    end_year_exclusive: int = ANCHOR_YEAR,
    start_year: int = HISTORICAL_START_YEAR,
) -> dict[int, float]:
    """Backward chain: даёт {year: Q4_level} от start_year до end_year_exclusive-1.

    Логика: yoy_table[Y] = (level[Y]/level[Y-1]) * 100.
    То есть level[Y-1] = level[Y] / (yoy_table[Y]/100).

    >>> build_historical_levels(130.5, {2014: 105.7, 2015: 99.7}, end_year_exclusive=2015, start_year=2014)
    {2014: 130.89...}
    """
    if anchor_q4_level <= 0:
        raise ValueError("anchor must be positive")
    out: dict[int, float] = {}
    level = anchor_q4_level
    # backward from end_year_exclusive towards start_year
    for y in range(end_year_exclusive, start_year - 1, -1):
        if y not in yoy_table:
            raise KeyError(f"missing yoy_table[{y}]")
        prev_year = y - 1
        prev_level = level / (yoy_table[y] / 100.0)
        if prev_year >= start_year:
            out[prev_year] = round(prev_level, 4)
        level = prev_level
    return dict(sorted(out.items()))
