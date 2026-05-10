# ADR 0005 — Calendar dates must be source-bound

- **Date:** 2026-05-10
- **Status:** Accepted
- **Last verified:** 2026-05-10 (`backend/tests/test_calendar_seed.py`: CPI April 2026 -> 2026-05-15, CBR ICS fixture, Minfin 14th working day, reschedule audit, public official-only confidences).
- **Part of:** [`../../CONTEXT.md`](../../CONTEXT.md) (термин `Calendar event`).
- **Related:** [ADR-0004](0004-rosstat-russian-canonical-sdds-deprecated.md) (official Russian source policy), [ADR-0002](0002-derived-always-reflects-source.md) (idempotent upsert principle).
- **Code anchors:** `backend/app/services/calendar_sources/`, `backend/app/services/calendar_seed.py`, `backend/app/api/calendar.py`, `backend/app/models.py::EconomicEvent`.

## Context

Календарь публикаций был rolling seed-ом: `typical_day`, `lag_days`, `WeeklySpec`, fixed CBR meetings. Это давало красивое 12-месячное покрытие, но даты были оценками. Инцидент 2026-05-10: Росстат анонсировал ИПЦ за апрель 2026 на 15 мая, а public calendar показывал 6 мая, потому что `cpi.typical_day = 6`.

Для аналитической платформы это недопустимо: публичный календарь не должен выдавать синтетическую дату как факт.

## Decision

Public calendar показывает только даты с provenance:

- `official_explicit` — дата пришла из официального календаря/ICS/страницы источника.
- `official_rule` — дата рассчитана из опубликованного официального правила и versioned календаря рабочих дней с `source_url`.
- `estimated` — внутренний fallback/черновик. В `/api/v1/calendar`, `/calendar/upcoming`, iCal и UI не отдаётся.

Каждое public-событие обязано иметь stable `event_key`, `source_url`, `source_hash`, `last_seen_at`, `date_confidence`, provenance в `metadata_json`. Перенос даты обновляет текущую запись по `event_key`; старая дата сохраняется в `metadata_json.reschedule_audit`.

## Implementation shape

1. `calendar_sources.common.CalendarCandidate` — нормализованный event-кандидат.
2. `upsert_calendar_candidates()` — upsert по `(source, event_type, event_key)`, fallback-update существующей old natural-key строки, audit reschedule.
3. `calendar_sources.official_calendar`:
   - CBR: official `indcalendar` + `vCalendar.ics`.
   - Rosstat: rule engine + `ru_working_calendar`.
   - Minfin: official schedule rule (`14-й рабочий день` для budget events).
4. `calendar_seed.seed_calendar()` теперь вызывает official ingest. Legacy estimated builders остаются только для debug/tests старого генератора.
5. Public API фильтрует `date_confidence IN ('official_explicit', 'official_rule')`.

## Consequences

Positive:

- Public calendar перестаёт врать датами.
- Переносы источников становятся update, не дублями.
- У каждого события есть source/provenance для аудита.

Trade-off:

- Первый rollout может уменьшить число событий. Это принято: неполный календарь лучше случайной даты.
- Для `official_rule` нужен ежегодный `ru_working_calendar` с source_url на официальный документ. Без календаря года rule-events на этот год не генерируются.
- CBR/Minfin/Rosstat site markup может ломаться; при падении parser сохраняем последние official rows, алертим логами, estimated не публикуем.
