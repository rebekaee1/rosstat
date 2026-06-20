# Рабочий процесс — Forecast Economy

**Last updated:** 2026-05-22 (документация-ревизия: добавлен ручной ETL recipe, обновлён прод-деплой чек с `_catch_up_empty_indicators` + `redis-cli FLUSHDB`).
**Part of:** [`../AGENTS.md`](../AGENTS.md), [`../CONTEXT.md`](../CONTEXT.md).
**See also:** [`enterprise_resilience.md`](enterprise_resilience.md) (чеклист канарейки 6/6), [`../AGENTS.md::Шаг 4`](../AGENTS.md) (чеклист «новый индикатор» 7/7 — другая ось), [`adr/`](adr/) (архитектурные решения).

## Модель работы

Раньше работа шла по **фазам** (план `forecast_economy_v2`, фазы 0–4). Все фазы закрыты к концу апреля 2026. Сейчас работа идёт по двум потокам:

- **Архитектурные кандидаты** — большие deepening-рефакторы (`refactor/...` ветки): calculation_engine pure ops + DerivedSpec, BaseParser template-method, forecast strategies registry, indicator metadata в БД, SEO single-source, IndicatorDetail декомпозиция и т.п. Фиксируются в `docs/adr/` (нумерованные ADR).
- **Точечные правки по обратной связи** — конкретные баги/правки от Никиты или собственного аудита (CPI квартальная вкладка, GDP nominal/real split, weekly forecast, calendar rolling 12-мес и т.п.). Идут в `feat/...` или `fix/...` ветках, мерджатся в `main` через `--no-ff`.

Любая правка должна проходить регламент ниже. Ничего «полу-готового» в `main`.

## Git и окружения

- **GitHub (`git push origin main`)** — основной способ фиксировать прогресс; коммиты должны быть **согласованы** с тем, что реально сделано.
- **Прод-сервер** (`5.129.204.194`, `/opt/rosstat`) — **не деплоить автоматически** и **не без явного запроса**. Разработка и проверка — локально (Docker Compose) и через CI; выкладка на сервер — отдельным шагом по команде.
- **Перед каждым прод-деплоем** — обязательный `pg_dump | gzip > /opt/rosstat/backups/pre-deploy-$(date +%Y%m%d-%H%M%S).sql.gz`. См. `scripts/pg-backup.sh` и стандарт ниже.
- **Персистентность данных пользователей (ADR-0007).** БД хранится в docker volume `postgres_data` — переживает `docker compose up -d --build`. Дополнительно `scripts/pg-backup.sh` (cron `0 4 * * *` на проде) делает (1) полный `pg_dump -Fc` и (2) отдельный data-only SQL identity-таблиц (`users/email_credentials/oauth_identities/consents/auth_audit`) — гарантия, что зарегистрированные пользователи не теряются. Восстановление:
  - полностью: `docker compose exec -T postgres pg_restore -U rustats -d rustats --clean --if-exists < backups/<file>.dump`;
  - только пользователи: `gunzip -c backups/<file>.identity.sql.gz | docker compose exec -T postgres psql -U rustats -d rustats`.

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

Для in-session браузер-чеков используется техника выше (`cursor-ide-browser`). Полноценный E2E-runner (`scripts/e2e/smoke.mjs`) пока не реализован — задача в `docs/backlog.md`.

Если dev-сервер недоступен в среде — явно записать что проверено альтернативно (только unit-тесты / только snapshot-тесты / только curl-сверка SSR).

## Прод-деплой

Стандартная процедура (через SSH из агента, по explicit команде пользователя):

1. `git push origin main` — закатить ветку.
2. `pg_dump | gzip > backups/pre-deploy-$(date +%Y%m%d-%H%M%S).sql.gz` — на проде.
3. `git pull --ff-only` на `5.129.204.194:/opt/rosstat`.
4. `docker compose build backend frontend` — **оба образа всегда вместе** (см. «Asset-hash mismatch trap» в `enterprise_resilience.md`). Если меняли frontend и переподнимаете отдельно — `docker compose build --no-cache frontend` для гарантии новых assets (см. «Browser-cache trap при rebuild frontend» в `CONTEXT.md`).
5. `docker compose up -d backend frontend` — **одновременно** (страховка от asset-hash mismatch). Backend на старте автоматически прогоняет `_catch_up_empty_indicators()` — ETL для всех `is_active=true` индикаторов с 0 точками (новые индикаторы дотягиваются без ручного `run_etl_for_indicator`). См. `app/main.py`.
6. Alembic миграции применяются автоматически из `entrypoint.sh`.
7. `redis-cli FLUSHDB` — обязательно, если правки касались форматирования/SSR, добавлены derived (forecast retrain trap), или изменилось мето `seo_renderer.py`.
8. Если деплой добавляет новые derived (`DERIVED_SPECS` пополнен): `docker compose exec backend python -c "import asyncio; from app.services.forecaster import retrain_indicator_forecast; asyncio.run(retrain_indicator_forecast('<source_code>'))"` для каждого изменённого источника. Daily ETL не подхватит автоматически (см. `enterprise_resilience.md::forecast retrain trap`).

### Smoke C — проверки после деплоя

Минимальный набор curl/SSR-сверок:

- `GET /api/v1/health` → 200.
- `GET /api/v1/analytics/health` (с токеном `Authorization: Bearer ${RUSTATS_ANALYTICS_API_TOKEN}`) → `enabled=true`, `failed_sync_runs=0`.
- 5–10 ключевых indicator forecast endpoints → 200 с непустым `forecast.values`.
- SSR главной + 2–3 категорий + 3–5 индикаторов через `User-Agent: YandexBot/3.0` → 200, осмысленные `<title>`, корректные ссылки.
- `GET /sitemap.xml` → 200, валидный XML.
- Headless E2E на 6+ страницах → 0 console errors / 0 4xx-5xx.

Зелёный smoke = деплой принят. Красный = решение по rollback (`git reset --hard <prev>` + `pg_restore < backups/pre-deploy-*.sql.gz`).

## История

`history_of_project.md` упразднён (мaй 2026). Архитектурные решения теперь живут в `docs/adr/`, оперативное состояние — в `CONTEXT.md`, runtime-наблюдения — в commit messages и коде Pull Request.

## Устойчивость

Чеклист по тому, что закладывать при доработках API, парсеров и UI: **[enterprise_resilience.md](enterprise_resilience.md)**.
