#!/usr/bin/env python3
"""Isolated executable mechanism evidence, not runtime/production acceptance.

Loads selected function AST bodies (no application imports), executes them against
explicit in-memory doubles, and asserts observable branches. SQL construction,
Redis time, transaction visibility, HTTP and task scheduling are doubles. No
network, main DB, Redis, credentials or production access. Each result records
the premises and the boundary of what the probe establishes.
"""
from __future__ import annotations
import argparse
import ast
import asyncio
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
import hashlib
import importlib.util
import json
import logging
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace as NS

ROOT = Path(__file__).resolve().parents[2]
RESULT = "docs/code-review/backend-mechanism-probes-2026-09-30.json"
SOURCE_ANCHORS = []


def extracted(path, name, namespace):
    source = (ROOT / path).read_text()
    tree = ast.parse(source, path)
    fn = next(node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name)
    fn.decorator_list = []
    program = ast.Module(body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0), fn], type_ignores=[])
    ast.fix_missing_locations(program)
    exec(compile(program, path, "exec"), namespace)
    SOURCE_ANCHORS.append({"path": path, "function": name, "line": fn.lineno, "end_line": fn.end_lineno,
                           "sha256": hashlib.sha256(source.encode()).hexdigest()})
    return namespace[name]


class Field:
    def __init__(self, name): self.name = name
    def __eq__(self, other): return (self.name, "eq", other)
    def __ge__(self, other): return (self.name, "ge", other)
    def __lt__(self, other): return (self.name, "lt", other)
    def __gt__(self, other): return (self.name, "gt", other)
    def in_(self, values): return (self.name, "in", values)
    def isnot(self, value): return (self.name, "isnot", value)
    def is_distinct_from(self, value): return (self.name, "distinct", value)


class Query:
    def __init__(self, kind, *columns):
        self.kind, self.columns, self.filters, self.entries = kind, columns, [], []
        self.excluded = NS(value=Field("excluded.value"))
    def values(self, values): self.entries = values; return self
    def on_conflict_do_update(self, **_): return self
    def returning(self, *_): return self
    def where(self, *conditions): self.filters.extend(conditions); return self
    def order_by(self, *_): return self
    def limit(self, *_): return self
    def distinct(self): return self
    def select_from(self, table): self.source_table=table; return self


class Result:
    def __init__(self, rows=(), rowcount=0): self.rows, self.rowcount = list(rows), rowcount
    def all(self): return self.rows
    def fetchall(self): return self.rows
    def scalars(self): return self
    def scalar(self): return self.rows[0] if self.rows else None
    def __iter__(self): return iter(self.rows)


def model(name, fields):
    item = NS(**{field: Field(name + "." + field) for field in fields})
    item.__table__ = NS(c=item, delete=lambda: Query("delete", name), insert=lambda: Query("insert", name))
    return item


def sql_namespace():
    return {"select": lambda *cols: Query("select", *cols), "delete": lambda table: Query("delete", table),
            "pg_insert": lambda table: Query("insert", table), "func": NS(coalesce=lambda *args: Field("coalesce")),
            "logger": logging.getLogger("isolated-probe")}


async def partial_replace():
    values = {date(2020, 1, 1): 1.0, date(2021, 1, 1): 2.0, date(2022, 1, 1): 3.0}
    original = dict(values)
    table = model("WorldDataPoint", ["id", "date", "indicator_id", "value"])
    class DB:
        async def execute(self, query):
            if query.kind == "insert":
                for row in query.entries: values[row["date"]] = row["value"]
                return Result([(1,) for _ in query.entries])
            if query.kind == "select": return Result(sorted(values))
            dates = query.filters[-1][2]
            for day in dates: del values[day]
            return Result(rowcount=len(dates))
    ns = {**sql_namespace(), "WorldDataPoint": table, "_UPSERT_CHUNK": 2000}
    fn = extracted("backend/app/services/world_national_ingest.py", "reconcile_points", ns)
    touched, removed = await fn(DB(), 1, [(date(2022,1,1),3.0)])
    assert removed == 2 and list(values) == [date(2022,1,1)]
    after_nonempty = dict(values)
    empty = await fn(DB(), 1, [])
    assert empty == (0,0) and values == after_nonempty
    return {"premise": "stored 2020/2021/2022; nonempty normalized response contains only 2022, with no completeness marker",
            "before": {str(k):v for k,v in original.items()}, "after": {str(k):v for k,v in values.items()},
            "removed": removed, "touched_double": touched, "empty_response_preserves": True,
            "establishes": "actual reconcile_points selects and deletes absent source dates; fake SQL result counts do not prove PostgreSQL behavior"}


async def invalidate_before_commit():
    trace, public, pending, cache = [], {"value":1}, {"value":2}, {}
    async def noop(*_): return None
    async def fetch(*_): return [(date(2022,1,1),2)], "https://fixture.invalid/"
    async def upsert(*_): trace.append("write_pending"); return 0,1
    async def invalidate(code):
        trace.append("invalidate")
        cache["new_namespace"] = public["value"]
        trace.append("concurrent_reader_cached_old_committed_value")
    class DB:
        async def commit(self): trace.append("commit"); public.update(pending)
        async def rollback(self): trace.append("rollback")
        def add(self,_): pass
    ns = {"logger": logging.getLogger("isolated-probe"), "fallback_reason": lambda _:None,
          "bulk_upsert": upsert, "cache_invalidate_indicator": invalidate,
          "_utcnow_naive": lambda:datetime(2026,9,30), "STATUS_SUCCESS":"success", "STATUS_NO_NEW_DATA":"no_new_data"}
    fn = extracted("backend/app/services/base_parser.py", "run", ns)
    parser = NS(replace_series=False, _fetch_and_parse=fetch, _validate=lambda p,c:p,
                _post_upsert=lambda *args:async_value((0,0)), _handle_forecasts=noop, _after_storage=noop)
    log = NS(error_message=None)
    await fn(parser, DB(), NS(id=1,code="fixture",model_config_json={}), log)
    assert trace.index("invalidate") < trace.index("commit") and cache["new_namespace"] == 1 and public["value"] == 2
    return {"premise": "reader runs after invalidate and before commit, and reads only committed old facts",
            "trace":trace, "database_after":public["value"], "cache_after":cache["new_namespace"],
            "establishes":"actual BaseParser.run orders invalidate before commit; visibility/reader interleaving is explicitly simulated, not live PG/Redis"}


async def async_value(value): return value


async def eurostat_remap_partial_failure():
    trace=[]
    ind=NS(slice_json={"unit":"old"},slice_hash="old")
    class DB:
        async def __aenter__(self): return self
        async def __aexit__(self,*_): return False
        async def get(self,*_): return ind
        async def commit(self): trace.append("remap_commit")
        async def execute(self,_): return Result([NS(code="DE",id=1,name_ru="Germany",slug="germany")])
    ns = {**sql_namespace(), "WorldIndicator":NS(), "async_session":DB}
    remap=extracted("backend/scripts/load-world-eurostat.py", "apply_remaps", ns)
    class Future:
        def result(self): return [NS(series_by_geo={"DE":[]},name="first"),NS(series_by_geo={"DE":[]},name="second")]
    class Pool:
        def __init__(self,**_): pass
        def __enter__(self): return self
        def __exit__(self,*_): return False
        def submit(self,*_,**__): return Future()
    async def persist(one,*_):
        trace.append("persist_"+one.name)
        if one.name == "second": raise RuntimeError("fixture slice failure")
        trace.append("first_slice_transaction_committed"); return 1,1
    async def bump(*_): trace.append("cache_bump")
    verdict=NS(remapped={1:({"unit":"new"},"new")},accept=True,reason="fixture",as_dict=lambda:{"accept":True})
    ns.update({"log":logging.getLogger("isolated-probe"), "WorldCountry":NS(), "WORLD_COUNTRIES":{"DE":("germany","Germany")},
        "select_datasets":lambda *_a,**_kw:async_value([{"dataset_id":"fixture","frequency":"M"}]),
        "ensure_countries":lambda *_:async_value({}), "ThreadPoolExecutor":Pool,"as_completed":list,
        "DEFAULT_WORKERS":1,"_parse_one":None,"check_structure":lambda *_:async_value(verdict),
        "persist_result":persist,"bump_namespaces":bump,"time":NS(time=lambda:1.0)})
    run=extracted("backend/scripts/load-world-eurostat.py", "run", ns)
    args=NS(themes="x",freq="M",limit=1,only=None,dry_run=False,workers=1,no_cache=True,structure_check=True)
    try: await run(args)
    except RuntimeError as exc: assert str(exc)=="fixture slice failure"
    else: raise AssertionError("expected slice failure")
    assert ind.slice_hash == "new" and trace[0] == "remap_commit" and "cache_bump" not in trace
    return {"premise":"accepted remap, first persist_result commits, second persist_result raises",
            "trace":trace,"metadata_hash_after":ind.slice_hash,
            "establishes":"actual loader.run/apply_remaps sequence leaves precommitted metadata and bypasses final bump on exception; DB atomicity of slice is source-established, simulated commit"}


async def session_window_boundary():
    t=datetime(2026,9,28,21,0)
    events=[NS(visitor_id_hash="v",session_id_hash="s",event_type="pageview",occurred_at=t-timedelta(minutes=2),page="/a",user_id=None,params_json={}),
            NS(visitor_id_hash="v",session_id_hash="s",event_type="pageview",occurred_at=t+timedelta(minutes=2),page="/b",user_id=None,params_json={})]
    behavior=model("BehaviorEvent",["visitor_id_hash","session_id_hash","event_type","occurred_at","page","user_id","params_json"])
    portrait=model("BehaviorSession",["session_id_hash","visitor_id_hash","channel","referrer","utm_source","utm_medium","yclid","device_type","is_webdriver","ua_raw","touch","screen_w","screen_h","cpu_cores","started_at"])
    frontend=model("FrontendEvent",["session_id_hash","event_name","occurred_at"])
    server=model("ServerSession",["visitor_id_hash","started_at"])
    output=[]
    class DB:
        def __init__(self): self.n=0
        async def execute(self,query,entries=None):
            self.n+=1
            if self.n==1:
                selected=[e for e in events if all(e.occurred_at>=v if op=="ge" else e.occurred_at<v if op=="lt" else True for f,op,v in query.filters)]
                return Result(selected)
            if query.kind=="insert": output.extend(entries)
            return Result()
        async def commit(self): pass
    module=ModuleType("app.services.analytics_marts"); module.admin_identity=lambda _:async_value((set(),set()))
    old=sys.modules.get(module.__name__); sys.modules[module.__name__]=module
    ns={**sql_namespace(),"BehaviorEvent":behavior,"BehaviorSession":portrait,"FrontendEvent":frontend,"ServerSession":server,
        "defaultdict":defaultdict,"timedelta":timedelta,"SESSION_GAP_MIN":30,"_SESSION_EVENT_TYPES":("pageview",),
        "msk_day":lambda d:(d+timedelta(hours=3)).date(),
        "_finalize_session":lambda visitor,chunk,*_a,**_kw:{"user_id":None,"started_at":str(chunk[0].occurred_at),"pageviews":len(chunk)}}
    fn=extracted("backend/app/tasks/analytics_rollups.py","sessionize",ns)
    try:
        whole=await fn(DB(),t-timedelta(days=1),until=t+timedelta(days=1)); whole_output=list(output);output.clear()
        left=await fn(DB(),t-timedelta(days=1),until=t)
        right=await fn(DB(),t,until=t+timedelta(days=1))
    finally:
        if old is None: del sys.modules[module.__name__]
        else: sys.modules[module.__name__]=old
    assert whole==1 and left+right==2
    return {"premise":"same visitor, two pageviews 4min apart across an MSK chunk boundary; no carry state between sessionize calls",
            "whole_count":whole,"chunked_count":left+right,"whole":whole_output,"chunked":output,
            "establishes":"actual sessionize event window and chunk logic split one <30min session; finalizer/admin/SQL are doubles, no observed BI impact"}


async def clickhouse_late_id():
    rows={2:NS(id=2,event_type="pageview",session_id_hash="s",visitor_id_hash="v",user_id=None,authed=False,page="/",element_path=None,
        element_text=None,is_dead=False,is_rage=False,params_json={},occurred_at=datetime(2026,9,30))}
    cursor={"behavior_events":0,"frontend_events":0}; inserted=[]
    fields=list(vars(rows[2])); behavior=model("BehaviorEvent",fields)
    frontend=model("FrontendEvent",["id","event_name","session_id_hash","visitor_id_hash","user_id","authed","url","params_json","occurred_at"])
    class DB:
        async def __aenter__(self): return self
        async def __aexit__(self,*_): return False
        async def execute(self,query):
            if query.columns[0].name.startswith("FrontendEvent"): return Result()
            return Result([row for ident,row in sorted(rows.items()) if ident>query.filters[0][2]])
    async def insert(_ch,table,payload,_columns):
        inserted.extend(row[0] for row in payload)
        # Simulate id=1 allocated by an older transaction becoming visible only now.
        rows[1]=NS(**{**vars(rows[2]),"id":1})
    async def set_cursor(table,value): cursor[table]=value
    ns={**sql_namespace(),"analytics_session":DB,"BehaviorEvent":behavior,"FrontendEvent":frontend,"_BATCH":20000,
        "_EVENT_COLUMNS":[],"_FRONTEND_COLUMNS":[],"_cursor_get":lambda t:async_value(cursor[t]),"_cursor_set":set_cursor,
        "_ch_insert":insert,"_dt":lambda dt:dt,"json":json}
    fn=extracted("backend/app/services/clickhouse_sync.py","_sync_events",ns)
    first=await fn(None);second=await fn(None)
    assert first==1 and second==0 and inserted==[2] and cursor["behavior_events"]==2 and 1 in rows
    return {"premise":"id1 allocated earlier but invisible at first SELECT; committed id2 visible and copied, cursor advances to2, id1 commits afterwards",
            "first_count":first,"second_count":second,"copied_ids":inserted,"pg_committed_ids_double":sorted(rows),"cursor":cursor,
            "establishes":"actual id>cursor logic skips late id1 under this permitted ordering; no live PostgreSQL sequence/transaction or CH merge test"}


async def regional_count_and_cache():
    """Execute actual seed skip and actual namespace bump against fixed API key."""
    import tempfile
    counts=[]; existing_value=999.0
    annual=model("annual",[]);monthly=model("monthly",[])
    class DB:
        async def __aenter__(self): return self
        async def __aexit__(self,*_): return False
        async def commit(self): counts.append("metadata_commit")
        async def execute(self,q): counts.append("count_"+("annual" if q.source_table is annual else "monthly"));return Result([1])
    with tempfile.TemporaryDirectory() as temp:
        (Path(temp)/"data.csv.gz").touch()
        ns={**sql_namespace(),"DATA_DIR":Path(temp),"async_session":DB,"load_meta":lambda:([],[]),
            "count_points":lambda:1,"count_monthly_points":lambda:1,"RegionDataPoint":annual,"RegionMonthlyPoint":monthly,
            "func":NS(count=lambda:Field("count")),"print":lambda *_:None}
        seed=extracted("backend/seed_regional.py","seed_regional",ns)
        await seed()
    assert counts==["metadata_commit","count_annual","count_monthly"] and existing_value==999.0
    # Evaluate the exact cache-key assignment, not an authored equivalent.
    path="backend/app/api/regions.py";source=(ROOT/path).read_text();tree=ast.parse(source)
    handler=next(n for n in tree.body if isinstance(n,ast.AsyncFunctionDef) and n.name=="region_indicator_monthly")
    assignment=next(n for n in handler.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=="cache_key" for t in n.targets))
    key_ns={"slug":"fixture","code":"fuel","get_locale":lambda:"ru"}
    exec(compile(ast.Module(body=[assignment],type_ignores=[]),path,"exec"),key_ns)
    cache={key_ns["cache_key"]:existing_value}; versions={}
    class Pipe:
        async def __aenter__(self): return self
        async def __aexit__(self,*_): return False
        def incr(self,k): versions[k]=versions.get(k,0)+1
        async def execute(self): pass
    class Redis:
        def pipeline(self,**_): return Pipe()
    ns={"get_redis":lambda:async_value(Redis()),"_ver_local":{},"_note_cache_failure":lambda *_:None}
    bump=extracted("backend/app/core/cache.py","bump_namespaces",ns)
    await bump("regions")
    assert versions=={"fe:ver:regions":1} and cache[key_ns["cache_key"]]==999.0
    SOURCE_ANCHORS.append({"path":path,"function":"region_indicator_monthly cache_key assignment","line":assignment.lineno,
       "end_line":assignment.end_lineno,"sha256":hashlib.sha256(source.encode()).hexdigest()})
    return {"premise":"artifact and DB annual/monthly row counts equal while one stored value differs; API has a populated fixed monthly key",
       "seed_trace":counts,"equal_count_skips_value_comparison":True,"api_key":key_ns["cache_key"],"namespace_after":versions,
       "cached_fixed_key_after":cache[key_ns["cache_key"]],
       "establishes":"actual seed returns after counts; actual namespace bump increments version without touching fixed API key; EMISS commit per month and terminal regions bump are source-established separately"}


async def scheduler_lock_expiry():
    now=[0]; keys={}; active=[0];peak=[0]; started=asyncio.Event();release=asyncio.Event();calls=[0]
    class Redis:
        async def set(self,key,token,nx,ex):
            if key in keys and keys[key][1] > now[0]: return False
            keys[key]=(token,now[0]+ex);return True
        async def eval(self,_lua,_n,key,token):
            if keys.get(key,(None,))[0]==token: del keys[key];return 1
            return 0
    async def job():
        calls[0]+=1; ident=calls[0];active[0]+=1;peak[0]=max(peak[0],active[0])
        if ident==1: started.set();await release.wait()
        active[0]-=1;return ident
    module=ModuleType("app.core.cache");module.get_state_redis=lambda:async_value(Redis())
    old=sys.modules.get(module.__name__);sys.modules[module.__name__]=module
    fn=extracted("backend/app/main.py","locked_job",{"logger":logging.getLogger("isolated-probe")})
    try:
        wrapped=fn(job,"fixture",10);first=asyncio.create_task(wrapped());await started.wait()
        held=await wrapped();assert held is None and calls[0]==1
        now[0]=11;second=await wrapped();release.set();await first
    finally:
        if old is None: del sys.modules[module.__name__]
        else: sys.modules[module.__name__]=old
    assert second==2 and peak[0]==2
    return {"premise":"two scheduler invocations same job id; first function still running when Redis SET NX EX lease expires",
        "before_expiry_skips":held is None,"after_expiry_executes":second,"peak_concurrent_calls":peak[0],
        "establishes":"actual locked_job has no lease renewal and permits overlap after TTL; Redis clock/atomic SET/token-Lua release are doubles"}


def inventory_regressions():
    spec=importlib.util.spec_from_file_location("mechanism_inventory",ROOT/"scripts/build-mechanism-inventory.py")
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    source="""from fastapi import APIRouter
from app.child import router as child
router=APIRouter(prefix='/x')
router.include_router(child, prefix='/y')
@router.get('/{id}', dependencies=[Depends(auth)])
async def handler(id: str): pass
router.add_api_route('/compat', handler, methods=['POST'])
"""
    scan=mod.scan_module("backend/app/sample.py",source)
    root={"symbol":"app.main.app","prefix":""}
    routes,unknown=mod.compose_routes([root]+scan["routers"],
        [{"parent":"app.main.app","child":"app.sample.router","prefix":"","conditions":[]}] + scan["router_edges"],scan["route_declarations"])
    assert {row["full_path"] for row in routes}=={"/x/{id}","/x/compat"}
    assert unknown[0]["symbol"]=="app.child.router"
    assert scan["route_declarations"][1]["methods"] == ["POST"]
    cyclic,_=mod.compose_routes([root],[],[])
    assert cyclic==[]
    return {"compose_prefix":True,"explicit_registration":True,"unknown_router_retained":True,
            "establishes":"isolated AST composition handles includes, explicit routes and unresolved child; no application import"}


async def run():
    SOURCE_ANCHORS.clear()
    results={"inventory_fixture":inventory_regressions()}
    for fn in (partial_replace,invalidate_before_commit,eurostat_remap_partial_failure,session_window_boundary,clickhouse_late_id,regional_count_and_cache,scheduler_lock_expiry):
        results[fn.__name__]=await fn()
    return {"date":"2026-09-30","basis":"local main 05302ff source bodies, in-memory doubles; no network/runtime state",
            "source_anchors":SOURCE_ANCHORS,"results":results,
            "not_established":["production incidence or frequency","real PG/Redis/CH multi-process correctness","capacity/p99/RTO","external provider completeness"]}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--write",action="store_true");args=parser.parse_args()
    result=asyncio.run(run())
    if args.write: (ROOT/RESULT).write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"asserted_cases":list(result["results"]),"external_calls":0},ensure_ascii=False))


if __name__=="__main__": main()
