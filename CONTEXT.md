# Forecast Economy — Project Context

**Last updated:** 2026-05-22 (звонок «всё доделать» + ревизия «ты уверен в данных?»: Phase 2 labour (wages-nominal + unemployment унифицированы в view-mode families), Phase 3 housing (housing-price-{primary,secondary} с YoY % режимом), Phase 4 rates rename (credit-rate-{corp,ind}-short и deposit-rate переименованы на общие имена, term split через VariantGroupPicker), Phase 5 daily-aggregation (виртуальные week/month/quarter/year avg для key-rate, ruonia, cbr-fx-*, gold-price, brent, btc-usd через `applyAggregateTransform` на фронте). `tradeViewModes.js` → `viewModeFamilies.js` (общий реестр для всех семей). `wages-nominal-annual` — annual sibling с историей 1991-2014, доступен как режим «Годовое (с 1991)» (фикс annual-in-monthly trap). Search haystack расширен на `seo_keywords` (поддержка корней/синонимов: «зарпл» → wages-nominal, wages-real, wages-yoy, wages-index). +3 trap'ы: `Source-depth trap` + `Browser-cache trap при rebuild frontend` + `Annual-in-monthly mixing trap`. См. ADR-0006 «Indicator card unification».
**Part of:** [`AGENTS.md`](AGENTS.md) (точка входа для AI-агента).
**See also:** [`README.md`](README.md), [`docs/workflow.md`](docs/workflow.md), [`docs/enterprise_resilience.md`](docs/enterprise_resilience.md), [`docs/data_sources.md`](docs/data_sources.md), [`docs/cbr_sources.md`](docs/cbr_sources.md), [`docs/analytics_api_inventory/`](docs/analytics_api_inventory/), [`docs/adr/`](docs/adr/).

> Domain glossary for the project. Every architectural discussion, ADR, and refactoring proposal should use the terms defined here. If a discussion needs a new term, add it to this file before finishing.

## Документы рядом

| Файл | Назначение |
|------|------------|
| [`AGENTS.md`](AGENTS.md) | Точка входа для AI-агента: с чего начать, как читать документацию, как её актуализировать |
| [`README.md`](README.md) | Высокоуровневая карта стека, API, indicators, deploy |
| [`docs/workflow.md`](docs/workflow.md) | Модель работы, локальный dev, прод-деплой, smoke C |
| [`docs/enterprise_resilience.md`](docs/enterprise_resilience.md) | Rate-limit, CSP, asset-hash trap, бэкапы, чеклист канарейки |
| [`docs/data_sources.md`](docs/data_sources.md) | Точная карта «индикатор → файл/endpoint» для всех 75 source-индикаторов. Single source of truth — обязательно обновлять при правке источника |
| [`docs/cbr_sources.md`](docs/cbr_sources.md) | Все не-Росстат источники: ЦБ РФ + Минфин (10 парсеров, детальные парсер-разделы) |
| [`docs/analytics_api_inventory/`](docs/analytics_api_inventory/) | Инвентарь Yandex API (Metrika, Webmaster) + статус реализации |
| [`docs/adr/0001`](docs/adr/0001-derived-indicators-engine-shape.md) | Engine shape: 28 derived через `DERIVED_SPECS` + 9 чистых ops |
| [`docs/adr/0002`](docs/adr/0002-derived-always-reflects-source.md) | Инвариант: derived всегда отражает source (`bulk_upsert` идемпотентен) |
| [`docs/adr/0003`](docs/adr/0003-seo-single-source-server-rendered.md) | SEO single-source: backend SSR через `__spa-index.html` + Vite asset discovery |
| [`docs/adr/0004`](docs/adr/0004-rosstat-russian-canonical-sdds-deprecated.md) | Rosstat русский canonical, SDDS English deprecated. Pilot: gdp-nominal end-to-end 2026-05-10 |
| [`docs/adr/0005`](docs/adr/0005-official-calendar-source-bound.md) | Calendar source-bound: public dates only from official source/rule with provenance |
| [`docs/adr/0006`](docs/adr/0006-indicator-card-unification.md) | Indicator card unification: ось «карточка vs derived vs variant vs frequency» (звонок 2026-05-22) |

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

**Доступ к rosstat.gov.ru из tooling/curl/python**: всегда через `--cacert backend/certs/russiantrustedca2024.pem` (или `verify=` в requests). Без сертификата `rosstat.gov.ru` отдаёт SSL-handshake error / Chrome `chrome-error://chromewebdata/`. `eng.rosstat.gov.ru` работает по стандартному cert, но это SDDS-зеркало и лагает на год (см. trap «SDDS English vs Rosstat русский»).

**Перечисление файлов раздела rosstat**: для категории `/statistics/<section>` (например `/statistics/price`) — `curl --cacert <cert> https://rosstat.gov.ru/statistics/price -o page.html && grep -oE 'href="[^"]*\.xlsx?"' page.html | sort -u` даёт полный список XLSX в разделе. Для `/statistics/price` (категория «Цены») — **94 XLSX** (audit 2026-05-08).

**Политика канонического источника (2026-05-10)**: для индикаторов с источником в Росстате — **only** русский XLSX из `rosstat.gov.ru/statistics/<section>/`, **never** SDDS-английский (`eng.rosstat.gov.ru/storage/mediabank/SDDS_*.xlsx`). См. trap «SDDS English vs Rosstat русский» и план миграции.

### Parser

Конкретная реализация ETL для одного формата источника. Базовый класс `BaseParser` (`backend/app/services/base_parser.py`) — **template-method**: финальный `run()` оркеструет fetch → parse → validate → upsert → forecast retrain → cache invalidate в одном месте. Дочерние классы реализуют `_fetch_and_parse(db, indicator, cfg, fetch_log) -> (points, source_url)` (обязательно) + опциональные hooks `_validate(points, cfg)`, `_post_upsert(...)`, `_handle_forecasts(...)`. Это устранило ~1100 строк boilerplate, унифицировало статусы `fetch_log` и каскад retrain'а.

**Текущее количество:** 23 парсер-типа в `PARSER_REGISTRY` (см. `rosstat_cpi_parser.py`, регистрируется как singleton-импорт из исторических соображений — артефакт). Парсер-файлов 24 (включая `base_parser.py`). Один парсер обычно обслуживает несколько индикаторов одного источника (CbrFxParser → 3 валюты; RosstatCpiParser → 4 листа CPI; CbrDataServiceParser → много ставок ЦБ).

### Derived indicator

Индикатор без собственного источника. Считается чистой функцией от других индикаторов. `parser_type = "derived"`. Запускается из `CalculationEngine.run_for_updated_sources` после daily ETL.

**Инвариант (ADR-0002):** *derived[t] всегда выводимо из текущего state source-рядов на момент последнего ETL-батча с новыми строками* (`records_added > 0`). При любом таком ETL прогоне CalculationEngine полностью пересчитывает все 28 derived-рядов от первой до последней точки (idempotent — `bulk_upsert` записывает только реально изменившиеся значения). Не «инкрементальный накопительный снимок», а чистая функция source. Если source ревизуется задним числом — derived перетягиваются автоматически на следующий же день с новыми строками (см. ADR-0002 «Limit of the invariant — pure-revision day»).

**Граница инварианта.** Инвариант односторонний: `bulk_upsert`-only. Если source-точка **удаляется** вручную (DELETE из IndicatorData), соответствующая derived-точка остаётся в БД как осиротевшая — engine не знает, что нужно её удалить. Это явный compromise (см. ADR-0002): автоматическое удаление derived создавало бы риск массовой потери данных при ошибке pure op. Ручные коррекции source требуют ручной чистки derived или прогона `scripts/rebuild-all-derived.py`.

Реестр операций (`backend/app/services/derived_ops.py`) — **10 чистых функций** без `db`/`async`:
- `quarterly_index` — chained product 3 месячных индексов CPI (для `*-quarterly`).
- `december_to_december` — годовая инфляция «Dec_Y / Dec_{Y-1} − 1» (для CPI-семьи и PPI `*-annual`; пришла на смену rolling-12M в 2026-05-06, см. ADR-0001 «Subsequent additions»).
- `annual_sum` — сумма квартальных или 12 месячных значений (для `gdp-{nominal,real}-annual`).
- `yoy`, `qoq` — рост к 12 мес назад / к предыдущему кварталу (в %).
- `yoy_abs` — **абсолютная** разница к 12 мес назад в единицах источника (звонок 2026-05-22, для balances со знаком, где % бессмыслен).
- `quarterly_avg`, `rolling_avg` — для unemployment.
- `wages_real` — особая, 2 источника (`wages-nominal`, `cpi`).
- `annual_inflation` — устаревшая op (rolling-12M product), сохранена в файле, но **не используется** в `DERIVED_SPECS`. Кандидат на удаление при следующей чистке.

Реестр спецификаций (`calculation_engine.DERIVED_SPECS`) — **29 entries**:

- **CPI семейство:** `inflation-quarterly` ← `cpi`, `inflation-annual` ← `cpi`, и аналоги для `cpi-food/nonfood/services` (8 spec'ов).
- **PPI:** `ppi-yoy`, `ppi-annual`.
- **GDP:** `gdp-{yoy,qoq}` ← `gdp-nominal`, `gdp-real-{yoy,qoq}` ← `gdp-real`, `gdp-{nominal,real}-annual` (annual_sum).
- **Wages/Unemployment:** `wages-real`, `wages-yoy`, `unemployment-{quarterly,annual}`.
- **Trade/External:** `exports-{yoy,qoq}`, `imports-{yoy,qoq}`, `trade-balance-yoy-abs`, `current-account-yoy-abs`. Старый `current-account-yoy` (%) **депрекейтнут** в seed_data как `is_active=false`, в DERIVED_SPECS убран — для balances со знаком процент YoY бессмыслен.
- **Other:** `ipi-yoy`, `housing-yoy-{primary,secondary}`.

**Frontend-only режимы (звонок 2026-05-22).** Поверх backend-derived'ов есть единый реестр view-mode families: `frontend/src/lib/viewModeFamilies.js::VIEW_MODE_FAMILIES`. Каждая семья (`exports`, `imports`, `trade-balance`, `current-account`, `*-monthly`, `wages-nominal`, `unemployment`, `housing-price-{primary,secondary}`) маппит parent → массив `modes[]`: `{mode, label, code, unit?, transform?}`. Routing в `IndicatorDetail.jsx`: `findViewModeFamily(code)` → `?mode=…` подменяет dataPoints, телеметрию и заголовок без перехода на другой URL.

Frontend-only трансформации:
- `applyMoMTransform(points)` — MoM% для `*-monthly` (Phase 1): `(val_t/val_{t-1} − 1) * 100`, backend spec сознательно не заводится.
- `applyAggregateTransform(points, granularity)` — bucket-avg для daily-индикаторов (Phase 5): `granularity ∈ {week, month, quarter, year}` → среднее по bucket'у с датой = конец bucket'а. Применяется к любому `indicator.frequency === 'daily'` (`key-rate`, `ruonia`, `cbr-fx-*`, `gold-price`, `brent`, `btc-usd`) без новых backend-derived.

Phases:
- Phase 1 — trade (4 quarterly + 4 monthly семьи).
- Phase 2 — labour: `wages-nominal` (4 режима: Номинальная / Реальная / YoY / Индекс), `unemployment` (3 режима: Месячно / Квартально / 12М avg).
- Phase 3 — housing prices (Уровень индекса / YoY %).
- Phase 5 — daily aggregation (виртуальные week/month/quarter/year avg).

Phase 4 (ставки) НЕ использует viewModeFamilies: `credit-rate-corp-short`, `credit-rate-ind-short`, `deposit-rate` — единые карточки с **VariantGroupPicker** (срок: До 1 года / 1-3 года / Свыше 3 лет). Это не «режим отображения», а отдельные индикаторы по сроку.

### Forecast

Прогноз индикатора на N шагов. Хранится в `Forecast` (метаданные + `is_current`) + `ForecastValue` (точки `(date, value, lower_bound, upper_bound)`).

**Реестр стратегий** (`backend/app/services/forecast_strategies/registry.py`) — диспетчеризует прогноз-генерацию по полю `Indicator.model_config_json.forecast_strategy`:

| Имя | Когда применяется | Что делает |
|---|---|---|
| `cpi_combined` | `cpi`, `cpi-food`, `cpi-nonfood`, `cpi-services` | Гонит `train_monthly_cpi` (помесячный) + `train_inflation_12m` (12-мес скользящий) и каскадит результат на `*-quarterly` derived |
| `housing_quarterly` | `housing-price-primary`, `housing-price-secondary` | `train_quarterly_housing` — 1:1 port `Прогнозы_цены_на_жилье (1).ipynb` Никиты (multi-window OLS на log-diff + outlier-clip + corr-filter + iv-weighted blend + per-step median). Byte-exact с notebook'ом |
| `gdp_nominal_quarterly` | `gdp-nominal` | `train_gdp_nominal_quarterly` (multi-window OLS на log-diff, без блендинга) — 1:1 port `Прогноз_номинальный_ВВП.ipynb` |
| `gdp_real_quarterly` | `gdp-real` | `train_gdp_real_quarterly` — то же ядро `_train_gdp_quarterly_port` на ряду реального ВВП; byte-exact с notebook'ом |
| `gdp_consumption_quarterly` | `gdp-consumption` | `train_gdp_consumption_quarterly` — то же ядро `_train_gdp_quarterly_port` на ряду расходов домохозяйств (методология семьи ВВП по просьбе Никиты; отдельного notebook'а нет) |
| `gdp_government_quarterly` | `gdp-government` | `train_gdp_government_quarterly` — то же ядро `_train_gdp_quarterly_port` на ряду гос.потребления |
| `ppi_monthly` | `ppi` | `train_ppi_monthly` (k=1..4, monthly lags log-diff) — 1:1 port `Прогноз_ИЦП.ipynb` |
| `approved` | исторически: `cpi-*`, `gdp-nominal`, `ppi`, `housing-price-*` | Использует ручные значения из `model_config_json.approved_forecast_values` (массив `{date, value}`) без переобучения. **В live-конфиге не используется** — все индикаторы переведены на свои live-стратегии (`ppi → ppi_monthly`, 2026-05-16). Strategy сохраняется в registry для обратной совместимости и тестовых сценариев |
| `derived_from_source` | Все *-yoy, *-qoq, *-annual derived с `derived_forecast: {source_code, operation, model_name}` (включая `housing-yoy-primary`, `housing-yoy-secondary`) | Применяет ту же чистую op (yoy / qoq / december_to_december / annual_sum / real_from_yoy) к **прогнозу** source-индикатора. Каскадный retrain срабатывает после успеха source |
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

**Calendar refresh** (`calendar_refresh` job): отдельный daily cron 03:00 МСК прокатывает `seed_calendar(months_ahead=12)`, который теперь вызывает official calendar ingest (`calendar_sources.official_calendar`). Public API отдаёт только source-bound rows: `date_confidence IN ('official_explicit', 'official_rule')`, `is_estimated = false`, заполнены `event_key`, `source_url`, `source_hash`, `last_seen_at`. Estimated rows и legacy backfill без provenance остаются внутренним fallback и скрыты (см. термин «Calendar event» и ADR-0005).

**Analytics scheduler** (опционально): если `RUSTATS_ANALYTICS_SCHEDULER_ENABLED=true` — два дополнительных cron-а: hourly :15 (Yandex Metrika reporting sync) и daily (management snapshot). По умолчанию выключен.

### Category

Функциональная группа индикаторов: Цены, Ставки, Финансы, **Рынок труда**, ВВП, Торговля, Бизнес, Население, Наука. Девять штук. На главной — сетка карточек, на `/category/{slug}` — список индикаторов в категории.

В БД хранится русское имя (`Цены`, `Рынок труда`); URL использует slug (`prices`, `labor`). Маппинг — `frontend/src/lib/categories.js` (включает `seoTitle`/`seoDescription`, идентичные backend `seo_content.py::CATEGORY_META.title/description` — это **зеркало backend SSR**, не источник правды; см. ADR-0003).

### Calendar event

Запись в `EconomicEvent` для расписания публикаций (релиз CPI Росстата, заседание совета директоров ЦБ, недельный ИПЦ Росстата, международные резервы РФ). После ADR-0005 public calendar **source-bound**: событие показывается пользователю только если `date_confidence = official_explicit` (официальная дата из календаря/ICS/страницы) или `official_rule` (дата рассчитана по опубликованному правилу + versioned `ru_working_calendar` с source_url), `is_estimated = false`, и заполнены `event_key`, `source_url`, `source_hash`, `last_seen_at`. `estimated` rows и миграционные legacy rows без provenance скрыты из `/api/v1/calendar`, `/upcoming` и iCal. Переносы обновляются по stable `event_key`, старая дата хранится в `metadata_json.reschedule_audit`. Статус `scheduled` → `released` автоматически промотится по `scheduled_date < today`.

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
- **Frontend instrumentation:** init-параметры Метрики, таксономия goals (`reachGoal`), UTM-разметка share-ссылок и URL cleanup описаны в [`docs/analytics_api_inventory/frontend_instrumentation.md`](docs/analytics_api_inventory/frontend_instrumentation.md). Webvisor 2 + form analytics включены через `webvisor:true, triggerEvent:true, childIframe:true` (2026-05-10). Каждый клик в `lib/track.js::events` дублируется в `frontend_events` через `POST /api/v1/analytics/events`.

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

В `backend/app/main.py` lifespan регистрируются **два обязательных** APScheduler job'а: `daily_etl` (06:00 МСК) и `calendar_refresh` (1-го числа 03:00 МСК). Дополнительно — два опциональных под `RUSTATS_ANALYTICS_SCHEDULER_ENABLED=true`: `analytics_hourly` (:15) и `analytics_daily` (07:20). С 2026-05-22 добавлен `ticker_live_pull` (interval 5s, `coalesce=True`, `max_instances=1`) — fetch MOEX/Binance/CBR-fallback в Redis для LiveTicker. Если scheduler-флаг выключен — работает только `daily_etl` + `calendar_refresh` + `ticker_live_pull`, analytics cron-ы не регистрируются.

### Live ticker: MOEX-приоритет с CBR-fallback для FX

Источники (`backend/app/services/ticker_sources/`):
- **MOEX ISS** — USD/RUB (`USD000UTSTOM`), CNY/RUB (`CNYRUB_TOM`), Brent (ближайший фьючерс `BR-X.Y` на FORTS, динамически определяется по `LASTTRADEDATE`). ISS возвращает 4 строки marketdata по бордам — реальные сделки на **CETS**, остальные пустые.
- **Binance public** — BTC/USDT (`/api/v3/ticker/24hr`).
- **ЦБ XML_daily fallback** (звонок 2026-05-22) — для FX когда MOEX отдал `LAST=None` на всех бордах. EUR/RUB на MOEX после санкций ЕС март-2024 **фактически мёртв** — у `EUR_RUB__TOM` LAST всегда null. Fallback тянет `https://www.cbr.ru/scripts/XML_daily.asp` (сегодня + вчера для % change) и подмешивает с пометкой `market_open=False, source="ЦБ РФ"`.

Frontend (`frontend/src/components/LiveTicker.jsx`): `useQuery` polling 4с, sticky-bar над Navbar (`fixed top-0 z-[110]`). Типографика **единая** для всех пяти snapshot'ов — `text-text-primary font-semibold` независимо от `market_open` и `source` (различие источника живёт в `title`-тултипе). Цена показывается всегда если `price > 0`, чтобы CBR-fallback не визуально ломал ряд.

Эндпоинт `/api/v1/ticker/live` (`backend/app/api/ticker.py`) читает Redis-снапшоты с TTL 30s. APScheduler job `ticker_pull_job` пишет их каждые 5s — клиент видит лаг ≤ 9s в худшем случае.

### `is_listed` vs VariantGroupPicker

Скрытие индикатора через `is_listed=False` — это **только** про карточку в `/category/{slug}`. Сам индикатор по-прежнему доступен по `/indicator/{code}`, отдаётся API, индексируется поисковиками, попадает в sitemap. Если нужно полностью убрать индикатор — это другой механизм (`is_active=False` + ручная чистка sitemap-генератора).

### Frequency switcher: пары индикаторов разной частоты

T3 (2026-05-12): для индикаторов внешней торговли публикуем одновременно квартальные (history с 1994) и месячные (history с 1997 для goods, с 2018 для services) ряды. Чтобы UI/SEO не плодили дубли — единая модель:

- **Primary** (родитель) = quarterly индикатор, `is_listed=True`, появляется в категориях и sitemap. В `model_config_json` ставится `alternate_frequencies = {"monthly": "<code>-monthly"}`.
- **Secondary** (counterpart) = monthly индикатор `<code>-monthly`, `is_listed=False`, `forecast_steps=0`, скрыт из категорийного листинга через `INDICATOR_HIDDEN_FROM_LISTING`. В `model_config_json` ставится `primary_indicator_code = "<parent_code>"`.

Backend контракт:
- `IndicatorRead` отдаёт оба поля (`alternate_frequencies`, `primary_indicator_code`). См. `backend/app/schemas.py`.
- `seo_renderer.render_indicator_html` рендерит `<link rel="alternate" hreflang="ru-RU">` на counterpart URL — поисковики видят семантическую пару `/indicator/exports` ↔ `/indicator/exports-monthly`.

Frontend контракт:
- Чистая логика — `frontend/src/lib/frequencySwitcher.js::buildFrequencyItems`. На неё опирается `FrequencySwitcher.jsx`, который рисует tabs «Квартальные / Месячные» над графиком (рядом с `VariantGroupPicker`/`CpiViewModePicker`).
- Переключение URL-based: каждая частота — отдельная карточка с собственным SSR canonical (SEO-благоприятно). `IndicatorChart`, telemetry, datatable читают `indicator.frequency` → автоматически адаптируются под помесячный/поквартальный formatter без отдельной логики.
- Yandex.Metrika goal `frequency_switch` (см. `track.js::events.FREQUENCY_SWITCH`) — каждый клик switcher логируется с `from/to/fromFrequency/toFrequency/indicatorCategory`.

Trap для будущих расширений: если добавляешь третью частоту в пару (например `inflation-weekly` к существующим `cpi`/`cpi-monthly`) — поле `alternate_frequencies` это map `{[freqKey]: code}`, поддерживает любое количество ключей. UI отрисует столько tabs, сколько entries (тест `frequencySwitcher.test.js::handles 3-way switcher` — фиксирует контракт).

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

### SDDS English vs Rosstat русский

**Trap**: SDDS-XLSX на `eng.rosstat.gov.ru` (`SDDS_*.xlsx`) — это IMF-зеркало в формате «2010 = 100 chained cumulative index», публикуется с лагом ~год (комментарий в `rosstat_sdds_fetcher.py:6-9`). Парсеры `rosstat_sdds_ppi`, `rosstat_sdds_housing`, `rosstat_sdds_gdp`, `rosstat_sdds_labor`, `rosstat_sdds_ipi`, `rosstat_population` (часть) тянут оттуда. Но **первичная публикация Росстата** — на `rosstat.gov.ru/statistics/<section>/` в формате MoM/QoQ % (100 = предыдущий период) и с историей с 1998+ (для PPI), 1991+ (для CPI), 1995+ (для ВВП).

**Симптомы расхождения с rosstat**:
1. **Format mismatch**: наша DB хранит cumulative index (PPI = 311.40), руководитель открывает rosstat и видит MoM (PPI = 100.6%) — разные числа, кажется баг.
2. **Короткая история**: SDDS даёт PPI с 2011, Housing с 2016, ВВП с 2011 — потому что 2010=100 base. Русский Росстат — глубже.
3. **Stale latest**: SDDS лагает на год. Текущий месяц/квартал в SDDS может отсутствовать или быть приближённым.

**Audit категории «Цены и инфляция» (2026-05-10)** (см. также chat-уровень): CPI 4/4 индикаторов 100% совпадают с rosstat (парсер `rosstat_cpi_xlsx` → `ipc_mes_*.xlsx` правильный). PPI и Housing (3 индикатора) — все из SDDS, требуют миграции на русский Росстат.

**Политика**: для всех новых индикаторов и при правке существующих SDDS-парсеров — переключение на русский Росстат. SDDS используется **только** как fallback, если русский эквивалент недоступен (на момент 2026-05-10 не известно ни одного такого случая в категории Цены). См. [ADR-0004](docs/adr/0004-rosstat-russian-canonical-sdds-deprecated.md) — содержит migration pattern и pilot evidence для `gdp-nominal`.

**Migration trap для ETL/forecast**: при замене source формата (2010=100 → MoM%) одного и того же `code` все исторические точки переписываются через `bulk_upsert WHERE value <> excluded.value` (ADR-0002). Frontend value formatter / chart unit и forecast model обучены на старом формате — оба требуют обновления одновременно с парсером (см. trap «Forecast retrain после деплоя» — здесь применяется тот же mitigation). Для unit-preserving миграций (например, `gdp-nominal` млрд руб → млрд руб) frontend трогать не нужно, retrain прогноза идёт каскадно автоматически из `run_etl_for_indicator`.

**Pilot подтверждение pattern (2026-05-10)**: `gdp-nominal` мигрирован end-to-end на локальном docker stack. Переключение `gdp_source: "official_quarterly", gdp_sheet: "2"` в `seed_data.py` → 60/60 точек переписаны (Q4 2025: 60516.7 → **62354.1** = rosstat publication ✓), derived gdp-yoy/qoq/annual пересчитаны через `rebuild-all-derived.py` (127 точечных изменений), forecast cascade retrain автоматически. Никаких изменений в коде парсера не потребовалось — `parse_rosstat_gdp_quarter_grid_xlsx` уже умеет произвольный sheet через config.

**Категория «ВВП» полностью мигрирована (2026-05-10)**: pilot (`gdp-nominal`) + rollout (`gdp-consumption`, `gdp-government`, `gdp-investment`). Для use-компонентов потребовался новый источник `GDP-quarters-of-use-1995-4kv-2025.xls` (legacy .xls binary, OLE2) → расширен `fetch_rosstat_static_xlsx` (теперь принимает оба magic — XLSX `PK\x03\x04` и XLS `\xd0\xcf\x11\xe0`), новая ветка парсера `gdp_source: "official_use"` (xlrd, multi-row layout), 4 unit-теста через synthetic .xls fixture (`xlwt==1.3.0` в requirements). Rollout pipeline test: `0 new, 0 updated` для всех 3 индикаторов — best-case migration, SDDS уже подтянул rosstat, миграция проактивная (защита от будущих лагов + canonical source policy без disruption). SDDS-ветка `fetch_sdds_xlsx("gdp")` больше не используется ни одним active индикатором.

**Категории «Демография», «Промышленность», «Труд», «Цены» полностью мигрированы (2026-05-10)**: 11 индикаторов переведены на canonical русские источники (commits cf08878 / 13a0251 / 5317421 / 0dc61b8 + housing pending). Pattern «path P (compat)» закрепился: для индикаторов где canonical Rosstat публикует только MoM/QoQ% (без cumulative index), парсер читает последнюю DB-точку и chains новый relative change → один новый datapoint per ETL run, исторический ряд от прошлой SDDS-стадии остаётся, gradual migration, frontend/forecast model не требуют изменений. Применён в `rosstat_ipi_parser` (chain monthly, нормализация 2023=100), `rosstat_ppi_parser` (chain monthly из PDF), `rosstat_housing_parser` (chain quarterly из PDF, primary+secondary). Для labor (4 индикатора) — sociomonomic PDF report повышен из supplementary до primary source (нет comprehensive monthly XLSX по labor на rosstat сайте). Подробности по каждой категории — в [ADR-0004 «Subsequent additions»](docs/adr/0004-rosstat-russian-canonical-sdds-deprecated.md).

**GDP history extension до 1995 (2026-05-10)**: 5/5 GDP source-индикаторов продлены с 60 до **124 точек** (1995-Q1 → 2025-Q4) через **ratio-splice на overlap-году 2011** — pure-функция `splice_at_overlap(history, modern, overlap_year)` в `rosstat_gdp_parser.py`. Калибрует `ratio = mean(modern_2011) / mean(history_2011)`, scale'ит historical-точки (year < 2011) к base modern-методологии (для nominal: ОКВЭД2007 → ОКВЭД2, ratio ~1.074; для real: в ценах 2008 → в ценах 2021, ratio ~2.81). Standard economic-series splice техника (ОЭСР/МВФ practice). Конфиг per индикатор — `gdp_history_sheet` + `gdp_overlap_year` в `model_config_json`. Закрыта прямая жалоба руководителя 08.05.2026 «у Росстата с 1995, у нас почему-то с 2011». Trap, выловленная на data: Rosstat Excel хранит часть значений как СТРОКИ с Russian decimal + footnote suffix («1662,82)» = 1662,8 + footnote 2) → добавлен `_parse_ru_number` хелпер.

### Source-depth trap (новый индикатор)

Парсер фетчит N лет, БД хранит M < N. Симптом — `/indicator/<code>` начинается с 2020 (или 2015), хотя источник публикует с 1991/1995. Это видно только пользователю, который сравнивает с публикацией Росстата/ЦБ; внутренний мониторинг молчит.

**Примеры обнаруженных пробелов** (звонок 2026-05-22):
- `wages-nominal` начинался с 2015 → Росстат публикует с 1991. Закрыто через `wages_historical.py` (immutable seed годовых точек 1991-2014).
- `key-rate` начинался с 2013-09 → ставка рефинансирования ЦБ с 1992. Закрыто через splice на overlap-точке 2013-09-13 (`refinancing_rate_historical.py`).
- `gdp-*` начиналось с 2011 → Росстат публикует с 1995 (ОКВЭД2007). Закрыто через ratio-splice на overlap-year 2011.
- `housing-price-{primary,secondary}` — backfill 1998-2014 через `housing_historical.py`.
- `inflation-weekly` начинается с 2022-01-10 → Росстат публикует с 2003, но **архив до 2022 утерян** (gks.ru не работает, Wayback не имеет нужных URL); это технический предел, не наша недоработка.

**Правило:** при добавлении любого нового парсера / индикатора — **обязательная проверка по чеклисту в `AGENTS.md::Шаг 4`** (`Source-depth invariant`). Если источник даёт глубже чем в seed — заводим `<name>_historical.py` immutable seed.

### Browser-cache trap при rebuild frontend

После `docker compose build frontend && up -d frontend` пользователь в обычном окне Chrome может видеть **unstyled HTML** (чёрный фон, синие подчёркнутые ссылки). Причина — браузер держит старый HTML в **disk cache** и пытается загрузить ассеты со старыми hashes, которые в новом контейнере отсутствуют → 404 → React shell не загрузился → unstyled.

Это **не** asset-hash trap (см. выше) — backend и frontend синхронизированы, ассеты на свежих hashes отдаются 200. Проблема в кеше **самого браузера** пользователя.

**Правило:** после rebuild frontend для демонстрации — открывать в **incognito** или делать **Cmd+Shift+R** (hard reload, минует disk cache). В DevTools → Network → Disable cache на время тестирования.

### New indicator initial ETL trap (закрыт автоматикой 2026-05-22)

После `seed_data.upsert_indicators()` создаёт новый indicator с `parser_type != "derived"` и `is_active=true`, **первый ETL** по нему ранее не запускался автоматически. Daily ETL job ходит в 06:00 МСК — между deploy и 06:00 новый индикатор стоял пустой, frontend показывал «нет данных».

**Случай 2026-05-22:** `deposit-rate-medium` и `deposit-rate-long` (звонок 21-05, правка C3) — оба добавлены в seed_data 21-05, daily-job не успел отработать, при ревизии 22-05 у обоих было 0 точек. Триггернул вручную → 147 точек 2014-2026.

**Закрытие:** в `app/main.py::lifespan` добавлен background task `_catch_up_empty_indicators()` — при startup ищет все `is_active=True AND parser_type != "derived"` индикаторы с `COUNT(indicator_data) = 0` и триггерит ETL для них. Запускается как `asyncio.create_task(...)`, не блокирует uvicorn ready. Применяется один раз при каждом старте контейнера. Derived подхватятся cascade'ом после source.

**Правило:** ничего не делать вручную. Если контейнер был запущен, а у нового source-индикатора всё ещё 0 точек — смотреть логи backend на `Startup catch-up: <code> failed: ...` (источник недоступен, конфиг битый и т.п.).

### Annual-in-monthly mixing trap (backfill в чужую частоту)

Парсер добавляет в indicator с `frequency=monthly` годовые точки (1 января каждого года). Frontend chart label остаётся «помесячно» (из `frequency`), а на графике рывок: 24 точки за 24 года выглядят как 24 month-точки с гэпами. Пользователь видит ложную динамику, фигуры месяц-к-месяцу несравнимы с годом.

**Случай 2026-05-22:** `wages-nominal` (frequency=monthly с 2015) → backfill 24 годовых точек 1991-2014. График показывал «ПОМЕСЯЧНО» + рваный ряд. **Фикс:** годовая история вынесена в отдельный `wages-nominal-annual` (`frequency=annual`, `is_listed=false`), доступна как режим «Годовое (с 1991)» через `viewModeFamilies`. Monthly indicator теперь содержит только monthly-точки.

**Правило:** **никогда** не лить точки чужой частоты в существующий indicator. Если source даёт annual до 1998 и monthly с 2015 — это **два разных indicator'а** с одним visual entry (через view-mode family). Аналогично quarterly история + monthly свежак, weekly прошлое + daily настоящее, и т.п.

**Проверка при backfill:** перед `bulk_upsert` сверить `target.frequency` с фактической частотой добавляемых точек. Если расхождение — заводим sibling indicator + добавляем режим в `viewModeFamilies`. См. чеклист в `AGENTS.md::Шаг 4` (новый пункт «Frequency consistency»).

### Calendar source coverage

Legacy `WeeklySpec` / `typical_day` builders в `calendar_seed.py` оставлены только для debug/tests старой плотности календаря. Public ingest идёт через `calendar_sources.official_calendar`: CBR official daily rules (`indcalendar`) для FX/RUONIA/gold; CBR official ICS (`indcalendar` / `vCalendar.ics`) для резервов, M0/M1/M2, кредитов/депозитов, ставок, ипотеки, внешнего сектора, долга; CBR official monetary-policy schedule (`cbr.ru/dkp/cal_mp/`) для заседаний и резюме по ключевой ставке; Rosstat/Minfin rule-events только по опубликованным правилам и versioned working calendar. После добора 2026-05-10 local source-bound coverage: 46/76 source codes, 1208 public events, `bad_public_rows=0`. Если источника/правила нет — событие не показывается, пока не будет донабрано через official parser/rule.

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
