# ADR-0003: SEO single-source-of-truth — backend-rendered HTML shell с Vite asset discovery

**Status:** Accepted (в production на forecasteconomy.com).
**Date:** 2026-05-07.
**Last verified:** 2026-05-22 (документация-ревизия: SSR через `__spa-index.html` + Vite shell discovery работает; 7 SSR-routes в `frontend/nginx.conf`: `/`, `/{about,privacy,compare,calculator,calendar,demographics,widgets}`, `/category/<slug>`, `/indicator/<code>`; добавлен `no-cache always` фикс 2026-05-22 для всех SSR routes — закрывает Browser-cache trap, см. `enterprise_resilience.md::Frontend и кэш`).
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

## Out of scope (future work)

- Migrate `frontend/src/lib/categories.js` тексты в API — вытащить через
  `/api/v1/categories` endpoint, чтобы single source of truth был ровно один файл.
- Кэширование SEO HTML в Redis на 30–60 секунд (сейчас каждый запрос идёт в БД
  и парсит shell) — пока нагрузки терпимые, оставлено как «когда понадобится».
- Build-time inlined assets (Vite plugin) вместо runtime fetch `__spa-index.html` —
  устранит TTL и asset-hash trap, но ценой того, что backend и frontend нужно
  синхронно билдить даже в dev. Сейчас runtime fetch выбран как более гибкий.
