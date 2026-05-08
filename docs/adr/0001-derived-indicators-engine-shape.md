# ADR 0001 — Derived indicators engine shape: declarative DSL over per-pair functions

- **Date:** 2026-05-05
- **Status:** Accepted
- **Last verified:** 2026-05-07 (28 derived in `DERIVED_SPECS`, 9 ops in `derived_ops.py`).
- **Author:** architecture audit (улучшение архитектуры по запросу пользователя).
- **Part of:** [`../../CONTEXT.md`](../../CONTEXT.md) (раздел `Derived indicator`).
- **Related:** [ADR-0002](0002-derived-always-reflects-source.md) (инвариант идемпотентности).
- **Code anchors:** `backend/app/services/calculation_engine.py::DERIVED_SPECS`, `backend/app/services/derived_ops.py`.

## Context

`backend/app/services/calculation_engine.py` (на момент решения — 559 строк) реализовывал **23 derived-индикатора** (`inflation-quarterly`, `inflation-annual`, `gdp-yoy`, `gdp-qoq`, `wages-real`, `unemployment-quarterly`, `current-account-yoy`, ipi-yoy, exports-yoy, imports-yoy, ppi-yoy, housing-yoy-{primary,secondary}, wages-yoy, exports-qoq, imports-qoq, cpi-{food,nonfood,services}-{quarterly,annual}). За эти 23 случая было написано **23 отдельных функции** `_compute_*`, из которых:

- **7 уникальных операций**: `quarterly_index` (CPI multiplicative), `annual_inflation` (CPI rolling 12-month product), `yoy` (vs 12 мес назад), `qoq` (vs предыдущая точка), `quarterly_avg`, `rolling_avg` (для unemployment), `wages_real` (особая, 2 источника).
- **9 wrapper-функций** — связки src→dst, которые ничего не делают кроме `return await _compute_quarterly_cpi_index("cpi-food", "cpi-food-quarterly")`.
- Дублирующиеся: `_compute_gdp_yoy`/`_compute_gdp_qoq` дублируют `_compute_yoy_generic`/`_compute_qoq_generic` с минимальными отличиями в guard-условиях.
- Регистрация в singleton `calculation_engine.register(code, sources, fn)` — третье место, где повторяется та же информация (dst-код и src-коды).

История фиксирует системный баг (2026-04-17): `if result.rowcount` использовался во всех 9 функциях вместо `result.fetchone() is not None`; ошибка проявилась только при глубоком аудите, потому что copy-paste boilerplate скрывал баг от unit-тестов. Это **проблема locality**: одна формула и её persistence — в 23 местах.

## Decision

Структура нового модуля:

```
backend/app/services/calculation_engine.py
├── Pure operations — `derived_ops.py` (NO db, NO async, NO upsert):
│     def quarterly_index(monthly: list[(date, value)]) -> list[(date, value)]
│     def annual_inflation(monthly: list[(date, value)]) -> list[(date, value)]
│     def yoy(series: list[(date, value)]) -> list[(date, value)]
│     def qoq(series: list[(date, value)]) -> list[(date, value)]
│     def quarterly_avg(monthly: list[(date, value)]) -> list[(date, value)]
│     def rolling_avg(series: list[(date, value)], window: int) -> list[(date, value)]
│     def wages_real(wages_nominal, cpi) -> list[(date, value)]
│
├── Declarative spec — one entry per derived (`calculation_engine.DERIVED_SPECS`):
│     DerivedSpec(dst_code="inflation-quarterly", src_codes=("cpi",), op=quarterly_index)
│     DerivedSpec(dst_code="cpi-food-quarterly", src_codes=("cpi-food",), op=quarterly_index)
│     DerivedSpec(dst_code="ipi-yoy", src_codes=("ipi",), op=yoy)
│     DerivedSpec(dst_code="wages-real", src_codes=("wages-nominal", "cpi"), op=wages_real)
│     ... (изначально 23 entries)
│
└── Generic engine:
      class CalculationEngine:
        - register_spec(spec: DerivedSpec) — сгенерирует executor автоматически
        - register(code, sources, fn) — escape hatch для ad-hoc derivations (сохранён для backward-compat)
        - run_for_updated_sources(db, source_codes) -> list[str]
          loads sources from DB, runs op, upserts result, invalidates cache,
          returns dst codes whose values actually changed
      calculation_engine = CalculationEngine()  # singleton, populated from DERIVED_SPECS at import
```

### Why this shape

- **Separation of formula and persistence.** Operations are pure functions on list-of-tuples. Test surface = list-of-tuples → list-of-tuples. No async, no DB, no mocking.
- **One source of truth per derived.** `DerivedSpec` declares dst, srcs, op в одну строку. No three-place duplication (function body / function-binding-args / register call).
- **Bug locality.** A formula bug fixed once. A persistence bug (e.g. `result.fetchone()` vs `result.rowcount`) fixed once.
- **Easy to add new derived.** One spec entry. One operation if formula is new.
- **Backward-compat.** `calculation_engine.register(...)` API preserved. `_derived` set keys preserved (existing test `test_all_derived_registered` still green).

### Why NOT alternatives

- **Class-based operations** (each op a class with state): overkill, ops are stateless.
- **Lambda expressions inline in DERIVED_SPECS**: unreadable for `wages_real` formula. Один компромисс допущен — `partial(ops.rolling_avg, window=12)` для `unemployment-annual`.
- **DB-stored formulas** (e.g. JSON spec в `Indicator.model_config_json`): formula execution shifts from typed Python to dynamic dispatch — net loss in safety, no big locality win.
- **Plugin discovery** (auto-register via decorators / entry points): unnecessary indirection for a closed set of ops + specs.

## Consequences

### Positive

- ~300 lines removed from `calculation_engine.py` (с 559 до 174).
- Каждая operation independently testable on synthetic series.
- Bug fixes apply once.
- New derived = 1 line.

### Negative / risks

- One-time refactor: every derived computation must produce **bit-identical** values to current. Mitigated by:
  - Snapshot test on production data before/after (сравнение через API endpoint `/data` для всех 23 derived).
  - Round-trip test for each operation with known inputs (CPI 12 reading point series → known annual inflation values).
  - Existing `test_all_derived_registered` keeps the registry contract.
- `_compute_gdp_yoy` and `_compute_gdp_qoq` had guard `len(data) < 5` and `len(data) < 2` — preserved as op preconditions.

## Subsequent additions (after acceptance)

Реестр и набор операций расширились без изменения формы решения:

- **2026-05-06 — December-to-December annual semantics.** Добавлены две чистые операции:
  - `december_to_december(monthly)` — для CPI-семьи и PPI: одна точка/год, anchored на `date(Y,1,1)`. Для CPI MoM-индекса (100.x) — chain product `∏(v_m/100)`; для PPI level-индекса — `Dec[Y]/Dec[Y-1] − 1`. Вытеснил rolling-12M `annual_inflation` в спецификациях `*-annual` (старая op оставлена в `derived_ops.py` как «used internally by other consumers if needed», но **в текущем `DERIVED_SPECS` не используется** — кандидат на удаление при следующем proper cleanup).
  - `annual_sum(quarterly_or_monthly)` — sum 4 квартальных или 12 месячных значений. Используется `gdp-nominal-annual` и `gdp-real-annual`.

  Обе автоматически попадают в forecast-страт `derived_from_source` (`backend/app/services/forecast_strategies/derived_from_source.py`) — те же чистые функции переиспользуются для прогноза.

- **2026-05-07 — GDP nominal/real split.** Добавлены 4 новых spec'а:
  - `gdp-real-yoy`, `gdp-real-qoq` — те же `yoy`/`qoq` ops, но src=`gdp-real` (раньше real-производные считались через `derived_from_source.real_from_yoy` от `gdp-yoy`, что давало накопленную ошибку).
  - `gdp-nominal-annual`, `gdp-real-annual` — `annual_sum`.

**Текущие числа (2026-05-07):** 9 операций в `derived_ops.py` (одна — `annual_inflation` — orphaned, не используется в spec'ах); 28 `DerivedSpec` в `DERIVED_SPECS`. Backwards-compat этих изменений: добавление spec'а или нового op'а — однострочное; никаких миграций БД.

### Out of scope (future ADRs)

- **CPI forecast propagation** to derived (`forecast_pipeline._propagate_cpi_forecast_to_derived`): пишет ForecastValue, не IndicatorData. Это другой слой; формульное дублирование с `quarterly_index` оставлено намеренно — не ходим в форекастер из calc_engine. После 2026-05-05 кросс-зависимости в forecast-слое унесены в реестр `forecast_strategies/`; см. отдельный ADR (TBD).
- **Persistence layer extraction**: общий `bulk_upsert` уже есть. ADR не вводит нового.
- **Cleanup of orphaned `annual_inflation` op**: безопасно удалить вместе со следующим релизом, т.к. ни один spec её не вызывает.

## Implementation checklist (исторический)

1. Add 7 pure-function unit tests with known input/output (snapshot from current production CPI/GDP/wages). ✅
2. Refactor `calculation_engine.py` to declarative DSL. ✅
3. Run `pytest backend/tests/test_calculation_engine.py` — must pass with same set of registered codes. ✅
4. Pull production snapshot: for each of 23 derived, GET `/api/v1/indicators/{code}/data?range=all` before/after refactor — diff must be 0 rows. ✅ (`verify_refactor.py` подтвердил bit-identical паритет; см. историю проекта 2026-05-05.)
5. Manual smoke: trigger one parent ETL (e.g. `cpi`), verify all dependent derived recompute and store identical values. ✅
