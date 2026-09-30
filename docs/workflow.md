# Рабочий процесс — Forecast Economy

**Last updated:** 2026-09-30 (ops: свежая доставка и изолированный restore; история 27.09 сохранена). Локальная `main` и датированный снимок серверной конфигурации разобраны отдельно: [реестр кода](code-review.md), [архитектура и окружение](architecture.md), [наблюдения и ограничения](code-review-findings.md). Кодовый разбор не заменяет приёмку выпуска на production.

**Previous:** 2026-09-20 (approved-SHA gate, миграции и архив ассетов). Ранее 2026-09-03 (post-deploy watch 15 мин + runbook «хост в свопе»). Ранее 2026-07-06 (CTO-аудит, Волна 5: прод-IP актуализирован — 201.51.11.170 (переезд 2026-07-03, старый 5.129.204.194 упразднён); прод-деплой переведён на `scripts/deploy.sh` — preflight-бэкап, ff-only guard, версионированные образы с автооткатом, расширенный smoke (SSR asset-hash / data-endpoint / OG), Caddy reload после smoke; ETL идёт двумя прогонами (06:00 и 20:00 МСК) + late-Minfin 15:00; smoke-набор дополнен readiness `/health/ready`; E2E-runner `scripts/e2e/smoke.mjs` реализован (Playwright, 5 сценариев + YandexBot SSR-suite) и включён в CI. Ранее 2026-05-22: добавлен ручной ETL recipe, `_catch_up_empty_indicators` + `redis-cli FLUSHDB`.)
**Part of:** [`../AGENTS.md`](../AGENTS.md), [`../CONTEXT.md`](../CONTEXT.md).
**See also:** [`enterprise_resilience.md`](enterprise_resilience.md) (чеклист канарейки), [`data-contracts.md`](data-contracts.md) (сквозные контракты данных), [`agent-recipes.md`](agent-recipes.md) (рецепты индикаторов), [`knowledge-workflow.md`](knowledge-workflow.md) (сопровождение знаний), [`adr/`](adr/) (архитектурные решения).

## Модель работы

Раньше работа шла по **фазам** (план `forecast_economy_v2`, фазы 0–4). Все фазы закрыты к концу апреля 2026. Сейчас работа идёт по двум потокам:

- **Архитектурные кандидаты** — большие deepening-рефакторы (`refactor/...` ветки): calculation_engine pure ops + DerivedSpec, BaseParser template-method, forecast strategies registry, indicator metadata в БД, SEO single-source, IndicatorDetail декомпозиция и т.п. Фиксируются в `docs/adr/` (нумерованные ADR).
- **Точечные правки по обратной связи** — конкретные баги/правки от Никиты или собственного аудита (CPI квартальная вкладка, GDP nominal/real split, weekly forecast, calendar rolling 12-мес и т.п.). Идут в `feat/...` или `fix/...` ветках, мерджатся в `main` через `--no-ff`.

Любая правка должна проходить регламент ниже. Ничего «полу-готового» в `main`.

## Git и окружения

- **GitHub (`git push origin main`)** — основной способ фиксировать прогресс; коммиты должны быть **согласованы** с тем, что реально сделано.
- **Прод-сервер** (`201.51.11.170`, `/opt/rosstat`; DNS `forecasteconomy.com`) — **не деплоить автоматически** и **не без явного запроса**. Разработка и проверка — локально (Docker Compose) и через CI; выкладка на сервер — отдельным шагом по команде.
- **SSH на прод — только по ключу** (с 2026-08-27): `ssh fe-prod` (алиас в `~/.ssh/config`) или явно `ssh -i ~/.ssh/id_ed25519_fe_prod root@201.51.11.170`. Парольный вход отключён (`/etc/ssh/sshd_config.d/00-hardening.conf`: `PermitRootLogin prohibit-password`, `PasswordAuthentication no`; бэкап старого конфига — `/etc/ssh/sshd_config.bak-keyauth`). Ключ только у владельца; потеря ключа = восстановление через панель провайдера (VNC/rescue).
- **Перед каждым прод-деплоем** — `scripts/deploy.sh` запускает `scripts/pg-backup.sh` и прекращает деплой при ненулевом коде бэкапа. Скрипт создаёт полный `pg_dump -Fc` (`.dump`) и отдельный `.identity.sql.gz`; локальные файлы старше `KEEP_DAYS` (по умолчанию 14) удаляет. Offsite-копирование зависит от `OFFSITE_S3_BUCKET` и наличия `aws`; если bucket задан, а `aws` отсутствует, скрипт предупреждает, но завершает работу успешно. Поэтому зелёный preflight доказывает создание локального dump, но сам по себе не доказывает offsite-копию или возможность восстановления. См. [`enterprise_resilience.md`](enterprise_resilience.md#восстановление-и-наблюдаемость).
- **Персистентность данных пользователей (ADR-0007).** БД хранится в docker volume `postgres_data` — переживает `docker compose up -d --build`. `scripts/pg-backup.sh` создаёт полный custom dump и отдельный data-only SQL пяти identity-таблиц (`users`, `email_credentials`, `oauth_identities`, `consents`, `auth_audit`). Наличие файлов не заменяет пробное восстановление и проверку связности записей. Пример **проверочного** восстановления на отдельном Docker-томе, без публикации порта и без обращения к рабочему compose-сервису. **30.09 этот подход выполнен** для свежих full/identity файлов: [протокол](code-review/backup-acceptance-2026-09-30.md). Переносимый пример для следующей проверки на хосте с доступным Docker:

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

## Прод-деплой

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
