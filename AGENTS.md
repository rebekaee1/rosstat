<!-- ============================================================ -->
<!-- FAST-PATH (feature/indicator-index, 2026-06-24)              -->
<!-- ============================================================ -->

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
2. **Запись `X` в [`docs/indicator-index.json`](docs/indicator-index.json)** —
   `ui_stack`, `parser_type`, `forecast_strategy`, `derived_siblings`, `is_listed`,
   `flags`. Человекочитаемо — [`docs/indicator-index.md`](docs/indicator-index.md).
3. **Правь механизм нужного слоя** (таблица выше) / для UI — стек из `ui_stack`:
   `generic` → `view_model_families.py` (+ regen) / `cpi|housing|ppi` → bespoke
   `frontend/src/lib/{cpi,housing,ppi}ViewMode*` / `variant` → `indicatorVariants.js`.
4. **Доведи данные до UI** — [`.cursor/rules/indicator-data-delivery.mdc`](.cursor/rules/indicator-data-delivery.mdc).
5. `./scripts/check-all.sh` (регенерирует карту + guard `--check`).

> **`flags.shadowed_legacy` / `in_both_viewmode_systems` — НЕ «можно удалять».**
> Флаг значит лишь, что standalone-ветка рендера в `IndicatorDetail.jsx` перекрыта
> generic. Сам легаси-файл обычно ЖИВОЙ: его content/resolve переиспользуются
> общими секциями (chart/table title, picker, data-resolve) и держат
> canonical-редиректы старых индексируемых URL (`*-yoy-abs`,
> `unemployment-quarterly/-annual` — движком не покрыты). Расследование и почему
> это НЕ delete-list — [`docs/dead-code-report.md`](docs/dead-code-report.md).
> Удаление редиректа = тихая просадка SEO, тесты не ловят → ЭСКАЛАЦИЯ.

Карта детерминированная, регенерируется в `check-all.sh`
(`scripts/build-indicator-index.py`, guard `--check`). Объективный список файлов —
[`docs/repo-inventory.md`](docs/repo-inventory.md).

> **Полнота индикатора = матрица {тип × частота}** (эталон — переключатель ИПЦ).
> Какие представления у `X` есть/чего не хватает — блок `completeness` в
> [`docs/indicator-index.json`](docs/indicator-index.json) + срез в
> [`docs/indicator-index.md`](docs/indicator-index.md) (модуль
> `scripts/completeness.py`). Доменная модель — `CONTEXT.md::Матрица представлений`.
> Это аудит-карта (read-only): пробел = кандидат на режим, не дефект.

## FAST-PATH — новая КАТЕГОРИЯ (раздел каталога)?

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

---

## FAST-PATH — новый ИНДИКАТОР (канонический рецепт владельца)

Диктовка владельца (звонки 2026-06; дословно «по такому рецепту мы будем
добавлять новые индикаторы»). Любой новый ряд обязан пройти ВСЕ пункты — иначе
карточка выглядит «сделано студентом». Детальный 8-пунктный чеклист с trap'ами —
в `Шаг 4` ниже; здесь — что именно требует владелец, в его формулировках:

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
   агрегаторов. Точная карта `URL/endpoint` — `docs/data_sources.md` + docstring
   парсера.
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

---

# AGENTS.md — точка входа для AI-агента

**Last updated:** 2026-07-03, вечер (DS-датасет расширен до трёх слоёв — ADR-0009 «Subsequent additions»: (1) retention поведенческого сырья ОТМЕНЁН (`behavior_raw_retention_days=0`, копим без удаления под Big Data/ML — директива владельца); (2) слой привлечения `metrika_acquisition.py` — ежедневный синк 08:20 МСК: повизитная выгрузка Logs API → `raw_metrika_visits` (фраза/источник/поисковик/реферер/UTM/гео/устройство/цели, 28 полей) + агрегаты Reporting API (traffic_sources/search_engines/referrers/ad_campaigns снапшоты, `metrika_search_phrases`, `metrika_daily_page_metrics`), Пульс-секция `acquisition` + `metrika_visits`/`metrika_ad_visits` в трендовой памяти; (3) булев слой знаний — таблица `hypotheses` (Alembic `20260703_hypotheses`): LLM-аналитик Пульса ведёт проверяемые гипотезы (вердикт true/false/открыта + confidence) через структурированный хвост ответа, кнопки бота «Датасет» (инвентаризация: строки/параметры/JSON-ключи по слоям, `dataset_inventory.py`) и «Гипотезы». Ранее 2026-07-03: ADR-0009 поведенческий поток first-party: `behavior.js` — автосбор без разметки (pageview на роут, каждый клик с иерархическим путём элемента + dead/rage-признаки, сэмплированная траектория мыши, dwell со скролл-глубиной, copy) → батчи `sendBeacon` на `/api/v1/analytics/behavior` → таблица `behavior_events` (Alembic `20260703_behavior`); дневные агрегаты в Пульс-снапшоте `snap["behavior"]` (топ страниц/кликов, dead/rage, dwell по страницам, копируемое) уходят LLM-ассистенту; прод переехал на 201.51.11.170 — DNS переключён, Caddy выпустил сертификат, Пульс включён с OpenRouter-ключом, телеграм-роутинг: дайджест владельцу+skrakan, realtime-алерты только владельцу, кнопки/CSV обоим (`interactive_authorized_ids`). Ранее 2026-07-02: региональный блок 2.0 + «Пульс» + auth: интерактивная SVG-карта регионов (choropleth, `RegionsMap.jsx` + `scripts/regional/build_map_paths.py`), сравнение регион-регион и dual-axis «— Россия» на карточке, экспорт CSV/Excel/PNG региональных рядов (auth-only) с watermark `forecasteconomy.com` везде, региональные ряды в /compare (`r:{slug}:{code}`), SEO-тексты+FAQ (JSON-LD) для ~38k региональных страниц, кросс-линки макро↔регионы (`RegionCrossLink`, `MACRO_BY_TABLE`), недельные цены на топливо с HTML-бюллетеня; **сессии изолированы от кэша** — state-Redis DB 1 (`get_state_redis`; sessions/lockout/quota/oauth-state), деплойный FLUSHDB больше не разлогинивает, sliding cookie через `/auth/me` (ADR-0007 Subsequent additions); **мониторинг «Пульс»** — дневные снапшоты всего (users/events/поиск/скачивания/ошибки/ETL) в Redis TTL 8 дней, LLM-отчёт через OpenRouter → Telegram владельцу, getUpdates-поллер с inline-кнопками (таблица/CSV пользователей, карточка-аналитика) — `services/{pulse,pulse_report,telegram_bot}.py`; почта `rebeka.ee@yandex.ru`. Плюс слитая с main работа 2026-07-01: ветка `feat/compare-view-modes`, локально: страница методологии прогнозирования `/methodology` — `frontend/src/pages/Methodology.jsx` + SSR `PAGE_META["methodology"]` + nginx-роут + help-подсказка у переключателя «Прогноз» на карточке (`IndicatorChartSection` → событие `methodology_click`); режим сравнения — второй проход по дефектам: безопасный ребейз «Общая база (=100)» (`isIndexableBase` — знакопеременные/%-ряды не индексируются, показываются нотой; снята коллизия «Индекс»-шкала vs «Индекс»-представление; подсказка при 3+ единицах); per-ряд переключатель представления Индекс·К прошлому периоду·К году через универсальный резолвер `frontend/src/lib/compareRepresentation.js` (generic sibling-коды из `viewModelFamilies.generated.json` + bespoke %-коды cpi/ppi/housing + client-transform'ы `sub100`/`mom`/`cpiCumulative`; накопленный индекс ИПЦ вынесен в общий `cpiCumulativeIndex.js`); прогнозы 5 квартальных баз (capital-investment/services-exports/services-imports/gdp-investment → generic_quarterly, fdi-net → signed_quarterly); annual-in-quarterly фикс `housing-qoq` через op `qoq_adjacent`; `wages-nominal-annual` автопродолжается движком (op `annual_mean_with_prefix`, ручной backfill-скрипт удалён) + gap-fill дыры 2022-12; +32 seo_keywords; About e-mail сотрудничества → rebeka.ee@yandex.ru. Детали — `docs/backlog.md`, ADR-0001 «Subsequent additions», `CONTEXT.md::Annual-in-quarterly trap`. Ранее 2026-06-30 (прогноз «К прошлому периоду» (М/м·Кв/Кв) ВОССТАНОВЛЕН для всех generic-семей с прогнозируемой месячной/квартальной базой (~140 кодов): derived от прогноза базы тем же generic-pipeline, что считает факт (mom поверх месячного прогноза; qoq — q/q на суммах/уровнях кварталов, неполный хвостовой квартал отбрасывает `_aggregate`); ранее был глобально отключён в `_mode_forecastable`/`_mode_forecast_meta` (созвон 2026-06-30: пустой тоггл «к прошлому периоду» во всех семьях — баг). weekly-базы (international-reserves, топливо) остаются без mom/qoq-прогноза (propagate-freq отсекает). 2026-06-25 (вечер: топливо переведено с недельного прогноза на месячный — `monthly_forecast` в `view_model_families`: avg-month → monthly_auto, квартал/год протягиваются из месячного; разделы ИПП (добыча/обработка/энергетика/водоснабжение) выведены отдельными карточками в «Бизнес и инвестиции» (variant-группа сохранена); «Индексы»→«Биржевые индексы», бензин→«Цены на бензин АИ-92/95», дизель→«Цена дизельного топлива», группа→«Цены на топливо»; OG-картинки переделаны в area-график (подписи осей в гаттерах, watermark); добавлен вечерний ETL-прогон 20:00 МСК + IndexNow; «О проекте» переписана (Росстат/ЦБ/Минфин, 100+ индикаторов); компаре-нудж «хотите больше двух — зарегистрируйтесь»; `scripts/verify-data-loaded.py`. Ранее: картинка-график индикатора теперь встроена ВИДИМЫМ `<img class="seo-chart">` в тело SSR + `ImageObject` + `og:image` — Алиса/Нейро берут график прямо из DOM страницы, не только из мета; картинка получила подписи осей min/max и крайние даты периода; **реальная зарплата `wages-real` выведена отдельной карточкой в категорию «Рынок труда»** — больше не скрыта, но остаётся в variant-группе «Заработная плата» переключателем с номинальной. Ранее: реализованы поголовые годовые OG-картинки `/og/{code}/{year}.png` + `ImageObject`-разметка годовых landing'ов для Алисы/Нейро; anti-orphan-инвариант для `is_listed=false`; реальная зарплата объединена со средней в variant-группу «Заработная плата» + собственная T8-семья + «О показателе» + прогноз + годовая частота 1991+; компаре-поиск трекает спрос с числом результатов; новые цели Метрики задокументированы в `analytics_api_inventory/frontend_instrumentation.md`. Ранее: добавлен FAST-PATH «новый ИНДИКАТОР» — канонический 9-пунктный рецепт владельца + автозанос в поиск + спецификация материалов для Яндекс.Алисы; ИПП объединён в variant-группу «Состав промышленного производства» (общий + 4 раздела), топливо — в «Автомобильное топливо» (АИ-92/95/дизель); «О показателе» заведены для ИПП-разделов и топлива (DRY-билдеры); глобальный поиск и поиск сравнения листают весь каталог без «топ-N»; экспорт картинки графика — фон из реальной светлой темы (фикс тёмного PNG), правило watermark унифицировано «гость ⇒ знак, зарегистрирован ⇒ чисто». Ранее: FAST-PATH «новая КАТЕГОРИЯ» — 6 точек касания; категории «Индексы»/«Товарные рынки»; крипта ETH/SOL; гостевой лимит выгрузок = 0).

Запись о региональном bounded context (ADR-0008): **региональный блок реализован локально** — ADR-0008: bounded context `регион × показатель × год` (модели `Region`/`RegionIndicator`/`RegionDataPoint`, Alembic `20260702_add_regional_tables`), данные из закоммиченного артефакта `backend/app/data/regional/` (сидер `seed_regional.py` в entrypoint, вне ETL-планировщика); пайплайн артефакта `scripts/regional/`: Excel 2025 → Excel 2023/2022 (исключённые показатели, разделы 21 «Внешняя торговля») → Word-редакции через LibreOffice (раздел 22 «Правонарушения» 1990–2018, продление 24 рядов в 1990-е с кросс-сверкой overlap ≤ 5%); 489 показателей × 96 территорий = 960 926 точек; API `/api/v1/regions*`, UI `/regions` → `/region/{slug}` → `/region/{slug}/{code}`, SSR `/seo/region*` + sitemap + OG `/og/region/*`; карта источников — `docs/data_sources.md::Региональный блок`. Ранее 2026-06-30: прогноз «К прошлому периоду» (М/м·Кв/Кв) ВОССТАНОВЛЕН для всех generic-семей с прогнозируемой месячной/квартальной базой (~140 кодов): derived от прогноза базы тем же generic-pipeline, что считает факт (mom поверх месячного прогноза; qoq — q/q на суммах/уровнях кварталов, неполный хвостовой квартал отбрасывает `_aggregate`); ранее был глобально отключён в `_mode_forecastable`/`_mode_forecast_meta` (созвон 2026-06-30: пустой тоггл «к прошлому периоду» во всех семьях — баг). weekly-базы (international-reserves, топливо) остаются без mom/qoq-прогноза (propagate-freq отсекает). 2026-06-25 (вечер: топливо переведено с недельного прогноза на месячный — `monthly_forecast` в `view_model_families`: avg-month → monthly_auto, квартал/год протягиваются из месячного; разделы ИПП (добыча/обработка/энергетика/водоснабжение) выведены отдельными карточками в «Бизнес и инвестиции» (variant-группа сохранена); «Индексы»→«Биржевые индексы», бензин→«Цены на бензин АИ-92/95», дизель→«Цена дизельного топлива», группа→«Цены на топливо»; OG-картинки переделаны в area-график (подписи осей в гаттерах, watermark); добавлен вечерний ETL-прогон 20:00 МСК + IndexNow; «О проекте» переписана (Росстат/ЦБ/Минфин, 100+ индикаторов); компаре-нудж «хотите больше двух — зарегистрируйтесь»; `scripts/verify-data-loaded.py`. Ранее: картинка-график индикатора теперь встроена ВИДИМЫМ `<img class="seo-chart">` в тело SSR + `ImageObject` + `og:image` — Алиса/Нейро берут график прямо из DOM страницы, не только из мета; картинка получила подписи осей min/max и крайние даты периода; **реальная зарплата `wages-real` выведена отдельной карточкой в категорию «Рынок труда»** — больше не скрыта, но остаётся в variant-группе «Заработная плата» переключателем с номинальной. Ранее: реализованы поголовые годовые OG-картинки `/og/{code}/{year}.png` + `ImageObject`-разметка годовых landing'ов для Алисы/Нейро; anti-orphan-инвариант для `is_listed=false`; реальная зарплата объединена со средней в variant-группу «Заработная плата» + собственная T8-семья + «О показателе» + прогноз + годовая частота 1991+; компаре-поиск трекает спрос с числом результатов; новые цели Метрики задокументированы в `analytics_api_inventory/frontend_instrumentation.md`. Ранее: добавлен FAST-PATH «новый ИНДИКАТОР» — канонический 9-пунктный рецепт владельца + автозанос в поиск + спецификация материалов для Яндекс.Алисы; ИПП объединён в variant-группу «Состав промышленного производства» (общий + 4 раздела), топливо — в «Автомобильное топливо» (АИ-92/95/дизель); «О показателе» заведены для ИПП-разделов и топлива (DRY-билдеры); глобальный поиск и поиск сравнения листают весь каталог без «топ-N»; экспорт картинки графика — фон из реальной светлой темы (фикс тёмного PNG), правило watermark унифицировано «гость ⇒ знак, зарегистрирован ⇒ чисто». Ранее: FAST-PATH «новая КАТЕГОРИЯ» — 6 точек касания; категории «Индексы»/«Товарные рынки»; крипта ETH/SOL; гостевой лимит выгрузок = 0).

Этот файл — первое, что читает любой новый AI-агент (Cursor, Claude Code, Codex, Gemini, любой другой), подключённый к этому репозиторию. Здесь живёт **карта документации**, **режим работы** и **протокол актуализации** этих самых документов.

Задача проекта в одну строку: публичная аналитическая платформа `forecasteconomy.com` — собирает 100+ экономических индикаторов России (Росстат, ЦБ РФ, Минфин), считает derived-ряды и forecast'ы, отдаёт фронтенду + ботам + embed-виджетам.

---

## Шаг 1 — что прочесть в первую очередь

В этом порядке (5–10 минут):

1. **[`CONTEXT.md`](CONTEXT.md)** — domain glossary и архитектурный язык. **Spine**, без неё нельзя обсуждать архитектуру. Читать целиком — он сжатый.
2. **[`README.md`](README.md)** — карта стека, ключевые группы endpoint'ов, индикаторы, deploy. Высокоуровневый обзор.
3. **[`docs/data_sources.md`](docs/data_sources.md)** — точная карта «индикатор → файл/endpoint» (75 source-индикаторов). Канонический справочник, откуда тянется каждый ряд. Parser internals — в docstrings соответствующего `backend/app/services/*_parser.py`.
4. **[`docs/workflow.md`](docs/workflow.md)** — модель работы, локальный dev, ручной ETL recipe, прод-деплой, smoke C.
5. **[`docs/enterprise_resilience.md`](docs/enterprise_resilience.md)** — операционные инварианты, чеклист канарейки 6/6 (другой от чеклиста «новый индикатор» 7/7 ниже).
6. **`docs/adr/`** — архитектурные решения (нумерованные ADR, читать в порядке номеров):
   - `0001-derived-indicators-engine-shape.md` — engine shape derived (29 specs + 10 pure ops + 2 client-side transforms).
   - `0002-derived-always-reflects-source.md` — инвариант идемпотентности `bulk_upsert`.
   - `0003-seo-single-source-server-rendered.md` — SSR через backend, asset discovery от Vite shell.
   - `0004-rosstat-russian-canonical-sdds-deprecated.md` — Rosstat русский canonical, SDDS English deprecated. Migration pattern + pilot evidence (gdp-nominal, 2026-05-10).
   - `0005-official-calendar-source-bound.md` — public calendar только official dates с provenance; estimated скрыты.
   - `0006-indicator-card-unification.md` — ось декомпозиции «карточка vs derived vs variant vs frequency» + 7-проверочный чеклист «новый индикатор» (звонок 2026-05-22 + ревизия).
 - `0007-identity-user-accounts.md` — личный кабинет Phase 1: идентичность (User/OAuthIdentity/EmailCredential), сессии в Redis, OAuth (Яндекс/VK/email, без Authlib), резолв против pre-hijack, 152-ФЗ. Alembic-ревизия `20260619_identity`. Boevые OAuth-креды — pre-prod чеклист в ADR.
 - `0008-regional-bounded-context.md` — региональный блок: отдельный bounded context `регион × показатель × год`, артефакт вместо ETL (сборник «Регионы России», обновление раз в год), дособор из архивных редакций 2003–2023, без прогнозов/derived.
 - `0009-behavior-stream-first-party.md` — поведенческий поток first-party («видеокамера»): `behavior.js` автосбор без разметки (pageview/click/move/dwell/copy, dead/rage-клики) → батчи в `behavior_events`; retention сырья 90 дней, дневные агрегаты в Пульс-снапшотах вечные; не смешивать с бизнес-событиями `track.js`/`frontend_events`.

После этих файлов агент способен ответить на ~90% вопросов и делать осмысленные правки.

---

## Шаг 2 — где искать конкретное

| Вопрос | Файл/папка |
|--------|------------|
| Как работает парсер X? | **docstring** `backend/app/services/<X>_parser.py` (canonical: source URL, лист, row/col mapping, `model_config_json` schema, traps) + `CONTEXT.md::Parser` (template-method обзор `BaseParser`) |
| Откуда берётся индикатор X? | **[`docs/data_sources.md`](docs/data_sources.md)** — точный URL/файл/endpoint по каждому из 75 source |
| Какие источники, кроме Росстата? | [`docs/data_sources.md`](docs/data_sources.md) (полная карта для всех 75 sources, включая CBR + Минфин) + docstrings парсеров `backend/app/services/{cbr_*,minfin_*}_parser.py` |
| Как считается derived-индикатор Y? | `DERIVED_SPECS` в `backend/app/services/calculation_engine.py` + ADR-0001 |
| Какая стратегия forecast у индикатора Z? | `Indicator.model_config_json.forecast_strategy` в БД + реестр `backend/app/services/forecast_strategies/registry.py` + таблица в `CONTEXT.md::Forecast` |
| Как собирается SEO/мета? | `backend/app/services/seo_renderer.py` + `seo_content.py` + ADR-0003 |
| Какие endpoints есть в API? | Swagger `/api/docs` (только при `DEBUG=true`, на проде отключён) + краткая сводка групп в `README.md::API` |
| Yandex Metrika / Webmaster | [`docs/analytics_api_inventory/`](docs/analytics_api_inventory/) — каждый файл начинается со status block (`partial` / `implemented` / `planned`) |
| Что менять при правке UI? | `frontend/src/...` + `docs/workflow.md::Браузерная проверка` (cursor-ide-browser + headless E2E) |
| Какие traps подстерегают? | Раздел «Operational invariants and traps» в `CONTEXT.md` (12 пунктов) |
| Что мы НЕ извлекаем из источников? | [`docs/missed_data_audit.md`](docs/missed_data_audit.md) — TOP-25 P0-индикаторов, доступных без новых источников |
| Какие правки в работе прямо сейчас? | [`docs/backlog.md`](docs/backlog.md) — живой бэклог: ID/затронутые файлы/риски/приоритет. Источник — звонки с Никитой |
| Как довести **семейство** индикаторов (не один код)? | **[`docs/indicator-family-playbook.md`](docs/indicator-family-playbook.md)** — продуктовая модель + фазы A–G; эталоны **ИПЦ** (макс.) и **жильё** (variant + custom view-mode); ADR-0006 + `AGENTS.md::Шаг 4` для отдельных кодов |
| Как делать прод-деплой? | `docs/workflow.md::Прод-деплой` + `enterprise_resilience.md` |

---

## Шаг 3 — режим работы

**Запреты (всегда):**
- **Не пушить на прод-сервер** (`5.129.204.194`, `/opt/rosstat`) без явной команды пользователя.
- **Не пушить на `main`** без зелёного `./scripts/check-all.sh` (pytest + lint + vitest + vite build).
- **Не редактировать `git config`**, не делать `--force` push, не амендить коммиты, которые уже на remote.
- **Не создавать новые .md файлы**, если можно обновить существующий. Документация консолидирована — фрактальная сеть выстроена; новые файлы только если возникает действительно новая категория знания.
- **Не мерджить «полу-готовое»** в `main`. Регламент канарейки 6/6 в `enterprise_resilience.md` — обязателен.
- **Не выдавать «внутренности» в публичных текстах** (`methodology`, `description`, `seo_*`, `categories.js`, любые user-visible payloads). Имена файлов источников, parser-жаргон, API-id, ADR-ссылки, координаты Excel — всё это живёт в `docs/data_sources.md`, docstrings парсеров и `CONTEXT.md`, а не на сайте. Полное правило — [`.cursor/rules/methodology-language.mdc`](.cursor/rules/methodology-language.mdc).

**Стандартная сессия:**
1. Понять, на каком уровне работаешь: оперативная правка (`fix/...`, `feat/...`) vs архитектурный кандидат (`refactor/...`, требует ADR).
2. Прочесть релевантные файлы из таблицы выше.
3. Сделать правку. Прогнать локальные проверки (`./scripts/check-all.sh`).
4. Если правка касается UI — обязательно браузер-snapshot через `cursor-ide-browser` (см. `docs/workflow.md::Браузерная проверка`).
5. Закоммитить **только** по явной команде пользователя.

**Доступные ресурсы:**
- `scripts/check-all.sh` — CI-эквивалент.
- `scripts/sync-local-from-prod.py` — read-only sync с прода.
- `scripts/rebuild-all-derived.py` — полный пересчёт derived (после правок `derived_ops.py` или `DERIVED_SPECS`).
- `scripts/seo-audit.py` — проверка SSR-meta на ключевых URL.
- `scripts/pg-backup.sh` — бэкап перед прод-деплоем.

---

## Шаг 4 — протокол актуализации документации (КРИТИЧНО)

**Документация — это код**. При архитектурных изменениях агент **обязан** актуализировать соответствующие файлы. Без этого фрактальная система деградирует, и следующий агент будет работать со stale-картой.

### Правила обновления

| Изменение в коде | Куда писать |
|------------------|-------------|
| **Любое изменение источника данных** (URL, имя файла, sheet, dataservice блок, file template) | **`docs/data_sources.md`** — single source of truth «индикатор → актуальный файл/endpoint» + **docstring** парсера `backend/app/services/<name>_parser.py` (parser-internals: source URL, layout, schema конфигурации, traps). ОБЯЗАТЕЛЬНО при любой правке парсера или `model_config_json` |
| Новый source-парсер (Rosstat/CBR/Минфин/иной) | `docs/data_sources.md` (per-indicator маппинг) + docstring парсера в `backend/app/services/<name>_parser.py` (canonical parser-internals) + регистрация в `PARSER_REGISTRY` + строка в `seed_data.py`. `CONTEXT.md::Parser` обновлять только если меняется обзорное число парсеров. |
| Новый derived-индикатор | `DERIVED_SPECS` в `calculation_engine.py` + `seed_data.py` + раздел в `CONTEXT.md::Derived indicator` (счётчики и категории) |
| Новая чистая op в `derived_ops.py` | ADR-0001 (раздел «Subsequent additions») + `CONTEXT.md::Derived indicator` (список ops) |
| Новая forecast-стратегия | `forecast_strategies/registry.py` + таблица в `CONTEXT.md::Forecast` + строка в `README.md::Прогнозы` |
| Новый API endpoint | Swagger (автоматически из FastAPI route); если новая группа endpoint'ов — обновить сводку в `README.md::API` |
| Новый категория или slug | `frontend/src/lib/categories.js` **и** `seo_content.py::CATEGORY_META` (синхронно — см. ADR-0003) + строка в `README.md::Индикаторы` |
| Изменение rate-limit / CORS / CSP | `enterprise_resilience.md::API и backend` + `enterprise_resilience.md::Frontend и кэш` |
| Новая операционная trap, обнаруженная в проде | `CONTEXT.md::Operational invariants and traps` (раздел traps) |
| Новое архитектурное решение | **Создать новый ADR** `docs/adr/<NNNN>-<kebab-name>.md` (следующий свободный номер); добавить ссылку в шапку `CONTEXT.md::Документы рядом` и в `AGENTS.md::Шаг 1` |
| Новый view-mode family / variant / virtual transform | `frontend/src/lib/viewModeFamilies.js` (реестр семей) **или** `lib/indicatorVariants.js` (variants). Тест в `viewModeFamilies.test.js`. ADR-0006 «Subsequent additions» если добавляется новый паттерн (не просто новый member существующего паттерна). Крупное семейство (несколько фаз) — чеклист в [`docs/indicator-family-playbook.md`](docs/indicator-family-playbook.md) |
| Изменение существующего ADR | Не редактировать body «как если бы решение было таким». Добавить раздел «Subsequent additions (after acceptance)» с датой и описанием. Status в шапке менять только при формальной депрекации |
| Новый Yandex API client | `docs/analytics_api_inventory/<service>.md` (если файл уже есть — обновить status block) или новый файл при новом сервисе + строка в `analytics_api_inventory/README.md::Implementation status` |
| Новая roadmap-задача / правка от пользователя | `docs/backlog.md` (приоритеты + ID + затронутые файлы + риски). Когда закрыто — переносим в раздел «История» с SHA коммита. Никаких параллельных `plan.md` — всё в одном backlog. |

### Когда создавать новый ADR vs обновлять старый

**Создавать новый ADR**, если:
- Меняется фундаментальный инвариант (например, переход с monorepo на микросервисы).
- Появляется новая ось декомпозиции, которой раньше не было (например, multi-tenancy).
- Решение **противоречит** существующему ADR (тогда новый ADR должен явно депрекать старый).

**Обновлять существующий ADR (раздел «Subsequent additions»)**, если:
- Эволюция в рамках принятого решения (например, добавили `december_to_december` op в систему derived — это эволюция ADR-0001, не новое решение).
- Уточнение границ инварианта (например, формулировка «pure-revision day limitation» в ADR-0002).
- Корректировка `Last verified` даты после ревизии.

### Чеклист «я закончил архитектурную правку»

Перед тем, как считать задачу завершённой:

- [ ] Код изменён, тесты добавлены/обновлены, `./scripts/check-all.sh` зелёный.
- [ ] Если правка меняет публичный интерфейс (API, парсер, derived-список, стратегия, операция): соответствующий .md обновлён по таблице выше.
- [ ] Если решение архитектурное: новый ADR создан или существующий дополнен.
- [ ] `Last updated` / `Last verified` дата обновлена в каждом изменённом .md.
- [ ] Cross-links целы: новые ADR упомянуты в `CONTEXT.md::Документы рядом` и в `AGENTS.md::Шаг 1`.
- [ ] Браузер-snapshot, если правка задела UI.

### Чеклист «новый индикатор» (КРИТИЧНО)

Перед добавлением **любого** нового индикатора (source-парсер, derived, manual seed) пройти все 7 проверок. Без них вероятен один из задокументированных trap'ов из `CONTEXT.md::Operational invariants and traps`. См. ADR-0006 «Indicator card unification».

| # | Проверка | Что делаем |
|---|----------|------------|
| 1 | **Source-depth invariant** | Какую максимальную глубину истории даёт источник? Если в seed_data залит **меньший** ряд — заводим `<name>_historical.py` immutable seed (как `housing_historical.py`, `refinancing_rate_historical.py`, `wages_historical.py`). НЕ оставляем огрызок. |
| 2 | **Frequency consistency** (КРИТИЧНО) | Перед `bulk_upsert` сверить `target.frequency` с фактической частотой добавляемых точек. Если расхождение (annual → monthly indicator) — заводим **отдельный sibling indicator** с правильной `frequency` и `is_listed=false`, добавляем режим в `viewModeFamilies`. См. trap `Annual-in-monthly mixing` в `CONTEXT.md`. |
| 2b | **Initial ETL trigger** | Закрыто автоматикой в `app/main.py::_catch_up_empty_indicators()` — при startup backend сам триггерит ETL для всех source-индикаторов с 0 точек. После deploy с новым indicator достаточно `docker compose up -d backend` — данные подтянутся в фоне. Если в логах `Startup catch-up: <code> failed: ...` — источник битый, чинить парсер. См. trap `New indicator initial ETL trap` в `CONTEXT.md`. |
| 3 | **View-mode family оценка** | Если ряд > 100 точек и есть осмысленные derived'ы (YoY/QoQ/MoM/aggregation) — заводим **одной строкой `FamilyDef`** в config-driven источнике `backend/app/data/view_model_families.py::_FAMILY_DEFS` (билдер по природе ряда сам развернёт полную матрицу {тип × частота}, включая многоуровневую Г/г через `_yoy_modes`; sibling-ряды авто-seed + авто-скрыты, тексты авто, прогноз авто-протягивается). Выбор шаблона по природе — таблица в [`docs/indicator-family-playbook.md`](docs/indicator-family-playbook.md)::«Generic-семья: природа ряда → билдер-шаблон». **Не** отдельная карточка каталога; derived скрыты автоматически. Легаси `frontend/src/lib/viewModeFamilies.js` — только для немигрированных bespoke-остатков. |
| 4 | **Variant decomposition** | Если индикатор имеет варианты по срезу (срок, регион, подгруппа, тип) — это **разные индикаторы со своими рядами** → `VariantGroupPicker` (см. `lib/indicatorVariants.js`). Не путать с view-mode (один ряд, разные представления). |
| 5 | **Negative-capable check** | Если значения могут быть отрицательными (`trade-balance`, `current-account`, `budget-deficit`, `*-migration`) — использовать `yoy_abs` (разница в единицах источника), **не** `yoy_pct` (% от базы с переходом через ноль = визуальный мусор и тысячи процентов). |
| 6 | **Frequency strategy** | Daily-индикатор: aggregation (week/month/quarter/year avg) — `applyAggregateTransform` на фронте, **backend derived не заводим**. Monthly counterpart существующего quarterly — отдельный индикатор с MoM%-режимом через виртуальный `transform: 'mom'`. |
| 7 | **Listing visibility ≠ searchability** | Если индикатор скрыт из каталога (`is_listed=false` через `INDICATOR_HIDDEN_FROM_LISTING`) — он всё равно ищется через `?include_unlisted=true` в `IndicatorSearch.jsx`. Search haystack включает `seo_keywords` — в новом индикаторе всегда задаём osmysленные ключевые корни на русском (зарпл/инфля/безраб и т.п.). |
| 8 | **SEO-автоматика — ничего руками** | Sitemap (lastmod/priority), related-блоки, годовые landing'и `/indicator/{code}/{year}`, OG-превью `/og/{code}.png`, RSS `/feed.xml`, IndexNow-пинг — всё подтянет новый индикатор из БД само (ADR-0003 «Subsequent additions», `CONTEXT.md::SEO meta bundle`). Единственное ручное: curated `seo_keywords` + `seo_title`/`seo_description` в `app/data/indicator_seo.py` (иначе сработает generic fallback). При смене дизайн-токенов фронта — синхронизировать `SEO_CRITICAL_CSS` в `seo_renderer.py`. |

**После прохождения чеклиста** — обновить `seed_data.py` + соответствующие mappings (variant/view-mode), прогнать `./scripts/check-all.sh`, обновить `CONTEXT.md::Operational invariants and traps` если открыли новую trap.

---

## Шаг 5 — карта папок проекта

```
rosstat/
├── AGENTS.md                       ← вы здесь
├── CONTEXT.md                      ← spine: glossary + invariants
├── README.md                       ← high-level overview
├── docs/
│   ├── adr/                        ← architectural decisions (ADR-0001..0006)
│   ├── analytics_api_inventory/    ← Yandex API контракт + status (6 файлов)
│   ├── data_sources.md             ← single source of truth: индикатор → файл/endpoint (75 source)
│   ├── missed_data_audit.md        ← reference: ещё не извлечённые поля в source files (TOP-25 P0)
│   ├── backlog.md                  ← живой бэклог (приоритеты + roadmap + история)
│   ├── workflow.md                 ← процесс, dev, ручной ETL, deploy
│   └── enterprise_resilience.md    ← операционные инварианты + канарейка 6/6
├── backend/
│   ├── app/
│   │   ├── api/                    ← FastAPI routes (indicators, forecasts, calendar, embed, ticker, analytics, …)
│   │   ├── services/               ← parsers (24 типа), forecaster, calculation_engine, derived_ops, seo_renderer
│   │   │                           ←   parser internals в docstrings *_parser.py (canonical)
│   │   ├── tasks/                  ← APScheduler jobs
│   │   ├── analytics/              ← Yandex clients + warehouse
│   │   ├── models.py, config.py, main.py, database.py
│   │   └── data/indicator_seo.py   ← per-indicator SEO defaults
│   ├── alembic/                    ← миграции
│   ├── seed_data.py                ← idempotent seeder (100+ индикаторов)
│   └── tests/                      ← pytest, snapshot-тесты forecast'ов
├── frontend/
│   ├── src/
│   │   ├── components/, pages/, lib/
│   │   └── lib/categories.js       ← синхронно с seo_content.py::CATEGORY_META
│   └── nginx.conf                  ← SPA + SSR-proxy + asset hashing
├── scripts/                        ← CI, deploy, sync, audit, backup
├── mcp/forecast-analytics-mcp/     ← отдельный MCP-сервер
├── Caddyfile                       ← edge HTTPS + CSP
└── docker-compose.yml
```

---

## Финал

Если ты дочитал до сюда, ты знаешь, **где** живёт знание, **как** его читать, **как** его обновлять, и **что нельзя делать**.

Если что-то в этом файле или в любом другом .md устарело или противоречит коду — это твоя зона ответственности обновить. Не оставляй stale-доку для следующего агента: он на тебя положится.
