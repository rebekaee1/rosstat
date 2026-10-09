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

Выпуск и замеры финального кода ещё не выполнены на момент этого текста.
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
