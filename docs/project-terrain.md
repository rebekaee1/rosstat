# Рельеф проекта — автоматически извлечённый срез

> Генерируется `scripts/build-project-terrain.py --refresh` через Graphify. Не править вручную.

[Локальный интерактивный просмотр — после `--render`](project-terrain.html) · [JSON](project-terrain.json) · [Архитектура](architecture.md) · [Контракты](data-contracts.md) · [История решений](architecture-history.md)

Экстрактор: `graphifyy==0.9.69`. Базовый commit: `b684290067bf`; снимок включает рабочие изменения. SHA-256 каждого входного файла записан в JSON. `unstaged_at_capture` и `untracked_at_capture` фиксируют состояние входов; коммит карты сам по себе не коммитит чужие изменения кода. HTML локальный, в Git не хранится; в чистом clone сначала выполнить `--render`.

## Покрытие

| Измерение | Число |
|---|---:|
| Файлы в инвентаризации | 1268 |
| Переданы структурному экстрактору | 1076 |
| Дали узлы графа | 1005 |
| Узлы / связи между символами | 12998 / 40627 |
| Связи между файлами (тип и уверенность сохраняются) | 8417 |

Полная инвентаризация относится к Git-дереву. Наличие в списке не означает, что каждый файл прошёл содержательный аудит. `nodes` — экстрактор нашёл структуру; `no_nodes` — файл прочитан экстрактором, но сущностей не получено; `inventory_only` — учтён без разбора структуры. Бинарные материалы, конфиги и данные включены в инвентарь; визуальное содержание скриншотов не анализировалось.

## Что означает связь

`EXTRACTED` и `INFERRED` — метки Graphify. Даже EXTRACTED означает статическую конструкцию, а не выполненный вызов. JSON сохраняет направление, тип, количество и примеры исходных строк. Внутрифайловые отношения остаются в полном Graphify-графе; внешние/неразрешённые endpoints не превращаются в выдуманные файлы. Отсутствие входящих связей не доказывает мёртвый код. Динамические реестры, HTTP, SQL, Redis и scheduler требуют контрактов из отдельных документов.

Метки связей: `{"EXTRACTED": 37353, "INFERRED": 3274}`.
Не включены в проекцию между файлами: `{"external_or_unresolved_file": 2196, "missing_endpoint": 2375, "within_file": 17434}`.

## Слои файлов

| Папка | Файлов | С узлами |
|---|---:|---:|
| `(root)` | 8 | 3 |
| `.cursor` | 11 | 0 |
| `.github` | 3 | 0 |
| `.tours` | 1 | 0 |
| `backend` | 623 | 539 |
| `clickhouse` | 2 | 0 |
| `deploy` | 10 | 3 |
| `docs` | 100 | 45 |
| `frontend` | 425 | 340 |
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
| [AGENTS.md](../AGENTS.md) | 421 | nodes |
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
| [docs/architecture.md](../docs/architecture.md) | 153 | nodes |
| [docs/backlog.md](../docs/backlog.md) | 1665 | nodes |
| [docs/data-contracts.md](../docs/data-contracts.md) | 91 | nodes |
| [docs/data_sources.md](../docs/data_sources.md) | 641 | nodes |
| [docs/dead-code-report.md](../docs/dead-code-report.md) | 82 | nodes |
| [docs/design/README.md](../docs/design/README.md) | 104 | nodes |
| [docs/design/accessibility-review.md](../docs/design/accessibility-review.md) | 58 | nodes |
| [docs/design/art-prompts/forecast-glass-reconstruction.md](../docs/design/art-prompts/forecast-glass-reconstruction.md) | 54 | nodes |
| [docs/design/design-review-gallery.md](../docs/design/design-review-gallery.md) | 78 | nodes |
| [docs/design/local-acceptance/README.md](../docs/design/local-acceptance/README.md) | 31 | nodes |
| [docs/design/requirements-coverage.md](../docs/design/requirements-coverage.md) | 16 | nodes |
| [docs/enterprise_resilience.md](../docs/enterprise_resilience.md) | 99 | nodes |
| [docs/indexnow-sitemap-backfill-plan.md](../docs/indexnow-sitemap-backfill-plan.md) | 204 | nodes |
| [docs/indicator-family-playbook.md](../docs/indicator-family-playbook.md) | 614 | nodes |
| [docs/indicator-index.md](../docs/indicator-index.md) | 1055 | nodes |
| [docs/missed_data_audit.md](../docs/missed_data_audit.md) | 449 | nodes |
| [docs/traffic-platform-2026-09-10.md](../docs/traffic-platform-2026-09-10.md) | 47 | nodes |
| [docs/verification/us-eu-source-audit-2026-09-24.md](../docs/verification/us-eu-source-audit-2026-09-24.md) | 114 | nodes |
| [docs/verification/us-indicators-2026-09-24.md](../docs/verification/us-indicators-2026-09-24.md) | 41 | nodes |
| [docs/verification/world-forecast-v2-2026-09-24.md](../docs/verification/world-forecast-v2-2026-09-24.md) | 64 | nodes |
| [docs/workflow.md](../docs/workflow.md) | 196 | nodes |
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
