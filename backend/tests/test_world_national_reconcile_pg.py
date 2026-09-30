"""Real national point writes in an explicitly opted-in isolated PostgreSQL.

F01_TEST_DATABASE_URL must name a loopback database with a ``fe_f01_`` prefix.
No application DATABASE_URL is read. Every test creates/drops only its own
random schema; adapters never call an external source in this suite.
"""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import date, datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from sqlalchemy.schema import CreateSchema, CreateTable, DropSchema

from app.models import WorldCountry, WorldDataPoint, WorldDatasetState, WorldIndicator
from app.services.world_national_ingest import (
    NationalSeriesSpec,
    ingest_series,
    reconcile_points,
)
from app.services.world_source_adapter import WorldObservation, WorldSeriesPayload, WorldSeriesRef


def _validated_pg_url(raw):
    url = make_url(raw)
    if (
        url.drivername != "postgresql+asyncpg"
        or url.host not in {"127.0.0.1", "localhost", "::1"}
        or not (url.database or "").startswith("fe_f01_")
        or url.query
    ):
        raise ValueError("F01_TEST_DATABASE_URL must be isolated PostgreSQL on loopback, database fe_f01_*")
    return url


@pytest.fixture
def isolated_pg_url():
    raw = os.environ.get("F01_TEST_DATABASE_URL")
    if not raw:
        pytest.skip("Set F01_TEST_DATABASE_URL to an isolated loopback fe_f01_* database")
    return _validated_pg_url(raw)


@asynccontextmanager
async def _world_database(url):
    schema = f"f01_test_{uuid4().hex}"
    engine = create_async_engine(
        url,
        poolclass=NullPool,
        connect_args={"server_settings": {"search_path": schema}},
    )
    created = False
    try:
        async with engine.begin() as conn:
            await conn.execute(CreateSchema(schema))
        created = True
        async with engine.begin() as conn:
            # Constraints are real; unrelated production search indexes and
            # extensions are unnecessary to exercise this write contract.
            for model in (WorldCountry, WorldIndicator, WorldDataPoint, WorldDatasetState):
                await conn.execute(CreateTable(model.__table__))
        yield async_sessionmaker(engine, expire_on_commit=False)
    finally:
        try:
            if created:
                async with engine.begin() as conn:
                    await conn.execute(DropSchema(schema, cascade=True))
        finally:
            await engine.dispose()


async def _seed_history(session):
    country = WorldCountry(code="T1", slug="f01-fixture", name_ru="Тест", name_en="Test")
    session.add(country)
    await session.flush()
    indicator = WorldIndicator(
        country_id=country.id,
        provider="fixture",
        code="f01-history",
        dataset_id="fixture",
        slice_hash="fixture",
        slice_json={},
        name_ru="Тест",
        frequency="monthly",
    )
    session.add(indicator)
    await session.flush()
    session.add_all([
        WorldDataPoint(indicator_id=indicator.id, date=date(2025, month, 1), value=float(month))
        for month in (1, 2, 3)
    ])
    await session.flush()
    return indicator.id


async def _stored_points(session, indicator_id):
    return list((await session.execute(
        select(WorldDataPoint.date, WorldDataPoint.value)
        .where(WorldDataPoint.indicator_id == indicator_id)
        .order_by(WorldDataPoint.date)
    )).all())


def test_partial_nonempty_response_preserves_committed_history(isolated_pg_url):
    async def run():
        async with _world_database(isolated_pg_url) as sessions:
            async with sessions() as session:
                async with session.begin():
                    indicator_id = await _seed_history(session)
                async with session.begin():
                    touched, removed = await reconcile_points(
                        session, indicator_id, [(date(2025, 3, 1), 30.0)]
                    )
            # A new session checks committed state, not only identity-map data.
            async with sessions() as session:
                assert await _stored_points(session, indicator_id) == [
                    (date(2025, 1, 1), 1.0),
                    (date(2025, 2, 1), 2.0),
                    (date(2025, 3, 1), 30.0),
                ]
                assert (touched, removed) == (1, 0)
            async with sessions() as session:
                async with session.begin():
                    assert await reconcile_points(
                        session, indicator_id, [(date(2025, 3, 1), 30.0)]
                    ) == (0, 0)

    asyncio.run(run())


@pytest.mark.parametrize("raw", [
    "postgresql+asyncpg://localhost/main",
    "postgresql+asyncpg://remote.example/fe_f01_test",
    "sqlite+aiosqlite:///fe_f01_test",
    "postgresql+asyncpg://localhost/fe_f01_test?host=remote.example",
])
def test_pg_fixture_rejects_nonisolated_urls(raw):
    with pytest.raises(ValueError, match="isolated PostgreSQL"):
        _validated_pg_url(raw)


def _ref():
    return WorldSeriesRef(
        provider="fixture", dataset_id="fixture", series_id="fixture",
        country_code="T1", frequency="monthly", unit_code="INDEX",
    )


def test_payload_is_partial_by_default_and_complete_requires_explicit_window():
    observation = WorldObservation(period=date(2025, 3, 1), value=30.0)
    partial = WorldSeriesPayload(
        ref=_ref(), observations=[observation], fetched_at=datetime.now(timezone.utc),
    )
    assert partial.is_complete is False
    assert partial.coverage_start is None and partial.coverage_end is None
    complete = replace(
        partial, is_complete=True,
        coverage_start=date(2025, 2, 1), coverage_end=date(2025, 3, 1),
    )
    assert complete.is_complete is True


@pytest.mark.parametrize("claim", [
    {"is_complete": "true"},
    {"is_complete": True},
    {"is_complete": True, "coverage_start": date(2025, 2, 1)},
    {"is_complete": True, "coverage_end": date(2025, 3, 1)},
    {"is_complete": True, "coverage_start": date(2025, 3, 1), "coverage_end": date(2025, 2, 1)},
    {"is_complete": True, "coverage_start": date(2025, 2, 1), "coverage_end": date(2025, 2, 1)},
    {"is_complete": True, "coverage_start": date(2025, 2, 1), "coverage_end": date(2025, 3, 1), "observations": []},
])
def test_payload_rejects_untrusted_complete_claims(claim):
    args = dict(
        ref=_ref(), observations=[WorldObservation(period=date(2025, 3, 1), value=30.0)],
        fetched_at=datetime.now(timezone.utc),
    )
    args.update(claim)
    with pytest.raises(ValueError):
        WorldSeriesPayload(**args)


def test_complete_window_prunes_inside_and_preserves_outside_and_other_series(isolated_pg_url):
    async def run():
        async with _world_database(isolated_pg_url) as sessions:
            async with sessions() as session:
                async with session.begin():
                    indicator_id = await _seed_history(session)
                    first = await session.get(WorldIndicator, indicator_id)
                    other = WorldIndicator(
                        country_id=first.country_id, provider="other", code="f01-other",
                        dataset_id="fixture", slice_hash="other", slice_json={},
                        name_ru="Другой ряд", frequency="monthly",
                    )
                    session.add(other)
                    await session.flush()
                    other_id = other.id
                    session.add_all([
                        WorldDataPoint(indicator_id=indicator_id, date=date(2025, 4, 1), value=4.0),
                        WorldDataPoint(indicator_id=other_id, date=date(2025, 2, 1), value=99.0),
                    ])
                async with session.begin():
                    assert await reconcile_points(
                        session, indicator_id, [(date(2025, 3, 1), 30.0)],
                        is_complete=True,
                        coverage_start=date(2025, 2, 1), coverage_end=date(2025, 3, 1),
                    ) == (1, 1)
                async with session.begin():
                    assert await reconcile_points(
                        session, indicator_id, [(date(2025, 3, 1), 30.0)],
                        is_complete=True,
                        coverage_start=date(2025, 2, 1), coverage_end=date(2025, 3, 1),
                    ) == (0, 0)
            async with sessions() as session:
                assert await _stored_points(session, indicator_id) == [
                    (date(2025, 1, 1), 1.0), (date(2025, 3, 1), 30.0), (date(2025, 4, 1), 4.0),
                ]
                assert await _stored_points(session, other_id) == [(date(2025, 2, 1), 99.0)]

    asyncio.run(run())


def test_invalid_replacement_fails_before_point_writes(isolated_pg_url):
    async def run():
        async with _world_database(isolated_pg_url) as sessions:
            async with sessions() as session:
                async with session.begin():
                    indicator_id = await _seed_history(session)
                async with session.begin():
                    with pytest.raises(ValueError, match="outside"):
                        await reconcile_points(
                            session, indicator_id, [(date(2025, 3, 1), 30.0)],
                            is_complete=True,
                            coverage_start=date(2025, 2, 1), coverage_end=date(2025, 2, 1),
                        )
            async with sessions() as session:
                assert await _stored_points(session, indicator_id) == [
                    (date(2025, 1, 1), 1.0), (date(2025, 2, 1), 2.0), (date(2025, 3, 1), 3.0),
                ]

    asyncio.run(run())


class _FixtureAdapter:
    provider = "fixture"
    public_source_name = "Fixture official source"

    def __init__(self, points, **payload_options):
        self.points = points
        self.payload_options = payload_options

    async def fetch_series(self, ref, *, date_from=None, date_to=None):
        if self.payload_options.get("fail_fetch"):
            raise TimeoutError("fixture upstream timeout")
        return WorldSeriesPayload(
            ref=replace(ref, series_id="wrong") if self.payload_options.get("wrong_identity") else ref,
            observations=[WorldObservation(period=period, value=value) for period, value in self.points],
            fetched_at=datetime.now(timezone.utc),
            **{key: value for key, value in self.payload_options.items() if key not in {"fail_fetch", "wrong_identity"}},
        )


def _spec():
    return NationalSeriesSpec(
        code_suffix="history", name_ru="Тест", name_en="Test", category_ru="Тест",
        unit="INDEX", unit_ru="индекс", frequency="monthly", provider="fixture",
        dataset_id="fixture", series_id="fixture",
    )


async def _initial_ingest(session, *, months=(1, 2, 3), spec=None):
    country = WorldCountry(code="T1", slug="f01-ingest", name_ru="Тест", name_en="Test")
    session.add(country)
    await session.flush()
    result = await ingest_series(
        session, country=country, spec=spec or _spec(),
        adapter=_FixtureAdapter([(date(2025, month, 1), float(month)) for month in months]),
    )
    assert result.error is None
    return country.id, result.indicator_id


def test_ingest_propagates_complete_scope_and_database_extent(isolated_pg_url):
    async def run():
        async with _world_database(isolated_pg_url) as sessions:
            async with sessions() as session:
                async with session.begin():
                    country_id, indicator_id = await _initial_ingest(session)
                async with session.begin():
                    country = await session.get(WorldCountry, country_id)
                    result = await ingest_series(
                        session, country=country, spec=_spec(),
                        adapter=_FixtureAdapter([(date(2025, 3, 1), 30.0)], is_complete=True,
                                                coverage_start=date(2025, 2, 1), coverage_end=date(2025, 3, 1)),
                    )
                    assert result.error is None
                    assert (result.points_touched, result.points_removed) == (1, 1)
            async with sessions() as session:
                indicator = await session.get(WorldIndicator, indicator_id)
                assert (indicator.points_count, indicator.history_start, indicator.history_end) == (
                    2, date(2025, 1, 1), date(2025, 3, 1),
                )
                assert await _stored_points(session, indicator_id) == [
                    (date(2025, 1, 1), 1.0), (date(2025, 3, 1), 30.0),
                ]

    asyncio.run(run())


@pytest.mark.parametrize("description", [None, "Авторское описание из паспорта"])
def test_partial_ingest_preserves_public_history_span_curated_text_and_source_date(isolated_pg_url, description):
    async def run():
        async with _world_database(isolated_pg_url) as sessions:
            spec = replace(_spec(), description=description, is_listed=True)
            async with sessions() as session:
                async with session.begin():
                    country_id, indicator_id = await _initial_ingest(session, months=(1, 2, 3, 4), spec=spec)
                async with session.begin():
                    country = await session.get(WorldCountry, country_id)
                    result = await ingest_series(
                        session, country=country, spec=spec,
                        adapter=_FixtureAdapter([(date(2025, 2, 1), 2.5), (date(2025, 3, 1), 3.5)]),
                    )
                    assert result.error is None
                    assert result.points_touched == 2 and result.points_removed == 0
                    assert result.metadata_changed is False
            async with sessions() as session:
                indicator = await session.get(WorldIndicator, indicator_id)
                expected = description or "Тест (Тест). Динамика с 2025-01-01 по 2025-04-01. Единица измерения — индекс."
                assert indicator.description == expected
                assert indicator.seo_description == expected
                assert indicator.is_listed is True and indicator.frequency == "monthly"
                assert indicator.source == _FixtureAdapter.public_source_name
                assert (indicator.points_count, indicator.history_start, indicator.history_end) == (
                    4, date(2025, 1, 1), date(2025, 4, 1),
                )
                state = await session.get(WorldDatasetState, ("fixture", "fixture"))
                assert state.last_update_of_data == date(2025, 4, 1)
                assert await _stored_points(session, indicator_id) == [
                    (date(2025, 1, 1), 1.0), (date(2025, 2, 1), 2.5),
                    (date(2025, 3, 1), 3.5), (date(2025, 4, 1), 4.0),
                ]

    asyncio.run(run())


@pytest.mark.parametrize("failure", ["upstream", "after-writes", "identity"])
def test_ingest_error_preserves_committed_points_metadata_and_error_status(isolated_pg_url, monkeypatch, failure):
    import app.services.world_national_ingest as ingest_mod

    async def run():
        async with _world_database(isolated_pg_url) as sessions:
            async with sessions() as session:
                async with session.begin():
                    country_id, indicator_id = await _initial_ingest(session)
                    initial_description = (await session.get(WorldIndicator, indicator_id)).description
                if failure == "after-writes":
                    async def fail_after_writes(db, iid):
                        raise RuntimeError("fixture failure after actual INSERT/UPDATE/DELETE")
                    monkeypatch.setattr(ingest_mod, "refresh_indicator_extent", fail_after_writes)
                async with session.begin():
                    country = await session.get(WorldCountry, country_id)
                    options = dict(is_complete=True, coverage_start=date(2025, 2, 1), coverage_end=date(2025, 3, 1))
                    if failure == "upstream":
                        options["fail_fetch"] = True
                    if failure == "identity":
                        options["wrong_identity"] = True
                    result = await ingest_series(
                        session, country=country, spec=replace(_spec(), description="Must roll back"),
                        adapter=_FixtureAdapter([(date(2025, 3, 1), 30.0)], **options),
                    )
                    assert result.error is not None
                    assert result.points_touched == 0 and result.points_removed == 0
            async with sessions() as session:
                assert await _stored_points(session, indicator_id) == [
                    (date(2025, 1, 1), 1.0), (date(2025, 2, 1), 2.0), (date(2025, 3, 1), 3.0),
                ]
                indicator = await session.get(WorldIndicator, indicator_id)
                assert indicator.description == initial_description
                assert indicator.points_count == 3
                state = await session.get(WorldDatasetState, ("fixture", "fixture"))
                assert state.status == "error"
                assert state.last_error == result.error

    asyncio.run(run())
