"""Разовый скрипт исправления предлога в сохранённых текстах мировых карточек (круг 13)."""
import asyncio
import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import select, text

from app.models import WorldCountry, WorldIndicator

DESC_FR = "Индекс цен в Франции: динамика с января 1996 по август 2026. Источник — Евростат."


def _load(auth_env, monkeypatch, tmp_path=None):
    spec = importlib.util.spec_from_file_location(
        "fix_country_prep", Path(__file__).resolve().parents[1] / "scripts" / "fix-world-country-prepositions.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "async_session", auth_env["session_maker"])
    bumped = []

    async def fake_bump():
        bumped.append(True)

    monkeypatch.setattr(module, "_bump", fake_bump)
    module.bumped = bumped
    module.backup = str(tmp_path / "backup.jsonl") if tmp_path else module.DEFAULT_BACKUP
    return module


def _seed(auth_env):
    async def go():
        async with auth_env["session_maker"]() as db:
            specs = [
                ("FR", "france", "Франция", "France", "Индекс цен в Франции"),
                ("CY", "cyprus", "Кипр", "Cyprus", "Безработица в Кипре"),
                ("MT", "malta", "Мальта", "Malta", "Население в Мальте"),
                ("DE", "germany", "Германия", "Germany", "Индекс цен в Германии"),
            ]
            for code, slug, ru, en, head in specs:
                country = WorldCountry(code=code, slug=slug, name_ru=ru, name_en=en, is_active=True)
                db.add(country)
                await db.flush()
                db.add(WorldIndicator(
                    country_id=country.id, code=f"{code.lower()}-x-1", dataset_id="x", slice_json={},
                    slice_hash=code, frequency="monthly", name_ru="Показатель", name_en=f"Indicator in {en}",
                    unit="I15", unit_ru="индекс", is_listed=True, points_count=2,
                    description=f"{head}: динамика с января 1996 по август 2026.",
                    seo_description=f"{head}: динамика с января 1996 по август 2026.",
                    seo_title=f"{head} — график и данные",
                    seo_keywords=f"Показатель, {ru}, {head}, {ru} статистика, график",
                    methodology="Источник данных — Евростат.",
                ))
            await db.commit()

    asyncio.run(go())


def _row(auth_env, code):
    async def go():
        async with auth_env["session_maker"]() as db:
            return (await db.execute(select(WorldIndicator).where(WorldIndicator.code == code))).scalar_one()

    return asyncio.run(go())


def test_rules_only_for_countries_where_phrase_differs():
    spec = importlib.util.spec_from_file_location(
        "fix_country_prep_rules", Path(__file__).resolve().parents[1] / "scripts" / "fix-world-country-prepositions.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    rules = module.country_rules([
        ("france", "Франция"), ("cyprus", "Кипр"), ("malta", "Мальта"), ("germany", "Германия"),
        ("poland", "Польша"), ("hungary", "Венгрия"),
    ])
    assert set(rules) == {"france", "cyprus", "malta"}
    pattern, good, _ = rules["france"]
    assert pattern.sub(good, DESC_FR).startswith("Индекс цен во Франции:")
    assert pattern.sub(good, "уже во Франции") == "уже во Франции"
    # часть слова не трогается
    assert pattern.sub(good, "ав Франции") == "ав Франции"


def test_dry_run_changes_nothing_apply_fixes_only_three_countries(auth_env, monkeypatch, tmp_path):
    mod = _load(auth_env, monkeypatch, tmp_path)
    _seed(auth_env)
    before = asyncio.run(mod.apply_fix(500, 0, apply=False, backup_file=mod.backup))
    assert before == {"france": 1, "cyprus": 1, "malta": 1}
    assert _row(auth_env, "fr-x-1").description.startswith("Индекс цен в Франции")
    assert mod.bumped == []

    after = asyncio.run(mod.apply_fix(2, 0, apply=True, backup_file=mod.backup))
    assert after == {"france": 0, "cyprus": 0, "malta": 0}
    fr, cy, mt, de = (_row(auth_env, c) for c in ("fr-x-1", "cy-x-1", "mt-x-1", "de-x-1"))
    assert fr.description.startswith("Индекс цен во Франции:")
    assert fr.seo_title == "Индекс цен во Франции — график и данные"
    assert "во Франции, Франция статистика" in fr.seo_keywords
    assert cy.description.startswith("Безработица на Кипре:")
    assert mt.seo_description.startswith("Население на Мальте:")
    # английское имя, методология и страна с обычным предлогом не тронуты
    assert fr.name_en == "Indicator in France"
    assert fr.methodology == "Источник данных — Евростат."
    assert de.description.startswith("Индекс цен в Германии:")
    assert mod.bumped == [True]

    # идемпотентность: повтор ничего не меняет и кэш не сбрасывает
    asyncio.run(mod.apply_fix(500, 0, apply=True, backup_file=mod.backup))
    assert mod.bumped == [True]
    assert _row(auth_env, "fr-x-1").description.startswith("Индекс цен во Франции:")
    # файл копий хранит прежние значения: по одной записи на ряд, повтор не дублирует
    lines = Path(mod.backup).read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 3 and all("в " in line for line in lines)


def test_rollback_restores_old_values_but_keeps_foreign_edits(auth_env, monkeypatch, tmp_path):
    mod = _load(auth_env, monkeypatch, tmp_path)
    _seed(auth_env)
    asyncio.run(mod.apply_fix(500, 0, apply=True, backup_file=mod.backup))

    async def edit():
        async with auth_env["session_maker"]() as db:
            await db.execute(text("UPDATE world_indicators SET seo_title = 'Новый заголовок' WHERE code = 'cy-x-1'"))
            await db.commit()

    asyncio.run(edit())
    assert asyncio.run(mod.rollback(500, 0, apply=False, backup_file=mod.backup)) == 3
    assert _row(auth_env, "fr-x-1").description.startswith("Индекс цен во Франции:")  # сухой откат не пишет
    assert asyncio.run(mod.rollback(500, 0, apply=True, backup_file=mod.backup)) == 3
    assert _row(auth_env, "fr-x-1").description.startswith("Индекс цен в Франции:")
    cy = _row(auth_env, "cy-x-1")
    assert cy.description.startswith("Безработица в Кипре:")
    assert cy.seo_title == "Новый заголовок"
    # повторный откат ничего не делает
    assert asyncio.run(mod.rollback(500, 0, apply=True, backup_file=mod.backup)) == 0
    # файла копий нет: откатывать нечего
    assert asyncio.run(mod.rollback(500, 0, apply=True, backup_file=str(tmp_path / "none.jsonl"))) == 0
