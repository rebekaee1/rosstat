# Производительность ForecastEconomy — 9 октября 2026

Исходный production SHA: 0bcf68b488d44a608b5e48ef56386daa14e72062.
За три часа журналы текущих контейнеров: 19 world/countries 503,
10 Rollups 15min failed. Холодные каталоги 11–39 секунд, генерация
v3118→v3124→v3127→v3130 в течение минуты. PostgreSQL EXPLAIN показывает
Parallel Seq Scan behavior_events и сортировку широких строк.
Оценка raw table: 2 747 822 live rows; total relation около 1986 MB.

## Изменения и основание

1. Partial normalized visitor/time covering index (pageview/dwell/click/move) + portrait visitor/started/SID index + literal empty key; narrow
   raw/history staging, ANALYZE промежуточных результатов, payload lookup
   только для touched logical sessions. Старое полное ownership/late bridge
   сохранено. Не уменьшены окна и не повышены timeout/память/workers.
2. Eurostat no-op не сбрасывает namespaces; фактическая point/metadata
   revision публикуется после commit; country catalogue сбрасывается только
   при изменении его входов/наличия nonzero signal.

Прежний незавершённый черновик оптимизации обнаружен в .artifacts и
использован как исходный материал: первая проверка на production через
rollback-only temp stages снова дала timeout. Финальная реализация
дополнена normalized covering index и узкими стадиями; чужой worktree
не изменён.

## Проверки

Изолированный PostgreSQL 16 на loopback 55441, временные схемы fe_f01_*.
Изолированный Redis на 55442, DB14/15. Caller boundary/equivalence,
site_locale/goals/change-log и real PG publication; same-value replay,
nonzero transitions, metadata, partial rollback, cancellation.
113 тестов прошли (один Redis opt-in на первом запуске пропущен);
повторный real-PG/real-Redis publication: 4 passed.

## Runtime и пределы

Runtime code 9eb29dcd выпущен approval-wrapper 57315651.
Миграция 20261009c_session_perf применена; оба индекса valid/ready.
Оба выпуска завершены; холодный каталог проверен в выпущенном контейнере.
Первый probe выполнял только temp SQL и rollback, постоянные raw/session
таблицы не менял. Проверки не гарантируют неограниченную нагрузку 4 vCPU.
Telegram ConnectTimeout остаётся отдельным внешним сетевым вопросом.

## Проверка на боевом объёме до выпуска

Rollback-only probe после partial index: 38 697 window visitors,
115 310 raw rows. Visitors 1.018 s, raw 0.869 s, history 1.041 s,
bounds 0.253 s, SIDs 0.594 s, goals 3.471 s. Для сравнения
промежуточный полный covering index давал raw 34.918 s и details
32.626 s; упорядоченное чтение + portrait index — raw 23.532 s,
details 9.760 s. SQL-план финального raw использует partial index-only
scan. Эти измерения являются точками под текущей нагрузкой, не p95
и не доказательством выполнения всего run_rollups.

## Выпуск и полный расчёт

Production: 57315651 (runtime target 9eb29dcd), 9 октября около 15:36 МСК.
Финальные индексы: partial history 313 MB, portrait 61 MB; два
промежуточных экспериментальных индекса удалены CONCURRENTLY.
Резервные копии: rustats_20261009_120038 и предрелизная
rustats_20261009_122942 (463 MB + 44 KB identity).

Локальный check-all прошёл: 4569 backend tests passed, 170 skips,
3168 frontend tests passed; lint/build/public-language/knowledge guards OK.
Точная миграция в изолированном PG: upgrade дважды (valid/ready),
downgrade удалил только два новых индекса; production downgrade не выполнялся.

Полный боевой run_rollups(days=2), с тем же scheduler lease:
sessionize 114.832 s (32 599 сессий), traffic 0.389 s (30),
goals 0.562 s (102), goal_dims 0.187 s (100), pages 5.681 s (29 250),
всего 121.694 s, signups 0; завершён с commit. Это время всего
расчёта, его нельзя заменять 0.9 s узкой raw стадии.

24 HTTPS GET (RU/EN, три прохода: /, /login, countries, map-series/gdp-usd)
все вернули 200. Первый проход 0.035–0.556 s, повторные 0.029–0.082 s
(TTFB/total с production host, compressed + YandexBot; это не LTE
телефона и не холодный каталог во время ETL).
34 representative RU/EN pages release gate прошли.
В IAB на 393×852 карта отображается, console errors нет;
снимок /tmp/fe-performance-20261009/mobile-map.jpg.

Следующий плановый Eurostat ещё не проходил: no-op и signal/revision
проверены на реальных изолированных PG/Redis, на проде проверена точная
версия loader. External Telegram ConnectTimeout этим выпуском не исправлялся.

## Дополнительная холодная проверка

Bypass-Redis rebuild на57315651 снова дал statement timeout30s.
После обычного VACUUM world_indicators (63k dead metadata rows,
all-visible pages76%→100%) original SQL всё ещё мог timeout.
Statistics1000 улучшила estimate nonzero IDs61k→212k при actual341k,
но original полная пересборка заняла40.541s. Поэтому VACUUM/statistics
не объявлены достаточным исправлением.

Materialized DISTINCT nonzero IDs + listed JOIN: SQL5.830s (268632 rows);
с существующей очисткой имён полный builder23.313s. Pure name cleanup
LRU8192 после overrides: полный builder6.661s,262495 hits/6137 misses.
Полное old/new payload сравнение в repeatable-read: equal; SHA256
81b4dfe511de4c6bcf784289c457e68b7d5a3b4e3d9d85e790414dc88df0d25e.
В этом отдельном сравнении оба прогона были warm (3.622/4.155s);
не выдавать это за cold disk или рост скорости каждого warm запроса.
53 world/API/cache/merge tests прошли до второго полного check-all.
Operator maintenance SQL применён; следующий auto-vacuum не наблюдался.

Первый штатный Rollups15min после выпуска: 15:46:42MSK,
sessions32626, traffic30, goals102, goal_dims100, pages29274, signups0.
Первый15min watch passed: ready=1, no OOM; одна первая проба5.598s
под maintenance, retry0.038s; остальные reported successful samples
0.034–0.858s. Это отдельные измерения, не p95.


## Второй выпуск и окончательная проверка

Выпущенный runtime: `597cbb04e621073bb236dbe629517d624093d780`; production approval-wrapper:
`034b05388e47dded59ef8dc1c67facff72f360b3`. Схема осталась `20261009c_session_perf`.
SHA256 обоих изменённых source files в контейнере совпал с локальным кодом.
Предрелизные копии `rustats_20261009_131521`: база 464 MB,
identity 44 KB. Эффективные параметры PostgreSQL подтверждены:
world_indicators autovacuum scale 0.01 / threshold 1000;
world_data_points.indicator_id statistics 1000.

Повторный `check-all.sh`: 4569 backend и 3168 frontend tests passed,
170 backend skips; lint/build/language/maps/knowledge checks прошли.
34 representative RU/EN release pages прошли. Все 24 HTTPS GET
главной, login, countries и map-series на двух хостах вернули 200;
полное время 0.030–0.781 s, из production host
с compressed YandexBot. Это серверная проба, не скорость LTE телефона.

Прямой полный builder, без Redis: на cutover при параллельных release
проверках первый процесс 30.711 s, второй проход 4.515 s. После release
gate новый процесс с пустым title cache: 4.943 s; повторный проход 4.754 s.
Все четыре payload содержат 55 стран и совпадают с исходным SHA256:
`81b4dfe511de4c6bcf784289c457e68b7d5a3b4e3d9d85e790414dc88df0d25e`.
Это cold application-cache замер с обходом Redis; файловый кэш ОС/PG
не сбрасывался. Измерения не являются p95 или гарантией любого уровня нагрузки.

В IAB на 393×852 после reload карта с данными отображается,
console errors нет. Снимок: `/tmp/fe-performance-20261009/mobile-map.jpg`.
Штатное 15-минутное наблюдение завершилось: все ready=1, backend/scheduler
OOM=false, reported successful TTFB 0.032–0.723 s.
Логи и повторяемые probes находятся в `/tmp/fe-performance-20261009/`.

Следующий штатный analytics job в новом scheduler: старт 16:29:54.602 МСК,
успешное завершение 16:31:41.993 (107.391 s, включая anomaly checks).
Rollups: sessions 32834, traffic 30, goals 102, goal_dims 100,
pages 29464, signups 0. Во время этого job watch сохранил ready=1;
отдельные home TTFB samples 0.318 s и 0.043 s.

Граница: улучшение подтверждено на проверенных страницах и боевых объёмах;
следующий Eurostat no-op запуск и последующий autovacuum ещё не наблюдались.
Внешний Telegram ConnectTimeout и скорость через конкретную мобильную сеть
этим результатом не считаются проверенными или исправленными.
Прямой anonymous HTTPS probe api.telegram.org с host: IPv4 connection
timeout 10 s до TLS, IPv6 connection failed; приложение в probe не участвовало.
