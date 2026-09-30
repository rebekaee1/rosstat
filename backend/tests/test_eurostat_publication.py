"""Committed Eurostat writes must publish even when a later slice fails.

The normal suite uses a real SQLite transaction for remaps. PostgreSQL slice
acceptance is covered separately; fetching Eurostat is never part of this test.
"""
import argparse
import asyncio
import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models import Base, WorldCountry, WorldIndicator
from app.services.eurostat_parser import DatasetParseResult
from app.services.eurostat_structure import StructureVerdict


def _loader():
    path = Path(__file__).resolve().parents[1] / "scripts/load-world-eurostat.py"
    spec = importlib.util.spec_from_file_location("eurostat_publication_loader", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_committed_remap_is_published_before_later_slice_error(tmp_path, monkeypatch):
    loader = _loader()

    async def scenario():
        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'world.db'}")
        maker = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            async with maker() as db:
                country = WorldCountry(code="DE", slug="germany", name_ru="Германия",
                                       name_en="Germany", region_ru="Европа")
                db.add(country)
                await db.flush()
                card = WorldIndicator(country_id=country.id, provider="eurostat",
                                      code="de-test-card", dataset_id="test", slice_hash="old",
                                      slice_json={"freq": "A"}, name_ru="Тест", frequency="annual")
                db.add(card)
                await db.commit()
                card_id = card.id

            observed = []

            async def publish(*namespaces):
                # A separate reader sees only committed state at publication.
                async with maker() as reader:
                    stored = await reader.get(WorldIndicator, card_id)
                    observed.append((namespaces, stored.slice_hash))

            async def selected(*args, **kwargs):
                return [{"dataset_id": "test", "frequency": "A", "title": "test"}]

            async def countries(*args):
                return {"DE": country.id}

            async def verdict(*args):
                return StructureVerdict(accept=True, remapped={card_id: ({"freq": "A", "unit": "PC"}, "new")})

            async def failed_slice(*args):
                raise RuntimeError("controlled slice persistence failure")

            result = DatasetParseResult(dataset_id="test", title_en="Test", frequency="annual",
                                        slice_={"freq": "A", "unit": "PC"}, slice_hash="new",
                                        unit="PC", series_by_geo={"DE": []}, source_url="https://example.invalid")
            monkeypatch.setattr(loader, "async_session", maker)
            monkeypatch.setattr(loader, "bump_namespaces", publish)
            monkeypatch.setattr(loader, "select_datasets", selected)
            monkeypatch.setattr(loader, "ensure_countries", countries)
            monkeypatch.setattr(loader, "check_structure", verdict)
            monkeypatch.setattr(loader, "_parse_one", lambda *args, **kwargs: [result])
            monkeypatch.setattr(loader, "persist_result", failed_slice)
            args = argparse.Namespace(themes="test", freq="A", limit=None, only="test",
                                      dry_run=False, no_cache=True, workers=1, structure_check=True)
            with pytest.raises(RuntimeError, match="controlled slice persistence failure"):
                await loader.run(args)
            async with maker() as reader:
                assert (await reader.get(WorldIndicator, card_id)).slice_hash == "new"
            assert observed == [(("world", "world-catalog", "ssr-world"), "new")]
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_remap_rollback_never_publishes(tmp_path, monkeypatch):
    loader = _loader()

    async def scenario():
        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'rollback.db'}")
        maker = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            async with maker() as db:
                country = WorldCountry(code="DE", slug="germany", name_ru="Германия",
                                       name_en="Germany", region_ru="Европа")
                db.add(country)
                await db.flush()
                for code, hash_ in (("de-one", "one"), ("de-two", "two")):
                    db.add(WorldIndicator(country_id=country.id, provider="eurostat", code=code,
                                          dataset_id="test", slice_hash=hash_, name_ru="Тест", frequency="annual"))
                await db.commit()
                ids = (await db.execute(select(WorldIndicator.id).order_by(WorldIndicator.id))).scalars().all()
            observed = []

            async def publish(*namespaces):
                observed.append(namespaces)

            monkeypatch.setattr(loader, "bump_namespaces", publish)
            verdict = StructureVerdict(accept=True, remapped={ids[0]: ({"freq": "A"}, "two")})
            from sqlalchemy.exc import IntegrityError
            with pytest.raises(IntegrityError):
                await loader.apply_remaps(verdict, session_factory=maker)
            assert observed == []
            async with maker() as reader:
                assert (await reader.get(WorldIndicator, ids[0])).slice_hash == "one"
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_country_metadata_commit_publishes_once_and_noop_does_not(tmp_path, monkeypatch):
    loader = _loader()

    async def scenario():
        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'countries.db'}")
        maker = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            observed = []

            async def publish(*namespaces):
                async with maker() as reader:
                    observed.append((await reader.execute(select(WorldCountry.code))).scalars().all())

            monkeypatch.setattr(loader, "async_session", maker)
            monkeypatch.setattr(loader, "bump_namespaces", publish)
            await loader.ensure_countries({"DE", "FR"})
            await loader.ensure_countries({"DE", "FR"})
            assert len(observed) == 1
            assert set(observed[0]) == {"DE", "FR"}
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_publication_finishes_before_propagating_cancellation(monkeypatch):
    loader = _loader()

    async def scenario():
        entered = asyncio.Event()
        release = asyncio.Event()
        published = []

        async def publish(*namespaces):
            entered.set()
            await release.wait()
            published.append(namespaces)

        monkeypatch.setattr(loader, "bump_namespaces", publish)
        task = asyncio.create_task(loader.publish_committed_changes())
        await entered.wait()
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert published == [("world", "world-catalog", "ssr-world")]

    asyncio.run(scenario())


def test_publication_failure_is_not_reported_as_success(monkeypatch):
    loader = _loader()

    async def publish(*namespaces):
        raise RuntimeError("controlled catalogue publication failure")

    monkeypatch.setattr(loader, "bump_namespaces", publish)
    with pytest.raises(RuntimeError, match="controlled catalogue publication failure"):
        asyncio.run(loader.publish_committed_changes())
