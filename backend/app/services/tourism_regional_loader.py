"""Загрузчик туризма по регионам (реестр — ``app.data.tourism_regional``; 20.11.2026, зона t2).

Пишет в региональные слои: ``region_data`` (год), ``region_quarterly_data`` (YYYYQ), ``region_monthly_data``
(YYYYMM). Источники:

- ЕМИСС — по названиям, без oid: страница набора (``/indicator/{id}``) даёт справочник измерений, по нему
  выбираются территории, периоды и позиции ряда, затем тот же ``dataGrid.do`` и тот же транспорт, что у
  остальных наборов (``emiss_regional_parser._post_grid``: прямой ход → HTTP-прокси → SOCKS). 20.11.2026 fedstat
  отвечает 403 всем нашим адресам; набор, который не ответил, просто ждёт следующего прогона;
- Банк России — ``exp/imp_services_reg_YY.xlsx`` (экспорт и импорт услуг по субъектам, блок «Поездки»);
- Росаккредитация — открытый API реестра средств размещения;
- уже скачанное 20.11.2026 (ЕМИСС до бана, оценка турпотока Росстата, туристический налог ФНС, реестр турагентов,
  СберИндекс) — снимок ``app/data/regional/tourism_seed.csv.gz``; он пишется «только если точки нет»
  (ON CONFLICT DO NOTHING), живой ответ источника пишется с обновлением значения (ADR-0002).

Разбор сырья (функции ``*_points``) общий для снимка и живой загрузки: снимок собирает
``scripts/build_tourism_regional_seed.py`` из файлов ``.artifacts/tourism-2026-11-20`` теми же функциями.

Ловушки сырья (сверка 20.11.2026, SUMMARY_s2 §3): нарастающие итоги «январь–…» → разность (январь как есть,
отрицательная разность и месяц без предыдущего не пишутся); Россия двумя строками → ``russia`` по году;
опечатки территорий («Централный федеральный округ», «город Москва » с пробелом, «г.Санкт-Петербург» и
«г. Санкт-Петербург» через месяц) → нормализация названия; числа с запятой и неразрывным пробелом; у ЦБ колонки
года и «январь–июнь» между кварталами не берутся; у ЦБ ряд региона из одних нулей — непубликация.
"""

from __future__ import annotations

import asyncio
import csv
import gzip
import io
import json
import logging
import re
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from math import isfinite
from pathlib import Path
from typing import Callable, Iterable, Sequence

from app.data.tourism_regional import SERIES, SERIES_BY_CODE, TSeries, emiss_datasets, source_note
from app.services.emiss_regional_parser import parse_ru_float

logger = logging.getLogger(__name__)

_DATA = Path(__file__).resolve().parents[1] / "data" / "regional"
SEED_PATH = _DATA / "tourism_seed.csv.gz"
_ALERT_MUTE_S = 3 * 24 * 3600

Point = tuple[str, str, int, float]  # (код ряда, slug, период: год | YYYYQ | YYYYMM, значение)


# ---------------------------------------------------------------------------------------------------------------
# Территории: название источника → slug сайта.

_SPACES = re.compile(r"\s+")
_DASHES = re.compile(r"\s*[-–—]\s*")
_PREFIX = re.compile(r"^(?:\d+\s+|г\.\s*|город\s+)+")
_FOOTNOTE = re.compile(r"(?<=[а-яa-z»)])\s*[\d*]+\)?$")
_PARENS = re.compile(r"\s*\([^)]*\)\s*")

# Названия вне общего справочника (подписи ЕМИСС, ЦБ, ФНС, Росаккредитации, Росстата), уже нормализованные.
_ALIASES = {
    "централный федеральный округ": "cfo",
    "архангельская область (кроме ненецкого автономного округа)": "arhangelskaya-oblast-bez-ao",
    "архангельская область (без ао)": "arhangelskaya-oblast-bez-ao",
    "архангельская область без ао": "arhangelskaya-oblast-bez-ao",
    "архангельская область (без автономного округа)": "arhangelskaya-oblast-bez-ao",
    "тюменская область (кроме ханты-мансийского автономного округа-югры и ямало-ненецкого автономного округа)":
        "tyumenskaya-oblast-bez-ao",
    "тюменская область (без ао)": "tyumenskaya-oblast-bez-ao",
    "тюменская область без ао": "tyumenskaya-oblast-bez-ao",
    "тюменская область (без автономных округов)": "tyumenskaya-oblast-bez-ao",
    "кемеровская область": "kemerovskaya-oblast",
    "чувашская республика-чувашия": "chuvashskaya-respublika",
    "республика северная осетия-алания": "respublika-severnaya-osetiya",
    "ханты-мансийский автономный округ-югра": "hanty-mansiyskiy-ao",
    "республика марий-эл": "respublika-mariy-el",
    "ханты-мансийский автономный округ": "hanty-mansiyskiy-ao",
    "архангельская область без данных по ненецкому автономному округу": "arhangelskaya-oblast-bez-ao",
    "тюменская область без данных по ханты-мансийскому автономному округу-югре и ямало-ненецкому автономному "
    "округу": "tyumenskaya-oblast-bez-ao",
    "москва": "moskva",
    "санкт-петербург": "sankt-peterburg",
    "севастополь": "sevastopol",
}
_RUSSIA = re.compile(r"^(российская федерация|россия|всего|рф)\b")
_SKIP = re.compile(r"^(крымский федеральный округ|не распределено|прочие|справочно)")
_RUSSIA_WITHOUT_NEW = re.compile(r"без учета новых субъектов")


def norm_territory(name: str) -> str:
    s = str(name or "").replace("\xa0", " ").strip().casefold().replace("ё", "е")
    s = _SPACES.sub(" ", s)
    s = _FOOTNOTE.sub("", s).strip()
    s = _PREFIX.sub("", s).strip()
    s = _DASHES.sub("-", s)
    return s


class Territories:
    """Сопоставление названий; неизвестные копятся в ``unknown`` (отчёт загрузки)."""

    def __init__(self) -> None:
        index: dict[str, str] = {}
        regions = json.loads((_DATA / "regions.json").read_text(encoding="utf-8"))
        for r in regions:
            index[norm_territory(r["name"])] = r["slug"]
        for name, slug in json.loads((_DATA / "emiss_dimnames.json").read_text(encoding="utf-8")).items():
            index[norm_territory(name)] = slug
        index.update(_ALIASES)
        self.index = index
        self.unknown: set[str] = set()

    def resolve(self, name: str) -> tuple[str | None, bool]:
        """(slug, запасное ли название). Запасное — найдено только без скобок («… (с учетом ФТ «Сириус»)»):
        берётся там, где основной строки субъекта за период нет."""
        n = norm_territory(name)
        if not n or _SKIP.match(n):
            return None, False
        if _RUSSIA.match(n):
            return "russia", False
        slug = self.index.get(n)
        if slug:
            return slug, False
        bare = _PARENS.sub(" ", n).strip()
        slug = self.index.get(bare)
        if slug:
            return slug, True
        self.unknown.add(str(name).strip())
        return None, False


def russia_rank(name: str, year: int) -> int:
    """Какая из двух строк России главнее за год: до 2022 — «Российская Федерация», с 2023 — «без учета новых»."""
    without_new = bool(_RUSSIA_WITHOUT_NEW.search(norm_territory(name)))
    return 0 if without_new == (year >= 2023) else 1


# ---------------------------------------------------------------------------------------------------------------
# Сборщик точек: приоритеты территорий, нарастающие итоги, масштаб.

MONTHS = ("январь", "февраль", "март", "апрель", "май", "июнь", "июль", "август", "сентябрь", "октябрь",
          "ноябрь", "декабрь")
YEAR_TITLE = "значение показателя за год"


def norm_value(text: str) -> str:
    return _DASHES.sub("-", _SPACES.sub(" ", str(text or "").replace("\xa0", " ")).strip().casefold()
                       .replace("ё", "е"))


def period_index(title: str, kind: str) -> int | None:
    """Номер периода по подписи: месяц 1–12 (``month`` — «март», ``ytd`` — «январь-март»), 0 — год."""
    t = norm_value(title).rstrip("*0123456789) ")
    if kind == "year":
        return 0 if t == YEAR_TITLE else None
    if kind == "month":
        return MONTHS.index(t) + 1 if t in MONTHS else None
    if kind == "ytd":
        if t == "январь":
            return 1
        if t.startswith("январь-"):
            tail = t[len("январь-"):]
            return MONTHS.index(tail) + 1 if tail in MONTHS[1:] else None
    return None


class Collector:
    """Точки одного прогона: (код, slug, период) → значение с учётом приоритета строки."""

    def __init__(self) -> None:
        self._best: dict[tuple[str, str, int], tuple[int, float]] = {}

    def add(self, code: str, slug: str, period: int, value: float, rank: int = 0) -> None:
        key = (code, slug, period)
        cur = self._best.get(key)
        if cur is None or rank < cur[0]:
            self._best[key] = (rank, value)

    def raw(self) -> dict[tuple[str, str, int], float]:
        return {k: v for k, (_r, v) in self._best.items()}


def finalize(series: TSeries, raw: dict[tuple[str, int], float]) -> dict[tuple[str, int], float]:
    """Значения одного ряда {(slug, период): значение источника} → значения сайта (разность, масштаб, отбор).

    Для ``diff`` период — YYYYMM (месяц нарастающего итога) или YYYYQ (квартал): разность с предыдущим периодом того
    же года, первый период года как есть.
    """
    out: dict[tuple[str, int], float] = {}
    for (slug, period), value in raw.items():
        if series.transform == "diff":
            step = 100 if series.layer == "monthly" else 10
            first = period % step == 1
            if not first:
                prev = raw.get((slug, period - 1))
                if prev is None:
                    continue
                value = value - prev
            if value < 0:
                continue  # оценка источника уточнилась между публикациями: месяц не выдумываем
        year = period if series.layer == "annual" else period // (100 if series.layer == "monthly" else 10)
        if series.min_year and year < series.min_year:
            continue
        if not isfinite(value) or (value < 0 and not series.allow_negative):
            continue
        out[(slug, period)] = round(value * series.scale, 6) if series.scale != 1.0 else value
    return out


def to_points(series: TSeries, raw: dict[tuple[str, int], float]) -> list[Point]:
    return [(series.code, slug, period, value) for (slug, period), value in sorted(finalize(series, raw).items())]


# ---------------------------------------------------------------------------------------------------------------
# ЕМИСС: строки в общем виде (территория, год, подпись периода, значения прочих измерений, значение).


@dataclass(frozen=True)
class EmissRow:
    territory: str
    year: int
    period: str
    values: tuple[str, ...]
    raw: object


_STRUCTURAL = {"0", "3", "33560", "30611"}
_TOTAL = re.compile(r"^(всего|итого|все виды|всего по)")


def _matches(alt: tuple[str, ...], values: Sequence[str]) -> bool:
    """Все значения альтернативы есть в строке (с повторами); остальные значения строки — «итоговые»."""
    rest = [norm_value(v) for v in values]
    for want in alt:
        if want.startswith("re:"):
            rx = re.compile(want[3:], re.I)
            hit = next((i for i, v in enumerate(rest) if rx.search(v)), None)
        else:
            w = norm_value(want)
            hit = next((i for i, v in enumerate(rest) if v == w), None)
        if hit is None:
            return False
        rest.pop(hit)
    return all(_TOTAL.match(v) for v in rest)


def emiss_points(
    series_list: Sequence[TSeries], rows: Iterable[EmissRow], territories: Territories, *, today: date,
) -> list[Point]:
    """Строки набора → точки его рядов. Слой и вид периода — у ряда; ряд берёт первую подошедшую альтернативу."""
    by_series: dict[str, Collector] = {s.code: Collector() for s in series_list}
    rows = list(rows)
    for s in series_list:
        assert s.emiss is not None
        kind = s.emiss.periods
        col = by_series[s.code]
        for row in rows:
            if row.year < s.first_year or row.year > today.year:
                continue
            idx = period_index(row.period, kind)
            if idx is None:
                continue
            alt_rank = next((i for i, alt in enumerate(s.emiss.match) if _matches(alt, row.values)), None)
            if alt_rank is None:
                continue
            value = parse_ru_float(row.raw)
            if value is None or not isfinite(value):
                continue
            if s.emiss.periods != "ytd" and value == 0 and s.layer != "annual":
                continue
            slug, spare = territories.resolve(row.territory)
            if slug is None:
                continue
            period = row.year if kind == "year" else row.year * 100 + idx
            if s.layer == "monthly" and period > today.year * 100 + today.month:
                continue
            rank = alt_rank * 10 + (russia_rank(row.territory, row.year) if slug == "russia" else 0) + (5 if spare else 0)
            col.add(s.code, slug, period, value, rank)
    points: list[Point] = []
    for s in series_list:
        raw = {(slug, period): v for (_c, slug, period), v in by_series[s.code].raw().items()}
        points += to_points(s, raw)
    return points


def rows_from_csv(text: str) -> list[EmissRow]:
    """Выгрузка ЕМИСС в виде таблицы (``s_OKATO;…;EI;PERIOD;TIME;VALUE``; так скачано 20.11.2026)."""
    reader = csv.reader(io.StringIO(text), delimiter=";")
    header = next(reader)
    t_col = header.index("s_OKATO") if "s_OKATO" in header else 0
    extra = [i for i, h in enumerate(header) if h.startswith("s_") and i != t_col]
    p_col, y_col, v_col = header.index("PERIOD"), header.index("TIME"), header.index("VALUE")
    out = []
    for r in reader:
        if len(r) < len(header) or not r[y_col].strip().isdigit():
            continue
        out.append(EmissRow(r[t_col], int(r[y_col]), r[p_col], tuple(r[i] for i in extra), r[v_col]))
    return out


_CELL = re.compile(r"^dim(\d+)_d")


def rows_from_grid(payload: dict, *, territory_dim: str, period_titles: dict[str, str]) -> list[EmissRow]:
    """Ответ ``dataGrid.do``: в строке измерения приходят названиями; в столбцах — период (oid → подпись по
    справочнику страницы) или год (тогда период — в ``dim33560`` строки). Оба вида встречаются."""
    rows = payload.get("results")
    if not isinstance(rows, list):
        raise ValueError("ЕМИСС: в ответе нет массива results")
    out = []
    for row in rows:
        territory = str(row.get(f"dim{territory_dim}") or "")
        values = tuple(str(v) for k, v in row.items()
                       if k.startswith("dim") and "_" not in k and k[3:] not in _STRUCTURAL
                       and k[3:] != territory_dim)
        for key, raw in row.items():
            m = _CELL.match(key)
            if not m or raw in (None, "", "-", "—"):
                continue
            x = m.group(1)
            if len(x) == 4 and 1990 <= int(x) <= 2100:
                year, period = int(x), str(row.get("dim33560") or "")
            else:
                year_text = str(row.get("dim3") or "").strip()
                if not year_text.isdigit() or x not in period_titles:
                    continue
                year, period = int(year_text), period_titles[x]
            out.append(EmissRow(territory, year, period, values, raw))
    return out


# --- живой запрос ЕМИСС -------------------------------------------------------------------------------------------

_PAGE_URL = "https://www.fedstat.ru/indicator/{id}"


def parse_indicator_page(page: str) -> dict:
    """Страница набора → {'filters': {dim: {'title', 'values': {oid: title}}}, 'unit', 'title'}.

    Справочник измерений лежит в JS-объекте ``filters: {…}`` перед ``left_columns``; ключи без кавычек, строки в
    одинарных кавычках с ``\\uXXXX`` (так разбирал рабочий скрипт сбора 20.11.2026).
    """
    start = page.index("filters: {") + len("filters: ")
    end = page.index("left_columns:", start)
    js = page[start:end].rstrip().rstrip(",")
    js = re.sub(r"([{,\s])([A-Za-z_0-9]+):", lambda m: f'{m.group(1)}"{m.group(2)}":', js)
    js = re.sub(r"'((?:[^'\\]|\\.)*)'",
                lambda m: json.dumps(m.group(1).encode("utf-8").decode("unicode_escape")
                                     if "\\u" in m.group(1) else m.group(1).replace("\\'", "'")), js)
    js = re.sub(r",\s*}", "}", js)
    raw = json.loads(js)
    filters = {}
    for dim, f in raw.items():
        values = {str(oid): str((v or {}).get("title", "")) for oid, v in (f.get("values") or {}).items()}
        filters[str(dim)] = {"title": str(f.get("title", "")), "values": values}

    def _str(name: str) -> str:
        m = re.search(name + r": '((?:[^'\\]|\\.)*)'", page)
        if not m:
            return ""
        text = m.group(1)
        return text.encode("utf-8").decode("unicode_escape") if "\\u" in text else text

    return {"filters": filters, "unit": _str("unit"), "title": _str("title")}


def territory_dim_of(filters: dict[str, dict]) -> str | None:
    for dim, f in filters.items():
        t = f["title"].casefold()
        if "окато" in t or "субъект" in t or "территор" in t:
            return dim
    return None


def build_grid_params(
    dataset: int, filters: dict[str, dict], series_list: Sequence[TSeries], years: Sequence[int],
) -> tuple[list[tuple[str, str]], str, dict[str, str]]:
    """Параметры ``dataGrid.do`` по справочнику страницы → (params, измерение территорий, oid периода → подпись)."""
    tdim = series_list[0].emiss.territory_dim or territory_dim_of(filters)
    if tdim is None or tdim not in filters:
        raise ValueError(f"ЕМИСС {dataset}: не найдено измерение территорий")
    kinds = {s.emiss.periods for s in series_list}
    periods = {oid: t for oid, t in filters.get("33560", {}).get("values", {}).items()
               if any(period_index(t, k) is not None for k in kinds)}
    if not periods:
        raise ValueError(f"ЕМИСС {dataset}: на странице нет нужных периодов")
    wanted = [w for s in series_list for alt in s.emiss.match for w in alt]
    other = [d for d in filters if d not in _STRUCTURAL and d != tdim]
    selected: list[str] = [f"0_{dataset}", *(f"30611_{oid}" for oid in filters.get("30611", {}).get("values", {}))]
    selected += [f"33560_{oid}" for oid in periods]
    selected += [f"{tdim}_{oid}" for oid in filters[tdim]["values"]]
    for d in other:
        vals = filters[d]["values"]
        keep = []
        for oid, title in vals.items():
            n = norm_value(title)
            hit = any((w[3:] and re.search(w[3:], n, re.I)) if w.startswith("re:") else norm_value(w) == n
                      for w in wanted)
            if hit or _TOTAL.match(n) or len(vals) == 1:
                keep.append(oid)
        if not keep:
            raise ValueError(f"ЕМИСС {dataset}: в измерении {filters[d]['title']!r} нет ни позиции ряда, ни итога")
        selected += [f"{d}_{oid}" for oid in keep]
    selected += [f"3_{y}" for y in years]
    params = [("lineObjectIds", tdim), *(("lineObjectIds", d) for d in other), ("lineObjectIds", "3"),
              ("columnObjectIds", "33560"), *(("selectedFilterIds", v) for v in selected)]
    return params, tdim, periods


def _fetch_page_sync(dataset: int) -> str:
    from app.services.http_client import create_session

    session = create_session(timeout=60)
    try:
        resp = session.get(_PAGE_URL.format(id=dataset), timeout=60,
                           headers={"User-Agent": "ForecastEconomy/1.0 (+https://forecasteconomy.com)"})
        if resp.status_code in (403, 404):
            raise RuntimeError(f"HTTP {resp.status_code}")
        resp.raise_for_status()
        return resp.text
    finally:
        session.close()


async def fetch_emiss_dataset(
    dataset: int, series_list: Sequence[TSeries], years: Sequence[int], territories: Territories, *,
    today: date, fetch_page: Callable | None = None, post_grid: Callable | None = None,
) -> list[Point]:
    from app.services.emiss_regional_parser import _post_grid

    page_html = await (fetch_page(dataset) if fetch_page else asyncio.to_thread(_fetch_page_sync, dataset))
    page = parse_indicator_page(page_html)
    unit = norm_value(page["unit"])
    usable = [s for s in series_list if norm_value(s.emiss.src_unit) == unit or not unit]
    if not usable:
        raise ValueError(f"ЕМИСС {dataset}: единица набора {page['unit']!r}, ожидалась "
                         f"{series_list[0].emiss.src_unit!r} — масштаб рядов был бы неверен")
    params, tdim, periods = build_grid_params(dataset, page["filters"], usable, years)
    payload = await (post_grid or _post_grid)(dataset, params)
    rows = rows_from_grid(payload, territory_dim=tdim, period_titles=periods)
    points = emiss_points(usable, rows, territories, today=today)
    if rows and not points:
        raise ValueError(f"ЕМИСС {dataset}: {len(rows)} строк, ни одна точка не разобрана")
    return points


# ---------------------------------------------------------------------------------------------------------------
# Банк России: экспорт/импорт услуг по субъектам, блок «Поездки».

_CBR_URL = "https://www.cbr.ru/vfs/statistics/credit_statistics/trade/{kind}_services_reg_{yy:02d}.xlsx"
_QUARTER = re.compile(r"^\s*(I{1,3}|IV)\s+квартал\s+(\d{4})", re.I)
_ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4}
_CBR_CODES = {
    ("exp", "всего"): "tour-cbr-poezdki-eksport", ("exp", "деловые"): "tour-cbr-poezdki-eksport-delovye",
    ("exp", "личные"): "tour-cbr-poezdki-eksport-lichnye", ("exp", "туристские услуги"): "tour-cbr-turuslugi-eksport",
    ("imp", "всего"): "tour-cbr-poezdki-import", ("imp", "деловые"): "tour-cbr-poezdki-import-delovye",
    ("imp", "личные"): "tour-cbr-poezdki-import-lichnye", ("imp", "туристские услуги"): "tour-cbr-turuslugi-import",
}


def cbr_points(content: bytes, kind: str, territories: Territories) -> list[Point]:
    """Файл ЦБ за год → квартальные точки «Поездки» (всего, деловые, личные, туристские услуги).

    Шапка: строки 4–6 — статья, «всего»/«в том числе», вид поездки; строка 7 — периоды. Блок «Поездки» тянется до
    следующей статьи; внутри — по 3–5 колонок на вид (кварталы, год или «январь–июнь»). Берутся только кварталы.
    """
    import openpyxl

    ws = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True).worksheets[0]
    rows = [list(r) for r in ws.iter_rows(values_only=True)]
    head = next((i for i, r in enumerate(rows[:12]) if any(_QUARTER.match(str(c or "")) for c in r)), None)
    if head is None:
        return []
    top = next((i for i in range(head) if any(norm_value(c) == "поездки" for c in rows[i])), None)
    if top is None:
        return []  # 2018 год: «Поездок» в файле нет
    width = max(len(r) for r in rows[:head + 1])
    label_at = lambda r, c: norm_value(rows[r][c]) if c < len(rows[r]) and rows[r][c] else ""  # noqa: E731
    start = next(c for c in range(width) if label_at(top, c) == "поездки")
    end = next((c for c in range(start + 1, width) if label_at(top, c)), width)
    columns: dict[int, tuple[str, int]] = {}
    current = "всего"
    for c in range(start, end):
        for r in range(top + 1, head):
            lab = re.sub(r"\s*\d+$", "", label_at(r, c)).strip()
            if lab in ("всего", "деловые", "личные", "туристские услуги"):
                current = lab
            elif lab and lab not in ("в том числе", "справочно:", "справочно"):
                current = lab  # «медицинское обслуживание», «из них услуги организованного туризма» — не берём
        m = _QUARTER.match(str(rows[head][c] or ""))
        if m and (kind, current) in _CBR_CODES:
            columns[c] = (_CBR_CODES[(kind, current)], int(m.group(2)) * 10 + _ROMAN[m.group(1).upper()])
    raw: dict[str, dict[tuple[str, int], float]] = defaultdict(dict)
    for r in rows[head + 1:]:
        if not r or not r[0]:
            continue
        slug, spare = territories.resolve(str(r[0]))
        if slug is None or spare:
            continue
        for c, (code, quarter) in columns.items():
            v = r[c] if c < len(r) else None
            value = v if isinstance(v, (int, float)) else parse_ru_float(v)
            if value is not None and isfinite(value) and value >= 0:
                raw[code][(slug, quarter)] = float(value)
    points: list[Point] = []
    for code, values in raw.items():
        points += to_points(SERIES_BY_CODE[code], values)
    return points


def drop_zero_series(points: list[Point]) -> list[Point]:
    """Ряд региона из одних нулей — непубликация (у ЦБ), а не ноль; такой ряд не пишется."""
    nonzero = {(c, s) for c, s, _p, v in points if v != 0}
    return [p for p in points if (p[0], p[1]) in nonzero]


def _get_sync(url: str, timeout: int = 60) -> bytes | None:
    from app.services.http_client import create_session

    session = create_session(timeout=timeout)
    try:
        resp = session.get(url, timeout=timeout)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.content
    finally:
        session.close()


async def fetch_cbr(territories: Territories, *, today: date, years: Iterable[int] | None = None) -> list[Point]:
    years = list(years) if years is not None else [today.year - 1, today.year]
    points: list[Point] = []
    for year in years:
        for kind in ("exp", "imp"):
            content = await asyncio.to_thread(_get_sync, _CBR_URL.format(kind=kind, yy=year % 100))
            if content:
                points += cbr_points(content, kind, territories)
    return drop_zero_series(points)


# ---------------------------------------------------------------------------------------------------------------
# Росстат: оценка туристского потока (Turpotok_*.xlsx) — годовые листы 1.1/1.2 и квартальные 2.1/2.2.

_TURPOTOK_SHEET = re.compile(r"^([12])\.([12])\.(\d{4})$")
_TURPOTOK_CODES = {("1", "1"): "tour-turpotok-poezdki", ("1", "2"): "tour-turpotok-nochevki",
                   ("2", "1"): "tour-turpotok-poezdki-kv", ("2", "2"): "tour-turpotok-nochevki-kv"}
_YTD_QUARTER = {"январь-март": 1, "январь-июнь": 2, "январь-сентябрь": 3, "январь-декабрь": 4}


def turpotok_points(content: bytes, territories: Territories) -> list[Point]:
    import openpyxl

    wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    raw: dict[str, Collector] = defaultdict(Collector)
    for ws in wb.worksheets:
        m = _TURPOTOK_SHEET.match(ws.title.strip())
        if not m:
            continue
        code = _TURPOTOK_CODES[(m.group(1), m.group(2))]
        year = int(m.group(3))
        rows = [list(r) for r in ws.iter_rows(values_only=True)]
        head = next((i for i, r in enumerate(rows[:12])
                     if any(norm_value(c).startswith(("значение показателя", "январь")) for c in r if c)), None)
        if head is None:
            continue
        cols: dict[int, int] = {}
        for c, cell in enumerate(rows[head]):
            t = norm_value(cell).rstrip("*0123456789) ").strip()
            if m.group(1) == "1" and t == YEAR_TITLE:
                cols[c] = year
            elif m.group(1) == "2" and t in _YTD_QUARTER:
                cols[c] = year * 10 + _YTD_QUARTER[t]
        for r in rows[head + 1:]:
            if not r or not r[0]:
                continue
            slug, spare = territories.resolve(str(r[0]))
            if slug is None:
                continue
            for c, period in cols.items():
                v = r[c] if c < len(r) else None
                value = v if isinstance(v, (int, float)) else parse_ru_float(v)
                if value is not None and value > 0:
                    raw[code].add(code, slug, period, float(value), 5 if spare else 0)
    points: list[Point] = []
    for code, col in raw.items():
        points += to_points(SERIES_BY_CODE[code], {(s, p): v for (_c, s, p), v in col.raw().items()})
    return points


# ---------------------------------------------------------------------------------------------------------------
# ФНС: туристический налог (1-НМ по субъектам, нарастающим итогом, тыс. руб.).


def fns_tax_points(rows: Iterable[tuple[int, str, float]], territories: Territories) -> list[Point]:
    """[(YYYYMM, название территории, поступило с начала года в конс. бюджет, тыс. руб.)] → точки.

    Названия «г. Санкт-Петербург» и «г.Санкт-Петербург» чередуются по месяцам — нормализация их склеивает.
    Годовая точка — декабрь нарастающего итога.
    """
    ytd = Collector()
    for month, name, value in rows:
        slug, spare = territories.resolve(name)
        if slug is None or value is None or not isfinite(value) or value < 0:
            continue
        ytd.add("ytd", slug, month, float(value), 5 if spare else 0)
    raw = {(s, p): v for (_c, s, p), v in ytd.raw().items()}
    points = to_points(SERIES_BY_CODE["tour-nalog-s-nachala-goda"], raw)
    annual = {(s, p // 100): v for (s, p), v in raw.items() if p % 100 == 12}
    points += to_points(SERIES_BY_CODE["tour-nalog-za-god"], annual)
    return points


def fns_rows_from_csv(text: str) -> list[tuple[int, str, float]]:
    """Сводка, собранная 20.11.2026 из архивов 1-НМ (``tourist_tax_regions_ytd.csv``)."""
    out = []
    for r in csv.DictReader(io.StringIO(text), delimiter=";"):
        y, m = r["period_ytd_end"].split("-")
        v = parse_ru_float(r["tour_tax_consolidated_thous_rub"])
        if v is not None:
            out.append((int(y) * 100 + int(m), r["region"], v))
    return out


# ---------------------------------------------------------------------------------------------------------------
# Росаккредитация: реестр классифицированных средств размещения.

_FSA_API = "https://tourism.fsa.gov.ru/api/v1/resorts/hotels/showcase?page={page}&limit={limit}"
_ACTIVE = re.compile(r"^действ", re.I)


def fsa_points(records: Iterable[dict], territories: Territories, *, today: date) -> list[Point]:
    """Записи реестра → действующие на текущий месяц (снимок) и новые записи по годам (полные годы)."""
    active: dict[str, float] = defaultdict(float)
    new: dict[tuple[str, int], float] = defaultdict(float)
    for rec in records:
        slug, spare = territories.resolve(str(rec.get("region") or ""))
        if slug is None or slug == "russia":
            continue
        targets = [slug, "russia"]
        if _ACTIVE.match(str(rec.get("status") or "")):
            for t in targets:
                active[t] += 1
        d = str(rec.get("registerRecordDate") or "")[:4]
        if d.isdigit() and 2023 <= int(d) < today.year:
            for t in targets:
                new[(t, int(d))] += 1
    month = today.year * 100 + today.month
    points = to_points(SERIES_BY_CODE["tour-reestr-ksr"], {(s, month): v for s, v in active.items()})
    points += to_points(SERIES_BY_CODE["tour-reestr-ksr-novye"], dict(new))
    return points


def _fsa_records_sync(limit: int = 500) -> list[dict]:
    from app.services.http_client import create_session

    session = create_session(timeout=60)
    out: list[dict] = []
    try:
        page = 1
        while True:
            resp = session.get(_FSA_API.format(page=page, limit=limit), timeout=60)
            resp.raise_for_status()
            body = resp.json()
            items = body.get("items") or body.get("data") or body.get("content") or []
            for it in items:
                region = it.get("region")
                if isinstance(region, dict):
                    region = region.get("name") or region.get("title")
                status = it.get("status")
                if isinstance(status, dict):
                    status = status.get("name") or status.get("title")
                out.append({"region": region, "status": status, "registerRecordDate": it.get("registerRecordDate")})
            total = int(body.get("total") or 0)
            if not items or page * limit >= total:
                break
            page += 1
            time.sleep(0.5)
    finally:
        session.close()
    return out


# ---------------------------------------------------------------------------------------------------------------
# Минэкономразвития: реестр турагентов (снимок), регион — по первым двум цифрам ИНН.

INN_REGION = {
    "01": "respublika-adygeya", "02": "respublika-bashkortostan", "03": "respublika-buryatiya",
    "04": "respublika-altay", "05": "respublika-dagestan", "06": "respublika-ingushetiya",
    "07": "kabardino-balkarskaya-respublika", "08": "respublika-kalmykiya", "09": "karachaevo-cherkesskaya-respublika",
    "10": "respublika-kareliya", "11": "respublika-komi", "12": "respublika-mariy-el", "13": "respublika-mordoviya",
    "14": "respublika-saha", "15": "respublika-severnaya-osetiya", "16": "respublika-tatarstan",
    "17": "respublika-tyva", "18": "udmurtskaya-respublika", "19": "respublika-hakasiya",
    "20": "chechenskaya-respublika", "21": "chuvashskaya-respublika", "22": "altayskiy-kray",
    "23": "krasnodarskiy-kray", "24": "krasnoyarskiy-kray", "25": "primorskiy-kray", "26": "stavropolskiy-kray",
    "27": "habarovskiy-kray", "28": "amurskaya-oblast", "29": "arhangelskaya-oblast", "30": "astrahanskaya-oblast",
    "31": "belgorodskaya-oblast", "32": "bryanskaya-oblast", "33": "vladimirskaya-oblast",
    "34": "volgogradskaya-oblast", "35": "vologodskaya-oblast", "36": "voronezhskaya-oblast",
    "37": "ivanovskaya-oblast", "38": "irkutskaya-oblast", "39": "kaliningradskaya-oblast",
    "40": "kaluzhskaya-oblast", "41": "kamchatskiy-kray", "42": "kemerovskaya-oblast", "43": "kirovskaya-oblast",
    "44": "kostromskaya-oblast", "45": "kurganskaya-oblast", "46": "kurskaya-oblast", "47": "leningradskaya-oblast",
    "48": "lipetskaya-oblast", "49": "magadanskaya-oblast", "50": "moskovskaya-oblast", "51": "murmanskaya-oblast",
    "52": "nizhegorodskaya-oblast", "53": "novgorodskaya-oblast", "54": "novosibirskaya-oblast",
    "55": "omskaya-oblast", "56": "orenburgskaya-oblast", "57": "orlovskaya-oblast", "58": "penzenskaya-oblast",
    "59": "permskiy-kray", "60": "pskovskaya-oblast", "61": "rostovskaya-oblast", "62": "ryazanskaya-oblast",
    "63": "samarskaya-oblast", "64": "saratovskaya-oblast", "65": "sahalinskaya-oblast",
    "66": "sverdlovskaya-oblast", "67": "smolenskaya-oblast", "68": "tambovskaya-oblast", "69": "tverskaya-oblast",
    "70": "tomskaya-oblast", "71": "tulskaya-oblast", "72": "tyumenskaya-oblast", "73": "ulyanovskaya-oblast",
    "74": "chelyabinskaya-oblast", "75": "zabaykalskiy-kray", "76": "yaroslavskaya-oblast", "77": "moskva",
    "78": "sankt-peterburg", "79": "evreyskaya-ao", "83": "nenetskiy-ao", "86": "hanty-mansiyskiy-ao",
    "87": "chukotskiy-ao", "89": "yamalo-nenetskiy-ao", "91": "respublika-krym", "92": "sevastopol",
    # Старые коды ИНН упразднённых округов: ИНН у организаций остаются прежними.
    "80": "zabaykalskiy-kray", "81": "permskiy-kray", "84": "krasnoyarskiy-kray", "85": "irkutskaya-oblast",
    "88": "krasnoyarskiy-kray",
}


def turagent_points(inns: Iterable[str], month: int) -> list[Point]:
    counts: dict[str, float] = defaultdict(float)
    for inn in inns:
        inn = str(inn or "").strip()
        slug = INN_REGION.get(inn[:2]) if len(inn) in (10, 12) and inn.isdigit() else None
        if slug:
            counts[slug] += 1
            counts["russia"] += 1
    return to_points(SERIES_BY_CODE["tour-reestr-turagenty"], {(s, month): v for s, v in counts.items()})


# ---------------------------------------------------------------------------------------------------------------
# СберИндекс: количество внутренних туристов, % г/г (ряд остановлен в 04.2022).


def sber_points(text: str, territories: Territories) -> list[Point]:
    raw: dict[tuple[str, int], float] = {}
    for r in csv.DictReader(io.StringIO(text), delimiter=";"):
        slug, spare = territories.resolve(r.get("ref_area") or "")
        value = parse_ru_float(r.get("value"))
        period = str(r.get("period") or "")
        if slug is None or spare or value is None or len(period) < 10:
            continue
        # Дата — конец месяца по Москве, записанный в UTC (2018-12-31T21:00Z = 1 января): месяц — по Москве.
        y, m, d = int(period[:4]), int(period[5:7]), int(period[8:10])
        if d >= 28 and "T21:00" in period:
            y, m = (y + 1, 1) if m == 12 else (y, m + 1)
        raw[(slug, y * 100 + m)] = value
    return to_points(SERIES_BY_CODE["tour-sber-vnutrennie-turisty"], raw)


# ---------------------------------------------------------------------------------------------------------------
# Снимок и запись в базу.


def write_seed(points: Iterable[Point], path: Path = SEED_PATH) -> int:
    rows = sorted(set(points))
    with gzip.open(path, "wt", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["code", "slug", "period", "value"])
        for code, slug, period, value in rows:
            w.writerow([code, slug, period, f"{value:.6f}".rstrip("0").rstrip(".")])
    return len(rows)


def read_seed(path: Path = SEED_PATH) -> list[Point]:
    if not path.exists():
        return []
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return [(r["code"], r["slug"], int(r["period"]), float(r["value"])) for r in csv.DictReader(f, delimiter=";")]


async def ensure_indicators(db) -> dict[str, int]:
    """Метаданные своих рядов → {код: id} всех рядов реестра, что есть в базе (продлённые — у сборника)."""
    from sqlalchemy import or_, select
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    from app.models import RegionIndicator

    for s in SERIES:
        if not s.own_metadata:
            continue
        values = dict(code=s.code, table_code=s.table_code, section_num=s.section[0], section_name=s.section[1],
                      name=s.name_ru, unit=s.unit_ru, note=s.note_ru, source_note=source_note(s)[:200])
        stmt = pg_insert(RegionIndicator).values(**values)
        fields = {k: getattr(stmt.excluded, k) for k in values if k != "code"}
        await db.execute(stmt.on_conflict_do_update(
            index_elements=["code"], set_=fields,
            where=or_(*(getattr(RegionIndicator, k).is_distinct_from(v) for k, v in fields.items())),
        ))
    return dict((await db.execute(
        select(RegionIndicator.code, RegionIndicator.id).where(RegionIndicator.code.in_([s.code for s in SERIES]))
    )).all())


async def write_points(db, points: Sequence[Point], *, overwrite: bool) -> dict[str, int]:
    """Точки → слои по ряду; ``overwrite=False`` — только отсутствующие (снимок), иначе upsert с охраной значения."""
    from sqlalchemy import select
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    from app.core.cache import publish_committed_regional_changes
    from app.models import Region, RegionDataPoint, RegionMonthlyPoint, RegionQuarterlyPoint
    from app.services.emiss_regional_parser import literal_inserted
    from app.services.regional_storage import acquire_regional_write_lock, update_regional_year_bounds

    layers = {
        "annual": (RegionDataPoint, "year", "uq_region_data_point"),
        "quarterly": (RegionQuarterlyPoint, "quarter", "uq_region_quarterly_point"),
        "monthly": (RegionMonthlyPoint, "month", "uq_region_monthly_point"),
    }
    await acquire_regional_write_lock(db)
    ids = await ensure_indicators(db)
    regions = dict((await db.execute(select(Region.slug, Region.id))).all())
    grouped: dict[str, list[dict]] = defaultdict(list)
    for code, slug, period, value in points:
        s = SERIES_BY_CODE.get(code)
        if s is None or code not in ids or slug not in regions:
            continue
        grouped[s.layer].append({"indicator_id": ids[code], "region_id": regions[slug],
                                 layers[s.layer][1]: period, "value": value})
    stats = {"added": 0, "updated": 0}
    affected: set[int] = set()
    try:
        for layer, values in grouped.items():
            model, _col, constraint = layers[layer]
            for start in range(0, len(values), 5000):
                part = values[start:start + 5000]
                stmt = pg_insert(model).values(part)
                if overwrite:
                    stmt = stmt.on_conflict_do_update(
                        constraint=constraint, set_={"value": stmt.excluded.value},
                        where=(model.__table__.c.value != stmt.excluded.value))
                else:
                    stmt = stmt.on_conflict_do_nothing(constraint=constraint)
                rows = (await db.execute(stmt.returning(literal_inserted()))).fetchall()
                stats["added"] += sum(1 for (ins,) in rows if ins)
                stats["updated"] += sum(1 for (ins,) in rows if not ins)
                affected.update(v["indicator_id"] for v in part)
        changed = await update_regional_year_bounds(db, affected) if affected else 0
        await db.commit()
    except BaseException:
        await db.rollback()
        raise
    if stats["added"] or stats["updated"] or changed:
        await publish_committed_regional_changes()
    return stats


async def _last_years(db, series_list: Sequence[TSeries]) -> int | None:
    """Последний сохранённый год самого короткого ряда набора; ряд без точек → None (вся история)."""
    from sqlalchemy import func, select

    from app.models import RegionDataPoint, RegionIndicator, RegionMonthlyPoint, RegionQuarterlyPoint

    lasts = []
    for s in series_list:
        model, col, div = {"annual": (RegionDataPoint, "year", 1), "quarterly": (RegionQuarterlyPoint, "quarter", 10),
                           "monthly": (RegionMonthlyPoint, "month", 100)}[s.layer]
        last = await db.scalar(select(func.max(getattr(model, col))).join(
            RegionIndicator, RegionIndicator.id == model.indicator_id).where(RegionIndicator.code == s.code)
            .where(getattr(model, col) >= (s.min_year or 0) * div))
        if last is None:
            return None
        lasts.append(int(last) // div)
    return min(lasts) if lasts else None


def plan_years(series_list: Sequence[TSeries], last: int | None, today: date) -> list[list[int]]:
    first = min(s.first_year for s in series_list)
    start = first if last is None else max(first, last - 1)
    years = list(range(start, today.year + 1))
    monthly = any(s.emiss.periods != "year" for s in series_list)
    size = 1 if monthly else 6
    return [years[i:i + size] for i in range(0, len(years), size)]


async def run_tourism_regional_update(
    db, *, today: date | None = None, emiss: bool = True, cbr: bool = True, fsa: bool = True,
    fetch_page: Callable | None = None, post_grid: Callable | None = None,
) -> dict[str, object]:
    """Снимок (только недостающие точки) → живые источники по очереди; сбой одного не останавливает остальные."""
    today = today or date.today()
    territories = Territories()
    stats: dict[str, object] = {"seed": await write_points(db, read_seed(), overwrite=False), "failed": []}
    if emiss:
        for dataset, series_list in emiss_datasets().items():
            try:
                last = await _last_years(db, series_list)
                total = {"added": 0, "updated": 0}
                for years in plan_years(series_list, last, today):
                    pts = await fetch_emiss_dataset(dataset, series_list, years, territories, today=today,
                                                    fetch_page=fetch_page, post_grid=post_grid)
                    got = await write_points(db, pts, overwrite=True)
                    total = {k: total[k] + got[k] for k in total}
                    await asyncio.sleep(0.6 if post_grid is None else 0)
                stats[f"emiss_{dataset}"] = total
            except Exception as exc:  # noqa: BLE001 — набор ждёт следующего прогона (403 fedstat и т. п.)
                logger.warning("tourism_regional: ЕМИСС %s: %s", dataset, exc)
                stats["failed"].append(f"ЕМИСС {dataset}: {str(exc)[:120]}")
                if "HTTP 403" in str(exc):
                    stats["failed"].append("fedstat 403: остальные наборы ЕМИСС пропущены до следующего прогона")
                    break
    for name, enabled, fetch in (
        ("cbr", cbr, lambda: fetch_cbr(territories, today=today)),
        ("fsa", fsa, lambda: _fsa_live(territories, today)),
    ):
        if not enabled:
            continue
        try:
            stats[name] = await write_points(db, await fetch(), overwrite=True)
        except Exception as exc:  # noqa: BLE001
            logger.warning("tourism_regional: %s: %s", name, exc)
            stats["failed"].append(f"{name}: {str(exc)[:120]}")
    if territories.unknown:
        logger.info("tourism_regional: незнакомые территории: %s", sorted(territories.unknown)[:30])
    return stats


async def _fsa_live(territories: Territories, today: date) -> list[Point]:
    records = await asyncio.to_thread(_fsa_records_sync)
    if len(records) < 1000:
        raise ValueError(f"реестр Росаккредитации: {len(records)} записей — похоже на сбой выдачи")
    return fsa_points(records, territories, today=today)


async def tourism_regional_job() -> dict[str, object]:
    """Точка входа планировщика (раз в сутки): туризм по регионам."""
    from app.database import async_session

    started = time.monotonic()
    async with async_session() as db:
        stats = await run_tourism_regional_update(db)
    failed = [f for f in stats.get("failed", []) if not str(f).startswith(("ЕМИСС", "fedstat"))]
    logger.info("tourism_regional_job done in %.1fs: %s", time.monotonic() - started, stats)
    if failed:
        from html import escape

        from app.services.alerting import alert_muted, send_telegram

        try:
            if not await alert_muted("tourism_regional:failed", _ALERT_MUTE_S):
                await send_telegram("🟡 <b>Туризм по регионам: часть источников не ответила</b>\n"
                                    + escape("; ".join(failed)), kind="etl_alert")
        except Exception:  # noqa: BLE001 — алерт не должен маскировать результат
            pass
    return stats


if __name__ == "__main__":  # python -m app.services.tourism_regional_loader [--seed-only]
    import sys

    async def _main() -> None:
        from app.database import async_session

        async with async_session() as db:
            if "--seed-only" in sys.argv:
                print(await write_points(db, read_seed(), overwrite=False))
            else:
                print(await run_tourism_regional_update(db))

    asyncio.run(_main())
