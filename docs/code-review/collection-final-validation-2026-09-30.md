# Завершение сбора и проверки досье — 30 сентября 2026

Работа: документация и инструменты знания для локальной `main`, основание
`05302ff1c4dbe104850116e6206d168ec4fa91d3` плюс собственный проверенный diff.
[Итоговая приёмка](../project-knowledge-acceptance.md) и
[неизвестное/проблемы](../knowledge-unknowns.md) задают объём и предел результата.

## Проверки приложения

**Итоговый полный `./scripts/check-all.sh`: exit0, `ALL CHECKS OK`.**
Чистая копия: knowledge gate и две серии по 10 тестов прошли. Из восьми новых
регрессий семь прошли, Babel случай явно skipped без dependencies; рабочая
копия выполняет все восемь.

Результат приложения:

- Backend: **3062 passed, 9 skipped, 73 warnings**.
- Frontend: **924 passed, 112 test files**.
- ESLint: **0 errors, 5 warnings**; Vite build успешно, предупреждения о chunks
  больше 500 kB сохранены. Precompress: 74 файла.
- Client AST inventory, Babel symbol guard и terrain DOM прошли.
- Первый финальный запуск остановился после этих фаз на `indicator-index --check`.
  Причина: старые карты включали nonignored untracked research inputs.
  Оба генератора исправлены на default Git tracked/index; рабочий срез теперь
  требует явного `--include-untracked`. 947 кодов, summary и completeness
  сохранены; в 189 записях обновилось только поле files. Результат повторного
  полного запуска и отдельных guards — в [JSON](collection-final-validation-2026-09-30.json).

Приложение не менялось при последующей актуализации доказательств. Повтор всей
pytest/vitest матрицы не нужен для изменения отчётного JSON; полный gate
повторяется один раз после исправления области входов карт, затем остаются
только read-only guards актуальности доказательств.

## Независимые и переносимые проверки

Восемь новых regressions проверяют классификацию omission edges, неоднозначность
путей, точные fingerprints, Babel callback/route/storage, полный MCP fallback и
stale HTML, saved JSON ordering после refresh и отделение Git index от untracked. Чистая копия без `node_modules` выполняет семь stdlib случаев,
а Babel случай явно skipped; рабочая копия выполняет все восемь.

Две существующие серии stdlib guards содержат по десять тестов.
Backend terrain suite входит в общий pytest. Независимый reviewer дополнительно
выполнил четыре targeted probes; actual-body backend protocol — семь рискованных
механизмов и отдельная inventory fixture. Эти числа не суммируются с app tests
в новый показатель тестового покрытия.

[Чистая копия](clean-copy-acceptance-2026-09-30.json) экспортируется из Git index
в отдельный временный каталог. Там нет локальных `.artifacts`, Graphify environment,
HTML или `node_modules`; stdlib knowledge gate проверяет portable JSON/Markdown,
source reviews и материалы. Старый результат первого этапа сохраняется отдельно. Итоговый экспорт `ea1ff9be5a8f0e66b14163088edccf5b5a056d2c`
прошёл все четыре commands exit0.
Это локальная переносимость, не remote GitHub CI или production acceptance.

Offline viewer проверяется на 1440 и 390 px: все 213 элементов App доступны,
нет overflow, page errors и внешних запросов. [Viewer protocol](terrain-viewer-acceptance-2026-09-30.json).

## История и границы

Пять критичных старых планов прочитаны полностью: Analytics OS в
[materials](material-content-acceptance-2026-09-30.md), три плана в
[supplement](historical-plan-supplement-2026-09-30.md), BI в
[BI supplement](historical-bi-plan-supplement-2026-09-30.md).
Первоначальные отчёты с handoff/pending остаются датированными свидетельствами;
содержательные дополнения закрывают именно указанное чтение.

Server/application/restore наблюдения имеют отдельный
[ops protocol](ops-mechanism-acceptance-2026-09-30.md), fresh-agent navigation —
[cold start](cold-start-acceptance-2026-09-30.md). Общие локальные тесты не заменяют
capacity measurement, полный failover, числовую сверку всех источников или проверку
недоступных originals/provider cabinet. Обнаруженные runtime проблемы не исправлялись
изменением документации. Push/deploy в этой работе не выполняются.

Машинный итог, фазы, SHA исполнения и оставшийся объём — в
[JSON](collection-final-validation-2026-09-30.json).
