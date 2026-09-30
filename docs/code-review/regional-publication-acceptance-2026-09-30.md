# Региональные данные: сверка, writers и публикация — 30 сентября 2026

## Область

Второй runtime-пакет после досье, база локальной `main c2a883d`. Исправляется
F03, включая найденные в его сценариях ошибки ОКАТО и блокировок. Production,
основная локальная БД и внешние источники не изменены. Старые наблюдения BM03,
июльский аудит и ADR сохранены с датами; они больше не описывают исправленный
механизм. [Действующий контракт](../data-contracts.md#региональный-контур-f03--2026-09-30).

## Изменения

1. Сидер сверяет содержание через PostgreSQL temporary staging/COPY, чанки
   10 000. Годовые ключи вставляются/исправляются при изменении значения в
   точности Numeric(18,4); отсутствующая история не удаляется. Месячный
   артефакт вставляет недостающие ключи, сохраняет существующие live значения.
   Неизменные point rows не расходуют sequence ids на каждой перезагрузке.
2. Metadata, annual/monthly точки и фактические границы каталога commit вместе.
   Невалидные значения/месяцы, неизвестные ссылки и duplicate keys отвергаются;
   проверенные ошибки импорта и инъецированный отказ commit откатывают весь
   SQL-снимок. Четырёхзначные годовые
   строки fuel-файла не превращаются в месячные.
3. Seed и ЕМИСС берут общий transaction advisory lock перед SQL-записью.
   ЕМИСС получает HTTP-ответ до lock; commit/rollback освобождают его. Это
   предотвращает взаимный порядок metadata→point / point→metadata. SQL-only
   helper поддерживает year bounds по обеим сохранённым частотам.
4. Каждый изменённый месяц ЕМИСС публикует поколения после commit. Ошибка
   следующего месяца не скрывает предыдущий успешный. Исправлен default
   slug→ОКАТО-id → id→slug mapping, хвост включает текущий и предыдущий месяцы.
5. Все 8 regional API readers, существующий SSR и 4 regional OG readers
   следуют поколениям `regions`, `ssr-region`, `og-region`. OG disk digest
   также меняется, поэтому прежний файл не возвращается новым backend-запросам.

## RED → GREEN и границы тестов

- До исправления 6 real-PG seed cases выявили same-count скрытую ревизию,
  удаление дополнительной истории/live-конфликтов и отдельно сохранённые
  metadata при ошибочном импорте. Первоначальная ошибка fixture была исправлена
  созданием настоящих unique indexes; она не считается воспроизведением бага.
- Publication regressions воспроизвели старый API после committed month и
  later error/cancel, fixed API/OG keys и native ОКАТО mapping. OG renderer
  заменён payload double: проверяется generation/memory/реальный disk-cache,
  не визуальное качество PNG.
- Concurrent real-PG сценарий с новым 202701 месяцем дал
  `DeadlockDetectedError`: seed держал metadata, ЕМИСС держал новый point.
  Same-year проба не обновляла bounds и была недостаточной — она не служит
  доказательством исправления. Проверка с пересечением двух actual writers
  принимает оба commit и итоговое live значение.
- SQLite publication fixtures адаптируют PG conflict syntax/xmax; реальные
  PG/Redis tests отдельно проверяют genuine upsert added/updated, SQL rollback,
  committed visibility и генерации. Fetch/plan controlled; сеть ЕМИСС не нужна.
  SSR проверяет actual route и cache с явным восстановлением aliases,
  отключаемых общей autouse fixture.

Регрессии: [seed PostgreSQL](../../backend/tests/test_regional_seed_pg.py),
[publication](../../backend/tests/test_regional_publication.py),
[publication PostgreSQL/Redis](../../backend/tests/test_regional_publication_pg.py).

Final exact-current три новых файла: **38 passed, 10,00 с**, включая
настоящие PostgreSQL/Redis. Независимый связанный прогон 9 файлов —
**199 passed, 11,21 с** (F02, SSR/SEO/i18n и regional publication).
Полный `./scripts/check-all.sh` завершён с **exit 0**: backend **3149 passed,
9 skipped, 73 warnings / 81,08 с**; frontend **924 passed / 112 files**;
lint **0 errors / 5 прежних warnings**, Vite/precompress успешны (5,42 с),
предупреждение крупных chunks сохраняется. Карты, счётчики, page-meta и
public-language gates пройдены. PG/Redis opt-in были подключены и в общем run.

## Замер полного артефакта

Полный actual committed артефакт: **961 494 annual + 73 740 monthly** точки.
Отдельный PostgreSQL 16: **1 CPU / 384 MiB**; Python на Mac. Проверены первичная
загрузка, неизменный повтор и исправление одной annual точки при прежнем
count. Это замер локального механизма, не capacity общего production 4 vCPU.
Финальный source: **53,764 с** первичная загрузка, **9,122 с** неизменная
сверка, **5,601 с** исправление одной точки; peak RSS Python **95,56 MiB**.
Повтор сделал 0 вызовов публикации, исправление — 1. В этом замере Redis
заменён счётчиком вызовов; настоящая Redis-публикация проверяется отдельно
в указанных regression tests. В окружении параллельно
выполнялись локальные проверки; это одиночные наблюдения, не p95/SLA.
Предварительный замер (до выделения общей блокировки): 34,888 / 5,024 / 7,138 с,
96,52 MiB. Разница между прогонами не доказана как регрессия реализации.
Оба замера не переносимы на совместную production-нагрузку без нового опыта.
[Машинное свидетельство](regional-benchmark-2026-09-30.json) сохраняет final
numbers, лимиты и exact source hashes. Собственные тестовые PG/Redis контейнеры
и credential-файл удалены после общего прогона; чужие сервисы не затронуты.

## Оставшиеся границы

- Месячная политика existing-wins защищает live, но без per-point provenance
  не отличает старый seed от ревизии ЕМИСС. Новый месячный артефакт автоматически
  не исправляет существующие значения; нужен explicit repair/source refresh.
- Отсутствующие annual keys сохраняются, включая ранее ошибочные. Отзыв или
  методологическая замена ряда требуют отдельного решения; отсутствие в файле
  само не является разрешением удалить историю.
- Redis publication bounded 15 секунд, best-effort и ожидается при cooperative
  cancellation. Crash между SQL/Redis, unknown commit outcome, outage/eviction
  и межпроцессный memo до 5 секунд не превращаются в durable guarantee.
- Browser/proxy может использовать уже полученную OG-картинку до max-age 3600;
  static sitemap shards обновляются отдельным job. Локальная generation не
  означает свежую sitemap publication или поисковую переиндексацию.
- Startup читает и сравнивает артефакт каждый раз, использует temporary disk;
  statement timeout сидера 120 секунд применяется к statement, не всему run.
  Ждущий EMISS сохраняет обычный timeout своего соединения и может безопасно
  завершиться ошибкой ожидания. Startup fallback при имеющейся annual истории
  сохраняется. Общая нагрузка ETL/BI/SSR, disk pressure и release пока не приняты.
- Полная восстановимость после live ingestion требует backup БД. Этот пакет
  не выполняет полного upstream numerical audit и не выпускает код на сервер.
