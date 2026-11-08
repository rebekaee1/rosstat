"""Разбор ответа ЕМИСС dataGrid.do (grid/{id}.json.gz сборщика) в ряды сайта. Только чтение, без баз.

Прототип для загрузчика (спецификация — docs/research/emiss-opendata-placement-2026-11-09.md, раздел 4).

Формат ответа (collect.py):
  grid = {"id", "lines": [id измерений в строках], "cols": ["3", "33560"], "payloads": [{"results": [row, ...]}]}
  row  = {"dim<id измерения>": "название значения", ...,            # строка: сочетание измерений
          "dim<год>_<oid периода>_d<..>_i<..>": "12,5", ...}        # ячейки: год и период в имени ключа
Территория лежит в одном из измерений ТЕРРИТОРИЯ_DIMS (в строке — название, не oid), единица — в 30611.

Использование:
    from grid_to_series import load_grid, build_series
    series = build_series(load_grid(path), page=json.load(open(page_path)), dimnames=load_dimnames())
    for s in series: s.layer  # 'annual' -> region_data(year), 'monthly' -> region_monthly_data(YYYYMM),
                              # 'quarterly' -> слоя нет (см. спецификацию), 'other' -> не берём
"""
from __future__ import annotations

import gzip
import json
import re
import zlib
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
REGIONAL = REPO / "backend" / "app" / "data" / "regional"

TERRITORY_DIMS = ("57831", "30628", "3301", "36175")   # ОКАТО (разные редакции) / справочник территорий РФ
UNIT_DIM = "30611"
SKIP_LINE_DIMS = {"0", "3", "33560", UNIT_DIM}
RUSSIA_LEGACY = "Российская Федерация"
RUSSIA_NEW = "Российская Федерация без учета новых субъектов (с 01.01.2023)"
NEW_SUBJECTS_FROM = 2023

MONTHS = {"январь": 1, "февраль": 2, "март": 3, "апрель": 4, "май": 5, "июнь": 6, "июль": 7,
          "август": 8, "сентябрь": 9, "октябрь": 10, "ноябрь": 11, "декабрь": 12}
GEN = {"января": 1, "февраля": 2, "марта": 3, "апреля": 4, "мая": 5, "июня": 6, "июля": 7,
       "августа": 8, "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12}
QUARTERS = {"I": 1, "II": 2, "III": 3, "IV": 4}


def parse_period(label: str) -> tuple[str, int]:
    """Название периода → (вид, номер). Виды:
    M месяц(1-12) · Q квартал(1-4) · A год-поток · AE на конец года (31 декабря) · AS на начало года (1 января)
    C нарастающим итогом(последний месяц) · H полугодие · S срез на 1-е число месяца · D срез на 16-е · QE срез на конец квартала
    ? неизвестно."""
    s = (label or "").strip().lower()
    if s in MONTHS:
        return "M", MONTHS[s]
    m = re.fullmatch(r"(iv|iii|ii|i) квартал(?: \(предварительные данные\))?", s)
    if m:
        return "Q", QUARTERS[m.group(1).upper()]
    if s == "значение показателя за год":
        return "A", 0
    if s in ("на 31 декабря",):
        return "AE", 12
    if s in ("на 1 января", "1 января"):
        return "AS", 1
    if s == "январь-декабрь":
        return "A", 0
    m = re.fullmatch(r"январь-(\w+)", s)
    if m and m.group(1) in MONTHS:
        return "C", MONTHS[m.group(1)]
    if s == "9 месяцев":
        return "C", 9
    if s.endswith("полугодие"):
        return "H", 1 if s.startswith("i ") else 2
    m = re.fullmatch(r"(?:на )?1 (\w+)", s)
    if m and m.group(1) in GEN:
        return "S", GEN[m.group(1)]
    m = re.fullmatch(r"16 (\w+)", s)
    if m and m.group(1) in GEN:
        return "D", GEN[m.group(1)]
    m = re.fullmatch(r"на (?:30|31) (\w+)", s)
    if m and m.group(1) in GEN:
        return "QE", (GEN[m.group(1)] + 2) // 3
    return "?", 0


def period_layer(kind: str) -> str:
    return {"M": "monthly", "Q": "quarterly", "A": "annual", "AE": "annual", "AS": "annual", "S": "monthly"}.get(kind, "other")


def period_key(layer: str, year: int, num: int) -> int:
    """annual → год; monthly → YYYYMM; quarterly → YYYYQ."""
    if layer == "monthly":
        return year * 100 + num
    if layer == "quarterly":
        return year * 10 + num
    return year


def parse_ru_float(raw) -> float | None:
    if raw in (None, "", "-", "…", "x"):
        return None
    try:
        return float(str(raw).replace("\xa0", "").replace(" ", "").replace(",", "."))
    except ValueError:
        return None


def load_grid(path) -> dict:
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        return json.load(fh)


def load_dimnames() -> dict[str, str]:
    """название территории в ответе → slug сайта (то же, что делает emiss_regional_parser.load_dimnames)."""
    okato = json.loads((REGIONAL / "emiss_okato_31448.json").read_text(encoding="utf-8"))
    out = {str(oid): slug for slug, oid in okato.items()}
    out.update(json.loads((REGIONAL / "emiss_dimnames.json").read_text(encoding="utf-8")))
    return out


def iter_cells(payloads):
    """Строка, год, oid периода, сырое значение — для каждой ячейки всех ответов."""
    for pl in payloads:
        for row in pl.get("results", []):
            for key, raw in row.items():
                if not key.startswith("dim") or "_" not in key:
                    continue
                parts = key[3:].split("_")
                if not parts[0].isdigit():
                    continue
                year = int(parts[0])
                if year < 1900 or year > 2100:
                    continue
                oid = parts[1] if len(parts) > 1 and not parts[1].startswith("d") else None
                yield row, year, oid, raw


_TR = dict(zip("абвгдеёжзийклмнопрстуфхцчшщъыьэюя",
               ["a", "b", "v", "g", "d", "e", "e", "zh", "z", "i", "y", "k", "l", "m", "n", "o", "p", "r", "s", "t",
                "u", "f", "h", "c", "ch", "sh", "sch", "", "y", "", "e", "yu", "ya"]))


def translit(text: str) -> str:
    out = "".join(_TR.get(ch, ch) for ch in text.lower())
    return re.sub(r"[^a-z0-9]+", "-", out).strip("-")


def series_code(ind_id: str, qualifiers: list[str], layer: str, variant: str = "") -> str:
    """Устойчивый код ряда: emiss<id>[-<вид>][-<слои>-<crc>]; до 96 знаков (как у region_indicators.code)."""
    base = f"emiss{ind_id}"
    if qualifiers:
        tail = translit("-".join(qualifiers))
        crc = format(zlib.crc32("|".join(qualifiers).encode()) & 0xFFFFFFFF, "08x")
        base = f"{base}-{tail[:70].rstrip('-')}-{crc}" if tail else f"{base}-{crc}"
    if layer == "quarterly":
        base += "-q"
    base += variant
    return base[:96]


@dataclass
class Series:
    code: str
    name: str
    unit: str
    layer: str                                   # annual | monthly | quarterly | other
    qualifiers: dict[str, str] = field(default_factory=dict)   # «Виды показателя» и т.п.
    points: dict[tuple[str, int], float] = field(default_factory=dict)   # (slug, period_key) → value
    skipped_regions: set[str] = field(default_factory=set)


def build_series(grid: dict, page: dict, dimnames: dict[str, str] | None = None, *, drop_other: bool = True) -> list[Series]:
    """grid + страница показателя → ряды. Ряд = сочетание всех измерений строки, кроме территории и единицы;
    слой берётся из периода ячейки. Территории вне справочника сайта (районы, города) попадают в skipped_regions."""
    dimnames = dimnames if dimnames is not None else load_dimnames()
    dims = page.get("dims", {})
    ind_id = str(grid.get("id"))
    base_name = (next(iter(dims.get("0", {}).get("values", {}).values()), "") or "").strip()
    periods = dims.get("33560", {}).get("values", {})
    terr_dim = next((d for d in grid.get("lines", []) if d in TERRITORY_DIMS), None)
    qual_dims = [d for d in grid.get("lines", []) if d not in SKIP_LINE_DIMS and d != terr_dim]
    dim_titles = {d: dims.get(d, {}).get("title", d) for d in qual_dims}
    out: dict[tuple, Series] = {}
    for row, year, oid, raw in iter_cells(grid.get("payloads", [])):
        value = parse_ru_float(raw)
        if value is None:
            continue
        kind, num = parse_period(periods.get(oid, "значение показателя за год")) if oid else ("A", 0)
        layer = period_layer(kind)
        if layer == "other" and drop_other:
            continue
        quals = [str(row.get(f"dim{d}") or "") for d in qual_dims]
        unit = str(row.get(f"dim{UNIT_DIM}") or "")
        variant = {"AS": "-1jan", "S": "-1st"}.get(kind, "")   # срез на 1 января / на 1-е число месяца
        skey = (tuple(quals), unit, layer, variant)
        s = out.get(skey)
        if s is None:
            s = out[skey] = Series(
                code=series_code(ind_id, quals, layer, variant), name=base_name, unit=unit, layer=layer,
                qualifiers={dim_titles[d]: q for d, q in zip(qual_dims, quals) if q})
        if terr_dim:
            terr = str(row.get(f"dim{terr_dim}") or "").strip()
            if terr == RUSSIA_LEGACY and year >= NEW_SUBJECTS_FROM:
                continue            # с 2023 строка «без новых субъектов» — основная
            slug = "russia" if terr == RUSSIA_NEW else dimnames.get(terr)
            if not slug:
                s.skipped_regions.add(terr)
                continue
        else:
            slug = "russia"
        s.points[(slug, period_key(layer, year, num))] = value
    return list(out.values())
