# Рельеф проекта — автоматически извлечённый срез

> Генерируется `scripts/build-project-terrain.py --refresh` через Graphify. Не править вручную.

[Локальный интерактивный просмотр — после `--render`](project-terrain.html) · [JSON](project-terrain.json) · [Архитектура](architecture.md) · [Контракты](data-contracts.md) · [История решений](architecture-history.md)

[Независимый backend-инвентарь](mechanism-inventory.md) · [Клиент/anonymous callbacks/MCP](client-mechanism-inventory.md) · [Приёмка и границы](project-knowledge-acceptance.md) · [Неизвестное](knowledge-unknowns.md)

Экстрактор: `graphifyy==0.9.69`. Базовый commit: `d383285df0d4`; снимок включает рабочие изменения. SHA-256 каждого входного файла записан в JSON. `unstaged_at_capture` и `untracked_at_capture` фиксируют состояние входов; коммит карты сам по себе не коммитит чужие изменения кода. HTML локальный, в Git не хранится; в чистом clone сначала выполнить `--render`.

Input scope: `tracked`. Для публикуемой main-карты используются Git tracked/index пути; новые файлы задачи сначала добавляются в index. Чужие untracked материалы остаются вне main-снимка и сохраняются на диске.

## Покрытие

| Измерение | Число |
|---|---:|
| Файлы в инвентаризации | 1869 |
| Переданы структурному экстрактору | 1604 |
| Дали узлы графа | 1524 |
| Узлы / связи между символами | 18609 / 58700 |
| Связи между файлами (тип и уверенность сохраняются) | 13510 |

Исходники, шаблоны и стили: **1485** файлов; узлы есть у **1436**, из них **109** дали только один файловый узел. Исторический смысловой граф содержит основания для **68** файлов. Это прежний выборочный срез; его изменившиеся основания показаны в HTML отдельно. Текущий содержательный разбор каждого файла и именованного определения находится в [реестре рецензий](code-review.md), с отдельным guard по SHA и аннотациям. Успешный прогон тестов не измеряет полноту этого разбора.

Полная инвентаризация относится к Git-дереву. Наличие в списке не означает, что каждый файл прошёл содержательный аудит. `nodes` — экстрактор нашёл структуру; `no_nodes` — файл прочитан экстрактором, но сущностей не получено; `inventory_only` — учтён без разбора структуры. Бинарные материалы, конфиги и данные включены в инвентарь. Содержательное чтение XLSX/PDF, просмотр исторических изображений и классификация внешних материалов фиксируются отдельно в [реестре](code-review/materials-current.json) и приёмке; сам экстрактор не устанавливает визуальное содержание.

## Общая структура

Просмотрщик начинается с групп исходников и матрицы связей между ними. Группировка детерминированная по путям файлов (`layer_for`); каждый файл входит ровно в одну группу, остаток виден в «Других файлах». Это технические слои, а не автоматически доказанные бизнес-домены. Ячейки матрицы суммируют только извлечённые связи; отсутствие ребра frontend→API не отменяет HTTP-вызов. Сквозные потоки через HTTP, БД, Redis и расписания описаны в архитектуре и контрактах.

| Группа | Файлов | Исходников | С узлами | Оснований в историческом смысловом графе |
|---|---:|---:|---:|---:|
| Браузер: страницы и компоненты | 243 | 243 | 203 | 3 |
| Клиент: данные, hooks и состояние | 181 | 177 | 177 | 4 |
| Встраиваемые виджеты | 8 | 8 | 8 | 0 |
| Языки и локализация | 15 | 15 | 15 | 0 |
| HTTP API | 27 | 27 | 27 | 9 |
| Сервисы и расчёты | 226 | 226 | 226 | 16 |
| Планировщик и фоновые задачи | 6 | 6 | 6 | 2 |
| Модели, ядро и запуск backend | 16 | 16 | 16 | 5 |
| Реестры и исходные данные | 62 | 35 | 35 | 4 |
| Миграции БД | 40 | 39 | 38 | 0 |
| Операционные скрипты | 121 | 114 | 114 | 3 |
| Инфраструктура и конфигурация | 42 | 8 | 9 | 1 |
| Тесты и fixtures | 590 | 561 | 561 | 0 |
| Документация и правила | 96 | 0 | 84 | 21 |
| Исследования и артефакты | 60 | 1 | 1 | 0 |
| Статические ресурсы | 136 | 9 | 4 | 0 |

## Что означает связь

`EXTRACTED` и `INFERRED` — метки Graphify. Даже EXTRACTED означает статическую конструкцию, а не выполненный вызов. JSON сохраняет направление, тип, количество и примеры исходных строк. Внутрифайловые отношения остаются в полном Graphify-графе; внешние/неразрешённые endpoints не превращаются в выдуманные файлы. Отсутствие входящих связей не доказывает мёртвый код. Динамические реестры, HTTP, SQL, Redis и scheduler требуют контрактов из отдельных документов.

Метки связей: `{"EXTRACTED": 53696, "INFERRED": 5004}`.
Не включены в проекцию между файлами: `{"external_or_unresolved_file": 2534, "missing_endpoint": 3424, "within_file": 25069}`.

## Слои файлов

| Папка | Файлов | С узлами |
|---|---:|---:|
| `(root)` | 8 | 3 |
| `.cursor` | 11 | 0 |
| `.github` | 3 | 0 |
| `.tours` | 1 | 0 |
| `backend` | 736 | 651 |
| `clickhouse` | 2 | 0 |
| `deploy` | 13 | 5 |
| `docs` | 137 | 78 |
| `frontend` | 846 | 688 |
| `mcp` | 4 | 3 |
| `scripts` | 108 | 96 |

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
| [AGENTS.md](../AGENTS.md) | 87 | nodes |
| [CONTEXT.md](../CONTEXT.md) | 1258 | nodes |
| [README.md](../README.md) | 273 | nodes |
| [deploy/tor-http-bridge/README.md](../deploy/tor-http-bridge/README.md) | 37 | nodes |
| [docs/adr/0001-derived-indicators-engine-shape.md](../docs/adr/0001-derived-indicators-engine-shape.md) | 158 | nodes |
| [docs/adr/0002-derived-always-reflects-source.md](../docs/adr/0002-derived-always-reflects-source.md) | 136 | nodes |
| [docs/adr/0003-seo-single-source-server-rendered.md](../docs/adr/0003-seo-single-source-server-rendered.md) | 247 | nodes |
| [docs/adr/0004-rosstat-russian-canonical-sdds-deprecated.md](../docs/adr/0004-rosstat-russian-canonical-sdds-deprecated.md) | 190 | nodes |
| [docs/adr/0005-official-calendar-source-bound.md](../docs/adr/0005-official-calendar-source-bound.md) | 83 | nodes |
| [docs/adr/0006-indicator-card-unification.md](../docs/adr/0006-indicator-card-unification.md) | 227 | nodes |
| [docs/adr/0007-identity-user-accounts.md](../docs/adr/0007-identity-user-accounts.md) | 252 | nodes |
| [docs/adr/0008-regional-bounded-context.md](../docs/adr/0008-regional-bounded-context.md) | 199 | nodes |
| [docs/adr/0009-behavior-stream-first-party.md](../docs/adr/0009-behavior-stream-first-party.md) | 128 | nodes |
| [docs/adr/0010-analytics-contour-identity-goals-marts-olap.md](../docs/adr/0010-analytics-contour-identity-goals-marts-olap.md) | 252 | nodes |
| [docs/adr/0011-world-eurostat-data-plane.md](../docs/adr/0011-world-eurostat-data-plane.md) | 286 | nodes |
| [docs/adr/0012-world-multi-provider-official-first-forecasts.md](../docs/adr/0012-world-multi-provider-official-first-forecasts.md) | 202 | nodes |
| [docs/adr/0013-country-first-url-architecture.md](../docs/adr/0013-country-first-url-architecture.md) | 309 | nodes |
| [docs/adr/0014-subnational-regions-generic.md](../docs/adr/0014-subnational-regions-generic.md) | 127 | nodes |
| [docs/adr/0015-us-bea-regional-catalog.md](../docs/adr/0015-us-bea-regional-catalog.md) | 67 | nodes |
| [docs/adr/0016-federated-public-search.md](../docs/adr/0016-federated-public-search.md) | 169 | nodes |
| [docs/adr/0017-platform-growth-boundaries.md](../docs/adr/0017-platform-growth-boundaries.md) | 68 | nodes |
| [docs/adr/0018-crystal-without-borders-design-system.md](../docs/adr/0018-crystal-without-borders-design-system.md) | 62 | nodes |
| [docs/agent-briefs/selector-brief.md](../docs/agent-briefs/selector-brief.md) | 18 | nodes |
| [docs/agent-briefs/visitor-brief.md](../docs/agent-briefs/visitor-brief.md) | 35 | nodes |
| [docs/agent-briefs/zone-brief.md](../docs/agent-briefs/zone-brief.md) | 39 | nodes |
| [docs/agent-orchestration.md](../docs/agent-orchestration.md) | 160 | nodes |
| [docs/agent-recipes.md](../docs/agent-recipes.md) | 220 | nodes |
| [docs/analytics_api_inventory/README.md](../docs/analytics_api_inventory/README.md) | 79 | nodes |
| [docs/analytics_api_inventory/frontend_instrumentation.md](../docs/analytics_api_inventory/frontend_instrumentation.md) | 330 | nodes |
| [docs/analytics_api_inventory/google_search_console.md](../docs/analytics_api_inventory/google_search_console.md) | 148 | nodes |
| [docs/analytics_api_inventory/metrika_logs.md](../docs/analytics_api_inventory/metrika_logs.md) | 57 | nodes |
| [docs/analytics_api_inventory/metrika_management.md](../docs/analytics_api_inventory/metrika_management.md) | 49 | nodes |
| [docs/analytics_api_inventory/metrika_reporting.md](../docs/analytics_api_inventory/metrika_reporting.md) | 47 | nodes |
| [docs/analytics_api_inventory/yandex_webmaster.md](../docs/analytics_api_inventory/yandex_webmaster.md) | 64 | nodes |
| [docs/architecture-history.md](../docs/architecture-history.md) | 226 | nodes |
| [docs/architecture.md](../docs/architecture.md) | 446 | nodes |
| [docs/backlog.md](../docs/backlog.md) | 2575 | nodes |
| [docs/client-mechanism-inventory.md](../docs/client-mechanism-inventory.md) | 131 | nodes |
| [docs/code-review-findings.md](../docs/code-review-findings.md) | 161 | nodes |
| [docs/data-contracts.md](../docs/data-contracts.md) | 571 | nodes |
| [docs/data_sources.md](../docs/data_sources.md) | 644 | nodes |
| [docs/dead-code-report.md](../docs/dead-code-report.md) | 82 | nodes |
| [docs/design-system.md](../docs/design-system.md) | 311 | nodes |
| [docs/design/README.md](../docs/design/README.md) | 109 | nodes |
| [docs/design/accessibility-review.md](../docs/design/accessibility-review.md) | 58 | nodes |
| [docs/design/art-prompts/forecast-glass-reconstruction.md](../docs/design/art-prompts/forecast-glass-reconstruction.md) | 54 | nodes |
| [docs/design/design-review-gallery.md](../docs/design/design-review-gallery.md) | 78 | nodes |
| [docs/design/local-acceptance/README.md](../docs/design/local-acceptance/README.md) | 31 | nodes |
| [docs/design/requirements-coverage.md](../docs/design/requirements-coverage.md) | 16 | nodes |
| [docs/enterprise_resilience.md](../docs/enterprise_resilience.md) | 115 | nodes |
| [docs/indexnow-sitemap-backfill-plan.md](../docs/indexnow-sitemap-backfill-plan.md) | 204 | nodes |
| [docs/indicator-family-playbook.md](../docs/indicator-family-playbook.md) | 614 | nodes |
| [docs/indicator-index.md](../docs/indicator-index.md) | 1058 | nodes |
| [docs/knowledge-unknowns.md](../docs/knowledge-unknowns.md) | 94 | nodes |
| [docs/knowledge-workflow.md](../docs/knowledge-workflow.md) | 107 | nodes |
| [docs/mechanism-inventory.md](../docs/mechanism-inventory.md) | 2654 | nodes |
| [docs/missed_data_audit.md](../docs/missed_data_audit.md) | 449 | nodes |
| [docs/planet-view.md](../docs/planet-view.md) | 527 | nodes |
| [docs/pravki-21-reanalysis.md](../docs/pravki-21-reanalysis.md) | 52 | nodes |
| [docs/project-knowledge-acceptance.md](../docs/project-knowledge-acceptance.md) | 84 | nodes |
| [docs/research/capacity-measurement-2026-10-04.md](../docs/research/capacity-measurement-2026-10-04.md) | 69 | nodes |
| [docs/research/competitor-roschart-2026-10-04.md](../docs/research/competitor-roschart-2026-10-04.md) | 277 | nodes |
| [docs/research/competitor-tradingeconomics-2026-10-04.md](../docs/research/competitor-tradingeconomics-2026-10-04.md) | 445 | nodes |
| [docs/research/search-acceptance-2026-09-30.md](../docs/research/search-acceptance-2026-09-30.md) | 148 | nodes |
| [docs/research/search-accuracy-2026-10-04.md](../docs/research/search-accuracy-2026-10-04.md) | 206 | nodes |
| [docs/research/search-history-2026-09-30.md](../docs/research/search-history-2026-09-30.md) | 231 | nodes |
| [docs/research/search-history-replay-2026-09-30.md](../docs/research/search-history-replay-2026-09-30.md) | 493 | nodes |
| [docs/research/search-methods-2026-09-30.md](../docs/research/search-methods-2026-09-30.md) | 444 | nodes |
| [docs/research/search-monte-carlo-2026-09-30.md](../docs/research/search-monte-carlo-2026-09-30.md) | 167 | nodes |
| [docs/research/session-replay-review-2026-10-04.md](../docs/research/session-replay-review-2026-10-04.md) | 227 | nodes |
| [docs/research/ui-brainstorm-planet-2026-10-04.md](../docs/research/ui-brainstorm-planet-2026-10-04.md) | 100 | nodes |
| [docs/research/ui-brainstorm-scenarios-2026-10-04.md](../docs/research/ui-brainstorm-scenarios-2026-10-04.md) | 250 | nodes |
| [docs/research/ui-review-2026-10-04.md](../docs/research/ui-review-2026-10-04.md) | 39 | nodes |
| [docs/search.md](../docs/search.md) | 635 | nodes |
| [docs/server-hardening-runbook-2026-10-04.md](../docs/server-hardening-runbook-2026-10-04.md) | 59 | nodes |
| [docs/traffic-platform-2026-09-10.md](../docs/traffic-platform-2026-09-10.md) | 47 | nodes |
| [docs/verification/ssr-analytics-delivery-2026-09-30.md](../docs/verification/ssr-analytics-delivery-2026-09-30.md) | 41 | nodes |
| [docs/verification/us-eu-source-audit-2026-09-24.md](../docs/verification/us-eu-source-audit-2026-09-24.md) | 114 | nodes |
| [docs/verification/us-indicators-2026-09-24.md](../docs/verification/us-indicators-2026-09-24.md) | 41 | nodes |
| [docs/verification/world-forecast-v2-2026-09-24.md](../docs/verification/world-forecast-v2-2026-09-24.md) | 64 | nodes |
| [docs/workflow.md](../docs/workflow.md) | 498 | nodes |
| [frontend/public/brand/README-prompts.md](../frontend/public/brand/README-prompts.md) | 42 | nodes |
| [frontend/public/planet/README.md](../frontend/public/planet/README.md) | 112 | nodes |
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
