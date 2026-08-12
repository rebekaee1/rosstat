#!/usr/bin/env python3
"""Аудит under-sliced Eurostat: headline/TOTAL вместо реальной разбивки.

Критерий (класс ilc_di04 / hhcomp):
  Eurostat отдаёт измерение D с ≥2 не-TOTALISH членами (или ≥1 не-TOTALISH
  при нашем TOTALISH pin), а в нашей БД по dataset_id на D ≤1 distinct value
  (или dim отсутствует → подразумевается TOTALISH).

Исключаемые измерения: geo, time, time_period, freq.
TOTALISH (case-insensitive): TOTAL, TOT, T, ALL, NSP;
  age: + Y15-74; coicop / coicop18: + CP00.

covered_by_deep=yes — dim варьируется в DEEP_DATASET_SLICES и в БД уже ≥2
значений → не mismatch, но строка в datasets-файле остаётся для полноты.

Запуск::

    docker compose cp backend/scripts/audit-world-eurostat-underslice.py \\
        backend:/app/scripts/
    docker compose exec -T backend python /app/scripts/audit-world-eurostat-underslice.py
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, "/app")

from sqlalchemy import select  # noqa: E402

from app.data.eurostat_listing import DEEP_DATASET_SLICES  # noqa: E402
from app.database import async_session  # noqa: E402
from app.models import WorldCountry, WorldIndicator  # noqa: E402
from app.services.eurostat_parser import (  # noqa: E402
    build_data_url,
    extract_dimensions,
    http_get_json,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("audit-world-eurostat-underslice")

SKIP_DIMS = frozenset({"geo", "time", "time_period", "freq"})
TOTALISH_BASE = frozenset({"TOTAL", "TOT", "T", "ALL", "NSP"})

# Внутри контейнера /tmp → наружу копируем в docs/research/
OUT_DIR_CANDIDATES = (
    Path("/tmp/eurostat-underslice"),
    Path("/app/scripts/../..") / "docs" / "research",  # не смонтирован
    Path(__file__).resolve().parents[2] / "docs" / "research",
)


def is_totalish(dim: str, member: str) -> bool:
    m = (member or "").strip().upper()
    if m in TOTALISH_BASE:
        return True
    d = (dim or "").strip().lower()
    if d == "age" and m == "Y15-74":
        return True
    if d in {"coicop", "coicop18"} and m == "CP00":
        return True
    return False


def non_totalish_members(dim: str, members: list[str]) -> list[str]:
    return [m for m in members if not is_totalish(dim, m)]


def deep_values_for_dim(dataset_id: str, dim: str) -> set[str]:
    specs = DEEP_DATASET_SLICES.get(dataset_id.lower()) or []
    vals: set[str] = set()
    for spec in specs:
        for k, v in spec.items():
            if k.lower() == dim.lower() and v is not None:
                vals.add(str(v))
    return vals


def fetch_structure_cached(dataset_id: str) -> tuple[str, dict[str, list[str]] | None, str | None]:
    """Return (dataset_id, dims|None, error|None). Uses disk cache via http_get_json."""
    try:
        url = build_data_url(dataset_id, {}, last_time_period=1)
        payload = http_get_json(url, use_cache=True)
        dims = extract_dimensions(payload)
        return dataset_id, dims, None
    except Exception as exc:  # noqa: BLE001
        return dataset_id, None, str(exc)


def compact_slice(slice_json: dict | None) -> str:
    if not slice_json:
        return "{}"
    # freq можно опустить для компактности — но пользователь просил our_slice_json_compact
    try:
        return json.dumps(slice_json, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    except (TypeError, ValueError):
        return str(slice_json)


def pick_out_dir() -> Path:
    # Всегда пишем в /tmp внутри контейнера — оттуда копируем на хост.
    p = Path("/tmp/eurostat-underslice")
    p.mkdir(parents=True, exist_ok=True)
    return p


async def load_indicators() -> tuple[
    list[tuple[str, str, str, str, str, dict | None]],
    dict[str, list[dict | None]],
]:
    """Return indicator rows and dataset_id → list of slice_json."""
    async with async_session() as db:
        q = (
            select(
                WorldIndicator,
                WorldCountry.slug,
                WorldCountry.name_ru,
            )
            .join(WorldCountry, WorldIndicator.country_id == WorldCountry.id)
            .where(WorldIndicator.provider == "eurostat")
        )
        rows = (await db.execute(q)).all()

    indicators: list[tuple[str, str, str, str, str, dict | None]] = []
    by_dataset: dict[str, list[dict | None]] = defaultdict(list)
    for ind, slug, cname in rows:
        indicators.append(
            (slug, cname, ind.code, ind.dataset_id, ind.name_ru, ind.slice_json)
        )
        by_dataset[ind.dataset_id].append(ind.slice_json)
    return indicators, dict(by_dataset)


def db_dim_values(slices: list[dict | None], dim: str) -> set[str]:
    vals: set[str] = set()
    dim_l = dim.lower()
    for sl in slices:
        if not isinstance(sl, dict):
            continue
        for k, v in sl.items():
            if k.lower() == dim_l and v is not None and str(v).strip() != "":
                vals.add(str(v))
    return vals


def analyze_dataset(
    dataset_id: str,
    dims: dict[str, list[str]],
    slices: list[dict | None],
) -> list[dict]:
    """Return list of dim findings (mismatch and/or covered_by_deep)."""
    findings: list[dict] = []
    for dim, members in dims.items():
        if dim.lower() in SKIP_DIMS:
            continue
        non_tot = non_totalish_members(dim, members)
        db_vals = db_dim_values(slices, dim)
        deep_vals = deep_values_for_dim(dataset_id, dim)

        # We pinned TOTALISH if every DB value is totalish, or dim missing entirely.
        pinned_totalish = False
        if not db_vals:
            pinned_totalish = True  # missing D → TOTALISH implied
        elif all(is_totalish(dim, v) for v in db_vals):
            pinned_totalish = True

        eurostat_breakdown = len(non_tot) >= 2 or (len(non_tot) >= 1 and pinned_totalish)
        if not eurostat_breakdown:
            continue

        covered_by_deep = len(deep_vals) >= 2 and len(db_vals) >= 2
        is_mismatch = len(db_vals) <= 1 and not covered_by_deep
        # Criterion 6: deep covers + DB ≥2 → list but NOT mismatch
        if covered_by_deep:
            is_mismatch = False

        if not is_mismatch and not covered_by_deep:
            # No mismatch and not deep-covered listing target — skip
            # (eurostat has breakdown but somehow we have ≥2 without deep? still under-interest)
            # User: under-sliced if db ≤1. If db ≥2 without deep — not under-sliced, don't list.
            if len(db_vals) >= 2:
                continue

        missing = [m for m in non_tot if m not in db_vals][:8]
        findings.append(
            {
                "dataset_id": dataset_id,
                "dim": dim,
                "eurostat_n_non_total": len(non_tot),
                "db_values": sorted(db_vals) if db_vals else [],
                "db_n": len(db_vals),
                "example_missing": missing,
                "covered_by_deep": "yes" if covered_by_deep else "no",
                "is_mismatch": is_mismatch,
            }
        )
    return findings


HEADER_DATASETS = """\
# Аудит under-sliced Eurostat — датасеты × измерения
#
# Критерий mismatch: у Eurostat на измерении D есть реальная разбивка
# (≥2 не-TOTALISH члена ИЛИ ≥1 не-TOTALISH при нашем TOTALISH pin), а в БД
# по dataset_id distinct-значений D ≤ 1 (или dim отсутствует).
# Исключены: geo, time, time_period, freq.
# TOTALISH: TOTAL, TOT, T, ALL, NSP; age+Y15-74; coicop/coicop18+CP00.
# covered_by_deep=yes — dim уже варьируется в DEEP_DATASET_SLICES и в БД ≥2
# значений → не mismatch (строка информационная).
#
# Формат: dataset_id | dim | eurostat_n_non_total | db_values | example_missing(≤8) | covered_by_deep | mismatch
#
"""

HEADER_INDICATORS = """\
# Аудит under-sliced Eurostat — индикаторы стран в under-sliced датасетах
#
# Строка на каждую пару country×indicator, чей dataset_id имеет хотя бы одно
# mismatch-измерение (см. eurostat-underslice-datasets.txt).
# missing_breakdown_dims — список dim с is_mismatch=yes.
#
# Формат: country_slug | country_name | indicator_code | dataset_id | name_ru | our_slice_json_compact | missing_breakdown_dims
#
"""


async def main() -> int:
    t0 = time.time()
    log.info("loading world indicators (provider=eurostat) …")
    indicators, by_dataset = await load_indicators()
    dataset_ids = sorted(by_dataset.keys())
    log.info(
        "loaded %d indicators across %d datasets",
        len(indicators),
        len(dataset_ids),
    )

    structures: dict[str, dict[str, list[str]]] = {}
    errors: dict[str, str] = {}
    done = 0
    with ThreadPoolExecutor(max_workers=8) as pool:
        futs = {pool.submit(fetch_structure_cached, ds): ds for ds in dataset_ids}
        for fut in as_completed(futs):
            ds_id, dims, err = fut.result()
            done += 1
            if err:
                errors[ds_id] = err
            elif dims is not None:
                structures[ds_id] = dims
            if done % 50 == 0 or done == len(dataset_ids):
                log.info(
                    "structure progress %d/%d (ok=%d err=%d)",
                    done,
                    len(dataset_ids),
                    len(structures),
                    len(errors),
                )

    all_findings: list[dict] = []
    mismatch_by_dataset: dict[str, list[str]] = defaultdict(list)
    for ds_id in dataset_ids:
        if ds_id in errors:
            continue
        dims = structures.get(ds_id) or {}
        findings = analyze_dataset(ds_id, dims, by_dataset[ds_id])
        for f in findings:
            all_findings.append(f)
            if f["is_mismatch"]:
                mismatch_by_dataset[ds_id].append(f["dim"])

    out_dir = pick_out_dir()
    datasets_path = out_dir / "eurostat-underslice-datasets.txt"
    indicators_path = out_dir / "eurostat-underslice-indicators.txt"

    # datasets file: mismatches first, then covered_by_deep informational
    lines_ds: list[str] = [HEADER_DATASETS]
    # ERROR datasets
    for ds_id in sorted(errors):
        err = errors[ds_id].replace("\n", " ")[:200]
        lines_ds.append(f"{ds_id} | ERROR | 0 | [] | {err} | no | error\n")

    mismatch_findings = [f for f in all_findings if f["is_mismatch"]]
    covered_findings = [f for f in all_findings if f["covered_by_deep"] == "yes"]

    def fmt_finding(f: dict) -> str:
        db_repr = ",".join(f["db_values"]) if f["db_values"] else "(missing)"
        miss = ",".join(f["example_missing"]) if f["example_missing"] else "-"
        mm = "yes" if f["is_mismatch"] else "no"
        return (
            f"{f['dataset_id']} | {f['dim']} | {f['eurostat_n_non_total']} | "
            f"{db_repr} | {miss} | {f['covered_by_deep']} | {mm}\n"
        )

    for f in sorted(mismatch_findings, key=lambda x: (x["dataset_id"], x["dim"])):
        lines_ds.append(fmt_finding(f))
    for f in sorted(covered_findings, key=lambda x: (x["dataset_id"], x["dim"])):
        # avoid duplicate if somehow both (shouldn't happen)
        if f["is_mismatch"]:
            continue
        lines_ds.append(fmt_finding(f))

    datasets_path.write_text("".join(lines_ds), encoding="utf-8")

    under_sliced_ds = set(mismatch_by_dataset.keys())
    lines_ind: list[str] = [HEADER_INDICATORS]
    ind_count = 0
    for slug, cname, code, ds_id, name_ru, slice_json in sorted(
        indicators, key=lambda r: (r[0], r[3], r[2])
    ):
        if ds_id not in under_sliced_ds:
            continue
        dims_miss = ",".join(sorted(mismatch_by_dataset[ds_id]))
        name_safe = (name_ru or "").replace("|", "/").replace("\n", " ")
        lines_ind.append(
            f"{slug} | {cname} | {code} | {ds_id} | {name_safe} | "
            f"{compact_slice(slice_json)} | {dims_miss}\n"
        )
        ind_count += 1

    indicators_path.write_text("".join(lines_ind), encoding="utf-8")

    n_mismatch_ds = len(under_sliced_ds)
    n_mismatch_dims = len(mismatch_findings)
    n_covered = len(covered_findings)
    elapsed = time.time() - t0

    print("=== SUMMARY ===")
    print(f"indicators_total:          {len(indicators)}")
    print(f"datasets_total:            {len(dataset_ids)}")
    print(f"structure_ok:              {len(structures)}")
    print(f"structure_error:           {len(errors)}")
    print(f"under_sliced_datasets:     {n_mismatch_ds}")
    print(f"under_sliced_dataset_dims: {n_mismatch_dims}")
    print(f"covered_by_deep_dims:      {n_covered}")
    print(f"under_sliced_indicators:   {ind_count}")
    print(f"elapsed_sec:               {elapsed:.1f}")
    print(f"datasets_file:             {datasets_path}")
    print(f"indicators_file:           {indicators_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
