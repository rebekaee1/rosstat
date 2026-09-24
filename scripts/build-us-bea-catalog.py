#!/usr/bin/env python3
"""Build the reviewed US/state BEA catalog from official regional ZIP files.

This is an editorial operation, separate from the automatic observation refresh.
Translations are a checked-in static glossary; unknown BEA descriptions fail the
build instead of silently publishing English names in the Russian interface.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
import zipfile
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.world_bea_regional import (  # noqa: E402
    CATALOG_PATH, TABLES_BY_ARCHIVE, archive_url, catalog_code,
    clean_description, clean_geofips, numeric_points, table_file_names, table_rows,
)
from app.services.world_subnational_ingest import load_subnational_passport  # noqa: E402
from app.data.world_indicator_titles_ru import is_public_catalog_name  # noqa: E402


TABLE_LABELS = {
    "SASUMMARY": ("State economy", "Основные показатели экономики"),
    "SAGDP1": ("State GDP overview", "Состав ВВП"),
    "SAGDP2": ("GDP by industry, current dollars", "ВВП по отраслям, текущие цены"),
    "SAGDP3": ("Production taxes less subsidies by industry", "Налоги на производство за вычетом субсидий по отраслям"),
    "SAGDP4": ("Employee compensation by industry", "Оплата труда по отраслям"),
    "SAGDP5": ("Production subsidies by industry", "Субсидии производству по отраслям"),
    "SAGDP6": ("Production taxes by industry", "Налоги на производство и импорт по отраслям"),
    "SAGDP7": ("Operating surplus by industry", "Валовой операционный излишек по отраслям"),
    "SAGDP8": ("Real GDP index by industry", "Индекс реального ВВП по отраслям"),
    "SAGDP9": ("Real GDP by industry", "Реальный ВВП по отраслям"),
    "SAGDP11": ("Industry contribution to GDP growth", "Вклад отраслей в рост ВВП"),
    "SQGDP1": ("Quarterly state GDP", "Квартальный ВВП"),
    "SQGDP2": ("Quarterly GDP by industry", "Квартальный ВВП по отраслям"),
    "SQGDP8": ("Quarterly real GDP index", "Квартальный индекс реального ВВП"),
    "SQGDP9": ("Quarterly real GDP by industry", "Квартальный реальный ВВП по отраслям"),
    "SQGDP11": ("Quarterly industry contribution to GDP growth", "Квартальный вклад отраслей в рост ВВП"),
    "SAINC1": ("Personal income", "Доходы населения"),
    "SAINC4": ("Personal income components", "Состав доходов населения"),
    "SAINC5N": ("Income and earnings by industry", "Доходы и заработки по отраслям"),
    "SAINC6N": ("Employee compensation by industry", "Оплата труда по отраслям"),
    "SAINC7N": ("Wages and salaries by industry", "Заработная плата по отраслям"),
    "SAINC11": ("Earnings contributions to income change", "Вклад заработков отраслей в изменение доходов"),
    "SAINC12": ("Income change by component", "Изменение доходов по компонентам"),
    "SAINC30": ("State economic profile", "Экономический профиль"),
    "SAINC35": ("Transfer receipts", "Социальные выплаты и трансферты"),
    "SAINC40": ("Property income", "Доходы от собственности"),
    "SAINC50": ("Personal taxes", "Налоги населения"),
    "SAINC51": ("Disposable personal income", "Располагаемый доход населения"),
    "SAINC70": ("State and local pension plan transactions", "Пенсионные планы штатов и муниципалитетов"),
    "SQINC1": ("Quarterly personal income", "Квартальные доходы населения"),
    "SQINC4": ("Quarterly income components", "Квартальный состав доходов"),
    "SQINC5N": ("Quarterly earnings by industry", "Квартальные заработки по отраслям"),
    "SQINC6N": ("Quarterly employee compensation", "Квартальная оплата труда"),
    "SQINC7N": ("Quarterly wages and salaries by industry", "Квартальная заработная плата по отраслям"),
    "SQINC11": ("Quarterly earnings contributions to income change", "Квартальный вклад заработков в изменение доходов"),
    "SQINC12": ("Quarterly income change by component", "Квартальное изменение доходов по компонентам"),
    "SQINC35": ("Quarterly transfer receipts", "Квартальные социальные выплаты"),
    "SAPCE1": ("Household consumption", "Потребление домохозяйств"),
    "SAPCE2": ("Consumption per person", "Потребительские расходы на душу населения"),
    "SAPCE3": ("Consumption by product", "Потребление по видам товаров и услуг"),
    "SAPCE4": ("Consumption by function", "Потребительские расходы по функциям"),
    "SAPCE5": ("Contributions to consumption change", "Вклад категорий в изменение потребительских расходов"),
    "SARPP": ("Regional price parities", "Региональные уровни цен"),
    "SARPI": ("Real income and consumption", "Реальные доходы и потребление"),
    "SAIRPD": ("Regional price deflator", "Региональный дефлятор цен"),
}

UNIT_RU = {
    "Thousands of dollars": "тыс. долл.",
    "Millions of current dollars": "млн долл., текущие цены",
    "Millions of chained 2017 dollars": "млн долл. 2017 г.",
    "Millions of constant 2017 dollars": "млн долл. 2017 г.",
    "Millions of dollars": "млн долл.",
    "Constant 2017 dollars": "долл. 2017 г.",
    "Dollars": "долл.",
    "Number of persons": "человек",
    "Number of jobs": "рабочих мест",
    "Quantity index": "индекс",
    "Index": "индекс",
    "Percentage points": "п. п.",
    "Percent change": "%",
    "Ratio": "отношение",
}


def public_label_ru(translation: str) -> str:
    """Keep units in the unit field, not twice in the visible indicator title."""
    label = re.sub(
        r" \((?:тыс\. долл\.|млн долл\.), с сезонной корректировкой\)$",
        " (с сезонной корректировкой)", translation,
    )
    label = re.sub(r" \(млн долл\. 2017 г\., цепная оценка\)$", " (цепная оценка)", label)
    return re.sub(
        r" \((?:тыс\. долл\.|млн долл\.|долл\.|млн долл\. 2017 г\.|"
        r"в миллионах долларов|в ценах 2017 г\.)\)$",
        "", label,
    )


def zip_path(root: Path, archive: str) -> Path:
    return root / f"fe-bea-{archive}.zip"


def download_archives(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    with requests.Session() as session:
        for archive in TABLES_BY_ARCHIVE:
            path = zip_path(root, archive)
            if path.is_file() and zipfile.is_zipfile(path):
                continue
            print(f"download {archive} from {archive_url(archive)}", file=sys.stderr)
            with session.get(archive_url(archive), stream=True, timeout=(10, 120)) as response:
                response.raise_for_status()
                with path.open("wb") as out:
                    for chunk in response.iter_content(1024 * 1024):
                        if chunk:
                            out.write(chunk)
            if not zipfile.is_zipfile(path):
                path.unlink(missing_ok=True)
                raise ValueError(f"invalid BEA ZIP: {archive}")


def candidates(root: Path) -> list[dict]:
    states = {f"{r.fips}000" for r in load_subnational_passport("us").regions}
    samples = {"00000", "06000", "36000"}
    out = []
    for archive in TABLES_BY_ARCHIVE:
        with zipfile.ZipFile(zip_path(root, archive)) as bundle:
            for table, member in table_file_names(bundle, archive).items():
                by_line: dict[str, dict] = {}
                for row in table_rows(bundle, member):
                    geo = clean_geofips(row["GeoFIPS"])
                    if geo not in states and geo != "00000":
                        continue
                    line = row["LineCode"].strip()
                    points = numeric_points(row)
                    if not points:
                        continue
                    item = by_line.setdefault(line, {
                        "archive": archive, "table": table, "line": line,
                        "description_en": clean_description(row.get("Description")),
                        "unit": (row.get("Unit") or "").strip(),
                        "industry_code": (row.get("IndustryClassification") or "").strip(),
                        "states": set(), "samples": {},
                    })
                    if geo in states and len(points) >= 3:
                        item["states"].add(geo)
                    if geo in samples:
                        item["samples"][geo] = tuple(points)
                for item in by_line.values():
                    sample = item["samples"]
                    national = sample.get("00000", ())
                    if len(item["states"]) < 45 or len(national) < 3:
                        continue
                    # An all-zero accounting line is not a useful public series.
                    if not any(value != 0 for _, value in national):
                        continue
                    if "06000" not in sample or "36000" not in sample:
                        continue
                    item["frequency"] = "quarterly" if any(p.month != 1 for p, _ in sample["00000"]) else "annual"
                    item["history_floor"] = str(sample["00000"][0][0].year)
                    out.append(item)
    # Exact data duplicates across BEA tables are one public indicator.
    # Prefer longer history and a detailed table over a summary table.
    out.sort(key=lambda row: (
        -len(row["samples"]["00000"]),
        row["table"] in {"SASUMMARY", "SAGDP1", "SQGDP1", "SAINC1", "SQINC1", "SAPCE1"},
        row["table"], int(row["line"]),
    ))
    seen: set[tuple] = set()
    selected = []
    for row in out:
        key = (
            row["frequency"], row["unit"],
            tuple(row["samples"][geo] for geo in ("00000", "06000", "36000")),
        )
        if key in seen:
            continue
        seen.add(key)
        selected.append(row)
    return sorted(selected, key=lambda row: (row["archive"], row["table"], int(row["line"])))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive-dir", type=Path, default=Path(tempfile.gettempdir()))
    parser.add_argument("--translations", type=Path, default=ROOT / "backend/app/data/world_bea_regional/description_ru.json")
    parser.add_argument("--output", type=Path, default=CATALOG_PATH)
    parser.add_argument("--descriptions-out", type=Path)
    args = parser.parse_args()
    download_archives(args.archive_dir)
    selected = candidates(args.archive_dir)
    print(f"eligible nonduplicate series: {len(selected)}", file=sys.stderr)
    descriptions = sorted({row["description_en"] for row in selected})
    if args.descriptions_out:
        args.descriptions_out.write_text(json.dumps(descriptions, ensure_ascii=False, indent=2) + "\n")
        return
    translations = json.loads(args.translations.read_text(encoding="utf-8"))
    missing = set(descriptions) - translations.keys()
    if missing:
        raise ValueError(f"{len(missing)} BEA descriptions need Russian review: {sorted(missing)[:8]}")
    series = []
    for row in selected:
        table = row["table"]
        desc = row["description_en"]
        prefix_en, prefix_ru = TABLE_LABELS[table]
        unit = row["unit"]
        if unit not in UNIT_RU:
            raise ValueError(f"unknown BEA unit: {unit}")
        code = catalog_code(table, row["line"])
        freq_en = "quarterly" if row["frequency"] == "quarterly" else "annual"
        freq_ru = "ежеквартально" if freq_en == "quarterly" else "ежегодно"
        industry = row["industry_code"]
        industry_tag_en = f" (NAICS {industry})" if industry not in ("", "...") else ""
        industry_tag_ru = f" (код отрасли {industry})" if industry not in ("", "...") else ""
        name_en = f"{prefix_en}: {desc}{industry_tag_en}"[:400]
        name_ru = f"{prefix_ru}: {public_label_ru(translations[desc])}{industry_tag_ru}"[:400]
        if not is_public_catalog_name(name_ru):
            raise ValueError(f"BEA Russian name would be hidden from catalog: {name_ru}")
        methodology_ru = (
            f"Официальная оценка Бюро экономического анализа США. Публикуется {freq_ru}; "
            f"единица измерения — {UNIT_RU[unit]}. Загружается вся доступная история и последующие пересмотры."
        )
        methodology_en = (
            f"Official U.S. Bureau of Economic Analysis estimate, published {freq_en}. "
            f"Unit: {unit}. The full available history and subsequent revisions are loaded."
        )
        if "chained" in unit.lower():
            methodology_ru += " Цепные стоимостные оценки разных отраслей не обязательно суммируются в общий итог."
            methodology_en += " Chained-dollar industry values do not necessarily sum to the total."
        series.append({
            "archive": row["archive"], "table": table, "line": row["line"],
            "code": code, "national_code": f"us-{code}",
            "name_en": name_en, "name_ru": name_ru,
            "section_en": prefix_en, "section_ru": prefix_ru,
            "unit": unit, "unit_ru": UNIT_RU[unit],
            "frequency": row["frequency"],
            "source_url": archive_url(row["archive"]),
            "description_en": f"{desc}. Official U.S. BEA regional economic accounts.",
            "description_ru": f"{translations[desc]}. Официальные региональные экономические счета США.",
            "methodology_en": methodology_en,
            "methodology_ru": methodology_ru,
            "history_floor": row["history_floor"],
        })
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"country_code": "US", "series": series}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(series)} indicators to {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
