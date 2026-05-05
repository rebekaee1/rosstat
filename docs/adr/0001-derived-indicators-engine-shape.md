# ADR 0001 — Derived indicators engine shape: declarative DSL over per-pair functions

- **Date:** 2026-05-05
- **Status:** Accepted
- **Author:** architecture audit (улучшение архитектуры по запросу пользователя)

## Context

`backend/app/services/calculation_engine.py` (559 строк) реализует **23 derived-индикатора** (`inflation-quarterly`, `inflation-annual`, `gdp-yoy`, `gdp-qoq`, `wages-real`, `unemployment-quarterly`, `current-account-yoy`, ipi-yoy, exports-yoy, imports-yoy, ppi-yoy, housing-yoy-{primary,secondary}, wages-yoy, exports-qoq, imports-qoq, cpi-{food,nonfood,services}-{quarterly,annual}). За эти 23 случая написано **23 отдельных функции** `_compute_*`, из которых:

- **7 уникальных операций**: `quarterly_index` (CPI multiplicative), `annual_inflation` (CPI rolling 12-month product), `yoy` (vs 12 мес назад), `qoq` (vs предыдущая точка), `quarterly_avg`, `rolling_avg` (для unemployment), `wages_real` (особая, 2 источника).
- **9 wrapper-функций** — связки src→dst, которые ничего не делают кроме `return await _compute_quarterly_cpi_index("cpi-food", "cpi-food-quarterly")`.
- Дублирующиеся: `_compute_gdp_yoy`/`_compute_gdp_qoq` дублируют `_compute_yoy_generic`/`_compute_qoq_generic` с минимальными отличиями в guard-условиях.
- Регистрация в singleton `calculation_engine.register(code, sources, fn)` — третье место, где повторяется та же информация (dst-код и src-коды).

История фиксирует системный баг (2026-04-17): `if result.rowcount` использовался во всех 9 функциях вместо `result.fetchone() is not None`; ошибка проявилась только при глубоком аудите, потому что copy-paste boilerplate скрывал баг от unit-тестов. Это **проблема locality**: одна формула и её persistence — в 23 местах.

## Decision

Структура нового модуля:

```
backend/app/services/calculation_engine.py
├── Pure operations (NO db, NO async, NO upsert):
│     def quarterly_index(monthly: list[(date, value)]) -> list[(date, value)]
│     def annual_inflation(monthly: list[(date, value)]) -> list[(date, value)]
│     def yoy(series: list[(date, value)]) -> list[(date, value)]
│     def qoq(series: list[(date, value)]) -> list[(date, value)]
│     def quarterly_avg(monthly: list[(date, value)]) -> list[(date, value)]
│     def rolling_avg(series: list[(date, value)], window: int) -> list[(date, value)]
│     def wages_real(wages_nominal, cpi) -> list[(date, value)]
│
├── Declarative spec — one entry per derived:
│     DerivedSpec(dst_code="inflation-quarterly", src_codes=("cpi",), op=quarterly_index, decimals=4)
│     DerivedSpec(dst_code="cpi-food-quarterly", src_codes=("cpi-food",), op=quarterly_index, decimals=4)
│     DerivedSpec(dst_code="ipi-yoy", src_codes=("ipi",), op=yoy, decimals=2)
│     DerivedSpec(dst_code="wages-real", src_codes=("wages-nominal", "cpi"), op=wages_real, decimals=2)
│     ... (23 entries total)
│
└── Generic engine:
      class CalculationEngine:
        - register(spec: DerivedSpec) — для backward-compat
        - run_for_updated_sources(db, source_codes) -> list[str]
          loads sources from DB, runs op, upserts result, invalidates cache, returns dst codes
      calculation_engine = CalculationEngine.from_specs(DERIVED_SPECS)  # singleton
```

### Why this shape

- **Separation of formula and persistence.** Operations are pure functions on pandas Series-like lists. Test surface = list-of-tuples → list-of-tuples. No async, no DB, no mocking.
- **One source of truth per derived.** `DerivedSpec` declares dst, srcs, op in one line. No three-place duplication (function body / function-binding-args / register call).
- **Bug locality.** A formula bug fixed once. A persistence bug (e.g. `result.fetchone()` vs `result.rowcount`) fixed once.
- **Easy to add new derived.** One spec entry. One operation if formula is new.
- **Backward-compat.** `calculation_engine.register(...)` API preserved. `_derived` set keys preserved (existing test `test_all_derived_registered` still green).

### Why NOT alternatives

- **Class-based operations** (each op a class with state): overkill, ops are stateless.
- **Lambda expressions inline in DERIVED_SPECS**: unreadable for `wages_real` formula.
- **DB-stored formulas** (e.g. JSON spec in `Indicator.model_config_json`): formula execution shifts from typed Python to dynamic dispatch — net loss in safety, no big locality win.
- **Plugin discovery** (auto-register via decorators / entry points): unnecessary indirection for a closed set of 7 ops + 23 specs.

## Consequences

### Positive

- ~300 lines removed from `calculation_engine.py`.
- Each operation independently testable on synthetic Series.
- Bug fixes apply once.
- New derived = 1 line.

### Negative / risks

- One-time refactor: every derived computation must produce **bit-identical** values to current. Mitigated by:
  - Snapshot test on production data before/after (сравнение через API endpoint `/data` для всех 23 derived).
  - Round-trip test for each operation with known inputs (CPI 12 reading point series → known annual inflation values).
  - Existing `test_all_derived_registered` keeps the registry contract.
- `_compute_gdp_yoy` and `_compute_gdp_qoq` had guard `len(data) < 5` and `len(data) < 2` — preserved as op preconditions.

### Out of scope (future ADRs)

- **CPI forecast propagation** to derived (`forecast_pipeline._propagate_cpi_forecast_to_derived`): пишет ForecastValue, не IndicatorData. Это другой слой; формульное дублирование с `quarterly_index` оставлено намеренно — не ходим в форекастер из calc_engine.
- **Persistence layer extraction**: общий `bulk_upsert` уже есть. ADR не вводит нового.

## Implementation checklist

1. Add 7 pure-function unit tests with known input/output (snapshot from current production CPI/GDP/wages).
2. Refactor `calculation_engine.py` to declarative DSL.
3. Run `pytest backend/tests/test_calculation_engine.py` — must pass with same set of registered codes.
4. Pull production snapshot: for each of 23 derived, GET `/api/v1/indicators/{code}/data?range=all` before/after refactor — diff must be 0 rows.
5. Manual smoke: trigger one parent ETL (e.g. `cpi`), verify all dependent derived recompute and store identical values.
