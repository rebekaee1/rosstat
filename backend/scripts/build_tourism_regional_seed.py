"""Снимок туризма по регионам из файлов, скачанных 20.11.2026 → ``app/data/regional/tourism_seed.csv.gz``.

Запуск (из ``backend``):

    .venv/bin/python -m scripts.build_tourism_regional_seed /путь/к/.artifacts/tourism-2026-11-20 [/путь/к/cbr]

Второй аргумент — папка с ``exp_YY.xlsx``/``imp_YY.xlsx`` Банка России за все годы (без него — только файлы a2).
Разбор — те же функции, что у живой загрузки (``app.services.tourism_regional_loader``). Печатает число точек по
рядам и незнакомые названия территорий.
"""

from __future__ import annotations

import gzip
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

from app.data.tourism_regional import emiss_datasets
from app.services import tourism_regional_loader as L


def main(root: Path, cbr_dir: Path | None, today: date) -> None:
    terr = L.Territories()
    points: list[L.Point] = []
    datasets = emiss_datasets()
    for dataset, series_list in datasets.items():
        seeded = [s for s in series_list if s.emiss.seed]
        if not seeded:
            continue
        a1 = root / "a1" / "raw" / "emiss" / f"{dataset}.csv.gz"
        a1_okved = root / "a1" / "raw" / "emiss_okved_I" / f"{dataset}_I.csv.gz"
        a3 = root / "a3" / "raw" / "emiss" / f"emiss_{dataset}.json"
        if a1.exists() or a1_okved.exists():
            text = gzip.decompress((a1 if a1.exists() else a1_okved).read_bytes()).decode("utf-8")
            rows = L.rows_from_csv(text)
        elif a3.exists():
            import json

            data = json.loads(a3.read_text(encoding="utf-8"))
            filters = data["meta"]["filters"]
            tdim = L.territory_dim_of({k: {"title": v["title"]} for k, v in filters.items()})
            periods = {oid: t for oid, t in filters.get("33560", {}).get("values", {}).items()}
            rows = L.rows_from_grid(data, territory_dim=tdim, period_titles=periods)
        else:
            print(f"ЕМИСС {dataset}: файла нет, пропуск")
            continue
        points += L.emiss_points(seeded, rows, terr, today=today)

    turpotok = root / "a1" / "raw" / "rosstat_turizm" / "Turpotok_2kv-2026.xlsx"
    points += L.turpotok_points(turpotok.read_bytes(), terr)

    fns = root / "a5" / "raw" / "fns" / "tourist_tax_regions_ytd.csv"
    points += L.fns_tax_points(L.fns_rows_from_csv(fns.read_text(encoding="utf-8")), terr)

    cbr_files = sorted((cbr_dir or (root / "a2" / "raw" / "cbr")).glob("*.xlsx"))
    cbr_points: list[L.Point] = []
    for f in cbr_files:
        kind = "exp" if f.name.startswith("exp") else "imp" if f.name.startswith("imp") else None
        if kind and ("services_reg" in f.name or cbr_dir is not None):
            cbr_points += L.cbr_points(f.read_bytes(), kind, terr)
    points += L.drop_zero_series(cbr_points)

    import csv

    with gzip.open(root / "a2" / "raw" / "fsa_hotels" / "fsa_hotels_registry.csv.gz", "rt", encoding="utf-8") as fh:
        records = list(csv.DictReader(fh, delimiter=";"))
    points += L.fsa_points(records, terr, today=today)

    import openpyxl

    ws = openpyxl.load_workbook(root / "a2" / "raw" / "minec_registry" / "subjects.xlsx", read_only=True).worksheets[0]
    inns = [r[3] for r in ws.iter_rows(min_row=2, values_only=True) if r and len(r) > 3]
    points += L.turagent_points(inns, today.year * 100 + today.month)
    tops = json.loads((root / "a2" / "raw" / "minec_registry" / "touroperators_2026-11-20.json").read_text("utf-8"))
    points += L.touroperator_points([t.get("ogrn") for t in tops["touroperators"]], today.year * 100 + today.month)

    sber = root / "a5" / "raw" / "sberindex" / "kolichestvo-vnutrennikh-turistov.csv"
    points += L.sber_points(sber.read_text(encoding="utf-8"), terr)

    n = L.write_seed(points)
    by_code = Counter(p[0] for p in points)
    for code, cnt in sorted(by_code.items()):
        print(f"{code:60s} {cnt}")
    print("точек:", n)
    if terr.unknown:
        print("незнакомые территории:", sorted(terr.unknown))


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]) if len(sys.argv) > 2 else None, date(2026, 11, 20))
