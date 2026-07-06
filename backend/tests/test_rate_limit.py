"""Регрессии Б-2/Б-6: rate-limiter — извлечение клиентского IP и атомарность.

Б-2: раньше брался ПЕРВЫЙ элемент X-Forwarded-For — клиент подделывал его
и ротацией фейковых значений обходил лимит. Теперь идём справа налево,
пропуская доверенные прокси-хопы (Caddy/nginx в приватных сетях).

Б-6: раньше INCR и EXPIRE шли двумя командами — сбой между ними оставлял
ключ без TTL (вечный 429 для IP). Теперь один атомарный Lua-скрипт.
"""
import asyncio

import fakeredis.aioredis

from app.main import _RATE_LIMIT_LUA, pick_client_ip


# --- Б-2: выбор клиентского IP из XFF ---------------------------------------

def test_spoofed_left_entries_are_ignored():
    """Подделанные клиентом левые элементы не влияют на ключ лимита."""
    # Старый Caddy (append) + nginx (append): spoof, реальный клиент, docker-хоп
    assert pick_client_ip("1.2.3.4, 93.184.216.34, 172.18.0.1", "peer") == "93.184.216.34"
    # Ротация фейков не меняет результат
    assert pick_client_ip("5.6.7.8, 93.184.216.34, 172.18.0.1", "peer") == "93.184.216.34"


def test_current_prod_chain_caddy_rewrites():
    """Актуальный Caddy (перезаписывает XFF) + nginx append."""
    assert pick_client_ip("93.184.216.34, 172.18.0.1", "peer") == "93.184.216.34"


def test_no_header_falls_back_to_peer():
    assert pick_client_ip("", "10.0.0.5") == "10.0.0.5"
    assert pick_client_ip("", "testclient") == "testclient"


def test_all_private_chain_dev_mode():
    """Вся цепочка приватная (dev за локальным прокси) — ближайший к клиенту."""
    assert pick_client_ip("192.168.1.50, 127.0.0.1", "peer") == "192.168.1.50"


def test_garbage_header_falls_back():
    assert pick_client_ip("not-an-ip, ещё мусор", "peer") == "peer"


def test_ipv6_client_behind_proxies():
    assert pick_client_ip("2a02:6b8::1, 172.18.0.1", "peer") == "2a02:6b8::1"


# --- Б-6: атомарный INCR+EXPIRE ----------------------------------------------

def test_lua_increments_and_sets_ttl_atomically():
    async def run():
        r = fakeredis.aioredis.FakeRedis(decode_responses=True)
        c1 = await r.eval(_RATE_LIMIT_LUA, 1, "rl:x", 60)
        c2 = await r.eval(_RATE_LIMIT_LUA, 1, "rl:x", 60)
        ttl = await r.ttl("rl:x")
        return c1, c2, ttl

    c1, c2, ttl = asyncio.run(run())
    assert (c1, c2) == (1, 2)
    assert 0 < ttl <= 60


def test_lua_heals_legacy_key_without_ttl():
    """Ключ, оставленный старым неатомарным кодом без TTL, получает окно."""
    async def run():
        r = fakeredis.aioredis.FakeRedis(decode_responses=True)
        await r.set("rl:legacy", 7)  # без TTL — как после сбоя старого кода
        count = await r.eval(_RATE_LIMIT_LUA, 1, "rl:legacy", 60)
        ttl = await r.ttl("rl:legacy")
        return count, ttl

    count, ttl = asyncio.run(run())
    assert count == 8
    assert 0 < ttl <= 60
