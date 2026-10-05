# Контракты данных Forecast Economy

## Аналитические окна и репликация F05/F06 — 2026-09-30

Локальное уточнение после `main 83c4555`; старые датированные строки ниже
сохраняют прежние механизмы и основания. [Приёмка и границы](code-review/analytics-boundaries-acceptance-2026-09-30.md).

### PostgreSQL: логический визит

`sessionize` выбирает посетителей с pageview/dwell/click/move в `[since,stop)`;
`stop=until` либо время начала вызова. Для них SQL рассматривает сохранённые
события до stop, включая историю раньше since. Разрыв `>=30 минут` отделяет
burst; burst без pageview до первого просмотра не образует сессию, последующие
такие bursts присоединяются к предыдущей сессии с pageview. Это сохраняет
прежний контракт позднего dwell даже после долгой паузы; не равно новой
30-минутной сессии по любому событию. Равные timestamps упорядочиваются по id.

Окно восстанавливает затронутые logical keys, в том числе начавшиеся слева;
temp staging, удаление старых splits и вставка итогов фиксируются вместе.
Временные visitor/history relations индексируются и ANALYZE внутри транзакции;
статистика source tables и глобальные planner/timeout настройки не меняются.
Unrelated visitors слева и будущие starts сохраняются. Те же observations и
cutoff сохраняют visitor/start; backfill может сдвинуть старт или объединить
прежние keys. SQL surrogate id при пересчёте меняется. Пачки Python
входа/выхода — по5 000 строк, портретный lookup — до10 000 own/fallback SID,
плюс один компактный накопитель. Admin identity считывается отдельно, прежним
механизмом. Это не общий фиксированный предел всей памяти sessionize;
SQL historical scan и temporary disk тоже расходуют ресурсы.
`run_rollups` сохраняет три МСК-дня на окно и отдельный analytics pool.

День и новизна относятся к первоначальному старту, visitor flood — к его
МСК-дню. Цели связываются через distinct client SID и logical start, с допуском
±5 минут от фактических краёв сессии. Own SID portrait имеет приоритет и
допускается только со started_at не позже logical end;
fallback — последний портрет между start−сутки и end. Последнее устраняет
зависимость от будущих портретов другого расчётного окна. Поздняя запись
подхватывается повторным пересчётом затронутого периода: обычный job берёт
2 суток, ночной — 60; автоматическое обнаружение произвольного старого backfill
вне этих окон не заявлено. При включённой raw retention source history может
стать недостаточной; это не механизм архивного восстановления.

### ClickHouse: append event-копия

Перед чтением committed ceiling `max(id)` отдельная короткая PG-транзакция
берёт `SHARE NOWAIT`. При конфликте с writer копия сразу откладывает таблицу;
после успешного lock новый writer может кратко ждать metadata/max query.
PG закрывается до Redis и CH network I/O. READ COMMITTED и обычная возрастающая
default/identity sequence с CACHE 1 без CYCLE проверяются; несовместимая схема
останавливает event-копию. Это контракт существующих INSERT writers: ручные
меньшие id, out-of-band nextval, сброс и live reconfiguration sequence не входят
в гарантию. Текущее CACHE1 не выявляет старые cached blocks после прежнего
CACHE>1; возвращение к поддерживаемому режиму требует закрытия старых
соединений и контролируемого catch-up. Такая runtime история здесь не проверена.

Revision `v2` игнорирует прежний cursor и повторно читает сохранённую историю.
Обычный job — до четырёх батчей по 20 000 **каждой** таблицы, затем продолжает
в следующем запуске. Cursor продвигается только после успешного CH insert.
Retry может оставить физические дубли MergeTree; pageviews/clicks используют
`uniqExactIf(id,...)`. Другой CH event-reader обязан соблюдать тот же immutable
ID контракт. Exact distinct state требует памяти; лимит строк копирования не
является лимитом памяти произвольного аналитического запроса.

`/admin/bi/slices/meta` дополнен `sync_progress`: cursor, ceiling, caught_up,
deferred по таблицам. `v2` heartbeat обновляется после replacing phase только
при достижении обоих captured ceilings. При partial/deferred прежний v2 timestamp
остаётся возрастом последнего успешного среза. `sync_progress` — последний
сохранённый capture: сбой до его записи может оставить прежний результат.
Он читается вместе с age и журналом job, а не как live-состояние PostgreSQL.
`available=true` означает enabled без известного pending rebuild, а не здоровую
или содержательно полную копию. Heartbeat не подтверждает новые commits после
capture и не подтверждает правильность session-копии. Manual `resync()` сначала
сохраняет state-Redis pending intent, сбрасывает оба event cursors, затем удаляет
derived CH tables и читает event history последовательными батчами. Pending
снимается только после полного успеха; прерывание блокирует ordinary sync и
`run_slice`, admin metadata возвращает unavailable/reason. Сохранность state
Redis и исключение уже запущенного concurrent sync — предпосылки; marker не
является fencing или atomic commit между Redis и CH. Потеря marker/state после
инфраструктурного сбоя требует отдельного recovery acceptance.

Сессии выбранного окна публикуются одним output commit. Visitor selection,
history, goals и portraits читаются несколькими READ COMMITTED statements;
единый snapshot всех источников при concurrent ingest не заявлен. Проверенные
сравнения относятся к зафиксированным observations и cutoff. Допуск late data
следующим штатным окном не гарантирует произвольный старый backfill вне lookback.

<a id="f05b-session-копия-и-журнал-изменений"></a>

### F05b: контракт журнала изменений сессий — 2026-10-04 (локально)

Действующий контракт (код: `services/session_change_log.py`,
`clickhouse_sync._sync_session_changes`, модель `ServerSessionChange`).

- `server_session_changes(visitor_id_hash, started_at) PK, rev, changed_at` —
  «ключ создан/изменён/исчез». Любая запись в `server_sessions`, меняющая ключ
  или зеркалируемые в CH колонки, обязана отметить ключ **в той же транзакции**
  (сейчас: `sessionize` и `reclassify_known_crawlers_day`; новый писатель
  `server_sessions` обязан делать то же). Пишется только при
  `RUSTATS_CLICKHOUSE_ENABLED=true`.
- Журнал не хранит значения: истина — текущий PG. Потребитель: строка есть →
  replacing insert (любой возраст `started_at`), нет → `ALTER TABLE … DELETE`
  (`mutations_sync=1`, ключ `(visitor, toUnixTimestamp(started_at))`, пачки ≤200).
  ACK — удаление записи при совпадении `rev`; сбой CH оставляет запись.
- Нет курсора и ceiling: порядок коммитов не важен. Повтор идемпотентен.
  Размер ограничен числом различных ключей.
- Синк: журнал → окно 2 суток (бутстрап и простой CH). Ограничения: 2 000
  записей × 4 пачки за прогон, весь сетевой I/O в executor.
- `resync()` пересобирает копию из PG и журнал не очищает (лишние записи
  безвредны). Журнал не восстанавливает прошлое: призраки, накопленные до
  выпуска, и включение CH с нуля требуют разового `resync()`.
- Пределы: один синк-процесс (F07), CH хранит `DateTime` секундной точности и
  кодирует naive `datetime` через `timestamp()` по TZ процесса (backend
  `TZ=Europe/Moscow`) — ключ удаления считается той же функцией, но сдвиг
  часовых срезов относительно UTC не исследовался. `ALTER DELETE` читает ключевые
  колонки всей таблицы; объём/время на production не измерялись.

Исходное описание дефекта (до 2026-10-04) сохранено ниже.

### F05b: session-копия пока не согласуется с удалениями

`server_sessions` в CH — ReplacingMergeTree по visitor/start. Новый logical key
не удаляет старый, даже с FINAL. После late bridge PG может иметь одну сессию,
а CH — две; обновление carry со start старше двух суток также не входит в
обычный copy window. Это постоянный дефект, а не только initial replay.
Нужны durable изменения/удаления logical keys в том же PG commit и versioned
tombstones либо согласованный snapshot с правилами generation/ack и ресурсным
бюджетом. Простое увеличение days или разовый resync не закрывает механизм.
До этого CH session-витрины не имеют принятой гарантии равенства PostgreSQL.

## Региональный контур F03 — 2026-09-30

Локальный пакет после `main c2a883d` заменяет count-skip/общую перезаливку
артефакта и публикацию ЕМИСС только в конце полного прогона. Старые описания
ниже сохраняют дату наблюдения. Основания выбора —
[ADR-0008](adr/0008-regional-bounded-context.md#2026-09-30--права-записи-артефакта-и-емисс),
сценарии и фактические результаты —
[приёмка](code-review/regional-publication-acceptance-2026-09-30.md).

| Producer | Права записи | Что сохраняется |
|---|---|---|
| Годовой артефакт `data.csv.gz` | INSERT отсутствующих ключей; UPDATE отличающегося значения по `(indicator_id,region_id,year)` | Все DB-only годы, показатели и территории, включая исторический дособор; отсутствие ключа не является DELETE |
| Месячный артефакт `fuel_points.csv` | INSERT отсутствующих `(indicator_id,region_id,YYYYMM)`; конфликт оставляет существующее значение | Живые ревизии и новые месяцы ЕМИСС; отсутствие файла не очищает месячную таблицу |
| ЕМИСС 31448 | INSERT/UPDATE фактически полученных месячных точек; каждый месяц — отдельный commit | Пропущенные в ответе точки и ранее закоммиченные месяцы при поздней ошибке |

**Сидер.** [Реализация](../backend/seed_regional.py) больше не принимает равенство
счётчиков за равенство содержания. При наличии годового артефакта каждый запуск
потоково переносит входные точки во временные PostgreSQL staging-таблицы
чанками по 10 000, проверяет их и
объединяет по уникальным ключам; в Python не строится список всей истории.
Годовые значения сравниваются в точности хранения `Numeric(18,4)`. Метаданные
и обе частоты фиксируются одной транзакцией; некорректный импорт откатывает их
вместе. Обновление metadata при тех же точках тоже является изменением.
Четырёхзначные годовые строки `fuel_points.csv` относятся к годовым топливным
рядам и не превращаются в месячные.

**Совместная запись.** Сидер и месячный ЕМИСС используют один PostgreSQL
transaction advisory lock для региональной записи. Он удерживается только
на SQL-части до commit/rollback; внешняя загрузка ЕМИСС выполняется до lock.
Это сохраняет общий порядок metadata/points и предотвращает встречное ожидание
при одновременном startup и живом месячном обновлении. Месячные конфликты по
значениям по-прежнему разрешаются описанными выше правами; lock не устанавливает
происхождение точки.

**Метаданные и происхождение.** Артефакт управляет names/units/notes имеющихся
в нём записей; отсутствие записи не удаляет её из БД. `year_min/year_max`
считаются по сохранённому объединению годовых лет и лет месячных точек, а не
по границам последнего файла. Живой месячный ingest поддерживает эти границы.
`note/source_note` — описание происхождения показателя, а не отдельный журнал
каждой точки. Без такого журнала нельзя безопасно отличить старое месячное
seed-значение от более свежей ревизии: поэтому месячный bootstrap оставляет
конфликтующее существующее значение. Обновление существующих месячных значений
из изменённого артефакта этим пакетом не реализовано.

**Commit → consumers.** После успешного commit выполняется ограниченная
best-effort попытка обновить namespaces `regions`, `ssr-region`, `og-region`;
regional API/SSR/OG используют их поколения.
ЕМИСС публикует каждую изменённую транзакцию до следующего fetch, поэтому
поздний source failure не оставляет предыдущий успешный месяц ожидающим
финальной публикации всего прогона. Rollback не публикуется. TTL и мемоизация
поколения остаются ограничением видимости; отдельные PostgreSQL и Redis не
дают гарантии доставки после падения процесса. Публикация статических sitemap
shards остаётся отдельным job, а не частью этой транзакции.

**План ЕМИСС.** Сохранённый артефакт сопоставляет slug → ОКАТО-id; grid parser
получает обратный id → slug, включая особую строку РФ до 2023 года. Помимо
догоняющего плана проверяются текущий и предыдущий календарные месяцы.
Это ограниченный хвост ревизий, не повторная сверка всех регионов и месяцев
истории с ЕМИСС. Метаданные могут требовать публикации даже при неизменных
значениях точек.

**Окружение.** [Entrypoint](../backend/entrypoint.sh) по-прежнему останавливает
первичный startup при ошибке сидера на пустой годовой БД, но продолжает старт
при уже имеющейся годовой истории. Это fallback доступности, не доказательство
актуальности источника. Полный restore после ЕМИСС требует БД, одного артефакта
недостаточно. Локальные тесты/замеры и production release различаются; число
4 vCPU не является измеренной пропускной способностью этого механизма.

## Защита истории и commit → публикация — 2026-09-30

Текущий локальный пакет после `main 506122b` уточняет F01/F02/F04; старые
наблюдения ниже сохраняются как история. Подробные проверки и пределы —
[приёмка](code-review/history-publication-acceptance-2026-09-30.md).

1. National `WorldSeriesPayload` имеет `is_complete=False` по умолчанию.
   Отсутствующая дата не является удалением. Для replacement обязательны
   `is_complete=True` и включительные `coverage_start/end`; удаление ограничено
   этим интервалом. Empty complete, невалидное окно или точки вне него — error
   до point writes. `ref` payload должен совпадать с запрошенной identity.
   Обычные ревизии обновляют value, повтор без изменения идемпотентен. Extent
   и автоматически построенный текст должны описывать сохранённую БД целиком,
   а не только окно последнего ответа; curated description сохраняется.
2. Федеральные source, weekly overrides и hooks пишут факт/derived/forecast
   в SQL-транзакции. CalculationEngine возвращает changed codes; namespace
   публикует владелец успешного commit. Rollback не публикуется. После commit
   сбой кэша не теряет success/changed и дальнейший derived-каскад.
3. Eurostat country metadata, remap и parsed slice публикуют world/catalog/SSR
   после commit, перед закрытием сессии: metadata/remap при реальном изменении,
   slice при наличии сохранённого индикатора, включая same-value retry.
   Later failure не отменяет предыдущие коммиты, loader остаётся ошибочным,
   applied TOC не продвигается. Ни dataset atomicity, ни общий PostgreSQL/Redis
   commit не обещаны. Strict world-catalog failure виден; DB0 best-effort и
   memo до пяти секунд сохранены.

Эти изменения локальны. Outbox/reconciliation при падении процесса, полнота
upstream всех федеральных replace/Eurostat и production acceptance остаются
отдельными задачами.

> **Актуализация 2026-09-30, `main 972579f`:** прежний снимок и история ниже сохранены. Новые backend-контракты сверены по прежнему полному source review и чтению изменённых блоков; подробности — [backend delta](code-review/backend-delta-2026-09-30.md). Это локальная кодовая сверка, не новая приёмка сервера.

## Актуальные уточнения контрактов — 2026-09-30

Эти уточнения заменяют старые формулировки только по указанным механизмам. Неизменённые контракты и инциденты сохраняют свои датированные основания.

| Механизм | Действующий контракт по `972579f` | Свидетельства / граница |
|---|---|---|
| Canonical валют | 11 явных base codes и их siblings живут в `/currencies/indicator/{code}`, годы/месяцы в том же дереве, категория `/currencies`. Историческое имя helper `russia_indicator` не означает российское дерево для этих кодов. SSR старых путей даёт прямой 301; новый base currency требует registry update | [Paths](../backend/app/services/site_paths.py#L142-L185), [SSR](../backend/app/api/seo_pages.py#L331-L368), [breadcrumbs](../backend/app/services/breadcrumbs.py#L62-L97). Реальный nginx/браузер здесь не проверены |
| Annual forecast | Annual horizon=1 в source/generated seed, Annual-Auto и world policy; annual derived допускает поправку anchor и максимум одну следующую календарную точку. API фильтрует старое stored содержимое; world fingerprint включает annual_horizon=1, subnational on-demand/cache обновлены | [API](../backend/app/api/forecasts.py#L51-L132), [derived](../backend/app/services/forecast_strategies/derived_from_source.py#L412-L453), [fingerprint](../backend/app/services/world_forecast_pipeline.py#L122-L199). Фактическая перетренировка/публикация не установлены |
| Eurostat structure | Вместо безусловного DSD quarantine loader проверяет slices: exact geo/hash принимается; missing сопоставляется по стране/частоте, ≥6 общим датам, ≥90% значений в допуске 1% и уникальному лучшему dimension score. History orphan сохраняется; quarantine при listed orphans >max(2,floor(20% listed)). Existing code/URL не меняется | [Planner](../backend/app/services/eurostat_structure.py#L40-L147), [loader](../backend/scripts/load-world-eurostat.py#L475-L656), [ADR-0011](adr/0011-world-eurostat-data-plane.md#2026-09-29--смена-структуры-автоматическая-сверка-вместо-вечного-карантина). Численное сходство не доказывает равенство методологий |
| Eurostat commit/state | Remap commit отдельно, каждая parsed slice пишет metadata/points в своей транзакции; namespace bump в конце loader, dataset state/log отдельно в scheduler. Non-geo/time skipped продвигает applied TOC, error/quarantine — нет. Orphan автоматически не снимается с листинга | [Commit](../backend/scripts/load-world-eurostat.py#L431-L526), [state](../backend/app/services/world_eurostat_ingest.py#L188-L228), [job](../backend/app/services/world_eurostat_ingest.py#L328-L535). Ошибка между фазами требует consistency проверки; dataset atomicity не заявляется |
| World API/сравнение | Country detail получает последние две точки per id через PG LATERAL LIMIT/SQLite row_number, newest-first. Compare catalog отдаёт peer_mode/value_adjust; готовый российский YoY подписывается процентом годового изменения. Индексная база/готовый темп не взаимозаменяемы, все валюты автоматически не приводятся к одной | [Queries](../backend/app/services/world_subnational_queries.py#L101-L146), [API](../backend/app/api/world.py#L1004-L1215), [selector](../backend/app/services/world_compare.py). SSR/CSR equivalence и реальный PG perf отдельно |
| ЕМИСС/US overlay | ЕМИСС lookup получает scalar ORM Indicator; commits по месяцу сохраняются. US YAML убирает BLS overlay трёх labour рядов, FRED mirror и generic BLS capability остаются | [ЕМИСС](../backend/app/services/emiss_regional_parser.py#L252-L334), [US](../backend/app/data/world_subnational/us.yaml). Live freshness не проверена; regional writer/count/cache риски не закрыты |
| Сессионизация | Sessionize пересчитывает [since,until), event types pageview/dwell/click/move; portrait lookback сутки, goals до until+5 минут. Большое окно делится по 3 МСК-дня с delete/insert/commit на окно; carry сессии через границу отсутствует | [Sessionize](../backend/app/tasks/analytics_rollups.py#L83-L234), [windows](../backend/app/tasks/analytics_rollups.py#L683-L711). Crossing case не проверен, новый тест исключает его |
| Фильтры аудитории | Python Метрика rollup исключает isRobot/isRobotPro/headless; SQL bundle/Pulse helper только headless, missing browser проходит. Own sessions score>=60 включает square desktop>=600 и cores>64 с весом 60 каждый. CH raw visits копируется без headless-фильтра | [Marts](../backend/app/services/analytics_marts.py#L138-L164), [score](../backend/app/services/bot_score.py), [CH](../backend/app/services/clickhouse_sync.py#L296-L416). Разные populations; отсутствие bot-признака не подтверждает человека |
| CH replication | Append: selected columns → PG close → executor insert → state id cursor. Replacing layers partitions по 5000, PG JSON projection; stream держит PG session во время insert. Identity links загружаются полностью | [CH](../backend/app/services/clickhouse_sync.py#L155-L416), [fixture](../backend/tests/test_clickhouse_sync.py). Loop blocking исправлен по коду; late commits, реальные CH merges, RAM/DB hold-time отдельно |
| Sitemap/IndexNow | Index lastmod=max(data date, content-change date), история section_changed. IndexNow history читает published shards, fallback registry при отсутствии; drain переносит партию (MULTI/SMOVE) в `in:proc:{host}:{batch_id}` с реестром `in:proc-idx:{host}`; ACK после debounce, неотправленное возвращается в очередь, партии старше 30 мин возвращает следующий drain (2026-10-04, локально: at-least-once). Все действующие canonical остаются в sitemap | [Publication](../backend/app/services/sitemap_static.py#L288-L405), [history](../backend/app/services/indexnow.py#L381-L464), [drain](../backend/app/services/indexnow.py#L683-L813). Delivery не равен index inclusion |
| Scheduler/DB timeout | Hour dedup process-local job/type/нормализованный текст, marker до Telegram; рестарт сбрасывает. Forecast-plan SET LOCAL statement_timeout=600000 только текущей PG транзакции, pool defaults прежние | [Listener](../backend/app/main.py#L302-L347), [helper](../backend/app/database.py#L72-L83), [plan](../backend/app/services/world_forecast_pipeline.py#L649-L675). Send failure может подавить повтор до часа; runtime ресурсы отдельно |

**Открытые прежние контракты:** полнота ответа перед destructive replace, commit → invalidate, региональные права записи и cache keys, единые SSR/sitemap eligibility, определения BI метрик. Доказательные проверки — [findings](code-review-findings.md) и [backend delta](code-review/backend-delta-2026-09-30.md); этот раздел не исправляет runtime.

**Проверено по коду:** HEAD `b684290067bf`, 2026-09-27; отличия параллельно изменяемого рабочего дерева отмечены [ниже](#параллельные-изменения-рабочего-дерева). Это карта локальных producer → storage → consumer и условий публикации, а не утверждение о состоянии продакшена. Исторические решения и мотивация остаются в [`CONTEXT.md`](../CONTEXT.md), [`data_sources.md`](data_sources.md) и [`adr/`](adr/); оперативные действия — в [`workflow.md`](workflow.md) и [`enterprise_resilience.md`](enterprise_resilience.md).

## Независимая проверка механизмов — завершающее продолжение 30.09

[Backend inventory](mechanism-inventory.md) перечисляет ORM поля/constraints/relationships,
DTO, HTTP/Depends, jobs/locks/flags, Settings/readers и candidate effects. Каждая запись
имеет source anchor и SHA; произвольный `execute/set/add` без receiver dispatch не
считается автоматически SQL/Redis write. [Backend trace](code-review/backend-mechanism-acceptance-2026-09-30.md)
и [actual-body probes](code-review/backend-mechanism-probes-2026-09-30.json)
сохраняют наблюдения до исправлений F01/F02/F03/F04 и уточняют прежние риски BM01–BM07: nonempty partial удаляет 2 из 3 дат; bump до commit
допускает old cache; равные regional counts скрывают values revision; fixed monthly key
не меняется от regions bump; remap+первый Eurostat slice сохраняются при ошибке второго
без final bump; 4-minute session через границу chunk даёт2 вместо1; late id1 пропускается
после cursor2; lease expiry допускает второго исполнителя. Это исполняемые in-memory
модели выбранных реальных тел, без внешних вызовов, не livePG/Redis/CH concurrent acceptance
и не доказательство фактической production потери.

Отдельная граница BM09: analytics MCP `propose_analytics_action` пишет proposal;
`/analytics/actions/{id}/apply` — административное применение с внешним executor
до DB audit commit. Repeat/status/idempotency и reconciliation нужно определять
отдельно; весь analytics API не является read-only. [Apply](../backend/app/api/analytics.py#L229)
и [executor](../backend/app/services/action_executor.py) — самостоятельные источники.

Клиентский [инвентарь](client-mechanism-inventory.md)/[сценарии](code-review/client-mechanism-acceptance-2026-09-30.md)
прослеживают queries/locale, numeric native units, retries, cancellation, storage,
analytics batches, embed/identity и loading/error/empty. Численное compact formatting
не конвертирует валюту; normalised comparison и будущий monetary USD R-3 различаются.
[Остаточные проблемы и пределы](knowledge-unknowns.md) сохраняются до отдельной проверки.

## Оси и владельцы контракта

| Контекст | Производитель → хранилище → потребитель | Идентичность факта и каноническая частота |
|---|---|---|
| Федеральная Россия | `PARSER_REGISTRY` / `BaseParser`, `CalculationEngine` → `indicators`, `indicator_data`, `fetch_log` → `/api/v1/indicators/*`, SSR/OG, прогноз | `(indicator_id, date)`; частота хранится на `Indicator`, не в ключе точки. [Модели](../backend/app/models.py#L19-L64), [API](../backend/app/api/indicators.py#L409-L453). |
| Регионы России | Артефакт `app/data/regional/` / `seed_regional.py`, отдельное обновление ЕМИСС → `regions`, `region_indicators`, `region_data`, `region_monthly_data` → `/api/v1/regions/*`, SSR/OG | Год: `(indicator_id, region_id, year)`; месяц: `(indicator_id, region_id, month)` с `month=YYYYMM`. [Модели](../backend/app/models.py#L77-L165), [seed](../backend/seed_regional.py#L81-L140). |
| Мир, страны | Official provider adapter / Eurostat TOC / BEA → `world_countries`, `world_indicators`, `world_data_points`, `world_dataset_state` → `/api/v1/world/*`, сравнение, SSR/OG, world forecast | Ряд: `(provider, country_id, dataset_id, slice_hash)`, факт: `(indicator_id, date)`, состояние источника: `(provider, dataset_id)`. `provider` не равен публичному `source`. [Модели](../backend/app/models.py#L189-L315). |
| Мир, регионы вне России | YAML-паспорт + FRED/BLS, BEA ZIP → `subnational_regions`, `subnational_indicators`, `subnational_data_points` → `/api/v1/world/countries/{slug}/regions/*` | Метаданные: `(country_code, slug/code)`; факт: `(indicator_id, region_id, period)` с `period` типа date, частота на индикаторе. [Модели](../backend/app/models.py#L435-L518). |
| Календарь | Официальные планы/правила → `economic_events` → `/api/v1/calendar`, upcoming, iCal | Stable `event_key` и provenance обязательны для публичности. [ADR-0005](adr/0005-official-calendar-source-bound.md), [public guard](../backend/app/api/calendar.py#L19-L47). |
| Identity и аналитика | Auth / first-party события / Метрика → Postgres + state Redis → `analytics_marts`, BI, Пульс; ClickHouse — копия для срезов | Различать `session_id_hash`, `visitor_id_hash`, `server_sessions` и визит Метрики. [Модели](../backend/app/models.py#L983-L1059), [rollups](../backend/app/tasks/analytics_rollups.py#L592-L610), [marts](../backend/app/services/analytics_marts.py#L318-L338). |

## 1. Федеральный факт, derived и прогноз

**Вход и provenance.** В `Indicator` находятся `code`, `unit`, `frequency`, `source`, `source_url`, `parser_type`, `model_config_json`, `is_active`, `is_listed` и методология. Точный URL/формат источника — в [`data_sources.md`](data_sources.md) и docstring конкретного парсера; поле `fetch_log.source_url` записывает URL фактического прогона. `BaseParser._fetch_and_parse` возвращает `(points, source_url)`; точки имеют `date/value` или форму `(date, value)`. [Модель](../backend/app/models.py#L19-L46), [вход парсера](../backend/app/services/base_parser.py#L292-L323).

**Запись и статус.** `bulk_upsert` отбрасывает `None`, для повторов даты оставляет последнее значение, обновляет существующую точку только при изменении value и возвращает отдельные `records_added`/`records_updated`. `replace_series` может удалить исчезнувшие даты; при резервном снимке сохраняются точки новее его покрытия. `BaseParser.run` записывает `running` до fetch, затем в рабочей транзакции upsert/forecast/cache invalidation и итоговый `success`, `no_new_data`, `parsed_zero` или `fallback_used`; исключение откатывает рабочую транзакцию и пишет отдельный `failed`. `parsed_zero` означает необъяснённый пустой parse при существующей истории, а `fallback_used` — другой provenance и возможный лаг, не обязательно отсутствие новых точек. [Upsert](../backend/app/services/upsert.py#L101-L143), [статусы](../backend/app/services/base_parser.py#L66-L85), [цикл](../backend/app/services/base_parser.py#L137-L231).

**Derived и кэш.** `DerivedSpec(dst_code, src_codes, op)` задаёт чистое преобразование; `run_for_updated_sources` пересчитывает транзитивное замыкание в топологическом порядке, включая in-place ревизии источника через `records_updated`. Изменившиеся derived инвалидируют namespace кода. При исключении отдельного derived код логирует ошибку и продолжает остальные; итоговый caller должен проверять completeness, а не считать факт обновления гарантией всего каскада. [Spec](../backend/app/services/calculation_engine.py#L52-L66), [dispatch](../backend/app/services/calculation_engine.py#L401-L440), [scheduler](../backend/app/tasks/scheduler.py#L188-L203). Полный ручной пересчёт — `scripts/rebuild-all-derived.py`; корневой `scripts/` не копируется в backend image, поэтому в контейнер передавать файл через stdin (см. workflow).

**Публичный ответ.** `/indicators/{code}` отдаёт `IndicatorDetail`: `source_url`, `methodology`, `first_date`, `last_date` могут быть `null`; `world_compare=null` означает отсутствие честной связки. `/indicators/{code}/data` отдаёт `{"indicator": code, "count": N, "data": [{"date", "value"}]}`; пустой **существующий** ряд — 200 с `count=0,data=[]`, неизвестный код — 404. Без диапазона API берёт до 10 000 последних точек и разворачивает в прямой порядок; `from/to` включительны. [Схемы](../backend/app/schemas.py#L51-L90), [реализация](../backend/app/api/indicators.py#L409-L453). `is_listed=false` исключает обычный листинг; детализация остаётся доступна по коду. [API](../backend/app/api/indicators.py#L149-L164). До новой версии глобальная палитра использовала `include_unlisted=true`; локальный `/search` 30.09 читает active data-backed российские ряды напрямую, включая unlisted и их canonical resolver. Контракт — [ниже](#7-поиск-и-допустимая-область-локальная-версия-2026-09-30).

**Прогноз.** Российский forecast хранится отдельно в `Forecast/ForecastValue`; `forecast=null` в ответе — допустимое состояние. Startup scheduler и плановый/late ETL запускают gap-fill для рядов с `forecast_steps>0` без текущего прогноза, но сам вызов retrain не доказывает наличие результата. [Схема](../backend/app/schemas.py#L93-L116), [gap-fill](../backend/app/services/forecast_pipeline.py#L472-L508), [startup](../backend/app/main.py#L417-L429).

## 2. Регионы России

**Год и месяц не смешивать.** `seed_regional.py` читает `regions.json`, `indicators.json`, `data.csv.gz`, опциональный `fuel_points.csv`; метаданные upsert по slug/code, годовые и месячные таблицы отдельно. `source_note`/`note` несут происхождение исторических добавлений; единица в `RegionIndicator.unit`, а не в значении точки. [Артефакт](../backend/seed_regional.py#L35-L63), [модель](../backend/app/models.py#L93-L165).

**История публикации 27–30.09 до F03.** Сидер пропускает загрузку точек, если **оба** счётчика БД равны счётчикам артефактов; иначе `TRUNCATE` обеих таблиц и потоковая загрузка внутри транзакции, затем commit. Это контракт *по количеству*, не по хэшу содержания: изменение значения без изменения числа строк само по себе не запустит перезаливку. Для редакции артефакта с прежней кардинальностью нужна отдельная проверка и управляемый refresh; в исходном аудите 27.09 такой сценарий не воспроизводился. Продолжение 30.09 проверило actual count-skip и cache-key/bump in-memory (BM03 выше); полная live-value сверка не выполнена. Старые позиции guard/commit относятся к тому исходному снимку, а не текущему файлу. [Действующий механизм](#региональный-контур-f03--2026-09-30) заменяет эту перезаливку. `entrypoint.sh` считает ошибку первичной загрузки фатальной, но при уже наполненной `region_data` продолжает старт; это operational fallback, не подтверждение свежести данных. [Entrypoint](../backend/entrypoint.sh#L20-L44).

**API.** Месячный `/regions/{slug}/i/{code}/monthly` возвращает `frequency="monthly"`, точки `{year,month,value,label}`, ряд РФ и соседей; при отсутствии точек выбранного региона — 404, не пустой `series`. [API](../backend/app/api/regions.py#L575-L667). Годовой путь использует другую таблицу и форму. Тесты артефакта проверяют известные метаданные, диапазоны и дубли; месячный/годовой consumer проверять раздельно. [Тесты](../backend/tests/test_regional.py#L35-L165).

## 3. Мировые ряды и актуальность источника

**Provider и подтверждение.** National-core адаптер нормализует значения и upsert ряда, точек, extent и `world_dataset_state` в savepoint отдельной серии. Ошибка серии откатывает savepoint, ставит `status=error`, не валит все страны; job завершает страну и формирует `WorldIngestRun` со статусом `ok/partial`. [Ingest](../backend/app/services/world_national_ingest.py#L796-L865), [job](../backend/app/services/world_national_ingest.py#L1054-L1116). Eurostat выбирает first-seen/изменившиеся TOC-наборы. **История 27.09:** смена DSD без отдельной проверки отправляла pinned slices в quarantine; applied TOC timestamp на `error/quarantine` не продвигался. **Текущий локальный код после изменения 29.09:** job запускает loader с `--structure-check`; exact/remap/orphan проверяются до записи, quarantine остаётся при разломе структуры, успешная сверка допускает загрузку. Remap, parsed slice и dataset state/log фиксируются отдельными транзакциями — это не атомарная замена dataset (см. [актуальные уточнения](#актуальные-уточнения-контрактов--2026-09-30)). До bounded loader изменённые `ok` переводятся в `pending`; первые два завершённых shadow-прогона и env-флаг управляют публикацией. Shadow фиксирует аудит без записи данных. [Selection/state](../backend/app/services/world_eurostat_ingest.py#L138-L248), [structure/job](../backend/app/services/world_eurostat_ingest.py#L249-L280), [verdict/commit](../backend/app/services/world_eurostat_ingest.py#L424-L463), [история и основание](adr/0011-world-eurostat-data-plane.md#2026-09-29--смена-структуры-автоматическая-сверка-вместо-вечного-карантина). Новая runtime-проверка этим описанием не выполнена.

**Null/stale/provenance.** `WorldIndicator` хранит `provider` как машинную идентичность, `source`/`source_url` как публичное происхождение, `history_start/end` и `points_count` как extent, `is_listed` как публикационный фильтр; у точки `value` не nullable. `WorldDatasetState.last_success_at=null` означает отсутствие подтверждённого успеха, `status=pending/error/quarantine` не равен свежему `ok`. Это особенно важно для Eurostat forecast. [Модель](../backend/app/models.py#L233-L315), [ADR-0012](adr/0012-world-multi-provider-official-first-forecasts.md#2026-09-24--v2-полный-горизонт-и-единый-строгий-допуск).

**API-режимы.** Мировая карточка отдаёт `provider/source_url`, `history_start/end`, `archived`, матрицу `modes`, частоты и варианты. `archived` вычисляется из конца истории и означает устаревшее покрытие, не удаление ряда. `/world/indicators/{slug}/{code}/data` отдаёт `mode`, `source_code`, `frequency`, `aggregated`, `aggregation` (объект только для агрегированного режима, иначе `null`), `points`, `forecast` (может быть `null`) и `count`. При неизвестном режиме/коде не подставлять чужой ряд молча; consumer должен использовать `source_code`/`aggregation.source` для подписи семантики. [Meta](../backend/app/api/world.py#L2054-L2085), [Data](../backend/app/api/world.py#L2279-L2303).

**Прогноз мира.** Отдельные `world_forecasts/world_forecast_values`; публичен только `gate_status=passed` с `model_params.method_version=2`, а для Eurostat дополнительно нужен подтверждённый актуальный `world_dataset_state`. `forecast_available=false` и `forecast=null` — допустимый результат строгого quality gate/состояния источника. Старые `advisory` и v1 не трактовать как текущие. [Модель](../backend/app/models.py#L372-L425), [gate](../backend/app/services/world_forecaster.py#L21-L32), [ADR-0012](adr/0012-world-multi-provider-official-first-forecasts.md#2026-09-24--v2-полный-горизонт-и-единый-строгий-допуск).

**Сравнение стран, дополнение 2026-09-28.** `/world/compare/catalog` отдаёт один ряд на страну и понятие с родной единицей, `peer_mode` и `value_adjust`; для России CPI указывается единица годового изменения, %, а не база индекса цен. На мировой карточке индексы цен с разными базами объединяются только как темпы одной частоты; процентный ряд не переводится в базу 100. В полном `/compare` разные базы индекса цен требуют общей базы по совпадающей дате, а процентные ряды из неё исключаются. [Producer](../backend/app/api/world.py), [выбор режима](../backend/app/services/world_compare.py), [consumer](../frontend/src/lib/useCountryComparison.js), [проверка](../frontend/src/lib/compareRepresentation.test.js).

## 4. Субнациональные данные вне России

YAML-паспорт описывает страны/территории/ряды. FRED CSV даёт исторический ряд, BLS может заменить свежие точки, не стирая долгую историю; при ошибке BLS overlay FRED-точки всё же могут быть записаны, но `SeriesReport.status="error"` сообщает деградацию overlay. Пропущенная/пустая серия — `skipped`, ошибка fetch — `error`. Коммиты идут после metadata и каждой пары серия×территория, то есть это не единая транзакция всей страны. [Ingest](../backend/app/services/world_subnational_ingest.py#L592-L699), [тесты](../backend/tests/test_world_subnational.py#L82-L155). BEA ZIP использует hash(payload+catalog) для пропуска неизменённого архива, пишет национальные и 51 штатный ряд с `WorldDatasetState` и одним commit; кэш `world/ssr-world/world-catalog` бампается после commit. [BEA](../backend/app/services/world_bea_regional.py#L323-L420).

`/world/countries/{slug}/regions/region/{slug}/{code}` отдаёт `series`, optional `national`, `rank`, `last_value`/`last_period` (могут быть `null`), `source_url` строится из template и series id. Период нормализован в точке `date` плюс `year/month/quarter/label`; точную частоту брать из `indicator.frequency`, а не угадывать из даты. [API](../backend/app/api/world_subnational.py#L442-L451), [payload](../backend/app/api/world_subnational.py#L546-L587).

## 5. Календарь публикаций

Public guard требует `official_explicit` либо `official_rule` **только с `source="cbr"`**, `is_estimated=false` и заполненных `event_key`, `source_url`, `source_hash`, `last_seen_at`. Прошедший `scheduled_date` без `actual_value` становится `awaiting_confirmation`; значение `released` нельзя выводить только из времени. `source_hash` и `last_seen_at` — provenance наблюдения, `actual_value=null` — отсутствие подтверждённого факта, не ноль. [API](../backend/app/api/calendar.py#L19-L85), [регрессия](../backend/tests/test_calendar_truth.py#L21-L52), [ADR-0005](adr/0005-official-calendar-source-bound.md#2026-09-10--evidence-must-survive-scheduling-and-source-outages).

## 6. Пользователь, сессия и аналитические числа

**Разбор сессий (локальная реализация 2026-09-30).** `session_analysis_reports` объединяет сохранённые behavior/business-события и маскированную запись `session_replay_chunks`; список и сводка охватывают все доступные сессии через пагинацию. Сессия браузера не становится числом физических людей. Факты, гипотезы, неизвестное и рекомендации ссылаются на доказательства; лимит отчёта 20 000 событий раскрывается отдельно от полного постраничного потока. Фоновая очередь проходит ID всех поступивших событий, пересматривает поздние поступления и не теряет ревизии при ожидании AI. AI по умолчанию выключен; внешней модели передаётся только очищенная сводка, её ссылки на доказательства валидируются. [Engine](../backend/app/services/session_analysis.py), [queue](../backend/app/tasks/session_analysis.py), [admin API](../backend/app/api/admin_session_analysis.py).

**Запись и внимание.** Отказ от аналитики немедленно очищает неотправленную очередь; формы, поля ввода и private-маршруты исключены. Реплей реконструирует DOM, не доказывает пиксельную точность и не сохраняет Canvas-графики. Collector ограничивает тело 64 KiB, отдельную запись 8 MB и час посетителя 16 MB; чтение ограничено 16 MB, каждый пропуск явный. Повтор фрагмента идемпотентен, конфликт отклоняется; хранение по умолчанию 14 дней. `block_view.visible_ms` требует видимости, фокуса и проверки перекрытия, `active_ms` отдельно опирается на недавний доверенный ввод; вложенные блоки нельзя суммировать в время сессии. Прокрутка сохраняет геометрию и валидность, INP — target, тип, исходное время и фазы задержки. Эти показатели не доказывают чтение или удовлетворённость. [Recorder](../frontend/src/lib/sessionReplay.js), [replay](../backend/app/services/session_replay.py), [collector](../backend/app/api/session_replay.py), [measurement](../frontend/src/lib/behavior.js).

**Identity.** `users`/credentials/OAuth/consents/audit в Postgres, opaque `fe_sess` и CSRF secret — в state Redis; cookie `XSRF-TOKEN` и заголовок `X-XSRF-TOKEN` обслуживают write-запросы. Сессия имеет sliding TTL, `logout-all` использует индекс пользователя; DB 0 cache и state Redis нельзя восстанавливать одинаково. [Сессия](../backend/app/services/session.py#L1-L83), [CSRF](../backend/app/security/auth.py#L99-L108), [модель](../backend/app/models.py#L1373-L1425).

**Сбор.** `/analytics/events` и `/analytics/behavior` — first-party POST collectors, они не требуют внутреннего `X-Analytics-Token`; отключение/отсев шумного UA возвращает `accepted=false`, а не нулевой аналитический факт. `session_id`/`visitor_id` хэшируются. Behavior batch ограничен максимумом, `batch_id` дедуплицируется через state Redis на 1 час и при недоступности Redis fail-open допускает дубль; `session_start` upsert портрета, pageview без него создаёт синтетический портрет. Гео выводится из IP, сырой IP в `BehaviorSession` не записывается. [Collectors](../backend/app/api/analytics.py#L258-L289), [batch](../backend/app/api/analytics.py#L544-L655), [portrait](../backend/app/api/analytics.py#L319-L401). Внутренний `/analytics/health` требует именно заголовок `X-Analytics-Token` и считает все строки `AnalyticsSyncRun.status=failed`, а не скользящие 24 часа. [Health](../backend/app/api/analytics.py#L25-L28), [ответ](../backend/app/api/analytics.py#L100-L128).

**Замер платного спроса «API и выгрузка с прогнозом» (2026-10-05, локально, не выпущено).** «Фальшивая дверь»: флаг `RUSTATS_API_INTEREST_ENABLED` (по умолчанию `false`, передан в compose для web backend) включает две точки входа (`ApiInterestLink` в тулбаре `IndicatorChartSection` и под CTA в `DownloadLimitModal`) и окно `ApiInterestModal`. Фронт узнаёт флаг из `GET /api/v1/api-interest/config` (`{enabled}`, `Cache-Control: no-store`; без пересборки фронта). `POST /api/v1/api-interest` открыт гостям (без CSRF, как `/auth/login`): `{email, use_case, comment?, source, indicator_code?, website}`; `use_case` — один из `analytics_treasury / planning_contracts / consulting / research / study / journalism / other`; при выключенном флаге — 404. Защита: honeypot `website` (бот получает `{ok:true}` без отправки), шумовой UA отсеивается, не более 5 заявок/час с IP и один дубль почты за сутки (state Redis, ключ — SHA-256 почты; при недоступном Redis fail-open), поверх общего `RateLimitMiddleware`. **Хранения заявок нет и миграции нет:** заявка идёт в Telegram всем получателям дайджеста с пометкой «Заявка на API» (`notify_api_interest`, `kind=api_interest`, входит в `RESEND_KINDS` — недоставленное досылается job'ом; realtime-флаг заявку не глушит). Единственное место хранения почты — текст в `telegram_outbox` (как у обратной связи); в логи и `frontend_events` она не пишется. 503 только если Telegram не настроен вовсе. События: `api_interest_view` (tier technical, 1 раз за сессию на точку входа), `api_interest_click` (intent), `api_interest_submit` (macro) — параметры `source`, `indicator_code`, `use_case`, без почты. [API](../backend/app/api/api_interest.py), [формат и рассылка](../backend/app/services/alerting.py), [клиент](../frontend/src/lib/apiInterest.js), [события](analytics_api_inventory/frontend_instrumentation.md). Неизвестно: реальный спрос; включение на production и доставка в боевой чат не проверялись. При включённой записи сессий убедиться, что поле почты маскируется реплеем (в этом пакете не проверялось).

**Веб-приложение (PWA, 2026-10-05, локально, не выпущено).** Сайт устанавливается на телефон из браузера. **Манифест** `/manifest.webmanifest` и **офлайн-страница** `/offline.html` отдаёт backend отдельно для каждого origin (язык по Host, как `robots.txt`: apex = en, `ru.` = ru; `Cache-Control: no-cache`, `Vary: Host`; nginx проксирует, geo-редирект apex→ru их не трогает). Иконки (192/512 any, 512 maskable, `apple-touch-icon.png` 180) лежат в `frontend/public` и пересобираются `scripts/build-pwa-icons.py`. `<link rel="manifest">`, `apple-touch-icon` и iOS-мета есть и в оболочке `index.html`, и в SSR-голове (`PWA_HEAD_META`, ссылки SSR берёт из оболочки). **Service worker** `/sw.js` — статический, `Cache-Control: no-store`; токен версии подставляет Vite на каждой сборке, `skipWaiting` + `clients.claim`, старые кэши `fe-` чистятся при активации. Он **не кэширует HTML, API и данные**: единственный кэш — офлайн-страница и иконка; перехватываются только навигации, при отказе сети отдаётся офлайн-страница (устаревшие цифры показать невозможно). **Аварийный выход без пересборки:** `RUSTATS_PWA_ENABLED=false` → `GET /api/v1/pwa/config` отдаёт `sw_enabled=false`; страница (`lib/pwa.js`) снимает регистрации и кэши, сам SW при активации и раз в 30 минут при навигации делает то же. `RUSTATS_PWA_INSTALL_PROMPT_ENABLED=false` прячет окно и пункт в подвале (по умолчанию оба флага `true`). Конфиг недоступен — SW не трогаем. **Caddy:** CSP получил `worker-src 'self'` (иначе service worker падал в `child-src` без `'self'`), `child-src 'self'`, `manifest-src 'self'` — правка в `Caddyfile` не выкатывалась. **Приглашение установить:** политика в `lib/pwaPolicy.js` (после полезного действия или второго захода, не раньше 15 с на странице; «Не сейчас» откладывает на 3 → 7 → 14 → 30 дней, дальше раз в 30 без лимита; установившим — никогда; постоянного «Больше не показывать» нет сознательно — это противоречит цели удержания; только телефоны/планшеты, не iframe, не `/embed`, `/admin`, `/login`, `/register`, `/account`, не поверх баннера согласия, модальных окон и нуджа регистрации). Установка определяется по `appinstalled`, `display-mode: standalone`/`navigator.standalone` и `getInstalledRelatedApps` (в манифесте есть `related_applications`) и запоминается в `localStorage` (`fe:pwa:v1`). Ограничение: на iOS событий нет, а хранилище Safari и приложения с экрана «Домой» раздельны, поэтому установку из Safari распознать нельзя — iPhone-подсказка возвращается раз в 30 дней после «Понятно». Для apex-посетителя из РФ действует гео-редирект на `ru.`: установленное с apex приложение уведёт такого человека на другой origin. События: `pwa_install_prompt_view/accept/dismiss`, `pwa_install_native_accepted/dismissed`, `pwa_installed`, `pwa_app_launch`, `pwa_ios_hint_view`, `pwa_install_entry_click` (параметры — только `platform`, `dismiss_count`). [API](../backend/app/api/pwa.py), [service worker](../frontend/public/sw.js), [политика](../frontend/src/lib/pwaPolicy.js), [клиент](../frontend/src/lib/pwa.js), [nginx](../frontend/nginx.conf), [Caddy](../Caddyfile). Не проверено: реальная установка на телефон, iOS-Safari вне эмуляции WebKit, Яндекс Браузер, production-CSP после выкладки Caddyfile.

**Подготовка к web-push, БЕЗ отправки (2026-10-05, локально, не выпущено).** Всё закрыто по умолчанию: `RUSTATS_PUSH_SUBSCRIBE_ENABLED=false` (эндпоинты `/api/v1/push/subscribe` и `/unsubscribe` отвечают 404, публичный ключ клиенту не отдаётся), `RUSTATS_PUSH_SEND_ENABLED=false` (сервис `app/services/web_push.py` отказывает исключением `PushSendDisabled`, даже в сухом прогоне), `RUSTATS_PUSH_DRY_RUN=true` (при включённой отправке в сеть всё равно ничего не уходит; вызывающий код может только усилить сухой прогон, но не обойти настройку). Реальная отправка требует всех трёх: `push_send_enabled=true`, `push_dry_run=false` и ключей VAPID из окружения (`RUSTATS_VAPID_PUBLIC_KEY`, `RUSTATS_VAPID_PRIVATE_KEY`, `RUSTATS_VAPID_SUBJECT`); ключи генерирует `scripts/generate-vapid-keys.py` (печатает в stdout, файлов не пишет, в репозитории их нет; приватный ключ не логируется и не отдаётся API). Ни одно задание планировщика отправку не вызывает (тест `test_nothing_schedules_or_imports_push_sender`). **Хранение:** таблица `push_subscriptions` (миграция `20261005_push_subscriptions` поверх `20261004_session_changes`): `endpoint`, `p256dh`, `auth`, `endpoint_hash` (SHA-256, уникален), `user_id` (FK `users.id` ON DELETE CASCADE, для гостей NULL), язык, укороченный User-Agent, счётчики сбоев, `revoked_at`. **Приём подписки:** `POST /api/v1/push/subscribe` и `/unsubscribe` открыты гостям и вошедшим (без CSRF-сессии, как `/api-interest`); адрес должен быть https с доменным именем (не IP, не `.local`/`.internal`, не userinfo), ключи — base64url заданной длины; не более 10 запросов в час с IP (state Redis, `fe:push:ip:*`, при недоступном Redis fail-open); повторная подписка того же адреса обновляет ключи, снимает `revoked_at`, обнуляет счётчик сбоев и, если есть сессия, перепривязывает `user_id` к вошедшему; владелец адреса не проверяется — подписку и отписку определяет знание `endpoint` (риск низкий: адрес не угадывается, наружу не отдаётся). **Приватность:** адрес подписки и ключи шифрования — **персональные данные** (по ним можно слать сообщения на конкретное устройство и связать устройство с аккаунтом): не логируются, не возвращаются в ответах, не попадают в аналитические события; отписка удаляет строку целиком, удаление аккаунта — каскадом, мёртвая подписка (404/410 от push-сервиса) гасится; в итог выгрузки данных аккаунта (`/account/export`) подписки пока не включены. **Перед включением подписки нужно обновить публичную Политику конфиденциальности** (категория данных, цель, срок хранения, способ отписки) — это текст для юриста/владельца, в пакете не менялся. Клиент: `lib/pushSubscription.js` (запрос разрешения только после `confirmedByUser: true` и только если сервер вернул `push_enabled`; нигде не импортируется — тест следит) и обработчики `push`/`notificationclick` в `sw.js` (открывают только страницы своего origin). Зависимость `pywebpush==2.5.0` (и транзитивные) закреплена в `requirements.txt`/`constraints.txt`; образ backend собирается, `pip check` чист. [API](../backend/app/api/push.py), [сервис](../backend/app/services/web_push.py), [модель](../backend/app/models.py), [миграция](../backend/alembic/versions/20261005_push_subscriptions.py), [клиент](../frontend/src/lib/pushSubscription.js). Не проверено: реальная доставка пуша, поведение на iOS (push только из установленного с экрана «Домой» приложения), миграция на боевом Postgres (проверена на SQLite против модели).

**Семантика BI.** Клиентская сессия/уникальный visitor, серверная 30-минутная сессия и визит Метрики — разные измерения. `Period` задаёт полуинтервал UTC и календарные даты МСК; North Star BI считает `ServerSession` без ботов и внутренней активности, `visitors` — distinct `visitor_id_hash`, Метрика остаётся сверкой. Сессионизация и rollups запускаются отдельными короткими `analytics_session` фазами; ClickHouse — асинхронная производная копия. [Period](../backend/app/services/analytics_period.py#L1-L85), [North Star](../backend/app/services/analytics_marts.py#L318-L349), [rollups](../backend/app/tasks/analytics_rollups.py#L592-L610), [CH](../backend/app/services/clickhouse_sync.py#L1-L18).

**Контракт админ-ответа.** BI-проверка администратора идёт короткой public DB-сессией, тяжёлая сборка — фоновой analytics-сессией; cold miss возвращает `202 {status:"building"}`, успешный/stale снимок содержит `cache_meta.{age_sec,stale,refreshing}`, ошибка — 503. Внутрипроцессный `_INFLIGHT` не доказывает координацию между несколькими web-воркерами; отсутствие такой гонки/перегрузки **не проверялось** в этом docs-аудите. [API](../backend/app/api/admin_bi.py#L53-L145), [route](../backend/app/api/admin_bi.py#L193-L272).

## 7. Поиск и допустимая область (локальная версия 2026-09-30)

`GET /search` публичен: `q` 1–256 символов, `limit` 1–100 (default 50),
локаль действующего API; валидация входа — 422. Ответ содержит `results`,
`total` (returned count), `has_more` (включая candidate clipping),
`version=federated-v2`, `intent.{countries,regions,year,month}`; при пустоте
может содержать reason `unsupported_query`/`unsupported_period`/
`ambiguous_geography`/`no_coverage`, при исправлении — `corrected_query`.
Метаданные кандидата имеют `key`, `kind`, локализованные имена, path/score и
соответствующие типу code/географию/частоту/единицу. [API](../backend/app/api/search.py),
[service](../backend/app/services/search.py), полный [контракт](search.md).

V2 защищает подтверждённый code/native title до разбора даты; для покрытых typed
concepts требует экономическую меру в имени/коде, а explicit quantity/frequency
проверяет в metadata. Набор typed guards конечен и не покрывает все меры.
SQL и Python используют общие guard definitions до и после bounded retrieval;
unknown qualifiers не отбрасываются. Короткие autocomplete совпадают только
с началом реального имени/кода компактного каталога. UI homepage отправляет
raw query в тот же глобальный endpoint; локальные поля сохраняют свой pool.
Обязательные native-denominator, валюта, масштаб и единица не конвертируются
друг в друга. Для покрытых ролей количество получателей, денежная сумма,
ставка, остаток, выдача и трудовой доход различаются shared measure guard.
Обычные слова/дефисы не становятся guessed code или typo-control.
Повтор всей сохранённой истории и отдельный relevance oracle описаны в
[датированном отчёте](research/search-history-replay-2026-09-30.md).

Общий Indicator контур: active ряд с конечным фактом, unlisted допускается
через `russia_search_path`; DXY/US10Y и materialized siblings могут иметь
US issuer по действующему market registry при прежнем storage/URL.
World: активная страна и конечный ненулевой факт, включая доступные hidden
slices; регионы: listed определения с фактом нужной территории и частоты.
Явная география, fact-date и поддержанные explicit-frequency predicates
ограничивают выбор до LIMIT; regional annual intent требует annual факта,
месячный ряд не подменяет его. Дополнительная world destination eligibility
(hidden year, несовместимая с month native frequency, canonical year+mode)
пока отбрасывается после budget/batch resolution. Это ограничение recall,
отдельное от обязательных native predicates; [подробности](search.md#намерение-кандидат-и-область).
Native world level означает сохранённую меру (включая rate), не только индекс.
Всего может быть больше
совпадений, чем извлечённый budget; total не является full catalog count.
Разные slice keys не склеиваются по одному URL. Период открывается document
navigation только при поддерживаемом route/факте; mode не отбрасывается
молча. Hidden world row не выдаётся document period без listed SSR права.
`world_search_paths` читает sibling/merge metadata одной SELECT на ranked
порцию по тем же card/merge/rank определениям canonical resolver.
Месячные региональные period destination пока отсутствуют.

Поиск read-only, не имеет commit/cache invalidation/jobs. Локальные поля
меняют matching/ranking внутри исходного eligibility pool, таблица —
даты/значения уже загруженных точек. UI loading/error/empty различимы и
pending не записывается как ноль результатов. Глобальная telemetry содержит
interaction_id и весь returned candidate set до 100 keys; это не measured
viewport exposure. Исторические параметры старых событий не мигрируются;
каждый input edit не собирается. [Instrumentation](analytics_api_inventory/frontend_instrumentation.md),
[ADR-0016](adr/0016-federated-public-search.md), [история](research/search-history-2026-09-30.md).

## Транзакции, кэш и проверка при изменении контракта

| Изменение | Точка commit / инвалидирование | Минимальная проверка |
|---|---|---|
| Федеральный парсер/формула | Парсер: commit после upsert/forecast/invalidate; derived: commit делает scheduler после closure. Redis `fe:{ns}:vN:*` бампается по изменившемуся коду, листингу и dashboard. [Parser](../backend/app/services/base_parser.py#L182-L231), [cache в HEAD](../backend/app/core/cache.py#L218-L304). | Повтор без изменений `(0,0)`, in-place ревизия, `parsed_zero/fallback_used`, зависимый derived и API после cache-hit. [ETL tests](../backend/tests/test_etl_statuses.py#L92-L129), [derived ops](../backend/tests/test_derived_ops.py). |
| World ingest | National-core — savepoint серии/commit страны; Eurostat — remap commit отдельно, parsed slice и dataset state/log в своих транзакциях, namespace bump в конце loader; BEA — commit архива; subnational FRED — commit каждой пары. `world`, `ssr-world`, `world-catalog` бампать только после подтверждённой записи. [National](../backend/app/services/world_national_ingest.py#L1054-L1116), [Eurostat commit](../backend/scripts/load-world-eurostat.py#L431-L526), [BEA](../backend/app/services/world_bea_regional.py#L410-L420), [subnational](../backend/app/services/world_subnational_ingest.py#L682-L753). | Source failure против missing series; structure accepted/remap/orphan либо quarantine при разломе, без advance TOC на error/quarantine; same-value revision, `forecast=null`, RU/EN payload. [Eurostat tests](../backend/tests/test_world_eurostat_ingest.py), [subnational tests](../backend/tests/test_world_subnational.py). |
| Regional artifact — история до F03 | Metadata commit отдельно; count guard или `TRUNCATE`/COPY/commit, API-кэш регионов имеет TTL. Эти прежние границы заменены [новым контрактом](#региональный-контур-f03--2026-09-30). | Сверить значения артефакта и БД, а не один count; прогнать годовой и месячный consumer и проверить cache-expiry/инвалидацию. |
| Аналитика | Коллекторы commit batch; rollup-фазы commit раздельно; BI snapshot TTL 24 ч с окнами свежести 5/15 мин. [Collector](../backend/app/api/analytics.py#L641-L655), [rollups](../backend/app/tasks/analytics_rollups.py#L592-L610), [BI](../backend/app/api/admin_bi.py#L53-L125). | Различить сессии и людей, МСК-границы, late/duplicate batch, пустой и stale BI; тесты — [`test_analytics_api.py`](../backend/tests/test_analytics_api.py), [`test_analytics2.py`](../backend/tests/test_analytics2.py), [`test_analytics_engine.py`](../backend/tests/test_analytics_engine.py). |

### Непроверенные риски и следующий доказательный шаг

> Дополнение 2026-10-04: пункты 1–2 ниже описывают срез 27.09. С тех пор локально закрыты F07 (блокировки фоновых задач с продлением — `services/job_lease.py`, общий lease `etl`) и F14 (`apply_action` аналитики записывает исход до исполнения и идемпотентен); оба ещё не выпущены на боевой.

1. **Региональный count guard:** при том же числе строк изменённые значения артефакта не вызывают reload по текущему условию. Сделать контролируемый тест ревизии одной точки в отдельной БД и сравнить с ожидаемым артефактом; не объявлять текущую продовую БД несогласованной без проверки.
2. **Кэш против commit:** федеральный `BaseParser` и derived бампают namespace до commit; это порядок кода, не воспроизведённая гонка. Проверить конкурентное чтение на отдельной БД/Redis при паузе перед commit, а затем свежесть detail/data/SSR. Ручной `FLUSHDB` не заменяет проверку.
3. **BI между воркерами:** `_INFLIGHT` и `_DASHBOARD_LOCK` — process-local. Проверить холодные одновременные запросы через несколько web-воркеров на тестовом окружении и нагрузку Postgres; не называть прошлую BI-проблему воспроизведённой.
4. **Восстановление:** `pg-backup.sh` и `/health/ready` проверяют создание файлов/возраст heartbeat, не успешный restore. **Ограничение среза 27.09:** full/identity restore ещё не был проведён, пригодность копии и RTO/RPO оставались неизвестны. **Датированная проверка 30.09:** свежие full/identity файлы доставлены на Mac со сверкой SHA-256/размеров; full dump и отдельный identity SQL восстановлены в изолированном PostgreSQL, выбранные числа строк/constraints/FK сверены. Это подтверждает пригодность именно проверенной пары. Owners/ACL, application login/API/SSR/jobs, полный failover, WAL/PITR, RTO/RPO, долговременный offsite и очередной плановый pull остаются непринятыми; 154,885 с — время `pg_restore`. [Протокол и пределы](code-review/backup-acceptance-2026-09-30.md#4-границы-результата), [runbook](enterprise_resilience.md#восстановление-и-наблюдаемость). Данный docs-проход restore не повторяет.

Для новой таблицы/поля/режима зафиксировать здесь identity, nullable/stale/provenance, producer, commit, namespace, публичный consumer и тест; затем обновить архитектурную карту проекта по [`workflow.md`](workflow.md#проверки-перед-коммитом).

## Изменения main после первоначального среза

<a id="параллельные-изменения-рабочего-дерева"></a>

При первом срезе `b684290067bf` этот блок описывал незакоммиченные изменения. Они вошли в локальную `main` к `c9c2d95` и повторно прочитаны при полном разборе. Production в read-only снимке 2026-09-27 остаётся на `e81b86e8`; новую миграцию `20260927_world_nonzero_idx` там ещё не наблюдали. Точный SHA файлов — в реестре разбора. Действующий локальный механизм:

- `world-catalog` получает поколение из state Redis, ключ `fe:world-catalog:g2:vN:*` и версионированную durable-копию; `/world/countries` читает поколение напрямую, использует межворкерный lock холодной сборки и допускает последнюю успешно опубликованную версию лишь в ограниченном stale-окне с `Cache-Control: no-store`. При ошибке до успешной SQL-сборки без пригодной резервной копии возвращает 503. После успешной сборки отказ публикации durable-кэша может вернуть собранный ответ с 200 и `Cache-Control: no-store`. [Cache](../backend/app/core/cache.py#L226-L309), [mirror](../backend/app/core/cache.py#L365-L503), [route](../backend/app/api/world.py#L850-L947). Для runtime-приёмки проверить concurrent bump/build и поведение при отказе state Redis.
- Субнациональный job бампает `world/ssr-world` при записанных точках или изменённых метаданных, включая частично записанные точки перед ошибкой страны; `world-catalog` — только при изменении метаданных. Метаданные сравниваются через `IS DISTINCT FROM`; commit по каждой паре остаётся. [Ingest](../backend/app/services/world_subnational_ingest.py#L418-L542), [job](../backend/app/services/world_subnational_ingest.py#L708-L753). Сверять тестами same-value/same-metadata, partial-failure и публичный country catalog.
- Добавлен partial index `ix_world_data_points_nonzero_indicator` и SQL-предикат `value <> 0` для холодного каталога стран. Модель/миграция входят в main; оценка плана запроса и времени сборки требует отдельного измерения. [Model](../backend/app/models.py#L282-L292), [query](../backend/app/api/world.py#L465-L480).
- Действующий [`scripts/deploy.sh`](../scripts/deploy.sh) запрещает `world-catalog` в `DEPLOY_CACHE_BUMP_NAMESPACES` (эта настройка работает с cache Redis), а новый partial index предварительно строит `CONCURRENTLY` до переключения backend. Недостроенный INVALID-индекс удаляется и создаётся повторно; Alembic revision оформляется при старте нового backend. В этом docs-проходе данный путь выпуска не запускался.

## Установленные границы реализации, 2026-09-27

Контракты выше описывают устройство и требуемые инварианты. Содержательный проход выявил места, где реализация может их нарушать: partial source response → удаление отсутствующих дат в national ingest; cache bump до commit в BaseParser; сохранение старых derived при пустом результате; разные eligibility-условия sitemap и SSR; неодинаковые выборки и усечение в BI. Точные механизмы и доказательства — [code-review-findings](code-review-findings.md), все элементы — [реестр кода](code-review.md). Эти нарушения не объявляются исправленными обновлением документации.


### Уточнение поиска 01.10: единицы, срезы и годовой режим

Проценты и процентные пункты — разные обязательные native facets. USD для
общей подписи dollars допускается только при объявленной валюте US state
producer; чужая валюта и отсутствующая unit не угадываются. Literal preflight
сохраняет целое действительное название внутри rawquery вместе с его
внутренними страной/датой/%; внешние слова, год, география и единицы остаются
обязательными. Это исправляет прежнюю описанную границу internal-title.

Eurostat slice qualifiers проверяют конкретную ось и её storedmember,
до candidateLIMIT и в Python. Total другой оси, category/SEO и отсутствующий
JSONmember не являются доказательством; ordinary bareall не снимается.
Слова о ежедневном использовании внутри economicdefinition отделены от
частоты наблюдений. Этот словарь конечен и не является обученной моделью.

Годовой поиск России может вернуть parent/year?mode только если shared
resolver рендерит тот же actualcode, для которого есть конечные факты года.
SSR использует nativeданные/единицу/title этого режима; canonical/hreflang/
соседние годы/graphlink сохраняютmode. Все supportedmode-year canonical
по замыслу входят в sitemap registry (**с 2026-10-04 публикация отложена**, см. статус в ADR-0003); обычная карточка canonicalбезmode. Подробности —
[ADR-0003](adr/0003-seo-single-source-server-rendered.md) и [search replay](research/search-history-replay-2026-09-30.md).
Worldmode-year и derivedmonth остаются unsupported, годы не отбрасываются.

Robots и Yandex Clean-param сохраняют identity годового mode; ограничения
query и ответственности REP/SSR — в [основном контракте поиска](search.md#crawl-policy-годового-режима-0110).

### Уточнение V5 01.10: независимые роли и нативные свидетельства

Частота исходного ряда и частота сохранённого результата — разные ограничения.
Source frequency берётся из объявленного native mode семейства; world frequency
её не заменяет. End-of-period подтверждается только последней операцией
`period_last` зарегистрированного pipeline либо полным native world названием.
Предыдущий шаг `period_last` внутри расчёта YoY не задаёт end-of-period identity.

Год базы постоянных/цепных цен не становится годом наблюдения. База и денежная
оценка требуют полного свидетельства внутри одной native unit подписи или,
для оценки в текущих/постоянных ценах, одного полного native title. Фрагменты
title и unit, либо двух переводов unit, не соединяются в выдуманное условие.
Чужая валюта/база/частота и неизвестное уточнение остаются обязательными.
Доказательство price subject у зарегистрированного товарного семейства требует
его категории и денежной единицы на физическое количество; одна currency unit
не превращает GDP или доход в товарную цену. SQL до LIMIT и финальный Python
guard проверяют эти условия на настоящих metadata, без подмены display label.

Новые named slice members остаются provider/axis/member контрактом, включая
string type JSON. TOTAL другой оси и `TOT_FTE` не равны универсальному total.
Конечная грамматика и ограниченные кеши чистых словоформ не хранят запросы
пользователей, выдачу или таблицу ответов. Проверки и границы переноса — в
[replay](research/search-history-replay-2026-09-30.md).
