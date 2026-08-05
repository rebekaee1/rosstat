"""Выгрузка спроса (Вебмастер + внутренний поиск) и паттернов поведения за квартал.

Пишет CSV/JSON в OUT_DIR (по умолчанию /tmp/seo_demand_export внутри контейнера).
"""
from __future__ import annotations

import asyncio
import csv
import json
import os
import re
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

from sqlalchemy import text

from app.database import async_session

OUT = Path(os.environ.get("OUT_DIR", "/tmp/seo_demand_export"))
OUT.mkdir(parents=True, exist_ok=True)

Q_FROM = date(2026, 4, 15)
Q_TO = date(2026, 7, 15)

BUCKET_RULES = [
    ("inflation_today", re.compile(r"инфляц.*(сегодня|сейчас)|какая инфляц", re.I)),
    ("inflation_chart", re.compile(r"инфляц.*(график|динамик|по годам)|ипц", re.I)),
    ("inflation", re.compile(r"инфляц", re.I)),
    ("key_rate", re.compile(r"ключев(ая|ой)\s*ставк|ставк[аи]\s*цб", re.I)),
    ("fx", re.compile(r"курс\s*(доллар|евро|юан)|доллар|евро\b|юан|usd|eur|cny", re.I)),
    ("gdp", re.compile(r"\bввп\b|валовой внутрен", re.I)),
    ("unemployment", re.compile(r"безработ", re.I)),
    ("wages", re.compile(r"зарплат|заработн", re.I)),
    ("fuel", re.compile(r"бензин|дизел|аи-?9|топлив", re.I)),
    ("housing", re.compile(r"жиль[её]|квартир|ипотек|недвиж", re.I)),
    ("gold", re.compile(r"золот", re.I)),
    ("imoex", re.compile(r"мосбирж|имоекс|imoex", re.I)),
    ("region", re.compile(r"москв|питер|спб|татарстан|регион|област|край|републик", re.I)),
    ("brand", re.compile(r"forecast\s*economy|forecasteconomy", re.I)),
    ("calendar", re.compile(r"календар", re.I)),
    ("compare", re.compile(r"сравн", re.I)),
]


def bucket(q: str) -> str:
    for name, rx in BUCKET_RULES:
        if rx.search(q or ""):
            return name
    return "other"


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k) for k in fieldnames})


def dt_from() -> datetime:
    return datetime.combine(Q_FROM, datetime.min.time())


def dt_to() -> datetime:
    return datetime.combine(Q_TO + timedelta(days=1), datetime.min.time())


async def main() -> None:
    report: dict = {
        "window": {"from": str(Q_FROM), "to": str(Q_TO)},
        "generated_at": datetime.now().isoformat(),
    }

    async with async_session() as db:
        cov = {}
        checks = [
            ("webmaster", "select count(*), min(date), max(date), count(distinct query) from webmaster_search_queries where date>=:a and date<=:b",
             {"a": Q_FROM, "b": Q_TO}),
            ("metrika_phrases", "select count(*), min(date), max(date), count(distinct phrase) from metrika_search_phrases where date>=:a and date<=:b",
             {"a": Q_FROM, "b": Q_TO}),
            ("search_events", "select count(*), min(occurred_at), max(occurred_at) from frontend_events where event_name in ('search_query','search_select','compare_search') and occurred_at>=:a and occurred_at<:b",
             {"a": dt_from(), "b": dt_to()}),
            ("behavior", "select count(*), min(occurred_at), max(occurred_at) from behavior_events where occurred_at>=:a and occurred_at<:b",
             {"a": dt_from(), "b": dt_to()}),
            ("metrika_visits", "select count(*), min(visit_date), max(visit_date) from raw_metrika_visits where visit_date>=:a and visit_date<=:b",
             {"a": Q_FROM, "b": Q_TO}),
        ]
        for name, sql, params in checks:
            r = (await db.execute(text(sql), params)).one()
            cov[name] = [None if x is None else str(x) for x in r]
        report["coverage"] = cov

        wm = (await db.execute(text("""
            select query,
                   sum(coalesce(impressions,0)) as imp,
                   sum(coalesce(clicks,0)) as clk,
                   case when sum(coalesce(impressions,0))>0
                        then round(sum(coalesce(clicks,0))::numeric / sum(impressions), 4) end as ctr,
                   round(avg(position)::numeric, 2) as avg_pos,
                   count(distinct date) as days
            from webmaster_search_queries
            where date >= :a and date <= :b
            group by query
            order by sum(coalesce(impressions,0)) desc
        """), {"a": Q_FROM, "b": Q_TO})).mappings().all()

        wm_rows = []
        for r in wm:
            row = {
                "query": r["query"],
                "imp": int(r["imp"] or 0),
                "clk": int(r["clk"] or 0),
                "ctr": float(r["ctr"]) if r["ctr"] is not None else None,
                "avg_pos": float(r["avg_pos"]) if r["avg_pos"] is not None else None,
                "days": int(r["days"] or 0),
            }
            row["bucket"] = bucket(row["query"])
            wm_rows.append(row)
        write_csv(OUT / "webmaster_queries_quarter.csv", wm_rows,
                  ["query", "imp", "clk", "ctr", "avg_pos", "days", "bucket"])

        by_b: dict[str, dict] = defaultdict(lambda: {"imp": 0, "clk": 0, "queries": 0, "pos_w": 0.0, "pos_n": 0})
        for r in wm_rows:
            b = by_b[r["bucket"]]
            b["imp"] += r["imp"]
            b["clk"] += r["clk"]
            b["queries"] += 1
            if r["avg_pos"] is not None and r["imp"]:
                b["pos_w"] += r["avg_pos"] * r["imp"]
                b["pos_n"] += r["imp"]
        bucket_wm = []
        for name, b in sorted(by_b.items(), key=lambda x: -x[1]["imp"]):
            bucket_wm.append({
                "bucket": name,
                "imp": b["imp"],
                "clk": b["clk"],
                "queries": b["queries"],
                "ctr": round(b["clk"] / b["imp"], 4) if b["imp"] else None,
                "avg_pos_weighted": round(b["pos_w"] / b["pos_n"], 2) if b["pos_n"] else None,
            })
        write_csv(OUT / "webmaster_by_bucket.csv", bucket_wm,
                  ["bucket", "imp", "clk", "ctr", "avg_pos_weighted", "queries"])

        opp_pos = sorted(
            [r for r in wm_rows if r["imp"] >= 5 and r["avg_pos"] and r["avg_pos"] > 10],
            key=lambda x: -x["imp"],
        )[:100]
        opp_ctr = sorted(
            [r for r in wm_rows if r["imp"] >= 15 and (r["ctr"] or 0) < 0.03],
            key=lambda x: -x["imp"],
        )[:100]
        top_clk = sorted(wm_rows, key=lambda x: -x["clk"])[:100]
        write_csv(OUT / "webmaster_opportunity_deep_pos.csv", opp_pos,
                  ["query", "imp", "clk", "ctr", "avg_pos", "days", "bucket"])
        write_csv(OUT / "webmaster_opportunity_low_ctr.csv", opp_ctr,
                  ["query", "imp", "clk", "ctr", "avg_pos", "days", "bucket"])
        write_csv(OUT / "webmaster_top_clicks.csv", top_clk,
                  ["query", "imp", "clk", "ctr", "avg_pos", "days", "bucket"])

        report["webmaster"] = {
            "distinct_queries": len(wm_rows),
            "total_imp": sum(r["imp"] for r in wm_rows),
            "total_clk": sum(r["clk"] for r in wm_rows),
            "by_bucket": bucket_wm,
            "top25_imp": wm_rows[:25],
            "top25_clk": top_clk[:25],
            "deep_position_top20": opp_pos[:20],
            "low_ctr_top20": opp_ctr[:20],
        }

        mp = (await db.execute(text("""
            select phrase, sum(visits) as visits, sum(users) as users,
                   count(distinct date) as days
            from metrika_search_phrases
            where date >= :a and date <= :b
            group by phrase order by sum(visits) desc
        """), {"a": Q_FROM, "b": Q_TO})).mappings().all()
        mp_rows = [{
            "phrase": r["phrase"],
            "visits": int(r["visits"] or 0),
            "users": int(r["users"] or 0),
            "days": int(r["days"] or 0),
            "bucket": bucket(r["phrase"]),
        } for r in mp]
        write_csv(OUT / "metrika_phrases_quarter.csv", mp_rows,
                  ["phrase", "visits", "users", "days", "bucket"])
        met_buckets = []
        for k in sorted({x["bucket"] for x in mp_rows},
                        key=lambda k: -sum(x["visits"] for x in mp_rows if x["bucket"] == k)):
            met_buckets.append({
                "bucket": k,
                "visits": sum(x["visits"] for x in mp_rows if x["bucket"] == k),
            })
        report["metrika_phrases"] = {
            "distinct": len(mp_rows),
            "total_visits": sum(r["visits"] for r in mp_rows),
            "window_note": cov.get("metrika_phrases"),
            "top40": mp_rows[:40],
            "by_bucket": met_buckets,
        }

        # raw visits: search engine landings
        cols = (await db.execute(text("""
            select column_name from information_schema.columns
            where table_name='raw_metrika_visits' order by ordinal_position
        """))).scalars().all()
        phrase_col = next((c for c in cols if c in (
            "search_phrase", "last_search_phrase", "search_phrase_normalized"
        )), None)
        if not phrase_col:
            phrase_col = next((c for c in cols if "phrase" in c), None)
        report["raw_metrika_phrase_column"] = phrase_col
        if phrase_col:
            raw_ph = (await db.execute(text(f"""
                select {phrase_col} as phrase, count(*) as visits
                from raw_metrika_visits
                where visit_date >= :a and visit_date <= :b
                  and coalesce({phrase_col}, '') <> ''
                group by 1 order by 2 desc limit 100
            """), {"a": Q_FROM, "b": Q_TO})).mappings().all()
            raw_rows = [{
                "phrase": r["phrase"],
                "visits": int(r["visits"]),
                "bucket": bucket(r["phrase"]),
            } for r in raw_ph]
            write_csv(OUT / "raw_metrika_search_phrases.csv", raw_rows,
                      ["phrase", "visits", "bucket"])
            report["raw_metrika_phrases_top40"] = raw_rows[:40]

        fe = (await db.execute(text("""
            select event_name, params_json, occurred_at, url
            from frontend_events
            where event_name in ('search_query','search_select','search_abandon',
                                 'compare_search','table_search')
              and occurred_at >= :a and occurred_at < :b
            order by occurred_at
        """), {"a": dt_from(), "b": dt_to()})).mappings().all()

        q_counter: Counter = Counter()
        zero: Counter = Counter()
        by_ctx: dict[str, Counter] = defaultdict(Counter)
        selects: Counter = Counter()
        select_codes: Counter = Counter()
        abandons = 0
        for row in fe:
            p = row["params_json"] or {}
            if not isinstance(p, dict):
                continue
            name = row["event_name"]
            q = str(p.get("q") or p.get("query") or "").strip().lower()
            if name == "search_abandon":
                abandons += 1
                continue
            if name == "search_select":
                if q:
                    selects[q] += 1
                code = str(p.get("code") or p.get("indicator") or "")
                if code:
                    select_codes[code] += 1
                continue
            if not q:
                continue
            ctx = str(p.get("context") or (
                "compare-macro" if name == "compare_search" else "global"
            ))
            q_counter[q] += 1
            by_ctx[ctx][q] += 1
            try:
                if int(p.get("results", -1)) == 0:
                    zero[q] += 1
            except (TypeError, ValueError):
                pass

        int_rows = [{
            "q": q, "count": c, "bucket": bucket(q), "zero": zero.get(q, 0),
        } for q, c in q_counter.most_common()]
        write_csv(OUT / "internal_search_quarter.csv", int_rows,
                  ["q", "count", "bucket", "zero"])
        write_csv(OUT / "internal_search_zero.csv",
                  [{"q": q, "count": c, "bucket": bucket(q)} for q, c in zero.most_common()],
                  ["q", "count", "bucket"])
        write_csv(OUT / "internal_search_select_codes.csv",
                  [{"code": c, "count": n} for c, n in select_codes.most_common()],
                  ["code", "count"])

        total_q = sum(q_counter.values())
        total_sel = sum(selects.values())
        int_buckets = []
        for k in sorted({x["bucket"] for x in int_rows},
                        key=lambda k: -sum(x["count"] for x in int_rows if x["bucket"] == k)):
            int_buckets.append({
                "bucket": k,
                "count": sum(x["count"] for x in int_rows if x["bucket"] == k),
            })
        report["internal_search"] = {
            "events_by_type": dict(Counter(r["event_name"] for r in fe)),
            "total_query_events": total_q,
            "unique_queries": len(q_counter),
            "selects": total_sel,
            "abandons": abandons,
            "select_rate": round(total_sel / total_q, 3) if total_q else None,
            "zero_rate": round(sum(zero.values()) / total_q, 3) if total_q else None,
            "top50": int_rows[:50],
            "zero_top25": [{"q": q, "count": c, "bucket": bucket(q)} for q, c in zero.most_common(25)],
            "select_codes_top30": [{"code": c, "count": n} for c, n in select_codes.most_common(30)],
            "by_context_top": {ctx: dict(c.most_common(15)) for ctx, c in by_ctx.items()},
            "by_bucket": int_buckets,
        }

        pv = (await db.execute(text("""
            select page, count(*) as views,
                   count(distinct session_id_hash) as sessions
            from behavior_events
            where event_type='pageview'
              and occurred_at >= :a and occurred_at < :b
              and coalesce(page,'') not like '/admin%'
            group by page
            order by count(*) desc
            limit 100
        """), {"a": dt_from(), "b": dt_to()})).mappings().all()
        pv_rows = [{
            "page": r["page"],
            "views": int(r["views"]),
            "sessions": int(r["sessions"]),
        } for r in pv]
        write_csv(OUT / "behavior_top_pages.csv", pv_rows, ["page", "views", "sessions"])

        fam: Counter = Counter()
        for r in pv_rows:
            p = r["page"] or "/"
            if p.startswith("/today"):
                fam_key = "/today*"
            elif p.startswith("/indicator/"):
                fam_key = "/indicator/*"
            elif p.startswith("/region-rating"):
                fam_key = "/region-rating/*"
            elif p.startswith("/region-vs"):
                fam_key = "/region-vs/*"
            elif p.startswith("/region/"):
                fam_key = "/region/*"
            elif p.startswith("/category/"):
                fam_key = "/category/*"
            elif p.startswith("/regions"):
                fam_key = "/regions*"
            elif p.startswith("/compare"):
                fam_key = "/compare*"
            elif p.startswith("/calculator"):
                fam_key = "/calculator*"
            elif p in ("/", ""):
                fam_key = "/"
            else:
                fam_key = "other"
            fam[fam_key] += r["views"]

        dwell = (await db.execute(text("""
            select page, count(*) as n,
                   round(avg(
                     coalesce(
                       (params_json->>'ms')::numeric,
                       (params_json->>'duration_ms')::numeric,
                       (params_json->>'active_ms')::numeric
                     )
                   )/1000.0, 1) as avg_sec,
                   round(avg(nullif(params_json->>'scrollDepth','')::numeric), 2) as avg_scroll
            from behavior_events
            where event_type='dwell'
              and occurred_at >= :a and occurred_at < :b
              and coalesce(page,'') not like '/admin%'
            group by page
            having count(*) >= 3
            order by avg(
              coalesce(
                (params_json->>'ms')::numeric,
                (params_json->>'duration_ms')::numeric,
                (params_json->>'active_ms')::numeric
              )
            ) desc nulls last
            limit 50
        """), {"a": dt_from(), "b": dt_to()})).mappings().all()
        dwell_rows = []
        for r in dwell:
            dwell_rows.append({
                "page": r["page"],
                "n": int(r["n"]),
                "avg_sec": float(r["avg_sec"]) if r["avg_sec"] is not None else None,
                "avg_scroll": float(r["avg_scroll"]) if r["avg_scroll"] is not None else None,
            })
        write_csv(OUT / "behavior_dwell.csv", dwell_rows,
                  ["page", "n", "avg_sec", "avg_scroll"])

        depth = (await db.execute(text("""
            with s as (
              select session_id_hash,
                     count(*) filter (where event_type='pageview') as pvs
              from behavior_events
              where occurred_at>=:a and occurred_at<:b
                and session_id_hash is not null
                and coalesce(page,'') not like '/admin%'
              group by 1
            )
            select
              count(*) as sessions,
              round(avg(pvs)::numeric, 2) as avg_pv,
              percentile_cont(0.5) within group (order by pvs) as p50_pv,
              count(*) filter (where pvs=1) as bounce_like,
              count(*) filter (where pvs>=3) as deep3
            from s
        """), {"a": dt_from(), "b": dt_to()})).mappings().one()

        et = (await db.execute(text("""
            select event_type, count(*) from behavior_events
            where occurred_at>=:a and occurred_at<:b
            group by 1 order by 2 desc
        """), {"a": dt_from(), "b": dt_to()})).all()

        nav = (await db.execute(text("""
            select session_id_hash, page, occurred_at
            from behavior_events
            where event_type='pageview' and occurred_at>=:a and occurred_at<:b
              and session_id_hash is not null
              and coalesce(page,'') not like '/admin%'
            order by session_id_hash, occurred_at
            limit 100000
        """), {"a": dt_from(), "b": dt_to()})).all()

        trans: Counter = Counter()
        entries: Counter = Counter()
        exits: Counter = Counter()
        prev_s, prev_p = None, None
        last_by_s: dict = {}
        first_by_s: dict = {}
        for s, page, _ts in nav:
            if not page:
                continue
            if s not in first_by_s:
                first_by_s[s] = page
                entries[page] += 1
            if prev_s == s and prev_p and prev_p != page:
                trans[(prev_p, page)] += 1
            prev_s, prev_p = s, page
            last_by_s[s] = page
        for page in last_by_s.values():
            exits[page] += 1
        top_trans = [{"from": a, "to": b, "n": n} for (a, b), n in trans.most_common(50)]
        write_csv(OUT / "behavior_transitions.csv", top_trans, ["from", "to", "n"])

        dead = (await db.execute(text("""
            select count(*) filter (where is_dead) as dead,
                   count(*) filter (where is_rage) as rage,
                   count(*) as clicks
            from behavior_events
            where event_type='click' and occurred_at>=:a and occurred_at<:b
        """), {"a": dt_from(), "b": dt_to()})).mappings().one()

        report["behavior"] = {
            "event_types": {k: int(v) for k, v in et},
            "family_views": dict(fam.most_common()),
            "top_pages": pv_rows[:50],
            "dwell_top": dwell_rows[:30],
            "session_depth": {
                k: (float(v) if v is not None and not isinstance(v, int) else v)
                for k, v in dict(depth).items()
            },
            "top_entries": [{"page": p, "n": n} for p, n in entries.most_common(30)],
            "top_exits": [{"page": p, "n": n} for p, n in exits.most_common(30)],
            "top_transitions": top_trans[:30],
            "clicks": {k: int(v or 0) for k, v in dict(dead).items()},
        }

        canons = {
            "inflation_today": "/today/cpi",
            "inflation_chart": "/indicator/cpi + inflation-annual",
            "inflation": "/today/cpi + /indicator/cpi",
            "key_rate": "/today/key-rate",
            "fx": "/today/usd-rub",
            "gdp": "/indicator/gdp-nominal",
            "unemployment": "/indicator/unemployment",
            "wages": "/indicator/wages-nominal",
            "fuel": "/today/fuel-ai92",
            "housing": "/indicator/housing-price-*",
            "gold": "/today/gold-price",
            "imoex": "/today/imoex",
            "region": "/region/* + ratings",
        }

        def match_pages(bname: str) -> list[dict]:
            out = []
            for r in pv_rows:
                p = r["page"] or ""
                ok = False
                if bname == "inflation_today":
                    ok = "/today/cpi" in p
                elif bname in ("inflation_chart", "inflation"):
                    ok = "/indicator/cpi" in p or "inflation" in p or "/today/cpi" in p or "/category/prices" in p
                elif bname == "key_rate":
                    ok = "key-rate" in p
                elif bname == "fx":
                    ok = any(x in p for x in ("usd-rub", "eur-rub", "cny-rub", "/today/usd", "/today/eur", "/today/cny"))
                elif bname == "gdp":
                    ok = "gdp" in p
                elif bname == "unemployment":
                    ok = "unemployment" in p
                elif bname == "wages":
                    ok = "wages" in p
                elif bname == "fuel":
                    ok = "fuel" in p
                elif bname == "housing":
                    ok = "housing" in p
                elif bname == "gold":
                    ok = "gold" in p
                elif bname == "imoex":
                    ok = "imoex" in p
                elif bname == "region":
                    ok = p.startswith("/region")
                if ok:
                    out.append(r)
            return out

        cross = []
        for bname, canon in canons.items():
            wm_b = next((x for x in bucket_wm if x["bucket"] == bname), None)
            int_b = next((x for x in int_buckets if x["bucket"] == bname), None)
            met_b = next((x for x in met_buckets if x["bucket"] == bname), None)
            pages_hit = match_pages(bname)
            cross.append({
                "bucket": bname,
                "canon": canon,
                "wm_imp": wm_b["imp"] if wm_b else 0,
                "wm_clk": wm_b["clk"] if wm_b else 0,
                "wm_pos": wm_b["avg_pos_weighted"] if wm_b else None,
                "wm_ctr": wm_b["ctr"] if wm_b else None,
                "internal_searches": int_b["count"] if int_b else 0,
                "metrika_visits": met_b["visits"] if met_b else 0,
                "onsite_views_matched": sum(r["views"] for r in pages_hit),
            })
        write_csv(OUT / "cross_demand_coverage.csv", cross,
                  ["bucket", "canon", "wm_imp", "wm_clk", "wm_pos", "wm_ctr",
                   "internal_searches", "metrika_visits", "onsite_views_matched"])
        report["cross"] = cross

        (OUT / "report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )

        print("OUT", OUT)
        print("WM", len(wm_rows), "imp", report["webmaster"]["total_imp"], "clk", report["webmaster"]["total_clk"])
        print("Internal", total_q, "select_rate", report["internal_search"]["select_rate"], "zero_rate", report["internal_search"]["zero_rate"])
        print("Buckets:", [(x["bucket"], x["imp"], x["clk"], x["avg_pos_weighted"]) for x in bucket_wm[:15]])


if __name__ == "__main__":
    asyncio.run(main())
