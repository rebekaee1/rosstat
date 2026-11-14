# ADR 0005 — Calendar dates must be source-bound

- **Date:** 2026-05-10
- **Status:** Accepted
- **Last verified:** 2026-11-14 (сверка с официальными источниками и живым календарём, см. Subsequent additions 2026-11-14); ранее 2026-05-22 (документация-ревизия: invariant в коде стабилен — `app/api/calendar.py` фильтрует public events по `event_key`/`source_url`/`source_hash`/`last_seen_at` IS NOT NULL; backend/tests/test_calendar_seed.py покрывает CPI April 2026 → 2026-05-15, CPI family same official release, CBR daily working-day rules, CBR ICS fixture/multi-indicator mapping, CBR key-rate meeting/summary, Minfin 14th working day incl. deficit, reschedule audit, public source-bound guard).
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

### 2026-11-14 — Calendar keeps itself current: sources read every night, moves shown, release confirmed by our loads

Повод: руководитель владельца сказал, что календарь «не актуальный и показывает что-то не то».
Сверка боевого календаря с официальными источниками 14.11.2026 (подробности — таблица в
[data-contracts](../data-contracts.md#calendar-actuality-2026-11-14)) нашла причины в коде, а не в источниках:

- ИПЦ за октябрь Росстат перенёс с 13.11 на 25.11 (`Grafik_srochn_2026.docx`, версия от 12.11; в майской
  версии — 13.11). Срезы ИПЦ переехали, а сам `cpi` с 01.11 падал на уникальности: 25.11 занимала скрытая
  оценка без ключа (наследие rolling seed). Переноса на карточке видно не было.
- Даты заседаний ЦБ были зашиты в код только за 2026 год; три даты резюме расходились со страницей ЦБ;
  2027 год на сайте отсутствовал, хотя ЦБ его опубликовал. Производственный календарь 2027 не был загружен.
- Время файла календаря ЦБ (UTC, `...Z`) показывалось как московское: −3 часа.
- События ЦБ без отчётного периода (заседания, резервы, денежная масса, курсы) никогда не получали факта
  выхода и навсегда оставались «ориентировочно».
- Безработицы, зарплат, розницы, ввода жилья и строительства в календаре не было вовсе; предварительная
  оценка ВВП (13.11) терялась из-за аббревиатуры «ВВП».

Решение (инвариант ADR не меняется: на витрину идут только даты с provenance):

1. Официальные источники читаются каждую ночь целиком: страница `cbr.ru/dkp/cal_mp/` (`cbr_key_rate.py`,
   запасной список на случай недоступности), все годовые `Grafik_srochn_YYYY.docx`, новый документ
   `Grafic_oper_public_YYYY.doc` (`rosstat_oper_plan.py`: доклад «Социально-экономическое положение России»
   и «Краткосрочные экономические показатели»), файл ЦБ `vCalendar.ics`.
2. Источник, ответивший полным списком, становится «полным» (`complete_feeds`): его будущие события,
   исчезнувшие из ответа, удаляются (`sweep_unseen_feed_events`), события с фактом не трогаются.
3. Перенос даты — не дубль и не сбой: устаревшая менее точная строка на новой дате удаляется
   (`_clear_stale_blocker`), старые бесключевые оценки удалены (`prune_legacy_keyless_estimates`);
   API отдаёт `rescheduled_from`, карточка пишет «Перенесено с …», `.ics` повышает `SEQUENCE`.
4. Факт выхода — из нашей загрузки: события с периодом — по точке периода (не раньше чем за 7 дней до
   даты выпуска, иначе второй выпуск ВВП получал «вышло» по первому); без периода — по первой новой точке
   ряда за 4 дня после даты (`confirm_releases_from_loads`), у дневных рядов ЦБ и решений по ставке — по
   дате точки. Предварительная оценка ВВП не подтверждается из ряда (ряд пополняется на первой оценке).
5. Минфин остаётся скрытым: официальное правило «14-й рабочий день» опубликовано
   (`minfin.gov.ru/ru/statistics/schedule`), но сентябрьские данные 2026 года пришли 12.10 при дате правила
   20.10 — правило оказалось сроком «не позднее», а не датой выхода.

### 2026-11-14 (второй заход) — world releases, Minfin deadline, our forecast on the card

Решения владельца по предложениям 1–7 (через координатора): 1, 2, 3, 4 (за флагом), 5 — да;
6 (еженедельный ИИ-агент) — нет, его заменяет детерминированный сторож; 7 — зона кабинета.

- **Новый класс даты `official_deadline`.** Минфин публикует не день выхода, а срок «не позднее
  14-го рабочего дня»; такая дата публична только для `source="minfin"`, карточка пишет «Не позднее …».
  Выход раньше срока подтверждается загрузкой (`enrich_events_from_indicator_data`). Старые строки
  Минфина `official_rule` остаются скрытыми — защита от ADR 2026-09-10 не ослаблена.
- **Мировые источники** `fed`, `bea`, `eurostat` (`calendar_sources/world_calendar.py`) — только те,
  что отвечают боевому серверу (проверено 14.11.2026). BLS (403), ЕЦБ (сайт не отвечает) и FRED (рвёт
  соединения после нескольких запросов, ключа нет) не подключены: недоступный источник не показывается.
  У мировых событий нет российского показателя, поэтому поиск существующей строки по естественному
  ключу для них отключён (в один день у BEA выходят ВВП и доходы). API без `source` и SSR/sitemap месяца
  отдают только российские источники: страница — «Экономический календарь России».
- **Прогноз Forecast Economy** на будущем выпуске (`fill_event_forecasts`): одно число текущего прогноза
  ряда на отчётный период, с точностью фактов ряда; диапазон не берётся никогда (принцип 8 дизайн-системы).
- **Сторож** в утренней сводке (`calendar_digest.py`): строка только при поломке.

### 2026-09-10 — Evidence must survive scheduling and source outages

Live reconciliation with `Grafik_srochn_2026.docx` showed that the Rosstat
nth-working-day rules do not establish publication dates (August IPI: official
23 September, synthetic rule: 11 September). Rosstat and Minfin rule candidates
are now private `estimated` rows; the public guard also excludes their legacy
`official_rule` rows immediately. Documented CBR rules remain public.
The official Rosstat document parser is enabled by default and exposed through
`RUSTATS_CALENDAR_ROSSTAT_PLAN_ENABLED` in Compose.

An elapsed scheduled date never proves publication. Without a matched actual
value the API shows `awaiting_confirmation`; ingestion and the scheduler no
longer promote elapsed dates, and the scheduler repairs legacy false release
statuses. Published observations still confirm release. A lower-confidence
candidate cannot overwrite a saved explicit date when fetching the plan fails.
Source HTTP and document parsing run outside the serving event loop.

Regression coverage: `backend/tests/test_calendar_truth.py` exercises the real
list, detail, upcoming and iCal routes, ingestion, the scheduler, and preservation
of explicit dates during source outages. No calendar rows are deleted by this repair.

### 2026-05-10 — Coverage expansion without estimates

Calendar ingest расширен только source-bound способами:

- CBR daily official-rule events: `usd-rub`, `eur-rub`, `cny-rub`, `gold-price`, `ruonia` по official `indcalendar` + versioned Russian working calendar.
- CBR official ICS mapping: M0/M1/M2, reserves, credits/deposits, credit/deposit rates, mortgage, goods/services trade, current account, external debt, FDI.
- Minfin: `budget-deficit` добавлен к тому же official 14th-working-day release, что `budget-revenue`/`budget-expenditure`.
- Rosstat: CPI components (`cpi-food`, `cpi-nonfood`, `cpi-services`) добавлены к same official CPI release/rule.

Local verification after refresh: 1208 public source-bound events, 46/76 source codes covered, `bad_public_rows=0`. Не покрыты заранее: `auto-loan-rate` (нет найденного official calendar row в CBR ICS на текущем horizon) и Rosstat annual/irregular groups без доказанного forward-rule/announcement row.
