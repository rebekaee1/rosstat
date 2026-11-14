"""«Этот показатель в других странах» (14.11.2026): кэш на срез, выдача та же, что у прежнего запроса."""
import asyncio

from sqlalchemy import select

from app.models import WorldCountry, WorldIndicator
from app.services import seo_world

from tests.test_analytics2 import _run_with_db


async def _old_peers(db, indicator, country_id):
    """Прежний запрос блока до 14.11.2026 — эталон."""
    return [tuple(r) for r in (await db.execute(
        select(WorldCountry.slug, WorldCountry.name_ru, WorldCountry.name_en, WorldIndicator.code)
        .join(WorldIndicator, WorldIndicator.country_id == WorldCountry.id)
        .where(
            WorldIndicator.provider == indicator.provider,
            WorldIndicator.dataset_id == indicator.dataset_id,
            WorldIndicator.slice_hash == indicator.slice_hash,
            WorldIndicator.is_listed.is_(True),
            WorldCountry.is_active.is_(True),
            WorldCountry.id != country_id,
        )
        .order_by(WorldCountry.sort_order, WorldCountry.name_ru)
        .limit(12)
    )).all()]


def _seed():
    out = []
    for i in range(1, 21):
        out.append(WorldCountry(id=i, code=f"C{i}", slug=f"c{i}", name_ru=f"Страна {i:02d}", name_en=f"Country {i}",
                                sort_order=i % 5, is_active=i != 7))
        out.append(WorldIndicator(id=i, country_id=i, code=f"c{i}-gdp", name_ru="ВВП", name_en="GDP",
                                  provider="eurostat", dataset_id="nama", slice_hash="s1", frequency="annual",
                                  is_listed=i != 9))
        out.append(WorldIndicator(id=100 + i, country_id=i, code=f"c{i}-other", name_ru="Другое", name_en="X",
                                  provider="eurostat", dataset_id="nama", slice_hash="s2", frequency="annual"))
    return out


def test_new_block_equals_old_query_for_every_country(monkeypatch):
    store = {}

    async def get(key):
        return store.get(key)

    async def put(key, value, ttl=None):
        store[key] = value

    async def vkey(ns, rest):
        return f"fe:{ns}:v1:{rest}"

    monkeypatch.setattr(seo_world, "cache_get", get)
    monkeypatch.setattr(seo_world, "cache_set", put)
    monkeypatch.setattr(seo_world, "versioned_key", vkey)

    async def scenario(maker):
        async with maker() as db:
            db.add_all(_seed())
            await db.commit()
        results = []
        async with maker() as db:
            inds = (await db.execute(select(WorldIndicator).where(WorldIndicator.slice_hash == "s1"))).scalars().all()
            for ind in inds:
                results.append((ind.country_id, await _old_peers(db, ind, ind.country_id),
                                await seo_world._same_series_peers(db, ind, ind.country_id)))
        return results

    results = _run_with_db(scenario)
    assert len(results) == 20
    for country_id, old, new in results:
        assert new == old, country_id
    assert len(store) == 1  # один список на срез для всех стран


def test_cached_list_skips_the_query():
    async def get(key):
        return [["c2", "Страна 02", "Country 2", "c2-gdp", 2], ["c1", "Страна 01", "Country 1", "c1-gdp", 1]]

    class NoDb:
        async def execute(self, *_a, **_k):
            raise AssertionError("при попадании в кэш запроса нет")

    import pytest

    mp = pytest.MonkeyPatch()
    try:
        mp.setattr(seo_world, "cache_get", get)

        async def vkey(ns, rest):
            return rest
        mp.setattr(seo_world, "versioned_key", vkey)
        ind = WorldIndicator(provider="eurostat", dataset_id="nama", slice_hash="s1", code="c1-gdp")
        peers = asyncio.run(seo_world._same_series_peers(NoDb(), ind, 1))
    finally:
        mp.undo()
    assert peers == [("c2", "Страна 02", "Country 2", "c2-gdp")]
