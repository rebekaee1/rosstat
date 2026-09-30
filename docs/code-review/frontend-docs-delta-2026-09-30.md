# Frontend, документы и история — содержательная дельта 2026-09-30

## Версия и предел проверки

Основа: локальная `main 972579f0b95b70d0ac8d4293331cd8d18c2521fe`, затем собственные
незакоммиченные документационные изменения и параллельные изменения других агентов.
Чужие untracked `assets/` и `.artifacts/` сохранены; они не входят автоматически
в tracked/index снимок main. Итоговый снимок и guards пересобирает корневой агент.
Сервер, API поставщиков и кабинеты этим проходом не опрашивались; commits/push/deploy
и runtime-фиксов нет. Тесты прочитаны как контракты с mocks; полный suite и браузер
не запускались. Это содержательная дельта, не независимая cold-start приёмка.

Прежнее знание сохранено: SHA старой рецензии сопоставлялся с точными байтами Git.
Для неизменённого тела используется прежнее полное чтение с явной версией, для
нового поведения прочитана полная дельта и связанные источники. Отдельные новые
файлы прочитаны целиком. Прежний SHA английского словаря не совпал ни с одной
Git-версией пути; текущие 1972 строки перечитаны целиком без inherited-основания.

## Что изменилось по смыслу

| Механизм | Текущее поведение по исходнику | Основание / граница |
|---|---|---|
| Валютный каталог | `/currencies` и currency-aware пути карточек/периодов; это исключение country-first. Brent/другие рынки не становятся валютами. | `sitePaths.js`, `App.jsx`, `CategoryPage.jsx`, breadcrumbs, categories и generated meta; backend builder адресно сверён. Живые 301 нового релиза не проверены. |
| Страны в сравнении | Одна доказанно сопоставимая concept-группа; начальный EN-список стран ставит США первым. Мировая частота остаётся официальной. | `ComparePage.jsx`, related component test, timecoded `pravki-21-reanalysis.md`. API mocks не доказывают весь актуальный каталог. |
| Общая база | Положительные уровни получают 100 на первой общей фактической дате внутри видимого окна; без пересечения — empty state. Проценты/знакопеременные исключены; разные HICP-базы требуют rebasing. | `commonIndexBase`, `isIndexableBase`, `requiresRebasedPriceIndex`, consumer ComparePage и добавленные тесты. Нет LOCF ради выдуманной начальной даты. |
| World card peers | GDP/population size concepts остаются в значениях по умолчанию; index opt-in. HICP catalogue peers согласуют rate-mode и frequency, Россия и сырой benchmark исключены. | `useCountryComparison.js` прочитан целиком; component tests нормализации `minus_100`. Входящий `peers` фильтрует Россию, остальные полагаются на свой producer: это отдельная граница контракта. |
| Источник / бренд | Основная methodology при неизвестном URL показывает источник текстом; гостевая подпись графика скрыта для вошедшего и auth-loading. | MethodologyPanel/ChartBrandCaption/tests; публичная provenance и правила быстрых страниц сохраняются отдельно. |
| Главная / поиск | RU региональное число не смешивает США и РФ; EN имеет world/US-подпись. Пустой EN-поиск начинает с curated US, typed search включает страны и loading. | HomeDataScope, IndicatorSearch и mocked tests. Цифры из fixtures не выданы за живой каталог. |
| Огромный каталог / карта штатов | Dense rendering ограничен для любой страны, строки доступны через reveal/search; non-US desktop сохраняет секции. Custom metric picker больше не ужимается tabs-строкой. | WorldCountry, component test и WorldRegionsHome; новая визуальная приёмка не выполнялась. |
| РСЯ | Shared rsyFloorAd применяется SPA и standalone SSR, data-no-ads исключает 404; timer destroy отключён, fill-goal отделён от cleanup по SDK onError, refresh cooldown 15 с. | Общий модуль и обвязки прочитаны; production release `535f226` и disabled provider page остаются датированным backlog-свидетельством. |
| Ticker | По6 кодов в RU/EN lane, lane от locale; карточные Brent/EIA, золото/ЦБ и EN-кроссы/ЕЦБ берутся из DB. Redis TTL 90 с, дневная память 300 с; normal polling 4 с с backoff429/ошибок. | API, worker constants/write path, LiveTicker и tickerPoll/tickerLane. Старые TTL 30/futures/«≤9с лаг» в CONTEXT явно исторические; устаревший docstring/comment worker приведён корнем к текущим constants 30 сентября, runtime этим не изменён. |
| Решения / generated | ADR-0010 bot-signals и ADR-0011 structure reconciliation прочитаны как датированные additions; BLS API overlay отменён без отказа от BLS через FRED. Machine indicator index:194 annual forecast_steps 2→1, прочее references/line shifts. | Сохранены старые причины; schema/semantic delta не является проверкой каждого значения каталога. |

## Актуализированное знание

README исправляет старое UA-only SSR описание и nonexistent sshscript, ведёт к
[knowledge-workflow](../knowledge-workflow.md) и [agent-recipes](../agent-recipes.md).
CONTEXT сохраняет хронику и добавляет дату/версии, currency/comparison/source,
точный ticker/RSYA, отменённый pure-revision предел и прежнее «только регистрация».
Опасный старый orphan-delete рецепт помечен историческим и подчинён проверке
consumers/redirect/history. [Architecture history](../architecture-history.md)
сохраняет прежнюю таблицу и маршруты восстановления удалённых документов,
фиксирует поздние уточнения и новое расположение прежних AGENTS-рецептов.

`.cursor/project.mdc` теперь ведёт к recipes/workflow; стандартный FLUSHDB
заменён namespace invalidation с сохранением основания старого разового релиза.
Рабочее соглашение ссылается на обязательный цикл знаний; packet-fixes различает
старое до-cutover условие apex-RU и нынешний locale-контракт.

## Точные прочитанные пути

### Полное текущее тело

- `.cursor/rules/packet-fixes.mdc`
- `.cursor/rules/project.mdc`
- `.cursor/rules/working-agreement.mdc`
- `CONTEXT.md`
- `README.md`
- `docs/architecture-history.md`
- `docs/pravki-21-reanalysis.md`
- `frontend/src/behavior-standalone.js`
- `frontend/src/behavior-standalone.test.js`
- `frontend/src/components/ChartBrandCaption.component.test.jsx`
- `frontend/src/components/ChartBrandCaption.jsx`
- `frontend/src/components/home/HomeDataScope.component.test.jsx`
- `frontend/src/i18n/messages.en.js`
- `frontend/src/lib/useCountryComparison.component.test.jsx`
- `frontend/src/lib/useCountryComparison.js`
- `.cursor/rules/indicator-data-delivery.mdc`
- `.cursor/rules/i18n-parity.mdc`
- `.cursor/rules/world-ui-parity.mdc`
- `.cursor/rules/outside-acceptance.mdc`
- `.cursor/rules/subagents.mdc`
- `.cursor/rules/no-middle-dot.mdc`
- `.cursor/rules/methodology-language.mdc`
- `frontend/package.json`
- `frontend/src/components/YandexRSY.jsx`
- `frontend/src/lib/rsyFloorAd.js`
- `frontend/src/lib/tickerLane.js`
- `frontend/src/lib/tickerPoll.js`
- `backend/app/api/ticker.py`
- `scripts/code-review-symbols.mjs`
- `AGENTS.md`
- `docs/knowledge-workflow.md`

### Прежнее полное чтение + содержательная дельта

Точные baseline commit/hash и current changed ranges находятся в каждой строке
[предложенных рецензий](frontend-docs-delta-reviews-2026-09-30.jsonl).

- `docs/adr/0010-analytics-contour-identity-goals-marts-olap.md`
- `docs/adr/0011-world-eurostat-data-plane.md`
- `docs/backlog.md`
- `docs/data_sources.md`
- `docs/dead-code-report.md`
- `docs/indicator-index.md`
- `frontend/index.html`
- `frontend/public/llms.txt`
- `frontend/src/App.jsx`
- `frontend/src/components/CountryComparePicker.component.test.jsx`
- `frontend/src/components/CountryComparePicker.jsx`
- `frontend/src/components/IndicatorMethodologyPanel.component.test.jsx`
- `frontend/src/components/IndicatorMethodologyPanel.jsx`
- `frontend/src/components/IndicatorSearch.component.test.jsx`
- `frontend/src/components/IndicatorSearch.jsx`
- `frontend/src/components/WorldChartSection.jsx`
- `frontend/src/components/home/HomeDataScope.jsx`
- `frontend/src/i18n/messages.ru.js`
- `frontend/src/lib/breadcrumbs.js`
- `frontend/src/lib/breadcrumbs.test.js`
- `frontend/src/lib/categories.js`
- `frontend/src/lib/compareRepresentation.js`
- `frontend/src/lib/compareRepresentation.test.js`
- `frontend/src/lib/globalMarketIndicators.js`
- `frontend/src/lib/sitePaths.js`
- `frontend/src/lib/sitePaths.test.js`
- `frontend/src/pages/CategoryPage.jsx`
- `frontend/src/pages/ComparePage.component.test.jsx`
- `frontend/src/pages/ComparePage.jsx`
- `frontend/src/pages/Dashboard.component.test.jsx`
- `frontend/src/pages/WorldCountry.component.test.jsx`
- `frontend/src/pages/WorldCountry.jsx`
- `frontend/src/pages/WorldRegionsHome.jsx`

### Generated schema / полная семантическая дельта

- `docs/indicator-index.json`
- `frontend/src/lib/pageMeta.generated.json`

### Адресная сверка / метаданные

- `backend/app/tasks/ticker_worker.py`: 1–59,120–188; REDIS_TTL_SECONDS and _SERIES_TICKER_SPECS.
- `frontend/src/components/LiveTicker.jsx`: 1–165; polling/dated-vs-intraday labels.
- `backend/app/services/ticker_sources/moex_iss.py`: source/Fx fallback declarations and fetch branches located by rg.
- `backend/app/tasks/scheduler.py`: 56–79,97–113; _fetch_changed.
- `backend/app/api/auth.py`: 85–98, login callsites; notify_login.
- `backend/app/services/base_parser.py`: zero-parse/dispatch reference spot checks; not full body review.
- `backend/app/services/site_paths.py`: currency reserved/classification/canonical builders.
- `docs/repo-inventory.md`: generator contract, headers, full listing structurally parsed; file bodies not read by inventory.
- `docs/project-terrain.md`: saved graph coverage/limits and reading route; no raw graphify-out available.
- `docs/code-review/readiness-criteria.md`: K01–K12 and all-format scope; section9 prior targeted reconciliation review.
- `docs/code-review/source-documents/2026-09-28-opus-forecast-economy-audit.md`: prior targeted review of decisive cited claims; copy hash verified separately.
- `docs/agent-recipes.md`: relocation/canonical/FAST-PATH opening; rest preserved and read by root.
- `docs/code-review/source-documents/AGENTS-before-knowledge-workflow-2026-09-30.md`: archive opening/old line references; byte-identical copy verified by root.

## Форматы и внешние области

[Машинный реестр](materials-2026-09-30.json) содержит current/canonical,
historical, generated, copy и отдельный review-status; он не приравнивает
metadata к прочитанному содержанию. Перечислены также исключённые из sourceguard
`docs/code-review/` evidence и собственная self-reference без рекурсивного hash.

30 сентября проверены имена файлов с учётом ignored/case в текущем checkout,
`../rosstat-docs` (HEAD `bb84eaab67f1400ad61578ac25084a73db14492f`),
`../rosstat-analysis` (HEAD `06ef84eee5b5ee8aedc49b9939efb9ae067c993d`),
`../rosstat-wip-snapshots`, `../rosstat-branch-backups`. Исключены `.git`,
node_modules/venv, build/dist и Python caches. DOC/DOCX/PDF/ODT/RTF/PPT(X),
notebooks, MOV/MP4/audio не найдены как файлы; такой вывод ограничен этими местами.
В шести `.tar.gz` проверен список членов: специальных форматов также нет; содержание
архивированных исходников/визуальных материалов целиком не изучено. Git bundle
не распакован и не использован как доказательство полноты всей истории.

13 XLSX из `docs/research/` совпадают побайтово с одноимёнными файлами
`../rosstat-docs/docs/research/`; содержимое листов/формул/комментариев в данном
проходе не исследовалось. Это исследовательские источники с неизвестной текущестью,
не автоматически действующая инструкция. Изображения и diagram SVG учтены по
метаданным/другим датированным рецензиям; этот проход не просмотрел их визуально.
Новые чужие illustrations не принимаются за текущую архитектуру по имени файла.

Найдена указанная рабочим соглашением папка
`/Users/iprofi/.cursor/projects/Users-iprofi-tradingeconomics-rosstat/agent-transcripts`:
1373 JSONL (включая subagents), учтены пути/hash, содержание целиком не прочитано.
Видео «НА ПРАВКИ 21.mov» доступно здесь через датированный Markdown reanalysis,
сам видеофайл в проверенных местах не обнаружен. Новых облачных project links
в проверенных Markdown/TXT/rules не найдено; кабинеты/облака и весь Home не сканировались.
Opus original/copy и прежний owner AGENTS сохраняют даты и самостоятельные версии.

## Оставшиеся неизвестные

| ID | Вопрос / класс | Прочитанное основание | Следующий способ проверки |
|---|---|---|---|
| FD01 | Current production/render/provider state: недоступное новое наблюдение | dated runtime/backlog, локальный main | Отдельный разрешённый runtime/Host/browser/provider check с SHA и датой; не смешивать с чтением кода. |
| FD02 | Workbook formulas/mappings and image/audio decisions: незавершённое чтение материалов | discovery+hash/копии, reanalysis | Читать конкретный XLSX/visual/original video по связи с задачей; проверить extraction/comments/render где требуется. |
| FD03 | История Cursor/archive versions: незавершённый разбор большого historical корпуса | metadata 1373 JSONL, 17 архивных файлов,2соседних checkout | Идти по обнаруженной ссылке/решению к точной версии; не объявлять весь корпус изученным. |
| FD04 | Полная semantic eligibility входящего world peers, адекватность публичной methodology для каждой стратегии | hook/API interface и EN-словарь; локальные mocks | Связать producer peer metadata с частотой/единицей по конкретной карточке; backend стратегия отдельно. Наличие текста не доказывает соответствие каждой стратегии. |
| FD05 | Независимая cold-start приёмка и полное K01–K12 | workflow/readiness только задали процедуру | Новый агент без чата выбирает сценарии по инвентарю; root сводит доказательства и ограничения. |

## Проверки данного прохода

- Статический JS inventory пересобран:368 файлов, 1692 определения, 0 parse errors
  до введения root tracked-only режима. Итоговый tracked/index inventory строит root.
- 50 предложенных review rows, 223 JS definitions, exact baseline SHA where inherited.
- JSONL парсится; `git diff --check` собственных документов/rules без ошибок.
- Содержание runtime/prod, provider SDK, весь test suite и browser acceptance не проверялось.
