# Аналитические окна и event-копия — 30 сентября 2026

## Область

Третий локальный пакет после досье, база `main 83c4555`. Исправлены
воспроизведённые F05 в PostgreSQL session layer и F06 для существующих
автоматических append writers. Production, рабочая локальная БД и внешние
аналитические сервисы не изменены. [Действующий контракт](../data-contracts.md#аналитические-окна-и-репликация-f05f06--2026-09-30)
отделяет эти результаты от незакрытого F05b и общих ресурсных гарантий.

## Механизм

1. SQL lag/gap/burst/latest pageview-bearing owner определяют logical session
   для посетителей окна с учётом их сохранённой истории. Равные timestamps
   упорядочиваются по id. Pageviewless tails сохраняют прежнюю политику
   присоединения назад; это не новое определение «сессия по любому событию».
2. Source/output пачки5k, portraits до10k SID и один компактный accumulator
   заменяют списки всей истории посетителей в Python. SQL рассматривает старые
   raw rows: readwork и staging disk не ограничены тремя днями. Admin identity
   остаётся отдельным прежним чтением. Tempstage/delete old splits/insert
   фиксируются в одном commit окна; run с несколькими окнами не атомарен целиком.
   Private visitor/history relations получают индексы и ANALYZE. Исходные
   таблицы и global planner/statement timeout/cgroup настройки не меняются.
   Output commit атомарен; visitor selection/history/goals/portraits читаются
   несколькими READ COMMITTED statements, поэтому единый source snapshot при
   concurrent ingest не заявлен.
3. День/новизна привязаны к исходному старту, цели — к distinct technical SID
   в пределах ±5 минут логических краёв. Own portrait позже end не используется;
   fallback ограничен start−сутки..end. Будущий портрет другого окна не меняет
   attribution/bot score прошлой сессии.
4. CH-копия берёт committed ceiling после PG SHARE NOWAIT. Занятый writer
   откладывает таблицу без продвижения cursor; после успешного lock новые
   INSERT могут кратко ждать metadata/max phase. PG закрывается до Redis/CH I/O.
   Проверены READ COMMITTED, default/identity sequence CACHE1/+1/no-cycle.
   Нарушения останавливают copy; ручные id/внешний nextval/live reconfiguration/незаметные resets
   не входят в проверенный writer contract.
5. Cursor/progress/heartbeat v2 игнорируют прежнюю отметку, чтобы восстановить
   уже пропущенную историю. Ordinary job копирует≤80k строк каждой event
   таблицы; prefix продолжается следующим job. Метрики pageview/click считают
   `uniqExactIf(id,...)`, даже если MergeTree хранит физические replay-дубли.
6. Admin slices metadata содержит captured ceiling/cursor/caught_up/deferred.
   Новый heartbeat требует caught_up обеих event таблиц и успешную replacing
   phase. При partial/deferred прежний v2 timestamp остаётся возрастом
   последнего успеха. Progress — последний сохранённый capture; ошибка до его
   записи может оставить прежний результат. Сверять age и журнал job.
   `available` означает enabled
   без known pending rebuild, не доказательство health/полноты.
   Он не утверждает новые commits после capture или правильность
   session-copy. Manual resync сохраняет state pending до reset обоих cursors
   и первого DROP, затем читает event history последовательно. Неоконченный
   rebuild блокирует ordinary sync/run_slice и делает admin meta unavailable.
   Pending снимается только после успеха; replacing cutoff остаётся3650суток,
   не бесконечная история. Marker не заменяет fencing и сохранность state Redis.

## RED → GREEN и границы проверки

До source fix actual `run_rollups` сравнивался с непрерывным расчётом:
**4 failed / 2 passed** — gap4/29, потеря позднего dwell+signup и backfill bridge;
gap30/31 корректно разделяли визиты. Дополнительные literal assertions проверяют
expected день, start/end, pageviews, active_ms, novelty, tiers и attribution;
reference equality сама по себе не считается полной проверкой алгоритма.

Реальный PostgreSQL воспроизвёл sequence allocation: low id оставался в открытой
транзакции, high id commit попадал в копию, поздний low commit терялся.
Две таблицы дали logical ids `{2}` вместо `{1,2}`. Дополнительные тесты проверяют
ограниченный replay/old cursor, unsafe sequence/isolation, progress и retry.
Большинство транспортных failure injections используют FakeRedis/observed sink;
настоящие PG/CH/Redis сценарии отмечены отдельно в итогах ниже.

Independent review выявил дополнительный сбой resync: настоящий первый DROP
и исключение перед вторым оставляли высокий cursor; обычный job пересоздавал
пустую таблицу и ставил fresh heartbeat. RED сохранён на intermediate source
`fe41aea8…`, это не результат финального кода. Final `09d60144…` на настоящих
PG/CH/Redis DB15: оба cursors0, pending=true, heartbeat отсутствует; ordinary
job не открывает CH, чтение заблокировано, API503/meta unavailable. Controlled
operator retry восстанавливает обе event таблицы по2/2 physical/logical IDs,
снимает pending и пишет heartbeat. Replacing phase в этом сценарии — явный
double0/days3650; её содержательная корректность этим доказательством не принята.

Owner focused GREEN: F05 —65 тестов SQLite/существующих analytics и12 настоящего
PG; эти два прогона были на `68d74e…`, финальная дельта к `51b65469…` меняет
только docstring. Benchmark выполнен на exact final source. F06 —25 тестов
(17 PG,6 native CH,2 прежних) на exact final source. Общий финальный gate ниже
повторяет все новые сценарии с explicit opt-in PG/Redis/CH на final hashes.

Тестовые источники используют отдельный loopback PG16 (1 CPU/512 MiB),
unique schema на сценарий; CH24.8 (1 CPU/768 MiB) с проектным low-memory profile;
Redis7 (0,25 CPU/96 MiB), зарезервированные DB14/15. Это не текущие лимиты
production и не приёмка общей машины4vCPU. Credential-файл0600 временный;
fixture не получает application DSN автоматически.

**Финальный `./scripts/check-all.sh`: GREEN**, 194,17 с на frozen source.
Backend: **3198 passed,9 skipped,74 warnings**, 108,25 с. Все новые opt-in
PG/Redis/CH cases включены; 9 skips относятся к прежним отдельным проверкам.
Frontend: **924 passed /112 files**; lint0errors/5warnings; build/precompression,
terrain DOM, JS/client inventories, indicator index, doc counters, page metadata
и public language audit прошли. Это локальные gates: remote CI migrations,
Docker/E2E и production release не принимаются этим прогоном.

Knowledge guard:1325 current file reviews/1009 code files,8794 definitions и
8794 annotations,0 files needing attention. Рельеф:14126 nodes/8917 file edges;
4970 omitted cross-file edges классифицированы, не превращены в dead-code list.
Исторический semantic graph сохранён с39 изменёнными source fingerprints.
После окончательного протокола/material registry guard повторяется отдельно.

[Новый агент без истории](analytics-cold-start-2026-09-30.md) нашёл различия PG/CH,
resync protocol, F05b, реальные границы dev/production/4CPU.11 source hashes
сверены root. Это один сценарий, не blanket полнота знания. Три собственных
synthetic контейнера и их anonymous volumes удалены, отсутствие имён проверено;
temporary fixture credential файл удалён. Рабочая локальная БД, production,
чужие контейнеры и untracked материалы не изменены.
## Замеры на замороженном коде

F05: source SHA-256 `51b65469da05ab9a68a1e997e90fab433b8ae03b5ce7cef4953fc1684c26220d`.
100 000 raw events: цепочка одного посетителя 70 000 событий за более восьми
суток, 5000 обычных сессий, 5000 portraits и 5000 goals. Непрерывный расчёт —
2,696 с; actual three-day caller — 5,488 с. Оба дают 5001 сохранённую сессию
(5000 starts принадлежат окну), одинаковый content SHA-256, 5000 macro goals
и 5000 search/mobile sessions. Peak Python RSS — 108,75 MiB, включая imports
и fixture loader; это не изолированная память тела функции.

Первый вариант запроса на этом fresh schema получил настоящий timeout 60 с.
Диагностика показала ошибочную оценку двух строк и nested loops. Ручной ANALYZE
raw fixture подтвердил причину; такой intermediate результат не принят как
финальная проверка. Финальный код индексирует и ANALYZE только private temp
stages; raw вручную не ANALYZE, automatic analyze timing не измерялся. Temp
visitor relation: 5001 строк / 434 176 bytes; history: 100 000 / 22 708 224 bytes
включая индекс. Это warm-after-seed наблюдение, не cold I/O/p95/capacity.

F06: source SHA-256 `09d60144066d7cc7fc291a4afdc41fbbbb5742b3e661abd0806b5d0468acf84e`.
100 000 событий, исходная загрузка 2,727 с. Инъекция ошибки одного Redis ACK
после настоящего CH insert оставляет physical replay: 120 000 строк при
100 000 logical IDs. Ordinary jobs переносят 80 000 за 1,224 с и 20 000 за
0,304 с; actual `run_slice` возвращает 50 000 pageviews / 50 000 clicks за
0,02236 / 0,02147 с. CH MemoryResident в точке — 344,61 MiB, Docker cgroup
point — 363,1 MiB. Метрики различаются; это не peak и не гарантия вместимости.

Точные исходы, промежуточные неудачи и hashes — в
[машинном свидетельстве](analytics-boundaries-evidence-2026-09-30.json).

## F05b: самостоятельное воспроизведение оставшегося дефекта

Actual `sessionize`/`_sync_replacing` и реальный CH24.8, PG-side SQLite fixture:
после чистой исходной копии late bridge меняет source с2 сессий/2 pageviews на
1/3, повторный replacing sync оставляет CH FINAL2/4. Другой случай: source
carry со start3daysago получает active_ms25000, current two-day copier его
не выбирает, CH остаётся0. Это не только dirty initial release: дефект
повторяется после любого успешного чистого resync. Точные final-source исходы
и самостоятельная уборка таблицы фиксируются в машинном свидетельстве.

Причина: ReplacingMergeTree дедуплицирует одинаковый visitor/start; новый key
не сообщает об удалении старого. FINAL не восстанавливает отсутствующий delete.
Обновление старого start также не входит в current copy cutoff. PostgreSQL
marts/BI и CH session metrics не имеют принятой гарантии равенства после этих
операций. F05 считается исправленным в PG layer; вся BI-цепочка не объявляется
исправленной.

Следующий отдельный пакет: durable mutation/deletion или dirty generations в
том же PG commit; monotone versioned tombstones либо coherent bounded month
snapshot, generation-specific ACK, fenced publisher и отключение overlapping
старой session-copy. Snapshot atomicity одной partition не означает atomicity
нескольких месяцев. Нужны реальные crash/retry/concurrent writer/empty snapshot
сценарии и ограничения SQL/spool/CH disk/RAM. Это проектная рекомендация,
не внедрённая архитектура.

## Оставшиеся ограничения

- SQL history visitor scan может расти и повторяться на каждом окне. Python
  batch не доказывает DB CPU/I/O/60s timeout запас; локальный synthetic sample
  не подтверждает смешанную ETL/SSR/BI нагрузку сервера4vCPU.
- Exact distinct state растёт с числом уникальных id. CH query RAM limits
  и external groupby/sort не превращают его в фиксированный размер состояния.
  Физические replay-дубли расходуют CH disk; обычная таблица не дедуплицируется.
- Ingest-side browser batch loss/retries, raw retention, arbitrary old backfill
  вне2/60-day lookback, clock skew, concurrent rollup leases и источники Метрики
  этим пакетом не закрываются. Own non-bot population не доказывает людей.
- Cursor safety предполагает immutable append rows и штатные automatic ids.
  CACHE1 guard не обнаруживает старые cached blocks после live перехода
  CACHE>1→1; нужны закрытие старых backends и controlled catch-up. История
  таких runtime действий на production здесь не проверялась.
  SHARE NOWAIT может многократно defer под постоянной записью; progress
  отличает это от completed captured prefix. Heartbeat не является barrier
  для commits после capture и не проверяет session deletion correctness.
- Production release/remote CI, полный recovery и multi-process failure/capacity
  остаются отдельной приёмкой. Исторические сентябрьские OOM/idle-in-tx основания
  и прежние ADR сохранены; настройки shared pools/cgroup этим пакетом не повышены.
- Interrupted resync безопасно откладывает ordinary job при сохранном state
  Redis. Concurrent operator/in-flight job, потеря state/AOF и cross-store
  crash atomicity требуют отдельной приёмки; перед resync исключить overlap.

## Первичные основания выбора

PostgreSQL16 описывает конфликты SHARE с INSERT RowExclusive и время жизни
table locks: [explicit locking](https://www.postgresql.org/docs/16/explicit-locking.html).
CACHE>1 допускает выдачу sequence values не по межсессионному порядку:
[CREATE SEQUENCE](https://www.postgresql.org/docs/16/sql-createsequence.html).
Прежние cached values могут пережить изменение CACHE в живых backends:
[ALTER SEQUENCE notes](https://www.postgresql.org/docs/16/sql-altersequence.html#SQL-ALTERSEQUENCE-NOTES).
Exact distinct state не имеет постоянного размера:
[ClickHouse uniqExact](https://clickhouse.com/docs/reference/functions/aggregate-functions/uniqExact).
Эти источники объясняют ограничения; локальную корректность проверяют actual
caller fixtures и независимый review, а не ссылка на документацию провайдера.
