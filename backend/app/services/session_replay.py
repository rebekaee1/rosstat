"""Bounded DOM reconstruction with explicit transport and visual limitations."""
from __future__ import annotations

import hashlib
import json
import math
import posixpath
import re
import zlib
from collections import defaultdict
from typing import Any
from urllib.parse import unquote, urlsplit, urlunsplit

from sqlalchemy import func, select

from app.models import SessionReplayChunk

MAX_FRAGMENT_BYTES = 32_000
MAX_READ_BYTES = 16_000_000
MAX_READ_ROWS = 20_000
MAX_BATCH_BYTES = 4_000_000
MAX_GAPS = 1000
MAX_DOM_STATES = 1000
PRIVATE_PATHS = ("/admin", "/account", "/auth", "/login", "/register", "/reset", "/embed", "/forgot-password", "/verify-email")
MASK = "[redacted]"
FIDELITY_LIMITATIONS = [
    "dom_reconstruction_not_pixel_recording",
    "inputs_and_sensitive_regions_are_masked",
    "canvas_content_not_recorded",
    "css_reconstruction_may_differ",
    "external_assets_may_be_unavailable_or_changed",
    "iframes_and_scripts_not_replayed",
]


def _finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and 0 <= value <= 8_640_000_000_000_000


def _redact(value, limit=5000):
    if not isinstance(value, str):
        return ""
    value = value[:limit]
    value = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", MASK, value)
    value = re.sub(r"(?<!\w)(?:\+?\d[\d ()-]{6,}\d)(?!\w)", MASK, value)
    return re.sub(r"\b[a-f0-9]{32,}\b", MASK, value, flags=re.I)


def public_page(value):
    if not isinstance(value, str) or not value.startswith("/") or value.startswith("//"):
        raise ValueError("invalid replay page")
    value = value.split("?", 1)[0].split("#", 1)[0]
    for _ in range(4):
        decoded = unquote(value, errors="strict")
        if decoded == value:
            break
        value = decoded
    value = value.split("?", 1)[0].split("#", 1)[0]
    value = value.replace("\\", "/")
    if any(ord(c) < 32 for c in value) or value.startswith("//"):
        raise ValueError("invalid replay page")
    value.encode("utf-8")
    path = posixpath.normpath(value)
    if any(path == p or path.startswith(p + "/") for p in PRIVATE_PATHS):
        raise ValueError("private replay page")
    return _redact(path, 500)


def public_url(value):
    if not isinstance(value, str):
        return ""
    try:
        parts = urlsplit(value)
        if parts.scheme and parts.scheme not in ("http", "https"):
            return ""
        path = public_page(parts.path or "/")
        # Credentials, query and fragment are never returned to a player/model.
        netloc = parts.hostname or ""
        if parts.port:
            netloc += ":" + str(parts.port)
        return urlunsplit((parts.scheme, netloc, path, "", ""))
    except (ValueError, UnicodeError):
        return ""


def _css(value):
    def url(match):
        target = match.group(2)
        return 'url("' + (target if _local_svg_ref(target) else public_url(target)) + '")'
    value = re.sub(r"url\(\s*(['\"]?)(.*?)\1\s*\)", url, value, flags=re.I)
    value = re.sub(r"(@import\s+)(['\"])(.*?)\2", lambda m: m.group(1) + '"' + public_url(m.group(3)) + '"', value, flags=re.I)
    return value


def _local_svg_ref(value):
    return isinstance(value, str) and re.fullmatch(r"#[A-Za-z_][A-Za-z0-9_.:-]{0,127}", value) is not None


def _sanitize(value, depth=0, budget=None):
    if budget is None:
        budget = [200_000]
    budget[0] -= 1
    if budget[0] < 0 or depth > 64:
        raise ValueError("replay structure limit")
    if isinstance(value, list):
        return [_sanitize(v, depth + 1, budget) for v in value]
    if isinstance(value, dict):
        attrs = value.get("attributes")
        private = isinstance(attrs, dict) and ("data-private" in attrs or "data-no-analytics" in attrs or "rr-block" in str(attrs.get("class", "")).split() or attrs.get("contenteditable") in ("", "true", True))
        tag = str(value.get("tagName", "")).lower()
        blocked = tag in ("script", "iframe", "form")
        if private or blocked:
            # rrweb NodeType.Element is 2; 1 is DocumentType and cannot be
            # inserted under HTML/head/body. Keep mirror/document identity.
            placeholder = {"type": 2, "id": value.get("id"), "tagName": "div",
                           "attributes": {"class": "rr-block"}, "childNodes": []}
            if "rootId" in value:
                placeholder["rootId"] = _sanitize(value["rootId"], depth + 1, budget)
            return placeholder
        result = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("invalid replay key")
            if key in ("value", "placeholder", "data-user-id", "data-email", "password", "token"):
                result[key] = MASK
            elif key == "childNodes" and tag in ("input", "textarea"):
                result[key] = []
            elif key == "xlink:href" and _local_svg_ref(item):
                result[key] = item
            elif key in ("href", "src", "action", "formaction", "url", "referrer", "poster", "xlink:href"):
                result[key] = public_url(item)
            elif key == "srcset" and isinstance(item, str):
                candidates = []
                for candidate in item.split(",")[:100]:
                    pieces = candidate.strip().split()
                    if pieces and (url := public_url(pieces[0])):
                        descriptor = pieces[1] if len(pieces) > 1 and re.fullmatch(r"\d+(?:\.\d+)?[wx]", pieces[1]) else ""
                        candidates.append((url + " " + descriptor).strip())
                result[key] = ", ".join(candidates)
            elif key in ("style", "_cssText", "fill", "stroke", "clip-path", "mask", "filter", "marker-start", "marker-mid", "marker-end") and isinstance(item, str):
                result[key] = _css(item)
            elif key.startswith("on") or (key.startswith("data-") and key not in ("data-block", "data-analytics-overlay", "data-fe-interaction", "data-fe-interaction-action")):
                result[key] = MASK
            elif key in ("textContent", "text", "visible_text", "title", "aria-label", "id", "name") and isinstance(item, str):
                result[key] = _redact(item, MAX_BATCH_BYTES)
            else:
                result[key] = _sanitize(item, depth + 1, budget)
        # IncrementalSource.Input. A forged/non-masked client event cannot
        # smuggle a field value into the admin player through data.text.
        if value.get("source") == 5 and "text" in result:
            result["text"] = MASK
        return result
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("nonfinite replay value")
    if isinstance(value, str):
        value.encode("utf-8")
    return value


def _inflate(part, remaining):
    size = part.raw_bytes
    if not isinstance(size, int) or isinstance(size, bool) or not 0 < size <= MAX_FRAGMENT_BYTES or size > remaining:
        raise ValueError("fragment size limit")
    decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
    raw = decoder.decompress(part.payload_gzip, min(MAX_FRAGMENT_BYTES, remaining) + 1)
    if len(raw) != size or not decoder.eof or decoder.unconsumed_tail or decoder.unused_data:
        raise ValueError("invalid compressed fragment")
    if hashlib.sha256(raw).hexdigest() != part.payload_hash:
        raise ValueError("fragment checksum mismatch")
    return raw


def _batch(parts, remaining):
    pieces = []
    size = 0
    for part in parts:
        raw = _inflate(part, remaining - size)
        size += len(raw)
        if size > MAX_BATCH_BYTES:
            raise ValueError("batch size limit")
        pieces.append(raw)
    payload = json.loads(b"".join(pieces), parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite JSON")))
    if not isinstance(payload, dict):
        raise ValueError("invalid payload")
    events = payload.get("events", [])
    states = payload.get("states", [])
    dropped = payload.get("dropped", 0)
    if not isinstance(events, list) or len(events) > 10_000 or not isinstance(states, list) or len(states) > 200:
        raise ValueError("invalid arrays")
    if not isinstance(dropped, int) or isinstance(dropped, bool) or not 0 <= dropped <= 10_000_000:
        raise ValueError("invalid loss counter")
    for event in events:
        if not isinstance(event, dict) or not _finite(event.get("timestamp")):
            raise ValueError("invalid event time")
        if not isinstance(event.get("type"), int) or isinstance(event["type"], bool) or not 0 <= event["type"] <= 6:
            raise ValueError("invalid event type")
        if event["type"] == 2 and not isinstance((event.get("data") or {}).get("node"), dict):
            raise ValueError("invalid full snapshot")
    return _sanitize(events), states, dropped, size


def _state(state, page, recording_id):
    if not isinstance(state, dict) or not isinstance(state.get("state_id"), str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", state["state_id"]):
        raise ValueError("invalid state")
    timestamp = state.get("original_timestamp_ms", state.get("original_time_ms"))
    if not _finite(timestamp):
        raise ValueError("invalid state time")
    viewport = state.get("viewport", {})
    viewport = {k: viewport.get(k) for k in ("w", "h")} if isinstance(viewport, dict) else {}
    viewport = {k: v for k, v in viewport.items() if _finite(v) and 0 < v <= 20_000}
    boxes = state.get("boxes", [])
    if not isinstance(boxes, list):
        raise ValueError("invalid boxes")
    safe_boxes = []
    for box in boxes[:80]:
        if not isinstance(box, dict):
            continue
        item = {k: box[k] for k in ("x", "y", "w", "h") if isinstance(box.get(k), (int, float)) and not isinstance(box[k], bool) and math.isfinite(box[k]) and abs(box[k]) <= 100_000}
        item.update(text=_redact(box.get("text"), 500), tag=_redact(box.get("tag"), 30), block=_redact(box.get("block"), 80))
        safe_boxes.append(item)
    return {"state_id": state["state_id"], "original_timestamp_ms": timestamp, "original_time_ms": timestamp,
            "page": public_page(state.get("page", page)), "visible_text": _redact(state.get("visible_text")),
            "viewport": viewport, "overlay": state.get("overlay") is True, "boxes": safe_boxes,
            "source": "dom_snapshot", "replay_id": recording_id}


def assemble_recordings(rows: list[Any]) -> dict:
    selected, reserved, invalid_metadata = [], 0, 0
    byte_limited = False
    for row in rows[:MAX_READ_ROWS]:
        raw = getattr(row, "raw_bytes", None)
        stored = len(row.payload_gzip)
        if not isinstance(raw, int) or isinstance(raw, bool) or not 0 < raw <= MAX_FRAGMENT_BYTES or not 0 < stored <= raw + 256:
            invalid_metadata += 1
            continue
        cost = max(raw, stored)
        if reserved + cost > MAX_READ_BYTES:
            byte_limited = True
            break
        reserved += cost
        selected.append(row)
    grouped = defaultdict(lambda: defaultdict(list))
    for row in selected:
        grouped[row.recording_id][row.sequence].append(row)
    recordings, gaps, states = [], [], []
    digest = hashlib.sha256()
    count = snapshots = duration = consumed = omitted_gaps = 0

    def gap(value):
        nonlocal omitted_gaps
        if len(gaps) < MAX_GAPS:
            gaps.append(value)
        else:
            omitted_gaps += 1

    if not rows:
        gap({"reason": "not_captured_or_expired"})
    if len(rows) > MAX_READ_ROWS:
        gap({"reason": "server_read_row_limit"})
    if byte_limited:
        gap({"reason": "server_read_byte_limit"})
    if invalid_metadata:
        gap({"reason": "invalid_fragment_metadata", "count": invalid_metadata})
    for recording_id, sequences in sorted(grouped.items()):
        events, page_states = [], []
        ended = False
        dropped = expected = 0
        for sequence, fragments in sorted(sequences.items()):
            if sequence != expected:
                gap({"recording_id": recording_id, "reason": "missing_sequence", "from_sequence": expected, "to_sequence": sequence - 1})
            expected = sequence + 1
            parts = sorted(fragments, key=lambda r: r.part)
            for part in parts:
                digest.update(f"{recording_id}:{sequence}:{part.part}:{part.payload_hash}".encode())
            if not parts or not 1 <= parts[0].parts <= 2000 or [p.part for p in parts] != list(range(parts[0].parts)):
                gap({"recording_id": recording_id, "sequence": sequence, "reason": "missing_fragment"})
                continue
            if any(p.parts != parts[0].parts or p.ended != parts[0].ended for p in parts):
                gap({"recording_id": recording_id, "sequence": sequence, "reason": "inconsistent_fragment_metadata"})
                continue
            try:
                page = public_page(parts[0].page)
                batch, batch_states, lost, size = _batch(parts, MAX_READ_BYTES - consumed)
                safe_states = [_state(state, page, recording_id) for state in batch_states]
            except (ValueError, TypeError, AttributeError, OSError, UnicodeError, RecursionError, zlib.error):
                gap({"recording_id": recording_id, "sequence": sequence, "reason": "invalid_payload"})
                continue
            consumed += size
            events.extend(batch)
            page_states.extend(safe_states)
            dropped += lost
            if parts[0].ended:
                ended = sequence == max(sequences)
                if not ended:
                    gap({"recording_id": recording_id, "sequence": sequence, "reason": "events_after_end"})
        events.sort(key=lambda e: e["timestamp"])
        full = sum(e["type"] == 2 for e in events)
        if not full:
            gap({"recording_id": recording_id, "reason": "missing_full_snapshot"})
        if not ended:
            gap({"recording_id": recording_id, "reason": "end_not_received"})
        if dropped:
            gap({"recording_id": recording_id, "reason": "client_dropped_events", "count": dropped})
        count += len(events)
        snapshots += full
        times = [e["timestamp"] for e in events] + [s["original_timestamp_ms"] for s in page_states]
        start, end = (min(times), max(times)) if times else (None, None)
        span = end - start if times else 0
        states.extend(page_states)
        recordings.append({"recording_id": recording_id, "page": public_url(next(iter(sequences.values()))[0].page),
                           "events": events, "ended": ended, "duration_ms": span, "full_snapshots": full,
                           "original_start_ms": start, "original_end_ms": end})
    recordings.sort(key=lambda r: (r["original_start_ms"] if r["original_start_ms"] is not None else math.inf, r["recording_id"]))
    starts = [r["original_start_ms"] for r in recordings if r["original_start_ms"] is not None]
    ends = [r["original_end_ms"] for r in recordings if r["original_end_ms"] is not None]
    original_start, original_end = (min(starts), max(ends)) if starts else (None, None)
    duration = original_end - original_start if starts else 0
    for recording in recordings:
        recording["timeline_start_ms"] = recording["original_start_ms"] - original_start if recording["original_start_ms"] is not None else None
    states.sort(key=lambda s: s["original_timestamp_ms"])
    if len(states) > MAX_DOM_STATES:
        gap({"reason": "dom_state_read_limit", "count": len(states) - MAX_DOM_STATES})
    if omitted_gaps:
        gaps.append({"reason": "additional_gaps", "count": omitted_gaps})
    return {"recordings": recordings, "chunk_count": len(selected), "event_count": count,
            "full_snapshot_count": snapshots, "gaps": gaps, "incomplete": bool(gaps),
            "original_duration_ms": duration, "fingerprint": digest.hexdigest(), "read_bytes": reserved,
            "original_start_ms": original_start, "original_end_ms": original_end,
            "source_clock": {"kind": "client_epoch_ms", "server_calibration": "not_performed", "bounds": "captured_event_and_dom_state_timestamps"},
            "dom_states": states[:MAX_DOM_STATES], "dom_state_count": len(states),
            "dom_states_returned_count": min(len(states), MAX_DOM_STATES),
            "dom_states_complete": len(states) <= MAX_DOM_STATES and not bool(gaps),
            "pixel_reviewed": False, "pixel_complete": False,
            "fidelity_limitations": list(FIDELITY_LIMITATIONS)}


async def load_session_replay(db, session_id_hash: str) -> dict:
    scope = SessionReplayChunk.session_id_hash == session_id_hash
    metadata = (await db.execute(select(SessionReplayChunk.id, SessionReplayChunk.raw_bytes,
                                      func.length(SessionReplayChunk.payload_gzip).label("stored_bytes"))
        .where(scope).order_by(SessionReplayChunk.recording_id, SessionReplayChunk.sequence, SessionReplayChunk.part)
        .limit(MAX_READ_ROWS + 1))).mappings().all()
    ids, used, read_gaps = [], 0, []
    if len(metadata) > MAX_READ_ROWS:
        read_gaps.append({"reason": "server_read_row_limit"})
    for row in metadata[:MAX_READ_ROWS]:
        raw, stored = row["raw_bytes"], row["stored_bytes"]
        if not isinstance(raw, int) or not 0 < raw <= MAX_FRAGMENT_BYTES or not isinstance(stored, int) or not 0 < stored <= raw + 256:
            read_gaps.append({"reason": "invalid_fragment_metadata"})
            continue
        cost = max(raw, stored)
        if used + cost > MAX_READ_BYTES:
            read_gaps.append({"reason": "server_read_byte_limit"})
            break
        ids.append(row["id"])
        used += cost
    rows = []
    if ids:
        stream = await db.stream(select(SessionReplayChunk).where(SessionReplayChunk.id.in_(ids))
            .order_by(SessionReplayChunk.recording_id, SessionReplayChunk.sequence, SessionReplayChunk.part)
            .execution_options(yield_per=32))
        async for row in stream.scalars():
            rows.append(row)
    result = assemble_recordings(rows)
    result["gaps"].extend(read_gaps[:MAX_GAPS])
    if len(read_gaps) > MAX_GAPS:
        result["gaps"].append({"reason": "additional_gaps", "count": len(read_gaps) - MAX_GAPS})
    result["incomplete"] = bool(result["gaps"])
    result["dom_states_complete"] = result["dom_states_complete"] and not result["incomplete"]
    if metadata and not rows:
        result["gaps"] = [g for g in result["gaps"] if g["reason"] != "not_captured_or_expired"]
    return result


async def analysis_replay_context(db, session_id_hash: str) -> dict:
    result = await load_session_replay(db, session_id_hash)
    result.pop("recordings", None)
    return result
