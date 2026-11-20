"""ЕМИСС: федеральные ряды раздела «Туризм» — авиаперевозки, аэропорты, железная дорога, гостиницы, санатории,
турфирмы (реестр — ``app.data.tourism_russia``, ``model_config_json.emiss_*``).

Живой ход. Страница витрины ``fedstat.ru/indicator/{id}`` отдаёт справочник фильтров; запрос ``dataGrid.do`` тем же
транспортом, что у остальных наборов ЕМИСС (``_post_grid``: прямой ход → HTTP-прокси → SOCKS), выбирает все значения
всех фильтров, кроме территорий — из них только Россия (до 2022 года строка «Российская Федерация», с 2023 года —
строка без учёта новых субъектов; если одной нет, берётся другая). Строки — все измерения, столбцы — годы.

Разбор общий для всех наборов (``parse_rows``): строка ответа — значения измерений (``dim<id>``) и ячейки по годам
(``dim<год>_…``). Ряд выбирает свои значения измерений (``emiss_match``), складывает по разрешённым измерениям
(``emiss_sum_dims``: например регулярные + чартерные, внутренние + международные) и берёт период нужного вида:
месяц, «значение показателя за год» или нарастающий итог «январь–…» (месяц = разность соседних итогов, январь как
есть). Месяц, в котором опубликованы не все слагаемые, не сохраняется: сумма была бы занижена. Занятость кресел —
отношение двух наборов (выполненный пассажирооборот к предельному) в процентах.

Резервный снимок. С 20.11.2026 fedstat отвечает 403 всем адресам проекта. Пока у ряда нет ни одной точки, сбой сети
заменяется снимком ответа от 20.11.2026 (``app/data/tourism_snapshots/emiss_<id>.json``, только строки России):
ряд получает историю и статус ``fallback_used``. Когда история уже есть, снимок не применяется — он не должен
затирать более свежие ревизии; ряд честно получает ``failed``.
"""

from __future__ import annotations

import asyncio
import json
import re
from datetime import date
from math import isfinite
from pathlib import Path
from typing import ClassVar

from sqlalchemy import func, select

from app.models import IndicatorData
from app.services.base_parser import BaseParser, mark_fallback_used
from app.services.emiss_regional_parser import _post_grid, parse_ru_float
from app.services.http_client import create_session
from app.services.rosstat_labor_parser import DataPoint

SNAPSHOT_DIR = Path(__file__).resolve().parents[1] / "data" / "tourism_snapshots"
PAGE_URL = "https://www.fedstat.ru/indicator/{}"
_UA = "ForecastEconomy/1.0 (+https://forecasteconomy.com)"

RUSSIA = "Российская Федерация"
RUSSIA_WITHOUT_NEW = "Российская Федерация без учета новых субъектов (с 01.01.2023)"
TERRITORY_DIMS = ("57831", "30613")
PERIOD_DIM = "33560"
UNIT_DIM = "30611"
YEAR_KEY = re.compile(r"^dim(\d{4})_")
DIM_KEY = re.compile(r"^dim(\d+|[a-z_]+)$")

MONTHS = ("январь", "февраль", "март", "апрель", "май", "июнь", "июль", "август", "сентябрь", "октябрь",
          "ноябрь", "декабрь")
ANNUAL = "значение показателя за год"
QUARTERS = {"i квартал": 3, "ii квартал": 6, "iii квартал": 9, "iv квартал": 12}


class EmissTourismFormatError(ValueError):
    pass


def _norm(text: object) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip().lower()


def _period_key(label: str, kind: str) -> int | None:
    """Номер месяца периода нужного вида или None (период другого вида)."""
    text = _norm(label).replace("–", "-").replace(" - ", "-")
    if kind == "annual":
        return 1 if text == ANNUAL else None
    if kind == "monthly":
        return MONTHS.index(text) + 1 if text in MONTHS else None
    if kind == "quarterly":
        return QUARTERS.get(text)
    if kind == "ytd_monthly":
        if text == "январь":
            return 1
        if text.startswith("январь-"):
            end = text.split("-", 1)[1].strip()
            return MONTHS.index(end) + 1 if end in MONTHS else None
        return None
    raise ValueError(f"неизвестный вид периода {kind!r}")


def _territory(row: dict) -> str | None:
    for dim in TERRITORY_DIMS:
        if f"dim{dim}" in row:
            name = re.sub(r"\s+", " ", str(row[f"dim{dim}"])).strip()
            return name if name in (RUSSIA, RUSSIA_WITHOUT_NEW) else ""
    return None  # набор без территориального измерения — Россия целиком


def parse_rows(rows: list[dict], cfg: dict) -> dict[date, float]:
    """Ответ dataGrid (или снимок) → {дата: значение} одного ряда в единицах источника × ``emiss_scale``."""
    kind = cfg["emiss_period"]
    match = {f"dim{k}": {_norm(v) for v in vals} for k, vals in (cfg.get("emiss_match") or {}).items()}
    sum_dims = {f"dim{d}" for d in cfg.get("emiss_sum_dims") or ()}
    service = {f"dim{d}" for d in (*TERRITORY_DIMS, PERIOD_DIM, UNIT_DIM)}
    # (территория, год, месяц) → {сочетание слагаемых: значение}
    cells: dict[tuple[str, int, int], dict[tuple, float]] = {}
    combos: set[tuple] = set()
    other_values: dict[str, set[str]] = {}
    for row in rows:
        if any(_norm(row.get(dim)) not in allowed for dim, allowed in match.items()):
            continue
        territory = _territory(row)
        if territory == "":
            continue
        month = _period_key(row.get(f"dim{PERIOD_DIM}", ANNUAL if kind == "annual" else ""), kind)
        if month is None:
            continue
        dims = {k: _norm(v) for k, v in row.items() if DIM_KEY.match(k) and not YEAR_KEY.match(k)}
        for k, v in dims.items():
            if k not in service and k not in match and k not in sum_dims and k != "dim0":
                other_values.setdefault(k, set()).add(v)
        combo = tuple(sorted((k, v) for k, v in dims.items() if k in sum_dims))
        combos.add(combo)
        for key, raw in row.items():
            m = YEAR_KEY.match(key)
            if not m or str(raw).strip() in ("", "-", "—", "–", "…", "x", "х"):
                continue
            value = parse_ru_float(raw)
            if value is None or not isfinite(value):
                raise EmissTourismFormatError(f"ЕМИСС {cfg['emiss_dataset']}: значение {raw!r}")
            cells.setdefault((territory or RUSSIA, int(m.group(1)), month), {})[combo] = value
    ambiguous = {k: v for k, v in other_values.items() if len(v) > 1}
    if ambiguous:
        raise EmissTourismFormatError(f"ЕМИСС {cfg['emiss_dataset']}: ряд не выбран по измерениям {sorted(ambiguous)}")
    scale = float(cfg.get("emiss_scale") or 1.0)
    first_year = int(cfg.get("emiss_first_year") or 0)
    totals: dict[tuple[int, int], dict[str, float]] = {}
    for (territory, year, month), parts in cells.items():
        if year < first_year or len(parts) < len(combos):
            continue  # опубликованы не все слагаемые — сумма была бы занижена
        totals.setdefault((year, month), {})[territory] = sum(parts.values())
    out: dict[date, float] = {}
    for (year, month), by_territory in sorted(totals.items()):
        order = (RUSSIA_WITHOUT_NEW, RUSSIA) if year >= 2023 else (RUSSIA, RUSSIA_WITHOUT_NEW)
        value = next(by_territory[t] for t in order if t in by_territory)
        out[date(year, month, 1)] = value * scale
    if kind == "ytd_monthly":
        monthly: dict[date, float] = {}
        for day, value in out.items():
            if day.month == 1:
                monthly[day] = value
                continue
            prev = out.get(date(day.year, day.month - 1, 1))
            if prev is not None:
                monthly[day] = value - prev
        out = monthly
    return out


def parse_snapshot_or_answer(payload: dict, cfg: dict) -> dict[date, float]:
    rows = payload.get("results")
    if not isinstance(rows, list):
        raise EmissTourismFormatError(f"ЕМИСС {cfg['emiss_dataset']}: нет массива results")
    return parse_rows(rows, cfg)


def series_points(main: dict[date, float], cfg: dict, denominator: dict[date, float] | None = None) -> list[DataPoint]:
    if denominator is not None:
        pts = [DataPoint(d, round(v / denominator[d] * 100, 2)) for d, v in main.items()
               if denominator.get(d)]
    else:
        pts = [DataPoint(d, round(v, 6)) for d, v in main.items()]
    return sorted(pts, key=lambda p: p.date)


# ── Живой ход ─────────────────────────────────────────────────────────────────

_FILTERS_BLOCK = re.compile(r"filters: \{(.*?)left_columns", re.S)


_JS_ESCAPE = re.compile(r"\\u([0-9a-fA-F]{4})|\\(['\"\\\\/])")


def _unescape(text: str) -> str:
    """Подпись из JS-строки страницы: раскрываются только ``\\uXXXX`` и экранированные кавычки/слэши.

    ``encode().decode("unicode_escape")`` портил строку, где обычная кириллица стоит рядом с ``\\u``-кодами: UTF-8
    байты кириллицы читались как Latin-1 («Ð\x9fÐ°…»).
    """
    return _JS_ESCAPE.sub(lambda m: chr(int(m.group(1), 16)) if m.group(1) else m.group(2), text)


def parse_page_filters(page: str) -> dict[str, dict[str, str]]:
    """Справочник фильтров со страницы витрины: {id измерения: {oid значения: подпись}}."""
    m = _FILTERS_BLOCK.search(page)
    if not m:
        raise EmissTourismFormatError("на странице витрины нет блока filters")
    filters: dict[str, dict[str, str]] = {}
    current = last = None
    for line in m.group(1).split("\n"):
        if mf := re.match(r"^ {28}(\w+): \{", line):
            current, last = mf.group(1), None
            filters[current] = {}
        elif (mv := re.match(r"^ {36}(\w+): \{", line)) and current:
            last = mv.group(1)
            filters[current][last] = ""
        elif (mt := re.match(r"^ {40}title: '(.*)',", line)) and current and last:
            filters[current][last] = _unescape(mt.group(1))
    if "0" not in filters or "3" not in filters:
        raise EmissTourismFormatError("в справочнике фильтров нет показателя или года")
    return filters


def _fetch_page_sync(dataset: int) -> str:
    session = create_session(timeout=60)
    try:
        resp = session.get(PAGE_URL.format(dataset), timeout=60, headers={"User-Agent": _UA})
        resp.raise_for_status()
        return resp.text
    finally:
        session.close()


def grid_params(filters: dict[str, dict[str, str]], years: range | None) -> list[tuple[str, str]]:
    params = [("lineObjectIds", fid) for fid in filters if fid not in ("0", "3")]
    params.append(("columnObjectIds", "3"))
    for fid, values in filters.items():
        for oid, title in values.items():
            if fid in TERRITORY_DIMS and re.sub(r"\s+", " ", title).strip() not in (RUSSIA, RUSSIA_WITHOUT_NEW):
                continue
            if fid == "3" and years is not None and (not oid.isdigit() or int(oid) not in years):
                continue
            params.append(("selectedFilterIds", f"{fid}_{oid}"))
    return params


async def fetch_dataset(dataset: int, years: range | None) -> dict:
    page = await asyncio.to_thread(_fetch_page_sync, dataset)
    return await _post_grid(dataset, grid_params(parse_page_filters(page), years))


def load_snapshot(dataset: int) -> dict:
    path = SNAPSHOT_DIR / f"emiss_{dataset}.json"
    return json.loads(path.read_text(encoding="utf-8"))


class EmissTourismParser(BaseParser):
    parser_type: ClassVar[str] = "rosstat_emiss_tourism"

    async def _fetch_and_parse(self, db, indicator, cfg, fetch_log):
        dataset = int(cfg["emiss_dataset"])
        ratio_of = cfg.get("emiss_ratio_of")
        latest = await db.scalar(
            select(func.max(IndicatorData.date)).where(IndicatorData.indicator_id == indicator.id)
        )
        # Первая загрузка — вся история; дальше — год последней точки, предыдущий (ревизии) и новые.
        years = range(latest.year - 1, date.today().year + 1) if latest else None
        try:
            payloads = [await fetch_dataset(dataset, years)]
            if ratio_of:
                payloads.append(await fetch_dataset(int(ratio_of), years))
        except Exception as exc:  # noqa: BLE001 — сеть/бан/формат страницы: решает наличие истории
            if latest is not None:
                raise
            payloads = [load_snapshot(dataset)] + ([load_snapshot(int(ratio_of))] if ratio_of else [])
            mark_fallback_used(fetch_log, f"fedstat {dataset} недоступен ({str(exc)[:160]}); снимок 20.11.2026")
        main = parse_snapshot_or_answer(payloads[0], cfg)
        denominator = parse_snapshot_or_answer(payloads[1], cfg) if ratio_of else None
        points = series_points(main, cfg, denominator)
        if not points and latest is None:
            raise EmissTourismFormatError(f"ЕМИСС {dataset}: ни одной точки ряда {indicator.code}")
        return points, PAGE_URL.format(dataset)
