"""Opt-in parser publication acceptance with actual PostgreSQL and Redis.

Set F01_TEST_DATABASE_URL to the isolated loopback ``fe_f01_*`` PostgreSQL and
PUBLICATION_TEST_REDIS_URL to an isolated Redis at a nondefault loopback port,
database 14 (state uses 15). No application DSN or SQLite writer is substituted.
The test creates/drops only its UUID schema and does not clear Redis databases
or delete keys.
"""

from __future__ import annotations

import asyncio
import os
from urllib.parse import urlsplit, urlunsplit

import pytest
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.schema import CreateTable

from app.core import cache
from app.models import FetchLog, Indicator, IndicatorData
from app.services import base_parser as bp
from test_parser_publication import (
    POINT_DATE,
    RevisionParser,
    api_value,
    committed_value,
    parser_inputs,
)
from test_world_national_reconcile_pg import _validated_pg_url, _world_database


def _validated_endpoints(pg_raw, redis_raw):
    pg_parts = urlsplit(pg_raw)
    pg_url = _validated_pg_url(pg_raw)
    if pg_parts.query or pg_parts.fragment or pg_url.port in {None, 5432}:
        raise ValueError("Publication PostgreSQL must use an explicit nondefault port without URL query/fragment")
    redis_parts = urlsplit(redis_raw)
    if (
        redis_parts.scheme != "redis"
        or redis_parts.hostname not in {"127.0.0.1", "localhost", "::1"}
        or redis_parts.port in {None, 6379}
        or redis_parts.path != "/14"
        or redis_parts.query
        or redis_parts.fragment
    ):
        raise ValueError("Publication Redis must be loopback on a nondefault port, DB14 without query/fragment")
    state_url = urlunsplit(redis_parts._replace(path="/15"))
    return pg_url, redis_raw, state_url


def test_parser_publication_sees_committed_revision_with_actual_postgres_and_redis(monkeypatch):
    pg_raw = os.environ.get("F01_TEST_DATABASE_URL")
    redis_raw = os.environ.get("PUBLICATION_TEST_REDIS_URL")
    if not pg_raw or not redis_raw:
        pytest.skip("Set explicit isolated F01_TEST_DATABASE_URL and PUBLICATION_TEST_REDIS_URL")
    pg_url, redis_url, state_url = _validated_endpoints(pg_raw, redis_raw)

    async def scenario():
        redis = Redis.from_url(redis_url, decode_responses=True, socket_connect_timeout=2, socket_timeout=2)
        state = Redis.from_url(state_url, decode_responses=True, socket_connect_timeout=2, socket_timeout=2)
        try:
            assert await redis.ping() and await state.ping()
            monkeypatch.setattr(cache, "_redis", redis)
            monkeypatch.setattr(cache, "_state_redis", state)
            monkeypatch.setattr(cache, "_ver_local", {})
            async with _world_database(pg_url) as sessions:
                async with sessions() as setup:
                    async with setup.begin():
                        connection = await setup.connection()
                        for model in (Indicator, IndicatorData, FetchLog):
                            await connection.execute(CreateTable(model.__table__))
                        indicator = Indicator(
                            code="publication-source", name="Fixture",
                            parser_type="publication_fixture", is_active=True,
                            model_config_json={"forecast_steps": 0},
                        )
                        setup.add(indicator)
                        await setup.flush()
                        setup.add(IndicatorData(indicator_id=indicator.id, date=POINT_DATE, value=1.0))

                # A unique starting generation isolates this API cache from any
                # earlier run without FLUSHDB or deleting another test's keys.
                await cache.bump_namespaces("publication-source")
                initial_generation = int(await redis.get("fe:ver:publication-source"))
                assert await api_value(sessions) == 1.0
                old_key = await cache.versioned_key("publication-source", "data:None:None:100")
                assert (await cache.cache_get(old_key))["data"][0]["value"] == 1.0

                observations = []
                invalidate = cache.cache_invalidate_indicator

                async def publish_and_read(code):
                    await invalidate(code)  # Genuine Redis INCR/cache publication.
                    observations.append((
                        await committed_value(sessions), await api_value(sessions),
                        int(await redis.get("fe:ver:publication-source")),
                    ))

                monkeypatch.setattr(bp, "cache_invalidate_indicator", publish_and_read)

                class VisibilityParser(RevisionParser):
                    async def _after_storage(self, db, indicator, cfg, fetch_log, *counts):
                        # The actual PostgreSQL upsert changed the writer's row;
                        # other sessions and the API still see committed value 1.
                        assert float(await db.scalar(select(IndicatorData.value))) == 2.0
                        assert await committed_value(sessions) == 1.0
                        assert await api_value(sessions) == 1.0
                        assert int(await redis.get("fe:ver:publication-source")) == initial_generation

                async with sessions() as writer:
                    indicator, fetch_log = await parser_inputs(writer)
                    await VisibilityParser().run(writer, indicator, fetch_log)
                    assert fetch_log.status == "success"
                    assert fetch_log.records_added == 0 and fetch_log.records_updated == 1

                assert observations == [(2.0, 2.0, initial_generation + 1)]
                assert await committed_value(sessions) == 2.0
                assert await api_value(sessions) == 2.0
                assert (await cache.cache_get(old_key))["data"][0]["value"] == 1.0
                assert await cache.versioned_key("publication-source", "data:None:None:100") != old_key
        finally:
            await redis.aclose()
            await state.aclose()

    asyncio.run(scenario())
