# Приёмка рабочего цикла знаний — 30 сентября 2026

**Последующее завершение:** [приёмка K01–K12](../project-knowledge-acceptance.md).
Этот протокол сохраняет первый этап 30 сентября; новые inventories, actual-body
probes, restore owners/auth, visual materials и fresh-agent acceptance отражены
в последующем протоколе, не переписывают исходные пределы этого испытания.


Основа: локальная `main 972579f` и изменения этой задачи. Итоговая структура
фиксирует tracked/index inputs; чужие untracked материалы не удалены и не
включены в commit. Это выполнение первых шагов [очереди](../backlog.md#knowledge-workflow-2026-09-30),
а не объявление всей платформы изученной и исправной.

## Выполнено

- Сохранён старый AGENTS побайтово, действующие рецепты перенесены в
  [agent-recipes](../agent-recipes.md). Короткий вход ведёт к обязательному
  [циклу обычной задачи](../knowledge-workflow.md); README/CONTEXT, подробные
  документы и правила согласованы с прочитанными изменениями.
- [Backend delta](backend-delta-2026-09-30.md), [frontend/docs delta](frontend-docs-delta-2026-09-30.md)
  и [ops manifest](ops-read-manifest-2026-09-30.json) различают новое полное
  чтение и прежнее полное чтение с проверенной содержательной дельтой.
- [Материалы](materials-current.json) отделяют current/historical/generated/copy
  от body/schema/metadata review. Изображение или таблица не становятся
  содержательно прочитанными по одному хешу. Поиск ограничен указанными местами.
- [Runtime 30.09](runtime-observation-2026-09-30.json) сохраняет отдельно
  фактический серверный SHA, ресурсы 4 vCPU и effective settings. Production
  этим этапом не изменён; исходный [runtime 27.09](runtime-inventory-2026-09-27.json) сохранён.
- [Бэкап](backup-acceptance-2026-09-30.md) доставлен с совпадающим SHA и восстановлен
  в изолированной PostgreSQL: full и identity. Next launchd, owner/ACL, приложение
  на восстановленной БД и полный failover/RTO/RPO этим не подтверждаются.
- Read-only gates подключены к check-all и CI. Структура/источники, рецензии,
  символы и материалы проверяются отдельно; автоматического reviewed stamp нет.

## Статус критериев K01–K12

| Область | Что подтверждено | Что остаётся |
|---|---|---|
| K01: версия/границы | Local main, owned diff, scope снимков и отдельный датированный prod | Образ контейнера не полностью аттестован по исходникам |
| K02–K04: состав/элементы/связи | Git inventory, именованные Python/JS определения, прежние рецензии + прочитанная дельта | Полная независимая сверка inventories маршрутов/полей/jobs/config и классификация всех unresolved graph endpoints не выполнены |
| K05–K06: lifecycle/сценарии | Контракты ingestion/forecast/UI/identity/analytics и новые расхождения описаны | Partial response, commit→invalidate, региональные writers/cache, Eurostat remap, оконные сессии и CH late commit требуют отдельных воспроизводимых проверок |
| K07–K09: среда/ops/внешние системы | Defaults/source и выбранные effective values; сервер 4 vCPU; схема/data restore | Не все host/provider настройки доступны; смешанная нагрузка, full failover, provider backup, все внешние ограничения не приняты |
| K10–K11: история/основания | Старые документы/ADR/Opus сохранены, отменённые правила отмечены, provenance отделена | Не все внешние переписки, изображения/записи и XLSX содержательно разобраны; отсутствие сохранённого мотива обозначается неизвестным |
| K12: вход/обновление | Обязательный цикл и guards реализованы, независимый tools review проведён | Полная сценарная приёмка новым агентом без истории чата открыта |

## Проверки

Локальный backend pytest: **3062 passed, 9 skipped, 73 warnings**; frontend Vitest:
**924 passed / 112 files**. ESLint: **0 errors, 5 существующих warnings**; Vite build
и precompress успешны, предупреждение о больших chunks сохраняется. Эти тесты
преимущественно используют SQLite/mocks/jsdom и не заменяют live PG/Redis/CH,
браузерную UI-приёмку или release smoke. Deploy fake-shell: 18 passed; OG retry:
7 passed. Knowledge regressions: **20 passed** (10 source-ledger, 10 material/scope).
Coverage: **1301/1301** current rows, **8413/8413** именованных определений с
аннотациями, 0 attention. Babel: 368 файлов, 1692 определения, 0 parse errors.
Структура: 1301 файл, 8661 file edges; unresolved/missing endpoints сохранены
в projection omissions и не объявлены изученными runtime-связями.
[Clean-copy proof](clean-copy-acceptance-2026-09-30.json): staged Git tree экспортирован
в пустой временный каталог, создан отдельный Git index; knowledge gate и обе
regression suites прошли без local untracked/ignored файлов, Graphify и app dependencies.
Временная копия удалена. Это проверка статического CI-входа на локальной машине;
remote GitHub CI и новый агент без истории чата ею не подменяются.
Remote CI не запускался: push отсутствует.

`./scripts/check-all.sh` завершился с **exit 0**: knowledge/source/terrain/material
gates, backend pytest, JS symbol check, frontend test/lint/build, indicator map,
doc counters, page meta и public-language audit. Повторный общий прогон использовал
те же исходники и подтвердил интеграцию нового gate. CI migrations/docker/E2E и
visitor browser smoke этим запуском не выполнялись.

Независимый tools reviewer нашёл два пробела: terrain принимал неверный
`input_scope` при совпадении fingerprints; весь `code-review/` исключался из
source-guard. Первый исправлен явным scope check; для второго добавлена отдельная
проверка SHA материалов без рекурсивного хеширования самого manifest.

## Проверка без истории чата

Новый collaboration-agent не создался из-за лимита agent threads текущей сессии.
Отдельный CLI exec не получил ответа модели: установленный CLI 0.46.0 сначала
не принял конфигурацию reasoning `ultra`, затем текущая модель `gpt-6.1-sol`
не поддержалась его ChatGPT account transport. Исходники, пользовательская
конфигурация и глобальная установка CLI ради обхода не менялись. Это технический
предел попытки, не успешная cold-start приёмка. Следующий шаг: отдельный новый чат
с repo/AGENTS и обычной задачей, без передачи нашей переписки; критерии — K12.

Общий зелёный guard подтверждает актуальность зафиксированных свидетельств.
Он не устанавливает истинность каждого описания, полный охват всех runtime
ветвей или способность любого нового агента правильно изменить платформу.
