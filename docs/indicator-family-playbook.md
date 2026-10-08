# Playbook — семейство индикаторов (продуктовая модель + фазы A–G)

**Last updated:** 2026-09-27 (сверен действующий generic-стек; исторические чеклисты сохранены ниже).
**Part of:** [`AGENTS.md`](../AGENTS.md), [`docs/adr/0006-indicator-card-unification.md`](adr/0006-indicator-card-unification.md), [`.cursor/rules/methodology-language.mdc`](../.cursor/rules/methodology-language.mdc).  
**Эталоны (закрыты):** **ИПЦ** — максимальная сложность (4 среза × 10 режимов). **Жильё** (`housing-price-primary` / `housing-price-secondary`) — эталон «variant + кастомный view-mode» на квартальных данных.

> **Для агента — порядок чтения:** (1) этот файл §«Продуктовая модель» и §0; (2) ADR-0006; (3) `AGENTS.md::Шаг 4` для отдельных кодов. Задача «довести семейство» ≠ «добавить два режима в `viewModeFamilies`». Сначала **источник и оси смысла**, потом код.

**Текущая точка входа:** `python scripts/locate-indicator.py <code>` → `docs/indicator-index.json` (`ui_stack`, `completeness`) → нужный слой. `docs/architecture.md` показывает сквозной путь от URL до данных. Строки §9–10 фиксируют состояние работ на момент их написания и не являются списком файлов для нового семейства.

---

## Продуктовая модель (что копируем с ИПЦ)

ИПЦ — референс **зрелой карточки**, не список из 10 кнопок. Переносим **инварианты**, число режимов и групп — из **модели данных Росстата**.

### Инварианты (обязательны для любого семейства с режимами)

| # | Инвариант | Смысл |
|---|-----------|--------|
| 1 | **Одна витрина — много смыслов** | В каталоге листинговые карточки; derived-режимы скрыты (`INDICATOR_HIDDEN_FROM_LISTING`), доступ через `?mode=` на каноническом URL. |
| 2 | **Две оси не смешивать** | **Variant (срез)** = другой ряд, другой `code`, другой URL. **Режим (`?mode=`)** = другое представление **того же** среза. |
| 3 | **Режим определяет точки** | Для generic ненативный режим указывает на свой source/derived `code`; у legacy бывают явно заданные виртуальные transforms. Нельзя менять только подпись, оставляя прежние точки без преобразования. |
| 4 | **Группы режимов по экономическому смыслу** | Как у ИПЦ: «инфляция за год», «рост за период», «к прошлому периоду», «индекс». **Г/г живёт внутри «к прошлому»**, не отдельной верхней кнопкой. |
| 5 | **Матрица контента** | Тексты = **срез × режим** (ИПЦ 4×10; жильё 2×3). Guard в `*ViewModeContent` — чужие семьи не получают CPI-тексты. |
| 6 | **SEO на каждую листинговую карточку** | Уникальные `seo_blocks` по срезам; режимы не плодят отдельные URL в каталоге. |
| 7 | **Прогноз = активный режим** | `useGenericViewModeData` или bespoke-hook обращается к forecast выбранного кода только если режим forecastable; не подставляет родительский прогноз в другой шкале. |
| 8 | **Variant UX** | Смена среза сохраняет `?mode=`; без прыжка скролла (`isVariantSiblingNavigation`). |

### Оси ИПЦ (зачем эталон)

| Верхняя группа | Смысл | Отдельный ряд? |
|----------------|--------|----------------|
| Инфляция за год | 12 мес., не то же, что г/г | Да |
| Рост за период | Накопление внутри периода (нед/мес/кв/год) | Да |
| К прошлому периоду | Шаг: н/н, м/м, **к/к**, **г/г** | Да |
| Индекс | Уровень (накопленная шкала) | Да |

У каждой **листовой** кнопки свой `?mode=` в URL (не один mode на всю группу — урок бага 2026-05).

### Жильё — второй эталон (квартальный срез)

Та же **архитектура** (`housingViewMode*`, `HousingIndicatorControls`), меньше режимов — **честно по источнику**:

| Группа ИПЦ | У жилья | Примечание |
|------------|---------|------------|
| Инфляция 12 мес. | **Нет** | Не выдумывать ряд |
| Рост за период (нед/мес/…) | **Нет** | Только квартальная частота |
| **К прошлому периоду** | **К/к** + **Г/г** | К/к — официальный прирост в обзоре; г/г — derived от индекса |
| **Индекс** | **Да** | 2010=100, цепочка от к/к |

**Variant:** первичное ↔ вторичное (`indicatorVariants.js`, группа «Рынок жилья»).

**Файлы эталона:** `housingViewModeGroups.js`, `housingViewModeResolve.js`, `housingViewModeContent.jsx`, `HousingIndicatorControls.jsx`; backend: `housing-yoy-*`, `housing-qoq-*`, `housing-price-*`; SEO: `indicator_seo.py` (`INDICATOR_SEO_BLOCKS`).

### Действующие стеки UI

| Стек | Когда | Канонический механизм |
|---------|--------|------|
| **Variant** | Другой экономический срез и другой `code` | `indicatorVariants.js` + `VariantGroupPicker`; ортогонален режимам |
| **Generic view-mode** | Представления одного ряда, включая многоуровневые группы и variant + режимы | `view_model_families.py::FamilyDef` → `scripts/export-view-models.py` → `viewModelFamilies.generated.json` → `viewModeEngine.js` → `GenericIndicatorView` |
| **Bespoke** | Только ИПЦ, жильё и ИЦП (`cpi`/`housing`/`ppi`) | Их `*ViewMode*` и `*IndicatorControls` с отдельными правилами семантики |

Наличие двух осей или многих режимов **само по себе не требует нового bespoke-стека**: generic-движок строит группы из общего конфига. Уровни A/B/C в исторических записях §9–10 описывают этап внедрения, а не сегодняшний выбор реализации. Основание: `backend/app/data/view_model_families.py::_FAMILY_DEFS`, `frontend/src/lib/viewModeEngine.js`, ранний generic-return в `frontend/src/pages/IndicatorDetail.jsx`.

### Продуктовый Definition of Done (перед «готово»)

- [ ] Экономист понимает переключатели **без** объяснения в чате (группы = смысл Росстата).
- [ ] Таблица **режим UI → code БД → частота → derived? → прогноз?** заполнена; нет режима без ряда.
- [ ] Для каждой активной ячейки **срез × режим** — свои description/methodology ([methodology-language](../.cursor/rules/methodology-language.mdc)).
- [ ] Старые URL derived (если были) → редирект/каноникал `parent?mode=…`.
- [ ] Локально прогнан §8; `./scripts/check-all.sh` зелёный; выборочно API data/forecast по спорным режимам.

---

## 0. Выбор паттерна (до кода)

### Decision tree

```
1. Есть несколько независимых рядов по срезу (рынок, состав, срок)?
   → Да: VARIANT (отдельные URL). Нет: пропустить variant.

2. Есть несколько представлений одного среза (YoY, QoQ, уровень, …)?
   → Нет: только фаза A + variant/SEO при необходимости.
   → Да: нужен VIEW-MODE.

3. Есть ли уже bespoke-семья cpi/housing/ppi?
   → Да: править её существующий *ViewMode* стек.
   → Нет: добавить/изменить FamilyDef в view_model_families.py;
     двухуровневые группы, variant + режимы и число режимов не меняют этот выбор.

4. Значения могут быть отрицательными?
   → yoy_abs, не yoy_pct (trade-balance, migration, …)
```

### Таблица паттернов

| Вопрос | Если «да» | Паттерн | Пример |
|--------|-----------|---------|--------|
| Разные ряды по срезу? | Да | **Variant** | ИПЦ ×4; жильё ×2; ставки ×3 |
| Несколько представлений одного ряда? | Да | **View-mode** (`?mode=`) | `exports` + `exports-yoy` |
| Срез × богатые режимы? | Да | **Variant + generic**, кроме трёх существующих bespoke-семей | Зарплата; bespoke: ИПЦ, жильё |
| Отрицательные значения? | Да | **`yoy_abs`** | `trade-balance` |

### Generic-семья: природа ряда → билдер-шаблон (авто-матрица)

Для **generic**-семьи (уровень B/C-lite через config-driven движок) НЕ пишут режимы руками — добавляют одну строку `FamilyDef` в `backend/app/data/view_model_families.py::_FAMILY_DEFS`. Билдер по `template` сам разворачивает полную матрицу {тип × частота}, включая **многоуровневую «Г/г»** (по месяцам/кварталам/годам через `_yoy_modes`). Sibling-ряды авто-seed + авто-скрыты из листинга, тексты авто-генерятся (`seed_data._sibling_texts`), прогноз авто-протягивается для базы monthly/quarterly/annual. Выбор шаблона — по **природе ряда**:

| Природа ряда | Шаблон | Частота | Г/г метод свода | Параметры `FamilyDef` | Примеры |
|---|---|---|---|---|---|
| Ставка/курс/сырьё, дневной | **T1** | daily | last | `abs_delta=True, yoy_unit="п.п."` (ставка) / без abs (курс/сырьё, %) | key-rate, usd-rub, brent |
| Ставка/доля, месячный | **T2y** | monthly | last | `yoy_unit="п.п."` | unemployment, mortgage-rate, deposit-rate |
| Запас (баланс на конец периода) | **T3**/**T4**/**T5** | monthly/quarterly/weekly | last | — (Г/г в %) | m2, external-debt, international-reserves |
| Среднемесячный уровень (обследование) | **T8** | monthly | **avg** | — | wages-nominal, labor-force, employment |
| Поток «за период» | **T6** | monthly | **sum** | — (Г/г в %) | budget-revenue, budget-expenditure |
| Поток со знаком (сальдо/дефицит) | **T7**/**T9s** | monthly/quarterly | **sum** | `yoy_unit=<ед.>` → `yoy_abs` | budget-deficit, current-account |
| ВВП (уровень кв + годовая сумма) | **T9** | quarterly | sum | `overrides=` для легаси-кодов | gdp-nominal, gdp-real |
| Годовой счётный ряд | **T10** | annual | — (Г/г leaf + Индекс) | — | population-total |
| Годовой со знаком/долей | **T10a** | annual | — (Г/г abs leaf) | `yoy_unit="‰"/"%"` | natural-increase-rate |
| Индекс-отношение (безразмерный) | **T12** | monthly | **avg** | — | housing-affordability |

**Правила выбора (критично для правдивости):**
- **Среднее vs на конец**: если «уровень» ряда — это *средняя за период* (зарплата, занятость, индекс-отношение) → **T8/T12** (`avg`), НЕ T3 (`last`): квартальная зарплата = средняя за 3 месяца, а не последний месяц.
- **Поток vs запас**: поток за период суммируется (T6/T7, `sum`); запас берётся на конец (T3–T5, `last`). Г/г наследует тот же метод.
- **Знак**: ряд может быть отрицательным/менять знак (сальдо, дефицит, миграция) → `yoy_abs` (T7/T9s/T10a, `yoy_unit` = единица/п.п.), НЕ `yoy_pct` (база через ноль = тысячи %).
- **Индекс-природа** (ИПЦ/ИЦП/ИПП): если ряд уже индекс (`unit=индекс`) и нужны bespoke-тексты/группы — это **уровень C** (`*ViewMode*`), не generic FamilyDef.
- Прогноз: для дневной/недельной базы агрегаты НЕ прогнозируются (`_FORECAST_PROPAGATE_FREQ` = monthly/quarterly/annual) — это и правило созвона «периодичность < месяца → без прогноза».

После добавления `FamilyDef`: `python3 scripts/export-view-models.py` (зеркало фронта) → пересборка backend → `docker compose exec backend python seed_data.py` → `scripts/build-indicator-index.py` → `./scripts/check-all.sh`. Матрица проверяется в `docs/indicator-index.json::completeness`.

### Прогноз нового source-индикатора: выбор стратегии по природе

Прогноз включается заданием `model_config_json.forecast_strategy` + `forecast_steps>0` в `seed_data.py` И регистрацией кода в соответствующем сете `backend/tests/test_forecast_policy.py` (whitelist `ALL_FORECAST_CODES` — иначе тест `test_only_approved_or_derived_forecasts_are_enabled` падает). После seed — retrain (`backend/scripts/retrain-all-monthly-auto.py --codes <code>`; в контейнере — `/app/scripts/retrain-all-monthly-auto.py`), он каскадно протянет прогноз в derived sibling'ы (`derived_forecast.source_code==base`).

| Природа базового ряда | Стратегия | Когда |
|---|---|---|
| Допущенный политикой месячный source | `monthly_auto` | ADF-автотрансформ + multi-window OLS; включение только для подходящей природы ряда, достаточной истории и whitelist. Частота сама по себе не разрешает прогноз. |
| Квартальный **положительный** трендовый (поток/запас в деньгах) | `generic_quarterly` | exports, imports, external-debt. Переиспользует log-diff методологию семейства ВВП. **Только ряды без смены знака** (log требует >0). |
| Квартальный с собственным notebook'ом руководителя | bespoke (`gdp_*_quarterly`, `housing_quarterly`, `ppi_monthly`) | ВВП, жильё, ИЦП. |
| Индекс цен (CPI-семья) | `cpi_combined` / `approved` | bespoke декомпозиция food/nonfood/services. |
| Недельная инфляция | `generic_ols` | короткий OLS-горизонт. |
| Derived от forecastable базы | `derived_from_source` | yoy/qoq/mom/агрегаты — прогноз протягивается из базы через pipeline. |
| **Крипта / биржевые котировки / периодичность < месяца** | **нет прогноза** (`forecast_steps=0`) | Правило созвона: «предсказывать курс биткоина — профанация». |
| **Квартальный знаковый** (сальдо/счёт/дефицит) | `signed_quarterly` либо `derived_from_source` | `signed_quarterly` использует первую разность уровня и допускает переход через ноль. Для `trade-balance` предпочтительно тождество `exports_fc − imports_fc` (`operation="subtract"`); выбор и допуск проверять по registry/seed/policy. |

### Антипаттерны (не делать)

| Ошибка | Почему плохо | Правильно |
|--------|--------------|-----------|
| Два переключателя: variant «Индекс/YoY» **и** `ViewModePicker` | Дублирование осей | YoY только в `?mode=`, variant только по **срезу** |
| **Г/г** отдельной верхней кнопкой | Не как у ИПЦ | Г/г внутри «К прошлому периоду» |
| Новый per-family `*ViewMode*` стек для обычной семьи | Дублирует generated-конфиг и resolver | `FamilyDef` + `GenericIndicatorView`; существующие `cpi`/`housing`/`ppi` остаются bespoke |
| Один `?mode=` на целую группу кнопок | Баг навигации 2026-05 | У каждой листовой кнопки свой mode |
| Одинаковый график, разные подписи | Ломает инвариант «режим = ряд» | Отдельный derived / source code |
| Копировать 10 режимов ИПЦ на квартальный ряд | Нет данных в источнике | Только группы с реальным рядом |
| CPI `getViewModeContent` без guard | Methodology leak (ADR-0006) | `isXxxFamily(code)` в семейном модуле |
| Отдельные карточки каталога на каждый YoY | SEO-зоопарк | Скрыть derived, каноникал + `?mode=` |

### Алгоритм работы агента (кратко)

1. **Источник** — `docs/data_sources.md` + docstring парсера: что публикует Росстат, частота, что считаем derived.
2. **Паттерн** — decision tree выше → variant / generic / существующий bespoke.
3. **Матрица режимов** — фаза A; согласовать с продуктом при неясности.
4. **Backend** — фаза B (source + derived, frequency).
5. **UI** — фаза C (нужные файлы по уровню).
6. **Контент + SEO + прогноз** — фазы D, E, F.
7. **Полировка** — фаза G; §8 локально.

---

## 1. Фаза A — Аудит карточки и инвентарь

**Цель:** таблица режимов; gaps зафиксированы.

- [ ] **Стартуй с готового аудита:** блок `completeness` в `docs/indicator-index.json` (+ срез в `docs/indicator-index.md`) — для корня уже посчитана матрица `present`/`expected`/`missing` {тип × частота} и 4 измерения паспорта (тексты/прогноз/группировка/seo). Это детерминированная замена ручной таблице ниже. Модель — `CONTEXT.md::Матрица представлений`, генератор — `scripts/completeness.py`.
- [ ] `docs/indicator-index.json::ui_stack` и `frontend/src/pages/IndicatorDetail.jsx` — определить реальный render-path; не считать `shadowed_legacy` разрешением на удаление старых redirect/content-модулей.
- [ ] Таблица: **режим UI → code БД → частота → derived? → прогноз?**
- [ ] `INDICATOR_HIDDEN_FROM_LISTING` в `indicator_seo.py` — витрина vs режимы.
- [ ] Gaps в `docs/backlog.md`.

**DoD:** нет режима без ряда; паттерн §0 выбран.

---

## 2. Фаза B — Данные и backend

**Цель:** у каждого режима свой ряд.

### 2.1 Source

- [ ] `docs/data_sources.md` + docstring `*_parser.py`.
- [ ] `seed_data.py`, `frequency` = фактическим точкам.
- [ ] ETL может наполнять несколько рядов за прогон.
- [ ] Source-depth → `*_historical.py` (`AGENTS.md` §1).

### 2.2 Derived

- [ ] Для generic сначала `FamilyDef`: sibling-спеки добавляются в `DERIVED_SPECS` через `iter_derived_specs`; собственные вычисления — в `derived_ops.py` + ручной `DerivedSpec` только при необходимости.
- [ ] `seed_data.py`, derived скрыты из каталога.
- [ ] `pytest` derived_ops / calculation_engine.

### 2.3 Инварианты

- [ ] Frequency consistency (`CONTEXT.md`).
- [ ] Для разных кривых задан разный source/derived `code` либо явный виртуальный transform; ИПЦ: `step-weekly` и `period-weekly` нельзя спутать.
- [ ] После изменения формулы/шаблона определить необходимость пересчёта и миграции осиротевших sibling-кодов; выполнение write-операций — по `docs/workflow.md`, с сохранением данных и контролем актуального SHA.

**DoD:** API `/data` — разные кривые для спорных пар; `check-all` зелёный.

---

## 3. Фаза C — UI

### Уровень C — ИПЦ (максимум)

- [ ] `indicatorVariants.js` — «Состав» (4 кода).
- [ ] `cpiViewModeGroups.js` — 4 верхние группы + подрежимы.
- [ ] `cpiViewModeResolve.js` — каждый `mode` → свой `dataMode`.
- [ ] `useIndicatorViewModeData.js` — data + forecast по `chartMode`.
- [ ] `CpiViewModePicker.jsx`, `CpiIndicatorControls.jsx`.
- [ ] `IndicatorChartSection.jsx` — ветки по `chartMode`.

### Уровень C — жильё (эталон проще)

- [ ] `indicatorVariants.js` — «Рынок жилья».
- [ ] `housingViewModeGroups.js` — **К прошлому** (к/к, г/г) | **Индекс**.
- [ ] `housingViewModeResolve.js`, `housingViewModeContent.jsx`, `HousingIndicatorControls.jsx`.
- [ ] Подключение в `IndicatorDetail.jsx` (как CPI).

### Generic (основной путь вне трёх bespoke-семей)

- [ ] Срезы: `indicatorVariants.js` + `VariantGroupPicker`, если есть независимые ряды.
- [ ] Режимы: `view_model_families.py::_FAMILY_DEFS`; запустить `python scripts/export-view-models.py` и проверить сгенерированный `viewModelFamilies.generated.json`.
- [ ] `viewModeEngine.js::resolveViewMode` задаёт `code`/частоту/единицу, `GenericIndicatorView` берёт точки и прогноз выбранного кода.
- [ ] Проверить `backend/tests/test_view_model_families.py`, `frontend/src/lib/viewModeEngine.test.js` и соответствующие UI-тесты; проверить старые canonical-редиректы перед удалением legacy-модулей.

### UX (любой variant)

- [ ] Сохранение `?mode=` при смене среза.
- [ ] `defaultSubModeForGroup` — осмысленный дефолт (не «первая кнопка в DOM»).

**DoD:** график = подпись режима; оси не сбрасывают друг друга.

---

## 4. Фаза D — Контент

- [ ] Для generic — тексты sibling в `seed_data.py::_sibling_texts`, `methodology`/`description` выбранного ряда и его `unit`/`frequency`; для bespoke — соответствующий `*ViewModeContent` и семейный guard.
- [ ] [methodology-language.mdc](../.cursor/rules/methodology-language.mdc).
- [ ] Ревью всех **срез × режим** (ИПЦ 40; жильё 6).
- [ ] Тесты контента семейства.

**DoD:** каждая комбинация описывает **этот** ряд.

---

## 5. Фаза E — SEO

- [ ] Каноникал на листинговые URL; режимы — `?mode=`.
- [ ] `seo_title` / `seo_description` / `seo_blocks` в `indicator_seo.py` — **уникально по срезу**.
- [ ] `scripts/seo-audit.py`; `IndicatorSeoBlocks.jsx`.

**DoD:** SSR title/description осмысленны на каждой витрине.

---

## 6. Фаза F — Прогнозы

- [ ] `forecast_strategy` + `derived_from_source` в sync с `derived_ops`.
- [ ] Стратегию назначать по типу и частоте ряда; source → dependent forecast пересчитывается после обновления данных. Ручной retrain/инвалидацию выполнять только по текущему deploy-регламенту, не через общий `FLUSHDB`.
- [ ] Фронт: forecast только на `chartMode`.

**DoD:** для forecastable режима `/forecast` содержит прогноз выбранного ряда и кривая на графике в той же шкале; для запрещённого/отключённого прогноза отсутствие forecast ожидаемо.

---

## 7. Фаза G — Полировка

- [ ] Мобильный H1, плотность блоков.
- [ ] `relatedIndicatorCardCopy` для variant-группы.
- [ ] Ссылки «Источник» по матрице режимов.
- [ ] Браузер-snapshot (`docs/workflow.md`).

---

## 8. Операционный рецепт (после фаз C–G)

Раздел описывает **порядок проверки**, а не команду на публикацию. Старый рецепт с ручным `seed_data.py`, `rebuild-all-derived.py` и `redis FLUSHDB` заменён: общий `FLUSHDB` затрагивает чужие кэши и не выражает актуальную версионированную инвалидацию (`backend/app/core/cache.py`). Деплой и data-write идут по [`workflow.md`](workflow.md), только до одобренного SHA.

```bash
python scripts/locate-indicator.py wages-nominal
python scripts/build-indicator-index.py --check
./scripts/check-all.sh
```

После изменения поведения проверить через локальный Compose SSR-маршрут `http://127.0.0.1:3000/russia/indicator/<code>` (RU/EN, широкий и узкий экран), JSON `/api/v1/indicators/<code>/data` и `/forecast` у тех кодов, для которых прогноз допустим. Это локальная проверка, не свидетельство деплоя или индексации. См. `CONTEXT.md` (Asset-hash, Browser-cache, Forecast retrain) и `docs/design/README.md`.

---

## 9. Чеклист закрытия по эталонам

> **Исторический снимок внедрения (2026-05/06).** Статус «Да» ниже означает закрытие задачи на тот момент, а названия `*ViewMode*` не доказывают, что модуль остаётся render-path сегодня. Для работы сейчас сверяйте `ui_stack` в `docs/indicator-index.json`, generic early-return в `IndicatorDetail.jsx` и [`dead-code-report.md`](dead-code-report.md); legacy-файлы могут удерживать контент и редиректы.

### ИПЦ (максимум)

| # | Блок | Статус |
|---|------|--------|
| 1 | 4 карточки + variant «Состав» | Да |
| 2 | Недельная у всех 4 (ETL сегменты) | Да |
| 3 | Уровень C, 10 URL-режимов | Да |
| 4 | period-weekly vs step-weekly | Да |
| 5 | Прогнозы по режимам | Да |
| 6 | Контент 4×10 | Да |
| 7 | SEO blocks по срезам | Да |
| 8 | mode + scroll при смене состава | Да |
| 9 | data_sources + тесты | Да |
| 10 | Мобилка / polish | Частично |

### Жильё (эталон уровня C)

| # | Блок | Статус |
|---|------|--------|
| 1 | Variant «Рынок жилья» + `housingViewMode*` | Да |
| 2 | UI: К прошлому (к/к, г/г) \| Индекс | Да |
| 3 | `housing-yoy-*`, `housing-qoq-*`, прогноз | Да |
| 4 | Контент 2×3 | Да |
| 5 | SEO blocks primary + secondary | Да |
| 6 | Данные: к/к → индекс; г/г derived | Да |
| 7 | Hero YoY в шапке | Backlog D3 |

### ИЦП (`ppi`) — уровень C, один срез

| # | Блок | Статус |
|---|------|--------|
| 1 | `ppiViewMode*` + `PpiIndicatorControls` | Да |
| 2 | UI: Инфляция за год \| К прошлому (м/м, г/г) \| Индекс | Да |
| 3 | `ppi-yoy`, `ppi-annual` derived; м/м на фронте | Да |
| 4 | Контент 4 режима (`ppiViewModeContent`) | Да |
| 5 | SEO blocks `ppi` | Да |
| 6 | Redirect `ppi-yoy` / `ppi-annual` → `ppi?mode=` | Да |

### Ипотека (`mortgage-rate`) — уровень C, monthly без variant

| # | Блок | Статус |
|---|------|--------|
| 1 | `mortgageRateViewMode*` + `MortgageRateIndicatorControls` | Да |
| 2 | UI: один режим «уровень ставки» | Да |
| 3 | Прогноз выкл. (`forecast_steps: 0`) | Да |
| 4 | Контент (`mortgageRateViewModeContent`) | Да |
| 5 | SEO blocks ×8 | Да |

### Нефть Brent (`brent`) — уровень C, daily без variant

| # | Блок | Статус |
|---|------|--------|
| 1 | `brentViewMode*` + `BrentIndicatorControls` | Да |
| 2 | UI: Цена (ежедневно) \| Среднее (нед/мес/кв/год) | Да |
| 3 | Агрегаты на фронте; прогноз выкл. | Да |
| 4 | Контент по режиму (`brentViewModeContent`) | Да |
| 5 | SEO blocks ×8 | Да |

### Цена золота (`gold-price`) — уровень C, daily без variant

| # | Блок | Статус |
|---|------|--------|
| 1 | `goldPriceViewMode*` + `GoldPriceIndicatorControls` | Да |
| 2 | UI: Цена (ежедневно) \| Среднее (нед/мес/кв/год) | Да |
| 3 | Агрегаты на фронте; прогноз выкл. | Да |
| 4 | Контент по режиму (`goldPriceViewModeContent`) | Да |
| 5 | SEO blocks ×8 (`test_gold_price_seo.py`, body ≥380) | Да |

### Курс доллара (`usd-rub`) — уровень C, daily без variant

| # | Блок | Статус |
|---|------|--------|
| 1 | `usdRubViewMode*` + `UsdRubIndicatorControls` | Да |
| 2 | UI: Курс (ежедневно) \| Среднее (нед/мес/кв/год) | Да |
| 3 | Агрегаты на фронте; прогноз выкл. | Да |
| 4 | Контент по режиму (`usdRubViewModeContent`) | Да |
| 5 | SEO blocks ×8 | Да |

### Курс евро (`eur-rub`) — уровень C, daily без variant

| # | Блок | Статус |
|---|------|--------|
| 1 | `eurRubViewMode*` + `EurRubIndicatorControls` | Да |
| 2 | UI: Курс (ежедневно) \| Среднее (нед/мес/кв/год) | Да |
| 3 | Агрегаты на фронте; прогноз выкл. | Да |
| 4 | Контент по режиму (`eurRubViewModeContent`) | Да |
| 5 | SEO blocks ×8 | Да |

### Курс юаня (`cny-rub`) — уровень C, daily без variant

| # | Блок | Статус |
|---|------|--------|
| 1 | `cnyRubViewMode*` + `CnyRubIndicatorControls` | Да |
| 2 | UI: Курс (ежедневно) \| Среднее (нед/мес/кв/год) | Да |
| 3 | Агрегаты на фронте; прогноз выкл. | Да |
| 4 | Контент по режиму (`cnyRubViewModeContent`) | Да |
| 5 | SEO blocks ×8 | Да |

### Курсы лиры и тенге (`try-rub`, `kzt-rub`) — daily ЦБ без variant, T1 `FamilyDef` (08.10.2026, локально)

Новые валюты ЦБ добавляются без нового ключа фронтенда: `cbr_fx_parser.CURRENCY_MAP` (код ЦБ и номинал) → строка `seed_data.py` (`forecast_steps: 0`, максимальная история) → `FamilyDef` в `data/view_model_families.py` → `python3 scripts/export-view-models.py` (зеркало `viewModelFamilies.generated.json`) → `site_paths._CURRENCY_BASE_CODES` и зеркало `frontend/src/lib/sitePaths.js` → SEO-блоки `indicator_seo.py` (`_FX_RATE_BLOCK_SPECS`, восемь блоков «О показателе») и EN-тексты `indicator_copy_en.py` → слова поиска (`search_intent.py`, `search_language.py`) → `python3 scripts/build-indicator-index.py`. Имя, знак и флаг валюты клиент берёт из `Intl` по коду пары (`lib/currencyRates.js::unitMeta`), конвертер и поиск «Из/В» подхватывают пару сами. Подробности и непройденные валюты — [data_sources](data_sources.md), [контракт](data-contracts.md#c9-data-2026-10-08).

### Биткоин (`btc-usd`) — уровень C, daily без variant

| # | Блок | Статус |
|---|------|--------|
| 1 | `btcUsdViewMode*` + `BtcUsdIndicatorControls` | Да |
| 2 | UI: Цена (ежедневно) \| Среднее (нед/мес/кв/год) | Да |
| 3 | Агрегаты на фронте; прогноз выкл. | Да |
| 4 | Контент по режиму (`btcUsdViewModeContent`) | Да |
| 5 | SEO blocks ×8 | Да |

### RUONIA (`ruonia`) — уровень C, daily без variant

| # | Блок | Статус |
|---|------|--------|
| 1 | `ruoniaViewMode*` + `RuoniaIndicatorControls` | Да |
| 2 | UI: Уровень ставки \| Среднее (нед/мес/кв/год) | Да |
| 3 | Агрегаты на фронте; прогноз выкл. | Да |
| 4 | Контент по режиму (`ruoniaViewModeContent`) | Да |
| 5 | SEO blocks ×8 | Да |

### Ключевая ставка (`key-rate`) — уровень C, daily без variant

| # | Блок | Статус |
|---|------|--------|
| 1 | `keyRateViewMode*` + `KeyRateIndicatorControls` | Да |
| 2 | UI: Уровень ставки \| Среднее (нед/мес/кв/год) | Да |
| 3 | Агрегаты на фронте (`applyAggregateTransform`); прогноз выкл. | Да |
| 4 | Контент по режиму (`keyRateViewModeContent`) | Да |
| 5 | SEO blocks ×8 (`indicator_seo.py`) | Да |
| 6 | История: рефинансирование до 2013 в одном ряду | Да (источник) |

### Федеральный бюджет (`budget-revenue` / `budget-expenditure` / `budget-deficit`) — уровень C + variant

| # | Блок | Статус |
|---|------|--------|
| 1 | `budgetViewMode*` + `BudgetIndicatorControls` | Да |
| 2 | Variant: «Федеральный бюджет» — доходы \| расходы \| дефицит/профицит | Да |
| 3 | UI: Помесячно \| Среднее (кв/год) | Да |
| 4 | Агрегаты на фронте; прогноз выкл. | Да |
| 5 | Контент по срезу × режиму (`budgetViewModeContent`) | Да |
| 6 | SEO blocks ×8 на каждый из трёх кодов | Да |

### Кредиты бизнесу (`business-credit`) — уровень C

| # | Блок | Статус |
|---|------|--------|
| 1 | `bankCreditViewMode*` + `BankCreditIndicatorControls` | Да |
| 2 | Variant | Нет (одиночная карточка) |
| 3 | UI: Помесячно \| Среднее (кв/год) | Да |
| 4 | Агрегаты на фронте; прогноз выкл. | Да |
| 5 | Контент по режиму (`bankCreditViewModeContent`) | Да |
| 6 | SEO blocks ×8; уникальные title/body | Да |

### Денежные агрегаты (`m0` / `m1` / `m2`) — уровень C + variant

| # | Блок | Статус |
|---|------|--------|
| 1 | `monetaryMassViewMode*` + `MonetaryMassIndicatorControls` | Да |
| 2 | Variant «Денежные агрегаты» (М0 / М1 / М2) | Да |
| 3 | UI: Помесячно \| Среднее (кв/год) | Да |
| 4 | Агрегаты на фронте; прогноз выкл. | Да |
| 5 | Контент по режиму и коду (`monetaryMassViewModeContent`) | Да |
| 6 | SEO blocks ×8 на каждый код; уникальные title/body ≥420 | Да |

### Средняя заработная плата (`wages-nominal`) — уровень C

| # | Блок | Статус |
|---|------|--------|
| 1 | `wagesNominalViewMode*` + `WagesNominalIndicatorControls` | Да |
| 2 | Variant | Нет (режимы на каноническом URL, derived в БД) |
| 3 | UI: Уровень (помесячно / с 1991) \| Динамика (реальная / г/г / индекс) | Да |
| 4 | Режимы — отдельные ряды в БД; годовой sibling `wages-nominal-annual`; прогноз выкл. | Да |
| 5 | Контент по режиму (`wagesNominalViewModeContent`) | Да |
| 6 | SEO blocks ×8; уникальные title/body ≥420 | Да |

### Уровень безработицы (`unemployment`) — уровень C

| # | Блок | Статус |
|---|------|--------|
| 1 | `unemploymentViewMode*` + `UnemploymentIndicatorControls` | Да |
| 2 | Variant | Нет (режимы на `?mode=`, derived в БД) |
| 3 | UI: Помесячно \| Сглаживание (кв / 12М) | Да |
| 4 | Квартал и 12М — отдельные ряды в БД; прогноз только на помесячном | Да |
| 5 | Контент по режиму (`unemploymentViewModeContent`) | Да |
| 6 | SEO blocks ×8; уникальные title/body ≥420 | Да |

### Рынок труда: занятость (`labor-force` / `employment`) — уровень C + variant

| # | Блок | Статус |
|---|------|--------|
| 1 | `laborMarketViewMode*` + `LaborMarketIndicatorControls` | Да |
| 2 | Variant «Рынок труда: занятость» (рабочая сила \| занятое население) | Да |
| 3 | UI: Помесячно \| Среднее (кв/год) | Да |
| 4 | Агрегаты на фронте; прогноз выкл. | Да |
| 5 | Контент по срезу × режиму (`laborMarketViewModeContent`) | Да |
| 6 | SEO blocks ×8 на каждый код; уникальные title/body ≥420 | Да |

### Международные резервы (`international-reserves`) — уровень C

| # | Блок | Статус |
|---|------|--------|
| 1 | `internationalReservesViewMode*` + `InternationalReservesIndicatorControls` | Да |
| 2 | Variant | Нет (одиночная карточка) |
| 3 | UI: Еженедельно \| Среднее (мес/кв/год) | Да |
| 4 | Агрегаты на фронте; прогноз выкл. | Да |
| 5 | Контент по режиму (`internationalReservesViewModeContent`) | Да |
| 6 | SEO blocks ×8; уникальные title/body ≥380 | Да |

### Расходы домохозяйств (`gdp-consumption`) — уровень C

| # | Блок | Статус |
|---|------|--------|
| 1 | `gdpUseViewMode*` + `GdpUseIndicatorControls` | Да |
| 2 | Variant «ВВП по использованию» (домохозяйства \| гос \| инвестиции) | Да |
| 3 | UI: Поквартально \| Среднее (по годам) | Да |
| 4 | Годовое усреднение кварталов на фронте; прогноз только на поквартальном | Да |
| 5 | Контент по срезу × режиму (`gdpUseViewModeContent`) | Да |
| 6 | SEO blocks ×8; уникальные title/body ≥420 | Да |

### Государственное потребление (`gdp-government`) — уровень C

| # | Блок | Статус |
|---|------|--------|
| 1 | `gdpUseViewMode*` + `GdpUseIndicatorControls` (общее семейство с `gdp-consumption`) | Да |
| 2 | Variant «ВВП по использованию» | Да |
| 3 | UI: Поквартально \| Среднее (по годам) | Да |
| 4 | Годовое усреднение на фронте; прогноз только на поквартальном | Да |
| 5 | Контент по срезу × режиму (`gdpUseViewModeContent`) | Да |
| 6 | SEO blocks ×8; уникальные title/body ≥420 | Да |

### ВВП номинальный (`gdp-nominal`) — уровень C

| # | Блок | Статус |
|---|------|--------|
| 1 | `gdpNominalViewMode*` + `GdpNominalIndicatorControls` | Да |
| 2 | Variant | Нет (режимы на `?mode=`, derived в БД) |
| 3 | UI: Поквартально \| Темпы (г/г, к/к) \| За год | Да |
| 4 | Режимы — отдельные ряды в БД; `gdp-nominal-annual` annual sibling; прогноз только на `level` | Да |
| 5 | Контент по режиму (`gdpNominalViewModeContent`) | Да |
| 6 | SEO blocks ×8; уникальные title/body ≥420 | Да |

### ВВП реальный (`gdp-real`) — уровень C

| # | Блок | Статус |
|---|------|--------|
| 1 | `gdpRealViewMode*` + `GdpRealIndicatorControls` | Да |
| 2 | Variant | Нет (режимы на `?mode=`, derived в БД) |
| 3 | UI: Поквартально \| Темпы (г/г, к/к) \| За год | Да |
| 4 | Режимы — отдельные ряды в БД; `gdp-real-annual` annual sibling; прогноз только на `level` | Да |
| 5 | Контент по режиму (`gdpRealViewModeContent`) | Да |
| 6 | SEO blocks ×8; уникальные title/body ≥420 | Да |

### Внешний долг (`external-debt`) — уровень C

| # | Блок | Статус |
|---|------|--------|
| 1 | `externalDebtViewMode*` + `ExternalDebtIndicatorControls` | Да |
| 2 | Variant | Нет (одиночная карточка) |
| 3 | UI: Поквартально \| Среднее за период (только по годам) | Да |
| 4 | Годовое усреднение кварталов на фронте; прогноз выкл. | Да |
| 5 | Контент по режиму (`externalDebtViewModeContent`) | Да |
| 6 | SEO blocks ×8; уникальные title/body ≥380 | Да |

### Кредиты и вклады населения (`consumer-credit` / `deposits-individual`) — уровень C + variant

| # | Блок | Статус |
|---|------|--------|
| 1 | `householdFinanceViewMode*` + `HouseholdFinanceIndicatorControls` | Да |
| 2 | Variant: «Кредиты и вклады населения» — кредиты \| вклады | Да |
| 3 | UI: Помесячно \| Среднее (кв/год) | Да |
| 4 | Агрегаты на фронте; прогноз выкл.; единицы трлн / млрд | Да |
| 5 | Контент по срезу × режиму (`householdFinanceViewModeContent`) | Да |
| 6 | SEO blocks ×8 на каждый код; уникальные title/body ≥320 | Да |

---

## 10. Следующие семейства — с чего начать

> Исторический backlog 2026-05/06. Актуальный выбор стека описан в §0; приоритеты — в `docs/backlog.md`.

| Семейство | Уровень | Не копировать слепо |
|-----------|---------|---------------------|
| **ВВП** | A + возможно B | 10 режимов ИПЦ |
| **PPI** (`ppi`) | **C** — `ppiViewMode*` (закрыто 2026-05-30) | `viewModeFamilies`; variant-pills |
| **Торговля** | B (уже есть) | Отдельные URL на YoY; довести тексты + SEO |
| **Зарплаты / безработица** | B | CPI content без guard |
| **Новое семейство с 2 осями** | Исторически: C по образцу жилья | Сегодня сначала `FamilyDef`; bespoke только для существующих `cpi`/`housing`/`ppi` |

Перед стартом: §0 decision tree → открыть **только** файлы эталона того же уровня (ИПЦ или жильё) → фазы A→G.

---

## 11. Связанные документы

| Документ | Когда |
|----------|--------|
| `AGENTS.md::Шаг 4` | Новый code / derived |
| `docs/adr/0006-*` | Variant vs view-mode vs listing |
| `docs/adr/0001-*` | Derived engine |
| `docs/backlog.md` | Приоритеты (P1: GDP/PPI/…) |
| `docs/workflow.md` | Деплой, браузер |
| `docs/architecture.md` | Текущие компоненты и сквозные потоки |

---

## История playbook

| Дата | Изменение |
|------|-----------|
| 2026-09-27 | Сверка с текущим кодом: generic `FamilyDef` стал основным механизмом; три bespoke-семьи сохранены, исторические чеклисты помечены; операционный рецепт заменён безопасным порядком проверки. |
| 2026-05-30 | Продуктовая модель, decision tree, антипаттерны, жильё как второй эталон; ИЦП (`ppiViewMode*`); ипотека (`mortgageRateViewMode*`, SEO ×8); RUONIA (`ruoniaViewMode*`, SEO ×8); USD/EUR/CNY (`*RubViewMode*`, SEO ×8); Brent/BTC (`brentViewMode*`, `btcUsdViewMode*`, SEO ×8); цена золота (`goldPriceViewMode*`, SEO ×8); ключевая ставка (`keyRateViewMode*`, SEO ×8); федеральный бюджет (`budgetViewMode*` + variant ×3, SEO ×8); кредиты бизнесу (`bankCreditViewMode*`, SEO ×8); кредиты и вклады населения (`householdFinanceViewMode*` + variant ×2, SEO ×8); денежные агрегаты (`monetaryMassViewMode*` + variant ×3, SEO ×8); международные резервы (`internationalReservesViewMode*`, SEO ×8); внешний долг (`externalDebtViewMode*`, SEO ×8); рынок труда (`laborMarketViewMode*` + variant ×2, SEO ×8); безработица (`unemploymentViewMode*`, SEO ×8); порог SEO-body для M0–M2 доведён до ≥420, склейки строк исправлены. |
| 2026-06-01 | Первая версия: фазы A–G на примере ИПЦ. |
