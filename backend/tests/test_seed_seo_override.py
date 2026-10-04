"""F12: сид не затирает SEO-поля, правленные в БД вручную (ADR-0003, DB override).

Контракт — в docstring `_apply_seo_preserving_overrides`. Тесты идут на SQLite:
сам `_seed_full` использует pg_insert, поэтому проверяется именно writer-функция.
"""
import asyncio

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import seed_data
from app.models import Base, Indicator, SeedState


def _run(tmp_path, scenario):
    async def main():
        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'seo.db'}")
        maker = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            async with maker() as db:
                db.add(Indicator(code="cpi", name="ИПЦ"))
                db.add(Indicator(code="other", name="Другой", seo_keywords="ручные ключи"))
                await db.commit()
            return await scenario(maker)
        finally:
            await engine.dispose()
    return asyncio.run(main())


async def _apply(maker, desired, **kwargs):
    async with maker() as db:
        stats = await seed_data._apply_seo_preserving_overrides(db, desired, **kwargs)
        await db.commit()
    return stats


async def _row(maker, code="cpi"):
    async with maker() as db:
        return (await db.execute(select(Indicator).where(Indicator.code == code))).scalar_one()


V1 = {"cpi": {"seo_title": "Сид v1", "seo_description": "Описание v1",
              "seo_keywords": "ключи v1", "seo_blocks": [{"h": "блок v1"}]}}
V2 = {"cpi": {"seo_title": "Сид v2", "seo_description": "Описание v2",
              "seo_keywords": "ключи v2", "seo_blocks": [{"h": "блок v2"}]}}


def test_first_run_adopts_seed_then_updates_untouched_fields(tmp_path):
    async def scenario(maker):
        stats = await _apply(maker, V1)
        assert stats["written"] == 4 and stats["preserved"] == 0
        row = await _row(maker)
        assert (row.seo_title, row.seo_blocks) == ("Сид v1", [{"h": "блок v1"}])
        # Сид изменился, БД не правили — новое значение применяется.
        stats = await _apply(maker, V2)
        assert stats["preserved"] == 0
        row = await _row(maker)
        assert (row.seo_title, row.seo_keywords, row.seo_blocks) == ("Сид v2", "ключи v2", [{"h": "блок v2"}])
    _run(tmp_path, scenario)


def test_manual_db_edit_survives_a_later_seed_run(tmp_path):
    async def scenario(maker):
        await _apply(maker, V1)
        async with maker() as db:
            await db.execute(update(Indicator).where(Indicator.code == "cpi").values(
                seo_title="Правка админки", seo_blocks=[{"h": "ручной блок"}]))
            await db.commit()
        stats = await _apply(maker, V2)
        row = await _row(maker)
        # Правленные поля сохранены, остальные поля сид обновил.
        assert row.seo_title == "Правка админки"
        assert row.seo_blocks == [{"h": "ручной блок"}]
        assert (row.seo_description, row.seo_keywords) == ("Описание v2", "ключи v2")
        assert sorted(stats["preserved_codes"]) == ["cpi.seo_blocks", "cpi.seo_title"]
        # И при повторном (третьем) прогоне — тоже.
        await _apply(maker, V2)
        row = await _row(maker)
        assert (row.seo_title, row.seo_blocks) == ("Правка админки", [{"h": "ручной блок"}])
    _run(tmp_path, scenario)


def test_empty_db_field_is_filled_and_foreign_value_for_unwritten_field_is_kept(tmp_path):
    async def scenario(maker):
        await _apply(maker, V1)  # создаёт снимок
        # `other`: сид раньше не писал seo_keywords, в БД ручное значение — не трогаем.
        stats = await _apply(maker, {"other": {"seo_keywords": "ключи сида"}})
        assert (await _row(maker, "other")).seo_keywords == "ручные ключи"
        assert stats["preserved_codes"] == ["other.seo_keywords"]
        # Пустое поле заполняется.
        async with maker() as db:
            await db.execute(update(Indicator).where(Indicator.code == "other").values(seo_keywords=None))
            await db.commit()
        await _apply(maker, {"other": {"seo_keywords": "ключи сида"}})
        assert (await _row(maker, "other")).seo_keywords == "ключи сида"
    _run(tmp_path, scenario)


def test_force_resets_overrides_to_seed(tmp_path):
    async def scenario(maker):
        await _apply(maker, V1)
        async with maker() as db:
            await db.execute(update(Indicator).where(Indicator.code == "cpi").values(seo_title="Правка"))
            await db.commit()
        await _apply(maker, V2, force=True)
        assert (await _row(maker)).seo_title == "Сид v2"
        # После сброса поле снова принадлежит сиду.
        await _apply(maker, V1)
        assert (await _row(maker)).seo_title == "Сид v1"
    _run(tmp_path, scenario)


def test_snapshot_lives_in_seed_state_and_stores_only_fingerprints(tmp_path):
    async def scenario(maker):
        await _apply(maker, V1)
        async with maker() as db:
            raw = (await db.get(SeedState, seed_data._SEO_SNAPSHOT_KEY)).value
        assert "Сид v1" not in raw and "cpi" in raw
    _run(tmp_path, scenario)


def test_corrupt_snapshot_is_treated_as_first_run(tmp_path):
    async def scenario(maker):
        async with maker() as db:
            db.add(SeedState(key=seed_data._SEO_SNAPSHOT_KEY, value="{not json"))
            await db.commit()
        await _apply(maker, V1)
        assert (await _row(maker)).seo_title == "Сид v1"
    _run(tmp_path, scenario)
