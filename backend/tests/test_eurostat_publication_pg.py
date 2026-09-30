"""Real PostgreSQL slice commits and rollbacks, using the isolated F01 fixture.

F01_TEST_DATABASE_URL is opt-in loopback-only. Each scenario gets a new random
schema. Network extraction and application databases are never used.
"""
import asyncio
import os
from datetime import date

import pytest
from sqlalchemy import select

from app.models import WorldCountry, WorldDataPoint, WorldIndicator
from app.services.eurostat_parser import DatasetParseResult
from app.services.eurostat_structure import StructureVerdict
from test_eurostat_publication import _loader
from test_world_national_reconcile_pg import _world_database, isolated_pg_url  # noqa: F401


def test_real_redis_and_api_observe_committed_revision_after_later_failure(isolated_pg_url, monkeypatch):
    raw = os.environ.get("PUBLICATION_TEST_REDIS_URL")
    if not raw:
        pytest.skip("Set PUBLICATION_TEST_REDIS_URL to isolated loopback Redis DB14 on an ephemeral port")
    from urllib.parse import urlparse, urlunparse
    parsed = urlparse(raw)
    if parsed.scheme != "redis" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"} or parsed.port in {None, 6379} or parsed.path != "/14" or parsed.query or parsed.fragment:
        pytest.fail("Publication Redis must use loopback, an explicit non-default port and DB14")
    from redis.asyncio import Redis
    import app.core.cache as cache
    from app.api.world import indicator_data
    loader = _loader()

    async def scenario():
        redis_cache = Redis.from_url(raw, decode_responses=True)
        redis_state = Redis.from_url(urlunparse(parsed._replace(path="/15")), decode_responses=True)
        monkeypatch.setattr(cache, "_redis", redis_cache)
        monkeypatch.setattr(cache, "_state_redis", redis_state)
        monkeypatch.setattr(cache, "_ver_local", {})
        try:
            async with _world_database(isolated_pg_url) as maker:
                monkeypatch.setattr(loader, "async_session", maker)
                ids = await loader.ensure_countries({"DE"})
                result = DatasetParseResult(dataset_id="fixture", title_en="Fixture", frequency="annual",
                                            slice_={"freq": "A", "unit": "PC"}, slice_hash="fixture",
                                            unit="PC", series_by_geo={"DE": [(date(2024, 1, 1), 10.0)]},
                                            source_url="https://example.invalid")
                await loader.persist_result(result, ids, {"DE": "Германия"})
                async with maker() as reader:
                    code = (await reader.execute(select(WorldIndicator.code))).scalar_one()

                async def api_values():
                    async with maker() as reader:
                        response = await indicator_data("germany", code, mode="level-annual",
                                                        include_forecast=False, date_from=None, date_to=None, db=reader)
                        return [point["value"] for point in response["points"]]

                assert await api_values() == [10.0]
                versions = (int(await redis_cache.get("fe:ver:world")), int(await redis_state.get("fe:ver:world-catalog")))
                result.series_by_geo["DE"] = [(date(2024, 1, 1), 20.0)]
                await loader.persist_result(result, ids, {"DE": "Германия"})
                result.series_by_geo["DE"] = [(date(2024, 1, 1), 30.0), (date(2024, 1, 1), 31.0)]
                from sqlalchemy.exc import DBAPIError
                with pytest.raises(DBAPIError):
                    await loader.persist_result(result, ids, {"DE": "Германия"})
                assert await api_values() == [20.0]
                assert (int(await redis_cache.get("fe:ver:world")), int(await redis_state.get("fe:ver:world-catalog"))) == (versions[0] + 1, versions[1] + 1)
        finally:
            await redis_cache.aclose()
            await redis_state.aclose()

    asyncio.run(scenario())


def test_slice_commit_then_later_rollback_keeps_published_facts(isolated_pg_url, monkeypatch):
    loader = _loader()

    async def scenario():
        async with _world_database(isolated_pg_url) as maker:
            monkeypatch.setattr(loader, "async_session", maker)
            country_ids = await loader.ensure_countries({"DE"})
            published = []

            async def publish(*namespaces):
                async with maker() as reader:
                    values = (await reader.execute(select(WorldDataPoint.value))).scalars().all()
                    published.append((namespaces, values))

            monkeypatch.setattr(loader, "bump_namespaces", publish)
            # Keep official metadata/upsert/reconcile and named PG constraints.
            def result(hash_, points):
                return DatasetParseResult(dataset_id="fixture", title_en="Fixture", frequency="annual",
                                          slice_={"freq": "A", "unit": "PC", "fixture": hash_},
                                          slice_hash=hash_, unit="PC", series_by_geo={"DE": points},
                                          source_url="https://example.invalid")

            first = result("first", [(date(2024, 1, 1), 10.0)])
            assert await loader.persist_result(first, country_ids, {"DE": "Германия"}) == (1, 1)
            # Duplicate dates trigger a real PostgreSQL cardinality violation;
            # metadata and both conflicting writes must roll back together.
            broken = result("broken", [(date(2024, 1, 1), 20.0), (date(2024, 1, 1), 21.0)])
            from sqlalchemy.exc import DBAPIError
            with pytest.raises(DBAPIError):
                await loader.persist_result(broken, country_ids, {"DE": "Германия"})
            async with maker() as reader:
                assert (await reader.execute(select(WorldDataPoint.value))).scalars().all() == [10.0]
                assert (await reader.execute(select(WorldIndicator.slice_hash))).scalars().all() == ["first"]
            assert published == [(("world", "world-catalog", "ssr-world"), [10.0])]

            # Unchanged point writes remain idempotent, but metadata is still a
            # published unit. A failed previous slice doesn't suppress retry.
            assert await loader.persist_result(first, country_ids, {"DE": "Германия"}) == (1, 0)
            assert len(published) == 2

    # Seed countries without a real Redis; publication assertions start after.
    async def noop(*namespaces):
        pass
    monkeypatch.setattr(loader, "bump_namespaces", noop)
    asyncio.run(scenario())


def test_remap_publication_failure_keeps_commit_and_same_url(isolated_pg_url, monkeypatch):
    loader = _loader()

    async def scenario():
        async with _world_database(isolated_pg_url) as maker:
            async with maker() as db:
                country = WorldCountry(code="DE", slug="germany", name_ru="Германия", name_en="Germany")
                db.add(country)
                await db.flush()
                card = WorldIndicator(country_id=country.id, provider="eurostat", code="de-stable-url",
                                      dataset_id="fixture", slice_hash="old", name_ru="Тест", frequency="annual")
                db.add(card)
                await db.commit()
                card_id = card.id

            async def failed_publish(*namespaces):
                raise RuntimeError("controlled Redis failure after commit")

            monkeypatch.setattr(loader, "bump_namespaces", failed_publish)
            verdict = StructureVerdict(accept=True, remapped={card_id: ({"freq": "A"}, "new")})
            with pytest.raises(RuntimeError, match="controlled Redis failure after commit"):
                await loader.apply_remaps(verdict, session_factory=maker)
            async with maker() as reader:
                card = await reader.get(WorldIndicator, card_id)
                assert (card.slice_hash, card.code) == ("new", "de-stable-url")

    asyncio.run(scenario())
