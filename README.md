# Forecast Economy (Rosstat) — Аналитическая платформа экономических индикаторов России

Enterprise-grade платформа для сбора, анализа и прогнозирования экономических индикаторов России на основе данных Росстата.

**Правила работы по фазам, Git и деплой:** см. [docs/workflow.md](docs/workflow.md).

## Архитектура

```
┌──────────────┐     ┌──────────────┐     ┌───────────┐
│   Frontend   │────▶│   Backend    │────▶│ PostgreSQL│
│  React 19    │     │   FastAPI    │     └───────────┘
│  Tailwind    │     │              │     ┌───────────┐
│  GSAP        │     │  APScheduler │────▶│   Redis   │
│  TanStack Q  │     │  OLS Forecast│     └───────────┘
└──────────────┘     └──────┬───────┘
                            │
                     ┌──────▼───────┐
                     │   Росстат    │
                     │  (daily ETL) │
                     └──────────────┘
```

## Стек

### Backend
- **FastAPI** — async REST API
- **PostgreSQL 16** + **SQLAlchemy 2** (asyncpg) — хранение данных
- **Redis 7** — кеширование API-ответов
- **APScheduler** — ежедневная загрузка данных из Росстата (06:00 MSK)
- **OLS Multi-Window** (statsmodels) — прогнозирование временных рядов
- **Alembic** — миграции БД

### Frontend
- **React 19** + **Vite 7** — SPA
- **Tailwind CSS v4** — стилизация (dark editorial design system)
- **GSAP 3** — анимации (fade-up, number counters, stagger)
- **TanStack Query** — data fetching + кеширование
- **Recharts** — интерактивные графики
- **Lucide React** — иконки

### Инфраструктура
- **Docker Compose** — PostgreSQL, Redis, Backend, Frontend
- **Nginx** — SPA + API proxy
- **Russian Trusted CA** — SSL для Росстата

## Проверка кода (как CI)

Из корня репозитория:

```bash
./scripts/check-all.sh
```

Скрипт гоняет `pytest` в `backend/` и `npm run test`, `lint`, `build` во `frontend/`.

## Быстрый старт

### Docker Compose (рекомендуется)

```bash
cp .env.example .env
# Отредактируй POSTGRES_PASSWORD в .env
docker compose up -d --build
```

**Всё остальное автоматически:**
- `entrypoint.sh` применяет миграции (`alembic upgrade head`)
- При пустой БД автоматически запускает seed (6 индикаторов + 419 точек ИПЦ + OLS-прогноз)
- Запускает uvicorn

Платформа будет доступна на `http://localhost`.

### Только фронтенд (`npm run dev`)

Прокси Vite по умолчанию направляет `/api` на **`https://forecasteconomy.com`** — индикаторы и графики в браузере **с реальными данными**, без поднятого локального backend.

Локальный API (полный стек у себя): в `frontend/.env.local` задайте `VITE_DEV_API_PROXY=http://127.0.0.1:8000` и поднимите backend (см. Docker Compose выше).

### Ручной запуск ETL (опционально)

Все активные индикаторы (в т.ч. ключевая ставка ЦБ):

```bash
docker compose exec backend python -c "
import asyncio
from app.tasks.scheduler import daily_update_job
asyncio.run(daily_update_job())
"
```

Только ключевая ставка (локально, если настроен `PYTHONPATH` и `RUSTATS_DATABASE_URL`):

```bash
./scripts/etl-key-rate.sh
```

## API

Base URL: `/api/v1`

| Endpoint | Описание |
|---|---|
| `GET /indicators` | Список всех индикаторов |
| `GET /indicators/{code}` | Детали индикатора |
| `GET /indicators/{code}/data` | Исторические данные |
| `GET /indicators/{code}/stats` | Статистика (min/max/avg) |
| `GET /indicators/{code}/forecast` | Прогноз OLS (помесячный) |
| `GET /indicators/{code}/inflation` | Кумулятивная 12-мес. инфляция + прогноз |
| `GET /system/status` | Статус системы |
| `GET /health` | Health check |

Документация Swagger: `/api/docs`

## Индикаторы

| Код | Название | Статус |
|---|---|---|
| `cpi` | Индекс потребительских цен | Active |
| `cpi-food` | ИПЦ — продовольственные товары | Active |
| `cpi-nonfood` | ИПЦ — непродовольственные товары | Active |
| `cpi-services` | ИПЦ — услуги | Active |
| `unemployment` | Уровень безработицы | Planned |
| `key-rate` | Ключевая ставка ЦБ РФ | Active (ETL с [cbr.ru](https://www.cbr.ru/hd_base/KeyRate/), см. [docs/cbr_sources.md](docs/cbr_sources.md)) |

## Структура проекта

```
rosstat/
├── backend/
│   ├── app/
│   │   ├── api/            # FastAPI routes
│   │   ├── core/           # Cache, deps
│   │   ├── services/       # Fetcher, Parser, Forecaster
│   │   ├── tasks/          # ETL Scheduler
│   │   ├── config.py       # Settings (pydantic-settings)
│   │   ├── database.py     # Async SQLAlchemy engine
│   │   ├── models.py       # ORM models
│   │   ├── schemas.py      # Pydantic schemas
│   │   └── main.py         # FastAPI app
│   ├── alembic/            # DB migrations
│   ├── certs/              # Russian Trusted CA
│   ├── seed_data.py        # Initial data seeder
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── components/     # Navbar, Chart, MetricCard, DataTable...
│   │   ├── pages/          # Dashboard, IndicatorDetail
│   │   └── lib/            # API client, hooks, formatters
│   ├── nginx.conf
│   └── Dockerfile
├── output/                 # Legacy CSV for initial seed
├── docker-compose.yml
└── .env.example
```

## Деплой

```bash
git clone <repo-url> && cd rosstat
cp .env.example .env
# Отредактируй POSTGRES_PASSWORD
docker compose up -d --build
# Готово. Миграции, seed, прогноз — всё автоматически.
```

### Что автоматизировано

| Процесс | Как |
|---|---|
| Миграции БД | `entrypoint.sh` → `alembic upgrade head` при каждом старте |
| Первичный seed | `entrypoint.sh` → проверяет пустую БД → seed + forecast |
| Ежедневная выгрузка Росстата | APScheduler cron 06:00 MSK |
| Парсинг Excel | Автоматический в ETL |
| Перетренировка OLS | Автоматическая при новых данных |
| Инвалидация кэша | Автоматическая после обновления данных |
| Рестарт при падении | `restart: unless-stopped` |
| SSL для Росстата | Сертификат включён в Docker-образ |
