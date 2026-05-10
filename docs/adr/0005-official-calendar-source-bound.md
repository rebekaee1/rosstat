# ADR 0005 — Calendar dates must be source-bound

- **Date:** 2026-05-10
- **Status:** Accepted
- **Last verified:** 2026-05-10 (`backend/tests/test_calendar_seed.py`: CPI April 2026 -> 2026-05-15, CPI family same official release, CBR daily working-day rules, CBR ICS fixture/multi-indicator mapping, CBR key-rate meeting/summary, Minfin 14th working day incl. deficit, reschedule audit, public source-bound guard).
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

Каждое public-событие обязано иметь stable `event_key`, `source_url`, `source_hash`, `last_seen_at`, `date_confidence`, provenance в `metadata_json`. Миграционный backfill со статусом `official_explicit`, но без этих полей, не считается public-событием. Перенос даты обновляет текущую запись по `event_key`; старая дата сохраняется в `metadata_json.reschedule_audit`.

## Implementation shape

1. `calendar_sources.common.CalendarCandidate` — нормализованный event-кандидат.
2. `upsert_calendar_candidates()` — upsert по `(source, event_type, event_key)`, fallback-update существующей old natural-key строки, audit reschedule.
3. `calendar_sources.official_calendar`:
   - CBR: official `indcalendar` daily rules (FX/RUONIA/gold), official `indcalendar` + `vCalendar.ics` (резервы, M0/M1/M2, кредиты/депозиты, ставки, ипотека, внешний сектор, долг) + official monetary-policy schedule `cbr.ru/dkp/cal_mp/` (заседания и резюме по ключевой ставке).
   - Rosstat: rule engine + `ru_working_calendar`.
   - Minfin: official schedule rule (`14-й рабочий день` для budget events).
4. `calendar_seed.seed_calendar()` теперь вызывает official ingest. Legacy estimated builders остаются только для debug/tests старого генератора.
5. Public API фильтрует source-bound rows: `date_confidence IN ('official_explicit', 'official_rule')`, `is_estimated = false`, `event_key/source_url/source_hash/last_seen_at IS NOT NULL`.

## Consequences

Positive:

- Public calendar перестаёт врать датами.
- Переносы источников становятся update, не дублями.
- У каждого события есть source/provenance для аудита.

Trade-off:

- Первый rollout может уменьшить число событий. Это принято: неполный календарь лучше случайной даты.
- Для `official_rule` нужен ежегодный `ru_working_calendar` с source_url на официальный документ. Без календаря года rule-events на этот год не генерируются.
- CBR/Minfin/Rosstat site markup может ломаться; при падении parser сохраняем последние official rows, алертим логами, estimated не публикуем.

## Subsequent additions (after acceptance)

### 2026-05-10 — Coverage expansion without estimates

Calendar ingest расширен только source-bound способами:

- CBR daily official-rule events: `usd-rub`, `eur-rub`, `cny-rub`, `gold-price`, `ruonia` по official `indcalendar` + versioned Russian working calendar.
- CBR official ICS mapping: M0/M1/M2, reserves, credits/deposits, credit/deposit rates, mortgage, goods/services trade, current account, external debt, FDI.
- Minfin: `budget-deficit` добавлен к тому же official 14th-working-day release, что `budget-revenue`/`budget-expenditure`.
- Rosstat: CPI components (`cpi-food`, `cpi-nonfood`, `cpi-services`) добавлены к same official CPI release/rule.

Local verification after refresh: 1208 public source-bound events, 46/76 source codes covered, `bad_public_rows=0`. Не покрыты заранее: `auto-loan-rate` (нет найденного official calendar row в CBR ICS на текущем horizon) и Rosstat annual/irregular groups без доказанного forward-rule/announcement row.
