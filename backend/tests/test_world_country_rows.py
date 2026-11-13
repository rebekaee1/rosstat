"""Узкое чтение рядов страны (`world_country_rows`): тот же ответ, что при чтении всей страны.

Карточка ряда и сравнение стран раньше читали все ряды страны (`_country_indicators`); теперь — только ряды из
наборов данных, которые могут участвовать в расчёте. Тесты сверяют оба способа на одной базе.
"""
from __future__ import annotations

import asyncio
from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.api.world as world
from app.data.world_concept_national import national_codes_for_concept
from app.data.world_concepts import CONCEPT_BY_SLUG, concept_dataset_allowed
from app.models import Base, WorldCountry, WorldDataPoint, WorldIndicator
from app.services import world_country_rows as rows_mod
from app.services.world_country_rows import (
    card_country_indicators,
    card_dataset_pairs,
    compare_country_indicators,
    compare_dataset_pairs,
    country_dataset_directory,
    country_indicators_for_datasets,
)


class _Ind:
    def __init__(self, provider: str, dataset_id: str):
        self.provider = provider
        self.dataset_id = dataset_id


_DIRECTORY = [
    ("eurostat", "une_rt_m"), ("eurostat", "une_rt_q"), ("eurostat", "une_rt_a"),
    ("eurostat", "une_rt_m_h"), ("eurostat", "une_rtx_m"), ("eurostat", "sts_inpr_m"),
    ("eurostat", "prc_hpi_q"), ("eurostat", "prc_hpi_a"), ("eurostat", "ei_hppi_q"),
    ("eurostat", "prc_hpi_ooq"), ("eurostat", "prc_hpi_ooa"),
    ("eurostat", "prc_hicp_midx"), ("eurostat", "prc_hicp_manr"), ("eurostat", "prc_hicp_minr"),
    ("eurostat", "tec00027"), ("eurostat", "prc_hicp_cind"),
    ("ons", "une_rt_m"), ("Eurostat ", "une_rt_q"),
    ("boj", "FM01"), ("boj", "fm01_m"), ("boj", "FM02"),
]


def _selected(provider: str, dataset_id: str) -> set[tuple[str, str]]:
    return set(card_dataset_pairs(_Ind(provider, dataset_id), _DIRECTORY))


def test_card_pairs_take_frequency_siblings_of_same_provider_only():
    assert _selected("eurostat", "une_rt_m") == {
        ("eurostat", "une_rt_m"), ("eurostat", "une_rt_q"), ("eurostat", "une_rt_a"),
        # Провайдер приводится как в ключе слияния каталога: регистр и пробелы не разводят ряды.
        ("Eurostat ", "une_rt_q"),
    }
    # Тот же набор другого ведомства — другая карточка.
    assert _selected("ons", "une_rt_m") == {("ons", "une_rt_m")}


def test_card_pairs_follow_glued_frequency_and_alias_groups():
    # Частота, приклеенная без «_»: квартальный и годовой набор — одна карточка каталога.
    assert _selected("eurostat", "prc_hpi_ooq") == {("eurostat", "prc_hpi_ooq"), ("eurostat", "prc_hpi_ooa")}
    # Группа срезов: основной индекс цен на жильё и быстрая оценка.
    assert _selected("eurostat", "prc_hpi_q") == {
        ("eurostat", "prc_hpi_q"), ("eurostat", "prc_hpi_a"), ("eurostat", "ei_hppi_q"),
    }
    # Слияние каталога: индекс ГИПЦ и его темпы; cind — другой показатель.
    assert _selected("eurostat", "prc_hicp_manr") == {
        ("eurostat", "prc_hicp_midx"), ("eurostat", "prc_hicp_manr"), ("eurostat", "prc_hicp_minr"),
        ("eurostat", "tec00027"),
    }


def test_card_pairs_ignore_dataset_case():
    assert _selected("boj", "FM01") == {("boj", "FM01"), ("boj", "fm01_m")}


def test_compare_pairs_follow_concept_datasets_per_provider():
    concept = CONCEPT_BY_SLUG["unemployment-rate"]
    directory = [("eurostat", "une_rt_m"), ("eurostat", "UNE_RT_M"), ("eurostat", "une_rt_q"),
                 ("imf", "WEO"), ("ons", "une_rt_m"), ("eurostat", "weo")]
    assert compare_dataset_pairs(concept, directory) == [
        ("eurostat", "une_rt_m"), ("eurostat", "UNE_RT_M"), ("imf", "WEO"),
    ]
    assert concept_dataset_allowed(concept, "IMF", "Weo") is True
    assert concept_dataset_allowed(concept, None, "une_rt_m") is False


# --- сверка на базе -------------------------------------------------------------------------------------------------

_END = date(2026, 9, 1)


def _row(country_id: int, n: int, dataset_id: str, frequency: str, points: int, *, provider: str = "eurostat",
         unit: str = "PC_ACT", unit_ru: str = "% ЭАН", slice_json: dict | None = None, listed: bool = False,
         quality: str = "curated", code: str | None = None, end: date = _END) -> WorldIndicator:
    return WorldIndicator(
        country_id=country_id, provider=provider, code=code or f"c{country_id}-{n}", dataset_id=dataset_id,
        slice_hash=f"h{n}", slice_json=slice_json or {}, name_ru=f"Показатель {n}", name_quality=quality,
        unit=unit, unit_ru=unit_ru, frequency=frequency, history_start=date(2000, 1, 1), history_end=end,
        points_count=points, is_listed=listed,
    )


def _country_rows(cid: int) -> list[WorldIndicator]:
    total = {"age": "TOTAL", "sex": "T", "s_adj": "SA"}
    cp00 = {"coicop": "CP00"}
    rows = [
        # Безработица: три частоты, срез по полу, другая мера, ряд без сверенного названия.
        _row(cid, 1, "une_rt_m", "monthly", 300, slice_json=total, listed=True),
        _row(cid, 2, "une_rt_m", "monthly", 300, slice_json={**total, "sex": "F"}, listed=True),
        _row(cid, 3, "une_rt_q", "quarterly", 100, slice_json=total),
        _row(cid, 4, "une_rt_a", "annual", 30, slice_json=total),
        _row(cid, 5, "une_rt_a", "annual", 30, slice_json=total, unit="THS_PER", unit_ru="тысяч человек", listed=True),
        _row(cid, 6, "une_rt_m", "monthly", 280, slice_json={**total, "age": "Y_LT25"}, quality="raw"),
        # Два ряда одной карточки с равной глубиной: первичный выбирается порядком строк.
        _row(cid, 7, "une_rt_m", "monthly", 300, slice_json={**total, "s_adj": "NSA"}),
        # ГИПЦ: слитая карточка индекса и темпов, отдельный срез корзины.
        _row(cid, 10, "prc_hicp_midx", "monthly", 350, slice_json=cp00, unit="I15", unit_ru="индекс 2015=100"),
        _row(cid, 11, "prc_hicp_minr", "monthly", 120, slice_json={"coicop18": "TOTAL"}, unit="I25",
             unit_ru="индекс 2025=100", listed=True),
        _row(cid, 12, "prc_hicp_manr", "monthly", 340, slice_json=cp00, unit="RCH_A", unit_ru="темп изменения, %"),
        _row(cid, 13, "prc_hicp_aind", "annual", 30, slice_json=cp00, unit="INX_A_AVG", unit_ru="индекс 2015=100"),
        _row(cid, 14, "prc_hicp_midx", "monthly", 350, slice_json={"coicop": "CP01"}, unit="I15",
             unit_ru="индекс 2015=100", listed=True),
        _row(cid, 15, "tec00027", "annual", 12, slice_json=cp00, unit="RCH_A_AVG", unit_ru="темп изменения, %"),
        # Жильё: основной набор, быстрая оценка, приклеенная частота.
        _row(cid, 20, "prc_hpi_q", "quarterly", 80, slice_json={"purchase": "TOTAL"}, unit="I15_Q",
             unit_ru="индекс 2015=100", listed=True),
        _row(cid, 21, "prc_hpi_a", "annual", 20, slice_json={"purchase": "TOTAL"}, unit="I15_A_AVG",
             unit_ru="индекс 2015=100"),
        _row(cid, 22, "ei_hppi_q", "quarterly", 60, slice_json={"indic": "TOTAL"}, unit="I15_Q",
             unit_ru="индекс 2015=100", listed=True),
        _row(cid, 23, "prc_hpi_q", "quarterly", 80, slice_json={"purchase": "DW_NEW"}, unit="I15_Q",
             unit_ru="индекс 2015=100", listed=True),
        _row(cid, 24, "prc_hpi_ooq", "quarterly", 70, slice_json={"expend": "TOTAL"}, unit="I15_Q",
             unit_ru="индекс 2015=100", listed=True),
        _row(cid, 25, "prc_hpi_ooa", "annual", 18, slice_json={"expend": "TOTAL"}, unit="I15_A_AVG",
             unit_ru="индекс 2015=100"),
        # Другие ведомства: тот же набор, верхний регистр набора, МВФ.
        _row(cid, 30, "une_rt_m", "monthly", 200, provider="ons", slice_json=total, listed=True),
        _row(cid, 31, "FM01", "monthly", 400, provider="boj", unit="PC", unit_ru="%", listed=True),
        _row(cid, 32, "fm01_m", "monthly", 90, provider="boj", unit="PC", unit_ru="%"),
        _row(cid, 33, "WEO", "annual", 45, provider="imf", slice_json={"weo_code": "LUR"}, listed=True),
        _row(cid, 34, "WEO", "annual", 45, provider="imf", slice_json={"weo_code": "LP"}, unit="NR",
             unit_ru="человек", listed=True),
    ]
    # Остальная страна: наборы, которые ни одной из карточек выше не нужны.
    rows += [
        _row(cid, 100 + n, f"sts_inpr{n}_m", "monthly", 250, slice_json={"nace_r2": f"C{n}"}, unit="I21",
             unit_ru="индекс 2021=100", listed=True)
        for n in range(40)
    ]
    return rows


async def _seed(maker) -> dict[str, int]:
    async with maker() as db:
        es = WorldCountry(code="ES", slug="spain", name_ru="Испания", name_en="Spain", sort_order=1)
        fr = WorldCountry(code="FR", slug="france", name_ru="Франция", name_en="France", sort_order=2)
        db.add_all([es, fr])
        await db.flush()
        rows = _country_rows(es.id) + _country_rows(fr.id)
        db.add_all(rows)
        await db.flush()
        # Ненулевые точки: без них ряд не попадает в переключатель срезов.
        for row in rows:
            db.add(WorldDataPoint(indicator_id=row.id, date=date(2026, 8, 1), value=5.0))
            db.add(WorldDataPoint(indicator_id=row.id, date=date(2026, 9, 1), value=6.0))
        await db.commit()
        return {"es": es.id, "fr": fr.id}


def _run(tmp_path, scenario):
    async def main():
        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'rows.db'}")
        maker = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            ids = await _seed(maker)
            return await scenario(maker, ids)
        finally:
            await engine.dispose()

    return asyncio.run(main())


async def _full(db, country_id: int) -> list[WorldIndicator]:
    return list(
        (
            await db.execute(
                select(WorldIndicator).where(WorldIndicator.country_id == country_id).order_by(WorldIndicator.id)
            )
        ).scalars().all()
    )


def _context_view(primary, by_freq) -> tuple:
    return primary.code, {freq: member.code for freq, member in sorted(by_freq.items())}


@pytest.fixture
def _no_world_cache(monkeypatch: pytest.MonkeyPatch):
    async def miss(key):
        return None

    async def skip(key, value, ttl=None):
        return None

    async def plain_key(namespace, key):
        return key

    monkeypatch.setattr(world, "cache_get", miss)
    monkeypatch.setattr(world, "cache_set", skip)
    monkeypatch.setattr(world, "versioned_key", plain_key)


def test_directory_lists_each_pair_once_and_only_for_the_country(tmp_path):
    async def scenario(maker, ids):
        async with maker() as db:
            directory = await country_dataset_directory(db, ids["es"])
            full = await _full(db, ids["es"])
            assert len(directory) == len(set(directory))
            assert set(directory) == {(row.provider, row.dataset_id) for row in full}

    _run(tmp_path, scenario)


def test_rows_for_datasets_are_exact_pairs_in_id_order(tmp_path):
    async def scenario(maker, ids):
        async with maker() as db:
            rows = await country_indicators_for_datasets(
                db, ids["es"], [("eurostat", "une_rt_m"), ("boj", "FM01")], codes=[f"c{ids['es']}-33"],
            )
            assert [row.id for row in rows] == sorted(row.id for row in rows)
            assert {row.country_id for row in rows} == {ids["es"]}
            # Пары не перемножаются: набор une_rt_m у ons не запрошен.
            assert {(row.provider, row.dataset_id) for row in rows} == {
                ("eurostat", "une_rt_m"), ("boj", "FM01"), ("imf", "WEO"),
            }
            assert sum(1 for row in rows if row.provider == "imf") == 1
            assert await country_indicators_for_datasets(db, ids["es"], []) == []

    _run(tmp_path, scenario)


def test_card_context_matches_full_country_read_for_every_row(tmp_path, monkeypatch):
    async def scenario(maker, ids):
        async with maker() as db:
            country = await db.get(WorldCountry, ids["es"])
            full = await _full(db, ids["es"])
            assert len(full) == 64
            narrowed = 0
            for ind in full:
                primary, by_freq, card_rows = await world._card_context(db, country, ind)
                narrow_view = _context_view(primary, by_freq)
                assert {row.country_id for row in card_rows} == {ids["es"]}
                narrowed += len(card_rows) < len(full)

                async def whole_country(_db, _ind):
                    return full

                with monkeypatch.context() as patch:
                    patch.setattr(world, "card_country_indicators", whole_country)
                    old_primary, old_by_freq, _ = await world._card_context(db, country, ind)
                assert narrow_view == _context_view(old_primary, old_by_freq), ind.code
            assert narrowed == len(full)

    _run(tmp_path, scenario)


def test_card_context_keeps_merged_frequencies_and_primary(tmp_path):
    async def scenario(maker, ids):
        async with maker() as db:
            country = await db.get(WorldCountry, ids["es"])
            by_code = {row.code: row for row in await _full(db, ids["es"])}
            c = f"c{ids['es']}-"
            # Скрытая годовая частота открывается через первичный месячный ряд.
            primary, by_freq, _rows = await world._card_context(db, country, by_code[c + "4"])
            assert primary.code == c + "1"
            assert {freq: member.code for freq, member in by_freq.items()} == {
                "monthly": c + "1", "quarterly": c + "3", "annual": c + "4",
            }
            # Слитая карточка ГИПЦ: годовой режим приходит из другого набора той же группы.
            _primary, by_freq, _rows = await world._card_context(db, country, by_code[c + "11"])
            assert by_freq["monthly"].code == c + "11"
            assert by_freq["annual"].code == c + "13"
            # Приклеенная частота: годовой набор prc_hpi_ooa дополняет квартальный prc_hpi_ooq.
            _primary, by_freq, _rows = await world._card_context(db, country, by_code[c + "24"])
            assert {freq: member.code for freq, member in by_freq.items()} == {
                "quarterly": c + "24", "annual": c + "25",
            }

    _run(tmp_path, scenario)


def test_indicator_meta_payload_matches_full_country_read(tmp_path, monkeypatch, _no_world_cache):
    async def scenario(maker, ids):
        async with maker() as db:
            full = await _full(db, ids["es"])
            checked_variants = 0
            for ind in full[:24]:
                narrow = await world.indicator_meta("spain", ind.code, db)

                async def whole_country(_db, _ind):
                    return full

                with monkeypatch.context() as patch:
                    patch.setattr(world, "card_country_indicators", whole_country)
                    old = await world.indicator_meta("spain", ind.code, db)
                assert narrow == old, ind.code
                checked_variants += bool(narrow.get("variants"))
            # Переключатель срезов действительно собирается (иначе сверка вариантов пуста).
            assert checked_variants >= 4

    _run(tmp_path, scenario)


def test_compare_series_matches_full_country_read(tmp_path, monkeypatch, _no_world_cache):
    async def scenario(maker, ids):
        async with maker() as db:
            full = await _full(db, ids["es"])
            found = 0
            for concept in world._compare_concepts():
                codes = national_codes_for_concept(concept.slug)
                old_pick = world._choose_compare_indicator(full, concept, codes)
                rows = await compare_country_indicators(db, ids["es"], concept, codes)
                new_pick = world._choose_compare_indicator(rows, concept, codes)
                assert (old_pick.code if old_pick else None) == (new_pick.code if new_pick else None), concept.slug
                assert len(rows) < len(full)
                if old_pick is None:
                    continue
                found += 1
                payload = await world.world_compare_series("spain", concept.slug, None, db)
                assert payload["meta"]["indicator_code"] == old_pick.code
            assert found >= 2
            unemployment = await world.world_compare_series("spain", "unemployment-rate", None, db)
            assert unemployment["meta"]["indicator_code"] == f"c{ids['es']}-1"

    _run(tmp_path, scenario)


def test_card_and_compare_do_not_read_the_whole_country(tmp_path, monkeypatch, _no_world_cache):
    async def scenario(maker, ids):
        async def forbidden(db, country_id):
            raise AssertionError("полное чтение страны")

        monkeypatch.setattr(world, "_country_indicators", forbidden)
        async with maker() as db:
            code = f"c{ids['es']}-1"
            assert (await world.indicator_meta("spain", code, db))["primary_code"] == code
            assert (await world.indicator_data("spain", code, "level", False, None, None, db))["points"]
            assert (await world.world_compare_series("spain", "unemployment-rate", None, db))["data"]

    _run(tmp_path, scenario)


def test_card_rows_read_only_selected_datasets(tmp_path, monkeypatch):
    async def scenario(maker, ids):
        seen: list[list[tuple[str, str]]] = []
        original = rows_mod.country_indicators_for_datasets

        async def spy(db, country_id, pairs, *, codes=()):
            seen.append(sorted(pairs))
            return await original(db, country_id, pairs, codes=codes)

        monkeypatch.setattr(rows_mod, "country_indicators_for_datasets", spy)
        async with maker() as db:
            ind = (
                await db.execute(select(WorldIndicator).where(WorldIndicator.code == f"c{ids['es']}-1"))
            ).scalar_one()
            rows = await card_country_indicators(db, ind)
            assert seen == [[("eurostat", "une_rt_a"), ("eurostat", "une_rt_m"), ("eurostat", "une_rt_q")]]
            assert sorted(row.code for row in rows) == sorted(f"c{ids['es']}-{n}" for n in (1, 2, 3, 4, 5, 6, 7))

    _run(tmp_path, scenario)
