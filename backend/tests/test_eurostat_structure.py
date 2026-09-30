"""Автоматическая сверка смены структуры набора Eurostat (замена ручного карантина).

2026-09-24…28 Eurostat поменял структуру 21 набора (нефть, розница, бедность,
промышленность); по ADR-0011 они ушли в карантин без выхода — ~5,3 тыс.
публичных карточек застыли. Проверка на проде показала: ни один срез не пропал,
смена структуры — добавленные коды, расхождения значений — обычные пересмотры.
"""
from datetime import date

from app.services.eurostat_structure import (
    ExistingSlice,
    plan_structure_migration,
    series_match,
)


def _pts(values, start_year=2010):
    return [(date(start_year + i, 1, 1), float(v)) for i, v in enumerate(values)]


def _slice(**dims):
    return {"freq": "A", "unit": "PC", **dims}


def test_series_match_tolerates_revisions_not_different_series():
    base = _pts([100, 101, 102, 103, 104, 105, 106, 107, 108, 109])
    revised = _pts([100, 101, 102.05, 103, 104, 105, 106, 107, 108, 109.4])
    assert series_match(base, revised)
    rebased = _pts([v * 0.8 for v in range(100, 110)])
    assert not series_match(base, rebased)
    assert not series_match(base[:3], revised[:3]), "слишком короткое перекрытие"


def test_intact_slices_are_kept_and_revisions_accepted():
    s1 = _slice(nace="G47")
    existing = [ExistingSlice(1, "DE", s1, "h1", True)]
    new = {("DE", "h1"): (s1, _pts(range(10))), ("DE", "h_new"): (_slice(nace="G48"), _pts(range(10)))}
    verdict = plan_structure_migration(existing, new, old_points={})
    assert verdict.accept
    assert verdict.kept == 1 and not verdict.remapped and not verdict.orphans


def test_renamed_slice_is_remapped_by_matching_history():
    old = _slice(nace="G47_FOOD")
    renamed = _slice(nace="G47_F")
    other = _slice(nace="G47_NF")
    history = _pts([10, 11, 12, 13, 14, 15, 16, 17])
    existing = [ExistingSlice(7, "FR", old, "h_old", True)]
    new = {
        ("FR", "h_ren"): (renamed, history + [(date(2018, 1, 1), 18.0)]),
        ("FR", "h_oth"): (other, _pts([50, 51, 52, 53, 54, 55, 56, 57])),
    }
    verdict = plan_structure_migration(existing, new, old_points={7: history})
    assert verdict.accept
    assert verdict.remapped == {7: (renamed, "h_ren")}
    assert verdict.orphans == []


def test_added_dimension_remaps_every_card():
    """Новое измерение меняет slice_hash у всех срезов — карточки не должны
    ни задвоиться, ни потерять URL."""
    existing, new, old_points = [], {}, {}
    for i, geo in enumerate(("DE", "FR", "IT")):
        hist = _pts([100 + i, 101 + i, 102 + i, 103 + i, 104 + i, 105 + i])
        existing.append(ExistingSlice(i + 1, geo, _slice(nace="B"), "h_old", True))
        old_points[i + 1] = hist
        new[(geo, "h_new")] = (_slice(nace="B", s_adj="NSA"), hist)
    verdict = plan_structure_migration(existing, new, old_points=old_points)
    assert verdict.accept
    assert set(verdict.remapped) == {1, 2, 3}


def test_ambiguous_candidates_are_not_guessed():
    old = _slice(nace="X")
    hist = _pts([1, 2, 3, 4, 5, 6, 7])
    existing = [ExistingSlice(1, "DE", old, "h_old", False)]
    new = {
        ("DE", "a"): (_slice(nace="Y"), hist),
        ("DE", "b"): (_slice(nace="Z"), hist),
    }
    verdict = plan_structure_migration(existing, new, old_points={1: hist})
    assert verdict.remapped == {}
    assert verdict.orphans == [1]


def test_candidate_must_keep_frequency_and_be_unclaimed():
    hist = _pts([1, 2, 3, 4, 5, 6, 7])
    existing = [
        ExistingSlice(1, "DE", _slice(nace="X"), "h_old", True),
        ExistingSlice(2, "DE", _slice(nace="K"), "h_kept", True),
    ]
    new = {
        ("DE", "h_kept"): (_slice(nace="K"), hist),                  # занят карточкой 2
        ("DE", "q"): ({**_slice(nace="X2"), "freq": "Q"}, hist),     # другая частота
    }
    verdict = plan_structure_migration(existing, new, old_points={1: hist})
    assert verdict.remapped == {}
    assert verdict.orphans == [1]


def test_structural_break_keeps_quarantine_with_report():
    existing = [ExistingSlice(i, "DE", _slice(nace=f"N{i}"), f"h{i}", True) for i in range(1, 11)]
    new = {("DE", f"h{i}"): (_slice(nace=f"N{i}"), _pts(range(8))) for i in range(1, 6)}
    verdict = plan_structure_migration(existing, new, old_points={})
    assert not verdict.accept
    assert len(verdict.orphans) == 5
    assert "5" in verdict.reason


def test_few_discontinued_series_do_not_block_the_dataset():
    existing = [ExistingSlice(i, "DE", _slice(nace=f"N{i}"), f"h{i}", True) for i in range(1, 21)]
    new = {("DE", f"h{i}"): (_slice(nace=f"N{i}"), _pts(range(8))) for i in range(1, 20)}
    verdict = plan_structure_migration(existing, new, old_points={})
    assert verdict.accept
    assert verdict.orphans == [20]


# ---------------------------------------------------------------------------
# Loader: сверка по БД, переподключение, неизменный код карточки
# ---------------------------------------------------------------------------

def _load_loader():
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "scripts" / "load-world-eurostat.py"
    spec = importlib.util.spec_from_file_location("load_world_eurostat", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_loader_remaps_renamed_slice_and_keeps_card_url(tmp_path, monkeypatch):
    import asyncio

    from sqlalchemy import create_engine
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.models import Base, WorldCountry, WorldDataPoint, WorldIndicator
    from app.services.eurostat_parser import DatasetParseResult, slice_hash

    loader = _load_loader()
    async def publish(*namespaces):
        pass
    monkeypatch.setattr(loader, "bump_namespaces", publish)
    db_path = tmp_path / "world.db"
    sync_engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(sync_engine)
    sync_engine.dispose()

    old_slice = {"freq": "A", "unit": "PC", "nace_r2": "G47_FOOD"}
    new_slice = {"freq": "A", "unit": "PC", "nace_r2": "G47_F"}
    history = _pts([10, 11, 12, 13, 14, 15, 16, 17])

    async def scenario():
        engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
        maker = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with maker() as db:
                country = WorldCountry(code="DE", slug="germany", name_ru="Германия",
                                       name_en="Germany", region_ru="Европа")
                db.add(country)
                await db.flush()
                ind = WorldIndicator(
                    country_id=country.id, provider="eurostat", code="de-sts-old-card",
                    dataset_id="sts_x_m", slice_json=old_slice, slice_hash=slice_hash(old_slice),
                    name_ru="Розница", frequency="annual", is_listed=True,
                )
                db.add(ind)
                await db.flush()
                for d, v in history:
                    db.add(WorldDataPoint(indicator_id=ind.id, date=d, value=v))
                await db.commit()
                ind_id, country_id = ind.id, country.id

            result = DatasetParseResult(
                dataset_id="sts_x_m", title_en="Retail", frequency="annual",
                slice_=new_slice, slice_hash=slice_hash(new_slice), unit="PC",
                series_by_geo={"DE": history + [(date(2018, 1, 1), 18.0)]},
                source_url="https://example.invalid",
            )
            verdict = await loader.check_structure("sts_x_m", [result], session_factory=maker)
            assert verdict.accept
            assert verdict.remapped == {ind_id: (new_slice, slice_hash(new_slice))}
            await loader.apply_remaps(verdict, session_factory=maker)

            async with maker() as db:
                found, _created = await loader.upsert_indicator_meta(
                    db, country_id=country_id, country_code="DE", country_name_ru="Германия",
                    result=result, points=result.series_by_geo["DE"], country_slug="germany",
                )
                await db.commit()
                card = await db.get(WorldIndicator, found)
                return found, card.code, card.slice_hash
        finally:
            await engine.dispose()

    found, code, hash_ = asyncio.run(scenario())
    assert found == 1, "обновлена прежняя карточка, а не создан дубль"
    assert code == "de-sts-old-card", "URL карточки не меняется"
    assert hash_ == slice_hash(new_slice)
