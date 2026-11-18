"""ЕМИСС: распределение доходов населения и заработных плат России (реестр — ``app.data.emiss_income``).

Транспорт — тот же, что у регионального и трудового ЕМИСС (`_post_grid`: прямой ход → HTTP-прокси → SOCKS; адресу
прода fedstat отвечает 403). Один запрос на ряд: строки — территория и год, столбец — период. Фильтры фиксируют
показатель, единицу, период (год или апрель), группу населения или работников и, у зарплат по группам, строку «Всего
по обследуемым видам экономической деятельности». Россия до 2022 года — строка «Российская Федерация» (если её нет —
строка без учёта новых субъектов, это та же страна), с 2023 года — строка без учёта новых субъектов, если она
опубликована. Отсутствующий в источнике год не стирает сохранённую историю.
"""

from datetime import date
from math import isfinite
from typing import ClassVar

from sqlalchemy import func, select

from app.data.emiss_income import RUSSIA, RUSSIA_WITHOUT_NEW, SERIES, IncomeSeries
from app.models import IndicatorData
from app.services.base_parser import BaseParser
from app.services.emiss_regional_parser import _post_grid, parse_ru_float
from app.services.rosstat_labor_parser import DataPoint

_TERRITORY_LABELS = {
    RUSSIA: "Российская Федерация",
    RUSSIA_WITHOUT_NEW: "Российская Федерация без учета новых субъектов (с 01.01.2023)",
}
_ALL_INDUSTRIES = "1692933"


def _territory(row: dict) -> str | None:
    value = str(row.get("dim57831") or "").strip()
    for oid, label in _TERRITORY_LABELS.items():
        if value in (oid, label):
            return oid
    return None


def _value(series: IncomeSeries, row: dict) -> float | None:
    cells = [raw for key, raw in row.items() if key.startswith(f"dim{series.period}_") and raw not in (None, "", "-", "—")]
    if not cells:
        return None
    if len(cells) > 1:
        raise ValueError(f"ЕМИСС {series.dataset}: несколько значений в одной ячейке")
    value = parse_ru_float(cells[0])
    if value is None or not isfinite(value) or value < 0 or (series.unit == "%" and value > 100):
        raise ValueError(f"ЕМИСС {series.dataset}: недопустимое значение {cells[0]!r}")
    return value


async def fetch_series(series: IncomeSeries, years: range) -> list[DataPoint]:
    filters = [f"0_{series.dataset}", f"30611_{series.unit_oid}", f"33560_{series.period}",
               f"57831_{RUSSIA}", f"57831_{RUSSIA_WITHOUT_NEW}", *(f"3_{year}" for year in years)]
    if series.group:
        filters.append(f"{series.group[0]}_{series.group[1]}")
    if series.all_industries:
        filters.append(f"57940_{_ALL_INDUSTRIES}")
    payload = await _post_grid(series.dataset, [
        ("lineObjectIds", "57831"), ("lineObjectIds", "3"), ("columnObjectIds", "33560"),
        *(("selectedFilterIds", value) for value in filters),
    ])
    rows = payload.get("results")
    if not isinstance(rows, list):
        raise ValueError(f"ЕМИСС {series.dataset}: нет массива результатов")
    by_year: dict[int, dict[str, float]] = {}
    for row in rows:
        territory = _territory(row)
        year_text = str(row.get("dim3") or "").strip()
        if territory is None or not year_text.isdigit():
            raise ValueError(f"ЕМИСС {series.dataset}: неожиданная строка {row!r:.200}")
        value = _value(series, row)
        if value is not None:
            by_year.setdefault(int(year_text), {})[territory] = value
    points = []
    for year in sorted(by_year):
        values = by_year[year]
        # До 2023 года обе строки — одна и та же страна (новые субъекты в статистику ещё не входили): доли групп
        # 2011–2022 (31400) ЕМИСС отдаёт только строкой «без учета новых субъектов». С 2023 года она основная.
        order = (RUSSIA_WITHOUT_NEW, RUSSIA) if year >= 2023 else (RUSSIA, RUSSIA_WITHOUT_NEW)
        territory = next((oid for oid in order if oid in values), None)
        if territory is not None:
            points.append(DataPoint(date(year, 1, 1), values[territory]))
    # Годовой ряд за прошлый год может ещё не выйти; более старый пропуск — сбой источника.
    if years and not points and years[0] <= date.today().year - 3:
        raise ValueError(f"ЕМИСС {series.dataset}: нет опубликованных точек за {years[0]}–{years[-1]}")
    return points


class EmissIncomeParser(BaseParser):
    parser_type: ClassVar[str] = "rosstat_emiss_income"

    async def _fetch_and_parse(self, db, indicator, cfg, fetch_log):
        series = SERIES[indicator.code]
        latest = await db.scalar(
            select(func.max(IndicatorData.date)).where(IndicatorData.indicator_id == indicator.id)
        )
        # Первая загрузка — вся история; дальше — последний сохранённый год (ревизии) и новые годы.
        first_year = max(series.first_year, latest.year - (2 if series.every_two_years else 1)) if latest else series.first_year
        points = await fetch_series(series, range(first_year, date.today().year + 1))
        return points, series.source_url
