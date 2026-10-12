"""Обёртка приложения для замера памяти воркера (круг 12, SPEED3). Только для стенда, не для боя.

Запуск в контейнере backend стенда (1 воркер, Redis DB 7, БД стенда только на чтение, планировщик выключен):
    python -m uvicorn perf_mem_wrap:app --host 0.0.0.0 --port 8000 --workers 1      # PYTHONPATH=/app, файл рядом
Добавляет маршруты /__mem (RSS/RssAnon, число gc-объектов, ?trim=1 — malloc_trim, ?top=N с переменной TM=1 — разница
tracemalloc), /__flush (очистка Redis DB 7; отказывается работать на другом номере) и, при SWR_TEST=1, /__swr со счётчиками
пересчётов (см. perf_swr_check.py). Поток боевых адресов подаёт perf_mem_replay.py.
"""
import ctypes, gc, os, sys, tracemalloc, json
if os.environ.get("TM"):
    tracemalloc.start(int(os.environ["TM"]))
from app.main import app
from fastapi import Response

_base = {"snap": None}
_libc = ctypes.CDLL("libc.so.6")

def _status():
    out = {}
    for line in open("/proc/self/status"):
        k, _, v = line.partition(":")
        if k in ("VmRSS", "RssAnon", "RssFile", "VmHWM"):
            out[k] = int(v.split()[0]) // 1024
    return out

@app.get("/__mem")
async def mem(top: int = 0, trim: int = 0, collect: int = 0, base: int = 0):
    res = {"pid": os.getpid(), "mb": _status(), "heavy": [m for m in ("pandas","scipy","statsmodels","numpy","PIL") if m in sys.modules]}
    if collect:
        res["gc_collected"] = gc.collect()
    res["gc_objects"] = len(gc.get_objects())
    if trim:
        _libc.malloc_trim(0)
        res["mb_after_trim"] = _status()
    if tracemalloc.is_tracing():
        cur, peak = tracemalloc.get_traced_memory()
        res["traced_mb"] = round(cur / 1048576, 1)
        if base or _base["snap"] is None:
            _base["snap"] = tracemalloc.take_snapshot()
            res["baseline_set"] = True
        if top:
            snap = tracemalloc.take_snapshot()
            stats = snap.compare_to(_base["snap"], "lineno")[:top]
            res["top_diff"] = [f"{s.size_diff/1048576:+.2f}MB {s.count_diff:+d} {s.traceback[0].filename.replace('/usr/local/lib/python3.12/site-packages/','')}:{s.traceback[0].lineno}" for s in stats]
            stats2 = snap.statistics("filename")[:top]
            res["top_files"] = [f"{s.size/1048576:.2f}MB {s.count} {s.traceback[0].filename.replace('/usr/local/lib/python3.12/site-packages/','')}" for s in stats2]
    return Response(json.dumps(res, ensure_ascii=False, indent=1), media_type="application/json")

@app.get("/__flush")
async def flush():
    from app.core.cache import get_redis, get_state_redis
    out = {}
    for name, getter in (("redis", get_redis), ("state", get_state_redis)):
        r = await getter()
        db = r.connection_pool.connection_kwargs.get("db")
        if db == 7:
            await r.flushdb()
            out[name] = "flushed db7"
        else:
            out[name] = f"REFUSED db={db}"
    return out

# ---- SWR-проверка (SWR_TEST=1): короткий TTL, счётчики пересчётов, подмена адреса пересчёта ----
if os.environ.get("SWR_TEST"):
    import time
    from starlette.requests import Request
    from app.api import seo_pages
    from app.services import ssr_swr
    from app.config import settings

    TTL = int(os.environ.get("SWR_TEST_TTL", "4"))
    _orig_set = seo_pages.cache_set

    async def _short_set(key, value, ttl=None, **kw):
        return await _orig_set(key, value, min(ttl or TTL, TTL), **kw)

    seo_pages.cache_set = _short_set
    ssr_swr._LOCK_SECONDS = int(os.environ.get("SWR_TEST_LOCK", "6"))
    counters = {"reval_requests": 0, "reval_ok": 0, "replay_calls": 0, "renders": 0}
    _orig_replay = ssr_swr._replay

    async def _counted_replay(*a, **k):
        counters["replay_calls"] += 1
        return await _orig_replay(*a, **k)

    ssr_swr._replay = _counted_replay

    @app.middleware("http")
    async def _count_reval(request: Request, call_next):
        is_reval = bool(request.headers.get(ssr_swr.REVALIDATE_HEADER))
        if is_reval:
            counters["reval_requests"] += 1
        resp = await call_next(request)
        if is_reval and resp.status_code == 200:
            counters["reval_ok"] += 1
        return resp

    from app.services import seo_renderer
    _orig_home = seo_renderer.render_home_html

    async def _counted_home(*a, **k):
        counters["renders"] += 1
        return await _orig_home(*a, **k)

    seo_renderer.render_home_html = _counted_home
    seo_pages.render_home_html = _counted_home

    @app.get("/__swr")
    async def swr_state(base: str = "", reset: int = 0):
        if base:
            settings.ssr_swr_base_url = base
        if reset:
            for k in counters:
                counters[k] = 0
        from app.core.cache import get_redis
        r = await get_redis()
        locks = [k.decode() if isinstance(k, bytes) else k async for k in r.scan_iter("fe:swr:lock:*")]
        return {"counters": dict(counters), "base": settings.ssr_swr_base_url, "locks": len(locks), "lock_ttl": settings.ssr_swr_stale_seconds}
