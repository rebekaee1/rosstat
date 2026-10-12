"""Воспроизводит поток GET-адресов (из журнала backend боевого) против perf_mem_wrap и печатает RSS (круг 12, SPEED3).

    python perf_mem_replay.py <сколько> <с какого> <параллельно> <печатать каждые N>      # PATHS_FILE=файл с адресами
Адреса:  на боевом (только чтение журнала).
"""
import asyncio, httpx, json, random, sys, time
PATHS = [l.strip() for l in open(__import__("os").environ.get("PATHS_FILE","/work/paths_uniq.txt")) if l.strip()]
N = int(sys.argv[1]); START = int(sys.argv[2]) if len(sys.argv) > 2 else 0
CONC = int(sys.argv[3]) if len(sys.argv) > 3 else 4
EVERY = int(sys.argv[4]) if len(sys.argv) > 4 else 250
sel = PATHS[START:START+N]
HOSTS = ["forecasteconomy.com", "ru.forecasteconomy.com"]
async def main():
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8000", timeout=60) as c:
        q = asyncio.Queue()
        for i, p in enumerate(sel): q.put_nowait((i, p))
        done = 0; codes = {}
        t0 = time.time()
        async def worker():
            nonlocal done
            while True:
                try: i, p = q.get_nowait()
                except asyncio.QueueEmpty: return
                host = HOSTS[i % 2]
                try:
                    r = await c.get(p, headers={"Host": host, "X-Forwarded-Host": host, "User-Agent": "memtest"})
                    codes[r.status_code] = codes.get(r.status_code, 0) + 1
                except Exception as e:
                    codes["err"] = codes.get("err", 0) + 1
                done += 1
                if done % EVERY == 0:
                    m = (await c.get("/__mem")).json()
                    print(f"{done:5d} t={time.time()-t0:6.0f}s rss={m['mb']['VmRSS']}MB anon={m['mb']['RssAnon']}MB objs={m['gc_objects']} traced={m.get('traced_mb')} codes={codes}", flush=True)
        await asyncio.gather(*[worker() for _ in range(CONC)])
        m = (await c.get("/__mem?collect=1")).json()
        print("final", json.dumps(m["mb"]), "objs", m["gc_objects"], "heavy", m.get("heavy"), flush=True)
asyncio.run(main())
