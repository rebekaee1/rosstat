# Forecast Economy — аналитическая платформа экономики России, регионов и стран

Платформа для сбора, анализа и публикации официальных экономических данных России, 85 регионов и доступных стран. Российский контур использует Росстат, Банк России и Минфин; мировой контур — Eurostat и подключаемые официальные национальные первоисточники. Прогнозы, ежедневный ETL, SSR + SEO, embed-виджеты, календарь публикаций, live ticker (USD/EUR/CNY/BTC/Brent), аналитический MCP. Доступна публично на [forecasteconomy.com](https://forecasteconomy.com).

**Точка входа в документацию (для AI-агентов и людей):** [`AGENTS.md`](AGENTS.md) — карта документации, режим работы, протокол актуализации.
**Domain glossary и инварианты:** [`CONTEXT.md`](CONTEXT.md).
**Рабочий процесс, локальный dev, прод-деплой:** [`docs/workflow.md`](docs/workflow.md).
**Источники данных:** [`docs/data_sources.md`](docs/data_sources.md) (per-indicator карта `URL/endpoint/sheet/row`); parser internals — в docstrings `backend/app/services/*_parser.py`.
**Архитектурные решения:** [`docs/adr/`](docs/adr/) (ADR-0001..0012).
**Backlog работ:** [`docs/backlog.md`](docs/backlog.md).

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

                       ┌─────────────────────────┐
                       │     Live Ticker         │  USD/EUR/CNY/BTC/Brent
                       │  MOEX ISS + Binance +   │  → Redis (TTL 30s)
                       │  CBR XML fallback       │  → /api/v1/ticker/live
                       └─────────────────────────┘
```

## Стек

### Backend

- **FastAPI** + **Uvicorn** — async REST API.
- **PostgreSQL 16** + **SQLAlchemy 2** (asyncpg) + **Alembic**.
- **Redis 7** — кэш форкаст-результатов и rate limit.
- **APScheduler** — ежедневный ETL (06:00 MSK), daily refresh official-source календаря (03:00 MSK), опциональный analytics scheduler (hourly :15 + daily).
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

**Полная и всегда актуальная документация** — Swagger при `DEBUG=true`: `http://localhost:8000/api/docs`. На проде Swagger физически отключён.

Ключевые группы endpoint'ов:

| Группа | Что отдаёт |
|--------|------------|
| `/indicators/*` | список / детали / точки / статистика / прогноз / накопленная инфляция (CPI) |
| `/calendar/*` | публикации в диапазоне, ближайшие, iCal-фид (источник: ADR-0005) |
| `/ticker/live` | live снимок USD/EUR/CNY/BTC/Brent из Redis (TTL 30с, MOEX + Binance + CBR fallback) |
| `/embed/*` | spark/card/badge SVG-виджеты + impression-pixel |
| `/dashboard/sparklines` | bundle sparkline'ов главной |
| `/analytics/*` | Forecast Analytics OS (Yandex.* через MCP, требует токен) |
| `/seo/*`, `/sitemap.xml`, `/og/*` | SSR-meta-bundle, sitemap, OpenGraph-картинки (источник: ADR-0003) |
| `/health`, `/system/status` | liveness + сводка по ETL и расписанию |

## Индикаторы

100+ активных индикаторов, разнесённые по 10 категориям (счётчики не фиксируем — растут постоянно; актуальное число в `seed_data.py` и в `/api/v1/system/status`).

| Категория (slug) | DB category | Покрытие |
|------------------|-------------|----------|
| `prices` | Цены | ИПЦ (общий, food/non-food/services), ИЦП, недельная инфляция |
| `rates` | Ставки | Ключевая ставка ЦБ (с 1992), RUONIA, ставки по кредитам и депозитам (с term split) |
| `currencies` | Валюты | USD/RUB, EUR/RUB, CNY/RUB, BTC/USD, Brent |
| `finance` | Деньги и бюджет | M0/M1/M2, золото, резервы, внешний долг, бюджет (доходы/расходы/дефицит) |
| `labor` | Рынок труда | Безработица, номинальная (с 1991) / реальная / индекс / YoY зарплата |
| `gdp` | ВВП | ВВП номинальный/реальный/потребление/госрасходы (+ annual/QoQ/YoY) |
| `population` | Население | Численность, рождаемость, смертность, миграция, пенсионеры, трудоспособное |
| `trade` | Торговля | Экспорт/импорт товаров и услуг (quarterly + monthly), trade-balance, current account, FDI |
| `business` | Бизнес | ИПП (default YoY), розница, ввод жилья, индекс доступности жилья, основные фонды |
| `science` | Наука | Аспиранты, докторанты, организации НИР, инновационная активность, R&D |

Source-индикаторы (111) извлекаются через 32 парсер-типа в `PARSER_REGISTRY` (`backend/app/services/*_parser.py`; 28 используются в seed, `cbr_dataservice_sum`/`cbr_monetary_html` зарегистрированы про запас); derived рассчитываются движком `calculation_engine` через `DERIVED_SPECS` (781 спек: 41 ручной + 740 сгенерированных view-mode-семьями) + 27 чистых ops из `derived_ops.py` (см. ADR-0001 и ADR-0002). Дублирующие карточки в каталоге объединены через 102 generic view-mode family (ADR-0006); всего в seed 892 ряда.

## Прогнозы

13 forecast strategies в реестре `backend/app/services/forecast_strategies/registry.py`: `cpi_combined`, `gdp_{nominal,real,consumption,government}_quarterly`, `housing_quarterly`, `ppi_monthly`, `monthly_auto`, `generic_quarterly` (положительные квартальные: exports/imports/external-debt), `signed_quarterly` (знаковые квартальные сальдо: current-account), `approved`, `derived_from_source` (включая op=`subtract` — тождество trade-balance = exports − imports), `generic_ols`. Стратегия выбирается через `model_config_json.forecast_strategy` индикатора и применяется при каждом ETL, если источник принёс новые точки. Прогнозы НЕ строятся для крипты/биржевых котировок/частоты < месяца (профанация).

Полная таблица «стратегия → индикаторы → notebook» и поля `model_config_json` — в [`CONTEXT.md::Forecast`](CONTEXT.md). Pure formulas стратегий — `backend/app/services/forecast_strategies/*.py`; derived chain — в `derived_ops.py` (ADR-0001).

Мировые прогнозы изолированы в `world_forecasts`: свежий регулярный месячный
или квартальный primary-series публикует прогноз только после rolling-origin
проверки `MASE < 1` и выигрыша у seasonal-naive. Новый provider получает такой
допуск только явно, после проверки официального adapter и provenance
(ADR-0012).

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
│   ├── adr/                # архитектурные решения (нумерованные ADR-0001..0006)
│   ├── analytics_api_inventory/  # инвентарь Yandex API (Metrika, Webmaster, …)
│   ├── data_sources.md     # карта «индикатор → файл/endpoint» (111 source)
│   ├── missed_data_audit.md  # reference: ещё не извлечённые поля в source-файлах
│   ├── workflow.md         # dev процесс, smoke C, прод-деплой
│   ├── enterprise_resilience.md  # rate limit / CSP / asset-hash trap / канарейка
│   └── backlog.md          # живой бэклог (приоритеты + история)
├── mcp/                    # Forecast Analytics MCP server (отдельный контейнер)
├── Caddyfile
├── docker-compose.yml
├── CONTEXT.md              # глоссарий и архитектурный язык — главная точка входа
└── README.md
```

## Деплой

См. полную процедуру в [`docs/workflow.md::Прод-деплой`](docs/workflow.md). Ключевые моменты:

1. `pg_dump | gzip > /opt/rosstat/backups/pre-deploy-<timestamp>.sql.gz` — обязательно перед каждым релизом.
2. `git pull && docker compose build backend frontend && docker compose up -d backend frontend` — backend и frontend пересобирать и поднимать **вместе** (asset-hash mismatch trap, см. `enterprise_resilience.md`). Backend на старте сам прогонит `_catch_up_empty_indicators` для новых indicators с 0 точек.
3. Alembic-миграции применяются автоматически из `entrypoint.sh`.
4. Smoke C — health-чеки (`/api/v1/health`, `/api/v1/analytics/health`), SSR-сверка через `User-Agent: YandexBot/3.0`, `scripts/seo-audit.py`. Детали — в `docs/workflow.md::Smoke C`.

## Что автоматизировано

| Процесс | Как |
|---------|-----|
| Миграции БД | `entrypoint.sh` → `alembic upgrade head` при каждом старте |
| Первичный seed | `entrypoint.sh` → идемпотентный `seed_data.py` |
| Startup catch-up | `app/main.py::_catch_up_empty_indicators()` — после lifespan startup догоняет ETL для всех `is_active=true` индикаторов с 0 точками (новые индикаторы дотягиваются без ручного `run_etl_for_indicator`) |
| Ежедневный ETL | APScheduler cron 06:00 и 20:00 MSK (все `is_active=true` source-индикаторы; 111 source через `PARSER_REGISTRY`) + late-Minfin 15:00 |
| Calendar refresh | APScheduler daily 03:00 MSK: official-source ingest, rolling 12 мес, public official-only |
| Forecast retrain | После каждого изменения данных (если `records_added>0`) |
| Derived recompute | Каскадно после ETL (если хотя бы один source-индикатор обновился) |
| Cache invalidation | После forecast retrain — Redis-ключи протухают |
| Auto-restart | `restart: unless-stopped` для всех сервисов |
| Russian Trusted CA | Сертификат в `backend/certs/` для походов на Росстат |
