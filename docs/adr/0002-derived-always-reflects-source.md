# ADR 0002 — Derived series always reflect current source state

- **Date:** 2026-05-05
- **Status:** Accepted
- **Author:** architecture grilling session (улучшение архитектуры по запросу пользователя)
- **Supersedes:** ad-hoc behaviour of `CalculationEngine.run_for_updated_sources` prior to this change.

## Context

`CalculationEngine.run_for_updated_sources(db, source_codes)` previously only recomputed derived series whose `src_codes` intersected `source_codes`. The list `source_codes` came from the daily ETL scheduler and contained only those parsers whose `fetch_log.records_added > 0` for that batch (`backend/app/tasks/scheduler.py:55`).

That detector treats *new rows* as the only signal of "this source updated". When Rosstat or CBR **revises** an existing point (a routine event — e.g. quarterly GDP revisions backfilling 2–3 years of values), the parser does an upsert: `records_added = 0`, `records_updated > 0`. The old detector returned `False`, the source was excluded from `source_codes`, and the dispatch filter inside `run_for_updated_sources` skipped every derived that depended on it.

Consequence: derived series silently drifted from their sources. A snapshot diff against the production API on 2026-05-05 found 18 stale derived points across 4 series:

- `gdp-yoy`: 15 historical values diverged from the formula applied to current `gdp-nominal`, plus a missing point for `2025-12-01`.
- `gdp-qoq`: 15 historical values + missing `2025-12-01`.
- `unemployment-annual`: `2018-04-01` (5.0 in DB; should be 5.1).
- `current-account-yoy`: missing `2014-10-01` and `2018-10-01` — both have valid `t-1y` partners now, but historically didn't.

These are not formula bugs. They are dispatch bugs: the pure operations themselves produce identical values to legacy (verified by `verify_refactor.py` against a 23-series prod snapshot — 0 diffs at the formula level on every code where `gdp-nominal` and `unemployment` weren't revised).

## Decision

`CalculationEngine.run_for_updated_sources(db, source_codes)` is redefined:

> If `source_codes` is empty, do nothing. Otherwise, recompute **every** registered derived series end-to-end (full history), regardless of which source codes appear in `source_codes`. `source_codes` is retained only as a short-circuit on no-op ETL batches.

Inside `_execute(db, spec)` each derived is rebuilt by loading the entire source series and running the pure op. `bulk_upsert` writes only points whose value actually differs (`WHERE value IS DISTINCT FROM excluded.value`), so cost is bounded — each daily ETL pays at most 23 × `bulk_upsert` calls, and most calls are no-op.

### One-shot catchup

A standalone CLI `scripts/rebuild-all-derived.py` calls `_execute` for every spec without the empty-batch guard. It is the operator's tool for:

- previewing changes locally before deploying calc-engine changes,
- re-syncing derived after manual SQL corrections to source,
- closing historical drift when needed.

It is **not** part of the production loop. The daily ETL by itself, after this ADR, keeps derived in sync.

### What is *not* changed

- The `Indicator` table, `IndicatorData`, public API, frontend, parsers — none of these touch.
- The 7 pure operations in `derived_ops.py` — unchanged. The shape was set by ADR-0001.
- The set of 23 registered `DerivedSpec` entries — unchanged.
- `_derived` registry shape and external API of `CalculationEngine.register / register_spec` — unchanged.
- `forecast_pipeline._propagate_cpi_forecast_to_derived` — out of scope. Forecasts and derived-historical are different layers; this ADR doesn't touch forecast propagation.

## Consequences

### Positive

- **Locality.** The semantic "derived[t] always reflects source[t]" lives in one module, `calculation_engine`. No more split between scheduler and engine on what "source updated" means.
- **Self-healing on revisions.** Any revision the daily ETL touches (whether `records_added > 0` or `records_updated > 0`) triggers full derived recompute next morning. No more silent drift.
- **Idempotent.** Running `_execute` N times on unchanged source produces zero writes. The dispatch loop is safe to re-trigger.
- **Cheap.** Daily cost: 23 derived × ~140–410 points × `bulk_upsert` no-op upsert. Measured locally: ~2 seconds total against the dev database.

### Negative

- **No silent skip on partial ETL.** If only one parser ran today (e.g. ad-hoc trigger on `cpi`) and other 21 sources are unchanged, all 23 derived will still be recomputed. Cost is bounded but it's strictly more work than the old filtered dispatch.
- **One-time UI shift on first deploy.** The first prod ETL after this ADR will close the existing 18-point drift. Affected indicators (gdp-yoy, gdp-qoq, unemployment-annual, current-account-yoy) will show updated values. These are *correct* values per the existing formulas — no formula changes, no methodology changes. Magnitude of shift on gdp-yoy is ±0.6–0.8 п.п. on 15 historical dates.

### Limit of the invariant — orphan derived points

The invariant is **one-directional**: `bulk_upsert` only inserts/updates, never deletes. If a source point is manually deleted (DELETE from `IndicatorData`), the corresponding derived point is **not** auto-removed; the derived for that date will simply not be rewritten by the next compute pass (the formula skips dates where source data is missing).

Rationale for not auto-deleting:

- 22 production parsers never delete — only upsert. There is no observed scenario where derived needs to follow a deletion.
- Any bug in a pure op (edge case, off-by-one, missing date) would cause **mass deletion** of derived data if `bulk_replace` semantics were used. This risk is asymmetric: undetected drift is cheap to fix later; lost historical values are expensive to reconstruct.
- The remediation when a source is manually corrected is a manual derived correction. This is documented in `CONTEXT.md`.

If future evidence shows this assumption breaking (e.g. a parser introduced that does delete points), revisit with a follow-up ADR proposing `bulk_replace` for `_execute`.

## Verification

1. Test `test_run_for_updated_sources_recomputes_every_derived_when_any_source_changed` — guard the dispatch contract.
2. Test `test_run_for_updated_sources_short_circuits_on_empty_batch` — guard the no-op short-circuit.
3. Locally: `docker compose exec backend python /tmp/rebuild.py` — first run prints non-zero changes for stale series; second run prints all zeros (idempotency).
4. Locally: visit `/indicator/wages-yoy`, `/indicator/cpi-food-quarterly`, `/indicator/unemployment-quarterly` after rebuild. Console clean, values render, charts plot.
5. On prod deploy: `verify_refactor.py` against the *new* state should report 0 mismatches across all 23 derived (since values now match what the formula gives on current source).

## Out of scope (future work)

- `had_new` detector in scheduler that ignores `records_updated`. With this ADR, that detector becomes irrelevant for derived correctness — the engine no longer cares about the per-source filter. But the detector also drives forecast retrain and other side effects; revisiting it is a separate concern.
- A telemetry hook reporting drift size after each daily ETL (e.g. "derived recomputation produced 0 changes today" → no drift, vs "produced 18 changes" → silent revision somewhere upstream). Useful but separate.
