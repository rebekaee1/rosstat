# ADR-0006 — Indicator card unification: view modes vs variants vs derived listings

- **Status:** Accepted
- **Date:** 2026-05-22
- **Last verified:** 2026-05-22 (звонок «всё доделать»).
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
2. **PPI family** — `ppi`, `ppi-yoy`, `ppi-annual`. Кандидат на семью [Индекс, YoY%, Annual] аналогично housing.
3. **CPI family** — частично уже unified через legacy `CpiViewModePicker.jsx` (внутри отдельная логика mom/qoq/annual/weekly/index). Стоит переехать на `viewModeFamilies` для консистентности, но это пересекается с inflation-weekly спецификой.
4. **Retail trade / consumption** — `retail-trade`, `retail-trade-yoy`, `retail-trade-monthly` — кандидаты на семью.
5. **Banking volumes** — `consumer-credit`, `business-credit`, `deposits-individual`, `deposits-business`, `external-debt`, `mortgage-volume` — может потребоваться рефакторинг категорий + view-modes.

Следующий agent, когда возьмётся за расширение — должен использовать чеклист из `AGENTS.md::Шаг 4` и регистрировать новые семьи в `viewModeFamilies.js`.

---

## Связь с другими ADR

- **ADR-0001** (derived engine shape) — фундамент: derived = pure op + spec. Это ADR (0006) добавляет ось «как derived представляется пользователю».
- **ADR-0002** (bulk_upsert идемпотентность) — критично для view-mode pattern: при пересчёте derived (когда меняется представление) bulk_upsert не должен затирать данные пустотой.
- **ADR-0003** (SSR via backend) — view-mode переключение происходит **на клиенте** через `?mode=…`, без перезагрузки SSR. SEO-canonical остаётся на родителе.

---

## Subsequent additions

(Раздел резервируется для эволюционных дополнений к этому решению. Не редактировать body «как если бы решение было таким».)
