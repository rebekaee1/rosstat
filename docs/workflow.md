# Рабочий процесс — Forecast Economy

**Last updated:** 2026-07-06 (CTO-аудит, Волна 5: прод-IP актуализирован — 201.51.11.170 (переезд 2026-07-03, старый 5.129.204.194 упразднён); прод-деплой переведён на `scripts/deploy.sh` — preflight-бэкап, ff-only guard, версионированные образы с автооткатом, расширенный smoke (SSR asset-hash / data-endpoint / OG), Caddy reload после smoke; ETL идёт двумя прогонами (06:00 и 20:00 МСК) + late-Minfin 15:00; smoke-набор дополнен readiness `/health/ready`; E2E-runner `scripts/e2e/smoke.mjs` реализован (Playwright, 5 сценариев + YandexBot SSR-suite) и включён в CI. Ранее 2026-05-22: добавлен ручной ETL recipe, `_catch_up_empty_indicators` + `redis-cli FLUSHDB`.)
**Part of:** [`../AGENTS.md`](../AGENTS.md), [`../CONTEXT.md`](../CONTEXT.md).
**See also:** [`enterprise_resilience.md`](enterprise_resilience.md) (чеклист канарейки 6/6), [`../AGENTS.md::Шаг 4`](../AGENTS.md) (чеклист «новый индикатор» 7/7 — другая ось), [`adr/`](adr/) (архитектурные решения).

## Модель работы

Раньше работа шла по **фазам** (план `forecast_economy_v2`, фазы 0–4). Все фазы закрыты к концу апреля 2026. Сейчас работа идёт по двум потокам:

- **Архитектурные кандидаты** — большие deepening-рефакторы (`refactor/...` ветки): calculation_engine pure ops + DerivedSpec, BaseParser template-method, forecast strategies registry, indicator metadata в БД, SEO single-source, IndicatorDetail декомпозиция и т.п. Фиксируются в `docs/adr/` (нумерованные ADR).
- **Точечные правки по обратной связи** — конкретные баги/правки от Никиты или собственного аудита (CPI квартальная вкладка, GDP nominal/real split, weekly forecast, calendar rolling 12-мес и т.п.). Идут в `feat/...` или `fix/...` ветках, мерджатся в `main` через `--no-ff`.

Любая правка должна проходить регламент ниже. Ничего «полу-готового» в `main`.

## Git и окружения

- **GitHub (`git push origin main`)** — основной способ фиксировать прогресс; коммиты должны быть **согласованы** с тем, что реально сделано.
- **Прод-сервер** (`201.51.11.170`, `/opt/rosstat`; DNS `forecasteconomy.com`) — **не деплоить автоматически** и **не без явного запроса**. Разработка и проверка — локально (Docker Compose) и через CI; выкладка на сервер — отдельным шагом по команде.
- **SSH на прод — только по ключу** (с 2026-08-27): `ssh fe-prod` (алиас в `~/.ssh/config`) или явно `ssh -i ~/.ssh/id_ed25519_fe_prod root@201.51.11.170`. Парольный вход отключён (`/etc/ssh/sshd_config.d/00-hardening.conf`: `PermitRootLogin prohibit-password`, `PasswordAuthentication no`; бэкап старого конфига — `/etc/ssh/sshd_config.bak-keyauth`). Ключ только у владельца; потеря ключа = восстановление через панель провайдера (VNC/rescue).
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

Стандартная процедура (через SSH из агента, по explicit команде пользователя):

1. `git push origin main` — закатить ветку.
2. `ssh root@201.51.11.170 'bash /opt/rosstat/scripts/deploy.sh'` — скрипт сам делает: preflight `pg-backup.sh` (hard fail при провале), dirty-guard + `merge --ff-only`, сборку **обоих** образов вместе (asset-hash trap) с тегом = SHA, `up -d`, ожидание `/health/ready` (до 300s: alembic + сидеры из `entrypoint.sh`), расширенный smoke (data-endpoint, SSR ссылается на реально существующие ассеты, OG-картинка), Caddy reload **после** smoke, автооткат на предыдущий SHA при провале.
3. Backend на старте автоматически прогоняет `_catch_up_empty_indicators()` — ETL для всех `is_active=true` индикаторов с 0 точками; провалы алертятся в Telegram.
4. `redis-cli -n 0 FLUSHDB` — если правки касались форматирования/SSR, добавлены derived (forecast retrain trap), или изменился `seo_renderer.py`. Только DB 0 — кэш; DB 1 = state (сессии), не трогать.
5. Если деплой добавляет новые derived (`DERIVED_SPECS` пополнен): `docker compose exec backend python -c "import asyncio; from app.services.forecaster import retrain_indicator_forecast; asyncio.run(retrain_indicator_forecast('<source_code>'))"` для каждого изменённого источника. Daily ETL не подхватит автоматически (см. `enterprise_resilience.md::forecast retrain trap`).

### Smoke C — проверки после деплоя

Минимальный набор curl/SSR-сверок (первые четыре пункта `deploy.sh` делает сам):

- `GET /api/v1/health/ready` → 200 (реальный readiness: БД + оба Redis + планировщик).
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

## Двуххостовый языковой cutover

`ru.forecasteconomy.com` является русским каноном, apex — английским после
`RUSTATS_APEX_LOCALE_EN=true`. Это один флаг для backend и frontend build;
отдельный `VITE_APEX_LOCALE_EN` в окружении запрещён. Язык страницы = хост:
IP, VPN и `Accept-Language` в выборе языка не участвуют (решение владельца
2026-08-31 — geo-редирект давал разное поведение с VPN и без). Cookie
`fe_locale_pref` — только память явного выбора переключателя, не источник
редиректа. Перед релизом обязательны `python3 scripts/dual-host-release-gate.py`
и полный `./scripts/check-all.sh`. Поисковые роботы, API, sitemap, robots,
RSS, OG, embed, health и OAuth callback отвечают на запрошенном хосте.
Явный выбор языка хранится год в cookie `fe_locale_pref` с Domain
`.forecasteconomy.com`.
