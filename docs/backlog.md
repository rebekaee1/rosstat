# Backlog — текущие правки в работе

**Last updated:** 2026-06-19 (Личный кабинет Phase 2 — ADR-0007 «Subsequent additions»: download-gate, телефоны OAuth, согласие на рассылку, брендовые кнопки + providers-endpoint, Telegram-бот (регистрации + дайджест), хедер-блок авторизации, инлайн-поиск, RegisterNudge, автобэкап identity-таблиц. Phase 2.1: обратная связь авторизованных (форма в кабинете + nudge → Telegram мгновенно), quota-aware кнопки скачивания, спрос-аналитика поиска (`search_query`/`search_select`/`search_abandon` в `FrontendEvent` → секция дайджеста: топ-запросы + «без результатов» = пробелы каталога), гейт глубины истории в гостевой выгрузке (`download_anon_history_years=3`, полный период — за регистрацию; обрезка в `export_table`, подсказка на кнопках), хедер-брейкпоинт `md→lg` + адаптивная подпись «Калькулятор» (фикс переполнения pill). См. История 2026-06-19. Предыдущий — Phase 1 2026-06-19 / 2026-06-16).
**Part of:** [`AGENTS.md`](../AGENTS.md), [`CONTEXT.md`](../CONTEXT.md), [`docs/adr/0006-indicator-card-unification.md`](adr/0006-indicator-card-unification.md), [`docs/adr/0007-identity-user-accounts.md`](adr/0007-identity-user-accounts.md).
**Источник:** звонки с Никитой Александровичем 2026-05-21 (Сочи) и 2026-05-22 («всё доделать»).

> Живой бэклог планируемых работ. Каждая правка имеет ID, описание, затронутые файлы, риски, зависимости и приоритет. Когда правка сделана — переносится в раздел «История» внизу с датой и SHA коммита/деплоя.

---

## Сводка приоритетов (актуальная — 2026-05-22, после-ревизия)

| Приоритет | Активно сейчас |
|-----------|----------------|
| **P0** | — (пусто; все P0 из звонков закрыты) |
| **P1** | ~~Расширение view-mode families на остальные индикаторы~~ — **закрыто 2026-06-06**: весь каталог (74 карточки) имеет режимы, mode-gaps=0 (ADR-0006 §2026-06-06). Осталось: SEO-наполнение (задача 2 — генератор блоков/FAQ есть, проверить покрытие и нестыковки), раздел сравнения (watermark + подписи), календарь (дубли + ссылки на источники), аудит индексации. **ИПЦ/ИЦП/housing-price** — эталоны bespoke, не мигрировать на generic без отдельного решения. |
| **P2** | C4 (research редких показателей — см. список в конце документа). Wages-2022-12 hole (одна точка пропущена в monthly, заметная как gap на годовом графике) — отдельный микрофикс при следующем wages ETL. Автоматизация `wages-nominal-annual` continuation через derived spec `annual_mean` (сейчас one-shot script). **G1 Search keywords ревизия** на всех 109 индикаторах — где-то полный список синонимов, где-то пустые SEO-шаблоны (см. ниже). **G2 Annual-in-monthly SQL-audit** на остальных backfilled индикаторах (wages фикснут; key-rate/gdp-real/housing на глаз согласованы, но явная проверка не сделана). |
| Future (отложено) | F1 крипто (частично закрыто через BTC/USD как полный indicator), F2 регионы, **F3 Telegram-бот** (подписка на indicator, daily push, custom alerts), **F4 Embed-виджеты UI** (дизайн + копи-кнопка кода + CSP), **F5 Календарь публикаций UI** (backend готов 1208 events) — см. раздел Roadmap. |

**Закрытые в звонке 2026-05-22 + после-ревизия:**
- A1+A2+A3 — унификация view-modes через `viewModeFamilies.js`, объединение дублирующих карточек (29 индикаторов в `INDICATOR_HIDDEN_FROM_LISTING`).
- D1 — full directory search через `?include_unlisted=true` + synonyms via `seo_keywords` (commit `cf4a679`).
- D3, D4, D5, D6 — закрыты commit'ами `91c3f9c`, `876b3c7`, `d4f57ae`.
- E1, E2 — закрыты раньше (audit bulk_upsert + budget-deficit smoke).
- B1 — key-rate splice со ставкой рефинансирования (1992-), коммит `75013ab`.
- **B2 — wages-nominal-annual с 1991 + autocontinuation 2015-2025**: коммит `3897cc6` залил исторические 24 точки 1991-2014, после-ревизия 2026-05-22 расширила `scripts/backfill-wages-history.py` авто-агрегацией monthly→annual_mean (10 новых точек 2015-2021, 2023-2025; 2022 пропущен из-за hole в monthly). Итог: 34 точки в `wages-nominal-annual`, ряд тянется до 2025-01.
- **B3 — audit-history-depth**: реализован как `scripts/audit-indicators-history.py` (markdown-таблица «текущая глубина / теоретически доступная / GAP» по всем 109 индикаторам + кандидаты на backfill). Использовался для приоритизации B1 (key-rate), B2 (wages) и C2 (wages-index). Коммит на стадии деплоя.
- C1, C2, C3 — housing-affordability, wages-index, deposit-rate term split.
- D2 — long SEO blocks на 12 индикаторов (на оставшиеся ~80 — по мере роста показов в Метрике).
- Phase 1-5 (новые) — trade + labour + housing + rates rename + daily aggregation.

---

## Кластер A — Time aggregations & view modes

> **A1 и A2 — это одна задача в двух частях:** A1 (движок переключателей, уже есть на CPI) + A2 (таблица «какие кнопки рисуем у каждого индикатора»). Без A2 движок не знает, что показывать. Без A1 таблица — мёртвая. Делаем вместе.

### A1. Унифицировать UX time-aggregation (freq × view) для большинства индикаторов

**Что меняем.** Эталон — текущая страница CPI: переключатель частоты (week/month/quarter/year) × переключатель режима (yoy / mom / cum / abs). Применить эту же пару (`FrequencySwitcher` + `CpiViewModePicker`) ко всем индикаторам, где исторически только один frequency. Конкретные пары — A2.

**Ключевое уточнение Никиты.** Для индикаторов, которые могут уходить в отрицательную зону (`current-account`, `trade-balance`, `budget-deficit`, `population-natural-growth`, `population-migration` и т.п.) — **никаких процентных изменений**. Только абсолютные значения и абсолютная разница год-к-году (в тех же единицах, не в %).

**Затронутые файлы.**
- `backend/seed_data.py` — `model_config_json` каждого индикатора получает `views: [...]` и `aggregations: [...]`.
- `backend/app/services/calculation_engine.py`, `backend/app/services/derived_ops.py` — возможно новые ops: `weekly_mean`, `quarterly_mean_from_daily`, `annual_mean_from_daily`, `mom_pct`, `rolling_12m_pct`, `yoy_absolute_diff` (для отрицательных).
- `backend/app/api/indicators.py` — endpoint должен отдавать список доступных views/aggregations для UI.
- `frontend/src/lib/useIndicatorViewModeData.js` — обобщить с CPI-only на любой индикатор.
- `frontend/src/components/IndicatorChartSection.jsx` — рендер переключателей по конфигу.
- `frontend/src/components/FrequencySwitcher.jsx`, `CpiViewModePicker.jsx` — переиспользуем, переименуем `CpiViewModePicker` → `ViewModePicker` для ясности.

**Риски.**
- Кэш forecast'ов под старые derived-коды (`exports-yoy`, etc.) — после объединения derived теперь живут как режимы внутри родителя. Нужен retrain или каскадная инвалидация (как в ADR-0001).
- ADR-0002: `bulk_upsert` должен продолжать быть идемпотентным для пересчёта режимов.

**Зависимости.** A2, A3.

**Приоритет.** P1 (большая, делаем после P0 фундамента).

---

### A2. Per-indicator config: какие частоты и какие режимы

**Зачем эта задача.** Движок переключателей (A1) — это шасси, A2 — это «какие кнопки рисуем на каждом индикаторе». Без A2 frontend либо рисует все возможные кнопки везде (и большинство нажатий дают невалидные данные), либо вообще ничего не рисует. Это контракт между backend и frontend: «вот этот индикатор поддерживает следующие комбинации».

**Что меняем.** Для каждого из ~109 индикаторов прописать в `model_config_json` поля `views` и `aggregations`. Шаблоны:

```text
DAILY (key-rate, usd-rub, eur-rub, cny-rub, ruonia, gold-price):
  aggregations: [daily, monthly, quarterly, annual]   # mean или close-of-period
  views: [abs, mom_pct, yoy_pct]                       # MoM/YoY только для absolute (ставки могут падать — но не отрицательно)

MONTHLY всегда положительные (wages, ipi, ppi, retail-trade, ставки, кредиты-объёмы):
  aggregations: [monthly, quarterly, annual]
  views: [abs, mom_pct, qoq_pct, yoy_pct, rolling_12m_pct]

QUARTERLY (gdp-*, housing-price-*):
  aggregations: [quarterly, annual]
  views: [abs, qoq_pct, yoy_pct]

NEGATIVE-CAPABLE (trade-balance, current-account, budget-deficit, *-migration, *-natural-growth):
  aggregations: [по своей частоте]
  views: [abs, yoy_abs_diff]   # только абсолютная разница, не %
```

**Затронутые файлы.** `backend/seed_data.py`.

**Риски.** Низкие — это таблица конфигов.

**Зависимости.** A1 (генерик инфраструктура).

**Приоритет.** P1.

---

### A3. Объединение дублирующих карточек + 301-редирект

**Что меняем.** Карточки-дубли убираем как отдельные индикаторы, оставляем как режимы родителя.

| Родитель | Дочерние (объединяем) |
|----------|----------------------|
| `exports` | `exports-monthly`, `exports-yoy`, `exports-qoq` |
| `imports` | `imports-monthly`, `imports-yoy`, `imports-qoq` |
| `trade-balance` | `trade-balance-monthly` |
| `services-exports` | `services-exports-monthly` |
| `services-imports` | `services-imports-monthly` |
| `current-account` | `current-account-yoy` |
| `unemployment` | `unemployment-quarterly`, `unemployment-annual` |
| `wages-nominal` | `wages-yoy` |
| `ipi` | `ipi-yoy` |
| `cpi-services` | `cpi-services-quarterly`, `cpi-services-annual` (audit аналогично для cpi-food, cpi-nonfood, ppi) |
| `credit-rate-corp` (новый зонт) | `credit-rate-corp-short`, `-1to3y`, `-over3y` (объединяются в одну карточку с переключателем срока «До 1 года / 1-3 / Свыше 3») |
| `credit-rate-ind` (новый зонт) | `credit-rate-ind-short`, `-1to3y`, `-over3y` |
| `deposit-rate` | новые `deposit-rate-short`, `-1to3y`, `-over3y` (см. C3) |

**Демография — НЕ объединяем** (Никита явно сказал): `population-total-growth`, `population-natural-growth`, `population-migration`, `births`, `deaths`, `birth-rate`, `death-rate` остаются отдельными.

**SEO-механика 301.** Старые URL вида `/indicator/exports-yoy` 301-редиректят на `/indicator/exports?view=yoy`. Google передаёт ranking при 301. Сделаем:
- `frontend/nginx.conf` — добавить `location ~ ^/indicator/(exports-yoy|exports-qoq|...)/?$` → `return 301 /indicator/<parent>?view=<mode>`.
- `backend/seed_data.py` — у дочернего индикатора `is_active=False`, добавить поле `redirect_to_code` и `redirect_to_view`.
- `backend/app/api/sitemap.py` — убрать дочерние из sitemap.
- `frontend/src/pages/IndicatorDetail.jsx` — читать `?view=` из querystring, при загрузке выставлять mode.

**Затронутые файлы.** `seed_data.py`, `nginx.conf`, `sitemap.py`, `IndicatorDetail.jsx`, `App.jsx` (если редиректить на SPA-уровне).

**Риски.**
- **Высокий риск SEO**, если редиректить неаккуратно: Google может временно понизить страницы. Нужно проверить, что в `robots.txt`/`sitemap.xml` дочерние URL убраны до 301.
- Старые форкасты под дочерними кодами в `forecast` таблице → нужно cascade retrain после миграции.
- Кэш Redis — обязательный FLUSHDB.

**Зависимости.** Сначала A1 (генерик режимы), потом A3 (миграция).

**Приоритет.** P0 (без объединения интерфейс перегружен — Никита flagged).

---

## Кластер B — Глубина истории

### B1. Ключевая ставка ЦБ — склеить со ставкой рефинансирования (1992-2013)

**Что меняем.** Сейчас `key-rate` начинается с 2013-09-13 (ввод ключевой ставки). До этого роль играла **ставка рефинансирования** (1992-2013). Никита: «надо как-то склеить, чтобы ряд был с максимальной историей».

**Механика.** Ставка рефинансирования и ключевая ставка — формально разные ставки, но **на 2013-09-13 они были фактически приравнены** (Банк России явно сообщал, что ключевая ставка = ставке рефинансирования). Это даёт чистый splice-point без сцепления.

**Данные.** Архив cbr.ru/hd_base/refinancing/ — список значений ставки рефинансирования с 01.01.1992 (~50 точек, ступенчатый ряд). Публичный источник, никаких внешних файлов не нужно.

**Затронутые файлы.**
- `backend/app/services/cbr_keyrate_html.py` (или новый `cbr_refinancing_html.py`) — fetcher для архивной ставки рефинансирования.
- `backend/app/data/refinancing_rate_historical.py` (новый seed-файл, аналог `housing_historical.py`) — immutable seed точек 1992-2013.
- `scripts/backfill_key_rate_historical.py` (новый, аналог `backfill_housing_historical.py`).
- `backend/seed_data.py` — `key-rate.methodology` обновить (без раскрытия внутренностей, по правилу языка).
- `docs/data_sources.md` — добавить запись.

**Риски.**
- Если ставка рефинансирования не точно равна ключевой ставке на 2013-09-13 — нужно явно отметить шов в данных (можно через `event` в forecast-таблице или просто в methodology упомянуть).
- Forecast retrain после backfill: `key-rate` обычно без прогноза, но проверить.

**Зависимости.** Нет.

**Приоритет.** P1.

---

### B2. Зарплата с 90-х — ✅ **CLOSED 2026-05-22** (см. История)

Залит `backend/app/data/wages_historical.py` (24 immutable точки 1991-2014, деноминация 1998 учтена). После-ревизия 2026-05-22 расширила `scripts/backfill-wages-history.py` авто-агрегацией monthly→annual_mean: 10 новых точек 2015-2025 (2022 пропущен — hole в monthly декабре 2022, занесён в P2). Итоговый ряд `wages-nominal-annual` 34 точки 1991-01..2025-01, доступен как режим «Годовое (с 1991)» через `viewModeFamilies`.

---

### B3. Аудит максимальной истории — ✅ **CLOSED 2026-05-21** (см. История)

Реализован как `scripts/audit-indicators-history.py` (а не `audit-history-depth.py`, как планировалось). Отдаёт markdown-таблицу по всем 109 индикаторам: «текущая глубина / теоретически доступная / GAP». Использовался для приоритизации B1 (key-rate), B2 (wages), C2 (wages-index). Регрессионный re-run — после любого нового backfill.

---

## Кластер C — Новые индикаторы

### C1. Индекс доступности жилья

**Что меняем.** Новый derived-индикатор `housing-affordability`. Формула (от Никиты): сколько квадратных метров жилья можно купить на месячную среднюю зарплату.

```text
housing-affordability[t] = wages-nominal[t] / housing-price-secondary[t]
```

Или, если используем индексы (что Никита и предложил):

```text
housing-affordability-index[t] = wages-index[t] / housing-price-index[t]   # база 2010 = 100
```

Чем больше — тем доступнее жильё.

**Затронутые файлы.**
- `backend/seed_data.py` — новый индикатор `housing-affordability` в категорию «Цены».
- `backend/app/services/calculation_engine.py` — `DERIVED_SPECS` запись.
- `backend/app/services/derived_ops.py` — новая op `ratio` (если нет) или специфичная `housing_affordability`.
- `frontend/src/lib/categories.js` — обновить SEO-описание категории «Цены», если нужно упомянуть.

**Риски.**
- `housing-price-secondary` сейчас в индексе (2010=100), а `wages-nominal` в рублях. Прямое деление даст «сколько метров стоит один рубль зарплаты» × коэффициент — нужно явно нормировать к 2010 (зависимость от C2).
- Альтернатива: считать в физических единицах — нужна цена квадратного метра в рублях, не индекс. Есть ли такие данные у Росстата? Возможно, есть «Стоимость 1 кв.м жилья» отдельно от индекса.

**Зависимости.** C2 (wages-index должен быть готов).

**Приоритет.** P1.

---

### C2. Зарплата в индексной форме (2010=100)

**Что меняем.** Новый derived `wages-nominal-index` (или `wages-2010-index`) — `wages-nominal` нормированный к 2010 году = 100.

**Затронутые файлы.**
- `backend/seed_data.py` — новый индикатор в «Рынок труда».
- `backend/app/services/derived_ops.py` — op `rebase_to_index(base_year=2010)`.
- `backend/app/services/calculation_engine.py` — DERIVED_SPECS.

**Риски.** Низкие — стандартная нормировка.

**Зависимости.** B2 (история зарплаты с 90-х, чтобы 2010 был в середине ряда, а не в начале).

**Приоритет.** P1.

---

### C3. Ставки по вкладам с разбивкой по сроку

**Что меняем.** Сейчас один общий `deposit-rate`. Никита хочет симметрию с кредитами — разбивка по сроку. Добавить 3 новых:
- `deposit-rate-short` (до 1 года)
- `deposit-rate-1to3y`
- `deposit-rate-over3y`

После — объединить в одну карточку «Ставки по вкладам» с переключателем срока (см. A3).

**Данные.** CBR DataService API уже даёт средневзвешенные ставки по вкладам с разбивкой по срокам (форма банковской отчётности 0409128). У ЦБ есть нужные element_id.

**Затронутые файлы.**
- `backend/app/services/cbr_dataservice_json.py` — переиспользуем existing parser, добавляем новые конфиги.
- `backend/seed_data.py` — 3 новых индикатора + объединение зонтиком в A3.
- `docs/data_sources.md` — добавить новый `element_id` в таблицу DataService; docstring `cbr_dataservice_parser.py` обновить если открыта новая trap.

**Риски.** Низкие — переиспользуем рабочий parser.

**Зависимости.** A3 (для объединения).

**Приоритет.** P0 (Никита явно flagged, лёгкая правка с большой видимой ценностью).

---

### C4. Research: редкие показатели типа RUONIA

**Что меняем.** Никита: «по руоне у нас растут показы… что ещё такого редкого можно добавить». Это **research-task**, не implementation.

**Кандидаты для предварительного скана:**
- MIACR (Moscow Interbank Actual Credit Rate).
- ROISfix (Russian Overnight Index Swap fixing).
- NFEA Swap Rate.
- OIS-кривая по разным срокам.
- ICOR (Incremental Capital-Output Ratio) — экзотический макропоказатель.
- TSI (Transportation Services Index) — ж/д, авто, авиа грузооборот.
- Real Effective Exchange Rate (REER) — у ЦБ есть.

**Затронутые файлы.** Нет (это research-фаза). По итогам — отдельные парсеры.

**Риски.** Нет.

**Зависимости.** Нет.

**Приоритет.** P2.

---

## Кластер D — UX / SEO

### D1. Поиск по индикаторам

**Что меняем.** Никита: «нам как будто поиска не хватает». Поиск по 109+ индикаторам по ключевой фразе (название, код, синонимы).

**Где разместить.** В шапке сайта (везде доступно). Поверх на главной — крупный input. На других страницах — компактная иконка → раскрывающийся input.

**Реализация.** Не нужен elastic — 109 индикаторов помещаются в один JSON ~30 КБ, ищем на frontend (substring match с подсветкой). Бэкенд может отдать готовый search-index файл.

**Затронутые файлы.**
- `frontend/src/components/SearchBar.jsx` (новый).
- `frontend/src/components/Navbar.jsx` — встроить.
- `frontend/src/pages/HomePage.jsx` — крупный input на главной.
- `backend/app/api/indicators.py` — endpoint `/api/v1/search-index` (или статический файл).
- `backend/app/data/indicator_seo.py` — добавить `synonyms: [...]` per indicator (для нахождения по альтернативным запросам, типа «инфляция» → cpi).

**Риски.**
- Если делать слишком умно (fuzzy match, морфология) — overhead. MVP: substring case-insensitive по name + name_en + synonyms.

**Зависимости.** Нет.

**Приоритет.** P0 (Никита flagged, ценность высокая).

---

### D2. Больше текста на странице индикатора (SEO)

**Что меняем.** Никита: «у нас мало текста на странице, нам бы побольше». Привёл пример как на жилье. Но `methodology` у нас по правилу проекта НЕ выдаёт внутренности и держится короткой. Значит — **новый блок**: «Что это и зачем».

**Структура нового блока (300-600 слов на индикатор):**
- Что этот показатель экономически означает (бытовым языком).
- Кто и для чего его использует (ЦБ для политики, аналитики для прогнозов, инвесторы для оценки).
- Какие у него типичные сезонные/циклические паттерны.
- Как читать график.
- Связь с другими индикаторами (linked indicators — уже добавлены, дополним текстом).

**Затронутые файлы.**
- `backend/app/data/indicator_seo.py` — новое поле `long_description` per indicator.
- `backend/seed_data.py` — возможно дублировать в model_config (зависит от архитектуры — лучше в seo_data).
- `backend/app/schemas.py` — добавить `long_description` в IndicatorDetail.
- `frontend/src/pages/IndicatorDetail.jsx` — новая секция под графиком, перед methodology.
- `backend/app/services/seo_renderer.py` — SSR-рендер этой секции (для индексации без JS).

**Риски.**
- Объём контента: 109 индикаторов × 400 слов = 40000 слов. Не быстро. Можно итеративно — сначала топ-20 по показам Google.

**Зависимости.** Нет.

**Приоритет.** P1.

---

### D3. IPP — главное число (hero value) должно быть абсолютным, не индексом

**Что меняем.** Никита: «на первую не вот этот 112, а вот это 663». Сейчас на карточке IPP в hero-числе индекс ~112. Никита хочет видеть **абсолютный объём промышленного производства** (~663 — это, видимо, индекс в каком-то другом разрезе или физический объём в млрд руб.). Аналогично подумать про другие индексы (PPI, housing-price-*).

**Источник 663 — open question.** Пользователь не помнит, откуда Никита взял это число. Два возможных подхода:

**Вариант A (default, без уточнений от Никиты — рекомендуется).** Hero-число у IPP меняем с индекса (112) на **YoY% изменение** (например, «+1.2% г/г»). Это в точности логика, которую Никита упомянул для инфляции: «как у инфляции». Бесплатно (никакого нового индикатора), просто меняем формулу hero. Применимо также к PPI, housing-price-*, любым «индексам».

**Вариант B (если 663 — это конкретный показатель Росстата).** Скорее всего, это **физический объём промышленного производства в млрд руб.** (Росстат публикует отдельно от индекса). Тогда нужен новый source-индикатор `industrial-shipped-volume` (или подобный), и hero берётся из него. Это вариант с добавлением данных.

**Что делать.** Имплементируем вариант A. После пуша — Никита посмотрит. Если скажет «не то» — переключаемся на B.

**Затронутые файлы (для варианта A).**
- `backend/app/api/indicators.py` или `backend/app/schemas.py` — добавить поле `hero_value` и `hero_subtitle` в IndicatorDetail (вычисляется на бэке).
- `backend/seed_data.py` — `model_config_json.hero_view = "yoy_pct"` для IPP, PPI, housing-price-primary/secondary.
- `frontend/src/pages/IndicatorDetail.jsx` — рендер hero из новых полей.

**Риски.** Минимальные — это смена отображения, данные не трогаем.

**Зависимости.** Нет.

**Приоритет.** P0 (Никита flagged визуально, фикс быстрый).

---

### D4. Live ticker (моргающее табло) сверху

**Что меняем.** Никита: «как у TradingEconomics, чтобы моргало». Сверху сайта — горизонтальная бегущая лента с курсами валют (USD/RUB, EUR/RUB, CNY/RUB), Brent oil, BTC. Каждое значение моргает при обновлении (раз в 30 сек — 1 мин). Можно автообновление через poll или WebSocket.

**Источники цен в real-time (предложенные, без ключей и платных подписок):**
- **Валюты intraday** — MOEX ISS API (`https://iss.moex.com/iss/engines/currency/markets/selt/securities/USD000UTSTOM.json` и аналоги для EUR, CNY). Публичный, без ключа, обновление ~1 сек, лимит ~10 req/sec.
- **Brent oil** — MOEX-фьючерсы Brent (`https://iss.moex.com/iss/engines/futures/markets/forts/securities/BR-*` — текущий ближний контракт) или Yahoo Finance (`https://query1.finance.yahoo.com/v8/finance/chart/BZ=F`, без ключа).
- **BTC, ETH** — CoinGecko (`https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum&vs_currencies=rub`), free tier 10-30 req/min, без ключа.

**Затронутые файлы.**
- `frontend/src/components/LiveTicker.jsx` (новый).
- `frontend/src/App.jsx` — встроить ticker в верх.
- `backend/app/api/ticker.py` (новый) — endpoint `/api/v1/ticker` с актуальными ценами.
- `backend/app/services/ticker_fetcher.py` (новый) — fetcher из внешних API.
- `backend/app/tasks/scheduler.py` — job `refresh_ticker` каждую минуту.
- `docker-compose.yml` — возможно отдельный env var для API ключей.

**Риски.**
- Внешние API могут rate-limit'ить или требовать ключ. Нужно проверить лимиты CoinGecko (бесплатный 10-50 req/min) — для одного экземпляра должно хватить.
- Поллинг с frontend каждые 30 сек — нагрузка на backend. Лучше WebSocket или Server-Sent Events.

**Зависимости.** Нет.

**Приоритет.** P2 (визуальный «бантик», полезен но не критичен).

---

### D5. Категория «Финансы» — разделить на Валюты / Фондовые / Товарные

**Что меняем.** Сейчас в «Финансах» 16 разнотипных индикаторов. Никита: «надо точно в отдельный блок выделить валюты… крипторынок… фондовые… товарные».

**Предложенное разбиение** (на основе текущих 16 индикаторов в «Финансах»):

- **Валюты** (если не в Ставках): `usd-rub`, `eur-rub`, `cny-rub`.
- **Драгметаллы / товарные**: `gold-price`, в будущем `oil-price`.
- **Денежно-кредитная сфера**: `m2`, `international-reserves`, `gold-reserves` (если есть).
- Кредиты/вклады/долг (см. C3): сейчас в Финансах — `consumer-credit`, `business-credit`, `deposits-individual`, `deposits-business`, `external-debt`, `mortgage-volume` — оставить в новой подкатегории «Кредиты и долг» или мигрировать в «Ставки».

**Затронутые файлы.**
- `frontend/src/lib/categories.js` — новые категории, slug'и, описания.
- `backend/app/services/seo_content.py::CATEGORY_META` — синхронно (см. ADR-0003).
- `backend/seed_data.py` — `category` для затронутых индикаторов.
- `frontend/nginx.conf` — `location ~ ^/(currencies|commodities|monetary)` для новых SPA-маршрутов.
- `backend/app/api/sitemap.py` — обновить sitemap.

**Риски.**
- **ADR-0003: `seo_content.py::CATEGORY_META` и `categories.js` должны быть синхронны.** При правке менять оба.
- SEO: URL'ы категорий `/category/finance` → новые `/currencies`, `/commodities` — потеря SEO-веса старой категории. Нужны 301 для всех старых индикаторов.

**Зависимости.** Нет.

**Приоритет.** P0 (Никита flagged как часть переработки UX).

---

### D6. Разрывы на дневных графиках (RUONIA в первую очередь)

**Что меняем.** Никита: «по ставке руоня сломано так вот немножко… разрыв получается». На дневных графиках есть визуальные дыры — выходные и праздники, когда нет торгов.

**Возможные причины и фиксы.**
- Recharts при `connectNulls={false}` рисует разрывы между точками с разной датой → выходные превращаются в визуальный «зигзаг».
- Фикс 1 (cheap): `connectNulls={true}` в IndicatorChart для daily-индикаторов → сплошная линия через выходные.
- Фикс 2 (better): на бизнес-дни не вставлять `null`, а либо переносить значение предыдущего дня (карри-форвард), либо просто пропускать пустые дни в X-оси.

**Затронутые файлы.**
- `frontend/src/components/IndicatorChart.jsx` — `connectNulls={true}` для daily.
- Возможно `frontend/src/lib/useIndicatorViewModeData.js` — фильтрация nulls.

**Риски.** Минимальные. Если карри-форвард — это уже семантика, может смутить аналитика (как будто «торги были в выходные»). Лучше connectNulls + tooltip с явной датой.

**Зависимости.** Нет.

**Приоритет.** P0 (Никита flagged, фикс на 1-2 строки кода).

---

## Кластер E — Integrity

### E1. ADR-0002 audit: `bulk_upsert` не затирает данные пустотой

**Что меняем.** Никита flagged: «допустим на Росстате пропало что-то… надо обеспечить, чтобы у нас это осталось». Это инвариант ADR-0002 (`bulk_upsert` идемпотентен `ON CONFLICT DO UPDATE WHERE value <> excluded.value`). Нужно подтвердить, что инвариант **не нарушен** ни одним парсером.

**Что проверяем.**
- ADR-0002 говорит: на конфликте по (`indicator_id`, `date`) обновляем `value` только если оно изменилось. **Но что если парсер вернул пустой список (источник пропал)?** Тогда `bulk_upsert([])` ничего не делает — данные в БД сохраняются. Это нужно подтвердить тестом.
- Что если парсер вернул `{date: 2026-03-01, value: None}`? Может ли это записать NULL поверх существующего? Нужен явный фильтр перед upsert.
- Что если парсер вернул короткий ряд (вместо 100 точек только 5)? `bulk_upsert` не удалит остальные 95 — это инвариант. Подтвердить тестом.

**Затронутые файлы.**
- `backend/app/services/upsert.py` — проверить логику, при необходимости добавить guard `if not data: return`.
- `backend/tests/test_upsert.py` — добавить тест-кейс «empty source preserves DB».
- `backend/tests/test_upsert.py` — добавить тест-кейс «None value не пишется».
- `docs/adr/0002-derived-always-reflects-source.md` — обновить раздел «Subsequent additions» с явным подтверждением data preservation.

**Риски.** Низкие — это audit с тестами.

**Зависимости.** Нет.

**Приоритет.** P0 (доверие к данным — фундамент).

---

### E2. Budget-deficit перепроверка

**Что меняем.** Пользователь поставил пункт 11. В транскрипции явно не упомянуто, но это контекст предыдущей задачи T6 (preliminary parsing из пресс-релизов Минфина). На проде сейчас:

- `budget-deficit` lag = 49 дней, последняя точка `2026-04-01`.
- Сегодня 21 мая → за май публикации Минфина обычно в конце месяца или начале июня.
- За апрель уже есть — значит **препарсер пресс-релизов работает корректно**.

**Что проверить дополнительно.**
- Логи backend на ошибки парсера Минфин за последний месяц.
- Сравнить наше значение за апрель 2026 с публикацией Минфина — если совпадает, всё ок.

**Затронутые файлы.** Нет правок кода — это проверка.

**Риски.** Нет.

**Зависимости.** Нет.

**Приоритет.** P0 (быстрая проверка, 5 минут).

---

## Future (отложено Никитой явно)

### F1. Криптовалюты в финансах

**Что отложено.** «Биткоин, эфир — можно добавить, но потом». См. D4 (часть live ticker — биткоин туда попадёт раньше как ценовая точка). Полноценные карточки `bitcoin-rub`, `eth-rub` с историей — отдельная задача после D4 и D5.

### F2. Региональные данные Росстата

**Что отложено.** «Возможность добавить огромное количество индикаторов, по типу сельхозтоваров, по регионам». Никита явно сказал «давай пока вначале вот с этим [федеральные]». Большая отдельная задача, требует расширения модели данных (region-key) и UI (фильтр по региону).

---

## Карта файлов «что за что отвечает»

Для удобства навигации при имплементации:

| Слой | Файл | Ответственность |
|------|------|----------------|
| **Seed** | `backend/seed_data.py` | Все 109 индикаторов: метаданные, categories, derived configs, methodology |
| **SEO seed** | `backend/app/data/indicator_seo.py` | Per-indicator seo_title, seo_description, synonyms (для поиска), long_description (D2) |
| **Categories sync** | `frontend/src/lib/categories.js` ⟷ `backend/app/services/seo_content.py` | ADR-0003: должны быть синхронны |
| **Historical seeds** | `backend/app/data/housing_historical.py`, `backend/app/data/refinancing_rate_historical.py` (новый), `backend/app/data/wages_historical.py` (новый) | Immutable архивные точки до начала автоматического парсинга |
| **Models** | `backend/app/models.py` | SQLAlchemy: `Indicator`, `IndicatorData`, `ForecastValue`, `CalendarEvent`, etc |
| **Schemas** | `backend/app/schemas.py` | Pydantic DTO для API |
| **Upsert (ADR-0002)** | `backend/app/services/upsert.py` | Идемпотентный bulk_upsert. Не должен затирать данные пустотой |
| **Calculation engine (ADR-0001)** | `backend/app/services/calculation_engine.py` + `derived_ops.py` | DERIVED_SPECS + чистые ops (yoy, qoq, annual_sum, etc) |
| **Parsers (source per file)** | `backend/app/services/{rosstat,cbr,minfin}_*_parser.py` | Каждый файл — один источник. См. `docs/data_sources.md` для карты source → file → лист/строка/колонка |
| **Forecast strategies** | `backend/app/services/forecast_strategies/registry.py` + конкретные стратегии | Live-SARIMA, derived-from-source, и др |
| **API routes** | `backend/app/api/{indicators,calendar,dashboard,forecasts,sitemap,system}.py` | FastAPI endpoints |
| **Scheduler** | `backend/app/tasks/scheduler.py` + `tasks/etl.py` | APScheduler: daily ETL 06:00 MSK, calendar refresh 03:00 MSK, late Minfin 15:00 MSK |
| **SEO renderer (ADR-0003)** | `backend/app/services/seo_renderer.py` | SSR для категорий и индикаторов |
| **Detail page** | `frontend/src/pages/IndicatorDetail.jsx` | Карточка индикатора: hero, график, view modes, методология, related |
| **Category page** | `frontend/src/pages/CategoryPage.jsx` | Листинг индикаторов по категории |
| **Chart core** | `frontend/src/components/IndicatorChart.jsx` | Recharts-обёртка. Свойства connectNulls, padding, intervals |
| **View modes** | `frontend/src/components/CpiViewModePicker.jsx` (переименовать в `ViewModePicker`), `FrequencySwitcher.jsx`, `lib/useIndicatorViewModeData.js` | Переключатели частоты и режима. **Уже generic** |
| **Edge / routing** | `frontend/nginx.conf` | SPA-роутинг, 301-редиректы (нужно для A3), location'ы для новых категорий (D5) |
| **Language rule** | `.cursor/rules/methodology-language.mdc` + `scripts/audit-public-language.py` | Не выдавать внутренности в публичных полях (применимо к D2) |

---

## Roadmap-задачи (мигрированы из бывшего `docs/plan.md` 2026-05-22)

### G1 — Search keywords ревизия (P2)

Сейчас `seo_keywords` заполнены неравномерно: у части индикаторов полный список синонимов (`cpi`: «инфляция, ИПЦ, рост цен»), у остальных — generic-шаблоны («Зарплаты (изм. г/г) Россия, Зарплаты (изм. г/г) прогноз»). После звонка 2026-05-22 поиск стал ходить по `seo_keywords` (haystack в `IndicatorSearch.jsx`) — качество корней теперь влияет на находимость. Пройтись по всем 109 индикаторам, добавить осмысленные корни на русском и английском. После — посмотреть в Yandex.Metrika метрику «пустых поисков» (категория Cmd+K без открытия результата). Затронутый файл: `backend/app/data/indicator_seo.py`.

### G2 — Annual-in-monthly SQL-audit (P2)

Wages фикснут (24 годовые точки переехали в `wages-nominal-annual`). Возможно тот же trap есть на других индикаторах с историческим backfill'ом: `key-rate` (event-based, не monthly — проверить как frontend label), `housing-price-{primary,secondary}` (quarterly — должны быть OK), `gdp-real` (quarterly с Q1-Q4 — должно быть OK). Скорее всего trap только на wages, но нужна явная проверка: `SELECT code, frequency, COUNT(*), MIN(date), MAX(date), date_part('month', date) FROM data_points JOIN indicators ON … WHERE indicators.code IN (…backfilled list…) GROUP BY 1,2,6` с поиском annual-only месяцев в monthly-объявленных рядах. См. trap `Annual-in-monthly mixing` в `CONTEXT.md`.

### F3 — Telegram-бот (Future)

Подписка на индикатор, daily push с изменениями, custom alerts (пороги, отклонения от прогноза). Инфраструктура: webhook URL, доступ к API через `TELEGRAM_BOT_TOKEN`, отдельная таблица в БД для подписок. Архитектурно — отдельный сервис в `docker-compose.yml`, не часть backend. `TELEGRAM_BOT_TOKEN` уже используется для `alerting.py` (критические алёрты ETL/forecast); subscriber-token будет отдельный канал.

### F4 — Embed-виджеты UI (Future)

Backend часть готова: `/embed/spark/{code}.svg`, `/embed/card/{code}.svg`, `/embed/badge/{code}.svg` + impression-pixel (`/embed/impression`, `/embed/pixel.gif`). UI часть: дизайн виджета на странице индикатора, **копи-кнопка** кода вставки (`<iframe>`), список allowed-origins в CSP. Текущая CSP в `Caddyfile` уже разрешает sentry/metrika — нужна явная политика для embed-host'ов.

### F5 — Календарь публикаций UI (Future)

Backend часть готова: 1208 событий, 46/76 source codes, `bad_public_rows=0` (ADR-0005). Текущая UI-страница `/calendar` либо отсутствует, либо плоская. Цель: цветная разметка по категориям, фильтр по источнику, push «через 24 часа выйдет ключевая ставка», iCal-фид (`/api/v1/calendar/export/ical` уже есть). См. `frontend/src/pages/CalendarPage.jsx` — стартовая точка.

---

## История (sealed правки)

### 2026-06-20 — Правки руководителя «на правки 11» (ADR-0007 Phase 2.2)

Транскрипт созвона (gpt-4o-transcribe) + кадры → 10 правок. Индикаторы (прогнозы режимов «к прошлому периоду / год к году», расширение истории) — отложены как второй приоритет по слову пользователя.

1. **OAuth-согласие.** Всплывающее окно перед Яндекс/VK с чекбоксами: политика (обязателен) + рассылка (по умолчанию вкл). Проброс `newsletter=1`; на callback при `created` пишем `Consent(pd)` + опц. `Consent(newsletter)`. `OAuthButtons.jsx`, `app/api/oauth.py`.
2. **Тоггл рассылки в кабинете.** `POST /auth/account/newsletter`; журнал append-only (`newsletter`/`newsletter_revoked`), последняя запись побеждает. `Account.jsx`, `app/api/auth.py`, `service.py`.
3. **Кабинет упрощён.** Убраны блоки «Вход в аккаунт» и «Пароль для входа по почте»; текст обратной связи переписан без негатива.
4. **«Скачать мои данные» убрана** (152-ФЗ ст. 14 = доступ по запросу, не self-service экспорт; GDPR-портируемость неприменима). Эндпоинт сохранён, политика уточнена. `Account.jsx`, `Privacy.jsx`.
5. **Хедер.** Убрана плашка «Онлайн»; десктоп-поиск pill «🔍 Поиск» (`IndicatorSearch variant="pill"`); мобильный без изменений. `Navbar.jsx`.
6. **Лимит выгрузок 2 → 5** (`download_anon_limit`, compose default `:-5`).
7. **Маркировка рекламы.** Пометка «Реклама» над РСЯ floor-баннером, только при фактической отрисовке. `YandexRSY.jsx`.

### 2026-06-19 — Личный кабинет Phase 2 (ADR-0007 «Subsequent additions»): UX, download-gate, телефоны, аналитика-бот

Доводка кабинета по правкам руководителя (10 пунктов) + Telegram-бот.

1. **Хедер.** Отдельный блок Войти/Регистрация (гость) / Кабинет (авторизован) с разделителем, desktop + mobile. `frontend/src/components/Navbar.jsx` (`AuthCluster`).
2. **Брендовые OAuth-кнопки.** Яндекс ID (#FC3F1D) / VK ID (#0077FF) с лого; редизайн карточек Login/Register (карточка, центрирование). Динамический список через `GET /auth/oauth/providers` — несконфигурированные скрыты. `OAuthButtons.jsx`, `Login.jsx`, `Register.jsx`.
3. **Чистка кабинета.** `Account.jsx` без техжаргона: профиль (имя/email/телефон), «Вход в аккаунт» с иконками, отвязка/добавление способов, опасное действие отделено.
4. **Согласия.** Чекбокс рассылки (email/телефон) при регистрации → `Consent kind="newsletter"`. `Register.jsx`, `app/api/auth.py` (`RegisterIn.newsletter`), `Privacy.jsx`.
5. **Download-gate.** Генерация Excel/CSV перенесена на backend (`app/api/export.py`, `POST /export/table`): минус ~430 КБ `xlsx` из бандла + жёсткий гейт. Гость — 2 выгрузки/сессия (cookie `fe_dl` + Redis `fe:dl:*`), авторизованный — безлимит. 403 `download_limit` → модалка регистрации. `excel.js` переписан, `xlsx` удалён из `package.json`. `app/security/download_quota.py`.
6. **OAuth под ключ.** Реальные креды Яндекс/VK в `backend/.env`; redirect-override (`oauth_*_redirect_uri`) + compat-роутер `/api/auth/{provider}/{start,callback}`; scope конфигурируем; authorize-URL проверен локально. Телефон в `OAuthIdentity.phone` (Alembic `20260619_oauth_phone`).
7. **Аналитика + Telegram.** CTA-цели в `track.js` (signup/login/oauth/download_limit/nudge/header). `notify_new_user` — мгновенное уведомление о регистрации (email/телефон/IP/UA/способ). `telegram_daily_digest_job` — ежедневный дайджест: пользователи БД + визиты/посетители + достижения всех целей Метрики. Конфиг `telegram_*`, бот/чат в env. `app/services/alerting.py`, `app/tasks/analytics_scheduler.py`, `app/main.py`.
8. **Инлайн-поиск.** `IndicatorSearch variant="inline"` на Dashboard и CategoryPage (не на IndicatorDetail), открывает существующую палитру. 
9. **RegisterNudge.** Плавающая пилюля → раскрытие с бенефитами; «не показывать больше» в `localStorage`; скрыто для авторизованных и на /login,/register,/account. `RegisterNudge.jsx`, `DownloadLimitModal.jsx`, mount в `App.jsx`.
10. **Персистентность/бэкап.** Тома `postgres_data`/`redis_data` (compose). `scripts/pg-backup.sh` + отдельный data-only dump identity-таблиц; восстановление в шапке скрипта и `docs/workflow.md`.

### 2026-06-19 — Личный кабинет Phase 1 (ADR-0007): идентичность, OAuth, сессии, 152-ФЗ

Фундамент идентичности (lead-gen-стратегия). Phase 1 локально, всё E2E; почты нет (без подтверждения email/сброса пароля/рассылок — Phase 2).

1. **Доменная модель + миграция.** `User` (UUID PK, без email) + `OAuthIdentity` + `EmailCredential` + `Consent` + `AuthAudit`. Email — атрибут способа входа, не `User`. Alembic `20260619_identity` (down_revision `20260510_calendar_official`), upgrade/downgrade проверены на докер-postgres. `backend/app/models.py`.
2. **Email+пароль.** argon2id, нормализация email (lower+trim), регистрация с явным согласием 152-ФЗ. `app/services/identity/{passwords,service}.py`, `app/api/auth.py` (`/register /login /logout /me`).
3. **Сессии в Redis.** Opaque id в httpOnly+Secure+SameSite=Lax `fe_sess`, значение (user_id, csrf) в `fe:sess:{id}`, индекс `fe:user_sessions:{uid}` для logout-all/purge, sliding TTL, ротация на входе. `app/services/session.py`. Double-submit CSRF (`XSRF-TOKEN` cookie + `X-XSRF-TOKEN` header). `app/security/auth.py`.
4. **OAuth без Authlib.** Authorization-code + PKCE(S256) вручную на httpx; реестр провайдеров `fake`/`yandex`/`vk`; state в Redis (TTL 10 мин) + `fe_oauth` Lax-cookie (login-CSRF); чистый 302-callback (требование VK ID). Резолв идентичности по `(provider, sub)`, автосвязывание только по равному верифицированному email — pre-hijack закрыт. Ветка User без email (VK). `app/services/oauth/*`, `app/services/identity/resolve.py`, `app/api/oauth.py`. Боевые Яндекс/VK требуют реальных app-кредов (pre-prod чеклист в ADR-0007).
5. **Управление аккаунтом.** set-password (для OAuth-only + доввод email), unlink (запрет снять последний способ), logout-all (текущее устройство перевыпускается). 
6. **152-ФЗ.** `Consent` при регистрации; `GET /auth/account/export` (JSON-выгрузка ПДн); `DELETE /auth/account` (явное удаление всех таблиц + purge Redis-сессий + анонимный маркер). Privacy/Terms обновлены (редакция 19 июня): состав данных учётной записи, цели, сроки, право на удаление/экспорт.
7. **Хардненинг.** lockout по (email, ip) → **423 Locked** (не 429, чтобы axios не ретраил креды); open-redirect guard на `next`; fake-провайдер запрещён в проде (startup-assert + реестр). `app/security/lockout.py`.
8. **Frontend.** `AuthProvider` (анти-фликер навбара), страницы Login/Register/Account (guard, noindex), `OAuthButtons`, кнопка «Войти/Кабинет» в навбаре, `api.js` (withCredentials + CSRF-интерсептор, без ретрая `/auth`). nginx: SPA-блок `/login|/register|/account` + `X-Robots-Tag noindex`; robots.txt Disallow. SSR/публичный кэш не трогаются — сессию читают только `/auth/*` (инвариант ADR-0003/0007).

Затронуты: `config.py`, `requirements*.txt` (argon2-cffi runtime; fakeredis+aiosqlite dev), `docker-compose.yml` (env auth/OAuth, fake+debug off по умолчанию). Тесты: 25 новых pytest (email/oauth-матрица/account/152-ФЗ/lockout/prod-assert) на герметичном SQLite+fakeredis — `check-all` зелёный без внешних сервисов. ADR-0007 создан, `CONTEXT.md::User/Identity` обновлён.

### 2026-06-16 — Созвон «ПРАВКИ ПЕРЕДЕЛ-2»: жильё-цены под ось ИПЦ, доступность без 12 мес., кнопки графика

Дореализация после первой выкатки (картинки от Никиты Александровича):

1. **Жильё-цены приведены к оси ИПЦ** (первичка + вторичка). Добавлена топ-группа **«К соотв. периоду пред. года»** (дефолт, квартальная YoY — каждый квартал к тому же кварталу год назад, `housing-yoy-*`). В группе **«К прошлому периоду»** теперь Кв/Кв + **Г/г по годам** — новый годовой ряд `housing-annual-{primary,secondary}` (декабрь-к-декабрю на квартальном индексе уровня через `ops.december_to_december`, одна точка/год, прогноз `derived_from_source`). Раньше «Г/г» в «К прошлому периоду» ошибочно показывал квартальную скользящую. `calculation_engine` (+2 spec), `seed_data`, `indicator_seo` (hidden+SEO), `housingViewModeGroups/Resolve/Content.jsx`, `useIndicatorViewModeData.js`. Прогноз 2026: первичка +12.38%, вторичка +7.06%.
2. **Доступность жилья — режим «Скользящая 12 мес.» убран** (вторичка + первичка): дублировал «среднюю за год», засорял переключатель. Убран mode+group из шаблона `T12` (`view_model_families.py`), регенерирован `viewModelFamilies.generated.json`. Осиротевшие ряды `housing-affordability(-primary)-rolling-12m` удалены из БД (локально + прод).
3. **Кнопки диапазона графика всегда справа**: при длинном заголовке контролы переносились на новую строку и липли влево. `ml-auto` на контейнере контролов в `IndicatorChart.jsx` — теперь правый край кнопок совпадает с правым краем карточки в любом режиме.

Тесты: `housingViewModeGroups.test.js` (3 группы + yoy-annual), `housingViewModeContent.test.js` (8 комбинаций), `test_view_model_families` (нет rolling у доступности), `test_calculation_engine`/`test_forecast_policy` (housing-annual в allowlist). `check-all` зелёный (482 pytest, vitest, lint, build). Браузер-smoke: пикер жилья 3 группы, Г/г годовой (27 точек + 2026 пунктир), доступность без «12 мес.», кнопки gapToRight=0. Деплой: SHA на стадии выкатки.

### 2026-06-15 — Созвон «ПРАВКИ ПЕРЕДЕЛ»: жильё, годовые прогнозы, неполный год, недельная, куки-152-ФЗ

Транскрипт видео + переписка Никиты Александровича. Шесть правок «здесь и сейчас» (личный кабинет/РЭО/рассылки — отложены):

1. **Доступность жилья** — зарплата сглаживается скользящей средней за 12 мес. перед делением на индекс цен (вторичка + первичка): разовая декабрьская премия больше не делает жильё резко «доступнее». `derived_ops.affordability_index_monthly` (+ `rolling_avg(window=12)`). Декабрьский выброс ушёл (297→213).
2. **Годовой прогноз = одна точка** (факт YTD + прогноз остатка), без 2027. `forecast_strategies/derived_from_source._forecast_from_monthly_tail` (year → один незавершённый год).
3. **Прогноз жилья «Индекс по годам»** — раньше отключён («семейство не трогаем»), теперь одна прогнозная точка на конец текущего года, как у ИПЦ/ИЦП. `useIndicatorViewModeData.js` (housing index-annual → `filterForecastToBucketEnds`).
4. **Недельная инфляция** — окно перечитывания `WEEKLY_REFRESH_WINDOW_DAYS=120`: перезапуск сервера больше не «замораживает» ряд (повторно отдаём недавние точки в idempotent upsert). `rosstat_weekly_inflation_parser.py`.
5. **Неполный текущий год не показываем** — `_aggregate` отбрасывает год/квартал с числом уникальных месяцев меньше ожидаемого (`_expected_subperiods`); порог в месяцах, не в сырых точках (иначе дневные агрегаты не отсекались). Дублировано на фронте в `applyAggregateTransform`. Инвестиции в осн. капитал больше не обваливаются за 2026. См. `CONTEXT.md::Incomplete-period aggregation trap`.
6. **Куки default-on (152-ФЗ, подразумеваемое согласие)** — Метрика и реклама грузятся всем при первом заходе (если нет явного opt-out текущей версии); баннер информационный, отзыв — «Настройки cookie» в подвале; Политика и Соглашение переписаны. `consent.js` (public + lib), `CookieConsent.jsx`, `Privacy.jsx`, `Terms.jsx`. Фикс падения статистики Метрики и дохода РСЯ.

Тесты: `test_derived_ops` (+2 кейса неполного периода daily/quarterly), `test_calculation_engine`, `test_derived` (forecast), `test_rosstat_weekly_inflation`, `viewModeFamilies.test.js` (обновлены под отсечение). `check-all` зелёный. Деплой: SHA на стадии выкатки.

### 2026-06-12 — SEO-усиление: IndexNow, OG-превью, годовые landing'и, RSS, ETag, code-split

Один проход по «high + medium effect» SEO-улучшениям (детали — ADR-0003 «Subsequent additions», инвариант для новых индикаторов — `CONTEXT.md::SEO meta bundle` и `AGENTS.md` чеклист «новый индикатор» п. 8):

- **IndexNow** (`backend/app/services/indexnow.py`): после daily/late ETL батч-пинг Яндексу с обновлёнными URL (source + derived + главная). Ключ в `config.py::indexnow_key`, key-файл `frontend/public/{key}.txt`.
- **OG-превью per-indicator** (`backend/app/services/og_image.py`, Pillow + Inter TTF с кириллицей в `app/assets/fonts/`): `/og/{code}.png` (nginx `^~ /og/` → backend), PNG 1200×630 со спарклайном и актуальным значением, in-memory кэш 1 ч. Подключено в `build_document(og_image=...)`.
- **Годовые landing-страницы** `/indicator/{code}/{year}` (`render_indicator_year_html`): чистый SSR без React-bundle (`include_app=False`), data-driven итоги года + таблица + навигация по годам; в sitemap listed-индикаторы с ≥ 2 точками за год (priority 0.4). Nginx-regex в кавычках (`{2}` иначе ломает парсер конфига).
- **RSS** `/feed.xml` + `<link rel="alternate">` во всех SSR-документах.
- **ETag/304 на SSR** (`seo_pages.py`) + методы GET+HEAD (роботы шлют HEAD — был 405).
- **Dataset JSON-LD**: `distribution` (DataDownload → `/api/v1/indicators/{code}/data`), `isAccessibleForFree`, `license`.
- **Autolink** терминов в seo_blocks (curated `AUTOLINK_TERMS` в `seo_renderer.py`), self-ссылки пропускаются.
- **Code-split**: `xlsx` (~430 КБ) из статического импорта `lib/excel.js` → динамический `await import('xlsx')` при экспорте; чанк IndicatorDetail похудел на ~60%.

### 2026-06-06 — истинность представления + полная выгрузка + мобильные тикеры + GDP vintage

Завершающий проход по «не-режимным» правкам созвона (после унификации view-mode семей):

- **Истинность дат (truth-visual + телеметрия).** Введён единый `resolveDateFormat({chartMode, frequency, safeViewMode})` в `frontend/src/lib/format.js` — один источник правды для формата периода на оси графика, в таблице и в телеметрии. Удалён дубль `dateFormatFor` из `IndicatorChartSection.jsx` и `IndicatorDataTableSection.jsx`. В `IndicatorTelemetryGrid.jsx` даты значения/предыдущего/максимума раньше были захардкожены `'full'` («месяц ГГГГ») — теперь по гранулярности ряда: квартальный → «I кв. 2026», годовой → «2026», дневной → «12 марта 2026». `chartMode` прокинут в телеметрию из `IndicatorDetail` и `GenericIndicatorView`. +30 format-тестов. Браузер-smoke: deaths (год → «2023»), gdp-investment (кв → «IV кв. 2025», ось X — кварталы), m2 (мес → «апрель 2026»).
- **Полная выгрузка CSV/Excel.** `IndicatorChart` получил колбэк `onFullData` — эмитит полный `chartData` (факт+прогноз) до нарезки видимого окна. Оба вью экспортируют всю историю (`range='all'`), снят 5-летний cap. Удалён мёртвый `chartData`/`currentRange`/`handleRangeChange` в `IndicatorDetail` и `GenericIndicatorView`.
- **Мобильные тикеры.** Снят desktop-only gate в `LiveTicker.jsx` — статичная компактная полоса котировок теперь рендерится и на мобиле. Синхронизированы отступы: `App.jsx main` → `pt-9` (было `pt-0 md:pt-9`), `Navbar.jsx` → `top-11 md:top-12`, чтобы тикер не перекрывался шапкой.
- **Variant-лейблы жилья.** `indicatorVariants.js`: «Первичное»/«Вторичное» → «Первичное жильё»/«Вторичное жильё» (полные названия, `flex-wrap` переносит). Золото/биткоин подтверждены в каталоге (is_listed=True, категории «Финансы»/«Валюты»).
- **Режим-консистентность прогноза.** `housing-qoq-primary`/`housing-qoq-secondary` имеют `derived_from_source`-прогноз (qoq от `housing-price-*`) — добавлены в контракт `test_forecast_policy.py::DERIVED_FROM_SOURCE_FORECAST_CODES`. Включение прогнозов остальных derived-siblings — под рубильником `forecast_steps:0`, ждёт curated-файл руководителя.
- **GDP vintage.** `ROSSTAT_STATIC_URLS['gdp_quarterly']` → `VVP_kvartal_s_1995-2026.xlsx` (текущая публикационная версия; +docstring парсера +`data_sources.md`). Структурная сетка уровней в файле заканчивается Q4 2025; Q1 2026 опубликован Росстатом 15.05.2026 только как предварительный индекс физобъёма 99.8% (−0.2% г/г) в пресс-релизе, не как уровень в млрд руб. Пайплайн авто-подхватит уровень при следующей публикации. Вставка расчётного уровня из пресс-% — открытая продуктовая развилка (оценка vs официальный уровень).

**Verification.** `./scripts/check-all.sh` зелёный: backend 431 passed / 8 skipped, frontend lint=0, vitest 200 passed, vite build чистый. Браузер-smoke (desktop deaths/gdp-investment/m2 + mobile homepage) — 4/4 PASS.

### 2026-05-22 — view-mode family downstream completion (methodology + frequency leak)

После Phase 1-5 (звонок «всё доделать») остались два downstream-протекания, замеченные на `/indicator/wages-nominal?mode=annual` при верификации B2:

- **Methodology cross-mode leak**. `cpiViewModeContent.jsx::getViewModeContent()` отдавал CPI-блок `ANNUAL` («годовая инфляция декабрь к декабрю») для любого `safeViewMode === 'annual'`, без проверки `isPriceCategory`. На странице wages пользователь видел чужой текст. Аналогично для `quarterly` и `weekly`.
- **Frequency metadata leak**. `effectiveIndicator` в `IndicatorDetail.jsx` подменял `unit` и `name`, но **не** `frequency`. Pill под breadcrumbs и заголовок графика читали `indicator.frequency` родителя (monthly у wages-nominal), хотя active sibling имел другой ритм (annual у wages-nominal-annual). Пользователь видел «ПОМЕСЯЧНО» в режиме «Годовое (с 1991)».

**Фикс (4 файла кода + 2 файла тестов + vitest.config):**
- `frontend/src/lib/cpiViewModeContent.jsx`: все CPI-specific ветки обёрнуты в `if (isPriceCategory)`. Не-CPI индикаторы падают в fallback на `indicator.{description, methodology}` из БД.
- `frontend/src/lib/viewModeFamilies.js`: у каждого не-`level` mode (real sibling) задан `frequency`. Добавлен `DAILY_AGG_FREQUENCY` mapping для Phase 5 daily-aggregation.
- `frontend/src/pages/IndicatorDetail.jsx`: `effectiveIndicator` подменяет `frequency` из `familyModeMeta.frequency` или `DAILY_AGG_FREQUENCY[granularity]`. Header принимает отдельный prop `displayFrequency`.
- `frontend/src/components/IndicatorDetailHeader.jsx`: новый prop `displayFrequency` (override `indicator.frequency` для pill, при сохранении родительского `name`/`category` для H1/breadcrumbs).
- `frontend/src/lib/cpiViewModeContent.test.js` (новый, 9 тестов): для `isPriceCategory=false` функция возвращает fallback; для `isPriceCategory=true` — CPI-блоки.
- `frontend/src/lib/viewModeFamilies.test.js`: инвариант «каждый не-level mode имеет `frequency` или `transform`» + проверка `DAILY_AGG_FREQUENCY`.
- `frontend/vitest.config.js`: добавлен `@vitejs/plugin-react` (нужен для JSX в импортируемых модулях).

**Verification.** `/indicator/wages-nominal?mode=annual` → заголовок графика «(...)  — годовая», методология «Среднемесячная номинальная начисленная заработная плата работников...» (свой текст wages). `/indicator/unemployment?mode=quarterly` → заголовок «(...) — квартально», методология «Доля безработных в экономически активном населении по методологии МОТ» (свой текст unemployment). 29/29 тестов зелёные.

ADR-0006 «Subsequent additions» дополнен описанием решения. CONTEXT.md: 4-я trap «View-mode family metadata leak» с правилами для новых семей и новых mode-specific блоков.

### 2026-05-22 — после-ревизия: B2 wages annual continuation + B3 итог зафиксирован

- **B2 (closure)**. Расширил `scripts/backfill-wages-history.py`: помимо immutable 1991-2014 из `wages_historical.py` теперь скрипт подтягивает monthly точки `wages-nominal` из БД, группирует по году, для **полных** лет (12 месяцев) считает annual mean, аппендит к историческому хвосту, всё одним идемпотентным `bulk_upsert` в `wages-nominal-annual`. Прогон на локальной БД: 24 hist + 10 auto = 34 точки, диапазон 1991-01..2025-01. Год 2022 пропущен — обнаружен hole в monthly (нет декабря 2022), перенесён в P2 как отдельный микрофикс. Год 2026 пропущен корректно (только 2 месяца, неполный). Trap «annual continuation требует ручного re-run после закрытия года или derived spec `annual_mean`» зафиксирован в docstring скрипта.
- **B3 (закрытие)**. Подтверждено: задача реализована как `scripts/audit-indicators-history.py` (имя отличается от planned `audit-history-depth.py`, функционально эквивалентно). Markdown-таблица «текущая / теоретическая / GAP» по всем 109 индикаторам, плюс список кандидатов на backfill. Скрипт переиспользуется при добавлении любого нового indicator (см. checklist «новый индикатор» в `AGENTS.md::Шаг 4`, пункт 1 «Source-depth invariant»).

### 2026-05-22 — звонок «всё доделать» (5 phases + grill-me ticker + search)

- **Phase 5** daily-aggregation: `applyAggregateTransform` для 8 daily-индикаторов (key-rate, ruonia, usd-rub, eur-rub, cny-rub, gold-price, brent, btc-usd), client-side bucket-avg [week/month/quarter/year]. Коммит `d4f57ae`.
- **Phase 4** rates rename: `credit-rate-corp-short`, `credit-rate-ind-short`, `deposit-rate` → общие имена («Ставка по кредитам юридическим лицам» / «физическим лицам» / «по вкладам физических лиц»); term split (До 1 года / 1-3 / >3 лет) через VariantGroupPicker. Коммит `d4f57ae`.
- **Phase 3** housing: `housing-price-{primary,secondary}` с view-mode picker [Индекс / YoY %]. `housing-yoy-*` стали режимами. Коммит `d4f57ae`.
- **Phase 2** labour: `wages-nominal` единая карточка с 4 режимами [Номинальная / Реальная / YoY % / Индекс 2015=100]; `unemployment` с 3 режимами [Месячно / Квартально / 12М avg]. 5 derived'ов скрыты из listing. Коммит `d4f57ae`.
- **Phase 1** trade unification: 8 view-mode семей (exports / imports / trade-balance / current-account + 4 monthly counterparts с MoM%). Новая 10-я op `yoy_abs` для negative-capable. Коммит `876b3c7`.
- **Live ticker grill-me**: USD/RUB / EUR/RUB / CNY/RUB / BTC/USD / Brent с MOEX-приоритет + CBR XML_daily fallback (для FX когда MOEX отдаёт `LAST=None` — особенно EUR/RUB после санкций) + Binance public API для BTC + Yahoo Finance для Brent historical. Backend APScheduler `ticker_live_pull` каждые 5s в Redis. Коммит `876b3c7`.
- **Search full directory**: `IndicatorSearch.jsx` показывает все индикаторы (включая скрытые из listing) через `?include_unlisted=true`. Коммит `876b3c7`.
- **Frontend rename**: `tradeViewModes.js` → `viewModeFamilies.js` (общий реестр), `tradeFamily/tradeMode` → `viewFamily/familyMode`. ADR-0006 (новый) фиксирует ось «карточка vs derived vs variant vs frequency». Чеклист «новый индикатор» в `AGENTS.md::Шаг 4`. CONTEXT.md: +2 trap'ы (source-depth + browser-cache). Коммит `d4f57ae`.

### 2026-06-07 — Бюджет Минфин: снять артефакты ~10 трлн (source + все режимы)

- **Симптом:** на проде май 2026 ~10–12 трлн на доходах/расходах; режимы М/м, Кв/Кв, За период (квартал/год), Г/г оставались кривыми после чистки source.
- **Причина:** `replace_series` почистил только source-ряды; derived sibling'и (`*-mom`, `*-sum-quarter`, `*-yoy`) не пересчитывались и не удаляли stale-даты.
- **Правки:** `prune` в `calculation_engine._execute`; `run_for_direct_dependents` + каскад из `MinfinBudgetParser._after_storage` на все view-mode ряды T6/T7.

### 2026-06-07 — Weekly CPI ETL: steady-state без лишних GET/upsert + timeout 600s

- **Симптом на проде:** `inflation-weekly` daily ETL 1–7 июня — `fetch_log.status=timeout` на 300с, июньская точка не попала в БД до ручного прогона.
- **Правки:** сегменты food/nonfood/services фильтруются по своим датам в БД (не upsert всей истории XLSX); steady-state central-news max 12 стр., search 2 мес., XLSX только текущий год; `ETL_TIMEOUT_BY_PARSER['rosstat_weekly_cpi']=600`. Файлы: `rosstat_weekly_inflation_parser.py`, `scheduler.py`, `CONTEXT.md` trap.

### 2026-06-07 — Базовая цифра карточки = первый вход + даты по частоте (звонок minskaya-ulitsa-2)

- **Hero на listing-карточке (задача «базовая цифра»):** list-endpoint теперь считает `hero_value` (YoY %) для индекс-индикаторов с `model_config_json.hero_view="yoy_pct"` (ИПП, ИЦП, цены на первичное/вторичное жильё). `IndicatorSummary` получил поле `frequency`. `IndicatorTile` показывает hero (10.8 % · г/г) вместо уровня индекса (346) — число на карточке каталога совпадает с тем, что видно при первом входе (там по умолчанию режим г/г). Файлы: `backend/app/api/indicators.py`, `backend/app/schemas.py`, `backend/seed_data.py`, `frontend/src/components/IndicatorTile.jsx`.
- **Персист последнего режима:** последний выбранный view-mode пишется в `localStorage` (`fe:viewmode:<code>`) и восстанавливается при заходе без `?mode` (в т.ч. из каталога). Для ИПП восстановление встроено в дефолт-редирект. Файл: `frontend/src/pages/IndicatorDetail.jsx`.
- **Даты телеметрии по частоте (задача «март/декабрь вместо квартала»):** `resolveDateFormat` теперь ставит частоту ряда выше режима — точка г/г на квартальном ряду датируется кварталом («I кв. 2026»), а не месяцем. Карточка «предыдущий» в режиме г/г переименована в «Предыдущий квартал/месяц» (совпадает с реальной датой), верхняя цифра г/г чистая (без двойного `%`-дельты), единица «%». Файлы: `frontend/src/lib/format.js`, `frontend/src/components/IndicatorTelemetryGrid.jsx`.
- **Чистка:** `housing-affordability` переименован в «Индекс доступности жилья» (без «вторичное жильё» в заголовке; переключатель первичное/вторичное оставлен). Устаревший осиротевший sibling `housing-affordability-eop-year` (эпоха T4) скрыт из листинга. Файлы: `backend/seed_data.py`, `backend/app/data/indicator_seo.py`.

### 2026-06-07 — Индекс доступности жилья (пересчёт v7) + фикс ИПП

- **Housing-affordability rework (C1/C2 доработка):** `wages-index` переведён с базы 2015 на базу 2010 (новая op `rebase_to_index_with_base`, базовое среднее из годового ряда зарплаты). `housing-affordability` стал помесячным (новая op `affordability_index_monthly`, forward-fill квартального индекса цен). Добавлена вторая карточка `housing-affordability-primary` (первичный рынок) как variant-группа «Доступность жилья». Новый generic-шаблон T12 (уровень: мес/ср.квартал/ср.год · М/м·Кв/Кв · Г/г · скользящая 12 мес.). Тексты приведены к единой базе 2010 (seed + indicator_seo). Прогноз не строится. ADR-0001 «Subsequent additions» 2026-06-07. Решение по развилке: помесячно с forward-fill цен (ряд начинается 2015, где есть помесячная зарплата; паритет базы 2010 проверяется на op-уровне).
- **Задача 2 — ИПП «вакханалия» при заходе из категории:** удалена устаревшая variant-группа `ipi` (`ipi-yoy` + `ipi`), дублировавшая режимы generic-семьи ИПП и конфликтовавшая с дефолт-редиректом `ipi→?mode=yoy`. Теперь карточка ИПП рендерит только ViewModePicker, редирект стабилен (11 API-запросов на загрузку вместо storm'а). Аудит остальных variant-групп: других mode-дублирований нет.

### 2026-05-21 — большой пакет P0+P1+P2

- 2026-05-21 P2 D4: live ticker (USD/EUR/CNY/key-rate/RUONIA/gold) над навбаром. Коммит на стадии деплоя.
- 2026-05-21 P2 B3: скрипт `scripts/audit-indicators-history.py` — markdown-таблица + список кандидатов на backfill. Коммит на стадии деплоя.
- 2026-05-21 P1 D2: длинные SEO-блоки (`IndicatorSeoBlocks` + INDICATOR_SEO_BLOCKS на 12 кодов). Коммит `75013ab`.
- 2026-05-21 P1 C2: derived `wages-index` (база 2015=100). Коммит `75013ab` + `ae3baf0`.
- 2026-05-21 P1 C1: derived `housing-affordability` = (wages-index ÷ housing-price-secondary) × 100. Коммит `75013ab` + `ae3baf0`.
- 2026-05-21 P1 B1: ставка рефинансирования 1992-2013 склеена с `key-rate` (84 точки, scripts/backfill-keyrate-history.py). Коммит `75013ab`.
- 2026-05-21 P0+правки №1, №2: 3 семейства ставок (corp/ind/deposit) с VariantGroupPicker по сроку; Cmd+K modal вместо узкого input. Коммит `800fa0a`.
- 2026-05-21 P0 batch: E1 bulk_upsert guard, E2 проверки, D6 connectNulls, D3 hero YoY, A3 is_listed-фильтр листинга, D5 split «Финансы» → «Валюты» + «Деньги и бюджет», D1 первичный поиск. Коммит `91c3f9c`.
- 2026-05-16 T13: чистка публичного языка в `methodology`/`description` (26 полей). Коммит `9789982`. См. `.cursor/rules/methodology-language.mdc`.
- 2026-05-16 T10: housing-price-* backfill 1998-2014. Коммит `840df17`.
- 2026-05-16 T11: `ppi` переведён с approved на live-SARIMA `ppi_monthly`. Коммит `ace7905`.
- 2026-05-16 T12: calendar group-by похожих событий (frontend). Коммит `ace7905`.
- 2026-05-13 T9: прогнозы для housing-yoy-* и gdp-{consumption,government}. Коммит `f7d4f85`.

---

## C4 — research: дополнительные индикаторы (P2, отложено)

> Ниже — short-list канонических индикаторов, которые имеет смысл добавить в платформу в будущих итерациях. Каждая позиция включает источник, частоту, сложность парсинга и ожидаемую ценность для пользователя.

### Краткосрочные ставки и денежный рынок

- **RUONIA по срокам (1D, 1W, 1M)** — у нас есть только дневная overnight ставка. CBR публикует на той же странице `https://cbr.ru/hd_base/RUONIA/`. Парсер `cbr_dataservice_json` уже работает с этим источником, нужны новые `element_id`.
- **MosPrime Rate** (1M, 3M, 6M) — независимая ставка межбанковского рынка от ACI Russia. Источник: `https://www.mosprime.com/`. Простой HTML-парсер; ценность — индикатор стресса/ликвидности.
- **NFEA Swap Rate** (1Y, 2Y, 5Y, 10Y) — процентный своп от Национальной финансовой ассоциации (forward-looking ставки). Источник: `https://www.nfea.ru/`.

### Спред и кривая доходности

- **OFZ Curve** (1Y, 3Y, 5Y, 10Y) — кривая бескупонной доходности ОФЗ. CBR публикует на `https://cbr.ru/hd_base/zcyc_params/`. Парсер: тот же `cbr_dataservice_json`, новые element_id.
- **Спред OFZ 10Y — Key Rate** — derived, мера ожиданий рынка по будущей ставке.

### Платёжный баланс, детализация

- **Доходы федерального бюджета по статьям** (Нефтегазовые vs ненефтегазовые). Минфин публикует ежемесячно. Парсер `minfin_budget_xlsx` уже есть, нужны дополнительные columns.
- **Внешний долг по секторам** (sovereign / corporate / banks). CBR публикует ежеквартально.

### Реальный сектор

- **Грузооборот транспорта** (млрд тонно-км). Росстат, ежемесячно, форма П-7. Опережающий индикатор экономической активности.
- **Электропотребление** (млрд кВт·ч). СО ЕЭС публикует ежедневно/ежемесячно. Тоже опережающий.
- **Розничный товарооборот** в реальном выражении (РТО) — уже частично есть как retail-sales, можно расширить разбивку на продовольственные/непродовольственные.

### Цены товаров

- **Brent / Urals spot** — котировки из MOEX или Reuters. Парсер пока не реализован.
- **Серебро / Платина / Палладий** — CBR публикует учётные цены наряду с золотом (`gold-price`). Тот же парсер, новые element_id.

### Демография и социальное

- **Реальные располагаемые доходы** (квартально, Росстат). Ключевая метрика уровня жизни.
- **Прожиточный минимум** — устанавливается правительством, базовая величина социальных выплат.

### Future (явно отложено пользователем)

- F1: Криптовалюты (BTC, ETH, USDT через CoinGecko) — Никита решил, что не нужно для аналитической платформы.
- F2: Региональные разрезы (например, инфляция по 82 субъектам РФ) — масштаб 100+ ×, требует отдельного UI с картой и фильтрами.
