"""Grounded first-party session reports. Events are never pixel recordings.

The deterministic report is available without AI or external services. Raw
evidence is read through a paginated admin API; bounded report construction
always exposes omitted events. Optional narrative cannot modify facts,
coverage, satisfaction, or the physical-human classification.
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
import re
from collections import Counter
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit

from sqlalchemy import case, func, or_, select, update

from app.config import settings
from app.models import BehaviorEvent, BehaviorSession, FrontendEvent, SessionAnalysisReport, SessionReplayChunk
from app.session_analysis_schema import NarrativeFindings, VisualReview

logger = logging.getLogger(__name__)
# Bump on changes to evidence rules or narrative contract. The queue rebuilds
# old versions, including inactive sessions with no newly captured events.
SCHEMA_VERSION = "1"
MAX_REPORT_EVENTS = 20_000
MAX_AI_INPUT_BYTES = 128_000
EVENT_PAGE_SIZE = 1000
_PARAM_KEYS = frozenset({
    "m", "v", "rating", "ms", "active_ms", "visible_ms", "attention_version",
    "scroll_pct", "clicks", "move_px", "block", "visibility_version",
    "visibility_ratio", "focused", "occluded", "vw", "vh", "dpr", "touch",
    "vx", "vy", "st", "ok", "u", "relative_ms", "inp_target", "inp_type", "inp_target_source", "inp_reported_target",
    "inp_start_ms", "input_delay_ms", "processing_ms", "presentation_ms",
    "load_state", "component", "visible", "config_version", "pointer_type",
    "phase", "target_path", "target_name", "duration_ms", "start_ms", "end_ms",
    "time_origin_ms", "interaction_epoch_ms", "evidence_version", "interaction_type",
    "input_type", "interaction_id", "target", "action", "trusted", "expanded",
    "scroll_version", "scroll_valid", "scroll_height", "viewport_height", "max_y", "scroll_viewport", "scroll_max_y",
    "indicator", "indicatorCategory", "range", "mode", "format", "world",
})


def _value(row, key, default=None):
    return row.get(key, default) if isinstance(row, dict) else getattr(row, key, default)


def _datetime(value) -> datetime:
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if not isinstance(value, datetime):
        raise ValueError("Evidence requires a valid original timestamp")
    return value.astimezone(timezone.utc).replace(tzinfo=None) if value.tzinfo else value


def _iso(value) -> str:
    return _datetime(value).isoformat(timespec="milliseconds") + "Z"


def redact_text(value, limit=400) -> str:
    """Drop likely identifiers; field allowlisting also removes input values."""
    s = str(value or "")[:limit]
    s = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[redacted]", s)
    s = re.sub(r"(?<!\w)(?:\+?\d[\d ()-]{6,}\d)(?!\w)", "[redacted]", s)
    s = re.sub(r"\b[a-f0-9]{32,}\b", "[redacted]", s, flags=re.I)
    s = re.sub(r"\[(?:value|data-user|data-email)[^\]]*\]", "[redacted]", s, flags=re.I)
    return s


def public_path(value) -> str | None:
    if not value:
        return None
    path = urlsplit(str(value)).path or "/"
    # Auth/private routes do not convey an individual's private document ID.
    if path.startswith(("/account", "/auth", "/admin")):
        return f"/{path.split('/')[1]}/[private]"
    return redact_text(path, 500)


def _number(value) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        n = float(value)
        return n if math.isfinite(n) else None
    except (TypeError, ValueError):
        return None


def sanitize_params(params) -> dict:
    if not isinstance(params, dict):
        return {}
    out = {}
    for key in sorted(_PARAM_KEYS & params.keys()):
        value = params[key]
        if isinstance(value, str):
            out[key] = public_path(value) if key == "u" else redact_text(value)
        elif value is None or isinstance(value, (bool, int, float)):
            if not isinstance(value, float) or math.isfinite(value):
                out[key] = value
    return out


def event_evidence(row, origin: datetime) -> dict:
    timestamp = _datetime(_value(row, "occurred_at"))
    event_id = int(_value(row, "id"))
    business = _value(row, "event_name") is not None
    return {
        "id": f"{'frontend' if business else 'event'}:{event_id}", "source": "frontend_event" if business else "behavior_event", "event_id": event_id,
        "occurred_at": _iso(timestamp),
        "ingested_at": _iso(_value(row, "ingested_at", timestamp)),
        "relative_ms": max(0, round((timestamp - origin).total_seconds() * 1000)),
        "event_type": _value(row, "event_name") if business else _value(row, "event_type"),
        "page": public_path(_value(row, "url")) if business else public_path(_value(row, "page")),
        "page_load_id": redact_text(_value(row, "page_load_id"), 40) or None,
        "element_path": redact_text(_value(row, "element_path")) or None,
        "element_text": redact_text(_value(row, "element_text"), 120) or None,
        "params": sanitize_params(_value(row, "params_json")),
        "heuristic_flags": {"dead": bool(_value(row, "is_dead")), "rage": bool(_value(row, "is_rage"))},
    }


def source_fingerprint(evidence, *, total_count, latest_event_id, visual=None, replay=None) -> str:
    payload = {"schema": SCHEMA_VERSION, "events": evidence, "total": total_count,
               "latest": latest_event_id, "visual": visual, "replay": replay or {}}
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()


def build_session_report(session_id, rows, *, portrait=None, captured_count=None,
                         latest_event_id=None, visual_review=None, replay_context=None,
                         source_counts=None, latest_frontend_event_id=0, latest_replay_chunk_id=0) -> dict:
    """Analyze every supplied row; counts disclose any repository budget limit."""
    rows = sorted(rows, key=lambda r: (_datetime(_value(r, "occurred_at")), int(_value(r, "id"))))
    total = len(rows) if captured_count is None else int(captured_count)
    if total < len(rows):
        raise ValueError("Captured count cannot be smaller than analyzed events")
    latest = int(max((_value(r, "id") for r in rows), default=0) if latest_event_id is None else latest_event_id)
    replay = replay_context or {}
    replay_start = _number(replay.get("original_start_ms"))
    epoch_start = replay_start is not None and 100_000_000_000 <= replay_start <= 4_000_000_000_000
    # An empty event stream must not acquire a new clock/fingerprint on each read.
    origin = (_datetime(_value(rows[0], "occurred_at")) if rows else
              datetime.fromtimestamp(replay_start / 1000, tz=timezone.utc).replace(tzinfo=None) if epoch_start else datetime(1970, 1, 1))
    evidence = [event_evidence(r, origin) for r in rows]
    facts, inferences, recommendations, issues, outcomes = [], [], [], [], []
    unknowns = [
        {"code": "task_outcome", "text": "Достижение задачи посетителя по этим данным не установлено."},
        {"code": "satisfaction", "text": "Удовлетворённость посетителя неизвестна; прокрутка и время её не доказывают."},
        {"code": "physical_human", "text": "Сессия браузера не доказывает отдельного физического человека."},
        {"code": "end_reason", "text": "Конец событий не устанавливает причину завершения или ухода."},
    ]

    def fact(code, text, refs):
        facts.append({"id": code, "text": text, "evidence_ids": refs})

    def issue(code, text, refs, verification):
        issues.append({"code": code, "evidence_ids": refs})
        recommendations.append({"id": f"{code}:{refs[0]}", "issue_code": code, "text": text, "reason": "Проверка наблюдаемого сигнала, причина пока не установлена.",
                                "evidence_ids": refs, "verification": verification})

    pageviews = [e for e in evidence if e["event_type"] == "pageview"]
    route = [e["page"] for e in pageviews]
    if pageviews:
        fact("route", "Зарегистрированный путь: " + " → ".join(p or "неизвестная страница" for p in route), [e["id"] for e in pageviews])
        if any(re.search(r"/indicator/[^/]+/\d{4}$", p or "") for p in route):
            inferences.append({"id": "historical_data_task", "text": "Вход на годовую страницу может соответствовать поиску исторических значений. Альтернатива — переход по готовой ссылке без конкретной задачи; точная цель неизвестна.",
                               "evidence_ids": [e["id"] for e in pageviews], "confidence": "tentative"})
    clicks = [e for e in evidence if e["event_type"] == "click"]
    if clicks:
        fact("clicks", f"Зарегистрировано кликов: {len(clicks)}. Само событие не подтверждает результат обработчика.", [e["id"] for e in clicks])
    inp = []
    old_visibility = []
    for e in evidence:
        p, typ, refs = e["params"], e["event_type"], [e["id"]]
        if e["source"] == "frontend_event" and typ in ("download_csv", "download_excel"):
            fact(f"export:{e['event_id']}", f"Клиент зарегистрировал {typ} после успешной выдачи файла помощником экспорта. Сохранение файла на устройстве не проверено.", refs)
            outcomes.append({"code": "client_export_dispatched", "event_name": typ, "evidence_ids": refs,
                             "scope": "client_reported_subtask", "file_saved": "unknown"})
        if typ == "vital" and str(p.get("m", "")).upper() == "INP":
            value = _number(p.get("v"))
            if value is None or value < 0:
                continue
            target = p.get("inp_target") or None
            inp.append({"value_ms": value, "page": e["page"], "target": target, "event_id": e["event_id"],
                        "interaction_type": p.get("inp_type"), "interaction_start_ms": p.get("inp_start_ms")})
            fact(f"inp:{e['event_id']}", f"На {e['page']} зарегистрирован INP {value:g} мс; " + (f"target: {target}." if target else "target не записан."), refs)
            if target is None:
                unknowns.append({"code": "inp_target", "text": "INP нельзя приписать cookie-баннеру или конкретной кнопке без атрибуции.", "evidence_ids": refs})
            if value > 500:
                issue("slow_inp", "Проверить задержку взаимодействия на этой странице.", refs,
                      "Сопоставить INP с типом, target, исходным временем, input/processing/presentation delay и воспроизвести на сопоставимом устройстве.")
        if typ == "js_error":
            fact(f"js_error:{e['event_id']}", "Зарегистрировано событие ошибки JavaScript; её влияние на задачу неизвестно.", refs)
            issue("js_error", "Проверить событие ошибки JavaScript и соседние состояния интерфейса.", refs, "Установить stack/source и повторить затронутое действие; отделить влияние расширения от кода сайта.")
        if typ == "api_timing" and (p.get("ok") in (False, 0) or (_number(p.get("st")) or 0) >= 400):
            fact(f"api_error:{e['event_id']}", "Зарегистрирован неуспешный API-запрос; видимое состояние неизвестно.", refs)
            issue("api_error", "Проверить неуспешный запрос и реакцию интерфейса.", refs, "Сопоставить HTTP-статус, endpoint, повторную попытку и визуальное состояние.")
        if typ == "block_view" and (_number(p.get("visibility_version")) or 0) < 3:
            old_visibility.append(e["id"])
        if typ == "ui_state":
            fact(f"ui:{e['event_id']}", f"Сборщик сообщил состояние {p.get('component', 'компонента')}: visible={p.get('visible', 'unknown')}; это не пиксельная проверка.", refs)
    if old_visibility:
        unknowns.append({"code": "block_visibility_legacy", "text": "Старые block_view не проверяют перекрытие баннером и не доказывают чтение блока.", "evidence_ids": old_visibility})
        issues.append({"code": "block_visibility_legacy", "evidence_ids": old_visibility})
    heuristic = [e["id"] for e in evidence if any(e["heuristic_flags"].values())]
    if heuristic:
        fact("heuristic_clicks", "Сборщик выставил эвристические dead/rage-флаги; это не подтверждённый дефект интерфейса.", heuristic)
        issue("click_heuristic", "Проверить эпизоды с эвристическими флагами кликов.", heuristic, "Проверить target, обработчик и изменение состояния; исключить повторный тап и артефакт записи.")
    scroll = max((min(100, max(0, _number(e["params"].get("scroll_pct")) or 0)) for e in evidence), default=0)
    valid_scroll = [e for e in evidence if e["event_type"] == "dwell" and e["params"].get("scroll_valid") in (True, 1) and (_number(e["params"].get("scroll_version")) or 0) >= 3]
    valid_scroll_pct = max((min(100, max(0, _number(e["params"].get("scroll_pct")) or 0)) for e in valid_scroll), default=None)
    if any(e["event_type"] == "dwell" and (_number(e["params"].get("scroll_version")) or 0) < 3 for e in evidence):
        unknowns.append({"code": "scroll_legacy", "text": "Старая глубина прокрутки могла измеряться на коротком загрузочном экране; 100% не доказывает просмотр всей страницы."})
    active_ms = sum(max(0, _number(e["params"].get("active_ms")) or 0) for e in evidence if e["event_type"] == "dwell")
    duration = evidence[-1]["relative_ms"] if evidence else None
    if not rows and replay.get("chunk_count"):
        unknowns.append({"code": "event_stream_missing", "text": "Сохранена запись replay, но поведенческие и бизнес-события отсутствуют; маршрут и действия из этих потоков проверить нельзя."})
    dom_states = replay.get("dom_states") or []
    if (replay.get("dom_states_complete") is False and (dom_states or replay.get("chunk_count"))) or len(dom_states) > 1000:
        unknowns.append({"code": "dom_state_budget", "text": "DOM-данные неполны (пропуски записи или лимит анализа); полный визуальный просмотр не подтверждён."})
    for state in dom_states[:1000]:
        if not isinstance(state, dict) or state.get("source") != "dom_snapshot" or not state.get("state_id"):
            continue
        ref = "dom:" + redact_text(state["state_id"], 80)
        timestamp_ms = _number(state.get("original_timestamp_ms", state.get("original_time_ms")))
        epoch_ms = round(origin.replace(tzinfo=timezone.utc).timestamp() * 1000)
        verified_epoch = timestamp_ms is not None and 100_000_000_000 <= timestamp_ms <= 4_000_000_000_000
        viewport = state.get("viewport") if isinstance(state.get("viewport"), dict) else {}
        viewport = {k: n for k in ("w", "h") if (n := _number(viewport.get(k))) is not None and 0 < n <= 20_000}
        boxes = []
        for box in (state.get("boxes") or [])[:80]:
            if not isinstance(box, dict):
                continue
            safe_box = {k: n for k in ("x", "y", "w", "h") if (n := _number(box.get(k))) is not None and abs(n) <= 100_000}
            safe_box.update(text=redact_text(box.get("text"), 500), tag=redact_text(box.get("tag"), 30), block=redact_text(box.get("block"), 80))
            boxes.append(safe_box)
        item = {"id": ref, "source": "dom_snapshot", "original_timestamp_ms": timestamp_ms,
                "relative_ms": max(0, round(timestamp_ms - epoch_ms)) if verified_epoch else None,
                "source_clock": "epoch_ms" if verified_epoch else "unknown",
                "occurred_at": _iso(datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)) if verified_epoch else None,
                "page": public_path(state.get("page")), "replay_id": state.get("replay_id"),
                "visible_text": redact_text(state.get("visible_text"), 2000), "overlay": state.get("overlay") is True,
                "viewport": viewport, "boxes": boxes,
                "pixel_verified": False}
        evidence.append(item)
        fact(ref, "В записанном DOM-состоянии: " + (item["visible_text"] or "доступна структура интерфейса") + ". Это реконструкция, не пиксельный кадр.", [ref])
    visual = VisualReview.model_validate(visual_review) if visual_review else None
    if visual:
        for observation in visual.observations:
            item = observation.model_dump(mode="json")
            item.update(id="visual:" + observation.observation_id, source="visual_observation")
            evidence.append(item)
            fact(item["id"], "В воспроизведении: " + redact_text(observation.description, 1500), [item["id"]])
    visual_status = visual.status if visual else ("dom_only" if dom_states else "not_reviewed")
    if not visual:
        unknowns.append({"code": "visual_review", "text": "Пиксельный просмотр записи не выполнен. События и DOM его не заменяют."})
    complete = total == len(rows)
    if not complete:
        unknowns.append({"code": "event_budget", "text": "Отчёт достиг лимита событий. Полный поток доступен через пагинацию; выводы относятся только к обработанным событиям."})
    if not rows and replay.get("chunk_count"):
        complete = False
    safe_portrait = {k: _value(portrait, k) for k in ("browser", "os", "device_type", "is_synthetic", "is_webdriver")} if portrait else None
    fingerprint = source_fingerprint(evidence, total_count=total, latest_event_id=latest,
                                     visual=visual.model_dump(mode="json") if visual else None,
                                     replay={"recording": replay, "portrait": safe_portrait})
    return {
        "session_id": session_id, "schema_version": SCHEMA_VERSION,
        "analysis_mode": "events_and_visual" if visual else ("events_and_dom" if dom_states else "events_only"),
        "facts": facts, "inferences": inferences, "unknowns": unknowns, "recommendations": recommendations,
        "issues": issues, "evidence": evidence, "outcomes": outcomes,
        "metrics": {"pageviews": len(pageviews), "clicks": len(clicks), "route": route,
                    "first_event_at": _iso(origin) if rows else None,
                    "last_event_at": evidence[len(rows) - 1]["occurred_at"] if rows else None,
                    "observed_duration_ms": duration, "reported_active_ms": active_ms,
                    "max_scroll_pct": scroll, "valid_max_scroll_pct": valid_scroll_pct,
                    "scroll_measurement": "validated_geometry" if valid_scroll else "legacy_or_missing", "inp": inp},
        "coverage": {"captured_events": total, "analyzed_events": len(rows), "event_complete": complete,
                     "scope": "currently_retained_behavior_frontend_and_replay_sources", "collection_completeness": "unknown",
                     "sources": source_counts or dict(Counter(e["source"] for e in evidence if e["source"] in ("behavior_event", "frontend_event"))),
                     "events_api_sources": ["behavior", "frontend"],
                     "satisfaction": "unknown", "human_identity": "unknown", "task_outcome": "observed_subtask" if outcomes else "unknown",
                     "visual": {"status": visual_status, "pixel_reviewed": bool(visual),
                                "viewed_intervals": [i.model_dump() for i in visual.viewed_intervals] if visual else [],
                                "original_duration_ms": visual.original_duration_ms if visual else replay.get("original_duration_ms")},
                     "dom": {"states_received": len(dom_states), "states_analyzed": sum(e["source"] == "dom_snapshot" for e in evidence),
                             "states_captured": replay.get("dom_state_count"), "states_complete": replay.get("dom_states_complete"),
                             "pixel_verified": False},
                     "timeline_clock": "first_retained_event_utc" if rows else ("replay_client_epoch_ms" if epoch_start else "unknown"),
                     "replay": {k: replay.get(k) for k in ("chunk_count", "event_count", "full_snapshot_count", "gaps", "incomplete", "fingerprint", "fidelity_limitations", "original_start_ms", "original_end_ms", "source_clock", "pixel_complete")}},
        "freshness": {"fingerprint": fingerprint, "latest_event_id": latest, "latest_frontend_event_id": latest_frontend_event_id,
                      "latest_replay_chunk_id": latest_replay_chunk_id},
        "ai": {"status": "disabled", "provider": None},
        "portrait": safe_portrait,
    }


async def load_replay_context(db, session_id):
    """Integration boundary owned by the replay service; absence is explicit."""
    try:
        from app.services.session_replay import analysis_replay_context
    except ImportError:
        return {}
    return await analysis_replay_context(db, session_id)


async def load_session_report(db, session_id, *, visual_review=None, replay_context=None):
    snapshot_at = datetime.now(timezone.utc).replace(tzinfo=None)
    portrait = await db.get(BehaviorSession, session_id)
    stats = (await db.execute(select(func.count(BehaviorEvent.id), func.max(BehaviorEvent.id)).where(BehaviorEvent.session_id_hash == session_id))).one()
    business_stats = (await db.execute(select(func.count(FrontendEvent.id), func.max(FrontendEvent.id)).where(FrontendEvent.session_id_hash == session_id))).one()
    replay_stats = (await db.execute(select(func.count(SessionReplayChunk.id), func.max(SessionReplayChunk.id)).where(SessionReplayChunk.session_id_hash == session_id))).one()
    if not stats[0] and not business_stats[0] and not replay_stats[0] and portrait is None:
        return None
    rows = (await db.execute(select(BehaviorEvent).where(BehaviorEvent.session_id_hash == session_id, BehaviorEvent.id <= (stats[1] or 0))
                            .order_by(BehaviorEvent.occurred_at, BehaviorEvent.id).limit(MAX_REPORT_EVENTS))).scalars().all()
    business_rows = (await db.execute(select(FrontendEvent).where(FrontendEvent.session_id_hash == session_id, FrontendEvent.id <= (business_stats[1] or 0))
                                     .order_by(FrontendEvent.occurred_at, FrontendEvent.id).limit(MAX_REPORT_EVENTS))).scalars().all()
    rows = sorted([*rows, *business_rows], key=lambda r: (_datetime(r.occurred_at), r.id))[:MAX_REPORT_EVENTS]
    context = await load_replay_context(db, session_id) if replay_context is None else replay_context
    stale_visual = False
    if visual_review:
        parsed = VisualReview.model_validate(visual_review)
        stale_visual = any(o.provenance.source == "own_replay" and o.provenance.replay_fingerprint != context.get("fingerprint") for o in parsed.observations)
        if stale_visual:
            visual_review = None
    report = build_session_report(session_id, rows, portrait=portrait, captured_count=stats[0] + business_stats[0], latest_event_id=stats[1] or 0,
                                  visual_review=visual_review, replay_context=context,
                                  source_counts={"behavior_event": stats[0], "frontend_event": business_stats[0]},
                                  latest_frontend_event_id=business_stats[1] or 0, latest_replay_chunk_id=replay_stats[1] or 0)
    report["freshness"]["snapshot_at"] = snapshot_at.isoformat()
    if stale_visual:
        report["unknowns"].append({"code": "visual_source_changed", "text": "Визуальный разбор относится к другой версии записи; требуется повторный просмотр."})
    return report


def redacted_llm_payload(report):
    """Only derived public facts and typed evidence metadata, no raw params/IDs."""
    aliases = {e["id"]: f"e{i}" for i, e in enumerate(report["evidence"], 1)}
    return {
        "facts": [{"text": redact_text(f["text"], 1200), "evidence_ids": [aliases[e] for e in f["evidence_ids"]]} for f in report["facts"]],
        "evidence": [{"id": aliases[e["id"]], "source": e["source"], "event_type": e.get("event_type"),
                      "page": public_path(e.get("page")), "relative_ms": e.get("relative_ms", e.get("original_time_ms"))} for e in report["evidence"]],
        "dom_state_facts": [{"evidence_id": aliases[e["id"]], "viewport": e["viewport"], "overlay_reported": e["overlay"],
                             "public_boxes": e["boxes"], "source": "dom_snapshot", "pixel_verified": False}
                            for e in report["evidence"] if e["source"] == "dom_snapshot"],
        "metrics": {k: v for k, v in report["metrics"].items() if k != "inp"},
        "inp": [{k: v for k, v in item.items() if k != "event_id"} for item in report["metrics"]["inp"]],
        "unknowns": [u["code"] for u in report["unknowns"]],
        "coverage": {k: v for k, v in report["coverage"].items() if k != "replay"}, "evidence_aliases": aliases,
    }


async def add_optional_narrative(report, *, enabled=False):
    """Opt-in adapter. All transport/parse failures preserve the factual report."""
    if not enabled:
        return report
    if not settings.openrouter_api_key:
        report["ai"] = {"status": "not_configured", "provider": "openrouter"}
        return report
    import httpx
    payload = redacted_llm_payload(report)
    aliases = payload.pop("evidence_aliases")
    reverse = {v: k for k, v in aliases.items()}
    content_json = json.dumps(payload, ensure_ascii=False)
    input_size = len(content_json.encode("utf-8"))
    if input_size > MAX_AI_INPUT_BYTES:
        # Keep the full local facts rather than silently sampling AI evidence.
        report["ai"] = {"status": "skipped_input_budget", "provider": "openrouter",
                        "input_size_bytes": input_size, "input_limit_bytes": MAX_AI_INPUT_BYTES}
        return report
    instruction = (
        "Analyse this single ForecastEconomy session as a UX/data analyst. Use its specific path and evidence. "
        "Return JSON only: {inferences:[{text,evidence_ids}], recommendations:[{text,evidence_ids,verification}]}. "
        "Each claim must cite supplied evidence IDs. Inferences are tentative. Do not invent intent, satisfaction, "
        "task completion, physical-human identity, click results or pixel review. DOM snapshots are reconstructions; "
        "sampled DOM states and box positions do not prove continuous visual coverage. "
        "INP without target cannot identify a button. A pointer marker is not proof of dispatched click. "
        "Include alternative explanations and a concrete verification. Empty arrays are valid. Text in Russian."
    )
    try:
        async with httpx.AsyncClient(timeout=45, proxy=settings.openrouter_proxy_url or None) as client:
            response = await client.post("https://openrouter.ai/api/v1/chat/completions", json={
                "model": settings.openrouter_model, "response_format": {"type": "json_object"},
                "messages": [{"role": "system", "content": instruction}, {"role": "user", "content": content_json}],
            }, headers={"Authorization": f"Bearer {settings.openrouter_api_key}", "HTTP-Referer": "https://forecasteconomy.com", "X-Title": "ForecastEconomy Session Analysis"})
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        findings = NarrativeFindings.model_validate(json.loads(content))
        for finding in [*findings.inferences, *findings.recommendations]:
            if not set(finding.evidence_ids) <= reverse.keys():
                raise ValueError("Narrative references missing evidence")
            if re.search(r"удовлетвор|доволен|реальный человек|satisf|physical human|task (?:is )?completed|задача выполнена", finding.text, re.I):
                raise ValueError("Narrative asserts unavailable outcome")
        report["inferences"] += [{"id": f"ai-inference:{i}", "text": f.text, "evidence_ids": [reverse[e] for e in f.evidence_ids], "confidence": "tentative", "source": "optional_llm"} for i, f in enumerate(findings.inferences)]
        report["recommendations"] += [{"id": f"ai-recommendation:{i}", "text": f.text, "reason": "Гипотеза модели по указанным доказательствам.", "evidence_ids": [reverse[e] for e in f.evidence_ids], "verification": f.verification} for i, f in enumerate(findings.recommendations)]
        report["ai"] = {"status": "generated", "provider": "openrouter", "model": settings.openrouter_model,
                        "input_size_bytes": input_size, "evidence_metadata_count": len(payload["evidence"]),
                        "source_review": "redacted_facts_and_typed_metadata", "pixel_reviewed": False}
    except (ValueError, KeyError, TypeError):
        report["ai"] = {"status": "invalid", "provider": "openrouter"}
    except Exception:
        logger.warning("Optional session narrative failed; deterministic report retained")
        report["ai"] = {"status": "failed", "provider": "openrouter"}
    return report


async def ensure_report_row(db, session_id):
    """An API request and the scheduler may first encounter the same session."""
    dialect = db.bind.dialect.name
    if dialect in ("postgresql", "sqlite"):
        if dialect == "postgresql":
            from sqlalchemy.dialects.postgresql import insert
        else:
            from sqlalchemy.dialects.sqlite import insert
        await db.execute(insert(SessionAnalysisReport).values(session_id_hash=session_id)
                         .on_conflict_do_nothing(index_elements=["session_id_hash"]))
        return await db.get(SessionAnalysisReport, session_id)
    row = await db.get(SessionAnalysisReport, session_id)
    if row is None:
        row = SessionAnalysisReport(session_id_hash=session_id)
        db.add(row)
        await db.flush()
    return row


async def persist_report(db, report, *, visual_review=None):
    row = await ensure_report_row(db, report["session_id"])
    row.schema_version = SCHEMA_VERSION
    row.source_fingerprint = report["freshness"]["fingerprint"]
    row.latest_event_id = report["freshness"]["latest_event_id"]
    row.event_count = report["coverage"]["captured_events"]
    row.report_json = report
    if visual_review is not None:
        row.visual_json = VisualReview.model_validate(visual_review).model_dump(mode="json")
    status = "complete" if report["coverage"]["event_complete"] else "partial"
    row.status = status
    row.generated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    row.error = None
    await db.flush()
    snapshot_at = datetime.fromisoformat(report["freshness"].get("snapshot_at", datetime.now(timezone.utc).replace(tzinfo=None).isoformat()))
    # The SQL expression sees queue revisions committed during an LLM wait.
    await db.execute(update(SessionAnalysisReport).where(SessionAnalysisReport.session_id_hash == report["session_id"])
                     .values(pending_event_id=case((SessionAnalysisReport.pending_event_id < row.latest_event_id, row.latest_event_id), else_=SessionAnalysisReport.pending_event_id),
                             status=case((or_(SessionAnalysisReport.pending_event_id > row.latest_event_id,
                                              SessionAnalysisReport.pending_at > snapshot_at), "pending"), else_=status)))
    return row
