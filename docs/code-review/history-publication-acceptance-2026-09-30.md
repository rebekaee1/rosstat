# Защита истории и публикация после commit — 30 сентября 2026

## Область

Первый пакет после сбора досье. База — локальная `main 506122b`. Исправляются
F01, F02 и F04; прежние воспроизведения и исторические документы сохранены.
Production, основной локальный PostgreSQL и внешние источники не изменялись.
Проверки используют синтетические ряды и отдельные временные базы.

## Принятые контракты

- **National-core / F01.** `WorldSeriesPayload` по умолчанию неполный:
  revision-aware upsert сохраняет отсутствующие даты. Только явные
  `is_complete=True`, `coverage_start`, `coverage_end` допускают удаление
  отсутствующих дат внутри этого включительного интервала. Полнота не выводится
  из HTTP 200, числа строк или min/max. Пустая полная выборка, неверные границы
  и точки вне окна отвергаются; отзыв всего ряда требует отдельного контракта.
  Ошибка/несовпадение identity откатывают savepoint серии. Нынешние адаптеры
  не заявляют доказанную полноту и остаются в режиме merge.
- **Федеральные парсеры / F02.** Владелец SQL-транзакции публикует source и
  изменившиеся derived-коды после успешного commit. CalculationEngine пишет
  только в переданную SQL-сессию и возвращает изменившиеся коды; hooks не
  публикуют незавершённую транзакцию. Ошибка кэша после commit не превращает
  сохранённые факты в failed fetch и не исключает source из derived-каскада.
- **Eurostat / F04.** Country metadata, remap и каждый parsed slice остаются
  отдельными транзакциями. Каждый реально записанный unit публикует
  `world/world-catalog/ssr-world` сразу после commit, до закрытия сессии.
  Ошибка следующего slice откатывает только его транзакцию; предыдущие
  изменения уже опубликованы. Remap сохраняет code/URL. Ошибка loader остаётся
  ошибкой; scheduler не продвигает applied TOC и не открывает прогноз как ready.

## Доказательства

До исправления тесты правильного поведения дали RED:

1. Реальный PostgreSQL: сохранены три даты, непустой ответ с одной ревизией
   оставляет одну дату. Потеря двух дат воспроизведена на тестовом ряду.
2. Реальная файловая SQLite, две сессии, BaseParser, upsert, Redis double и
   API-reader: при новой версии кэша reader видит прежнее значение 1,
   хотя после commit БД содержит 2. PG CONFLICT spelling адаптирован к SQLite.
3. Реальная SQLite-транзакция remap + controlled следующая ошибка в actual
   Eurostat run: новый hash сохранён, публикаций нет.

Регрессии — [national PostgreSQL](../../backend/tests/test_world_national_reconcile_pg.py),
[payload](../../backend/tests/test_world_national_reconcile_pg.py),
[парсеры](../../backend/tests/test_parser_publication.py),
[парсер PostgreSQL/Redis](../../backend/tests/test_parser_publication_pg.py),
[Eurostat](../../backend/tests/test_eurostat_publication.py),
[Eurostat PostgreSQL/Redis](../../backend/tests/test_eurostat_publication_pg.py).

Общая адресная проверка exact-current пяти новых файлов: **49 passed, 6.60 с**,
включая реальные PostgreSQL/Redis. Для F02 дополнительно пройдено 902 связанных
случая; для F01 — 228 совместимых national/job/adapter случаев. Независимое
чтение закрыло найденные ошибки metadata/SEO, precommit hooks/weekly и CLI,
cancellation outcome и URL query guards тестового окружения.

Реальный PG/Redis парсер без SQLite-адаптации: до commit writer=2, отдельный
reader/API=1, namespace прежний; после commit reader/API=2, namespace +1.
Eurostat API warm=10 → commit revision=20 → следующая SQL cardinality error:
новая генерация читает 20, неуспешная транзакция не публикуется.

PostgreSQL-тесты opt-in: `F01_TEST_DATABASE_URL` допускает только loopback и
базу `fe_f01_*`; каждый тест создаёт и удаляет собственную случайную схему.
Redis-тест требует отдельный loopback-port и DB14/15; обычные тесты не берут
application DATABASE_URL и не запускают внешние fetch/Telegram.

## Итог общего прогона

`./scripts/check-all.sh` завершён с exit 0, включая явно подключённые isolated
PG/Redis acceptance: **3111 passed, 9 skipped, 73 warnings** в backend;
**924 passed / 112 files** в frontend; lint **0 errors / 5 warnings**;
Vite build/precompress успешны, предупреждение крупных chunks сохраняется.
49 новых случаев уже включены в backend total, суммировать их повторно нельзя.
Knowledge/terrain/omissions/materials, indicator map, doc counters, page meta и
public-language guards прошли. Текущий реестр: **1317 файлов, 1001 code files,
8607 именованных определений**, все проверяемые аннотации актуальны.

Исходники после общего прогона не менялись. После записи этого протокола
materials/knowledge guard сверяется ещё раз. Тестовые контейнеры PostgreSQL и
Redis удаляются адресно; остальные контейнеры, пользовательские untracked
`.artifacts/` и `assets/` сохраняются. Пакет фиксируется локально, без push/deploy.

## Практические пределы

- PostgreSQL и Redis не стали одной атомарной системой. SIGKILL, неизвестный
  результат commit при обрыве соединения и отказ Redis требуют reconciliation;
  durable outbox этим пакетом не добавлен.
- Публикация Eurostat ждёт bounded попытку Redis при cooperative cancellation
  (15 секунд), затем возвращает отмену. Обычные DB0 namespace bumps сохраняют
  best-effort политику; world-catalog/state bump строгий, его отказ виден.
- Межпроцессный memo namespace живёт до пяти секунд. Свежесть каждого SSR/OG,
  весь 4-vCPU mixed workload и выпуск на production этой приёмкой не доказаны.
- Политика полноты national-core не меняет отдельный full-slice контракт
  Eurostat и destructive replace федеральных парсеров. Их upstream completeness
  требует собственных доказательств; прочие F03, F05–F14 остаются открытыми.
- Полнота инвалидации всех каскадных forecast-targets, прочие seed/gap-fill
  writers и SQL savepoints не объявлены исправленными. Старые утраты истории
  этим пакетом не восстанавливались; production loss не устанавливалась.
