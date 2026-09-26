# Рабочий процесс — Forecast Economy

**Part of:** [`../AGENTS.md`](../AGENTS.md), [`../CONTEXT.md`](../CONTEXT.md).
**See also:** [`STATE.md`](STATE.md) (где остановились), [`indicators.md`](indicators.md) (чеклист «новый индикатор»), [`adr/`](adr/) (архитектурные решения).

## Модель работы

Раньше работа шла по **фазам** (план `forecast_economy_v2`, фазы 0–4). Все фазы закрыты к концу апреля 2026. Сейчас работа идёт по двум потокам:

- **Архитектурные кандидаты** — большие deepening-рефакторы (`refactor/...` ветки): calculation_engine pure ops + DerivedSpec, BaseParser template-method, forecast strategies registry, indicator metadata в БД, SEO single-source, IndicatorDetail декомпозиция и т.п. Фиксируются в `docs/adr/` (нумерованные ADR).
- **Точечные правки по обратной связи** — конкретные баги/правки от Никиты или собственного аудита (CPI квартальная вкладка, GDP nominal/real split, weekly forecast, calendar rolling 12-мес и т.п.). Идут в `feat/...` или `fix/...` ветках, мерджатся в `main` через `--no-ff`.

Любая правка должна проходить регламент ниже. Ничего «полу-готового» в `main`.

## Git и окружения

- **GitHub (`git push origin main`)** — основной способ фиксировать прогресс; коммиты должны быть **согласованы** с тем, что реально сделано.
- **Прод-сервер** (`ssh fe-prod`, `/opt/rosstat`; DNS `forecasteconomy.com`, `ru.forecasteconomy.com`) — **не деплоить автоматически** и **не без явного запроса**. Разработка и проверка — локально (Docker Compose) и через CI; выкладка на сервер — отдельным шагом по команде.
- **SSH на прод — только по ключу** (с 2026-08-27): `ssh fe-prod` (алиас в `~/.ssh/config`) или явно `ssh -i ~/.ssh/id_ed25519_fe_prod root@201.51.11.170`. Парольный вход отключён (`/etc/ssh/sshd_config.d/00-hardening.conf`: `PermitRootLogin prohibit-password`, `PasswordAuthentication no`; бэкап старого конфига — `/etc/ssh/sshd_config.bak-keyauth`). Ключ только у владельца; потеря ключа = восстановление через панель провайдера (VNC/rescue).
- **Перед каждым прод-деплоем** `scripts/deploy.sh` сам запускает `scripts/pg-backup.sh` (сбой = деплой остановлен). Бэкапы и восстановление — runbook ниже.
- **Персистентность данных пользователей (ADR-0007).** БД — docker volume `postgres_data` (переживает `up -d --build`); плюс ежедневные бэкапы (runbook ниже), identity-таблицы отдельным SQL.

## Локальная разработка

### Поднять стек

```bash
cp .env.example .env
docker compose up -d --build
```

Backend `entrypoint.sh` сам поднимет миграции (`alembic upgrade head`), seed-данные (`seed_data.py` идемпотентный upsert), календарь (`calendar_seed`) и Uvicorn.

### Синхронизация с продом

Если локальная БД отстала от продa по точкам — read-only sync через публичный API:

```bash
docker compose exec backend python /app/scripts/sync-local-from-prod.py
```

Идемпотентный — `bulk_upsert` с `ON CONFLICT DO NOTHING` для существующих локально точек, никогда не удаляет.

### Полный пересчёт derived

Если меняли `derived_ops.py` или `DERIVED_SPECS`, либо вручную правили source через SQL:

```bash
docker compose exec backend python /app/scripts/rebuild-all-derived.py
```

Прогон без guard'а (без проверки `source_codes`); first run выводит non-zero changes для stale серий, second run — все нули (idempotency check).

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

Локально одной командой (эквивалент CI):

```bash
./scripts/check-all.sh
```

Гонит `pytest backend/`, `npm run lint`, `npm test`, `npm run build` во `frontend/`. Зелёное `check-all.sh` — обязательное предусловие для `git push`.

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

**`main` не означает разрешение на выкладку.** Нужна явная команда владельца
«деплой до `<sha>`» и полный SHA в `deploy/approved-shas.txt`. Пустой список =
запрет. Владелец предпочитает 2–3 больших пачки, а не деплой на каждую правку.

1. Показать владельцу диапазон `git log --oneline <PROD_SHA>..<TARGET_SHA>` и
   изменения `backend/alembic/versions/` в нём; миграции — отдельное
   предупреждение (откат кода не откатывает схему). CI на целевом SHA зелёный.
2. Approval-only коммит: единственный ребёнок целевого SHA, меняющий только
   `deploy/approved-shas.txt` (допустимо + `scripts/deploy.sh`); push по команде.
3. Запуск (не в 03:40–04:00 МСК — ночная сборка sitemap; всего ~25 мин):

   ```bash
   ssh fe-prod 'cd /opt/rosstat && git fetch origin main && \
     git show origin/main:scripts/deploy.sh > /tmp/rosstat-deploy-<sha>.sh && \
     nohup bash /tmp/rosstat-deploy-<sha>.sh > /tmp/rosstat-deploy-<sha>.log 2>&1 &'
   ```

   Копия в `/tmp` + `nohup`: скрипт переживает обрыв SSH и собственный
   `git reset` при откате. Следить: `tail -f /tmp/rosstat-deploy-<sha>.log`;
   логи backend — `/tmp/backend-<sha>.log` (`-rollback.log` при откате).
4. Что делает скрипт: `pg-backup.sh` → ff-only + approved/scope/migration
   guards → сборка backend+frontend на проде → архив ассетов → `compose up` →
   readiness → очистка **только** SSR-кэша (`fe:*:ssr:*`, SCAN+UNLINK; доп.
   `DEPLOY_CACHE_EXTRA_PATTERNS` / `DEPLOY_CACHE_BUMP_NAMESPACES`) → smoke
   данных/ассетов/OG → HTTPS обоих хостов + `scripts/dual-host-release-gate.py`
   (34 RU/EN страницы) → 15-минутный watch (TTFB, `/health/ready`, память, OOM)
   → при срыве автооткат на предыдущий SHA. Успех — строка
   `deploy <sha> complete`.
5. FLUSHDB не делать никогда (холодный кэш под ботами = 503, CONTEXT, Cold-cache
   pool exhaustion). Если деплой добавил derived — ручной retrain источников:
   `docker compose exec backend python -c "import asyncio; from app.services.forecast_pipeline import retrain_indicator_forecast; asyncio.run(retrain_indicator_forecast('<source_code>'))"`,
   затем `cache_invalidate_indicator(code)`.
6. При старте backend `_catch_up_empty_indicators()` сам догоняет ETL для
   активных индикаторов без точек; провалы — в Telegram.

Откат образов не откатывает схему: при несовместимости — CONTEXT, Deploy-scope
trap, а не перезапуск старого кода по кругу.

**Канарейка перед мерджем в `main`:** `./scripts/check-all.sh` зелёный; парсер —
двойной прогон без изменений на втором; forecast-стратегия —
`rebuild-all-derived.py` второй прогон нулевой; SEO/SSR — `YandexBot/3.0` на 3+
страницах (`title`, `meta`).

### Smoke C — проверки после деплоя

Минимальный набор curl/SSR-сверок (первые четыре пункта `deploy.sh` делает сам):

- `GET /api/v1/health/ready` → 200 (реальный readiness: БД + оба Redis + планировщик).
- `GET /api/v1/analytics/health` (с токеном `Authorization: Bearer ${RUSTATS_ANALYTICS_API_TOKEN}`) → `enabled=true`, `failed_sync_runs=0`.
- 5–10 ключевых indicator forecast endpoints → 200 с непустым `forecast.values`.
- SSR главной + 2–3 категорий + 3–5 индикаторов через `User-Agent: YandexBot/3.0` → 200, осмысленные `<title>`, корректные ссылки.
- `GET /sitemap.xml` → 200, валидный XML.
- Headless E2E на 6+ страницах → 0 console errors / 0 4xx-5xx.

`deploy.sh` после smoke держит **15-минутный watch**: TTFB главной, `/health/ready`,
память контейнера backend, признак `OOMKilled`. Срыв — автооткат на предыдущий SHA.

**Архив ассетов.** `scripts/deploy.sh` под общей блокировкой публикует hashed-ассеты фактически работающего frontend и новой сборки через `scripts/frontend-asset-archive.py` **до** замены контейнеров и выдачи нового HTML. nginx читает архив как fallback; HTML, source maps и файлы без хэша туда не попадают. На успешном пути `prune --keep 3` выполняется только после smoke и 15-минутного watch. На пути отката сначала повторно публикуется восстановленный frontend, затем выполняется очистка. Проверять старый ассет, отсутствующий в новой сборке, и навигацию старой вкладки; retention ограничен тремя релизами, это не бессрочная гарантия Вебвизора.

### Runbook: хост в свопе (2026-09-03)

Симптомы: главная 5–30 с, `idle in transaction` в Postgres, RSS backend у лимита.

Смотреть:

```
docker stats --no-stream
docker compose exec postgres psql -c "select datname, state, now()-state_change as idle, query from pg_stat_activity where state <> 'idle' order by state_change"
curl -sS https://forecasteconomy.com/api/v1/metrics | grep -E 'fe_db_pool|fe_process_rss|fe_cgroup_memory'
```

Делать: не рестартовать по кругу, если схема обогнала код (Deploy-scope trap).
Аналитические джобы — на `analytics_engine`; если старый код ещё на проде —
`docker compose restart backend` только после проверки, что это не alembic-голова.
ClickHouse вторичен: можно `stop clickhouse` без влияния на витрину.

Зелёный smoke сам по себе не завершает приёмку: нужны успешный watch и проверка исходных пользовательских сценариев. Красный результат — разбор совместимости кода и схемы по [CONTEXT](../CONTEXT.md), не автоматическое восстановление БД поверх новых пользовательских данных.

### Runbook: пул БД исчерпан / 503 под ботами

Симптомы: 503 на SSR, `QueuePool limit ... timed out` в логах backend, в
`pg_stat_activity` много `idle in transaction`, watch деплоя откатывает релиз.

- Проверить, не было ли FLUSHDB / массовой инвалидации (холодный кэш).
- `pg_stat_activity` (запрос выше) и `fe_db_pool` в `/api/v1/metrics`; nginx
  access-лог — доля ботов и темп запросов.
- Не рестартовать по кругу: рестарт тоже холодный. Дать кэшу прогреться; если
  новый SSR-роут держит сессию во время ожидания — фикс в коде (`_release_db`).
- Временный щит — включить `deploy/optional/perplexitybot-ratelimit.nginx.conf`
  (только с согласия владельца).

### Runbook: бэкапы и восстановление

**Сервер.** Cron `0 4 * * *` UTC (07:00 МСК) → `scripts/pg-backup.sh` →
`/opt/rosstat/backups/rustats_YYYYMMDD_HHMMSS.dump` (`pg_dump -Fc`, штамп UTC) +
`.identity.sql.gz` (data-only: `users`, `email_credentials`, `oauth_identities`,
`consents`, `auth_audit`); хранение 14 дней; heartbeat/алерт в Telegram. Плюс
бэкап в начале каждого деплоя.

**Копия на Mac владельца.** `~/bin/fe-backup-pull.sh` + launchd
`~/Library/LaunchAgents/com.forecasteconomy.backup-pull.plist` (08:15 и при входе)
→ `~/Backups/forecasteconomy/`. Берёт самый свежий дневной дамп, у которого уже
есть identity-файл и оба старше 10 мин; rsync, сверка размера и sha256 с
сервером, `pg_restore --list` (локально или `docker postgres:16-alpine`),
`gzip -t`, маркер `.verified`; держит 14; лог `pull.log`; при сбое —
уведомление macOS. Эталонные копии — `deploy/mac/` (после правки скопировать
обратно в `~/bin` и `~/Library/LaunchAgents`, `launchctl` перезагрузить).

**Восстановление — НЕ ОТРАБОТАНО на практике, сначала репетиция:**

1. Проверить файл: `pg_restore --list <file>.dump | head`.
2. Репетиция во временную БД:
   `docker compose exec postgres createdb -U rustats rustats_restore_test` →
   `docker compose exec -T postgres pg_restore -U rustats -d rustats_restore_test --no-owner < <file>.dump` →
   сверить счётчики → `dropdb`.
3. Реальное восстановление (только по решению владельца): свежий
   `pg-backup.sh` → `docker compose stop backend` →
   `docker compose exec -T postgres pg_restore -U rustats -d rustats --clean --if-exists < <file>.dump`
   → `docker compose up -d backend` → `/api/v1/health/ready`.
4. Только пользователи:
   `gunzip -c <file>.identity.sql.gz | docker compose exec -T postgres psql -U rustats -d rustats`.

Дамп должен соответствовать alembic-голове кода: старый дамп + новый код →
entrypoint докатит миграции; новый дамп + старый код — Deploy-scope trap.

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
