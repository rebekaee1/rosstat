# Forecast Economy — Project Context

**Last updated:** 2026-08-16 (ADR-0013 Proposed: страна = первый сегмент URL, регионы внутри `/russia`, path-cut на `.com` затем path-identical переезд на `.ru`; карта и счётчики — `docs/backlog.md::Карта миграции URL`). Ранее тем же днём (мировой оперативный срез на официальных первоисточниках: новый парсер-тип `fred_csv` — спотовый Brent Управления энергетической информации США, индекс доллара и доходность десятилетних госбумаг Федрезерва; площадь и население в профиле территории страны — курируемый справочник `app/data/world_country_area.py` плюс concept `population`; страница рейтинга стран только по сопоставимым показателям. Ранее 2026-08-06 — ADR-0011: Eurostat-мир — отдельный TOC-driven data plane с shadow/provenance; до доказанной `sum|avg|last` synthetic частоты карточек fail-closed). Ранее 2026-07-06, вечер (CTO-аудит, дозакрытие хвостов: trap «nginx map с capture-группой» добавлен в traps; adjacency-guard `period_over_period{,_abs}`; батч-hero каталога; COPY-сидер регионов; полная матрица покрытия — `docs/backlog.md::2026-07-06`. Ранее Волна 5: сверены счётчики рядов, source, derived, парсер-типов, ops и generic-семей — актуальные цифры живут в разделах «Indicator» и «Parser» ниже (2026-07-08: минус один авто-сиблинг `wages-nominal-avg-year` после `overrides={"avg-year": "wages-nominal-annual"}` — созвон «На правки 13»); derived-пересчёт стал инкрементальным по dependency-графу в topo-порядке (П-2), «пересчитывает все 31» — история. Ранее 2026-06-24: Фаза 3 — углублена история source-рядов до пола источника: `usd-rub`/`cny-rub`/`gold-price`→1998, `eur-rub`→1999, `m2`→1992, `current-account`→1998 (через `backfill_from`/`backfill_from_year`, деноминация-aware floor; каскад протянул на все уровни матрицы); знаковые квартальные прогнозы закрыты — `trade-balance` тождеством `exports−imports` (`derived_from_source` op=`subtract`, 2-source), `current-account` стратегией `signed_quarterly` (level-diff); skip-лист рядов на полу источника — `docs/backlog.md::A0.3`. Ранее — новая стратегия `generic_quarterly` для положительных квартальных рядов — `exports`/`imports`/`external-debt` получили квартальный прогноз; каскад заполнил прогноз новых yoy-кв/год sibling'ов A0.1. Ранее 2026-06-23 (прогноз во всех режимах: `_mode_forecastable` в `view_model_families` — флаг режима выводится из частоты базы (`yoy/mom/qoq` показывают derived-прогноз, не хардкод False); `monthly_auto` = 36 (+`housing-affordability`/`-primary` собственной моделью на ряде отношения, ретрейн через `scheduler._retrain_self_modeled_derived`); `hero_change` (ускорение Г/г в п.п.) на индекс-карточках; фикс key-rate `_handle_forecasts`). Ранее 2026-06-22 (forecast registry: `monthly_auto` обновлённый алгоритм, 34 ряда).
**Part of:** [`AGENTS.md`](AGENTS.md) (точка входа для AI-агента).
**See also:** [`README.md`](README.md), [`docs/workflow.md`](docs/workflow.md), [`docs/enterprise_resilience.md`](docs/enterprise_resilience.md), [`docs/data_sources.md`](docs/data_sources.md), [`docs/analytics_api_inventory/`](docs/analytics_api_inventory/), [`docs/adr/`](docs/adr/). Parser internals (CBR/Минфин/Rosstat) живут в docstrings `backend/app/services/*_parser.py`.

> Domain glossary for the project. Every architectural discussion, ADR, and refactoring proposal should use the terms defined here. If a discussion needs a new term, add it to this file before finishing.

## Документы рядом

| Файл | Назначение |
|------|------------|
| [`AGENTS.md`](AGENTS.md) | Точка входа для AI-агента: с чего начать, как читать документацию, как её актуализировать |
| [`README.md`](README.md) | Высокоуровневая карта стека, API, indicators, deploy |
| [`docs/workflow.md`](docs/workflow.md) | Модель работы, локальный dev, прод-деплой, smoke C |
| [`docs/enterprise_resilience.md`](docs/enterprise_resilience.md) | Rate-limit, CSP, asset-hash trap, бэкапы, чеклист канарейки |
| [`docs/data_sources.md`](docs/data_sources.md) | Точная карта «индикатор → файл/endpoint» для всех 117 source-индикаторов. Single source of truth — обязательно обновлять при правке источника |
| `backend/app/services/*_parser.py` docstrings | Parser internals (CBR / Минфин / Rosstat): source URL, лист, row/col mapping, `model_config_json` schema, traps. Канонично живёт рядом с кодом |
| [`docs/analytics_api_inventory/`](docs/analytics_api_inventory/) | Инвентарь Yandex API (Metrika, Webmaster) + статус реализации |
| [`docs/adr/0001`](docs/adr/0001-derived-indicators-engine-shape.md) | Engine shape: 822 derived через `DERIVED_SPECS` (43 ручных + 779 generic) + 28 чистых ops |
| [`docs/adr/0002`](docs/adr/0002-derived-always-reflects-source.md) | Инвариант: derived всегда отражает source (`bulk_upsert` идемпотентен) |
| [`docs/adr/0003`](docs/adr/0003-seo-single-source-server-rendered.md) | SEO single-source: backend SSR через `__spa-index.html` + Vite asset discovery |
| [`docs/adr/0004`](docs/adr/0004-rosstat-russian-canonical-sdds-deprecated.md) | Rosstat русский canonical, SDDS English deprecated. Pilot: gdp-nominal end-to-end 2026-05-10 |
| [`docs/adr/0005`](docs/adr/0005-official-calendar-source-bound.md) | Calendar source-bound: public dates only from official source/rule with provenance |
| [`docs/adr/0006`](docs/adr/0006-indicator-card-unification.md) | Indicator card unification: ось «карточка vs derived vs variant vs frequency» (звонок 2026-05-22) |
| [`docs/adr/0008`](docs/adr/0008-regional-bounded-context.md) | Региональный блок: bounded context `регион × показатель × год`, артефакт вместо ETL, дособор из архивных редакций |
| [`docs/adr/0009`](docs/adr/0009-behavior-stream-first-party.md) | Поведенческий поток first-party: `behavior.js` автосбор (клики/мышь/скролл/dwell/copy) → `behavior_events`, retention сырья + вечные агрегаты в Пульсе |
| [`docs/adr/0010`](docs/adr/0010-analytics-contour-identity-goals-marts-olap.md) | Аналитический контур: visitor_id + identity_links, серверные сессии (30 мин), таксономия целей, rollup'ы, единый слой витрин `analytics_marts`, OLAP-копия ClickHouse |
| [`docs/adr/0011`](docs/adr/0011-world-eurostat-data-plane.md) | Eurostat-мир: отдельный TOC-driven data plane, shadow/provenance и fail-closed частоты |
| [`docs/adr/0012`](docs/adr/0012-world-multi-provider-official-first-forecasts.md) | Multi-provider world: только официальные первоисточники, provider-aware identity, единый adapter contract и quality-gated прогнозы |
| [`docs/adr/0013`](docs/adr/0013-country-first-url-architecture.md) | Страна = первый сегмент URL; регионы внутри `/russia`; path-миграция на `.com`, затем path-identical переезд на `.ru` |
| [`docs/indicator-family-playbook.md`](docs/indicator-family-playbook.md) | Семейство до продакшена: продуктовая модель, уровни UI A/B/C; эталоны **ИПЦ** (4×10) и **жильё** (2×3); фазы A–G |

---

## What this is

`forecasteconomy.com` — публичная аналитическая платформа по экономическим показателям России. Собирает данные с Росстата, ЦБ РФ и Минфина, считает производные ряды и прогнозы, отдаёт фронтенду + поисковикам + соцботам + embed-виджетам.

- **Backend**: Python 3.12, FastAPI 0.115 + Uvicorn, SQLAlchemy 2.0 (async, asyncpg), Alembic, APScheduler, statsmodels (forecaster + SARIMA-семейство), pandas/openpyxl/xlrd (parsers), beautifulsoup4 (HTML), requests/httpx (HTTP), Redis 7 (cache).
- **Frontend**: React 19, Vite 7, Tailwind 4, Recharts 3, TanStack React Query 5, GSAP 3, React Router 7, Axios, Lucide, `xlsx` (Excel-экспорт), `@sentry/react` (только фронт — backend без Sentry).
- **Infra**: Docker Compose × 4 (backend, frontend, postgres-16, redis-7), Caddy reverse-proxy на хосте (HTTPS + CSP с десятками `mc.yandex.*` доменов + `frame-ancestors *` для embed), Nginx внутри контейнера frontend (роутинг между SPA-shell и backend SSR), Yandex.Metrika (counter `107136069`) + Yandex.Webmaster, Telegram alerts (`alerting.py`), кастомный Forecast Analytics MCP (`mcp/forecast-analytics-mcp/`).
- **Прод**: `5.129.204.194` (Timeweb Cloud, Ubuntu 24.04, 2 GB RAM).

---

## Domain glossary

### Indicator

Отслеживаемый экономический показатель. Каждый индикатор имеет:

- `code` — slug (`cpi`, `usd-rub`, `gdp-nominal`, `inflation-annual`).
- `name`, `name_en`, `description`, `methodology` — для UI и SEO.
- `unit` — `%`, `руб.`, `млрд руб.`, `млн чел.`, `индекс`, `‰`, `ед.`, ...
- `frequency` — `daily`, `weekly`, `monthly`, `quarterly`, `annual`.
- `source` — `Росстат` / `Банк России` / `Минфин`. Хранится строкой; используется фронтом для подписи и SEO. Терминология «ЦБ РФ» допускается в текстах, но в БД канон — «Банк России».
- `parser_type` — какой парсер обновляет ряд (`rosstat_cpi_xlsx`, `cbr_fx_xml`, `derived`, ...).
- `category` — русская строка категории (`Цены`, `Ставки`, ...). Маппится на `slug` фронта (`prices`, `rates`).
- `model_config_json` — все остальные параметры: `forecast_steps`, `backfill_from_year`, специфика парсера (`dataservice` блок, `bop_target` блок, `element_id`), `approved_forecast_values`, `forecast_strategy` (диспатчинг в реестр стратегий), `derived_forecast` блок (для прогноза-производного-от-источника), `forecast_transform` (для frontend re-scaling, например `cpi_index`).
- **Editorial поля для SEO** (живут в БД, редактируются без деплоя):
  - `seo_title`, `seo_description` — meta для индикатора, fallback к шаблону.
  - `seo_keywords` — meta keywords (37 ручных override + `default_keywords()` fallback).
  - `seo_blocks` — JSON-массив `{title, body}` дополнительных секций под графиком.
  - `is_listed` — boolean: показывать ли карточку индикатора в листинге категории. По умолчанию `true`. `false` — индикатор доступен только через `VariantGroupPicker` внутри родительского индикатора (например, `cpi-food-quarterly` скрыт, виден только при выборе «Состав индекса → продовольственные → квартально» на странице `cpi`).

Хранится в таблице `Indicator`. **Текущее количество (2026-08-23):** 939 рядов в seed; точное число — в `seed_data.py` и `/api/v1/system/status`. Из них 117 source-индикаторов (через 34 парсер-типа) и 822 derived (через `DERIVED_SPECS`: 43 ручных + 779 сгенерированных generic view-mode-семьями, см. `view_model_families.py`).

### DataPoint

Одна точка временного ряда для индикатора. `(date, value)`. Хранится в `IndicatorData` с `UniqueConstraint(indicator_id, date)`.

### Source

Официальный поставщик данных:

- **Росстат** (`rosstat.gov.ru`, `eng.rosstat.gov.ru`). Форматы: SDDS XLSX (стандарт IMF), КЭП XLSX (`ind_MM-YYYY.xlsx`), HTML-бюллетени (недельный CPI), демографические XLSX, годовые XLS (наука/инновации, основные фонды).
- **Банк России** (`cbr.ru`). XML (FX, gold), HTML/UniDbQuery (KeyRate, RUONIA, monetary, reserves), DataService JSON (rates по срочности — mortgage/deposit/auto-loan/credit-rate-corp/ind, M2, current account, exports/imports), XLSX (BOP, debt).
- **Минфин** (`minfin.gov.ru`). CSV для бюджета (revenue, expenditure, deficit).

Каждый источник требует свой SSL/CA setup (Росстат — русские CA-сертификаты, `backend/certs/russiantrustedca2024.pem` через `RUSTATS_ROSSTAT_CA_CERT`).

**Доступ к rosstat.gov.ru из tooling/curl/python**: всегда через `--cacert backend/certs/russiantrustedca2024.pem` (или `verify=` в requests). Без сертификата `rosstat.gov.ru` отдаёт SSL-handshake error / Chrome `chrome-error://chromewebdata/`. `eng.rosstat.gov.ru` работает по стандартному cert, но это SDDS-зеркало и лагает на год (см. trap «SDDS English vs Rosstat русский»).

**Перечисление файлов раздела rosstat**: для категории `/statistics/<section>` (например `/statistics/price`) — `curl --cacert <cert> https://rosstat.gov.ru/statistics/price -o page.html && grep -oE 'href="[^"]*\.xlsx?"' page.html | sort -u` даёт полный список XLSX в разделе. Для `/statistics/price` (категория «Цены») — **94 XLSX** (audit 2026-05-08).

**Политика канонического источника (2026-05-10)**: для индикаторов с источником в Росстате — **only** русский XLSX из `rosstat.gov.ru/statistics/<section>/`, **never** SDDS-английский (`eng.rosstat.gov.ru/storage/mediabank/SDDS_*.xlsx`). См. trap «SDDS English vs Rosstat русский» и план миграции.

### Parser

Конкретная реализация ETL для одного формата источника. Базовый класс `BaseParser` (`backend/app/services/base_parser.py`) — **template-method**: финальный `run()` оркеструет fetch → parse → validate → upsert → forecast retrain → cache invalidate в одном месте. Дочерние классы реализуют `_fetch_and_parse(db, indicator, cfg, fetch_log) -> (points, source_url)` (обязательно) + опциональные hooks `_validate(points, cfg)`, `_post_upsert(...)`, `_handle_forecasts(...)`. Это устранило ~1100 строк boilerplate, унифицировало статусы `fetch_log` и каскад retrain'а.

**Текущее количество (2026-08-22):** 34 парсер-типа в `PARSER_REGISTRY` (см. `rosstat_cpi_parser.py`, регистрируется как singleton-импорт из исторических соображений — артефакт). Включают Rosstat-парсеры (`rosstat_*_parser.py`, в т.ч. demo/ind/science/fixed_assets/weekly_price), CBR (`cbr_*_parser.py` + `cbr_keyrate.py` helper), Минфин (`minfin_budget_parser.py`), Binance (`BinanceBtcUsdtParser`, BTC/ETH/SOL), MOEX (`MoexIndexParser` — индексы и товарные, `BrentDailyFredParser` — legacy-имя, источник MOEX ISS), FRED-CSV (`fred_csv` — публичные ряды первоисточников без ключа: спотовый Brent Управления энергетической информации США, индекс доллара и доходность десятилетних госбумаг Федрезерва). Два типа зарегистрированы, но в seed не используются (задел, не удалять без ревизии прод-БД): `cbr_dataservice_sum`, `cbr_monetary_html`. Файл `rosstat_sdds_fetcher.py` существует, но в PARSER_REGISTRY не зарегистрирован — deprecated (ADR-0004). Один парсер обычно обслуживает несколько индикаторов одного источника: CbrFxParser → 3 валюты; RosstatCpiParser → 4 листа CPI; CbrDataServiceParser → 16+ ставок и агрегатов ЦБ.

### Derived indicator

Индикатор без собственного источника. Считается чистой функцией от других индикаторов. `parser_type = "derived"`. Запускается из `CalculationEngine.run_for_updated_sources` после daily ETL.

**Инвариант (ADR-0002):** *derived[t] всегда выводимо из текущего state source-рядов на момент последнего ETL-батча с новыми строками или ревизиями* (`records_added > 0` или `records_updated > 0`). CalculationEngine пересчитывает derived от первой до последней точки (idempotent — `bulk_upsert` записывает только реально изменившиеся значения). С 2026-07-06 (П-2 CTO-аудита) пересчёт **инкрементальный**: dependency-index строит транзитивное замыкание зависимых от реально обновившихся source и обходит его в топологическом порядке (цепочки derived-от-derived до 4 уровней); полный прогон всех 799 — только `scripts/rebuild-all-derived.py`. Не «инкрементальный накопительный снимок», а чистая функция source. Если source ревизуется задним числом — derived перетягиваются автоматически тем же прогоном (см. ADR-0002 «Limit of the invariant — pure-revision day»).

**Граница инварианта.** Инвариант односторонний: `bulk_upsert`-only. Если source-точка **удаляется** вручную (DELETE из IndicatorData), соответствующая derived-точка остаётся в БД как осиротевшая — engine не знает, что нужно её удалить. Это явный compromise (см. ADR-0002): автоматическое удаление derived создавало бы риск массовой потери данных при ошибке pure op. Ручные коррекции source требуют ручной чистки derived или прогона `scripts/rebuild-all-derived.py`.

Реестр операций (`backend/app/services/derived_ops.py`) — **28 публичных чистых функций** без `db`/`async` (актуализация 2026-08-22; полный список — сам модуль; orphaned `annual_inflation` / `affordability_index` / `rebase_to_index` удалены в чистке 2026-06-24; 2026-08-22 добавлен `series_ratio` для кросс-курсов ЕЦБ). Ядро:
- `quarterly_index` — chained product 3 месячных индексов CPI (для `*-quarterly`).
- `december_to_december` — годовая инфляция «Dec_Y / Dec_{Y-1} − 1» (для CPI-семьи и PPI `*-annual`; пришла на смену rolling-12M в 2026-05-06, см. ADR-0001 «Subsequent additions»).
- `annual_sum` — сумма квартальных или 12 месячных значений (для `gdp-{nominal,real}-annual`).
- `yoy`, `qoq` — рост к 12 мес назад / к предыдущему кварталу (в %).
- `yoy_abs` — **абсолютная** разница к 12 мес назад в единицах источника (звонок 2026-05-22, для balances со знаком, где % бессмыслен).
- `quarterly_avg`, `rolling_avg` — для unemployment.
- `wages_real` — особая, 2 источника (`wages-nominal`, `cpi`).

Реестр спецификаций (`calculation_engine.DERIVED_SPECS`) — **822 entries** (43 ручных + 779 из `view_model_families.iter_derived_specs()`). Ручное ядро:

- **CPI семейство:** `inflation-quarterly` ← `cpi`, `inflation-annual` ← `cpi`, и аналоги для `cpi-food/nonfood/services` (8 spec'ов).
- **PPI:** `ppi-yoy`, `ppi-annual`.
- **GDP:** `gdp-{yoy,qoq}` ← `gdp-nominal`, `gdp-real-{yoy,qoq}` ← `gdp-real`, `gdp-{nominal,real}-annual` (annual_sum).
- **Wages/Unemployment:** `wages-real`, `wages-yoy`, `unemployment-{quarterly,annual}`.
- **Trade/External:** `exports-{yoy,qoq}`, `imports-{yoy,qoq}`, `trade-balance-yoy-abs`, `current-account-yoy-abs`. Старый `current-account-yoy` (%) **депрекейтнут** в seed_data как `is_active=false`, в DERIVED_SPECS убран — для balances со знаком процент YoY бессмыслен.
- **Other:** `ipi-yoy`, `housing-yoy-{primary,secondary}`.

**Frontend-only режимы (звонок 2026-05-22).** Поверх backend-derived'ов есть единый реестр view-mode families: `frontend/src/lib/viewModeFamilies.js::VIEW_MODE_FAMILIES`. Каждая семья (`exports`, `imports`, `trade-balance`, `current-account`, `*-monthly`, `wages-nominal`, `unemployment`, `housing-price-{primary,secondary}`) маппит parent → массив `modes[]`: `{mode, label, code, unit?, transform?}`. Routing в `IndicatorDetail.jsx`: `findViewModeFamily(code)` → `?mode=…` подменяет dataPoints, телеметрию и заголовок без перехода на другой URL.

Frontend-only трансформации:
- `applyMoMTransform(points)` — MoM% для `*-monthly` (Phase 1): `(val_t/val_{t-1} − 1) * 100`, backend spec сознательно не заводится.
- `applyAggregateTransform(points, granularity)` — bucket-avg для daily-индикаторов (Phase 5): `granularity ∈ {week, month, quarter, year}` → среднее по bucket'у с датой = конец bucket'а. Применяется к любому `indicator.frequency === 'daily'` (`key-rate`, `ruonia`, `cbr-fx-*`, `gold-price`, `brent`, `btc-usd`) без новых backend-derived.

Phases:
- Phase 1 — trade (4 quarterly + 4 monthly семьи).
- Phase 2 — labour: `wages-nominal` (4 режима: Номинальная / Реальная / YoY / Индекс), `unemployment` (3 режима: Месячно / Квартально / 12М avg).
- Phase 3 — housing prices (Уровень индекса / YoY %).
- Phase 5 — daily aggregation (виртуальные week/month/quarter/year avg).

Phase 4 (ставки) НЕ использует viewModeFamilies: `credit-rate-corp-short`, `credit-rate-ind-short`, `deposit-rate` — единые карточки с **VariantGroupPicker** (срок: До 1 года / 1-3 года / Свыше 3 лет). Это не «режим отображения», а отдельные индикаторы по сроку.

### Матрица представлений (representation matrix)

Каноническая модель «полноты» индикатора, эталон — двухуровневый переключатель ИПЦ (`frontend/src/lib/cpiViewModeGroups.js`). Полнота — это **матрица из двух осей**:

- **Верхняя ось — ТИП представления** (что показываем): `value` уровень/средняя/на конец/за период · `pop` к прошлому периоду (Н/н·М/м·Кв/Кв·Г/г-календарный) · `yoy` к соотв. периоду пред. года (rolling) · `index` индекс (rebase к базе).
- **Нижняя ось — ЧАСТОТА** (за какой промежуток): `week` · `month` · `quarter` · `year`.

Каждая «ячейка» (тип × частота) — либо есть у индикатора (режим/sibling-код), либо пуста. Пустая ячейка относительно **ожидаемого по природе ряда** — это пробел (кандидат на добавление режима, не дефект: для ставки `index` не нужен, у годового счётного ряда нет `pop`).

**Природа ряда** (детерминированно из билдер-типа `view_model_families.py` или `unit`): `rate` (T1/T2/T2y) · `stock` (T3/T4/T5) · `flow` (T6) · `signed-flow` (T7/T9s, baланс со знаком → `yoy_abs`, нет `index`) · `avg-level` (T8 зарплата/занятость) · `gdp` (T9) · `annual-count`/`annual-signed` (T10/T10a) · `ratio-index` (T12, отношение индексов — уровень-ряд, без rebase-группы) · `index` (ИПЦ/ИЦП/ИПП, `unit=индекс` — уровень ряда = сам индекс, величину закрывает группа `index`).

**Ожидаемая матрица** на природу — единая точка истины: `expected_matrix(nature, native)` в `scripts/completeness.py`. **Present** generic-семей берётся из билдеров (authoritative), bespoke (cpi/ppi/housing) — из их режим-реестров.

**Аудит полноты** (read-only) генерируется в `docs/indicator-index.json::completeness` + срез в `docs/indicator-index.md` (модуль `scripts/completeness.py`, вызывается из `build-indicator-index.py`, под guard `--check`). На каждый КОРЕНЬ-семейство: `present`/`expected`/`missing`-ячейки, `matrix_score` и 4 измерения паспорта — `texts` (description+methodology в seed; **у ИПЦ-семьи методология живёт в `cpiViewModeContent.jsx`**, не в seed → `partial` там ожидаем), `forecast`, `grouping`, `seo`. Системный вывод первого прогона (2026-06-24): доминирующий пробел — `yoy:quarter`/`yoy:year` почти у всех sub-annual семей (rolling Г/г есть только на нативной частоте).

**Заполнение матрицы (2026-06-24).** Доминирующий пробел закрыт: группа «Г/г» стала **многоуровневой** (по месяцам/кварталам/годам) во всех generic-билдерах через единый helper `view_model_families.py::_yoy_modes(base, freq, ov, method=, abs_delta=)`. Метод свода суб-периодов к кварталу/году — по природе ряда: `last` (ставки/запасы/индекс), `avg` (зарплата/занятость, индекс-отношение T8/T12), `sum` (потоки/ВВП/сальдо; для знаковых — `abs_delta=True` → `yoy_abs`). Пайплайн `(period_<method> gran → yoy[_abs])` исполняется в `calculation_engine`; неполный текущий квартал/год отбрасывается (`derived_ops._aggregate`), прогноз протягивается `_mode_forecast_meta` (guard полноты bucket'а). +105 sibling-рядов (104 yoy-кв/год + `international-reserves-mom`), все авто-seed + авто-скрыты из листинга, тексты — period-aware в `seed_data._sibling_texts`. Правдивость сверена независимо (`budget-revenue-yoy-year`, `m2-yoy-quarter`). Аудит после заполнения: 78/91 корней complete; остаток 13 — bespoke-канон CPI/ПЦП/жильё (свои тексты/реестры, не трогаем без отдельного решения) + by-design (`wages-nominal-annual` — историч. режим карточки, не каталог; `ipi`/housing `pop:year` ≈ `yoy:year`).

### Forecast

Прогноз индикатора на N шагов. Хранится в `Forecast` (метаданные + `is_current`) + `ForecastValue` (точки `(date, value, lower_bound, upper_bound)`).

**Реестр стратегий** (`backend/app/services/forecast_strategies/registry.py`) — диспетчеризует прогноз-генерацию по полю `Indicator.model_config_json.forecast_strategy`:

| Имя | Когда применяется | Что делает |
|---|---|---|
| `cpi_combined` | `cpi`, `cpi-food`, `cpi-nonfood`, `cpi-services` | Гонит `train_monthly_cpi` (помесячный) + `train_inflation_12m` (12-мес скользящий) и каскадит результат на `*-quarterly` derived |
| `housing_quarterly` | `housing-price-primary`, `housing-price-secondary` | `train_quarterly_housing` — 1:1 port `Прогнозы_цены_на_жилье (1).ipynb` Никиты (multi-window OLS на log-diff + outlier-clip + corr-filter + iv-weighted blend + per-step median). Byte-exact с notebook'ом |
| `gdp_nominal_quarterly` | `gdp-nominal` | `train_gdp_nominal_quarterly` (multi-window OLS на log-diff, без блендинга) — 1:1 port `Прогноз_номинальный_ВВП.ipynb` |
| `gdp_real_quarterly` | `gdp-real` | `train_gdp_real_quarterly` — то же ядро `_train_gdp_quarterly_port` на ряду реального ВВП; byte-exact с notebook'ом |
| `gdp_consumption_quarterly` | `gdp-consumption` | `train_gdp_consumption_quarterly` — то же ядро `_train_gdp_quarterly_port` на ряду расходов домохозяйств (методология семьи ВВП по просьбе Никиты; отдельного notebook'а нет) |
| `gdp_government_quarterly` | `gdp-government` | `train_gdp_government_quarterly` — то же ядро `_train_gdp_quarterly_port` на ряду гос.потребления |
| `generic_quarterly` | `exports`, `imports`, `external-debt` (2026-06-24) | `train_generic_quarterly` — то же ядро `_train_gdp_quarterly_port` (log-diff семьи ВВП) для **положительных** квартальных рядов без своего notebook'а; model_name из кода. Закрыл запрос созвона «квартальным тоже нужны прогнозы». **Не для знаковых** (сальдо/счёт — log-diff неопределён) |
| `signed_quarterly` | `current-account` (2026-06-24) | `train_signed_quarterly` — то же ядро `_train_gdp_quarterly_port`, но `transform="level"` (multi-window OLS на **первой разности уровня**, аддитивная реконструкция). Знако-устойчива — для квартальных сальдо/счетов со сменой знака, где log-diff неопределён. `trade-balance` сюда НЕ входит: он прогнозируется тождеством (см. `derived_from_source` op=`subtract`) |
| `ppi_monthly` | `ppi` | `train_ppi_monthly` (k=1..4, monthly lags log-diff) — 1:1 port `Прогноз_ИЦП.ipynb` |
| `monthly_auto` | 36 месячных рядов (`MONTHLY_AUTO_FORECAST_CODES` в `seed_data`): wages, unemployment, M0/M2, доходы/расходы/дефицит бюджета, торговый баланс, экс/имп товаров и услуг, **construction-work / retail-trade / ipi** (2026-06-22), **housing-affordability / -primary** (2026-06-23, derived-ряд отношения, собственная модель) и др. **Кроме ИПЦ-семьи** (своя `cpi_combined`) | `train_monthly_auto` — ADF-автотрансформ (level/dif/log) + multi-window OLS по лагам `[m,m+1,m+2,12]`. Обновление 2026-06-22 (`Прогноз_месячных_данных.ipynb`): rolling(m)-сглаживание изменений для нестационарных рядов + пер-горизонтная реконструкция `последнее + m·aux[m]`. Срезы `-mom`/`-yoy` тянутся через `derived_from_source`. **Видимость прогноза в режиме** карточки определяет `_mode_forecastable` (фронт-флаг = частота базы протягивает прогноз), а не per-mode хардкод. Derived с собственной моделью (доступность жилья) ретрейнятся в `scheduler._retrain_self_modeled_derived` после движка (источниковый каскад их не покрывает) |
| `approved` | исторически: `cpi-*`, `gdp-nominal`, `ppi`, `housing-price-*` | Использует ручные значения из `model_config_json.approved_forecast_values` (массив `{date, value}`) без переобучения. **В live-конфиге не используется** — все индикаторы переведены на свои live-стратегии (`ppi → ppi_monthly`, 2026-05-16). Strategy сохраняется в registry для обратной совместимости и тестовых сценариев |
| `derived_from_source` | Все *-yoy, *-qoq, *-annual derived с `derived_forecast: {source_code, operation, model_name}` (включая `housing-yoy-primary`, `housing-yoy-secondary`); **`trade-balance`** (op=`subtract`, 2026-06-24) | Применяет ту же чистую op (yoy / qoq / december_to_december / annual_sum / real_from_yoy / **subtract**) к **прогнозу** source-индикатора. `subtract` берёт ДВА источника (`source_code` + `source_code_2`) — тождество `trade-balance = exports − imports`, согласовано с прогнозами компонент. Каскадный retrain срабатывает после успеха любого из источников |
| `generic_ols` | `inflation-weekly`, fallback | `train_and_forecast` (multi-window OLS с inverse-variance weighting); универсальная модель |

**Поля связки:**

- `model_config_json.forecast_strategy` — имя стратегии (если не задано — fallback `legacy_resolve(indicator)`).
- `model_config_json.derived_forecast` — `{source_code, operation, model_name}` для `derived_from_source` стратегии.
- `model_config_json.forecast_transform` — например `cpi_index` для `inflation-weekly`: значения возвращаются как уровень индекса 100.x; фронт пересчитывает в delta через `adjustCpiForecastDisplay`.
- `model_config_json.approved_forecast_values` — массив для approved-стратегии.
- `model_config_json.forecast_steps` — горизонт. По умолчанию 12 (`RUSTATS_FORECAST_STEPS`).

**Каскадный retrain.** После успешного retrain индикатора-источника (в `forecast_pipeline.retrain_indicator_forecast`) ищем все индикаторы, у которых `derived_forecast.source_code == this.code`, и retrain их рекурсивно с защитой от циклов. Это заменило старый side-effect `_propagate_cpi_forecast_to_derived`, который остался для cascade `cpi → cpi-{food,nonfood,services}-quarterly`, но `*-annual` (Dec-to-Dec) теперь живут отдельной стратегией.

### ETL run

Запуск одного парсера для одного индикатора. Записывается в `FetchLog`:

- `status` ∈ `running` / `success` / `no_new_data` / `failed` / `timeout`.
- `started_at`, `completed_at` (TIMESTAMP WITHOUT TIME ZONE — все datetime tz-naive!).
- `records_added`, `error_message`, `source_url`.

Внимание: `fetch_log.records_added` записывает **только новые строки**, не in-place revisions. `bulk_upsert` возвращает `(records_added, records_updated)`, но в `BaseParser.run()` поле в БД заполняется только из `records_added`. Это влияет на dispatch derived (см. ADR-0002 «Limit of the invariant — pure-revision day»).

Daily ETL (06:00 МСК, `RUSTATS_SCHEDULER_CRON_HOUR/MINUTE`) запускает все `is_active=True` non-derived индикаторы → `CalculationEngine.run_for_updated_sources` для derived (если хотя бы один parser добавил новые строки) → `_promote_past_events` для календаря.

**Calendar refresh** (`calendar_refresh` job): отдельный daily cron 03:00 МСК прокатывает `seed_calendar(months_ahead=12)`, который теперь вызывает official calendar ingest (`calendar_sources.official_calendar`). Public API отдаёт только source-bound rows: `date_confidence IN ('official_explicit', 'official_rule')`, `is_estimated = false`, заполнены `event_key`, `source_url`, `source_hash`, `last_seen_at`. Estimated rows и legacy backfill без provenance остаются внутренним fallback и скрыты (см. термин «Calendar event» и ADR-0005).

**Analytics scheduler** (опционально): если `RUSTATS_ANALYTICS_SCHEDULER_ENABLED=true` — два дополнительных cron-а: hourly :15 (Yandex Metrika reporting sync) и daily (management snapshot). По умолчанию выключен.

### Category

Функциональная группа индикаторов: Цены, Ставки, Финансы, **Рынок труда**, ВВП, Торговля, Бизнес, Население, Наука. Девять штук. На главной — сетка карточек, на `/category/{slug}` — список индикаторов в категории.

В БД хранится русское имя (`Цены`, `Рынок труда`); URL использует slug (`prices`, `labor`). Маппинг — `frontend/src/lib/categories.js` (включает `seoTitle`/`seoDescription`, идентичные backend `seo_content.py::CATEGORY_META.title/description` — это **зеркало backend SSR**, не источник правды; см. ADR-0003).

### Calendar event

Запись в `EconomicEvent` для расписания публикаций (релиз CPI Росстата, заседание совета директоров ЦБ, недельный ИПЦ Росстата, международные резервы РФ). После ADR-0005 public calendar **source-bound**: событие показывается пользователю только если `date_confidence = official_explicit` (официальная дата из календаря/ICS/страницы) или `official_rule` (дата рассчитана по опубликованному правилу + versioned `ru_working_calendar` с source_url), `is_estimated = false`, и заполнены `event_key`, `source_url`, `source_hash`, `last_seen_at`. `estimated` rows и миграционные legacy rows без provenance скрыты из `/api/v1/calendar`, `/upcoming` и iCal. Переносы обновляются по stable `event_key`, старая дата хранится в `metadata_json.reschedule_audit`. Статус `scheduled` → `released` автоматически промотится по `scheduled_date < today`.

### Embed widget

Внешний виджет, встраиваемый по `<iframe>` (5 типов: chart, card, table, ticker, compare) или SVG-эндпойнтам (`/api/v1/embed/spark/{code}.svg`, `/card/{code}.svg`, `/badge/{code}.svg`). Имеют отдельный CSP в Caddy (`frame-ancestors *`), отдельный rate limit (600/мин в `RateLimitMiddleware`), impression tracking (`/api/v1/embed/impression`, `/pixel.gif`).

### Approved forecast

Ручные прогнозные значения от Никиты (партнёр), хранящиеся в `Indicator.model_config_json.approved_forecast_values` (массив `{date, value}`). Применяются стратегией `approved` в forecast registry без переобучения модели.

### SEO meta bundle

Пакет meta-данных для индикатора/категории/страницы: `seo_title`, `seo_description`, `seo_keywords`, `canonical`, JSON-LD, OG image, twitter card.

**Принцип хранения (ADR-0003 — Accepted, см. файл):** разделение по природе.

- **Редакционный контент** живёт в БД (`Indicator.seo_title`, `seo_description`, `seo_keywords`, `seo_blocks`, `is_listed`). Меняется людьми, без деплоя — через прямой UPDATE или будущий admin-UI.
- **Шаблоны и fallback** живут в коде: правила генерации seo_title для индикаторов, у которых ручной override пуст (`backend/app/services/seo_renderer.py` + `default_keywords()`); общие SEO-блоки для всех индикаторов; форматирование. Меняются через деплой.
- **Frontend читает из API и зеркалит SSR** — никаких локальных констант не осталось (`SEO_MAP`, `INDICATOR_BLOCKS`, `HIDDEN_FROM_LISTING` удалены в Шаге 4 фазы 2). Backend-SSR через `/seo/page/*`, `/seo/category/{slug}`, `/seo/indicator/{code}` — единственный источник правды; frontend `useDocumentMeta(null)` no-op до подгрузки данных, потом ставит то же, что лежит в SSR.

**SEO-автоматика (2026-06-12, ADR-0003 «Subsequent additions») — всё data-driven из БД, при добавлении индикатора руками ничего не делать:** sitemap (lastmod из последней точки, priority по `is_listed`), related-блоки (flagship-first, только listed), годовые landing'и `/indicator/{code}/{year}` (SSR без React-bundle), OG-превью `/og/{code}.png` (Pillow-спарклайн), RSS `/feed.xml`, IndexNow-пинг после daily ETL (`services/indexnow.py`), ETag/304 на SSR, autolink терминов в seo_blocks (`AUTOLINK_TERMS`), critical CSS (`SEO_CRITICAL_CSS` — синхронизировать при смене дизайн-токенов). Обязательное ручное действие — только осмысленные `seo_keywords` (fallback `default_keywords()` сработает, но curated лучше).
- **`/__spa-index.html`** — raw Vite SPA shell с заголовком `X-Robots-Tag: noindex, nofollow`. Используется backend SSR-renderer'ом для discover текущих hashed JS/CSS asset-имён. Не индексируется.

Исторически (до Шага 4 фазы 2, 2026-05-05) дублировалось в 4 местах: `seed_data.py`, `SEO_MAP` (frontend), `INDICATOR_BLOCKS` (backend), `categories.js HIDDEN_FROM_LISTING`. Сейчас — один источник в БД + код-fallback.

### Forecast Analytics OS

Отдельный backend-слой для интеграции с Yandex.Metrika / Yandex.Webmaster / SEO crawler. Включает:

- **Yandex клиенты:** `app/services/yandex_metrika_management.py`, `yandex_metrika_reporting.py`, `yandex_metrika_logs.py`, `yandex_webmaster_client.py`, `yandex_client.py`.
- **Ingestion / backfill / features:** `analytics_ingestion.py`, `analytics_backfill.py`, `analytics_features.py`.
- **Action policy / executor:** `action_policy.py`, `action_executor.py` — safety classes (read_only / low_risk_write / high_risk_write / denied).
- **API:** `app/api/analytics.py` (10 endpoints под `Authorization: Bearer ${RUSTATS_ANALYTICS_API_TOKEN}`).
- **Warehouse models:** `AnalyticsSyncRun`, `AnalyticsWatermark`, `MetrikaCounterSnapshot`, `MetrikaGoalSnapshot`, `MetrikaReportSnapshot`, `MetrikaDailyPageMetric`, `MetrikaSearchPhrase`, `RawMetrikaVisit`, `RawMetrikaHit`, `WebmasterDiagnostic`, `WebmasterSearchQuery`, `SeoPageSnapshot`, `AgentFinding`, `AgentActionAudit`, `FrontendEvent`, `Experiment`.
- **MCP:** `mcp/forecast-analytics-mcp/` (Node.js, 7 tools), интегрирован в Cursor через `~/.cursor/mcp.json`. Нужен для агента-аналитика; ходит в backend `/api/v1/analytics`.
- **Scope:** read-only Metrika tools работают; live writes выключены флагом `RUSTATS_ANALYTICS_LIVE_WRITES_ENABLED=false`. Webmaster и data-import API — endpoint-ы перечислены в `docs/analytics_api_inventory/`, но требуют дополнительных OAuth scopes (см. inventory README header).
- **Frontend instrumentation:** init-параметры Метрики, таксономия goals (`reachGoal`), UTM-разметка share-ссылок и URL cleanup описаны в [`docs/analytics_api_inventory/frontend_instrumentation.md`](docs/analytics_api_inventory/frontend_instrumentation.md). Webvisor 2 + form analytics включены через `webvisor:true, triggerEvent:true, childIframe:true` (2026-05-10). Каждый клик в `lib/track.js::events` дублируется в `frontend_events` через `POST /api/v1/analytics/events`.

### User / Identity (ADR-0007, Phase 1+2 реализованы локально 2026-06-19)

Словарь акторов для личного кабинета (lead-gen, звонок-стратегия). Phase 1 (email+пароль, OAuth Яндекс/VK + fake, сессии в Redis, 152-ФЗ-минимум) реализована: `app/api/{auth,oauth}.py`, `app/services/{session.py,identity/,oauth/}`, `app/security/`, Alembic `20260619_identity`. Боевые Яндекс/VK требуют реальных app-кредов (pre-prod чеклист в ADR-0007). **Phase 2 (2026-06-19):** серверный download-gate (`app/api/export.py`, гость 2 выгрузки/сессия через cookie `fe_dl` + Redis `fe:dl:*`, авторизованный — безлимит), телефон в `OAuthIdentity.phone` (Alembic `20260619_oauth_phone`), согласие на рассылку (`Consent kind="newsletter"`), `GET /auth/oauth/providers` + брендовые кнопки, redirect-override + compat-роутер, Telegram-бот (уведомление о регистрации `notify_new_user` + ежедневный дайджест `telegram_daily_digest_job` со статистикой Метрики/целей-CTA), UI (хедер-блок авторизации, инлайн-поиск, `RegisterNudge`). См. ADR-0007 «Subsequent additions».

- **Visitor** — анонимный посетитель без идентичности. Дефолт всего публичного сайта (ADR-0003, SEO). Остаётся таким: никаких wall'ов на контент/графики/прогнозы.
- **User** — человек, у которого есть хотя бы одна `OAuthIdentity`. Появляется только после входа. Доменная сущность; e-mail не PK (PK — внутренний id).
- **OAuthIdentity** — привязка `(provider, provider_user_id, verified_email)`. У одного `User` может быть несколько (Яндекс + VK = один `User`, две привязки). Провайдеры — реестр в стиле `PARSER_REGISTRY` (не if-else). **Phase 1 провайдеры: Яндекс ID, VK ID** (у VK email не гарантирован → `User` может быть без email) **+ email+пароль**. Mail.ru и прочие — потом, одной записью в реестре.
- **Фазность (звонок-грилл 2026-06-19).** **Phase 1 (локально, всё E2E):** регистрация/вход (Яндекс, VK, email+пароль) + личный кабинет + сквозные user-path'ы. Почты на Phase 1 **нет вообще** → нет подтверждения email, сброса пароля, double-opt-in, рассылок. **Phase 2+:** почтовый провайдер (за `NotificationChannel`), download-gate (домен Export), подписки/рассылки (домен Notifications), монетизация.
- **Инвариант на будущее (Phase 2): рассылка — только double-opt-in.** Регистрация по email остаётся без подтверждения (низкое трение, вход и выгрузка сразу), но в список рассылки — только подтверждённый email (ст. 18 ФЗ «О рекламе» + защита деливерабилити: неподтверждённые → bounce → бан sending-домена). Транзакционную почту вводим в Phase 2 вместе с рассылками.
- **Личный кабинет** — UI-поверхность (`/account`), не отдельная сущность. В домене оперируем `User`. Весь `/account/*` — `noindex`, вне sitemap.
- **Partner/Admin** (Никита) — отдельный актор, **не** обычный `User`. Сейчас неявно живёт в `Approved forecast`. OAuth-регистрация Visitor'а **не** даёт editorial-прав.
- **Резолв идентичности (инвариант).** Email не живёт на `User` (нет глобальной уникальности `User.email`) — он атрибут способа входа: `OAuthIdentity` (ключ `(provider, provider_user_id)`) либо `EmailCredential` (`email` уникален, `email_verified=false` на Phase 1). Автосвязывание разных способов в один `User` — **только когда оба email верифицированы и равны**; парольный (неверифиц.) аккаунт никогда не мерджится автоматически; кросс-способ связывание — вручную из кабинета под активной сессией. Это закрывает pre-hijack (нельзя подменить аккаунт жертвы, заранее заняв её email паролем без подтверждения).
- **Трап: публичный кэш не варьировать по auth-куке.** `fe_sess` cookie летит на все same-origin запросы, но публичные эндпоинты (`/api/v1/indicators/...`, SSR) сессию **не читают** и кэш по куке **не варьируют** — иначе общий Redis-кэш дробится по юзерам и убивает SEO-трафик. Сессию читают только `/auth/*`, `/account/*` и приватные ручки.

Не путать с `RUSTATS_ANALYTICS_API_TOKEN` (Forecast Analytics OS) — это машинный bearer-токен для MCP-агента, не идентичность конечного пользователя.

Цель кабинета — **lead-gen**: вход через OAuth открывает полную выгрузку рядов (gate только на download, см. домен Export) и собирает согласие на рассылки о выходе данных (домен Notifications). Не монетизация, не платный wall. Детали — ADR-0007 (в работе).

### Мировой multi-provider блок (ADR-0011/0012)

Отдельный bounded context с осью `provider × страна × dataset × slice × период`.
Eurostat — первый адаптер, а не универсальный источник для всех стран.

- **Official-first** — ряд поступает только из официального национального ведомства,
  центрального банка, таможни, министерства, официальной биржи или
  наднационального статистического органа. Национальный первоисточник имеет
  приоритет; коммерческие и новостные агрегаторы запрещены.
- **Provider** — машинный код издателя (`eurostat`, далее `bea`, `bls`, `ibge`,
  `mospi`, `nbs` после отдельной проверки). Он входит в identity и provenance;
  публичное поле `source` — человекочитаемое имя организации.
- **WorldSourceAdapter** — единый контракт catalogue → series identity →
  dimensions/frequency/unit → observations/revision metadata. Product-слои не
  знают wire-формат ведомства.
- **WorldConcept** — вручную доказанная семантическая связь рядов разных стран и
  providers. Совпадение названия/единицы само по себе сравнение не открывает.
- **WorldForecast** — отдельный от России прогнозный контур. Публичен только для
  свежего регулярного M/Q primary-series, где rolling-origin `MASE < 1` и модель
  минимум на 2% точнее seasonal-naive. Не прошедший gate ряд корректно остаётся
  без прогнозной линии.

### Региональный блок (ADR-0008, реализован локально 2026-07-02)

Отдельный bounded context с осью `регион × показатель × год` — НЕ часть макро-каталога. Источник — годовой сборник Росстата «Регионы России. Социально-экономические показатели» (Excel-приложение с 2024, ранее Word).

- **Region** — территория: РФ, 8 федеральных округов, 85 субъектов, 2 агрегата-остатка (Архангельская/Тюменская без АО). Канонический реестр + нормализация имён строк Росстата — `scripts/regional/regions_registry.py`.
- **RegionIndicator** — показатель сборника (489 штук, 22 раздела; разделы 21 «Внешняя торговля» и 22 «Правонарушения» дособраны из архивных редакций). Кода макро-`Indicator` не касается.
- **RegionDataPoint** — годовая точка `(indicator, region, year)`; 960 926 точек, 1990–2024.
- **Артефакт вместо ETL**: `scripts/regional/parse_pril_2025.py` → `backfill_pril_2022_2023.py` → `backfill_word.py` пишут `backend/app/data/regional/` (коммитится); `seed_regional.py` идемпотентно заливает из entrypoint. Планировщик региональные данные не трогает; обновление — раз в год руками по новому архиву.
- **Прогнозов и derived нет** намеренно: годовая частота, полный пересмотр издания. Динамика Г/г считается на лету.
- UI: `/regions` → `/region/{slug}` → `/region/{slug}/{code}`; SSR/sitemap/OG — по ADR-0003 (`seo_regional.py`).

---

## Operational invariants and traps

Вещи, которые ломаются неочевидно. Каждый пункт — проверенный пост-мортем.

### Asset-hash mismatch trap

После `docker compose build frontend` без перезапуска backend — backend SEO renderer возвращает HTML со ссылками на удалённые `/assets/*-OLD-HASH.js`. Причина: `seo_renderer._APP_ASSETS` кэширует discover'ные имена файлов в памяти процесса.

**Правило:** при rebuild фронта всегда делать `docker compose up -d backend frontend` одновременно (backend перезапустится, кэш сбросится). Альтернатива: `docker compose restart backend && redis-cli -n 0 FLUSHDB` (только DB 0 — кэш; в DB 1 живут сессии/квоты, их не трогать).

### Pure-revision day

Описано в ADR-0002. Если в ETL-батч ни один парсер не добавил новые строки (только in-place revisions), `run_for_updated_sources` не сработает; derived останутся stale до следующего «обычного» дня. Митигируется тем, что `cbr-fx`/`cbr-ruonia`/`gold-price`/`key-rate` — daily-источники. На практике pure-revision day без `records_added > 0` — крайне редкое явление. Жёсткий триггер ручного катчапа: `scripts/rebuild-all-derived.py`.

### Derived-forecast ordering trap (прогноз поверх свежего факта)

Инцидент 2026-08-05: на карточках «ВВП и рост» режим «К прошлому периоду» рисовал свежий факт Q1-2026 как ПРОГНОЗ. Причина — гонка двух каскадов: source-ETL ретрейнит `derived_from_source` siblings (`_retrain_dependents`) ДО того, как CalculationEngine досчитал их собственный факт. Фильтр `derived_from_source._select_forecast_points` отсекает прошлое по stale-факту derived-ряда → прогноз получает точку на дате, которая минутой позже становится фактом, а collision-policy фронта (`chartForecastMerge.js`: «на последней дате факта прогноз побеждает» — нужна для partial-bucket агрегатов) рисует её как прогноз.

**Правило:** прогноз derived-ряда валиден только относительно СВЕЖЕГО собственного факта. Поэтому после `calculation_engine.run_for_updated_sources` вызывается `_retrain_recalculated_derived` (scheduler.py), ретрейнящий ВСЕ пересчитанные derived с активной стратегией — включая `derived_from_source` (исключение для них отсюда убрано 2026-08-05). Исключение-не-дефект: конфиги с `monthly_tail_extrapolate`/`period_sum` легально держат ОДНУ прогнозную точку на якоре текущего незакрытого bucket'а (nowcast). Тот же класс бага был у сегментов weekly-CPI: primary-прогон пишет sibling-ряды в обход их `_handle_forecasts` — теперь `_post_upsert` сам ретрейнит сегменты с `forecast_steps>0`.

**Диагностика**: прогноз, у которого `min(forecast date) <= max(fact date)` у ряда без anchor-конфига = stale. Ремонт — ретрейн таких рядов (`retrain_indicator_forecast`), данные трогать не нужно.

### auto-loan-rate `element_id` (ЦБ DataService)

Декабрь 2025: ЦБ переразложил dataset 28 (auto-loan-rate). Исторические `element_id 2/4/5/6/7/9/10/11` больше не публикуются, остался только агрегированный `element_id=110` («По всем срокам»). Парсер с `element_id=11` тихо возвращал 0 точек 5 месяцев. Текущий `seed_data.py` хранит `"element_id": 110`. Если ЦБ снова переразложит другой dataset — симптом тот же: ETL `success` + `records_added=0` несколько недель подряд.

### CBR DataService date semantics + 1-month lag за XLSX (M0/M1/M2/deposits)

ЦБ DataService API (`/dataservice/data?publicationId=5&datasetId=*`) для денежных агрегатов имеет **две независимые ловушки**:

1. **Date offset**: ЦБ записывает «остаток на 1-е число» (т.е. dt=`2026-04-01` = состояние **конца марта**). Без `date_offset_months: -1` в конфиге индикатора последняя точка отображается на месяц вперёд («март как апрель»). Правка 2026-05-25 (Никита: «данные за март выдаются как данные за апрель»).
2. **Lag за XLSX**: DataService отстаёт на 2–4 недели от файла `https://www.cbr.ru/vfs/statistics/credit_statistics/monetary_agg.xlsx`. На 25 мая 2026 DataService отдавал последнюю точку 2026-04-01 (=март), а XLSX уже содержал 2026-05-01 (=апрель, M2=131989.8). Trading Economics берёт из XLSX → у нас был «отстающий» индикатор на 1 публикацию. Правка 2026-05-25 (Никита: «теперь стало за март, но апреля все ещё нет, а на trading economics уже есть»).

**Решение**: для `m0`/`m1`/`m2`/`deposits-individual`/`deposits-business` переключены на парсер `cbr_monetary_agg_xlsx` (`backend/app/services/cbr_monetary_agg_parser.py`) — читает XLSX напрямую, мапит rows (M0=row2, M1=row9, M2=row14, deposits-individual=row6+13+18, deposits-business=row5+12+17), применяет `date_offset_months: -1`. Один XLSX покрывает 5 индикаторов одной HTTP-выгрузкой.

**Что осталось на DataService**: `consumer-credit`/`business-credit` (publicationId=20/22) — другие публикации, не в `monetary_agg.xlsx`. Если у них всплывёт аналогичный лаг — нужен XLSX или альтернативная страница ЦБ.

**Регрессионный признак**: симптом «у trading economics уже опубликовано, у нас нет» для денежных индикаторов = вероятно ЦБ обновил `monetary_agg.xlsx`, а DataService ещё нет. Проверка: `curl -sI https://www.cbr.ru/vfs/statistics/credit_statistics/monetary_agg.xlsx | grep last-modified`.

### inflation-weekly: ETL_TIMEOUT_SECONDS vs полный crawl Rosstat-архива

`scheduler.run_etl_for_indicator` использует жёсткий per-indicator timeout = `ETL_TIMEOUT_SECONDS = 300` (`backend/app/tasks/scheduler.py`). Парсер `rosstat_weekly_cpi` исторически делал «толстый» прогон каждый день: crawl до 70 страниц `central-news`, `search` × 12 месяцев × все годы [2023..today.year], full GET каждого найденного bulletin (~150 на момент 2026-05), плюс XLSX (~110 продов + `ipc_spr_MM-YYYY.xlsx`). По мере накопления bulletin'ов общий wall-time приближался к лимиту: 24 мая 2026 ещё успел, 25-27 мая — `status=timeout` 4 дня подряд, точка 2026-05-25 (bulletin 77 от 27-05) не подхватилась. Никита: «недельная инфляция не обновилась, вчера вышла вечером, а у нас старые данные» (2026-05-28).

**Решение** (`backend/app/services/rosstat_weekly_inflation_parser.py`):

1. **Steady-state guard**: `_fetch_and_parse` выбирает `IndicatorData.date` для своего indicator → `existing_dates: set[date]`. Если есть хотя бы одна точка за прошлый год — backfill точно сделан, парсер качает **только `today.year`** (1 год вместо 4-х).
2. **Skip bulletin GETs**: для каждого URL вытаскиваем pub_date через regex `_BULLETIN_PUB_DATE_RE`. Если `pub_date < max(existing_dates) - 14d`, week-end такого bulletin'а заведомо в БД — `continue` без GET'a.
3. **XLSX-fallback только при cold-start**: в steady-state XLSX-приближение покрывает только историю до `weekly_cutoff_date`, которая уже в БД. Качать `nedel_Ipc.xlsx` + `ipc_spr` смысла нет.

Эффект: cold-start ≈ 5+ минут (мог не уложиться в 300с), steady-state — **~28 секунд**.

**Регрессионный признак**: `fetch_log.status='timeout'` несколько дней подряд для `inflation-weekly` при том, что bulletin на `rosstat.gov.ru/central-news?page=1` уже есть. Проверка: `curl -sk https://rosstat.gov.ru/central-news?page=1 | grep -oE 'storage/mediabank/\d+_\d{2}-\d{2}-\d{4}\.html' | head -5` — должен быть bulletin за позавчера-вчера.

**Что делать если опять отвалится**: запустить ETL вручную: `docker compose exec backend python -c "import asyncio; from app.tasks.scheduler import run_etl_for_indicator; asyncio.run(run_etl_for_indicator('inflation-weekly'))"`. Если внутри парсера за 10+ минут не приходит свежий bulletin — значит изменился layout `rosstat.gov.ru/central-news` или `/search`, нужна правка discovery (см. `_find_bulletin_urls_central_news` / `_find_bulletin_urls`).

**Subsequent (2026-06-07)**: на проде daily ETL 1–7 июня давал `timeout` ровно на 300с — парсер до steady-state деплоя укладывался в 295–328с. Доработки: (1) сегменты food/nonfood/services фильтруются по своим `existing_dates`, не upsert всей истории XLSX; (2) steady-state central-news max 12 страниц, search — 2 месяца; (3) XLSX парсится только за текущий (±январь) год; (4) `ETL_TIMEOUT_BY_PARSER['rosstat_weekly_cpi']=600` в `scheduler.py`.

### Rate limit policy

`RateLimitMiddleware` в `backend/app/main.py`: 120 req/min на обычные `/api/...` пути, **600 req/min** на `/api/v1/embed/*`, окно 60s, ключ — `X-Forwarded-For` (Caddy/Nginx добавляют). При превышении — `429 Retry-After: 60`. Если Redis недоступен — middleware пропускает запросы (graceful degradation).

### CSP whitelist для Yandex.Metrika

`Caddyfile` явно перечисляет десятки доменов `mc.yandex.{ru,by,...}`, `mc.webvisor.com`, `*.ingest.sentry.io` в `script-src` / `connect-src` / `child-src`. Любой новый Yandex-домен (например, `mc.yandex.kz` для Казахстана) — в whitelist через PR в Caddyfile, без него браузеры блокируют скрипт счётчика.

### Yandex.RSY (РСЯ floor-ad) — отдельный CSP-набор доменов

Контекстная реклама РСЯ — **независимый от Метрики** домен-граф (официальный CSP partner docs + наш Caddyfile):
- `script-src https://yandex.ru https://an.yandex.ru https://yastatic.net https://*.yandex.ru https://*.adfox.ru` — `context.js` / AdvManager.
- `img-src` + `media-src` для `yandex.ru` / `*.yandex.ru` / `*.yandex.net` / `*.adfox.ru` / `yastatic.net` / `blob:` / `data:` — картинки и **видео** Floor Ad (touch).
- `connect-src` + `blob:` для телеметрии показов/кликов и adfox.
- `frame-src` + `child-src`: `yandex.ru` / `an.yandex.ru` / `*.yandex.ru` / `*.yandex.net` / `yandexadexchange.net` / `*.yandexadexchange.net` / `*.adfox.ru` — рекламный iframe.
- `style-src https://yastatic.net`, `font-src https://yastatic.net data:` — стили блока.

Точка инициализации:
1. **Loader** (`context.js`) грузится из consent-bootstrap `frontend/public/consent.js::loadAds()`. С 2026-06-16 модель — **подразумеваемое согласие** (152-ФЗ, ст. 9 ч. 1: согласие действием): Метрика и реклама грузятся **всем по умолчанию** при первом заходе, если в `localStorage['fe:consent:v1']` нет явного opt-out текущей версии. Баннер `CookieConsent.jsx` стал информационным («Продолжая пользоваться сайтом, вы соглашаетесь…»), отзыв/настройка — кнопка «Настройки cookie» в подвале; Политика и Соглашение переписаны под это (фикс падения статистики Метрики и дохода РСЯ после прежнего opt-in). И SPA shell (`index.html`), и SSR (`seo_renderer.py::_consent_bootstrap()`) подключают один и тот же `/consent.js` (nginx отдаёт с no-cache). Loader один на документ, независимо от количества блоков.
2. **Рендер блоков** — фронт-компонент `frontend/src/components/YandexRSY.jsx`, массив `RSY_BLOCKS`. Рендерится **только** блок текущей платформы через `AdvManager.getPlatform()`. Монтируется в `App.jsx::AppRoutes`. Embed-routes (`/embed/*`) **не** включают РСЯ.
3. **Guard от двойного рендера** — `window.__rsyFloorAdRendered = true` на первом mount. SPA-навигация не вызывает повторный `render()`.
4. **Empty-state** — если SDK оставил серый chrome без креатива (`onError` / пустой `.needsclick` ~2 с), вызываем `destroy` + force-remove шелла; goal `rsy_floor_render` — только при непустом fill.

Активные блоки (2026-06-23):
- `R-A-19489903-2` тип `floorAd` платформа `touch` (мобильные).
- `R-A-19489903-1` тип `floorAd` платформа `desktop` (десктоп).

Trap-симптомы при ломанной CSP:
- Консоль: `Refused to load the script 'https://yandex.ru/ads/system/context.js' ...` → не хватает `yandex.ru` в `script-src`.
- Объявление загружается, но iframe пустой → `frame-src` / `child-src` режут `*.yandex.net` / `yandexadexchange.net`.
- Креативы битые → `img-src` режет `avatars.mds.yandex.net`.
- **Пустой серый Floor Ad «РЕКЛАМА»+X на iPhone без креатива** → нет `media-src` (fallback на `default-src 'self'` режет video Floor Ad). Фикс 2026-07-14.

Goal в Метрике: `rsy_floor_render` — успешный непустой render.

Маркировку «Реклама» (+ домен/erid рекламодателя) несёт сам креатив РСЯ — отдельный оверлей-ярлык мы не рисуем (убран 2026-06-24: floorAd переменной высоты, фиксированный ярлык попадал в середину объявления).

### Scheduler dual jobs + analytics-scheduler флаг

В `backend/app/main.py` lifespan регистрируются **два обязательных** APScheduler job'а: `daily_etl` (06:00 МСК) и `calendar_refresh` (1-го числа 03:00 МСК). Дополнительно — два опциональных под `RUSTATS_ANALYTICS_SCHEDULER_ENABLED=true`: `analytics_hourly` (:15) и `analytics_daily` (07:20). С 2026-05-22 добавлен `ticker_live_pull` (interval 5s, `coalesce=True`, `max_instances=1`) — fetch MOEX/Binance/CBR-fallback в Redis для LiveTicker. Если scheduler-флаг выключен — работает только `daily_etl` + `calendar_refresh` + `ticker_live_pull`, analytics cron-ы не регистрируются.

### Live ticker: MOEX-приоритет с CBR-fallback для FX

Источники (`backend/app/services/ticker_sources/`):
- **MOEX ISS** — USD/RUB (`USD000UTSTOM`), CNY/RUB (`CNYRUB_TOM`), Brent (ближайший фьючерс `BR-X.Y` на FORTS, динамически определяется по `LASTTRADEDATE`). ISS возвращает 4 строки marketdata по бордам — реальные сделки на **CETS**, остальные пустые.
- **Binance public** — BTC/USDT (`/api/v3/ticker/24hr`).
- **ЦБ XML_daily fallback** (звонок 2026-05-22) — для FX когда MOEX отдал `LAST=None` на всех бордах. EUR/RUB на MOEX после санкций ЕС март-2024 **фактически мёртв** — у `EUR_RUB__TOM` LAST всегда null. Fallback тянет `https://www.cbr.ru/scripts/XML_daily.asp` (сегодня + вчера для % change) и подмешивает с пометкой `market_open=False, source="ЦБ РФ"`.

Frontend (`frontend/src/components/LiveTicker.jsx`): `useQuery` polling 4с, sticky-bar над Navbar (`fixed top-0 z-[110]`). Типографика **единая** для всех пяти snapshot'ов — `text-text-primary font-semibold` независимо от `market_open` и `source` (различие источника живёт в `title`-тултипе). Цена показывается всегда если `price > 0`, чтобы CBR-fallback не визуально ломал ряд.

Эндпоинт `/api/v1/ticker/live` (`backend/app/api/ticker.py`) читает Redis-снапшоты с TTL 30s. APScheduler job `ticker_pull_job` пишет их каждые 5s — клиент видит лаг ≤ 9s в худшем случае.

### `is_listed` vs VariantGroupPicker

Скрытие индикатора через `is_listed=False` — это **только** про карточку в `/category/{slug}`. Сам индикатор по-прежнему доступен по `/indicator/{code}`, отдаётся API, индексируется поисковиками, попадает в sitemap. Если нужно полностью убрать индикатор — это другой механизм (`is_active=False` + ручная чистка sitemap-генератора).

### Frequency switcher: пары индикаторов разной частоты

T3 (2026-05-12): для индикаторов внешней торговли публикуем одновременно квартальные (history с 1994) и месячные (history с 1997 для goods, с 2018 для services) ряды. Чтобы UI/SEO не плодили дубли — единая модель:

- **Primary** (родитель) = quarterly индикатор, `is_listed=True`, появляется в категориях и sitemap. В `model_config_json` ставится `alternate_frequencies = {"monthly": "<code>-monthly"}`.
- **Secondary** (counterpart) = monthly индикатор `<code>-monthly`, `is_listed=False`, `forecast_steps=0`, скрыт из категорийного листинга через `INDICATOR_HIDDEN_FROM_LISTING`. В `model_config_json` ставится `primary_indicator_code = "<parent_code>"`.

Backend контракт:
- `IndicatorRead` отдаёт оба поля (`alternate_frequencies`, `primary_indicator_code`). См. `backend/app/schemas.py`.
- `seo_renderer.render_indicator_html` рендерит `<link rel="alternate" hreflang="ru-RU">` на counterpart URL — поисковики видят семантическую пару `/indicator/exports` ↔ `/indicator/exports-monthly`.

Frontend контракт:
- Чистая логика — `frontend/src/lib/frequencySwitcher.js::buildFrequencyItems`. На неё опирается `FrequencySwitcher.jsx`, который рисует tabs «Квартальные / Месячные» над графиком (рядом с `VariantGroupPicker`/`CpiViewModePicker`).
- Переключение URL-based: каждая частота — отдельная карточка с собственным SSR canonical (SEO-благоприятно). `IndicatorChart`, telemetry, datatable читают `indicator.frequency` → автоматически адаптируются под помесячный/поквартальный formatter без отдельной логики.
- Yandex.Metrika goal `frequency_switch` (см. `track.js::events.FREQUENCY_SWITCH`) — каждый клик switcher логируется с `from/to/fromFrequency/toFrequency/indicatorCategory`.

Trap для будущих расширений: если добавляешь третью частоту в пару (например `inflation-weekly` к существующим `cpi`/`cpi-monthly`) — поле `alternate_frequencies` это map `{[freqKey]: code}`, поддерживает любое количество ключей. UI отрисует столько tabs, сколько entries (тест `frequencySwitcher.test.js::handles 3-way switcher` — фиксирует контракт).

### CPI level «Индекс» режим (frontend)

Фронт строит cumulative index с базы `2000-01 = 100` через `frontend/src/lib/useIndicatorViewModeData.js::buildCumulativeIndex`. История 1991–1999 обрезается: январь 1992 = 345% месячный → цепное произведение через 9 лет даёт сотни тысяч и шкала становится нечитаемой. Это **не** ошибка, это осознанный cutoff.

### `/api/docs` (Swagger) на проде

`main.py` регистрирует Swagger только если `settings.debug=True`. На проде `RUSTATS_DEBUG=false` (см. `docker-compose.yml`) — Swagger недоступен. Локально для разработки: `RUSTATS_DEBUG=true` в `.env` → доступно `/api/docs`, `/api/redoc`, `/api/openapi.json`.

### Forecast retrain после деплоя (новые derived)

Когда деплой добавляет **новые derived-индикаторы** (через правки `seed_data.py` + `DERIVED_SPECS`), `entrypoint.sh` идемпотентно отрабатывает seed (создаёт/обновляет строки `indicator`), но **forecast retrain не запускается автоматически**. Daily ETL-job переобучает прогнозы только тех индикаторов, у которых на этом тике добавились новые точки в `data_points` — для свежесозданного derived это произойдёт только после следующего ревизии источника.

Симптом: `/api/v1/indicators/<new-derived-code>/forecast` возвращает `null` несколько часов или дней. Так было 2026-05-07 после деплоя GDP nominal/real split — три из восьми GDP-индикаторов отдавали `null` до ручного `--forecast-only` retrain.

Mitigation: после любого деплоя, добавляющего derived, выполнить ручной retrain в правильном порядке (источники → derived):

```bash
docker compose exec backend python -c \
  "import asyncio; from app.services.forecast_pipeline import retrain_indicator_forecast; \
   asyncio.run(retrain_indicator_forecast('<source_code>'))"
```

Каскадный retrain `derived_from_source` стратегии подхватит зависимые индикаторы. После — `redis-cli -n 0 FLUSHDB` для сброса `fe:*:forecast` ключей (только DB 0: DB 1 хранит сессии пользователей — с 2026-07-02 они изолированы от кэша, FLUSHDB кэша больше никого не разлогинивает).

### Inflation-weekly: семантика и источник

`inflation-weekly` ряд = **недельный прирост ИПЦ к предыдущей неделе** (`100.XX` означает «×1.00XX»), **не** накопленная с начала месяца. Парсер `rosstat_weekly_cpi` ходит за HTML-бюллетенями Росстата только за `today.year`; для 2022–2025 — XLSX-fallback (~110 продов × веса корзины). HTML перезаписывает XLSX при коллизии. В `indicator_data` нет колонки `data_source` — различить «из бюллетеня» vs «из приближения» можно только косвенно через `fetch_log`.

Январский трёхнедельный «выпад» (одна точка с 23 декабря по 12 января ~100.45/101.26) — штатный новогодний бюллетень Росстата, а не баг.

### SDDS English vs Rosstat русский

**Trap**: SDDS-XLSX на `eng.rosstat.gov.ru` (`SDDS_*.xlsx`) — это IMF-зеркало в формате «2010 = 100 chained cumulative index», публикуется с лагом ~год (комментарий в `rosstat_sdds_fetcher.py:6-9`). Парсеры `rosstat_sdds_ppi`, `rosstat_sdds_housing`, `rosstat_sdds_gdp`, `rosstat_sdds_labor`, `rosstat_sdds_ipi`, `rosstat_population` (часть) тянут оттуда. Но **первичная публикация Росстата** — на `rosstat.gov.ru/statistics/<section>/` в формате MoM/QoQ % (100 = предыдущий период) и с историей с 1998+ (для PPI), 1991+ (для CPI), 1995+ (для ВВП).

**Симптомы расхождения с rosstat**:
1. **Format mismatch**: наша DB хранит cumulative index (PPI = 311.40), руководитель открывает rosstat и видит MoM (PPI = 100.6%) — разные числа, кажется баг.
2. **Короткая история**: SDDS даёт PPI с 2011, Housing с 2016, ВВП с 2011 — потому что 2010=100 base. Русский Росстат — глубже.
3. **Stale latest**: SDDS лагает на год. Текущий месяц/квартал в SDDS может отсутствовать или быть приближённым.

**Audit категории «Цены и инфляция» (2026-05-10)** (см. также chat-уровень): CPI 4/4 индикаторов 100% совпадают с rosstat (парсер `rosstat_cpi_xlsx` → `ipc_mes_*.xlsx` правильный). PPI и Housing (3 индикатора) — все из SDDS, требуют миграции на русский Росстат.

**Политика**: для всех новых индикаторов и при правке существующих SDDS-парсеров — переключение на русский Росстат. SDDS используется **только** как fallback, если русский эквивалент недоступен (на момент 2026-05-10 не известно ни одного такого случая в категории Цены). См. [ADR-0004](docs/adr/0004-rosstat-russian-canonical-sdds-deprecated.md) — содержит migration pattern и pilot evidence для `gdp-nominal`.

**Migration trap для ETL/forecast**: при замене source формата (2010=100 → MoM%) одного и того же `code` все исторические точки переписываются через `bulk_upsert WHERE value <> excluded.value` (ADR-0002). Frontend value formatter / chart unit и forecast model обучены на старом формате — оба требуют обновления одновременно с парсером (см. trap «Forecast retrain после деплоя» — здесь применяется тот же mitigation). Для unit-preserving миграций (например, `gdp-nominal` млрд руб → млрд руб) frontend трогать не нужно, retrain прогноза идёт каскадно автоматически из `run_etl_for_indicator`.

**Pilot подтверждение pattern (2026-05-10)**: `gdp-nominal` мигрирован end-to-end на локальном docker stack. Переключение `gdp_source: "official_quarterly", gdp_sheet: "2"` в `seed_data.py` → 60/60 точек переписаны (Q4 2025: 60516.7 → **62354.1** = rosstat publication ✓), derived gdp-yoy/qoq/annual пересчитаны через `rebuild-all-derived.py` (127 точечных изменений), forecast cascade retrain автоматически. Никаких изменений в коде парсера не потребовалось — `parse_rosstat_gdp_quarter_grid_xlsx` уже умеет произвольный sheet через config.

**Категория «ВВП» полностью мигрирована (2026-05-10)**: pilot (`gdp-nominal`) + rollout (`gdp-consumption`, `gdp-government`, `gdp-investment`). Для use-компонентов потребовался новый источник `GDP-quarters-of-use-1995-4kv-2025.xls` (legacy .xls binary, OLE2) → расширен `fetch_rosstat_static_xlsx` (теперь принимает оба magic — XLSX `PK\x03\x04` и XLS `\xd0\xcf\x11\xe0`), новая ветка парсера `gdp_source: "official_use"` (xlrd, multi-row layout), 4 unit-теста через synthetic .xls fixture (`xlwt==1.3.0` в requirements). Rollout pipeline test: `0 new, 0 updated` для всех 3 индикаторов — best-case migration, SDDS уже подтянул rosstat, миграция проактивная (защита от будущих лагов + canonical source policy без disruption). SDDS-ветка `fetch_sdds_xlsx("gdp")` больше не используется ни одним active индикатором.

**Категории «Демография», «Промышленность», «Труд», «Цены» полностью мигрированы (2026-05-10)**: 11 индикаторов переведены на canonical русские источники (commits cf08878 / 13a0251 / 5317421 / 0dc61b8 + housing pending). Pattern «path P (compat)» закрепился: для индикаторов где canonical Rosstat публикует только MoM/QoQ% (без cumulative index), парсер читает последнюю DB-точку и chains новый relative change → один новый datapoint per ETL run, исторический ряд от прошлой SDDS-стадии остаётся, gradual migration, frontend/forecast model не требуют изменений. Применён в `rosstat_ipi_parser` (chain monthly, нормализация 2023=100), `rosstat_ppi_parser` (chain monthly из PDF), `rosstat_housing_parser` (chain quarterly из PDF, primary+secondary). Для labor (4 индикатора) — sociomonomic PDF report повышен из supplementary до primary source (нет comprehensive monthly XLSX по labor на rosstat сайте). Подробности по каждой категории — в [ADR-0004 «Subsequent additions»](docs/adr/0004-rosstat-russian-canonical-sdds-deprecated.md).

**GDP history extension до 1995 (2026-05-10)**: 5/5 GDP source-индикаторов продлены с 60 до **124 точек** (1995-Q1 → 2025-Q4) через **ratio-splice на overlap-году 2011** — pure-функция `splice_at_overlap(history, modern, overlap_year)` в `rosstat_gdp_parser.py`. Калибрует `ratio = mean(modern_2011) / mean(history_2011)`, scale'ит historical-точки (year < 2011) к base modern-методологии (для nominal: ОКВЭД2007 → ОКВЭД2, ratio ~1.074; для real: в ценах 2008 → в ценах 2021, ratio ~2.81). Standard economic-series splice техника (ОЭСР/МВФ practice). Конфиг per индикатор — `gdp_history_sheet` + `gdp_overlap_year` в `model_config_json`. Закрыта прямая жалоба руководителя 08.05.2026 «у Росстата с 1995, у нас почему-то с 2011». Trap, выловленная на data: Rosstat Excel хранит часть значений как СТРОКИ с Russian decimal + footnote suffix («1662,82)» = 1662,8 + footnote 2) → добавлен `_parse_ru_number` хелпер.

### Source-depth trap (новый индикатор)

Парсер фетчит N лет, БД хранит M < N. Симптом — `/indicator/<code>` начинается с 2020 (или 2015), хотя источник публикует с 1991/1995. Это видно только пользователю, который сравнивает с публикацией Росстата/ЦБ; внутренний мониторинг молчит.

**Примеры обнаруженных пробелов** (звонок 2026-05-22):
- `wages-nominal` начинался с 2015 → Росстат публикует с 1991. Закрыто через `wages_historical.py` (immutable seed годовых точек 1991-2014).
- `key-rate` начинался с 2013-09 → ставка рефинансирования ЦБ с 1992. Закрыто через splice на overlap-точке 2013-09-13 (`refinancing_rate_historical.py`).
- `gdp-*` начиналось с 2011 → Росстат публикует с 1995 (ОКВЭД2007). Закрыто через ratio-splice на overlap-year 2011.
- `housing-price-{primary,secondary}` — backfill 1998-2014 через `housing_historical.py`.
- `inflation-weekly` начинается с 2022-01-10 → Росстат публикует с 2003, но **архив до 2022 утерян** (gks.ru не работает, Wayback не имеет нужных URL); это технический предел, не наша недоработка.

**Правило:** при добавлении любого нового парсера / индикатора — **обязательная проверка по чеклисту в `AGENTS.md::Шаг 4`** (`Source-depth invariant`). Если источник даёт глубже чем в seed — заводим `<name>_historical.py` immutable seed.

### Browser-cache trap при rebuild frontend

После `docker compose build frontend && up -d frontend` пользователь в обычном окне Chrome может видеть **unstyled HTML** (чёрный фон, синие подчёркнутые ссылки). Причина — браузер держит старый HTML в **disk cache** и пытается загрузить ассеты со старыми hashes, которые в новом контейнере отсутствуют → 404 → React shell не загрузился → unstyled.

Это **не** asset-hash trap (см. выше) — backend и frontend синхронизированы, ассеты на свежих hashes отдаются 200. Проблема в кеше **самого браузера** пользователя.

**Правило:** после rebuild frontend для демонстрации — открывать в **incognito** или делать **Cmd+Shift+R** (hard reload, минует disk cache). В DevTools → Network → Disable cache на время тестирования.

### New indicator initial ETL trap (закрыт автоматикой 2026-05-22)

После `seed_data.upsert_indicators()` создаёт новый indicator с `parser_type != "derived"` и `is_active=true`, **первый ETL** по нему ранее не запускался автоматически. Daily ETL job ходит в 06:00 МСК — между deploy и 06:00 новый индикатор стоял пустой, frontend показывал «нет данных».

**Случай 2026-05-22:** `deposit-rate-medium` и `deposit-rate-long` (звонок 21-05, правка C3) — оба добавлены в seed_data 21-05, daily-job не успел отработать, при ревизии 22-05 у обоих было 0 точек. Триггернул вручную → 147 точек 2014-2026.

**Закрытие:** в `app/main.py::lifespan` добавлен background task `_catch_up_empty_indicators()` — при startup ищет все `is_active=True AND parser_type != "derived"` индикаторы с `COUNT(indicator_data) = 0` и триггерит ETL для них. Запускается как `asyncio.create_task(...)`, не блокирует uvicorn ready. Применяется один раз при каждом старте контейнера. Derived подхватятся cascade'ом после source.

**Правило:** ничего не делать вручную. Если контейнер был запущен, а у нового source-индикатора всё ещё 0 точек — смотреть логи backend на `Startup catch-up: <code> failed: ...` (источник недоступен, конфиг битый и т.п.).

### Annual-in-monthly mixing trap (backfill в чужую частоту)

Парсер добавляет в indicator с `frequency=monthly` годовые точки (1 января каждого года). Frontend chart label остаётся «помесячно» (из `frequency`), а на графике рывок: 24 точки за 24 года выглядят как 24 month-точки с гэпами. Пользователь видит ложную динамику, фигуры месяц-к-месяцу несравнимы с годом.

**Случай 2026-05-22:** `wages-nominal` (frequency=monthly с 2015) → backfill 24 годовых точек 1991-2014. График показывал «ПОМЕСЯЧНО» + рваный ряд. **Фикс:** годовая история вынесена в отдельный `wages-nominal-annual` (`frequency=annual`, `is_listed=false`), доступна как режим «Годовое (с 1991)» через `viewModeFamilies`. Monthly indicator теперь содержит только monthly-точки.

**Доводка 2026-07-01:** `wages-nominal-annual` из manual_historical seed переведён в **derived** через op `annual_mean_with_prefix` (immutable хвост 1991-2014 + annual mean месячного ряда 2015+) — движок продолжает годовой ряд сам при закрытии года, ручной `scripts/backfill-wages-history.py` удалён (см. ADR-0001 «Subsequent additions»). Попутно закрыта дыра `wages-nominal` 2022-12 (декабрь пропущен в разовой заливке monthly-ряда; из-за неё 2022 выпадал из годового среднего): точка 88 468 ₽ добавлена в `MONTHLY_GAP_FILL` (`wages_historical.py`), идемпотентный gap-fill в `seed_data.py` льёт её ДО пересчёта derived. **Внутренние дыры месячного ряда должны быть закрыты gap-fill'ом**, иначе annual mean года с пропуском занижен — общее ограничение любого annual-mean sibling'а.

**Правило:** **никогда** не лить точки чужой частоты в существующий indicator. Если source даёт annual до 1998 и monthly с 2015 — это **два разных indicator'а** с одним visual entry (через view-mode family). Аналогично quarterly история + monthly свежак, weekly прошлое + daily настоящее, и т.п.

**Проверка при backfill:** перед `bulk_upsert` сверить `target.frequency` с фактической частотой добавляемых точек. Если расхождение — заводим sibling indicator + добавляем режим в `viewModeFamilies`. См. чеклист в `AGENTS.md::Шаг 4` (новый пункт «Frequency consistency»).

### Annual-in-quarterly trap (кросс-каденс QoQ/MoM даёт годовой прирост под видом квартального)

Родственник trap'а выше, но на слое derived-приростов, а не backfill. Если ряд-**источник** сам смешивает годовую историю и квартальный современный сегмент (обычная ситуация для индексов цен Росстата: годовые точки до ребейза, квартальные после), то `qoq()`/`mom()`, считающие % «к предыдущей точке любой ценой», между двумя годовыми точками возвращают **годовой** прирост, ошибочно подписанный как квартальный.

**Случай 2026-07 (G2-аудит):** `housing-price-primary/secondary` — годовые точки 1998-2014, квартальные с 2015. `housing-qoq-*` рисовал 46 %, 25 %, 18 %… (годовые скачки) на всём отрезке до 2015, а затем обрыв до ±1 % — визуальный мусор. **Фикс:** чистая op `qoq_adjacent(series, max_gap_days=110)` считает % **только между соседними кварталами** (интервал ≤110 дн ≈ квартал + запас; годовой ~365 дн отбрасывается). Ряд `housing-qoq-*` теперь стартует 2015-03, макс |QoQ| ~8 %.

**Правило:** для QoQ/MoM поверх ряда, чья история может менять частоту, использовать cadence-aware op (`qoq_adjacent`), а не «слепой» `qoq()`. SQL-аудит на смешение: медианный интервал между точками не совпадает с объявленной `frequency`, либо в quarterly/monthly ряду есть annual-размерные гэпы.

### Incomplete-period aggregation trap (неполный текущий год/квартал)

Годовой/квартальный режим строится агрегацией под-периодов: backend `derived_ops._aggregate` (`period_sum`/`period_avg`/`period_last` для семей `viewModeFamilies`), `annual_sum` (ВВП), и client-side `viewModeFamilies.applyAggregateTransform` (daily-индикаторы Phase 5). Если текущий год не завершён, агрегат неполного года рисуется точкой факта: сумма (инвестиции за 1 квартал 2026) обваливается вниз, среднее за полгода занижено, «на конец года» подменяется YTD-значением.

**Случай 2026-06-15** (созвон: «инвестиции за 2026 не показывать — год же не закончился, проверь все индикаторы»): `capital-investment-sum-year` показывал обвал 2026 из одного квартала. Фикс — `_aggregate` отбрасывает bucket, в котором уникальных под-периодов меньше ожидаемого (`_expected_subperiods`: месячный источник → 12, квартальный → 4; quarter → 3). **Полнота считается по уникальным месяцам, а не по числу сырых точек** — иначе у дневного источника ~250 точек в году всегда «проходили» порог 12, и неполный год дневных агрегаций (ключевая ставка, валюты, золото, Brent, резервы) не отсекался. Тот же месяц-based порог продублирован на фронте в `applyAggregateTransform` (year→12, quarter→3 уникальных месяцев).

**Trap внутри trap (idempotent upsert не удаляет):** пересчёт через `_aggregate` отдаёт меньше точек, но `bulk_upsert` — INSERT…ON CONFLICT, он **не** удаляет устаревшую точку 2026. Чистит её `_execute` через `prune_indicator_dates_not_in` (даты, которых нет в свежем ряду). Поэтому после правки агрегации обязателен полный `scripts/rebuild-all-derived.py` (он зовёт `_execute`), а не только проверка значений — иначе обвальная точка остаётся в БД.

**Случай 2026-06-16** (доводка той же правки): `_expected_subperiods` определял частоту источника по «макс. числу месяцев в каком-то году». У weekly-ряда с КОРОТКОЙ историей (`international-reserves`: ~66 точек, старт ~март 2025 из-за бага формата дат UniDbQuery — см. trap ниже, самый полный год = 10 месяцев) это давало `mx=10 → ожидание 4` (как у квартального), и неполный 2026 (6 месяцев ≥ 4) снова проходил фильтр. Фикс — частота определяется по **медианному интервалу между точками** (`≤45 дн → 12/3`, `≤100 дн → 4/None`, иначе None), что устойчиво к длине истории. Следствие: если у источника нет ни одного полного календарного года, годовой агрегат корректно пуст.

**CBR UniDbQuery monthpicker trap (2026-08-10).** Страница `cbr.ru/hd_base/mrrf/mrrf_7d/` использует monthpicker: `UniDbQuery.From`/`To` = `MM.YYYY` (например `05.1998`). Формат `DD.MM.YYYY` (как у KeyRate/RUONIA) сайт молча игнорирует и отдаёт дефолтное окно ~последний год → в БД оставался огрызок с середины 2025 при доступной истории с 29.05.1998. Фикс: `format_unidb_month` + `backfill_from=1998-05-01` + self-heal `[floor, earliest)`. Не путать с daily-фильтрами KeyRate/RUONIA — там по-прежнему `DD.MM.YYYY`.

**Правило:** любую новую годовую/квартальную агрегацию (backend op или client transform) проверять на неполный текущий период; порог полноты — в уникальных под-периодах (месяцах), не в сырых точках; частоту источника определять по ритму (медиана интервалов), не по «макс. месяцев в году».

### View-mode template change orphans (сироты при смене шаблона)

При смене view-mode шаблона индикатора, при которой **исчезают режимы** (T3→T8 убрал «на конец периода» у зарплаты/labor-force/employment; Tidx→Tidxq убрал «М/м» у `housing-affordability`), sibling-коды старых режимов (`*-eop-quarter`, `*-mom`, …) перестают генерироваться конфигом, но **остаются в БД** с прошлого seed. Seed не удаляет строки и сбрасывает `is_listed=True` для всех, пряча обратно только коды из `INDICATOR_HIDDEN_FROM_LISTING`. Сироты в этот набор не попадают → **всплывают карточками в каталоге**.

**Случай 2026-06-06:** перевод зарплаты/labor-force/employment на T8 оставил 6 сирот `*-eop-quarter/-year` → «Рынок труда» показал 10 карточек вместо 4.

**Правило:** после reseed, изменившего шаблоны, удалять коды, которых нет в текущем `seed_data.INDICATORS` (`IndicatorData` + `Forecast` + `Indicator`). Идемпотентно; чистит и каталог, и пересчёт derived. Не полагаться на то, что seed «сам уберёт» — он только upsert.

### View-mode family metadata leak (downstream-протекание родительских полей)

При добавлении нового члена в семью `viewModeFamilies.js` (real sibling с другой частотой или единицей) недостаточно прописать `code` — нужно протянуть **все** поля, от которых зависят downstream-компоненты `IndicatorDetail.jsx`. Иначе родительские метаданные «протекают»: pill и заголовок графика читают `indicator.frequency` родителя, секция «Методология» читает обобщённый CPI-блок из `cpiViewModeContent.jsx`, и пользователь видит чужой смысл.

**Случай 2026-05-22:** `/indicator/wages-nominal?mode=annual` (target = `wages-nominal-annual` с `frequency=annual`):
- Pill показывал «ПОМЕСЯЧНО», заголовок графика — «— помесячно» (frequency leak — `effectiveIndicator` подменял `unit`/`name`, но не `frequency`).
- Секция «Методология» отдавала текст CPI: «Годовая инфляция декабрь к декабрю» (methodology leak — `getViewModeContent()` отдавал блок `ANNUAL` для любого `safeViewMode === 'annual'` без проверки `isPriceCategory`).

**Фикс:**
1. `effectiveIndicator` в `IndicatorDetail.jsx` дополнительно подменяет `frequency` из `familyModeMeta.frequency` (для real siblings) или `DAILY_AGG_FREQUENCY[granularity]` (для daily-aggregation Phase 5).
2. `IndicatorDetailHeader.jsx` принимает отдельный prop `displayFrequency`, чтобы pill отражал actual frequency, при сохранении родительского `name`/`category` для H1/breadcrumbs.
3. `getViewModeContent()` в `cpiViewModeContent.jsx` обёрнут в `if (isPriceCategory)`. Не-CPI индикаторы падают в fallback `{ description: indicator.description, methodology: indicator.methodology }`.

**Правило для новых семей в `viewModeFamilies.js`:** у каждого **не-`level`** mode (real sibling) задаём явный `frequency` ИЛИ `transform`. Виртуальные transforms (`mom`) сохраняют родительскую частоту — `frequency` опускаем. Инвариант покрыт тестом `viewModeFamilies.test.js::каждый не-level mode имеет frequency или transform`.

**Правило для новых mode-specific блоков в `cpiViewModeContent.jsx`:** если блок применим только к CPI-семейству (Index, Annual, Weekly, Quarterly, CPI-monthly, Inflation), его условие должно быть **внутри** `if (isPriceCategory)`. Для не-CPI индикаторов с теми же режимами (`wages-nominal?mode=annual`, `unemployment?mode=quarterly`) функция должна падать в fallback на `indicator.{description, methodology}` из БД.

### Calendar source coverage

Legacy `WeeklySpec` / `typical_day` builders в `calendar_seed.py` оставлены только для debug/tests старой плотности календаря. Public ingest идёт через `calendar_sources.official_calendar`: CBR official daily rules (`indcalendar`) для FX/RUONIA/gold; CBR official ICS (`indcalendar` / `vCalendar.ics`) для резервов, M0/M1/M2, кредитов/депозитов, ставок, ипотеки, внешнего сектора, долга; CBR official monetary-policy schedule (`cbr.ru/dkp/cal_mp/`) для заседаний и резюме по ключевой ставке; Rosstat/Minfin rule-events только по опубликованным правилам и versioned working calendar. После добора 2026-05-10 local source-bound coverage: 46/76 source codes, 1208 public events, `bad_public_rows=0`. Если источника/правила нет — событие не показывается, пока не будет донабрано через official parser/rule.

### Telegram-уведомления: env-precedence + флаг (двойной .env trap)

Уведомления о новых пользователях/обратной связи (`alerting.notify_new_user` / `notify_feedback`, call-sites в `api/auth.py::register` и `api/oauth.py::oauth_callback`, оба `await`-ятся до ответа) уходят **только** при `settings.telegram_realtime_alerts_enabled=true` И наличии `telegram_bot_token`+`telegram_chat_id`. Сам код-путь рабочий; молчание почти всегда — **конфиг**.

**Trap 1 — два `.env` и precedence.** Есть корневой `./.env` (docker-compose читает его для `${VAR}`-интерполяции в блоке `environment:`) и `backend/.env` (pydantic `env_file` ВНУТРИ контейнера). Для переменной, перечисленной в `environment:` с **непустым** дефолтом (`RUSTATS_TELEGRAM_REALTIME_ALERTS_ENABLED: ${...:-true}`), compose всегда инжектит непустое значение → оно **перекрывает** `backend/.env` (OS env > env_file в pydantic). Для переменной с **пустым** дефолтом (`${...:-}`) инжектится `""` → pydantic игнорирует → выигрывает `backend/.env`. Вывод: **realtime/digest-флаги меняй в корневом `./.env`**, не в `backend/.env` (там правка молча не применится). Проверка факта: `docker compose exec backend printenv RUSTATS_TELEGRAM_REALTIME_ALERTS_ENABLED`.

**Trap 2 — локалка должна зеркалить прод.** Если глушишь алерты на локалке (`realtime=false`) ради тестового шума — это рвёт паритет «локалка = прод» и выглядит как «уведомления сломаны»: на `localhost` регистрация молчит by design. Правильный паритет — `realtime=true` и на локалке, и на проде (оба `./.env`). Тестовый шум гасить не флагом, а дисциплиной (не гонять лишние E2E-регистрации) либо опциональным suppression по test-email-паттерну. Прод-факт на момент 2026-06-20: `realtime=true`, `digest=true` (дайджест 09:00 МСК), `chat_id=433221767`, токен задан, `debug=false`.

**Trap 3 — что НЕ триггерит пинг.** Уведомление шлётся только на **создание нового** пользователя (`created=True`); повторный вход существующим аккаунтом — тишина. И `sendMessage` доставит, только если получатель раньше нажал Start у бота (иначе HTTP 403 «can't initiate conversation»). Быстрый E2E канала: `curl -s "https://api.telegram.org/bot<token>/sendMessage" -d chat_id=<id> -d text=ping` → ждём `{"ok":true}`. Узнать реальный `chat_id` получателя: `getUpdates` после его `/start`.

**Trap 4 — прод не достаёт Telegram по IPv6 (главная причина «с сайта не шлётся»).** На прод-сервере `api.telegram.org` резолвится **только в IPv6**, а IPv6-маршрут до Telegram у хостера мёртвый → `httpx.ConnectTimeout` (15s), который глушится в `_notify_*_safe`/`send_telegram` (warning в логах). Симптом: тест из dev-окружения приходит, а **с прода и дайджест — нет**. Диагностика: `docker compose exec backend python -c "import socket; socket.create_connection(('149.154.167.220',443),5)"` — рабочий IPv4 Telegram DC. Фикс — `extra_hosts: api.telegram.org:${TELEGRAM_API_IP:-149.154.167.220}` у backend в `docker-compose.yml` (пишет `/etc/hosts` контейнера на уровне C-резолвера; Python-monkeypatch `socket.getaddrinfo` НЕ помогает — httpx/anyio резолвит мимо него). Проверка из контейнера: `docker compose exec backend curl --resolve api.telegram.org:443:149.154.167.220 -s ".../getMe"` → `{"ok":true}`.

### View-mode `shadowed_legacy` ≠ мёртвый код (расследование 2026-06-24)

Карта (`docs/indicator-index.json`) ставит `shadowed_legacy` / `in_both_viewmode_systems` для кодов, чья **standalone-ветка рендера** в `IndicatorDetail.jsx` перекрыта generic-движком (early-return `getViewModeFamily` ПЕРВЫМ). Флаг ловит только shadowing рендера и **НЕ доказывает**, что легаси-файл можно удалить. Подтверждено на cbr-term / unemployment / trade двумя независимыми причинами:

- **Живые canonical-редиректы старых URL.** Старые derived-коды `trade-balance-yoy-abs`, `current-account-yoy-abs`, `unemployment-quarterly`, `unemployment-annual` **отсутствуют** в `viewModelFamilies.generated.json` → их редирект на родительскую карточку держится ТОЛЬКО на легаси `viewModeCanonicalTarget` / `unemploymentCanonicalTarget` (каскад в `IndicatorDetail.jsx`). Эти URL в sitemap и **индексируются** — удаление редиректа = тихий 404 со старых ссылок и просадка SEO, чего `check-all`/тесты НЕ ловят.
- **bespoke content переиспользуется живыми секциями.** `cbrTermSliceRate*` / `unemploymentViewMode*` импортируются в `IndicatorChartSection`, `IndicatorDataTableSection`, `cpiViewModeContent`, `useIndicatorViewModeData`, picker-groups — заголовки графика/таблицы и резолв режимов живут через общие секции, а не только через standalone-ветку.

**Mitigation:** перед удалением любого view-mode-легаси — (1) `grep` по `viewModelFamilies.generated.json`: покрывает ли движок старый URL; (2) проверить импорты экспортов по `frontend/src`. Если редирект живой — сперва вынести его в явную redirect-карту, и только потом чистить рендер. `docs/dead-code-report.md` переписан под это (список на расследование, НЕ delete-list). Сама консолидация старых `*-yoy-abs` URL в движок — backlog A3 (требует продуктового решения по 301-карте).

### nginx `map` с capture-группой перетирает `$1` location-регекспов (2026-07-06)

`map $http_user_agent $ssr_limit_key { ~*(yandex|googlebot|…) ""; }` для SSR rate-limit (П-22): nginx вычисляет map лениво — в момент обращения к переменной внутри location. Если regex map'а содержит **capture-группу**, её совпадение перезаписывает нумерованные `$1/$2` регекспа location → `proxy_pass http://backend:8000/seo/indicator/$1` уходил на `/seo/indicator/Yandex` и боты получали 404 на всех SSR-страницах (симптом виден ТОЛЬКО под бот-UA; человеческий curl-смоук проходит). Фикс двойной: в map — только non-capturing `(?:…)`, а все SSR-локации переведены на **именованные капчеры** `(?<ind_code>…)` — им чужие числовые группы не страшны.

**Правило:** в nginx-конфиге этого проекта числовые `$1/$2` в proxy_pass запрещены, если в запросе участвует любая map-переменная с regex; смоук новых SSR-правил гонять и обычным UA, и `-A "Mozilla/5.0 (compatible; YandexBot/3.0)"`.

---

## Architectural language (from improve-codebase-architecture skill)

- **Module** — anything with an interface and an implementation (function, class, package).
- **Interface** — everything a caller must know: types, invariants, error modes, ordering, config. Not just signature.
- **Implementation** — code inside.
- **Depth** — leverage at the interface: many behaviours behind a small interface.
- **Shallow** — interface complexity ≈ implementation complexity (e.g. wrapper function that just binds two args).
- **Seam** — where an interface lives; place to alter behaviour without editing in place.
- **Adapter** — concrete thing satisfying an interface at a seam.
- **Leverage** — what callers gain from depth.
- **Locality** — what maintainers gain from depth: change concentrated in one place.
- **Deletion test** — imagine deleting the module. If complexity vanishes, it was a pass-through. If complexity reappears across N callers, it was earning its keep.

When suggesting refactors, use this language. Use the **Indicator/DataPoint/Derived/Forecast/Parser/Strategy** vocabulary above for the domain.
