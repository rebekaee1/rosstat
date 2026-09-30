# Итоги содержательного разбора main

## Последующее исправление F05/F06 и новый F05b — 2026-09-30

После `main 83c4555` воспроизведены разрыв сессии, потеря pageviewless dwell/цели
и late bridge на трёхдневной границе; реальные PostgreSQL транзакции подтвердили
пропуск меньшего незакоммиченного event id. Локальное исправление использует
SQL ownership/bounded stream и SHARE NOWAIT captured ceiling/revision replay.
CH event-метрики учитывают уникальные id после повторных вставок.
[Доказательства и ограничения](code-review/analytics-boundaries-acceptance-2026-09-30.md).

Найден **F05b**, постоянный дефект производной session-копии: replacing insert
не передаёт удаление старого visitor/start, а двухдневный cutoff пропускает
обновление сессии с более старым стартом. FINAL не устраняет отсутствующий
delete. Поэтому исправление PostgreSQL sessionize не закрывает правильность
всех CH session-витрин. Старые исходные findings ниже сохраняются с датами.

## Последующее исправление F03 — 2026-09-30

В пакете после `main c2a883d` равное число строк больше не скрывает годовые
ревизии; сидер сохраняет DB-only историю и live месячные значения, откатывает
metadata с ошибочным импортом. Каждый успешный месяц ЕМИСС публикуется до
следующего запроса; региональные API и OG ключи учитывают namespace version.
Исправлены native ОКАТО mapping и предыдущий месяц в хвосте ревизий.
[Проверки и ограничения](code-review/regional-publication-acceptance-2026-09-30.md).
Прежние описания F03 ниже остаются датированным свидетельством дефектов.
Локальное исправление не доказывает upstream truth, durable publication или
production freshness. Остальные findings сохраняются.


## Последующее исправление F01/F02/F04 — 2026-09-30

Исходные наблюдения ниже сохранены. В локальном пакете после `main 506122b`
national-core переходит на merge по умолчанию и bounded explicit replacement;
федеральный commit owner публикует source/derived после commit; Eurostat
публикует каждую записанную транзакцию до следующего slice. Сценарии RED и
реальные PostgreSQL/Redis проверки — [приёмка](code-review/history-publication-acceptance-2026-09-30.md).
На production пакет не применялся. Остальные findings сохраняют свой статус.

## Актуализация backend — 2026-09-30, `main 972579f`

Сохранённый разбор дополнен чтением изменённых блоков **63 backend путей** и их сквозных контрактов. Основание переноса неизменённых тел, конкретные named-function аннотации, файлы/диапазоны и границы тестов — [backend delta](code-review/backend-delta-2026-09-30.md). Новая дата не обновляет серверный снимок 27 сентября и не означает, что runtime-defects исправлены документацией.

| Прежнее наблюдение | Текущий статус по коду |
|---|---|
| Росстат ordinal после фильтра менял r2→r1 | **Исправлено:** ordinal назначается по полному DOCX до cutoff; [код](../backend/app/services/calendar_sources/rosstat_plan.py#L312-L368), [новая fixture](../backend/tests/test_rosstat_plan.py#L125-L151). Исторический пункт ниже объясняет причину изменения |
| Синхронный CH insert блокировал loop | **Исправлено в исходниках:** executor, column projection, bounded batches; [код](../backend/app/services/clickhouse_sync.py#L155-L416). Реальная завершённость sync, late-commit id cursor и resource acceptance отдельно |
| Безусловный Eurostat structure quarantine | **Заменено:** предварительная exact/remap/orphan проверка, code/URL сохраняется; [planner](../backend/app/services/eurostat_structure.py), [ADR-0011](adr/0011-world-eurostat-data-plane.md#2026-09-29--смена-структуры-автоматическая-сверка-вместо-вечного-карантина). Это не формальная проверка равенства методологий |
| Annual forecast на второй год | **Ограничено:** source/derived/world/subnational horizon и public filters = один следующий год; old annual fingerprint требует retrain. [API](../backend/app/api/forecasts.py#L51-L132), [pipeline](../backend/app/services/world_forecast_pipeline.py#L122-L199). Stored/prod acceptance не установлены |
| Sitemap correction не сдвигала shard lastmod | **Добавлено:** section_changed/content digest учитываются в index date; [код](../backend/app/services/sitemap_static.py#L288-L405). Реальное перечитывание и index inclusion отдельно |
| IndexNow exception теряла popped batch | **Exception ветка возвращает batch:** [drain](../backend/app/services/indexnow.py#L658-L724). Crash после SPOP или отказ Redis при возврате всё ещё не durable ack |

Новые статические вопросы требуют воспроизведения перед исправлением:

1. **Eurostat commit consistency:** [apply_remaps](../backend/scripts/load-world-eurostat.py#L515-L526) отдельно коммитит новый slice/hash до [persist_result](../backend/scripts/load-world-eurostat.py#L431-L472). Ошибка следующего slice может оставить прежние facts под новым slice и не достигнуть финального cache bump. Проверка: controlled failure после remap/первого slice, затем metadata/points/state/forecast/cache. Orphans сохраняются listed, допустимый порог включает до двух даже в маленьком наборе.
2. **Сессия через границу 3 дней:** [sessionize](../backend/app/tasks/analytics_rollups.py#L83-L234) не переносит предыдущий chunk; следующий pageview создаёт другую session, leading dwell/click без pageview отбрасывается. [Fixture окон](../backend/tests/test_analytics2.py#L797-L840) исключает boundary-crossing. Проверка: один visitor с 30-мин session и целью/dwell вокруг MSK boundary, сравнить whole-window/chunked result.
3. **Populations аналитики различаются:** Python isRobot/isRobotPro/headless и SQL only-headless не эквивалентны; CH raw visits ещё без этого фильтра, own sessions оцениваются hardware/поведением. [Predicates](../backend/app/services/analytics_marts.py#L138-L164). Подписать определения метрик и сравнить одинаковые fixtures; не объявлять весь оставшийся трафик людьми.
4. **CH streaming hold-time:** append events закрывают PG до insert, replacing stream держит analytics session во время CH network call; identity links всё ещё полностью материализованы. Executor исправляет loop blocking, не доказывает бюджет RAM/PG contention. Проверка на разрешённом runtime совместно с ops evidence.

Риски destructive history reconcile, invalidate-before-commit, региональных двух writers/count guard/fixed cache keys, SSR/sitemap eligibility и разнородных BI чисел из прежнего разбора остаются открытыми. Политика владельца «все действующие canonical в sitemap» сохраняется; demand-фильтры/массовое 410 не приняты. Полный audit, production restore/capacity и внешняя SEO-приёмка здесь не закрыты.

**Дата:** 27 сентября 2026. Кодовая основа — локальная `main` (`f8e239a` перед фиксацией этой документации), включая описанные рабочие изменения документации и её инструментов. Точные SHA-256, функции, контракты, побочные эффекты и тестовые границы каждого файла — в [реестре](code-review.md). Новые коммиты требуют проверки diff и обновления соответствующих рецензий.

Сервер проверен отдельно: [архитектура и бюджет 4 vCPU](architecture.md#реальное-окружение-сервер-с-4-vcpu-и-локальная-разработка), [машинный снимок](runtime-inventory.json), [профили локального запуска](workflow.md#локальная-разработка). Серверный `e81b86e` отличается от разобранной локальной main. Этот документ не устанавливает, что все найденные кодовые сценарии происходили на сервере.

**Последующая сверка, 30 сентября:** [сопоставление с анализом Opus](code-review/readiness-criteria.md#opus-reconciliation-2026-09-30) выполнено по `main c3ad382`; оно уточняет сохранённые риски, уже исправленные механизмы и границы предложений. Снимок сервера от 27 сентября не становится текущим по дате этой ссылки.

## Как читать результат

- **Воспроизведено изолированно** — небольшой вызов чистой функции или mock транспорта, без БД/сети/записи на сервере. Данные проверок — [probes.json](code-review/probes.json).
- **Подтверждено по исходникам** — условие, ветка и её последствие прослежены в коде; наличие соответствующих данных и частота срабатывания на production не измерены.
- **Наблюдение окружения** — значение прочитано на сервере/локальной машине в указанное время. Healthy не означает успешную работу всех заданий, восстановимость backup или запас производительности.

Полный список замечаний распределён по рецензиям файлов. Ниже — связи между слоями и приоритеты, которые нельзя увидеть из одного списка imports.

## 1. Целостность истории данных — первый приоритет

### Частичный ответ источника может удалять сохранённую историю

[world_national_ingest.py](../backend/app/services/world_national_ingest.py), `ingest_series` → `reconcile_points`: непустой ответ после нормализации считается полным набором дат; даты, отсутствующие в нём, удаляются. Пустой ответ не вызывает такого удаления. При этом адаптеры допускают сокращённый непустой ответ:

| Адаптер | Условие сокращения |
|---|---|
| [NBS](../backend/app/services/world_adapters/nbs_stats.py) | `_fetch_stream_merged` пропускает неудачные исторические leaf-загрузки, если хотя бы одна дала данные |
| [MoSPI](../backend/app/services/world_adapters/mospi_api.py) | `_fetch_all_rows_sync` прекращает чтение после 100 страниц по 200 строк даже при большем `totalPages` |
| [ABS](../backend/app/services/world_adapters/abs_data.py) | После timeout запрос меняется на последние 1200 наблюдений; явные границы исходного запроса локально не восстанавливаются |
| [BoE](../backend/app/services/world_adapters/boe_iadb.py) | Запрос с началом по умолчанию может последовательно сократиться с 2000 до 2010/2020 года |
| [BLS](../backend/app/services/world_adapters/bls_api.py) | Запрошенная глубина свыше 20 лет обрезается без разбиения на окна |
| [BCB](../backend/app/services/world_adapters/bcb_sgs.py) | Окна с 404, не-JSON или selected invalid-request ошибками могут быть пропущены |
| [e-Stat](../backend/app/services/world_adapters/estat_api.py), [FRED JSON](../backend/app/services/world_adapters/fred_stlouis.py) | Получается один ответ без проверки полноты пагинации |
| [StatCan](../backend/app/services/world_adapters/statcan_wds.py) | Без явных дат используется latest-N (по умолчанию 10000) |

**Статический вывод:** нужны явные `complete/partial`, область покрытия ответа и отдельные merge/replace операции. Удаление допустимо только в доказанно полном срезе. Для проверки — fixture с успешной новой частью и неудачной исторической частью; старые точки должны сохраниться. Это предложение контракта, ещё не реализованная защита.

Многие адаптеры вычисляют `source_hash` из количества, границ и последнего значения. Это не полный fingerprint истории. Однако текущий national ingest **не использует этот hash для skip**: возвращённые старые ревизии сравниваются по значениям. Поэтому нельзя объяснять потерю ревизий одним слабым hash; существенны полнота ответа и удаление отсутствующих дат.

### Частота, единицы и идентичность ответа

- [ONS](../backend/app/services/world_adapters/ons_timeseries.py), `select_frequency_rows`: при отсутствии нужной частоты выбирает другой массив, сохраняя частоту исходного reference. [MoSPI](../backend/app/services/world_adapters/mospi_api.py): annual IIP endpoint совмещён с парсером, которому нужен месяц. [StatCan](../backend/app/services/world_adapters/statcan_wds.py) и [ABS](../backend/app/services/world_adapters/abs_data.py) приближают некоторые неподдерживаемые частоты поддерживаемыми.
- BoE/FRED CSV, BoJ, Banxico и CCPR имеют fallback на единственную/вторую колонку или первый блок без строгого совпадения запрошенного кода. e-Stat/ABS могут получить несколько срезов и объединить их по датам. Проверять нужно весь ключ измерений и источник единицы, а не только число.
- [base_parser.py](../backend/app/services/base_parser.py), `run`: bump cache namespace предшествует commit. Конкурентный reader может заполнить новое поколение старым состоянием БД. Это статический race, не воспроизведённый конкурентный PG-тест.
- [calculation_engine.py](../backend/app/services/calculation_engine.py), `_execute`: отсутствующий источник или пустой результат операции оставляет прежние derived-точки. `run_for_updated_sources` после исключения продолжает зависимые расчёты, которые могут прочитать старый upstream. [derived_ops.py](../backend/app/services/derived_ops.py) отсекает неполный последний bucket, но более ранний неполный bucket может остаться.
- [world_pop_ingest.py](../backend/app/services/world_pop_ingest.py): результат США и state не закоммичены до последующей загрузки Бразилии; её rollback может отменить первую часть при счётчике, считающем США успешными.

## 2. Транспорт и отказоустойчивость

| Наблюдение | Статус и архитектурное следствие |
|---|---|
| [http_client.py](../backend/app/services/http_client.py): вызов без timeout передаёт `timeout=None`; `setdefault` не заменяет его | Воспроизведено mock транспорта. Задуманный default timeout не гарантируется |
| Там же: direct connection error → HTTP proxy error → исключение; SOCKS не вызывается | Воспроизведено mock транспорта. Заявленная цепочка fallback не выполняется в этом случае |
| [MoSPI](../backend/app/services/world_adapters/mospi_api.py), `_LegacySSLAdapter`/`build_session` | Отключены certificate/hostname checks; это часть текущего transport-контракта, а не только разрешение legacy negotiation |
| [NBS](../backend/app/services/world_adapters/nbs_stats.py), `_force_ipv4` | Меняет urllib3 address-family process-wide, без восстановления; влияет и на соседние источники |
| [RBA](../backend/app/services/world_adapters/rba_stats.py), `_csv_cache` | Нет TTL; повторное использование одного adapter instance может читать старую таблицу |
| [alerting.py](../backend/app/services/alerting.py), [webmaster_indexing_report.py](../backend/app/services/webmaster_indexing_report.py) | Антиспам/предыдущее наблюдение обновляются до подтверждённой доставки; неудачное уведомление может быть подавлено или потерять дельту |
| [telegram_bot.py](../backend/app/services/telegram_bot.py) | Polling offset продвигается и после ошибки handler; повторная доставка такой команды не гарантируется |
| [pulse.py](../backend/app/services/pulse.py) | `build_snapshot` может отправить alert через `_bot_signals`; старое описание «без побочных эффектов» неполно |
| [clickhouse_sync.py](../backend/app/services/clickhouse_sync.py) | Историческое наблюдение 27 сентября: синхронный `ch.insert` мог задерживать event loop scheduler. **Уточнение 30 сентября:** `e32abdf` вынес `_ch_insert` в executor; исправление подтверждено в текущем коде. Курсор `id` и полнота синхронизации требуют отдельной проверки; приёмка выпуска на сервере здесь не установлена |

Доработки должны сохранять различия read fail-open, auth/state fail-closed, retryable source error и partial success. Один общий `except → []` уничтожает важную для последующего слоя информацию.

## 3. Публичная витрина и SEO

- [site_urls.py](../backend/app/services/site_urls.py) включает `/russia/today/{code}` для активного индикатора с 0/1 точкой, тогда как [seo_today.py](../backend/app/services/seo_today.py) требует минимум две. Для мировых сравнений регионов sitemap проверяет наличие рядов, а [seo_world_subnational_compare.py](../backend/app/services/seo_world_subnational_compare.py) требует общий период. Это два статических пути sitemap → 404 при соответствующих данных. Нужна единая eligibility-функция.
- [seo_world_compare.py](../backend/app/services/seo_world_compare.py) сравнивает последние значения стран, даже когда даты различаются. При несовпадающих единицах видимый verdict может скрыть численную разницу, а meta description её всё равно выводит. Нужен единый comparison result с общей датой и признаком сопоставимости для текста и metadata.
- [seo_regional.py](../backend/app/services/seo_regional.py): monthly neighbor mapping построен как slug → id, но проверяется по числовому id; блок соседей остаётся пустым. Monthly FAQ использует прошлогодний `last_period - 100` рядом с месячной дельтой.
- [sitemap_static.py](../backend/app/services/sitemap_static.py), `_reuse_shard`: повторное использование проверяет URL digest и наличие файла по host, но не прежний origin. Смена схемы или alternate-origin при том же host требует отдельной проверки reuse.
- [indicator_seo.py](../backend/app/data/indicator_seo.py): тексты кредитных ставок обещают «один режим», хотя их FamilyDef содержит матрицу; текст топлива обещает недельный прогноз при разрешённом месячном. Старые curated тексты нужно сверять с актуальным движком, сохраняя историческую причину изменения.
- [ticker_sources/moex_iss.py](../backend/app/services/ticker_sources/moex_iss.py): `market_open` определяется наличием LAST, CBR fallback теряет дату наблюдения и не нормализует `Value/Nominal`. [binance.py](../backend/app/services/ticker_sources/binance.py): BTCUSDT публикуется под `btc-usd` без пересчёта.
- [calendar_sources/rosstat_plan.py](../backend/app/services/calendar_sources/rosstat_plan.py): ordinal ключа назначается после фильтра даты; при сдвиге окна r2 может стать r1. [official_calendar.py](../backend/app/services/calendar_sources/official_calendar.py) не интерпретирует timezone ICS; календарь рабочих дней ограничен 2026 годом.
- Frontend: `inflationCalc` считает изменение между соседними доступными годами без проверки соседства календарных лет; `WorldRatingPage` может остановить поиск на неполном fallback-году; `CalculatorPage` читает `label` вместо `labelKey`; `CalendarEventCard` скрывает нулевой прогноз truthy-проверкой. Подробные ветки и проверки — в рецензиях соответствующих файлов.

## 4. Аналитика: единица измерения и полнота выборки

[admin_bi.py](../backend/app/services/admin_bi.py) не выдаёт одну однородную выборку: собственные server sessions, browser portraits, raw pageviews и визиты Метрики имеют разные фильтры и единицы. Для сравнения их надо подписывать отдельно.

- `_retention`: один посетитель, вернувшийся на неделях 8 и 9, даёт `size=1, week_plus[8]=2`. **Воспроизведено чистой функцией.** Дедупликация выполняется до объединения всех недель ≥8 в bucket8.
- `_kpi_daily` и retention читают визиты без фильтра роботов, применяемого в `_load_window_visits`. Собственные acquisition slices и audience portraits используют другие фильтры, чем ServerSession. `portrait_coverage_pct` не гарантированно ограничен 100%.
- Navigation ограничена 40000 строками в порядке session hash, onsite search — 20000 последними событиями, dwell — 50000 строками без порядка. Признак усечения не возвращается. Bounce и Webmaster position усредняются без весов.
- `_soft_mart` подавляет ошибку, но не делает rollback: после SQL-ошибки PostgreSQL следующий запрос может получить aborted transaction. Пустой fallback некоторых витрин не отличим от отсутствия наблюдений.
- [dataset_inventory.py](../backend/app/services/dataset_inventory.py) использует оценки `reltuples` и выборку JSON-ключей до 200 строк; не перечисляет все мировые таблицы. Формулировку «всё точно пересчитано» применять к нему нельзя.
- [analytics_backfill.py](../backend/app/services/analytics_backfill.py) получает до 500 Metrika pages без пагинации; интервальные фразы записывает на дату конца окна. GSC/Вебмастер/Метрика имеют отдельные лаги и квоты; sitemap submitted не равен indexed. Сохранённые исторические исследования объясняют эти границы.

## 5. Что означает сервер с четырьмя ядрами

На датированном снимке VPS: 4 vCPU, 7,75 GiB RAM, 4 GiB swap, диск занят на 88%. Сумма RAM hard limits контейнеров — 7616 MiB; это не текущий расход и не reservation. Три web workers, один scheduler, PostgreSQL, Redis, ClickHouse, nginx и host Caddy конкурируют за общий ресурс. Суммарный верхний предел application DB pools — 73 соединения при 97 обычных доступных слотах.

Практические приоритеты из наблюдений:

1. Учёт роста диска: локальные backups занимают около 10,97 GiB; retention/логи/образы/ассеты рассматриваются вместе. Ничего не удалялось в ходе аудита.
2. Проверяемое восстановление backup и отдельное хранение: offsite-ветка текущего скрипта не настроена; наличие backup провайдера неизвестно; restore не выполнялся.
3. Разделение cache/state: production использует отдельный state Redis; локальные процессы пока используют DB1 cache-инстанса, хотя state-контейнер существует.
4. Наблюдение смешанной нагрузки SSR/API + ETL + BI. Один healthy response и занятый swap не дают ни оценки предельной аудитории, ни доказательства нехватки RAM.
5. Vite `5173`, Compose SSR `3000` и прямой API — разные профили. Backend image не обновляется от изменения исходников; Vite default proxy может направлять все методы к production. Точные команды и флаги — в workflow.

## Следующая архитектурная работа

Сначала закрыть контракты полноты истории и commit → invalidate, затем согласовать eligibility публичных страниц и определения аналитических метрик. Это можно сделать внутри существующего приложения с явными модулями и контрактными тестами.

После этого измерить самые дорогие SQL/SSR/ETL/BI пути на текущем ресурсном бюджете. Извлекать новый процесс или сервис стоит при доказанной потребности в независимом ресурсе/отказе/масштабировании. Само количество файлов или наличие 4 vCPU не обосновывает переход на микросервисы.

Приёмка последующих изменений: фикстура/контрактный тест → реальный PostgreSQL/Redis для транзакций и многопроцессности → локальный Compose SSR/API → отдельная разрешённая выкладка утверждённого SHA и внешняя проверка. Текущий аудит обновляет документацию и инструменты навигации; перечисленные runtime-дефекты этим документом не исправлены.
