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
4. **URL** (ADR-0013): `/{country}/regions`, `/{country}/region/{slug}`,
   `/{country}/region/{slug}/{code}`. Россия остаётся на `/russia/region…`
   (конкретные роуты выше динамического `/:countrySlug`).
5. **Без прогнозов и derived.** Национальный ряд на графике штата читается из
   `world_indicators` по `national_code`.
6. **Карта** — закоммиченный SVG-path JSON той же формы, что `regionsMap.json`.
   Геометрия США: Census cartographic boundaries через us-atlas (public domain),
   проекция `geoAlbersUsa`.

Ingest: `scripts/load-world-subnational.py`, weekly job под флагом
`RUSTATS_WORLD_SUBNATIONAL_INGEST_ENABLED` (default false).

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
