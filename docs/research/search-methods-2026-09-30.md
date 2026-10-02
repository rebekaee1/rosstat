# Методы поиска Forecast Economy — 30 сентября 2026

Статус: исследование baseline и выбор методов; локальная реализация первой
версии описана отдельно в конце документа и в [контракте поиска](../search.md).
Baseline чтения: detached HEAD `05302ff1c4dbe104850116e6206d168ec4fa91d3`.
Этот документ не подтверждает production-поведение, качество новой модели или
полноту выгрузки исторических событий. Примеры ниже синтетические; реальные
пользовательские запросы не отправлялись внешним API.

## Рекомендация

Сначала единый контракт поисковых документов и разбор намерения, затем
лексическое извлечение кандидатов и прозрачное ранжирование. Для первой версии
достаточны имеющийся PostgreSQL, токены, типизированные aliases, Damerau–Levenshtein
и преобразование раскладки. BM25 и локальные multilingual embeddings следует
сравнить на одном отложенном наборе; learned ranker допустим после появления
пригодных оценок релевантности и логов показов. Это инженерный выбор для данного
проекта, а не утверждение об универсальном превосходстве метода.

Приоритет исправления: **покрытие → гео/единица/период → кандидаты → порядок → UX**.
Ранжировщик не восстановит ряд, который отрезали до ранжирования, и не создаст
данные для несуществующего региона, режима или периода.

## Что установлено в baseline коде до новой версии

Следующая таблица и её воспроизведения относятся к исходному `05302ff1`.
Действующий контракт последующих локальных версий — [search.md](../search.md);
исторические причины выбора методов ниже сохраняются.

| Механизм | Фактический контракт | Следствие |
|---|---|---|
| `frontend/src/lib/searchSynonyms.js` | Нормализация регистра, `ё→е`, пробелов; curated aliases; 5 стабильных tiers; fuzzy с одной ошибкой включается только при отсутствии любого substring hit | Один посторонний substring отключает fuzzy для всех оставшихся кандидатов; порядок внутри tier наследует каталог |
| `resolveSynonymTargets` | Собирает все распознанные фразы, включая более короткие пересекающиеся | «ВВП на душу …» может одновременно активировать общий ВВП |
| `expandSearchQuery` | Для точного alias использует только `targets[0]` | `ипц→cpi`; альтернативные `inflation`/`hicp-index` больше не представлены в мировом запросе |
| `IndicatorSearch.jsx` | RU каталог включая unlisted до 600; мир через API до 100; RU и EN меняют порядок целых групп | География задаётся языком группы, а не намерением; сравнимого общего ранга нет |
| `backend/app/api/world.py::search_world` | Цельная `ILIKE '%q%'` по code/name/keywords; listed; сигнал; отдельная страна; кандидаты ограничены по длине кода до финального ранга | Составные слова, страна и год не разбираются; полезный длинный код может не попасть в shortlist |
| Ветка `matched_countries` | Повторно требует совпадение q в code/name/keywords ряда | Чистый запрос по стране не даёт перечисление её показателей, вопреки комментарию о country-only |
| Ответ `search_world` | `total=len(results)` после limit | Это количество возвращённых строк, а не всех совпадений |
| `worldCompareSearch.js` | Подстрока country name/slug/code, отдельные aliases России | Правило отличается от глобального поиска, нет общих aliases географии и раскладки |
| `useSearchTracking.js` | Пауза 900 мс, minLen=2, q до 60 символов, results/context; зависит также от resultsCount | Нет каждого нажатия; одна строка может логироваться повторно после изменения числа результатов |
| Global telemetry, исходный срез до v2 | q до 120 символов; query после 900 мс; select с code/scope/country/position; abandon | Нет явного общего request ID и полного списка показанных результатов; q не является уникальным ключом сессии |

Источники: [исходник синонимов](../../frontend/src/lib/searchSynonyms.js),
[компонент](../../frontend/src/components/IndicatorSearch.jsx),
[world API](../../backend/app/api/world.py), [country matcher](../../frontend/src/lib/worldCompareSearch.js),
[трекинг](../../frontend/src/lib/useSearchTracking.js), [миграция индексов](../../backend/alembic/versions/20260826_world_search_trgm.py).
Рецензии прочитаны в `docs/code-review/reviews.jsonl`; они описывают источник и
не доказывают текущий runtime. ADR-0006 различает listing visibility и
searchability; ADR-0009 прямо фиксирует отсутствие keystroke-сбора.

Прямой запуск baseline `filterSearchIndicators` на синтетическом каталоге дал:

| Запрос | Текущий результат | Требование новой версии |
|---|---|---|
| `мрот` | Средняя заработная плата | МРОТ и средняя зарплата — разные понятия; близкий ряд не должен подменять отсутствующий |
| `Москва зарплата` | Общероссийская зарплата | География обязательна; региональный ряд либо честная пустота |
| `ввп на душу Германия` | Сначала общий ВВП, затем ВВП на душу | Длинный alias «на душу» имеет приоритет; Germany ограничивает кандидатов |
| `инфляция Германия 2024` | Российский CPI | Geo/year сохраняются и проверяются по реальному покрытию |
| `byakzwbz` | Пусто | Раскладка даёт «инфляция»; исходная строка сохраняется, исправление объясняется |

Это воспроизведение чистой функции, а не проверка живой выдачи. Имеющиеся тесты
хорошо защищают несколько aliases, один typo и tiers, но не измеряют полный
customer journey, geo constraints, покрытие периодов или качество всего каталога.

## Один документ, несколько поисковых поверхностей

`SearchDocument` должен описывать конечный публичный объект: тип, стабильный ID,
canonical URL, RU/EN title, aliases/concept/family, страну, регион, единицу,
частоты/режимы/варианты, доступный диапазон дат и признак доступности фактов.
У exact variant и базовой карточки разные намерения, хотя они могут иметь один
canonical путь с параметром mode. Не дублировать каждую дату как миллионы
полнотекстовых документов: хранить реальное покрытие и строить периодный путь
только через существующие helpers и контракты.

Глобальная палитра использует все публичные типы. Локальный country/region/
concept picker передаёт `allowed_types` и scope, затем применяет те же нормализацию
и ранжирование. У каждой поверхности отдельные тексты и действие выбора;
одинаковый движок не превращает селектор сравнения в навигацию.

Документы берутся из российских и мировых реестров, действующего card/variant
resolver и фактического покрытия регионов. «Нет в обычном листинге» не означает
«нет в поиске». В то же время служебные, неактивные и неработающие URL не становятся
публичными от одного наличия строки БД. Zero — допустимый экономический факт;
если действующий публичный контракт намеренно исключает all-zero ряды, это
отдельная политика, а не универсальный тест существования данных.

## Разбор намерения RU + EN

1. Сохранить raw query. Нормализовать Unicode, регистр, пробелы, тире и `ё→е` в
   отдельном поисковом представлении; коды/ISO/валютные пары не терять.
2. Проверить exact ID/code/name до исправления. Генерировать максимум несколько
   вариантов: исходный, смена раскладки RU↔EN, ограниченное исправление опечатки.
   Exact code всегда выигрывает у похожего; краткие ISO/коды нельзя свободно fuzzy.
3. Найти длинные aliases понятий и географии по границам токенов. Пересекающиеся
   фразы разрешать по специфичности: GDP per capita ≠ GDP, МРОТ ≠ средняя зарплата,
   цена жилья ≠ ввод жилья, nominal ≠ real, total ≠ per capita, level ≠ YoY.
4. Извлечь country/region, дату/диапазон, частоту, режим изменения, единицу/валюту.
   Полностью распознанные однозначные ограничения обязательны. Неоднозначность
   «Georgia», «Москва», «ставка» даёт несколько подписанных вариантов, а не скрытый
   выбор одного. Частота и период — отдельные поля: «2024» не означает annual.
5. Остаточные содержательные токены искать с ALL semantics; географические слова
   и валидный период уже обработаны как facets. Для короткого незавершённого слова
   применять prefix, для typo — bounded edit distance. Не выбрасывать неизвестное
   слово ради выдачи популярного, но другого экономического показателя.
6. Проверить facets по фактам до candidate LIMIT. Не создавать запросом
   несуществующие периоды или регионы. Явный неизвестный qualifier даёт пустоту и
   доступные соседние варианты. Без явного qualifier текущая страница и locale —
   только слабые priors, не фильтры.

Это предлагаемая детерминированная грамматика, которую нужно проверить на
аннотированных путях. ML extraction можно сравнить позже; правила и каталог
остаются валидатором любых извлечённых сущностей.

## Методы извлечения и ранжирования

| Метод | Подходит для | Ограничение / требуемые данные | Решение |
|---|---|---|---|
| Field-aware exact/prefix/token + aliases | Коды, короткие запросы, понятия, строгие facets | Требует качественного каталога и явного правила disambiguation | Основа первой версии; детерминированный fallback |
| PostgreSQL FTS (`tsvector`, RU/EN configuration, `ts_rank_cd`) | Словоформы, несколько токенов, веса полей | Стемминг не заменяет aliases/коды; `ts_rank_cd` не BM25 | Сравнить после безопасной подготовки индекса |
| `pg_trgm` / bounded Damerau–Levenshtein | Typo, prefix, похожее написание | Очень короткие строки малоинформативны; fuzzy не даёт смысловой эквивалентности | Отдельный канал кандидатов, не безусловное исправление |
| BM25 / BM25F | Редкие термины, насыщение term frequency, веса полей | Corpus statistics и length normalization нужны на полном актуальном корпусе; templates/SEO шум требуют очистки | Offline baseline против текущих tiers/FTS; не вводить отдельный engine без выигрыша |
| Multilingual bi-encoder | Перефразировка и RU↔EN без общего написания | Локальная модель, document embeddings, versioned text; проверка доменных ошибок и ресурсов | Экспериментальный дополнительный канал после lexical baseline |
| Cross-encoder reranker | Более точная оценка query/document пар | Стоимость каждой пары, задержка на CPU; candidate recall уже должен быть хорошим | Только bounded shortlist и измеренный SLA |
| Linear model / LambdaMART | Обучение весов lexical/semantic/context features | Группы query→документы с graded labels; click bias; удержанный test | После подготовки labels/impressions; 150 путей сами по себе не доказывают train sufficiency |

PostgreSQL поддерживает weighted FTS и cover-density ranking; его функции не
используют глобальную статистику корпуса, поэтому их нельзя называть BM25 или
вероятностью правильности. Индекс GIN предпочтителен для FTS. [PG 16 controls](https://www.postgresql.org/docs/16/textsearch-controls.html),
[PG 16 indexes](https://www.postgresql.org/docs/16/textsearch-indexes.html).

`pg_trgm` обеспечивает similarity/word similarity и индексирование ILIKE;
GIN ускоряет фильтр, но nearest-neighbor `ORDER BY distance LIMIT` относится к
GiST. Шаблон без извлекаемых триграмм может вести к полному сканированию индекса.
Имеющаяся миграция GIN ещё не означает, что fuzzy-операторы уже используются.
[PG 16 pg_trgm](https://www.postgresql.org/docs/16/pgtrgm.html).

BM25 учитывает частоту термина с насыщением, длину документа и inverse document
frequency. BM25F расширяет подход на поля. Для экономического каталога веса title,
concept/aliases и описания нужно валидировать, а не равнять с SEO keywords.
[Robertson & Zaragoza, оригинальная работа](https://www.staff.city.ac.uk/~sbrp622/papers/foundations_bm25_review.pdf).

Первичная схема ранга — lexicographic tuple: выполнение обязательных facets,
exact code/title, exact specific concept/alias, полнота токенов, direct name
match, prefix/fuzzy penalty, затем слабый context prior и стабильный ID. Такой
порядок защищает редкие точные запросы от популярности и metadata noise.
Промежуточные score components сохранять для debugging; не показывать пользователю
«точность 97%» из ненормированной суммы.

Для объединения разных retrieval channels можно сравнить weighted RRF:
`score(d)=Σ w_j/(k+rank_j(d))` для присутствующих в каналах документов.
RRF не требует считать несопоставимые BM25 и cosine оценки одинаковой шкалой;
`k=60` — отправная точка оригинальной работы, не доказанная константа проекта.
Обязательные facets и exact match guard применяются независимо от fusion.
[Cormack, Clarke & Buettcher, SIGIR 2009](https://cormack.uwaterloo.ca/cormacksigir09-rrf.pdf).

Мировые кандидаты должны отбираться индексированными запросами с ограниченным
результатом. LIMIT после нужных facet/lexical условий, плюс oversampling на
обоснованную величину; параметры измерять по Recall, query plans и времени.
Не грузить все мировые ряды в браузер или каждый web worker для одной строки.

## Как учесть ML без выдуманной обученности

BEIR сравнивал методы на разных доменах: BM25 оказался сильным baseline,
а отдельные reranking методы показывали хороший результат с большей вычислительной
стоимостью. Это основание измерять наши данные; его результат не переносится
автоматически на Forecast Economy. [BEIR, оригинальный benchmark](https://arxiv.org/abs/2104.08663).

Для эксперимента подходит семейство Multilingual E5: выбрать small/base после
проверки RU/EN, лицензии и ресурсов, зафиксировать model revision и правила
encoding. Использовать локальную inference для исторических q и публичных метаданных
каталога. Обучение такой модели и измерения в этом исследовании не проводились.
[Авторы E5](https://github.com/microsoft/unilm/blob/master/e5/README.md),
[Multilingual E5 technical report](https://arxiv.org/abs/2402.05672).

Document text должен описывать экономическое понятие и facets без копирования
десятков SEO фраз; дата факта не является semantic text. Нельзя выбирать страну,
валюту или YoY только по cosine similarity. В ANN поиска обязательные фильтры
могут снижать число найденных кандидатов; pgvector отдельно описывает это
поведение и iterative scans. Точность ANN сравнивать с exact vector search.
[pgvector, авторская документация](https://github.com/pgvector/pgvector).

Bi-encoder извлекает кандидатов, cross-encoder оценивает пары query/document
на shortlist. Последний не нужен на каждом keystroke; любой отказ/timeout
возвращает lexical выдачу. [Sentence Transformers retrieve/rerank](https://sbert.net/examples/sentence_transformer/applications/retrieve_rerank/README.html).

LambdaMART — обучаемое деревьями ранжирование; используемые features могут включать
lexical score, alias specificity, typo penalty, exact facets, semantic score и
контекст. Нужна query-grouped разметка, а не мешок популярных строк.
[Burges, Microsoft Research](https://www.microsoft.com/en-us/research/publication/from-ranknet-to-lambdarank-to-lambdamart-an-overview/).

Клики смещены позицией, привычкой к текущей выдаче и видимостью. Без журнала
показов нельзя превращать «не кликнул» в отрицательный label. IPS также требует
обоснованных propensity estimates: нельзя назначить их по предположению.
Исторические click/select события полезны для гипотез и ручной проверки;
доказательство качества — независимая разметка и отложенные метрики.
[Joachims, Swaminathan & Schnabel, WSDM 2017](https://www.cs.cornell.edu/people/tj/publications/joachims_etal_17a.pdf).

## Минимум 150 клиентских путей и оценка качества

Путь: **исходная страница → конкретное поле → последовательность ввода/исправлений
→ состояние выдачи → выбор/закрытие → конечная страница или выбранная сущность →
доступный факт**. Список 150 поисковых строк без этих переходов не является 150
проверенными клиентскими путями. Исторический reconstructed путь, синтетический
сценарий и браузерное наблюдение имеют разные метки evidence.

Первый набор: 15 страт × 10 отдельных путей = 150. Страты выбираются по истории
и действующей матрице; таблица — план, а не отчёт о уже выполненной приёмке.

| Страта | Минимум путей | Что устанавливает эталон |
|---|---:|---|
| Exact code, в том числе скрытый sibling | 10 | Правильный canonical и режим |
| Exact публичное имя RU/EN | 10 | Название не уступает SEO шуму |
| Acronyms и curated aliases | 10 | Синоним ведёт к тому же понятию |
| Словоформы и порядок слов | 10 | Token matching работает вне цельной подстроки |
| Одна/две опечатки по длине слова | 10 | Исправление без подмены короткого кода |
| Ошибочная RU/EN раскладка | 10 | Корректное преобразование и отсутствие ложных исправлений |
| Страна + показатель | 10 | Страна обязательна |
| Только страна / регион | 10 | Entity и каталог без выдуманных рядов |
| Российский регион + показатель | 10 | Региональные факты и конкретная единица |
| Зарубежный субнациональный регион | 10 | Правильная страна/регион, действительное покрытие |
| Год/месяц/диапазон | 10 | Реальная дата и существующий периодный путь |
| Frequency, YoY/MoM, nominal/real | 10 | Правильное представление экономического ряда |
| Currency/unit/per capita | 10 | Сопоставимые единицы без semantic подмены |
| Compare/map/embed/local pickers | 10 | Корректное локальное действие и ограничения поверхности |
| Empty/error/no coverage + клавиатура/мобильный | 10 | Честная пустота, retry и доступное управление |
| **Всего** | **150** | |

Каждый существующий context поля должен иметь хотя бы один путь; оставшиеся
места страты распределять по frequency of use и редким важным случаям. RU/EN,
desktop/mobile, global/local, России/world/regions и успешные/пустые исходы
отмечать ортогонально. Если отдельная поверхность не помещается, расширить набор
сверх 150. Размер 150 — минимальный аудит, не статистическая гарантия ML качества.

Для offline qrels использовать pooled candidates текущего и новых методов плюс
известные хорошие документы вне pool; два независимых прочтения спорных кейсов.
Labels: 3 — точный ответ с facets; 2 — полезная и совместимая альтернатива;
1 — тематически связан, но не удовлетворяет запросу; 0 — нерелевантен или нарушает
явное обязательное ограничение. Для Recall бинарно релевантными считать 2/3;
период/region violations отдельно имеют нулевую терпимость в regression gate.

Основные отчётные метрики:

- `Recall@20/50`: найденные релевантные документы / известные релевантные; точность
  этой оценки ограничена полнотой qrels. Диагностирует candidate retrieval.
- `MRR@10`: средний обратный ранг первого релевантного результата. Удобен для
  навигационного запроса с одним главным ответом.
- `nDCG@10`: ранжирование по graded relevance с discount позиции; считать IDCG
  из того же набора оценок, не объявлять unjudged документы отрицательными.
- `Success@1/5`, доля facet violations, честная пустота для no-coverage, ошибки
  canonical/mode и результата local picker; для unavailable intents retrieval
  Recall не усреднять с обычными запросами.
- End-to-end: доля выполненных задач, переформулировки, abandon после готовой
  выдачи, время до выбора; API p50/p95, input→paint, cold/warm и error rate.

Формулы и смысл ranked retrieval см. [книга авторов IIR](https://nlp.stanford.edu/IR-book/html/htmledition/evaluation-of-ranked-retrieval-results-1.html);
готовые IR evaluator contracts — [Sentence Transformers evaluation](https://sbert.net/docs/package_reference/sentence_transformer/evaluation.html).
Результаты дополнительно публиковать по языку, контексту, домену и сложности,
а не только общей средней: большой российский head не должен скрыть провал world.

Защита от leakage:

1. Разделять train/dev/test по целому поисковому эпизоду/session; похожие
   исправления, дубли строки, переводы и synthetic variants одного seed вместе.
2. Для оценки generalization выделить unseen normalized query/intent families;
   отдельно temporal holdout на поздних событиях. Не смешивать эти две задачи.
3. Aliases, typo dictionaries, популярность и IDF строить из допустимого train
   окна; метаданные каталога привязать к snapshot. Нельзя использовать будущий
   выбранный ряд или dwell как query-time feature.
4. Не тюнить веса/пороги на test; final test открывать после фиксации алгоритма.
   При 150 путях learning curves и доверительные интервалы информативнее
   обещания «точности 99%».
5. Сравнивать старую/новую выдачу на одинаковых путях; paired bootstrap по query
   group/session, с заранее выбранными primary metrics. Пока мало live событий,
   не объявлять статистически доказанный онлайн uplift.

## Что нужно добавить к телеметрии для следующего шага

Для всех разрешённых поисковых полей: `search_episode_id`, `query_revision`,
`context`, route/locale, `request_id`, ready/error state, engine/catalog version,
применённые facets и result IDs/ranks реально показанного shortlist. Select и
abandon связать с эпизодом; loading и stale ответ не являются zero-result search.
Отдельно хранить correction/clear/submit, если нужен разбор набранных вариантов.
Это требует реализации; историю недособранных символов восстановить нельзя.

Исторические события выгружать отдельно от новых synthetic fixtures и labels,
с manifest: таблица/фильтр/границы времени/число строк/hash/версия кода; сохранять
raw и normalized query раздельно. Идентификацию сессий не угадывать по одной строке
q. Выбор режима полного текста конкретных поисковых полей не означает автосбор
всех `input` страницы; текущий generic behavior collector специально не снимает
input text. См. [ADR-0009](../adr/0009-behavior-stream-first-party.md).

## Порядок выполнения и неизвестное

1. Manifest существующих полей + визуальная проверка desktop/mobile RU/EN +
   read-only экспорт фактически хранимых поисковых событий за всё доступное окно.
2. Зафиксировать coverage snapshot и ≥150 путей с gold expected outcomes.
3. Новый общий matcher/intent contract, обязательные qualifiers, корректный
   canonical/variant resolver; убрать доказанные ложные aliases.
4. Indexed world retrieval и общая federation с пагинацией; тесты geo/coverage,
   bounded work, race/stale response, explicit error и local picker behavior.
5. Измерить lexical baseline; сравнить FTS/BM25 и локальный embedding channel.
   Подключать ML только после измеренного улучшения при допустимом времени/памяти.
6. Связная telemetry пригодного качества, независимые labels, затем learned
   reranker и онлайн эксперимент при достаточном числе эпизодов.

Неизвестно в этом исследовании: фактические даты/число/полнота server events,
доля успешных эпизодов, актуальное число searchable публичных документов,
latency/CPU/RAM новых методов и browser acceptance. Эти измерения выполняются
отдельными подзадачами и не заменяются ссылками на исследования.

## Выбранная локальная реализация первой версии

`GET /api/v1/search` с `version=federated-v1` соединяет компактные российские и
региональные каталоги, активные страны и индексированный shortlist мировых рядов.
Сервис не обучает модель, не отправляет запросы во внешний API и не добавляет
новое хранилище. Намерения режима берутся из действующих `FAMILIES`, ссылки —
из `site_paths` и правил canonical resolver. Один физический годовой ряд может
обслуживать YoY и period-on-period: выбранная группа сохраняется в URL.

Прозрачный baseline: exact code даёт 1000, exact title — 900; иначе каждый
обязательный term получает лучший доступный сигнал: полный code 100, token
code 80, name 70, metadata/внутренний code fragment 20, prefix 15, одна edit
ошибка 5. Сумма требует совпадения **всех** terms. Известный публичный headline
и его физические family modes получают 180 в России; мировой national concept
160, curated concept 140. Listed даёт только 2. Это детерминированные веса,
не вероятность и не выученные коэффициенты; они требуют независимого offline
сравнения при следующем изменении. Равный score разрешают тип результата при
отсутствии региона, слабый locale prior и стабильный ключ.

География и факт за нужный период проверяются до LIMIT. Мир сохраняет текущий
nonzero signal gate; региональный конечный ноль остаётся доступным фактом.
Annual/monthly региональное ограничение проверяется по соответствующей таблице
фактов, не по подписи каталога. Недоступная period+mode комбинация и скрытый
мировой ряд без допустимого SSR period destination не получают выдуманной
ссылки. Неоднозначные страны дают явное состояние; USD/JPY отдельно распознаёт
упоминание эмитента доллара внутри конкретной существующей валютной пары.

Мировой shortlist ограничен 500 metadata rows; точные поля/curated identities
попадают до отсечения. Canonical siblings/merges последних ранжированных
кандидатов читаются одним batch-запросом по их dataset groups. Geo entities
проверяют факты по группе, без одного EXISTS-запроса на каждый регион.
Это ограниченный shortlist, а не доказанный exhaustive corpus ranking.
У мировых рыночных активов в общей российской таблице `country_slug` сохраняет
контекст хранения/явного запроса для текущей навигации и telemetry; display
`country_name` показывает зарегистрированного эмитента либо «Мировой рынок».
Это оговорённое исключение поля, а не российская экономическая география актива.

67 hermetic проверок в [test_search_federated.py](../../backend/tests/test_search_federated.py)
прошли локально 30 сентября. Они включают strict geo, отсутствие MROT/deposit
подмен, zero/hidden gates, actual annual/monthly availability, mode paths,
FX issuer distinction, сравнение batch canonical с authoritative resolver и
ограничение числа SQL statements. PostgreSQL replay, reconstructed history и
браузерная приёмка находятся в отдельных артефактах аудита; этот документ не
подменяет их синтетическими тестами и не подтверждает выпуск в production.

## Subsequent implementation: bounded v2, not trained semantic readiness

V2 implements typed bilingual compound subjects/question roles, native-unit and
frequency markers, literal-first code/title parsing and actual-catalogue geo
inflection. Shared guards gate SQL before LIMIT and recheck returned identities.
Candidate-title df is computed once and supplies a small `6*log1p((N+1)/(df+1))`
bonus per strongest term alternative, with a capped semicolon-slice penalty.
Exact scores≥900 are unchanged. This is bounded inverse-frequency evidence,
not corpus BM25/TF-IDF, trained relevance probability or semantic entailment.

The [history replay report](search-history-replay-2026-09-30.md) distinguishes
all retained inputs, nonempty coverage, exact historical click recall and the
manually frozen economic gold. A first unseen120 evaluation failed; broad
grammar/quantity/geo repairs followed, so any later use of120 is development.
The newly sealed80 on source9167af was the separate first generalization
test:22/80top5 despite finite facts. After its failures were read, economic-role,
denominator/currency and ordinary-word parser repairs followed. A replay on
source60ac58 is development; it never replaces that independent negative score
or establishes universal natural-query understanding. No gold/case deletions or post-hoc-equivalent substitutions
raise the frozen primary score. The earlier learned/hybrid alternatives above
remain research candidates; no external inference or model persistence was added.

Continuation 2026-10-01: current v2 global UI telemetry retains q up to256
characters; the old global120/local60 snapshots above describe historical
capture, not the new global limit. No individual keystroke recording was added.

## Последующая реализация 01.10: конечные facets и точный годовой destination

После раскрытия отрицательного blind40 результата 5/40 внесены общие
исправления экономических отношений, physical units и защиты целого native
title span; относительное сравнение задаёт меру/частоту, не произвольную дату.
Eurostat qualifiers требуют реальный member указанной оси до LIMIT и при
проверке результата; отсутствующая ось не выводится из темы или dataset ID.
Russia year+registered-mode использует точный materialized ряд, native SSR
и сохраняющий mode canonical/sitemap контракт. Подробности сосредоточены в
[основном документе](../search.md#методы-и-границы-ранжирования) и
[ADR-0003](../adr/0003-seo-single-source-server-rendered.md).

Это конечная детерминированная грамматика. Старые ML/hybrid предложения и
требования независимых labels остаются исследовательским планом. Завершённый
source60ac58 historical acceptance — 109/110 strict top5 и 2 542/3 664 nonempty;
первичный blind40 не переписывается. На момент этой записи будущий replay
ещё не был завершён; последующий статус V4 приведён ниже.
[Датированный отчёт](search-history-replay-2026-09-30.md)
разделяет эти метрики и development повторы, без заявления о production.

## Последующее состояние 01.10: запечатанный V4 и общий ремонт V5

V4 historical replay source `259cb677` / 51 files завершён полностью:
1 915 main и 736 nginx requests, HTTP/transport errors — 0. Frozen economic
historical110 сохраняет **109/110 strict top5**; retained client occurrences
дали **2 607/3 664 nonempty**, nginx backend q — **725/1 106**. Coverage
не означает semantic correctness всех q, nginx q не всегда равен raw visitor
input. Историческая размеченная часть уже известна разработке.

Отдельный независимый V4 corpus80 сохраняет первичный **8/80 top5**.
Readonly post-outcome review аннотировал 1 invalid semantic gold,
3 underspecified query и 2 preregistered route limits, без adjusted score,
исключений или расширения допустимых физических целей. После чтения этот
набор стал development. Предварительный V5 source `c9668f27` на тех же80
дал **22/80 top5**, 0 HTTP errors; это не новая blind оценка и не итог
финального полного V5 replay. Свидетельства — в
[датированном отчёте](search-history-replay-2026-09-30.md).

Общие V5 правила сохраняют независимые роли: запрошенная observation frequency
и полная поддержанная source-methodology clause; зарегистрированный
terminal `period_last` и промежуточная операция перед темпом; предмет price
и valuation basis ВВП; денежная база `constant/chained 2017 dollars` и
год искомого наблюдения. База подтверждается полной native unit, не числом
в SEO. Свидетельства current/constant prices разделены по title/code labels
и каждому native unit label: `Current transfers` + `USD` не дают новую
valuation, несовместимые units/неизвестная source frequency не отбрасываются.
Native currency/scale/physical denominator не подменяют экономический предмет.

Официальные 20 Eurostat payloads дали 34 общих axis/member witnesses на
17 осях; конечный registry содержит 29 известных осей. Поддержанные named
totals, contract duration, worktime, country of birth, statistical information,
sector и national-account item требуют настоящей строки member на нужной
оси. TOTAL другого поля, numeric JSON, отсутствующая ось и dataset name
не подтверждают роль. ED02 и M_STS получили точные официальные смыслы;
общего AnyTotal или alias по case/native indicator code нет. Эти условия
повторяются в SQL до LIMIT и Python metadata/финальном guard.

Это конечная детерминированная грамматика, типовые словари и небольшой
candidate-title inverse-frequency bonus. Обучения, learned reranker,
embeddings и внешнего model API в реализации нет. Старые ML/hybrid варианты
выше остаются планом сравнения после независимых labels. V5 интегрирован
локально; финальные replay/gates ещё проверяются. Production не изменён,
сильное произвольное понимание новых вопросов этим ремонтом не установлено.
