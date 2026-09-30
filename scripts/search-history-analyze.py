#!/usr/bin/env python3
"""Analyze retained client search journeys without claiming to know every key.

Raw output stays under ignored analytics/. Client sessionStorage session !=
server 30-minute session != person. 'human_supported' is evidence, not identity.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timedelta
import gzip
import hashlib
import json
import os
from pathlib import Path
import re


def read_rows(folder: Path, name: str):
    with gzip.open(folder / (name + ".ndjson.gz"), "rt", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle]


def dt(value):
    return datetime.fromisoformat(value) if value else None


def context(event):
    return (event.get("params_json") or {}).get("context") or "unrecorded"


def query(event):
    params = event.get("params_json") or {}
    return str(params.get("q", params.get("query", "")))


def as_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def analyze(folder: Path, minimum: int = 150):
    os.umask(0o077)
    folder.chmod(0o700)
    searches = read_rows(folder, "search_events")
    frontend = read_rows(folder, "journey_frontend_events")
    behavior = read_rows(folder, "journey_behavior_events")
    portraits = {r["session_id_hash"]: r for r in read_rows(folder, "journey_behavior_sessions")}
    server_by_visitor = defaultdict(list)
    for row in read_rows(folder, "journey_server_sessions"):
        server_by_visitor[row["visitor_id_hash"]].append(row)
    grouped = defaultdict(list)
    f_by_session = defaultdict(list)
    b_by_session = defaultdict(list)
    for row in searches:
        grouped[row["session_id_hash"]].append(row)
    for row in frontend:
        f_by_session[row["session_id_hash"]].append(row)
    for row in behavior:
        b_by_session[row["session_id_hash"]].append(row)
    bot_re = re.compile(r"bot|spider|crawl|headless|phantom|selenium|puppeteer|playwright|python|httpx|curl/", re.I)
    journeys = []
    for sid, events in grouped.items():
        events.sort(key=lambda r: (r["occurred_at"], r["id"]))
        portrait = portraits.get(sid) or {}
        be = b_by_session[sid]
        fe = f_by_session[sid]
        by_type = Counter(r["event_type"] for r in be)
        active_ms = sum(as_int((r.get("params_json") or {}).get("active_ms")) or 0 for r in be if r["event_type"] == "dwell")
        visible_active_ms = sum(as_int((r.get("params_json") or {}).get("active_ms")) or 0 for r in be
                                if r["event_type"] == "dwell" and (r.get("params_json") or {}).get("attention_version") == 2)
        scroll = max((as_int((r.get("params_json") or {}).get("scroll_pct")) or 0 for r in be), default=0)
        synthetic_clicks = sum(1 for r in be if r["event_type"] == "click" and (r.get("params_json") or {}).get("synthetic") is True)
        normal_clicks = by_type["click"] - synthetic_clicks
        server = {}
        for event in events:
            when = dt(event["occurred_at"])
            for row in server_by_visitor.get(event.get("visitor_id_hash"), []):
                if dt(row["started_at"]) - timedelta(minutes=1) <= when <= dt(row["ended_at"]) + timedelta(minutes=1):
                    server[row["id"]] = row
        servers = list(server.values())
        reasons = []
        if portrait.get("is_webdriver"):
            reasons.append("webdriver")
        if bot_re.search(portrait.get("ua_raw") or ""):
            reasons.append("explicit_bot_ua")
        if portrait.get("device_type") == "desktop" and (portrait.get("screen_w") or 0) >= 600 and portrait.get("screen_w") == portrait.get("screen_h"):
            reasons.append("square_desktop_screen")
        if (portrait.get("cpu_cores") or 0) > 64:
            reasons.append("server_cpu")
        if any(r.get("is_bot") for r in servers):
            reasons.append("stored_server_bot")
        if by_type["click"] > 0 and synthetic_clicks == by_type["click"]:
            reasons.append("all_clicks_synthetic")
        if any(r.get("is_internal") for r in servers):
            classification = "internal"
        elif reasons:
            classification = "bot_signals"
        elif normal_clicks > 0 or visible_active_ms > 0 or (by_type["move"] > 0 and scroll > 0):
            classification = "human_supported"
        else:
            classification = "unknown"
        seq = [{"id": e["id"], "time_utc": e["occurred_at"], "event": e["event_name"],
                "context": context(e), "q": query(e), "results": (e.get("params_json") or {}).get("results"),
                "selected_code": (e.get("params_json") or {}).get("code"),
                "selected_position": (e.get("params_json") or {}).get("position"), "url": e.get("url")}
               for e in events]
        routes = []
        for e in be:
            if e["event_type"] == "pageview" and (not routes or routes[-1]["page"] != e.get("page")):
                routes.append({"time_utc": e["occurred_at"], "page": e.get("page")})
        if not routes:
            for e in fe:
                if e.get("url") and (not routes or routes[-1]["page"] != e["url"]):
                    routes.append({"time_utc": e["occurred_at"], "page": e["url"]})
        query_events = [e for e in seq if e["event"] in ("search_query", "compare_search", "table_search")]
        zero_events = [e for e in query_events if as_int(e["results"]) == 0]
        selects = [e for e in seq if e["event"] == "search_select"]
        abandons = [e for e in seq if e["event"] == "search_abandon"]
        deep_selections = [e for e in selects if (as_int(e["selected_position"]) or 0) > 3]
        if zero_events:
            observed = "Recorded zero-result query; catalog coverage versus matching failure remains unverified."
            preferred = "Explain the searched scope; offer plausible exact entities, typo/synonym alternatives and a broader-scope action."
        elif deep_selections:
            observed = "An entity was selected below the first three results."
            preferred = "Rank country, indicator concept, frequency and scope against the full intent, then expose why the hit matches."
        elif abandons and not selects:
            observed = "The global dialog closed without a recorded selection. Intent satisfaction is unknown."
            preferred = "Keep the query and filters visible; allow scope expansion and identify unavailable data before the user leaves."
        elif len(query_events) > 1:
            observed = "Multiple retained query states in one technical session; rapid edits between debounce samples are absent."
            preferred = "Use one retrieval contract across fields, preserve context, and record search-only changes with interaction id and sequence."
        elif selects:
            observed = "A selection was recorded; downstream page arrival alone does not prove the selected data answered the intent."
            preferred = "Open the intended country/region/indicator variant and measure usable data arrival with the same interaction id."
        else:
            observed = "Only a retained query state is available; outcome cannot be reconstructed reliably."
            preferred = "Record query state, pending/loaded result state and a terminal select/clear/close outcome."
        journeys.append({"journey_id": "search-" + sid[:12], "session_id_hash": sid,
                         "classification": classification, "bot_signals": reasons,
                         "first_search_utc": events[0]["occurred_at"], "last_search_utc": events[-1]["occurred_at"],
                         "contexts": sorted(set(context(e) for e in events)),
                         "device": portrait.get("device_type") or "unrecorded", "language": portrait.get("language"),
                         "portrait_present": bool(portrait), "synthetic_portrait": portrait.get("is_synthetic"),
                         "search_events": len(events), "query_events": len(query_events), "zero_result_events": len(zero_events),
                         "select_events": len(selects), "abandon_events": len(abandons), "deep_selection_events": len(deep_selections),
                         "frontend_events": len(fe), "behavior_events": len(be), "behavior_types": dict(by_type),
                         "normal_clicks": normal_clicks, "synthetic_clicks": synthetic_clicks,
                         "active_ms": active_ms, "attention_v2_active_ms": visible_active_ms, "max_scroll_pct": scroll,
                         "server_session_ids": sorted(server), "search_sequence": seq, "page_path": routes,
                         "observed_problem": observed, "preferred_behavior": preferred,
                         "evidence_limit": "Client technical session; stored query snapshots, not all keystrokes. Human status is an inference; query count is not search attempt count."})
    journeys.sort(key=lambda r: r["first_search_utc"])
    surfaces = defaultdict(Counter)
    events_by_name = Counter()
    results_by_event = defaultdict(Counter)
    for e in searches:
        events_by_name[e["event_name"]] += 1
        if e["event_name"] == "search_query":
            count = as_int((e.get("params_json") or {}).get("results"))
            surfaces[context(e)].update({"query_events": 1, "zero_results": int(count == 0), "results_unknown": int(count is None)})
        if e["event_name"] in ("search_query", "compare_search", "table_search"):
            c = as_int((e.get("params_json") or {}).get("results"))
            results_by_event[e["event_name"]]["zero" if c == 0 else "nonzero" if c is not None else "unknown"] += 1
    selected_positions = Counter(str(as_int((e.get("params_json") or {}).get("position")) or "unrecorded") for e in searches if e["event_name"] == "search_select")
    classification_by_session = {j["session_id_hash"]: j["classification"] for j in journeys}
    weak_clicks = []
    demand = defaultdict(Counter)
    for e in searches:
        params = e.get("params_json") or {}
        q = query(e)
        cls = classification_by_session[e["session_id_hash"]]
        if e["event_name"] == "search_select":
            weak_clicks.append({"event_id": e["id"], "occurred_at_utc": e["occurred_at"],
                                "session_id_hash": e["session_id_hash"], "classification": cls,
                                "q": q, "selected_code": params.get("code"), "scope": params.get("scope"),
                                "country": params.get("country"), "position": params.get("position"),
                                "label_kind": "observed_selection; relevance unjudged; no candidate set"})
        if e["event_name"] in ("search_query", "compare_search", "table_search"):
            key = (e["event_name"], context(e), q)
            demand[key].update({"events": 1, "zero_results": int(as_int(params.get("results")) == 0),
                                "human_supported_events": int(cls == "human_supported"),
                                "internal_events": int(cls == "internal"), "unknown_events": int(cls == "unknown")})
    # Round-robin strata so the 150 examples do not consist only of one busy user/surface.
    eligible = [j for j in journeys if j["classification"] == "human_supported"]
    buckets = defaultdict(list)
    for j in eligible:
        outcome = "zero" if j["zero_result_events"] else "deep" if j["deep_selection_events"] else "abandon" if j["abandon_events"] and not j["select_events"] else "select" if j["select_events"] else "query_only"
        buckets[(j["contexts"][0], j["device"], outcome)].append(j)
    chosen = []
    while len(chosen) < minimum and any(buckets.values()):
        for key in sorted(buckets):
            if buckets[key] and len(chosen) < minimum:
                chosen.append(buckets[key].pop(0))
    summary = {"total_search_events": len(searches), "technical_client_sessions": len(journeys),
               "distinct_visitors_nonnull": len(set(e["visitor_id_hash"] for e in searches if e.get("visitor_id_hash"))),
               "events_by_name": dict(events_by_name), "search_query_surfaces": {k: dict(v) for k, v in sorted(surfaces.items())},
               "result_counts": {k: dict(v) for k, v in results_by_event.items()}, "selection_positions": dict(selected_positions),
               "classification": dict(Counter(j["classification"] for j in journeys)),
               "journeys_with_zero_results": sum(bool(j["zero_result_events"]) for j in journeys),
               "journeys_with_selection": sum(bool(j["select_events"]) for j in journeys),
               "journeys_with_reformulation_samples": sum(j["query_events"] > 1 for j in journeys),
               "human_supported_journeys_reviewed": len(eligible), "detailed_stratified_journeys": len(chosen),
               "weak_click_labels": len(weak_clicks),
               "nonempty_human_supported_click_labels": sum(bool(r["q"].strip()) and r["classification"] == "human_supported" for r in weak_clicks),
               "raw_keystrokes_available": False, "causal_relevance_labels_available": False,
               "sampling": "All client sessions analyzed; first 150 round-robin by retained context/device/outcome with positive human-use signals and no detected internal/bot evidence.",
               "limits": ["A client session can span multiple server sessions and tabs/time; it is not a person or an attempt.",
                          "No bot signal does not establish human identity; movement/click/attention are only support.",
                          "Raw input edits, scope/filter/result candidate sets, result-loading state, downstream answer satisfaction are absent.",
                          "Zero results can mean absent coverage, a matching/ranking defect, or a sampled loading state.",
                          "Earlier events have missing contexts/visitors and no behavior stream."]}
    (folder / "analysis-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    with gzip.open(folder / "all-client-journeys.ndjson.gz", "wt", encoding="utf-8") as handle:
        for j in journeys:
            handle.write(json.dumps(j, ensure_ascii=False, separators=(",", ":")) + "\n")
    with gzip.open(folder / "historical-search-clicks.ndjson.gz", "wt", encoding="utf-8") as handle:
        for row in weak_clicks:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    with (folder / "query-demand.csv").open("w", newline="", encoding="utf-8") as handle:
        fields_demand = ["event", "context", "q", "events", "zero_results", "human_supported_events", "internal_events", "unknown_events"]
        writer = csv.DictWriter(handle, fields_demand)
        writer.writeheader()
        for (event, ctx, q), values in sorted(demand.items(), key=lambda item: (-item[1]["events"], item[0])):
            writer.writerow({"event": event, "context": ctx, "q": q, **values})
    (folder / "journeys-150.json").write_text(json.dumps(chosen, ensure_ascii=False, indent=2) + "\n")
    fields = ["journey_id", "classification", "first_search_utc", "last_search_utc", "contexts", "device", "query_events",
              "zero_result_events", "select_events", "abandon_events", "deep_selection_events", "normal_clicks", "synthetic_clicks",
              "attention_v2_active_ms", "max_scroll_pct", "observed_problem", "preferred_behavior"]
    with (folder / "journeys-150.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fields)
        writer.writeheader()
        for j in chosen:
            writer.writerow({k: ";".join(j[k]) if isinstance(j[k], list) else j[k] for k in fields})
    manifest_path = folder / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["analysis_outputs"] = {}
    for filename in ["analysis-summary.json", "all-client-journeys.ndjson.gz", "journeys-150.json", "journeys-150.csv", "historical-search-clicks.ndjson.gz", "query-demand.csv"]:
        p = folder / filename
        manifest["analysis_outputs"][filename] = {"sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "bytes": p.stat().st_size}
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if len(chosen) < minimum:
        raise RuntimeError(f"Only {len(chosen)} human-supported retained journeys; minimum {minimum} not established")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("analytics/search-audit/2026-09-30"))
    parser.add_argument("--minimum", type=int, default=150)
    args = parser.parse_args()
    analyze(args.input, args.minimum)
