"""Трассировка холодного рендера: число и время SQL-запросов и Python (круг 12, SPEED2).

Запуск внутри контейнера backend (стенд, данные боевого размера), первый проход прогревает импорты,
замер — второй проход (как у долгоживущего процесса сервера):
    docker exec -i rosstat-backend-1 python - world-country germany en [--profile] < scripts/dev/perf_cold_trace.py
    docker exec -i rosstat-backend-1 python - home - en < scripts/dev/perf_cold_trace.py
    docker exec -i rosstat-backend-1 python - indicators - en < scripts/dev/perf_cold_trace.py
    docker exec -i rosstat-backend-1 python - country-api germany en < scripts/dev/perf_cold_trace.py
Ничего не пишет в базу (read-only транзакция); кэш Redis не используется (функции рендера вызываются напрямую,
кроме внутренних кэшей процесса).
"""
from __future__ import annotations

import asyncio
import sys
import time
from collections import defaultdict

from sqlalchemy import event, text

from app.database import async_session, engine

KIND = sys.argv[1]
ARG = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] != "-" else None
LOCALE = sys.argv[3] if len(sys.argv) > 3 else "en"
PROFILE = "--profile" in sys.argv

stats: list[tuple[float, str]] = []


def _install() -> None:
    sync_engine = engine.sync_engine

    @event.listens_for(sync_engine, "before_cursor_execute")
    def _before(conn, cursor, statement, parameters, context, executemany):  # noqa: ARG001
        conn.info.setdefault("t0", []).append(time.perf_counter())

    @event.listens_for(sync_engine, "after_cursor_execute")
    def _after(conn, cursor, statement, parameters, context, executemany):  # noqa: ARG001
        dt = time.perf_counter() - conn.info["t0"].pop()
        flat = " ".join(statement.split())
        # начало (SELECT …) и хвост (FROM/WHERE …) — запросы одной таблицы отличаются условиями
        stats.append((dt, flat if "--full" in sys.argv else flat[:60] + " … " + flat[-110:] if "--detail" in sys.argv else flat[:170]))


async def once() -> str:
    from app.services import locale as loc

    loc.set_locale(LOCALE)
    async with async_session() as db:
        await db.execute(text("SET TRANSACTION READ ONLY"))
        if KIND == "http":
            # Полный путь запроса через приложение (middleware, кэш, рендер); перед проходом сбрасывается кэш DB 0 стенда.
            import httpx

            from app.core.cache import get_redis
            from app.main import app

            await (await get_redis()).flushdb()
            headers = {"Host": "forecasteconomy.com", "X-Original-URI": ARG, "Accept-Encoding": "identity"}
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://backend") as client:
                t_cold = time.perf_counter()
                response = await client.get(ARG, headers=headers)
                cold_ms = (time.perf_counter() - t_cold) * 1000
                t_warm = time.perf_counter()
                again = await client.get(ARG, headers=headers)
                warm_ms = (time.perf_counter() - t_warm) * 1000
            out = f"{response.status_code} {len(response.content)} bytes; COLD {cold_ms:.0f} ms, WARM {warm_ms:.0f} ms ({again.status_code})"
        elif KIND == "hash-country":
            # Сверка до/после: md5 HTML и md5 JSON каталога по списку стран (ARG = slug,slug,… или ALL)
            import hashlib
            import json

            from sqlalchemy import select as _select

            from app.api import world as wapi
            from app.models import WorldCountry
            from app.services.seo_world import render_world_country_html

            async def _no_get(key):  # noqa: ARG001
                return None

            async def _no_set(key, value, ttl=None):  # noqa: ARG001
                return None

            wapi.cache_get, wapi.cache_set = _no_get, _no_set
            if ARG == "ALL":
                slugs = [r for r in (await db.execute(_select(WorldCountry.slug).where(WorldCountry.is_active.is_(True)).order_by(WorldCountry.slug))).scalars()]
            else:
                slugs = ARG.split(",")
            import gc

            for slug in slugs:
                # новая сессия на страну: 54 страны по 10 тыс. ORM-объектов в одной сессии съедают память контейнера
                async with async_session() as db2:
                    st, html = await render_world_country_html(slug, db2)
                    if "--norm" in sys.argv:
                        # без различий в разметке картинки и приоритетов загрузки (круг 12, SPEED2): остальное побайтно
                        import re as _re

                        html = _re.sub(r"<picture>.*?(<img[^>]*>)</picture>", r"\1", html, flags=_re.S)
                        html = _re.sub(r'<link rel="preload" as="image"[^>]*>\n?', "", html)
                        html = _re.sub(r' fetchpriority="(?:high|low)"', "", html)
                    hh = hashlib.md5(html.encode()).hexdigest()[:12]
                    hl = len(html)
                async with async_session() as db3:
                    try:
                        payload = await wapi.country_detail(slug, db=db3)
                        dump = json.dumps(payload, sort_keys=True, default=str)
                        ah = hashlib.md5(dump.encode()).hexdigest()[:12]
                        asz = len(dump)
                        del payload, dump
                    except Exception as exc:  # noqa: BLE001
                        ah, asz = f"ERR:{type(exc).__name__}", 0
                print(f"HASH {slug} html={st}:{hh}:{hl} api={ah}:{asz}", flush=True)
                gc.collect()
            out = f"{len(slugs)} countries"
        elif KIND == "world-country":
            from app.services.seo_world import render_world_country_html

            status, html = await render_world_country_html(ARG, db)
            out = f"{status} {len(html)}"
        elif KIND == "home":
            from app.services.seo_renderer import render_home_html

            out = f"200 {len(await render_home_html(db))}"
        elif KIND == "indicators":
            from app.api import indicators as mod

            async def _no_get(key):  # noqa: ARG001
                return None

            async def _no_set(key, value, ttl=None):  # noqa: ARG001
                return None

            mod.cache_get, mod.cache_set = _no_get, _no_set
            res = await mod.list_indicators(db=db, category=None, include_inactive=False, include_unlisted=False)
            import json

            import hashlib

            dump = json.dumps([r.model_dump(mode="json") for r in res], sort_keys=True, default=str)
            out = f"{len(dump)} bytes json, {len(res)} items, md5 {hashlib.md5(dump.encode()).hexdigest()[:12]}"
        elif KIND == "country-api":
            from app.api import world as mod
            from app.core import cache as cache_mod

            async def _no_get(key):  # noqa: ARG001
                return None

            async def _no_set(key, value, ttl=None):  # noqa: ARG001
                return None

            mod.cache_get, mod.cache_set = _no_get, _no_set
            res = await mod.country_detail(ARG, db=db)
            import json

            out = f"{len(json.dumps(res, default=str))} bytes json"
            del cache_mod
        else:
            raise SystemExit("kind?")
        await db.rollback()
    return out


async def main() -> None:
    _install()
    await once()  # прогрев импортов и внутрипроцессных кэшей
    stats.clear()
    t0 = time.perf_counter()
    if PROFILE:
        import cProfile
        import pstats

        pr = cProfile.Profile()
        pr.enable()
    out = await once()
    if PROFILE:
        pr.disable()
    total = time.perf_counter() - t0
    sql = sum(s for s, _ in stats)
    print(f"{KIND} {ARG}: total {total:.2f}s, sql {sql:.2f}s in {len(stats)} queries, python {total - sql:.2f}s, {out}")
    agg: dict[str, list[float]] = defaultdict(list)
    for dt, st in stats:
        agg[st].append(dt)
    for st, v in sorted(agg.items(), key=lambda kv: -sum(kv[1]))[:10]:
        print(f"  {sum(v):6.3f}s x{len(v):<3} {st}")
    if PROFILE:
        pstats.Stats(pr).sort_stats("tottime").print_stats(25)


asyncio.run(main())
