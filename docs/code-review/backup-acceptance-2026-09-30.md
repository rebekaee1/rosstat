# Сохранность: приёмка 2026-09-30

**Основание:** существующий завершённый daily backup сервера. Production только читался; серверный backup/job, deploy, restart и изменение настроек не запускались. Локальная main `972579f`; серверный чистый checkout `367ff336a307ad57d528b26078ca35883ec3de68`. [Машинный протокол](backup-acceptance-2026-09-30.json), [ops-снимок](runtime-observation-2026-09-30.json), [исходный снимок 27.09](runtime-inventory-2026-09-27.json).

## 1. Доставка свежей копии

Ошибки локального `~/bin/fe-backup-pull.sh` за 27–30.09: `Broken pipe` / `Connection closed`. Независимое SSH-соединение работало при диагностике; единственная причина старых отказов не установлена. Исходный скрипт сохранён рядом как `fe-backup-pull.sh.before-20260930T133007Z`. Изменены SSH options: `ControlMaster=no`, `ControlPath=none`, keepalive 15 с ×2, connect timeout 20 с. `bash -n` успешен. launchd расписание **08:15 МСК** сохранено.

Ручной pull **16:30:24–16:32:38 МСК** завершился успешно. Каталог Mac: `~/Backups/forecasteconomy`; журнал `pull.log`. Размеры и SHA-256 сравнивались с сервером:

| Файл | Размер, байт | SHA-256 |
|---|---:|---|
| `rustats_20260930_040001.dump` | 434247670 | `729783e7e419f62b44f461bc4eec307db9d853576dca8b180563730022ea8211` |
| `rustats_20260930_040001.identity.sql.gz` | 37171 | `d19b2c88efde57bf03a8163cab6ee2b8f503aa17ae7edf2d33eca306fe8e9067` |

`pg_restore --list`: 529 TOC entries / 59 TABLE DATA; `gzip -t` успешен, `.verified` создана. Предыдущая проверенная копия 26.09 сохранена. Повтор **16:43:47 МСК** обнаружил уже проверенную пару и пропустил скачивание; он не выполнял новый полный restore. Следующий плановый запуск после исправления ещё не наблюдался.

## 2. Изолированное восстановление

Отдельные контейнер и volume `fe_restore_drill_20260930t133353z`, label `fe.acceptance.owner=rosstat-backup-acceptance-2026-09-30`; PostgreSQL 16.11, образ `postgres:16-alpine`, CPU1 / RAM1 GiB, `network=none`, без host ports, backup mount read-only. Существующие локальные и серверные БД не использовались как target.

Полный dump восстановлен через `pg_restore --exit-on-error --no-owner --no-privileges`: **13:34:14–13:36:49 UTC, 154,885 с, exit0**. Размер восстановленной БД 5963862499 байт. 58 public-таблиц плюс `research.source_catalog` (17264 строки); Alembic `20260927_world_nonzero_idx`. Числа всех 59 таблиц сохранены в JSON; это содержимое backup на 04:00 UTC, не контрольный снимок live-БД в 16:40.

| Контроль | Результат |
|---|---:|
| `world_data_points` | 16191915 |
| `subnational_data_points` | 4476315 |
| `region_data` | 961494 |
| `indicator_data` | 311759 |
| `users` / `oauth_identities` / `email_credentials` | 118 / 43 / 75 |
| `consents` / `auth_audit` | 194 / 205 |
| Невалидированные constraints | 0 |
| Identity-сироты по четырём FK | 0 по каждому |
| Дубли `(indicator_id,date)` в `indicator_data` | 0 |

Контрольные ряды: CPI 428 точек, 1991-01-01…2026-08-01; USD/RUB 7132 точки, 1998-01-01…2026-09-30. Эти проверки обнаруживают повреждение/потерю выбранных данных, но не подтверждают методологию каждой экономической точки.

**Отдельный identity restore:** другая пустая БД `fe_identity_drill` в том же изолированном контейнере, совместимая schema-only из full dump, затем `.identity.sql.gz` через `psql -X -v ON_ERROR_STOP=1`. Exit0, числа пяти таблиц совпали с full dump, FK-сирот и невалидированных constraints нет. Data-only SQL не накладывался поверх наполненной БД.

После записи результата отдельно проверены owner labels контейнера и volume, отсутствие ports, `network=none`, точный собственный PG-том. **13:45:32 UTC** удалены только эти два ресурса; последующий inspect подтвердил их отсутствие.

## 3. Что известно о сервере 30.09

4 vCPU / 7,75 GiB RAM; свободно ≈16,65 GiB на `/` (79% занято), swap used ≈0,40 GiB. Семь контейнеров healthy, restart0, OOMfalse; readiness web/scheduler `ok`, `degraded=false`. Это моментальный снимок, не нагрузочная приёмка. Backup каталог 92 файла / ≈15,61 GiB, cron04:00 UTC /07:00 МСК; full dump завершён04:02:14 UTC.

S3 bucket/endpoint не настроены, `aws` CLI отсутствует. Mac — подтверждённая отдельная копия данного backup, доступность и расписание которой зависят от локальной машины. Backup провайдера и иной offsite механизм не проверены. Effective web `metrics_token` пуст: инструментация в коде есть, рабочий scrape не подтверждён; production настройки не менялись.

## 4. Границы результата

- Исходные owners/ACL не воспроизводились; application login, API, SSR и jobs на восстановленной БД не запускались.
- Полный failover, потеря VPS, WAL/PITR, целевые RTO/RPO и долговременная доступность offsite не приняты. 154,885 с — только время pg_restore.
- Свежая полная live-схема и каждый файл работающих images не аттестованы; семь хэшей подтверждают выбранные файлы checkout.
- Capacity, p95/p99, IO/swap rates и работа всех scheduled jobs не измерялись.

Следующие отдельные шаги: наблюдать очередной launchd pull; согласовать независимое offsite хранение и RTO/RPO; провести application acceptance на изолированной копии; затем полный сценарий восстановления сервиса с owners/ACL/config/TLS/state и measured RTO. Текущий протокол не разрешает автоматически менять production.
