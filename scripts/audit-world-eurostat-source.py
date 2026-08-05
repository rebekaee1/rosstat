#!/usr/bin/env python3
"""Сверка world_data_points / API с первоисточником Eurostat JSON-stat.

Выборка ≥40 листингуемых рядов: разные страны, частоты, темы (ВВП, инфляция,
безработица, население, промпроизводство, торговля, зарплаты).

Запуск:
  python3 scripts/audit-world-eurostat-source.py
  python3 scripts/audit-world-eurostat-source.py --limit 50
"""

from __future__ import annotations

import argparse
import random
import sys
import time
from collections import defaultdict
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from audit_world_lib import (  # noqa: E402
    api_get,
    as_slice_dict,
    build_eurostat_url,
    classify_topic,
    connect,
    fetch_eurostat_series,
    fetch_indicator_points,
    run_async,
    values_close,
    write_json,
    eprint,
)

REQUIRED_TOPICS = {
    "gdp", "inflation", "unemployment", "population", "industry", "trade", "wages",
}


async def pick_sample(conn, *, limit: int, seed: int) -> list[dict]:
    rows = await conn.fetch(
        """
        SELECT i.id, i.code, i.dataset_id, i.slice_json, i.unit, i.unit_ru,
               i.frequency, i.name_ru, i.category_ru, i.points_count,
               i.history_start, i.history_end,
               c.code AS geo, c.slug, c.name_ru AS country_name
        FROM world_indicators i
        JOIN world_countries c ON c.id = i.country_id
        WHERE i.is_listed
          AND i.points_count > 0
          AND c.is_active
        """
    )
    by_topic: dict[str, list] = defaultdict(list)
    other: list = []
    for r in rows:
        topic = classify_topic(r["name_ru"], r["dataset_id"], r["category_ru"])
        item = dict(r)
        item["topic"] = topic
        if topic:
            by_topic[topic].append(item)
        else:
            other.append(item)

    rng = random.Random(seed)
    chosen: list[dict] = []
    seen_ids: set[int] = set()

    # обязательно по теме — несколько стран
    for topic in REQUIRED_TOPICS:
        pool = by_topic.get(topic) or []
        rng.shuffle(pool)
        # diversify geos
        used_geo: set[str] = set()
        for item in pool:
            if item["id"] in seen_ids:
                continue
            if item["geo"] in used_geo and len(used_geo) < 4:
                continue
            chosen.append(item)
            seen_ids.add(item["id"])
            used_geo.add(item["geo"])
            if len(used_geo) >= 3:
                break

    # добор: разные частоты / регионы
    freq_need = {"monthly", "quarterly", "annual"}
    have_freq = {x["frequency"] for x in chosen}
    for freq in sorted(freq_need - have_freq):
        pool = [r for r in rows if r["frequency"] == freq and r["id"] not in seen_ids]
        rng.shuffle(pool)
        for item in pool[:2]:
            d = dict(item)
            d["topic"] = classify_topic(d["name_ru"], d["dataset_id"], d["category_ru"])
            chosen.append(d)
            seen_ids.add(d["id"])

    # крупные EU + партнёры
    for geo in ("DE", "FR", "PL", "US", "CN", "JP", "AM", "TR", "UA"):
        pool = [r for r in rows if r["geo"] == geo and r["id"] not in seen_ids]
        rng.shuffle(pool)
        for item in pool[:2]:
            d = dict(item)
            d["topic"] = classify_topic(d["name_ru"], d["dataset_id"], d["category_ru"])
            chosen.append(d)
            seen_ids.add(d["id"])

    # зарплаты — отдельный добор (мало рядов)
    wage_pool = by_topic.get("wages") or []
    rng.shuffle(wage_pool)
    for item in wage_pool[:3]:
        if item["id"] not in seen_ids:
            chosen.append(item)
            seen_ids.add(item["id"])

    # добор случайный до limit
    rest = [dict(r) for r in rows if r["id"] not in seen_ids]
    for d in rest:
        d["topic"] = classify_topic(d["name_ru"], d["dataset_id"], d["category_ru"])
    rng.shuffle(rest)
    for item in rest:
        if len(chosen) >= limit:
            break
        chosen.append(item)
        seen_ids.add(item["id"])

    return chosen[:limit]


def compare_series(
    ours: list[tuple],
    source: list[tuple],
    *,
    sample_n: int = 12,
) -> dict:
    our_map = {d: v for d, v in ours}
    src_map = {d: v for d, v in source}
    our_dates = set(our_map)
    src_dates = set(src_map)
    only_ours = sorted(our_dates - src_dates)
    only_src = sorted(src_dates - our_dates)
    common = sorted(our_dates & src_dates)

    mismatches = []
    for d in common:
        a, b = our_map[d], src_map[d]
        if not values_close(a, b):
            mismatches.append({
                "date": d.isoformat(),
                "ours": a,
                "eurostat": b,
                "abs_diff": abs(a - b),
            })

    # spot-check sample of matching points
    sample_ok = 0
    sample_checked = 0
    if common:
        step = max(1, len(common) // sample_n)
        for d in common[::step][:sample_n]:
            sample_checked += 1
            if values_close(our_map[d], src_map[d]):
                sample_ok += 1

    status = "match"
    if mismatches or only_ours or only_src:
        # small date-edge diffs can be lastTimePeriod / revision lag
        if not mismatches and len(only_ours) <= 2 and len(only_src) <= 2:
            status = "near_match"
        elif mismatches:
            status = "value_mismatch"
        else:
            status = "date_mismatch"

    return {
        "status": status,
        "ours_n": len(ours),
        "eurostat_n": len(source),
        "common_n": len(common),
        "only_ours_n": len(only_ours),
        "only_eurostat_n": len(only_src),
        "only_ours_sample": [d.isoformat() for d in only_ours[:5]],
        "only_eurostat_sample": [d.isoformat() for d in only_src[:5]],
        "value_mismatches_n": len(mismatches),
        "value_mismatches_sample": mismatches[:10],
        "period_ours": [ours[0][0].isoformat(), ours[-1][0].isoformat()] if ours else None,
        "period_eurostat": [source[0][0].isoformat(), source[-1][0].isoformat()] if source else None,
        "sample_checked": sample_checked,
        "sample_ok": sample_ok,
    }


async def amain(args) -> int:
    conn = await connect()
    try:
        sample = await pick_sample(conn, limit=args.limit, seed=args.seed)
        eprint(f"Sample size: {len(sample)}")
        topics = sorted({s.get("topic") for s in sample if s.get("topic")})
        eprint(f"Topics covered: {topics}")

        sess = requests.Session()
        results = []
        for i, ind in enumerate(sample, 1):
            geo = ind["geo"]
            dataset_id = ind["dataset_id"]
            slice_json = as_slice_dict(ind["slice_json"])
            eprint(f"[{i}/{len(sample)}] {ind['slug']}/{ind['code']}  {dataset_id}")

            ours = await fetch_indicator_points(conn, ind["id"])
            entry = {
                "code": ind["code"],
                "slug": ind["slug"],
                "geo": geo,
                "country": ind["country_name"],
                "dataset_id": dataset_id,
                "slice_json": slice_json,
                "name_ru": ind["name_ru"],
                "unit": ind["unit"],
                "unit_ru": ind["unit_ru"],
                "frequency": ind["frequency"],
                "topic": ind.get("topic"),
                "eurostat_url": build_eurostat_url(dataset_id, slice_json, geo=geo),
            }

            try:
                source = fetch_eurostat_series(
                    dataset_id, slice_json, geo, session=sess, timeout=args.timeout,
                )
            except Exception as exc:  # noqa: BLE001
                entry["error"] = f"eurostat_fetch: {exc}"
                entry["compare"] = None
                results.append(entry)
                time.sleep(args.sleep)
                continue

            if not source:
                entry["error"] = "eurostat_empty_for_geo"
                entry["compare"] = None
                results.append(entry)
                time.sleep(args.sleep)
                continue

            cmp_ = compare_series(ours, source)
            entry["compare"] = cmp_

            # API level mode vs DB
            try:
                api = api_get(f"/world/indicators/{ind['slug']}/{ind['code']}/data", params={"mode": "level"})
                api_pts = [(p["date"], float(p["value"])) for p in api.get("points") or []]
                db_map = {d.isoformat(): v for d, v in ours}
                api_mism = []
                for d, v in api_pts:
                    if d not in db_map or not values_close(v, db_map[d]):
                        api_mism.append({"date": d, "api": v, "db": db_map.get(d)})
                # length / edges
                entry["api_vs_db"] = {
                    "api_n": len(api_pts),
                    "db_n": len(ours),
                    "mismatches_n": len(api_mism),
                    "mismatches_sample": api_mism[:5],
                    "match": len(api_mism) == 0 and len(api_pts) == len(ours),
                }
            except Exception as exc:  # noqa: BLE001
                entry["api_vs_db"] = {"error": str(exc)}

            results.append(entry)
            time.sleep(args.sleep)

        matched = [r for r in results if (r.get("compare") or {}).get("status") in {"match", "near_match"}]
        hard_fail = [
            r for r in results
            if r.get("error")
            or (r.get("compare") or {}).get("status") == "value_mismatch"
            or (r.get("compare") or {}).get("status") == "date_mismatch"
        ]
        api_fail = [
            r for r in results
            if isinstance(r.get("api_vs_db"), dict)
            and r["api_vs_db"].get("match") is False
        ]

        summary = {
            "checked": len(results),
            "matched_or_near": len(matched),
            "hard_issues": len(hard_fail),
            "api_db_mismatches": len(api_fail),
            "topics_present": sorted({r.get("topic") for r in results if r.get("topic")}),
            "countries": sorted({r["geo"] for r in results}),
            "required_topics_missing": sorted(REQUIRED_TOPICS - set(topics)),
        }
        out = {"summary": summary, "results": results}
        path = write_json("eurostat-source-compare.json", out)
        eprint(f"Wrote {path}")
        print(json_dumps_summary(summary, hard_fail, api_fail))
        return 0 if not hard_fail else 1
    finally:
        await conn.close()


def json_dumps_summary(summary, hard_fail, api_fail) -> str:
    lines = [
        f"SOURCE COMPARE: checked={summary['checked']} "
        f"ok/near={summary['matched_or_near']} issues={summary['hard_issues']} "
        f"api_db_fail={summary['api_db_mismatches']}",
    ]
    for r in hard_fail[:30]:
        cmp_ = r.get("compare") or {}
        lines.append(
            f"  ISSUE {r['geo']} {r['dataset_id']} {r['code']}: "
            f"{r.get('error') or cmp_.get('status')} "
            f"mism={cmp_.get('value_mismatches_n')} "
            f"only_ours={cmp_.get('only_ours_n')} only_src={cmp_.get('only_eurostat_n')}"
        )
        sample = (cmp_.get("value_mismatches_sample") or [])[:2]
        for m in sample:
            lines.append(
                f"    {m['date']}: ours={m['ours']} eurostat={m['eurostat']} diff={m['abs_diff']}"
            )
    for r in api_fail[:10]:
        lines.append(f"  API≠DB {r['code']}: {r.get('api_vs_db')}")
    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, default=48)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--timeout", type=int, default=120)
    p.add_argument("--sleep", type=float, default=0.35)
    args = p.parse_args()
    raise SystemExit(run_async(amain(args)))


if __name__ == "__main__":
    main()
