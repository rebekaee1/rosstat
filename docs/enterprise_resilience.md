# Enterprise resilience — практики и инварианты

**Last updated:** 2026-09-30 (ops-механизмы main `05302ff`: owners/ACL restore, bounded HTTP auth/API/nginx и clean startup; source/runtime host config различия датированы). Прежняя сверка27.09 с `b684290` сохраняется в истории; проверки не означают новый production release.

**Previous:** 2026-09-20 (локальный пакет `fix/history-access-reliability`: история, per-IP доступ, архив ассетов и происхождение метрик Пульса; прод не принят). Ранее 2026-07-06 (CTO-аудит, Волны 1/4: наблюдаемость и операционка выросли — реальный readiness `/health/ready` (БД + оба Redis + планировщик + возраст ETL как мягкая деградация), APScheduler-listener EVENT_JOB_ERROR/MISSED → Telegram, staleness-монитор индикаторов (10:00 МСК), алерты derived/retrain/backup-heartbeat/lockout/5xx-spike/rate-limit-fail-open, 5xx-счётчики в `/metrics`; deploy.sh с автооткатом на SHA-теги; Redis: maxmemory + выделенный `redis-state` (noeviction+AOF) для сессий; распределённые локи мутационных джобов (state-Redis SET NX); prod-assertions при `debug=false` (warn-режим); body-limit/таймауты на nginx и Caddy. Ранее 2026-05-22: nginx no-cache always на SSR routes.)
**Part of:** [`../AGENTS.md`](../AGENTS.md), [`../CONTEXT.md`](../CONTEXT.md) (раздел «Operational invariants and traps»).
**See also:** [`workflow.md`](workflow.md) (smoke C, прод-деплой), [`data-contracts.md`](data-contracts.md) (доказанные producer/consumer и семантика полей), [`adr/0003-seo-single-source-server-rendered.md`](adr/0003-seo-single-source-server-rendered.md) (asset-hash trap), [`../AGENTS.md::Шаг 4 — чеклист «новый индикатор»`](../AGENTS.md) (другая ось при добавлении indicator).

Чеклист для каждой доработки API/парсера/UI/деплоя — по уровням системы.

## API и backend

**Доступ, локальная реализация 2026-09-20.** nginx ограничивает SSR по IP (5 r/s), региональные страницы и OG — строгой зоной (2 r/s); заявленный поисковый UA не освобождает от лимита. Общего SSR-бакета больше нет; общий OG-потолок 8 r/s и 4 соединения сохранён отдельно. `$bad_bot` удалён, но отдельная политика training/archive crawlers остаётся. Отсутствующая/чужая `fe_bind`, страна и ASN не блокируют HTML/API; cookie лишь перевыпускается. X-Forwarded-For принимается только от доверенного proxy peer. Это ограничение объёма, не гарантия распознавания распределённого скрейпинга; host-level fail2ban требует отдельной проверки на приёмке. Контекст — [CONTEXT](../CONTEXT.md#history-access-reliability-2026-09-20).

- **Rate limit (Redis-based)** — все `/api/*` ограничены: 120/мин на IP для основного API, 600/мин для `/api/v1/embed/*`. Окно 60 сек, ключ `rl:<ip>` / `rle:<ip>`. При превышении — `429 {detail: "Rate limit exceeded"}` с `Retry-After: 60`. При недоступном Redis — middleware пропускает запрос (`logger.warning` + allow). `RateLimitMiddleware` в `backend/app/main.py`.
- **CORS** — белый список в `app/main.py`: `settings.public_origin`, `www.` и `ru.` от `settings.public_host`, `localhost:{5173,5174,3000}`. Только `GET, OPTIONS` для cross-origin. Любой новый внешний потребитель — добавить явно.
- **Сжатие** — `GZipMiddleware` из Python снят; nginx сжимает HTML/JSON/XML/JS/CSS/CSV/calendar на публичном пути. Не считать прямой ответ backend:8000 эквивалентом edge-ответа по заголовкам сжатия.
- **Ошибки** — обычный FastAPI `{"detail": ...}` встречается в API, но контракт зависит от маршрута и статуса (в том числе 202/503 у BI); общего поля `code` и единой схемы ошибок нет. Проверять конкретный consumer-contract, а не выводить его из одного маршрута.
- **Пустой ряд / no data** — нет общей схемы для всех контекстов: федеральный `/indicators/{code}/data` отдаёт `{"indicator", "count", "data"}` с пустым `data`; world `/indicators/{slug}/{code}/data` отдаёт `points` и `forecast`; региональный месячный маршрут возвращает 404 при отсутствии точек. Семантика — в [`data-contracts.md`](data-contracts.md).
- **`/api/docs`, `/api/redoc`, `/api/openapi.json`** — гейтированы через `settings.debug`. На проде (`DEBUG=false`) Swagger физически отключён в FastAPI-конструкторе (`docs_url=None`). Не оставлять `DEBUG=true` на проде.
- **Backend Sentry** — **не подключён** (нет ни SDK в `requirements.txt`, ни init в `main.py`). Aspirational — добавить при первом инциденте, требующем трейсинга. Сейчас единственный backend-канал — JSON-логи в `stdout` (формат через `JsonFormatter`, видны через `docker compose logs backend`).
- **Telegram-алерты (`alerting.py`)** — кастомный канал для критических событий ETL и форкастов: уведомление о провале daily-job или конкретного парсера. Включается через `RUSTATS_TELEGRAM_BOT_TOKEN` + `RUSTATS_TELEGRAM_CHAT_ID` через действующий environment mapping. См. `backend/app/services/alerting.py`.
- **Спокойный режим Telegram (`telegram_calm.py`, с 2026-11-08, решение владельца)** — технические виды (`HELD_KINDS`: выгрузка данных, всплески 5xx, сброс нагрузки, сторож хоста, сбои задач, просрочки, аналитика) не отправляются сразу, а пишутся в `telegram_outbox` строкой `method=held` и раз в сутки в 09:10 МСК приходят одной сводкой без красного: первой строкой «нужно ли что-то делать», дальше сайт, данные, задачи и свёрнутые подробности. Сразу приходят только `site_down` (настоящие 5xx выше порога монитора идут без перерыва дольше 3 минут и в сумме ≥10 минут), `site_up` (ошибок больше нет; проверяет сторож хоста раз в минуту), `disk_space` и `prod_config_alert`; регистрации, обратная связь, дайджест, Пульс и отчёты не трогаются. Откладывается только главный чат. Досылка (`telegram_resend`) смотрит только `sendMessage` и held-строки не трогает; `analytics_marts._server_5xx_spikes` считает всплески по `kind` и видит их как раньше. Выключатель `RUSTATS_TELEGRAM_CALM_MODE=false` возвращает прежний поток. Предел: если backend целиком не отвечает, 5xx не считаются вовсе и `site_down` не придёт — это закрывает только внешний монитор `/health/live`.
- **Сторож данных (`upsert.point_rejection`, с 2026-11-08)** — единственная точка записи рядов `bulk_upsert` (через неё идут все парсеры `base_parser`, derived `calculation_engine`, недельные парсеры Росстата, ключевая ставка и мировой `world_imf_ingest`) не пишет точки с датой раньше 1800 года или дальше 730 дней вперёд, а также `NaN`/`±inf` и нечисловые значения; остальные точки той же пачки записываются. Об отброшенном — лог `ERROR` и алерт `data_guard` (раз в сутки на ряд, в спокойном режиме — в утреннюю сводку). Пара к нему — **ежедневная проверка базы `data_sanity_job`** (08:20 МСК): тот же запрет по всей `indicator_data` (51 мс на проде 08.11.2026), находка → алерт `data_sanity` с подсказкой «почисти битые точки». Мировые и региональные таблицы проверка не сканирует (16,5 и 4,5 млн строк; ручная проверка 08.11.2026 нашла их чистыми). Повод — точки цен на топливо с датами 0001-… (запись `docs/backlog.md#fuel-year-pages-2026-11-08`).

## База данных и ETL

- **Идемпотентность федеральных парсеров** — `BaseParser.run` пишет в `indicator_data` через `bulk_upsert` по уникальной паре `(indicator_id, date)`. `ON CONFLICT ... DO UPDATE WHERE value <> excluded.value` учитывает ревизии источника; повтор без изменений даёт `(records_added, records_updated)=(0,0)`. `None` не затирает точку, дубли дат схлопываются `last wins`. См. ADR-0002 и `backend/app/services/upsert.py`.
- **Пакетный seed** — `seed_data.py` идемпотентный: повторный запуск не создаёт дублей. `entrypoint.sh` гонит его при каждом старте.
- **Бэкап перед деплоем** — `deploy.sh` вызывает `scripts/pg-backup.sh` как hard gate. Скрипт создаёт полный `pg_dump -Fc` и отдельный data-only gzip SQL identity-таблиц (с круга 11 от 09.10.2026, до выкладки, их девять: пять прежних и четыре таблицы кабинета; `user_signups` в эту копию не входит), после успешного дампа оставляет одну новейшую пару файлов (`KEEP_COPIES`, по умолчанию 1; до 11.11.2026 — 14 дней хранения, что заполнило диск). Копия на Mac — раз в месяц, одна ([workflow](workflow.md)). Следствие: на сервере нет копии старше суток; откат на неделю назад возможен только из месячной копии на Mac или offsite, если он включён. В полный дамп не входят данные `session_replay_chunks` (`--exclude-table-data`): записи сессий слишком велики и временны. Наличие dump/heartbeat не подтверждает restore или offsite; см. [восстановление ниже](#восстановление-и-наблюдаемость).
- **Rolling-window очистка** — старые `fetch_logs` (>90 дней) и старые `forecast_runs` без активных привязок чистятся вручную раз в квартал; скрипта `scripts/cleanup-old-runs.py` в репозитории больше нет — перед использованием нужен новый SQL по этим таблицам.
- **Календарь** — APScheduler-job `calendar_refresh` ежедневно в 03:00 МСК обновляет rolling 12 мес. Public API допускает `official_explicit` и **только CBR** `official_rule`, причём требует `is_estimated=false` и ненулевые `event_key`, `source_url`, `source_hash`, `last_seen_at`; старые rule-строки Росстата/Минфина скрыты. Прошедшая дата без `actual_value` отображается как `awaiting_confirmation`, а не как релиз. Цифры покрытия из проверки 2026-05-10 — история, не текущий счётчик. См. ADR-0005 и `backend/tests/test_calendar_truth.py`.

## Парсеры и источники

- **Защита от частичной загрузки** — `BaseParser.run` откатывает текущую транзакцию при исключении, затем записывает `fetch_log.status="failed"` и `error_message`; факты живут в `indicator_data`. Пустой ответ ранее живого ряда получает `parsed_zero`, ожидаемо пустой — `no_new_data`, резервный источник — `fallback_used`. `records_added` и `records_updated` учитываются отдельно. `fetch_log` со статусом `running` создаётся отдельным commit до fetch, поэтому это не одна транзакция на весь аудит.
- **Ретраи (уточнение30.09, 08.10)** — общий `http_client.create_session` использует urllib3 `Retry(total=3, connect=1, backoff_factor=2)` для GET/POST и408/500/502/504; connect timeout 15 с напрямую / 30 с через прокси (read — от вызывающего); хост, отказавший в соединении на всех хопах, 20 мин отвечает мгновенной ошибкой (предохранитель в памяти процесса);403/407/429/503 переходят direct→HTTP→SOCKS fallback без status-retry. Parser-specific Retry/timeout и прямые `requests.get` имеют собственные границы: общий client не охватывает автоматически все запросы. Повтор daily-job — дополнительный job-level механизм, не единственный retry.
- **`is_active=false`** — выключение парсера для индикатора без удаления данных. ETL job их пропускает.
- **`is_listed=false`** — федеральный индикатор скрыт из обычного листинга категорий, но `/indicators?include_unlisted=true` отдаёт его глобальному поиску. Детальный маршрут доступен по коду. Перед скрытием проверить reachability через sibling/variant/frequency/bespoke (anti-orphan контракт в `AGENTS.md`).
- **Minfin in-place CSV content update (trap)** — `minfin.gov.ru/opendata/7710168360-fedbud_month/` публикует CSV под стабильным URL `data-YYYYMMDDTHHMM-structure-...csv`. Timestamp в имени = **дата создания паспорта набора**, не snapshot content. Минфин **дополняет content того же URL** новыми месяцами в течение дня без смены URL. Симптом, который мы наблюдали 5-11 мая 2026: `daily_update_job` в 03:00 MSK скачивал CSV → `bulk_upsert` возвращал `(0, 0)` → status `no_new_data`; через 12-14 часов тот же CSV отдавал уже свежий контент с новым месяцем. **Контрмеры**: 1) `late_minfin_etl_job` (APScheduler, 15:00 MSK ежедневно) — second pass через `run_etl_for_parser_type("minfin_budget_csv")`; 2) `minfin_budget_parser` логирует `last_parsed_date` + `last_db_date` + `len(points)` (см. `MinfinBudgetParser._fetch_and_parse`) — для последующих аномалий легче ловить разрыв через `docker compose logs backend | grep "Minfin budget"`. См. `docs/data_sources.md::budget-*`.
- **Minfin catalog 503 / `/ru/` CSV 404 (trap, 2026-07)** — каталог OpenData отвечает 503 intermittent; раньше global Retry(total=3) исчерпывался и три `budget-*` индикатора независимо долбили каталог. Контрмеры: Minfin-specific `Retry(total=1, connect=1, read=1)`; ban-статусы 403/429/503 передаются proxy fallback без urllib3 status-retry, process TTL-кэш CSV URL, last-good URL в state Redis. CSV path без `/ru/` (`/ru/opendata/…/data-*.csv` → 404).

## Frontend и кэш

**Архив релизов, локальная реализация 2026-09-20.** Hashed-ассеты старого работающего и нового frontend публикуются атомарно по файлам с manifest в общий архив до выдачи нового HTML; nginx использует read-only fallback. HTML, source maps и фиксированные имена исключены. На успешном деплое prune оставляет три релиза только после smoke/watch; при rollback сначала повторно публикуется восстановленный релиз. Автоперезагрузка устаревшей вкладки (`lib/chunkRecovery.js`, с 2026-10-04): при `vite:preloadError`, отклонённом `import()` или `React.lazy` в `ErrorBoundary` — не чаще одного раза в 5 минут (отметка времени и release в sessionStorage; при недоступном storage перезагрузки нет), не во время ввода в поле и не при идущей выгрузке файла; иначе обычный экран ошибки. Архив не заменяет совместную сборку backend/frontend и не гарантирует бессрочный replay. Порядок и одобрение SHA — [workflow](workflow.md#прод-деплой).

**История SEO, решение владельца 2026-09-20.** Все действующие публичные canonical-страницы должны входить в sitemap. Curated-отбор мировых годов, повышенный порог точек годов РФ, порог стран мирового рейтинга и выборка популярных/соседних пар сняты. Условия самого SSR (существующие данные, допустимая территория, сопоставимость), канон и исключение служебных URL остаются; sitemap не создаёт страницы, для которых нет маршрута. Региональный реестр учитывает также округ/РФ, скрытые из каталога публичные ряды и месячные карточки. Генерация потоковая, границы/счётчики версионированы `public-v3`. Детали и статус выкладки — [CONTEXT](../CONTEXT.md#history-access-reliability-2026-09-20) и [backlog](backlog.md#history-access-reliability-2026-09-20).

- **Asset-hash mismatch trap** — Vite строит файлы вида `index-<hash>.js`. Если backend и frontend пересобраны не вместе, новый `__spa-index.html` будет ссылаться на ассеты, которых уже нет на nginx-сервинге (или наоборот). **Правило:** backend/frontend собираются согласованно; production выпускается только через `scripts/deploy.sh` до одобренного SHA с обновлением scheduler тем же backend image. Fallback на `/__spa-index.html` задаёт `frontend/nginx.conf`; `Caddyfile` только проксирует в nginx на `127.0.0.1:3000`.
- `behavior-standalone.js` лежит под `/assets/`, но имя файла без хэша: nginx отдаёт его с `Cache-Control: no-cache, must-revalidate`, чтобы старая версия не оставалась у посетителя после релиза; архив hashed-ассетов этот файл не хранит.
- **nginx no-cache always на SSR HTML** — без флага `always` в `add_header Cache-Control` сам заголовок не применялся к 4xx/5xx и переопределялся upstream-заголовком. Браузер кэшировал stale HTML на часы. Фикс 2026-05-22: `proxy_hide_header Cache-Control` + `add_header Cache-Control "no-cache, no-store, must-revalidate" always` на всех SSR-routes (`/`, `/about`, `/privacy`, `/compare`, `/calculator`, `/calendar`, `/demographics`, `/widgets`, `/category/*`, `/indicator/*`, `/__spa-index.html`, `/embed/*`). Ассеты в `/assets/` остаются `max-age=31536000, immutable`. См. `frontend/nginx.conf`. Закрывает Browser-cache trap из `CONTEXT.md::Operational invariants and traps`.
- **CSP в Caddyfile** — отдельные политики для embed и остальных страниц. Основная разрешает домены Метрики/Вебвизора и Яндекс-рекламы, `connect-src` включает `*.ingest.sentry.io`; `font-src` — self / yastatic / data. Общего разрешения Google Fonts, Webmaster или внешнего Sentry script в текущем файле нет. Новый внешний потребитель сверяется с конкретной директивой CSP, затем с браузером; наличие frontend SDK не заменяет разрешение connect-src.
- **Frontend Sentry** — `@sentry/react` подключён в `frontend/src/main.jsx`. DSN — env-переменная `VITE_SENTRY_DSN`. Backend Sentry — отдельная задача (см. выше).
- **SEO single-source** — `__spa-index.html` собирается на каждый запрос: SSR-meta в `<head>` для ботов и людей; legacy локальные `seo.js` константы удалены. См. ADR-0003.

### Effective окружение30.09

[Ops-досье](code-review/ops-mechanism-acceptance-2026-09-30.md) связывает source, image,
host units и limits. CPU quotas суммарно5 при общем4vCPU, PG/Redis/host дополнительно
конкурируют; RAM limits7616MiB оставляют≈325MiB при одновременном максимуме. App pools73,
ordinary budget97, но app-role rustats superuser и может занять reserved slots. Work_mem
расходуется по операциям/планам, а не фиксированно по соединениям; capacity не выведена из
этой арифметики. Host nginx logrotate — всё ещё14/compress/copytruncate, source —
7/nocompress/rename+USR1. Caddy active config и402backend payload SHA аттестованы отдельно.

Host HTTP CONNECT→Tor bridge вне Git использует hardcoded Basic credential и логирует
headers вместе с Proxy-Authorization. Это подтверждённый дефект; его исправление/rotation
не выполнялись при read-only сборе. Provider backup/SLA/control-panel остаются access limit,
а capacity/RTO — unmeasured properties. Санитизированный snapshot/точные источники — в JSON.

## Производительность

- **Cache (Redis)** — `app/core/cache.py` строит инвалидируемые ключи через `versioned_key(ns, rest)` и `bump_namespaces()`; федеральные detail/data/list, мировые карточки и SSR используют разные namespace. `deploy.sh` удаляет только SSR HTML через `SCAN` + `UNLINK`; версии namespace не сбрасывает. Есть отдельный state Redis для сессий/локов и durable-копии каталога стран. Локальная main хранит поколение `world-catalog` в state Redis и использует отдельный `g2`-ключ; механизм описан в [`data-contracts.md`](data-contracts.md#параллельные-изменения-рабочего-дерева). Для ручной SQL-правки составить адресную инвалидацию по конкретным consumer'ам и проверить холодный ответ.
- **DB indexes/identity** — федеральный факт уникален по `(indicator_id,date)`, мировой по `(indicator_id,date)`, российский региональный годовой по `(indicator_id,region_id,year)`, месяц по `(indicator_id,region_id,month)`, мировой субнациональный по `(indicator_id,region_id,period)`. Поля и миграции сверять через `backend/app/models.py` и CI migration-drift, не переносить старые `data_points/period_start/frequency` в новые запросы.

## Мониторинг

**Пульс, локальная реализация 2026-09-20.** UTM-строки, платное привлечение Метрики, органический поиск, доход РСЯ и расходы на рекламу не смешиваются. Нет снимка за день — нет данных, а не нулевой трафик/доход; различаются `missing`, `failed`, `stale`, `invalid`, сохраняются metadata периода, счётчика и семплирования. Сумма дохода за окно не выдаётся за дневной доход, отсутствие расходов не доказывает прибыль. Приёмка — [backlog](backlog.md#history-access-reliability-2026-09-20).

- **Health endpoints** — `/api/v1/health/live` (тривиальный liveness), `/api/v1/health/ready` (readiness: SELECT 1 + PING обоих Redis + `scheduler.running`; устаревший ETL и fd >80% soft ulimit — мягкая `degraded: true`, не 503 — см. Р-8), `/api/v1/analytics/health` (внутренний `X-Analytics-Token`; `failed_sync_runs` считает все строки `status=failed`, не только последние 24 часа). Docker-healthcheck и deploy-smoke смотрят на `/health/ready`; external uptime monitor — на `/health/live` + `/health/ready`. Поле `checks.open_fds` — текущее число дескрипторов процесса.
- **FD gauge / ulimit (2026-09-20)** — `/api/v1/metrics` отдаёт `fe_process_open_fds` и `fe_process_open_fds_limit`. Сервис `backend` в `docker-compose.yml` поднимает `ulimits.nofile` soft/hard 65536 (Docker-дефолт 1024 на python-slim исчерпывался плановыми Session/шрифтами). Staleness-алерт дописывает `fd N/limit`.
- **JSON-логи** — все backend-логи в stdout как JSON (`{ts, level, logger, msg, exc?}`). Удобно вбирать в любой коллектор.
- **SEO audit** — `scripts/seo-audit.py` периодически проходит по списку indicator-страниц и проверяет, что SSR возвращает осмысленные `<title>`, `<meta description>`, `og:*`, JSON-LD. Запускается вручную, расписание — после крупных правок.

## Восстановление и наблюдаемость

**Статус проверки 2026-09-30:** [свежий существующий dump доставлен на Mac и восстановлен](code-review/backup-acceptance-2026-09-30.md) в изолированном PostgreSQL, отдельно проверен identity SQL. Размеры/SHA-256 совпали с сервером; full restore 154,885 с, все constraints валидны, identity без сирот. Исходный [снимок 27.09](code-review/runtime-inventory-2026-09-27.json), когда restore ещё не проводился, сохранён; [повторная ops-сверка](code-review/runtime-observation-2026-09-30.json) и [runtime-inventory.json](runtime-inventory.json) разделяют даты. Cron backup — 04:00 UTC (07:00 МСК). S3 bucket/endpoint и aws CLI по-прежнему не настроены; внешние бэкапы провайдера не проверялись. Первый сценарий не проверял owner/ACL/application. [Поздняя проверка30.09](code-review/ops-mechanism-acceptance-2026-09-30.md) добавила restore без подавления owner/ACL (182,967с, синтетический исходный role rustats, nondefault ACL0), HTTP API/email auth/CSRF/state-session и current nginx SSR/assets на restored DB. Полный browser/external-provider/AOF/CH failover и бизнес-цели RTO/RPO остаются вне этих bounded probes; время pg_restore не подменяет RTO.

- **Что является исходным состоянием.** Postgres хранит ряды, пользователей и аналитику; полный `.dump` — основной путь восстановления, `.identity.sql.gz` — отдельный data-only запас для пяти identity-таблиц. Российский годовой региональный контекст дополнительно воспроизводится из версионированного артефакта `backend/app/data/regional/` через `seed_regional.py`. ClickHouse — вторичная копия Postgres, восстанавливается через resync; том `clickhouse_data` не входит в `pg_dump`. Сессии, lockout и локи живут в state Redis (в compose отдельный `redis-state` с AOF, если `RUSTATS_STATE_REDIS_URL` указывает на него); не подменять восстановление Postgres очисткой state Redis.
- **Что доказывает heartbeat.** `pg-backup.sh` сначала создаёт оба файла, при настроенном S3 загружает их, удаляет старые локальные файлы, затем шлёт зелёное Telegram-сообщение и пытается записать `fe:ops:pg_backup_last_ok` в state Redis. Отказ записи heartbeat только предупреждает. `/health/ready` выводит устаревший существующий heartbeat как мягкую деградацию; полностью отсутствующий heartbeat её не включает, а 503 даёт при отказе БД/Redis/планировщика; heartbeat не проверяет читаемость dump и полноту offsite-копии. Если `OFFSITE_S3_BUCKET` задан, а `aws` отсутствует либо заливка или сверка размера объекта не прошла, с 27.10.2026 скрипт завершается успешно (локальный дамп есть), но шлёт жёлтое «offsite НЕ выполнен» вместо зелёного (раньше мог прислать зелёное: пробел сигнала закрыт в коде, на хост не выпущено; тесты `backend/tests/test_pg_backup_offsite.py`). Включение — [runbook](offsite-backup-runbook.md). Отдельный runtime-снимок подтверждает отсутствие настройки именно S3-пути этого скрипта; он не исследует внешнюю систему бэкапов провайдера. Источники: `scripts/pg-backup.sh:62-115`, `backend/app/api/system.py:74-174`, `backend/tests/test_backup_readiness.py`.
- **Проверочный restore.** На отдельном Docker-томе/контейнере без сетевого порта восстановить свежий `.dump`, сверить версии схемы, число пользователей, связность identity и выборку ключевых рядов с контрольными данными момента backup; затем отдельно проверить `.identity.sql.gz` в чистой совместимой схеме. Команды изолированного примера — в [`workflow.md`](workflow.md#git-и-окружения). Записать дату, входной dump, результат, длительность и кто проводил учение. **Приёмка 30.09** выполняла этот сценарий (58 public-таблиц + `research.source_catalog`, Alembic `20260927_world_nonzero_idx`); свои контейнер/том удалены только после проверки owner labels. Полный [машинный протокол](code-review/backup-acceptance-2026-09-30.json) содержит входные хэши, контрольные числа и пределы проверки. Для offsite дополнительно скачать объект в этот изолированный контур и сверить хэш/восстановление; факт `aws s3 cp` без restore недостаточен.
- **Границы автоматического отката.** `deploy.sh` откатывает образы и frontend-ассеты после smoke/watch, но не делает Alembic downgrade и не откатывает записи пользователей. При несовместимой схеме действовать по [Deploy-scope trap в CONTEXT](../CONTEXT.md) после отдельной оценки изменений данных. Не выполнять `pg_restore --clean` на рабочей БД лишь потому, что smoke красный.

## Деплой-инцидент trap: forecast retrain не пробрасывается

**Исторический trap закрыт частично автоматикой.** После seed/startup отдельный `scheduler` запускает ETL пустых source-рядов и `catch_up_empty_forecasts`; после daily/late ETL тот же gap-fill повторяется. Он выбирает `forecast_steps>0` без текущего прогноза, но вызов retrain не гарантирует точек при недостаточной истории, отключённой стратегии или ошибке. Для нового derived проверить `/data`, `/forecast` и `fetch_log` после catch-up; ручной retrain и адресная инвалидация нужны по результату диагностики, обычный `FLUSHDB` не является шагом релиза. См. `main.py::_startup_data_catch_up`, `forecast_pipeline.py::catch_up_empty_forecasts` и [`workflow.md`](workflow.md#прод-деплой).

## Канарейка изменений

Перед мерджем feature-ветки в `main` — провести по чеклисту:

1. Pytest и vitest зелёные локально.
2. Vite build без ошибок.
3. Браузер-snapshot ключевых страниц (см. `workflow.md`).
4. Если правка касается парсеров — идемпотентность проверена двойным прогоном `daily_update_job` на dev-БД.
5. Если правка касается forecast-стратегии — `rebuild-all-derived.py` гонит первым прогоном изменения, вторым — все нули.
6. Если правка касается SEO/SSR — `User-Agent: YandexBot/3.0` запрос к 3+ страницам, проверить `<title>` и `<meta>`.

Без зелёных «6 из 6» в `main` не идём.

### Dual-host locale cutover

RU/EN запускаются как два канонических HTTPS-хоста с одинаковыми путями.
Sitemap, RSS, canonical, hreflang, OG и JSON-LD формируются от исходного Host;
кэш разделён по host/locale. После cutover людей с IP России/СНГ с apex
уводим на `ru.`; `Accept-Language` не редиректит. Bot UA и служебные маршруты
всегда получают ответ запрошенного хоста. Канарейка: `scripts/dual-host-release-gate.py`.

## 2026-10-09 — измеренная деградация и исправление

На runtime 0bcf68b4 healthy контейнеры сочетались с Rollups 15min failed
и 503 каталога: health не подтверждает успешный фоновой расчёт.
Исправления: normalized visitor/time covering index и узкая history staging;
Eurostat no-op не инвалидирует кэш, value revision не сбрасывает country
catalogue без изменения его nonzero signal/metadata. Не повышены worker/
память/таймауты. Доказательства и остаточные пределы —
[приёмка](code-review/performance-acceptance-2026-10-09.md).

Уточнение performance delta 09.10: history index частичный по четырём
session event types; visitor/time/id и исходные ключи покрыты. Константы
в SQL совпадают с expression/predicate индекса и при generic prepare.
Raw читается по visitor/time/id; подбор fallback portrait использует
индекс (visitor, started_at DESC, session_id). Миграция обновляет
статистику expression index перед первым запуском.

### 2026-10-09 — холодная пересборка каталога

После первого выпуска прямой catalogue rebuild всё ещё падал на SQL30s;
VACUUM метаданных сам по себе не устранил это. Listed metadata279k
вызывала отдельные random probes nonzero index. Materialized DISTINCT
indicator IDs меняет способ чтения, сохраняя exact signal/count/name
контракт, RU/региональные счётчики и empty-world fallback. Чистка
одинаковых заголовков после overrides кэшируется LRU8192 по исходной
строке, без изменения текста/quality. Боевое полное old/new payload
сравнение в repeatable-read совпало; candidate rebuild6.661s.
Operator SQL: `deploy/pg-world-catalog-maintenance.sql` — обычный
VACUUM/ANALYZE, autovacuum метаданных0.01/1000, statistics indicator_id1000.
Он применён вручную; не запускается при каждом рестарте приложения.
Таймауты/память/workers не повышены. Границы и выпуск — performance
acceptance09.10; actual auto-vacuum timing не обещан.


### Telegram delivery — 2026-10-09

Прямой IPv4 Telegram API на production периодически даёт ConnectTimeout даже после extra_hosts; авторизованный существующий CONNECT relay проверен отдельно. Отдельный маршрут задаётся RUSTATS_TELEGRAM_PROXY_URL. В технической досылке теперь есть scheduler/5xx/anomaly/ETL/staleness warnings: producer mute после неудачной отправки больше не оставляет их вне retry queue.

Основной контракт: [data-contracts.md](data-contracts.md#telegram-маршрут-и-техническая-досылка--2026-10-09).

### Алерты 5xx: общий счёт и сброс нагрузки — 2026-11-02

Всплеск алертов 01–02.11.2026 разобран по архиву `telegram_outbox`, логам backend/scheduler, Redis и sar на проде (только чтение). Почти все 325 ответов 5xx за сутки — намеренный сброс очереди холодного рендера на `/seo/world-indicator-year/*`; всплески совпали с окнами iowait 25–40% (00:00–00:30 и 02:00–02:50 UTC), при swap 34% и памяти backend 95% лимита. Наблюдение датировано, не вечное. Код алерта изменён локально (сброс отдельно от настоящих ошибок, один алерт на все воркеры): контракт — [data-contracts.md](data-contracts.md#алерты-5xx-настоящие-ошибки-и-сброс-нагрузки--2026-11-02). Нагрузка на диск хоста и память не лечатся этим изменением: источник не установлен, см. [backlog](backlog.md#alert-spike-2026-11-02).

Там же, вечером 02.11: красная «Ежедневная выгрузка данных» (45 рядов с ошибкой) — это сайт Росстата на технических работах, а не поломка проекта. Заглушка распознаётся, ряды идут отдельной жёлтой строкой и догружаются сами (`rosstat_recovery_job`, раз в 30 минут): [data-contracts.md](data-contracts.md#etl-заглушка-технические-работы-и-догрузка-росстата--2026-11-02).

### Диск хоста и ферма: всплеск 5xx 05.11.2026

05.11.2026 с 06:10 до 07:30 UTC задержка диска `sda` выросла с 6–24 мс до 0,5–1,5 с при **падении** числа операций (sar), iowait дошёл до 85%, load average 32, PSI io some 98%; тот же след в `dmesg` 12.10.2026. Параллельно ферма резидентных IP (46 тысяч запросов с 39,7 тысяч адресов за 53 минуты, без Referer) занимала очередь рендера и пул БД холодными страницами. Монтирование `/`: `discard,nobarrier,commit=30`, свободно 4,2 ГБ (95%). Наблюдение датировано, не вечное. Что сделано в коде и что за владельцем: [backlog.md](backlog.md#alert-spike-2026-11-05), контракт нового потолка: [data-contracts.md](data-contracts.md#потолок-безымянного-трафика-на-страницы-длинного-хвоста--2026-11-05).

Выпущено 05.11.2026 (прод `8726586d`, [ADR-0026](adr/0026-graceful-degradation-and-traffic-priority.md)); хост: `/` без `discard`, `vm.swappiness=10`; Redis без swap и с щадящей записью применены вживую. Итог и живые цифры — [backlog.md](backlog.md#alert-spike-2026-11-05).

**Дополнение 08.11.2026 (локально, не выпущено; [ADR-0026](adr/0026-graceful-degradation-and-traffic-priority.md#дополнение-08112026-полезные-роботы-подтверждаются-ферма-упирается-в-общие-бюджеты-человек-получает-пропуск)).** Полезные роботы вне трёх поисковиков подтверждаются по официальным сетям (`goodbot`) и не делят ни бюджеты nginx, ни слоты рендера с фермой; неподтверждённые роботы и самозванцы — общий бюджет `robotcold` 5 зап/с на сайт; человек без Referer в волну фермы получает пропуск со страницы 429 (нужен `FE_HUMAN_PASS_SECRET` в `.env`, без него выключено). Утренняя сводка по классам трафика — `services/bot_traffic.py`. Это не 100 %: ферма с поддельным Referer или исполняющая JS проходит дальше; следующий слой — CDN/антибот или отпечаток TLS (решение владельца).

<a id="postgres-memory-2026-11-13"></a>

### «Диск хоста тормозит» — это чтение Postgres, а не диск: замер 13.11.2026

Сообщения «Диск хоста тормозит» и «Сервер сбрасывает нагрузку» после чистки диска (25 ГБ свободно) участились: 12.11 — восемь эпизодов на 249 минут. Замер на боевом 13.11.2026 (только чтение):

| Что измерено | Значение |
|---|---|
| cgroup Postgres: `memory.max` / `memory.current` | 3072 МБ / 3071 МБ |
| cgroup Postgres: `memory.events max` (упёрся в потолок) | 9 735 435 раз за 6 недель |
| cgroup Postgres: `io.pressure some total` | 394 567 с при 377 680 с на всём хосте — почти всё ожидание диска создаёт база |
| Размер базы / `shared_buffers` | 12 ГБ / 896 МБ |
| Попадание в кэш (`pg_stat_database`) | 89,4 % |
| cgroup backend: `memory.current` / `max`, swap | 2255 / 2304 МБ, 569 МБ в swap; потолок достигнут 112 993 раза |
| Память хоста / сумма потолков контейнеров | 7,9 ГБ / 7,6 ГБ |
| Чтение базы с диска в замере 6 минут | 203 МБ/мин |

Кто читает (доля чтений с диска по `pg_stat_statements`, окно 6 минут 13.11 и накопленно с 26.09):

| Запрос | Сейчас | С 26.09 | Откуда |
|---|---|---|---|
| все листинговые ряды категории страны (в среднем 1766 строк, 1,4 МБ за вызов) | 36,8 % | 13,6 % | блок «Ещё в разделе» на странице ряда страны, `seo_world.py` |
| все ряды страны целиком (8371 строка, 7,9 МБ за вызов) | 23,1 % | 2,8 % | `_country_indicators` в `api/world.py` (карточка ряда, сравнение) |
| `SELECT COUNT(*) FROM world_data_points` | 0 | 22,5 % | в текущем коде не найден, за время замера не вызывался |
| `max(ingested_at)` по `raw_metrika_visits` и `behavior_events` | — | 6,1 % | `check_anomalies` каждые 15 минут, витрины Пульса |

Что сделано в коде (ветка `fix/pulse-week-2026-11-13`, не выпущено): блок «Ещё в разделе» считается один раз на страну и категорию и хранится списком id (`_category_siblings`); свежесть сырья читается по индексам (`ingest_freshness.py`); сессионизация, синк ClickHouse и счётчик роботов больше не стартуют в одну секунду (`main.py`, сдвиги 7,5 мин и 75 с). С 12.11 тринадцать из восемнадцати «сбросов нагрузки» приходились на :00 и :30 — моменты, когда эти задачи совпадали.

Что не сделано и почему: запрос «все ряды страны» питает несколько потребителей (`_card_context`, сравнение, карточка) и требует отдельной правки с проверкой равенства результата на живых данных; строки `world_indicators` широкие (867 МБ на 380 тыс. строк из-за SEO-текстов), вынос текстов из основной таблицы уменьшил бы чтение всех запросов к ней в разы, но требует перезаписи таблицы в окно обслуживания; памяти сервера не хватает на базу такого размера — увеличение ОЗУ или перераспределение потолков есть решение владельца. Прежний вывод «вопрос к провайдеру (хранилище ВМ)» в тексте сообщения этим замером не подтверждается: текст сообщения стоит пересмотреть после выпуска и повторного замера.

**Дополнение 13.11.2026 (ветка `perf/world-country-rows`, не выпущено).** Запрос «все ряды страны» сужен: [узкое чтение рядов страны](#world-country-rows-2026-11-13). Вынос текстов из основной таблицы оценён без изменений в базе: [оценка](#world-indicators-texts-2026-11-13).

<a id="world-country-rows-2026-11-13"></a>

### Узкое чтение рядов страны: карточка и сравнение — 13.11.2026

Ветка `perf/world-country-rows` от `fix/pulse-week-2026-11-13` (71981486), **не выпущено**. Ответы API не менялись; ключи кэша, схема базы и настройки не тронуты.

**Что читалось.** `_country_indicators` в `backend/app/api/world.py` выполнял `SELECT … FROM world_indicators WHERE country_id = …` и возвращал полные строки. Его звали карточка ряда (`_card_context` → `indicator_meta`, `indicator_data`), ряд сравнения (`world_compare_series`) и среднее по странам с режимом (`world_compare_average_series`, по одному вызову на каждую страну). Строки страны лежат в основной таблице почти по одной на страницу: у Испании 10 831 строка на 10 581 странице (83 МБ) на каждый вызов.

**Что читается теперь** (`backend/app/services/world_country_rows.py`):

1. Справочник страны — разные пары (провайдер, набор данных). Запрос идёт только по индексу `ix_world_indicators_card_lookup`, без строк основной таблицы.
2. Из справочника теми же функциями, что считают ключи карточек и понятий, отбираются нужные пары; полные строки читаются только для них, в порядке `id`.

| Потребитель | Какие ряды нужны | Решение |
|---|---|---|
| `_card_context`: первичный ряд и частоты | тот же ключ карточки (провайдер, `dataset_stem`); тот же ключ слияния каталога (`catalog_stem_alias`); карточки этих рядов | узкая выборка `card_dataset_pairs` |
| `indicator_meta`: переключатель срезов | карточки той же группы срезов (`variant_stem_alias(dataset_stem)`) у того же провайдера | та же узкая выборка, третий элемент `_card_context` |
| `indicator_data`, `world_compare_average_series` | только первичный ряд и частоты | узкая выборка через `_card_context` |
| `world_compare_series`: выбор ряда | ряды из наборов понятия у провайдера (первый шаг `concept_for_indicator`) и национальные ряды по коду | узкая выборка `compare_dataset_pairs` плюс коды |
| запасная ветка `_country_indicators_for_listing` | первичные ряды всех карточек страны, у которой нет ни одного listed-ряда | полный запрос оставлен: сузить нельзя. На боевом 13.11 таких стран 0 из 54 активных |

Почему результат тот же: оба отбора зависят от ряда только через провайдера и набор данных, а `catalog_stem_alias` и `variant_stem_alias` — только через `dataset_stem`. У карточки один провайдер и один `dataset_stem`, значит любая карточка попадает в выборку целиком или не попадает вовсе; расчёт обращается только к карточкам из выборки. Отбор идёт по сырым значениям из базы кодом Python, а не выражением SQL, поэтому правила регистра и пробелов не расходятся.

**Сверка на боевых данных** (13.11.2026, боевой 4f8fa681, контейнер `scheduler`, транзакция только для чтения, по одному ряду без параллельных запросов; файлы модуля в ветке и на боевом сверены по md5, скрипт сверки исполнял текст модуля из ветки):

| Что сверено | Объём | Расхождений |
|---|---|---|
| Справочник против пар из полного чтения | 21 страна, 56 219 строк | 0 |
| Первичный ряд и частоты карточки | 365 рядов (340 listed, 25 скрытых), 18 провайдеров, 226 наборов | 0 |
| Состав переключателя срезов | 365 рядов | 0 |
| Порядок кнопок переключателя срезов | 365 рядов | 9 — см. ниже |
| Выбранный ряд сравнения | 252 пары страна × понятие (12 понятий, 180 с найденным рядом) | 0 |

Строк на вызов в выборке: было в среднем 4822 (медиана 4488), стало в среднем 9,2 (медиана 7, максимум 73); для сравнения — в среднем 7,7, максимум 26.

**Расхождения поштучно.** Прежний запрос шёл без `ORDER BY`: у больших стран строки приходили в порядке расположения на диске (Bitmap Heap Scan), у малых — в порядке индекса (Index Scan по `ix_world_indicators_card_lookup`). Порядок на диске меняется при каждом обновлении ряда. Узкий запрос задаёт порядок явно — по `id`. При том же порядке строк, что у старого запроса, расхождений нет ни в одном из 365 рядов. Явный порядок меняет две вещи:

- *Девять карточек из 365* (`es-`, `de-`, `tr-prc_hicp_aind-cp00-inx-a-avg`; `de-sts_trlb_a-emp-g473-nsa-i15`; `al-nrg_stk_oilm-o4669-stk-op-ths-t`; `al-ei_isrt_q-is-epi-g45-sca-i15`; `md-road_eqs_unlweig-nr-kg-lt1000`; `br-ext_lt_introeu27_2020-mio-exp-val-total`; `mx-ext_lt_introeu27_2020-pc-imp-wrl-total`): в переключателе срезов несколько кнопок с одинаковой подписью («индекс (2015 = 100)», «автомобилей», «Доля ЕС в мировой торговле») меняются местами между собой. Последовательность подписей, состав кнопок и отметка текущей — те же.
- *Первичный ряд при равном ранге.* Из 53 425 карточек 21 страны у семи два ряда делят первое место; у двух из них выбор зависел от порядка строк: `lfsi_long_e06` в Испании и Польше — два одинаковых listed-ряда, различаются именем измерения (`wstatus=TOTAL` и `indic_em=TOTAL`). Старый код в Испании и Польше выбирал ряд с большим `id`, в Турции — с меньшим; новый везде выбирает меньший `id`. У `hlth_cd_aro` (возраст `Y15-24` и `Y_LT25`) выбор совпал.

Оба случая — места, где прежний ответ определялся расположением строк на диске и мог измениться после очередной загрузки данных.

**Замер `EXPLAIN (ANALYZE, BUFFERS)` на боевом** (13.11.2026; «обращения» — счётчик `Buffers`, повторное обращение к той же странице считается снова):

| Страна и вызов | До: строк / обращений | После, справочник: пар / обращений / строк таблицы | После, ряды: строк / обращений |
|---|---|---|---|
| Испания, карточка безработицы | 10 831 / 10 604 | 1401 / 1733 / 67 | 16 / 25 |
| Испания, карточка ГИПЦ (слитая группа) | 10 831 / 10 604 | 1401 / 1733 / 67 | 42 / 79 |
| Испания, сравнение «безработица» | 10 831 / 10 604 | 1401 / 1733 / 67 | 15 / 295 |
| Германия, карточка торговли | 10 672 / 10 523 | 1399 / 1659 / 31 | 32 / 42 |
| Германия, сравнение «цены» | 10 672 / 10 523 | 1399 / 1659 / 31 | 14 / 301 |
| США, карточка FRED | 2066 / 1284 | 1975 / 549 / 12 | 1 / 4 |
| США, сравнение «цены» | 2066 / 1284 | 1975 / 549 / 12 | 15 / 301 |

Страниц основной таблицы на вызов у Испании: было 10 581 (83 МБ), стало не больше 150 (около 1 МБ). Обращения справочника — это около 30 страниц индекса (весь индекс 8 МБ, 1036 страниц) и повторные обращения к четырём страницам карты видимости; с диска в замере не читалось ничего. Холодный старый запрос в том же замере читал с диска 2937 страниц за 442 мс (Испания) и 834 страницы за 472 мс (США); узкие запросы заняли 5 мс и меньше 1 мс.

**Границы.**
- Справочник читается только по индексу, пока карта видимости таблицы свежая. У таблицы стоит `autovacuum_vacuum_scale_factor=0.01`; в замере 67 обращений к строкам на 10 831 запись. Если автоочистка отстанет, справочник начнёт читать страницы таблицы.
- Долю чтения базы с диска после правки покажет только повторный замер после выпуска.
- `concept_for_indicator` бросает ошибку реестра, если ряд подходит двум понятиям. Раньше её мог вызвать любой ряд страны, теперь только ряд из наборов запрошенного понятия. В сверке ошибка не возникла ни разу.
- Наблюдение рядом, не исправлялось и на живых данных не проверено: `_country_indicators_for_listing` ищет скрытые частоты по `_sibling_stems_match`, который не находит набор с приклеенной частотой (`prc_hpi_ooa` при listed `prc_hpi_ooq`); карточка такую частоту показывает.

<a id="world-indicators-texts-2026-11-13"></a>

### Вынос описаний и SEO-текстов из `world_indicators`: оценка 13.11.2026

Оценка без изменений в базе. Перезапись таблицы — решение владельца и окно обслуживания.

**Что измерено на боевом** (статистика `pg_stats`, размеры отношений, выборка 0,5 % строк):

| Что | Значение |
|---|---|
| Основная таблица / TOAST / индексы / всего | 867 МБ (110 920 страниц) / 134 МБ / около 580 МБ / 1588 МБ |
| Строк, строк на страницу | 380 460; 3,4 |
| Средняя строка | 1793 байта |
| Из них тексты: `seo_description` 296, `description` 262, `methodology` 243, `seo_keywords` 233, `seo_title` 199 | 1233 байта, 69 % строки |
| Разных значений `methodology` | 179 на всю таблицу |
| Триграммный индекс поиска (включает `seo_keywords`) | 326 МБ |
| Обновлений строк / из них без переноса строки (HOT) | 418 325 / 17 178 (4 %) |
| Расположение строк страны | Испания: 10 831 строка на 10 581 странице |

**Главный вывод.** Ширина строки — половина причины. Вторая половина — строки одной страны разбросаны по всей таблице (таблица заполнялась набор за набором по всем странам). Если только сузить строки, запрос по стране по-прежнему тронет почти столько же страниц; зато вся таблица начнёт помещаться в память базы. Если ещё и уложить строки по стране, запрос по стране тронет в 9–10 раз меньше страниц.

**Способ `toast_tuple_target` не работает.** Проверено на PostgreSQL 16.11 (одноразовый контейнер, 40 000 строк по 1,5 КБ): `toast_tuple_target = 256` и `VACUUM FULL`, затем обновление всех строк, затем `STORAGE EXTERNAL` у текстов — основная таблица осталась 63 МБ, TOAST 0. Postgres выносит значения только из строк длиннее 2 КБ; средняя строка здесь 1,8 КБ. Вынеслись бы только самые длинные строки, остальные остались бы широкими.

**Рабочий способ — отдельная таблица текстов** (`indicator_id`, `description`, `methodology`, `seo_title`, `seo_description`) и укладка основной таблицы по стране (`CLUSTER … USING ix_world_indicators_card_lookup`). `seo_keywords` остаётся в основной таблице: на нём стоит индекс поиска. Замер на синтетической копии (380 460 строк по 1,6 КБ, те же 11 индексов, PostgreSQL 16.11 на ноутбуке, `maintenance_work_mem` 256 МБ как на боевом):

| Шаг | Основная таблица | Страниц на запрос «все ряды страны» | Время шага |
|---|---|---|---|
| Как сейчас | 594 МБ | 7046 | — |
| Только укладка по стране | 594 МБ | 1419 | 19 с |
| Копия четырёх текстов в отдельную таблицу | — | — | 6,6 с, основная таблица доступна |
| Удаление колонок и укладка по стране | 297 МБ | 715 | 28 с |
| То же без `seo_keywords` и без индекса поиска | 212 МБ | — | 6,6 с |

Пересчёт на боевой: основная таблица 867 МБ → около 380–430 МБ (с `seo_keywords` — около 270 МБ); страниц на запрос по стране — примерно в 9 раз меньше (у Испании около 1200 вместо 10 581); одна укладка без выноса текстов даёт около 3200 страниц.

**Блокировка.** `CLUSTER` держит таблицу закрытой для чтения и записи всё время перезаписи и пересборки индексов: раздел «Мир», карточки, поиск по миру и сборка sitemap в это время ждут. На ноутбуке это 19–28 с. На боевом ожидаю 3–6 минут: индекс поиска там втрое больше (326 МБ против 100 МБ в копии), процессор медленнее, диск занят. Если индекс поиска удалить до укладки и собрать после без блокировки (`CREATE INDEX CONCURRENTLY`), закрытое окно сократится примерно до 1–2 минут, но поиск по миру на время сборки будет медленным. **На боевом и на стенде время не измерялось** — перед окном нужна репетиция на тестовом сервере с копией таблицы.

**Порядок, если владелец решит делать.**
1. Сначала выпустить узкое чтение и блок «Ещё в разделе» и повторить замер: возможно, таблица перестанет быть главным читателем диска.
2. Укладка по стране без изменения кода: `CLUSTER` и `fillfactor = 90`, чтобы обновления оставались на своей странице и порядок не расползался. Одно окно 3–6 минут. Выигрыш — в 3–5 раз меньше страниц на запросы по стране (каталог страны, блок «Ещё в разделе»).
3. Отдельная таблица текстов: миграция с копированием, код (около 36 мест чтения описаний и SEO-текстов: карточка, SSR, сниппеты), затем удаление колонок и вторая укладка. Два выпуска и второе окно.
4. `methodology` при 179 разных значениях можно хранить справочником по набору данных; это отдельное упрощение.

**Не установлено.** Сколько чтения с диска останется за `world_indicators` после выпуска уже сделанных правок; точное время блокировки на боевом диске; сколько мест кода придётся изменить на самом деле (36 — счёт обращений к полям поиском по тексту).

### База больше памяти, поиск на холодном диске — 2026-11-13

Наблюдение 13.11.2026, 09:00–09:30 UTC, боевой `4f8fa681`, только чтение; датировано, не вечное. База PostgreSQL 12 ГБ (`behavior_events` 3,6 ГБ,
`region_monthly_data` 2,0 ГБ, `world_data_points` 1,9 ГБ, `world_indicators` 1,6 ГБ), память хоста 7,9 ГБ, страничный кэш 3,8 ГБ, swap занят на 1,2 ГБ,
`shared_buffers` 896 МБ, лимит контейнера postgres 3 ГБ. Диск `sda` (QEMU HARDDISK): 150 чтений в секунду, 7 мс на чтение, занятость 39%.
PSI io full: 21% за 5 минут. Доля попаданий в кэш PostgreSQL с начала статистики: 89,4%. Backend: 2,0–2,1 из 2,25 ГБ.

Следствие: публичный запрос, читающий много холодных страниц, идёт десятки секунд и упирается в `db_statement_timeout_ms` = 30 000. Так вёл себя
поиск после заливки региональных цен (13,1 млн строк): [search.md](search.md#2026-11-13--боевая-база-проверки-есть-данные-без-чтения-всех-строк-ветка-fixsearch-region-exists-не-выпущено).
Правка поиска сокращает число чтений, но не причину. Не сделано: сводные таблицы наличия фактов, память и диск базы, перенос или сокращение
`behavior_events`, проверка скорости поиска в Пульсе. Мой проверочный `count(distinct region_id)` по `region_monthly_data` шёл 95 с и был отменён:
подсчёты по всей таблице на боевом не запускать.
