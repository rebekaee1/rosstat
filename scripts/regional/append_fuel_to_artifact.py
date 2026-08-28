"""Досеивание топливных показателей ЕМИСС в региональный артефакт.

Источник — fuel_points.csv из fetch_emiss_fuel.py (ЕМИСС: потребительские
цены 31448 помесячно; розница дизтоплива 57699 по 2021; опт 59002 за 2017).
Годовые ряды (розница/опт) дописываются в data.csv.gz как обычные годовые
точки; помесячные цены живут отдельным слоем fuel_points.csv и грузятся
сидером в region_monthly_data (миграция 20260827_region_monthly_points,
ADR-0008 «Subsequent additions»).

Шаг досеивания: годовые ряды → data.csv.gz; метаданные всех топливных
показателей (включая помесячные цены) → indicators.json. Идемпотентно:
повторный запуск не создаёт дублей (ключ indicator_code+region_slug+year).

Запуск: python3 scripts/regional/append_fuel_to_artifact.py
"""

import csv
import gzip
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ART_DIR = os.path.join(HERE, "..", "..", "backend", "app", "data", "regional")
FUEL_CSV = os.path.join(ART_DIR, "fuel_points.csv")

# Период YYYYMM → годовой ряд не конвертируется: месячные цены остаются
# в fuel_points.csv. В data.csv.gz (годовая сетка) попадают только ряды
# с целочисленным периодом-годом.
ANNUAL_CODES = {"roznica-dt", "opt-benzin", "opt-dt"}

# Помесячные коды (слой region_monthly_data): метаданные идут в indicators.json,
# точки остаются в fuel_points.csv → seed_regional читает их оттуда напрямую.
MONTHLY_CODES = {"ceni-ai92", "ceni-ai95", "ceni-dt"}

# Новые записи каталога показателей (раздел 16 «Транспорт», продолжение
# нумерации таблиц сборника — 16.20+, чтобы не пересекаться с 16.1–16.12).
FUEL_INDICATORS = [
    {
        "code": "ceni-ai92",
        "table_code": "16.20",
        "section_num": 16,
        "section_name": "Транспорт",
        "name": "Потребительские цены на бензин АИ-92, рублей за литр",
        "unit": "рубль за литр",
        "note": "Средние потребительские цены по субъекту, конец месяца. Частота — месячная.",
        "source_sheet": "ЕМИСС, витрина 31448",
        "frequency": "monthly",
    },
    {
        "code": "ceni-ai95",
        "table_code": "16.21",
        "section_num": 16,
        "section_name": "Транспорт",
        "name": "Потребительские цены на бензин АИ-95, рублей за литр",
        "unit": "рубль за литр",
        "note": "Средние потребительские цены по субъекту, конец месяца. Частота — месячная.",
        "source_sheet": "ЕМИСС, витрина 31448",
        "frequency": "monthly",
    },
    {
        "code": "ceni-dt",
        "table_code": "16.22",
        "section_num": 16,
        "section_name": "Транспорт",
        "name": "Потребительские цены на дизельное топливо, рублей за литр",
        "unit": "рубль за литр",
        "note": "Средние потребительские цены по субъекту, конец месяца. Частота — месячная.",
        "source_sheet": "ЕМИСС, витрина 31448",
        "frequency": "monthly",
    },
    {
        "code": "roznica-dt",
        "table_code": "16.23",
        "section_num": 16,
        "section_name": "Транспорт",
        "name": "Розничные продажи дизельного топлива, тыс. рублей",
        "unit": "тысяча рублей",
        "note": "Годовые данные публикуются по 2021 год включительно.",
        "source_sheet": "ЕМИСС, витрина 57699 (ОКПД2 1700657, январь–декабрь)",
    },
    {
        "code": "opt-benzin",
        "table_code": "16.24",
        "section_num": 16,
        "section_name": "Транспорт",
        "name": "Оптовые продажи автомобильного бензина, тысяч тонн",
        "unit": "тысяч тонн",
        "note": "Публикуется за 2017 год. Поставки, не потребление.",
        "source_sheet": "ЕМИСС, витрина 59002 (ОКПД2 1704128)",
    },
    {
        "code": "opt-dt",
        "table_code": "16.25",
        "section_num": 16,
        "section_name": "Транспорт",
        "name": "Оптовые продажи дизельного топлива, тысяч тонн",
        "unit": "тысяч тонн",
        "note": "Публикуется за 2017 год. Поставки, не потребление.",
        "source_sheet": "ЕМИСС, витрина 59002 (ОКПД2 1692982)",
    },
]


def main():
    rows = list(csv.reader(open(FUEL_CSV, encoding="utf-8"), delimiter=";"))
    header, data = rows[0], rows[1:]

    inds = json.load(open(os.path.join(ART_DIR, "indicators.json"), encoding="utf-8"))
    known = {i["code"] for i in inds}

    annual_points = []
    monthly_points = []
    added_codes = set()
    for code, slug, period, value in data:
        period = str(period)
        if code in MONTHLY_CODES:
            if len(period) == 6 and period.isdigit():
                monthly_points.append((code, slug, int(period), float(value)))
                added_codes.add(code)
            continue
        if code not in ANNUAL_CODES:
            continue
        if "." in period or len(period) != 4:
            continue
        annual_points.append((code, slug, int(period), float(value)))
        added_codes.add(code)

    # каталог: месячные считаются по своим точкам, годовые по своим
    def span(code, pts):
        sel = [k for c, _s, k, _v in pts if c == code]
        return (min(sel), max(sel), len(sel)) if sel else (None, None, 0)

    if added_codes:
        known_before = set(known)
        for ind in FUEL_INDICATORS:
            if ind["code"] not in added_codes:
                continue
            pts = monthly_points if ind["code"] in MONTHLY_CODES else annual_points
            y_min, y_max, n = span(ind["code"], pts)
            inds.append({
                **ind,
                "year_min": y_min,
                "year_max": y_max,
                "n_points": n,
            })
        with open(os.path.join(ART_DIR, "indicators.json"), "w", encoding="utf-8") as fh:
            json.dump(inds, fh, ensure_ascii=False, indent=1)
        fresh = added_codes - known_before
        print(f"indicators.json: +{len(fresh)} новых записей, обновлены метаданные "
              f"{len(added_codes)} топливных (раздел 16)")

    # дозапись точек в data.csv.gz с дедупликацией по (code, slug, year)
    existing = set()
    with gzip.open(os.path.join(ART_DIR, "data.csv.gz"), "rt", encoding="utf-8") as fh:
        reader = csv.reader(fh, delimiter=";")
        out_rows = [next(reader)]
        for code, slug, year, value in reader:
            existing.add((code, slug, year))
            out_rows.append([code, slug, year, value])

    n_new = 0
    for code, slug, year, value in annual_points:
        key = (code, slug, str(year))
        if key in existing:
            continue
        out_rows.append([code, slug, str(year), value])
        existing.add(key)
        n_new += 1

    with gzip.open(os.path.join(ART_DIR, "data.csv.gz"), "wt", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerows(out_rows)

    print(f"data.csv.gz: +{n_new} точек (всего строк {len(out_rows) - 1})")


if __name__ == "__main__":
    main()
