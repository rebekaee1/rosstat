"""Поисковый индекс (ADR-0036, 18.11.2026): выдача та же, что по основным таблицам.

Индекс — копии столбцов, по которым поиск отбирает и сортирует, и заранее посчитанное условие «есть факт». Здесь
поиск идёт дважды по одной базе: без индекса (как до 18.11) и с собранным индексом; ответы должны совпасть целиком.
Отдельно сверяются сами отметки копий с прежними условиями факта и порядок «ранг 0–2, затем ранг 3» с одним запросом
«условия + факт + порядок + предел».
"""
import asyncio
import json
import random
from datetime import date

import pytest
from sqlalchemy import case, exists, or_, select, text

from tests.test_search_federated import search_client  # noqa: F401 — общая фикстура каталога поиска

QUERIES = (
    "cpi", "CPI USA", "cpi Germany", "инфляция США", "consumer price index", "уровень", "уровень безработицы",
    "Germany", "Moscow", "California", "Россия", "ключевая ставка", "курс доллара", "USD JPY", "бензин", "АИ-95",
    "население", "population", "зарплата", "Зарплата Москва", "численность студентов", "ВРП Москва",
    "цены на первичном рынке жилья", "IPCA", "IPCA 12-month", "annual rate of change", "brent", "биткоин",
    "экспорт", "импорт", "unemployment rate", "cpi 2024", "инфляция май 2024", "Germany 2024", "hicp", "index",
    "индекс", "уровень инновационной активности", "state population", "California population", "Japan",
)


async def _answers(session_maker, queries, locales=("ru", "en"), limit=50):
    from app.services.locale import set_locale
    from app.services.search import federated_search

    out = {}
    for locale in locales:
        set_locale(locale)
        for query in queries:
            async with session_maker() as db:
                out[f"{locale}|{query}"] = await federated_search(db, query, limit=limit)
    set_locale("ru")
    return json.loads(json.dumps(out, ensure_ascii=False, sort_keys=True, default=str))


async def _build(session_maker, parts=None):
    from app.services import search_index

    kwargs = {"parts": parts} if parts else {}
    reports = await search_index.refresh(force=True, session_maker=session_maker, release_after=0, **kwargs)
    search_index.reset_cache()
    return reports


@pytest.fixture(autouse=True)
def _fresh_index_state():
    from app.services import search_index

    search_index.reset_cache()
    yield
    search_index.reset_cache()


def test_answers_with_index_equal_live_tables(search_client, auth_env):
    maker = auth_env["session_maker"]

    async def run():
        before = await _answers(maker, QUERIES)
        reports = await _build(maker)
        assert [report["status"] for report in reports] == ["built"] * 3
        from app.services import search_index
        async with maker() as db:
            index = await search_index.active_index(db)
        assert index.world is not None and index.russia is not None and index.region_facts is not None
        after = await _answers(maker, QUERIES)
        return before, after

    before, after = asyncio.run(run())
    assert sum(1 for body in before.values() if body["results"]) >= 25, "фикстура должна давать непустые ответы"
    for key in before:
        assert after[key] == before[key], key


def test_index_flags_match_live_fact_conditions(search_client, auth_env):
    from app.models import (Indicator, IndicatorData, RegionDataPoint, RegionMonthlyPoint, SearchIndexState,
                            SubnationalDataPoint, WorldIndicator)
    from app.services import search_index
    from app.services.search import _finite, _world_fact

    class _NoPeriod:
        year = month = None

    maker = auth_env["session_maker"]

    async def run():
        await _build(maker)
        async with maker() as db:
            index = await search_index.active_index(db)
            world = {row.id: bool(row.fact) for row in (await db.execute(select(
                WorldIndicator.id, _world_fact(_NoPeriod()).label("fact")))).all()}
            copied = {row.id: bool(row.has_fact) for row in (await db.execute(select(index.world.c.id, index.world.c.has_fact))).all()}
            assert copied == world
            assert False in world.values() and True in world.values()
            # Номера строк копии — порядок выдачи (is_listed DESC, code): по всему каталогу и внутри страны, подряд с 1.
            live = (await db.execute(select(WorldIndicator.code, WorldIndicator.country_id).order_by(
                WorldIndicator.is_listed.desc(), WorldIndicator.code))).all()
            numbered = (await db.execute(select(index.world.c.code, index.world.c.ord, index.world.c.country_id,
                index.world.c.country_ord).order_by(index.world.c.ord))).all()
            assert [row.code for row in numbered] == [row.code for row in live]
            assert [row.ord for row in numbered] == list(range(1, len(live) + 1))
            for country_id in {row.country_id for row in live}:
                assert [row.country_ord for row in numbered if row.country_id == country_id] == list(
                    range(1, sum(1 for row in live if row.country_id == country_id) + 1))

            russia = {row.id: bool(row.fact) for row in (await db.execute(select(Indicator.id, exists(select(1).where(
                IndicatorData.indicator_id == Indicator.id, _finite(IndicatorData.value))).label("fact")).where(
                Indicator.is_active.is_(True)))).all()}
            assert {row.id: bool(row.has_fact) for row in (await db.execute(select(index.russia.c.id, index.russia.c.has_fact))).all()} == russia

            annual = {(row.indicator_id, row.region_id) for row in (await db.execute(select(
                RegionDataPoint.indicator_id, RegionDataPoint.region_id).where(_finite(RegionDataPoint.value)))).all()}
            monthly = {(row.indicator_id, row.region_id) for row in (await db.execute(select(
                RegionMonthlyPoint.indicator_id, RegionMonthlyPoint.region_id).where(_finite(RegionMonthlyPoint.value)))).all()}
            facts = {(row.indicator_id, row.region_id): (bool(row.has_annual), bool(row.has_monthly)) for row in
                     (await db.execute(select(index.region_facts))).all()}
            assert facts == {pair: (pair in annual, pair in monthly) for pair in annual | monthly}
            sub = {(row.indicator_id, row.region_id) for row in (await db.execute(select(
                SubnationalDataPoint.indicator_id, SubnationalDataPoint.region_id).where(_finite(SubnationalDataPoint.value)))).all()}
            assert {(row.indicator_id, row.region_id) for row in (await db.execute(select(index.subnational_facts))).all()} == sub
            states = {row.part: row for row in (await db.execute(select(SearchIndexState))).scalars()}
            assert set(states) == {"world", "russia", "territory"} and all(row.rows for row in states.values())

    asyncio.run(run())


def test_regional_last_values_from_index_equal_live(search_client, auth_env):
    from app.models import Region, RegionDataPoint, RegionIndicator, RegionMonthlyPoint
    from app.services import search_index
    from app.services.search_regional_groups import _latest_by_region

    maker = auth_env["session_maker"]

    async def run():
        async with maker() as db:
            # Несколько точек на пару, нулевые и поздние нечисловые нет: последняя конечная — по периоду.
            moscow = (await db.execute(select(Region).where(Region.slug == "moskva"))).scalar_one()
            primorye = (await db.execute(select(Region).where(Region.slug == "primorskiy-kray"))).scalar_one()
            wages = (await db.execute(select(RegionIndicator).where(RegionIndicator.code == "monthly-wages"))).scalar_one()
            students = (await db.execute(select(RegionIndicator).where(RegionIndicator.code == "students"))).scalar_one()
            db.add_all([RegionMonthlyPoint(indicator_id=wages.id, region_id=moscow.id, month=202312, value=90),
                        RegionMonthlyPoint(indicator_id=wages.id, region_id=primorye.id, month=202401, value=70.5),
                        RegionDataPoint(indicator_id=students.id, region_id=moscow.id, year=2020, value=80),
                        RegionDataPoint(indicator_id=students.id, region_id=primorye.id, year=2023, value=0)])
            await db.commit()
        cases = [(code, monthly, slugs) for code in ("monthly-wages", "students", "population", "ceni-ai95", "absent")
                 for monthly in (False, True) for slugs in (None, ("moskva",), ("primorskiy-kray", "ghost-region"))]
        async with maker() as db:
            live = [await _latest_by_region(db, code, monthly=monthly, slugs=slugs) for code, monthly, slugs in cases]
        await _build(maker, parts=("territory",))
        async with maker() as db:
            assert (await search_index.active_index(db)).region_facts is not None
            indexed = [await _latest_by_region(db, code, monthly=monthly, slugs=slugs) for code, monthly, slugs in cases]
        return live, indexed

    live, indexed = asyncio.run(run())
    assert any(live) and indexed == live


def test_rebuild_switches_copy_and_releases_previous(search_client, auth_env):
    from app.models import SearchWorldRowA, SearchWorldRowB
    from app.services import search_index

    maker = auth_env["session_maker"]

    async def run():
        first = await _build(maker, parts=("world",))
        second = await _build(maker, parts=("world",))
        async with maker() as db:
            count_a = (await db.execute(text("SELECT count(*) FROM search_world_a"))).scalar()
            count_b = (await db.execute(text("SELECT count(*) FROM search_world_b"))).scalar()
            index = await search_index.active_index(db)
        return first[0], second[0], count_a, count_b, index

    first, second, count_a, count_b, index = asyncio.run(run())
    assert (first["active"], second["active"], second["previous"]) == ("a", "b", "a")
    # Прежняя копия очищена, действующая полна.
    assert count_a == 0 and count_b > 0
    assert index.world is SearchWorldRowB.__table__ and index.world is not SearchWorldRowA.__table__


def test_disabled_flag_and_missing_state_read_live_tables(search_client, auth_env, monkeypatch):
    from app.config import settings
    from app.services import search_index

    maker = auth_env["session_maker"]

    async def run():
        await _build(maker)
        monkeypatch.setattr(settings, "search_index_enabled", False)
        search_index.reset_cache()
        async with maker() as db:
            assert await search_index.active_index(db) == search_index.EMPTY
        monkeypatch.setattr(settings, "search_index_enabled", True)
        async with maker() as db:
            await db.execute(text("DROP TABLE search_index_state"))
            await db.commit()
        search_index.reset_cache()
        async with maker() as db:
            index = await search_index.active_index(db)
            # Чтение указателя не испортило транзакцию: следующий запрос в той же сессии идёт.
            assert (await db.execute(text("SELECT 1"))).scalar() == 1
        return index, await _answers(maker, ("cpi", "Moscow"), locales=("ru",))

    index, answers = asyncio.run(run())
    assert index == search_index.EMPTY
    assert answers["ru|cpi"]["results"] and answers["ru|Moscow"]["results"]


def test_unchanged_sources_are_not_rebuilt_without_force(search_client, auth_env, monkeypatch):
    """Без `force` сборка ждёт `search_index_min_interval_minutes` (SQLite не ведёт счётчиков изменений)."""
    from app.config import settings
    from app.services import search_index

    maker = auth_env["session_maker"]
    monkeypatch.setattr(settings, "search_index_min_interval_minutes", 60)

    async def run():
        await _build(maker, parts=("russia",))
        return await search_index.refresh(("russia",), session_maker=maker, release_after=0)

    assert [report["status"] for report in asyncio.run(run())] == ["deferred"]


# --- Случайный каталог: ранг 0–2, проход кусками и остаток дают тот же итог, что один запрос «факт + порядок + предел» --

_WORDS = ("уровень", "индекс", "цена", "level", "index", "price", "коэффициент", "rate", "доля", "share")


def _random_catalogue(rng: random.Random, countries):
    from app.models import WorldIndicator

    rows, codes = [], set()
    for number in range(400):
        name = " ".join(rng.sample(_WORDS, rng.randint(1, 3)))
        if rng.random() < 0.05:
            name = rng.choice(_WORDS)  # название целиком совпадает со словом — ранг 1
        country = rng.choice(countries)
        code = f"{country.code.lower()}-{rng.choice(_WORDS)}-{number:04d}"
        if rng.random() < 0.03 and code.split("-")[1] not in codes:
            code = code.split("-")[1]  # код целиком совпадает со словом — ранг 0
        codes.add(code)
        rows.append(WorldIndicator(country_id=country.id, code=code, name_ru=name,
                                   name_en=name if rng.random() < 0.7 else None, dataset_id=f"ds-{number % 17}",
                                   slice_hash=f"h{number}", unit="PC", unit_ru="%", category_ru="Fixture",
                                   frequency=rng.choice(("monthly", "annual", "quarterly")),
                                   is_listed=rng.random() < 0.7, points_count=rng.randint(0, 5), provider="national"))
    return rows


@pytest.mark.parametrize("walk", [(8, 64), (16, 24), (2048, 32768)])
def test_index_walk_equals_single_ordered_query_on_random_catalogues(auth_env, monkeypatch, walk):
    from app.models import WorldCountry, WorldDataPoint, WorldIndicator
    from app.services import search, search_index
    from app.services.search import _world_fact, _world_top_from_index, _world_top_with_facts

    class _NoPeriod:
        year = month = None

    monkeypatch.setattr(search, "_WORLD_WALK_FIRST", walk[0])
    monkeypatch.setattr(search, "_WORLD_WALK_MAX", walk[1])
    maker = auth_env["session_maker"]
    trials = 100
    shapes = [random.Random(trial).random() for trial in range(trials)]
    preferred = [random.Random(1000 + trial).choice(_WORDS) for trial in range(trials)]

    async def run():
        rng = random.Random(20261118)
        async with maker() as db:
            countries = [WorldCountry(code=code, slug=f"c-{code.lower()}", name_ru=code, name_en=code)
                         for code in ("AA", "BB", "CC")]
            db.add_all(countries)
            await db.flush()
            rows = _random_catalogue(rng, countries)
            db.add_all(rows)
            await db.flush()
            for row in rows:
                roll = rng.random()
                if roll < 0.6:
                    db.add(WorldDataPoint(indicator_id=row.id, date=date(2024, 1, 1), value=rng.choice((1, 2.5, -3))))
                elif roll < 0.75:
                    db.add(WorldDataPoint(indicator_id=row.id, date=date(2024, 1, 1), value=0))
            await db.commit()
        await _build(maker, parts=("world",))
        checked = 0
        async with maker() as db:
            copy = (await search_index.active_index(db)).world
            for trial in range(trials):
                word = rng.choice(_WORDS)
                need = rng.choice((1, 3, 7, 20, 60, 500))
                chosen = rng.sample(countries, rng.randint(1, 3))
                country_ids = [country.id for country in chosen]

                def where_lists(entity):
                    shape = shapes[trial]
                    term = (entity.name_ru.like(f"%{word}%") if shape < 0.6 else
                            entity.frequency.in_(("monthly", "annual")) if shape < 0.9 else entity.code.like("%zz%"))
                    return [[entity.country_id.in_(country_ids), term]]

                def conditions(entity):
                    return (entity.code.ilike(word), entity.code.ilike(word), entity.name_ru.ilike(word),
                            entity.name_en.ilike(word), entity.code.like(f"%-{preferred[trial]}-%"))

                def rank_for(entity):
                    found = conditions(entity)
                    return case(*zip(found, (0, 0, 1, 1, 2)), else_=3), or_(*found)

                live_rank, _hit = rank_for(WorldIndicator)
                statement = select(WorldIndicator.id, live_rank.label("fe_rank")).where(
                    *where_lists(WorldIndicator)[0]).order_by(live_rank, WorldIndicator.is_listed.desc(), WorldIndicator.code)
                live = await _world_top_with_facts(db, statement, _NoPeriod(), (WorldIndicator.id, WorldIndicator.code,
                    WorldIndicator.is_listed), need, {}, postgres=False)
                indexed = await _world_top_from_index(db, copy, where_lists, rank_for,
                    lambda entity: (entity.id, entity.code, entity.is_listed), need,
                    country_id=country_ids[0] if len(country_ids) == 1 else None, postgres=False)
                # Образец — один запрос «факт + порядок + предел» по основной таблице.
                reference = (await db.execute(select(WorldIndicator.id, live_rank).where(*where_lists(WorldIndicator)[0],
                    _world_fact(_NoPeriod())).order_by(live_rank, WorldIndicator.is_listed.desc(), WorldIndicator.code)
                    .limit(need))).all()
                expected = [(int(rank), row_id) for row_id, rank in reference]
                assert [(rank, row.id) for rank, row in live] == expected
                assert [(rank, row.id) for rank, row in indexed] == expected, (word, need, country_ids)
                checked += bool(expected)
        return checked

    assert asyncio.run(run()) > 50
