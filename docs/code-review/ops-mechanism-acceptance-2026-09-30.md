# Окружение, конфигурация и запуск: проверка механизмов 30.09.2026

**Область:** K07–K09, локальная `main` `05302ff1c4dbe104850116e6206d168ec4fa91d3`.
Production checkout — `367ff336a307ad57d528b26078ca35883ec3de68`.
Наблюдения хоста: 14:59–15:26 UTC; изолированные испытания: 14:56–15:30 UTC.
Production jobs, deployment и изменение серверных настроек не выполнялись.
Подробные списки, SHA и результаты — в [машинном протоколе](ops-mechanism-acceptance-2026-09-30.json).
Первоначальные [27.09](runtime-inventory-2026-09-27.json), [ранний снимок 30.09](runtime-observation-2026-09-30.json)
и [первое backup-учение](backup-acceptance-2026-09-30.md) сохраняют свою дату и границы.

## 1. Что теперь установлено

| Механизм | Основание | Граница результата |
|---|---|---|
| Settings | 160 полей: тип, default expression, строка, 364 прямые ссылки, динамические readers, web/scheduler effective значения и Compose mapping | Наличие поля не означает consumer; секреты заменены признаком configured |
| Compose | Все 7 сервисов, 7 named volumes, 97 interpolation inputs, environment/build/ports/mounts/health/restart/limits | Root `.env` не является автоматическим `env_file` контейнера |
| Production backend | 402 tracked payload-файла внутри web и scheduler побайтово совпали с checkout | Исходники/seed/миграции/fonts/generated/data/config охвачены; loaded Python state и результаты retrain не выводятся из SHA |
| Production frontend | 264 dist-файла, index и 6 ссылок на bundles; nginx config SHA; `docker diff` | Повторная frontend-сборка не выполнялась; отсутствуют изменения dist/nginx в writable layer |
| Caddy | Активный admin JSON равен результату `caddy adapt` `/etc/caddy/Caddyfile`; файл равен checkout | Это проверка загруженного config, а не одного файла на диске |
| DNS/TLS | Apex, `ru.` и `www.` разрешаются; сертификаты прошли обычную chain/hostname проверку с Mac | Не исследованы кабинет DNS, права аккаунта и будущая автоматическая renewal |
| Backup owners/data | Fresh dump восстановлен без `--no-owner`/`--no-privileges`, exit0, 182,967с | Роль `rustats` создана с синтетическим паролем; globals/password/session AOF не восстанавливались |
| Приложение после restore | Настоящий HTTP Uvicorn → restored PostgreSQL + два своих Redis | Email auth/readiness/API/nginx SSR проверены; внешние OAuth, browser и весь DR journey не заявлены |
| Чистый startup | Пустая своя БД → 34 миграции → seed → readiness200 | Scheduler/jobs выключены, CBR calendar недоступен в internal network, Rosstat plan отключён |

У web/scheduler один image ID
`sha256:61bc497c528d6c76b88a220c8d00eae8806b11836c73d701ffd2225b5acb2b95`.
Сравнение всех 402 payload-путей не обнаружило missing или изменённого tracked файла
в writable layer. Изменения директорий/`__pycache__` не считаются изменением их исходников.
От local main отличается только `backend/app/tasks/ticker_worker.py`: проверенный
`git diff 367ff336..05302ff` меняет комментарии/docstring, а не исполняемые выражения.
У scheduler обнаружен download-cache `/app/.cache/eurostat` в writable layer, без
persistent mount: recreating container может удалить этот cache; долговременное
состояние ingest определяется БД и контрактами loader.

## 2. Как настройки доходят до исполнения

`Settings()` создаётся один раз при импорте `app.config`. Здесь нет custom source order,
CLI settings или live reload. Для установленного `pydantic-settings==2.7.1` порядок:
явные аргументы конструктора → process environment → `.env` текущего каталога →
secrets directory при его явной настройке → defaults. В проекте secrets directory
не настроен. Порядок подтверждён локально: default10 → dotenv16 → env17 → argument18;
неизвестное dotenv-поле игнорируется, неверный int отклоняется. `db_pool_size=-1`
проходит Settings type-validation: тип не является положительной границей domain.
Следующие проверки/ограничения нужно искать по consumers, указанным для каждого поля.
[Документация именно 2.7.1](https://raw.githubusercontent.com/pydantic/pydantic-settings/v2.7.1/docs/index.md).

Compose сначала интерполирует `${NAME:-default}` из shell/root `.env`/явного env-файла,
затем передаёт лишь свои `environment` записи и image ENV. Здесь нет общего backend
`env_file`; `.env` исключён `.dockerignore`. Изменение root `.env` не меняет env уже
созданного контейнера: нужно recreate, а для Vite/build args — rebuild.
[Правила Compose](https://docs.docker.com/compose/how-tos/environment-variables/envvars-precedence/).

В `.env.example` **9 имён не входят в текущий Compose interpolation**:

- `PUBLIC_HOST`: историческая переменная, текущий Caddyfile содержит домены явно.
- Settings-only: `RUSTATS_METRICS_TOKEN`, `RUSTATS_SCHEDULER_CRON_HOUR`,
  `RUSTATS_SCHEDULER_CRON_MINUTE`, `RUSTATS_FORECAST_STEPS`,
  `RUSTATS_WORLD_FORECAST_MAX_AGE_DAYS`, `RUSTATS_WORLD_FORECAST_CACHE_BUMP_EVERY`,
  `RUSTATS_WORLD_FORECAST_PRIORITY_COUNTRIES`, `RUSTATS_WEBMASTER_RECRAWL_ENABLED`.

Они могут работать при прямом Python/export/явном override; запись лишь в root `.env`
не передаёт их этому Compose-профилю. У web/scheduler effective metrics token пуст,
поэтому `/api/v1/metrics`403. Токен/collector не включались. Изменённые комментарии
шаблона объясняют mapping; значения и работающая конфигурация не изменены.

Динамические readers: OAuth redirect override выбирается таблицей provider→field;
`scrape_challenge_min_cores` читается через `getattr`. Banxico использует **direct
environment**, а не объявленное Settings-поле: explicit token → три aliases
`RUSTATS_BANXICO_API_TOKEN`, `BANXICO_API_TOKEN`, `BMX_TOKEN` → optional `getattr` → empty.
Неизвестная строка dotenv не экспортируется автоматически в `os.environ`.
В JSON сохранены и поля без прямого/разрешённого динамического reader; они не
выданы за работающие flags.

Frontend `loadEnv`/Vite читает mode-specific и local env; существующий process env
имеет приоритет. Dev-сервер нужно перезапускать, client values входят в build.
`VITE_DEV_API_PROXY` выбирает local API; без него fallback — public origin, все
HTTP methods. `VITE_SENTRY_DSN` имеет source-reader, но текущие Docker build args
его не передают и `.env*` не копируются в build context. Наличие SDK не доказывает
собранный DSN или работающую доставку событий.
[Vite environment](https://vite.dev/guide/env-and-mode.html).

`RUSTATS_DEBUG=false` включает startup diagnostics: insecure cookie/http/dev-password
логируются; это не hard gate. `auth_fake_provider_enabled && !debug` действительно
останавливает startup исключением. В изолированных пробах debug=true, fake provider=false.

## 3. Исполняемые service/host boundaries

Все Compose services используют `restart: unless-stopped`. Web запускает Alembic,
metadata seed и regional seed; ошибка regional seed фатальна при пустой региональной
БД, при имеющихся данных допускается warning. Calendar seed — warning path.
Scheduler role пропускает web migrations/seeds и запускает один worker. Shutdown
останавливает scheduler и закрывает engine/Redis clients.

Публичный путь: DNS → Caddy80/443 (TLS/CSP/body1MB) → loopback3000 → nginx80 →
backend8000 или dist/retained assets. Loopback8000/5434/6380 — API/PG/cache.
State Redis и ClickHouse не публикуют host ports. Volumes сохраняют PG/cache/state,
GeoIP/OG/sitemap/CH; backend output mount read-only, nginx security logs bind RW,
sitemap/retained assets read-only. Их имена, mounts, limits и health start-period
даны отдельно по каждому service в JSON.

Host Caddy, Docker/containerd, cron, fail2ban и Tor active; Caddy исполняет
`/usr/bin/caddy run --config /etc/caddy/Caddyfile` пользователем caddy. Ubuntu24.04.4,
KVM/QEMU; `vm.swappiness=60`, `overcommit_memory=0`, `somaxconn=4096`, range32768–60999,
`tcp_fin_timeout=60`. UFW inactive, iptables INPUT/OUTPUT ACCEPT и FORWARD DROP
с Docker/fail2ban chains. Это не свидетельство внешней provider-firewall политики.
Host ports дополнительно: SSH22, resolved53, Caddy admin2019 loopback,
Zabbix10050 wildcard, Tor9050 loopback+Docker gateway, HTTP bridge8888 на gateway.
Списки заблокированных IP и реальные identity-строки не собирались.

**Важная дельта logrotate:** source `deploy/fail2ban/logrotate-rosstat-nginx` —
daily/7/nocompress/rename+USR1; effective `/etc/logrotate.d/rosstat-nginx` —
daily/14/compress/delaycompress/copytruncate. Host ещё использует старый механизм,
разбор исходника не заменяет его выпуск. Fail2ban limits повторно прочитаны:
42930/600s→86400s, volume80/600s→86400s, honeytrap1/3600s→172800s,
recidive2/86400s→604800s. Nginx собственные limits и адресный Alibaba deny отдельны.

**Найден внешний к Git исполняемый producer:** `tor-http-bridge.service` и
`/opt/tor-http-bridge/tor_http_bridge.py` (167 строк прочитаны). Gateway172.18.0.1:8888
→ local Tor SOCKS9050, Basic auth, CONNECT-only; ошибки407/501/502; unit root,
Restartalways/5s, ProtectSystem=strict/ProtectHome=true. Credential захардкожен;
лог первых400bytes headers включает Proxy-Authorization. Это конкретный текущий
дефект, не гипотеза. В опубликованном snapshot assignments credentials заменены
на `<redacted>`, исходный SHA сохранён. Без этого отдельного host-механизма ссылка
`openrouter_proxy_url` не объясняла egress. Сетевой вызов к платному LLM не выполнялся.

Docker JSON logs ограничены service settings; nginx файловые логи ротируются отдельно,
host proxy пишет journald. Root cron `0 4 * * *` читает checkout backup-script;
host timezone UTC, поэтому это07:00МСК. Health/metrics, heartbeat30h, ETL freshness36h,
FD pressure80%, fail-open counters и их consumers объяснены в system/main/cache
и основных документах. Fresh heartbeat не подтверждает читаемость dump/offsite.

## 4. Бюджет общего хоста

Семь hard RAM limits дают7616MiB; физически7941,195MiB, разность≈325MiB.
Это арифметика возможных максимумов, не reservation и не текущая свободная память.
CPU quotas3(web)+1(scheduler)+0,5(nginx)+0,5(CH)=**5CPU на общем4vCPU хосте**;
PG/обаRedis и host не имеют этой CPU-квоты. Cpuset нет: ядра не закреплены.
Workers и CPU quota — разные параметры. Наблюдались16–17 OS threads у web worker
и13 у scheduler; число threads не означает одновременно runnable CPU или capacity.
[Смысл ограничений Docker](https://docs.docker.com/engine/containers/resource_constraints/).

Connection ceilings: web3×(8+7)=45; scheduler6+6=12; analytics4×(2+2)=16;
всего73. При100 connections и3 reserved консервативный ordinary запас24.
**Фактический app-role rustats — superuser**, поэтому reserved slots не защищены
от этого приложения; это budget guidance, а не enforced least-privilege isolation.
CLI/migrations/backup тоже требуют соединений. Pools открывают их по потребности.

Пример, а не измерение: shared_buffers896 + одна work_mem16 операция×73=1168 +
3 autovacuum×128=384 + одна maintenance256 =2704MiB; остаётся368MiB до PG3GiB
для процессов/буферов и остальных операций. Несколько plan nodes, hash multiplier
и parallel workers могут превысить эту модель. `effective_cache_size2304MiB`
не является allocation. PG/CH/WAL/Docker/backups/logrotate/swap/asset archive делят
один диск. ROTA1 на виртуальном block device не определяет physical storage/IOPS.

## 5. Пробы и их точные границы

Fresh dump434247670bytes с SHA из предыдущего pull восстановлен без подавления
owner/ACL:182,967с, exit0,58 public tables + research.source_catalog, head
`20260927_world_nonzero_idx`, все table owners rustats, nondefault table ACL0.
Роль заранее создана с синтетическим паролем как observed Compose superuser.
`pg_dump` не содержит role passwords/globals; нулевые ACL не доказывают replay
несуществующих специфических grants. [pg_restore16](https://www.postgresql.org/docs/16/app-pgrestore.html).

На restored DB и двух своих Redis current backend прошёл:

- Live/ready200; DB/cache/stateok, отсутствие backup-heartbeat=`never` без degradation.
- CPI data200:8 точек2026; USD200:20 последних точек; world countries200.
- Synthetic register201; login/me200; неверный пароль401.
- Own cache `FLUSHDB` сохранил state-session; logout безCSRF403, сCSRF204, затем me401.
- Остановка **своего** state Redis дала readiness503; restart вернул200.
- Current nginx: API ready200, unauthenticated me401, CPI/currency SSR200,
  все6 shell assets200, HTML no-cache; legacy Russia currency URL301.

Первый nginx probe использовал ошибочный `/api/health/ready` без `/v1` и получил404;
проверка исправлена на настоящий `/api/v1/...`. Первичная SQL-проба clean DB ошибочно
называла `regional_data`; corrected actual `region_data` подтвердил counts. Эти
ошибки probes сохранены в JSON, не названы дефектами приложения.

Пустая отдельная `fe_clean`:34 migrations,947 indicators,961494 region points,
users0,438 calendar events, live/ready200. CBR DNS в internal network не разрешался;
fallback/error-calendar путь позволил startup. Seed не равен свежему ETL факту.
Приложение исполняло current tracked backend из read-only copy поверх existing
Sep26 dependency image. Nginx config current; client JS/CSS — existing local image.
Эти пробы не заявляют fresh dependency build, current frontend browser acceptance,
production auth или full failover.

Все6 своих containers, volume и internal network удалены после проверки labels,
точных IDs/mounts, отсутствия ports и exclusive network members. Другие15 container
IDs сохранены. Raw logs/source остаются в private каталоге вне Git.

## 6. Остаток знания отделён от свойств и решений

В JSON каждый остаток имеет ID, объект, класс, проверенные источники, недостающее
основание и следующий способ проверки:

- **OPS-U01 unavailable:** provider control panel/backups/firewall/SLA/physical storage.
  SSH показывает VM/host, но не доступ к этим account-level сведениям.
- **OPS-U02 future observation:** launchd08:15 mechanism зарегистрирован, manual pull
  принят; следующий scheduled invocation ещё не наблюдался. `launchctl list` last exit1
  относится к прежнему launchd invocation и не отменяет отдельный manual success.
- **OPS-U03 unmeasured property:** capacity/p95/p99/full RTO; limits и restore-time
  не являются обещанным результатом смешанной production-нагрузки.
- **OPS-U04 unaccepted decision:** бизнес-цели RPO/RTO не согласованы.
- **OPS-U05 unmeasured wider journey:** original Redis AOF, CH resync, external OAuth
  и browser восстановление всей платформы не проверены bounded DB/auth drill.

Доступное устройство перечисленных механизмов объяснено; недоступный provider
контур остаётся явным ограничением K08/K09. Кодовые контракты внешних экономических
источников и UI имеют отдельные inventories; этот ops-протокол их не подменяет.
