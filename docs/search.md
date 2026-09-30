# Поиск Forecast Economy

**Состояние 30.09.2026:** локальная новая реализация поверх существующих
каталогов и фактов. Выпуск и production acceptance фиксируются отдельно.
Основной документ подсистемы; решение — [ADR-0016](adr/0016-federated-public-search.md),
исторический спрос и границы выгрузки — [аудит истории](research/search-history-2026-09-30.md),
выбор методов — [исследование](research/search-methods-2026-09-30.md).

## Намерение, кандидат и область

Поисковое намерение содержит текст, экономическое понятие, явную страну или
регион и поддерживаемый период. Кандидат — доступная публичная территория
либо конкретный экономический ряд с `key`, частотой, единицей и готовым путём.
Разные срезы могут вести на один canonical с различным режимом; нельзя
склеивать их только по URL и терять выбранное представление.

Глобальная палитра открывает страницы из всех четырёх контуров данных.
Локальные поля ранжируют предоставленный им допустимый набор: выбор страны
для сравнения сохраняет сопоставимость, калькулятор — свой набор стран,
конструктор виджета — listed российские ряды. Поле таблицы ищет только среди
уже загруженных наблюдений. Общая нормализация не расширяет права или
покрытие конкретного инструмента.

## Глобальный API

`GET /api/v1/search?q=...&limit=...` публичен и только читает БД.
`q`: 1–256 символов; `limit`: 1–100, по умолчанию 50. Локаль берётся из
действующего API locale-контракта; браузер передаёт `X-FE-Locale` через `api.js`.
Пустая нормализованная строка возвращает пустой результат; отсутствие `q`,
слишком длинный текст или неверный limit дают FastAPI 422.

```json
{
  "results": [{
    "key": "ru:cpi", "kind": "russia", "code": "cpi",
    "name": "...", "country_slug": "russia",
    "frequency": "monthly", "unit": "...",
    "path": "/russia/indicator/cpi", "navigation": "spa", "score": 1000
  }],
  "total": 1, "has_more": false, "version": "federated-v1",
  "intent": {"countries": [], "regions": [], "year": null, "month": null}
}
```

Пример показывает структуру, а не утверждает имя, единицу или score живого
`cpi`. `total` — число возвращённых строк, **не** число всех совпадений.
`has_more=true` также означает усечение промежуточного набора кандидатов;
пагинации полного результата в этом контракте нет. Поля рядов/территорий
различаются: `code`, `region_slug`, `region_name`, `country_name`, `category`,
`frequency`, `unit`, `navigation` могут отсутствовать у соответствующего kind.
`name_ru`/`name_en` сохраняют доступные имена; `name` предназначено для UI.
У global market assets из общего `Indicator` поле `country_slug` сохраняет
контекст хранения/явного запроса; `country_name` показывает зарегистрированного
эмитента или «Мировой рынок». Это исключение registry, а не российская
экономическая география актива; canonical path и key сохраняются.

Kind: `country`, `region`, `subnational_region`, `russia`, `world`,
`region_indicator`, `subnational_indicator`. Для неподдержанного запроса
возвращается 200 с `results=[]` и `reason`: `unsupported_query`,
`unsupported_period`, `ambiguous_geography` либо `no_coverage`. Исправленная
раскладка может сопровождаться `corrected_query`. Ошибка транспорта/SQL
отличается от завершённой пустой выдачи.

Producer: [api/search.py](../backend/app/api/search.py) →
[search.py](../backend/app/services/search.py) → существующие модели и
`site_paths`/[search_paths.py](../backend/app/services/search_paths.py).
Адаптер путей использует действующие family/card/merge identities и ranking
canonical resolvers. Новых таблиц, миграций, jobs, серверного cache результатов
поиска или внешних модельных запросов нет. Старый `/world/search`
сохраняется для совместимости; глобальная палитра использует новый endpoint.

## Покрытие и доступность

| Контур | Источники и условия кандидата | Навигация / граница |
|---|---|---|
| Страна | Активная `WorldCountry` плюс Россия; у страны есть соответствующий доступный факт | Country-first профиль; Россия отдельно от world |
| Общий `Indicator` контур | Активный ряд с конечным фактом; listed и unlisted физические ряды, российские и действующие рыночные assets | `russia_search_path`: family/mode и валютное исключение сохраняются; data plane/URL не подменяет экономическую географию asset |
| Мир | `WorldIndicator` активной страны с конечным ненулевым фактом; listed и data-backed hidden slices | Country-first карточка; `world_search_paths` пакетно повторяет действующие card/frequency/merge правила; hidden допускаются в SPA, document periods требуют listed |
| Регион России | `Region.kind` = region/district с годовым или месячным конечным фактом | Субъект/округ; РФ и агрегаты-остатки не выдаются отдельными региональными сущностями |
| Региональный показатель России | Listed `RegionIndicator` × выбранная территория с фактом требуемой annual/monthly частоты до LIMIT | Без явной частоты обычная карточка предпочитает месячный слой; explicit year требует годового факта и не заменяется месячными точками |
| Субнациональные территории/показатели | Только страны действующего `country_has_subnational`; listed определения и конечный факт нужной территории | Действующий country × region × indicator путь; отсутствующие страны не создаются |

Явная география, факты, период и поддерживаемая частота ограничивают набор
**до** SQL limit. При запросе
`CPI USA` российский `cpi` не становится заменой отсутствующего американского
ряда. Все содержательные группы обязательны; неизвестное уточнение не
выбрасывается ради совпадения по популярному слову.

Рыночные assets из общего `Indicator` контура имеют узкие действующие
исключения географии: registry `COUNTRY_MARKET_INDICATOR_CODES` связывает
США с DXY (`usd-index`) и US10Y (`ust-10y`) и их materialized siblings.
Явное намерение USD/RUB вместе с США допускает соответствующее валютное
семейство. Это не разрешает любой российский показатель при запросе США;
код/понятие всё равно обязательны. Storage kind/key остаётся `russia`/`ru:*`,
country label отражает economic issuer, path строится действующим helper.
Основание — [global_market_indicators.py](../backend/app/data/global_market_indicators.py)
и `_russia` поискового сервиса, без переноса рядов между хранилищами.

`по годам`/annual, `по кварталам`/quarterly и `по месяцам`/monthly задают
частоту, `уровень`/level, `год к году`, `к прошлому периоду`, `средняя`
задают существующее представление. Общий `Indicator` контур использует
реальные materialized family modes: один код может реализовать annual YoY
и period-on-period, выбранная группа сохраняется в destination. World
`level` означает исходную сохранённую меру, включая процент безработицы
или ставку; это не обязательная единица «индекс» и не новый derived.
YoY/period-on-period/average world распознаются только по имеющейся мере/
метаданным. Противоречивые frequency qualifiers дают `unsupported_query`.

Год 1000–2999 и месяц `YYYY-MM`/название месяца с годом распознаются отдельно
от понятия. `2015=100` распознаётся как база индекса, не запрос года.
Несколько лет, день, конкретный квартальный период (`Q1 2024`), относительная дата и месяц без года дают
`unsupported_period`. Годовые/квартальные ряды не превращаются в месячные.
Для периода используется существующий document URL; если canonical с
`?mode=` нельзя сохранить в period-контракте, такой кандидат пропускается.
Hidden world row с фактами может быть доступен в SPA/API, но не выдаётся
как document period: действующий standalone SSR требует listed. Отсутствие
такой ссылки возвращает пустоту, не путь с отброшенным mode/другим срезом.
Месячные period URL регионов России и субнациональных регионов этой версией
не поддерживаются. Поиск не синтезирует новую частоту или новые данные.

Матрица представлений остаётся источником доступных family/variant/mode,
а не перечнем искусственных поисковых документов. Проверка должна включать
точные коды, hidden siblings, единицы, частоты, виды территории, оба языка,
отсутствующие факты и недоступные периоды. Наличие тестового сценария не
доказывает полный охват всех возможных сочетаний матрицы.

## Методы и границы ранжирования

[search_intent.py](../backend/app/services/search_intent.py) нормализует
Unicode NFKC, регистр, пробелы и `ё/е`, выделяет токены, географические
алиасы и ограниченный словарь эквивалентных понятий. Альтернативы одной
группы соединены OR, содержательные группы — AND. МРОТ и средняя зарплата,
депозитная и ключевая ставки — разные понятия. Раскладка исправляется только
при распознавании известной географии/понятия; опечатки ограничены одной
операцией вставки/удаления/замены/соседней перестановки и длиной токена.

Ранжирование детерминированно: точный код/имя выше имени, метаданных,
префикса и опечатки. Каталожные headline identities могут получить явный
bonus; это не популярность, вычисленная по кликам. World SQL использует
escaped ILIKE и PostgreSQL word similarity для допустимых длинных токенов.
Промежуточный budget = `min(500, max(100, limit*4))` для больших контуров;
финальная сортировка не является exhaustive ranking всего world-каталога.
При равном score действует стабильный key и локализованный приоритет
Россия/международный контур; без явного региона равные regional instances
идут после национальных кандидатов.

`search_paths.world_search_paths` разрешает текущую ranked порцию одной
metadata SELECT для sibling/merge групп вместо per-result resolver-запросов;
availability территорий также проверяется пакетами. Сравнение с
`resolve_world_frequency_sibling` закреплено отдельной регрессией.
`test_search_query_count_is_bounded` устанавливает budget ≤12 SQL SELECT
для fixtures `CPI Germany` (limit=100) и `Russia`. Это регрессионный критерий
этих сценариев, не универсальная гарантия count/latency любого запроса.

[searchSynonyms.js](../frontend/src/lib/searchSynonyms.js) даёт локальным
полям единый `filterSearchOptions`: точный код/имя, эквивалентные понятия,
токены, префиксы, ограниченная русская морфология и typo/layout fallback.
Он сохраняет исходные объекты, stable ties и supplied eligibility pool;
его веса и бюджет отличаются от серверного retrieval. Контракт понимания
общий, один идентичный числовой score между сервером и браузером не обещан.

Обученной ML-модели здесь нет. BM25/TF-IDF, learned ranking и embeddings —
исследованные варианты, а не заявленные механизмы текущего кода. История
содержит слабые click labels без полного exposure/релевантности; обучение
требует ручных judgments, независимого holdout и hard gates географии,
частоты и варианта. Подробности — в двух исследованиях выше.

## Все обнаруженные поисковые поверхности

| Поле / consumer | Набор / механизм | Context аналитики |
|---|---|---|
| Navbar desktop/mobile, Home hero/workbench, category/currencies triggers | Одна глобальная палитра → `/search` | global |
| WorldCountry | Каталог выбранной страны и допустимых family/variant cards → `filterSearchOptions` | world-country-indicators |
| RegionsHome: территории / метрика карты | Текущие территории / полный региональный metric catalog → общий matcher | regions-list / map-metric |
| RegionProfile | Sections показателей текущего региона → общий matcher | region-profile |
| WorldRegionsHome: территории / метрика карты | Текущий country region hub / его metrics → общий matcher | world-regions-hub / world-map-metric |
| WorldRegionProfile | Sections текущей субнациональной территории → общий matcher | world-region-profile |
| ComparePage: macro, страна, регион, показатель, world concept и world region | Supplied compatible/unselected groups, общий matcher и bounded world compare adapter | compare-macro, compare-country, compare-region, compare-region-indicator, compare-world-concept, compare-world-region, compare-world-region-indicator; возможен compare-combo |
| Home map / WorldRating: WorldConceptPicker | Доступные concept options → общий matcher | world-concept-picker |
| CountryComparePicker | Доказанные comparable страны → world compare matcher | world-chart-countries |
| CalcCountryPicker | Страны текущего калькулятора → world compare matcher | calc-country |
| EmbedBuilder | Listed российские ряды → общий matcher | embed-builder |
| DataTable на разных карточках | Только загруженные точки → `tableRowMatches` | table_search, отдельное событие |

Calendar, BI, account/login и статические страницы не получают новый
catalog filter; где смонтирован SPA Navbar, доступна глобальная палитра.
Чистые SSR document-страницы без SPA не имеют этой React-палитры. Старый
`world-countries` context в docstring сам по себе не доказывает живое поле.

## Состояния UI, клавиатура и таблицы

[useGlobalSearch.js](../frontend/src/lib/useGlobalSearch.js) применяет debounce
200 мс, query key по версии клиента/локали/строке/limit, AbortSignal,
staleTime 60 секунд, gcTime 5 минут и один retry. Во время нового запроса
палитра скрывает старые строки и отличает loading, error с retry и loaded
empty. Историческая нулевая выдача не выводится из pending состояния.

Только один видимый trigger принимает Cmd/Ctrl+K или `/`. Диалог удерживает
фокус/прокрутку страницы, возвращает прежний фокус, поддерживает стрелки,
Enter и Escape; composition/229 не выбирает строку и не закрывает IME.
Highlight ограничен новым размером результата. Вторичная строка показывает
географию, частоту и единицу; при одинаковых именах также code среза.
Переход разрешён только по относительному пути без `//` и обратной косой
черты; period destination открывается document navigation.

[tableSearch.js](../frontend/src/lib/tableSearch.js) сопоставляет видимую
дату, ISO-дату, quarterly `YYYY-QN`, raw/formatted значение и значение с
единицей. NFKC и десятичная запятая/точка, пробелы тысячных групп позволяют
найти скопированное отображаемое число. Это буквальный фильтр строк, без
синонимов экономических понятий или запроса новых фактов. Debounce 250 мс;
UI и `table_search.results` используют один predicate. Видимая страница
ограничена новым числом строк при замене входных данных.

## Телеметрия и история

Глобальный loaded query ≥2 символов после 900 мс пишет `search_query`:
bounded `q` до 256, `results`, `context=global`, version, interaction_id,
все возвращённые `keys` (до 100), returned_count и has_more. Returned/rendered
keys не доказывают viewport impression каждой строки или её relevance. Select добавляет
code/kind-country-region/path/position, abandon — последний count, включая
`null` при pending/error. Новый interaction_id создаётся при открытии
диалога; повтор того же q внутри открытия дедуплицируется.

Локальные `useSearchTracking` пока сохраняют 900 мс, minLen=2 и q до 60;
DataTable сохраняет отдельный `table_search{query,results}`. Общего
interaction/exposure-контракта всех локальных полей пока нет. Изменения
каждой буквы, удаления и вставки не записываются. `behavior.js` намеренно
не снимает текст input/textarea/contenteditable; новая typing capture
в эту версию не добавлялась. First-party отправка и consent-границы —
[инвентарь](analytics_api_inventory/frontend_instrumentation.md).

Read-only экспорт охватил все удержанные PG поисковые строки и связанный
контекст, CH копию и все удержанные nginx security rotations. Проанализированы
919 технических сессий и подробно отобраны/просмотрены 150 реальных путей
с положительным свидетельством человеческого использования. Raw архив и
псевдонимные идентификаторы лежат в игнорируемом `analytics/search-audit/2026-09-30/`;
публичный [отчёт](research/search-history-2026-09-30.md) содержит агрегаты,
критерии и ограничения. Это не восстановление всех клавиш за всю историю.

## Проверка и следующий выпуск

API intent/retrieval, shared matcher, table predicate и компонентные сценарии
проверяются соответствующими `test_search_federated.py`,
`test_regional_search_metadata.py`, `searchSynonyms.test.js`,
`worldCompareSearch.test.js`, `tableSearch.test.js`, `useGlobalSearch.test.jsx`
и компонентными tests. Fixtures и [225 synthetic сценариев](research/search-matrix-2026-09-30.json)
отличать от 150 наблюдавшихся реальных путей и browser acceptance.
Backend регрессии дополнительно проверяют batch canonical parity, annual/
monthly fact gates, materialized modes, native rate level, asset issuer
exceptions и отказ hidden period destination. Само наличие теста не
объявляет успешный final run: результаты фиксируются по финальному evidence.

**Датированный API replay 30.09:** неизменённый корпус expected canonical
paths дал **197/201**, HTTP errors **0**, p50 **490 мс**, p95 **1 276 мс**
при двух одновременных запросах к локальному API на восстановленной PG.
Это replay запросов, не 201 browser journey или production latency.
Исходный результат — локальный `analytics/search-audit/2026-09-30/api-evaluation.json`;
итоговое свидетельство и browser границы — в
[протоколе](research/search-acceptance-2026-09-30.md).

Четыре несовпадения expected path оставлены в строгом счёте: native
`cn-industrial-production`, `kr-cpi-all`, `kr-unemployment-rate`,
`kr-gdp-real` отсутствуют в данном снимке БД. Три дают корректный
`no_coverage`; Korean CPI возвращает доступную альтернативу
`kr-prc_ipc_g20-i15` (monthly, 368 ненулевых фактов). Эта проверка доступности
объясняет отклонения, не заменяет исходные expected targets и не повышает
strict score. Отсутствие native ряда требует отдельной проверки ingest/
источника; поиск его не создаёт.

Финальные результаты команд, браузера и локальной PostgreSQL относятся
к конкретному снимку кода и сохраняются в [backlog](backlog.md#search-v2-2026-09-30).
Перед выпуском нужны утверждённый SHA, оба языка, mobile/desktop, все
обнаруженные поля, wrong-geography/variant/frequency empty cases, переходы
SPA/document и latency/resource budget на разрешённом окружении. Полная
production приёмка и causal uplift текущим наличием тестов не установлены.
