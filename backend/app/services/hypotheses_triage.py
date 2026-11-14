"""Применение расчистки гипотез Пульса (14.11.2026) — по таблице решений сухого прогона.

Вход — `решения.csv` из `.artifacts/pulse-hypotheses-triage-2026-11-14/` (колонки id, действие, объединить_в,
запись_контекста, обоснование). Действия:

* close_true / close_false — вердикт true / false, обоснование «Расчистка ДД.ММ: … [запись]»;
* merge — дубль закрывается со ссылкой на гипотезу-ядро: вердикт false, `source = "triage_merge"` (в сводке
  датасета считается «объединено», а не «опровергнуто»), обоснование «Объединена с #N: …»;
* keep — без изменений.

Идемпотентность: гипотеза, у которой уже есть вердикт или отметка `evidence_json.triage`, не трогается; повторный
прогон ничего не меняет. Ядро объединения должно существовать и быть открытым (или закрываться в этом же прогоне не
как дубль) — иначе строка пропускается с причиной. По умолчанию — только план; запись — с `apply=True`.
Каждое применённое изменение возвращается для журнала (было/стало).
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

MERGE_SOURCE = "triage_merge"
ACTIONS = ("close_true", "close_false", "merge", "keep")


@dataclass(frozen=True)
class Decision:
    id: int
    action: str
    merge_into: int | None
    ref: str | None
    reason: str


def read_decisions(path: Path) -> list[Decision]:
    out = []
    with open(path, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            action = (row.get("действие") or "").strip()
            if action not in ACTIONS:
                continue
            merge_into = (row.get("объединить_в") or "").strip()
            out.append(Decision(
                id=int(row["id"]), action=action,
                merge_into=int(merge_into) if merge_into else None,
                ref=(row.get("запись_контекста") or "").strip() or None,
                reason=(row.get("обоснование") or "").strip(),
            ))
    return out


async def apply_triage(db, decisions: list[Decision], *, apply: bool, now: datetime | None = None) -> dict:
    """План или применение. Возвращает {"changes": [...], "skipped": [...], "kept": n}."""
    from app.models import Hypothesis

    now = now or datetime.now()
    day = f"{now:%d.%m}"
    changes, skipped, kept = [], [], 0
    by_id = {d.id: d for d in decisions}
    for d in decisions:
        if d.action == "keep":
            kept += 1
            continue
        h = await db.get(Hypothesis, d.id)
        if h is None:
            skipped.append({"id": d.id, "why": "гипотезы нет"})
            continue
        if h.verdict is not None or (h.evidence_json or {}).get("triage"):
            skipped.append({"id": d.id, "why": "уже закрыта (повторный прогон)"})
            continue
        if d.action == "merge":
            core = await db.get(Hypothesis, d.merge_into) if d.merge_into else None
            core_decision = by_id.get(d.merge_into)
            if core is None or core.verdict is not None or (core_decision and core_decision.action == "merge"):
                skipped.append({"id": d.id, "why": f"ядро #{d.merge_into} не открыто или само объединяется"})
                continue
            verdict, source = False, MERGE_SOURCE
            rationale = f"Объединена с #{d.merge_into}: {d.reason}"
        else:
            verdict, source = d.action == "close_true", h.source
            rationale = f"Расчистка {day}: {d.reason}" + (f" {d.ref}" if d.ref else "")
        change = {"id": d.id, "action": d.action, "merge_into": d.merge_into, "ref": d.ref,
                  "before": {"verdict": h.verdict, "rationale": (h.rationale or "")[:300], "source": h.source},
                  "after": {"verdict": verdict, "rationale": rationale[:2000], "source": source}}
        changes.append(change)
        if apply:
            h.verdict = verdict
            h.source = source
            h.rationale = rationale[:2000]
            h.evidence_json = {**(h.evidence_json or {}), "triage": {
                "action": d.action, "merge_into": d.merge_into, "ref": d.ref, "applied_at": now.isoformat()}}
            h.updated_at = now
    if apply and changes:
        await db.commit()
    return {"changes": changes, "skipped": skipped, "kept": kept}
