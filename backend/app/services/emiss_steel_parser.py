"""ЕМИСС 57606: средние цены производителей стали в России (реестр — ``app.data.emiss_steel``).

Транспорт — тот же `_post_grid`, что у регионального, трудового и доходного ЕМИСС (прямой ход → HTTP-прокси → SOCKS;
адресу прода fedstat отвечает 403). Один запрос на ряд: строки — продукция, территория и год, столбцы — месяцы.
Фильтры фиксируют показатель, рубль, тонну, канал «Внутренний рынок» и позицию ОКПД2. Россия до 2022 года — строка
«Российская Федерация», с 2023 года — строка без учёта новых субъектов (если какой-то строки нет, берётся другая: до
2023 года это одна и та же страна). Отсутствующий в источнике месяц не стирает сохранённую историю.
"""

from datetime import date
from math import isfinite
from typing import ClassVar

from sqlalchemy import func, select

from app.data.emiss_income import RUSSIA, RUSSIA_WITHOUT_NEW
from app.data.emiss_steel import (
    DATASET, DOMESTIC, FIRST_YEAR, PRODUCT_DIM, RUBLE, SERIES, SOURCE_URL, TONNE, SteelSeries,
)
from app.models import IndicatorData
from app.services.base_parser import BaseParser
from app.services.emiss_income_parser import _territory
from app.services.emiss_regional_parser import MONTH_OIDS, _post_grid, parse_ru_float
from app.services.rosstat_labor_parser import DataPoint

# Тонна стального проката или труб у производителя: десятки тысяч рублей. Граница ловит сбой единицы или позиции
# (у соседней позиции «трубы прочие» в ответе встречаются 1,2 млн ₽/т), а не колебания рынка.
_MIN_PRICE, _MAX_PRICE = 3_000.0, 500_000.0


def _month(key: str) -> int | None:
    return MONTH_OIDS.get(key.removeprefix("dim").split("_", 1)[0]) if key.startswith("dim") and "_d" in key else None


async def fetch_series(series: SteelSeries, years: range) -> list[DataPoint]:
    filters = [f"0_{DATASET}", f"30611_{RUBLE}", f"57956_{TONNE}", f"58601_{DOMESTIC}",
               f"{PRODUCT_DIM}_{series.product}", f"57831_{RUSSIA}", f"57831_{RUSSIA_WITHOUT_NEW}",
               *(f"3_{year}" for year in years), *(f"33560_{oid}" for oid in MONTH_OIDS)]
    payload = await _post_grid(DATASET, [
        ("lineObjectIds", PRODUCT_DIM), ("lineObjectIds", "57831"), ("lineObjectIds", "3"),
        ("columnObjectIds", "33560"), *(("selectedFilterIds", value) for value in filters),
    ])
    rows = payload.get("results")
    if not isinstance(rows, list):
        raise ValueError(f"ЕМИСС {DATASET}: нет массива результатов")
    by_month: dict[date, dict[str, float]] = {}
    for row in rows:
        product = str(row.get(f"dim{PRODUCT_DIM}") or "").strip()
        territory = _territory(row)
        year_text = str(row.get("dim3") or "").strip()
        if product not in (series.product, series.label) or territory is None or not year_text.isdigit():
            raise ValueError(f"ЕМИСС {DATASET}: неожиданная строка {row!r:.200}")
        for key, raw in row.items():
            month = _month(key)
            if month is None or raw in (None, "", "-", "—"):
                continue
            value = parse_ru_float(raw)
            if value is None or not isfinite(value) or not _MIN_PRICE <= value <= _MAX_PRICE:
                raise ValueError(f"ЕМИСС {DATASET}: недопустимое значение {raw!r}")
            by_month.setdefault(date(int(year_text), month, 1), {})[territory] = value
    points = []
    for day in sorted(by_month):
        values = by_month[day]
        order = (RUSSIA_WITHOUT_NEW, RUSSIA) if day.year >= 2023 else (RUSSIA, RUSSIA_WITHOUT_NEW)
        points.append(DataPoint(day, next(values[oid] for oid in order if oid in values)))
    # Текущий год в январе–феврале ещё пуст (данные выходят через три недели); пустой прошлый год — сбой источника.
    if years and not points and years[0] < date.today().year:
        raise ValueError(f"ЕМИСС {DATASET}: нет опубликованных точек за {years[0]}–{years[-1]}")
    return points


class EmissSteelParser(BaseParser):
    parser_type: ClassVar[str] = "rosstat_emiss_steel"

    async def _fetch_and_parse(self, db, indicator, cfg, fetch_log):
        series = SERIES[indicator.code]
        latest = await db.scalar(
            select(func.max(IndicatorData.date)).where(IndicatorData.indicator_id == indicator.id)
        )
        # Первая загрузка — вся история с 2017 года; дальше — год последней точки и предыдущий (ревизии) и новые.
        first_year = max(FIRST_YEAR, latest.year - 1) if latest else FIRST_YEAR
        points = await fetch_series(series, range(first_year, date.today().year + 1))
        return points, SOURCE_URL
