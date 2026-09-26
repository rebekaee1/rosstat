# Analytics — Яндекс Метрика, Вебмастер, Google Search Console, фронтовые события

Единый справочник аналитических интеграций (бывшая папка `docs/analytics_api_inventory/`).
Контекст и инварианты — [`../CONTEXT.md`](../CONTEXT.md) (раздел `Forecast Analytics OS`), ADR-0003.
Код: `backend/app/services/yandex_*.py`, `gsc_client.py` (клиенты); `metrika_acquisition.py`,
`webmaster_recrawl.py` (09:10 МСК), `webmaster_indexing_daily.py`, `webmaster_indexing_report.py` (пн 09:30 МСК),
`admin_bi.py` (потребители); `backend/app/api/analytics.py` (REST); `mcp/forecast-analytics-mcp/` (MCP).

**Code anchors:** `backend/app/services/yandex_*.py` (clients), `backend/app/services/analytics_*.py` (ingestion + features), `backend/app/api/analytics.py` (REST), `mcp/forecast-analytics-mcp/` (MCP server).

This document is the implementation checklist for Forecast Analytics OS.
Every Yandex API client must be mapped here before code is allowed to call it.

### Статус реализации клиентов

The inventory is the **long-term contract** of which Yandex APIs the platform may
touch. Actual implementation is partial; live integrations require an OAuth token
in `.env` (`YANDEX_METRIKA_TOKEN` / `YANDEX_METRIKA_WRITE_TOKEN` /
`YANDEX_WEBMASTER_TOKEN`) and `analytics_live_writes_enabled=true` for any
non-`read_only` operation. Without tokens the analytics scheduler is a no-op
and `analytics-smoke.py` exits with `enabled=false`.

| File | Code module | Status |
|------|-------------|---------------------|
| [§ frontend_instrumentation](#frontend_instrumentation) | `frontend/src/lib/track.js`, `utm.js`, `cleanUrl.js`, `useScrollDepth.js`, `index.html`; backend collector `app/api/analytics.py::events_collector` → `FrontendEvent` | `implemented` — Webvisor 2 + form analytics включены, ~60 целей в `events`, UTM helper + taxonomy. Канонический документ для frontend goals и share-ссылок. |
| [§ metrika_logs](#metrika_logs) | `app/services/yandex_metrika_logs.py` | `partial` — `list_requests`, `create_request`, `request_info`, `download_part`, `clean_request`. Missing: fields catalog. |
| [§ metrika_management](#metrika_management) | `app/services/yandex_metrika_management.py` | `partial` — read of counters/goals/filters/grants + goal create/update/delete behind approval. Missing: counter writes, filter writes, segments/labels/notes/direct-links. |
| [§ metrika_reporting](#metrika_reporting) | `app/services/yandex_metrika_reporting.py` | `implemented` — все JSON-варианты `table` / `bytime` / `drilldown` / `comparison` / `comparison_drilldown`. CSV-варианты пока только через ручной HTTP. |
| [§ yandex_webmaster](#yandex_webmaster) | `app/services/yandex_webmaster_client.py` | `partial` — host/summary, diagnostics, sitemaps read+delete, search queries, indexing + in-search/events history, recrawl. Missing: important URLs, owners, SQI, sitemap add, external links. |
| [§ google_search_console](#google_search_console) | `app/services/gsc_client.py` | `live local API verified, 2026-09-21` — read-only OAuth refresh, Sites (`siteFullUser`), Sitemaps status and daily web/image Search Analytics exports accepted. Bounded URL Inspection is implemented/tested but not live-probed. CLI `backend/scripts/google-search-console.py`; production credential mount/scheduler activation not part of this setup. |

Activation cheat-sheet:

- Без `RUSTATS_ANALYTICS_API_TOKEN` (защищающего внутренний REST) endpoints
  `/api/v1/analytics/*` отвечают 401. Это отдельный токен от Yandex OAuth.
- `analytics_scheduler_enabled=true` в `.env` включает hourly + daily jobs;
  без Yandex OAuth-токенов они выполняются вхолостую и пишут предупреждение.
- Live writes (`low_risk_write` / `high_risk_write`) требуют `analytics_live_writes_enabled=true`
  + одобренной записи в `agent_action_audit`.

Each endpoint row records:

- method and path;
- official documentation URL;
- OAuth scopes;
- required/optional parameters;
- response fields consumed by the app;
- limits, quotas, lag, sampling/privacy flags;
- retry/error handling;
- warehouse destination;
- protected Analytics API endpoint;
- MCP tool mapping;
- safety class;
- fixture/smoke coverage.

Safety classes:

- `read_only`: can run without approval if credentials and target are allowlisted.
- `low_risk_write`: requires an approved action record before live execution.
- `high_risk_write`: requires explicit manual approval and detailed before/after diff.
- `denied`: not executable by the agent.

Implementation rule: a client module is not complete until every endpoint family in
its inventory has a storage/API/MCP decision and at least one fixture.

## frontend_instrumentation

### Атрибуция аудитории (2026-07-02)

Разрез «гость vs зарегистрированный» — на двух уровнях:

- **First-party (`frontend_events`).** `POST /analytics/events` резолвит куку `fe_sess` и пишет `user_id` + `authed` (миграция `20260702_fe_audience`). Эндпоинт POST, не кэшируется — чтение куки не нарушает инвариант ADR-0003. Гость → `authed=false, user_id=NULL`. Гейт сбора — собственный флаг `frontend_events_enabled` (default on), НЕ `analytics_enabled`: телеметрия пишется всегда.
- **Метрика.** `track.js` добавляет `authed` (0/1) в params каждого `reachGoal`; при резолве `/me` вызывает `ym(id,'setUserID',userId)` и `ym(id,'userParams',{authed,audience})`. Сегмент «зарегистрированные» в интерфейсе = визиты с `userParam authed=1`.
- **Цели.** `scripts/metrika-goals-audit.py` сверяет события фронта с целями счётчика; `--create` заводит недостающие JS-цели (нужен write-token). На 2026-07-02 без цели — 64 события (см. вывод скрипта).
**Implementation status:** `implemented` — `frontend/public/consent.js` (consent-bootstrap, загрузка трекеров), `frontend/src/lib/consent.js` + `frontend/src/components/CookieConsent.jsx` (баннер согласия), `frontend/src/lib/track.js`, `frontend/src/lib/utm.js`, `frontend/src/lib/cleanUrl.js`, `frontend/src/lib/useScrollDepth.js`, backend collector — `app/api/analytics.py::POST /api/v1/analytics/events` → `FrontendEvent`.

**Consent gating (2026-06-12):** Метрика и РСЯ грузятся ТОЛЬКО после активного согласия пользователя (cookie-баннер, выбор хранится в `localStorage['fe:consent:v1']`, версия согласия = дата редакции политики в `lib/consent.js::CONSENT_VERSION`). До согласия `window.ym` не существует — все `ym()`-хелперы в `track.js` guard'ятся. Факт согласия логируется событием `consent_update` в собственный collector. Первый hit с очищенным URL шлётся из `consent.js` в момент загрузки счётчика.

Этот файл описывает, как фронтенд платит дань Яндекс.Метрике и собственному `frontend_events` warehouse. В нём — единый источник правды для:

- параметров инициализации счётчика;
- состава `events` (целей `reachGoal`);
- UTM-разметки исходящих и share-ссылок;
- очистки URL от tracking-меток.

Любая правка соответствующего фронт-кода обязана обновить этот документ — иначе следующий агент будет работать со stale-картой.

### Counter init (frontend/public/consent.js)

Counter ID: `107136069`. Инициализация — в `loadMetrika()` внутри consent-bootstrap, вызывается после согласия на категорию «Аналитические»:

```js
ym(107136069, 'init', {
  defer: true,
  webvisor: true,
  clickmap: true,
  accurateTrackBounce: true,
  trackLinks: true,
  trackHash: true,
  triggerEvent: true,
  childIframe: true
});
```

Что это даёт:

- `defer: true` — отключает автоматический первый hit (мы шлём вручную с очищенным URL).
- `webvisor: true` — Webvisor 2: запись курсора, кликов, скроллов, форм. Воспроизведение через `webvisor.yandex.ru`.
- `clickmap: true` — карта кликов отдельно от Webvisor.
- `accurateTrackBounce: true` — отказы считаются по 15-секундному порогу, а не по «one-page session».
- `trackLinks: true` — автотрек внешних ссылок (`mc.yandex.*::extLink`).
- `trackHash: true` — учитывает изменения URL hash (для будущих deeplink-якорей `#forecast`, `#table`).
- `triggerEvent: true` — Метрика дёргает `yacounter*` события на window (нужно для form analytics + JS event triggers Webvisor 2).
- `childIframe: true` — Webvisor пишет события из вложенных iframe (наш embed-виджет на сторонних сайтах).

После init выполняется ручной first-hit с очисткой tracking-параметров (см. секцию `URL cleanup` ниже).

### events (reachGoal таксономия)

Источник: `frontend/src/lib/track.js::events`. Ключи snake_case, имена-цели в Метрике.

#### Загрузка/выгрузка данных

| Goal | Site | Surface | Параметры |
|---|---|---|---|
| `download_csv` | `IndicatorDetail`, `DemographicsPage` | кнопка «Скачать CSV» | `indicator`, `range`, `category` |
| `download_excel` | `IndicatorDetail` | кнопка «Скачать Excel» | `indicator`, `range`, `category` |
| `download_ical` | `CalendarPage` | кнопка «iCal» | — |

#### График и режим

| Goal | Site | Surface | Параметры |
|---|---|---|---|
| `chart_mode_change` | `IndicatorDetail` | `CpiViewModePicker` | `mode`, `code`, `category` |
| `chart_range_change` | `IndicatorDetail` | range-кнопки внутри `IndicatorChart` | `range`, `indicator`, `category` |
| `chart_zoom` | `IndicatorChart` | reset zoom | `action`, `indicator`, `category` |
| `forecast_toggle` | `IndicatorChartSection` | переключатель «Прогноз» | `enabled`, `indicator`, `category` |
| `forecast_view` | `IndicatorForecastSection` | IntersectionObserver ≥40% | `indicator`, `category`, `chartMode` |

#### Таблица

| Goal | Site | Surface | Параметры |
|---|---|---|---|
| `table_search` | `DataTable` | search input (debounced) | `query` |
| `table_sort` | `DataTable` | column header click | `order` |
| `table_page` | `DataTable` | pagination buttons | `direction` |

#### Сравнение и калькулятор

| Goal | Site | Surface | Параметры |
|---|---|---|---|
| `compare_open` | `ComparePage` | mount страницы /compare | `a`, `b`, `hasInitialPair` |
| `compare_change` | `ComparePage` | смена индикатора A/B | `position`, `code` |
| `compare_range` | `ComparePage` | смена периода | `range` |
| `calc_direction` | `CalculatorPage` | смена направления | `reversed` |
| `calc_preset` | `CalculatorPage` | пресет периода | `preset` |
| `calc_share` | `CalculatorPage` | кнопка share-ссылки | `from`, `to`, `amount` |
| `calc_copy_result` | `CalculatorPage` | кнопка «Копировать результат» | — |
| `calc_chart_mode` | `CalculatorPage` | переключатель режима графика | `mode` |
| `calc_breakdown` | `CalculatorPage` | разворот таблицы | `expanded` |
| `faq_toggle` | `CalculatorPage` | развёртывание вопроса | `question` |

#### Календарь

| Goal | Site | Surface | Параметры |
|---|---|---|---|
| `calendar_month_nav` | `CalendarPage` | навигация по месяцам | `direction` |
| `calendar_source_filter` | `CalendarPage` | фильтр источника | `source` |
| `calendar_day_select` | `CalendarPage` | клик по дню | `date` |
| `calendar_clear_day` | `CalendarPage` | сброс выбранного дня | — |

#### Демография

| Goal | Site | Surface | Параметры |
|---|---|---|---|
| `demographics_chart_type` | `DemographicsPage` | переключатель типа графика | `type` |
| `demographics_csv` | `DemographicsPage` | кнопка CSV | — |

#### Embed Builder

`embed_type_change`, `embed_indicator_select`, `embed_period_change`, `embed_theme_change`, `embed_size_change`, `embed_option_toggle`, `embed_code_tab`, `embed_code_copy`, `embed_runtime_view`. Параметры см. `EmbedBuilder.jsx`.

#### Навигация и engagement

| Goal | Site | Surface | Параметры |
|---|---|---|---|
| `nav_category_open` | `Navbar` | dropdown «Категории» | — |
| `nav_mobile_toggle` | `Navbar` | гамбургер | — |
| `nav_link_click` | `Navbar` | пункты в дроп-дауне | (ещё не подключено) |
| `home_category_click` | `CategoryBlock` | dashboard tile → `/category/:slug` | `category`, `indicatorCount` |
| `home_indicator_click` | `IndicatorTile` (`surface='home'`) | главная → `/indicator/:code` | `indicator`, `category`, `surface` |
| `category_tile_click` | `IndicatorTile` (`surface='category'`) | category → `/indicator/:code` | `indicator`, `category`, `surface` |
| `related_indicator_click` | `IndicatorDetail` нижний CTA | соседи по категории | `from`, `to`, `category`, `surface` |
| `related_link_click` | `CategoryPage` («Связанные категории») | category → category | `from`, `to`, `surface` |
| `breadcrumb_click` | (зарезервировано) | хлебные крошки | — |
| `scroll_depth` | `useScrollDepth` (Indicator/Compare/Calculator/Category) | пороги 25/50/75/100 | `percent`, `page`, `indicator`, `category` |
| `indicator_view` | `IndicatorDetail` | mount страницы | `indicator`, `category` |

#### Конверсия, лимиты и спрос-поиск (создать в Метрике вручную)

Цели ниже отправляются `reachGoal`, но не считаются, пока в счётчике Метрики
не создан одноимённый goal (тип «JavaScript-событие», идентификатор = значение
из колонки Goal). Это новые цели вокруг регистрационной стены, скачиваний
картинок и спрос-аналитики поиска (звонки 2026-06-25).

| Goal | Site | Surface | Параметры |
|---|---|---|---|
| `compare_add` | `ComparePage` | добавление индикатора в сравнение | `code`, `count` |
| `compare_search` | `ComparePage` | поиск в сравнении (debounce) | `q`, `results` (0 = пробел каталога) |
| `compare_image_download` | `ComparePage` | скачивание картинки сравнения | `count`, `scale` |
| `compare_image_blocked` | `ComparePage` | гость уперся в гейт картинки | `count` |
| `compare_limit_hit` | `ComparePage` | гость уперся в лимит 2 рядов | `cap` |
| `chart_image_download` | `IndicatorChartSection` | скачивание графика картинкой | `indicator`, `mode`, `withForecast` |
| `chart_image_blocked` | `IndicatorChartSection` | гость уперся в гейт картинки | `indicator` |
| `download_limit` | `excel.js`/`IndicatorChartSection` | гость уперся в стену выгрузки данных | `indicator` |
| `search_query` | `IndicatorSearch` | основной поиск ⌘K (debounce) | `q`, `results` (0 = пробел каталога) |
| `search_select` | `IndicatorSearch` | выбор индикатора из поиска | `q`, `code` |
| `search_abandon` | `IndicatorSearch` | закрыли поиск без выбора | `q`, `results` |
| `register_nudge_view` / `register_nudge_expand` / `register_nudge_cta` | глобально | плашка «регистрация» | — |
| `feedback_nudge_view` / `feedback_nudge_expand` / `feedback_nudge_cta` / `feedback_submit` | глобально | обратная связь | — |
| `header_login_click` / `header_register_click` | `Navbar` | CTA в шапке | — |
| `signup` / `login_success` / `oauth_start` | auth-флоу (ADR-0007) | регистрация/вход | `method` |
| `newsletter_opt_in` / `newsletter_opt_out` | кабинет | подписка на рассылку | — |

> Конверсионная воронка картинок/выгрузок: `*_blocked` / `download_limit`
> (гость уперся в стену) → `register_nudge_cta` / `header_register_click` →
> `signup` → `chart_image_download` / `compare_image_download` (уже как юзер).
> Соотношение `*_blocked` к `signup` — основная метрика регистрационной стены.

#### Внешние интеграции

| Goal | Site | Surface | Параметры |
|---|---|---|---|
| `outbound_link` | (зарезервировано) | произвольная внешняя ссылка | `url` |
| `source_link_click` | (зарезервировано) | клик «источник данных» | `indicator`, `source` |
| `contact_email` | `Footer`, `About`, `Privacy` | mailto-ссылка | — |
| `api_retry` | `ApiRetryBanner` | кнопка повторить | — |
| `api_load_error` | (зарезервировано) | системное падение | — |
| `error_reload` | `ErrorBoundary` | reload after crash | — |
| `empty_state` | (зарезервировано) | пустые состояния | — |

`experiment_exposure` — зарезервировано под A/B-тесты, ещё не подключено.

#### Bridge to backend warehouse

`track(event, params)` дублирует событие в `POST /api/v1/analytics/events` → SQL-таблица `frontend_events` (модель `FrontendEvent`). Это нужно для:

- кросс-чек Метрики (sampling и privacy скрытые сегменты);
- возможности join'ить goals с прочей analytics-warehouse (поиск пользовательских когорт без лимитов API).

Endpoint защищён origin-валидацией `app/api/analytics.py::events_collector`. Не требует токена авторизации (это публичный сборщик с фронта).

### URL cleanup и атрибуция

Источники: `frontend/public/consent.js` (first-hit; очистка URL выполняется всегда, hit — только при согласии) и `frontend/src/lib/cleanUrl.js` (SPA-hits).

#### TRACKING параметры, удаляемые перед `ym('hit')`

`etext`, `ybaip`, `yclid`, `ysclid`, `gclid`, `fbclid`, `_openstat`, `openstat`, `clid`, `yandex_referrer`, `_ga`, `utm_source`, `utm_medium`, `utm_campaign`, `utm_term`, `utm_content`, `utm_referrer`, `from`, `ref`, `ref_src`, `source`, `mc_cid`, `mc_eid`, `igshid`.

#### Особенность first-hit (public/consent.js)

В первом hit мы НЕ удаляем `utm_*` — они нужны Метрике для атрибуции source/medium/campaign на сессии. Удаляются только tracking-метки Яндекса (`ybaip`, `etext`, `ysclid`, `yclid`) и сторонние (`gclid`, `fbclid` и пр.).

После очистки выполняется `history.replaceState(history.state, '', cleanPath)` — это ключевой момент: иначе Webvisor 2 пишет первую запись с URL=`/?ybaip=1`, и в Метрике появляется отдельный «landing page» вместо `/`. Эта правка убирает 368 «фиктивных» landing'ов в месяц (см. `canvases/metrika-webvisor-deep-2026-05-10.canvas.tsx`).

#### SPA-hits (lib/cleanUrl.js)

При navigation в SPA `App.jsx::YandexMetrikaHit` отправляет `cleanPathWithSearch(pathname, search)` — здесь `utm_*` уже включены в чёрный список (атрибуция уже сохранена на первом hit, дублировать не нужно).

#### Sync с robots.txt

Список `TRACKING_PARAMS` синхронизирован с директивой `Clean-param` в `frontend/public/robots.txt`. Если добавляете новый tracking-параметр — обновите оба места.

### UTM Taxonomy (для исходящих и share-ссылок)

Источник: `frontend/src/lib/utm.js`. Применяется ко всем нашим share-button'ам, embed-виджетам, social-постам, рассылкам.

#### Канонические значения

`utm_source`:

- `self` — share-кнопки внутри fe (Calculator, Compare, IndicatorPage)
- `embed` — пользовательский iframe-виджет (Embed Builder)
- `newsletter` — email-рассылка (когда появится)
- `social-tg` / `social-vk` / `social-dzen` / `social-youtube` — наши собственные посты
- `direct` — Yandex Direct рекламные кампании (проставляются в кабинете Direct)

`utm_medium`:

- `share-link` — ручной share через clipboard / native share
- `embed` — iframe widget
- `cta` — кнопка-призыв («Сравнить с другим», «Открыть калькулятор»)
- `context` — контекстная ссылка внутри текстов

`utm_campaign` (kebab-case):

- `calc-share` — share из калькулятора
- `compare-share` — share из /compare (когда добавится кнопка)
- `indicator-share` — share страницы индикатора (когда добавится кнопка)
- `forecast-cta` — баннер «Смотреть прогноз»
- `calendar-event` — share конкретного события

`utm_content` — контекст внутри кампании. Например, для `calc-share`: `${fromYear}-${toYear}` или `${amount}`.

`utm_term` — для рекламных кампаний (Direct), keyword.

#### Direct-кампании (внешний контракт)

UTM проставляются в кабинете Yandex Direct. Шаблон:

```
?utm_source=direct&utm_medium=cpc&utm_campaign={CAMPAIGN_NAME}&utm_content={ad_id}&utm_term={keyword}
```

Где:

- `{CAMPAIGN_NAME}` — kebab-case имя кампании в Direct (например, `ipoteka-2026q2`)
- `{ad_id}` — `{ad_id}` (макрос Direct)
- `{keyword}` — `{keyword}` (макрос Direct)

Без UTM-разметки трафик из Direct пишется в Метрике как смешанный с органикой → атрибуция слепа. Это fallout #1 P0 из `metrika-webvisor-deep-2026-05-10` deep dive.

### Связь с warehouse

Frontend goals + UTM сходятся в трёх местах:

1. **Yandex Metrika UI** — кабинет 107136069, отчёты «Конверсии» / «Источники трафика».
2. **`frontend_events` table** — sql warehouse, доступен через `/api/v1/analytics/events` GET (с токеном) и через MCP `analytics_query_visits` (для агента).
3. **`MetrikaReportSnapshot`** — daily snapshot из Reporting API, агрегаты вокруг goals (см. `analytics_ingestion.py::sync_daily_metrika`).

### Когда обновлять этот файл

- Новый goal в `events` → добавить строку в соответствующую таблицу выше.
- Изменение init-параметров → обновить раздел «Counter init».
- Изменение TRACKING-чёрного списка → обновить раздел «URL cleanup» И `frontend/public/robots.txt`.
- Новая UTM-кампания (Direct/social/email) → добавить в «UTM Taxonomy → utm_campaign».
- Удаление цели → пометить `(deprecated)`, не удалять сразу — иначе сломается ретроактивная аналитика.

## metrika_logs

**Implementation status:** `partial` — `app/services/yandex_metrika_logs.py`.
Реализовано: `list_requests`, `create_request`, `request_info`, `download_part`,
`clean_request`. Не реализовано: fields catalog (`logs_fields_catalog`). Повизитный ingest в
`raw_metrika_visits` делает `app/services/metrika_acquisition.py` (cron 08:20/14:20/20:20 МСК);
`raw_metrika_hits` не наполняется.

Base URL: `https://api-metrika.yandex.net`.

Scope: `metrika:read`.

Important constraints:

- current day is not complete and should not be requested for stable analysis;
- max request period is one year;
- `fields` length must stay within the API limit;
- prepared/downloaded log files count against storage quota until cleaned;
- sessions can finalize late, so recent days should be re-synced.

| Endpoint family | Safety | Storage | MCP tool | Fixture |
| --- | --- | --- | --- | --- |
| Fields catalog for `visits` | read_only | `metrika_log_field_catalog` | `logs_fields_catalog` | `tests/fixtures/metrika/log_fields_visits.json` |
| Fields catalog for `hits` | read_only | `metrika_log_field_catalog` | `logs_fields_catalog` | `tests/fixtures/metrika/log_fields_hits.json` |
| Create request for `visits` | read_only | `metrika_log_requests` | `logs_create_request` | `tests/fixtures/metrika/log_create_visits.json` |
| Create request for `hits` | read_only | `metrika_log_requests` | `logs_create_request` | `tests/fixtures/metrika/log_create_hits.json` |
| List requests | read_only | `metrika_log_requests` | `logs_status` | `tests/fixtures/metrika/log_requests.json` |
| Request info/status | read_only | `metrika_log_requests` | `logs_status` | `tests/fixtures/metrika/log_status.json` |
| Download request part | read_only | `raw_metrika_visits`, `raw_metrika_hits` | `logs_download_ingest` | `tests/fixtures/metrika/log_hits.tsv` |
| Clean/delete prepared request | low_risk_write | `agent_action_audit` | `logs_clean_request` | `tests/fixtures/metrika/log_clean.json` |

Normalized visit fields:

- visit id, client id hash, start/end timestamps, start URL, referer, traffic source,
  search engine, search phrase, device/browser, region, goals, revenue fields if present.

Normalized hit fields:

- watch id, page view id, timestamp, URL, referer, title, event/action fields,
  device flags, raw row hash.

Money/value caveat:

- preserve raw values and documented multipliers for revenue, goals price and product price fields.

Live smoke:

```bash
python scripts/analytics-smoke.py metrika-logs --counter-id 107136069 --date yesterday
```

## metrika_management

**Implementation status:** `partial` — `app/services/yandex_metrika_management.py`.
Реализовано: `counters` (list/get), `goals` (list + create/update/delete с флагом
`approved=true`), `filters` (list), `grants` (list). Не реализовано: counter
create/edit (high_risk_write), filter create/update/delete, operations,
labels, segments, notes, Yandex Direct links. Эти строки таблицы ниже —
целевой контракт для будущих доработок.

Base URL: `https://api-metrika.yandex.net`.

Read scope: `metrika:read`.

Write scope: `metrika:write`, only through the action policy gateway.

| Resource | Operations | Safety | Storage | MCP tool | Fixture |
| --- | --- | --- | --- | --- | --- |
| Counters | list/get | read_only | `metrika_counters`, `metrika_counter_snapshots` | `management_counter_snapshot` | `tests/fixtures/metrika/counters.json` |
| Counters | create/edit | high_risk_write | `agent_action_audit`, `metrika_config_diffs` | `management_counter_diff` | `tests/fixtures/metrika/counter_update.json` |
| Counters | delete/restore | denied | `agent_action_audit` | none | `tests/fixtures/metrika/counter_delete_denied.json` |
| Counter code/options | get | read_only | `metrika_counter_snapshots` | `management_counter_snapshot` | `tests/fixtures/metrika/counter_code.json` |
| Goals | list/get | read_only | `metrika_goals` | `management_goals_snapshot` | `tests/fixtures/metrika/goals.json` |
| Goals | create/update | low_risk_write | `agent_action_audit`, `metrika_config_diffs` | `management_apply_goal` | `tests/fixtures/metrika/goal_update.json` |
| Goals | delete | high_risk_write | `agent_action_audit`, `metrika_config_diffs` | `management_apply_goal` | `tests/fixtures/metrika/goal_delete.json` |
| Filters | list/get | read_only | `metrika_filters` | `management_filters_snapshot` | `tests/fixtures/metrika/filters.json` |
| Filters | create/update | low_risk_write | `agent_action_audit`, `metrika_config_diffs` | `management_apply_filter` | `tests/fixtures/metrika/filter_update.json` |
| Filters | delete | high_risk_write | `agent_action_audit` | `management_apply_filter` | `tests/fixtures/metrika/filter_delete.json` |
| Operations | list/get/create/update/delete if available | high_risk_write for writes | `metrika_operations`, `agent_action_audit` | `management_operations` | `tests/fixtures/metrika/operations.json` |
| Grants/access/representatives | read | read_only | `metrika_grants` | `management_access_audit` | `tests/fixtures/metrika/grants.json` |
| Grants/access/representatives | write | denied | `agent_action_audit` | none | `tests/fixtures/metrika/access_write_denied.json` |
| Labels | read/write where available | low_risk_write for writes | `metrika_config_diffs` | `management_labels` | `tests/fixtures/metrika/labels.json` |
| Segments | read/write where available | low_risk_write for writes | `metrika_config_diffs` | `management_segments` | `tests/fixtures/metrika/segments.json` |
| Notes/annotations | read/write where available | low_risk_write for writes | `deploy_events`, `metrika_config_diffs` | `management_notes` | `tests/fixtures/metrika/notes.json` |
| Yandex Direct links | read/write where available | high_risk_write for writes | `metrika_config_diffs` | `management_direct_links` | `tests/fixtures/metrika/direct_links.json` |

Policy defaults:

- Delete/restore counter is denied.
- Grant/revoke access is denied.
- Counter edits require manual approval and before/after diff.
- Goal/filter edits require an approved action id.
- All writes require `settings.analytics_live_writes_enabled=true`.

Live smoke:

```bash
python scripts/analytics-smoke.py metrika-management --counter-id 107136069
```

## metrika_reporting

**Implementation status:** `implemented` — `app/services/yandex_metrika_reporting.py`.
Все 5 JSON-эндпоинтов (`table`, `bytime`, `drilldown`, `comparison`,
`comparison_drilldown`) обёрнуты в методы клиента. CSV-варианты (`*.csv`)
доступны через тот же транспорт `YandexOAuthClient`, но отдельных методов-удобств
сейчас нет — при необходимости вызов делается напрямую (`response_format='csv'`
в параметрах). Snapshot-таблицы и аггрегаты в БД заполняются `analytics_ingestion.py`.

Base URL: `https://api-metrika.yandex.net`.

Scope: `metrika:read`.

Shared params: `id`, `ids`, `metrics`, `dimensions`, `date1`, `date2`, `filters`,
`segment`, `sort`, `limit`, `offset`, `group`, `attribution`, `accuracy`.

Shared response metadata: `sampled`, `sample_share`, `sample_size`,
`sample_space`, `contains_sensitive_data`, `data_lag`, `totals`, `min`, `max`.

| Endpoint | Format | Safety | Storage | MCP tool | Fixture |
| --- | --- | --- | --- | --- | --- |
| `GET /stat/v1/data` | JSON | read_only | `metrika_report_snapshots`, aggregates | `metrika_report_table` | `tests/fixtures/metrika/report_data.json` |
| `GET /stat/v1/data.csv` | CSV | read_only | optional raw archive | `metrika_report_table_csv` | `tests/fixtures/metrika/report_data.csv` |
| `GET /stat/v1/data/bytime` | JSON | read_only | `metrika_report_snapshots`, time series aggregates | `metrika_report_bytime` | `tests/fixtures/metrika/report_bytime.json` |
| `GET /stat/v1/data/bytime.csv` | CSV | read_only | optional raw archive | `metrika_report_bytime_csv` | `tests/fixtures/metrika/report_bytime.csv` |
| `GET /stat/v1/data/drilldown` | JSON | read_only | `metrika_report_snapshots` | `metrika_report_drilldown` | `tests/fixtures/metrika/report_drilldown.json` |
| `GET /stat/v1/data/drilldown.csv` | CSV | read_only | optional raw archive | `metrika_report_drilldown_csv` | `tests/fixtures/metrika/report_drilldown.csv` |
| `GET /stat/v1/data/comparison` | JSON | read_only | `metrika_report_snapshots` | `metrika_compare_segments` | `tests/fixtures/metrika/report_comparison.json` |
| `GET /stat/v1/data/comparison.csv` | CSV | read_only | optional raw archive | `metrika_compare_segments_csv` | `tests/fixtures/metrika/report_comparison.csv` |
| `GET /stat/v1/data/comparison/drilldown` | JSON | read_only | `metrika_report_snapshots` | `metrika_compare_drilldown` | `tests/fixtures/metrika/report_comparison_drilldown.json` |
| `GET /stat/v1/data/comparison/drilldown.csv` | CSV | read_only | optional raw archive | `metrika_compare_drilldown_csv` | `tests/fixtures/metrika/report_comparison_drilldown.csv` |

Catalog coverage:

- Session metrics and dimensions: `ym:s:*`.
- Hit/pageview metrics and dimensions: `ym:pv:*`.
- Compatibility rule: do not mix `ym:s:*` and `ym:pv:*` in the same metric/dimension set except inside supported filters.
- Segmentation language: persisted as query text plus normalized hash.
- Attribution models: store requested model on every report snapshot.
- Privacy: reports with `contains_sensitive_data=true` remain queryable but agent output must disclose limited disclosure.

Live smoke:

```bash
python scripts/analytics-smoke.py metrika-reporting --counter-id 107136069
```

## yandex_webmaster

**Implementation status:** `partial` — `app/services/yandex_webmaster_client.py`.
Реализовано: `user`, `hosts`, `host`, `summary`, `diagnostics`, `sitemaps` (read + user-added delete),
`search_queries_popular` (ежедневный синк 08:40 МСК в `webmaster_search_queries`),
`recrawl_queue` / `recrawl_quota` / `submit_recrawl`,
`indexing_history`, `in_search_history`, `search_events_history` / `search_events_samples`,
`links_internal_broken_samples`. Ежедневный снимок: `webmaster_indexing_daily_job` 08:50 МСК.
Не реализовано: important-urls (+ history), owners, verification (read+start), sqi_history,
links/external, sitemap add (`POST user-added-sitemaps`). Эти строки таблицы
ниже — целевой контракт.

Base URL: `https://api.webmaster.yandex.net`.

Scope: Webmaster OAuth scope required by Yandex for verified site access.

Host allowlist: `forecasteconomy.com` и `ru.forecasteconomy.com` (после cutover оба свойства).
Языковой сплит — **не** «Переезд сайта»: Яндекс не переклеивает индекс apex→ru. целиком.
Канон RU живёт на `ru.` (hreflang + self-canonical); apex остаётся EN + x-default.
Документация: [локализованные страницы](https://yandex.ru/support/webmaster/ru/yandex-indexing/locale-pages).

| Endpoint | Operation | Safety | Storage | MCP tool | Fixture |
| --- | --- | --- | --- | --- | --- |
| `GET /user/` | get user id | read_only | `webmaster_hosts` | `webmaster_hosts` | `tests/fixtures/webmaster/user.json` |
| `GET /user/{user-id}/hosts/` | list hosts | read_only | `webmaster_hosts` | `webmaster_hosts` | `tests/fixtures/webmaster/hosts.json` |
| `GET /user/{user-id}/hosts/{host-id}/` | host info | read_only | `webmaster_hosts` | `webmaster_host_summary` | `tests/fixtures/webmaster/host.json` |
| `GET /user/{user-id}/hosts/{host-id}/summary/` | host summary | read_only | `webmaster_host_summaries` | `webmaster_host_summary` | `tests/fixtures/webmaster/summary.json` |
| `GET /user/{user-id}/hosts/{host-id}/important-urls/` | important URLs | read_only | `webmaster_important_urls` | `webmaster_important_urls` | `tests/fixtures/webmaster/important_urls.json` |
| `GET /user/{user-id}/hosts/{host-id}/important-urls/history/` | important URL history | read_only | `webmaster_important_urls` | `webmaster_important_urls` | `tests/fixtures/webmaster/important_urls_history.json` |
| `GET /user/{user-id}/hosts/{host-id}/verification/` | verification info | read_only | `webmaster_hosts` | `webmaster_hosts` | `tests/fixtures/webmaster/verification.json` |
| `POST /user/{user-id}/hosts/{host-id}/verification/` | start verification | high_risk_write | `agent_action_audit` | `webmaster_verification_start` | `tests/fixtures/webmaster/verification_start.json` |
| `GET /user/{user-id}/hosts/{host-id}/owners/` | owners | read_only | `webmaster_owners` | `webmaster_owners` | `tests/fixtures/webmaster/owners.json` |
| `GET /user/{user-id}/hosts/{host-id}/sitemaps/` | all sitemaps | read_only | `webmaster_sitemaps` | `webmaster_sitemaps` | `tests/fixtures/webmaster/sitemaps.json` |
| `GET /user/{user-id}/hosts/{host-id}/sitemaps/{sitemap-id}/` | sitemap details | read_only | `webmaster_sitemaps` | `webmaster_sitemaps` | `tests/fixtures/webmaster/sitemap_detail.json` |
| `GET /user/{user-id}/hosts/{host-id}/user-added-sitemaps/` | user sitemaps | read_only | `webmaster_sitemaps` | `webmaster_sitemaps` | `tests/fixtures/webmaster/user_sitemaps.json` |
| `POST /user/{user-id}/hosts/{host-id}/user-added-sitemaps/` | add sitemap | low_risk_write | `agent_action_audit`, `webmaster_sitemaps` | `webmaster_sitemap_add` | `tests/fixtures/webmaster/sitemap_add.json` |
| `GET /user/{user-id}/hosts/{host-id}/user-added-sitemaps/{sitemap-id}/` | user sitemap detail | read_only | `webmaster_sitemaps` | `webmaster_sitemaps` | `tests/fixtures/webmaster/user_sitemap_detail.json` |
| `DELETE /user/{user-id}/hosts/{host-id}/user-added-sitemaps/{sitemap-id}/` | remove sitemap | high_risk_write | `agent_action_audit` | `webmaster_sitemap_delete` | `tests/fixtures/webmaster/sitemap_delete.json` |
| `GET /user/{user-id}/hosts/{host-id}/sqi_history/` | SQI/IKS history | read_only | `webmaster_sqi_history` | `webmaster_sqi_history` | `tests/fixtures/webmaster/sqi_history.json` |
| `GET /user/{user-id}/hosts/{host-id}/search-queries/popular/` | popular queries | read_only | `webmaster_search_queries` | `webmaster_search_queries` | `tests/fixtures/webmaster/search_popular.json` |
| `GET /user/{user-id}/hosts/{host-id}/search-queries/all/history/` | all query history | read_only | `webmaster_search_queries` | `webmaster_search_queries` | `tests/fixtures/webmaster/search_all_history.json` |
| `GET /user/{user-id}/hosts/{host-id}/search-queries/{query-id}/history/` | query history | read_only | `webmaster_search_queries` | `webmaster_search_queries` | `tests/fixtures/webmaster/search_query_history.json` |
| `GET /user/{user-id}/hosts/{host-id}/recrawl/queue/` | recrawl queue | read_only | `webmaster_recrawl_tasks` | `webmaster_reindex_plan` | `tests/fixtures/webmaster/recrawl_queue.json` |
| `POST /user/{user-id}/hosts/{host-id}/recrawl/queue/` | submit recrawl | low_risk_write | `agent_action_audit`, `webmaster_recrawl_tasks` | `webmaster_apply_reindex` | `tests/fixtures/webmaster/recrawl_submit.json` |
| `GET /user/{user-id}/hosts/{host-id}/recrawl/quota/` | recrawl quota | read_only | `webmaster_recrawl_tasks` | `webmaster_reindex_plan` | `tests/fixtures/webmaster/recrawl_quota.json` |
| `GET /user/{user-id}/hosts/{host-id}/recrawl/queue/{task-id}/` | recrawl task status | read_only | `webmaster_recrawl_tasks` | `webmaster_reindex_plan` | `tests/fixtures/webmaster/recrawl_task.json` |
| `GET /user/{user-id}/hosts/{host-id}/diagnostics/` | diagnostics | read_only | `webmaster_diagnostics` | `webmaster_diagnostics` | `tests/fixtures/webmaster/diagnostics.json` |
| `GET /user/{user-id}/hosts/{host-id}/indexing/history/` | indexing history | read_only | `webmaster_index_history` | `webmaster_indexing_status` | `tests/fixtures/webmaster/indexing_history.json` |
| `GET /user/{user-id}/hosts/{host-id}/indexing/samples/` | downloaded samples | read_only | `webmaster_index_history` | `webmaster_indexing_status` | `tests/fixtures/webmaster/indexing_samples.json` |
| `GET /user/{user-id}/hosts/{host-id}/search-urls/in-search/history/` | pages in search history | read_only | `webmaster_index_history` | `webmaster_indexing_status` | `tests/fixtures/webmaster/in_search_history.json` |
| `GET /user/{user-id}/hosts/{host-id}/search-urls/in-search/samples/` | pages in search samples | read_only | `webmaster_index_history` | `webmaster_indexing_status` | `tests/fixtures/webmaster/in_search_samples.json` |
| `GET /user/{user-id}/hosts/{host-id}/search-urls/events/history/` | search URL event history | read_only | `webmaster_search_url_events` | `webmaster_search_url_events` | `tests/fixtures/webmaster/search_events_history.json` |
| `GET /user/{user-id}/hosts/{host-id}/search-urls/events/samples/` | search URL event samples | read_only | `webmaster_search_url_events` | `webmaster_search_url_events` | `tests/fixtures/webmaster/search_events_samples.json` |
| `GET /user/{user-id}/hosts/{host-id}/links/internal/broken/samples/` | broken internal links | read_only | `webmaster_internal_broken_links` | `webmaster_links_audit` | `tests/fixtures/webmaster/internal_broken_samples.json` |
| `GET /user/{user-id}/hosts/{host-id}/links/internal/broken/history/` | broken internal link history | read_only | `webmaster_internal_broken_links` | `webmaster_links_audit` | `tests/fixtures/webmaster/internal_broken_history.json` |
| `GET /user/{user-id}/hosts/{host-id}/links/external/samples/` | external links | read_only | `webmaster_external_links` | `webmaster_links_audit` | `tests/fixtures/webmaster/external_links_samples.json` |
| `GET /user/{user-id}/hosts/{host-id}/links/external/history/` | external link history | read_only | `webmaster_external_links` | `webmaster_links_audit` | `tests/fixtures/webmaster/external_links_history.json` |

Live smoke:

```bash
python scripts/analytics-smoke.py webmaster --host forecasteconomy.com
```

## google_search_console

**Implementation status:** local read-only API access verified after user consent.
The Search Console API is enabled; `sites` returned `sc-domain:forecasteconomy.com`
with `permissionLevel: siteFullUser`. `app/services/gsc_client.py` supports renewable
OAuth and the existing daily job (09:10 Moscow). Credentials are local; the
production scheduler/credential mount has **not** been activated by this setup.

**Provider UI, 2026-09-21:** `sc-domain:forecasteconomy.com` and the intended owner
account were verified in Search Console. The existing Google Cloud project's
OAuth Audience is **In production**, not Testing. The Russian sitemap was
submitted in the UI alongside the apex sitemap and then showed **Success**.
The subsequent API export confirms both sitemap indexes are processed
(`isPending: false`) with zero errors and warnings:

- Russian: `submitted: 839907`, downloaded `2026-09-20T21:04:11.381Z`
  (2026-09-21 00:04 Moscow).
- Apex: `submitted: 906780`, downloaded `2026-09-20T20:36:30.881Z`
  (2026-09-20 23:36 Moscow).

These are Google's sitemap snapshots, not the current complete site inventory or
indexed-page totals. The returned `contents[].indexed: 0` is a **deprecated field**
that Google explicitly says not to use; it does not mean zero indexed pages.
Search Console API has no equivalent of the UI's full Page indexing report or a
reliable total indexed-page counter. Use the UI for that report and bounded URL
Inspection samples for individual URLs.

**Initial private exports:** `analytics/gsc/{sites,sitemaps,web,image}.json`, all
mode `0600`, ignored by git. Both search exports cover 2026-08-21 through 2026-09-17
inclusive, 28 days in `America/Los_Angeles`, finalized data, dimensions
`query,page,date`. Web returned **20,253 rows across 28 nonempty days**; Image
returned **230 rows across 25 nonempty days**. Neither hit the configured daily
row cap. These are query/page/day rows, not unique URLs or a complete index count.

### Access and credentials

Use the verified Domain property `sc-domain:forecasteconomy.com` to cover both apex
and `ru.`. `sites` lists the properties actually available to the authorized account;
a URL-prefix property only covers its own prefix. `RUSTATS_GSC_SITE_URL` can override
the default `sc-domain:<public_host>`.

The only requested scope is
`https://www.googleapis.com/auth/webmasters.readonly`. This client cannot submit
sitemaps, request indexing, alter properties or read Gmail. Service accounts are
not implemented. Legacy `RUSTATS_GSC_ACCESS_TOKEN` still works for one-off access,
but expires; persistent access uses `RUSTATS_GSC_CREDENTIALS_FILE` pointing to a
private `authorized_user` JSON with `client_id`, `client_secret`, `refresh_token`
and `scopes: ["https://www.googleapis.com/auth/webmasters.readonly"]`.

Default local credentials path: `~/.config/forecasteconomy/gsc-oauth.json`, mode
`0600`. The backend requires the path to be explicitly configured; the local CLI
uses this default directly. Secrets and exported search data never go into git.
In Docker, mount the file read-only and point `RUSTATS_GSC_CREDENTIALS_FILE` at the
**container** path; setting a laptop file path in Compose does not mount it.

OAuth requires the Search Console API to be enabled in the Google Cloud project
and an existing **Desktop** OAuth client. A Cloud login alone does not grant API
access to Search Console. The user's consent connects that client to their verified
property. External OAuth apps left in Testing can issue refresh tokens that expire
after seven days; project publication status must be checked before promising
unattended long-term access. Revocation and token expiry require authorization again.

### Local authorization and exports

Run from the repo root with the backend virtual environment. Global options go
**before** the subcommand. Never paste client secrets or refresh tokens into chat.

```bash
backend/.venv/bin/python backend/scripts/google-search-console.py authorize \
  --client-secrets /private/path/client_secret_desktop.json \
  --no-open --authorization-url-file /tmp/fe-gsc-auth-url.txt
```

Open the URL in that private file in the owner's browser. The helper generates
state and PKCE S256, listens only on `127.0.0.1` for ten minutes, validates state,
exchanges the code, then atomically saves credentials with mode `0600`. Callback
codes and tokens are not logged. Without `--no-open` it opens the system browser.

```bash
# Verify property permission and renewable credentials.
backend/.venv/bin/python backend/scripts/google-search-console.py sites

# Read submitted sitemap statuses (no submit/write operation).
backend/.venv/bin/python backend/scripts/google-search-console.py \
  --output analytics/gsc/sitemaps.json sitemaps

# Finalized query/page/date data, default 28 days ending three days ago (PT).
backend/.venv/bin/python backend/scripts/google-search-console.py \
  --output analytics/gsc/web.json search

# Image-search performance uses its own file/aggregation.
backend/.venv/bin/python backend/scripts/google-search-console.py \
  --output analytics/gsc/image.json search --type image

# Country/device breakdown, optional explicit date range.
backend/.venv/bin/python backend/scripts/google-search-console.py \
  --output analytics/gsc/country-device.json search \
  --dimensions date,country,device --start 2026-09-01 --end 2026-09-15

# A bounded sample, not an indexing request or a live URL test.
backend/.venv/bin/python backend/scripts/google-search-console.py \
  --output analytics/gsc/inspection.json inspect --urls /private/path/sample-urls.txt
```

### Coverage and storage

- `GET /webmasters/v3/sites`: available properties and permission levels.
- `POST /webmasters/v3/sites/{site}/searchAnalytics/query`: finalized daily search
  performance, 25,000 rows per API page, `startRow` pagination, local cap 50,000
  rows per day. The response records when the cap is reached. Search Console
  exposes top rows and can omit queries; this is **not** a complete inventory of
  indexed pages, and summing query-level rows is not a substitute for property totals.
- The scheduled sync refreshes the last seven days in Google's
  `America/Los_Angeles` timezone, persists only `web/query/page/date` in
  `gsc_search_queries`, and uses the existing uniqueness/upsert rule. Country,
  device and image results are separate exports so incompatible aggregations
  cannot overwrite that table. No schema migration is needed.
- `GET /webmasters/v3/sites/{site}/sitemaps`: read-only submitted sitemap status.
- `POST https://searchconsole.googleapis.com/v1/urlInspection/index:inspect`:
  indexed-version snapshots; the CLI deduplicates and limits each run to 20 URLs
  belonging to the chosen property. Google currently allows 2,000/day/property
  and 600/minute/property. All clients share that quota; the local cap is not a
  global daily ledger. Quota/permission errors stop the run without repeated retries.
- Meta `google-site-verification` remains available through
  `RUSTATS_GOOGLE_SITE_VERIFICATION`; this is separate from API authorization.

Indexing API is not implemented. Domain verification, DNS and publication settings
remain Google/owner configuration; the client does not mutate them. Bing meta
`msvalidate.01` remains `RUSTATS_BING_SITE_VERIFICATION`.

### Official references and verification

- [Native-app OAuth / PKCE / refresh](https://developers.google.com/identity/protocols/oauth2/native-app)
- [Refresh-token expiration](https://developers.google.com/identity/protocols/oauth2#expiration)
- [Search Analytics query](https://developers.google.com/webmaster-tools/v1/searchanalytics/query)
- [Sites list](https://developers.google.com/webmaster-tools/v1/sites/list)
- [Sitemaps list](https://developers.google.com/webmaster-tools/v1/sitemaps/list)
- [Sitemap resource: deprecated indexed field](https://developers.google.com/webmaster-tools/v1/sitemaps)
- [URL Inspection](https://developers.google.com/webmaster-tools/v1/urlInspection.index/inspect)
- [API quotas](https://developers.google.com/webmaster-tools/limits)

Local tests: `backend/.venv/bin/python -m pytest backend/tests/test_gsc_client.py -q`.
Provider acceptance passed locally on 2026-09-21: successful OAuth refresh followed
by real Sites, Sitemaps and web/image Search Analytics exports. URL Inspection is
implemented and unit-tested; it was not called in this initial live acceptance.
