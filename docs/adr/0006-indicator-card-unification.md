# ADR-0006 — Indicator card unification: view modes vs variants vs derived listings

- **Status:** Accepted
- **Date:** 2026-05-22
- **Last verified:** 2026-06-16 (жильё-цены приведены к оси режимов ИПЦ: топ-группа «К соотв. периоду пред. года» + годовой Г/г `housing-annual-*`; доступность жилья без «Скользящая 12 мес.»; кнопки диапазона графика всегда справа).
- **Part of:** [`AGENTS.md`](../../AGENTS.md), [`CONTEXT.md`](../../CONTEXT.md), [`ADR-0001`](0001-derived-indicators-engine-shape.md), [`ADR-0003`](0003-seo-single-source-server-rendered.md).
- **Контекст:** правки 2026-05-21 (кластер A: «time aggregations & view modes», объединение дублирующих карточек) + звонок 2026-05-22 («всё доделать»).

---

## Контекст

После введения derived-индикаторов (ADR-0001) и SSR через backend (ADR-0003) у нас образовалась ситуация, когда **один пользовательский показатель публикуется через несколько карточек в каталоге**: `exports` + `exports-yoy` + `exports-qoq` + `exports-monthly`, `current-account` + `current-account-yoy`, `wages-nominal` + `wages-real` + `wages-yoy` + `wages-index`, etc.

Это создавало 3 системных проблемы:

1. **UI noise.** Каталог `/category/trade` показывал 11 trade-карточек вместо 4 показателей. Пользователь не понимал, что `exports-yoy` — это «тот же экспорт, другой режим», не отдельный показатель.
2. **SEO дублирование.** Поисковики получали 11 URL для одной семантической пары (экспорт товаров, режим = % YoY) — каннибализация ranking.
3. **Размытие чеклиста.** Когда добавлялся новый индикатор, было неясно: заводить его как отдельную карточку, как derived, как variant — критериев в документации не было.

Параллельно возникли частные паттерны, которые **не укладывались** в существующее «всё — derived»:
- **Negative-capable** indicators (`trade-balance`, `current-account`): `yoy %` от базы, переходящей через ноль, даёт визуальный мусор и тысячи процентов.
- **Daily aggregation** (week/month/quarter/year avg для daily-индикаторов): 28 daily-индикаторов × 4 агрегации = 112 backend derived'ов. Слишком много spec'ов в `DERIVED_SPECS` ради UI-фичи.
- **Variants по срезу** (`credit-rate-corp-{short,1to3y,over3y}`): это **разные ряды**, не разные представления одного ряда — не «режим».

---

## Решение

Формализуется **ось декомпозиции** между «карточкой», «режимом», «вариантом» и «частотой»:

### Один пользовательский показатель = одна карточка в каталоге

В `/category/{slug}` показываем **только** primary-индикаторы. Производные (`*-yoy`, `*-qoq`, `*-real`, `*-index`, etc.) скрываются через `INDICATOR_HIDDEN_FROM_LISTING` в `backend/app/data/indicator_seo.py`.

Скрытие из листинга **не означает** скрытие из API, sitemap, поиска или прямых URL — это только про карточку в каталоге (см. trap «`is_listed` vs VariantGroupPicker» в `CONTEXT.md`).

### Derived = режим, не отдельная карточка

Производные индикаторы (`*-yoy`, `*-qoq`, `*-real`, `*-index`) на странице родителя доступны через `frontend/src/components/ViewModePicker.jsx`, который читает реестр семей `frontend/src/lib/viewModeFamilies.js::VIEW_MODE_FAMILIES`.

Каждая семья — `{parentCode: {label, modes: [{mode, label, code, unit?, transform?}]}}`. Routing в `IndicatorDetail.jsx`: `findViewModeFamily(code)` → `?mode=<mode>` подменяет dataPoints, телеметрию и effective name, **не меняя URL**.

Виртуальные transforms (computed на клиенте, без backend derived):
- `applyMoMTransform(points)` — MoM% для monthly counterparts (`*-monthly`): `(val_t/val_{t-1} − 1) * 100`.
- `applyAggregateTransform(points, granularity)` — bucket-avg для daily-индикаторов: `granularity ∈ {week, month, quarter, year}`.

См. ADR-0001 «Subsequent additions» для деталей.

### Variant = разные ряды по срезу, не режим

Если показатель имеет **варианты по срезу** (срок: `credit-rate-corp-{short,1to3y,over3y}`; рынок: `housing-price-{primary,secondary}`; стадия: `gdp-{nominal,real}`) — это **разные индикаторы со своими рядами**, объединённые в группу через `frontend/src/components/VariantGroupPicker.jsx` (реестр в `lib/indicatorVariants.js`).

Variant ≠ режим:
- variant = выбираешь другой ряд (другой `code` в URL, другие точки).
- режим = тот же ряд, другое представление (без смены URL).

### Negative-capable показатели — только `yoy_abs`

Для индикаторов, чьи значения могут пересекать ноль (`trade-balance`, `current-account`, `budget-deficit`, `*-migration`, `*-natural-growth`), вместо `*-yoy` (%) используем `*-yoy-abs` (разница в единицах источника).

`yoy_abs` — 10-я pure op в `derived_ops.py`, добавленная 2026-05-22. См. ADR-0001 «Subsequent additions».

### Frequency strategy

Несколько случаев:

| Случай | Решение |
|--------|---------|
| Quarterly indicator + monthly counterpart с своим source-парсером (например, `exports` + `exports-monthly`) | Оба индикатора в БД, monthly hidden_from_listing. На странице quarterly — `FrequencySwitcher` (URL-based, отдельная карточка для monthly). Каждый со своим SSR canonical. |
| Daily indicator + желание видеть week/month/quarter/year avg | `applyAggregateTransform` на клиенте. Backend хранит только daily. |
| Quarterly indicator + желание MoM% от monthly counterpart | Виртуальный `transform: 'mom'` в режиме monthly-карточки (`exports-monthly`). |

### Source-depth invariant

При добавлении любого нового индикатора — обязательная проверка глубины истории источника. Если источник публикует с 1991/1995, а seed_data заливает с 2015 — заводим immutable `<name>_historical.py` (как `housing_historical.py`, `refinancing_rate_historical.py`, `wages_historical.py`).

Это **не отдельный паттерн данных**, а часть инварианта «один пользовательский показатель = один максимально полный ряд».

---

## Чеклист «новый индикатор»

См. `AGENTS.md::Шаг 4::Чеклист «новый индикатор»`. 6 проверок:

1. Source-depth invariant.
2. View-mode family оценка (если ряд > 100 точек).
3. Variant decomposition.
4. Negative-capable check.
5. Frequency strategy.
6. Listing visibility ≠ searchability.

---

## Последствия

### Положительные

- **Каталог стал короче и понятнее.** 109 индикаторов → ~80 видимых карточек, остальные 29 — режимы родителей.
- **SEO-сигнал чище.** Один URL = один показатель. Каннибализация ranking устранена.
- **Структурированный чеклист.** Следующий агент / разработчик знает по 6 вопросам, как раскладывать новый показатель.
- **Расширяемость без новых backend derived.** Daily aggregation и MoM% — frontend-only, нагрузка на forecast pipeline не растёт.

### Риски и trade-offs

- **301-редиректы старых URL.** Когда индикатор переходит из категории в режим (`exports-yoy` → hidden), его старый URL `/indicator/exports-yoy` всё ещё работает — это **не** редирект, это прямой доступ. Если хочется направить SEO-weight на родителя — нужны явные 301 в nginx. На 2026-05-22 этого нет: индикаторы доступны напрямую через API и SSR, ranking распределяется естественно.
- **Frontend сложность.** `IndicatorDetail.jsx` теперь содержит логику для viewModeFamilies + dailyAggGranularity + variantGroup + cpiViewMode (legacy). Это 4 параллельных переключателя над графиком. Trap: при добавлении 5-го (например, region) — refactor обязателен.
- **Связность виртуальных transforms с базовым indicator.** `applyMoMTransform` и `applyAggregateTransform` работают над `baseDataPoints`. Если в будущем добавим caching/pagination на API, нужно убедиться, что transform получает полный ряд (не страницу).

### Migration

Реализация шла в 5 phases (2026-05-22):
- **Phase 1** — trade (8 семей: exports, imports, trade-balance, current-account + 4 monthly counterparts).
- **Phase 2** — labour: `wages-nominal` (4 режима: Номинальная/Реальная/YoY%/Index), `unemployment` (3 режима: Monthly/Quarterly/Annual).
- **Phase 3** — housing: `housing-price-{primary,secondary}` (Уровень + YoY%).
- **Phase 4** — rates rename: `credit-rate-corp-short`, `credit-rate-ind-short`, `deposit-rate` переименованы на общие имена; term-split через VariantGroupPicker (не view-mode).
- **Phase 5** — daily aggregation: `applyAggregateTransform` для 8 daily-индикаторов (key-rate, ruonia, usd-rub, eur-rub, cny-rub, gold-price, brent, btc-usd).

---

## Что НЕ покрыто этим ADR (открытые направления)

На момент 2026-05-22 этот ADR покрывает 5 кластеров (trade, labour, housing, rates rename, daily). **Не покрыты пока**:

1. **GDP family** — `gdp-nominal`, `gdp-real`, `gdp-real-yoy`, `gdp-real-qoq`, `gdp-real-annual`, `gdp-nominal-annual`, `gdp-consumption`, `gdp-government`, `gdp-investment`. Сейчас все 8 в листинге. Кандидаты на унификацию: `gdp-real` → семья с режимами [Уровень, YoY%, QoQ%, Annual], `gdp-nominal` → семья с режимами [Уровень, Annual]. Use-компоненты (`gdp-consumption`, `-government`, `-investment`) — это **варианты** по компоненту, нужен `VariantGroupPicker`.
2. **PPI family** — **закрыто (2026-05-30):** `ppi` + `ppiViewMode*` (инфляция за год / к прошлому м/м+г/г / индекс); `ppi-yoy`, `ppi-annual` скрыты, canonical `?mode=`.
3. **CPI family** — **завершённый эталон** (2026-06): variant × двухуровневый `cpiViewMode*` (10 URL-режимов, отдельные derived на режим). Не мигрировать слепо на `viewModeFamilies` — см. [`indicator-family-playbook.md`](../indicator-family-playbook.md).
4. **Retail trade / consumption** — `retail-trade`, `retail-trade-yoy`, `retail-trade-monthly` — кандидаты на семью.
5. **Banking volumes** — `consumer-credit`, `business-credit`, `deposits-individual`, `deposits-business`, `external-debt`, `mortgage-volume` — может потребоваться рефакторинг категорий + view-modes.

Следующий agent, когда возьмётся за расширение — должен использовать чеклист из `AGENTS.md::Шаг 4`, playbook [`indicator-family-playbook.md`](../indicator-family-playbook.md) (фазы A–G) и регистрировать новые семьи в `viewModeFamilies.js` (или CPI-подобный стек, если две оси UI).

---

## Связь с другими ADR

- **ADR-0001** (derived engine shape) — фундамент: derived = pure op + spec. Это ADR (0006) добавляет ось «как derived представляется пользователю».
- **ADR-0002** (bulk_upsert идемпотентность) — критично для view-mode pattern: при пересчёте derived (когда меняется представление) bulk_upsert не должен затирать данные пустотой.
- **ADR-0003** (SSR via backend) — view-mode переключение происходит **на клиенте** через `?mode=…`, без перезагрузки SSR. SEO-canonical остаётся на родителе.

---

## Subsequent additions

### 2026-06-16 — жильё-цены приведены к оси режимов ИПЦ (три топ-группы)

Эталон «к соответствующему периоду пред. года» / «к прошлому периоду» / «индекс» (созвоны 2026-06-06/11 для ИПЦ) распространён на семейство цен на жильё (`housing-price-{primary,secondary}`). До правки у жилья было две топ-группы (`step` + `index`), и квартальная YoY (`housing-yoy-*`) сидела как «Г/г» внутри «К прошлому периоду» — что концептуально неверно (поквартальное сравнение ≠ «год к году»).

**Решение:** структура зеркалит ИПЦ:
- топ-группа `inflation` «К соотв. периоду пред. года» (leaf, дефолт) → квартальная YoY `housing-yoy-*` (каждый квартал к тому же кварталу год назад, 4 точки/год);
- группа `step` «К прошлому периоду» → Кв/Кв (`housing-qoq-*`) + **Г/г по годам** — новый годовой ряд `housing-annual-{primary,secondary}` (`ops.december_to_december` на квартальном индексе уровня: декабрь-к-декабрю, одна точка/год, прогноз `derived_from_source`);
- группа `index` без изменений.

Это **эволюция в рамках принятой оси декомпозиции** (view-mode family, ось «к-соотв-периоду vs к-прошлому-периоду» уже зафиксирована для ИПЦ/ИЦП), а не новая ось — поэтому без отдельного ADR. Годовой Г/г-ряд — тот же класс sibling-derived, что `inflation-annual`/`ppi-annual` (december_to_december). Файлы: `calculation_engine` (+2 spec), `seed_data`, `indicator_seo`, `housingViewMode{Groups,Resolve,Content}.js(x)`, `useIndicatorViewModeData.js`. Параллельно у семейства доступности жилья (`T12`) убран дублирующий режим «Скользящая 12 мес.» (== «средняя за год»); осиротевшие `*-rolling-12m` ряды удалены из БД. Кнопки диапазона графика прижаты вправо (`ml-auto`) при переносе на новую строку. См. `docs/backlog.md::История::2026-06-16`.

### 2026-06-06 — единый резолвер формата периода (view-layer single source)

Истинность представления: формат периода (месяц / квартал / год / день) на оси графика, в таблице данных и в телеметрии должен быть согласован и соответствовать гранулярности отображаемого ряда. До этой правки логика дублировалась: `dateFormatFor` жил отдельными копиями в `IndicatorChartSection.jsx` и `IndicatorDataTableSection.jsx`, а `IndicatorTelemetryGrid.jsx` вообще хардкодил `'full'` («месяц ГГГГ») — из-за чего квартальный/годовой/дневной ряд в карточках телеметрии показывал неверную дату («декабрь 2025» вместо «IV кв. 2025», «май 2024» вместо «2024»).

**Решение:** один `resolveDateFormat({ chartMode, frequency, safeViewMode })` в `frontend/src/lib/format.js` — единственный источник правды. Для generic-семей `chartMode === 'cpi'` (нейтрально) и формат диктует `frequency` resolved-sibling'а (тот же single-source принцип, что и `effectiveIndicator` для unit/name); для legacy CPI/housing/ppi гранулярность диктует режим. Ось графика дополнительно ужимает `'full' → 'short'` на уровне тиков, поэтому общий резолвер для оси безопасен. Это развитие frequency-override решения 2026-05-22 (тот закрыл pill/заголовок, этот — даты во всех трёх местах). +30 format-тестов. Браузер-smoke подтвердил deaths (год), gdp-investment (кв), m2 (мес).

Сопутствующие view-layer правки того же прохода (не меняют ось декомпозиции ADR-0006, поэтому без отдельного ADR): полная выгрузка CSV/Excel через `onFullData` (вся история, не видимое окно); статичные тикеры на мобиле (`LiveTicker` без desktop-gate + синхронизация отступов `App`/`Navbar`); полные variant-лейблы жилья. См. `docs/backlog.md::История::2026-06-06`.

### 2026-05-22 — view-mode family downstream completion

Pilot Phase 1-5 ввёл `viewModeFamilies.js` как реестр семей режимов отображения, но не дотянул правки до всех downstream-компонентов `IndicatorDetail.jsx`. Это привело к двум багам, замеченным на `/indicator/wages-nominal?mode=annual`:

1. **Methodology cross-mode leak.** Функция `getViewModeContent()` в `lib/cpiViewModeContent.jsx` отдавала блок `ANNUAL` (текст про «годовую инфляцию декабрь к декабрю» — стандарт CPI-семейства) для любого `safeViewMode === 'annual'`, без проверки `isPriceCategory`. На странице зарплат пользователь видел чужой текст про инфляцию вместо собственной методологии wages. Аналогично затрагивало `quarterly` и `weekly` ветки.

2. **Frequency metadata leak.** `effectiveIndicator` в `IndicatorDetail.jsx` подменял `unit` и `name` под активный mode, но не `frequency`. Из-за этого pill под breadcrumbs (`IndicatorDetailHeader`) и заголовок графика (`IndicatorChartSection`) читали родительский `frequency` (monthly у wages-nominal), хотя target sibling имел другой ритм (annual у wages-nominal-annual). Пользователь видел «ПОМЕСЯЧНО» в режиме «Годовое (с 1991)».

**Решение:**

- `cpiViewModeContent.jsx::getViewModeContent` — обернуть все CPI-specific ветки в `if (isPriceCategory)`. Не-CPI индикаторы падают в fallback `{ description: indicator.description, methodology: indicator.methodology }`.
- `viewModeFamilies.js` — у каждого не-`level` mode (real sibling) задан явный `frequency`. Виртуальные transforms (`transform: 'mom'`) сохраняют родительскую частоту.
- `viewModeFamilies.js` — добавлен `DAILY_AGG_FREQUENCY` mapping (`week → weekly`, …, `year → annual`) для Phase 5 daily-aggregation.
- `IndicatorDetail.jsx::effectiveIndicator` — подменяет `frequency` из `familyModeMeta.frequency` (для real siblings) или `DAILY_AGG_FREQUENCY[granularity]` (для daily).
- `IndicatorDetailHeader.jsx` — принимает отдельный prop `displayFrequency` (override родительского `indicator.frequency` для пилла, при сохранении родительского `name`/`category` для H1/breadcrumbs).
- `IndicatorDetail.jsx` — передаёт `displayFrequency={effectiveIndicator?.frequency}` в Header.

**Тесты:**
- Новый `frontend/src/lib/cpiViewModeContent.test.js` (9 тестов): для `isPriceCategory=false` функция возвращает fallback на indicator-поля; для `isPriceCategory=true` — CPI-блоки.
- Расширен `viewModeFamilies.test.js`: инвариант «каждый не-level mode имеет `frequency` или `transform`» (anti-leak guard) + проверка `DAILY_AGG_FREQUENCY` mapping.

**Затронутые файлы:**
- `frontend/src/lib/cpiViewModeContent.jsx`
- `frontend/src/lib/viewModeFamilies.js`
- `frontend/src/pages/IndicatorDetail.jsx`
- `frontend/src/components/IndicatorDetailHeader.jsx`
- `frontend/src/lib/cpiViewModeContent.test.js` (новый)
- `frontend/src/lib/viewModeFamilies.test.js`
- `frontend/vitest.config.js` (добавлен `@vitejs/plugin-react` — для JSX в импортируемых модулях).

См. также trap «View-mode family metadata leak» в `CONTEXT.md::Operational invariants and traps`.

### 2026-06-01 — CPI family playbook (reference implementation)

Семейство ИПЦ (`cpi`, `cpi-food`, `cpi-nonfood`, `cpi-services`) доведено до эталона: variant по составу + 10 режимов с **отдельными рядами** (в т.ч. разведение `period-weekly` MTD vs `step-weekly` WoW), контент 40 комбинаций, прогнозы по режимам, SEO без дублирования URL.

Операционный и продуктовый чеклист вынесен в **[`docs/indicator-family-playbook.md`](../indicator-family-playbook.md)** — использовать при работе над GDP/PPI и любыми семьями с variant + view-mode. Для одного нового кода по-прежнему достаточно `AGENTS.md::Шаг 4` (7 пунктов).

### 2026-06-06 — view-mode families на весь каталог (config-driven, mode-gaps=0)

Аудит (`scripts/audit-indicator-unification.py` → `indicator-unification-audit.temp.txt`) показал, что из 75 карточек каталога **37 не имели ни одного временного режима** (только нативный уровень): вся годовая демография и наука, квартальная торговля, часть бизнеса и месячных ставок. Унификация прошлого pilot'а покрывала не весь каталог.

**Решение** — довести единый config-driven движок (`backend/app/data/view_model_families.py`, зеркало `frontend/src/lib/viewModelFamilies.generated.json`) до **каждой** карточки, добавив строки `FamilyDef` и недостающие шаблоны. Новые шаблоны:

- **T2y** — месячные ставки/доли: «На конец периода» + «Средняя» + «Г/г в п.п.» (`yoy_abs`). Унифицирует ставочные карточки с запасами. Коды: mortgage-rate, auto-loan-rate, deposit-rate, credit-rate-corp/ind-short, unemployment.
- **T9s** — квартальный ряд со знаком (сальдо/баланс/нетто): «Уровень» (кв + годовая сумма) + «Г/г в единицах источника». Без Кв/Кв и %-Г/г (база меняет знак). Коды: trade-balance, current-account, fdi-net.
- **T10** — годовые счётные ряды: «Уровень» + «Г/г %». Коды: births, population, working-age-population, pop-over/under-working-age, pensioners, doctoral-students, grad-students, rd-organizations, rd-personnel (+ deaths из прошлого прохода).
- **T10a** — годовые коэффициенты/доли/приросты со знаком: «Уровень» + «Г/г абс.» (‰ / п.п. / тыс. чел.). Коды: birth-rate, death-rate, depreciation-rate, innovation-activity, small-business-innovation, tech-innovation-share, population-natural/total-growth, population-migration.
- **Tidx** — месячный индекс: «Уровень» + «М/м» + «Г/г %». Код: ipi.
- **Tidxq** — квартальный индекс: «Уровень» + «Кв/Кв» + «Г/г %». Код: housing-affordability.

Прежние T6/T9 расширены на месячные потоки бизнеса (construction-work, housing-commissioned, retail-trade) и квартальные положительные потоки (capital-investment, exports, imports, services-exports, services-imports).

**Negative-capable invariant (ADR-0006 чеклист п.5) реализован движком:** для рядов со знаком и ставок/долей режим «Г/г» использует `yoy_abs` (разница в единицах источника / пунктах), а не `yoy_pct`. Единица режима задаётся полем `FamilyDef.yoy_unit`; `seed_data._sibling_texts` для `-yoy` с unit≠«%» печатает абсолютную формулировку.

**Folding (меньше карточек, ось «derived vs карточка»):** официальный `ipi-yoy` (hand-written `DerivedSpec("ipi-yoy", ("ipi",), ops.yoy)`) свёрнут в режим «Г/г» карточки ИПП через `overrides={"yoy":"ipi-yoy"}` + добавление `ipi-yoy` в `INDICATOR_HIDDEN_FROM_LISTING`. Каталог: 75 → 74.

**Frequency-trap фикс:** `housing-affordability` имел `frequency="monthly"` при фактически квартальном ряде (Mar/Jun/Sep/Dec) — исправлено на `quarterly` + шаблон Tidxq.

**Orphan-cleanup discipline (новая trap):** смена шаблона, при которой исчезают режимы (T3→T8 убрал eop у зарплаты/labor-force/employment; Tidx→Tidxq убрал mom у affordability), оставляет sibling-коды старых режимов сиротами в БД. Seed не удаляет строки, а `is_listed` сбрасывается в True для всех → сироты всплывают карточками в каталоге (регрессия «Рынок труда 4→10», 2026-06-06). Лечение: после reseed удалять коды, которых нет в текущем `seed_data.INDICATORS` (data + forecast + indicator). См. trap «View-mode template change orphans» в `CONTEXT.md`.

**Прогнозы (1.1):** новые годовые/квартальные карточки прогнозов НЕ получили (`forecast_steps=0`); месячные ряды сохранили `monthly_auto` из allow-list `MONTHLY_AUTO_FORECAST_CODES`; CPI/ИЦП/ВВП/жильё со своими стратегиями не тронуты. Проверено: population/exports/trade-balance/birth-rate — 0 точек прогноза; m2/ipi — 12.

**Итог:** `mode-gaps=0` по всему каталогу (74 карточки), `check-all.sh` зелёный (40+ конфиг-тестов, vitest, build). Эталоны CPI/ИЦП/housing-price остаются bespoke (T11 + `cpiViewMode*`/`housingViewMode*`).
