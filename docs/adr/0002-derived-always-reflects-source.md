# ADR 0002 — Derived series always reflect current source state

- **Date:** 2026-05-05
- **Status:** Accepted
- **Last verified:** 2026-05-22 (документация-ревизия: 31 derived в `DERIVED_SPECS`; инвариант `bulk_upsert` — `INSERT … ON CONFLICT DO UPDATE WHERE data_points.value <> excluded.value` — стабилен в `backend/app/services/upsert.py::bulk_upsert`; тестами покрыто в `backend/tests/test_upsert.py` через empty list / None value / partial / mixed cases (закрытие E1 из звонка 2026-05-21)).
- **Author:** architecture grilling session (улучшение архитектуры по запросу пользователя).
- **Supersedes:** ad-hoc behaviour of `CalculationEngine.run_for_updated_sources` prior to this change.
- **Part of:** [`../../CONTEXT.md`](../../CONTEXT.md) (раздел `Derived indicator` + «Pure-revision day» trap).
- **Related:** [ADR-0001](0001-derived-indicators-engine-shape.md) (engine shape). Идемпотентность реальных парсеров (CBR / Минфин / Rosstat) — в их docstrings, см. `backend/app/services/*_parser.py`.
- **Code anchors:** `backend/app/services/upsert.py::bulk_upsert`, `backend/app/tasks/scheduler.py::_indicator_had_new`.

## Context

`CalculationEngine.run_for_updated_sources(db, source_codes)` previously only recomputed derived series whose `src_codes` intersected `source_codes`. The list `source_codes` came from the daily ETL scheduler and contained only those parsers whose `fetch_log.records_added > 0` for that batch (`backend/app/tasks/scheduler.py:55`).

That detector treats *new rows* as the only signal of "this source updated". When Rosstat or CBR **revises** an existing point (a routine event — например, quarterly GDP revisions backfilling 2–3 years of values), the parser does an upsert: новых строк не добавилось, существующие были перезаписаны. Старая dispatch-логика возвращала `False`, источник не попадал в `source_codes`, и фильтр внутри `run_for_updated_sources` пропускал каждый derived, который от него зависит.

Consequence: derived series silently drifted from their sources. A snapshot diff against the production API on 2026-05-05 found 18 stale derived points across 4 series:

- `gdp-yoy`: 15 historical values diverged from the formula applied to current `gdp-nominal`, plus a missing point for `2025-12-01`.
- `gdp-qoq`: 15 historical values + missing `2025-12-01`.
- `unemployment-annual`: `2018-04-01` (5.0 in DB; should be 5.1).
- `current-account-yoy`: missing `2014-10-01` and `2018-10-01` — both have valid `t-1y` partners now, but historically didn't.

These are not formula bugs. They are dispatch bugs: the pure operations themselves produce identical values to legacy (verified by `verify_refactor.py` against a 23-series prod snapshot — 0 diffs at the formula level on every code where `gdp-nominal` and `unemployment` weren't revised).

## Decision

`CalculationEngine.run_for_updated_sources(db, source_codes)` is redefined:

> If `source_codes` is empty, do nothing. Otherwise, recompute **every** registered derived series end-to-end (full history), regardless of which source codes appear in `source_codes`. `source_codes` is retained only as a short-circuit on no-op ETL batches.

Inside `_execute(db, spec)` each derived is rebuilt by loading the entire source series and running the pure op. `bulk_upsert` writes only points whose value actually differs (`upsert.py:upsert_indicator_data` ставит `ON CONFLICT DO UPDATE … WHERE value != excluded.value`), так что cost is bounded — каждый daily ETL платит at most 28 × `bulk_upsert` calls, и большинство — no-op.

### The actual invariant

Точная формулировка инварианта:

> **Если в этот ETL-батч хотя бы один парсер добавил новые строки** (`fetch_log.records_added > 0`), все 28 derived пересчитываются end-to-end от первой до последней точки. Любая ревизия (in-place upsert старых значений) одного из источников будет подхвачена этим пересчётом, потому что фильтра «по конкретному src_code» больше нет.

Что это **не** гарантирует:

- **Pure-revision day** — день, когда **ни один** парсер не добавил новые строки, но какой-то парсер ревизовал старые. В таком случае `updated_codes` остаётся пустым, scheduler не вызывает `run_for_updated_sources`, и derived остаются stale до следующего «обычного» дня. Это known limitation. Mitigation: ежедневный ETL-батч включает CBR daily-серии (`usd-rub`, `eur-rub`, `cny-rub`, `key-rate`, `ruonia`, `gold-price`), которые на каждый рабочий день публикуют новые строки. На практике pure-revision day без хотя бы одного `records_added > 0` — крайне редкое явление; оно мaскируется на следующий же рабочий день.
- **Manual SQL corrections** to source rows вне ETL — не триггерят пересчёт. Используется `scripts/rebuild-all-derived.py` (см. ниже).

### One-shot catchup

A standalone CLI `scripts/rebuild-all-derived.py` calls `_execute` for every spec without the empty-batch guard. It is the operator's tool for:

- previewing changes locally before deploying calc-engine changes;
- re-syncing derived after manual SQL corrections to source;
- закрытия pure-revision-day drift, если он накопится;
- closing historical drift when needed.

It is **not** part of the production loop. The daily ETL by itself, after this ADR, keeps derived in sync **on days with at least one `records_added > 0`** (см. limit выше).

### What is *not* changed

- The `Indicator` table, `IndicatorData`, public API, frontend, parsers — none of these touch.
- Pure operations in `derived_ops.py` — unchanged. The shape was set by ADR-0001.
- `_derived` registry shape and external API of `CalculationEngine.register / register_spec` — unchanged.
- `forecast_pipeline._propagate_cpi_forecast_to_derived` — out of scope. Forecasts and derived-historical are different layers; this ADR doesn't touch forecast propagation. (После ADR-0001 + дальнейших шагов forecast-каскад вынесен в реестр `forecast_strategies/derived_from_source.py` — отдельный механизм поверх forecast-слоя, не пересекается с derived-historical.)

## Consequences

### Positive

- **Locality.** The semantic «derived[t] always reflects source[t] **for source-state observed at the most recent ETL day with new rows**» lives in one module, `calculation_engine`. No more split between scheduler and engine on what «source updated» means.
- **Self-healing on revisions** — но с уточнением: пересчёт срабатывает в тот же день, когда хотя бы один парсер вернул новые строки. Если ревизуется источник, который сам в этот день не добавил новых строк, derived всё равно подхватится — потому что dispatch loop теперь идёт по всем spec'ам, а не фильтрует по `src_code`.
- **Idempotent.** Running `_execute` N times on unchanged source produces zero writes. The dispatch loop is safe to re-trigger.
- **Cheap.** Daily cost: 28 derived × ~140–410 points × `bulk_upsert` no-op upsert. Measured locally: ~2 seconds total against the dev database.

### Negative

- **No silent skip on partial ETL.** Если только один парсер сегодня отработал (например, ad-hoc trigger на `cpi`) и другие 75 источников unchanged — все 28 derived всё равно будут пересчитаны. Cost is bounded but it's strictly more work than the old filtered dispatch.
- **One-time UI shift on first deploy.** The first prod ETL after this ADR will close the existing 18-point drift. Affected indicators (gdp-yoy, gdp-qoq, unemployment-annual, current-account-yoy) will show updated values. These are *correct* values per the existing formulas — no formula changes, no methodology changes. Magnitude of shift on gdp-yoy is ±0.6–0.8 п.п. on 15 historical dates.

### Limit of the invariant — orphan derived points

Инвариант **односторонний**: `bulk_upsert` only inserts/updates, never deletes. Если source-точка **удаляется вручную** (DELETE из `IndicatorData`), corresponding derived-точка **не** auto-removed; derived for that date просто не будет переписан следующим compute pass (формула пропускает даты, где source-данные отсутствуют).

Rationale for not auto-deleting:

- 23 production parsers never delete — only upsert. There is no observed scenario where derived needs to follow a deletion.
- Любой bug в pure op (edge case, off-by-one, missing date) вызвал бы **mass deletion** derived data при `bulk_replace`-семантике. This risk is asymmetric: undetected drift is cheap to fix later; lost historical values are expensive to reconstruct.
- The remediation when a source is manually corrected is `scripts/rebuild-all-derived.py` followed by manual orphan cleanup if needed.

If future evidence shows this assumption breaking (e.g. парсер introduced that does delete points), revisit with a follow-up ADR proposing `bulk_replace` for `_execute`.

### Limit of the invariant — pure-revision day

Описано выше в «The actual invariant». Это **не** silent drift в обычном смысле: ревизия будет подхвачена в первый же следующий ETL день с `records_added > 0`. На практике это almost-always next morning. Если кто-то хочет hard guarantee «ревизия отражена в derived прямо в день ревизии» — это будет отдельный ADR с изменением scheduler-детектора (`updated_codes` должен принимать парсеров с `records_updated > 0`, что требует протаскивать второе поле через `fetch_log` или scheduler).

## Verification

1. Test `test_run_for_updated_sources_recomputes_every_derived_when_any_source_changed` — guard the dispatch contract.
2. Test `test_run_for_updated_sources_short_circuits_on_empty_batch` — guard the no-op short-circuit.
3. Locally: `docker compose exec backend python /tmp/rebuild.py` — first run prints non-zero changes for stale series; second run prints all zeros (idempotency).
4. Locally: visit `/indicator/wages-yoy`, `/indicator/cpi-food-quarterly`, `/indicator/unemployment-quarterly` after rebuild. Console clean, values render, charts plot.
5. On prod deploy: `verify_refactor.py` against the *new* state should report 0 mismatches across all 28 derived (since values now match what the formula gives on current source).

## Out of scope (future work)

- **`had_new` detector** в scheduler, который игнорирует ревизии. С этим ADR детектор остаётся релевантным как **no-op short-circuit для совсем пустых ETL-батчей** (если ни один парсер не вернул новых строк, нет смысла тратить CPU на пересчёт). Если потребуется убрать pure-revision-day limit — это отдельный ADR с изменением `BaseParser.run()` (передавать `records_added + records_updated` в `fetch_log`) и scheduler-детектора.
- **Telemetry hook**, отчитывающийся о размере drift после каждого daily ETL (например, «derived recomputation produced 0 changes today» → no drift, vs «produced 18 changes» → silent revision somewhere upstream). Полезно, но separate.
