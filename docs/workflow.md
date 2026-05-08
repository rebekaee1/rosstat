# Рабочий процесс — Forecast Economy

**Last updated:** 2026-05-07.
**Part of:** [`../AGENTS.md`](../AGENTS.md), [`../CONTEXT.md`](../CONTEXT.md).
**See also:** [`enterprise_resilience.md`](enterprise_resilience.md) (чеклист канарейки), [`adr/`](adr/) (архитектурные решения).

## Модель работы

Раньше работа шла по **фазам** (план `forecast_economy_v2`, фазы 0–4). Все фазы закрыты к концу апреля 2026. Сейчас работа идёт по двум потокам:

- **Архитектурные кандидаты** — большие deepening-рефакторы (`refactor/...` ветки): calculation_engine pure ops + DerivedSpec, BaseParser template-method, forecast strategies registry, indicator metadata в БД, SEO single-source, IndicatorDetail декомпозиция и т.п. Фиксируются в `docs/adr/` (нумерованные ADR).
- **Точечные правки по обратной связи** — конкретные баги/правки от Никиты или собственного аудита (CPI квартальная вкладка, GDP nominal/real split, weekly forecast, calendar rolling 12-мес и т.п.). Идут в `feat/...` или `fix/...` ветках, мерджатся в `main` через `--no-ff`.

Любая правка должна проходить регламент ниже. Ничего «полу-готового» в `main`.

## Git и окружения

- **GitHub (`git push origin main`)** — основной способ фиксировать прогресс; коммиты должны быть **согласованы** с тем, что реально сделано.
- **Прод-сервер** (`5.129.204.194`, `/opt/rosstat`) — **не деплоить автоматически** и **не без явного запроса**. Разработка и проверка — локально (Docker Compose) и через CI; выкладка на сервер — отдельным шагом по команде.
- **Перед каждым прод-деплоем** — обязательный `pg_dump | gzip > /opt/rosstat/backups/pre-deploy-$(date +%Y%m%d-%H%M%S).sql.gz`. См. `scripts/pg-backup.sh` и стандарт ниже.

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

### Headless E2E (puppeteer-core + system Chrome)

Для регрессионных smoke-чеков (особенно после прод-деплоя):

```bash
node scripts/e2e/smoke.mjs --target=https://forecasteconomy.com  # пример
```

Проверяет 6+ ключевых страниц на **0 console errors, 0 page errors, 0 4xx/5xx**. Скриншоты в `/tmp/e2e-prod/screens/`. Этот формат используется как «Smoke C» после прод-деплоя — см. ниже.

Если dev-сервер недоступен в среде — явно записать что проверено альтернативно (только unit-тесты / только snapshot-тесты / только curl-сверка SSR).

## Прод-деплой

Стандартная процедура (через SSH из агента, по explicit команде пользователя):

1. `git push origin main` — закатить ветку.
2. `pg_dump | gzip > backups/pre-deploy-$(date +%Y%m%d-%H%M%S).sql.gz` — на проде.
3. `git pull --ff-only` на `5.129.204.194:/opt/rosstat`.
4. `docker compose build backend frontend` — **оба образа всегда вместе** (см. «Asset-hash mismatch trap» в `enterprise_resilience.md`).
5. `docker compose up -d backend frontend` — **одновременно** (страховка от asset-hash mismatch).
6. Alembic миграции применяются автоматически из `entrypoint.sh`.
7. `redis-cli FLUSHDB` — если правки касались форматирования/SSR.

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
