# Forecast Economy — Project Context

**Last updated:** 2026-05-07.
**Part of:** [`AGENTS.md`](AGENTS.md) (точка входа для AI-агента).
**See also:** [`README.md`](README.md), [`docs/workflow.md`](docs/workflow.md), [`docs/enterprise_resilience.md`](docs/enterprise_resilience.md), [`docs/cbr_sources.md`](docs/cbr_sources.md), [`docs/analytics_api_inventory/`](docs/analytics_api_inventory/), [`docs/adr/`](docs/adr/).

> Domain glossary for the project. Every architectural discussion, ADR, and refactoring proposal should use the terms defined here. If a discussion needs a new term, add it to this file before finishing.

## Документы рядом

| Файл | Назначение |
|------|------------|
| [`AGENTS.md`](AGENTS.md) | Точка входа для AI-агента: с чего начать, как читать документацию, как её актуализировать |
| [`README.md`](README.md) | Высокоуровневая карта стека, API, indicators, deploy |
| [`docs/workflow.md`](docs/workflow.md) | Модель работы, локальный dev, прод-деплой, smoke C |
| [`docs/enterprise_resilience.md`](docs/enterprise_resilience.md) | Rate-limit, CSP, asset-hash trap, бэкапы, чеклист канарейки |
| [`docs/cbr_sources.md`](docs/cbr_sources.md) | Все не-Росстат источники: ЦБ РФ + Минфин (10 парсеров) |
| [`docs/analytics_api_inventory/`](docs/analytics_api_inventory/) | Инвентарь Yandex API (Metrika, Webmaster) + статус реализации |
| [`docs/adr/0001`](docs/adr/0001-derived-indicators-engine-shape.md) | Engine shape: 28 derived через `DERIVED_SPECS` + 9 чистых ops |
| [`docs/adr/0002`](docs/adr/0002-derived-always-reflects-source.md) | Инвариант: derived всегда отражает source (`bulk_upsert` идемпотентен) |
| [`docs/adr/0003`](docs/adr/0003-seo-single-source-server-rendered.md) | SEO single-source: backend SSR через `__spa-index.html` + Vite asset discovery |

---

## What this is

`forecasteconomy.com` — публичная аналитическая платформа по экономическим показателям России. Собирает данные с Росстата, ЦБ РФ и Минфина, считает производные ряды и прогнозы, отдаёт фронтенду + поисковикам + соцботам + embed-виджетам.

- **Backend**: Python 3.12, FastAPI 0.115 + Uvicorn, SQLAlchemy 2.0 (async, asyncpg), Alembic, APScheduler, statsmodels (forecaster + SARIMA-семейство), pandas/openpyxl/xlrd (parsers), beautifulsoup4 (HTML), requests/httpx (HTTP), Redis 7 (cache).
- **Frontend**: React 19, Vite 7, Tailwind 4, Recharts 3, TanStack React Query 5, GSAP 3, React Router 7, Axios, Lucide, `xlsx` (Excel-экспорт), `@sentry/react` (только фронт — backend без Sentry).
- **Infra**: Docker Compose × 4 (backend, frontend, postgres-16, redis-7), Caddy reverse-proxy на хосте (HTTPS + CSP с десятками `mc.yandex.*` доменов + `frame-ancestors *` для embed), Nginx внутри контейнера frontend (роутинг между SPA-shell и backend SSR), Yandex.Metrika (counter `107136069`) + Yandex.Webmaster, Telegram alerts (`alerting.py`), кастомный Forecast Analytics MCP (`mcp/forecast-analytics-mcp/`).
- **Прод**: `5.129.204.194` (Timeweb Cloud, Ubuntu 24.04, 2 GB RAM).

---

## Domain glossary

### Indicator

Отслеживаемый экономический показатель. Каждый индикатор имеет:

- `code` — slug (`cpi`, `usd-rub`, `gdp-nominal`, `inflation-annual`).
- `name`, `name_en`, `description`, `methodology` — для UI и SEO.
- `unit` — `%`, `руб.`, `млрд руб.`, `млн чел.`, `индекс`, `‰`, `ед.`, ...
- `frequency` — `daily`, `weekly`, `monthly`, `quarterly`, `annual`.
- `source` — `Росстат` / `Банк России` / `Минфин`. Хранится строкой; используется фронтом для подписи и SEO. Терминология «ЦБ РФ» допускается в текстах, но в БД канон — «Банк России».
- `parser_type` — какой парсер обновляет ряд (`rosstat_cpi_xlsx`, `cbr_fx_xml`, `derived`, ...).
- `category` — русская строка категории (`Цены`, `Ставки`, ...). Маппится на `slug` фронта (`prices`, `rates`).
- `model_config_json` — все остальные параметры: `forecast_steps`, `backfill_from_year`, специфика парсера (`dataservice` блок, `bop_target` блок, `element_id`), `approved_forecast_values`, `forecast_strategy` (диспатчинг в реестр стратегий), `derived_forecast` блок (для прогноза-производного-от-источника), `forecast_transform` (для frontend re-scaling, например `cpi_index`).
- **Editorial поля для SEO** (живут в БД, редактируются без деплоя):
  - `seo_title`, `seo_description` — meta для индикатора, fallback к шаблону.
  - `seo_keywords` — meta keywords (37 ручных override + `default_keywords()` fallback).
  - `seo_blocks` — JSON-массив `{title, body}` дополнительных секций под графиком.
  - `is_listed` — boolean: показывать ли карточку индикатора в листинге категории. По умолчанию `true`. `false` — индикатор доступен только через `VariantGroupPicker` внутри родительского индикатора (например, `cpi-food-quarterly` скрыт, виден только при выборе «Состав индекса → продовольственные → квартально» на странице `cpi`).

Хранится в таблице `Indicator`. **Текущее количество:** 104 индикатора (76 source-индикаторов + 28 derived).

### DataPoint

Одна точка временного ряда для индикатора. `(date, value)`. Хранится в `IndicatorData` с `UniqueConstraint(indicator_id, date)`.

### Source

Официальный поставщик данных:

- **Росстат** (`rosstat.gov.ru`, `eng.rosstat.gov.ru`). Форматы: SDDS XLSX (стандарт IMF), КЭП XLSX (`ind_MM-YYYY.xlsx`), HTML-бюллетени (недельный CPI), демографические XLSX, годовые XLS (наука/инновации, основные фонды).
- **Банк России** (`cbr.ru`). XML (FX, gold), HTML/UniDbQuery (KeyRate, RUONIA, monetary, reserves), DataService JSON (rates по срочности — mortgage/deposit/auto-loan/credit-rate-corp/ind, M2, current account, exports/imports), XLSX (BOP, debt).
- **Минфин** (`minfin.gov.ru`). CSV для бюджета (revenue, expenditure, deficit).

Каждый источник требует свой SSL/CA setup (Росстат — русские CA-сертификаты, `backend/certs/russiantrustedca2024.pem` через `RUSTATS_ROSSTAT_CA_CERT`).

### Parser

Конкретная реализация ETL для одного формата источника. Базовый класс `BaseParser` (`backend/app/services/base_parser.py`) — **template-method**: финальный `run()` оркеструет fetch → parse → validate → upsert → forecast retrain → cache invalidate в одном месте. Дочерние классы реализуют `_fetch_and_parse(db, indicator, cfg, fetch_log) -> (points, source_url)` (обязательно) + опциональные hooks `_validate(points, cfg)`, `_post_upsert(...)`, `_handle_forecasts(...)`. Это устранило ~1100 строк boilerplate, унифицировало статусы `fetch_log` и каскад retrain'а.

**Текущее количество:** 23 парсер-типа в `PARSER_REGISTRY` (см. `rosstat_cpi_parser.py`, регистрируется как singleton-импорт из исторических соображений — артефакт). Парсер-файлов 24 (включая `base_parser.py`). Один парсер обычно обслуживает несколько индикаторов одного источника (CbrFxParser → 3 валюты; RosstatCpiParser → 4 листа CPI; CbrDataServiceParser → много ставок ЦБ).

### Derived indicator

Индикатор без собственного источника. Считается чистой функцией от других индикаторов. `parser_type = "derived"`. Запускается из `CalculationEngine.run_for_updated_sources` после daily ETL.

**Инвариант (ADR-0002):** *derived[t] всегда выводимо из текущего state source-рядов на момент последнего ETL-батча с новыми строками* (`records_added > 0`). При любом таком ETL прогоне CalculationEngine полностью пересчитывает все 28 derived-рядов от первой до последней точки (idempotent — `bulk_upsert` записывает только реально изменившиеся значения). Не «инкрементальный накопительный снимок», а чистая функция source. Если source ревизуется задним числом — derived перетягиваются автоматически на следующий же день с новыми строками (см. ADR-0002 «Limit of the invariant — pure-revision day»).

**Граница инварианта.** Инвариант односторонний: `bulk_upsert`-only. Если source-точка **удаляется** вручную (DELETE из IndicatorData), соответствующая derived-точка остаётся в БД как осиротевшая — engine не знает, что нужно её удалить. Это явный compromise (см. ADR-0002): автоматическое удаление derived создавало бы риск массовой потери данных при ошибке pure op. Ручные коррекции source требуют ручной чистки derived или прогона `scripts/rebuild-all-derived.py`.

Реестр операций (`backend/app/services/derived_ops.py`) — 9 чистых функций без `db`/`async`:
- `quarterly_index` — chained product 3 месячных индексов CPI (для `*-quarterly`).
- `december_to_december` — годовая инфляция «Dec_Y / Dec_{Y-1} − 1» (для CPI-семьи и PPI `*-annual`; пришла на смену rolling-12M в 2026-05-06, см. ADR-0001 «Subsequent additions»).
- `annual_sum` — сумма квартальных или 12 месячных значений (для `gdp-{nominal,real}-annual`).
- `yoy`, `qoq` — рост к 12 мес назад / к предыдущему кварталу.
- `quarterly_avg`, `rolling_avg` — для unemployment.
- `wages_real` — особая, 2 источника (`wages-nominal`, `cpi`).
- `annual_inflation` — устаревшая op (rolling-12M product), сохранена в файле, но **не используется** в `DERIVED_SPECS`. Кандидат на удаление при следующей чистке.

Реестр спецификаций (`calculation_engine.DERIVED_SPECS`) — **28 entries**:

- **CPI семейство:** `inflation-quarterly` ← `cpi`, `inflation-annual` ← `cpi`, и аналоги для `cpi-food/nonfood/services` (8 spec'ов).
- **PPI:** `ppi-yoy`, `ppi-annual`.
- **GDP:** `gdp-{yoy,qoq}` ← `gdp-nominal`, `gdp-real-{yoy,qoq}` ← `gdp-real`, `gdp-{nominal,real}-annual` (annual_sum).
- **Wages/Unemployment:** `wages-real`, `wages-yoy`, `unemployment-{quarterly,annual}`.
- **Trade/External:** `current-account-yoy`, `exports-{yoy,qoq}`, `imports-{yoy,qoq}`.
- **Other:** `ipi-yoy`, `housing-yoy-{primary,secondary}`.

### Forecast

Прогноз индикатора на N шагов. Хранится в `Forecast` (метаданные + `is_current`) + `ForecastValue` (точки `(date, value, lower_bound, upper_bound)`).

**Реестр стратегий** (`backend/app/services/forecast_strategies/registry.py`) — диспетчеризует прогноз-генерацию по полю `Indicator.model_config_json.forecast_strategy`:

| Имя | Когда применяется | Что делает |
|---|---|---|
| `cpi_combined` | `cpi`, `cpi-food`, `cpi-nonfood`, `cpi-services` | Гонит `train_monthly_cpi` (помесячный) + `train_inflation_12m` (12-мес скользящий) и каскадит результат на `*-quarterly` derived |
| `housing_quarterly` | `housing-price-secondary` | `train_quarterly_housing` (multi-window OLS на квартальных уровнях) |
| `gdp_nominal_quarterly` | `gdp-nominal` | `train_gdp_nominal_quarterly` (multi-window OLS на log-diff, без блендинга) |
| `gdp_real_quarterly` | `gdp-real` | `train_gdp_real_quarterly` (то же ядро `_log_diff_no_blend_forecast`, что и nominal, но обучается на real-уровнях; bit-exact с блокнотом Никиты ±0.15%) |
| `ppi_monthly` | `ppi` | `train_ppi_monthly` (k=1..4, monthly lags log-diff) |
| `approved` | `housing-price-primary` (Niktia), исторически: `gdp-nominal`, `ppi` | Использует ручные значения из `model_config_json.approved_forecast_values` (массив `{date, value}`) без переобучения |
| `derived_from_source` | Все *-yoy, *-qoq, *-annual derived с `derived_forecast: {source_code, operation, model_name}` | Применяет ту же чистую op (yoy / qoq / december_to_december / annual_sum / real_from_yoy) к **прогнозу** source-индикатора. Каскадный retrain срабатывает после успеха source |
| `generic_ols` | `inflation-weekly`, fallback | `train_and_forecast` (multi-window OLS с inverse-variance weighting); универсальная модель |

**Поля связки:**

- `model_config_json.forecast_strategy` — имя стратегии (если не задано — fallback `legacy_resolve(indicator)`).
- `model_config_json.derived_forecast` — `{source_code, operation, model_name}` для `derived_from_source` стратегии.
- `model_config_json.forecast_transform` — например `cpi_index` для `inflation-weekly`: значения возвращаются как уровень индекса 100.x; фронт пересчитывает в delta через `adjustCpiForecastDisplay`.
- `model_config_json.approved_forecast_values` — массив для approved-стратегии.
- `model_config_json.forecast_steps` — горизонт. По умолчанию 12 (`RUSTATS_FORECAST_STEPS`).

**Каскадный retrain.** После успешного retrain индикатора-источника (в `forecast_pipeline.retrain_indicator_forecast`) ищем все индикаторы, у которых `derived_forecast.source_code == this.code`, и retrain их рекурсивно с защитой от циклов. Это заменило старый side-effect `_propagate_cpi_forecast_to_derived`, который остался для cascade `cpi → cpi-{food,nonfood,services}-quarterly`, но `*-annual` (Dec-to-Dec) теперь живут отдельной стратегией.

### ETL run

Запуск одного парсера для одного индикатора. Записывается в `FetchLog`:

- `status` ∈ `running` / `success` / `no_new_data` / `failed` / `timeout`.
- `started_at`, `completed_at` (TIMESTAMP WITHOUT TIME ZONE — все datetime tz-naive!).
- `records_added`, `error_message`, `source_url`.

Внимание: `fetch_log.records_added` записывает **только новые строки**, не in-place revisions. `bulk_upsert` возвращает `(records_added, records_updated)`, но в `BaseParser.run()` поле в БД заполняется только из `records_added`. Это влияет на dispatch derived (см. ADR-0002 «Limit of the invariant — pure-revision day»).

Daily ETL (06:00 МСК, `RUSTATS_SCHEDULER_CRON_HOUR/MINUTE`) запускает все `is_active=True` non-derived индикаторы → `CalculationEngine.run_for_updated_sources` для derived (если хотя бы один parser добавил новые строки) → `_promote_past_events` для календаря.

**Calendar refresh** (`calendar_refresh` job): отдельный cron 1-го числа каждого месяца 03:00 МСК прокатывает `seed_calendar(months_ahead=12)` — rolling 12-месячное окно событий ЦБ/Росстата/Минфина (см. термин «Calendar event»).

**Analytics scheduler** (опционально): если `RUSTATS_ANALYTICS_SCHEDULER_ENABLED=true` — два дополнительных cron-а: hourly :15 (Yandex Metrika reporting sync) и daily (management snapshot). По умолчанию выключен.

### Category

Функциональная группа индикаторов: Цены, Ставки, Финансы, **Рынок труда**, ВВП, Торговля, Бизнес, Население, Наука. Девять штук. На главной — сетка карточек, на `/category/{slug}` — список индикаторов в категории.

В БД хранится русское имя (`Цены`, `Рынок труда`); URL использует slug (`prices`, `labor`). Маппинг — `frontend/src/lib/categories.js` (включает `seoTitle`/`seoDescription`, идентичные backend `seo_content.py::CATEGORY_META.title/description` — это **зеркало backend SSR**, не источник правды; см. ADR-0003).

### Calendar event

Запись в `EconomicEvent` для расписания публикаций (релиз CPI Росстата, заседание совета директоров ЦБ, недельный ИПЦ Росстата по средам, международные резервы РФ по четвергам). Статус `scheduled` → `released` (автоматически промотится по `scheduled_date < today` в `_promote_past_events`). Окно — rolling 12 месяцев; обновляется ежемесячно через `calendar_refresh` cron.

### Embed widget

Внешний виджет, встраиваемый по `<iframe>` (5 типов: chart, card, table, ticker, compare) или SVG-эндпойнтам (`/api/v1/embed/spark/{code}.svg`, `/card/{code}.svg`, `/badge/{code}.svg`). Имеют отдельный CSP в Caddy (`frame-ancestors *`), отдельный rate limit (600/мин в `RateLimitMiddleware`), impression tracking (`/api/v1/embed/impression`, `/pixel.gif`).

### Approved forecast

Ручные прогнозные значения от Никиты (партнёр), хранящиеся в `Indicator.model_config_json.approved_forecast_values` (массив `{date, value}`). Применяются стратегией `approved` в forecast registry без переобучения модели.

### SEO meta bundle

Пакет meta-данных для индикатора/категории/страницы: `seo_title`, `seo_description`, `seo_keywords`, `canonical`, JSON-LD, OG image, twitter card.

**Принцип хранения (ADR-0003 — Accepted, см. файл):** разделение по природе.

- **Редакционный контент** живёт в БД (`Indicator.seo_title`, `seo_description`, `seo_keywords`, `seo_blocks`, `is_listed`). Меняется людьми, без деплоя — через прямой UPDATE или будущий admin-UI.
- **Шаблоны и fallback** живут в коде: правила генерации seo_title для индикаторов, у которых ручной override пуст (`backend/app/services/seo_renderer.py` + `default_keywords()`); общие SEO-блоки для всех индикаторов; форматирование. Меняются через деплой.
- **Frontend читает из API и зеркалит SSR** — никаких локальных констант не осталось (`SEO_MAP`, `INDICATOR_BLOCKS`, `HIDDEN_FROM_LISTING` удалены в Шаге 4 фазы 2). Backend-SSR через `/seo/page/*`, `/seo/category/{slug}`, `/seo/indicator/{code}` — единственный источник правды; frontend `useDocumentMeta(null)` no-op до подгрузки данных, потом ставит то же, что лежит в SSR.
- **`/__spa-index.html`** — raw Vite SPA shell с заголовком `X-Robots-Tag: noindex, nofollow`. Используется backend SSR-renderer'ом для discover текущих hashed JS/CSS asset-имён. Не индексируется.

Исторически (до Шага 4 фазы 2, 2026-05-05) дублировалось в 4 местах: `seed_data.py`, `SEO_MAP` (frontend), `INDICATOR_BLOCKS` (backend), `categories.js HIDDEN_FROM_LISTING`. Сейчас — один источник в БД + код-fallback.

### Forecast Analytics OS

Отдельный backend-слой для интеграции с Yandex.Metrika / Yandex.Webmaster / SEO crawler. Включает:

- **Yandex клиенты:** `app/services/yandex_metrika_management.py`, `yandex_metrika_reporting.py`, `yandex_metrika_logs.py`, `yandex_webmaster_client.py`, `yandex_client.py`.
- **Ingestion / backfill / features:** `analytics_ingestion.py`, `analytics_backfill.py`, `analytics_features.py`.
- **Action policy / executor:** `action_policy.py`, `action_executor.py` — safety classes (read_only / low_risk_write / high_risk_write / denied).
- **API:** `app/api/analytics.py` (10 endpoints под `Authorization: Bearer ${RUSTATS_ANALYTICS_API_TOKEN}`).
- **Warehouse models:** `AnalyticsSyncRun`, `AnalyticsWatermark`, `MetrikaCounterSnapshot`, `MetrikaGoalSnapshot`, `MetrikaReportSnapshot`, `MetrikaDailyPageMetric`, `MetrikaSearchPhrase`, `RawMetrikaVisit`, `RawMetrikaHit`, `WebmasterDiagnostic`, `WebmasterSearchQuery`, `SeoPageSnapshot`, `AgentFinding`, `AgentActionAudit`, `FrontendEvent`, `Experiment`.
- **MCP:** `mcp/forecast-analytics-mcp/` (Node.js, 7 tools), интегрирован в Cursor через `~/.cursor/mcp.json`. Нужен для агента-аналитика; ходит в backend `/api/v1/analytics`.
- **Scope:** read-only Metrika tools работают; live writes выключены флагом `RUSTATS_ANALYTICS_LIVE_WRITES_ENABLED=false`. Webmaster и data-import API — endpoint-ы перечислены в `docs/analytics_api_inventory/`, но требуют дополнительных OAuth scopes (см. inventory README header).

---

## Operational invariants and traps

Вещи, которые ломаются неочевидно. Каждый пункт — проверенный пост-мортем.

### Asset-hash mismatch trap

После `docker compose build frontend` без перезапуска backend — backend SEO renderer возвращает HTML со ссылками на удалённые `/assets/*-OLD-HASH.js`. Причина: `seo_renderer._APP_ASSETS` кэширует discover'ные имена файлов в памяти процесса.

**Правило:** при rebuild фронта всегда делать `docker compose up -d backend frontend` одновременно (backend перезапустится, кэш сбросится). Альтернатива: `docker compose restart backend && redis-cli FLUSHDB`.

### Pure-revision day

Описано в ADR-0002. Если в ETL-батч ни один парсер не добавил новые строки (только in-place revisions), `run_for_updated_sources` не сработает; derived останутся stale до следующего «обычного» дня. Митигируется тем, что `cbr-fx`/`cbr-ruonia`/`gold-price`/`key-rate` — daily-источники. На практике pure-revision day без `records_added > 0` — крайне редкое явление. Жёсткий триггер ручного катчапа: `scripts/rebuild-all-derived.py`.

### auto-loan-rate `element_id` (ЦБ DataService)

Декабрь 2025: ЦБ переразложил dataset 28 (auto-loan-rate). Исторические `element_id 2/4/5/6/7/9/10/11` больше не публикуются, остался только агрегированный `element_id=110` («По всем срокам»). Парсер с `element_id=11` тихо возвращал 0 точек 5 месяцев. Текущий `seed_data.py` хранит `"element_id": 110`. Если ЦБ снова переразложит другой dataset — симптом тот же: ETL `success` + `records_added=0` несколько недель подряд.

### Rate limit policy

`RateLimitMiddleware` в `backend/app/main.py`: 120 req/min на обычные `/api/...` пути, **600 req/min** на `/api/v1/embed/*`, окно 60s, ключ — `X-Forwarded-For` (Caddy/Nginx добавляют). При превышении — `429 Retry-After: 60`. Если Redis недоступен — middleware пропускает запросы (graceful degradation).

### CSP whitelist для Yandex.Metrika

`Caddyfile` явно перечисляет десятки доменов `mc.yandex.{ru,by,...}`, `mc.webvisor.com`, `*.ingest.sentry.io` в `script-src` / `connect-src` / `child-src`. Любой новый Yandex-домен (например, `mc.yandex.kz` для Казахстана) — в whitelist через PR в Caddyfile, без него браузеры блокируют скрипт счётчика.

### Scheduler dual jobs + analytics-scheduler флаг

В `backend/app/main.py` lifespan регистрируются **два обязательных** APScheduler job'а: `daily_etl` (06:00 МСК) и `calendar_refresh` (1-го числа 03:00 МСК). Дополнительно — два опциональных под `RUSTATS_ANALYTICS_SCHEDULER_ENABLED=true`: `analytics_hourly` (:15) и `analytics_daily` (07:20). Если scheduler-флаг выключен — работает только `daily_etl` + `calendar_refresh`, прочие cron-ы не регистрируются.

### `is_listed` vs VariantGroupPicker

Скрытие индикатора через `is_listed=False` — это **только** про карточку в `/category/{slug}`. Сам индикатор по-прежнему доступен по `/indicator/{code}`, отдаётся API, индексируется поисковиками, попадает в sitemap. Если нужно полностью убрать индикатор — это другой механизм (`is_active=False` + ручная чистка sitemap-генератора).

### CPI level «Индекс» режим (frontend)

Фронт строит cumulative index с базы `2000-01 = 100` через `frontend/src/lib/useIndicatorViewModeData.js::buildCumulativeIndex`. История 1991–1999 обрезается: январь 1992 = 345% месячный → цепное произведение через 9 лет даёт сотни тысяч и шкала становится нечитаемой. Это **не** ошибка, это осознанный cutoff.

### `/api/docs` (Swagger) на проде

`main.py` регистрирует Swagger только если `settings.debug=True`. На проде `RUSTATS_DEBUG=false` (см. `docker-compose.yml`) — Swagger недоступен. Локально для разработки: `RUSTATS_DEBUG=true` в `.env` → доступно `/api/docs`, `/api/redoc`, `/api/openapi.json`.

### Forecast retrain после деплоя (новые derived)

Когда деплой добавляет **новые derived-индикаторы** (через правки `seed_data.py` + `DERIVED_SPECS`), `entrypoint.sh` идемпотентно отрабатывает seed (создаёт/обновляет строки `indicator`), но **forecast retrain не запускается автоматически**. Daily ETL-job переобучает прогнозы только тех индикаторов, у которых на этом тике добавились новые точки в `data_points` — для свежесозданного derived это произойдёт только после следующего ревизии источника.

Симптом: `/api/v1/indicators/<new-derived-code>/forecast` возвращает `null` несколько часов или дней. Так было 2026-05-07 после деплоя GDP nominal/real split — три из восьми GDP-индикаторов отдавали `null` до ручного `--forecast-only` retrain.

Mitigation: после любого деплоя, добавляющего derived, выполнить ручной retrain в правильном порядке (источники → derived):

```bash
docker compose exec backend python -c \
  "import asyncio; from app.services.forecast_pipeline import retrain_indicator_forecast; \
   asyncio.run(retrain_indicator_forecast('<source_code>'))"
```

Каскадный retrain `derived_from_source` стратегии подхватит зависимые индикаторы. После — `redis-cli FLUSHDB` для сброса `fe:*:forecast` ключей.

### Inflation-weekly: семантика и источник

`inflation-weekly` ряд = **недельный прирост ИПЦ к предыдущей неделе** (`100.XX` означает «×1.00XX»), **не** накопленная с начала месяца. Парсер `rosstat_weekly_cpi` ходит за HTML-бюллетенями Росстата только за `today.year`; для 2022–2025 — XLSX-fallback (~110 продов × веса корзины). HTML перезаписывает XLSX при коллизии. В `indicator_data` нет колонки `data_source` — различить «из бюллетеня» vs «из приближения» можно только косвенно через `fetch_log`.

Январский трёхнедельный «выпад» (одна точка с 23 декабря по 12 января ~100.45/101.26) — штатный новогодний бюллетень Росстата, а не баг.

### Calendar weekly events

Три `WeeklySpec` в `calendar_seed.py`: четверг 16:00 МСК — Международные резервы РФ (CBR, importance=2, по СCРД МВФ); пятница 11:00 — Денежная база узкая (CBR, importance=1); среда (без точного времени) — недельный ИПЦ (Росстат, importance=2). Реальные даты могут смещаться из-за длинных праздничных периодов (например, в мае 2026 reserves публикация смещена с четверга 7 мая на пятницу 8 мая) — генератор этого не учитывает и ставит на канонический weekday. Для точных дат в перспективе подключить парсер `cbr.ru/Queries/FileSource/96347/vCalendar.ics`.

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

When suggesting refactors, use this language. Use the **Indicator/DataPoint/Derived/Forecast/Parser/Strategy** vocabulary above for the domain.
