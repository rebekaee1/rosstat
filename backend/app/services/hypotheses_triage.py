"""Применение расчистки гипотез Пульса (14.11.2026) — по таблице решений сухого прогона.

Вход — `решения.csv` из `.artifacts/pulse-hypotheses-triage-2026-11-14/` (колонки id, действие, объединить_в,
запись_контекста, обоснование). Действия:

* close_true / close_false — вердикт true / false, обоснование «Расчистка ДД.ММ: … [запись]»;
* merge — дубль закрывается со ссылкой на гипотезу-ядро: вердикт false, `source = "triage_merge"` (в сводке
  датасета считается «объединено», а не «опровергнуто»), обоснование «Объединена с #N: …»;
* keep — без изменений.

19.11.2026: второй вход — план JSON (`.artifacts/pulse-fixes-2026-11-19/hypotheses-plan-2026-11-19.json`):
`[{id, action, verdict, keep_id, rationale}]`, действия close_true / close_false / close_duplicate (= merge,
`keep_id` — ядро) / close_obsolete / keep. close_obsolete — проверить больше нечем (источник отключён): вердикт
false, `source = "triage_obsolete"` (в сводке датасета «устарело», а не «опровергнуто»).
Дубль закрывается и тогда, когда ядро уже закрыто или закрывается в этом же прогоне: вердикт дубля — вердикт ядра
(повтор подтверждённой — подтверждён); при открытом ядре — false с `source = "triage_merge"`. Модель Пульса видит
только открытые (`verdict IS NULL`), поэтому закрытый дубль из её входа уходит, а ядро остаётся.

Идемпотентность: гипотеза, у которой уже есть вердикт или отметка `evidence_json.triage`, не трогается; повторный
прогон ничего не меняет. Ядро объединения должно существовать и само не объединяться в этом прогоне (без цепочек) —
иначе строка пропускается с причиной. По умолчанию — только план; запись — с `apply=True`, одной транзакцией.
Каждое применённое изменение возвращается для журнала (было/стало).
"""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

MERGE_SOURCE = "triage_merge"
OBSOLETE_SOURCE = "triage_obsolete"
ACTIONS = ("close_true", "close_false", "close_obsolete", "merge", "keep")
_PLAN_ACTIONS = {"close_duplicate": "merge"}


@dataclass(frozen=True)
class Decision:
    id: int
    action: str
    merge_into: int | None
    ref: str | None
    reason: str


def read_plan_json(path: Path) -> list[Decision]:
    """План JSON 19.11: [{id, action, verdict, keep_id, rationale}]. Вердикт закрытия сверяется с действием."""
    out = []
    for row in json.loads(Path(path).read_text(encoding="utf-8")):
        action = _PLAN_ACTIONS.get(row.get("action"), row.get("action"))
        if action not in ACTIONS:
            raise ValueError(f"гипотеза {row.get('id')}: неизвестное действие {row.get('action')!r}")
        expected = {"close_true": True, "close_false": False, "close_obsolete": False}.get(action)
        if expected is not None and row.get("verdict") is not expected:
            raise ValueError(f"гипотеза {row['id']}: действие {action} и вердикт {row.get('verdict')!r} расходятся")
        if action == "merge" and not row.get("keep_id"):
            raise ValueError(f"гипотеза {row['id']}: дубль без keep_id")
        out.append(Decision(id=int(row["id"]), action=action,
                            merge_into=int(row["keep_id"]) if action == "merge" else None,
                            ref=None, reason=str(row.get("rationale") or "").strip()))
    return out


def read_decisions(path: Path) -> list[Decision]:
    if Path(path).suffix.lower() == ".json":
        return read_plan_json(path)
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
            if core is None or (core_decision and core_decision.action == "merge"):
                skipped.append({"id": d.id, "why": f"ядра #{d.merge_into} нет или оно само объединяется"})
                continue
            # Вердикт дубля — вердикт ядра (уже вынесенный или выносимый этим прогоном); при открытом ядре — false.
            if core.verdict is not None:
                verdict = core.verdict
            elif core_decision and core_decision.action in ("close_true", "close_false"):
                verdict = core_decision.action == "close_true"
            else:
                verdict = False
            source = MERGE_SOURCE
            rationale = f"Объединена с #{d.merge_into}: {d.reason}"
        elif d.action == "close_obsolete":
            verdict, source = False, OBSOLETE_SOURCE
            rationale = f"Устарела {day}: {d.reason}"
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
