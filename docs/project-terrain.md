# Рельеф проекта — автоматически извлечённый срез

> Генерируется `scripts/build-project-terrain.py --refresh` через Graphify. Не править вручную.

[Локальный интерактивный просмотр — после `--render`](project-terrain.html) · [JSON](project-terrain.json) · [Архитектура](architecture.md) · [Контракты](data-contracts.md) · [История решений](architecture-history.md)

[Независимый backend-инвентарь](mechanism-inventory.md) · [Клиент/anonymous callbacks/MCP](client-mechanism-inventory.md) · [Приёмка и границы](project-knowledge-acceptance.md) · [Неизвестное](knowledge-unknowns.md)

Экстрактор: `graphifyy==0.9.69`. Базовый commit: `83c455556998`; снимок включает рабочие изменения. SHA-256 каждого входного файла записан в JSON. `unstaged_at_capture` и `untracked_at_capture` фиксируют состояние входов; коммит карты сам по себе не коммитит чужие изменения кода. HTML локальный, в Git не хранится; в чистом clone сначала выполнить `--render`.

Input scope: `tracked`. Для публикуемой main-карты используются Git tracked/index пути; новые файлы задачи сначала добавляются в index. Чужие untracked материалы остаются вне main-снимка и сохраняются на диске.

## Покрытие

| Измерение | Число |
|---|---:|
| Файлы в инвентаризации | 1325 |
| Переданы структурному экстрактору | 1133 |
| Дали узлы графа | 1059 |
| Узлы / связи между символами | 14126 / 43923 |
| Связи между файлами (тип и уверенность сохраняются) | 8917 |

Исходники, шаблоны и стили: **1009** файлов; узлы есть у **1000**, из них **72** дали только один файловый узел. Исторический смысловой граф содержит основания для **68** файлов. Это прежний выборочный срез; его изменившиеся основания показаны в HTML отдельно. Текущий содержательный разбор каждого файла и именованного определения находится в [реестре рецензий](code-review.md), с отдельным guard по SHA и аннотациям. Успешный прогон тестов не измеряет полноту этого разбора.

Полная инвентаризация относится к Git-дереву. Наличие в списке не означает, что каждый файл прошёл содержательный аудит. `nodes` — экстрактор нашёл структуру; `no_nodes` — файл прочитан экстрактором, но сущностей не получено; `inventory_only` — учтён без разбора структуры. Бинарные материалы, конфиги и данные включены в инвентарь. Содержательное чтение XLSX/PDF, просмотр исторических изображений и классификация внешних материалов фиксируются отдельно в [реестре](code-review/materials-current.json) и приёмке; сам экстрактор не устанавливает визуальное содержание.

## Общая структура

Просмотрщик начинается с групп исходников и матрицы связей между ними. Группировка детерминированная по путям файлов (`layer_for`); каждый файл входит ровно в одну группу, остаток виден в «Других файлах». Это технические слои, а не автоматически доказанные бизнес-домены. Ячейки матрицы суммируют только извлечённые связи; отсутствие ребра frontend→API не отменяет HTTP-вызов. Сквозные потоки через HTTP, БД, Redis и расписания описаны в архитектуре и контрактах.

| Группа | Файлов | Исходников | С узлами | Оснований в историческом смысловом графе |
|---|---:|---:|---:|---:|
| Браузер: страницы и компоненты | 118 | 118 | 115 | 3 |
| Клиент: данные, hooks и состояние | 99 | 95 | 95 | 4 |
| Встраиваемые виджеты | 7 | 7 | 7 | 0 |
| Языки и локализация | 14 | 14 | 14 | 0 |
| HTTP API | 20 | 20 | 20 | 9 |
| Сервисы и расчёты | 204 | 204 | 204 | 16 |
| Планировщик и фоновые задачи | 5 | 5 | 5 | 2 |
| Модели, ядро и запуск backend | 15 | 15 | 15 | 5 |
| Реестры и исходные данные | 61 | 34 | 34 | 4 |
| Миграции БД | 37 | 36 | 35 | 0 |
| Операционные скрипты | 106 | 101 | 102 | 3 |
| Инфраструктура и конфигурация | 39 | 7 | 8 | 1 |
| Тесты и fixtures | 375 | 347 | 347 | 0 |
| Документация и правила | 68 | 0 | 56 | 21 |
| Исследования и артефакты | 59 | 1 | 1 | 0 |
| Статические ресурсы | 98 | 5 | 1 | 0 |

## Что означает связь

`EXTRACTED` и `INFERRED` — метки Graphify. Даже EXTRACTED означает статическую конструкцию, а не выполненный вызов. JSON сохраняет направление, тип, количество и примеры исходных строк. Внутрифайловые отношения остаются в полном Graphify-графе; внешние/неразрешённые endpoints не превращаются в выдуманные файлы. Отсутствие входящих связей не доказывает мёртвый код. Динамические реестры, HTTP, SQL, Redis и scheduler требуют контрактов из отдельных документов.

Метки связей: `{"EXTRACTED": 40244, "INFERRED": 3679}`.
Не включены в проекцию между файлами: `{"external_or_unresolved_file": 2276, "missing_endpoint": 2694, "within_file": 19196}`.

## Слои файлов

| Папка | Файлов | С узлами |
|---|---:|---:|
| `(root)` | 8 | 3 |
| `.cursor` | 11 | 0 |
| `.github` | 3 | 0 |
| `.tours` | 1 | 0 |
| `backend` | 646 | 562 |
| `clickhouse` | 2 | 0 |
| `deploy` | 10 | 3 |
| `docs` | 111 | 53 |
| `frontend` | 436 | 351 |
| `mcp` | 4 | 3 |
| `scripts` | 93 | 84 |

## Документы и правила

Ниже весь реестр текстовой документации и правил, включая старые материалы. Исторический статус и решения — в [индексе истории](architecture-history.md).

| Документ | Строк | Извлечение |
|---|---:|---|
| [.cursor/rules/i18n-parity.mdc](../.cursor/rules/i18n-parity.mdc) | 52 | inventory_only |
| [.cursor/rules/indicator-data-delivery.mdc](../.cursor/rules/indicator-data-delivery.mdc) | 58 | inventory_only |
| [.cursor/rules/methodology-language.mdc](../.cursor/rules/methodology-language.mdc) | 96 | inventory_only |
| [.cursor/rules/no-middle-dot.mdc](../.cursor/rules/no-middle-dot.mdc) | 32 | inventory_only |
| [.cursor/rules/outside-acceptance.mdc](../.cursor/rules/outside-acceptance.mdc) | 31 | inventory_only |
| [.cursor/rules/packet-fixes.mdc](../.cursor/rules/packet-fixes.mdc) | 32 | inventory_only |
| [.cursor/rules/prod-ssh.mdc](../.cursor/rules/prod-ssh.mdc) | 32 | inventory_only |
| [.cursor/rules/project.mdc](../.cursor/rules/project.mdc) | 55 | inventory_only |
| [.cursor/rules/subagents.mdc](../.cursor/rules/subagents.mdc) | 12 | inventory_only |
| [.cursor/rules/working-agreement.mdc](../.cursor/rules/working-agreement.mdc) | 63 | inventory_only |
| [.cursor/rules/world-ui-parity.mdc](../.cursor/rules/world-ui-parity.mdc) | 32 | inventory_only |
| [AGENTS.md](../AGENTS.md) | 85 | nodes |
| [CONTEXT.md](../CONTEXT.md) | 1109 | nodes |
| [README.md](../README.md) | 261 | nodes |
| [docs/adr/0001-derived-indicators-engine-shape.md](../docs/adr/0001-derived-indicators-engine-shape.md) | 158 | nodes |
| [docs/adr/0002-derived-always-reflects-source.md](../docs/adr/0002-derived-always-reflects-source.md) | 136 | nodes |
| [docs/adr/0003-seo-single-source-server-rendered.md](../docs/adr/0003-seo-single-source-server-rendered.md) | 210 | nodes |
| [docs/adr/0004-rosstat-russian-canonical-sdds-deprecated.md](../docs/adr/0004-rosstat-russian-canonical-sdds-deprecated.md) | 190 | nodes |
| [docs/adr/0005-official-calendar-source-bound.md](../docs/adr/0005-official-calendar-source-bound.md) | 83 | nodes |
| [docs/adr/0006-indicator-card-unification.md](../docs/adr/0006-indicator-card-unification.md) | 227 | nodes |
| [docs/adr/0007-identity-user-accounts.md](../docs/adr/0007-identity-user-accounts.md) | 237 | nodes |
| [docs/adr/0008-regional-bounded-context.md](../docs/adr/0008-regional-bounded-context.md) | 181 | nodes |
| [docs/adr/0009-behavior-stream-first-party.md](../docs/adr/0009-behavior-stream-first-party.md) | 128 | nodes |
| [docs/adr/0010-analytics-contour-identity-goals-marts-olap.md](../docs/adr/0010-analytics-contour-identity-goals-marts-olap.md) | 240 | nodes |
| [docs/adr/0011-world-eurostat-data-plane.md](../docs/adr/0011-world-eurostat-data-plane.md) | 286 | nodes |
| [docs/adr/0012-world-multi-provider-official-first-forecasts.md](../docs/adr/0012-world-multi-provider-official-first-forecasts.md) | 202 | nodes |
| [docs/adr/0013-country-first-url-architecture.md](../docs/adr/0013-country-first-url-architecture.md) | 309 | nodes |
| [docs/adr/0014-subnational-regions-generic.md](../docs/adr/0014-subnational-regions-generic.md) | 99 | nodes |
| [docs/adr/0015-us-bea-regional-catalog.md](../docs/adr/0015-us-bea-regional-catalog.md) | 67 | nodes |
| [docs/agent-recipes.md](../docs/agent-recipes.md) | 220 | nodes |
| [docs/analytics_api_inventory/README.md](../docs/analytics_api_inventory/README.md) | 76 | nodes |
| [docs/analytics_api_inventory/frontend_instrumentation.md](../docs/analytics_api_inventory/frontend_instrumentation.md) | 279 | nodes |
| [docs/analytics_api_inventory/google_search_console.md](../docs/analytics_api_inventory/google_search_console.md) | 148 | nodes |
| [docs/analytics_api_inventory/metrika_logs.md](../docs/analytics_api_inventory/metrika_logs.md) | 57 | nodes |
| [docs/analytics_api_inventory/metrika_management.md](../docs/analytics_api_inventory/metrika_management.md) | 49 | nodes |
| [docs/analytics_api_inventory/metrika_reporting.md](../docs/analytics_api_inventory/metrika_reporting.md) | 47 | nodes |
| [docs/analytics_api_inventory/yandex_webmaster.md](../docs/analytics_api_inventory/yandex_webmaster.md) | 64 | nodes |
| [docs/architecture-history.md](../docs/architecture-history.md) | 138 | nodes |
| [docs/architecture.md](../docs/architecture.md) | 344 | nodes |
| [docs/backlog.md](../docs/backlog.md) | 1791 | nodes |
| [docs/client-mechanism-inventory.md](../docs/client-mechanism-inventory.md) | 107 | nodes |
| [docs/code-review-findings.md](../docs/code-review-findings.md) | 161 | nodes |
| [docs/data-contracts.md](../docs/data-contracts.md) | 340 | nodes |
| [docs/data_sources.md](../docs/data_sources.md) | 642 | nodes |
| [docs/dead-code-report.md](../docs/dead-code-report.md) | 82 | nodes |
| [docs/design/README.md](../docs/design/README.md) | 104 | nodes |
| [docs/design/accessibility-review.md](../docs/design/accessibility-review.md) | 58 | nodes |
| [docs/design/art-prompts/forecast-glass-reconstruction.md](../docs/design/art-prompts/forecast-glass-reconstruction.md) | 54 | nodes |
| [docs/design/design-review-gallery.md](../docs/design/design-review-gallery.md) | 78 | nodes |
| [docs/design/local-acceptance/README.md](../docs/design/local-acceptance/README.md) | 31 | nodes |
| [docs/design/requirements-coverage.md](../docs/design/requirements-coverage.md) | 16 | nodes |
| [docs/enterprise_resilience.md](../docs/enterprise_resilience.md) | 115 | nodes |
| [docs/indexnow-sitemap-backfill-plan.md](../docs/indexnow-sitemap-backfill-plan.md) | 204 | nodes |
| [docs/indicator-family-playbook.md](../docs/indicator-family-playbook.md) | 614 | nodes |
| [docs/indicator-index.md](../docs/indicator-index.md) | 1058 | nodes |
| [docs/knowledge-unknowns.md](../docs/knowledge-unknowns.md) | 83 | nodes |
| [docs/knowledge-workflow.md](../docs/knowledge-workflow.md) | 107 | nodes |
| [docs/mechanism-inventory.md](../docs/mechanism-inventory.md) | 2404 | nodes |
| [docs/missed_data_audit.md](../docs/missed_data_audit.md) | 449 | nodes |
| [docs/pravki-21-reanalysis.md](../docs/pravki-21-reanalysis.md) | 52 | nodes |
| [docs/project-knowledge-acceptance.md](../docs/project-knowledge-acceptance.md) | 84 | nodes |
| [docs/traffic-platform-2026-09-10.md](../docs/traffic-platform-2026-09-10.md) | 47 | nodes |
| [docs/verification/us-eu-source-audit-2026-09-24.md](../docs/verification/us-eu-source-audit-2026-09-24.md) | 114 | nodes |
| [docs/verification/us-indicators-2026-09-24.md](../docs/verification/us-indicators-2026-09-24.md) | 41 | nodes |
| [docs/verification/world-forecast-v2-2026-09-24.md](../docs/verification/world-forecast-v2-2026-09-24.md) | 64 | nodes |
| [docs/workflow.md](../docs/workflow.md) | 385 | nodes |
| [scripts/audit-world-truthfulness-report.md](../scripts/audit-world-truthfulness-report.md) | 145 | nodes |

## Обновление и проверка

```bash
# В окружении с graphifyy==0.9.69; не импортирует backend и не обращается к БД
python scripts/build-project-terrain.py --refresh --tracked-only
# Проверка drift, Graphify не требуется
python3 scripts/build-project-terrain.py --check
# Пересоздать HTML из закоммиченного JSON, без Graphify
python3 scripts/build-project-terrain.py --render
```

Полные `extraction.json`, `graph.json` и диагностика сохраняются в `.artifacts/project-terrain/` (локальные, не Git). `graphify explain <symbol> --graph .artifacts/project-terrain/graph.json` даёт точечную навигацию. Для просмотра HTML достаточно открыть файл; сеть и CDN не нужны. Проверка `--check --tracked-only` включена в `check-project-knowledge.sh`, `check-all.sh` и CI knowledge job. Она читает сохранённый срез без перезаписи и требует актуальной main-карты. Команды требуют Git checkout; Python-зависимости для `--check`/`--render` не нужны.

Смысловой граф исследовательских агентов — отдельное датированное свидетельство в `docs/architecture-knowledge.json`; он не смешивается со статическим графом и не обновляется автоматически при изменении кода. Проверяйте его ссылки и дату аудита.
