# Границы знания и подтверждённые проблемы

## Локальное уточнение F05/F06 — 2026-09-30

После `main 83c4555` исправляются воспроизведённые границы расчёта PG сессий
и поздние commits обычных append event writers в CH-копию.
[Приёмка](code-review/analytics-boundaries-acceptance-2026-09-30.md) различает
actual PG/CH, герметические doubles и ресурсные наблюдения. Исходные F05/F06
строки ниже остаются историей дефектов. Гарантия F06 требует READ COMMITTED,
автоматических возрастающих CACHE 1 ids без manual writes/sequence reset;
catch-up v2 выполняется постепенно. F05 не обещает произвольный старый backfill
за пределами штатного lookback или восстановление удалённого raw history.

**F05b закрыт локально 2026-10-04 (не выпущен):** durable журнал
`server_session_changes` + применение удалений/старых правок в CH
(см. [backlog](backlog.md#f05b-session-changes-2026-10-04),
[контракт](data-contracts.md#f05b-session-копия-и-журнал-изменений)). Не проверено:
реальные PG/CH-тесты, `ALTER DELETE` на объёме production, часовой пояс
`started_at` в CH (см. контракт), накопленные до выпуска призраки (нужен один
`resync()`), межпроцессный fencing (F07). Исходная формулировка дефекта:
CH session-copy сохраняет удалённые PG keys и не копирует
старое carry. Нужны durable mutation/deletion и generation/ack snapshot либо
tombstones; разовый resync этого постоянно не решает. SQL historical readwork,
exact-distinct memory, общее расписание на 4 vCPU и production release
остаются непроверенными. Документальная текущесть не закрывает эти границы.

## Локальное уточнение F03 — 2026-09-30

После `main c2a883d` воспроизведённые count/content, destructive startup,
metadata rollback, terminal EMISS publication и fixed API/OG key дефекты
исправлены локально: [приёмка](code-review/regional-publication-acceptance-2026-09-30.md).
Строка F03 ниже сохраняет первоначальное основание. Открыты per-point
provenance существующих месячных значений, обновление их из нового артефакта,
crash recovery между SQL/Redis, обновление static sitemap и production release.


Срез 30 сентября 2026. Основная [приёмка](project-knowledge-acceptance.md) различает
устройство, риск в конструкции и фактически наблюдавшуюся потерю/сбой.
Этот реестр не является delete-list или принятой новой архитектурой.

## Подтверждённые механизмы, требующие отдельного исправления

**Текущий локальный статус F01/F02/F04, 30.09:** реализован пакет защиты истории
и публикации после commit; [контракт и приёмка](code-review/history-publication-acceptance-2026-09-30.md).
Таблица сохраняет исходные воспроизведённые дефекты. Пакет не выложен на сервер;
crash-durability, DB0 cache outage и unknown commit outcome не закрыты.

| ID | Что известно | Следующая проверка/действие |
|---|---|---|
| F01 | Непустой частичный national response удаляет сохранённые даты вне ответа; empty response сохраняет историю | Явный complete/partial scope и merge/replace, затем реальные fixture/upstream cases. Actual body probe воспроизводит удаление 2 из 3 дат; потеря на production не доказана. |
| F02 | BaseParser bump выполняется до commit: читатель способен закешировать старые данные под новой версией | Определить transaction owner и publication boundary; PostgreSQL/Redis concurrent/rollback test. Детерминированная actual-body проба подтверждает порядок. |
| F03 | Regional seed guard сравнивает counts, не значения; seed/EMISS владеют пересекающимися данными; fixed monthly keys не следуют regions bump | Snapshot/overlay ownership и producer→consumer invalidation scopes, проверка исправления данных при равных counts. |
| F04 | Eurostat remap и ранний slice могут commit до последующей ошибки, минуя final cache bump | Зафиксировать атомарность/partial success и обязательную публикацию committed изменений. Исходные remap IDs и ошибки сохранять. |
| F05 | Оконная сессионизация без carry разделяет одну сессию на две на границе; click tail/dwell имеют отдельные ограничения | Continuous reference result против chunk processing, late/backfill и каноническая граница session end. |
| F06 | CH cursor `id > cursor` пропускает поздно закоммиченный меньший id | Overlap/reconciliation или иной safe cursor; реальная concurrent DB проверка, восстановление пропуска. Сам INSERT dict bug Opus уже исправлен ранее. |
| F07 | Исправлено локально 2026-10-04, не выпущено: lease с токеном владельца, heartbeat TTL/3, compare-and-delete, отмена задачи и `JobLeaseLostError` при потере, общий ключ `sched:lock:etl` для daily/evening/late_minfin/late_fred (`job_lease.py`, [backlog](backlog.md)). Проверено fakeredis-тестами | Реальный multi-process Redis, остановка event loop дольше TTL, отмена посреди транзакции ETL и код в `to_thread` (не отменяется) — не проверены; TTL 3 ч после SIGKILL по-прежнему держит ключ. |
| F08 | Текущий host logrotate всё ещё compress/copytruncate/14; main содержит rename/USR1/7 | Отдельная адресная установка и ночная I/O/inode/fail2ban приёмка после разрешённого выпуска. Source change не применяет host config. |
| F09 | Cache Redis effective `allkeys-lru`, current default `volatile-lru`; metrics token пуст и endpoint403; S3 не настроен | Адресные изменения и проверка namespace survival/collector/offsite semantics. Не заменять setting snapshot обещанием capacity/durability. |
| F10 | Host Tor HTTP bridge имеет hardcoded credential; первые 400 bytes headers логируются, включая Proxy-Authorization | Убрать sensitive-header logging, вынести/сменить credential с проверкой клиентов; описание и snapshot redacted. Эта работа конфигурацию хоста не меняла. |
| F11 | **2026-10-04, исправлено локально, не выпущено.** Axios-повторы 429/503 теперь только для GET/HEAD и явно идемпотентных запросов, `/auth*` никогда, Retry-After соблюдается (потолок 10 с, 3 повтора); `api_timing` измеряет и XHR. Неуспешные батчи аналитики уже сохранялись и повторялись с тем же `batch_id`, сервер дедуплицирует (Redis done-маркер). | Production acceptance: Network по реальной 429/503. Остаток: дедуп батча в Redis best effort (потеря Redis → возможный дубль); батчи не переживают закрытие вкладки (по замыслу). См. [backlog](backlog.md). |
| F13 | Production app-role `rustats` — PostgreSQL superuser, reserved connections не изолируют приложение | Минимальные privileges/roles и отдельная migration owner роль с login/seed/restore acceptance; сейчас описано фактическое состояние. |
| F14 | Исправлено локально 2026-10-04, не выпущено: `apply_action` сначала коммитит `applying`, затем внешнее действие, затем `approved`/`failed`; повтор из `approved`/`applying` — 409, параллельные apply — один исполнитель; при сбое записи итога остаётся `applying` с пометкой для сверки. Live writes по умолчанию выключены, новых действий нет ([backlog](backlog.md)) | Реальные Метрика/Вебмастер не вызывались (исполнитель подменён); автоматической сверки `applying` с внешней системой нет — только ручная; повтор из `failed` разрешён и может задвоить действие, если ошибка пришла после фактического применения. |
| F12 | Seed при выполнении перезаписывает SEO поля; ADR обещал DB override; IndexNow batch не crash-durable между read и ACK | Описать writer contract и durable delivery policy. Наличие hash-skip не является гарантией сохранения override. |

| F14 | Analytics action executor выполняет внешнее действие до DB audit commit; repeat apply не запрещён status guard | Idempotency/status и external reconciliation, без несанкционированных внешних apply. |
| F12 | **2026-10-04, исправлено локально, не выпущено.** Сид не затирает SEO-поля, правленные в БД (отпечатки записанного сидом в `seed_state[seo_seed_written]`, `FORCE_SEED_SEO=1` сбрасывает); IndexNow-партия переносится в processing и возвращается после таймаута 30 мин (at-least-once, debounce отсекает дубли). | Прогон сида на копии PostgreSQL; реальный Redis; наблюдение `in:proc-idx:*` после выката. `is_listed` сид по-прежнему пересчитывает целиком. См. [backlog](backlog.md). |

Источники: [contracts](data-contracts.md), [findings](code-review-findings.md),
[backend probes](code-review/backend-mechanism-probes-2026-09-30.json),
[client acceptance](code-review/client-mechanism-acceptance-2026-09-30.md),
[ops acceptance](code-review/ops-mechanism-acceptance-2026-09-30.md).
Не все F являются доказанными production incidents; источник каждого это различает.

## Неизвестное с конкретной границей

| ID | Не установлено | Как получить ответ |
|---|---|---|
| U01 | Provider backups/firewall/account quota/physical placement: KVM/QEMU DMI не раскрывает provider | Read-only cabinet/API evidence и отдельно проверка доступности/restore backup. SSH файловая проверка этого не заменяет. |
| U02 | Смешанная устойчивая capacity 4vCPU, запас для новых FX/news/forum jobs | Cold/warm SSR+API+ETL+BI workload, p95/p99, throttling, SQL wait, disk latency/swap, когорты запросов и failure recovery. Историческое p95 не переносить на новую нагрузку. |
| U03 | Полный RTO/RPO, восстановление secrets/globals/AOF/media/DNS/TLS и аварийный failover/WAL/PITR | Полное DR учение с acceptance budget и external visitor/auth proof; выполненный DB/app restore — часть, не весь путь. |
| U04 | Длительная независимая offsite durability и следующий плановый launchd run | Наблюдать реальный scheduled pull, age/result signal и независимый restore. Текущая копия на Mac подтверждена; S3/provider гарантия отсутствует. |
| U05 | Исходная запись НАПРАВКИ21.mov, первоначальная версия аудио по старой filename-ссылке и необнаруженные по exact links старые файлы | Получить исходники по зафиксированным missing locations; новый доступ требует content review. Transcript/image не подтверждает всё отсутствующее audio/video. |
| U06 | Полная правильность каждой экономической точки/внешней методологии и каждый model retrain outcome | Source-specific source-of-record reconciliation с revision/coverage/units/frequency/forecast validation. Schema/body review и несколько восстановленных API выборок не являются полной числовой верификацией. |
| U07 | Все внешние OAuth/SMTP/Telegram/LLM/upstream endpoints на текущую минуту | Согласованные реальные end-to-end сценарии и dated evidence; source/SDK contract раскрыт, внешнее исполнение всех adapters не делалось. |
| U08 | CI на GitHub и выпуск данного doc/tool commit | Remote CI после push, потом отдельный release; локальные gates не выдают себя за remote/deploy/live acceptance. |

Новые требования продукта — отдельный класс: nominal USD/period-average official
FX уже описаны в backlog R-3, PPP не выбрана автоматически. News/forum moderation,
права, storage/retention и допустимая нагрузка требуют проектного решения.
Старые обещания API-продукта/SDK, кабинетов, RID, нормативных актов и коммерческих
результатов сохранены в [сверке планов](code-review/historical-plan-supplement-2026-09-30.md):
наличие HTTP API, рекламы или About не подтверждает принятие этих отдельных продуктов.
Ответы не следует извлекать из отсутствия кода или выдавать за неизвестные существующие механизмы.
