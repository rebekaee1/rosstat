# Frontend Instrumentation Inventory

**Last verified:** 2026-07-02 (атрибуция аудитории: `authed`/`user_id` в `frontend_events` + `ym userParams/setUserID`; приём событий развязан с `analytics_enabled`).

## Атрибуция аудитории (2026-07-02)

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

## Counter init (frontend/public/consent.js)

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

## events (reachGoal таксономия)

Источник: `frontend/src/lib/track.js::events`. Ключи snake_case, имена-цели в Метрике.

### Загрузка/выгрузка данных

| Goal | Site | Surface | Параметры |
|---|---|---|---|
| `download_csv` | `IndicatorDetail`, `DemographicsPage` | кнопка «Скачать CSV» | `indicator`, `range`, `category` |
| `download_excel` | `IndicatorDetail` | кнопка «Скачать Excel» | `indicator`, `range`, `category` |
| `download_ical` | `CalendarPage` | кнопка «iCal» | — |

### График и режим

| Goal | Site | Surface | Параметры |
|---|---|---|---|
| `chart_mode_change` | `IndicatorDetail` | `CpiViewModePicker` | `mode`, `code`, `category` |
| `chart_range_change` | `IndicatorDetail` | range-кнопки внутри `IndicatorChart` | `range`, `indicator`, `category` |
| `chart_zoom` | `IndicatorChart` | reset zoom | `action`, `indicator`, `category` |
| `forecast_toggle` | `IndicatorChartSection` | переключатель «Прогноз» | `enabled`, `indicator`, `category` |
| `forecast_view` | `IndicatorForecastSection` | IntersectionObserver ≥40% | `indicator`, `category`, `chartMode` |

### Таблица

| Goal | Site | Surface | Параметры |
|---|---|---|---|
| `table_search` | `DataTable` | search input (debounced) | `query` |
| `table_sort` | `DataTable` | column header click | `order` |
| `table_page` | `DataTable` | pagination buttons | `direction` |

### Сравнение и калькулятор

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

### Календарь

| Goal | Site | Surface | Параметры |
|---|---|---|---|
| `calendar_month_nav` | `CalendarPage` | навигация по месяцам | `direction` |
| `calendar_source_filter` | `CalendarPage` | фильтр источника | `source` |
| `calendar_day_select` | `CalendarPage` | клик по дню | `date` |
| `calendar_clear_day` | `CalendarPage` | сброс выбранного дня | — |

### Демография

| Goal | Site | Surface | Параметры |
|---|---|---|---|
| `demographics_chart_type` | `DemographicsPage` | переключатель типа графика | `type` |
| `demographics_csv` | `DemographicsPage` | кнопка CSV | — |

### Embed Builder

`embed_type_change`, `embed_indicator_select`, `embed_period_change`, `embed_theme_change`, `embed_size_change`, `embed_option_toggle`, `embed_code_tab`, `embed_code_copy`, `embed_runtime_view`. Параметры см. `EmbedBuilder.jsx`.

### Навигация и engagement

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

### Конверсия, лимиты и спрос-поиск (создать в Метрике вручную)

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

### Внешние интеграции

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

### Bridge to backend warehouse

`track(event, params)` дублирует событие в `POST /api/v1/analytics/events` → SQL-таблица `frontend_events` (модель `FrontendEvent`). Это нужно для:

- кросс-чек Метрики (sampling и privacy скрытые сегменты);
- возможности join'ить goals с прочей analytics-warehouse (поиск пользовательских когорт без лимитов API).

Endpoint защищён origin-валидацией `app/api/analytics.py::events_collector`. Не требует токена авторизации (это публичный сборщик с фронта).

## URL cleanup и атрибуция

Источники: `frontend/public/consent.js` (first-hit; очистка URL выполняется всегда, hit — только при согласии) и `frontend/src/lib/cleanUrl.js` (SPA-hits).

### TRACKING параметры, удаляемые перед `ym('hit')`

`etext`, `ybaip`, `yclid`, `ysclid`, `gclid`, `fbclid`, `_openstat`, `openstat`, `clid`, `yandex_referrer`, `_ga`, `utm_source`, `utm_medium`, `utm_campaign`, `utm_term`, `utm_content`, `utm_referrer`, `from`, `ref`, `ref_src`, `source`, `mc_cid`, `mc_eid`, `igshid`.

### Особенность first-hit (public/consent.js)

В первом hit мы НЕ удаляем `utm_*` — они нужны Метрике для атрибуции source/medium/campaign на сессии. Удаляются только tracking-метки Яндекса (`ybaip`, `etext`, `ysclid`, `yclid`) и сторонние (`gclid`, `fbclid` и пр.).

После очистки выполняется `history.replaceState(history.state, '', cleanPath)` — это ключевой момент: иначе Webvisor 2 пишет первую запись с URL=`/?ybaip=1`, и в Метрике появляется отдельный «landing page» вместо `/`. Эта правка убирает 368 «фиктивных» landing'ов в месяц (см. `canvases/metrika-webvisor-deep-2026-05-10.canvas.tsx`).

### SPA-hits (lib/cleanUrl.js)

При navigation в SPA `App.jsx::YandexMetrikaHit` отправляет `cleanPathWithSearch(pathname, search)` — здесь `utm_*` уже включены в чёрный список (атрибуция уже сохранена на первом hit, дублировать не нужно).

### Sync с robots.txt

Список `TRACKING_PARAMS` синхронизирован с директивой `Clean-param` в `frontend/public/robots.txt`. Если добавляете новый tracking-параметр — обновите оба места.

## UTM Taxonomy (для исходящих и share-ссылок)

Источник: `frontend/src/lib/utm.js`. Применяется ко всем нашим share-button'ам, embed-виджетам, social-постам, рассылкам.

### Канонические значения

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

### Direct-кампании (внешний контракт)

UTM проставляются в кабинете Yandex Direct. Шаблон:

```
?utm_source=direct&utm_medium=cpc&utm_campaign={CAMPAIGN_NAME}&utm_content={ad_id}&utm_term={keyword}
```

Где:

- `{CAMPAIGN_NAME}` — kebab-case имя кампании в Direct (например, `ipoteka-2026q2`)
- `{ad_id}` — `{ad_id}` (макрос Direct)
- `{keyword}` — `{keyword}` (макрос Direct)

Без UTM-разметки трафик из Direct пишется в Метрике как смешанный с органикой → атрибуция слепа. Это fallout #1 P0 из `metrika-webvisor-deep-2026-05-10` deep dive.

## Связь с warehouse

Frontend goals + UTM сходятся в трёх местах:

1. **Yandex Metrika UI** — кабинет 107136069, отчёты «Конверсии» / «Источники трафика».
2. **`frontend_events` table** — sql warehouse, доступен через `/api/v1/analytics/events` GET (с токеном) и через MCP `analytics_query_visits` (для агента).
3. **`MetrikaReportSnapshot`** — daily snapshot из Reporting API, агрегаты вокруг goals (см. `analytics_ingestion.py::sync_daily_metrika`).

## Когда обновлять этот файл

- Новый goal в `events` → добавить строку в соответствующую таблицу выше.
- Изменение init-параметров → обновить раздел «Counter init».
- Изменение TRACKING-чёрного списка → обновить раздел «URL cleanup» И `frontend/public/robots.txt`.
- Новая UTM-кампания (Direct/social/email) → добавить в «UTM Taxonomy → utm_campaign».
- Удаление цели → пометить `(deprecated)`, не удалять сразу — иначе сломается ретроактивная аналитика.

## Last verified context

- 2026-05-10: добавлены `compare_open`, `forecast_view`, `category_tile_click`, `related_indicator_click`. Включены `triggerEvent`, `childIframe`, `trackHash` для Webvisor 2. `useScrollDepth` подключён к 4 страницам. UTM-helper применён к Calculator share. Раздел перелинковки category→indicator запущен (`relatedSlugs` в categories.js + блоки на /category и /indicator).
