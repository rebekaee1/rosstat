# Forecast Economy — Аналитическая платформа экономических индикаторов России

Платформа для сбора, прогнозирования и публикации **104 экономических индикаторов** России (Росстат, ЦБ РФ, Минфин). Прогнозы по 8 стратегиям, ежедневный ETL, SSR + SEO, embed-виджеты, календарь публикаций, аналитический MCP. Доступна публично на [forecasteconomy.com](https://forecasteconomy.com).

**Точка входа в документацию:** [`CONTEXT.md`](CONTEXT.md) — глоссарий и архитектурный язык.
**Рабочий процесс, деплой:** [`docs/workflow.md`](docs/workflow.md).
**Источники данных:** [`docs/cbr_sources.md`](docs/cbr_sources.md) (CBR + Минфин); Rosstat-парсеры — в `CONTEXT.md`.
**Архитектурные решения:** [`docs/adr/`](docs/adr/) (нумерованные ADR).

## Архитектура

```
                     ┌──────────────────┐
                     │     Caddy        │  HTTPS, CSP, reverse-proxy
                     │  (forecasteconomy│
                     │      .com)       │
                     └─────┬────────┬───┘
                           │        │
              ┌────────────▼─┐    ┌─▼─────────────────────┐
              │   Frontend   │    │      Backend          │
              │  Nginx + SPA │    │  FastAPI + Uvicorn    │
              │  React 19    │    │  APScheduler          │
              │  Vite 7      │    │  SQLAlchemy 2 (async) │
              └──────────────┘    └──┬──────────┬─────────┘
                                     │          │
                       ┌─────────────▼──┐    ┌──▼────────┐
                       │  PostgreSQL 16 │    │  Redis 7  │
                       └────────────────┘    └───────────┘
                                     │
                ┌────────────────────┼────────────────────┐
                │                    │                    │
        ┌───────▼─────┐      ┌───────▼─────┐      ┌───────▼─────┐
        │   Росстат   │      │    ЦБ РФ    │      │   Минфин    │
        │  (CPI, GDP, │      │  (key-rate, │      │  (бюджет:   │
        │   labor,    │      │   FX, M0/   │      │   доходы,   │
        │   industry, │      │   M1/M2,    │      │   расходы,  │
        │   demo, …)  │      │   BoP, …)   │      │   баланс)   │
        └─────────────┘      └─────────────┘      └─────────────┘

                       ┌─────────────────────────┐
                       │  Forecast Analytics MCP │  Yandex.Metrika /
                       │  (Yandex.* + warehouse) │  Webmaster → DB
                       └─────────────────────────┘
```

## Стек

### Backend

- **FastAPI** + **Uvicorn** — async REST API.
- **PostgreSQL 16** + **SQLAlchemy 2** (asyncpg) + **Alembic**.
- **Redis 7** — кэш форкаст-результатов и rate limit.
- **APScheduler** — ежедневный ETL (06:00 MSK), монтонный refresh календаря (1-е число 03:00 MSK), опциональный analytics scheduler (hourly :15 + daily).
- **statsmodels** — 8 forecast strategies (`forecast_v2`, `arima`, `sarima`, `derived_forecast`, `derived_transform`, `weekly_yoy`, `approved`, `none`).
- **pandas / openpyxl / xlrd / beautifulsoup4 / requests / httpx** — парсинг XLSX, HTML и API.
- **Alerting** — JSON-логи в stdout + Telegram-канал для критических сбоев.

### Frontend

- **React 19** + **Vite 7** + **Tailwind 4** (dark editorial design).
- **TanStack React Query 5** — data fetching и кэш.
- **Recharts** — графики; **GSAP 3** — анимации.
- **React Router 7** + **Axios** + **Lucide** + **xlsx** + **@sentry/react**.
- **Nginx** внутри `frontend` контейнера — раздаёт статику Vite-сборки и проксирует SSR-запросы (Yandex/Google bot UA → backend `/seo/*`).

### Инфраструктура

- **Docker Compose** — 4 сервиса: `db` (Postgres), `redis`, `backend`, `frontend`.
- **Caddy** — внешний reverse-proxy, HTTPS-сертификат, CSP-политики (Yandex.Metrika, Sentry, Webmaster, шрифты).
- **Yandex.Metrika** + **Yandex.Webmaster** — публичная аналитика и контроль индексирования.
- **Forecast Analytics OS / MCP** — отдельный модуль для агрегации Yandex.* данных и сценариев в backend (см. `docs/analytics_api_inventory/`).

## Быстрый старт

### Локально через Docker Compose

```bash
cp .env.example .env
docker compose up -d --build
```

Backend `entrypoint.sh` сам:

1. Применяет Alembic-миграции (`alembic upgrade head`).
2. Идемпотентно заливает `seed_data.py` (104 индикатора, источники, категории).
3. Сидит календарь публикаций на 12 месяцев вперёд.
4. Поднимает Uvicorn.

После этого:

- API: `http://localhost:8000/api/v1/...`
- Swagger: `http://localhost:8000/api/docs` (только при `DEBUG=true`).
- Frontend: `http://localhost:3000` (через nginx из контейнера `frontend`).

### Только фронтенд против прода (без локального backend)

```bash
cd frontend && npm install && npm run dev
```

Vite-прокси по умолчанию направляет `/api` на `https://forecasteconomy.com` — графики и форкасты работают на реальных данных, без поднятия Postgres/Redis локально.

Чтобы переключиться на локальный backend, добавьте в `frontend/.env.local`:

```
VITE_DEV_API_PROXY=http://127.0.0.1:8000
```

## Проверки и регламент

- **CI-эквивалент локально:** `./scripts/check-all.sh` — pytest + frontend lint/test/build.
- **Полный регламент:** см. [`docs/workflow.md`](docs/workflow.md).
- **Чеклист устойчивости (rate limit, CORS, asset-hash, бэкап):** [`docs/enterprise_resilience.md`](docs/enterprise_resilience.md).

## API

Base URL: `/api/v1` (за исключением SSR-эндпоинтов `/seo/*` и `/sitemap.xml`).

| Группа | Endpoint | Описание |
|--------|----------|----------|
| **Indicators** | `GET /indicators` | Список всех индикаторов (с фильтрами, сортировкой). |
| | `GET /indicators/{code}` | Детали (метаданные, единицы, источник, SEO-блоки). |
| | `GET /indicators/{code}/data` | Исторические точки (с пагинацией по диапазону). |
| | `GET /indicators/{code}/stats` | min/max/avg/yoy за период. |
| **Forecasts** | `GET /indicators/{code}/forecast` | Прогноз (по `forecast_strategy` индикатора). |
| | `GET /indicators/{code}/inflation` | Накопленная 12-мес. инфляция + прогноз (только для CPI). |
| **Calendar** | `GET /calendar` | Список календарных публикаций в диапазоне. |
| | `GET /calendar/upcoming` | Ближайшие публикации. |
| | `GET /calendar/{event_id}` | Детали события. |
| | `GET /calendar/export/ical` | iCal-фид для подписки. |
| **Embed** | `GET /embed/spark/{code}.svg` | Sparkline-виджет. |
| | `GET /embed/card/{code}.svg` | Карточка с метрикой. |
| | `GET /embed/badge/{code}.svg` | Inline-бейдж. |
| | `POST /embed/impression`, `GET /embed/pixel.gif` | Учёт показов. |
| **Dashboard** | `GET /dashboard/sparklines` | Бандл sparkline'ов главной. |
| **Demographics** | `GET /demographics/structure` | Половозрастная структура. |
| **Analytics (MCP)** | `GET /analytics/health` | Состояние Forecast Analytics OS (требует токен). |
| | `POST /analytics/query/metrika`, `GET /pages`, `GET /search-phrases`, `GET /anomalies`, `GET /deploy-impact`, `POST /actions/propose`, `POST /actions/{id}/apply`, `POST /events` | Сценарии аналитики. |
| **System** | `GET /health` | Liveness probe (DB ping). |
| | `GET /system/status` | Сводка по индикаторам, последним ETL-запускам, расписанию. |
| | `GET /metrics` (hidden) | Прометей-совместимые метрики. |
| **SEO / SSR** | `GET /seo/page/{page}`, `/seo/category/{slug}`, `/seo/indicator/{code}` | SSR-meta-bundle для ботов. |
| | `GET /sitemap.xml` | Полная карта сайта. |
| | `GET /api/v1/og/{indicator,category,page}/{key}` | OpenGraph-картинки. |

Полную, всегда актуальную документацию смотрите в Swagger (`/api/docs`) при запущенном backend в `DEBUG=true`. На проде Swagger физически отключён.

## Индикаторы

104 активных индикатора в 9 категориях:

| Категория (slug) | DB category | Покрытие |
|------------------|-------------|----------|
| `prices` | Цены | ИПЦ (общий, food/non-food/services), ИЦП, недельная инфляция |
| `rates` | Ставки | Ключевая ставка ЦБ, RUONIA, ставки по кредитам и депозитам |
| `finance` | Финансы | USD/EUR/CNY, M0/M1/M2, золото, резервы, внешний долг, бюджет |
| `labor` | Рынок труда | Безработица, реальные/номинальные зарплаты, рабочая сила |
| `gdp` | ВВП | ВВП номинальный/реальный, госрасходы, потребление, инвестиции |
| `population` | Население | Численность, рождаемость, смертность, пенсионеры, трудоспособное |
| `trade` | Торговля | Экспорт/импорт товаров и услуг, торговый баланс, current account, FDI |
| `business` | Бизнес | ИПП, розничная торговля, ввод жилья, основные фонды |
| `science` | Наука | Аспиранты, докторанты, организации НИР, инновационная активность |

Из 104 индикаторов: **76 source-индикаторов** (через 23 типа парсеров) и **28 derived-индикаторов** (рассчитываются через `DERIVED_SPECS` + `derived_ops`, см. ADR-0001 и ADR-0002).

## Прогнозы

8 forecast strategies в реестре `backend/app/services/forecast_strategies/registry.py`:

- `cpi_combined` — CPI семья: `train_monthly_cpi` + `train_inflation_12m` + cascade на `*-quarterly` derived.
- `gdp_nominal_quarterly` — multi-window OLS на log-diff номинального ВВП.
- `gdp_real_quarterly` — то же ядро на real-уровнях (bit-exact с эталонным notebook'ом ±0.15%).
- `housing_quarterly` — multi-window OLS на квартальных уровнях для `housing-price-secondary`.
- `ppi_monthly` — `train_ppi_monthly` (k=1..4, monthly lags log-diff).
- `approved` — захардкоженные значения из `model_config_json.approved_forecast_values` (например, `housing-price-primary`).
- `derived_from_source` — все `*-yoy` / `*-qoq` / `*-annual` derived: применяет чистую op (yoy/qoq/december_to_december/annual_sum/real_from_yoy) к прогнозу source-индикатора. Каскадный retrain после источника.
- `generic_ols` — fallback и `inflation-weekly`: multi-window OLS с inverse-variance weighting.

Стратегия выбирается через `model_config_json.forecast_strategy` индикатора и применяется при каждом ETL, если источник принёс новые точки. См. CONTEXT.md для полной таблицы и `model_config_json` полей.

## Структура проекта

```
rosstat/
├── backend/
│   ├── app/
│   │   ├── api/            # FastAPI routes (indicators, forecasts, calendar, embed,
│   │   │                   #   dashboard, demographics, analytics, system, seo, sitemap)
│   │   ├── core/           # cache (Redis), deps, helpers
│   │   ├── services/       # parsers (24 файла), forecaster, calculation_engine,
│   │   │                   #   derived_ops, calendar_seed, alerting, seo_renderer
│   │   ├── tasks/          # scheduler, analytics_scheduler
│   │   ├── analytics/      # Forecast Analytics OS — Yandex clients, warehouse, MCP
│   │   ├── config.py       # pydantic-settings
│   │   ├── database.py     # async engine, sessionmaker
│   │   ├── models.py       # ORM (Indicator, IndicatorData, Forecast, FetchLog, …)
│   │   └── main.py         # FastAPI app + lifespan + middleware
│   ├── alembic/            # миграции
│   ├── certs/              # Russian Trusted CA (нужен для https-походов на Росстат)
│   ├── seed_data.py        # идемпотентный seeder (104 индикатора)
│   └── entrypoint.sh
├── frontend/
│   ├── src/
│   │   ├── components/     # Navbar, Footer, Chart, MetricCard, EmbedHelpers, …
│   │   ├── pages/          # Home, Category, IndicatorDetail, Calendar, Embed, …
│   │   └── lib/            # api client, categories.js, formatters, hooks
│   ├── nginx.conf          # SPA + SSR-bot-proxy + asset hashing
│   └── Dockerfile
├── scripts/
│   ├── check-all.sh        # CI-эквивалент локально
│   ├── pg-backup.sh        # pg_dump перед прод-деплоем
│   ├── deploy.sh           # обвязка sshscript для прод-деплоя
│   ├── sync-local-from-prod.py
│   ├── rebuild-all-derived.py
│   ├── seo-audit.py
│   └── analytics-smoke.py
├── docs/
│   ├── adr/                # архитектурные решения (нумерованные)
│   ├── analytics_api_inventory/  # инвентарь Yandex API (Metrika, Webmaster, …)
│   ├── workflow.md
│   ├── cbr_sources.md
│   ├── enterprise_resilience.md
│   └── embed_widgets_research.md
├── mcp/                    # Forecast Analytics MCP server (отдельный контейнер)
├── Caddyfile
├── docker-compose.yml
├── CONTEXT.md              # глоссарий и архитектурный язык — главная точка входа
└── README.md
```

## Деплой

См. полную процедуру в [`docs/workflow.md`](docs/workflow.md). Ключевые моменты:

1. `pg_dump | gzip > /opt/rosstat/backups/pre-deploy-<timestamp>.sql.gz` — обязательно перед каждым релизом.
2. `git pull && docker compose build backend frontend && docker compose up -d backend frontend` — backend и frontend пересобирать и поднимать **вместе** (asset-hash mismatch trap, см. `enterprise_resilience.md`).
3. Alembic-миграции применяются автоматически из `entrypoint.sh`.
4. Smoke C — health-чеки + headless E2E (см. `scripts/e2e/smoke.mjs`).

## Что автоматизировано

| Процесс | Как |
|---------|-----|
| Миграции БД | `entrypoint.sh` → `alembic upgrade head` при каждом старте |
| Первичный seed | `entrypoint.sh` → идемпотентный `seed_data.py` |
| Ежедневный ETL | APScheduler cron 06:00 MSK (все `is_active=true`, 76 source-парсеров) |
| Calendar refresh | APScheduler daily 03:00 MSK: official-source ingest, rolling 12 мес, public official-only |
| Forecast retrain | После каждого изменения данных (если `records_added>0`) |
| Derived recompute | Каскадно после ETL (если хотя бы один source-индикатор обновился) |
| Cache invalidation | После forecast retrain — Redis-ключи протухают |
| Auto-restart | `restart: unless-stopped` для всех сервисов |
| Russian Trusted CA | Сертификат в `backend/certs/` для походов на Росстат |
