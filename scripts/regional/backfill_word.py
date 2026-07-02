"""Дособор из Word-редакций сборника: 1990-е из TOM2 (изд. 2003) + «Правонарушения».

Источники (DOC -> docx через LibreOffice, см. main()):
  * TOM2 (Регионы России, 2003; данные 1990-2002) — продление рядов 2025-го
    артефакта в 1990-е (mode=extend) и преступность 1990-2002 (mode=new).
  * soc-pok18 (изд. 2018; данные 2005-2017) — раздел «8. Преступность»,
    исключённый из сборника после 2019 г. (mode=new).

Механика:
  * файл читается в порядке тела документа: заголовок таблицы (параграф
    `N.M. НАЗВАНИЕ`) -> все docx-таблицы до следующего заголовка (таблица
    физически разбита на 2+ куска);
  * колонки-годы берутся из первой строки-шапки, колонка «Место, занимаемое…»
    и прочие не-годы игнорируются;
  * строка «Российская Федерация, тыс.» — значение РФ в 1000 раз крупнее
    регионов (scale из resolve_region);
  * mode=extend: КРОСС-СВЕРКА на overlap-годах с текущим артефактом
    (относительное расхождение медианы по регионам > порога = job отклоняется),
    затем добавляются только годы СТРОГО МЛАДШЕ year_min целевого ряда;
    для денежных рядов min_year=1998 (до деноминации 1998 г. — тыс. руб.,
    несовместимо со шкалой);
  * mode=new: новый показатель (раздел 22 «Правонарушения»).

Запуск ПОСЛЕ parse_pril_2025.py и backfill_pril_2022_2023.py:
  python3 scripts/regional/backfill_word.py
"""

import csv
import gzip
import json
import os
import re
import statistics
import subprocess
import sys

import docx
from docx.table import Table
from docx.text.paragraph import Paragraph

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from parse_pril_2025 import OUT_DIR, norm_text, parse_value, translit_slug  # noqa: E402
from regions_registry import resolve_region  # noqa: E402

SOFFICE = "/Applications/LibreOffice.app/Contents/MacOS/soffice"
TOM2_SRC = "/tmp/reg_all/19/TOM2"
ED2018_SRC = "/tmp/reg_all/05/soc-pok18"
TOM2_DIR = "/tmp/lo_tom2"
ED2018_DIR = "/tmp/lo_out"
ED2019_DIR = "/tmp/reg_all/04/soc-pok2019"  # уже docx, конвертация не нужна

EDITION_DIRS = {"tom2": TOM2_DIR, "2018": ED2018_DIR, "2019": ED2019_DIR}

YEAR_RE = re.compile(r"^(19[89]\d|20[0-2]\d)\s*(?:г\.)?\s*(?:\d\))?$")
HEAD_RE = re.compile(r"^\s*(\d+\.\d+)\.\s+(\S.*)", re.S)

# (docx, номер таблицы в редакции, mode, target-код 2025 | спека нового, min_year)
JOBS = [
    # --- TOM2: продление демографии/труда/уровня жизни в 1990-е ---
    ("tom2", "R-02.docx", "2.8",  "extend", "1.9",    1990),  # рождаемость
    ("tom2", "R-02.docx", "2.9",  "extend", "1.10",   1990),  # смертность
    ("tom2", "R-02.docx", "2.10", "extend", "1.13",   1990),  # младенческая смертность
    ("tom2", "R-02.docx", "2.11", "extend", "1.14",   1990),  # естественный прирост
    ("tom2", "R-02.docx", "2.13", "extend", "1.17",   1990),  # брачность
    ("tom2", "R-02.docx", "2.14", "extend", "1.18",   1990),  # разводимость
    ("tom2", "R-02.docx", "2.15", "extend", "1.19",   1990),  # браки/разводы
    ("tom2", "R-03.docx", "3.2",  "extend", "2.3",    1990),  # занятые
    ("tom2", "R-03.docx", "3.10", "extend", "2.7",    1992),  # безработные
    ("tom2", "R-03.docx", "3.14", "extend", "2.8",    1992),  # зарег. безработные
    ("tom2", "R-03.docx", "3.15", "extend", "2.10.1", 1992),  # уровень безработицы
    ("tom2", "R-04-1.docx", "4.2",  "extend", "3.2",  1998),  # денежные доходы (руб)
    ("tom2", "R-04-1.docx", "4.3",  "extend", "3.4",  1998),  # зарплата (руб)
    ("tom2", "R-04-1.docx", "4.4",  "extend", "3.6",  1998),  # пенсии (руб)
    ("tom2", "R-04-1.docx", "4.5",  "extend", "3.7.1", 1990),  # пенсионеры
    ("tom2", "R-04-1.docx", "4.17", "extend", "3.17", 1990),  # автомобили на 1000
    ("tom2", "R-04-2.docx", "4.18", "extend", "3.18", 1990),  # мясо
    ("tom2", "R-04-2.docx", "4.19", "extend", "3.19", 1990),  # молоко
    ("tom2", "R-04-2.docx", "4.20", "extend", "3.20", 1990),  # яйца
    ("tom2", "R-04-2.docx", "4.21", "extend", "3.21", 1990),  # сахар
    ("tom2", "R-04-2.docx", "4.22", "extend", "3.22", 1990),  # растительное масло
    ("tom2", "R-04-2.docx", "4.25", "extend", "3.23", 1990),  # хлебные продукты
    ("tom2", "R-04-2.docx", "4.26", "extend", "3.24.1", 1990),  # жилищный фонд
    ("tom2", "R-04-2.docx", "4.28", "extend", "3.25", 1990),  # жильё на жителя
    # --- Преступность: новый раздел 22 (изд. 2018 = 2005-2017, TOM2 = 1990-2002) ---
    ("2018", "R_08.docx", "8.1", "new", {
        "code": "chislo-zaregistrirovannyh-prestupleniy-na-100000",
        "table_code": "22.1",
        "name": "Число зарегистрированных преступлений на 100 000 человек населения",
        "unit": "на 100 000 человек населения",
    }, 2005),
    ("tom2", "R-08.docx", "8.1", "new-merge", "chislo-zaregistrirovannyh-prestupleniy-na-100000", 1990),
    ("2018", "R_08.docx", "8.4", "new", {
        "code": "chislo-zaregistrirovannyh-ubiystv-i-pokusheniy-na-ubiystvo",
        "table_code": "22.2",
        "name": "Число зарегистрированных убийств и покушений на убийство",
        "unit": "случаев",
    }, 2005),
    ("tom2", "R-08.docx", "8.4", "new-merge", "chislo-zaregistrirovannyh-ubiystv-i-pokusheniy-na-ubiystvo", 1990),
    ("2018", "R_08.docx", "8.5", "new", {
        "code": "chislo-prestupleniy-nesovershennoletnih",
        "table_code": "22.3",
        "name": "Число преступлений, совершённых несовершеннолетними и при их соучастии",
        "unit": "случаев",
    }, 2005),
    ("tom2", "R-08.docx", "8.5", "new-merge", "chislo-prestupleniy-nesovershennoletnih", 1990),
    # изд. 2019 (последнее с разделом) добавляет 2018 год
    ("2019", "R_08.docx", "8.2", "new-merge", "chislo-prestupleniy-nesovershennoletnih", 2018),
]

CRIME_SECTION = (22, "Правонарушения")
CRIME_NOTE = (
    "Раздел исключён из актуальных выпусков сборника Росстата; ряд собран из "
    "архивных редакций (издания 2003 и 2018 годов, данные МВД России)."
)
EXTEND_NOTE = "История до 2000 года дособрана из архивной редакции сборника (издание 2003 года)."


def iter_blocks(doc):
    for child in doc.element.body.iterchildren():
        if child.tag.endswith("}p"):
            yield Paragraph(child, doc)
        elif child.tag.endswith("}tbl"):
            yield Table(child, doc)


def tables_by_heading(path: str) -> dict:
    """`N.M` -> список docx-таблиц под этим заголовком (куски одной таблицы)."""
    doc = docx.Document(path)
    out, cur = {}, None
    for block in iter_blocks(doc):
        if isinstance(block, Paragraph):
            m = HEAD_RE.match(norm_text(block.text))
            if m:
                cur = m.group(1)
                out.setdefault(cur, [])
        elif isinstance(block, Table) and cur is not None:
            out[cur].append(block)
    return out


def parse_word_table(chunks: list) -> tuple[dict, list]:
    """Куски таблицы -> ({(region_slug, year): value}, unresolved_names)."""
    points, unresolved = {}, []
    for t in chunks:
        rows = t.rows
        year_cols, header_rows = {}, 0
        for ri in range(min(3, len(rows))):
            cols = {}
            for ci, cell in enumerate(rows[ri].cells):
                m = YEAR_RE.match(norm_text(cell.text))
                if m and ci > 0:
                    cols[ci] = int(m.group(1))
            if len(set(cols.values())) >= 3:
                year_cols, header_rows = cols, ri + 1
                break
        if not year_cols:
            continue
        # дубликаты лет из merged-ячеек: берём первую колонку года
        seen = {}
        for ci in sorted(year_cols):
            seen.setdefault(year_cols[ci], ci)
        for row in rows[header_rows:]:
            cells = row.cells
            name = norm_text(cells[0].text)
            if not name or name.lower().startswith(("продолжение", "окончание")):
                continue
            slug, scale = resolve_region(name)
            if slug is None:
                if re.search(r"[а-яё]{4,}", name.lower()):
                    unresolved.append(name)
                continue
            for year, ci in seen.items():
                if ci >= len(cells):
                    continue
                v = parse_value(cells[ci].text, False)
                if v is None or v == "UNPARSED":
                    continue
                points[(slug, year)] = v * scale
    return points, unresolved


def cross_check(points: dict, existing: dict, code: str) -> tuple[bool, str]:
    """Сверка overlap-годов нового источника с артефактом (медиана |отн. расх.|)."""
    diffs = []
    for (slug, year), v in points.items():
        old = existing.get((code, slug, year))
        if old is None or old == 0:
            continue
        diffs.append(abs(v - old) / abs(old))
    if not diffs:
        return True, "overlap пуст (сверка невозможна)"
    med = statistics.median(diffs)
    return med <= 0.05, f"overlap {len(diffs)} тчк, медиана расхождения {med:.1%}"


def main():
    # конвертация DOC -> docx (кэшируется)
    for src, dst, names in [
        (TOM2_SRC, TOM2_DIR, ["R-02.DOC", "R-03.DOC", "R-04-1.DOC", "R-04-2.DOC", "R-08.DOC"]),
        (ED2018_SRC, ED2018_DIR, ["R_08.doc"]),
    ]:
        os.makedirs(dst, exist_ok=True)
        todo = [os.path.join(src, n) for n in names
                if not os.path.exists(os.path.join(dst, os.path.splitext(n)[0] + ".docx"))]
        if todo:
            subprocess.run([SOFFICE, "--headless", "--convert-to", "docx",
                            "--outdir", dst, *todo], check=True, capture_output=True)

    indicators = json.load(open(os.path.join(OUT_DIR, "indicators.json")))
    my_codes = {j[4]["code"] for j in JOBS if j[3] == "new"}
    indicators = [i for i in indicators if i["code"] not in my_codes]
    by_code = {i["code"]: i for i in indicators}
    # extend-цели адресуются table_code'ом 2025-артефакта; дубликаты table_code
    # от Excel-дособора (2022/2023) не в счёт
    by_table = {}
    for i in indicators:
        if "(2022)" in i.get("source_sheet", "") or "(2023)" in i.get("source_sheet", ""):
            continue
        by_table.setdefault(i["table_code"], i)

    existing = {}
    rows_all = []
    with gzip.open(os.path.join(OUT_DIR, "data.csv.gz"), "rt", encoding="utf-8") as fh:
        r = csv.reader(fh, delimiter=";")
        next(r)
        for code, rslug, year, value in r:
            if code in my_codes:
                continue
            y, v = int(year), float(value)
            rows_all.append([code, rslug, y, v])
            existing[(code, rslug, y)] = v
    # extend-джобы идемпотентны: снести ранее дописанные точки младше базового
    # года Excel-артефакта (2000) у целевых кодов
    extend_codes = {by_table[j[4]]["code"] for j in JOBS
                    if j[3] == "extend" and j[4] in by_table}
    rows_all = [r for r in rows_all if not (r[0] in extend_codes and r[2] < 2000)]
    existing = {k: v for k, v in existing.items()
                if not (k[0] in extend_codes and k[2] < 2000)}
    base_min = {}
    for code, _, y, _ in rows_all:
        if code not in base_min or y < base_min[code]:
            base_min[code] = y

    headings_cache = {}
    added_points, report = [], []
    for edition, fname, tab, mode, target, min_year in JOBS:
        path = os.path.join(EDITION_DIRS[edition], fname)
        key = (edition, fname)
        if key not in headings_cache:
            headings_cache[key] = tables_by_heading(path)
        chunks = headings_cache[key].get(tab)
        if not chunks:
            report.append(f"FAIL {edition}/{tab}: заголовок не найден")
            continue
        points, unresolved = parse_word_table(chunks)
        points = {k: v for k, v in points.items() if k[1] >= min_year}
        if not points:
            report.append(f"FAIL {edition}/{tab}: 0 точек")
            continue

        if mode == "extend":
            ind = by_table.get(target)
            if ind is None:
                report.append(f"FAIL {edition}/{tab}: нет цели {target}")
                continue
            tcode = ind["code"]
            ok, msg = cross_check(points, existing, tcode)
            if not ok:
                report.append(f"REJECT {edition}/{tab} -> {target}: {msg}")
                continue
            floor = base_min.get(tcode, ind["year_min"])
            new = {(s, y): v for (s, y), v in points.items() if y < floor}
            if not new:
                report.append(f"SKIP {edition}/{tab} -> {tcode}: нечего добавлять; {msg}")
                continue
            for (s, y), v in sorted(new.items()):
                rows_all.append([tcode, s, y, v])
            ind["year_min"] = min([y for _, y in new] + [floor])
            note = (ind.get("note") or "").strip()
            if EXTEND_NOTE not in note:
                if note and not note.endswith("."):
                    note += "."
                ind["note"] = f"{note} {EXTEND_NOTE}".strip()
            added_points.extend(new)
            report.append(f"OK {edition}/{tab} -> {tcode}: +{len(new)} тчк "
                          f"({min(y for _, y in new)}-{max(y for _, y in new)}); {msg}; "
                          f"unresolved={len(set(unresolved))}")
        else:  # new | new-merge
            code = target["code"] if mode == "new" else target
            if mode == "new":
                sec_num, sec_name = CRIME_SECTION
                ind = {
                    "code": code,
                    "table_code": target["table_code"],
                    "section_num": sec_num,
                    "section_name": sec_name,
                    "name": target["name"],
                    "unit": target["unit"],
                    "note": CRIME_NOTE,
                    "source_sheet": f"{fname} (изд. 2018) / табл. {tab}",
                    "year_min": 9999, "year_max": 0, "n_points": 0,
                }
                indicators.append(ind)
                by_code[code] = ind
            ind = by_code[code]
            fresh = {(s, y): v for (s, y), v in points.items()
                     if (code, s, y) not in existing}
            for (s, y), v in sorted(fresh.items()):
                rows_all.append([code, s, y, v])
                existing[(code, s, y)] = v
            years = [y for _, y in fresh]
            if years:
                ind["year_min"] = min(ind["year_min"], min(years))
                ind["year_max"] = max(ind["year_max"], max(years))
            ind["n_points"] += len(fresh)
            added_points.extend(fresh)
            report.append(f"OK {edition}/{tab} -> {code}: +{len(fresh)} тчк; "
                          f"unresolved={len(set(unresolved))}")
            if unresolved:
                report.append(f"     unresolved: {sorted(set(unresolved))[:6]}")

    with open(os.path.join(OUT_DIR, "indicators.json"), "w", encoding="utf-8") as fh:
        json.dump(indicators, fh, ensure_ascii=False, indent=1)
    with gzip.open(os.path.join(OUT_DIR, "data.csv.gz"), "wt", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(["indicator_code", "region_slug", "year", "value"])
        for row in rows_all:
            w.writerow(row)

    for line in report:
        print(line)
    print(f"\nдобавлено точек: {len(added_points)}; "
          f"итог: {len(indicators)} показателей, {len(rows_all)} точек")


if __name__ == "__main__":
    main()
