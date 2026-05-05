# Forecast Economy — Project Context

**Last updated:** 2026-05-05.

> Domain glossary for the project. Every architectural discussion, ADR, and refactoring proposal should use the terms defined here. If a discussion needs a new term, add it to this file before finishing.

---

## What this is

`forecasteconomy.com` — публичная аналитическая платформа по экономическим показателям России. Собирает данные с Росстата, ЦБ РФ и Минфина, считает производные ряды и прогнозы, отдаёт фронтенду + поисковикам + соцботам + embed-виджетам.

- **Backend**: Python 3.12, FastAPI + Uvicorn, SQLAlchemy 2 (async, asyncpg), Alembic, APScheduler, statsmodels (forecaster), pandas/openpyxl (parsers), Redis (cache).
- **Frontend**: React 19, Vite 7, Tailwind 4, Recharts, React Query 5, GSAP, React Router 7, Axios, Lucide.
- **Infra**: Docker Compose × 4 (backend, frontend, postgres-16, redis-7), Caddy reverse-proxy с автоматическим HTTPS, Yandex.Metrika + Webmaster, Sentry, Telegram alerts, кастомный Forecast Analytics MCP.
- **Прод**: `5.129.204.194` (Timeweb Cloud, Ubuntu 24.04, 2 GB RAM).

---

## Domain glossary

### Indicator

Отслеживаемый экономический показатель. Каждый индикатор имеет:

- `code` — slug (`cpi`, `usd-rub`, `gdp-nominal`, `inflation-annual`).
- `name`, `name_en`, `description`, `methodology` — для UI и SEO.
- `unit` — `%`, `руб.`, `млрд руб.`, `млн чел.`, `индекс`, `‰`, `ед.`, ...
- `frequency` — `daily`, `weekly`, `monthly`, `quarterly`, `annual`.
- `source` — `Росстат` / `ЦБ РФ` / `Минфин` / иное.
- `parser_type` — какой парсер обновляет ряд (`rosstat_cpi_xlsx`, `cbr_fx_xml`, `derived`, ...).
- `category` — русская строка категории (`Цены`, `Ставки`, ...). Маппится на `slug` фронта (`prices`, `rates`).
- `model_config_json` — все остальные параметры: `forecast_steps`, `backfill_from_year`, специфика парсера (`dataservice` блок, `bop_target` блок), `approved_forecast_values`, `forecast_transform`.

Хранится в таблице `Indicator`. Текущее количество: 80+.

### DataPoint

Одна точка временного ряда для индикатора. `(date, value)`. Хранится в `IndicatorData` с `UniqueConstraint(indicator_id, date)`.

### Source

Официальный поставщик данных:

- **Росстат** (`rosstat.gov.ru`, `eng.rosstat.gov.ru`). Форматы: SDDS XLSX (стандарт IMF), КЭП XLSX (`ind_MM-YYYY.xlsx`), HTML-бюллетени (недельный CPI), демографические XLSX, годовые XLS (наука/инновации).
- **Центральный банк** (`cbr.ru`). XML (FX, gold), HTML/UniDbQuery (KeyRate, RUONIA, monetary, reserves), DataService JSON (rates по срочности, current account, ...), XLSX (BOP, debt).
- **Минфин** (`minfin.gov.ru`). CSV для бюджета.
- **inflation-monitor.ru** — был источником недельной CPI (заменён на Росстат HTML-бюллетени + Nedel_ipc.xlsx).

Каждый источник требует свой SSL/CA setup (Росстат — русские CA-сертификаты).

### Parser

Конкретная реализация ETL для одного формата источника. Базовый класс `BaseParser` (сейчас просто `run(db, indicator, fetch_log)`). 22 живых парсера. Регистрируются в `PARSER_REGISTRY` (живёт в `backend/app/services/rosstat_cpi_parser.py` — исторический артефакт, должен переехать).

Один парсер обычно обслуживает несколько индикаторов одного источника (CbrFxParser → 3 валюты; RosstatCpiParser → 4 листа CPI; CbrDataServiceParser → много ставок ЦБ).

### Derived indicator

Индикатор без собственного источника. Считается формулой из других индикаторов. `parser_type = "derived"`. Запускается из `CalculationEngine.run_for_updated_sources` после daily ETL.

Примеры:
- `inflation-quarterly` ← `cpi` (произведение 3 месячных индексов).
- `inflation-annual` ← `cpi` (12-месячное скользящее произведение − 100).
- `gdp-yoy`, `ipi-yoy`, `current-account-yoy`, ... ← yoy-формула.
- `wages-real` ← `wages-nominal` × `cpi` (real wage index).
- `unemployment-quarterly` ← `unemployment` (quarterly avg).

Текущее количество: 23.

### Forecast

Прогноз индикатора на N шагов. Хранится в `Forecast` (метаданные + `is_current`) + `ForecastValue` (точки `(date, value, lower_bound, upper_bound)`).

Модели:
- **CPI семейство** (cpi/cpi-food/cpi-nonfood/cpi-services): `train_monthly_cpi` (blend OLS + prior 4/12 по апрельскому ноутбуку Никиты).
- **CPI annual rolling** (`inflation-annual`): `train_inflation_12m` — скользящая 12-месячная инфляция от прогноза.
- **Quarterly housing** (`housing-price-primary/secondary`): `train_quarterly_housing`.
- **Approved forecast**: ручные значения из `model_config_json.approved_forecast_values` (для PPI, GDP — ноутбуки Никиты).
- **Generic**: `train_and_forecast` (multi-window OLS с inverse-variance weighting). По дефолту для всех остальных.

**CPI derived forecasts** (inflation-quarterly, inflation-annual, cpi-food-quarterly, ...) — пишутся как **side-effect** от прогноза источника CPI через `forecast_pipeline._propagate_cpi_forecast_to_derived`. Их собственный `forecast_steps = 0`, `retrain_indicator_forecast` для них skipped.

### ETL run

Запуск одного парсера для одного индикатора. Записывается в `FetchLog`:
- `status` ∈ `running` / `success` / `no_new_data` / `failed` / `timeout`.
- `started_at`, `completed_at` (TIMESTAMP WITHOUT TIME ZONE — все datetime tz-naive!).
- `records_added`, `error_message`, `source_url`.

Daily ETL (06:00 МСК) запускает все `is_active=True` non-derived индикаторы → CalculationEngine для derived → `_promote_past_events` для календаря.

### Category

Функциональная группа индикаторов: Цены, Ставки, Финансы, Труд, ВВП, Торговля, Бизнес, Население, Наука. На главной — сетка карточек, на `/category/{slug}` — список индикаторов в категории.

В БД хранится русское имя (`Цены`); URL использует slug (`prices`). Маппинг — фронтовый файл `frontend/src/lib/categories.js` (источник правды для фронта).

### Calendar event

Запись в `EconomicEvent` для расписания публикаций (релиз CPI Росстата, заседание совета директоров ЦБ). Статус `scheduled` → `released` (автоматически промотится по `scheduled_date < today`).

### Embed widget

Внешний виджет, встраиваемый по `<iframe>` или SVG. Типы: chart, card, table, ticker, compare, badge. Имеют отдельный CSP (`frame-ancestors *`), отдельный rate limit (600/мин), impression tracking.

### Approved forecast

Ручные прогнозные значения от Никиты (партнёр), хранящиеся в `Indicator.model_config_json.approved_forecast_values` (массив `{date, value}`). Применяются в `retrain_indicator_forecast` без переобучения модели.

### SEO meta bundle

Пакет meta-данных для индикатора/категории/страницы: `seo_title`, `seo_description`, `canonical`, JSON-LD, OG image, twitter card. Сейчас распределён по:

- `frontend/src/pages/IndicatorDetail.jsx::SEO_MAP` — для frontend-routing useMeta.
- `backend/app/services/seo_content.py` — для backend OG/SEO renderer.
- `backend/seed_data.py` (description, methodology, source_url).
- `frontend/src/lib/categories.js` (descriptions для категорий).

Это **дублирование**, отслеженное как кандидат №1 на refactor.

### Forecast Analytics OS

Отдельный backend-слой для интеграции с Yandex.Metrika / Yandex.Webmaster / SEO crawler. Включает: `app/services/yandex_*.py`, `app/services/analytics_*.py`, `app/api/analytics.py`, отдельный warehouse (`metrika_*`, `seo_*` таблицы), кастомный MCP (`mcp/forecast-analytics-mcp/`). Интегрирован в Cursor через `~/.cursor/mcp.json`. Нужен для агента-аналитика.

---

## Architectural language (from improve-codebase-architecture skill)

- **Module** — anything with an interface and an implementation (function, class, package).
- **Interface** — everything a caller must know: types, invariants, error modes, ordering, config. Not just signature.
- **Implementation** — code inside.
- **Depth** — leverage at the interface: many behaviours behind a small interface.
- **Shallow** — interface complexity ≈ implementation complexity (e.g. wrapper function that just binds two args).
- **Seam** — where an interface lives; place to alter behaviour without editing in place.
- **Adapter** — concrete thing satisfying an interface at a seam.
- **Leverage** — what callers gain from depth.
- **Locality** — what maintainers gain from depth: change concentrated in one place.
- **Deletion test** — imagine deleting the module. If complexity vanishes, it was a pass-through. If complexity reappears across N callers, it was earning its keep.

When suggesting refactors, use this language. Use the **Indicator/DataPoint/Derived/Forecast/Parser** vocabulary above for the domain.
