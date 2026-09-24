# ADR-0014 — Обобщённый субнациональный bounded context (штаты / земли / провинции)

- **Status:** Accepted
- **Date:** 2026-09-20
- **Last verified:** 2026-09-20
- **Part of:** [`AGENTS.md`](../../AGENTS.md), [`CONTEXT.md`](../../CONTEXT.md), [`ADR-0008`](0008-regional-bounded-context.md), [`ADR-0012`](0012-world-multi-provider-official-first-forecasts.md), [`ADR-0013`](0013-country-first-url-architecture.md)

---

## Контекст

Российский региональный блок ([ADR-0008](0008-regional-bounded-context.md)) заточен под
годовой сборник Росстата: ось `регион × показатель × год`, артефакт вместо ETL,
без прогнозов и derived. Штаты США (и далее земли Германии, провинции Канады)
публикуют **месячные, квартальные и годовые** официальные ряды. Смешивать частоты
в `region_data` — известный trap annual-in-monthly. Расширять российские таблицы
под FRED/BLS/BEA значило бы сломать инварианты сборника.

Первая страна — США (таргет EN apex). UI-эталон — российский хаб карты-хороплета
и профиль региона с линией национальной экономики на графике.

## Решение

Отдельный bounded context **для любой страны кроме России**, config-driven по
паспорту. Никакой логики `if country == 'us'` в коде.

1. **Схема** (`subnational_regions` / `subnational_indicators` / `subnational_data_points`).
   Alembic `20260920_subnational`. Точка — `period date`, частота на показателе
   (`monthly` | `quarterly` | `annual`). Upsert — ADR-0002
   (`ON CONFLICT DO UPDATE WHERE value <> excluded.value`).
2. **Паспорт** `backend/app/data/world_subnational/<cc>.yaml`: территории
   (slug, имена RU/EN, geo_code, fips, kind) и показатели (шаблон серии,
   единица, частота, `national_code` для линии «— United States»).
3. **Источник** — только официальный первоисточник. Для США FRED keyless CSV
   редистрибуирует BLS LAUS/CES, BEA, Census, FHFA. Публичные тексты не называют
   идентификаторы серий.
   Для трёх новых численных рядов LAUS полная история FRED перекрывается
   последними шестью календарными годами напрямую из пакетного API BLS:
   первоисточник может опережать зеркало на один выпуск.
4. **URL** (ADR-0013): `/{country}/regions`, `/{country}/region/{slug}`,
   `/{country}/region/{slug}/{code}`. Россия остаётся на `/russia/region…`
   (конкретные роуты выше динамического `/:countrySlug`).
5. **Прогноз только после проверки.** Национальный ряд
   на графике штата читается из `world_indicators` по `national_code`.
   Для любого ряда штата с достаточной актуальной историей отдельный
   `world_subnational_forecast.py` по запросу запускает Python-стратегию
   соответствующей частоты (`annual_auto` / `quarterly_auto` / `monthly_auto`).
   Rolling-origin MASE должен быть ниже 1 и минимум на 2% лучше сезонного
   наивного ориентира; короткие, нерегулярные и устаревшие ряды не получают
   опубликованный прогноз. С 2026-09-24 проверяется весь публикуемый горизонт
   и масштаб на каждом origin берётся только из доступной тогда истории;
   недавняя дыра календаря блокирует прогноз. Кэш привязан к версии `world`
   и сбрасывается после
   ingest. Derived для этого контура нет.
6. **Карта** — закоммиченный SVG-path JSON той же формы, что `regionsMap.json`.
   Геометрия США: Census cartographic boundaries через us-atlas (public domain),
   проекция `geoAlbersUsa`.

Ingest: `scripts/load-world-subnational.py`, еженедельный job под флагом
`RUSTATS_WORLD_SUBNATIONAL_INGEST_ENABLED` (default true с 2026-09-24).
После записи точек job инвалидирует `world` и `ssr-world`; сетевые сбои
отмечаются ошибками, а отсутствующие серии — пропусками. Ошибки выпуска
завершают job с исключением, чтобы listener планировщика отправил алерт.

## Последствия

- Российский regional (таблицы, сидер, API, UI `/russia/region`) не меняется
  по смыслу; параметризация карты обратно совместима.
- Новая страна = новый YAML + геометрия карты, без правок ядра.

## Subsequent additions

### 2026-09-20 — OG-картинки субнациональных страниц

Три публичных пути (generic по стране, без `if country ==`):

- `/og/world/{country}/regions.png` → `/api/v1/og-image/world-regions/{country}.png` (барчарт топ-8 дефолтного показателя)
- `/og/world/{country}/region/{region}.png` → `/api/v1/og-image/world-region/{country}/{region}.png` (сводка 6 показателей)
- `/og/world/{country}/region/{region}/{indicator}.png` → `/api/v1/og-image/world-region/{country}/{region}/{indicator}.png` (график ряда)

Рендер переиспользует `render_rating_og` / `render_world_country_og` / `render_indicator_og`.
SSR (`seo_world_subnational`): `og:image` + JSON-LD `ImageObject` + видимый `<figure class="seo-chart">`.
nginx: правила в `location ^~ /og/` стоят после `/og/world/rating/…` и до generic `/og/world/{country}/{code}`.

### 2026-09-24 — годовые быстрые страницы штатов

У восьми ключевых рядов каждого штата доступны страницы только за годы с
опубликованными наблюдениями: `/{country}/region/{region}/{indicator}/{year}`.
Страница даёт значение выбранного периода, предшествующий год, сопоставимый
национальный ряд при наличии, ссылки на другие штаты и соседние годы. Для
месячных и квартальных рядов последнее наблюдение не объявляется годовой суммой.
OG-постер выделяет выбранный год в общем шаблоне `render_indicator_og`.
Страницы входят в отдельную секцию sitemap `world-region-years`.

Постоянная страница `/{country}/region-vs/{a}-vs-{b}` сопоставляет штаты по
совпадающим датам наблюдений ключевых показателей. Все 1 225 пар из 50 штатов
идут в `world-region-vs` sitemap и открываются из профиля каждого штата.
Постер сравнения использует общий pearl/glass шаблон `render_region_vs_og`;
полные единицы и даты каждого ряда остаются в таблице страницы.
