from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EconomicEvent, Indicator


OFFICIAL_CONFIDENCES = ("official_explicit", "official_rule")


@dataclass(frozen=True)
class CalendarCandidate:
    event_key: str
    title: str
    event_type: str
    source: str
    scheduled_date: date
    date_confidence: str
    importance: int
    indicator_code: str | None = None
    title_en: str | None = None
    scheduled_time: str | None = None
    reference_period: str | None = None
    description: str | None = None
    source_url: str | None = None
    source_event_uid: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def source_hash(self) -> str:
        payload = {
            "event_key": self.event_key,
            "title": self.title,
            "event_type": self.event_type,
            "source": self.source,
            "scheduled_date": self.scheduled_date.isoformat(),
            "scheduled_time": self.scheduled_time,
            "reference_period": self.reference_period,
            "date_confidence": self.date_confidence,
            "source_url": self.source_url,
            "source_event_uid": self.source_event_uid,
            "metadata": self.metadata,
        }
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def now_naive_utc() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def stable_key(*parts: object) -> str:
    return ":".join(str(p).strip().lower().replace(" ", "-") for p in parts if p is not None)


async def resolve_indicator_ids(db: AsyncSession) -> dict[str, int]:
    result = await db.execute(select(Indicator.code, Indicator.id))
    return {code: id_ for code, id_ in result.all()}


def merge_metadata(existing: dict | None, candidate: CalendarCandidate, fetched_at: datetime) -> dict:
    metadata = dict(existing or {})
    provenance = dict(metadata.get("provenance") or {})
    provenance.update({
        "date_confidence": candidate.date_confidence,
        "source_url": candidate.source_url,
        "source_event_uid": candidate.source_event_uid,
        "source_hash": candidate.source_hash(),
        "fetched_at": fetched_at.isoformat(),
    })
    if candidate.metadata:
        provenance["details"] = candidate.metadata
    metadata["provenance"] = provenance
    return metadata


def append_reschedule_audit(metadata: dict, old_date: date, new_date: date, fetched_at: datetime) -> dict:
    audit = list(metadata.get("reschedule_audit") or [])
    audit.append({
        "previous_date": old_date.isoformat(),
        "new_date": new_date.isoformat(),
        "fetched_at": fetched_at.isoformat(),
    })
    metadata["reschedule_audit"] = audit[-20:]
    return metadata


async def upsert_calendar_candidates(db: AsyncSession, candidates: list[CalendarCandidate]) -> int:
    """Upsert official calendar events by stable event_key, auditing date moves."""
    code_to_id = await resolve_indicator_ids(db)
    fetched_at = now_naive_utc()
    changed = 0

    for candidate in candidates:
        if candidate.date_confidence not in OFFICIAL_CONFIDENCES:
            raise ValueError(f"Unsupported public calendar confidence: {candidate.date_confidence}")

        indicator_id = code_to_id.get(candidate.indicator_code) if candidate.indicator_code else None
        existing = await _find_existing_event(db, candidate, indicator_id)
        metadata = merge_metadata(
            existing.metadata_json if existing else None,
            candidate,
            fetched_at,
        )
        if existing and existing.scheduled_date != candidate.scheduled_date:
            metadata = append_reschedule_audit(
                metadata,
                existing.scheduled_date,
                candidate.scheduled_date,
                fetched_at,
            )

        if existing is None:
            db.add(EconomicEvent(
                title=candidate.title,
                title_en=candidate.title_en,
                event_type=candidate.event_type,
                source=candidate.source,
                indicator_id=indicator_id,
                scheduled_date=candidate.scheduled_date,
                scheduled_time=candidate.scheduled_time,
                is_estimated=False,
                reference_period=candidate.reference_period,
                importance=candidate.importance,
                status="released" if candidate.scheduled_date < fetched_at.date() else "scheduled",
                description=candidate.description,
                source_url=candidate.source_url,
                event_key=candidate.event_key,
                date_confidence=candidate.date_confidence,
                source_event_uid=candidate.source_event_uid,
                source_hash=candidate.source_hash(),
                last_seen_at=fetched_at,
                metadata_json=metadata,
                created_at=fetched_at,
                updated_at=fetched_at,
            ))
            changed += 1
            continue

        before = (
            existing.scheduled_date,
            existing.scheduled_time,
            existing.title,
            existing.source_hash,
            existing.event_key,
        )
        existing.title = candidate.title
        existing.title_en = candidate.title_en
        existing.event_type = candidate.event_type
        existing.source = candidate.source
        existing.indicator_id = indicator_id
        existing.scheduled_date = candidate.scheduled_date
        existing.scheduled_time = candidate.scheduled_time
        existing.is_estimated = False
        existing.reference_period = candidate.reference_period
        existing.importance = candidate.importance
        existing.status = "released" if candidate.scheduled_date < fetched_at.date() else "scheduled"
        existing.description = candidate.description
        existing.source_url = candidate.source_url
        existing.event_key = candidate.event_key
        existing.date_confidence = candidate.date_confidence
        existing.source_event_uid = candidate.source_event_uid
        existing.source_hash = candidate.source_hash()
        existing.last_seen_at = fetched_at
        existing.metadata_json = metadata
        existing.updated_at = fetched_at
        after = (
            existing.scheduled_date,
            existing.scheduled_time,
            existing.title,
            existing.source_hash,
            existing.event_key,
        )
        if before != after:
            changed += 1

    await db.commit()
    return changed


async def _find_existing_event(
    db: AsyncSession,
    candidate: CalendarCandidate,
    indicator_id: int | None,
) -> EconomicEvent | None:
    by_key = await db.execute(
        select(EconomicEvent).where(
            EconomicEvent.source == candidate.source,
            EconomicEvent.event_type == candidate.event_type,
            EconomicEvent.event_key == candidate.event_key,
        )
    )
    found = by_key.scalars().first()
    if found:
        return found

    natural_conditions = [
        EconomicEvent.source == candidate.source,
        EconomicEvent.event_type == candidate.event_type,
        EconomicEvent.scheduled_date == candidate.scheduled_date,
    ]
    if indicator_id is None:
        natural_conditions.append(EconomicEvent.indicator_id.is_(None))
    else:
        natural_conditions.append(EconomicEvent.indicator_id == indicator_id)
    by_natural = await db.execute(select(EconomicEvent).where(*natural_conditions))
    return by_natural.scalars().first()
