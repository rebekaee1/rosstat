"""Применение расчистки гипотез (14.11.2026): план по умолчанию, запись по флагу, идемпотентность, журнал."""
import asyncio
import csv
import importlib.util
import json
from datetime import datetime
from pathlib import Path

from sqlalchemy import select

from app.models import Hypothesis
import pytest

from app.services.hypotheses_triage import MERGE_SOURCE, OBSOLETE_SOURCE, apply_triage, read_decisions
from tests.test_analytics2 import _run_with_db

NOW = datetime(2026, 11, 15, 10, 0)


def _csv(tmp_path: Path, rows: list[dict]) -> Path:
    path = tmp_path / "решения.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "действие", "объединить_в", "запись_контекста", "обоснование", "гипотеза", "обновлена"])
        for r in rows:
            w.writerow([r["id"], r["action"], r.get("into", ""), r.get("ref", ""), r.get("reason", "причина"), "", ""])
    return path


async def _seed(maker):
    async with maker() as db:
        db.add_all([Hypothesis(id=i, statement=f"гипотеза {i}", confidence=0.5, created_at=NOW, updated_at=NOW)
                    for i in range(1, 8)])
        db.add(Hypothesis(id=9, statement="уже закрытая", verdict=True, created_at=NOW, updated_at=NOW))
        await db.commit()


ROWS = [
    {"id": 1, "action": "close_false", "ref": "[pulse-etl-count]", "reason": "артефакт обрезки до 20"},
    {"id": 2, "action": "close_true", "reason": "решено выпуском"},
    {"id": 3, "action": "merge", "into": 4, "reason": "дубль про графики"},
    {"id": 4, "action": "keep"},
    {"id": 5, "action": "merge", "into": 9, "reason": "ядро уже закрыто"},      # 19.11: вердикт ядра (true)
    {"id": 6, "action": "merge", "into": 3, "reason": "ядро само дубль"},      # пропуск: цепочка
    {"id": 9, "action": "close_false", "reason": "повтор"},                    # пропуск: уже закрыта
    {"id": 99, "action": "close_true", "reason": "нет такой"},                 # пропуск: нет гипотезы
]


def test_plan_by_default_does_not_touch_the_database(tmp_path):
    decisions = read_decisions(_csv(tmp_path, ROWS))

    async def scenario(maker):
        await _seed(maker)
        async with maker() as db:
            plan = await apply_triage(db, decisions, apply=False, now=NOW)
        async with maker() as db:
            open_rows = (await db.execute(select(Hypothesis).where(Hypothesis.verdict.is_(None)))).scalars().all()
        return plan, len(open_rows)

    plan, still_open = _run_with_db(scenario)
    assert [c["id"] for c in plan["changes"]] == [1, 2, 3, 5]
    assert sorted(s["id"] for s in plan["skipped"]) == [6, 9, 99]
    assert plan["kept"] == 1 and still_open == 7


def test_apply_writes_verdicts_marks_merges_and_is_idempotent(tmp_path):
    decisions = read_decisions(_csv(tmp_path, ROWS))

    async def scenario(maker):
        await _seed(maker)
        async with maker() as db:
            first = await apply_triage(db, decisions, apply=True, now=NOW)
        async with maker() as db:
            second = await apply_triage(db, decisions, apply=True, now=NOW)
        async with maker() as db:
            rows = {h.id: h for h in (await db.execute(select(Hypothesis))).scalars()}
        return first, second, rows

    first, second, rows = _run_with_db(scenario)
    assert len(first["changes"]) == 4 and second["changes"] == []
    assert rows[1].verdict is False and rows[1].rationale == "Расчистка 15.11: артефакт обрезки до 20 [pulse-etl-count]"
    assert rows[2].verdict is True
    assert rows[3].verdict is False and rows[3].source == MERGE_SOURCE
    assert rows[3].rationale.startswith("Объединена с #4") and rows[3].evidence_json["triage"]["merge_into"] == 4
    assert rows[5].verdict is True and rows[5].source == MERGE_SOURCE  # повтор подтверждённой — подтверждён
    assert rows[4].verdict is None and rows[6].verdict is None
    assert rows[9].rationale is None  # уже закрытая не тронута


def test_inventory_counts_merged_apart_from_refuted(tmp_path):
    from app.services.dataset_inventory import build_inventory

    decisions = read_decisions(_csv(tmp_path, ROWS))

    async def scenario(maker):
        await _seed(maker)
        async with maker() as db:
            await apply_triage(db, decisions, apply=True, now=NOW)
        async with maker() as db:
            return await build_inventory(db)

    inv = _run_with_db(scenario)
    sections = inv.get("sections", inv)
    assert sections["hypotheses"]["by_verdict"] == {"open": 3, "true": 2, "false": 1, "merged": 2}


def test_script_plans_by_default_and_journals_on_apply(tmp_path, monkeypatch, capsys):
    path = Path(__file__).resolve().parents[1] / "scripts/apply-hypotheses-triage.py"
    spec = importlib.util.spec_from_file_location("apply_triage_script", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    csv_path = _csv(tmp_path, ROWS)
    journal = tmp_path / "journal.jsonl"

    async def scenario(maker):
        monkeypatch.setattr("app.database.analytics_session", maker)
        await _seed(maker)
        await mod.main([str(csv_path)])
        planned = capsys.readouterr().out
        await mod.main([str(csv_path), "--apply", "--journal", str(journal)])
        applied = capsys.readouterr().out
        await mod.main([str(csv_path), "--apply", "--journal", str(journal)])
        again = capsys.readouterr().out
        return planned, applied, again

    planned, applied, again = _run_with_db(scenario)
    assert planned.startswith("ПЛАН") and "объединить 2" in planned
    assert applied.startswith("ПРИМЕНЕНО") and "журнал:" in applied
    assert "объединить 0" in again and "журнал:" not in again
    lines = [json.loads(x) for x in journal.read_text(encoding="utf-8").splitlines()]
    assert [x["id"] for x in lines] == [1, 2, 3, 5] and lines[0]["before"]["verdict"] is None


def _plan(tmp_path: Path, rows: list[dict]) -> Path:
    path = tmp_path / "hypotheses-plan.json"
    path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    return path


PLAN = [
    {"id": 1, "action": "close_true", "verdict": True, "keep_id": None, "rationale": "решено выпуском [table-period-jump]"},
    {"id": 2, "action": "close_duplicate", "verdict": True, "keep_id": 1, "rationale": "повтор [1]"},
    {"id": 3, "action": "close_duplicate", "verdict": False, "keep_id": 4, "rationale": "повтор открытой [4]"},
    {"id": 4, "action": "keep", "verdict": None, "keep_id": None, "rationale": "ждёт пункта 2"},
    {"id": 6, "action": "close_obsolete", "verdict": False, "keep_id": None, "rationale": "РСЯ отключена 29.09"},
]


def test_json_plan_closes_duplicates_with_core_verdict_and_marks_obsolete(tmp_path):
    from app.services.dataset_inventory import build_inventory

    decisions = read_decisions(_plan(tmp_path, PLAN))

    async def scenario(maker):
        await _seed(maker)
        async with maker() as db:
            result = await apply_triage(db, decisions, apply=True, now=datetime(2026, 11, 19, 12, 0))
        async with maker() as db:
            rows = {h.id: h for h in (await db.execute(select(Hypothesis))).scalars()}
            inv = await build_inventory(db)
        return result, rows, inv.get("sections", inv)

    result, rows, sections = _run_with_db(scenario)
    assert [c["id"] for c in result["changes"]] == [1, 2, 3, 6] and result["kept"] == 1
    assert rows[1].verdict is True and rows[1].rationale.startswith("Расчистка 19.11: решено выпуском")
    assert rows[2].verdict is True and rows[2].source == MERGE_SOURCE   # ядро закрыто этим же прогоном
    assert rows[3].verdict is False and rows[3].source == MERGE_SOURCE  # ядро осталось открытым
    assert rows[4].verdict is None
    assert rows[6].verdict is False and rows[6].source == OBSOLETE_SOURCE and rows[6].rationale.startswith("Устарела")
    assert sections["hypotheses"]["by_verdict"] == {"open": 3, "true": 2, "false": 0, "merged": 2, "obsolete": 1}


def test_json_plan_rejects_a_verdict_that_contradicts_the_action(tmp_path):
    with pytest.raises(ValueError):
        read_decisions(_plan(tmp_path, [{"id": 1, "action": "close_true", "verdict": False}]))
    with pytest.raises(ValueError):
        read_decisions(_plan(tmp_path, [{"id": 1, "action": "close_duplicate", "verdict": False, "keep_id": None}]))
