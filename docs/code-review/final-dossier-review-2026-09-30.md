# Независимая проверка инструментов досье — 30 сентября 2026

Область: root changes в client inventory, Graphify omission classification,
terrain overlays/viewer, guards и CI; согласованность итоговой приёмки и unknowns
с нашим backend evidence. [SHA, findings и команды](final-dossier-review-2026-09-30.json).
Никаких runtime исправлений, коммитов, серверных вызовов или изменений общего ledger.

## Найденные проблемы и повторная проверка

| ID | До исправления | Принятое исправление и независимое основание |
|---|---|---|
| DR01 / P2 | При валидных JSON/Markdown obsolete HTML давал `check=0`; встроенные review/mechanism статусы могли устареть | [check:429](../../scripts/build-project-terrain.py#L429) сравнивает существующий HTML с `render(data)`. Actual function probe теперь возвращает1. Отсутствующий ignored HTML допускается с сообщением: clean clone возвращает0 |
| DR02 / P2 | Backend fallback7 MCP tools без client inventory показывал только1, `current=True` | [overlay:342](../../scripts/build-project-terrain.py#L342) фиксирует client MCP paths до backend loop. Actual function probes: fallback7/7; client-prefilled7/7 без дубликатов |
| DR03 / P2 | Датированная omission classification не была связана portable guard с текущим terrain | [check_identity:117](../../scripts/classify-graph-omissions.py#L117) проверяет SHA terrain, omission totals и category totals; `--check` включён в knowledge gate. Regression: изменённые terrain bytes и удалённая запись отвергаются. Raw `.artifacts` для clean CI не требуется |
| DR04 / P3 | K06 называл8 рискованных механизмов вместо7 рисков + AST fixture | [Приёмка:45](../project-knowledge-acceptance.md#L45) теперь точно различает7 actual-body mechanism cases и1 inventory fixture |

Все четыре замечания закрыты в проверенных изменениях. Первоначальные результаты
DR01 (`exit0` при obsolete HTML) и DR02 (`1/7`) воспроизведены отдельно до правки;
исправление выполнил root. [Наши четыре повторных probes](final-dossier-review-probes-2026-09-30.json)
используют реальные функции, временные файлы и явную подмену только Git inventory
на идентичные сохранённые fingerprints. Приложение и сеть не импортируются.

## Выполненные проверки

- Собственные probes: **4/4**.
- Root regression suite `scripts/tests/test_mechanism_inventories.py`: **6/6**;
  Node/Babel fixture выполнена, не пропущена.
- `node scripts/test_project_terrain.mjs`: passed; search/filter/drilldown/missing
  review/full mechanisms/text escaping. Это DOM, не повторная visual приёмка.
- Client inventory `--check`: passed;351 файлов,5376 функций,3905 anonymous,
  1707 imports,72 route declarations,1339 hooks,64 HTTP call sites,555 handlers,
  7 MCP registrations; parse errors0. В счётчиках есть тестовые declarations.

## Циклы, scope и clean CI

Самозависимость SHA не найдена. Terrain JSON/MD/HTML и evidence directory не
входят в собственный terrain denominator. Classifier output связан с terrain SHA,
но не является его input. HTML renderer читает overlays, не собственный HTML.
Materials manifest/pointer исключены из собственного identity gate. Backend/client
generators не читают review ledger и не назначают `reviewed`.

Knowledge CI использует stdlib и portable артефакты. Node-dependent test явно
пропускается без Babel и повторяется в frontend job после `npm ci`; client generator
`--check` запускается там же. Отсутствие локального ignored HTML не делает свежий
checkout некорректным. Имеющийся устаревший HTML теперь отвергается.

## Граница выводов

Итоговые backend counts,7+1 probes и F01–F07/F14 согласуются с нашим содержательным
чтением и воспроизведениями. Изолированные doubles не доказали реальную конкуренцию
PostgreSQL/Redis/ClickHouse или частоту инцидентов. Исторические материалы, notebooks,
сервер, restore и визуальная приёмка подтверждаются отдельными протоколами других
агентов; здесь они повторно не исполнялись.

Блокирующих ошибок в проверенных исправлениях не осталось. Финальные current SHA,
общий ledger, пересборка terrain/classifier/material registry и полный integration
gate принадлежат root; эта проверка не объявляет их автоматически зелёными.

## Итоговая crosscheck после объединения reader row

[Датированная final reconciliation](backend-mechanism-crosscheck-2026-09-30.json):
405/405 source SHA,3655/3655 named definition annotations,144/144 handlers;
missing/stale/unmatched/duplicate0. Исходный baseline403 сохранён.
Это identity/localization поверх ручных рецензий; исполнение всех ветвей не доказано.
