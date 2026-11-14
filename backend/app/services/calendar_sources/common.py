from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EconomicEvent, Indicator

logger = logging.getLogger(__name__)


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


# Источники, которые отдают полный список своих событий на окно: если событие источника исчезло
# из свежего ответа, его больше нет в официальном графике. Условие отбирает сохранённые строки
# этого источника (в том числе записанные до появления поля ``feed``).
def _feed_row_conditions(feed: str) -> list:
    if feed == "cbr_key_rate":
        return [
            EconomicEvent.source == "cbr",
            or_(
                EconomicEvent.event_key.like("cbr:key-rate-decision:%"),
                EconomicEvent.event_key.like("cbr:key-rate-summary:%"),
            ),
        ]
    if feed == "cbr_ics":
        return [
            EconomicEvent.source == "cbr",
            EconomicEvent.date_confidence == "official_explicit",
            ~EconomicEvent.event_key.like("cbr:key-rate-%"),
        ]
    if feed == "rosstat_plan":
        return [
            EconomicEvent.source == "rosstat",
            EconomicEvent.event_key.like("rosstat:plan:%"),
        ]
    if feed == "rosstat_oper":
        return [
            EconomicEvent.source == "rosstat",
            EconomicEvent.event_key.like("rosstat:sep:%"),
        ]
    raise ValueError(f"Unknown calendar feed: {feed}")


async def sweep_unseen_feed_events(
    db: AsyncSession,
    *,
    feed: str,
    seen_keys: set[str],
    start: date,
    end: date,
) -> list[str]:
    """Удалить события источника в окне [start, end], которых нет в его свежем ответе.

    Вызывается только после удачного чтения источника. Событие с фактом из нашей загрузки
    (``actual_value``) не трогается: это уже история выхода, а не обещание даты.
    14.11.2026: резюме ЦБ 04.11 оставалось на сайте после того, как ЦБ поставил его на 05.11.
    """
    rows = (await db.execute(
        select(EconomicEvent).where(
            *_feed_row_conditions(feed),
            EconomicEvent.scheduled_date >= start,
            EconomicEvent.scheduled_date <= end,
            or_(EconomicEvent.actual_value.is_(None), EconomicEvent.actual_value == ""),
        )
    )).scalars().all()
    removed: list[str] = []
    for row in rows:
        if row.event_key in seen_keys:
            continue
        removed.append(f"{row.event_key}@{row.scheduled_date}")
        await db.delete(row)
    if removed:
        await db.commit()
        logger.info("Calendar: %s dropped %d event(s) no longer in the source: %s",
                    feed, len(removed), ", ".join(removed[:10]))
    return removed


async def prune_legacy_keyless_estimates(db: AsyncSession) -> int:
    """Удалить старые скрытые оценки дат без ключа (до перехода на официальные источники).

    Их не показывает ни сайт, ни .ics: публичные условия требуют ключ и источник. Но они
    занимали естественный ключ базы (14.11.2026: ИПЦ не мог переехать на 25.11) и попадали
    в ответы ботов. Строки с фактом выхода не трогаются.
    """
    rows = (await db.execute(
        select(EconomicEvent).where(
            EconomicEvent.event_key.is_(None),
            EconomicEvent.is_estimated.is_(True),
            or_(EconomicEvent.actual_value.is_(None), EconomicEvent.actual_value == ""),
        )
    )).scalars().all()
    for row in rows:
        await db.delete(row)
    if rows:
        await db.commit()
        logger.info("Calendar: pruned %d legacy keyless estimated rows", len(rows))
    return len(rows)


async def repair_legacy_cbr_ics_times(db: AsyncSession) -> int:
    """Перевести в московское время строки файла ЦБ, записанные до 14.11.2026 временем UTC.

    Свежие строки окна обновления переписывает сам проход; эта правка нужна для истории
    (события старше двух недель проход не трогает). Строка помечается ``time_zone: msk``,
    поэтому повторный запуск ничего не сдвигает.
    """
    from datetime import datetime as _dt
    from datetime import timedelta as _td

    rows = (await db.execute(
        select(EconomicEvent).where(
            EconomicEvent.source == "cbr",
            EconomicEvent.date_confidence == "official_explicit",
            ~EconomicEvent.event_key.like("cbr:key-rate-%"),
            EconomicEvent.scheduled_time.is_not(None),
        )
    )).scalars().all()
    fixed = 0
    for row in rows:
        meta = dict(row.metadata_json or {})
        details = (meta.get("provenance") or {}).get("details") or {}
        if meta.get("time_zone") == "msk" or details.get("feed") == "cbr_ics":
            continue
        try:
            moment = _dt.strptime(f"{row.scheduled_date.isoformat()} {row.scheduled_time}", "%Y-%m-%d %H:%M")
        except ValueError:
            continue
        moment += _td(hours=3)
        if moment.date() != row.scheduled_date:
            continue  # переход через полночь меняет дату — такую строку обновит сам проход
        row.scheduled_time = moment.strftime("%H:%M")
        meta["time_zone"] = "msk"
        row.metadata_json = meta
        fixed += 1
    if fixed:
        await db.commit()
        logger.info("Calendar: %d CBR events moved from UTC to Moscow time", fixed)
    return fixed


async def upsert_calendar_candidates(db: AsyncSession, candidates: list[CalendarCandidate]) -> int:
    """Upsert official calendar events by stable event_key, auditing date moves.

    Каждое событие пишется в своей точке сохранения. 13.11.2026 одно событие встало на дату, где у того же
    показателя уже стояло другое (`uq_event_natural_key`: источник, тип, дата, показатель), и ошибка одной строки
    отменила обновление всего календаря на сутки. Теперь такое событие пропускается с записью в журнал, остальные
    сохраняются.
    """
    code_to_id = await resolve_indicator_ids(db)
    fetched_at = now_naive_utc()
    changed = 0
    skipped: list[str] = []

    run_keys = {(c.source, c.event_type, c.event_key) for c in candidates}
    for candidate in candidates:
        if candidate.date_confidence not in (*OFFICIAL_CONFIDENCES, "estimated"):
            raise ValueError(f"Unsupported calendar confidence: {candidate.date_confidence}")
        try:
            async with db.begin_nested():
                await _clear_stale_blocker(db, candidate, code_to_id, run_keys)
                delta = await _apply_candidate(db, candidate, code_to_id, fetched_at)
                await db.flush()
            changed += delta
        except IntegrityError as exc:
            skipped.append(f"{candidate.source}/{candidate.event_key}@{candidate.scheduled_date}")
            logger.warning(
                "Calendar: event %s/%s on %s skipped, it collides with a stored event: %s",
                candidate.source, candidate.event_key, candidate.scheduled_date, str(exc.orig)[:200],
            )

    await db.commit()
    if skipped:
        logger.warning("Calendar: %d colliding event(s) skipped: %s", len(skipped), ", ".join(skipped[:10]))
    return changed


async def _clear_stale_blocker(
    db: AsyncSession,
    candidate: CalendarCandidate,
    code_to_id: dict[str, int],
    run_keys: set[tuple[str, str, str]],
) -> None:
    """Освободить дату, если её занимает устаревшая строка того же показателя.

    Естественный ключ базы — (источник, тип, дата, показатель). Когда официальная дата
    переезжает на день, где лежит старая строка с другим ключом (прежняя оценка по правилу,
    выпуск из прошлой версии графика), перенос падал на уникальности и событие оставалось на
    старой дате. Мешающая строка удаляется, если её нет среди событий текущего прохода, у неё
    нет факта выхода и она не точнее кандидата. Иначе это настоящий конфликт — пропуск с записью.
    14.11.2026: ИПЦ за октябрь с 01.11 не мог переехать с 13.11 на 25.11 — 25.11 занимала скрытая
    строка-оценка без ключа (cpi, 2026-11-25), а остальные срезы ИПЦ переехали.
    """
    indicator_id = code_to_id.get(candidate.indicator_code) if candidate.indicator_code else None
    if indicator_id is None:
        return
    blockers = (await db.execute(
        select(EconomicEvent).where(
            EconomicEvent.source == candidate.source,
            EconomicEvent.event_type == candidate.event_type,
            EconomicEvent.scheduled_date == candidate.scheduled_date,
            EconomicEvent.indicator_id == indicator_id,
            # Старые строки-оценки лежат без ключа (NULL): «!=» их не видит.
            or_(EconomicEvent.event_key.is_(None), EconomicEvent.event_key != candidate.event_key),
        )
    )).scalars().all()
    for blocker in blockers:
        if (blocker.source, blocker.event_type, blocker.event_key) in run_keys:
            continue
        if blocker.actual_value not in (None, ""):
            continue
        # Мешает только менее точная строка: оценка, правило или старая строка без ключа.
        # Две официальные даты одного показателя в один день — настоящий конфликт, его не решаем удалением.
        if blocker.date_confidence == "official_explicit" and blocker.event_key:
            continue
        # Строка с ключом кандидата где-то ещё есть? Тогда мешающая — чужой остаток, удаляем;
        # если строки с ключом кандидата нет, _find_existing_event сама подхватит мешающую
        # по естественному ключу и перепишет её — удалять не нужно.
        same_key = (await db.execute(
            select(EconomicEvent.id).where(
                EconomicEvent.source == candidate.source,
                EconomicEvent.event_type == candidate.event_type,
                EconomicEvent.event_key == candidate.event_key,
            )
        )).first()
        if same_key is None:
            continue
        logger.info(
            "Calendar: removing stale %s/%s on %s to make room for %s",
            blocker.source, blocker.event_key, blocker.scheduled_date, candidate.event_key,
        )
        await db.delete(blocker)
        await db.flush()


async def _apply_candidate(
    db: AsyncSession,
    candidate: CalendarCandidate,
    code_to_id: dict[str, int],
    fetched_at: datetime,
) -> int:
    """Записать одно событие; 1, если оно создано или изменено."""
    indicator_id = code_to_id.get(candidate.indicator_code) if candidate.indicator_code else None
    existing = await _find_existing_event(db, candidate, indicator_id)
    # A temporary plan-fetch failure must never erase a previously verified
    # date through the natural-key fallback or a lower-confidence refresh.
    if (existing is not None and existing.date_confidence == "official_explicit"
            and candidate.date_confidence != "official_explicit"):
        return 0
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

    # Preserve early-release enrichment: if IndicatorData already filled
    # actual_value, do not downgrade status back to scheduled on sync.
    if existing is not None and (existing.actual_value is not None and existing.actual_value != ""):
        status = "released"
    else:
        status = "scheduled"

    if existing is None:
        db.add(EconomicEvent(
            title=candidate.title,
            title_en=candidate.title_en,
            event_type=candidate.event_type,
            source=candidate.source,
            indicator_id=indicator_id,
            scheduled_date=candidate.scheduled_date,
            scheduled_time=candidate.scheduled_time,
            is_estimated=candidate.date_confidence == "estimated",
            reference_period=candidate.reference_period,
            importance=candidate.importance,
            status=status,
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
        return 1

    before = (
        existing.scheduled_date,
        existing.scheduled_time,
        existing.title,
        existing.source_hash,
        existing.event_key,
        existing.status,
        existing.source_url,
    )
    existing.title = candidate.title
    existing.title_en = candidate.title_en
    existing.event_type = candidate.event_type
    existing.source = candidate.source
    existing.indicator_id = indicator_id
    existing.scheduled_date = candidate.scheduled_date
    existing.scheduled_time = candidate.scheduled_time
    existing.is_estimated = candidate.date_confidence == "estimated"
    existing.reference_period = candidate.reference_period
    existing.importance = candidate.importance
    existing.status = status
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
        existing.status,
        existing.source_url,
    )
    return int(before != after)


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
