# Индикаторы и категории — рецепты

**Когда читать:** задача про конкретный индикатор, новый ряд, семейство режимов
или новую категорию каталога. Общий контекст — [`../AGENTS.md`](../AGENTS.md),
глоссарий и ловушки — [`../CONTEXT.md`](../CONTEXT.md), решения — ADR-0001/0002/0006.

## 1. Задача про индикатор X — быстрый путь

1. **Где код встречается:** `python scripts/locate-indicator.py X`
   (seed / parser / derived / family / seo / variants / tests).
2. **Запись `X` в [`docs/indicator-index.json`](indicator-index.json)** —
   `ui_stack`, `parser_type`, `forecast_strategy`, `derived_siblings`, `is_listed`,
   `flags`. Человекочитаемо — [`docs/indicator-index.md`](indicator-index.md).
3. **Правь механизм нужного слоя** (таблица выше) / для UI — стек из `ui_stack`:
   `generic` → `view_model_families.py` (+ regen) / `cpi|housing|ppi` → bespoke
   `frontend/src/lib/{cpi,housing,ppi}ViewMode*` / `variant` → `indicatorVariants.js`.
4. **Доведи данные до UI** — [`.cursor/rules/indicator-data-delivery.mdc`](../.cursor/rules/indicator-data-delivery.mdc).
5. `./scripts/check-all.sh` (регенерирует карту + guard `--check`).

> **`flags.shadowed_legacy` / `in_both_viewmode_systems` — НЕ «можно удалять».**
> Флаг значит лишь, что standalone-ветка рендера в `IndicatorDetail.jsx` перекрыта
> generic. Сам легаси-файл обычно ЖИВОЙ: его content/resolve переиспользуются
> общими секциями (chart/table title, picker, data-resolve) и держат
> canonical-редиректы старых индексируемых URL (`*-yoy-abs`,
> `unemployment-quarterly/-annual` — движком не покрыты). Расследование и почему
> это НЕ delete-list — [`docs/dead-code-report.md`](dead-code-report.md).
> Удаление редиректа = тихая просадка SEO, тесты не ловят → ЭСКАЛАЦИЯ.

Карта детерминированная, регенерируется в `check-all.sh`
(`scripts/build-indicator-index.py`, guard `--check`). Объективный список файлов —
[`docs/repo-inventory.md`](repo-inventory.md).

> **Полнота индикатора = матрица {тип × частота}** (эталон — переключатель ИПЦ).
> Какие представления у `X` есть/чего не хватает — блок `completeness` в
> [`docs/indicator-index.json`](indicator-index.json) + срез в
> [`docs/indicator-index.md`](indicator-index.md) (модуль
> `scripts/completeness.py`). Доменная модель — `CONTEXT.md::Матрица представлений`.
> Это аудит-карта (read-only): пробел = кандидат на режим, не дефект.

## 2. Новая категория (полка каталога)

Категория — это не индикатор, а полка каталога: значение `Indicator.category` в
БД + карточка в меню/футере + SSR-SEO страницы `/category/<slug>`. Шесть
обязательных точек касания (эталон — добавление «Индексы»/«Товарные рынки»,
2026-06-25). `<slug>` латиницей, `<api_category>` — точное русское имя в seed:

1. **Frontend-карточка** — `frontend/src/lib/categories.js::CATEGORIES`: объект
   `{ slug, name, nameEn, icon, apiCategory, status:'active', flagshipCode,
   sentiment, description, seoTitle, seoDescription, relatedSlugs }`.
   `seoTitle/seoDescription` обязаны **побайтово** совпасть с backend (п. 2),
   иначе SSR-meta разойдётся с CSR и поисковик переиндексирует страницу.
2. **Backend-SEO** — `backend/app/services/seo_content.py::CATEGORY_META`: запись
   `CategorySeo(slug, name, api_category, title, description, intro,
   flagship_code, keywords)`. `CATEGORIES` (для sitemap) выводится отсюда —
   страница `/category/<slug>` в sitemap появится сама.
3. **Иконка** — `frontend/src/components/CategoryBlock.jsx`: добавить
   lucide-иконку и в `import`, и в `CATEGORY_ICONS` (иначе тихий фолбэк на
   `LayoutGrid`).
4. **Индикаторы в полке** — в `seed_data.py` у нужных рядов выставить
   `"category": "<api_category>"`; завести FamilyDef/parser/seo по
   indicator-чеклисту ниже.
5. **Тесты-счётчики** — обновить `len(CATEGORIES)` в
   `frontend/src/lib/categories.test.js` и `backend/tests/test_seo_og.py`
   (`test_sitemap_static_pages_constant`).
6. **Меню-сетка** — `Dashboard.jsx` рендерит `CATEGORIES` в `lg:grid-cols-3`;
   держать число категорий кратным 3 (12 = 3×4) для ровной сетки.

`./scripts/check-all.sh` зелёный; затем браузер-smoke `/category/<slug>` и любой
карточки внутри (меню/футер показывают новую полку, график не пустой).

## 3. Новый индикатор — рецепт владельца

Диктовка владельца (звонки 2026-06; дословно «по такому рецепту мы будем
добавлять новые индикаторы»). Любой новый ряд обязан пройти ВСЕ пункты — иначе
карточка выглядит «сделано студентом». Детальный 8-пунктный чеклист с trap'ами —
в §4 ниже; здесь — что именно требует владелец, в его формулировках:

1. **Максимальная история** — стартовать с самого раннего года, который отдаёт
   источник (live-probe пола; `backfill_from*` в конфиге). Огрызок недопустим —
   при коротком seed завести `<name>_historical.py`. Если глубже нельзя
   (методологический пол) — задокументировать в `docs/backlog.md`.
2. **Двухуровневая матрица** (унификация) — одной строкой `FamilyDef` в
   `backend/app/data/view_model_families.py::_FAMILY_DEFS`; билдер развернёт полную
   матрицу {тип × частота} (к прошлому периоду / к году по мес·кв·год / средние /
   уровень). Bespoke (cpi/ppi/housing) — только эти три семьи.
3. **Объединение при необходимости** — если у показателя есть варианты-срезы
   (продукты, сроки, разделы): это РАЗНЫЕ ряды → variant-группа в
   `frontend/src/lib/indicatorVariants.js` (`VariantGroupPicker`), а компоненты
   скрыть из листинга (`INDICATOR_HIDDEN_FROM_LISTING`). Эталоны: жильё
   первичка/вторичка, ИПП (общий + 4 раздела), топливо (АИ-92/95/дизель),
   зарплата (номинальная/реальная). Не путать с view-mode (один ряд, разные
   представления).
   **Anti-orphan-инвариант (звонок 2026-06-25):** `is_listed=false` ⇒ ряд исчез
   из каталога, но остался в поиске. Он ОБЯЗАН быть достижим хотя бы одним
   способом: (а) sibling generic-семьи (`view_model_families`), (б) член
   variant-группы (`indicatorVariants.js`), (в) `alternate_frequencies`/
   `primary_indicator_code` (FrequencySwitcher), (г) bespoke-режим
   (cpi/ppi/housing/unemployment resolve). Иначе индикатор «осиротевший» —
   виден только в поиске, на категории его нет (баг real-wages: derived-ряд
   был скрыт, но ни в семье, ни в группе → чинили variant-группой «Заработная
   плата» + собственной T8-семьёй). Аудит: скрипт сверки `is_listed=false`
   против объединения gen∪variant∪freq∪bespoke.
4. **Источник — только официальный** (Росстат, Банк России, Минфin, МосБиржа ISS
   и подобные первоисточники / биржи). Никаких новостных сайтов и сервисов-
 агрегаторов. Для зарубежного национального показателя приоритет всегда у
 национального статистического ведомства/ЦБ/таможни/министерства; OECD и
 Всемирный банк не заменяют доступный первоисточник. Точная карта `URL/endpoint`
 — `docs/data_sources.md` + docstring парсера.
5. **Правильные названия графика и осей** — заголовок и подпись оси отражают
   единицу/частоту/режим (generic берёт из `unit`/`frequency`; bespoke — из
   `*ViewModeContent`). Проверить глазами в каждом режиме.
6. **Прогноз, если нужен** — стратегия в
   `forecast_strategies/registry.py` (`model_config_json.forecast_strategy`).
   НЕ ставить прогноз на биржевое/крипту/частоту < месяца (профанация). Месячные
   — `monthly_auto`; короткие тренды (недельные цены) — `generic_ols`; завести в
   соответствующем whitelist (`MONTHLY_AUTO_FORECAST_CODES` /
   `GENERIC_OLS_FORECAST_CODES` в тесте политики).
7. **Методология** — поле `methodology` в seed: содержательно, публичным языком
   (`.cursor/rules/methodology-language.mdc`), без parser-жаргона.
8. **Блок «О показателе»** — `INDICATOR_SEO_BLOCKS` в `indicator_seo.py` (6
   подблоков: что показывает / какой режим / чем важен / как читать / как часто
   обновляется / откуда данные). Для однотипных семейств — DRY-билдер по спеку
   (эталоны: `_build_commodity_blocks`, `_build_ipi_component_blocks`,
   `_build_fuel_blocks`).
9. **Автоматический SEO** — curated `seo_keywords` + `seo_title`/`seo_description`
   в `KEYWORDS_BY_INDICATOR` + `INDICATOR_SEO`. Остальное (sitemap, годовые
   landing `/indicator/{code}/{year}`, OG `/api/v1/og-image/...`, RSS,
   related-блоки) подтянется из БД само — ручного ничего.
10. **Главная страница** — при каждом добавлении или обновлении показателей
    сверить счётчики, источники и формулировки на `/` (SSR и SPA, RU и EN).
    Числа брать из текущего публичного каталога/БД; устаревшие константы в
    `HomeDataScope`, `seo_content` и текстах главной не оставлять.

### Поиск — автоматически (ничего не править)

Любой новый индикатор попадает И в **глобальный поиск** (`IndicatorSearch.jsx`,
⌘K — `include_unlisted`, весь каталог листается), И в **поиск сравнения**
(`ComparePage.jsx::AddIndicator`, listed-пул, листается весь). Оба берут список
из API и фильтруют по `name/name_en/category/code/seo_keywords`. Никаких
жёстких «топ-N»: списки скроллятся целиком. Единственное условие, чтобы новый
ряд хорошо искался, — осмысленные `seo_keywords` (корни/синонимы на русском,
п. 9).

### Материалы для Яндекс.Алисы / Нейро (генерация — отдельным проходом)

Цель (диктовка владельца): когда в Яндексе спрашивают Алису/Нейро про показатель
(«дефицит бюджета по годам график», «средняя ставка по автокредитам»), ассистент
ссылается на нас И показывает НАШ график-картинку. Как Алиса/Нейро берут
материалы и что готовим:

- **Что показывает ассистент:** текст-сниппет (meta description / структурный
  контент) + одну картинку. Картинка берётся ТРЕМЯ путями, и мы закрываем все:
  (а) `og:image` в `<head>`; (б) `schema.org/ImageObject` (JSON-LD); (в) **видимый
  `<img>` в теле страницы** — Алиса ходит в поиск по картинкам и берёт изображения
  прямо из DOM SSR-страницы, поэтому одного `og:image` мало. Картинка должна быть
  **самодостаточной** (заголовок, ось min/max, крайние даты периода, последнее
  значение, источник, бренд `forecasteconomy.com`) — тогда, показанная отдельно,
  она объясняет себя и разносит бренд.
- **Под какие запросы готовим (Wordstat-логика):** alt/`name` картинок и заголовки
  страниц повторяют формулировки пользователей — «{имя} график», «{имя} по
  годам», «{имя} по месяцам», «{имя} {год}», «{имя} статистика», «{имя} прогноз».
- **Поверхности (реализовано 2026-06-25):**
  1. Карточка `/indicator/{code}` — картинка-график `/og/{code}.png`
     (`og_image.py` → `sitemap.py::og_image_indicator`): бренд-полоса, имя,
     последнее значение, дата, линейный график с подписями осей (min/max по Y,
     крайние годы по X), домен. Подключена ТРЕМЯ способами в
     `seo_renderer::render_indicator_html`: `og:image`, `ImageObject` (JSON-LD,
     representativeOfPage) и **видимый `<figure class="seo-chart"><img>`** в теле
     SSR с описательным `alt` («{имя} — график динамики, последнее значение …,
     источник …»). Видимый `<img>` — ключ к тому, чтобы Алиса взяла именно наш
     график, а не любую картинку со страницы.
  2. Годовые landing `/indicator/{code}/{year}` — **поголовая** картинка-график
     `/og/{code}/{year}.png` (`sitemap.py::og_image_indicator_year`): график
     по точкам конкретного года, метка «{year} год» в шапке, среднее за год,
     крайние даты периода по оси X. Стоит в `og:image` + `ImageObject` + **видимый
     `<img>`** в теле годовой страницы (`render_indicator_year_html`) рядом с
     `Dataset`/`temporalCoverage`.
  3. nginx: `location ^~ /og/` — два rewrite (год сначала, потом базовый).
- **Любой новый индикатор получает все картинки и разметку автоматически** из БД:
  ручного ничего, кроме curated `seo_keywords`/`seo_title` (п. 9). Дизайн картинки —
  единственная правка `og_image.py` (шрифт Inter с кириллицей). CSS видимого
  графика — `.seo-chart` в `SEO_CRITICAL_CSS` (`seo_renderer.py`).

## 4. Чеклист «новый индикатор» (trap'ы)

Перед добавлением **любого** нового индикатора (source-парсер, derived, manual seed) пройти все 7 проверок. Без них вероятен один из задокументированных trap'ов из `CONTEXT.md::Operational invariants and traps`. См. ADR-0006 «Indicator card unification».

| # | Проверка | Что делаем |
|---|----------|------------|
| 1 | **Source-depth invariant** | Какую максимальную глубину истории даёт источник? Если в seed_data залит **меньший** ряд — заводим `<name>_historical.py` immutable seed (как `housing_historical.py`, `refinancing_rate_historical.py`, `wages_historical.py`). НЕ оставляем огрызок. |
| 2 | **Frequency consistency** (КРИТИЧНО) | Перед `bulk_upsert` сверить `target.frequency` с фактической частотой добавляемых точек. Если расхождение (annual → monthly indicator) — заводим **отдельный sibling indicator** с правильной `frequency` и `is_listed=false`, добавляем режим в `viewModeFamilies`. См. trap `Annual-in-monthly mixing` в `CONTEXT.md`. |
| 2b | **Initial ETL trigger** | Закрыто автоматикой в `app/main.py::_catch_up_empty_indicators()` — при startup backend сам триггерит ETL для всех source-индикаторов с 0 точек. После deploy с новым indicator достаточно `docker compose up -d backend` — данные подтянутся в фоне. Если в логах `Startup catch-up: <code> failed: ...` — источник битый, чинить парсер. См. trap `New indicator initial ETL trap` в `CONTEXT.md`. |
| 3 | **View-mode family оценка** | Если ряд > 100 точек и есть осмысленные derived'ы (YoY/QoQ/MoM/aggregation) — заводим **одной строкой `FamilyDef`** в config-driven источнике `backend/app/data/view_model_families.py::_FAMILY_DEFS` (билдер по природе ряда сам развернёт полную матрицу {тип × частота}, включая многоуровневую Г/г через `_yoy_modes`; sibling-ряды авто-seed + авто-скрыты, тексты авто, прогноз авто-протягивается). Выбор шаблона по природе — таблица «Generic-семья: природа ряда → билдер-шаблон» в §5 ниже. **Не** отдельная карточка каталога; derived скрыты автоматически. Легаси `frontend/src/lib/viewModeFamilies.js` — только для немигрированных bespoke-остатков. |
| 4 | **Variant decomposition** | Если индикатор имеет варианты по срезу (срок, регион, подгруппа, тип) — это **разные индикаторы со своими рядами** → `VariantGroupPicker` (см. `lib/indicatorVariants.js`). Не путать с view-mode (один ряд, разные представления). |
| 5 | **Negative-capable check** | Если значения могут быть отрицательными (`trade-balance`, `current-account`, `budget-deficit`, `*-migration`) — использовать `yoy_abs` (разница в единицах источника), **не** `yoy_pct` (% от базы с переходом через ноль = визуальный мусор и тысячи процентов). |
| 6 | **Frequency strategy** | Daily-индикатор: aggregation (week/month/quarter/year avg) — `applyAggregateTransform` на фронте, **backend derived не заводим**. Monthly counterpart существующего quarterly — отдельный индикатор с MoM%-режимом через виртуальный `transform: 'mom'`. |
| 7 | **Listing visibility ≠ searchability** | Если индикатор скрыт из каталога (`is_listed=false` через `INDICATOR_HIDDEN_FROM_LISTING`) — он всё равно ищется через `?include_unlisted=true` в `IndicatorSearch.jsx`. Search haystack включает `seo_keywords` — в новом индикаторе всегда задаём osmysленные ключевые корни на русском (зарпл/инфля/безраб и т.п.). |
| 8 | **SEO-автоматика — ничего руками** | Sitemap (lastmod/priority), related-блоки, годовые landing'и `/indicator/{code}/{year}`, OG-превью `/og/{code}.png`, RSS `/feed.xml`, IndexNow-пинг — всё подтянет новый индикатор из БД само (ADR-0003 «Subsequent additions», `CONTEXT.md::SEO meta bundle`). Единственное ручное: curated `seo_keywords` + `seo_title`/`seo_description` в `app/data/indicator_seo.py` (иначе сработает generic fallback). При смене дизайн-токенов фронта — синхронизировать `SEO_CRITICAL_CSS` в `seo_renderer.py`. |

**После прохождения чеклиста** — обновить `seed_data.py` + соответствующие mappings (variant/view-mode), прогнать `./scripts/check-all.sh`, обновить `CONTEXT.md::Operational invariants and traps` если открыли новую trap.

## 5. Семейство индикаторов — продуктовая модель и фазы A–G

### Продуктовая модель (что копируем с ИПЦ)

ИПЦ — референс **зрелой карточки**, не список из 10 кнопок. Переносим **инварианты**, число режимов и групп — из **модели данных Росстата**.

#### Инварианты (обязательны для любого семейства с режимами)

| # | Инвариант | Смысл |
|---|-----------|--------|
| 1 | **Одна витрина — много смыслов** | В каталоге листинговые карточки; derived-режимы скрыты (`INDICATOR_HIDDEN_FROM_LISTING`), доступ через `?mode=` на каноническом URL. |
| 2 | **Две оси не смешивать** | **Variant (срез)** = другой ряд, другой `code`, другой URL. **Режим (`?mode=`)** = другое представление **того же** среза. |
| 3 | **Один режим = один ряд в БД** | График, таблица, прогноз, «О показателе» — **другие точки**, не другая подпись к тем же точкам. |
| 4 | **Группы режимов по экономическому смыслу** | Как у ИПЦ: «инфляция за год», «рост за период», «к прошлому периоду», «индекс». **Г/г живёт внутри «к прошлому»**, не отдельной верхней кнопкой. |
| 5 | **Матрица контента** | Тексты = **срез × режим** (ИПЦ 4×10; жильё 2×3). Guard в `*ViewModeContent` — чужие семьи не получают CPI-тексты. |
| 6 | **SEO на каждую листинговую карточку** | Уникальные `seo_blocks` по срезам; режимы не плодят отдельные URL в каталоге. |
| 7 | **Прогноз = активный режим** | `useIndicatorViewModeData` / аналог грузит forecast по `chartMode`, не по родительскому source. |
| 8 | **Variant UX** | Смена среза сохраняет `?mode=`; без прыжка скролла (`isVariantSiblingNavigation`). |

#### Оси ИПЦ (зачем эталон)

| Верхняя группа | Смысл | Отдельный ряд? |
|----------------|--------|----------------|
| Инфляция за год | 12 мес., не то же, что г/г | Да |
| Рост за период | Накопление внутри периода (нед/мес/кв/год) | Да |
| К прошлому периоду | Шаг: н/н, м/м, **к/к**, **г/г** | Да |
| Индекс | Уровень (накопленная шкала) | Да |

У каждой **листовой** кнопки свой `?mode=` в URL (не один mode на всю группу — урок бага 2026-05).

#### Жильё — второй эталон (квартальный срез)

Та же **архитектура** (`housingViewMode*`, `HousingIndicatorControls`), меньше режимов — **честно по источнику**:

| Группа ИПЦ | У жилья | Примечание |
|------------|---------|------------|
| Инфляция 12 мес. | **Нет** | Не выдумывать ряд |
| Рост за период (нед/мес/…) | **Нет** | Только квартальная частота |
| **К прошлому периоду** | **К/к** + **Г/г** | К/к — официальный прирост в обзоре; г/г — derived от индекса |
| **Индекс** | **Да** | 2010=100, цепочка от к/к |

**Variant:** первичное ↔ вторичное (`indicatorVariants.js`, группа «Рынок жилья»).

**Файлы эталона:** `housingViewModeGroups.js`, `housingViewModeResolve.js`, `housingViewModeContent.jsx`, `HousingIndicatorControls.jsx`; backend: `housing-yoy-*`, `housing-qoq-*`, `housing-price-*`; SEO: `indicator_seo.py` (`INDICATOR_SEO_BLOCKS`).

#### Три уровня реализации UI

| Уровень | Когда | Стек |
|---------|--------|------|
| **A. Только variant** | Разные срезы, один смысл на карточке | `indicatorVariants.js` + `VariantGroupPicker` |
| **B. Generic view-mode** | 2–4 простых режима одного ряда, без двухуровневых групп | `viewModeFamilies.js` + `ViewModePicker` |
| **C. Семейный view-mode** (ИПЦ, жильё) | Две оси **или** много режимов с разной семантикой / группами | `*ViewModeGroups`, `*ViewModeResolve`, `*ViewModeContent`, `*IndicatorControls` |

**Правило:** если сомневаешься между B и C — открой ИПЦ и жильё; если оси как у них — уровень **C**, не «быстрый» B.

#### Продуктовый Definition of Done (перед «готово»)

- [ ] Экономист понимает переключатели **без** объяснения в чате (группы = смысл Росстата).
- [ ] Таблица **режим UI → code БД → частота → derived? → прогноз?** заполнена; нет режима без ряда.
- [ ] Для каждой активной ячейки **срез × режим** — свои description/methodology ([methodology-language](../.cursor/rules/methodology-language.mdc)).
- [ ] Старые URL derived (если были) → редирект/каноникал `parent?mode=…`.
- [ ] Локально прогнан §8; `./scripts/check-all.sh` зелёный; выборочно API data/forecast по спорным режимам.

---

### 0. Выбор паттерна (до кода)

#### Decision tree

```
1. Есть несколько независимых рядов по срезу (рынок, состав, срок)?
   → Да: VARIANT (отдельные URL). Нет: пропустить variant.

2. Есть несколько представлений одного среза (YoY, QoQ, уровень, …)?
   → Нет: только фаза A + variant/SEO при необходимости.
   → Да: нужен VIEW-MODE.

3. Сколько режимов и насколько разная семантика?
   → 2–4 плоских, без групп «к прошлому / индекс»
        → Уровень B: viewModeFamilies.js
   → Группы как у ИПЦ ИЛИ variant + режимы ИЛИ >4 режимов
        → Уровень C: свой *ViewMode* стек (скопировать структуру cpi/housing, не текст)

4. Значения могут быть отрицательными?
   → yoy_abs, не yoy_pct (trade-balance, migration, …)
```

#### Таблица паттернов

| Вопрос | Если «да» | Паттерн | Пример |
|--------|-----------|---------|--------|
| Разные ряды по срезу? | Да | **Variant** | ИПЦ ×4; жильё ×2; ставки ×3 |
| Несколько представлений одного ряда? | Да | **View-mode** (`?mode=`) | `exports` + `exports-yoy` |
| Срез × богатые режимы? | Да | **Variant + уровень C** | ИПЦ, жильё |
| Отрицательные значения? | Да | **`yoy_abs`** | `trade-balance` |

#### Generic-семья: природа ряда → билдер-шаблон (авто-матрица)

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

#### Прогноз нового source-индикатора: выбор стратегии по природе

Прогноз включается заданием `model_config_json.forecast_strategy` + `forecast_steps>0` в `seed_data.py` И регистрацией кода в соответствующем сете `backend/tests/test_forecast_policy.py` (whitelist `ALL_FORECAST_CODES` — иначе тест `test_only_approved_or_derived_forecasts_are_enabled` падает). После seed — retrain (`backend/scripts/retrain-all-monthly-auto.py --codes <code>`; в контейнере — `/app/scripts/retrain-all-monthly-auto.py`), он каскадно протянет прогноз в derived sibling'ы (`derived_forecast.source_code==base`).

| Природа базового ряда | Стратегия | Когда |
|---|---|---|
| Месячный source (любой) | `monthly_auto` | ADF-автотрансформ + multi-window OLS. Дефолт для всех месячных. |
| Квартальный **положительный** трендовый (поток/запас в деньгах) | `generic_quarterly` | exports, imports, external-debt. Переиспользует log-diff методологию семейства ВВП. **Только ряды без смены знака** (log требует >0). |
| Квартальный с собственным notebook'ом руководителя | bespoke (`gdp_*_quarterly`, `housing_quarterly`, `ppi_monthly`) | ВВП, жильё, ИЦП. |
| Индекс цен (CPI-семья) | `cpi_combined` / `approved` | bespoke декомпозиция food/nonfood/services. |
| Недельная инфляция | `generic_ols` | короткий OLS-горизонт. |
| Derived от forecastable базы | `derived_from_source` | yoy/qoq/mom/агрегаты — прогноз протягивается из базы через pipeline. |
| **Крипта / биржевые котировки / периодичность < месяца** | **нет прогноза** (`forecast_steps=0`) | Правило созвона: «предсказывать курс биткоина — профанация». |
| **Квартальный знаковый** (сальдо/счёт/дефицит) | **пока нет generic-стратегии** | log-diff неопределён. `trade-balance` → тождество `exports_fc − imports_fc` (нужна 2-source инфра); прочие → level-diff модель. Не подключать наивную модель. |

#### Антипаттерны (не делать)

| Ошибка | Почему плохо | Правильно |
|--------|--------------|-----------|
| Два переключателя: variant «Индекс/YoY» **и** `ViewModePicker` | Дублирование осей | YoY только в `?mode=`, variant только по **срезу** |
| **Г/г** отдельной верхней кнопкой | Не как у ИПЦ | Г/г внутри «К прошлому периоду» |
| `viewModeFamilies` для жилья/ИПЦ | Не тянет группы и resolve | `housingViewMode*` / `cpiViewMode*` |
| Один `?mode=` на целую группу кнопок | Баг навигации 2026-05 | У каждой листовой кнопки свой mode |
| Одинаковый график, разные подписи | Ломает инвариант «режим = ряд» | Отдельный derived / source code |
| Копировать 10 режимов ИПЦ на квартальный ряд | Нет данных в источнике | Только группы с реальным рядом |
| CPI `getViewModeContent` без guard | Methodology leak (ADR-0006) | `isXxxFamily(code)` в семейном модуле |
| Отдельные карточки каталога на каждый YoY | SEO-зоопарк | Скрыть derived, каноникал + `?mode=` |

#### Алгоритм работы агента (кратко)

1. **Источник** — `docs/data_sources.md` + docstring парсера: что публикует Росстат, частота, что считаем derived.
2. **Паттерн** — decision tree выше → уровень A / B / C.
3. **Матрица режимов** — фаза A; согласовать с продуктом при неясности.
4. **Backend** — фаза B (source + derived, frequency).
5. **UI** — фаза C (нужные файлы по уровню).
6. **Контент + SEO + прогноз** — фазы D, E, F.
7. **Полировка** — фаза G; §8 локально.

---

### 1. Фаза A — Аудит карточки и инвентарь

**Цель:** таблица режимов; gaps зафиксированы.

- [ ] **Стартуй с готового аудита:** блок `completeness` в `docs/indicator-index.json` (+ срез в `docs/indicator-index.md`) — для корня уже посчитана матрица `present`/`expected`/`missing` {тип × частота} и 4 измерения паспорта (тексты/прогноз/группировка/seo). Это детерминированная замена ручной таблице ниже. Модель — `CONTEXT.md::Матрица представлений`, генератор — `scripts/completeness.py`.
- [ ] `frontend/src/pages/IndicatorDetail.jsx` — `VariantGroupPicker`, `ViewModePicker`, `CpiIndicatorControls`, `HousingIndicatorControls`.
- [ ] Таблица: **режим UI → code БД → частота → derived? → прогноз?**
- [ ] `INDICATOR_HIDDEN_FROM_LISTING` в `indicator_seo.py` — витрина vs режимы.
- [ ] Gaps в `docs/backlog.md`.

**DoD:** нет режима без ряда; паттерн §0 выбран.

---

### 2. Фаза B — Данные и backend

**Цель:** у каждого режима свой ряд.

#### 2.1 Source

- [ ] `docs/data_sources.md` + docstring `*_parser.py`.
- [ ] `seed_data.py`, `frequency` = фактическим точкам.
- [ ] ETL может наполнять несколько рядов за прогон.
- [ ] Source-depth → `*_historical.py` (`AGENTS.md` §1).

#### 2.2 Derived

- [ ] `derived_ops.py` + `DerivedSpec` в `calculation_engine.py`.
- [ ] `seed_data.py`, derived скрыты из каталога.
- [ ] `pytest` derived_ops / calculation_engine.

#### 2.3 Инварианты

- [ ] Frequency consistency (`CONTEXT.md`).
- [ ] Разные UI-режимы = разные codes (ИПЦ: `step-weekly` vs `period-weekly`).
- [ ] `rebuild-all-derived.py` после правок.

**DoD:** API `/data` — разные кривые для спорных пар; `check-all` зелёный.

---

### 3. Фаза C — UI

#### Уровень C — ИПЦ (максимум)

- [ ] `indicatorVariants.js` — «Состав» (4 кода).
- [ ] `cpiViewModeGroups.js` — 4 верхние группы + подрежимы.
- [ ] `cpiViewModeResolve.js` — каждый `mode` → свой `dataMode`.
- [ ] `useIndicatorViewModeData.js` — data + forecast по `chartMode`.
- [ ] `CpiViewModePicker.jsx`, `CpiIndicatorControls.jsx`.
- [ ] `IndicatorChartSection.jsx` — ветки по `chartMode`.

#### Уровень C — жильё (эталон проще)

- [ ] `indicatorVariants.js` — «Рынок жилья».
- [ ] `housingViewModeGroups.js` — **К прошлому** (к/к, г/г) | **Индекс**.
- [ ] `housingViewModeResolve.js`, `housingViewModeContent.jsx`, `HousingIndicatorControls.jsx`.
- [ ] Подключение в `IndicatorDetail.jsx` (как CPI).

#### Уровень A / B

- [ ] A: только `indicatorVariants.js` + `VariantGroupPicker`.
- [ ] B: `viewModeFamilies.js` + `ViewModePicker`.
- [ ] Тесты: `cpiViewModeGroups.test.js`, `viewModeFamilies.test.js`, семейные `housing*`.

#### UX (любой variant)

- [ ] Сохранение `?mode=` при смене среза.
- [ ] `defaultSubModeForGroup` — осмысленный дефолт (не «первая кнопка в DOM»).

**DoD:** график = подпись режима; оси не сбрасывают друг друга.

---

### 4. Фаза D — Контент

- [ ] `*ViewModeContent.jsx` + titles для графика/таблицы.
- [ ] Guard `isXxxFamily(code)`.
- [ ] [methodology-language.mdc](../.cursor/rules/methodology-language.mdc).
- [ ] Ревью всех **срез × режим** (ИПЦ 40; жильё 6).
- [ ] Тесты контента семейства.

**DoD:** каждая комбинация описывает **этот** ряд.

---

### 5. Фаза E — SEO

- [ ] Каноникал на листинговые URL; режимы — `?mode=`.
- [ ] `seo_title` / `seo_description` / `seo_blocks` в `indicator_seo.py` — **уникально по срезу**.
- [ ] `scripts/seo-audit.py`; `IndicatorSeoBlocks.jsx`.

**DoD:** SSR title/description осмысленны на каждой витрине.

---

### 6. Фаза F — Прогнозы

- [ ] `forecast_strategy` + `derived_from_source` в sync с `derived_ops`.
- [ ] Retrain: source → dependents; после деплоя `--forecast-only` + **`redis FLUSHDB`**.
- [ ] Фронт: forecast только на `chartMode`.

**DoD:** `/forecast` не null для derived режима; кривая на графике в той же шкале.

---

### 7. Фаза G — Полировка

- [ ] Мобильный H1, плотность блоков.
- [ ] `relatedIndicatorCardCopy` для variant-группы.
- [ ] Ссылки «Источник» по матрице режимов.
- [ ] Браузер-snapshot (`docs/workflow.md`).

---

### 8. Операционный рецепт (после фаз C–G)

Выполнять **самостоятельно**:

```bash
docker compose build backend frontend
docker compose up -d backend frontend

docker compose exec backend python seed_data.py
docker compose cp scripts/rebuild-all-derived.py backend:/app/rebuild-all-derived.py
docker compose exec backend python /app/rebuild-all-derived.py
docker compose exec backend python seed_data.py --forecast-only

docker compose exec redis redis-cli -a changeme FLUSHDB
```

```bash
./scripts/check-all.sh
curl -s "http://127.0.0.1:8000/api/v1/indicators/<code>/data?limit=3"
curl -s "http://127.0.0.1:8000/api/v1/indicators/<code>/forecast"
```

См. `CONTEXT.md` (Asset-hash, Browser-cache, Forecast retrain).

---
