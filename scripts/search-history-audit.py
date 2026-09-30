#!/usr/bin/env python3
"""Export the complete retained search history and only its journey context.

Production access is read-only: one REPEATABLE READ / READ ONLY transaction.
Raw query text and pseudonymous identifiers stay in the ignored analytics/ tree.
No account/credential/session-cookie tables are copied. Uses only stdlib.
"""
from __future__ import annotations

import argparse
from collections import Counter
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import shlex
from datetime import datetime, timezone

SEARCH_PREDICATE = """event_name ILIKE '%search%' OR event_name ILIKE '%query%'
 OR params_json::jsonb ? 'q' OR params_json::jsonb ? 'query'"""
SEARCH_CTE = f"WITH searches AS (SELECT * FROM frontend_events WHERE {SEARCH_PREDICATE})"
SSH = ["ssh", "-C", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10",
       "-o", "ControlPath=none", "-o", "ServerAliveInterval=20",
       "-o", "ServerAliveCountMax=10", "-J", "tts-proxy", "fe-prod"]
TABLES = ["frontend_events", "behavior_events", "behavior_sessions", "server_sessions",
          "raw_metrika_visits", "raw_metrika_hits", "metrika_search_phrases",
          "webmaster_search_queries", "gsc_search_queries"]


def sql_export() -> str:
    quoted = ",".join("'" + t + "'" for t in TABLES)
    datasets = {
        "search_events": (f"{SEARCH_CTE} SELECT * FROM searches ORDER BY occurred_at,id", "occurred_at"),
        "journey_frontend_events": (
            f"{SEARCH_CTE} SELECT f.* FROM frontend_events f WHERE f.session_id_hash IN "
            "(SELECT DISTINCT session_id_hash FROM searches) ORDER BY f.occurred_at,f.id", "occurred_at"),
        "journey_behavior_events": (
            f"{SEARCH_CTE} SELECT b.* FROM behavior_events b WHERE b.session_id_hash IN "
            "(SELECT DISTINCT session_id_hash FROM searches) ORDER BY b.occurred_at,b.id", "occurred_at"),
        "journey_behavior_sessions": (
            f"{SEARCH_CTE} SELECT b.* FROM behavior_sessions b WHERE b.session_id_hash IN "
            "(SELECT DISTINCT session_id_hash FROM searches) ORDER BY b.started_at,b.session_id_hash", "started_at"),
        "journey_server_sessions": (
            f"{SEARCH_CTE} SELECT b.* FROM server_sessions b WHERE EXISTS "
            "(SELECT 1 FROM searches s WHERE s.visitor_id_hash=b.visitor_id_hash "
            "AND s.occurred_at >= b.started_at - interval '1 minute' "
            "AND s.occurred_at <= b.ended_at + interval '1 minute') ORDER BY b.started_at,b.id", "started_at"),
        "external_raw_metrika_visits": (
            "SELECT * FROM raw_metrika_visits WHERE nullif(trim(search_phrase),'') IS NOT NULL ORDER BY start_time,id", "start_time"),
        "metrika_search_phrases": ("SELECT * FROM metrika_search_phrases ORDER BY date,id", "date"),
        "webmaster_search_queries": ("SELECT * FROM webmaster_search_queries ORDER BY date,id", "date"),
        "gsc_search_queries": ("SELECT * FROM gsc_search_queries ORDER BY date,id", "date"),
        "raw_metrika_search_hits": (
            "SELECT * FROM raw_metrika_hits WHERE event_name ILIKE '%search%' OR event_name ILIKE '%query%' ORDER BY event_time,id", "event_time"),
    }
    sql = ["BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;",
           "SET LOCAL statement_timeout='120000';",
           "SET LOCAL lock_timeout='3000';",
           "SET LOCAL idle_in_transaction_session_timeout='120000';",
           "SET LOCAL work_mem='8MB';",
           "SELECT jsonb_build_object('dataset','_metadata','row',jsonb_build_object("
           "'snapshot_utc', current_timestamp AT TIME ZONE 'UTC',"
           "'transaction_read_only',current_setting('transaction_read_only'),"
           "'transaction_isolation',current_setting('transaction_isolation'),"
           "'postgres_version',current_setting('server_version')));",
           "SELECT jsonb_build_object('dataset','_schemas','row',to_jsonb(s)) FROM "
           "(SELECT table_name,column_name,data_type,is_nullable FROM information_schema.columns "
           f"WHERE table_schema='public' AND table_name IN ({quoted}) ORDER BY table_name,ordinal_position) s;",
           "SELECT jsonb_build_object('dataset','_inventory','row',to_jsonb(s)) FROM "
           "(SELECT relname,n_live_tup,pg_total_relation_size(relid) AS total_bytes "
           f"FROM pg_stat_user_tables WHERE relname IN ({quoted}) ORDER BY relname) s;"]
    for name, (query, time_column) in datasets.items():
        # Declare empty datasets too, so a missing output is never mistaken for zero.
        sql.append(f"SELECT jsonb_build_object('dataset','_dataset','row',jsonb_build_object('name','{name}','time_column','{time_column}'));")
        sql.append(f"SELECT jsonb_build_object('dataset','{name}','row',to_jsonb(r)-'user_id') FROM ({query}) r;")
    sql += ["COMMIT;"]
    return "\n".join(sql)


def export(out: Path) -> None:
    os.umask(0o077)
    out.mkdir(parents=True, exist_ok=True, mode=0o700)
    out.chmod(0o700)
    sql = sql_export()
    (out / "export.sql").write_text(sql, encoding="utf-8")
    meta = {"started_utc": datetime.now(timezone.utc).isoformat(),
            "source": "production PostgreSQL, /opt/rosstat",
            "access": "SSH -> docker exec psql; one read-only repeatable-read snapshot",
            "selection": SEARCH_PREDICATE, "datasets": {}, "schemas": [], "inventory": []}
    rev = subprocess.run(SSH + ["git -C /opt/rosstat rev-parse HEAD"], capture_output=True, text=True, check=True)
    meta["production_checkout_sha"] = rev.stdout.strip()
    local = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True)
    meta["local_checkout_sha"] = local.stdout.strip()
    handles = {}
    stderr_path = out / "export.stderr.log"
    with stderr_path.open("w") as err:
        proc = subprocess.Popen(SSH + ["docker exec -i rosstat-postgres-1 psql -X -qAt -v ON_ERROR_STOP=1 -U rustats -d rustats"],
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=err, text=True, encoding="utf-8")
        assert proc.stdin and proc.stdout
        proc.stdin.write(sql)
        proc.stdin.close()
        try:
            for line in proc.stdout:
                record = json.loads(line)
                name, row = record["dataset"], record["row"]
                if name == "_metadata":
                    meta.update(row)
                elif name in ("_schemas", "_inventory"):
                    meta["schemas" if name == "_schemas" else "inventory"].append(row)
                elif name == "_dataset":
                    key = row["name"]
                    meta["datasets"][key] = {"rows": 0, "min_time": None, "max_time": None,
                                               "time_column": row["time_column"], "file": key + ".ndjson.gz"}
                    handles[key] = gzip.open(out / (key + ".ndjson.gz"), "wt", encoding="utf-8")
                else:
                    info = meta["datasets"][name]
                    handles[name].write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
                    info["rows"] += 1
                    value = row.get(info["time_column"])
                    if value:
                        info["min_time"] = min(value, info["min_time"] or value)
                        info["max_time"] = max(value, info["max_time"] or value)
            proc.stdout.close()
            result = proc.wait()
            if result:
                raise RuntimeError(f"Read-only export failed (exit {result}); see {stderr_path}")
        finally:
            for handle in handles.values():
                handle.close()
    meta["completed_utc"] = datetime.now(timezone.utc).isoformat()
    for name, info in meta["datasets"].items():
        path = out / info["file"]
        info["bytes_gzip"] = path.stat().st_size
        info["sha256_gzip"] = hashlib.sha256(path.read_bytes()).hexdigest()
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            reread_count = sum(1 for _ in handle)
        if reread_count != info["rows"]:
            raise RuntimeError(f"{name}: gzip verification failed")
        info["verified_gzip_rows"] = reread_count
    (out / "manifest.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"snapshot_utc": meta["snapshot_utc"],
                      "datasets": {name: info["rows"] for name, info in meta["datasets"].items()}}, ensure_ascii=False))


def export_clickhouse_copy(out: Path) -> None:
    """Keep the derived copy separately; plain MergeTree can contain duplicates."""
    os.umask(0o077)
    out.chmod(0o700)
    sql = """SELECT id,event_name,session_id_hash,visitor_id_hash,authed,url,params,
 occurred_at,toUnixTimestamp(occurred_at) AS occurred_at_epoch,timezone() AS source_timezone
 FROM analytics.frontend_events WHERE event_name ILIKE '%search%' OR event_name ILIKE '%query%'
 OR JSONHas(params,'q') OR JSONHas(params,'query') ORDER BY id,occurred_at FORMAT JSONEachRow"""
    command = "docker exec rosstat-clickhouse-1 clickhouse-client --readonly 1 --max_execution_time 30 --query " + shlex.quote(sql)
    result = subprocess.run(SSH + [command], capture_output=True, text=True, check=True)
    rows = [json.loads(line) for line in result.stdout.splitlines()]
    for row in rows:
        row["id"] = int(row["id"])
    path = out / "clickhouse-search-copy.ndjson.gz"
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    with gzip.open(out / "search_events.ndjson.gz", "rt", encoding="utf-8") as handle:
        pg = {row["id"]: row for row in map(json.loads, handle)}
    ch = {row["id"]: row for row in rows}
    different = []
    time_offsets = Counter()
    for row_id in pg.keys() & ch.keys():
        pg_seconds = int(datetime.fromisoformat(pg[row_id]["occurred_at"]).replace(tzinfo=timezone.utc).timestamp())
        time_offsets[str(int(ch[row_id]["occurred_at_epoch"]) - pg_seconds)] += 1
        if pg[row_id]["event_name"] != ch[row_id]["event_name"] or (pg[row_id].get("params_json") or {}) != json.loads(ch[row_id]["params"] or "{}"):
            different.append(row_id)
    manifest_path = out / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["clickhouse_copy"] = {
        "file": path.name, "exported_utc": datetime.now(timezone.utc).isoformat(),
        "access": "ClickHouse readonly=1 SELECT; separate later snapshot from PostgreSQL",
        "rows": len(rows), "unique_ids": len(ch), "duplicate_rows_by_id": len(rows) - len(ch),
        "ids_only_in_clickhouse": sorted(ch.keys() - pg.keys()),
        "ids_only_in_postgres_snapshot": sorted(pg.keys() - ch.keys()),
        "same_id_different_event_or_params": sorted(different),
        "clickhouse_epoch_minus_pg_utc_seconds": dict(time_offsets),
        "source_timezones": sorted(set(row["source_timezone"] for row in rows)),
        "min_displayed_time": min((row["occurred_at"] for row in rows), default=None),
        "max_displayed_time": max((row["occurred_at"] for row in rows), default=None),
        "bytes_gzip": path.stat().st_size, "sha256_gzip": hashlib.sha256(path.read_bytes()).hexdigest(),
        "interpretation": "Derived copy, not independent people/queries. Never sum it with PostgreSQL. Displayed CH times can differ from naive UTC PG times; event ids and params are compared directly."}
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    info = manifest["clickhouse_copy"]
    print(json.dumps({key: len(value) if isinstance(value, list) else value
                      for key, value in info.items()}, ensure_ascii=False))


def export_nginx_search_requests(out: Path) -> None:
    """Read all retained security rotations, selecting requests to search APIs.

    HTTP requests contain only states transmitted to the server; browser-local
    field edits are absent. Raw client IP is hashed on the server before export.
    """
    os.umask(0o077)
    out.chmod(0o700)
    code = r'''
import pathlib,gzip,json,re,hashlib
from urllib.parse import urlsplit,parse_qs
root=pathlib.Path('/var/log/rosstat-nginx')
for path in sorted(root.glob('security.log*')):
    opened_bytes=path.stat().st_size
    lines=matches=0
    first=last=None
    opener=gzip.open if path.suffix=='.gz' else open
    with opener(path,'rt',encoding='utf-8',errors='replace') as handle:
        for line in handle:
            lines+=1
            if first is None:first=line.split(' ',1)[0]
            last=line.split(' ',1)[0]
            if '/search' not in line:continue
            m=re.match(r'(\S+) (\S+) (\d+) "([^"]+)" "(.*)"',line)
            if not m:continue
            bits=m[4].split(' ')
            if len(bits)<2:continue
            url=bits[1]
            pathpart=urlsplit(url).path
            if not (pathpart.startswith('/api/') and '/search' in pathpart):continue
            params=parse_qs(urlsplit(url).query,keep_blank_values=True)
            row={'source_file':path.name,'source_line':lines,'time':m[1],
                 'ip_hash':hashlib.sha256(m[2].encode()).hexdigest(),
                 'status':int(m[3]),'request':m[4],'ua':m[5],
                 'query_states':params.get('q',params.get('query',[])), 'api_path':pathpart}
            print(json.dumps({'dataset':'requests','row':row},ensure_ascii=False))
            matches+=1
    print(json.dumps({'dataset':'sources','row':{'file':path.name,'opened_bytes':opened_bytes,
         'lines_scanned':lines,'matched_requests':matches,'first_time':first,'last_time':last}}))
'''
    proc = subprocess.run(SSH + ["python3 -"], input=code, capture_output=True, text=True, check=True)
    requests, sources = [], []
    for line in proc.stdout.splitlines():
        record = json.loads(line)
        (requests if record["dataset"] == "requests" else sources).append(record["row"])
    path = out / "nginx-search-requests.ndjson.gz"
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        for row in requests:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    manifest_path = out / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["nginx_search_requests"] = {
        "file": path.name, "exported_utc": datetime.now(timezone.utc).isoformat(),
        "access": "Read-only streaming of all retained /var/log/rosstat-nginx/security.log*",
        "rows": len(requests), "sources": sources,
        "first_request_time": min((r["time"] for r in requests), default=None),
        "last_request_time": max((r["time"] for r in requests), default=None),
        "bytes_gzip": path.stat().st_size, "sha256_gzip": hashlib.sha256(path.read_bytes()).hexdigest(),
        "limits": "Partial query states transmitted to an API, potentially transformed by synonym expansion; bots and users combined. Not all input changes, not every search surface, not all-time logs; live file can grow during reading. Raw client IP never leaves the server."}
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    info = manifest["nginx_search_requests"]
    print(json.dumps({k: len(v) if k == "sources" else v for k, v in info.items()}, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("analytics/search-audit/2026-09-30"))
    parser.add_argument("--print-sql", action="store_true", help="Show read-only SQL without connecting")
    parser.add_argument("--clickhouse-only", action="store_true", help="Export/reconcile the derived copy against an existing PG snapshot")
    parser.add_argument("--nginx-only", action="store_true", help="Export all retained search API request states from nginx rotations")
    args = parser.parse_args()
    if args.print_sql:
        print(sql_export())
    elif args.clickhouse_only:
        export_clickhouse_copy(args.output)
    elif args.nginx_only:
        export_nginx_search_requests(args.output)
    else:
        export(args.output)
        export_clickhouse_copy(args.output)
        export_nginx_search_requests(args.output)


if __name__ == "__main__":
    main()
