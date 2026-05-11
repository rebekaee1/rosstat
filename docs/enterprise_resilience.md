# Enterprise resilience — практики и инварианты

**Last updated:** 2026-05-11.
**Part of:** [`../AGENTS.md`](../AGENTS.md), [`../CONTEXT.md`](../CONTEXT.md) (раздел «Operational invariants and traps»).
**See also:** [`workflow.md`](workflow.md) (smoke C, прод-деплой), [`adr/0003-seo-single-source-server-rendered.md`](adr/0003-seo-single-source-server-rendered.md) (asset-hash trap).

Чеклист для каждой доработки API/парсера/UI/деплоя — по уровням системы.

## API и backend

- **Rate limit (Redis-based)** — все `/api/*` ограничены: 120/мин на IP для основного API, 600/мин для `/api/v1/embed/*`. Окно 60 сек, ключ `rl:<ip>` / `rle:<ip>`. При превышении — `429 {detail: "Rate limit exceeded"}` с `Retry-After: 60`. При недоступном Redis — middleware пропускает запрос (`logger.warning` + allow). `RateLimitMiddleware` в `backend/app/main.py`.
- **CORS** — белый список фиксирован: `forecasteconomy.com`, `www.forecasteconomy.com`, `localhost:{5173,5174,3000}`. Только `GET, OPTIONS`. Любой новый внешний потребитель — добавить явно в `app/main.py`.
- **GZip middleware** — включён для ответов > 1000 байт.
- **Ошибки имеют стабильную форму** — FastAPI default `{"detail": "..."}`. Поля `code` сейчас **нет** (aspirational — добавить при появлении первого внешнего интегратора, который попросит).
- **Пустой ряд / no data** — endpoint возвращает `200` со схемой `{indicator_id, frequency, points: []}`. Поля `empty_reason` сейчас **нет** (aspirational); фронт сам показывает empty-state, опираясь на `points.length === 0`.
- **`/api/docs`, `/api/redoc`, `/api/openapi.json`** — гейтированы через `settings.debug`. На проде (`DEBUG=false`) Swagger физически отключён в FastAPI-конструкторе (`docs_url=None`). Не оставлять `DEBUG=true` на проде.
- **Backend Sentry** — **не подключён** (нет ни SDK в `requirements.txt`, ни init в `main.py`). Aspirational — добавить при первом инциденте, требующем трейсинга. Сейчас единственный backend-канал — JSON-логи в `stdout` (формат через `JsonFormatter`, видны через `docker compose logs backend`).
- **Telegram-алерты (`alerting.py`)** — кастомный канал для критических событий ETL и форкастов: уведомление о провале daily-job или конкретного парсера. Включается через `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` в `.env`. См. `backend/app/services/alerting.py`.

## База данных и ETL

- **Идемпотентность парсеров** — все `BaseParser`-наследники используют `bulk_upsert` с `ON CONFLICT (indicator_id, period_start, frequency) DO UPDATE`. Повторный прогон того же дня = 0 изменений. См. ADR-0002.
- **Пакетный seed** — `seed_data.py` идемпотентный: повторный запуск не создаёт дублей. `entrypoint.sh` гонит его при каждом старте.
- **Бэкап перед деплоем** — `pg_dump | gzip > /opt/rosstat/backups/pre-deploy-<timestamp>.sql.gz` обязательно. См. `scripts/pg-backup.sh`. Хранение — последние 7 копий (TODO: автоматический ротатор).
- **Rolling-window очистка** — старые `fetch_logs` (>90 дней) и старые `forecast_runs` без активных привязок чистит `scripts/cleanup-old-runs.py` (запуск ручной, периодичность — раз в квартал).
- **Календарь** — APScheduler-job `calendar_refresh` ежедневно в 03:00 MSK обновляет rolling 12 мес. через official-source ingest. Public API отдаёт только source-bound rows: `official_explicit` / `official_rule` плюс `event_key`, `source_url`, `source_hash`, `last_seen_at`; `estimated` и legacy backfill без provenance скрыты. Local verification 2026-05-10 после CBR/Minfin/Rosstat safe expansion: 1208 public events, 46/76 source codes, `bad_public_rows=0`. См. ADR-0005 и `seed_calendar(months_ahead=12)`.

## Парсеры и источники

- **Защита от частичной загрузки** — при ошибке парсинга `BaseParser.run` пишет `fetch_logs(status="error", error_message=...)` и **не** трогает `data_points`. Получившая частичную пачку точек серия не остаётся в неконсистентном состоянии.
- **Ретраи** — Rosstat-парсеры используют `requests` + явный `try/except`; CBR-парсеры — то же. Backoff не реализован централизованно, ретраи делаются повторным прогоном daily-job на следующий день.
- **`is_active=false`** — выключение парсера для индикатора без удаления данных. ETL job их пропускает.
- **`is_listed=false`** — индикатор скрыт со списочных страниц (категории, поиск), но детальная страница `/indicator/<slug>` доступна. Используется для архивных серий или предрелизных черновиков.
- **Minfin in-place CSV content update (trap)** — `minfin.gov.ru/opendata/7710168360-fedbud_month/` публикует CSV под стабильным URL `data-YYYYMMDDTHHMM-structure-...csv`. Timestamp в имени = **дата создания паспорта набора**, не snapshot content. Минфин **дополняет content того же URL** новыми месяцами в течение дня без смены URL. Симптом, который мы наблюдали 5-11 мая 2026: `daily_update_job` в 03:00 MSK скачивал CSV → `bulk_upsert` возвращал `(0, 0)` → status `no_new_data`; через 12-14 часов тот же CSV отдавал уже свежий контент с новым месяцем. **Контрмеры**: 1) `late_minfin_etl_job` (APScheduler, 15:00 MSK ежедневно) — second pass через `run_etl_for_parser_type("minfin_budget_csv")`; 2) `minfin_budget_parser` логирует `last_parsed_date` + `last_db_date` + `len(points)` (см. `MinfinBudgetParser._fetch_and_parse`) — для последующих аномалий легче ловить разрыв через `docker compose logs backend | grep "Minfin budget"`. См. `docs/data_sources.md::budget-*`.

## Frontend и кэш

- **Asset-hash mismatch trap** — Vite строит файлы вида `index-<hash>.js`. Если backend и frontend пересобраны не вместе, новый `__spa-index.html` будет ссылаться на ассеты, которых уже нет на nginx-сервинге (или наоборот). **Правило:** `docker compose build backend frontend` всегда вместе перед `up -d`. См. `Caddyfile` для текущего fallback на `/__spa-index.html`.
- **CSP в Caddyfile** — белые списки прописаны для Yandex.Metrika (`mc.yandex.ru`, `mc.yandex.com`), Sentry frontend (`sentry.io`, `*.ingest.sentry.io`), Yandex.Webmaster, шрифтов Google. Любой новый внешний скрипт — добавить в CSP, иначе он будет заблокирован.
- **Frontend Sentry** — `@sentry/react` подключён в `frontend/src/main.jsx`. DSN — env-переменная `VITE_SENTRY_DSN`. Backend Sentry — отдельная задача (см. выше).
- **SEO single-source** — `__spa-index.html` собирается на каждый запрос: SSR-meta в `<head>` для ботов и людей; legacy локальные `seo.js` константы удалены. См. ADR-0003.

## Производительность

- **Cache (Redis)** — `app/core/cache.py` — ключи forecast-результатов и иногда indicator-метаданных. TTL 1ч / 1 день в зависимости от типа. Инвалидация при ручной правке через `redis-cli FLUSHDB`.
- **GZip** — для всех ответов > 1000 байт.
- **DB indexes** — `data_points (indicator_id, period_start, frequency)` уникальный, `forecast_runs (indicator_id, created_at desc)`. См. `migrations/`.

## Мониторинг

- **Health endpoints** — `/api/v1/health` (DB ping) и `/api/v1/analytics/health` (с проверкой failed analytics syncs за последние 24ч). Использовать в external uptime monitor.
- **JSON-логи** — все backend-логи в stdout как JSON (`{ts, level, logger, msg, exc?}`). Удобно вбирать в любой коллектор.
- **SEO audit** — `scripts/seo-audit.py` периодически проходит по списку indicator-страниц и проверяет, что SSR возвращает осмысленные `<title>`, `<meta description>`, `og:*`, JSON-LD. Запускается вручную, расписание — после крупных правок.

## Деплой-инцидент trap: forecast retrain не пробрасывается

Когда деплой добавляет **новые derived-индикаторы** (через правки `seed_data.py` + `DERIVED_SPECS`), `entrypoint.sh` идемпотентно отрабатывает seed, но forecast retrain не запускается автоматически. Daily ETL переобучает прогнозы только тех индикаторов, у которых на этом тике добавились новые точки. Симптом — `/forecast` отдаёт `null` для свежесозданного derived несколько часов/дней. Mitigation описана в CONTEXT.md (раздел «Forecast retrain после деплоя»). После любого деплоя, добавляющего derived, делать ручной `retrain_indicator_forecast(<source_code>)` для каждого источника + `redis-cli FLUSHDB`.

## Канарейка изменений

Перед мерджем feature-ветки в `main` — провести по чеклисту:

1. Pytest и vitest зелёные локально.
2. Vite build без ошибок.
3. Браузер-snapshot ключевых страниц (см. `workflow.md`).
4. Если правка касается парсеров — идемпотентность проверена двойным прогоном `daily_update_job` на dev-БД.
5. Если правка касается forecast-стратегии — `rebuild-all-derived.py` гонит первым прогоном изменения, вторым — все нули.
6. Если правка касается SEO/SSR — `User-Agent: YandexBot/3.0` запрос к 3+ страницам, проверить `<title>` и `<meta>`.

Без зелёных «6 из 6» в `main` не идём.
