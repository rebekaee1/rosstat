"""Проверка stale-while-revalidate на стенде (круг 12, SPEED3): устаревшее отдаётся сразу, пересчёт один на ключ,
отказ пересчёта (соединение / 504) не стирает запись. Запускать внутри контейнера с perf_mem_wrap и SWR_TEST=1,
RUSTATS_SSR_SWR_ENABLED=true, RUSTATS_SSR_SWR_BASE_URL=http://127.0.0.1:8000. TTL записей сжат до 4 с, замок — до 6 с."""
import asyncio, hashlib, http.server, threading, time, httpx

H = {"Host": "ru.forecasteconomy.com", "X-Forwarded-Host": "ru.forecasteconomy.com", "User-Agent": "swrtest"}
URL = "/seo/page/home"

class Fail504(http.server.BaseHTTPRequestHandler):
    hits = 0
    def do_GET(self):
        Fail504.hits += 1
        self.send_response(504); self.end_headers()
    def log_message(self, *a): pass

def start_504():
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 8099), Fail504)
    threading.Thread(target=srv.serve_forever, daemon=True).start()

async def get(c):
    t = time.perf_counter()
    r = await c.get(URL, headers=H)
    return r.headers.get("x-fe-cache"), r.status_code, hashlib.md5(r.content).hexdigest()[:8], round((time.perf_counter() - t) * 1000)

async def state(c, **kw):
    q = "&".join(f"{k}={v}" for k, v in kw.items())
    return (await c.get("/__swr?" + q)).json()

def summ(rows):
    from collections import Counter
    return dict(Counter(r[0] for r in rows)), "bodies", len({r[2] for r in rows}), "max_ms", max(r[3] for r in rows), "statuses", sorted({r[1] for r in rows})

async def main():
    start_504()
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8000", timeout=60) as c:
        await c.get("/__flush")
        print("reset", await state(c, base="http://127.0.0.1:8000", reset=1))
        print("1 cold  ", await get(c))
        print("2 warm  ", await get(c))
        print("-- ждём истечения TTL (5 с)")
        await asyncio.sleep(5.5)
        rows = await asyncio.gather(*[get(c) for _ in range(30)])
        print("3 после TTL, 30 параллельных:", summ(rows))
        await asyncio.sleep(3)
        s = await state(c)
        print("   пересчётов:", s["counters"])
        print("4 после пересчёта:", await get(c))

        print("== сценарий отказа пересчёта: адрес пересчёта недоступен (connection refused)")
        await asyncio.sleep(4.5)  # TTL истёк
        await state(c, base="http://127.0.0.1:9", reset=1)
        rows = await asyncio.gather(*[get(c) for _ in range(20)])
        print("5 после TTL при мёртвом пересчёте:", summ(rows))
        await asyncio.sleep(2)
        s = await state(c); print("   попыток пересчёта:", s["counters"]["replay_calls"], "замков:", s["locks"])
        rows = [await get(c) for _ in range(5)]
        print("6 повторные визиты (замок держит):", summ(rows))
        s = await state(c); print("   попыток пересчёта:", s["counters"]["replay_calls"])

        print("== сценарий 504 от адреса пересчёта")
        await asyncio.sleep(6.5)  # замок (6 с) истёк
        await state(c, base="http://127.0.0.1:8099", reset=1)
        rows = await asyncio.gather(*[get(c) for _ in range(20)])
        print("7 после снятия замка, пересчёт отвечает 504:", summ(rows))
        await asyncio.sleep(2)
        s = await state(c); print("   попыток пересчёта:", s["counters"]["replay_calls"], "ответов 504 получено сервером-заглушкой:", Fail504.hits)
        print("8 запись жива, ответ тот же:", await get(c))

        print("== восстановление: пересчёт снова работает")
        await asyncio.sleep(6.5)
        await state(c, base="http://127.0.0.1:8000", reset=1)
        print("9 визит после снятия замка:", await get(c))
        await asyncio.sleep(3)
        s = await state(c); print("   пересчётов:", s["counters"])
        print("10 после успешного пересчёта:", await get(c))
asyncio.run(main())
