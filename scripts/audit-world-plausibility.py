#!/usr/bin/env python3
"""Правдоподобие единиц и значений по ВСЕМ листингуемым world-рядам.

Ловит misleading-класс: % вне разумного диапазона, масштаб населения,
индексы без базы ≈100, отрицательные где нельзя, разрывы частоты,
дубли дат, нули подряд, сильно устаревший period_end.

Запуск:
  python3 scripts/audit-world-plausibility.py
"""

from __future__ import annotations

import argparse
import statistics
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from audit_world_lib import (  # noqa: E402
    POP_MILLIONS_APPROX,
    connect,
    index_base_year,
    run_async,
    unit_looks_index,
    unit_looks_percent,
    unit_scale_people,
    write_json,
    eprint,
)
from app.services.world_plausibility import plausibility_reasons  # noqa: E402

TODAY = date(2026, 7, 27)  # зафиксировано датой аудита (user_info)


def median_gap_days(dates: list[date]) -> float | None:
    if len(dates) < 3:
        return None
    gaps = [(b - a).days for a, b in zip(dates, dates[1:]) if (b - a).days > 0]
    if not gaps:
        return None
    return float(statistics.median(gaps))


EXPECTED_GAP = {
    "monthly": (25, 40),
    "quarterly": (80, 100),
    "annual": (350, 380),
    "weekly": (5, 10),
    "daily": (1, 4),
}


async def amain(args) -> int:
    conn = await connect()
    try:
        inds = await conn.fetch(
            """
            SELECT i.id, i.code, i.dataset_id, i.unit, i.unit_ru, i.frequency,
                   i.name_ru, i.category_ru, i.points_count,
                   i.history_start, i.history_end, i.slice_json,
                   c.code AS geo, c.slug, c.name_ru AS country_name
            FROM world_indicators i
            JOIN world_countries c ON c.id = i.country_id
            WHERE i.is_listed AND c.is_active
            ORDER BY c.code, i.code
            """
        )
        eprint(f"Listed indicators: {len(inds)}")

        # bulk load all points for listed — memory ~1.7M ok
        points = await conn.fetch(
            """
            SELECT p.indicator_id, p.date, p.value::float8 AS value
            FROM world_data_points p
            JOIN world_indicators i ON i.id = p.indicator_id
            WHERE i.is_listed
            ORDER BY p.indicator_id, p.date
            """
        )
        by_id: dict[int, list[tuple[date, float]]] = defaultdict(list)
        for r in points:
            by_id[r["indicator_id"]].append((r["date"], float(r["value"])))

        findings: list[dict] = []

        for ind in inds:
            pts = by_id.get(ind["id"]) or []
            if not pts:
                findings.append(_f(ind, "empty_listed", "Листингуемый ряд без точек", "P0"))
                continue

            dates = [d for d, _ in pts]
            vals = [v for _, v in pts]
            unit, unit_ru = ind["unit"] or "", ind["unit_ru"] or ""
            freq = (ind["frequency"] or "").lower()
            geo = ind["geo"]
            name = ind["name_ru"] or ""

            # duplicate dates (DB unique should prevent — still check)
            if len(dates) != len(set(dates)):
                findings.append(_f(ind, "duplicate_dates", "Дубли дат в ряде", "P0"))

            # stale — только заметно мёртвые ряды (не «прошлый календарный год»)
            end = dates[-1]
            stale_days = (TODAY - end).days
            if freq == "monthly" and stale_days > 540:
                findings.append(_f(
                    ind, "stale_monthly",
                    f"Месячный ряд обрывается {end.isoformat()} ({stale_days} дн. назад)",
                    "P2", last=vals[-1], end=end.isoformat(),
                ))
            elif freq == "quarterly" and stale_days > 730:
                findings.append(_f(
                    ind, "stale_quarterly",
                    f"Квартальный ряд обрывается {end.isoformat()} ({stale_days} дн. назад)",
                    "P2", last=vals[-1], end=end.isoformat(),
                ))
            elif freq == "annual" and stale_days > 1500:
                findings.append(_f(
                    ind, "stale_annual",
                    f"Годовой ряд обрывается {end.isoformat()} ({stale_days} дн. назад)",
                    "P3", last=vals[-1], end=end.isoformat(),
                ))

            # frequency gap mismatch
            med_gap = median_gap_days(dates)
            if med_gap is not None and freq in EXPECTED_GAP:
                lo, hi = EXPECTED_GAP[freq]
                # annual-in-monthly: median gap ~365 while labeled monthly
                if freq == "monthly" and med_gap > 300:
                    findings.append(_f(
                        ind, "freq_gap_annual_as_monthly",
                        f"Заявлен monthly, медианный шаг {med_gap:.0f} дн. (~год)",
                        "P0", median_gap_days=med_gap,
                    ))
                elif freq == "quarterly" and med_gap > 300:
                    findings.append(_f(
                        ind, "freq_gap_annual_as_quarterly",
                        f"Заявлен quarterly, медианный шаг {med_gap:.0f} дн.",
                        "P1", median_gap_days=med_gap,
                    ))
                elif not (lo * 0.5 <= med_gap <= hi * 2.5) and med_gap > hi * 2.5:
                    findings.append(_f(
                        ind, "freq_gap_suspicious",
                        f"Частота {freq}, медианный шаг {med_gap:.0f} дн. (ожидали ~{lo}–{hi})",
                        "P2", median_gap_days=med_gap,
                    ))

            # long zero runs
            run = 0
            max_zero = 0
            for v in vals:
                if abs(v) < 1e-12:
                    run += 1
                    max_zero = max(max_zero, run)
                else:
                    run = 0
            if max_zero >= 12 and unit_looks_percent(unit, unit_ru):
                findings.append(_f(
                    ind, "zero_run_pct",
                    f"Подряд нулей в %-ряду: {max_zero}",
                    "P2", max_zero_run=max_zero,
                ))
            elif max_zero >= 24:
                findings.append(_f(
                    ind, "zero_run",
                    f"Подряд нулей: {max_zero}",
                    "P3", max_zero_run=max_zero,
                ))

            # unit PC + label %, но значения явно не проценты (PPS/уровни)
            slice_j = ind["slice_json"]
            if isinstance(slice_j, str):
                import json as _json
                slice_j = _json.loads(slice_j) if slice_j else {}
            slice_j = slice_j or {}

            # Единый предохранитель (тот же код, что в repair-world-listing)
            for reason in plausibility_reasons(
                name_ru=name,
                unit=unit,
                unit_ru=unit_ru,
                slice_json=slice_j,
                values=vals,
                dataset_id=ind["dataset_id"],
            ):
                findings.append(_f(ind, reason, f"plausibility:{reason}", "P0", last=vals[-1]))

            unit_code = (unit or slice_j.get("unit") or "").upper()
            # legacy detail messages (не ослабляем — дубли kind схлопнутся в by_kind)
            if (unit_ru or "").strip() in {"%", "% ВВП", "% населения"} or (unit_ru or "").startswith("%"):
                lo_v, hi_v = min(vals), max(vals)
                if hi_v > 500 and unit_code in {"PC", "PC_GDP"} and "HAB" in str(slice_j).upper():
                    findings.append(_f(
                        ind, "unit_mislabeled_pct_but_level",
                        f"Подпись «{unit_ru}», unit-код={unit_code}, но значения "
                        f"{lo_v:.0f}…{hi_v:.0f} — это уровень (PPS/на душу), не процент. "
                        f"На витрине выглядит как «{hi_v:.0f}%»",
                        "P0", min_v=lo_v, max_v=hi_v, last=vals[-1],
                    ))
                elif hi_v > 500 and unit_looks_percent(unit, unit_ru) and unit_code == "PC":
                    findings.append(_f(
                        ind, "unit_mislabeled_pct_but_level",
                        f"Подпись «{unit_ru}», значения {lo_v:.0f}…{hi_v:.0f} — не похоже на процент",
                        "P0", min_v=lo_v, max_v=hi_v, last=vals[-1],
                    ))

            na_item = str(slice_j.get("na_item") or "").upper()
            if (
                unit_code == "PC_GDP"
                and na_item == "B1GQ"
                and abs(statistics.median(vals) - 100) < 0.5
            ):
                findings.append(_f(
                    ind, "tautological_gdp_pc_gdp",
                    "ВВП в единице «% ВВП» — тождество ≈100%. Бессмысленно и вводит в заблуждение",
                    "P0", last=vals[-1], median=statistics.median(vals),
                ))

            # percent range
            if unit_looks_percent(unit, unit_ru):
                if unit.upper() == "BAL" or "сальдо" in unit_ru.lower():
                    pass
                elif max(vals) > 500 and unit_code == "PC":
                    pass  # already covered by unit_mislabeled
                else:
                    lo_v, hi_v = min(vals), max(vals)
                    last = vals[-1]
                    hard_hi = 500
                    hard_lo = -100
                    if any(k in name.lower() for k in ("инфляц", "hicp", "ипц", "цен")):
                        hard_hi = 2000
                    if hi_v > hard_hi or lo_v < hard_lo:
                        findings.append(_f(
                            ind, "pct_out_of_range",
                            f"%-ряд: min={lo_v:.2f} max={hi_v:.2f} last={last:.2f} "
                            f"(unit={unit_ru or unit})",
                            "P0" if hi_v > 5000 or last > 500 else "P1",
                            min_v=lo_v, max_v=hi_v, last=last,
                        ))
                    # classic CPI-index-as-percent trap
                    if (
                        80 <= last <= 130
                        and abs(statistics.median(vals) - 100) < 8
                        and "индекс" not in unit_ru.lower()
                        and not unit_looks_index(unit, unit_ru)
                        and unit_code != "PC_GDP"  # handled as tautological
                        and "занят" not in name.lower()
                        and "занятост" not in name.lower()
                        # доли энергосистемы / ВВП к среднему ЕС — легитимные % около 100
                        and not ind["dataset_id"].lower().startswith("nrg_ind_")
                        and "eu27" not in unit_code.lower()
                        and "средн" not in unit_ru.lower()
                        and "от среднего" not in unit_ru.lower()
                    ):
                        findings.append(_f(
                            ind, "pct_looks_like_index_100",
                            f"Подписан как %, значения около 100 (last={last:.2f}, "
                            f"median={statistics.median(vals):.2f}) — риск путаницы "
                            f"индекс↔процент",
                            "P0", last=last, median=statistics.median(vals),
                        ))

            # index base year ≈ 100
            if unit_looks_index(unit, unit_ru):
                base_y = index_base_year(unit, unit_ru)
                if base_y:
                    base_pts = [v for d, v in pts if d.year == base_y]
                    if base_pts:
                        med = statistics.median(base_pts)
                        if not (85 <= med <= 115):
                            findings.append(_f(
                                ind, "index_base_not_near_100",
                                f"Индекс {unit_ru or unit}: в {base_y} медиана {med:.2f}, не ≈100",
                                "P1", base_year=base_y, base_median=med,
                            ))
                    else:
                        if dates[0].year > base_y + 1:
                            findings.append(_f(
                                ind, "index_missing_base_year",
                                f"Индекс с базой {base_y}, ряд начинается с {dates[0].year}",
                                "P3", base_year=base_y,
                            ))

            # negative where impossible
            neg_ok = any(
                k in (name + " " + unit_ru + " " + unit + " " + ind["dataset_id"]).lower()
                for k in (
                    "сальдо", "баланс", "миграц", "прирост", "изменен", "темп",
                    "bal", "net", "рост", "pch", "deficit", "профицит", "confidence",
                    "уверен", "mf-ddi", "ddi", "ставк", "процентн", "доходност",
                    "ei_mfir", "irt_",
                )
            )
            if not neg_ok and any(v < -1e-9 for v in vals):
                if unit_scale_people(unit, unit_ru) or "цен" in name.lower() or "населен" in name.lower():
                    findings.append(_f(
                        ind, "negative_impossible",
                        f"Отрицательные значения при unit={unit_ru or unit}",
                        "P0", min_v=min(vals),
                    ))
                elif min(vals) < -1e-9 and unit_looks_index(unit, unit_ru):
                    findings.append(_f(
                        ind, "negative_index",
                        f"Отрицательный индекс: min={min(vals):.2f}",
                        "P1", min_v=min(vals),
                    ))

            # population scale — только запас населения, не рождения/смерти/браки
            scale = unit_scale_people(unit, unit_ru)
            approx = POP_MILLIONS_APPROX.get(geo)
            ds_l = ind["dataset_id"].lower()
            name_l = name.lower()
            is_pop_stock = (
                ds_l.startswith(("demo_pjan", "tps00001"))
                or (
                    ("численность населения" in name_l or "население на 1 января" in name_l
                     or name_l.startswith("население,"))
                    and not any(
                        k in name_l
                        for k in (
                            "рожд", "смерт", "брак", "развод", "младен", "фертил",
                            "миграц", "ожидаем", "продолжит",
                        )
                    )
                )
            )
            if scale and approx and is_pop_stock:
                last = vals[-1]
                if scale == "ths":
                    implied_mio = last / 1000.0
                elif scale == "mio":
                    implied_mio = last
                else:
                    implied_mio = last / 1_000_000.0
                ratio = implied_mio / approx if approx else 0
                if ratio < 0.05 or ratio > 20:
                    findings.append(_f(
                        ind, "population_scale_mismatch",
                        f"Население: last={last} ({unit_ru or unit}) ≈ {implied_mio:.2f} млн, "
                        f"ожидали ~{approx} млн ({geo})",
                        "P0", last=last, implied_mio=implied_mio, expected_mio=approx,
                    ))
                elif ratio < 0.3 or ratio > 3:
                    findings.append(_f(
                        ind, "population_scale_suspicious",
                        f"Население: last={last} ≈ {implied_mio:.2f} млн vs ~{approx} млн ({geo})",
                        "P1", last=last, implied_mio=implied_mio, expected_mio=approx,
                    ))

            # unemployment % sanity
            if "безработ" in name.lower() and unit_looks_percent(unit, unit_ru):
                last = vals[-1]
                if last < 0 or last > 60:
                    findings.append(_f(
                        ind, "unemployment_pct_weird",
                        f"Безработица % = {last:.2f}",
                        "P0" if last > 100 else "P1", last=last,
                    ))

            # GDP scale rough check
            if ("ввп" in name.lower() or ind["dataset_id"].lower().startswith("nama_10_gdp")) and approx:
                u = unit.upper()
                last = vals[-1]
                if "MEUR" in u or "млн евро" in unit_ru.lower() or "mio_eur" in u.lower():
                    expected = approx * 40
                    ratio = last / expected if expected else 0
                    if last > 0 and (ratio < 0.02 or ratio > 50):
                        findings.append(_f(
                            ind, "gdp_scale_suspicious",
                            f"ВВП last={last} {unit_ru or unit}; грубо ожидали ~{expected:.0f} "
                            f"млн евро для {geo}",
                            "P2", last=last, expected_rough=expected,
                        ))

        # aggregate
        by_kind: dict[str, int] = defaultdict(int)
        by_sev: dict[str, int] = defaultdict(int)
        for f in findings:
            by_kind[f["kind"]] += 1
            by_sev[f["severity"]] += 1

        # Инварианты витрины: константы и listed на is_active=false
        constant_n = by_kind.get("constant_series", 0) + by_kind.get("constant_hundred_pct", 0)
        inactive_listed = await conn.fetch(
            """
            SELECT c.code, c.slug, i.code AS icode, i.name_ru
            FROM world_indicators i
            JOIN world_countries c ON c.id = i.country_id
            WHERE i.is_listed AND NOT c.is_active
            LIMIT 50
            """
        )
        for r in inactive_listed:
            findings.append({
                "kind": "listed_on_inactive_country",
                "severity": "P0",
                "code": r["icode"],
                "slug": r["slug"],
                "geo": r["code"],
                "country": r["code"],
                "dataset_id": "",
                "name_ru": r["name_ru"],
                "unit": "",
                "unit_ru": "",
                "frequency": "",
                "message": f"is_listed=true при world_countries.is_active=false ({r['code']})",
            })
            by_kind["listed_on_inactive_country"] = by_kind.get("listed_on_inactive_country", 0) + 1
            by_sev["P0"] = by_sev.get("P0", 0) + 1

        # keep report manageable: all P0/P1, sample P2/P3
        p0 = [f for f in findings if f["severity"] == "P0"]
        p1 = [f for f in findings if f["severity"] == "P1"]
        p2 = [f for f in findings if f["severity"] == "P2"]
        p3 = [f for f in findings if f["severity"] == "P3"]

        out = {
            "meta": {
                "listed_total": len(inds),
                "findings_total": len(findings),
                "by_severity": dict(by_sev),
                "by_kind": dict(sorted(by_kind.items(), key=lambda kv: -kv[1])),
                "constant_series_in_listing": constant_n,
                "listed_on_inactive_country": len(inactive_listed),
                "audit_date": TODAY.isoformat(),
            },
            "p0": p0,
            "p1": p1[:200],
            "p2_sample": p2[:80],
            "p3_sample": p3[:40],
            "p1_total": len(p1),
            "p2_total": len(p2),
            "p3_total": len(p3),
        }
        path = write_json("plausibility.json", out)
        eprint(f"Wrote {path}")
        print(
            f"PLAUSIBILITY: listed={len(inds)} findings={len(findings)} "
            f"P0={len(p0)} P1={len(p1)} P2={len(p2)} P3={len(p3)} "
            f"constants={constant_n} inactive_listed={len(inactive_listed)}"
        )
        for f in p0[:40]:
            print(f"  P0 [{f['kind']}] {f['geo']} {f['code']}: {f['message']}")
        return 0 if not p0 else 1
    finally:
        await conn.close()


def _f(ind, kind, message, severity, **extra):
    row = {
        "kind": kind,
        "severity": severity,
        "code": ind["code"],
        "slug": ind["slug"],
        "geo": ind["geo"],
        "country": ind["country_name"],
        "dataset_id": ind["dataset_id"],
        "name_ru": ind["name_ru"],
        "unit": ind["unit"],
        "unit_ru": ind["unit_ru"],
        "frequency": ind["frequency"],
        "message": message,
    }
    row.update(extra)
    return row


def main():
    p = argparse.ArgumentParser()
    args = p.parse_args()
    raise SystemExit(run_async(amain(args)))


if __name__ == "__main__":
    main()
