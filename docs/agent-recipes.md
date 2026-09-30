# Рецепты изменения каталога и индикаторов

**Актуализация:** 2026-09-30. Перенесено из прежнего AGENTS с сохранением обязательных рецептов владельца. Полная история — [архив исходника](code-review/source-documents/AGENTS-before-knowledge-workflow-2026-09-30.md); актуальные механизмы и причины — [архитектура](architecture.md), [контракты](data-contracts.md), [playbook](indicator-family-playbook.md) и ADR. Числа и старые URL в датированной истории не являются текущими настройками.

Canonical: `/russia/indicator/{code}`, `/russia/category/{slug}`, `/{country}/indicator/{code}`. Legacy URL сохраняются через редиректы. Годовые страницы входят в sitemap; блок ссылок на каждый год на основной карточке отменён 27 сентября.

## Слои индикатора (актуальный механизм каждого)

Индикатор «прошивает» все слои; у каждого один канонический механизм. Перед
правкой найди слой, правь его механизм:

| Слой | Актуальный механизм (правится тут) |
|------|-------------------------------------|
| данные/парсер | `PARSER_REGISTRY` + `backend/app/services/*_parser.py` (internals — в docstring парсера) |
| derived | `DERIVED_SPECS` (`calculation_engine.py`) + чистые ops в `derived_ops.py` |
| прогноз | `forecast_strategies/registry.py` (`model_config_json.forecast_strategy` в БД) |
| отрисовка/view-mode | **generic** config-движок: `view_model_families.py` → `viewModelFamilies.generated.json` → `viewModeEngine.js` → `GenericIndicatorView`. Bespoke (`cpi`/`housing`/`ppi`) — только эти 3 семьи |
| seo | `app/data/indicator_seo.py` (curated) + `seo_content.py` (категории) + `seo_renderer.py` (SSR); остальное (sitemap/og/rss) — авто из БД |
| листинг | `INDICATOR_HIDDEN_FROM_LISTING` в `indicator_seo.py` → `seed_data.py` (флаг `is_listed`) |

## FAST-PATH — задача про индикатор X?

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

## FAST-PATH — новая КАТЕГОРИЯ (раздел каталога)?

Категория — это не индикатор, а полка каталога: значение `Indicator.category` в
БД + карточка в меню/футере + SSR-SEO страницы `/category/<slug>`. Шесть
обязательных точек касания (эталон — добавление «Индексы»/«Товарные рынки»,
2026-06-25). `<slug>` латиницей, `<api_category>` — точное русское имя в seed:

1. **Frontend-карточка** — `frontend/src/lib/categories.js::CATEGORY_DEFS` → `CATEGORIES`: объект
   `{ slug, name, nameEn, icon, apiCategory, status:'active', flagshipCode,
   sentiment, description, seoTitle, seoDescription, relatedSlugs }`.
   RU SEO-поля подмешивает `withCategorySeo` из generated-зеркала backend;
   после правки `CATEGORY_META` обновить `scripts/export-page-meta.py`.
   Ручные EN-поля также сверять с backend. Источник механизма — `lib/pageMeta.js`.
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

---

## FAST-PATH — новый ИНДИКАТОР (канонический рецепт владельца)

Диктовка владельца (звонки 2026-06; дословно «по такому рецепту мы будем
добавлять новые индикаторы»). Любой новый ряд обязан пройти ВСЕ пункты — иначе
карточка выглядит «сделано студентом». Детальный 8-пунктный чеклист с trap'ами —
в дополнительных проверках ниже; здесь — что именно требует владелец, в его формулировках:

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


## Дополнительные проверки отдельного кода

### Чеклист «новый индикатор» (КРИТИЧНО)

Перед добавлением **любого** нового индикатора (source-парсер, derived, manual seed) пройти все проверки. Без них вероятен один из задокументированных trap'ов из `CONTEXT.md::Operational invariants and traps`. См. ADR-0006 «Indicator card unification».

| # | Проверка | Что делаем |
|---|----------|------------|
| 1 | **Source-depth invariant** | Какую максимальную глубину истории даёт источник? Если в seed_data залит **меньший** ряд — заводим `<name>_historical.py` immutable seed (как `housing_historical.py`, `refinancing_rate_historical.py`, `wages_historical.py`). НЕ оставляем огрызок. |
| 2 | **Frequency consistency** (КРИТИЧНО) | Перед `bulk_upsert` сверить `target.frequency` с фактической частотой добавляемых точек. Если расхождение (annual → monthly indicator) — заводим **отдельный sibling indicator** с правильной `frequency` и `is_listed=false`, добавляем режим в generic FamilyDef либо в существующий bespoke resolve. См. trap `Annual-in-monthly mixing` в `CONTEXT.md`. |
| 2b | **Initial ETL trigger** | Закрыто автоматикой в `app/main.py::_catch_up_empty_indicators()` — при startup backend сам триггерит ETL для всех source-индикаторов с 0 точек. После deploy с новым indicator достаточно `docker compose up -d backend` — данные подтянутся в фоне. Если в логах `Startup catch-up: <code> failed: ...` — источник битый, чинить парсер. См. trap `New indicator initial ETL trap` в `CONTEXT.md`. |
| 3 | **View-mode family оценка** | Если ряд > 100 точек и есть осмысленные derived'ы (YoY/QoQ/MoM/aggregation) — заводим **одной строкой `FamilyDef`** в config-driven источнике `backend/app/data/view_model_families.py::_FAMILY_DEFS` (билдер по природе ряда сам развернёт полную матрицу {тип × частота}, включая многоуровневую Г/г через `_yoy_modes`; sibling-ряды авто-seed + авто-скрыты, тексты авто, прогноз авто-протягивается). Выбор шаблона по природе — таблица в [`docs/indicator-family-playbook.md`](indicator-family-playbook.md)::«Generic-семья: природа ряда → билдер-шаблон». **Не** отдельная карточка каталога; derived скрыты автоматически. Легаси `frontend/src/lib/viewModeFamilies.js` — только для немигрированных bespoke-остатков. |
| 4 | **Variant decomposition** | Если индикатор имеет варианты по срезу (срок, регион, подгруппа, тип) — это **разные индикаторы со своими рядами** → `VariantGroupPicker` (см. `lib/indicatorVariants.js`). Не путать с view-mode (один ряд, разные представления). |
| 5 | **Negative-capable check** | Если значения могут быть отрицательными (`trade-balance`, `current-account`, `budget-deficit`, `*-migration`) — использовать `yoy_abs` (разница в единицах источника), **не** `yoy_pct` (% от базы с переходом через ноль = визуальный мусор и тысячи процентов). |
| 6 | **Frequency strategy** | Daily-индикатор: aggregation (week/month/quarter/year avg) — `applyAggregateTransform` на фронте, **backend derived не заводим**. Monthly counterpart существующего quarterly — отдельный индикатор с MoM%-режимом через виртуальный `transform: 'mom'`. |
| 7 | **Listing visibility ≠ searchability** | Если индикатор скрыт из каталога (`is_listed=false` через `INDICATOR_HIDDEN_FROM_LISTING`) — он всё равно ищется через `?include_unlisted=true` в `IndicatorSearch.jsx`. Search haystack включает `seo_keywords` — в новом индикаторе всегда задаём osmysленные ключевые корни на русском (зарпл/инфля/безраб и т.п.). |
| 8 | **SEO-автоматика — ничего руками** | Sitemap (lastmod/priority), related-блоки, годовые landing'и `/indicator/{code}/{year}`, OG-превью `/og/{code}.png`, RSS `/feed.xml`, IndexNow-пинг — всё подтянет новый индикатор из БД само (ADR-0003 «Subsequent additions», `CONTEXT.md::SEO meta bundle`). Единственное ручное: curated `seo_keywords` + `seo_title`/`seo_description` в `app/data/indicator_seo.py` (иначе сработает generic fallback). При смене дизайн-токенов фронта — синхронизировать `SEO_CRITICAL_CSS` в `seo_renderer.py`. |

**После прохождения чеклиста** — обновить `seed_data.py` + соответствующие mappings (variant/view-mode), прогнать `./scripts/check-all.sh`, обновить `CONTEXT.md::Operational invariants and traps` если открыли новую trap.
