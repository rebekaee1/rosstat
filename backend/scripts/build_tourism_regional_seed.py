"""Снимок туризма по регионам из файлов, скачанных 20.11.2026 → ``app/data/regional/tourism_seed.csv.gz``.

Запуск (из ``backend``):

    .venv/bin/python -m scripts.build_tourism_regional_seed /путь/к/.artifacts/tourism-2026-11-20 [/путь/к/cbr]

Второй аргумент — папка с ``exp_YY.xlsx``/``imp_YY.xlsx`` Банка России за все годы (без него — только файлы a2).
Разбор — те же функции, что у живой загрузки (``app.services.tourism_regional_loader``). Печатает число точек по
рядам и незнакомые названия территорий.
"""

from __future__ import annotations

import csv
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
        # 21.11.2026: очередь a1 докачала ЕМИСС — в снимок идут все наборы, для которых есть выгрузка; масштаб —
        # по единице выгрузки (как у живой загрузки), другая единица — набор пропускается.
        meta_path = root / "a1" / "raw" / "emiss" / f"{dataset}.meta.json"
        unit = json.loads(meta_path.read_text("utf-8")).get("unit", "") if meta_path.exists() else ""
        seeded = L.series_for_unit(series_list, unit)
        if not seeded:
            print(f"ЕМИСС {dataset}: единица {unit!r} не совпала с реестром, пропуск")
            continue
        a1 = root / "a1" / "raw" / "emiss" / f"{dataset}.csv.gz"
        a1_okved = root / "a1" / "raw" / "emiss_okved_I" / f"{dataset}_I.csv.gz"
        a3 = root / "a3" / "raw" / "emiss" / f"emiss_{dataset}.json"
        if a1.exists() or a1_okved.exists():
            text = gzip.decompress((a1 if a1.exists() else a1_okved).read_bytes()).decode("utf-8")
            rows = L.rows_from_csv(text)
        elif a3.exists():

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

    # Сборщик c4 (20.11.2026): курортный сбор, «Туризм в России» 2024, tochno.st, средние цены туруслуг.
    c4 = root / "c4" / "raw"
    points += L.kurort_points((c4 / "kurort_sbor" / "kurort_tour_tax_treasury_2018_2025.csv").read_text("utf-8"), terr)
    merged = {(c, s, p): v for c, s, p, v in L.tur_rus_points(
        (c4 / "rosstat_pub" / "R5-tur_wb20250201.xlsx").read_bytes(), terr)}
    with open(c4 / "tochno_st" / "tochno_tourism_filtered.csv", encoding="utf-8") as fh:
        merged.update({(c, s, p): v for c, s, p, v in L.tochno_points(csv.DictReader(fh, delimiter=";"), terr)})
    points += [(c, s, p, v) for (c, s, p), v in merged.items()]
    best: dict[tuple[str, str, int], tuple[int, float]] = {}
    for rank, name in enumerate(("sred_potreb_cen_09-2026.xlsx", "sred_potreb_cen_2025_wb.xlsx",
                                 "sred_potreb_cen_2024_wb.xlsx", "sred_potreb_cen_09-2023_wb.xlsx",
                                 "sred_potreb_cen_2022_wb.xlsx")):
        for (c, s, p, v), r in L.price_points((c4 / "rosstat_price" / name).read_bytes(), terr, rank):
            if (c, s, p) not in best or r < best[(c, s, p)][0]:
                best[(c, s, p)] = (r, v)
    points += [(c, s, p, v) for (c, s, p), (_r, v) in best.items()]
    points += L.occupancy_points(points)

    # Добор g1 (21.11.2026): выгрузки ЕМИСС через стенд (оборот, работники, инвестиции), реестр МСП, ИПЦ 31074.
    # Средние цены 31448 в снимок не идут: на боевом их история с 2000 года уже есть (загрузчик цен), а 2022–2026 —
    # в снимке из файлов Росстата (c4); недостающие месяцы до 2022 года на боевом не найдены.
    g1 = root / "g1" / "out"
    from app.data import tourism_regional as R

    specs = {
        "tour-oborot-gostinicy-mes": ("57710", f"{R._LARGE_SMALL}, {R._HOTELS}"),
        "tour-oborot-turagentstva-mes": ("57710", f"{R._LARGE_SMALL}, {R._AGENCIES}"),
        "obshchepit-oborot-organizaciy-mes": ("57710", f"{R._LARGE_SMALL}, {R._FOOD}"),
        "tour-rabotniki-gostinicy-mes": ("57848", R._HOTELS),
        "tour-rabotniki-turagentstva-mes": ("57848", R._AGENCIES),
        "tour-investicii-gostinicy": ("59084", f"{R._HOTELS}, {R._INVEST_SCOPE}"),
        "tour-investicii-sanatorii": ("59084", f"{R._SANATORIUMS}, {R._INVEST_SCOPE}"),
    }
    for dataset in sorted({d for d, _s in specs.values()}):
        with gzip.open(g1 / f"emiss_{dataset}_tidy.csv.gz", "rt", encoding="utf-8") as fh:
            points += L.g1_points(csv.DictReader(fh, delimiter=";"),
                                  {c: suf for c, (d, suf) in specs.items() if d == dataset}, terr)
    with open(g1 / "msp_rsmp_tourism_tidy.csv", encoding="utf-8") as fh:
        points += L.msp_points(csv.DictReader(fh, delimiter=";"), terr)

    # ИПЦ 31074 (35 позиций, 2002-01…2026-09): боевому fedstat отвечает 403 (21.11.2026), поэтому история — снимком;
    # снимок пишет только недостающее, живая загрузка дальше идёт от последнего года (``_last_years``) и дописывает
    # новые месяцы. Вид индекса — «к соответствующему периоду предыдущего года».
    cpi_specs = {s.code: tuple(f"{label}, {kind}" for label, kind in s.emiss.match)
                 for s in R.SERIES if s.emiss is not None and s.emiss.dataset == 31074}
    with gzip.open(g1 / "emiss_31074_tidy.csv.gz", "rt", encoding="utf-8") as fh:
        points += L.g1_points(csv.DictReader(fh, delimiter=";"), cpi_specs, terr)

    # Добор g2 (20.11.2026): оценки турпотока регионов с методикой и открытые данные Москвы.
    g2 = root / "g2"
    with open(g2 / "regions" / "tidy.csv", encoding="utf-8") as fh:
        flow, meta = L.regional_flow_points(csv.DictReader(fh, delimiter=";"), terr)
    points += flow
    with open(g2 / "tidy" / "moscow_opendata_tidy.csv", encoding="utf-8") as fh:
        points += L.moscow_points(csv.DictReader(fh, delimiter=";"))
    # Методика регионов — вручную в app/data/regional/tourism_region_methods.json (публичный текст ru/en);
    # здесь только сверка: годы разрывов, найденные по данным, должны быть отмечены и там.
    curated = json.loads((Path(L.__file__).resolve().parents[1] / "data" / "regional" /
                          "tourism_region_methods.json").read_text("utf-8"))
    for slug, m in meta.items():
        missing = set(m["breaks"]) - set(curated.get(slug, {}).get("breaks", []))
        if slug not in curated or missing:
            print(f"методика {slug}: нет описания или не отмечены разрывы {sorted(missing)}")

    n = L.write_seed(points)
    by_code = Counter(p[0] for p in points)
    for code, cnt in sorted(by_code.items()):
        print(f"{code:60s} {cnt}")
    print("точек:", n)
    if terr.unknown:
        print("незнакомые территории:", sorted(terr.unknown))


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]) if len(sys.argv) > 2 else None, date(2026, 11, 20))
