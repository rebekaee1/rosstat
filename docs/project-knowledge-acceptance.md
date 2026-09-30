# Приёмка досье Forecast Economy — 30 сентября 2026

## Результат и границы

Сбор устройства доступной текущей реализации завершён для локальной `main`:
исходники, декларации, вложенные функции, конфигурация, связи, старые основания и
датированное исполнение связаны в досье. Критерии — [K01–K12](code-review/readiness-criteria.md).
Это основание для выбора улучшений. Оно не подтверждает все возможные исполнения,
правильность каждой экономической точки или отсутствие дефектов.

Основа продолжения — `05302ff1c4dbe104850116e6206d168ec4fa91d3` и проверенный
собственный diff. Итоговый commit получается после пересборки; точные source SHA
и Git baseline находятся в [рельефе](project-terrain.json) и [рецензиях](code-review/reviews.jsonl).
Production наблюдался отдельно: checkout `367ff336a307ad57d528b26078ca35883ec3de68`.
Исходники 402 backend payload-файлов обоих работающих образов побайтово сопоставлены
с серверным checkout; frontend dist, loaded Caddy config и writable layers проверены.
Изменения документов в локальной main этим наблюдением не объявляются выпущенными.

**Общие ограничения:** [реестр неизвестного и известных проблем](knowledge-unknowns.md).
Недоступная запись, provider cabinet, полный failover и измеренная смешанная capacity
сохраняют ограничения соответствующих критериев. Без этих оснований нельзя обещать
универсальные «100% понимания», безопасный новый масштаб или готовую новую архитектуру.

## Как читать полную картину

1. [Архитектура](architecture.md) → [контракты](data-contracts.md) → [история](architecture-history.md).
2. [Backend inventory](mechanism-inventory.md): HTTP, ORM/поля/relationships, DTO,
   Settings/readers, jobs, middleware, lifecycle, migrations, registries, SQL и эффекты.
3. [Client inventory](client-mechanism-inventory.md): routes, imports, все функции
   включая anonymous callbacks, hooks, HTTP, storage, события, JSX handlers и MCP.
4. [HTML-рельеф](project-terrain.html): файл → ручное объяснение → все независимые
   элементы с owner/строками → соседние файлы/слои. Списки элементов не обрезаются.
5. [Разработка и выпуск](workflow.md), [ресурсы и восстановление](enterprise_resilience.md),
   [сопровождение при обычном промпте](knowledge-workflow.md).

## Приёмка по критериям

| Критерий | Что установлено | Основание и предел |
|---|---|---|
| K01 — версия | main/index, source SHA, исторические версии, серверный checkout, image IDs и наблюдения различаются | Source ledger + terrain; [ops](code-review/ops-mechanism-acceptance-2026-09-30.md). SHA файлов образа не аттестует загруженный Python state. |
| K02 — состав | Независимые AST/Babel списки сопоставлены с рецензиями; все 144 HTTP routes, 57 ORM tables, 626 columns, 34 relationships, 39 jobs, 160 Settings, 27 DTO и 7 MCP tools имеют адреса | [Backend crosscheck](code-review/backend-mechanism-crosscheck-2026-09-30.json), [client crosscheck](code-review/client-inventory-reconciliation-2026-09-30.json). Генератор сохраняет синтаксис, не исполняет регистрацию. |
| K03 — элементы | Полное прежнее чтение сохранено для совпавших SHA; изменённые тела/дельты перечитаны. Клиентский список адресует 5376 функций, включая 3905 anonymous, 1339 hooks, 555 handlers | [Реестр](code-review.md), [клиент](code-review/client-mechanism-acceptance-2026-09-30.md). Вложенный callback описан в контексте рецензии тела; отдельный AST адрес не является отдельным доказательством исполнения. Числа включают тесты. |
| K04 — связи | Import/call/HTTP/storage/cache/event/generated связи дополнены сценариями; каждому исключённому raw Graphify ребру присвоены категория и source anchor | [Классификация](code-review/graph-omission-classification-2026-09-30.json). External types/packages, ambiguous paths и dynamic dispatch не превращены в придуманные runtime edges. |
| K05 — данные | Факт, derived, forecast, analytics, identity, regional/subnational и catalog имеют отдельные жизненные циклы; поля/типы/defaults и effects перечислены; restore schema сопоставлена с миграциями | [Contracts](data-contracts.md), [backend probes](code-review/backend-mechanism-probes-2026-09-30.json), [restore](code-review/ops-mechanism-acceptance-2026-09-30.md). Не выполнена перепроверка всех значений относительно каждого upstream источника. |
| K06 — сценарии | UI/API/job/CLI/MCP отнесены к семействам; empty/error/auth/retry/cancel/commit/cache/lock/queue описаны. Семь рискованных механизмов и inventory fixture проверены actual-body probes | [Backend acceptance](code-review/backend-mechanism-acceptance-2026-09-30.md), [client acceptance](code-review/client-mechanism-acceptance-2026-09-30.md). Детерминированные doubles/модели не являются реальной конкуренцией PostgreSQL/Redis. |
| K07 — настройки | Все Settings/defaults/readers, Compose mappings/precedence, Vite modes/build, host settings и effective отличия связаны | [Ops](code-review/ops-mechanism-acceptance-2026-09-30.md). Root .env не передаёт всё в контейнер; 9 имён шаблона вне Compose interpolation отмечены. Секретные значения не опубликованы. |
| K08 — исполнение | 4 vCPU, RAM/swap/disk, 7 services, workers/quotas/pools, mounts/ports, Caddy/nginx/Tor bridge/cron/logrotate, backup и startup раскрыты | [Ops](code-review/ops-mechanism-acceptance-2026-09-30.json). CPU quotas суммарно 5 на 4 vCPU, hard RAM limits оставляют около 325 MiB сверх суммы; это не фактическая reservation/capacity. |
| K09 — внешние границы | Provider adapters/официальные источники, OAuth, Telegram, analytics, LLM/MCP, lockfiles, timeout/retry/fallback и данные наружу прослежены | [Sources](data_sources.md), [analytics inventory](analytics_api_inventory/README.md), contracts/ops. Оплаченные вызовы, внешние OAuth и каждый upstream endpoint повторно не исполнялись. |
| K10 — история | ADR/старый AGENTS/Opus/owner text сохранены; внешние копии/дельты, пять полностью прочитанных старых планов, XLSX, Cursor owner records, изображения, FE approval PDFs и notebooks связаны с текущими механизмами | [Материалы](code-review/material-content-acceptance-2026-09-30.md), [три старых плана](code-review/historical-plan-supplement-2026-09-30.md), [BI-план](code-review/historical-bi-plan-supplement-2026-09-30.md), [PDF](code-review/pdf-material-acceptance-2026-09-30.md). Subagent coordination не становится решением владельца; неподтверждённые visual prototypes не становятся утверждённым дизайном. |
| K11 — основания | Code/doc/runtime расхождения разрешены по версии или зарегистрированы; история не переписана. Исходные факты и новые probes/restore имеют явные пределы | [Предыдущий этап](code-review/knowledge-acceptance-2026-09-30.md), новые протоколы и [unknowns](knowledge-unknowns.md). Test count и healthy не подменяют semantics/completeness. |
| K12 — использование | Новый агент без истории чата нашёл сценарии/версии/границы, выбрал Calendar и Embed самостоятельно; 3 реальные doc gaps исправлены. Карта показывает каждый элемент на desktop/mobile | [Cold start](code-review/cold-start-acceptance-2026-09-30.md), [viewer acceptance](code-review/terrain-viewer-acceptance-2026-09-30.json), guards/CI. Три сценария подтверждают полезность навигации, не понимание всех будущих задач любым агентом. |

## Проверенное исполнение

- Свежий backup доставлен на Mac с совпавшим SHA. Первый restore с `--no-owner`
  сохранён отдельно; повторный restore с owners/ACL выполнен exit0 за 182,967 с
  в собственной изолированной инфраструктуре. Исходный dump PostgreSQL 16.14,
  восстановление 16.11; исходные secrets/globals/AOF не восстанавливались.
- Настоящий Uvicorn с восстановленной БД и двумя своими Redis: readiness, российские
  данные, валюты и world catalog; synthetic register/login/me/logout/CSRF; cache
  FLUSHDB не уничтожил сессию. Это не live-user/внешний OAuth acceptance.
- Чистый web entrypoint на пустой БД: 34 migrations, seed и readiness. Jobs выключены,
  внешняя сеть отключена; nginx SSR использовал явно датированный существующий bundle.
- Offline HTML проверен на 1440 и 390 px: полный список элементов, без overflow,
  JS errors и внешних запросов. Это приёмка инструмента документации.
- Общие source/material/terrain/inventory gates и существующие app тесты проверяются
  после пересборки; точный результат и границы — в [протоколе завершения](code-review/collection-final-validation-2026-09-30.md).

## Что следует из результата

Сначала выбирать подтверждённый риск и критерий исправления, затем менять механизм
с его consumers и обновлять досье в той же задаче. Валютная нормализация уже имеет
исторический план R-3; новости/форум требуют собственных сущностей, прав, moderation,
retention и ресурсного бюджета. Универсальная фабрика стран и новая архитектура
не считаются принятыми только потому, что исходники собраны.

Предложенные ранее runtime-исправления и архитектурный пилот остаются отдельной
работой. Три ошибки нового инструмента найдены независимой проверкой и исправлены:
проверка устаревшего существующего HTML, сохранение всех 7 fallback MCP tools
и привязка omission report к SHA текущего portable terrain. Изолированные регрессии проверяют все три случая; отсутствие ignored HTML в чистом
checkout допускается явно.

В этом проходе завершены сбор, актуализация, проверка навигации и сохранность
текущего backup; обнаруженные дефекты не скрыты и не объявлены исправленными.
