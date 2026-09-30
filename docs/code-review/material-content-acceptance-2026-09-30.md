# Содержательная приёмка материалов — 30 сентября 2026

**Статус:** завершено чтение доступного содержимого в указанной ниже области;
ограничения и pending сохранены. Это evidence для K10/K11, а не самостоятельная
приёмка всей платформы. Начальная локальная main: `05302ff1c4dbe104850116e6206d168ec4fa91d3`;
параллельные локальные изменения перечисляются отдельными рецензиями. Production
не запрашивался. Исходные XLSX, ноутбуки, архивы, изображения и переписки не изменены.

Точные пути, SHA, sheet/cell, notebook cell/output, transcript line и классификация
находятся в [JSON-досье](material-content-acceptance-2026-09-30.json).
Оно содержит нейтральные выводы и указатели, без исходных частных переписок,
секретов, аудиобайтов или пользовательских фотографий. Общий
[реестр](materials-2026-09-30.json) этим документом автоматически не переписан;
обновление предложено отдельно с сохранением прежнего evidence.

## 1. Метод и предел доказательства

[Readiness criteria](readiness-criteria.md) прочитан целиком, включая K01–K12 и
датированную сверку Opus. Содержимое файла, смысл требований, код механизма,
сохранённый результат и проверенное окружение — разные основания.

Для XLSX применён read-only маршрут skill `spreadsheets:Spreadsheets`: прочитаны
SKILL и относящиеся references; по заданию использован stdlib ZIP/XML reader,
без Excel, пересчёта или сохранения книги. Полное извлечение ячеек не является
проверкой каждого экономического значения против обновившегося ведомства.
Семантическая сверка охватывает схему, источники, срезы, частоты, единицы,
статус оценок и расхождения с действующими правилами.

Для исторических checkout сравнивались точные bytes/SHA и полный текстовый diff
с main; совпадающие фрагменты не объявлены новым независимым чтением. Для
переписок просканированы все user messages, затем дедупликация и содержательный
отбор решений. Assistant/tool сообщения не являются директивами владельца.
Выборка не доказывает исчерпывающую ручную интерпретацию каждого частного сообщения.
Визуальная классификация сделана по действительно просмотренным контактным
листам; мелкий текст каждого снимка не принят по thumbnail.

## 2. Все 13 research XLSX

Reader: [read-project-workbooks.py](../../scripts/read-project-workbooks.py).
Прочитаны **37 листов, 94 224 непустые ячейки, 9 233 строки с данными/заголовками**.
Все source SHA до и после совпали. Проверены формулы, состояния листов, hidden
rows/columns, comments, hyperlink objects, external workbook links и media:
в этих книгах их нет. URL находятся в обычных строковых ячейках.

| Книга | Содержательный вывод |
|---|---|
| `catalog-scan-2026-07-19.xlsx` | Summary сообщает 17 264 набора; лист «Наборы» содержит только 8 000 (2 759 IBGE, 5 241 Eurostat). `A8002` прямо поясняет truncation. ONS в summary есть, в выгрузке листа нет. 42 строки заканчиваются после 2026 года: `A18`/соседние колонки — population projection 2019–2100. «81 год» здесь не история наблюдённых фактов. |
| `intl-sources-2026-07-19.xlsx` | README `B13/B15` описывает curated shortlist и ETL пригодность, а не полный каталог; P0/P1/P2 — июльские исследовательские приоритеты, не результат сегодняшнего внедрения. |
| Brazil | SIDRA GDP требует нужного classification; PNAD rolling quarter не обычный календарный квартал; BCB daily и Tesouro имеют разные ограничения. Stock/flow, WEO forecast и nominal/real разделять. |
| China | NBS legacy/new API, PBOC и MOF имеют разные истории, базы и cadence; MOF YTD нельзя выдавать за месячный flow. ChinaData/агрегатор не национальный первоисточник. Июльские 403 и оценки доступа не свежая проверка. |
| France | INSEE BDM/Melodi и Banque de France — разные каталоги; FR/EA, CIF/FOB и товары/услуги нельзя смешивать. Упоминание ключей/лимитов датировано исследованием. |
| Germany | История DE/West Germany, базы и национальный вклад M3 отличаются от агрегата EA. Совет research считать Eurostat primary для DE не заменяет позднее national-first решение. |
| India | MoSPI/RBI/OEA, base revisions и fiscal year различаются; CGA progressive YTD не monthly flow; ILO estimate не PLFS observation. |
| Japan | Fiscal/calendar, денежные stocks и резервы — разные сущности; наличие API key gate не означает отсутствие официальных открытых данных. |
| Russia | 55 субъектов/376 dataset строк включают и ведомственные реестры, и временные ряды. Official agency/portal не означает подтверждённый публичный macro API. DOC/DOCX/PDF могут быть необходимы для старого backfill. |
| South Korea | KOSIS и BoK ECOS имеют разные владельцев рядов и охват; sample десяти строк не вся история. |
| Turkey | CPI base changes и EVDS key/пагинация датированы; неподтверждённый SDMX не утверждение о работающем endpoint. |
| UK | Retail GB, population England/Wales и HMLR не общий UK; HMRC IMTS не ONS BoP; BoE spot не официальный policy rate. Месячный GDP существует в исследовательском каталоге. |
| USA | BEA annual 1929 и FRED quarterly 1947 SAAR не одна частота/единица; Treasury fiscal year отдельный; WB value-added percent не Fed industrial production. FRED mirror не заменяет методологического первоисточника. |

Все книги датированы **19 июля 2026**. Их API/search snippets, estimates и
доступность не перепроверялись по сети. Research summary/dataset counts не равны
числу действующих индикаторов FE, карточек, sitemap URL или проиндексированных страниц.
Действующий national-first маршрут находится в
[data_sources](../data_sources.md), ADR-0012 и [рецептах](../agent-recipes.md).
Данные каталога проверены на отсутствие duplicate `(source,id)` и пустых URL;
это узкая проверка структуры, не полнота каталога ведомств.

## 3. Одиннадцать исходных ноутбуков

Полностью прочитаны source cells и сохранённые текстовые outputs всех **11**
доступных IPYNB: **33 cells, 23 уникальных source cells, 56 outputs**. Все
**12 уникальных сохранённых PNG графиков** действительно просмотрены. JSON
содержит SHA каждого ноутбука/cell/output; одинаковый код CPI `(1)/(2)` и часть
общих plot/input cells дедуплицированы. Код не выполнялся, source bytes не менялись.

- Annual notebook строит **один** будущий год: ADF → differences/log differences,
  clipping выбросов, несколько OLS окон/лагов, отбор по correlation/p-value,
  inverse residual-MSE weighting и обратное преобразование. Saved `2024-01-01 =
  8.547826` — старый расчёт birth-rate, не актуальный forecast.
- Первоначальный `Прогноз_инфляции_12_мес.ipynb` создаёт **синтетический** CPI
  (`np.random.seed(42)`, 120 точек 2020–2029); saved 2030 не данные Росстата.
  Версия `(1)` берёт `ipc_mes_03-2026.xlsx`; происхождение этих двух inputs различается.
- Функции `train_sarima_model` в CPI/PPI/nominal GDP/housing фактически используют
  `sm.OLS`; импорт `SARIMAX` и имя функции не доказывают SARIMA реализацию.
  Monthly CPI выводит MoM процентные пункты, rolling inflation — 12-месячный
  compounded показатель, PPI/housing возвращают индекс, GDP — уровень млрд руб.
- Обновлённый месячный CPI смешивает target `4/1200` с `df-100`; масштаб target
  требует отдельной сверки при использовании исходника. Это наблюдение о
  историческом notebook, не найденный этим чтением дефект текущего runtime.
- GDP/housing дают четыре квартала; housing усиливает median contribution к
  дальнему горизонту. Generic monthly версии отличаются восстановлением:
  construction использует `m*latest`, M2 — cumulative forecast sum. Их нельзя
  свести к одному алгоритму по совпадению названия файла.
- Relative input XLSX (`birth-rate_data_all.xlsx`, `ipc_mes_02/03-2026.xlsx`,
  `ppi_data_all.xlsx`, `gdp-nominal_data_all.xlsx`, housing/construction/M2 exports)
  отсутствуют **рядом с notebook**. Их наличие в другом месте не исследовалось;
  воспроизводимость saved outputs не заявляется. Интервалы/качество/replay и
  точные input hashes нельзя восстановить из красивого графика.

Текущий registry/pipeline/fingerprint/quality и annual horizon=1 разобраны в
[backend-delta](backend-delta-2026-09-30.md) и отдельной backend mechanism приёмке.
Старый saved output не является доказательством exact implementation, deploy
или текущей стратегии. Публичные тексты сохраняют правило объяснять смысл
без notebook/function/parser жаргона.

## 4. Внешние checkout и backup архивы

`rosstat-docs` (`bb84eaab…`) и `rosstat-analysis` (`06ef84ee…`): **130 документных
путей**, **82 точные копии main**, **48 отличающихся исторических версий**,
уникального отсутствующего в main документного пути в проверенной области нет.
Сохранены обе версии SHA и diff SHA. Область: README/AGENTS/CONTEXT, docs текстовые
документы/схемы и `.cursor/rules`; это не рецензия всего кода checkout.

Содержательная дельта прочитана с сохранением старых оснований: старые counts,
Caddy/runtime, Redis DB0/DB1, ручная viewModeFamilies, forecasts only-new-points,
Yahoo commodities и отсутствие позднего OAuth не переносить в current state.
Июльские traffic/capacity targets — намерения; smoke и URL submission —
датированный факт проверки/подачи, не current live state и не search inclusion.
Новая точка входа — AGENTS/knowledge-workflow; прежний AGENTS сохраняется
побайтово в source-documents и recipes. Generated index/map JSON сопоставлены
как артефакты структуры, не прочитаны как новые владельческие решения.

В `rosstat-wip-snapshots` и `rosstat-branch-backups` разобраны **17 внешних
предметов**: manifests/RESTORE/BRANCH_AUDIT, все непустые текстовые patches и
документные tar members; package/member SHA сохранены. Git bundle проверен
как сохранённый контейнер истории, его весь pack не заявляется прочитанным.
Runtime code members/generated AST отделены от project documentation.

World patch содержит national-first/provider gates, source labels, map GB↔UK,
listing/fold и старые visibility thresholds. Current source уже имеет часть
этого механизма; архивный статус «pending» не означает отсутствие всей функции.
Сегодня `eurostat_country_visibility.py` допускает national core при одном
fresh non-Eurostat ряде; historical patch требовал пять/allowlist и иной freshness.
Current retitle допускает все Eurostat, несмотря на старый/оставшийся curated
docstring. Archived `_concept_members` расположен не в текущем owner module.
Этот diff не инструкция применить patch и не доказательство production migration.

Quicklinks V3 acceptance plan/coverage/data-notes прочитаны целиком и сверены
с fixture/schema; **49 уникальных архивных изображений** просмотрены на двух
контактных листах. Сохранены требования null≠0, выбранный period, CPI compound,
stock/flow, M2 непересекающиеся компоненты, units/SAAR, отсутствие произвольных
«95%» labels, mobile/RU/EN и разделение card/article/OG композиции. **21 сентября
визуальное направление отклонено владельцем**; позже одобренный дизайн от
24 сентября — отдельное решение. В архиве не приняты browser QA и live probes,
если их исходный план говорит «не завершено»/SSH255/HTTP000.

## 5. Переписки, изображения и решения владельца

### Дополнение: Analytics OS plan и editorial criteria

Полностью прочитан linked `analytics-os_71a51ec5.plan-L1-L921-0.md`
(920 строк; exact SHA в JSON). Frontmatter всех 14 todos имеет `pending`, но
это исторический план: он не является текущей матрицей выполнения.
Его protected Analytics API, ingestion/warehouse, MCP, first-party collector,
связь SEO/queries/deploys и action gateway имеют действующие источники в
`backend/app/api/analytics.py`, `action_policy.py`, `yandex_*`,
`mcp/forecast-analytics-mcp`, [API inventory](../analytics_api_inventory/README.md),
ADR-0009/0010 и contracts. Существование реализации отдельных частей не означает
выполнение каждого предложенного endpoint и live integration.

В plan API completeness — endpoint-by-endpoint storage/MCP/safety/fixtures и
smoke, а не наличие пяти названий доменов. Current inventory прямо разделяет
implemented/partial и activation; `yandex_webmaster_client.py` содержит
17 async API methods с отдельными policy gates для writes, а не весь целевой
Webmaster каталог. Целевые Data Import, Webvisor replay, CRM и расходы не
объявлены внедрёнными этим чтением. Public replay в plan помечен non-API gap.

Сверены важные поздние решения: ADR-0009 оставляет собственное behavior сырьё
без удаления (`behavior_raw_retention_days=0`), при этом config отдельно задаёт
analytics/raw-log defaults 180/90 — это разные populations. ADR-0010 уже ввёл
ClickHouse как производную копию Postgres, единые marts и server session слой;
старое «CH отдельной будущей фазой» не current отсутствие CH. Action policy
проверяет allowlist, deny, live-write setting и approval; API apply сохраняет
audit и требует approval token. Плановый autonomous low-risk rollout не
подтверждён этим чтением как включённое production поведение.

Все три cached editorial prompts прочитаны целиком: initial/recheck отсекают
microspam/NUTS duplicates; поздний `seo_reopen/SEO_CRITERIA.md` разрешает полезные
ниши, headline slices и уникальный NUTS. Это история редакторского выбора;
технические row gates и current national-first остаются самостоятельными.
Фраза «ожидаем больше yes» не заменяет доказательство качества каждого ряда.

Остальные четыре существенных linked плана переданы root для полного чтения
ops/backend; их exact paths/SHA и handoff status сохраняются в JSON. Они не
исключены как незначимые. Четыре April9 raw chat exports — исследовательские
запросы и assistant рекомендации; owner sections имеют отдельные SHA, но
рекомендации не повышены до current approval. `uploads/ru-0.md` — внешний
Yandex ID legal snapshot, не решение владельца об архитектуре.

Просканированы все **1 373 Cursor JSONL** в обнаруженной проектной области:
**7 807 user messages**, **4 219 уникальных** после нормализации,
**3 588 повторов**. Семь ошибок парсинга — пустые первые строки; непустых
повреждённых JSON records не найдено. Есть hash/line anchors, отдельно scope
top-level и subagent. Full-text отбор дал 1 924 FE кандидата (1 127 top-level,
797 subagent); дополнительно прочитана выборка кратких policy сообщений.

Top-level запись тоже может быть delegated task или вставленным ответом агента.
Такие тексты, tool quotes и инструкции из архивов не становятся действующей
директивой. Owner-relayed remarks руководителя обозначены отдельно от прямого
запроса владельца. Raw private conversations не копируются в Git.

В JSON приведены нейтральные source-linked решения и действующий canonical
маршрут: официальные источники/максимальная история; единицы и actual cadence;
hero/card/detail parity; прогноз по конкретному mode/frequency; generic monthly
и отдельные CPI/PPI/housing; weekly CPI без произвольного forecast; полный поиск;
RU/EN hosts; весь canonical sitemap; сбор поисков/Telegram outbox; разделение
визитов/просмотров/сессий; scoped release и видимая приёмка. Поздние решения
заменяют старые просьбы о homepage map, forum, языковом autodetect и составе ticker.
Сами исторические планы/предложения не означают выполненный продукт или очередь
на автоматическую реализацию.

Все **709 доступных linked PNG/JPG путей** дедуплицированы в **680 SHA**;
15 контактных листов действительно просмотрены. Это исторические FE UI/data/SEO/
analytics и примеси других задач. Три рукописных требования просмотрены также
в оригинальном масштабе: `image-13c678e4…`, `image-50cdc089…`, `image-8ab3dfa7…`.
Они показывают намерения по navigation/rank/units/registration/homepage/ticker,
а не автоматически действующий acceptance checklist. Thumbnail classification
не подтверждает мелкий текст всех 680 originals или текущую работу сайта.

## 6. PDF, Word, аудио, raw statistical books

PDF обработаны root в отдельном
[PDF-досье](pdf-material-acceptance-2026-09-30.md): FE cards/screens — полный текст
и все 94 страницы действительно визуально просмотрены; paired manifest QA
parsed, не rerun. Три посторонних PDF — title/text relevance scan, без заявления
full-body FE review. Exact source/report SHA и ограничения находятся в обоих JSON.

Два доступных TXT «На правки 13» прочитаны полностью: partial chunk и более
полный transcript. Последний содержит предложения о portal/comments, сравнение
месячных/годовых рядов, equal temporal ticks, region↔macro links, annual region
YoY, map custom metric/zoom/watermark, сохранение состояния и аналитические цели.
Это производный текст, без новой идентификации говорящих/синхронизации с видео.
Числа 85/489/960k и заявления о deployment в речи — исторические заявления.
Поздний current каталог и readiness имеют отдельное основание.

Root отдельно прочитал `/Users/iprofi/Downloads/Минская улица 2.m4a`
(164.8s, 1 412 058 bytes, SHA `5e3f1422e7e7b2d7380056253ce5029efd5878c582d6d1b0945338edd688c195`):
локальная source transcription содержит посторонний личный разговор, без FE
требований. [Audio reconciliation](audio-source-reconciliation-2026-09-30.md)
сохраняет границу: старое имя/ссылка `e4580183…:1526` на производный hero/view
transcript не доказывает тождество версии сегодняшнего аудио. Исторический
derivative сохраняется самостоятельным источником; аудиотекст не копируется.
`Новая запись 82 (копия).m4a` доступна, но источник только
«транскрибируй», FE relevance не установлена; один VOICE reel — внешний пример.

Все найденные DOCX/MOV ссылки отсутствуют, включая исходники правок и
`НА ПРАВКИ 21.mov`; cabinet/video доступны только через датированные производные
документы. По названию, metadata или чужому «просмотрено» новое source-read не дано.

**17 RAR** и связанные **7 ZIP** — статистические исходники региональных
изданий: member layout XLSX/DOCX/DOC/PDF/вложенный RAR, подтверждённый parser
references в `scripts/regional/parse_pril_2025.py`, `backfill_word.py`,
`backfill_pril_2022_2023.py` и data_sources. Это raw data, не пропущенная
архитектурная документация FE. Member-list чтение не объявлено проверкой всех
статистических ячеек/страниц, текущей БД или правомерности её покрытия.

## 7. Оставшееся неизвестное и передача

- Audio filename/старый derivative не удалось связать тождеством версии;
  отсутствующие MOV/DOCX и кабинет не восстановлены.
- Непрочитанные целиком linked исторические планы/экспорты чатов и отдельные
  служебные skill файлы перечислены в JSON честно; они не повышены по filename.
  Проверены их linkage/relevance и content scan; этот проход не объявляет новую
  полную ручную рецензию всех экспортированных assistant сообщений.
- Workbook endpoints/все экономические значения, notebook replay/input hashes,
  raw RAR statistical contents и restore Git bundle не приняты этим проходом.
- Original image мелкий текст вне трёх выбранных notes, private non-FE обсуждения
  и assistant/tool transcripts не интерпретированы полностью.
- Чужие untracked `assets/` сохранены вне main; исходные частные материалы и
  локальные intermediates `.artifacts/` не предлагаются в Git.

Root получает отдельные exact SHA assertions, внешний status delta и manual
reader/doc review proposal. Общий ledger/manifest и итоговая K01–K12 matrix
обновляются их владельцем. Последующее source изменение требует нового SHA
и соответствующей delta review; старое свидетельство не исчезает.

**Проверки:** source SHA before/after для всех XLSX/IPYNB; все XML cells/relationships;
edge fixture (shared strings/formulas, booleans/errors, hidden state, comments,
hyperlinks, defined name); notebook JSON/code/output/image parsing; exact file/
archive/member/image hashes; body/diff чтение и визуальный просмотр выше.
Полный test suite, app runtime, production calls, commit/push/deploy не выполнялись.
