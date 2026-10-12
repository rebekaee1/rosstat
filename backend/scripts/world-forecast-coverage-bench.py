"""Бенч охвата и качества world-прогнозов на фиксированной выборке (круг 12).

Работает без БД: читает выгрузку из двух CSV и гоняет ту же функцию гейта, что
использует плановая задача (``train_quality_gated_world_forecast``).

Выгрузка (тестовый стенд или боевая база, только чтение)::

    -- meta.csv: id,slug,cc,provider,dataset_id,code,frequency,unit,name_quality,
    --           points_count,history_end,name_en,rn
    -- points.csv (без заголовка): indicator_id,date,value

Режимы (``--variant``): ``before`` — только главная модель, как до круга 12;
``after`` — кандидаты с вложенным выбором (правило допуска по умолчанию) и
заполнение коротких дыр; ``strict`` / ``none`` — другие правила допуска модели
к гейту (для сравнения). ``--holdout`` отрезает последние h наблюдений, гоняет
гейт на остатке и сравнивает опубликованный прогноз с отрезанной реальностью.

Пример::

    python scripts/world-forecast-coverage-bench.py --data-dir /path/to/export \\
        --variant after --out result-after.jsonl
    python scripts/world-forecast-coverage-bench.py --data-dir /path/to/export \\
        --variant after --holdout --out holdout-after.jsonl
    python scripts/world-forecast-coverage-bench.py --summarize result-before.jsonl result-after.jsonl
"""

from __future__ import annotations

import argparse
import collections
import csv
import json
import os
import statistics
import sys
import time
import warnings
from datetime import date
from multiprocessing import Pool
from pathlib import Path
from types import SimpleNamespace

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.data.world_forecast_policy import forecast_eligibility_for  # noqa: E402
from app.services import world_forecaster as wf  # noqa: E402

TODAY = date(2026, 10, 3)  # дата снимка выгрузки: возраст ряда считается от неё
_RULES = {"after": "mase", "strict": "naive", "none": "none"}


def _load(data_dir: Path):
    meta: dict[int, dict] = {}
    for row in csv.DictReader(open(data_dir / "meta.csv", encoding="utf-8")):
        row["id"] = int(row["id"])
        row["points_count"] = int(row["points_count"])
        row["history_end"] = date.fromisoformat(row["history_end"])
        meta[row["id"]] = row
    points: dict[int, list[tuple[date, float]]] = collections.defaultdict(list)
    for iid, day, value in csv.reader(open(data_dir / "points.csv", encoding="utf-8")):
        points[int(iid)].append((date.fromisoformat(day), float(value)))
    return meta, points


def _worker(job):
    row, series, variant, holdout = job
    if variant in _RULES:
        wf.SELECTION_RULE = _RULES[variant]
    indicator = SimpleNamespace(
        provider=row["provider"], dataset_id=row["dataset_id"], unit=row["unit"],
        frequency=row["frequency"], is_listed=True, name_quality=row["name_quality"],
        points_count=row["points_count"], history_end=row["history_end"],
    )
    eligibility, reason = forecast_eligibility_for(indicator, today=TODAY)
    out = {
        "id": row["id"], "slug": row["slug"], "provider": row["provider"],
        "freq": row["frequency"], "code": row["code"], "unit": row["unit"],
        "name": row["name_en"], "n": len(series),
    }
    if eligibility is None:
        out.update(status="skipped", reason=reason, mase=None, base=None, cpu=0.0)
        return out
    horizon = eligibility.horizon
    actual: list[float] = []
    if holdout:
        if len(series) < eligibility.min_points + horizon:
            out.update(status="short", reason="short", mase=None, base=None, cpu=0.0)
            return out
        actual = [value for _, value in series[-horizon:]]
        series = series[:-horizon]
    dates = [day for day, _ in series]
    values = [value for _, value in series]
    kwargs: dict = {}
    if variant != "before":
        kwargs["candidates"] = True
        kwargs["fill_gaps"] = True
        if wf.is_percentage_unit(row["unit"]) and values and min(values) >= 0 and max(values) <= 100:
            kwargs["bounds"] = (0.0, 100.0)
    else:
        kwargs["candidates"] = False
        kwargs["fill_gaps"] = False
    started = time.process_time()
    try:
        gate = wf.train_quality_gated_world_forecast(
            dates, values, frequency=eligibility.frequency, horizon=horizon,
            season=eligibility.season, strategy=eligibility.strategy, strict=True, **kwargs,
        )
    except Exception as exc:  # noqa: BLE001
        out.update(status="error", reason=f"{type(exc).__name__}", mase=None, base=None,
                   cpu=time.process_time() - started)
        return out
    out.update(
        status=gate.status, reason=gate.reason, mase=gate.mase, base=gate.baseline_mase,
        strategy=gate.strategy, details=gate.details, cpu=time.process_time() - started,
    )
    if holdout and gate.result is not None:
        scale = wf._scale(values, eligibility.season)
        forecast = [point.value for point in gate.result.points[:horizon]]
        naive = wf._seasonal_projection(values, season=eligibility.season, steps=horizon, drift=False)
        out["ho"] = sum(abs(p - a) for p, a in zip(forecast, actual)) / horizon / scale
        out["ho_naive"] = sum(abs(p - a) for p, a in zip(naive, actual)) / horizon / scale
        out["cand"] = str(gate.strategy).startswith("candidate")
    return out


def run(args) -> None:
    meta, points = _load(Path(args.data_dir))
    jobs = [(meta[i], points[i], args.variant, args.holdout) for i in meta]
    started = time.time()
    with Pool(args.processes) as pool:
        rows = pool.map(_worker, jobs, chunksize=8)
    with open(args.out, "w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"done {len(rows)} rows, wall {time.time() - started:.0f}s -> {args.out}")


def summarize(paths: list[str]) -> None:
    for path in paths:
        rows = [json.loads(line) for line in open(path, encoding="utf-8")]
        status = collections.Counter(r["status"] for r in rows)
        passed = [r for r in rows if r["status"] == "passed"]
        evaluated = [r for r in rows if r["status"] in {"passed", "failed"}]
        print(f"== {path}: evaluated={len(evaluated)} passed={len(passed)} {dict(status)}")
        by_country = collections.defaultdict(lambda: [0, 0])
        for r in evaluated:
            by_country[r["slug"]][0] += 1
            by_country[r["slug"]][1] += r["status"] == "passed"
        print("   by country:", {k: f"{v[1]}/{v[0]}" for k, v in sorted(by_country.items())})
        if passed and "ho" not in passed[0]:
            mases = sorted(r["mase"] for r in passed)
            print(f"   backtest MASE median={statistics.median(mases):.3f} "
                  f"p25={mases[len(mases) // 4]:.3f} p75={mases[3 * len(mases) // 4]:.3f}; "
                  f"median MASE/naive={statistics.median(r['mase'] / r['base'] for r in passed):.3f}")
        cpu = [r["cpu"] for r in evaluated]
        if cpu:
            print(f"   CPU per 1000 evaluated series: {1000 * sum(cpu) / len(cpu):.0f} s")
        if passed and "ho" in passed[0]:
            for label, sub in (
                ("all", passed),
                ("main", [r for r in passed if not r["cand"]]),
                ("candidate", [r for r in passed if r["cand"]]),
            ):
                if not sub:
                    continue
                ratios = [r["ho"] / r["ho_naive"] for r in sub if r["ho_naive"] > 0]
                print(
                    f"   holdout {label}: n={len(sub)} MASE mean={statistics.mean(r['ho'] for r in sub):.3f} "
                    f"median={statistics.median(r['ho'] for r in sub):.3f} "
                    f"beat naive={sum(r['ho'] < r['ho_naive'] for r in sub) / len(sub):.1%} "
                    f"MASE<1={sum(r['ho'] < 1 for r in sub) / len(sub):.1%} "
                    f"median ratio={statistics.median(ratios):.3f}"
                )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-dir")
    parser.add_argument("--variant", choices=["before", "after", "strict", "none"], default="after")
    parser.add_argument("--holdout", action="store_true")
    parser.add_argument("--processes", type=int, default=int(os.environ.get("NPROC", "4")))
    parser.add_argument("--out", default="result.jsonl")
    parser.add_argument("--summarize", nargs="*")
    args = parser.parse_args()
    if args.summarize:
        summarize(args.summarize)
        return
    if not args.data_dir:
        parser.error("--data-dir обязателен")
    run(args)


if __name__ == "__main__":
    main()
