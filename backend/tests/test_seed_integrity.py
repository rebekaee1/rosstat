"""Т-12: целостность посева.

1. Каждый parser_type из INDICATORS зарегистрирован в PARSER_REGISTRY —
   иначе ETL молча не найдёт парсер (KeyError в рантайме планировщика).
2. Коды индикаторов уникальны (dupe в 4600-строчном файле глазами не видно).
3. `seed()` идемпотентен на уровне решения: при совпадении хэша полный прогон
   НЕ запускается (П-12), при FORCE_SEED=1 — запускается всегда.
"""

import asyncio

import pytest

import seed_data
from app.services.rosstat_cpi_parser import PARSER_REGISTRY


def test_every_parser_type_registered():
    missing = {
        ind["parser_type"]
        for ind in seed_data.INDICATORS
        if ind.get("parser_type") and ind["parser_type"] not in PARSER_REGISTRY
    }
    # "derived" — вычисляется движком, не парсером; ETL его не диспатчит.
    missing -= {"derived"}
    assert not missing, f"parser_type без парсера в PARSER_REGISTRY: {sorted(missing)}"


def test_indicator_codes_unique():
    codes = [ind["code"] for ind in seed_data.INDICATORS]
    dupes = {c for c in codes if codes.count(c) > 1}
    assert not dupes, f"дубли кодов в INDICATORS: {sorted(dupes)}"


@pytest.fixture
def seed_env(auth_env, monkeypatch):
    """seed_data.* на герметичной SQLite-сессии; _seed_full подменён счётчиком."""
    calls = {"full": 0}

    async def fake_full():
        calls["full"] += 1

    monkeypatch.setattr(seed_data, "async_session", auth_env["session_maker"])
    monkeypatch.setattr(seed_data, "_seed_full", fake_full)
    return calls


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def test_seed_skips_when_hash_matches(seed_env, monkeypatch):
    monkeypatch.delenv("FORCE_SEED", raising=False)
    _run(seed_data.seed())          # первый прогон: хэша нет → полный
    _run(seed_data.seed())          # второй: хэш совпал → скип
    assert seed_env["full"] == 1


def test_force_seed_overrides_hash(seed_env, monkeypatch):
    monkeypatch.delenv("FORCE_SEED", raising=False)
    _run(seed_data.seed())
    monkeypatch.setenv("FORCE_SEED", "1")
    _run(seed_data.seed())
    assert seed_env["full"] == 2
