"""Материализованный счётчик публичных рядов по странам (круг 12, SPEED3): тот же результат, что у живого COUNT."""
from __future__ import annotations

import asyncio
from datetime import timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import settings
from app.models import Base, WorldCountry, WorldCountryListedCount, WorldIndicator
from app.services import seo_world, world_listed_counts


def _indicator(country_id: int, n: int, *, listed: bool) -> WorldIndicator:
    return WorldIndicator(
        country_id=country_id, provider="eurostat", code=f"c{country_id}-{n}", dataset_id=f"ds{n}",
        slice_hash=f"h{n}", slice_json={"freq": "A"}, name_ru=f"Ряд {n}", frequency="annual", is_listed=listed,
    )


async def _seed(maker):
    async with maker() as db:
        # Порядок каталога: sort_order, затем имя. «Пустая» — без публичных рядов, «Закрытая» — неактивна.
        countries = [
            WorldCountry(code="DE", slug="germany", name_ru="Германия", name_en="Germany", sort_order=2),
            WorldCountry(code="FR", slug="france", name_ru="Франция", name_en="France", sort_order=1),
            WorldCountry(code="XX", slug="empty", name_ru="Пустая", name_en="Empty", sort_order=3),
            WorldCountry(code="ZZ", slug="closed", name_ru="Закрытая", name_en="Closed", sort_order=4, is_active=False),
        ]
        db.add_all(countries)
        await db.flush()
        de, fr, empty, closed = (c.id for c in countries)
        for n in range(3):
            db.add(_indicator(de, n, listed=True))
        db.add(_indicator(de, 9, listed=False))
        db.add(_indicator(fr, 0, listed=True))
        db.add(_indicator(empty, 0, listed=False))
        db.add(_indicator(closed, 0, listed=True))
        await db.commit()
        return {"de": de, "fr": fr, "empty": empty, "closed": closed}


def _run(tmp_path, scenario):
    async def main():
        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'w.db'}")
        maker = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            return await scenario(maker)
        finally:
            await engine.dispose()

    return asyncio.run(main())


def test_flag_is_off_by_default():
    assert settings.world_listed_counts_enabled is False


def test_refresh_matches_live_count_and_drops_vanished_rows(tmp_path, monkeypatch):
    async def scenario(maker):
        ids = await _seed(maker)
        async with maker() as db:
            result = await world_listed_counts.refresh_world_listed_counts(db)
        # Страна без публичных рядов в таблицу не попадает — как в подзапросе с GROUP BY.
        assert result == {"countries": 3, "rows_deleted": 0}
        async with maker() as db:
            stored = {r.country_id: r.listed_count for r in (await db.execute(select(WorldCountryListedCount))).scalars()}
        assert stored == {ids["de"]: 3, ids["fr"]: 1, ids["closed"]: 1}

        # Ряды исчезли/появились: пересчёт повторяет живой COUNT, лишние строки удаляются.
        async with maker() as db:
            for ind in (await db.execute(select(WorldIndicator).where(WorldIndicator.country_id == ids["fr"]))).scalars():
                ind.is_listed = False
            db.add(_indicator(ids["empty"], 5, listed=True))
            await db.commit()
        async with maker() as db:
            result = await world_listed_counts.refresh_world_listed_counts(db)
        assert result == {"countries": 3, "rows_deleted": 1}
        async with maker() as db:
            stored = {r.country_id: r.listed_count for r in (await db.execute(select(WorldCountryListedCount))).scalars()}
        assert stored == {ids["de"]: 3, ids["empty"]: 1, ids["closed"]: 1}

    _run(tmp_path, scenario)


def test_read_returns_none_when_flag_off_empty_or_stale(tmp_path, monkeypatch):
    async def scenario(maker):
        await _seed(maker)
        async with maker() as db:
            monkeypatch.setattr(settings, "world_listed_counts_enabled", False)
            assert await world_listed_counts.read_listed_counts(db) is None
            monkeypatch.setattr(settings, "world_listed_counts_enabled", True)
            assert await world_listed_counts.read_listed_counts(db) is None  # пустая таблица
            await world_listed_counts.refresh_world_listed_counts(db)
            fresh = await world_listed_counts.read_listed_counts(db)
            assert fresh and sorted(fresh.values()) == [1, 1, 3]
            for row in (await db.execute(select(WorldCountryListedCount))).scalars():
                row.computed_at = row.computed_at - timedelta(hours=7)
            await db.commit()
            assert await world_listed_counts.read_listed_counts(db) is None  # старше 6 часов

    _run(tmp_path, scenario)


def test_catalog_readers_are_identical_with_and_without_table(tmp_path, monkeypatch):
    async def scenario(maker):
        await _seed(maker)
        monkeypatch.setattr(settings, "world_listed_counts_enabled", False)
        async with maker() as db:
            live_links = await seo_world.listed_country_links(db)
            live_rating = [c.slug for c in await seo_world._world_rating_countries(db)]
        monkeypatch.setattr(settings, "world_listed_counts_enabled", True)
        async with maker() as db:
            await world_listed_counts.refresh_world_listed_counts(db)
            assert await world_listed_counts.read_listed_counts(db) is not None
            table_links = await seo_world.listed_country_links(db)
            table_rating = [c.slug for c in await seo_world._world_rating_countries(db)]
        assert live_links == table_links
        assert live_rating == table_rating == ["france", "germany"]
        assert len(live_links) == 2

    _run(tmp_path, scenario)


def test_missing_table_does_not_break_the_catalog(tmp_path, monkeypatch):
    """Выкладка раньше миграции: чтение таблицы падает, но запрос страницы продолжается по-старому."""
    async def scenario(maker):
        await _seed(maker)
        async with maker() as db:
            from sqlalchemy import text

            await db.execute(text("DROP TABLE world_country_listed_counts"))
            await db.commit()
        monkeypatch.setattr(settings, "world_listed_counts_enabled", True)
        async with maker() as db:
            links = await seo_world.listed_country_links(db)
        assert len(links) == 2

    _run(tmp_path, scenario)


def test_catalog_bump_refreshes_counts_before_version_change(monkeypatch):
    from app.core import cache

    order: list[str] = []

    async def fake_refresh():
        order.append("refresh")

    class FakeRedis:
        async def eval(self, *args):
            order.append("bump")

    async def fake_state():
        return FakeRedis()

    async def fake_clear():
        order.append("clear")

    monkeypatch.setattr(world_listed_counts, "refresh_before_catalog_bump", fake_refresh)
    monkeypatch.setattr(cache, "get_state_redis", fake_state)
    monkeypatch.setattr(cache, "clear_durable_world_countries", fake_clear)
    asyncio.run(cache.bump_namespaces("world-catalog"))
    assert order[:2] == ["refresh", "bump"]

    order.clear()
    asyncio.run(cache.bump_namespaces("ssr-world"))
    assert "refresh" not in order


def test_refresh_before_bump_swallows_errors_and_respects_flag(monkeypatch):
    calls = []

    async def failing():
        calls.append(1)
        raise RuntimeError("db down")

    monkeypatch.setattr(world_listed_counts, "_refresh_in_new_session", failing)
    monkeypatch.setattr(settings, "world_listed_counts_enabled", False)
    asyncio.run(world_listed_counts.refresh_before_catalog_bump())
    assert calls == []
    monkeypatch.setattr(settings, "world_listed_counts_enabled", True)
    asyncio.run(world_listed_counts.refresh_before_catalog_bump())  # не бросает
    assert calls == [1]


@pytest.mark.parametrize("name", ["20261012c_world_listed_cnt"])
def test_migration_revision_id_fits_alembic_version(name):
    assert len(name) <= 32
