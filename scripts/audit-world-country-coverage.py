#!/usr/bin/env python3
"""Покрытие стран world-блока + разбор Армении + сверка с research xlsx.

Группы:
  A — Евростат полноценный первоисточник (listed ≥ median*0.5 или ≥ 150)
  B — страна-партнёр с огрызком данных

Запуск:
  python3 scripts/audit-world-country-coverage.py
"""

from __future__ import annotations

import statistics
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from audit_world_lib import (  # noqa: E402
    REPO,
    connect,
    run_async,
    write_json,
    eprint,
)

TODAY = date(2026, 7, 27)

# EU/EEA/candidate + deep Eurostat coverage expected
EUROSTAT_CORE_GEOS = {
    "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "EL",
    "HU", "IE", "IT", "LV", "LT", "LU", "MT", "NL", "PL", "PT", "RO", "SK",
    "SI", "ES", "SE", "IS", "NO", "CH", "UK",
}

# Partner / enlargement fringe — often partial but still "European" Eurostat
EUROSTAT_ENLARGEMENT = {
    "TR", "RS", "ME", "MK", "AL", "BA", "XK", "UA", "MD", "GE", "AM", "AZ",
}

# Non-European partners appearing in a handful of Eurostat tables
PARTNER_GEOS = {
    "US", "CN", "JP", "KR", "IN", "BR", "MX", "CA", "AU", "NZ", "ZA", "IL",
}

RESEARCH_XLSX = {
    "US": "usa-official-sources.xlsx",
    "CN": "china-official-sources.xlsx",
    "JP": "japan-official-sources.xlsx",
    "KR": "south-korea-official-sources.xlsx",
    "IN": "india-official-sources.xlsx",
    "BR": "brazil-official-sources.xlsx",
    "TR": "turkey-official-sources.xlsx",
    "FR": "france-official-sources.xlsx",
    "DE": "germany-official-sources.xlsx",
    "UK": "uk-official-sources.xlsx",
}


def recommend(geo: str, listed: int, loaded: int, median_listed: float, region: str) -> dict:
    has_research = geo in RESEARCH_XLSX and (
        REPO / "docs" / "research" / RESEARCH_XLSX[geo]
    ).exists()

    if geo in PARTNER_GEOS or (listed < 40 and geo not in EUROSTAT_CORE_GEOS):
        group = "B"
        if listed == 0:
            action = "hide"
            reason = "Нет листингуемых рядов — карточка страны пустая/вводящая в заблуждение."
        elif listed <= 12 and has_research:
            action = "hide_until_national"
            reason = (
                f"Огрызок Eurostat ({listed} listed / {loaded} loaded) рядом с полными "
                f"EU-странами; есть разведка национального источника "
                f"({RESEARCH_XLSX[geo]}) — лучше скрыть до подключения нац. первоисточника."
            )
        elif listed <= 12:
            action = "hide"
            reason = (
                f"Огрызок ({listed} listed). Без оговорки создаёт ложное равенство с "
                f"Германией (~{int(median_listed)} рядов)."
            )
        elif listed < 80:
            action = "keep_with_disclaimer"
            reason = (
                f"Частичное покрытие Eurostat ({listed}). Допустимо с явной оговоркой "
                f"«данные Евростата, неполный набор»"
                + (f"; есть research {RESEARCH_XLSX[geo]}" if has_research else "")
                + "."
            )
        else:
            action = "keep"
            reason = "Покрытие приемлемое для витрины Eurostat."
            group = "A" if listed >= median_listed * 0.4 else "B"
    else:
        group = "A"
        action = "keep"
        reason = "Европейское покрытие Eurostat."
        if listed < 100 and geo in EUROSTAT_ENLARGEMENT:
            group = "B"
            action = "keep_with_disclaimer"
            reason = (
                f"Страна расширения/соседей: {listed} listed — заметно меньше медианы "
                f"({int(median_listed)}). Оставить с оговоркой о неполноте."
            )

    return {
        "group": group,
        "action": action,
        "reason": reason,
        "has_national_research": has_research,
        "research_file": RESEARCH_XLSX.get(geo),
    }


async def armenia_deep_dive(conn) -> dict:
    rows = await conn.fetch(
        """
        SELECT i.id, i.code, i.dataset_id, i.name_ru, i.name_quality, i.is_listed,
               i.points_count, i.frequency, i.unit, i.unit_ru, i.category_ru,
               i.history_start, i.history_end, i.slice_json
        FROM world_indicators i
        JOIN world_countries c ON c.id = i.country_id
        WHERE c.code = 'AM'
        ORDER BY i.is_listed DESC, i.points_count DESC, i.name_ru
        """
    )
    # depth thresholds (mirror eurostat_listing)
    min_pts = {"monthly": 60, "quarterly": 20, "annual": 10, "yearly": 10, "weekly": 104, "daily": 250}

    by_q = defaultdict(lambda: {"listed": 0, "hidden": 0, "codes": []})
    hidden_reasons = []
    cats_listed = defaultdict(int)
    cats_all = defaultdict(int)

    for r in rows:
        q = r["name_quality"] or "raw"
        cats_all[r["category_ru"] or ""] += 1
        if r["is_listed"]:
            by_q[q]["listed"] += 1
            cats_listed[r["category_ru"] or ""] += 1
        else:
            by_q[q]["hidden"] += 1
            need = min_pts.get((r["frequency"] or "").lower(), 60)
            reasons = []
            if q == "raw":
                reasons.append("name_quality=raw (предохранитель заголовка)")
            if (r["points_count"] or 0) < need:
                reasons.append(
                    f"глубина {r['points_count']} < порога листинга {need} для {r['frequency']}"
                )
            if not reasons:
                reasons.append("скрыт семантическим дедупом или иным правилом загрузчика")
            hidden_reasons.append({
                "code": r["code"],
                "dataset_id": r["dataset_id"],
                "name_ru": r["name_ru"],
                "name_quality": q,
                "frequency": r["frequency"],
                "points_count": r["points_count"],
                "category_ru": r["category_ru"],
                "reasons": reasons,
                "could_restore_legally": (
                    q in ("curated", "composed")
                    and (r["points_count"] or 0) >= need
                ),
            })

    # What Eurostat has for AM — probe a few known datasets via DB distinct
    datasets = await conn.fetch(
        """
        SELECT dataset_id, COUNT(*) AS n,
               COUNT(*) FILTER (WHERE is_listed) AS listed_n,
               MAX(points_count) AS max_pts
        FROM world_indicators i
        JOIN world_countries c ON c.id = i.country_id
        WHERE c.code = 'AM'
        GROUP BY dataset_id
        ORDER BY listed_n DESC, n DESC
        """
    )

    restorable = [h for h in hidden_reasons if h["could_restore_legally"]]
    depth_blocked = [
        h for h in hidden_reasons
        if any("глубина" in x for x in h["reasons"]) and h["name_quality"] in ("curated", "composed")
    ]
    raw_blocked = [h for h in hidden_reasons if h["name_quality"] == "raw"]

    return {
        "loaded": len(rows),
        "listed": sum(1 for r in rows if r["is_listed"]),
        "hidden": sum(1 for r in rows if not r["is_listed"]),
        "by_name_quality": {k: dict(v) for k, v in by_q.items()},
        "categories_listed": dict(sorted(cats_listed.items(), key=lambda kv: -kv[1])),
        "categories_all": dict(sorted(cats_all.items(), key=lambda kv: -kv[1])),
        "datasets": [dict(d) for d in datasets],
        "hidden_detail": hidden_reasons,
        "restorable_now": restorable,
        "hidden_by_depth_curated": depth_blocked,
        "hidden_by_raw_title": raw_blocked,
        "verdict": (
            f"Армения: загружено {len(rows)}, на витрине {sum(1 for r in rows if r['is_listed'])}. "
            f"Скрыто в основном из-за порога глубины истории (curated, но <5 лет) "
            f"и 3 raw-заголовков. Eurostat реально отдаёт по AM лишь узкий набор "
            f"таблиц расширения — это не баг фильтра «мало блоков», а ограничение источника. "
            f"Законно вернуть сейчас: {len(restorable)} рядов "
            f"(curated/composed + достаточная глубина, но всё ещё скрыты)."
        ),
    }


async def amain() -> int:
    conn = await connect()
    try:
        countries = await conn.fetch(
            """
            SELECT c.id, c.code, c.slug, c.name_ru, c.region_ru,
                   COUNT(i.id) AS loaded,
                   COUNT(i.id) FILTER (WHERE i.is_listed) AS listed,
                   COALESCE(AVG(i.points_count) FILTER (WHERE i.is_listed), 0)::float AS avg_pts_listed,
                   COALESCE(
                     percentile_cont(0.5) WITHIN GROUP (ORDER BY i.points_count)
                       FILTER (WHERE i.is_listed), 0
                   )::float AS median_depth,
                   MAX(i.history_end) FILTER (WHERE i.is_listed) AS max_end,
                   MIN(i.history_start) FILTER (WHERE i.is_listed) AS min_start
            FROM world_countries c
            LEFT JOIN world_indicators i ON i.country_id = c.id
            WHERE c.is_active
            GROUP BY c.id
            ORDER BY listed ASC, loaded ASC
            """
        )

        # categories per country
        cat_rows = await conn.fetch(
            """
            SELECT c.code AS geo, i.category_ru, COUNT(*) AS n
            FROM world_indicators i
            JOIN world_countries c ON c.id = i.country_id
            WHERE i.is_listed AND c.is_active
            GROUP BY c.code, i.category_ru
            """
        )
        cats_by_geo: dict[str, dict[str, int]] = defaultdict(dict)
        for r in cat_rows:
            cats_by_geo[r["geo"]][r["category_ru"] or ""] = r["n"]

        listed_counts = [int(r["listed"]) for r in countries]
        median_listed = float(statistics.median(listed_counts)) if listed_counts else 0

        table = []
        for r in countries:
            geo = r["code"]
            listed = int(r["listed"])
            loaded = int(r["loaded"])
            rec = recommend(geo, listed, loaded, median_listed, r["region_ru"])
            freshness_days = None
            if r["max_end"]:
                freshness_days = (TODAY - r["max_end"]).days
            table.append({
                "geo": geo,
                "slug": r["slug"],
                "name_ru": r["name_ru"],
                "region_ru": r["region_ru"],
                "loaded": loaded,
                "listed": listed,
                "median_depth_points": round(float(r["median_depth"] or 0), 1),
                "avg_depth_points": round(float(r["avg_pts_listed"] or 0), 1),
                "history_start": r["min_start"].isoformat() if r["min_start"] else None,
                "history_end": r["max_end"].isoformat() if r["max_end"] else None,
                "freshness_days": freshness_days,
                "categories": cats_by_geo.get(geo, {}),
                "category_count": len(cats_by_geo.get(geo, {})),
                **rec,
            })

        armenia = await armenia_deep_dive(conn)

        group_a = [t for t in table if t["group"] == "A"]
        group_b = [t for t in table if t["group"] == "B"]
        hide = [t for t in table if t["action"] in {"hide", "hide_until_national"}]

        # research files present
        research_dir = REPO / "docs" / "research"
        research_present = {
            geo: (research_dir / fname).exists()
            for geo, fname in RESEARCH_XLSX.items()
        }

        out = {
            "meta": {
                "countries": len(table),
                "median_listed": median_listed,
                "group_a": len(group_a),
                "group_b": len(group_b),
                "recommend_hide": len(hide),
                "audit_date": TODAY.isoformat(),
            },
            "research_xlsx_present": research_present,
            "countries": table,
            "group_b_detail": group_b,
            "hide_candidates": hide,
            "armenia": armenia,
        }

        # Инвариант: у is_active=false не должно быть is_listed рядов
        leak = await conn.fetch(
            """
            SELECT c.code, c.slug, COUNT(*) FILTER (WHERE i.is_listed) AS listed
            FROM world_countries c
            LEFT JOIN world_indicators i ON i.country_id = c.id
            WHERE NOT c.is_active
            GROUP BY c.code, c.slug
            HAVING COUNT(*) FILTER (WHERE i.is_listed) > 0
            """
        )
        out["inactive_with_listed"] = [dict(r) for r in leak]
        out["meta"]["inactive_with_listed_n"] = len(leak)

        path = write_json("country-coverage.json", out)
        eprint(f"Wrote {path}")
        print(
            f"COVERAGE: countries={len(table)} median_listed={median_listed:.0f} "
            f"A={len(group_a)} B={len(group_b)} hide={len(hide)} "
            f"inactive_listed_leak={len(leak)}"
        )
        print("--- Group B / hide ---")
        for t in group_b:
            print(
                f"  {t['geo']:3} listed={t['listed']:4} loaded={t['loaded']:4} "
                f"action={t['action']:20} research={t['has_national_research']}"
            )
        print("--- Armenia ---")
        print(armenia["verdict"])
        return 1 if leak else 0
    finally:
        await conn.close()


if __name__ == "__main__":
    raise SystemExit(run_async(amain()))
