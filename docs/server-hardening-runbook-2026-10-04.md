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

**Репетиция на тестовом сервере, 2026-10-04.** Роль создана `scripts/db-roles.sh`, backend и scheduler пересозданы
(приложение под `rustats_app`, миграции — под `rustats`), `health/ready` 200, в журналах `permission denied` нет.
Под новой ролью вручную прошли `behavior_retention_job`, `staleness_check_job`, `analytics_daily_job`; нагрузочный
прогон (около 7 тыс. запросов) — без ошибок 5xx. `scripts/db-roles.sh --verify` показал роль без суперпользователя и
отказ `CREATE TABLE`. Репетиция нашла две ошибки самой проверки (выход при `set -e` без `|| true`; ложный отказ из-за
`| grep -q` под `pipefail`) — исправлены. Не проверялось на тесте: `scripts/pg-backup.sh` под новой ролью (он идёт под
`rustats` внутри контейнера PostgreSQL), вход пользователей и регистрация (на тесте нет пользовательских таблиц).

## F09 — настройки Redis, токен метрик

- `REDIS_CACHE_POLICY=volatile-lru` в боевом `.env` (сейчас `allkeys-lru`): ключи версий `fe:ver:*` без TTL не должны вытесняться; все остальные кэш-ключи имеют TTL.
  `docker compose up -d redis` пересоздаёт cache-Redis (state-Redis — отдельный сервис и не затрагивается).
- `RUSTATS_METRICS_TOKEN` пуст, endpoint метрик отвечает 403: сгенерировать токен (`openssl rand -hex 24`), записать в `.env`, перезапустить backend; затем подключить сборщик (если нужен).
- Offsite-копия бэкапов (`OFFSITE_S3_BUCKET`) требует бакета и ключей владельца — **без них не настраивается**; пока копия на Mac (`~/bin/fe-backup-pull.sh`) единственная вне сервера.

## F08 — ротация nginx-логов

`scripts/install-host-logrotate.sh` (dry-run → установка, старый конфиг сохраняется): `rename` вместо `copytruncate`, `USR1` контейнеру nginx, 7 дней без сжатия.
Причина: gzip + `copytruncate` держали I/O и роняли SQL-запросы; `security.log` — 250 МБ/сут. Проверка утром после 00:00: новые `*.log.1`, `nginx -t`, `fail2ban-client status`.

## Круг починки 27.10.2026: подготовка хоста без применения (агент №4)

Замеры сделаны только чтением на `fe-prod` 27.10; на хосте **ничего не менялось**. Каждый скрипт по умолчанию
`--dry-run`, имеет явный откат, проверен в контейнере Ubuntu 24.04 (ufw 0.36, logrotate 3.21 — как на проде) или локально
с заглушками системных команд. Рекомендуемый порядок: диск → logrotate → F10 → Zabbix → фаервол последним (самый рискованный).

| Что | Скрипт / файл | Откат | Что проверено и что нет |
|---|---|---|---|
| Первая чистка кэша Docker и потолок journald | `scripts/docker-cleanup.sh` (`--dry-run`, затем запуск; `df -h /` до и после), `scripts/install-host-disk-hygiene.sh` | `--rollback` убирает drop-in и cron; удалённые журналы и кэш не вернуть, кэш пересоберётся | Синтаксис. Сколько освободит кэш — 4…16 ГБ, точно покажет запуск (сумма записей 3,9 ГБ, «reclaimable» 16,1 ГБ) |
| logrotate nginx (F08 с сжатием) | `deploy/fail2ban/logrotate-rosstat-nginx` + `scripts/install-host-logrotate.sh` | `--rollback` возвращает `*.before-f08-*` | На logrotate 3.21: разбор, rename, `delaycompress`, `ionice -c3 nice -n19 gzip -6` даёт валидный gzip, владелец 101:101, USR1. Не проверено: время сжатия настоящих ~360 МБ и влияние на Postgres |
| F10 Tor-мост | `scripts/host-tor-bridge-f10.sh`, `deploy/tor-http-bridge/README.md` | `--rollback` (вернёт и старый пароль в файле) | Настоящий `tor_http_bridge.py` против поддельного SOCKS5: без пароля 407, с паролем 200, неверный пароль 407, заголовки в лог не попадают. На хосте не запускалось |
| Zabbix-агент не читает секреты | `scripts/host-zabbix-denykey.sh` | `--rollback` из `zabbix_agentd.conf.before-denykey` | Вставка строк, идемпотентность, откат — на заглушке агента. На настоящем zabbix_agentd 5.0.3 не запускалось |
| Фаервол ufw | `scripts/host-firewall-ufw.sh` | страховка (ufw сам выключится через 10 мин без `--confirm`), `--rollback`, `--reset` | В контейнере с NET_ADMIN: все правила принимаются, `ufw enable` работает, `--apply` с автооткатом при потере Tor, `--confirm`, `--rollback`. Не проверено: настоящий хост с Docker и fail2ban (порядок цепочек), доступ по ssh |

**Фаервол — что нашли.** ufw inactive, `iptables INPUT = ACCEPT`. Снаружи слушают 22/tcp, 80/tcp, 443/tcp и **443/udp** (HTTP/3 Caddy),
10050/tcp (zabbix-agent, `Server=92.53.116.12,92.53.116.111,92.53.116.119`). Порты Docker опубликованы на `127.0.0.1`. Контейнеры ходят
на хост: `172.18.0.1:9050` (Tor SOCKS для ETL Росстата/Минфина, `RUSTATS_ETL_SOCKS_PROXY_URL`) и `172.18.0.1:8888` (резервный мост) —
ufw их разрешает для `172.18.0.0/16`, иначе пропадёт Tor-маршрут. Политика переадресации `allow routed`: пересылку контейнеров ведёт Docker.
Порядок применения: второе ssh-окно, `--apply`, проверка нового ssh-подключения и сайта, `--confirm`. `limit` на 22 не ставится
(много параллельных ssh-сессий). Что неизвестно: нужен ли внешний доступ на другие порты (на хосте их не слушает ничего, кроме перечисленных).

**gsc-oauth.json — кто владелец.** `/etc/rosstat-secrets/gsc-oauth.json`, 0600, uid:gid 999:999, каталог 0700. Смонтирован только в `scheduler`
(`/opt/rosstat/docker-compose.override.yml` — вне Git, создан 08.10 для job `gsc_search_queries`). 999 — это uid `appuser` внутри контейнера;
приложение (`gsc_client.read_credentials`) требует режим 0600 и должно прочитать файл, поэтому владельцем обязан быть 999. На хосте имя
«zabbix» — совпадение номеров (zabbix_agentd работает от него, группа 999 = systemd-journal). Реальный риск: агент может читать файл (в конфиге
запрещён только `system.run[*]`), и элемент `vfs.file.contents[...]` с сервера мониторинга вернул бы секрет. Поэтому владельца не меняем, а запрещаем
агенту `vfs.file.contents/regexp/regmatch` (`host-zabbix-denykey.sh`). Конфиг ведёт Timeweb (`timeweb_config_version`) — при перезаписи повторить.
Альтернатива, не рекомендуемая сейчас: сменить uid `appuser` в образе (перепись владельцев томов og_cache/sitemap/geoip). Override-файла в репозитории нет:
mount несуществующего файла Docker превратит в каталог, поэтому он остаётся локальной добавкой хоста; его наличие теперь описано здесь.

**F10 — находка сверх задачи.** Пароль в `RUSTATS_OPENROUTER_PROXY_URL` (боевой relay `5.129.210.89:8888`) совпадает со старым зашитым паролем
моста (сравнение хэшей на хосте, значение не выводилось). Старый пароль лежал в файле 0644 и 7 раз попал в журнал (27.08). Ротация пароля только на
хосте боевой путь Pulse не закрывает: пароль relay меняет владелец на самом relay и в `/opt/rosstat/.env`.
