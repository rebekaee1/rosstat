# ADR-0016 — Федеративное обнаружение публичных данных

- **Status:** Accepted for local implementation; production release separate
- **Date:** 2026-09-30
- **Scope:** глобальный поиск и единый контракт намерения локальных полей
- **Supersedes:** только исключение регионального discovery из `IndicatorSearch`
  в [ADR-0008](0008-regional-bounded-context.md); storage/ETL границы сохраняются
- **Основной документ:** [search.md](../search.md)

## Контекст и основание

Владелец потребовал исправить все варианты поиска с учётом полной матрицы
покрытия, визуального аудита и не менее 150 клиентских путей. Прежняя
глобальная палитра объединяла российский и world indicator search, исключая
страны, регионы России и субнациональные контуры. Локальные поля имели
разные substring rules. Фраза со страной не была единым намерением;
загрузка могла выглядеть как нулевая выдача.

[Исторический аудит](../research/search-history-2026-09-30.md) восстановил
919 технических сессий и подробно рассмотрел 150 путей с human_supported
свидетельством. Это реальные сохранённые последовательности, не доказанная
личность/релевантность. Индивидуальные клавиши до debounce не сохранялись.
Наблюдения обосновывают строгую географию, эквивалентные понятия, typo/layout
и честные loaded/empty состояния; causal выигрыш они не измеряют.

## Решение

1. Один public read-only `/api/v1/search` объединяет discovery поверх
   существующих четырёх data planes. БД, источники, частоты, ETL, forecast
   policy и права регионов/мира сохраняются в своих bounded contexts.
2. Явная география, экономическое понятие и поддерживаемый период —
   ограничения намерения. Все содержательные группы обязательны; популярный
   российский ряд не заменяет запрос конкретной другой страны или МРОТ.
3. Кандидат требует доступного факта своего контура. Конечность проверяется
   явно; world требует ненулевой сигнал по существующему контракту каталога.
   Срезы/частоты/mode разрешаются canonical resolvers, а не выдумываются
   поиском. Unsupported period/ambiguous geography дают честный empty reason.
   Annual regional intent требует годового факта до LIMIT; hidden world
   slice допускается в SPA, но не в document period без listed SSR права.
   Native world level может быть процентной мерой, а не только индексом.
4. Ограниченный детерминированный lexical retrieval — первый локальный
   механизм: нормализация, алиасы, токены, prefix, edit-distance-one,
   контролируемая раскладка, PostgreSQL word similarity. Candidate budgets и
   has_more явны; total не объявляет полный счётчик совпадений.
5. Локальные селекторы получают общий matcher внутри supplied eligible pool;
   таблицы сохраняют отдельный буквальный поиск загруженных дат/значений.
6. Палитра отделяет pending/error/empty, скрывает чужие query hits, сохраняет
   доступную клавиатуру и отправляет bounded query/returned candidates/interaction
   telemetry. Returned keys не являются measured viewport impressions.
   Нового сбора каждого изменения input в этой версии нет.

Destination adapter `search_paths` пакетно читает world sibling/merge
метаданные одной SELECT на ranked порцию и сохраняет family group при
общем annual YoY/pop коде. География рыночных `Indicator` assets следует
действующему issuer registry: DXY/US10Y допускаются с США; это узкое
исключение, не fallback на любой российский ряд. Методы/storage/URL не
меняют экономическую сущность. Подробный контракт — [search.md](../search.md).

## Альтернативы и последствия

Полный перенос всех рядов в российскую модель отвергнут: он нарушает
идентичность/частоты и причины ADR-0008/0011/0014. Загрузка полного world
каталога в Navbar дорого стоит в DOM/сети и не решает fact eligibility.
Серверная федерация оставляет producer/consumer контракты неизменными и
ограничивает извлекаемые метаданные, но query budget может усечь кандидатов
до финального score. Exhaustive ranking и pagination не заявляются.

Обученный ranker/embeddings не выбран без relevance judgments, exposure
и independent holdout. Кликовые события — слабые метки; выбор неправильной
страны может означать исследовательский переход. Методологические варианты
с источниками — [research](../research/search-methods-2026-09-30.md).

Новых миграций/search jobs/storage и внешних model calls нет. Требуются
проверка действующих индексов/планов PostgreSQL и ресурсного бюджета,
RU/EN/mobile/desktop и all-surface приёмка. Статус локальной реализации,
набор выполненных проверок и production gate ведутся в [backlog](../backlog.md#search-v2-2026-09-30).
Сохранённые 225 synthetic paths не являются 225 browser проверками или
реальными пользователями; полный исторический набор клавиш невосстановим.

## Subsequent addition 2026-09-30: v2 and evidence of its limits

Following the frozen Monte-Carlo failure, v2 protects catalogue literals, resolves
compound subjects before typo expansion, and adds bounded RU/EN question roles,
native quantity/frequency facets, catalogue geography inflections and shared
SQL/Python typed measure guards. A small candidate-title inverse-frequency bonus
uses the same ё/е normalization; exact identities still dominate. These are
deterministic methods, not an already trained multilingual model. No migration,
search job, external model call or production resource allocation is introduced.

All homepage entries remain global across four data planes and send raw queries.
IME intermediate input is suppressed; help/status copy is paired RU/EN. Local
selectors retain eligibility and now preserve keyboard punctuation and supported
long native prefixes. API fields remain stable, version is federated-v2; client
cache revision v3 is separate.

The full retained historical replay, independent relevance labels, unmodified
first-pass failures and subsequent unseen80 evaluation are separately reported
in [the dated replay report](../research/search-history-replay-2026-09-30.md).
A high score on clear selected historical queries does not establish arbitrary
question understanding. Empty results may reflect language/retrieval limits even
when facts exist. A future learned semantic channel needs independent relevance
acceptance and the4vCPU resource budget; it is not hidden behind the v2 label.

## Subsequent addition 2026-10-01: typed-role repair and preserved blind evidence

The untouched80 pass on source9167af exposed ordinary-word correction, hyphen
identity, denominator/currency geography and economic-role failures. Its score
remains preserved. The next local source60ac58 uses actual-catalogue code
preflight, bounded long-word correction, exact native denominator matching and
additional count/amount/stock/rate/income-role guards. Hectare area keeps its unit
and is distinguished from per-hectare yield. The inspected80 replay is development;
it cannot be presented as independent generalization after these repairs.
All historical gold/corpus bytes remain fixed; a separate complete acceptance
replay seals this source without replacing the previous full replay.


### 2026-10-01: subsequent general repair after independent40

The next untouched40 pass on60ac58 scored5/40top5 with finite facts for every
target; this negative evidence is retained. General repair separates percent
from percentage points, uses US state producer/native-unit USD evidence,
protects whole native title spans before geography/period parsing, and retains
actual name/code autocomplete separately from control-word typos. Structured
Eurostat qualifiers require the named stored axis/value before LIMIT and during
scoring; missing members and unknown qualifiers remain mandatory. Official
member labels provide semantic evidence, never category/SEO-derived axes.

Russia year+registered-mode now resolves the exact materialized series and
provides a validated query-preserving standalone SSR canonical, reciprocal
locale/graph/year links and native values. Such fact-backed canonicals were designed to
enter the sitemap registry; ordinary card mode canonicals still strip query.
**Status 2026-10-04:** sitemap/robots/Clean-param publication of year-document modes is deferred by the owner and restored to the server behaviour (see ADR-0003 status note).
See [ADR-0003 addition](0003-seo-single-source-server-rendered.md). World year
modes and derived monthly documents remain unsupported. Inspected40/80 replays
are development checks, not replacements for first blind results.

### 2026-10-01: subsequent V5 repair after the independent V4 sample

The untouched V4 sample scored8/80top5. Its later semantic audit found one
invalid gold and three underspecified questions without rewriting the original
score. General V5 rules add complete-word morphology, independent registered
source/output frequencies, terminal end-of-period identity and monetary
constant/chained base-year grammar. Verified Eurostat member evidence remains
exact provider/axis/string-member evidence, including axis-specific totals.

Current/constant valuation is proved within one native title/code or one native
unit label. Partial fragments across fields never manufacture that identity.
Commodity price subject may derive from an actual registered family with a
monetary-per-physical unit; a currency label or code suffix alone is insufficient.
These are finite deterministic rules and bounded pure-token caches, with no
trained model, response/history cache or query-to-answer lookup. Replaying the
inspected80 is development evidence. Source freezes, full retained-history
metrics and remaining language limits are recorded in [the replay report](../research/search-history-replay-2026-09-30.md).

### 2026-10-01: V6 retains native prefixes and groups lexical member predicates

The completed V5 replay retained four statement timeouts and three native
prefix regressions. Its source snapshot, first bodies and unchanged gold stay
sealed. Added complete noun forms must not replace the raw singleton's existing
prefix/fuzzy role; already parsed nominal groups still require complete words.

For lexical native member discovery, a finite static label catalogue now selects
exact axis/member groups and emits one Boolean identity predicate per required
term. Provider, JSON string type and separately typed facets remain mandatory
before LIMIT and in the final scorer. Where measure/display needs label text,
simple CASE evaluates one member expression per axis. This changes SQL shape,
not native identity, storage, query history or the eight-second test timeout.
Plan construction and hermetic controls do not establish live latency; the final
version requires a new full retained-history replay and preregistered sample.
