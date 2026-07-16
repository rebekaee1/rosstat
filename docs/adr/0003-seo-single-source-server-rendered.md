# ADR-0003: SEO single-source-of-truth — backend-rendered HTML shell с Vite asset discovery

**Status:** Accepted (в production на forecasteconomy.com).
**Date:** 2026-05-07.
**Last verified:** 2026-07-14 (SEO `/regions/map/{code}` для шаринга карты; см. Subsequent additions).
**Part of:** [`../../CONTEXT.md`](../../CONTEXT.md) (раздел `SEO meta bundle` + «Asset-hash mismatch trap»).
**Related:** [ADR-0002](0002-derived-always-reflects-source.md) (паттерн single-source-of-truth), [`../enterprise_resilience.md`](../enterprise_resilience.md) (asset-hash trap, CSP).
**Code anchors:** `backend/app/services/seo_renderer.py`, `backend/app/services/seo_content.py`, `backend/app/api/seo_pages.py`, `frontend/nginx.conf` (location-блоки `/seo/*` и `/__spa-index.html`).

## Context

Изначально вся meta-разметка (`<title>`, `<meta description>`, OpenGraph, JSON-LD)
жила во frontend и применялась клиентским рендером (через `useMeta.js` хук, который
после mount компонента обновляет `document.title`/`document.head`). Это создавало
несколько проблем:

1. **Боты не получают мета сразу.** Yandex имеет ограниченную и слабо документированную
   политику JS-рендеринга, и регулярно индексирует пустой `index.html` без `<title>` —
   это ведёт к удалению из индекса или к страницам с дефолтным шаблонным title.
   Google JS-render тоже не идеален и ввёл задержку.
2. **Дублирование source of truth.** Тексты для категорий жили и в
   `frontend/src/lib/categories.js` (для UI-карточек), и в backend в виде констант
   рядом с API. При любой правке нужно было синхронизировать вручную, а если фронт
   и бэк выкатывались отдельными релизами — окно рассинхронизации видел Yandex и
   считал страницу изменённой → удалял и снова добавлял в индекс (URL «трепало»).
3. **Legacy локальные `seo.js` константы во frontend** дублировали backend-тексты
   и приводили к рассинхрону при правках.
4. **Asset hashes от Vite.** SPA-shell — это `index.html` с `<script src="/assets/index-<hash>.js">`.
   Если backend хочет вернуть HTML с правильным `<head>`, ему нужны эти hash'и,
   которые меняются при каждом фронтенд-билде.

## Decision

**Single source of truth — `backend/app/services/seo_content.py`.** Здесь живут
`PAGE_META` (для статичных страниц `/about`, `/privacy`, `/calendar`, …),
`CATEGORY_META` (по категориям), `GLOBAL_INDICATOR_BLOCKS`, и `SeoBlock`-схема для
конкретных индикатор-страниц (тексты сохраняются в `Indicator.seo_blocks` JSONB
и редактируются без деплоя).

**Backend рендерит полный HTML** через `seo_renderer.py`:

- `render_home_html`, `render_page_html`, `render_category_html`, `render_indicator_html`.
- Каждая функция: берёт raw Vite shell `__spa-index.html` (через `get_app_assets()`),
  парсит BeautifulSoup'ом, инжектирует `<title>`, `<meta>`, OpenGraph, JSON-LD,
  основной visible-контент в `<div id="root">`, отдаёт законченный HTML.
- Endpoint'ы `/seo/page/{home,about,…}`, `/seo/category/{slug}`, `/seo/indicator/{code}` —
  `app/api/seo_pages.py`, без префикса `/api/v1`, потому что отдаются как HTML.

**Nginx ВСЕГДА проксирует indexable routes на backend** — не только для ботов,
для всех (`frontend/nginx.conf`):

```
location = /                                    → /seo/page/home
location ~ ^/(about|privacy|...|widgets)/?$     → /seo/page/$1
location ~ ^/category/([a-z0-9-]+)/?$           → /seo/category/$1
location ~ ^/indicator/([a-z0-9-]+)/?$          → /seo/indicator/$1
```

Это убирает развилку «бот / человек» — все получают одинаковый осмысленный SSR
с полной meta. После загрузки React-bundle поверх hydration'а перерисовывает
`<div id="root">` в интерактивное приложение.

**Vite-asset discovery через служебный route `/__spa-index.html`.**
Frontend nginx экспортирует raw build shell на этом обскурном пути с
`X-Robots-Tag: noindex, nofollow` (чтобы случайно не попало в индекс).
Backend в `seo_renderer.get_app_assets()` ходит на
`http://frontend/__spa-index.html` (внутренний docker-network URL),
парсит `<head>` и `<body>`, извлекает текущие hash'ированные `<script>` и `<link>`,
кэширует на 300 секунд. Это значит: backend и frontend могут перевыпускаться
независимо, и backend подхватит свежие asset hashes автоматически.

**Удалены legacy локальные `seo.js` константы во frontend.**
Сейчас единственное место текстов категорий вне `seo_content.py` — это
`frontend/src/lib/categories.js` (`seoTitle`, `seoDescription` поля).
Они **должны строго совпадать** с `CATEGORY_META.title/description` в backend
(в файле `categories.js` об этом написан комментарий с предупреждением).
`useMeta.js` остаётся как fallback на случай dev-режима без backend
(когда Vite-сервер отдаёт сырой `index.html` без SSR), но source of truth — backend.

## Consequences

**Положительные:**

- Yandex и Google всегда получают осмысленный HTML за один запрос — индексирование работает корректно.
- Один источник текстов (backend) — никаких окон рассинхрона между фронтенд- и бэкенд-релизами.
- Для индикатор-страниц тексты редактируются прямо в БД (`Indicator.seo_blocks` JSONB),
  без деплоя — миграция `20260506_indicator_seo_keywords.py` ввела поля.
- Nginx-кэш на backend SEO endpoints отключён (`Cache-Control: no-cache`),
  поэтому свежие данные индикаторов попадают в HTML сразу же. (При высоких нагрузках
  можно ввести Redis-кэш на 60 сек со стороны backend.)

**Отрицательные:**

- Backend остаётся в критическом пути HTML-рендера. Если backend упал, индексные
  страницы недоступны — nginx возвращает upstream-error, fallback на статический
  `/index.html` для этих route'ов **не настроен** (это сознательное решение: лучше
  сразу 502, чем отдать пустой shell с дефолтным title и засветить его в индексе).
- **Asset-hash mismatch trap.** Если frontend пересобран и опубликован, а backend
  ещё ходит к закэшированному `__spa-index.html` (TTL до 5 минут), HTML будет
  ссылаться на устаревшие hash'и — браузер получит 404 на ассеты. Mitigation:
  всегда `docker compose build backend frontend && docker compose up -d backend frontend`
  одновременно. См. `docs/enterprise_resilience.md` и операционные инварианты в `CONTEXT.md`.
- Тексты `seo_content.py` и `frontend/src/lib/categories.js` дублируются и могут
  разойтись. Каждый PR, меняющий тексты категорий, должен затрагивать оба места —
  это отслеживается ревью и комментарием в `categories.js`.

## The actual invariant

**Бот** (любой User-Agent), запрашивающий `/`, `/category/<slug>`, `/indicator/<code>`,
`/about|privacy|compare|calculator|calendar|demographics|widgets`, **получает HTTP 200
с полным HTML**, в котором:

1. `<title>` соответствует backend-source (`PAGE_META` / `CATEGORY_META` /
   `Indicator.seo_title` или дефолтному билдеру).
2. `<meta name="description">` соответствует backend-source.
3. OpenGraph / Twitter card теги присутствуют и ссылаются на корректную OG-картинку
   (`/api/v1/og/...`).
4. JSON-LD (для главной и индикатор-страниц) присутствует и валиден.
5. `<div id="root">` содержит видимый текст (заголовок, описание, основной блок),
   достаточный для индексирования без выполнения JS.
6. Vite-bundle ссылки в `<script>` / `<link>` соответствуют последнему успешному
   фронтенд-билду (через `get_app_assets()` cache TTL ≤ 5 мин).

## Verification

- **`scripts/seo-audit.py`** — CLI, обходит список приоритетных URL'ов
  (главная, ключевые категории, флагманские индикаторы), проверяет SSR-meta
  и валидность JSON-LD. Запускается вручную после крупных правок.
- **Локально curl-ом:**

  ```bash
  curl -A "YandexBot/3.0" -i https://forecasteconomy.com/indicator/cpi | head -50
  ```

  Видеть `200 OK`, `<title>...индикатор...</title>`, `<meta name="description"...>`,
  `<div id="root"><h1>...`.

- **PR-чеклист.** Если PR трогает `seo_content.py` или `frontend/src/lib/categories.js` —
  ревью обязано подтвердить синхрон обоих файлов.

## Subsequent additions (after acceptance)

**2026-06-12 — SEO-усиление (Fable, один проход).** Расширение в рамках принятого решения:

1. **Critical CSS inline** (`SEO_CRITICAL_CSS` в `seo_renderer.py`): `.seo-page`-разметка стилизована до загрузки Tailwind-bundle — устранён FOUC при hard refresh. При смене дизайн-токенов (цвета/шрифты в `frontend/src/index.css::@theme`) синхронизировать эту константу.
2. **IndexNow** (`app/services/indexnow.py`): после daily ETL scheduler пингует Яндекс batch-ом обновлённых URL (source + derived + главная). Key-файл `frontend/public/{indexnow_key}.txt`, ключ в `config.py::indexnow_key`.
3. **Per-indicator OG-изображения** (`app/services/og_image.py`, Pillow + DM Sans TTF в `app/assets/fonts/`): `/og/{code}.png` → nginx → `/api/v1/og-image/indicator/{code}.png`. PNG 1200×630 со спарклайном и актуальным значением, in-memory кэш 1 ч.
4. **Годовые landing-страницы** `/indicator/{code}/{year}` (`render_indicator_year_html`): чистый SSR **без React-bundle** (`build_document(include_app=False)` — у SPA-роутера нет маршрута, гидратация показала бы 404). Контент data-driven: итоги года, таблица значений, навигация по годам. В sitemap — только listed-индикаторы с ≥ 2 точками за год, priority 0.4.
5. **ETag/304 на SSR** (`seo_pages._html_response`): content-hash, If-None-Match → 304 — экономия crawl budget.
6. **RSS-фид** `/feed.xml`: последние обновления данных listed-индикаторов; `<link rel="alternate" type="application/rss+xml">` во всех SSR-документах.
7. **Sitemap**: `lastmod` = дата последней точки данных, priority 0.8 listed / 0.5 derived-sibling / 0.4 годовые.
8. **Autolink в seo_blocks** (`_autolink`, curated `AUTOLINK_TERMS`): первое вхождение термина (ИПЦ, RUONIA, ключевая ставка, …) — ссылка на индикатор; self-ссылки пропускаются. SSR-only.
9. **Dataset JSON-LD**: `distribution` (DataDownload → API), `isAccessibleForFree`, `license`, `dateModified` — кандидат в Google Dataset Search.
10. **Meta description с актуальным значением** (`_enrich_description`) — CTR-сниппеты «Актуальное значение — N на дату».

**Инвариант для новых индикаторов:** вся SEO-автоматика (sitemap, related, годовые страницы, OG-превью, RSS, IndexNow) подтягивает новый индикатор сама — из БД. Руками ничего добавлять не нужно; обязательны только осмысленные `seo_keywords` (см. чеклист «новый индикатор» в `AGENTS.md`).

**2026-07-04 — программа индексации 40k + программатик-спрос (спринт «10k визитов/день»).** Расширение в рамках принятого решения:

1. **Единый реестр URL** `app/services/site_urls.py::collect_url_sections` — одна точка истины для sitemap, IndexNow и очереди переобхода. Порядок секций = приоритет обхода.
2. **Sitemap-индекс** — `/sitemap.xml` теперь `<sitemapindex>` из секций `/sitemap-{name}.xml` (core / today / ratings / maps / regions / region-vs / calendar / years / regional-1..N по 10k). Per-file lastmod и статистика обхода в Вебмастере. nginx: regex-location `^/sitemap(-[a-z0-9-]+)?\.xml$`.
3. **IndexNow full-site** (`indexnow.ping_full_site` + `backend/scripts/indexnow-ping-all.py`): батчи по 10 000 URL (лимит протокола), разовый прогон всех ~43k URL выполнен 2026-07-04; ETL-пинг дополнен страницами `/today/{code}`.
4. **Автоподача переобхода Вебмастера** (`app/services/webmaster_recrawl.py`, cron 09:10 MSK): ежедневный дренаж квоты (~150 URL/день) приоритетными URL из реестра; state — Redis-set `wm:recrawl:submitted` в state-DB (переживает FLUSHDB кэша); цикл перезапускается после полного прохода. Флаг `webmaster_recrawl_enabled` + `yandex_webmaster_token`.
5. **Новые SSR-семейства страниц** (все чистый SSR, `include_app=False`, свои canonical):
   - `/today` + `/today/{code}` (`seo_today.py`, whitelist `TODAY_SPECS`, 10 кодов) — ВЧ-интент «X сегодня/сейчас»: значение, изменение к предыдущей точке, таблица, FAQ. `TodaySpec.series` разводит slug страницы и код ряда данных: `/today/cpi` показывает годовую инфляцию `cpi-yoy`, а не месячный индекс ~100. Типографика: русские даты, «п. п.» для %-рядов, `_dot()` против двойных точек после «руб.».
   - `/region-rating/{code}` (`seo_regional.py::render_region_rating_html`, ~489 стр.) — «топ регионов по X»: полный ранжир за последний год, лидеры/аутсайдеры/РФ, ItemList. Порог ≥ 10 регионов за max-год (согласован с sitemap).
   - `/region-vs/{a}-vs-{b}` (`seo_region_compare.py`, C(20,2)=190 пар топ-регионов по населению) — «Москва или СПб»: ключевые показатели за последний общий год. Canonical — упорядоченная пара.
   - `/calendar/{y}/{mm}` (`seo_calendar.py`) — месячные посадочные календаря, только official-даты (ADR-0005), месяцы с ≥ 3 событиями.
6. **Перелинковка**: SSR-хаб регионов → рейтинги; карточка регион-показателя → «полный рейтинг регионов»; главная (PAGE_META home links) → /today и /regions; месячные страницы календаря связаны prev/next.
7. **Фикс BreadcrumbList в региональном SSR**: элементы `(name, path)` передавались в `_breadcrumbs` в перевёрнутом порядке — `item` получал имя вместо URL. Исправлено во всех региональных рендерах.
8. **Деплой 2026-07-04**: всё выше на проде (`201.51.11.170`); `RUSTATS_YANDEX_WEBMASTER_TOKEN` добавлен в прод-`.env`; IndexNow-пинг новых секций (706 URL) принят; recrawl-job активен, первый автодренаж квоты — 05.07 09:10 МСК (квота 04.07 выбрана ручной подачей 200 URL).

**2026-07-14 — SEO шаринга карты регионов.** `/region-rating/{code}` ≠ интерактивная карта с годом. Канон shareable URL:

1. **`/regions/map/{code}`** (+ опционально `?year=YYYY`) — SSR `seo_regional.py::render_regions_map_html`, nginx → `/seo/regions/map/{code}`, SPA-роут тот же компонент `RegionsHome`. Meta/OG/JSON-LD/видимый chart; OG переиспользует `/og/region-rating/{code}.png` (отдельный map-PNG не плодим).
2. **Legacy query** `/regions?view=map&indicator=&year=` (прод `9226c77`) → **301** на канон (`seo_pages.seo_regions`).
3. **Sitemap** секция `maps` (`site_urls._map_urls`) — тот же пул listed ≥10 регионов, что у ratings; year-варианты в индекс не входят.
4. **Перелинковка**: хаб `/regions` → рейтинги и карты; рейтинг ↔ карта; макро-кросслинк → `/regions/map/{code}`.

**2026-07-16 — фильтр неканонических URL в реестре / переобходе.** Searchable в Вебмастере просел (~9070→~3134) на классе дублей: очередь `webmaster_recrawl` подавала bare `/indicator/{sibling}`, которые SSR 301 на `/indicator/{base}?mode=…` (NOT_CANONICAL), сжигая ~150 URL/день квоты.

1. **`site_urls.is_redirect_only_indicator` / `is_recrawl_eligible`** — одна точка: коды из `legacy_redirects.resolve_*` и любые path с `?` не входят в индексный контур.
2. **`_core_urls` / `_year_urls`** — redirect-only siblings вычищены из sitemap и IndexNow (раньше попадали с priority 0.5).
3. **`webmaster_recrawl`**: `filter_recrawl_paths` + skip-on-submit (SADD без POST) — курсор идёт мимо junk, квота не тратится; полный reset `wm:recrawl:submitted` не нужен.
4. Тесты: `tests/test_site_urls_recrawl_filter.py`.

## Out of scope (future work)

- Migrate `frontend/src/lib/categories.js` тексты в API — вытащить через
  `/api/v1/categories` endpoint, чтобы single source of truth был ровно один файл.
- Кэширование SEO HTML в Redis на 30–60 секунд (сейчас каждый запрос идёт в БД
  и парсит shell) — пока нагрузки терпимые, оставлено как «когда понадобится».
- Build-time inlined assets (Vite plugin) вместо runtime fetch `__spa-index.html` —
  устранит TTL и asset-hash trap, но ценой того, что backend и frontend нужно
  синхронно билдить даже в dev. Сейчас runtime fetch выбран как более гибкий.
