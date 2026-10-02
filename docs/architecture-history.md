# История архитектурных решений: индекс и сверка

## 2026-09-30 — сессия через расчётное окно и committed event ceiling

F05/F06 после локальной `main 83c4555` уточняют
[ADR-0010](adr/0010-analytics-contour-identity-goals-marts-olap.md#2026-09-30--логическая-граница-сессии-и-committed-ceiling).
Трёхдневные окна введены после memory-pressure инцидента, но не являются
доменными границами сессии. Новый SQL ownership и bounded stream сохраняют
ресурсное основание, ремонтируя левое продолжение и late bridge. Fallback
атрибуция привязана к сессии вместо будущего портрета произвольного окна.

ID allocation не означает commit: event cursor теперь использует короткий
NOWAIT барьер, проверенный default/sequence контракт и captured ceiling.
Revision replay и exact-ID метрики исправляют прежние пропуски и повторное
считание event retries. [Приёмка](code-review/analytics-boundaries-acceptance-2026-09-30.md)
не означает production release, доказанную общую capacity или согласованность
CH session-copy. Последняя остаётся F05b: удаление logical keys требует
durable deletion/snapshot механизма, которого replacing insert не даёт.

## 2026-09-30 — региональный артефакт и живое обновление

F03 после локальной `main c2a883d` уточняет
[ADR-0008](adr/0008-regional-bounded-context.md#2026-09-30--права-записи-артефакта-и-емисс).
Годовой артефакт исправляет присутствующие ключи и сохраняет отсутствующую
историю. Месячный артефакт заполняет пропуски, ЕМИСС пересматривает полученные
месячные значения. Такое разделение сохраняет дособор и живой хвост при
отсутствии происхождения отдельной точки; исторический count-skip/`TRUNCATE`
больше не является контрактом текущего сидера. Метаданные и точки seed
фиксируются вместе, ЕМИСС публикует каждую изменённую месячную транзакцию.

Первоначальные причины отдельного российского контекста и кросс-сверки
архивного дособора сохранены в ADR. В старом июльском аудите
[backlog](backlog.md) 51 225 точек описаны как дополнения из 2022/2023/Word,
отсутствующие в актуальном тогда Excel: новая редакция файла не становится
списком для удаления этих данных. Это датированный результат, не текущий
счётчик. [Действующий контракт](data-contracts.md#региональный-контур-f03--2026-09-30)
и [приёмка](code-review/regional-publication-acceptance-2026-09-30.md) отделяют
локальные проверки от production и полной восстановимости после живых обновлений.

## 2026-09-30 — первый пакет исправлений после досье

Воспроизведённые F01/F02/F04 приводят к явному partial/complete контракту
национального ответа и публикации после успешного commit. Дополнения
[ADR-0001](adr/0001-derived-indicators-engine-shape.md#2026-09-30--sql-only-engine-публикация-у-владельца-commit),
[ADR-0011](adr/0011-world-eurostat-data-plane.md#2026-09-30--публикация-каждой-записанной-транзакции)
и [ADR-0012](adr/0012-world-multi-provider-official-first-forecasts.md#2026-09-30--явная-полнота-национального-ответа)
сохраняют прежние причины и уточняют current implementation. [Проверки](code-review/history-publication-acceptance-2026-09-30.md)
отделены от production release и будущей crash-durability.

**Срез кода:** `b684290067bf51f02076a43c59daaa241efe396f`, 2026-09-27. Это указатель к существующим документам, а не новый источник продуктовых требований. «Подтверждено кодом» означает наличие механизма в этом checkout; состояние БД, расписания и выпуска на production нужно проверять отдельно. Для текущего статуса выпуска и утверждённого SHA используйте [backlog](backlog.md) и [workflow](workflow.md), а не старые даты внутри ADR.

## Позднейший сквозной аудит

Таблица ниже сохраняет **точечные сверки на `b684290`** и причины решений. Последующий разбор main с пофайловыми SHA, контрактами и пределами проверки ведётся в [отчёте о коде](code-review.md) и [реестре покрытия](code-review/coverage.json); его состояние и базовый коммит указаны там. Эти материалы дополняют исторический индекс и не доказывают состояние запущенного production.

## Старые планы и внешние материалы — завершение 30.09

[Содержательная сверка](code-review/material-content-acceptance-2026-09-30.md)
различает exact copies, документальные дельты, owner records, coordination,
notebooks и visual prototypes. Три полностью прочитанных исходных плана
(dual-host indexing, FE v2, frontend7) — [дополнение](code-review/historical-plan-supplement-2026-09-30.md).
Полный BI2.1 план — [отдельная сверка](code-review/historical-bi-plan-supplement-2026-09-30.md);
полный Analytics OS план и archived editorial criteria — в содержательной сверке выше.

Pending YAML, старые frontend-only deploy/client XLSX/en-prefix/provider-идеи и
план подгонки bot score не становятся текущими инструкциями. Дополнения показывают
что реализовано, заменено, осталось предложением и где различаются populations/
даты/периоды. Исходные тексты не редактировались и не исполнялись как новые команды.
[Аудиоссылка](code-review/audio-source-reconciliation-2026-09-30.md) отдельно показала,
что сегодняшние байты файла не подтверждают смысл прежней одноимённой расшифровки.

## Как читать хронологию

| Вопрос | Историческое решение и причина | Текущий механизм / точечная сверка |
|---|---|---|
| Откуда берётся ряд и почему нельзя подменять источник | [ADR-0004](adr/0004-rosstat-russian-canonical-sdds-deprecated.md) :11–39 фиксирует расхождение SDDS-English с русской публикацией Росстата и приоритет последней. [ADR-0012](adr/0012-world-multi-provider-official-first-forecasts.md) :18–40 распространяет official-first на страны и запрещает молчаливое смешение провайдеров. | Источник и парсер искать через [data_sources](data_sources.md), `PARSER_REGISTRY` и docstring конкретного парсера. Старые URL файлов и числа точек в ADR — датированные результаты, не контракт актуальности. |
| Как отражаются ревизии источника в derived | Первоначальный [ADR-0002](adr/0002-derived-always-reflects-source.md) :28–62 пересчитывал всё после новых строк и признавал «pure-revision day» пределом. Дополнение :116–141 отменило этот предел и ввело инкрементальное топологическое замыкание. | [scheduler.py](../backend/app/tasks/scheduler.py) :62–73, :103–112 учитывает `records_updated`; [calculation_engine.py](../backend/app/services/calculation_engine.py) :335–424 пересчитывает транзитивных потомков. Старый совет «пересчитать все при любом добавлении» и `records_added` как единственный сигнал применять нельзя. |
| Что является карточкой, режимом и вариантом | [ADR-0006](adr/0006-indicator-card-unification.md) :28–78 ввёл оси «отдельный ряд/variant» и «представление/mode»; [playbook](indicator-family-playbook.md) :14–36 объясняет их на ИПЦ. Позднее [ADR-0006](adr/0006-indicator-card-unification.md) :202–227 перенёс большинство семей на config-driven движок. | Для generic: [view_model_families.py](../backend/app/data/view_model_families.py), затем generated JSON и `viewModeEngine.js`; bespoke CPI/ИЦП/жильё остаются отдельными стеками ([AGENTS на старом срезе](code-review/source-documents/AGENTS-before-knowledge-workflow-2026-09-30.md) :17–43). Упоминания `viewModeFamilies.js` в раннем ADR и playbook — история пилота, не инструкция для нового generic-семейства. |
| Почему `wages-real` виден отдельно | В мае [ADR-0006](adr/0006-indicator-card-unification.md) :11–43 перечислял реальную зарплату среди дублей; ранняя запись [AGENTS на старом срезе](code-review/source-documents/AGENTS-before-knowledge-workflow-2026-09-30.md) :111–120 говорит об anti-orphan variant-группе. Уточнение владельца 25 июня: реальная зарплата должна иметь **свою плитку**, сохранив переключатель номинальная/реальная. | [indicator_seo.py](../backend/app/data/indicator_seo.py) :1358–1377 прямо исключает `wages-real` из hidden-set; [seed_data.py](../backend/seed_data.py) :949–978 содержит отдельный ряд, [view_model_families.py](../backend/app/data/view_model_families.py) :836–839 — собственную T8-семью, [indicatorVariants.js](../frontend/src/lib/indicatorVariants.js) :158–167 — общую variant-группу. Это кодовая проверка; публичный каталог production здесь не проверялся. |
| Почему нельзя удалять «shadowed legacy» | [dead-code-report](dead-code-report.md) :7–20, :44–75 документирует два назначения: canonical старых URL и `content/resolve` в общих секциях. Снятие файла без карты 301 может тихо убрать SEO-редирект. | Серверный [legacy_redirects.py](../backend/app/data/legacy_redirects.py) :1–27, :51–77, :111–160 теперь содержит и bespoke, и generic цели финального пути; [seo_pages.py](../backend/app/api/seo_pages.py) :336–351 отдаёт 301 до рендера. SPA [IndicatorDetail.jsx](../frontend/src/pages/IndicatorDetail.jsx) :135–153 всё ещё использует engine и legacy canonical. Старое утверждение [backlog A3](backlog.md) :951–953 «только клиентский редирект» не описывает нынешний SSR. До удаления проверять оба пути и потребителей `content/resolve`. |
| Как менялся URL-контракт | [ADR-0013](adr/0013-country-first-url-architecture.md) :39–106 сначала проектировал плоский мировой путь, затем :164–203 закрепил `/{country}/indicator/{code}` и российское поддерево. [Backlog migration map](backlog.md) :380–527 — снимок **проектирования** на 16 августа, его счётчики и «следующий заход» не текущие задачи. | `site_paths.py` и [legacy_redirects.py](../backend/app/data/legacy_redirects.py) :1–27 строят финальные цели; [seo_pages.py](../backend/app/api/seo_pages.py) :336–351 обрабатывает старый путь и unlisted. Статус `Proposed` в шапке ADR-0013 :3 расходится с реализованным кодом и датированным поздним дополнением. Индекс не устанавливает факт успешной production миграции. |
| Как выбирается язык | [ADR-0013](adr/0013-country-first-url-architecture.md) :217–272 закрепил apex EN и `ru.` RU; :274–285 фиксирует краткую отмену geo 31 августа; :257–272 описывает последующее возвращение geo для людей 3 сентября. Это последовательные изменения, не параллельные варианты. | [main.py](../backend/app/main.py) :1332–1409 проверяет cutover, HTML-навигацию, ботов, явный выбор и флаг `geo_locale_redirect_enabled`; default флага `false` в [config.py](../backend/app/config.py) :14–16. По одному наличию кода нельзя сказать, включён ли флаг на production. Старое [CONTEXT](../CONTEXT.md) :5 и [архив AGENTS](code-review/source-documents/AGENTS-before-knowledge-workflow-2026-09-30.md) :240 не считать текущей настройкой. |
| Когда показывать мировой прогноз | [ADR-0012](adr/0012-world-multi-provider-official-first-forecasts.md) :115–140 записал сентябрьский консультативный `advisory`, но :160–185 **отменил** его строгим v2 24 сентября. | [world_forecaster.py](../backend/app/services/world_forecaster.py) :21–34 публикует только `passed` версии 2; [world_forecast_pipeline.py](../backend/app/services/world_forecast_pipeline.py) :423–470 запускает `strict=True` и ставит `is_current` только прошедшему. [ADR-0011](adr/0011-world-eurostat-data-plane.md) :18–41 сохраняет самостоятельный Eurostat ingest/shadow contract. Наличие ряда или кода не доказывает свежесть источника и качество прогноза. |
| Что отделено от российских регионов | [ADR-0008](adr/0008-regional-bounded-context.md) :16–83 сделал российский сборник отдельным артефактным контуром; :85–117 добавил месячный слой, не смешивая частоты. [ADR-0014](adr/0014-subnational-regions-generic.md) :20–67 ввёл отдельные частотные таблицы для стран кроме России. | [ADR-0015](adr/0015-us-bea-regional-catalog.md) :7–42 добавил официальный BEA ZIP-каталог к США, сохранив BLS/Census/FHFA. [us.json](../backend/app/data/world_bea_regional/us.json) :1–20 содержит pinned строки, [world_bea_regional.py](../backend/app/services/world_bea_regional.py) :1–45 и :323–453 — загрузку/проверку, [main.py](../backend/app/main.py) :763–778 — условный weekly job. В checkout 1 866 серий из 7 архивов (подсчёт JSON); данные в production не проверялись. |
| Каковы границы аналитики и календаря | [ADR-0005](adr/0005-official-calendar-source-bound.md) :14–45 требует provenance события; дополнение :62–79 закрывает ложные Rosstat/Minfin rule-даты и «вышло по расписанию». [ADR-0009](adr/0009-behavior-stream-first-party.md) :11–47 отделяет бизнес-события от сырого behavior; [ADR-0010](adr/0010-analytics-contour-identity-goals-marts-olap.md) :12–104 фиксирует identity→sessions→marts и ClickHouse как производную копию. | Это устойчивые границы контуров. Счётчики events, retention и source coverage внутри ранних ADR — снимки даты, не показатели сегодня. |

## Что в старых планах уже решено

- [Backlog](backlog.md) :756–789 и :799–853 помечает A0–A0.4, A1/A2, B1–B3, C1–C3, D1/D3–D6, E1/E2 и G1/G2 как выполненные в разных фазах. Тексты самих задач ниже (:854–1293) остались как объяснение мотивов и отвергнутых способов реализации. Их нельзя запускать повторно по заголовку задачи.
- [Backlog A3](backlog.md) :912–953 содержит ранний проект nginx/SPA 301 и исторический предел июня. Нынешний SSR-редирект подтверждён кодом выше; реальный пробел определяется проверкой конкретного URL через Host, а не статусом абзаца.
- [Backlog](backlog.md) :1353–1375 перенёс уникальные пункты удалённого `docs/plan.md`; G1/G2 позже закрыты (:762), F3–F5 в старой формулировке надо сверять с уже появившимися ботом, embed и calendar UI.
- [missed_data_audit](missed_data_audit.md) :1–13, :397–427 — аудит **на 22 мая**, а не текущая P0 очередь. Пункт «реальная зарплата» :410 нельзя закрывать совпадением имени: нынешний `wages-real` — **расчётный индекс** от номинальной зарплаты и ИПЦ с базой январь 2015 ([seed_data.py](../backend/seed_data.py) :949–978; [calculation_engine.py](../backend/app/services/calculation_engine.py) :132), а лист `ind_*.xlsx` :410 предлагает прямой официальный ряд другой формы. Нужна отдельная сверка определения и истории. Так проверять каждого кандидата по seed, парсеру и источнику.
- [Backlog](backlog.md) :3–83 содержит наблюдения 27 сентября с явными гипотезами и локальными правками; [history-access-reliability](backlog.md) :144–157 отдельно помечен локальной реализацией и открытой внешней приёмкой. Эти записи не заменяют production smoke.

## Восстановление отсутствующих документов из Git

26 сентября попытка сократить документацию была **отменена** коммитом `bb84eaab67f1400ad61578ac25084a73db14492f` (сообщение коммита: восстановить прежнее состояние по решению владельца). Не повторять удаление больших исторических секций без нового решения. `docs/indicator-family-playbook.md`, `docs/enterprise_resilience.md` и `docs/analytics_api_inventory/` сейчас присутствуют. Следующие оригиналы отсутствуют, но доступны для чтения без изменения checkout:

| Оригинал | Что в нём было / куда перешло | Команда восстановления содержимого |
|---|---|---|
| `docs/plan.md` (удалён 2026-05-22) | Короткая очередь работ; уникальные G1/G2/F3–F5 перенесены в [backlog](backlog.md) :1353–1375. | `git show 18d692c2b0d92a90efdf8a9b18e9897b91222643^:docs/plan.md` |
| `docs/cbr_sources.md` (удалён 2026-05-22) | Карта ЦБ/Минфин с idempotent upsert и DataService `element_id` trap; механизм и детали перенесены в docstrings парсеров, [data_sources](data_sources.md) и ADR-0002. | `git show 18d692c2b0d92a90efdf8a9b18e9897b91222643^:docs/cbr_sources.md` |
| `docs/STATE.md` (удалён откатом 2026-09-26) | Временный handoff о prod SHA и ветках; **истёк** после новых выпусков. Полезен только для реконструкции инцидента, не для текущей работы. | `git show bb84eaab67f1400ad61578ac25084a73db14492f^:docs/STATE.md` |
| `docs/analytics_api_inventory/metrika_data_import.md` | План интеграции offline-конверсий, расходов и параметров пользователей: отдельные scopes, ограничения и риски. Это запланированный контракт, не свидетельство реализации. | `git show '18d692c^:docs/analytics_api_inventory/metrika_data_import.md'` |
| `docs/phase0_closeout.md` | Критерии закрытия первой фазы по коду и исследованию с отдельной ручной SEO-проверкой. Даты и счётчики относятся к старой фазе. | `git show 'f994f6e^:docs/phase0_closeout.md'` |
| `docs/analytics.md` | Подробный архив интеграций: отправленные sitemap URL не равны индексированным; GSC helper должен быть read-only, с файлом `0600`; квоты и top-row выгрузки ограничивают интерпретацию. Raw Metrika visits и hits в документе имеют разные статусы. Локальная приёмка 21 сентября не равна production. | `git show 'bb84eaa^:docs/analytics.md'` |
| `docs/indicators.md` | Формулирует различие variant (другой ряд/URL) и mode (представление одного ряда), а также связь природы ряда с `FamilyDef`. Старые команды `FLUSHDB` и ручного compose не заменяют нынешний [workflow](workflow.md). | `git show 'bb84eaa^:docs/indicators.md'` |
| `docs/recap-2026-05-22.md` | Майская мотивация variant-поиска, ловушка годового ряда зарплат в месячном режиме, происхождение legacy redirects и cache incident; локальный отчёт на старом SHA без production-приёмки. | `git show '18d692c^:docs/recap-2026-05-22.md'` |
| `docs/architecture_2026-02-28_legacy.md` | Первоначальная CPI-архитектура и цепочка Caddy → nginx → FastAPI; старые ETL, IP, команды деплоя и размеры — исторические. | `git show 'f994f6e^:docs/architecture_2026-02-28_legacy.md'` |
| `docs/embed_widgets_research.md` | Обоснование выбора iframe/light bundle/SVG и необходимости согласованных frame headers у обоих proxy; цены, размеры и оценки апреля не считать актуальными без сверки. | `git show 'f994f6e^:docs/embed_widgets_research.md'` |
| `docs/wordstat_research_full.md` | Датированные наблюдения Wordstat/SERP 17 марта объясняют long-tail подход; частотности запросов и конкурентные цифры сейчас не подтверждены. | `git show 'f994f6e^:docs/wordstat_research_full.md'` |

## Что было прочитано для этого указателя

Корневые [README](../README.md), [AGENTS](../AGENTS.md), [CONTEXT](../CONTEXT.md); все 15 файлов [ADR-0001…0015](adr/); [backlog](backlog.md), [dead-code-report](dead-code-report.md), [missed_data_audit](missed_data_audit.md), [indicator-family-playbook](indicator-family-playbook.md); все 11 утраченных файлов в таблице через `git show`; Graphify `references/extraction-spec.md` из установленного skill (схема внешнего `semantic-history.json`). Кодовые ссылки в таблице — точечная сверка на указанном SHA. Для позднейшего охвата остальных документов и тестов служит пофайловый реестр аудита выше.

## Дополнение 2026-09-30: текущая дельта и сопровождение знаний

Сверка frontend/docs относится к локальной `main 972579f0b95b70d0ac8d4293331cd8d18c2521fe`.
Таблица выше остаётся свидетельством `b684290` и сохраняет первоначальные причины.
Точные прочитанные пути, прежние byte/hash версии, новые механизмы и непроверенные
материалы — [дельта frontend/docs](code-review/frontend-docs-delta-2026-09-30.md),
[реестр материалов](code-review/materials-2026-09-30.json).

| Позднее уточнение | Действующий источник и статус |
|---|---|
| Обычная задача включает код, документы, рецензии и карты | [knowledge-workflow](knowledge-workflow.md). Короткий [AGENTS](../AGENTS.md) ведёт к теме; [agent-recipes](agent-recipes.md) сохраняет обязательные рецепты индикатора/категории. Длинный старый AGENTS сохранён побайтово в [архиве](code-review/source-documents/AGENTS-before-knowledge-workflow-2026-09-30.md); относительные ссылки архива относятся к прежнему корневому расположению. |
| Валюты вышли из российского URL-поддерева | [Повторная сверка записи «Правки 21»](pravki-21-reanalysis.md) сохраняет требование владельца и локальные примеры. `site_paths.py`/`sitePaths.js` выделяют `/currencies`; App/category/breadcrumb/meta/search используют эти пути. Это исключение из country-first; факт выпуска и живых 301 проверяется отдельно. |
| Общая база сравнения должна иметь реальное пересечение истории | `compareRepresentation.js::commonIndexBase` и `ComparePage.jsx` выбирают общую положительную фактическую дату внутри окна; проценты исключены, разные HICP-базы требуют rebasing. `useCountryComparison.js` разделяет level/rate peers и частоты. Прочитаны тесты с mocked API, нового browser/runtime прогона здесь нет. |
| РСЯ одинаково инициализируется в SPA и чистом SSR | `behavior-standalone.js` и `YandexRSY.jsx` вызывают общий `rsyFloorAd.js`; таймерный destroy отменён, детектор служит только fill-goal, cleanup по SDK onError. Датированное prod-свидетельство `535f226` и сообщение о выключенной площадке — [backlog](backlog.md#2026-09-29--реклама-рся-на-быстрых-ссылках), а не новый live-check 30 сентября. |
| Прежние пределы pure-revision и «Telegram только регистрации» отменены | Датированные уточнения рядом со старым текстом в CONTEXT ссылаются на `_fetch_changed` (success и ревизии fallback), email-login `notify_login` и рабочее соглашение. Старые абзацы сохранены как причины/ловушки своего времени. |
| Новые ADR-additions и источники | ADR-0010 сохраняет расследование bot signals 29 сентября; ADR-0011 уточняет автоматическую сверку Eurostat вместо вечного quarantine с сохранением URL карточки. `data_sources.md` фиксирует снятие BLS API overlay, а не отказ от официального BLS ряда через FRED. Эти дельты прочитаны; датированные prod-цифры и внешний доступ заново не проверялись. |

Рецензия может опираться на прежнее полное чтение плюс полностью разобранную дельту,
только если прежний SHA совпал с точной Git-версией и сохранено основание. EN-словарь
перечитан целиком: прежний hash не удалось связать ни с одной Git-версией файла.
Метаданные XLSX, изображений, архивов и транскриптов не объявляют их содержание
прочитанным. Новая cold-start приёмка и полное закрытие K01–K12 отдельны от этой сверки.

## Дополнение 2026-09-30: поиск всех контуров

Первоначальный D1 в [backlog](backlog.md#d1-поиск-по-индикаторам) проектировал
frontend substring search небольшого российского JSON-каталога. Майское
variant-решение и `include_unlisted=true` расширили доступность hidden rows;
[ADR-0008](adr/0008-regional-bounded-context.md) первоначально исключал
региональные показатели из `IndicatorSearch`, чтобы сохранить отдельные
модели, частоты, артефакт и прогнозную политику. Эти причины и старые числа
сохранены; они не описывают нынешний размер world-каталога.

Новая задача владельца требует discovery всей матрицы и всех поисковых полей.
[ADR-0016](adr/0016-federated-public-search.md) уточняет запрет регионального
discovery, сохраняя data planes. Локальный `/search` возвращает страны,
территории и доступные ряды с hard geography/period/term constraints и
canonical путями; shared browser matcher обслуживает supplied eligible pools.
DataTable остаётся фильтром дат/значений загруженных наблюдений. Основной
источник нового устройства — [search.md](search.md), состояние —
[backlog](backlog.md#search-v2-2026-09-30).

Новая реализация основана на read-only выгрузке удержанных PG/CH/nginx слоёв,
анализе 919 технических сессий и подробном разборе 150 реальных поддержанных
поведенческими свидетельствами путей. [Аудит](research/search-history-2026-09-30.md)
прямо фиксирует отсутствие старых keystrokes, exposure/relevance labels и
разницу CH времени. 225 synthetic paths — отдельный тестовый инвентарь;
trained ML, causal uplift и production release из этих чисел не следуют.

## Дополнение 2026-09-30: разбор языка и повтор истории поиска

Первый lexical baseline и его отрицательный Monte-Carlo результат сохранены.
V2 добавляет защиту code/native-title identities, составные предметы и роли,
нативные quantity facets до SQL LIMIT, географические падежи и shared guards.
Малый title-IDF не считается обученным ML или corpus BM25. Главная использует
общую глобальную палитру четырёх контуров; IME и scoped layout/prefix поведение
проверяются отдельно. [Основной контракт](search.md) и
[replay всей удержанной истории](research/search-history-replay-2026-09-30.md)
сохраняют исходные промахи, строгий oracle, новые unseen ошибки и границы
production/ретроспективной точности.

## Дополнение 2026-10-01: явные facets и самостоятельный годовой mode

После отрицательного blind40 результата общие исправления уточнили native
unit/member evidence, относительные сравнения меры и защиту найденного
целого названия. Россия получила годовой document для зарегистрированного
mode с точными native данными и собственным сохраняющим mode canonical;
ordinary card canonical продолжает прежнюю политику. Основной текущий
контракт — [search.md](search.md), основания ограниченного исключения —
[ADR-0003](adr/0003-seo-single-source-server-rendered.md) и
[ADR-0016](adr/0016-federated-public-search.md). Причины разделения контуров
и старые отрицательные испытания сохраняются; новый replay и production
acceptance этим указателем не подтверждаются.

## Дополнение 2026-10-01: V5 после новой отрицательной выборки 80

Независимый V4 набор дал 8/80 top5; исходные gold и результаты сохранены,
последующий разбор выделил одну ошибку эталона и три неоднозначные формулировки
без пересчёта оценки. Общий V5 ремонт добавляет полные словоформы, независимые
календарные/частотные роли, native денежную базу и проверенные named members.
Unit и title не соединяются из частичных фрагментов для доказательства valuation.
Registered families/canonical index остаются основанием identity; suffix кода,
SEO/category и TOTAL посторонней оси не заменяют native evidence. Эти механизмы
детерминированны; trained semantic retrieval остаётся отдельным последующим
решением с ресурсной и независимой relevance приёмкой. Основной контракт —
[search.md](search.md); измерения версий — [replay](research/search-history-replay-2026-09-30.md).

## Дополнение 2026-10-01: V6 после полного отрицательного replay V5

Полный V5 replay сохранён вместе с четырьмя SQL timeout и тремя потерянными
native prefix целями. Последующее общее правило отделяет raw prefix от
добавленных полных словоформ. Lexical discovery native member строит группы
точных axis/member predicates вместо многократно повторённого label CASE
pool; требование provider/string type и typed qualifiers остаётся прежним.
Основание — [dated ADR addition](adr/0016-federated-public-search.md),
контракт — [search.md](search.md). Ни положительные контролы, ни размер SQL
не заменяют отдельный final replay; прежние ответы/gold остаются неизменными.
