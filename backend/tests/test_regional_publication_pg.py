"""Opt-in regional writer/reader acceptance with actual PostgreSQL and Redis.

Only random test schemas and reserved Redis DB14 at an explicit nondefault
loopback port are used. No application DSN fallback or FLUSHDB is permitted.
"""

import asyncio
from contextlib import asynccontextmanager
import os

import pytest
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError

from app.core import cache
from app.models import RegionIndicator
from app.services import emiss_regional_parser as parser
from test_parser_publication_pg import _validated_endpoints
from test_regional_publication import CODE, SLUG, monthly_value, populate_regional, sql_value
from test_regional_seed_pg import _regional_database


@asynccontextmanager
async def regional_pg_env(monkeypatch):
    pg_raw = os.environ.get("F01_TEST_DATABASE_URL")
    redis_raw = os.environ.get("PUBLICATION_TEST_REDIS_URL")
    if not pg_raw or not redis_raw:
        pytest.skip("Set explicit isolated F01_TEST_DATABASE_URL and PUBLICATION_TEST_REDIS_URL")
    pg_url, redis_url, _ = _validated_endpoints(pg_raw, redis_raw)
    redis = Redis.from_url(redis_url, decode_responses=True, socket_connect_timeout=2, socket_timeout=2)
    try:
        assert await redis.ping()
        monkeypatch.setattr(cache, "_redis", redis)
        monkeypatch.setattr(cache, "_ver_local", {})
        monkeypatch.setattr(parser, "_PAUSE_BETWEEN_REQUESTS", 0)
        async with _regional_database(pg_url) as sessions:
            await populate_regional(sessions)
            # Advance instead of deleting: older unrelated test cache is unreachable.
            await cache.bump_namespaces("regions", "ssr-region", "og-region")
            yield sessions, redis
    finally:
        await redis.aclose()


def test_later_postgres_month_failure_preserves_published_previous_commit(monkeypatch):
    async def scenario():
        async with regional_pg_env(monkeypatch) as (sessions, redis):
            start = {ns: int(await redis.get(f"fe:ver:{ns}")) for ns in ("regions", "ssr-region", "og-region")}
            assert await monthly_value(sessions) == 1
            monkeypatch.setattr(parser, "months_to_fetch", lambda existing: [(2026, 1), (2026, 2)])

            async def fetch(year, month, *args, **kwargs):
                if month == 1:
                    return [(CODE, SLUG, 202601, 2)]
                # First code is staged, then duplicate keys in another code cause
                # real PG ON CONFLICT cardinality violation; entire month rolls back.
                return [(CODE, SLUG, 202601, 9), ("ceni-ai95", SLUG, 202602, 3), ("ceni-ai95", SLUG, 202602, 4)]

            monkeypatch.setattr(parser, "fetch_month_points", fetch)
            async with sessions() as writer:
                with pytest.raises(DBAPIError):
                    await parser.run_emiss_regional_update(writer, territory_ids=[], dimnames={})
                # Parser explicitly rolls back the failed month; session stays usable.
                assert (await writer.scalar(select(RegionIndicator.id).limit(1))) is not None
            assert await sql_value(sessions) == await monthly_value(sessions) == 2
            for ns, initial in start.items():
                assert int(await redis.get(f"fe:ver:{ns}")) == initial + 1
    asyncio.run(scenario())


def test_native_postgres_upsert_counts_and_extent_then_publishes_each_month(monkeypatch):
    async def scenario():
        async with regional_pg_env(monkeypatch) as (sessions, redis):
            initial = int(await redis.get("fe:ver:regions"))
            assert await monthly_value(sessions) == 1
            monkeypatch.setattr(parser, "months_to_fetch", lambda existing: [(2026, 1), (2027, 1)])

            async def fetch(year, month, *args, **kwargs):
                return [(CODE, SLUG, year * 100 + month, 2 if year == 2026 else 3)]

            monkeypatch.setattr(parser, "fetch_month_points", fetch)
            async with sessions() as writer:
                stats = await parser.run_emiss_regional_update(writer, territory_ids=[], dimnames={})
            assert stats == {"months": 2, "added": 1, "updated": 1}  # Genuine xmax distinction.
            async with sessions() as reader:
                bounds = (await reader.execute(select(RegionIndicator.year_min, RegionIndicator.year_max).where(RegionIndicator.code == CODE))).one()
            assert tuple(bounds) == (2026, 2027)
            assert int(await redis.get("fe:ver:regions")) == initial + 2
            assert await monthly_value(sessions) == 2
    asyncio.run(scenario())
