# Границы знания и подтверждённые проблемы

Срез 30 сентября 2026. Основная [приёмка](project-knowledge-acceptance.md) различает
устройство, риск в конструкции и фактически наблюдавшуюся потерю/сбой.
Этот реестр не является delete-list или принятой новой архитектурой.

## Подтверждённые механизмы, требующие отдельного исправления

| ID | Что известно | Следующая проверка/действие |
|---|---|---|
| F01 | Непустой частичный national response удаляет сохранённые даты вне ответа; empty response сохраняет историю | Явный complete/partial scope и merge/replace, затем реальные fixture/upstream cases. Actual body probe воспроизводит удаление 2 из 3 дат; потеря на production не доказана. |
| F02 | BaseParser bump выполняется до commit: читатель способен закешировать старые данные под новой версией | Определить transaction owner и publication boundary; PostgreSQL/Redis concurrent/rollback test. Детерминированная actual-body проба подтверждает порядок. |
| F03 | Regional seed guard сравнивает counts, не значения; seed/EMISS владеют пересекающимися данными; fixed monthly keys не следуют regions bump | Snapshot/overlay ownership и producer→consumer invalidation scopes, проверка исправления данных при равных counts. |
| F04 | Eurostat remap и ранний slice могут commit до последующей ошибки, минуя final cache bump | Зафиксировать атомарность/partial success и обязательную публикацию committed изменений. Исходные remap IDs и ошибки сохранять. |
| F05 | Оконная сессионизация без carry разделяет одну сессию на две на границе; click tail/dwell имеют отдельные ограничения | Continuous reference result против chunk processing, late/backfill и каноническая граница session end. |
| F06 | CH cursor `id > cursor` пропускает поздно закоммиченный меньший id | Overlap/reconciliation или иной safe cursor; реальная concurrent DB проверка, восстановление пропуска. Сам INSERT dict bug Opus уже исправлен ранее. |
| F07 | Job lock TTL не продлевается; daily/evening используют разные locks; процесс после expiry может продолжать работу | Actual multi-process lock expiry/retry; определить допустимое перекрытие и lease ownership. |
| F08 | Текущий host logrotate всё ещё compress/copytruncate/14; main содержит rename/USR1/7 | Отдельная адресная установка и ночная I/O/inode/fail2ban приёмка после разрешённого выпуска. Source change не применяет host config. |
| F09 | Cache Redis effective `allkeys-lru`, current default `volatile-lru`; metrics token пуст и endpoint403; S3 не настроен | Адресные изменения и проверка namespace survival/collector/offsite semantics. Не заменять setting snapshot обещанием capacity/durability. |
| F10 | Host Tor HTTP bridge имеет hardcoded credential; первые 400 bytes headers логируются, включая Proxy-Authorization | Убрать sensitive-header logging, вынести/сменить credential с проверкой клиентов; описание и snapshot redacted. Эта работа конфигурацию хоста не меняла. |
| F11 | Axios retry429/503 охватывает non-auth mutations; passive collector wrapper не измеряет Axios XHR, неуспешные обычные batches могут теряться | Idempotency/retry policy по операциям; transport/collection completeness tests. |
| F13 | Production app-role `rustats` — PostgreSQL superuser, reserved connections не изолируют приложение | Минимальные privileges/roles и отдельная migration owner роль с login/seed/restore acceptance; сейчас описано фактическое состояние. |
| F14 | Analytics action executor выполняет внешнее действие до DB audit commit; repeat apply не запрещён status guard | Idempotency/status и external reconciliation, без несанкционированных внешних apply. |
| F12 | Seed при выполнении перезаписывает SEO поля; ADR обещал DB override; IndexNow batch не crash-durable между read и ACK | Описать writer contract и durable delivery policy. Наличие hash-skip не является гарантией сохранения override. |

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
