# Рабочий процесс — Forecast Economy

**Last updated:** 2026-10-04 (тестовый сервер через Cloudflare, порядок выкладки и пачка 04.10; ранее 2026-09-30: свежая доставка и изолированный restore, история 27.09 сохранена). Локальная `main` и датированный снимок серверной конфигурации разобраны отдельно: [реестр кода](code-review.md), [архитектура и окружение](architecture.md), [наблюдения и ограничения](code-review-findings.md). Кодовый разбор не заменяет приёмку выпуска на production.

**Previous:** 2026-09-20 (approved-SHA gate, миграции и архив ассетов). Ранее 2026-09-03 (post-deploy watch 15 мин + runbook «хост в свопе»). Ранее 2026-07-06 (CTO-аудит, Волна 5: прод-IP актуализирован — 201.51.11.170 (переезд 2026-07-03, старый 5.129.204.194 упразднён); прод-деплой переведён на `scripts/deploy.sh` — preflight-бэкап, ff-only guard, версионированные образы с автооткатом, расширенный smoke (SSR asset-hash / data-endpoint / OG), Caddy reload после smoke; ETL идёт двумя прогонами (06:00 и 20:00 МСК) + late-Minfin 15:00; smoke-набор дополнен readiness `/health/ready`; E2E-runner `scripts/e2e/smoke.mjs` реализован (Playwright, 5 сценариев + YandexBot SSR-suite) и включён в CI. Ранее 2026-05-22: добавлен ручной ETL recipe, `_catch_up_empty_indicators` + `redis-cli FLUSHDB`.)
**Part of:** [`../AGENTS.md`](../AGENTS.md), [`../CONTEXT.md`](../CONTEXT.md).
**See also:** [`enterprise_resilience.md`](enterprise_resilience.md) (чеклист канарейки), [`data-contracts.md`](data-contracts.md) (сквозные контракты данных), [`agent-recipes.md`](agent-recipes.md) (рецепты индикаторов), [`knowledge-workflow.md`](knowledge-workflow.md) (сопровождение знаний), [`adr/`](adr/) (архитектурные решения).

## Модель работы

Раньше работа шла по **фазам** (план `forecast_economy_v2`, фазы 0–4). Все фазы закрыты к концу апреля 2026. Сейчас работа идёт по двум потокам:

- **Архитектурные кандидаты** — большие deepening-рефакторы (`refactor/...` ветки): calculation_engine pure ops + DerivedSpec, BaseParser template-method, forecast strategies registry, indicator metadata в БД, SEO single-source, IndicatorDetail декомпозиция и т.п. Фиксируются в `docs/adr/` (нумерованные ADR).
- **Точечные правки по обратной связи** — конкретные баги/правки от Никиты или собственного аудита (CPI квартальная вкладка, GDP nominal/real split, weekly forecast, calendar rolling 12-мес и т.п.). Идут в `feat/...` или `fix/...` ветках, мерджатся в `main` через `--no-ff`.

Любая правка должна проходить регламент ниже. Ничего «полу-готового» в `main`.

## Аналитические окна и event replay — локальное уточнение 30.09

После `main 83c4555` ordinary rollup остаётся в отдельном analytics pool,
окна по3МСК-дня; temp staging и historical visitor SQL предотвращают разрыв
логической сессии без материализации60дней в Python. CPU/readwork SQL и
temporary disk не ограничиваются размером Python batch; прежние timeout,
pool и low-memory CH settings не повышаются этим пакетом.
Индексы и ANALYZE применяются только к private temp visitor/history stages:
это устраняет плохие cardinality estimates на новой БД без global tuning.

Event cursor/heartbeat перешли наv2. Первый запуск повторно читает сохранённые
PG event rows, до80k каждой таблицы на job; оставшийся prefix продолжится
следующим job. Проверять `/api/v1/admin/bi/slices/meta::sync_progress`, а не
старый Redis heartbeat. Прежний v2 age остаётся last successful copy, даже если
последний записанный progress уже partial/deferred. Сбой до его записи может
оставить прежний capture; сверять также age и журнал job. `available` — enabled без pending
rebuild, не доказательство health/полноты.
Live sequence reconfiguration не поддерживается: CACHE1 после CACHE>1 при
старых живых backends не доказывает отсутствие reserved lower ids. Нужны
закрытие старых соединений и controlled catch-up, это отдельный release gate.
SHARE NOWAIT не ждёт открытого writer; после успешного
lock новые INSERT могут кратко ждать SQL metadata/max phase. Incompatible
sequence/isolation останавливает copy без продвижения cursor.

`resync()` — отдельная разрушительная для **производной CH-копии** операция:
reset/drop/rebuild и последовательная полная event загрузка, replacing cutoff
по-прежнему3650суток. Это не импорт PostgreSQL и не обычный15min job.
Сбой оставляет CH incomplete без нового успешного heartbeat; повтор требует
того же контролируемого maintenance сценария. Не запускать автоматически
ради F05b: resync не обеспечивает передачу будущих session deletes (с
2026-10-04 их передаёт журнал `server_session_changes`; после выпуска F05b один
resync по maintenance-сценарию очистит ранее накопленные призраки).
Pending intent записывается до cursor reset и первого DROP; обычный job и
срезы блокируются до полного operator repair. После успеха marker снимается.
Это действует при сохранном state Redis, не обеспечивает cross-store atomicity
при потере state/AOF и не заменяет полноценный recovery протокол.
Перед manual resync исключить одновременно работающий incremental sync,
включая уже начатый: pending marker не заменяет межпроцессный fencing F07.

Изолированные проверки принимают explicit loopback PostgreSQL `fe_f01_*`,
необычный порт и unique schema; RedisDB14/15 и CH также только на owned
контейнерах. Cred-файл временный0600, после gates удаляется вместе с ними.
[Приёмка](code-review/analytics-boundaries-acceptance-2026-09-30.md) различает
synthetic ресурсы и общий сервер4vCPU. Production release отдельно; до F05b
CH session-метрики не имеют гарантии равенства PG после backfill/carry.

## Git и окружения

- **GitHub (`git push origin main`)** — основной способ фиксировать прогресс; коммиты должны быть **согласованы** с тем, что реально сделано.
- **Прод-сервер** (`201.51.11.170`, `/opt/rosstat`; DNS `forecasteconomy.com`) — **не деплоить автоматически** и **не без явного запроса**. Разработка и проверка — локально (Docker Compose) и через CI; выкладка на сервер — отдельным шагом по команде.
- **SSH на прод — только по ключу** (с 2026-08-27): `ssh fe-prod` (алиас в `~/.ssh/config`) или явно `ssh -i ~/.ssh/id_ed25519_fe_prod root@201.51.11.170`. Парольный вход отключён (`/etc/ssh/sshd_config.d/00-hardening.conf`: `PermitRootLogin prohibit-password`, `PasswordAuthentication no`; бэкап старого конфига — `/etc/ssh/sshd_config.bak-keyauth`). Ключ только у владельца; потеря ключа = восстановление через панель провайдера (VNC/rescue).
- **Перед каждым прод-деплоем** — `scripts/deploy.sh` запускает `scripts/pg-backup.sh` и прекращает деплой при ненулевом коде бэкапа. Скрипт создаёт полный `pg_dump -Fc` (`.dump`) и отдельный `.identity.sql.gz`; локальные файлы старше `KEEP_DAYS` (по умолчанию 14) удаляет. Offsite-копирование зависит от `OFFSITE_S3_BUCKET` и наличия `aws`; если bucket задан, а `aws` отсутствует, скрипт предупреждает, но завершает работу успешно. Поэтому зелёный preflight доказывает создание локального dump, но сам по себе не доказывает offsite-копию или возможность восстановления. См. [`enterprise_resilience.md`](enterprise_resilience.md#восстановление-и-наблюдаемость).
- **Персистентность данных пользователей (ADR-0007).** БД хранится в docker volume `postgres_data` — переживает `docker compose up -d --build`. `scripts/pg-backup.sh` создаёт полный custom dump и отдельный data-only SQL девяти identity-таблиц (`users`, `email_credentials`, `oauth_identities`, `consents`, `auth_audit` и, с круга 11 от 09.10.2026, четыре таблицы кабинета `user_saved_items`, `user_watches`, `user_exports`, `user_preferences`; `pg_dump -t` с ещё не созданной таблицей не падает, пока найдена хотя бы одна из перечисленных, поэтому скрипт безопасен и до выкладки миграции; `user_signups` в эту копию не входит и сохраняется только полным dump). Наличие файлов не заменяет пробное восстановление и проверку связности записей. Пример **проверочного** восстановления на отдельном Docker-томе, без публикации порта и без обращения к рабочему compose-сервису. **30.09 этот подход выполнен** для свежих full/identity файлов: [протокол](code-review/backup-acceptance-2026-09-30.md). Переносимый пример для следующей проверки на хосте с доступным Docker:

  ```bash
  drill_id="fe_restore_drill_$(date -u +%Y%m%dT%H%M%SZ)"
  docker volume create --label fe.acceptance.owner="$drill_id" "$drill_id"
  docker run -d --name "$drill_id" --network none --memory 1g --cpus 1 \
    --label fe.acceptance.owner="$drill_id" \
    -e POSTGRES_HOST_AUTH_METHOD=trust -e POSTGRES_USER=rustats \
    -e POSTGRES_DB=rustats -v "$drill_id:/var/lib/postgresql/data" \
    postgres:16-alpine
  until docker exec "$drill_id" pg_isready -U rustats; do sleep 1; done
  docker exec -i "$drill_id" pg_restore -U rustats -d rustats \
    --exit-on-error --no-owner --no-privileges < /absolute/path/to/backup.dump
  docker exec "$drill_id" psql -U rustats -d rustats \
    -c 'SELECT count(*) FROM users'
  ```

  Сверить также числа точек, Alembic-head и выборку identity-связей с контрольными значениями на момент бэкапа. Для проверки `.identity.sql.gz` нужна **другая** чистая БД с совместимой схемой; не импортировать data-only SQL поверх полного dump без плана дедупликации. После записи результата проверить у **обоих** ресурсов label `fe.acceptance.owner`, точное имя, отсутствие host ports и единственный собственный PostgreSQL-том; затем удалить только созданные ресурсы. `--no-owner --no-privileges` проверяет восстановление схемы/данных без исходных owner/ACL, их replay требует отдельного сценария. **30.09** full dump восстановился за 154,885 с, отдельный identity SQL — успешно, размеры/хэши обоих совпали с сервером, сирот identity нет. Это время `pg_restore`, а не целевой RTO/RPO или время полного failover.

### Доставка существующего backup на Mac

`~/Library/LaunchAgents/com.forecasteconomy.backup-pull.plist` запускает `~/bin/fe-backup-pull.sh` в **08:15 МСК**; каталог `~/Backups/forecasteconomy`, основной журнал `~/Backups/forecasteconomy/pull.log` (launchd stdout/stderr рядом). Скрипт выбирает завершённый daily dump (не `.partial` и не pre-deploy), скачивает full/identity и сверяет SHA-256/размеры, custom-dump TOC (если доступен pg_restore/Docker) и gzip до отметки `.verified`; уже проверенную пару пропускает. Эти файлы находятся вне Git и не являются dev DATABASE_URL.

**Проверка 30.09:** после SSH errors 27–30.09 исходная версия скрипта сохранена рядом (`.before-20260930T133007Z`), SSH multiplexing отключён через `ControlMaster=no` / `ControlPath=none`, keepalive ограничен 15 с ×2. Исторический Broken pipe/Connection closed не устанавливает единственную причину: независимое SSH-соединение в момент проверки работало. Ручной pull 16:30–16:32 МСК и повтор 16:43 успешно подтверждены; следующий плановый запуск ещё не наблюдался. Поздняя проверка plist/launchctl подтвердила08:15/RunAtLoad и регистрацию; last launchd exit1 исторический, manual success учитывается отдельно, ждать следующего расписания для описания механизма не требуется. Полный restore и identity restore описаны в [датированном протоколе](code-review/backup-acceptance-2026-09-30.md). Production jobs при этой проверке не запускались.

## Локальная разработка

Текущие характеристики VPS с 4 vCPU, локального Mac/Docker VM, лимиты контейнеров, порты и обнаруженные различия — [архитектура: реальное окружение](architecture.md#реальное-окружение-сервер-с-4-vcpu-и-локальная-разработка). Датированные машинные свидетельства — [runtime-inventory.json](runtime-inventory.json). Локальная main и работающий Docker image — разные версии до пересборки.

### Как настройки попадают в процесс

1. Корневой `.env` читает **Compose для подстановки** `${...}`. В контейнер попадают только перечисленные в `docker-compose.yml::environment` ключи. `env_file` для backend не подключён. Просто добавить произвольный `RUSTATS_*` в корневой `.env` недостаточно: нужен явный environment mapping/override.
   **Прод, с 2026-10-08:** в `/opt/rosstat` есть не входящий в Git `docker-compose.override.yml`. Он монтирует в scheduler файлы-секреты из `/etc/rosstat-secrets/` (сейчас только OAuth Google Search Console, см. [GSC](analytics_api_inventory/google_search_console.md)). `deploy.sh` вызывает обычный `docker compose` и подхватывает его; при переносе сервера файл и каталог нужно перенести вручную.
2. При прямом `uvicorn`/Python `Settings` читает переменные процесса и `.env` **текущего рабочего каталога** (`config.py::Settings.model_config`). Из `backend/` это `backend/.env`, а не автоматически корневой файл. Default Settings для одного процесса отличается от Compose (например, pool 10+15 против web 8+7).
3. `VITE_*` — параметры Vite build/dev. Смена runtime env уже собранного nginx-контейнера не меняет JS. Locale build arg в Compose берётся из `RUSTATS_APEX_LOCALE_EN`; SSR и browser должны собираться для одного режима.
4. Caddy работает на хосте. Корневой `.env` не является `EnvironmentFile` systemd автоматически.

### Проверенная активация и изолированный startup, 30.09

[Ops-протокол](code-review/ops-mechanism-acceptance-2026-09-30.md) / [JSON](code-review/ops-mechanism-acceptance-2026-09-30.json)
перечисляют160 Settings-полей, их readers/defaults/type и environment mapping каждого service.
При прямом Python приоритет initializer→process env→cwd dotenv→default; Settings global
создаётся при импорте. Для environment changes нужен restart, для Compose — recreate,
для Vite client/build args — rebuild. Типы не гарантируют domain bounds: отрицательный
pool-size принимается Settings, затем зависит от consumer/library validation.

`PUBLIC_HOST` не читает нынешний Caddy. В root `.env` этого Compose также не передаются
metrics token, scheduler cron hour/minute, forecast steps, world forecast max-age/cache-bump/
priority и webmaster recrawl flag. Требуется явный service mapping/override; существующий
empty metrics token закрывает endpoint403. Banxico aliases читаются direct os.environ,
а не неизвестным Settings dotenv-field. `VITE_SENTRY_DSN` source-reader существует,
но в нынешние Docker build args не включён. `debug=false` даёт warn diagnostics;
fake-provider при `!debug` — настоящий hard startup fail.

Изолированная проверка выполнила current backend web entrypoint на пустой собственной БД:
34 migrations,947 indicators,961494 region points,438 calendar events, users0, readiness200.
Scheduler/jobs выключены; internal network блокировала внешнюю сеть, CBR calendar DNS
failed и startup продолжился. Это проверка запуска/seeds, а не полноты экономических фактов.
Current code исполнялся поверх существующего local dependency image, без online build.
Отдельная restored БД прошла owners/ACL + API/email auth/CSRF/state-session + current nginx
SSR/assets; client JS был прежнего local image. Все6 своих containers/volume/network
удалены после ownership checks,15 других container IDs сохранены.

На сервере source logrotate и effective host config отличаются: main rotate7/nocompress/
rename+USR1, host rotate14/compress/copytruncate. Выпуск/замена host-config — отдельное
разрешённое действие; `deploy.sh` не устанавливает fail2ban/logrotate install bundle сам.
Host `tor-http-bridge.service` вне Git обеспечивает gateway8888→Tor9050. Hardcoded Basic
credential и логирование headers — текущая известная проблема; не копировать private
source/журнал с credentials в Git. Санитизированный механизм и исходныйSHA — в ops JSON.

### Профиль A: Compose, SSR и интеграция

Команды выполняются из корня проекта. Существующий `.env` сохраняется:

```bash
test -f .env || cp .env.example .env
```

Перед стартом проверить локальные значения. Шаблон содержит production origin и включённые locale-флаги; он не является готовым изолированным dev-профилем. Для обычной разработки установить в локальном `.env`:

```dotenv
RUSTATS_AUTH_PUBLIC_BASE_URL=http://localhost:3000
RUSTATS_AUTH_COOKIE_SECURE=false
RUSTATS_APEX_LOCALE_EN=false
RUSTATS_GEO_LOCALE_REDIRECT_ENABLED=false
RUSTATS_INDEXNOW_ENABLED=false
RUSTATS_ANALYTICS_LIVE_WRITES_ENABLED=false
RUSTATS_ANALYTICS_SCHEDULER_ENABLED=false
RUSTATS_TELEGRAM_DIGEST_ENABLED=false
RUSTATS_TELEGRAM_POLLER_ENABLED=false
RUSTATS_TELEGRAM_REALTIME_ALERTS_ENABLED=false
RUSTATS_PULSE_ENABLED=false
```

Production-токены Telegram/OAuth/Метрики/IndexNow/LLM в dev не копировать. Некоторые интерактивные события (например, login) имеют отдельные пути уведомлений; выключенный digest не является общим выключателем отправки. Для воспроизведения server state-изоляции задать `RUSTATS_STATE_REDIS_URL` на **`redis-state:6379/0`** с локальным Redis-паролем; Compose default — `redis:6379/1`. Не менять адрес поверх работающей сессии незаметно: это другое хранилище. Пароль внутри URL требует URL-encoding.

Первый старт nginx требует доступных bind-каталогов `/var/log/rosstat-nginx` (запись uid101) и архива ассетов (default `/var/lib/rosstat/frontend-assets`, можно переопределить `FRONTEND_ASSET_ARCHIVE` локальным абсолютным путём). Linux-рецепт создания log-каталога есть в CI; на Docker Desktop каталог должен быть доступен для file sharing. `output/` монтируется read-only в `/app/data`; named volumes сохраняют Postgres, Redis, GeoIP, OG, sitemap и ClickHouse.

```bash
docker compose build backend frontend
docker compose up -d postgres redis redis-state backend frontend clickhouse
docker compose ps
curl --fail http://127.0.0.1:8000/api/v1/health/ready
curl --fail -A 'YandexBot/3.0' http://127.0.0.1:3000/russia/indicator/cpi
```

Эта команда `up` **не запускает scheduler впервые**, но уже работающий scheduler не останавливает. При обычной разработке проверить `docker compose ps scheduler` и остановить его явно командой `docker compose stop scheduler`, если он остался от прошлой сессии. `RUSTATS_SCHEDULER_ENABLED=false` в `.env` недостаточно: Compose задаёт для отдельного scheduler литерал `true`.

Web-role `backend/entrypoint.sh` выполняет Alembic, федеральный/региональный/calendar seed и запускает 3 Uvicorn workers. Seed создаёт метаданные; полноценная история всех рядов из этого не следует. Ошибка первого пустого регионального seed фатальна, при уже наполненной региональной БД логируется. Порт **3000** проверяет nginx→SSR и собранные assets. Backend исходники не bind-mounted: после их правки повторить совместную сборку и `up`; Vite HMR не обновляет контейнерный Python.

### Региональный startup после пакета F03, 30.09

`seed_regional.py` выполняет содержательную COPY/staging сверку при каждом
web startup. Временные таблицы, чанки 10 000 и conditional merge сохраняют
память ограниченной и не перезаписывают всю БД; неизменный запуск всё равно
читает артефакт и сравнивает его с БД. SQL budget сидера — `SET LOCAL
statement_timeout=120000` (на statement), advisory xact lock сериализует
SQL-запись сидера и ЕМИСС (HTTP fetch предшествует lock), после транзакции возвращается обычный timeout. Metadata и обе частоты
commit вместе; месячные конфликты принадлежат live-обновлению ЕМИСС.
Старый startup fallback при уже заполненной годовой таблице сохраняется.

После выпуска проверить startup duration/temp disk/SQL waits на общем
сервере 4 vCPU, региональные API/SSR/OG и очередную sitemap generation.
Локальный constrained PostgreSQL замер приведён в [приёмке](code-review/regional-publication-acceptance-2026-09-30.md);
он не заменяет измерение совместного ETL/BI/SSR workload production.

### Профиль B: быстрый frontend с HMR и локальным API

Нужны Node22, `npm ci` во `frontend/` и работающий локальный backend. Запуск из `frontend/`:

```bash
npm ci
VITE_DEV_API_PROXY=http://127.0.0.1:8000 npm run dev -- --host 127.0.0.1
```

Тот же `VITE_DEV_API_PROXY` можно хранить в игнорируемом `frontend/.env.local`. Без него Vite берёт `VITE_PUBLIC_BASE_URL`, а затем default `https://forecasteconomy.com`. Proxy `/api` **не фильтрует HTTP methods**: утверждение старого комментария «только GET» было неверным. Поэтому локальный UI с default proxy может обращаться к серверным auth/analytics API. Для проверки своего backend указывать localhost явно.

Порт **5173** показывает CSR/HMR. Он не воспроизводит nginx SSR/OG routing, Caddy, host fail2ban, production Secure cookies или серверную производительность. Для UI проверять desktop/mobile, затем отдельно тот же сценарий через **3000**, SSR HTML и API. RU/EN preview через `?preview_locale=` помогает проверить перевод, но не заменяет dual-host canonical/hreflang gate.

### Профиль C: Python вне Docker

Использовать Python3.12 и `backend/.venv` с `requirements-dev.txt`; запускать из `backend/`. Задать явные process env или отдельный локальный `backend/.env`: `RUSTATS_DATABASE_URL` на localhost:**5434**, `RUSTATS_REDIS_URL` на localhost:**6380** с локальными паролями, `RUSTATS_SCHEDULER_ENABLED=false` и отключённые внешние отправки. Default Settings `localhost:5432`/`6379` не соответствует портам Compose. Выделенный `redis-state` не публикует host port; для прямого Python нужно отдельно продуманное подключение либо dev DB1 cache Redis с явно меньшей изоляцией.

```bash
cd backend
PYTHONPATH=. .venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```

Порт 8001 позволяет не конфликтовать с Compose backend:8000. Для такого процесса Vite proxy направить на 8001. `uvicorn` сам не выполняет shell entrypoint: миграции и нужные seed выполняются отдельно **в выбранной dev-БД**. Не подменять этим запуском проверку production startup.

### Профиль D: ETL и фоновые задания

Для интеграционной проверки расписания после настройки локальной БД и внешних отправок:

```bash
docker compose up -d scheduler
docker compose exec -T scheduler curl --fail http://127.0.0.1:8000/api/v1/health/ready
docker compose logs --tail=100 scheduler
```

Scheduler — тот же backend image, один worker, без host port; он пропускает Alembic/seed, зависит от healthy web. Запускает startup catch-up и расписание, поэтому может обращаться к официальным источникам и менять dev-данные сразу после старта. Это профиль проверки ETL, а не условие frontend-разработки. После проверки можно остановить только scheduler, сохранив тома. `docker compose down -v` уничтожает named volumes и для обычной разработки не требуется.

### Синхронизация с продом

`scripts/sync-local-from-prod.py` — исторический инструмент для **частичного RU gap-fill** через публичный API: фиксированный limit10000, без pagination полного каталога/всех историй, без world/regions/identity. Существующие точки сохраняются (`ON CONFLICT DO NOTHING`), ревизии их значений не переносятся. Публичная API-политика глубины/доступа ограничивает результат; это не эквивалент `pg_dump`.

Файл находится в корневом `scripts/`, которого нет в backend Docker build context. После проверки, что контейнер подключён именно к локальной БД:

```bash
docker compose exec -T backend python - < scripts/sync-local-from-prod.py
```

Команда не меняет прод через SQL, но пишет в **настроенную target-БД** и делает параллельные GET к продакшену. Название `local` само по себе не проверяет DATABASE_URL. Forecast/derived/cache после этого автоматически не актуализируются.

### Полный пересчёт derived

После изменения `derived_ops.py`/`DERIVED_SPECS` или ручной коррекции source в **dev-БД**:

```bash
docker compose exec -T backend python - < scripts/rebuild-all-derived.py
```

Корневой скрипт также отсутствует по старому адресу `/app/scripts/rebuild-all-derived.py`. Он вызывает каждый `_execute`, коммитит изменения и инвалидирует изменившиеся индикаторы. Повтор без изменений должен дать нули; это проверяется выводом. Per-spec исключения логируются, но `main` возвращает 0: успешный exit не гарантирует успешность каждого derived. Orphan-derived точки не удаляются автоматически, retrain прогнозов этим скриптом не выполняется.

### Ручной прогон мировых прогнозов

Инкрементальный job listed M/Q/A `world_indicators` (отпечаток в `model_params`, приоритет стран). Полный прогон на холодную — часы; повтор без `--force` пропускает неизменённые ряды.

```bash
docker compose exec -T backend python -u /app/scripts/rebuild-world-forecasts.py --dry-run
docker compose exec -T backend python -u /app/scripts/rebuild-world-forecasts.py --country austria --limit 30
docker compose exec -T backend python -u /app/scripts/rebuild-world-forecasts.py --force
```

### Ручной прогон ETL одного индикатора

Для дебага парсера или ручного pull данных под конкретный `code` (например после правки `model_config_json.element_id` в CBR DataService — см. trap в docstring `cbr_dataservice_parser.py`):

```bash
docker compose exec backend python -c \
  "import asyncio; from app.tasks.scheduler import run_etl_for_indicator; \
   asyncio.run(run_etl_for_indicator('key-rate'))"
```

Заменить `'key-rate'` на любой `code`. Логи в JSON через `JsonFormatter` (`docker compose logs backend | grep -i <code>`). Для полной перезаливки истории — установить `model_config_json.full_refresh = true` через SQL (`UPDATE indicators SET model_config_json = jsonb_set(...)`) и прогнать; не все парсеры поддерживают `full_refresh` (CBR DataService/BOP — да; для остальных проще пересоздать через `seed_data.py` + локальная очистка `data_points`).

## Проверки перед коммитом

Локально одной командой (основные unit/lint/build проверки; дополнительные CI gates ниже):

```bash
./scripts/check-all.sh
```

Гонит `pytest backend/` (если есть `backend/.venv/bin/pytest`, использует его), `npm test`, `npm run lint`, `npm run build` во `frontend/`, затем регенерирует `docs/repo-inventory.md` и проверяет карту индикаторов, счётчики документации, page-meta и публичный язык. Он может изменить файл инвентаря: после прогона просмотреть `git diff`. Зелёное `check-all.sh` — обязательное предусловие для `git push`, но **не** заменяет отдельные CI jobs `migrations` (чистая БД/дрейф Alembic) и `e2e` (Docker Compose + Playwright), определённые в `.github/workflows/ci.yml`.

**Документирование рельефа проекта.** После осмысленных изменений модулей и связей обновить generated-карту через `python scripts/build-project-terrain.py --refresh`, затем проверить `python scripts/build-project-terrain.py --check` и посмотреть diff [`project-terrain.md`](project-terrain.md) / [`project-terrain.json`](project-terrain.json). Генератор читает внешнюю семантическую карту и код; это навигационный срез, не доказательство поведения продакшена. Для фактических полей и статусов сверять [`data-contracts.md`](data-contracts.md) с кодом/тестами.

**Политика зависимостей (Э-1/Э-8, 2026-07-06).** Backend: прямые пины `==` в `backend/requirements.txt`, транзитивные лочатся `backend/constraints.txt` (`pip freeze` из venv Python 3.12; Dockerfile ставит `-r requirements.txt -c constraints.txt`) — после правки requirements регенерировать constraints. Frontend: диапазоны caret в `package.json` осознанны; детерминизм держится на `package-lock.json` + `npm ci` (Dockerfile и CI используют только `npm ci`; `npm install` руками не запускать, кроме намеренного обновления lock). Node — 22 (`frontend/.nvmrc`, `engines` в package.json).

Если Docker/сеть в среде агента недоступны — pytest/vitest гнать в venv-эквиваленте, а Docker-смок зафиксировать как пропущенный с пометкой «Docker daemon недоступен в окружении агента».

## Браузерная проверка после правок UI

Любое изменение страниц/компонентов фронтенда **не считается завершённым**, пока агент не открыл маршрут в браузере, не сделал snapshot и не убедился визуально + не прочитал console.

**Две техники проверки:**

### `cursor-ide-browser` (in-session)

Для итеративной разработки — `browser_navigate` → `browser_snapshot` → `browser_console_messages`. На любые правки UI: открыть локальный маршрут (например, `http://localhost:3000/indicator/cpi`), снять snapshot, проверить, что console чистая (только Vite/React/CursorBrowser служебные сообщения; ошибок приложения нет). При изменениях, которые меняют шапку/SEO/layout — обязательно проверить и SSR через user-agent `YandexBot/3.0` или `Googlebot/2.1`.

### Headless проверки через curl + SSR user-agent

Для регрессионных smoke-чеков после прод-деплоя — `scripts/seo-audit.py` проходит по списку ключевых indicator-страниц и проверяет, что SSR через `User-Agent: YandexBot/3.0` возвращает осмысленные `<title>`, `<meta description>`, `og:*`, JSON-LD. Запуск:

```bash
python scripts/seo-audit.py --target=https://forecasteconomy.com
```

Для in-session браузер-чеков используется техника выше (`cursor-ide-browser`). Полноценный E2E-runner реализован (2026-07-06): `node scripts/e2e/smoke.mjs [BASE_URL]` — Playwright-хром, 5 браузерных сценариев (`/indicator/cpi`, `/compare`, `/regions`, `/embed/chart/cpi`, `/admin/bi`) + SSR-suite под YandexBot (canonical/JSON-LD/title). Гоняется в CI job `e2e` на живом compose-стеке.

Если dev-сервер недоступен в среде — явно записать что проверено альтернативно (только unit-тесты / только snapshot-тесты / только curl-сверка SSR).

## Тестовый сервер (демо-стенд за Cloudflare)

**Датировано 2026-10-04.** Отдельный VPS для репетиции выпуска и показа владельцу. Это **не боевой** сервер:
`scripts/test-server/deploy.sh` отказывается работать с адресом прода. Ничего, что требует боевых токенов, здесь не запускается.

| | Тестовый | Боевой |
|---|---|---|
| Хост | `176.57.220.170` (Timeweb, Санкт-Петербург), Ubuntu 26.04, каталог `/opt/rosstat` | `201.51.11.170` |
| Ресурсы | 2 vCPU, 3,9 ГБ RAM + 4 ГБ swap, диск 48 ГБ | 4 vCPU, 8 ГБ RAM, 77 ГБ |
| Доступ | SSH **по ключу** `~/.ssh/id_ed25519_fe_demo` (установлен давно; пароль не используется и нигде не хранится) | ключ `id_ed25519_fe_prod`, алиас `fe-prod` |
| Наружу | `cloudflared` quick tunnel (systemd `fe-demo-tunnel`) → `127.0.0.1:80`. Адрес `*.trycloudflare.com` **меняется при каждом старте туннеля**; текущий — в `/var/log/fe-demo-tunnel.log` после последней строки `=== start` (файл `/root/fe-demo-tunnel.url` с 08.10.2026 ненадёжен, [ниже](#доступ-при-блокировке-vpn-и-актуальный-адрес-туннеля-наблюдение-08102026)) | Caddy, домены |
| Данные | product-only восстановление из проверенного бэкапа (без пользователей и аналитики), см. ниже | живые |
| Исходящие действия | выключены: Telegram (дайджест, алерты, опрос), Pulse, IndexNow, Вебмастер, Метрика/аналитический планировщик, ClickHouse, Eurostat-ингест, мировые прогнозы | включены |
| Память (лимиты cgroup) | PostgreSQL 1,1 ГБ, backend 900 МБ (1 воркер), scheduler 700 МБ, frontend 256 МБ, Redis 448 МБ | 3 ГБ / 2,25 ГБ (3 воркера) / 1 ГБ / … |

Файлы рядом с `docker-compose.yml` на сервере, не входящие в Git: `docker-compose.override.yml` (эталон —
`scripts/test-server/docker-compose.override.yml`: урезанные лимиты, порт `127.0.0.1:80`, **`build.network: host`** — без него
`pip`/`npm` из docker-сети таймаутят; с 05.10 ещё bind-mount `/root/nginx-test.conf` в frontend и `RUSTATS_API_RATE_LIMIT`/`RUSTATS_EMBED_RATE_LIMIT` = `6000` в backend)
и `.env` (добавки лимитов — `scripts/test-server/env.additions`; пароли и токены там свои). **`deploy.sh` override на сервер не копирует:** изменение эталона в репозитории
действует только после ручного копирования файла на сервер и `docker compose up -d`. Применён ли расширенный override на стенде, из репозитория не видно (на сервер при сверке 06.10 не заходили).

### Выкладка кода

```bash
scripts/test-server/deploy.sh            # текущий HEAD; REF и --no-build — по необходимости
```

Код едет без push: `git bundle` поверх SHA, который уже стоит на сервере (если он не предок цели — полный bundle), затем
`git checkout --detach <SHA>`, **генерация `/root/nginx-test.conf`** (ниже), `docker compose build backend frontend`, `docker compose up -d backend scheduler frontend`, ожидание
`/api/v1/health/ready`, **сброс SSR-кэша** и вывод адреса туннеля. Образ один на `backend` и `scheduler`. Обычный прогон — около минуты, со сборкой — 3–5.

<a id="test-server-limits"></a>

### Лимиты запросов стенда и конфиг nginx (05.10.2026)

Все проверяющие (владелец, критики, агенты) приходят на стенд с одного внешнего адреса Cloudflare-туннеля. Боевые лимиты (`rate=5r/s`, `limit_conn perip 8`, API 120 запросов в минуту) отдавали им «429», поэтому стенд работает со своими значениями; **боевой `frontend/nginx.conf` и боевое окружение не меняются**.

| Что | Как устроено на стенде |
|---|---|
| nginx | шаг 1b `deploy.sh`: `sed` над `frontend/nginx.conf` на сервере пишет `/root/nginx-test.conf`: каждое `rate=Nr/s` → `N00r/s` (×100), `burst=N` → `N0` (×10), `limit_conn perip N` → `N000` (8 → 8000); `ogconn` (картинки OG) не трогается, он защищает память. Файл **генерируется при каждой выкладке** (`grep -c limit_req_zone` в выводе проверяет, что зоны на месте) и монтируется в контейнер `frontend` как `/etc/nginx/conf.d/default.conf` через override |
| API | `RUSTATS_API_RATE_LIMIT=6000`, `RUSTATS_EMBED_RATE_LIMIT=6000` в `backend` (читаются в `app/main.py::RateLimitMiddleware` при старте; боевые умолчания 120 и 600) |
| SSR-кэш | после `up -d` `deploy.sh` сбрасывает ключи `fe:*:ssr:*` в Redis (как `scripts/deploy.sh` на проде): подпись ключа зависит только от хэша ассетов фронта, и правка рендера на backend без сброса отдавала бы старый HTML до 6 часов |

Ограничения (выведены из кода, на стенде не проверены): при `--no-build` и неизменном compose-конфиге `up -d frontend` контейнер не пересоздаёт, и nginx не перечитает свежий `/root/nginx-test.conf`: после смены лимитов нужен `docker compose restart frontend` либо полный прогон со сборкой. Остальное в конфиге стенд повторяет боевое (фирменные `429/50x`, `/forecasts`, `/search` → 301).

### Данные: product-only восстановление

Полный дамп с пользователями на публичный стенд не заливаем. Из последнего **проверенного** бэкапа (`~/Backups/forecasteconomy/*.verified`)
строится список восстановления без данных личных и аналитических таблиц (`users`, `email_credentials`, `oauth_identities`,
`identity_links`, `auth_audit`, `consents`, `behavior_*`, `frontend_events`, `server_sessions`, `telegram_outbox`, `raw_metrika_*`, `metrika_*`,
`gsc_*`, `webmaster_*`, `partner_revenue`, `daily_*`, `agent_*`, `analytics_*`, `hypotheses`, `experiments`, `direct_costs`, `fetch_log` остаётся):

```bash
# локально: dump внутрь контейнера postgres, список без данных личных таблиц, plain SQL в gzip
docker cp ~/Backups/forecasteconomy/rustats_YYYYMMDD_040002.dump rosstat-postgres-1:/tmp/prod.dump
docker exec rosstat-postgres-1 pg_restore -l /tmp/prod.dump > full.list        # строки "TABLE DATA public <table>" личных таблиц закомментировать «;»
docker exec rosstat-postgres-1 sh -c 'pg_restore -L /tmp/product.list --no-owner --no-privileges -f - /tmp/prod.dump | gzip -3 > /tmp/product.sql.gz'
# на сервере: остановить frontend/backend/scheduler, drop/create database rustats, gunzip | psql -v ON_ERROR_STOP=1
```

04.10.2026: дамп от 03.10 (ревизия `20260927_world_nonzero_idx`) → 215 МБ SQL, восстановление на 2 vCPU заняло ~3 минуты; в базе 24 продуктовые
таблицы с данными, остальные — только структура. Прежний демо-дамп и конфигурация сохранены на сервере в `/root/backups/` (`demo-db-before-20261004.dump`,
`env-before-20261004`, `override-before-20261004.yml`, `state-before-20261004.txt` — прежний SHA `a58cf29`).

### Что проверено на стенде 04.10.2026 (репетиция выпуска)

- Миграция `20260927_world_nonzero_idx → 20260930_session_reviews` прошла при старте backend; региональный сидер на данных боевого масштаба:
  «сверено 961 494 годовых + 73 740 месячных точек, изменено 71 годовых, 0 новых месячных».
- Все процессы healthy (PostgreSQL, Redis ×2, backend, scheduler, frontend); `/api/v1/health/ready` 200 и по туннелю.
- Главная, планета, поиск с главной («сколько стоил бензин 95 в 2022» → АИ-95), страницы индикатора и страны, `robots.txt` (`?mode=` закрыт), sitemap.
- Не воспроизводится на стенде: **время построения индексов миграции на боевых таблицах событий** (в product-only дампе `behavior_events`/`frontend_events` пусты),
  производительность 4 vCPU, ClickHouse и аналитический планировщик (выключены), исходящие уведомления.

### Репетиция отката (проведена 04.10.2026)

Миграции пачки (`20260930_session_reviews`, `20261004_session_changes`) обратимы: на стенде остановлены frontend/scheduler/backend,
`docker compose run --rm --no-deps -T --entrypoint python backend -m alembic downgrade 20260927_world_nonzero_idx` вернул ревизию за 3 с и удалил
таблицы/индексы (`server_session_changes`, `session_replay_chunks`, `session_analysis_reports`, четыре индекса событий); `docker compose up -d backend scheduler frontend`
накатил обе миграции повторно без ошибок. Рецепт при реальном сбое — «Deploy-scope trap» в [CONTEXT.md](../CONTEXT.md): автооткат кода при новой ревизии схемы **запрещён**,
порядок — бэкап → `stop backend` → `alembic downgrade` образом нового кода → перетегировать образы на старый SHA → `up -d --force-recreate`.

### Пачка 09.10.2026 (круг 11): цепочка миграций, флаги и откат

**Цепочка ревизий невыложенной пачки (одна голова, проверено тестами на SQLite):** `20260927_world_nonzero_idx` (сервер на 30.09) → `20260930_session_reviews` → `20261004_session_changes` → `20261005_push_subscriptions` → **`20261009_user_cabinet`** (четыре таблицы кабинета) → **`20261009b_analytics_signups`** (`user_signups`, `daily_goal_dims`, колонки `site_locale` у `behavior_sessions` и `server_sessions`). Обе новые миграции только добавляют (`CREATE TABLE`, `CREATE INDEX` на новых пустых таблицах, nullable-колонки без значения по умолчанию, которые PostgreSQL 11+ добавляет мгновенно); индексов на `frontend_events`/`behavior_events` нет, старый код новых таблиц не читает, откат кода безопасен. **Не запускалось:** настоящий `alembic upgrade head` по всей цепочке на PostgreSQL, `scripts/check-migration-drift.py` (нужен Postgres), `pg-backup.sh` в бою (только `bash -n`), типы `Uuid`/`JSON` кабинета и план запросов ленты на PostgreSQL; репетиция на тестовом стенде не проводилась.

**Релиз в два шага.** (1) Схема и API с `RUSTATS_CABINET_ENABLED=false` (по умолчанию в коде, compose и `.env.example`): все `/cabinet/*` кроме `config` отвечают 404, ничего не меняется для людей. (2) Включение флага в `.env` боевого сервера (для тестового стенда в его `.env`) и перезапуск backend. Порядок выкладки аналитики: сначала backend (миграция), затем scheduler (как и раньше). Новые флаги отчётов Telegram (`telegram_digest_v2_enabled`, `telegram_weekly_enabled`, `telegram_monthly_enabled`, `telegram_new_alerts_enabled`) выключены; включать по одному и сначала в тестовый чат (`TELEGRAM_CHAT_ID`/`TELEGRAM_DIGEST_CHAT_IDS` на время проверки).

**Рецепт отката схемы** (тот же, что в «Deploy-scope trap» из [CONTEXT.md](../CONTEXT.md): автооткат кода при новой ревизии запрещён): свежий `scripts/pg-backup.sh` → `stop backend scheduler` → `alembic downgrade 20261005_push_subscriptions` (снимает `user_signups`, `daily_goal_dims`, `site_locale` и **четыре таблицы кабинета вместе с данными людей**) образом нового кода → перетегировать образы на прежний SHA → `up -d --force-recreate`. На пустых таблицах чисто; на заполненных downgrade кабинета удаляет избранное, слежения, историю выгрузок и настройки: только по решению владельца. Чистая репетиция (SQLite): тест `test_cabinet_migration.py` накатывает `upgrade()`, сверяет с `Base.metadata` через `compare_metadata` и проверяет `downgrade()`.

**Что проверять после выкладки.** Миграция применилась без блокировок (`\d user_saved_items`, `\d user_signups`, `\d daily_goal_dims`, `site_locale` в двух таблицах сессий); `GET /api/v1/cabinet/config` отвечает `{"enabled":false,...}` при выключенном флаге и 404 на остальных ручках; в логе Caddy/nginx не пишется query пути `/api/v1/cabinet/calendar.ics` (токен личного календаря идёт в адресе); `pg-backup.sh` создал identity-файл со всеми девятью таблицами; разовое восстановление регистраций: `docker compose exec backend python scripts/backfill-signup-attribution.py --dry-run`, затем без `--dry-run`; время `Rollups 15min` и память scheduler (лимит 1 ГиБ) после добавления `rollup_daily_goal_dims` и атрибуции; регистрация тестового аккаунта на `ru.` и на apex создаёт строку `user_signups` с языком и методом, через 15 минут — канал и устройство; согласие: у браузера с явным отказом новых строк в `frontend_events` нет (кроме `consent_update`).

### Нагрузочная проверка

`scripts/test-server/loadtest.py` (stdlib) запускается на самом стенде против `127.0.0.1`; результаты и оговорки (2 vCPU ≠ 4 vCPU боевого) —
[docs/research/capacity-measurement-2026-10-04.md](research/capacity-measurement-2026-10-04.md).

### Доступ при блокировке VPN и актуальный адрес туннеля (наблюдение 08.10.2026)

Наблюдалось при круге дизайна 08.10.2026 (критики на симуляторах, [agent-orchestration](agent-orchestration.md#krug-7-2026-10-08)); из репозитория не воспроизводится, потому что всё это живёт на ноутбуке владельца и на самом стенде.

- **VPN владельца режет SSH к стенду** (`176.57.220.170`): прямой `ssh -i ~/.ssh/id_ed25519_fe_demo root@176.57.220.170` обрывался по таймауту. Рабочий путь — SSH-прыжок через боевой хост по алиасу `fe-prod` (только как транзитный узел; на боевом сервере при этом ничего не выполняется и не меняется):

  ```bash
  ssh -o IdentitiesOnly=yes -i ~/.ssh/id_ed25519_fe_demo -J fe-prod root@176.57.220.170 'cd /opt/rosstat && git rev-parse HEAD'
  ```

  `scripts/test-server/deploy.sh` прыжок сам не умеет (массив `SSH=(ssh … -i "$KEY" "$HOST")` не принимает `-J`); при блокировке выкладка шла теми же командами, что внутри скрипта, через `-J`. Вариант без правки скрипта — запись в `~/.ssh/config` (`Host fe-demo`, `HostName 176.57.220.170`, `User root`, `ProxyJump fe-prod`, `IdentityFile ~/.ssh/id_ed25519_fe_demo`, `IdentitiesOnly yes`) и `FE_TEST_HOST=fe-demo scripts/test-server/deploy.sh`; **этот вариант выведен из кода скрипта и не запускался**. Защита от адреса прода в скрипте проверяет значение `FE_TEST_HOST` строкой, поэтому по алиасу она не сработает: цель проверять глазами (первая строка вывода «сервер: … → цель: …»).
- **Файл адреса туннеля ошибся.** Скрипт, который пишет адрес в `/root/fe-demo-tunnel.url`, в круге дал неверный результат (файл не соответствовал действующему туннелю). Скрипт лежит на самом стенде и в Git не входит, причина не расследована, поэтому `deploy.sh` (последний шаг `cat /root/fe-demo-tunnel.url`) мог напечатать устаревший или пустой адрес. **Брать адрес из журнала туннеля после последней строки `=== start`:**

  ```bash
  # на стенде (Linux): журнал в обратном порядке до самой поздней строки «=== start», в этом куске первый адрес — текущий
  tac /var/log/fe-demo-tunnel.log | sed '/^=== start/q' | grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' | head -1
  ```

  Если разбор неудобен, достаточно `tail -n 40 /var/log/fe-demo-tunnel.log` и взять последний адрес `*.trycloudflare.com` ниже самой поздней строки `=== start` (строка `=== start` пишется при каждом запуске туннеля, адреса выше неё принадлежат прежним запускам). **Команда проверена на синтетическом журнале (`tail -r` вместо `tac` на macOS); настоящий журнал стенда при подготовке этого раздела не читался, формат строки с адресом взят из наблюдения оркестратора.** Перед раздачей адреса критикам и владельцу проверить его запросом `curl -s -o /dev/null -w '%{http_code}' <адрес>/api/v1/health/ready` с ноутбука.
- Нагрузка на ноутбук при приёмке (14 симуляторов) замедляет страницы так же, как медленный стенд; прежде чем считать загрузку дефектом, смотреть `curl` до туннеля и нагрузку ноутбука.

### Известные ограничения стенда

- Хост медленнее ноутбука разработчика примерно в 2–3 раза: холодный поиск ~1–2,5 с против 0,5–1 с локально; ночной `sitemap_build` на 2 vCPU идёт заметно дольше боевых 15 минут (до правки 04.10 его чанк US-штатов упирался в 60 с analytics-пула).
- Адрес туннеля эфемерен; при перезапуске `fe-demo-tunnel` или перезагрузке сервера его нужно прочитать заново. С 08.10.2026 **`/root/fe-demo-tunnel.url` не считается надёжным** (см. следующий подраздел): истина — `/var/log/fe-demo-tunnel.log`.
- Данные — снимок боевой базы от 03.10; ежедневные ETL стенда выключены (`RUSTATS_SCHEDULER_*` задания работают по расписанию, исходящие уведомления и аналитика — нет).

## Прод-деплой

**Пачка 04.10.2026 (`integration/all-20261002`): две миграции — `20260930_session_reviews`, `20261004_session_changes`.** Первая строит четыре индекса `CREATE INDEX CONCURRENTLY`
на `behavior_events` (1,45 ГБ) и `frontend_events` (266 МБ) **при старте backend**, пока API недоступен, а `deploy.sh` ждёт готовности 300 с — поэтому индексы строятся заранее, на работающем старом коде:

```sql
-- psql под владельцем БД, вне транзакции; свободное место ≥ 3 ГБ (диск боевого 77 ГБ, занято 79%)
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_behavior_session_event ON behavior_events (session_id_hash, id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_behavior_occurred      ON behavior_events (occurred_at);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_frontend_session_event ON frontend_events (session_id_hash, id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_frontend_occurred      ON frontend_events (occurred_at);
-- проверка: все четыре valid и ready, иначе DROP INDEX CONCURRENTLY и повтор
SELECT indexrelid::regclass, indisvalid AND indisready FROM pg_index WHERE indexrelid::regclass::text IN
  ('ix_behavior_session_event','ix_behavior_occurred','ix_frontend_session_event','ix_frontend_occurred');
```

Миграция затем только проверяет и пропускает готовые индексы (`IF NOT EXISTS` + проверка `indisvalid`). Время построения на боевых таблицах **не измерялось** (на стенде таблицы пусты) — смотреть `pg_stat_progress_create_index`.
Запись и анализ сессий в этом выпуске выключены (`RUSTATS_SESSION_*_ENABLED=false` — значения по умолчанию в коде и compose); `session_replay_chunks` не попадает в данные ежедневного дампа.
Откат схемы — только по рецепту «Deploy-scope trap» ([CONTEXT.md](../CONTEXT.md)); репетиция downgrade обеих миграций проведена на стенде.

**Текущее наблюдение 30.09:** серверный head уже `20260927_world_nonzero_idx`, checkout `367ff336`, выбранные `deploy.sh`/Compose/Caddy/nginx совпадают с main. Ниже сохраняется рецепт **первого** выпуска и инцидент 27.09: он не является инструкцией повторно выполнять уже применённую миграцию. Для любого нового выпуска заново проверять прод → цель и совместимость схемы.

**Регламент 2026-09-20: `main` не означает разрешение на выкладку.** Нужна явная команда владельца «деплой до `<sha>`, включая всё, что он тянет» и полный целевой SHA в `deploy/approved-shas.txt`. Пустой/отсутствующий список = запрет. Эта документация не одобряет ни один SHA.

1. До запуска показать весь диапазон прод → цель: `git log --oneline <PROD_SHA>..<TARGET_SHA>` и изменения `backend/alembic/versions/` в том же диапазоне. При наличии миграций отдельно запросить подтверждение с описанием влияния на данные и возможности отката; guard удаления миграций не заменяет эту проверку. Push — только по отдельной явной команде и после зелёного `./scripts/check-all.sh`.
   Для **первого** выпуска с `20260927_world_nonzero_idx` заранее, после подтверждения этой миграции, построить индекс на работающем старом backend через `CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_world_data_points_nonzero_indicator ON world_data_points (indicator_id) WHERE value <> 0` отдельным `psql`-вызовом вне транзакции. Перед `deploy.sh` проверить в `pg_catalog.pg_index`, что `indisvalid AND indisready` истинны: установленный на проде старый `deploy.sh` не содержит нового шага prebuild и не подхватит его надёжно при собственном `git merge`; полный `alembic upgrade` заранее не запускать, чтобы старый backend оставался пригоден для отката. После первого выпуска вручную проверить `/api/v1/world/countries` на RU и EN хостах: HTTP 200, непустые `countries`, повторный быстрый ответ; старый `deploy.sh` не содержит и нового smoke этого маршрута.
2. Только после выполнения этих условий — `ssh fe-prod 'bash /opt/rosstat/scripts/deploy.sh'`. Скрипт fetch/ff-only ориентируется на `origin/main`, поэтому заранее сверить его с одобренной целью, не выкатывать накопившийся `main` и не обходить scope guard. Скрипт выполняет preflight `pg-backup.sh` (hard fail), dirty/scope/migration guards, совместную сборку backend+frontend, `up -d`, readiness, smoke данных/SSR-ассетов/OG, Caddy reload и post-deploy watch.

   **Первый выпуск с обновлённым скриптом после инцидента 2026-09-27:** установленный на проде старый `deploy.sh` при собственном `git merge` не получает надёжно новые шаги. После `git fetch` и проверки точного SHA `origin/main` взять `scripts/deploy.sh` из этого SHA в отдельный файл `/tmp/rosstat-deploy-<sha>.sh` и запустить его: он читает `deploy/approved-shas.txt` из `/opt/rosstat` и остаётся неизменным во время merge. После Caddy reload `dual-host-release-gate.py::_check_og_image` повторяет **только HTTP 429** с паузами 2/4/8/16 с; первичный OG curl в `deploy.sh` выполняется один раз и может завершить smoke раньше gate. Gate требует 200, image Content-Type и тело ≥1000 байт, транспортные ошибки/другие HTTP статусы не повторяет. При новых файлах миграций, изменении Alembic revision или неизвестной ревизии БД автоматический откат кода прекращается без запуска несовместимого старого образа; ручное восстановление — [CONTEXT, Deploy-scope trap](../CONTEXT.md), со свежим бэкапом и проверкой ревизии до старта старого backend. В первом запуске 2026-09-27 старый gate ошибочно счёл временный 429 поломкой OG и автооткат оставил новую ревизию БД под старым кодом; база и сайт были восстановлены по этому рецепту.

   **Окно 502 при cutover ещё существует.** `up -d` может снять единственный frontend на `:3000`, пока новый backend выполняет миграции и сиды; IPv4-адрес Caddy устраняет только ошибку резолвинга `localhost` в `::1`. Черновой preboot из PR #1 не перенесён: он запускал новые миграции и сиды рядом со старым web и scheduler без проверки совместимости схемы и повторной записи; перед staged cutover нужен прогон на копии production БД и проверка rollback для всего диапазона миграций.
3. Отдельный `scheduler` при старте фоном запускает `_catch_up_empty_indicators()`, затем `_catch_up_empty_forecasts_safe("startup")`. После планового и late-ETL есть повторный gap-fill прогнозов. Эти шаги не блокируют web-readiness и не гарантируют непустой прогноз при короткой истории или неподходящей стратегии; после добавления derived проверять факты и прогнозы через API.
4. `deploy.sh` сам удаляет только SSR HTML-ключи в cache Redis DB 0 через `SCAN` + `UNLINK`. Data-кэши и ключи версий `fe:ver:*` сохраняются; для доказанной необходимости отдельной инвалидации доступны `DEPLOY_CACHE_EXTRA_PATTERNS` и `DEPLOY_CACHE_BUMP_NAMESPACES`. Не запускать ручной `FLUSHDB` как обычный шаг релиза: он сносит дорогие data-кэши. State Redis (логический DB 1 либо отдельный `redis-state`) не очищать; поколение `world-catalog` живёт там, а `DEPLOY_CACHE_BUMP_NAMESPACES` для него запрещён (см. [`data-contracts.md`](data-contracts.md#параллельные-изменения-рабочего-дерева)).
5. Если менялся контракт факта/derived/forecast, проверить конкретные ряды после деплоя. При отсутствии прогноза сначала проверить `forecast_steps`, доступную историю и результат gap-fill; ручной retrain — диагностический/восстановительный шаг через `app.services.forecast_pipeline.retrain_indicator_forecast(db, indicator)` с `AsyncSession`, а не прежний вызов из `app.services.forecaster` по строковому коду.

### Smoke C — проверки после деплоя

Минимальный набор curl/SSR-сверок: `deploy.sh` выполняет readiness и часть data/SSR/OG-smoke; аналитику, конкретные прогнозы и браузерные сценарии проверяют отдельно.

- `GET /api/v1/health/ready` → 200 (реальный readiness: БД + оба Redis + планировщик).
- `GET /api/v1/analytics/health` с заголовком `X-Analytics-Token` → проверить `enabled`, `scheduler_enabled` и последние `last_runs`; `failed_sync_runs` в текущем API — счётчик всех строк `status=failed`, не окно 24 часа, поэтому требование «=0» без контекста неверно.
- 5–10 ключевых indicator forecast endpoints → 200 с непустым `forecast.values`.
- SSR главной + 2–3 категорий + 3–5 индикаторов через `User-Agent: YandexBot/3.0` → 200, осмысленные `<title>`, корректные ссылки.
- `GET /sitemap.xml` → 200, валидный XML.
- Headless E2E на 6+ страницах → 0 console errors / 0 4xx-5xx.
- Проверенные поисковые роботы (изменение 2026-10-04): `docker compose exec frontend nginx -t` OK и файл `/etc/nginx/search-crawlers.conf` на месте; через сутки в `/var/log/rosstat-nginx/security.log*` у запросов с IP Google/Bing/Яндекса и UA их индексирующего бота нет ответов 429 (до выкладки: ≥3 573 в сутки у Googlebot), а нагрузка хоста (`uptime`) не выросла против прежней. Список сетей обновлять раз в месяц: `python3 scripts/refresh-search-crawler-ranges.py`, затем `deploy/test-nginx-config.sh`, `python3 scripts/test-crawler-routing.py`, пересборка frontend.

`deploy.sh` после smoke держит **15-минутный watch**: TTFB главной, `/health/ready`,
память контейнера backend, признак `OOMKilled`. Срыв передаётся в rollback; возврат прежних image IDs допускается только при подтверждённой совместимости миграций/revision. При неизвестной ревизии или изменении схемы автоматический запуск старого кода прекращается.

**Архив ассетов (локальная реализация 2026-09-20).** `scripts/deploy.sh` под общей блокировкой публикует hashed-ассеты фактически работающего frontend и новой сборки через `scripts/frontend-asset-archive.py` **до** замены контейнеров и выдачи нового HTML. nginx читает архив как fallback; HTML, source maps и файлы без хэша туда не попадают. На успешном пути `prune --keep 3` выполняется только после smoke и 15-минутного watch. На пути отката сначала повторно публикуется восстановленный frontend, затем выполняется очистка. Проверять старый ассет, отсутствующий в новой сборке, и навигацию старой вкладки; retention ограничен тремя релизами, это не бессрочная гарантия Вебвизора. Приёмка пакета — [backlog](backlog.md#history-access-reliability-2026-09-20).

### Runbook: хост в свопе (2026-09-03)

Симптомы: главная 5–30 с, `idle in transaction` в Postgres, RSS backend у лимита.

Смотреть:

```
docker stats --no-stream
docker compose exec postgres psql -c "select datname, state, now()-state_change as idle, query from pg_stat_activity where state <> 'idle' order by state_change"
# /api/v1/metrics требует непустой RUSTATS_METRICS_TOKEN и query token;
# 30.09 effective token web пуст, поэтому endpoint закрыт (403).
```

Дополнительно: пул/FD/pressure gauges в коде существуют, но scrape требует отдельно настроенного токена/коллектора. Токен не помещать в общий журнал/документ. Readiness, Docker stats и pg_stat_activity доступны для диагностики; один снимок не измеряет swap-in/out или latency во времени.

Делать: не рестартовать по кругу, если схема обогнала код (Deploy-scope trap).
Аналитические джобы — на `analytics_engine`; если старый код ещё на проде —
`docker compose restart backend` только после проверки, что это не alembic-голова.
ClickHouse вторичен: можно `stop clickhouse` без влияния на витрину.

Зелёный smoke сам по себе не завершает приёмку: нужны успешный watch и проверка исходных пользовательских сценариев. Красный результат — разбор совместимости кода и схемы по [CONTEXT](../CONTEXT.md), не автоматическое восстановление БД поверх новых пользовательских данных.

## История

`history_of_project.md` упразднён (мaй 2026). Архитектурные решения теперь живут в `docs/adr/`, оперативное состояние — в `CONTEXT.md`, runtime-наблюдения — в commit messages и коде Pull Request.

## Устойчивость

Чеклист по тому, что закладывать при доработках API, парсеров и UI: **[enterprise_resilience.md](enterprise_resilience.md)**.

## Двуххостовый языковой cutover

`ru.forecasteconomy.com` — русский канон, apex `forecasteconomy.com` — английский
(`RUSTATS_APEX_LOCALE_EN=true` на проде). Один флаг для backend и frontend
build; отдельный `VITE_APEX_LOCALE_EN` в окружении запрещён. Людей с IP
России/СНГ с apex уводим на `ru.`; поисковые и ИИ-боты остаются на
запрошенном хосте. `Accept-Language` не редиректит. Флажок «Русский» =
host-swap на `ru.` + cookie `fe_locale_pref`. Перед релизом обязательны
`python3 scripts/dual-host-release-gate.py` и полный `./scripts/check-all.sh`.
Поисковые роботы, API, sitemap, robots, RSS, OG, embed, health и OAuth
callback отвечают на запрошенном хосте. Явный выбор языка хранится год
в cookie `fe_locale_pref` с Domain `.forecasteconomy.com`.

## 2026-10-09 — выпуск оптимизации сессионизации

Миграция 20261009c_session_perf добавляет ix_behavior_logical_time
CONCURRENTLY и проверяет valid/ready. Можно подготовить ровно этот индекс
перед заменой backend, оставив прежний код и alembic_version неизменными;
entrypoint нового образа затем быстро применит/stamp миграцию. Индекс
добавочный, старый код продолжает работать. Не повышать statement_timeout
для маскировки ошибки. После выпуска проверить завершение реального
15-минутного расчёта и холодный/тёплый API карты на обоих хостах.
[Протокол](code-review/performance-acceptance-2026-10-09.md).

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
