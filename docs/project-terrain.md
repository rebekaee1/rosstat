# Рельеф проекта — автоматически извлечённый срез

> Генерируется `scripts/build-project-terrain.py --refresh` через Graphify. Не править вручную.

[Локальный интерактивный просмотр — после `--render`](project-terrain.html) · [JSON](project-terrain.json) · [Архитектура](architecture.md) · [Контракты](data-contracts.md) · [История решений](architecture-history.md)

Экстрактор: `graphifyy==0.9.69`. Базовый commit: `a33696f734da`; снимок включает рабочие изменения. SHA-256 каждого входного файла записан в JSON. `unstaged_at_capture` и `untracked_at_capture` фиксируют состояние входов; коммит карты сам по себе не коммитит чужие изменения кода. HTML локальный, в Git не хранится; в чистом clone сначала выполнить `--render`.

## Покрытие

| Измерение | Число |
|---|---:|
| Файлы в инвентаризации | 1281 |
| Переданы структурному экстрактору | 1089 |
| Дали узлы графа | 1018 |
| Узлы / связи между символами | 13149 / 41099 |
| Связи между файлами (тип и уверенность сохраняются) | 8554 |

Исходники, шаблоны и стили: **976** файлов; узлы есть у **967**, из них **72** дали только один файловый узел. Смысловые свидетельства с проверенными основаниями относятся к **68** файлам (включая документы), а не ко всем функциям проекта. Успешный прогон тестов не измеряет полноту этого разбора.

Полная инвентаризация относится к Git-дереву. Наличие в списке не означает, что каждый файл прошёл содержательный аудит. `nodes` — экстрактор нашёл структуру; `no_nodes` — файл прочитан экстрактором, но сущностей не получено; `inventory_only` — учтён без разбора структуры. Бинарные материалы, конфиги и данные включены в инвентарь; визуальное содержание скриншотов не анализировалось.

## Общая структура

Просмотрщик начинается с групп исходников и матрицы связей между ними. Группировка детерминированная по путям файлов (`layer_for`); каждый файл входит ровно в одну группу, остаток виден в «Других файлах». Это технические слои, а не автоматически доказанные бизнес-домены. Ячейки матрицы суммируют только извлечённые связи; отсутствие ребра frontend→API не отменяет HTTP-вызов. Сквозные потоки через HTTP, БД, Redis и расписания описаны в архитектуре и контрактах.

| Группа | Файлов | Исходников | С узлами | Файлов со смысловыми свидетельствами |
|---|---:|---:|---:|---:|
| Браузер: страницы и компоненты | 118 | 118 | 115 | 3 |
| Клиент: данные, hooks и состояние | 99 | 95 | 95 | 4 |
| Встраиваемые виджеты | 7 | 7 | 7 | 0 |
| Языки и локализация | 14 | 14 | 14 | 0 |
| HTTP API | 20 | 20 | 20 | 9 |
| Сервисы и расчёты | 202 | 202 | 202 | 16 |
| Планировщик и фоновые задачи | 5 | 5 | 5 | 2 |
| Модели, ядро и запуск backend | 15 | 15 | 15 | 5 |
| Реестры и исходные данные | 61 | 34 | 34 | 4 |
| Миграции БД | 37 | 36 | 35 | 0 |
| Операционные скрипты | 94 | 89 | 90 | 3 |
| Инфраструктура и конфигурация | 39 | 7 | 8 | 1 |
| Тесты и fixtures | 356 | 328 | 328 | 0 |
| Документация и правила | 60 | 0 | 48 | 21 |
| Исследования и артефакты | 56 | 1 | 1 | 0 |
| Статические ресурсы | 98 | 5 | 1 | 0 |

## Что означает связь

`EXTRACTED` и `INFERRED` — метки Graphify. Даже EXTRACTED означает статическую конструкцию, а не выполненный вызов. JSON сохраняет направление, тип, количество и примеры исходных строк. Внутрифайловые отношения остаются в полном Graphify-графе; внешние/неразрешённые endpoints не превращаются в выдуманные файлы. Отсутствие входящих связей не доказывает мёртвый код. Динамические реестры, HTTP, SQL, Redis и scheduler требуют контрактов из отдельных документов.

Метки связей: `{"EXTRACTED": 37809, "INFERRED": 3290}`.
Не включены в проекцию между файлами: `{"external_or_unresolved_file": 2209, "missing_endpoint": 2388, "within_file": 17640}`.

## Слои файлов

| Папка | Файлов | С узлами |
|---|---:|---:|
| `(root)` | 8 | 3 |
| `.cursor` | 11 | 0 |
| `.github` | 3 | 0 |
| `.tours` | 1 | 0 |
| `backend` | 628 | 544 |
| `clickhouse` | 2 | 0 |
| `deploy` | 10 | 3 |
| `docs` | 100 | 45 |
| `frontend` | 433 | 348 |
| `mcp` | 4 | 3 |
| `scripts` | 81 | 72 |

## Документы и правила

Ниже весь реестр текстовой документации и правил, включая старые материалы. Исторический статус и решения — в [индексе истории](architecture-history.md).

| Документ | Строк | Извлечение |
|---|---:|---|
| [.cursor/rules/i18n-parity.mdc](../.cursor/rules/i18n-parity.mdc) | 52 | inventory_only |
| [.cursor/rules/indicator-data-delivery.mdc](../.cursor/rules/indicator-data-delivery.mdc) | 53 | inventory_only |
| [.cursor/rules/methodology-language.mdc](../.cursor/rules/methodology-language.mdc) | 96 | inventory_only |
| [.cursor/rules/no-middle-dot.mdc](../.cursor/rules/no-middle-dot.mdc) | 32 | inventory_only |
| [.cursor/rules/outside-acceptance.mdc](../.cursor/rules/outside-acceptance.mdc) | 31 | inventory_only |
| [.cursor/rules/packet-fixes.mdc](../.cursor/rules/packet-fixes.mdc) | 32 | inventory_only |
| [.cursor/rules/prod-ssh.mdc](../.cursor/rules/prod-ssh.mdc) | 32 | inventory_only |
| [.cursor/rules/project.mdc](../.cursor/rules/project.mdc) | 53 | inventory_only |
| [.cursor/rules/subagents.mdc](../.cursor/rules/subagents.mdc) | 12 | inventory_only |
| [.cursor/rules/working-agreement.mdc](../.cursor/rules/working-agreement.mdc) | 61 | inventory_only |
| [.cursor/rules/world-ui-parity.mdc](../.cursor/rules/world-ui-parity.mdc) | 32 | inventory_only |
| [AGENTS.md](../AGENTS.md) | 425 | nodes |
| [CONTEXT.md](../CONTEXT.md) | 900 | nodes |
| [README.md](../README.md) | 236 | nodes |
| [docs/adr/0001-derived-indicators-engine-shape.md](../docs/adr/0001-derived-indicators-engine-shape.md) | 142 | nodes |
| [docs/adr/0002-derived-always-reflects-source.md](../docs/adr/0002-derived-always-reflects-source.md) | 136 | nodes |
| [docs/adr/0003-seo-single-source-server-rendered.md](../docs/adr/0003-seo-single-source-server-rendered.md) | 210 | nodes |
| [docs/adr/0004-rosstat-russian-canonical-sdds-deprecated.md](../docs/adr/0004-rosstat-russian-canonical-sdds-deprecated.md) | 190 | nodes |
| [docs/adr/0005-official-calendar-source-bound.md](../docs/adr/0005-official-calendar-source-bound.md) | 83 | nodes |
| [docs/adr/0006-indicator-card-unification.md](../docs/adr/0006-indicator-card-unification.md) | 227 | nodes |
| [docs/adr/0007-identity-user-accounts.md](../docs/adr/0007-identity-user-accounts.md) | 237 | nodes |
| [docs/adr/0008-regional-bounded-context.md](../docs/adr/0008-regional-bounded-context.md) | 118 | nodes |
| [docs/adr/0009-behavior-stream-first-party.md](../docs/adr/0009-behavior-stream-first-party.md) | 128 | nodes |
| [docs/adr/0010-analytics-contour-identity-goals-marts-olap.md](../docs/adr/0010-analytics-contour-identity-goals-marts-olap.md) | 185 | nodes |
| [docs/adr/0011-world-eurostat-data-plane.md](../docs/adr/0011-world-eurostat-data-plane.md) | 248 | nodes |
| [docs/adr/0012-world-multi-provider-official-first-forecasts.md](../docs/adr/0012-world-multi-provider-official-first-forecasts.md) | 185 | nodes |
| [docs/adr/0013-country-first-url-architecture.md](../docs/adr/0013-country-first-url-architecture.md) | 309 | nodes |
| [docs/adr/0014-subnational-regions-generic.md](../docs/adr/0014-subnational-regions-generic.md) | 99 | nodes |
| [docs/adr/0015-us-bea-regional-catalog.md](../docs/adr/0015-us-bea-regional-catalog.md) | 67 | nodes |
| [docs/analytics_api_inventory/README.md](../docs/analytics_api_inventory/README.md) | 63 | nodes |
| [docs/analytics_api_inventory/frontend_instrumentation.md](../docs/analytics_api_inventory/frontend_instrumentation.md) | 279 | nodes |
| [docs/analytics_api_inventory/google_search_console.md](../docs/analytics_api_inventory/google_search_console.md) | 148 | nodes |
| [docs/analytics_api_inventory/metrika_logs.md](../docs/analytics_api_inventory/metrika_logs.md) | 51 | nodes |
| [docs/analytics_api_inventory/metrika_management.md](../docs/analytics_api_inventory/metrika_management.md) | 49 | nodes |
| [docs/analytics_api_inventory/metrika_reporting.md](../docs/analytics_api_inventory/metrika_reporting.md) | 47 | nodes |
| [docs/analytics_api_inventory/yandex_webmaster.md](../docs/analytics_api_inventory/yandex_webmaster.md) | 64 | nodes |
| [docs/architecture-history.md](../docs/architecture-history.md) | 40 | nodes |
| [docs/architecture.md](../docs/architecture.md) | 161 | nodes |
| [docs/backlog.md](../docs/backlog.md) | 1667 | nodes |
| [docs/data-contracts.md](../docs/data-contracts.md) | 91 | nodes |
| [docs/data_sources.md](../docs/data_sources.md) | 641 | nodes |
| [docs/dead-code-report.md](../docs/dead-code-report.md) | 82 | nodes |
| [docs/design/README.md](../docs/design/README.md) | 104 | nodes |
| [docs/design/accessibility-review.md](../docs/design/accessibility-review.md) | 58 | nodes |
| [docs/design/art-prompts/forecast-glass-reconstruction.md](../docs/design/art-prompts/forecast-glass-reconstruction.md) | 54 | nodes |
| [docs/design/design-review-gallery.md](../docs/design/design-review-gallery.md) | 78 | nodes |
| [docs/design/local-acceptance/README.md](../docs/design/local-acceptance/README.md) | 31 | nodes |
| [docs/design/requirements-coverage.md](../docs/design/requirements-coverage.md) | 16 | nodes |
| [docs/enterprise_resilience.md](../docs/enterprise_resilience.md) | 100 | nodes |
| [docs/indexnow-sitemap-backfill-plan.md](../docs/indexnow-sitemap-backfill-plan.md) | 204 | nodes |
| [docs/indicator-family-playbook.md](../docs/indicator-family-playbook.md) | 614 | nodes |
| [docs/indicator-index.md](../docs/indicator-index.md) | 1055 | nodes |
| [docs/missed_data_audit.md](../docs/missed_data_audit.md) | 449 | nodes |
| [docs/traffic-platform-2026-09-10.md](../docs/traffic-platform-2026-09-10.md) | 47 | nodes |
| [docs/verification/us-eu-source-audit-2026-09-24.md](../docs/verification/us-eu-source-audit-2026-09-24.md) | 114 | nodes |
| [docs/verification/us-indicators-2026-09-24.md](../docs/verification/us-indicators-2026-09-24.md) | 41 | nodes |
| [docs/verification/world-forecast-v2-2026-09-24.md](../docs/verification/world-forecast-v2-2026-09-24.md) | 64 | nodes |
| [docs/workflow.md](../docs/workflow.md) | 201 | nodes |
| [scripts/audit-world-truthfulness-report.md](../scripts/audit-world-truthfulness-report.md) | 145 | nodes |

## Обновление и проверка

```bash
# В окружении с graphifyy==0.9.69; не импортирует backend и не обращается к БД
python scripts/build-project-terrain.py --refresh
# Проверка drift, Graphify не требуется
python3 scripts/build-project-terrain.py --check
# Пересоздать HTML из закоммиченного JSON, без Graphify
python3 scripts/build-project-terrain.py --render
```

Полные `extraction.json`, `graph.json` и диагностика сохраняются в `.artifacts/project-terrain/` (локальные, не Git). `graphify explain <symbol> --graph .artifacts/project-terrain/graph.json` даёт точечную навигацию. Для просмотра HTML достаточно открыть файл; сеть и CDN не нужны. Проверка `--check` отдельная: не включена в обязательные gates `check-all`/CI, поскольку этот датированный срез включает рабочие изменения параллельных задач. Команды требуют Git checkout; Python-зависимости для `--check`/`--render` не нужны.

Смысловой граф исследовательских агентов — отдельное датированное свидетельство в `docs/architecture-knowledge.json`; он не смешивается со статическим графом и не обновляется автоматически при изменении кода. Проверяйте его ссылки и дату аудита.
