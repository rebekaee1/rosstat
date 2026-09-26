# Forecast Economy — аналитическая платформа официальной макроэкономической статистики по странам

Сбор, анализ и публикация официальных экономических данных: национальные
статведомства, центральные банки, Евростат, BEA/FRED; по России — особенно глубоко
(Росстат, Банк России, Минфин, 85 субъектов). Прогнозы, ежедневный ETL, SSR + SEO
(~5 млн URL на хост), embed-виджеты, календарь публикаций, live ticker.
EN: [forecasteconomy.com](https://forecasteconomy.com); RU: [ru.forecasteconomy.com](https://ru.forecasteconomy.com).

**AI-агентам:** начать с [`AGENTS.md`](AGENTS.md) и [`docs/STATE.md`](docs/STATE.md) (где остановились).
Глоссарий и ловушки — [`CONTEXT.md`](CONTEXT.md); процесс и деплой — [`docs/workflow.md`](docs/workflow.md);
источники — [`docs/data_sources.md`](docs/data_sources.md); решения — [`docs/adr/`](docs/adr/) (ADR-0001..0015);
открытые задачи — [`docs/backlog.md`](docs/backlog.md).

## Коротко для владельца

- **Что это.** Сайт с официальной статистикой по странам: графики, таблицы,
  прогнозы, быстрые страницы для поисковиков и ИИ-ассистентов.
- **Как текут данные.**

  ```
  Росстат / ЦБ / Минфин / Евростат / ФРС …  →  сервер (ежедневная загрузка)
    →  база данных  →  сайт и быстрые страницы  →  посетители и поисковики
  ```

- **Где что лежит.** Код — на Mac (`/Users/iprofi/tradingeconomics/rosstat`) и на
  GitHub (`rebekaee1/rosstat`). Сайт работает на сервере (`ssh fe-prod`, папка
  `/opt/rosstat`).
- **Выкладка.** Только по вашей команде «деплой до …»: сервер сам делает бэкап,
  собирает, проверяет 34 страницы и 15 минут следит; при сбое сам откатывается.
- **Бэкапы.** Каждый день в 07:00 МСК на сервере (хранятся 14 дней), в 08:15
  копия проверяется и скачивается на Mac в `~/Backups/forecasteconomy/`.

## Архитектура

```
 Интернет ─► Caddy на хосте (HTTPS, CSP; forecasteconomy.com + ru.)
               │
               ▼
     frontend: nginx :3000→80 (SPA-статика, rate-limit, SSR-прокси, OG-rewrite)
               │
               ▼
     backend: FastAPI + Uvicorn + APScheduler (~40 job'ов; 1 воркер до perf batch 2)
        │            │               │                 │
        ▼            ▼               ▼                 ▼
  PostgreSQL 16   Redis 7 кэш    redis-state         ClickHouse
  (лимит 2,5 ГБ)  (256 МБ)       (сессии, квоты,     (OLAP-копия
                                 локи; AOF)           аналитики)
        ▲
        └── ETL: Росстат, ЦБ РФ, Минфин, ЕМИСС, Eurostat, FRED/BEA/BLS, нац. ведомства
```

Live ticker: MOEX ISS + Binance + CBR fallback → Redis → `/api/v1/ticker/live`.
Forecast Analytics: Метрика / Вебмастер / GSC → warehouse → BI и MCP
(`mcp/forecast-analytics-mcp/`, [`docs/analytics.md`](docs/analytics.md)).

## Стек

- **Backend:** Python 3.12, FastAPI, SQLAlchemy 2 (asyncpg), Alembic, APScheduler,
  statsmodels, pandas/openpyxl/httpx; Pillow для OG-картинок.
- **Frontend:** React 19, Vite 7, Tailwind 4, TanStack Query 5, Recharts, React Router 7,
  `@sentry/react`; nginx в контейнере `frontend`.
- **Инфраструктура:** Docker Compose — 6 сервисов: `postgres`, `redis`,
  `redis-state`, `backend`, `frontend`, `clickhouse`; Caddy на хосте; бэкапы
  `scripts/pg-backup.sh`.

## Быстрый старт

```bash
cp .env.example .env
docker compose up -d --build        # сайт: http://localhost:3000
cd frontend && npm ci && npm run dev  # Vite: http://localhost:5173
```

`backend/entrypoint.sh`: `alembic upgrade head` → идемпотентный `seed_data.py` →
календарь → Uvicorn. Swagger — `http://localhost:8000/api/docs` только при
`RUSTATS_DEBUG=true`. Vite по умолчанию проксирует `/api` на прод; локальный
backend — `VITE_DEV_API_PROXY=http://127.0.0.1:8000` в `frontend/.env.local`.

Проверки: `./scripts/check-all.sh` (эквивалент CI). Регламент — [`docs/workflow.md`](docs/workflow.md).

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

Счётчики не фиксируем вручную — актуальное число в `seed_data.py`,
`docs/indicator-index.md` и `/api/v1/system/status`.

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

Source-индикаторы (118) извлекаются через 34 парсер-типа в `PARSER_REGISTRY` (`backend/app/services/*_parser.py`; 32 используются в seed, `cbr_dataservice_sum`/`cbr_monetary_html` зарегистрированы про запас); derived рассчитываются движком `calculation_engine` через `DERIVED_SPECS` (829 спеков: 44 ручных + 785 сгенерированных view-mode-семьями) + 28 чистых ops из `derived_ops.py` (см. ADR-0001 и ADR-0002). Дублирующие карточки в каталоге объединены через 109 generic view-mode family (ADR-0006); всего в seed 947 рядов.

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
├── backend/app/{api,core,services,tasks,data}  # роуты, кэш, парсеры/сервисы, планировщик, реестры
├── backend/alembic/versions/                   # миграции
├── backend/seed_data.py, entrypoint.sh          # идемпотентный seed, старт
├── frontend/src/{components,pages,lib}, nginx.conf
├── scripts/  check-all.sh · deploy.sh (прод-деплой с автооткатом) · pg-backup.sh (ежедневный дамп)
├── deploy/   approved-shas.txt (одобренные SHA) · fail2ban/ · optional/ · mac/ (копия бэкапа на Mac)
├── docs/     STATE.md · workflow.md · data_sources.md · indicators.md · analytics.md · backlog.md · adr/ (ADR-0001..0015)
├── mcp/forecast-analytics-mcp/
├── Caddyfile, docker-compose.yml
└── AGENTS.md, CONTEXT.md, README.md
```

## Деплой

Только по явной команде владельца и SHA из `deploy/approved-shas.txt`;
запуск `scripts/deploy.sh` на сервере через `nohup` (~25 мин): бэкап → сборка →
очистка SSR-кэша → smoke + 34 страницы RU/EN → 15-минутный watch с автооткатом.
Пошагово — [`docs/workflow.md`](docs/workflow.md#прод-деплой).

## Что автоматизировано

| Процесс | Как |
|---------|-----|
| Миграции и seed | `entrypoint.sh` при каждом старте |
| Startup catch-up | `_catch_up_empty_indicators()` догоняет ETL для индикаторов без точек |
| ETL | 06:00 и 20:00 МСК + late-Minfin 15:00, late-FRED, мировые job'ы |
| Календарь | ежедневно 03:00 МСК, только official-source даты |
| Sitemap | ночная сборка 03:40 МСК, шарды по 10 000 URL |
| Прогнозы и derived | после ETL, если источник принёс новые точки |
| Бэкапы | 07:00 МСК на сервере (14 дней) + 08:15 копия на Mac |
| Auto-restart | `restart: unless-stopped` |
