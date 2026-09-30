"""Regional commit/cache regressions using separate SQL readers and Redis.

SQLite fixtures adapt only PostgreSQL conflict syntax and xmax classification;
the real parser, transaction owner, API handlers and cache generation run.
Actual PostgreSQL acceptance lives in test_regional_publication_pg.py.
"""

import asyncio
from contextlib import asynccontextmanager, suppress
import json
from datetime import date

import fakeredis.aioredis
import pytest
from sqlalchemy import event, literal, select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from starlette.requests import Request

from app.api import regions as api
from app.core import cache
from app.models import Base, Region, RegionDataPoint, RegionIndicator, RegionMonthlyPoint
from app.services import emiss_regional_parser as parser


REGIONAL_TABLES = [m.__table__ for m in (Region, RegionIndicator, RegionDataPoint, RegionMonthlyPoint)]
CODE = "ceni-ai92"
SLUG = "belgorodskaya-oblast"


class SQLiteConflict:
    """Keep actual upsert builder, adapting PostgreSQL named constraint only."""

    def __init__(self, statement):
        self.statement = statement

    def values(self, rows):
        self.statement = self.statement.values(rows)
        return self

    @property
    def excluded(self):
        return self.statement.excluded

    def on_conflict_do_update(self, *, constraint, set_, where):
        assert constraint == "uq_region_monthly_point"
        return self.statement.on_conflict_do_update(
            index_elements=["indicator_id", "region_id", "month"], set_=set_, where=where,
        )


async def populate_regional(sessions):
    async with sessions() as db:
        territories = [
            Region(slug="russia", name="Российская Федерация", kind="country"),
            Region(slug=SLUG, name="Белгородская область", kind="region"),
            Region(slug="bryanskaya-oblast", name="Брянская область", kind="region"),
        ]
        territories.extend(Region(slug=f"fixture-{n}", name=f"Регион {n}", kind="region") for n in range(3))
        indicators = [RegionIndicator(
            code=code, name=code, table_code="1.1" if code == CODE else "16.20",
            section_num=16, section_name="Транспорт", unit="руб./л",
            year_min=2026, year_max=2026,
        ) for code in parser.PRICE_FUELS.values()]
        db.add_all(territories + indicators)
        await db.flush()
        for territory in territories:
            for indicator in indicators:
                db.add(RegionMonthlyPoint(indicator_id=indicator.id, region_id=territory.id, month=202601, value=1))
                db.add(RegionDataPoint(indicator_id=indicator.id, region_id=territory.id, year=2026, value=1))
        await db.commit()


@asynccontextmanager
async def regional_env(tmp_path, monkeypatch):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'regional.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(lambda c: Base.metadata.create_all(c, tables=REGIONAL_TABLES))
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    server = fakeredis.FakeServer()
    redis = fakeredis.aioredis.FakeRedis(server=server, decode_responses=True)
    binary = fakeredis.aioredis.FakeRedis(server=server, decode_responses=False)
    monkeypatch.setattr(cache, "_redis", redis)
    monkeypatch.setattr(cache, "_redis_bin", binary)
    monkeypatch.setattr(cache, "_ver_local", {})
    monkeypatch.setattr(parser, "pg_insert", lambda model: SQLiteConflict(sqlite_insert(model)))
    monkeypatch.setattr(parser, "literal_inserted", lambda: literal(True))
    monkeypatch.setattr(parser, "_PAUSE_BETWEEN_REQUESTS", 0)
    await populate_regional(sessions)
    try:
        yield sessions, redis, engine
    finally:
        await redis.aclose()
        await binary.aclose()
        await engine.dispose()


async def monthly_value(sessions):
    async with sessions() as reader:
        return (await api.region_indicator_monthly(SLUG, CODE, db=reader))["series"][0]["value"]


async def sql_value(sessions):
    async with sessions() as reader:
        return float(await reader.scalar(
            select(RegionMonthlyPoint.value).join(Region).join(RegionIndicator)
            .where(Region.slug == SLUG, RegionIndicator.code == CODE, RegionMonthlyPoint.month == 202601),
        ))


def set_fetch(monkeypatch, points, plan=((2026, 1),)):
    monkeypatch.setattr(parser, "months_to_fetch", lambda existing: list(plan))

    async def fetch(year, month, *args, **kwargs):
        if isinstance(points, BaseException) or month > 1:
            raise points if isinstance(points, BaseException) else RuntimeError("later month failed")
        return points

    monkeypatch.setattr(parser, "fetch_month_points", fetch)


def test_committed_month_is_visible_when_later_month_fails(tmp_path, monkeypatch):
    async def scenario():
        async with regional_env(tmp_path, monkeypatch) as (sessions, redis, _):
            assert await monthly_value(sessions) == 1
            set_fetch(monkeypatch, [(CODE, SLUG, 202601, 2)], plan=((2026, 1), (2026, 2)))
            async with sessions() as writer:
                with pytest.raises(RuntimeError, match="later month failed"):
                    await parser.run_emiss_regional_update(writer, territory_ids=[], dimnames={})
            assert await sql_value(sessions) == 2
            assert await monthly_value(sessions) == 2
            assert await redis.get("fe:ver:ssr-region") == "1"
            assert await redis.get("fe:ver:og-region") == "1"
    asyncio.run(scenario())


def test_fetch_cancel_after_commit_keeps_previous_month_published(tmp_path, monkeypatch):
    async def scenario():
        async with regional_env(tmp_path, monkeypatch) as (sessions, _, __):
            assert await monthly_value(sessions) == 1
            set_fetch(monkeypatch, [(CODE, SLUG, 202601, 2)], plan=((2026, 1), (2026, 2)))
            original = parser.fetch_month_points

            async def cancel_second(year, month, *args, **kwargs):
                if month == 2:
                    raise asyncio.CancelledError
                return await original(year, month, *args, **kwargs)

            monkeypatch.setattr(parser, "fetch_month_points", cancel_second)
            async with sessions() as writer:
                with pytest.raises(asyncio.CancelledError):
                    await parser.run_emiss_regional_update(writer, territory_ids=[], dimnames={})
            assert await sql_value(sessions) == await monthly_value(sessions) == 2
    asyncio.run(scenario())


def test_real_regional_ssr_cache_observes_previous_commit_after_later_error(tmp_path, monkeypatch):
    from app.api import seo_pages

    async def scenario():
        async with regional_env(tmp_path, monkeypatch) as (sessions, _, engine):
            # conftest disables SSR caching globally; restore all real aliases
            # so a repeated route is a genuine compressed-cache hit.
            monkeypatch.setattr(seo_pages, "cache_get", cache.ssr_cache_get)
            monkeypatch.setattr(seo_pages, "cache_set", cache.ssr_cache_set)
            monkeypatch.setattr(seo_pages, "versioned_key", cache.versioned_key)
            queries = []
            event.listen(engine.sync_engine, "before_cursor_execute", lambda *a: queries.append(a[2]))
            request = Request({"type": "http", "method": "GET", "path": f"/seo/region/{SLUG}/{CODE}", "query_string": b"", "headers": []})
            async with sessions() as reader:
                old = await seo_pages.seo_region_indicator(SLUG, CODE, request, db=reader)
            assert old.status_code == 200
            assert "1 руб./л" in old.body.decode()
            key = await seo_pages._ssr_key("ssr-region", f"region:{SLUG}:{CODE}:ru", await seo_pages._asset_sig())
            raw = await (await cache.get_redis_bin()).get(key)
            assert raw.startswith(cache._SSR_ZLIB_PREFIX)
            n_warm = len(queries)
            async with sessions() as reader:
                assert (await seo_pages.seo_region_indicator(SLUG, CODE, request, db=reader)).body == old.body
            assert len(queries) == n_warm
            set_fetch(monkeypatch, [(CODE, SLUG, 202601, 2)], plan=((2026, 1), (2026, 2)))
            async with sessions() as writer:
                with pytest.raises(RuntimeError, match="later month failed"):
                    await parser.run_emiss_regional_update(writer, territory_ids=[], dimnames={})
            async with sessions() as reader:
                new = await seo_pages.seo_region_indicator(SLUG, CODE, request, db=reader)
            assert new.status_code == 200
            assert "2 руб./л" in new.body.decode()
            assert new.body != old.body
    asyncio.run(scenario())


@pytest.mark.parametrize("failure", [RuntimeError("commit failed"), asyncio.CancelledError()])
def test_failed_commit_or_cancel_publishes_nothing(tmp_path, monkeypatch, failure):
    async def scenario():
        async with regional_env(tmp_path, monkeypatch) as (sessions, redis, _):
            assert await monthly_value(sessions) == 1
            set_fetch(monkeypatch, [(CODE, SLUG, 202601, 2)])
            async with sessions() as writer:
                async def failed_commit():
                    raise failure
                monkeypatch.setattr(writer, "commit", failed_commit)
                with pytest.raises(type(failure)):
                    await parser.run_emiss_regional_update(writer, territory_ids=[], dimnames={})
                await writer.rollback()
            assert await sql_value(sessions) == await monthly_value(sessions) == 1
            assert await redis.get("fe:ver:regions") is None
            assert await redis.get("fe:ver:ssr-region") is None
            assert await redis.get("fe:ver:og-region") is None
    asyncio.run(scenario())


def test_unchanged_month_does_not_publish(tmp_path, monkeypatch):
    async def scenario():
        async with regional_env(tmp_path, monkeypatch) as (sessions, redis, _):
            set_fetch(monkeypatch, [(CODE, SLUG, 202601, 1)])
            async with sessions() as writer:
                stats = await parser.run_emiss_regional_update(writer, territory_ids=[], dimnames={})
            assert stats == {"months": 1, "added": 0, "updated": 0}
            assert await redis.get("fe:ver:regions") is None
    asyncio.run(scenario())


def test_bounds_only_repair_is_committed_and_published(tmp_path, monkeypatch):
    async def scenario():
        async with regional_env(tmp_path, monkeypatch) as (sessions, redis, _):
            async with sessions() as setup:
                await setup.execute(update(RegionIndicator).values(year_min=2003, year_max=2025))
                await setup.commit()
            async with sessions() as reader:
                old = await api.regions_catalog(db=reader)
            assert old["sections"][0]["indicators"][0]["year_min"] == 2003
            set_fetch(monkeypatch, [(CODE, SLUG, 202601, 1)])
            async with sessions() as writer:
                stats = await parser.run_emiss_regional_update(writer, territory_ids=[], dimnames={})
            assert stats == {"months": 1, "added": 0, "updated": 0}
            async with sessions() as reader:
                row = next(i for i in (await api.regions_catalog(db=reader))["sections"][0]["indicators"] if i["code"] == CODE)
            assert (row["year_min"], row["year_max"]) == (2026, 2026)
            assert await redis.get("fe:ver:regions") == "1"
    asyncio.run(scenario())


def test_failed_namespace_does_not_recast_sql_success_or_skip_other_consumers(tmp_path, monkeypatch):
    async def scenario():
        async with regional_env(tmp_path, monkeypatch) as (sessions, redis, _):
            set_fetch(monkeypatch, [(CODE, SLUG, 202601, 2)])
            bump = cache.bump_namespaces
            attempted = []

            async def fail_api(*namespaces):
                attempted.extend(namespaces)
                if "regions" in namespaces:
                    raise RuntimeError("cache publication failure")
                await bump(*namespaces)

            monkeypatch.setattr(cache, "bump_namespaces", fail_api)
            async with sessions() as writer:
                stats = await parser.run_emiss_regional_update(writer, territory_ids=[], dimnames={})
            assert stats["added"] + stats["updated"] == 1
            assert await sql_value(sessions) == 2
            assert attempted == ["regions", "ssr-region", "og-region"]
            assert await redis.get("fe:ver:ssr-region") == await redis.get("fe:ver:og-region") == "1"
    asyncio.run(scenario())


def test_cancel_during_publication_waits_for_committed_cache_generations(tmp_path, monkeypatch):
    async def scenario():
        async with regional_env(tmp_path, monkeypatch) as (sessions, redis, _):
            assert await monthly_value(sessions) == 1
            set_fetch(monkeypatch, [(CODE, SLUG, 202601, 2)])
            entered, release = asyncio.Event(), asyncio.Event()
            bump = cache.bump_namespaces

            async def blocked(*namespaces):
                if "regions" in namespaces:
                    assert await sql_value(sessions) == 2  # Independent committed reader.
                    entered.set()
                    await release.wait()
                await bump(*namespaces)

            monkeypatch.setattr(cache, "bump_namespaces", blocked)
            # Old implementation imported this function directly.
            monkeypatch.setattr(parser, "bump_namespaces", blocked, raising=False)
            async with sessions() as writer:
                task = asyncio.create_task(parser.run_emiss_regional_update(writer, territory_ids=[], dimnames={}))
                try:
                    await asyncio.wait_for(entered.wait(), timeout=2)
                    task.cancel()
                    await asyncio.sleep(0.01)
                    assert not task.done(), "cancellation abandoned a committed publication"
                    release.set()
                    with pytest.raises(asyncio.CancelledError):
                        await task
                    assert await monthly_value(sessions) == 2
                    assert await redis.get("fe:ver:ssr-region") == "1"
                    assert await redis.get("fe:ver:og-region") == "1"
                finally:
                    release.set()
                    task.cancel()
                    with suppress(asyncio.CancelledError):
                        await task
    asyncio.run(scenario())


def test_revision_plan_includes_previous_month_even_after_future_anchor():
    plan = parser.months_to_fetch({202609}, today=date(2026, 9, 30))
    assert (2026, 8) in plan
    assert (2026, 9) in plan
    assert len(plan) == len(set(plan))


@pytest.mark.parametrize("name,args", [
    ("og_image_region_indicator", (SLUG, CODE)),
    ("og_image_region_indicator_year", (SLUG, CODE, 2026)),
    ("og_image_region_rating", (CODE,)),
    ("og_image_region_vs", (SLUG, "bryanskaya-oblast")),
])
def test_regional_og_generation_bypasses_both_memory_and_disk_after_commit(tmp_path, monkeypatch, name, args):
    from app.api import sitemap
    from app.services import og_image

    async def scenario():
        async with regional_env(tmp_path, monkeypatch) as (sessions, _, __):
            monkeypatch.setattr(og_image, "_DISK_DIR", tmp_path / "og")
            monkeypatch.setattr(og_image, "_CACHE", {})
            rendered = []

            async def render(renderer, **kwargs):
                rendered.append(kwargs)
                return json.dumps(kwargs, ensure_ascii=False, default=str).encode()

            monkeypatch.setattr(sitemap, "render_og_async", render)
            reader = getattr(sitemap, name)
            async with sessions() as db:
                old = await reader(*args, db=db)
            assert old.status_code == 200
            assert len(rendered) == 1
            assert len(list((tmp_path / "og").glob("*.png"))) == 1
            og_image._CACHE.clear()  # Simulate another process/restart: disk cache remains.
            async with sessions() as db:
                assert (await reader(*args, db=db)).body == old.body
            assert len(rendered) == 1
            async with sessions() as writer:
                await writer.execute(update(RegionDataPoint).values(value=2))
                await writer.execute(update(RegionMonthlyPoint).values(value=2))
                await writer.commit()
            await cache.bump_namespaces("og-region")
            async with sessions() as db:
                new = await reader(*args, db=db)
            assert len(rendered) == 2
            assert new.body != old.body
            assert len(list((tmp_path / "og").glob("*.png"))) == 2
            if "values" in rendered[-1]:
                assert rendered[-1]["values"] == [2.0]
            else:
                assert any("2" in str(row) for row in rendered[-1]["rows"])
    asyncio.run(scenario())


READERS = [
    (api.regions_landing, ()), (api.regions_catalog, ()),
    (api.regions_heatmap, (CODE,)), (api.regions_heatmap_series, (CODE,)),
    (api.regions_compare, (SLUG, "bryanskaya-oblast")), (api.region_profile, (SLUG,)),
    (api.region_indicator_detail, (SLUG, CODE)), (api.region_indicator_monthly, (SLUG, CODE)),
]


@pytest.mark.parametrize("reader,args", READERS, ids=[r.__name__ for r, _ in READERS])
def test_each_regional_api_reader_observes_committed_namespace_change(tmp_path, monkeypatch, reader, args):
    async def scenario():
        async with regional_env(tmp_path, monkeypatch) as (sessions, _, engine):
            queries = []
            event.listen(engine.sync_engine, "before_cursor_execute", lambda *a: queries.append(a[2]))
            async with sessions() as db:
                old = await reader(*args, db=db)
            n_warm = len(queries)
            async with sessions() as db:
                assert await reader(*args, db=db) == old
            assert len(queries) == n_warm  # A genuine cached API hit.
            async with sessions() as writer:
                await writer.execute(update(RegionDataPoint).values(value=2))
                await writer.execute(update(RegionMonthlyPoint).values(value=2))
                await writer.execute(update(RegionIndicator).values(name="Обновлённое название"))
                await writer.execute(update(Region).values(name="Обновлённый регион"))
                await writer.commit()
            await cache.bump_namespaces("regions")
            before = len(queries)
            async with sessions() as db:
                new = await reader(*args, db=db)
            assert len(queries) > before, "old fixed cache key hid the committed data"
            assert new != old
    asyncio.run(scenario())


def test_default_okato_registry_maps_official_payload_to_region_and_russia(tmp_path, monkeypatch):
    async def scenario():
        async with regional_env(tmp_path, monkeypatch) as (sessions, _, __):
            # Exercise native mapping/parsing with only the SQL syntax adapter.
            monkeypatch.setattr(parser, "months_to_fetch", lambda existing: [(2026, 1)])

            async def post_grid(*args):
                return {"results": [
                    {"dim57831": "1688489", "dim1709730_d0_i0": "2,0"},
                    {"dim57831": "1849012", "dim1709730_d0_i0": "3,0"},
                ]}

            async with sessions() as writer:
                stats = await parser.run_emiss_regional_update(writer, post_grid=post_grid)
            assert stats["added"] + stats["updated"] == 2
            assert await sql_value(sessions) == 2
    asyncio.run(scenario())
