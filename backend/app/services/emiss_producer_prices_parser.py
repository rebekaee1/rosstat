"""ЕМИСС 57609, 57608, 57724, 57796, 63349: цены производителей и цены в строительстве России.

Реестр рядов — ``app.data.emiss_producer_prices``. Транспорт — тот же `_post_grid`, что у стали и доходов (прямой
ход → HTTP-прокси → SOCKS). Один запрос на набор за прогон: строки — позиция (и единица у 57724), территория и год,
столбцы — месяцы; ответ живёт в памяти процесса несколько минут, и остальные ряды того же набора берут его оттуда.
Россия до 2022 года — строка «Российская Федерация», с 2023 года — без учёта новых субъектов (если какой-то строки
нет, берётся другая). Индекс к тому же месяцу прошлого года хранится как изменение в процентах (104,5 → 4,5).
Отсутствующий в источнике месяц не стирает сохранённую историю.
"""

from __future__ import annotations

import asyncio
import time
from datetime import date
from math import isfinite
from typing import ClassVar

from sqlalchemy import func, select

from app.data.emiss_income import RUSSIA, RUSSIA_WITHOUT_NEW
from app.data.emiss_producer_prices import DATASETS, SERIES, UNITS, Dataset, Series
from app.models import IndicatorData
from app.services.base_parser import BaseParser
from app.services.emiss_income_parser import _territory
from app.services.emiss_regional_parser import MONTH_OIDS, _post_grid, parse_ru_float
from app.services.rosstat_labor_parser import DataPoint

# Индекс к прошлому году: обычно 80–130, у нефти в мае 2021 года — 552,92 (база — провал цен весной 2020-го).
# Средняя цена материала: от сотен рублей за м³ до сотен тысяч за тонну. Границы ловят сбой единицы или позиции, а не колебания рынка.
_INDEX_RANGE = (10.0, 1_000.0)
_PRICE_RANGE = (50.0, 1_000_000.0)
_CACHE_TTL_S = 15 * 60

_cache: dict[tuple[int, tuple[int, ...]], tuple[float, list[dict]]] = {}
_locks: dict[tuple[int, tuple[int, ...]], asyncio.Lock] = {}


def _month(key: str) -> int | None:
    return MONTH_OIDS.get(key.removeprefix("dim").split("_", 1)[0]) if key.startswith("dim") and "_d" in key else None


def dataset_series(dataset: int) -> list[Series]:
    return [series for series in SERIES.values() if series.dataset == dataset]


def grid_params(spec: Dataset, years: range) -> list[tuple[str, str]]:
    members = dataset_series(spec.id)
    lines = [spec.line_dim, *(["57956"] if spec.unit_dim else []), "57831", "3"]
    filters = [f"0_{spec.id}", *spec.filters, f"57831_{RUSSIA}", f"57831_{RUSSIA_WITHOUT_NEW}",
               *(f"3_{year}" for year in years), *(f"33560_{oid}" for oid in MONTH_OIDS),
               *dict.fromkeys(f"{spec.line_dim}_{oid}" for series in members for oid in series.items),
               *dict.fromkeys(f"57956_{series.unit_oid}" for series in members if series.unit_oid)]
    return [*(("lineObjectIds", dim) for dim in lines), ("columnObjectIds", "33560"),
            *(("selectedFilterIds", value) for value in filters)]


async def fetch_rows(spec: Dataset, years: range) -> list[dict]:
    """Строки ответа набора за годы `years`; повторный вызов в пределах 15 минут не ходит в ЕМИСС."""
    key = (spec.id, tuple(years))
    lock = _locks.setdefault(key, asyncio.Lock())
    async with lock:
        cached = _cache.get(key)
        if cached and time.monotonic() - cached[0] < _CACHE_TTL_S:
            return cached[1]
        payload = await _post_grid(spec.id, grid_params(spec, years))
        rows = payload.get("results")
        if not isinstance(rows, list):
            raise ValueError(f"ЕМИСС {spec.id}: нет массива результатов")
        _cache[key] = (time.monotonic(), rows)
        return rows


def parse_series(series: Series, rows: list[dict], years: range) -> list[DataPoint]:
    spec = series.spec
    known = {item.label for item in dataset_series(series.dataset)}
    unit_label = UNITS[series.unit_oid][0] if series.unit_oid else None
    low, high = _PRICE_RANGE if spec.kind == "price" else _INDEX_RANGE
    by_month: dict[date, dict[str, float]] = {}
    for row in rows:
        label = str(row.get(f"dim{spec.line_dim}") or "").strip()
        territory = _territory(row)
        year_text = str(row.get("dim3") or "").strip()
        if label not in known or territory is None or not year_text.isdigit():
            raise ValueError(f"ЕМИСС {spec.id}: неожиданная строка {row!r:.200}")
        if label != series.label or (unit_label and str(row.get("dim57956") or "").strip() != unit_label):
            continue
        year = int(year_text)
        if year < series.start_year:
            continue
        for key, raw in row.items():
            month = _month(key)
            if month is None or raw in (None, "", "-", "—"):
                continue
            value = parse_ru_float(raw)
            if value is None or not isfinite(value) or not low <= value <= high:
                raise ValueError(f"ЕМИСС {spec.id}: недопустимое значение {raw!r} ({series.label[:60]})")
            by_month.setdefault(date(year, month, 1), {})[territory] = value
    points = []
    for day in sorted(by_month):
        values = by_month[day]
        order = (RUSSIA_WITHOUT_NEW, RUSSIA) if day.year >= 2023 else (RUSSIA, RUSSIA_WITHOUT_NEW)
        value = next(values[oid] for oid in order if oid in values)
        points.append(DataPoint(day, value if spec.kind == "price" else round(value - 100.0, 2)))
    # Текущий год в январе–феврале ещё пуст (данные выходят через три недели); пустой прошлый год — сбой источника.
    if years and not points and years[0] < date.today().year:
        raise ValueError(f"ЕМИСС {spec.id}: нет опубликованных точек «{series.label[:60]}» за {years[0]}–{years[-1]}")
    return points


async def fetch_series(series: Series, years: range) -> list[DataPoint]:
    return parse_series(series, await fetch_rows(series.spec, years), years)


class EmissProducerPricesParser(BaseParser):
    parser_type: ClassVar[str] = "rosstat_emiss_producer_prices"

    async def _fetch_and_parse(self, db, indicator, cfg, fetch_log):
        series = SERIES[indicator.code]
        latest = await db.scalar(
            select(func.max(IndicatorData.date)).where(IndicatorData.indicator_id == indicator.id)
        )
        # Первая загрузка — вся история набора; дальше — год последней точки и предыдущий (ревизии) и новые. Ряды
        # одного набора после первой загрузки просят одни и те же годы и делят один ответ.
        first_year = max(series.spec.first_year, latest.year - 1) if latest else series.spec.first_year
        points = await fetch_series(series, range(first_year, date.today().year + 1))
        return points, series.spec.source_url


__all__ = ["DATASETS", "EmissProducerPricesParser", "fetch_rows", "fetch_series", "grid_params", "parse_series"]
