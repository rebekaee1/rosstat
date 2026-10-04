# Серверные пакеты F08, F09, F10, F13 — подготовка и порядок выполнения

Датировано 2026-10-04. Владелец разрешил менять сервер по этим дефектам; перед каждым выполнением на **боевом** сервере владельцу
показывается этот список и ждётся «да». Всё ниже **подготовлено и проверено на тестовом сервере или локально**, на боевом
(`fe-prod`) не выполнялось. Порядок по важности и риску: F10 → F13 → F09 → F08.

| № | Что | Риск окна | Откат | Где проверено |
|---|---|---|---|---|
| F10 | Tor-мост без зашитого пароля и без логирования заголовков; новый пароль | нет (мост — резерв) | вернуть `tor_http_bridge.py.before-f10`, `systemctl restart` | юнит-тесты `scripts/tests/test_tor_http_bridge.py`; на хосте не запускалось |
| F13 | Приложение под ролью `rustats_app` без прав суперпользователя | перезапуск backend/scheduler (~1 мин) | убрать две строки из `.env`, `docker compose up -d` — вернётся роль `rustats` | репетиция на тестовом сервере (раздел ниже) |
| F09 | `REDIS_CACHE_POLICY=volatile-lru`, токен метрик | перезапуск cache-Redis: кэш пуст, 5–10 мин медленнее | вернуть значение в `.env`, `docker compose up -d redis` | прежняя политика прод: `allkeys-lru` |
| F08 | `scripts/install-host-logrotate.sh` на хосте | нет (меняется конфиг; ротация в 00:00) | вернуть `/etc/logrotate.d/rosstat-nginx.before-f08-*` | dry-run `logrotate -d` |

## F10 — Tor-мост

См. [deploy/tor-http-bridge/README.md](../deploy/tor-http-bridge/README.md): новые файлы, новый пароль в `/etc/tor-http-bridge.env` (0600),
очистка журнала. Проверка: 407 без пароля, в журнале нет `Proxy-Authorization`.

## F13 — роль приложения без прав суперпользователя

Сейчас: приложение подключается под `rustats` — bootstrap-суперпользователем контейнера PostgreSQL. Следствия: уязвимость SQL-инъекции
или кода в приложении даёт полный доступ к серверу БД (чтение файлов, `COPY PROGRAM`, DDL), а `reserved connections` не защищают админа
от исчерпания соединений приложением.

Решение (минимальное, без переноса данных и владения): `scripts/db-roles.sql` создаёт `rustats_app` — `LOGIN NOSUPERUSER`, DML на все таблицы,
`USAGE/SELECT/UPDATE` на последовательности, `TEMPORARY` и `pg_read_all_stats`, `CONNECTION LIMIT 80`, без `CREATE` на схеме; default privileges дают те же
права на объекты, которые создаст владелец миграциями. Владелец объектов и роль миграций остаются `rustats` (alembic использует
`RUSTATS_MIGRATION_DATABASE_URL`, в compose всегда под `rustats`). Приложение переключается значениями `RUSTATS_APP_DB_USER/PASSWORD` в `.env`.

```bash
# на сервере, /opt/rosstat — сначала свежий бэкап (scripts/pg-backup.sh), затем:
scripts/db-roles.sh            # создаёт роль, дописывает RUSTATS_APP_DB_USER/PASSWORD в .env (пароль не печатается)
docker compose up -d --force-recreate backend scheduler
scripts/db-roles.sh --verify   # роль не суперпользователь, подключение работает, CREATE TABLE запрещён
```

Приёмка после переключения: `health/ready` 200 на обоих хостах; в логах backend/scheduler нет `permission denied`; ручной прогон ключевых задач
(ежедневный ETL, sessionize, sitemap_build, sitemap, ClickHouse-синхронизация); вход пользователя и регистрация; `scripts/pg-backup.sh` (идёт под `rustats` внутри контейнера).
Откат: удалить две строки из `.env`, `docker compose up -d --force-recreate backend scheduler`.

## F09 — настройки Redis, токен метрик

- `REDIS_CACHE_POLICY=volatile-lru` в боевом `.env` (сейчас `allkeys-lru`): ключи версий `fe:ver:*` без TTL не должны вытесняться; все остальные кэш-ключи имеют TTL.
  `docker compose up -d redis` пересоздаёт cache-Redis (state-Redis — отдельный сервис и не затрагивается).
- `RUSTATS_METRICS_TOKEN` пуст, endpoint метрик отвечает 403: сгенерировать токен (`openssl rand -hex 24`), записать в `.env`, перезапустить backend; затем подключить сборщик (если нужен).
- Offsite-копия бэкапов (`OFFSITE_S3_BUCKET`) требует бакета и ключей владельца — **без них не настраивается**; пока копия на Mac (`~/bin/fe-backup-pull.sh`) единственная вне сервера.

## F08 — ротация nginx-логов

`scripts/install-host-logrotate.sh` (dry-run → установка, старый конфиг сохраняется): `rename` вместо `copytruncate`, `USR1` контейнеру nginx, 7 дней без сжатия.
Причина: gzip + `copytruncate` держали I/O и роняли SQL-запросы; `security.log` — 250 МБ/сут. Проверка утром после 00:00: новые `*.log.1`, `nginx -t`, `fail2ban-client status`.
