# Data sources — точная карта индикатор → файл/endpoint

**World extension last verified:** 2026-08-16 (country area registry `world_country_area.py`;
Eurostat `reg_area3` Total area + national statistical/cadastre sources).

**Last updated:** 2026-08-16 (демография/наука: discovery со страниц разделов + EDN_12 для лагов demo21; сырьё: Yahoo desk снят с витрины — `natural-gas` → EIA `DHHNGSP` через `fred_csv`; `coal`/`copper`/`silver`/`wheat`/`soybean` → World Bank Pink Sheet monthly `world_bank_pink_sheet`; `steel` деактивирован / unlisted. Ранее тем же днём: FRED CSV `fred_csv` для `usd-index`/`ust-10y`/`brent`; `gold-usd` не заведён — нет свободного дневного ряда). Ранее 2026-07-06 (CTO-аудит, Волна 5: счётчик source-индикаторов актуализирован — 109 (было заявлено 75); добавленные с 2026-05-31 семейства покрыты соответствующими разделами ниже и docstrings парсеров: демография (`rosstat_demo`), наука/инновации (`rosstat_science`), основные фонды (`rosstat_fixed_assets`), ИПП-разделы (`rosstat_ind`), крипта BTC/ETH/SOL (`binance_btcusdt`), биржевые индексы и товарные MOEX (`moex_index`, `moex_brent_daily`), недельные цены топлива (`rosstat_weekly_price`), денежные агрегаты M0/M1/M2 (`cbr_monetary_agg`). Два parser_type зарегистрированы, но в seed не используются (задел): `cbr_dataservice_sum` — суммирование нескольких DataService-элементов по дате, `cbr_monetary_html` — HTML-таблицы денежной статистики ЦБ; не удалять без ревизии прод-БД. Ранее 2026-05-31: T13 — данный файл стал основным местом хранения технических деталей источников — имена файлов, листы, строки/колонки, API-id; публичные `methodology` поля индикаторов в `seed_data.py` не выдают этих внутренностей, см. правило [`.cursor/rules/methodology-language.mdc`](../.cursor/rules/methodology-language.mdc).)
**Part of:** [`AGENTS.md`](../AGENTS.md), [`CONTEXT.md`](../CONTEXT.md).
**Related:** docstrings парсеров `backend/app/services/{cbr_*,minfin_*,rosstat_*}_parser.py` (per-parser internals: traps, схема `model_config_json`, особенности формата), [`docs/adr/0004`](adr/0004-rosstat-russian-canonical-sdds-deprecated.md) (Rosstat русский canonical).

> **Single source of truth** для актуальных URL/файлов, откуда тянется каждый из 111 source-индикаторов. Если меняется источник в коде парсера или `seed_data.py` — **обязательно** актуализировать этот файл (см. [`AGENTS.md::Шаг 4`](../AGENTS.md#шаг-4--протокол-актуализации-документации-критично)).
>
> Derived-индикаторы (28) не входят — они не имеют внешнего источника, считаются из source через `DERIVED_SPECS`.

---

## Convention

- **CBR base**: `https://www.cbr.ru`
- **Rosstat base**: `https://rosstat.gov.ru/storage/mediabank/`
- **Минфин base**: `https://minfin.gov.ru/opendata/`
- В таблицах URL сокращён до пути от соответствующего base.
- Конфигурация per-indicator живёт в `Indicator.model_config_json` (PostgreSQL JSONB).

---

## ЦБ РФ — платёжный баланс (CbrBopParser)

Файл: `cbr.ru/vfs/statistics/credit_statistics/bop/bal_of_payments_standart.xlsx` (общий для 6 индикаторов, селектор `bop_target` в `model_config`). Лист «Кварталы». Глубина с 1994-Q1.

| Индикатор | bop_target |
|-----------|------------|
| `exports` | `exports` |
| `imports` | `imports` |
| `services-exports` | `services-exports` |
| `services-imports` | `services-imports` |
| `trade-balance` | `trade-balance` |
| `fdi-net` | `fdi-net` |

## ЦБ РФ — внешняя торговля **товарами** monthly (CbrTradeGoodsMonthlyParser)

Файл: `cbr.ru/vfs/statistics/credit_statistics/trade/trade.xls` (legacy XLS), лист «Ежемесячные», 17 columns. **Глубина с 1997-01**. Селектор `bop_target` в `model_config`.

| Индикатор | bop_target | Источник колонка |
|-----------|------------|------------------|
| `exports-monthly` | `exports-monthly` | col 2 (Экспорт ФОБ Всего, млн $) |
| `imports-monthly` | `imports-monthly` | col 8 (Импорт ФОБ Всего, млн $) |
| `trade-balance-monthly` | `trade-balance-monthly` | col 14 (Сальдо торгового баланса, млн $) |

Цель: монтлы-разбивка для frequency switcher на карточках `exports`/`imports`/`trade-balance` (`alternate_frequencies.monthly` в parent `model_config`). См. `docs/adr/0004` для аргументации canonical Russian sources. `is_listed=False` — карточки доступны через switcher из родителя, не дублируем в листинге категории «Торговля».

**Cross-check c TradingEconomics (2026-05-12)**: последние точки сходятся 1:1 (Feb 2026: exports=30,123 / imports=24,770 / balance=5,353 — копия из ЦБ РФ). Исторические extremes: max exports Dec 2021 = 58,148, max imports Dec 2025 = 34,011 — также 1:1. **Единственная разница**: TE имеет историю с **1994-01** (3 года глубже нашего 1997-01). Это потому что `trade.xls` ЦБ сам начинается с 1997-01; ранее 1994-1996 ЦБ публиковал только через bulletin'ы платёжного баланса (другой формат, требует отдельного парсера). Backfill 1994-1996 = **P2 priority** (29 лет покрытия уже более чем достаточно).

## ЦБ РФ — внешняя торговля **услугами** monthly (CbrTradeServicesMonthlyParser)

Файл: `cbr.ru/vfs/statistics/credit_statistics/trade/trade_monthly.xlsx`, лист «месяцы » (с trailing-пробелом). **Transposed layout**: row 4 — даты в headers (datetime cells + последние 1-2 cell = estimate strings типа «янв.26\n(оценка)»), col 1 — labels. **Глубина с 2018-01**.

| Индикатор | bop_target | Источник row label |
|-----------|------------|---------------------|
| `services-exports-monthly` | `services-exports-monthly` | «Экспорт услуг» |
| `services-imports-monthly` | `services-imports-monthly` | «Импорт услуг» |

## ЦБ РФ — внешний долг (CbrDebtParser)

| Индикатор | File |
|-----------|------|
| `external-debt` | `cbr.ru/vfs/statistics/credit_statistics/debt/debt_new.xlsx` |

## ЦБ РФ — курсы валют (CbrFxParser)

Endpoint: `cbr.ru/scripts/XML_dynamic.asp?date_req1={from}&date_req2={to}&VAL_NM_RQ={code}`.

| Индикатор | VAL_NM_RQ | Пол истории (`backfill_from`) |
|-----------|-----------|-------------------------------|
| `usd-rub` | `R01235` | `1998-01-01` |
| `eur-rub` | `R01239` | `1999-01-01` (евро у ЦБ с 1999) |
| `cny-rub` | `R01375` | `1998-01-01` |

> **Пол истории = деноминация рубля 1000:1 (1998-01-01).** XML_dynamic отдаёт курсы с 1992-07, но до 1998 они в «старых» рублях (1997-12-30 USD = 5960). Сплайс со «новыми» дал бы разрыв ×1000 и не прошёл бы `validation.max=500`. Поэтому floor = 1998-01-01 (`backfill_from` в `model_config_json`); ряд непрерывен и захватывает кризисы 1998/2008/2014/2022. Среднее/агрегаты по периодам (avg-week/month/quarter/year) автоматически тянутся с 1998.

## ЦБ РФ — драгметаллы (CbrGoldParser)

| Индикатор | Endpoint | Пол истории |
|-----------|----------|-------------|
| `gold-price` | `cbr.ru/scripts/xml_metall.asp?date_req1={from}&date_req2={to}` | `1998-01-01` (`backfill_from`; `validation.min` 100→40 — ранний-1998 ≈ 52 руб/г до девальвации) |

## Binance — crypto daily (BinanceBtcUsdtParser)

Тикер config-driven через `model_config_json.binance_symbol`. Прогноз не строится (`forecast_steps=0`), категория «Валюты».

Глубина истории (2026-08-05, self-healing): Binance BTCUSDT/ETHUSDT листингованы с 2017-08-17, SOLUSDT — с 2020-08-11; более ранний сегмент добирается с Coinbase Exchange (`api.exchange.coinbase.com/products/<sym>/candles`, дневные, ≤300 свечей/запрос) по `model_config_json.pre_binance`. Парсер дозапрашивает окно `[backfill_from, earliest)`, когда самая ранняя точка БД позже `backfill_from` — расширение истории делается сменой конфига + ETL, без одноразовых скриптов. На пересечении дат побеждает Binance (канон свежей эпохи).

| Индикатор | Endpoint | История |
|-----------|----------|---------|
| `btc-usd` | `api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1d` — поле `close`, дата = календарный торговый день (UTC). Live-тикер — отдельно `ticker_sources/binance.py`. | 2015-07-20 → (Coinbase BTC-USD до 2017-08-16, дальше Binance) |
| `eth-usd` | то же, `symbol=ETHUSDT`. | 2016-05-18 → (Coinbase ETH-USD до 2017-08-16, дальше Binance) |
| `sol-usd` | то же, `symbol=SOLUSDT`. | 2020-08-11 → (Binance; монета запущена 2020-03, раньше первоисточника нет) |

## World Bank Pink Sheet monthly (`WorldBankPinkSheetParser`, `parser_type=world_bank_pink_sheet`)

Официальная месячная сводка цен на сырьё Всемирного банка (Commodity Markets / Pink Sheet). URL xlsx **меняется каждый месяц** — парсер открывает `worldbank.org/en/research/commodity-markets` и ищет ссылку `CMO-Historical-Data-Monthly.xlsx`. Лист `Monthly Prices`: строка имён, строка единиц, строки `YYYYMmm`. Колонка — `model_config_json.pink_sheet_column`. `replace_series=True` (полный снимок, срезает хвост старого Yahoo daily). Лицензия: CC-BY 4.0 Всемирного банка (attribution); публичное поле `source` = «Всемирный банк». Прогноз не строится; семья view-mode — T8 (месячный уровень).

| Индикатор | pink_sheet_column | Единица | Заметки |
|-----------|-------------------|---------|---------|
| `coal` | `Coal, Australian` | USD/т | Бенчмарк Ньюкасл; с 1970M01. Ранее Yahoo ICE Rotterdam `MTF=F` (мёртв с 2025-12-26). |
| `copper` | `Copper` | USD/т | Было USD/фунт daily Yahoo `HG=F`. |
| `silver` | `Silver` | USD/унция | Было daily Yahoo `SI=F`. |
| `wheat` | `Wheat, US HRW` | USD/т | Было US¢/бушель Yahoo `ZW=F`. |
| `soybean` | `Soybeans` | USD/т | Было US¢/бушель Yahoo `ZS=F`. |

**Снято с витрины:** `steel` (`is_active=False`, в `INDICATOR_HIDDEN_FROM_LISTING`) — нет свободного официального ряда HRC: CME/LME требуют коммерческой лицензии на историю; в Pink Sheet колонки HRC нет; индекс BLS PPI — не цена в USD/т.

**Legacy:** `parser_type=moex_brent_daily` (Yahoo chart) оставлен в реестре для тестов и неактивного `steel`; новые listed-ряды на Yahoo не заводить.

## FRED graph CSV (`FredCsvParser`, `parser_type=fred_csv`)

Публичный CSV без API-ключа: `fred.stlouisfed.org/graph/fredgraph.csv?id={fred_series_id}`. Заголовок `observation_date` (алиас `DATE`); пропуски — `.` (строки пропускаются). `backfill_from` обрезает более ранние точки после parse. Полная история приходит одним ответом; upsert идемпотентен (ADR-0002). `replace_series=True`. Канал доставки — FRED; публичное поле `source` называет **первоисточник** (ФРС / Минфин США / EIA), не St. Louis Fed.

Правовое основание для рядов ниже: данные ведомств США в public domain (EIA Copyrights and Reuse; Fed/Treasury H.10/H.15). FRED — redistributor. Ряды IMF Primary Commodity Prices на FRED (`PCOPPUSDM` и др.) **не используем** для витрины: copyright IMF, нужна отдельная лицензия на commercial redistribution — вместо них Pink Sheet напрямую от Всемирного банка.

| Индикатор | fred_series_id | Первоисточник (публичное поле) | Заметки |
|-----------|----------------|--------------------------------|---------|
| `usd-index` | `DTWEXBGS` | ФРС, релиз H.10 | Nominal Broad U.S. Dollar Index, база янв. 2006 = 100; с 2006-01-02. |
| `ust-10y` | `DGS10` | Минфин США | Доходность 10-летних Treasury; с 1962-01-02. |
| `brent` | `DCOILBRENTEU` | EIA | Europe Brent Spot Price FOB, USD/bbl; с 1987-05-20. Ранее Yahoo `BZ=F`. |
| `natural-gas` | `DHHNGSP` | EIA | Henry Hub Natural Gas Spot Price, USD/млн БТЕ; с 1997-01-07. Ранее Yahoo `NG=F`. |

Официального свободного дневного ряда цены золота (USD/унция) на FRED/ЕЦБ/LBMA без лицензии нет: `gold-usd` не заведён. Месячный ряд золота есть в Pink Sheet (`Gold`, $/troy oz) — отдельная задача, в оперативный срез главной не ставится.

## MOEX ISS — биржевые индексы daily (MoexIndexParser, `parser_type=moex_index_daily`)

Тикер config-driven через `model_config_json.moex_secid`. Прогноз не строится, категория «Индексы». Endpoint: `iss.moex.com/iss/history/engines/stock/markets/index/securities/<SECID>.json` с пагинацией по `start` (страница 100 строк). **Пагинация по сырому числу строк страницы, не по отфильтрованным точкам** — ранняя история индексов (напр. RGBI) содержит строки с `CLOSE=null`, и остановка по короткому отфильтрованному списку обрезала бы ряд.

| Индикатор | moex_secid | Заметки |
|-----------|-----------|---------|
| `imoex` | `IMOEX` | Индекс МосБиржи. |
| `mcftr` | `MCFTR` | Индекс полной доходности. |
| `rtsi` | `RTSI` | Индекс РТС (в долларах). |
| `rgbi` | `RGBI` | Индекс гособлигаций (ОФЗ), история с 2003. |
| `corp-bond-index` | `RUCBTRNS` | Индекс корпоративных облигаций. |

## ЦБ РФ — HTML-таблицы (CbrKeyRateParser, CbrReservesParser, CbrRuoniaParser)

| Индикатор | URL |
|-----------|-----|
| `key-rate` | `cbr.ru/hd_base/KeyRate/` (UniDbQuery `DD.MM.YYYY`) |
| `international-reserves` | `cbr.ru/hd_base/mrrf/mrrf_7d/` (monthpicker `MM.YYYY`, пол с 29.05.1998; `backfill_from=1998-05-01`) |
| `ruonia` | `cbr.ru/hd_base/ruonia/dynamics/` (UniDbQuery `DD.MM.YYYY`) |

## ЦБ РФ — DataService JSON (CbrDataServiceParser)

Endpoint: `cbr.ru/dataservice/data?publicationId={pub}&datasetId={ds}&measureId={measure}&y1={from}&y2={to}` → фильтр по `element_id`.

| Индикатор | publicationId / datasetId / measureId / element_id | date_offset_months |
|-----------|----------------------------------------------------|--------------------|
| `mortgage-rate` | 14 / 29 / — / 36 | -1 (default) |
| `auto-loan-rate` | 14 / 28 / 2 / 110 | -1 |
| `credit-rate-corp-short` | 14 / 25 / 2 / 7 | -1 |
| `credit-rate-corp-1to3y` | 14 / 25 / 2 / 9 | -1 |
| `credit-rate-corp-over3y` | 14 / 25 / 2 / 10 | -1 |
| `credit-rate-ind-short` | 14 / 27 / 2 / 7 | -1 |
| `credit-rate-ind-1to3y` | 14 / 27 / 2 / 9 | -1 |
| `credit-rate-ind-over3y` | 14 / 27 / 2 / 10 | -1 |
| `deposit-rate` | 18 / 37 / 2 / 7 | -1 |
| `consumer-credit` | 20 / 42 / 22 / 35 | 0 (value_divisor=10⁶ → трлн) |
| `business-credit` | 22 / 50 / 22 / 35 | 0 (value_divisor=10⁶ → трлн) |
| `current-account` | 8 / 9 / — / — | 0 |
| `m0` | 5 / 5 / — / — | 0 |
| `m1` | 5 / 6 / — / 12 | 0 |
| `m2` | 5 / 7 / — / 12 | 0 |

> **Глубина истории (Фаза 3, 2026-06-24).** `current-account` — `backfill_from_year=1998` (API-пол ряда 1998-04, понижено с 2000). Ставки/кредиты/ипотека (`credit-rate-*`, `deposit-rate*`, `auto-loan-rate`, `consumer-credit`, `business-credit`, `mortgage-rate`) — API-floor = текущему `backfill` (2014/2017/2019): это начало датасета CBR по данной методологии, глубже официально нет (пред-2014 ставки — иной ряд, сплайс = методологический разрыв). `m0/m1/m2` денежные агрегаты с 2026-05 живут в `cbr_monetary_agg_xlsx` (отдельный парсер, см. ниже), не в DataService; `m2` понижен до `backfill_from_year=1992` (xlsx содержит M2 с 1992-12).

**Сумма-композит** (CbrDataServiceSumParser, `dataservice_components` массив):

| Индикатор | Components (pub/ds/element_id) |
|-----------|--------------------------------|
| `deposits-business` | sum(5/6/15, 5/7/21, 5/8/25) |
| `deposits-individual` | sum(5/6/16, 5/7/22, 5/8/26) |

## Минфин — федеральный бюджет (MinfinBudgetParser)

Каталог OpenData: `minfin.gov.ru/opendata/7710168360-fedbud_month/` → находит latest CSV → парсит.

**Trap (in-place content update)**: timestamp в имени CSV (`data-YYYYMMDDTHHMM-structure-…csv`) — это дата создания паспорта, а **не** snapshot content. Минфин дополняет тот же URL новыми месяцами в течение дня. Поэтому утренний `daily_update_job` (03:00 MSK) может получить ещё «вчерашнюю» версию того же URL. Контрмеры: `late_minfin_etl_job` (APScheduler 15:00 MSK) перезапускает все `parser_type=minfin_budget_csv` индикаторы; парсер логирует `last_parsed_date` + `last_db_date`. См. `docs/enterprise_resilience.md::Парсеры и источники`.

**Trap (503 + `/ru/` CSV path, 2026-07)**: каталог Минфина периодически отвечает 503; глобальный `http_client` (total=3) исчерпывался → падали сразу три индикатора (`budget-*`), каждый раз заново долбя каталог. Контрмеры в `minfin_budget_parser`: Minfin-specific Retry, process TTL-кэш URL (10 мин, один hit на тройку), last-good URL в state Redis. **CSV всегда без `/ru/`**: `…/opendata/…/data-*.csv` (200); `…/ru/opendata/…/data-*.csv` → 404.

**Trap (прод-IP ban на весь minfin.gov.ru, 2026-07-12)**: с `201.51.11.170` и с OpenRouter-прокси `5.129.210.89` — стабильный 503; с обычных сетей — 200. `http_client.ProxyFallbackSession`: direct → HTTP (`RUSTATS_ETL_HTTP_PROXY_URL` / `OPENROUTER`) → SOCKS (`RUSTATS_ETL_SOCKS_PROXY_URL`). На проде SOCKS = host Tor `socks5h://172.18.0.1:9050` (Tor `SocksPort` на gateway сети `rosstat_default`; из контейнера нужен PySocks). Live-проверка: catalog+CSV через Tor = 200. Packaged snapshot `backend/app/data/minfin/fedbud_month.csv` остаётся последним fallback. **Не ставить Cloudflare WARP на хост** — ломает весь сетевой стек. **Trap (ночные timeout 300с, 2026-07-13)**: urllib3 Retry(connect/read=3) × timeout 45–90с сжигал бюджет `wait_for` до artifact; укорочены Minfin retries (total/connect/read=1, timeout 25–40с), `ETL_TIMEOUT_BY_PARSER[minfin_budget_csv]=600`.

| Индикатор | budget_target |
|-----------|---------------|
| `budget-revenue` | `revenue` |
| `budget-expenditure` | `expenditure` |
| `budget-deficit` | (default = revenue − expenditure) |

---

## Росстат — потребительские цены (RosstatCpiParser)

Шаблон файла из `settings.rosstat_cpi_template`: `ipc_mes_{MM}-{YYYY}.xlsx` (resolve latest через `RosstatFetcher.fetch_latest`).

| Индикатор | Sheet |
|-----------|-------|
| `cpi` | `01` |
| `cpi-food` | `02` |
| `cpi-nonfood` | `03` |
| `cpi-services` | `04` |

## Росстат — недельная инфляция (RosstatWeeklyCpiParser)

Multi-source merge:

1. **Primary HTML-бюллетени** `mediabank/<num>_DD-MM-YYYY.html`. Discovery (union):
   - **central-news crawler**: пагинированный список `rosstat.gov.ru/central-news?page=1..N` с заголовками. Архив 2023-05-04 → today (page=1). page=66+ возвращают пустую ленту.
   - **search API fallback**: `rosstat.gov.ru/search?q=оценке индекса потребительских цен <месяц> <год>` для edge cases когда новый bulletin ещё не на page=1.
2. **XLSX продкорзина** `mediabank/Nedel_ipc.xlsx` + веса из `mediabank/ipc_spr_{MM}-{YYYY}.xlsx` — applied только для дат **≥ `weekly_cutoff_date`** (current 2023-01-09).

| Индикатор | Files |
|-----------|-------|
| `inflation-weekly` | `Nedel_ipc.xlsx` + `ipc_spr_{MM}-{YYYY}.xlsx` + bulletin HTMLs |
| `inflation-weekly-food` | тот же `Nedel_ipc` + `ipc_spr` (сегмент продовольствие, local code 10–4099); ETL пишет primary `inflation-weekly` |
| `inflation-weekly-nonfood` | то же (сегмент непродовольствие, code ≥4100 &lt;9000) |
| `inflation-weekly-services` | то же (сегмент услуги, code ≥9000) |

**Глубина**: 2023-01-09 → present. **Cutoff введён 2026-05-12**: до 2023-01-09 у Росстата нет публично доступных bulletins (rosstat.gov.ru 404 на старые номера, search API возвращает 0 results за 2022, Wayback CDX empty для `mediabank/*-2022.html`). XLSX-approximation за 2022 расходилась с monthly CPI до 3 pp (март 2022) — введение явно. См. `docs/missed_data_audit.md::Nedel_ipc` для развёрнутой research-сводки.

**Deep dive 2026-05-12 — bulletin coverage увеличена до 169/170**:
1. **Открытие**: Росстат начал публиковать **отдельные weekly bulletin'ы** только в **январе 2023 года**. До 2023 — только monthly «Об индексе потребительских цен в <месяц>». Утверждение «бюллетени с 2003 года» — заблуждение. Подтверждено через Wayback Machine CDX `rosstat.gov.ru/storage/mediabank/*.htm` за 2020-2023: 174 candidate URLs, 0 weekly bulletin'ов за 2020-2022, первый weekly bulletin за 2023-01-09.
2. **Bug fix**: `bulletin_years = [today.year]` → `[2023..today.year]`. Раньше 135 точек 2023-2025 в БД были XLSX-агрегатом (расхождение с bulletin до 0.12pp). После backfill — все 153 точки 2023-05+ = bulletin.
3. **Wayback backfill 2023-01..04**: для 16 недель до начала central-news архива (2023-05-04) восстановили bulletin через `web.archive.org/web/<ts>id_/<url>` + `_parse_bulletin_html`. Заменили XLSX → bulletin.
4. **Итог**: 169/170 точек = подлинные значения Росстатовских bulletin'ов. Единственный gap — 2023-05-02 (XLSX-fallback, в Wayback нет snapshot bulletin'а за эту неделю).

## Росстат — производственные цены (RosstatPpiParser)

| Индикатор | File |
|-----------|------|
| `ppi` | `mediabank/osn-{MM}-{YYYY}.pdf` (chain MoM% from socioeconomic report PDF) |

## Росстат — цены на жильё (RosstatHousingParser)

| Индикатор | File |
|-----------|------|
| `housing-price-primary` | `mediabank/osn-{MM}-{YYYY}.pdf` (chain QoQ% primary) |
| `housing-price-secondary` | `mediabank/osn-{MM}-{YYYY}.pdf` (chain QoQ% secondary) |

## Росстат — ВВП (RosstatGdpParser)

Два источника + ratio-splice через `gdp_overlap_year=2011` (см. ADR-0004).

| Индикатор | gdp_source | File | Modern sheet | History sheet | Row |
|-----------|------------|------|--------------|---------------|-----|
| `gdp-nominal` | official_quarterly | `mediabank/VVP_kvartal_s-1995-2026.xlsx` | `2` | `1` | — |
| `gdp-real` | official_quarterly | `mediabank/VVP_kvartal_s-1995-2026.xlsx` | `9` | `3` | — |
| `gdp-consumption` | official_use | `mediabank/GDP-quarters-of-use-1995_1kv-2026.xls` | `2` | `1` | 7 |
| `gdp-government` | official_use | `mediabank/GDP-quarters-of-use-1995_1kv-2026.xls` | `2` | `1` | 8 |
| `gdp-investment` | official_use | `mediabank/GDP-quarters-of-use-1995_1kv-2026.xls` | `2` | `1` | 11 |

История ВВП: 1995-Q1 → present (~125 точек на каждый индикатор после Q1-2026).

**Trap (имя файла, 2026-07):** на `/statistics/accounts` канон — `VVP_kvartal_s-1995-2026.xlsx` (дефис после `s`). Старый URL `VVP_kvartal_s_1995-2026.xlsx` (подчёркивание) всё ещё 200, но без I кв. 2026 — ETL молча `no_new_data`. URL в `ROSSTAT_STATIC_URLS['gdp_quarterly']`. Аналогично use-side: канон `GDP-quarters-of-use-1995_1kv-2026.xls`; старый `…-4kv-2025.xls` остаётся без I кв. 2026.

## Росстат — промышленность (RosstatIpiParser)

Chain MoM% из двух XLSX (база 2018 + база 2023).

Раздел ОКВЭД2 config-driven через `model_config_json.okved_section` (точный код в колонке «Код ОКВЭД2», лист «1»): `BCDE` агрегат (default), `B`/`C`/`D`/`E` — составляющие. Chain/anchor (2023 avg=100) общий. Прогноз — `monthly_auto` (12 мес), generic-семья T3 разворачивает уровень/средние/приросты/Г-г.

| Индикатор | okved_section | Files |
|-----------|---------------|-------|
| `ipi` | `BCDE` | `mediabank/ind_baza_2018_12-2025.xlsx` (history) + `mediabank/ind_baza_2023_{MM}-{YYYY}.xlsx` (current) |
| `ipi-mining` | `B` | те же файлы |
| `ipi-manufacturing` | `C` | те же файлы |
| `ipi-energy` | `D` | те же файлы |
| `ipi-water` | `E` | те же файлы |

## Росстат — еженедельные средние цены на топливо (RosstatWeeklyPriceParser)

Источник: `mediabank/nedel_sred_cen.xlsx` — «Еженедельные средние потребительские цены (на конец периода)», листы по годам (2022→текущий), абсолютная цена в руб./единицу. Целевая строка config-driven через `model_config_json.product_label` (точное совпадение col 0 → подстрока). Частота weekly, категория «Цены», прогноз `generic_ols` (8 недель, transform absolute). Generic-семья T5 (как резервы): уровень на конец периода + средние мес/кв/год + Г/г.

| Индикатор | product_label |
|-----------|---------------|
| `fuel-ai92` | «Бензин автомобильный марки АИ-92, л» |
| `fuel-ai95` | «Бензин автомобильный марки АИ-95, л» |
| `fuel-diesel` | «Дизельное топливо, л» |

> Тот же файл содержит ещё ~110 товаров (продовольствие, лекарства, стройматериалы) — при необходимости любой расширяется одной seed-строкой с нужным `product_label`, без правки парсера.

## Росстат — труд (RosstatLaborParser)

Все 4 индикатора из одного PDF доклада СЭП (`fetch_latest_socioeconomic_report_pdf`).

| Индикатор | File |
|-----------|------|
| `employment` | `mediabank/osn-{MM}-{YYYY}.pdf` |
| `labor-force` | `mediabank/osn-{MM}-{YYYY}.pdf` |
| `unemployment` | `mediabank/osn-{MM}-{YYYY}.pdf` |
| `wages-nominal` | `mediabank/osn-{MM}-{YYYY}.pdf` |

## Росстат — мес. промышленные показатели (RosstatIndParser)

Шаблон файла: `mediabank/ind_{MM}-{YYYY}.xlsx`.

| Индикатор | Sheet |
|-----------|-------|
| `capital-investment` | `1.6 ` — `quarterly_flow`: лист до ~2016 с помесячными потоками, с 2016 только кварталы; парсер сворачивает в квартальные суммы и `prune` старых месячных дат |
| `construction-work` | `1.7 ` |
| `housing-commissioned` | `1.8 ` |
| `retail-trade` | `1.12 ` |

## Росстат — основные фонды (RosstatFixedAssetsParser)

| Индикатор | File template |
|-----------|---------------|
| `depreciation-rate` | discovery: `folder/11186` → `St_izn_of_{YYYY}.xlsx` (fallback year-probe) |

## Росстат — демография (RosstatDemoParser)

Каталог раздела: `https://rosstat.gov.ru/folder/12781`. Имена файлов резолвятся
со страницы (regex), затем fallback year-probe — Росстат периодически меняет
точное имя (`demo21_2023.xlsx` и т.п.).

| Индикатор | demo_file | File |
|-----------|-----------|------|
| `births` | `demo21` | `mediabank/demo21_{YYYY}.xlsx` + при лаге годовой таблицы — полный год из `Edn_12-{YYYY}_t1.xlsx` (оперативные итоги ЕДН) |
| `deaths` | `demo21` | то же |
| `birth-rate` | `demo21` | то же |
| `death-rate` | `demo21` | то же |
| `working-age-population` | `demo14` | `mediabank/demo14.xlsx` |
| `pop-under-working-age` | `demo14` | `mediabank/demo14.xlsx` |
| `pop-over-working-age` | `demo14` | `mediabank/demo14.xlsx` |
| `pensioners` | `pensioners` | `mediabank/Sp_2.1_{YYYY}.xlsx` |

> **demo21:** в файле три блока (всё / город / село) с повторяющимися годами —
> парсер берёт первое вхождение каждого года (= «Все население»). Годовая
> таблица на август 2026 опубликована как `demo21_2023.xlsx` (ряд до 2023);
> календарный 2024 подтягивается из оперативного ЕДН за декабрь, пока Росстат
> не выложит `demo21_2024.xlsx`. Возрастные группы `demo14` — последний год
> источника 2023 (естественный лаг публикации).

## Росстат — население (RosstatPopulationParser)

Multi-source merge: история (1897+) + components (1990+) + latest актуальный год.

| Индикатор | Files |
|-----------|-------|
| `population` | `mediabank/Popul_1897+.xlsx` + `mediabank/Popul components_1990+.xlsx` + `mediabank/OkPopul_Comp{YYYY}_Site.xlsx` |
| `population-total-growth` | `mediabank/Popul components_1990+.xlsx` (обновлено 25.04.2025, последний год ряда — 2024) |
| `population-natural-growth` | `mediabank/Popul components_1990+.xlsx` |
| `population-migration` | `mediabank/Popul components_1990+.xlsx` |

## Росстат — наука и инновации (RosstatScienceParser)

Каталоги: `https://rosstat.gov.ru/statistics/science`, кадры ВО —
`https://rosstat.gov.ru/statistics/education`. Discovery по regex со страницы
раздела (устойчиво к `Kadry_VO`↔`Kadry-VO`, `innov-mp_1`↔`Innov_mp_1`).

| Индикатор | File | Sheet/Row |
|-----------|------|-----------|
| `grad-students` | `mediabank/Kadry-VO.xls` (fallback `Kadry_VO.xls`) | sheet 1 |
| `doctoral-students` | то же | sheet 4 |
| `rd-organizations` | `mediabank/Nauka_1.xls` | sheet 1, "всего" row |
| `rd-personnel` | `mediabank/nauka_2.xls` | sheet 1, "всего" row |
| `innovation-activity` | `mediabank/innov_1_{YYYY}.xls` | sheet 1, RF row; `min_year=2018` |
| `tech-innovation-share` | `mediabank/innov_2_{YYYY}.xls` | sheet 1, RF row; `min_year=2018` |
| `small-business-innovation` | `mediabank/Innov_mp_1.xls` (fallback `innov-mp_1.xls`) | sheet 5, RF row |

> **Методологический разрыв (Осло 3→4, приказ Росстата № 788).** С перерасчёта
> за 2017 показатели инноваций считаются по 4-й редакции Руководства Осло и
> несопоставимы со старым рядом (`tech-innovation-share` ≤2017 ~7-9% → ≥2018
> ~20-24%; `innovation-activity` аналогично, мягче). У нас значения за ≤2017
> остались по старой методике → ложный вертикальный «обрыв» на графике. Лечится
> `min_year=2018` в `SCIENCE_CONFIG` (`rosstat_science_parser.py`): парсер
> отдаёт только новый ряд. Существующие старые точки на проде вычищены разово
> (DELETE date < 2018). `small-business-innovation` уже идёт с 2019 — не затронут.

---

## Мировой блок — Eurostat и официальный multi-provider contract

Мировой bounded context не входит в счётчик 109 российских source-индикаторов.
Первый действующий provider — официальный Eurostat; подключение национальных
ведомств выполняется отдельными adapters по ADR-0012.

| Provider | Официальный источник | Каталог/версии | Наблюдения |
|----------|----------------------|----------------|------------|
| `eurostat` | Eurostat, Statistical Office of the European Union | `https://ec.europa.eu/eurostat/api/dissemination/catalogue/toc/txt?lang=en` (`last update of data`, `last table structure change`) | Eurostat Dissemination API; ссылка конкретного dataset хранится в `WorldIndicator.source_url` |

Техническая identity ряда:
`provider × country × dataset_id × slice_hash`; slice включает все значимые
dimensions, единицу и частоту. `world_dataset_state` хранит версии источника по
паре `provider × dataset_id`. Parser internals Eurostat — docstrings
`app/services/eurostat_parser.py`, обновление — `world_eurostat_ingest.py`.

**Площадь территории (карточка страны):** курируемый справочник
`backend/app/data/world_country_area.py` — не ETL и не таблица БД. Для стран
ЕС/ЕАСТ/кандидатов с покрытием Eurostat — dataset `reg_area3`, мера Total area
(`landuse=TOTAL`, км²), ссылка на databrowser. Для остальных — национальное
статистическое ведомство или картография/кадастр (SORS, BHAS, BNS Moldova,
Geostat, US Census Bureau, NRCan Atlas, GSI/Statistics Bureau Japan, NBS China,
India.gov/Survey of India, IBGE, INEGI «Mexico at a glance» (замер территории
1998, публикация 2014), Geoscience Australia). Публичная подпись `source` —
по-русски, латиница допускается только аббревиатурой ведомства; guard —
`test_world_country_area_sources_are_public_ready`. Китай — единственное
округление: ведомство публикует «около 9,6 млн км²». Население на карточке —
последнее значение курируемого concept `population` из `world_data_points`
(источник и URL берутся с `WorldIndicator`).

**Инвариант источника:** национальная статистика берётся прежде всего из
официального национального ведомства, центрального банка, таможни или
министерства. OECD/World Bank разрешены только как канонический международный
издатель конкретного ряда или контрольная сверка; коммерческий/новостной
агрегатор не может быть source. Проверенные, но ещё не подключённые источники из
исследовательских Excel не считаются production provider до реализации adapter,
golden-series теста и фиксации здесь.

---

## Региональный блок — сборник «Регионы России» (ADR-0008, вне ETL)

Отдельный bounded context (`regions`/`region_indicators`/`region_data`), данные заливаются из закоммиченного артефакта `backend/app/data/regional/`, а не парсером по расписанию. Полная механика — [`docs/adr/0008`](adr/0008-regional-bounded-context.md) + docstrings скриптов `scripts/regional/*.py`.

| Стадия | Источник (rosstat.gov.ru) | Что берёт |
|--------|---------------------------|-----------|
| `parse_pril_2025.py` | `folder/210/document/47652` → архив `Pril_Region_Pokaz_2025.rar` (20 файлов `Раздел N - *.xlsx`, ~460 листов) | 461 показатель, 2000–2024 |
| `backfill_pril_2022_2023.py` | те же приложения изданий 2023/2022 (`Pril_2023`, `Pril_2022`) | 25 показателей, исключённых из 2025: внешняя торговля ФТС (21.x), госслужащие (2.15–2.18), ПИИ (10.4), лён (13.8/13.17/13.18), ж/д грузы (16.1), прожиточный минимум пенсионера (3.14), зарплата муниципальных служащих (3.5), интернет/ПК в организациях (17.2/17.6), темпы прироста населения (1.8) |
| `backfill_word.py` | Word-редакции: `TOM2.rar` (изд. 2003), `soc-pok18.rar` (изд. 2018), `soc-pok2019` (изд. 2019); .doc → .docx через LibreOffice headless | раздел «Правонарушения» (8.1/8.4/8.5, 1990–2018) + продление 24 рядов в 1990-е с кросс-сверкой на overlap (медиана расхождения ≤ 5%) |

Ежегодное обновление: скачать новый архив приложения, прогнать три стадии по порядку, закоммитить артефакт, `seed_regional.py` подхватит на деплое. Денежные ряды глубже 1998 не продлеваются (деноминация).

---

## Соглашения о публикационных задержках

| Источник | Публикационная конвенция |
|----------|--------------------------|
| ЦБ DataService (`int_rat`, `mortgage`, `auto`) | publication date = M+1, фактическая дата данных = publication − 1 месяц (`date_offset_months=-1`) |
| ЦБ DataService (`m0/m1/m2`, deposits, credits) | дата = реальный месяц данных (`date_offset_months=0`) |
| Росстат `osn-MM-YYYY.pdf` (СЭП) | публикуется в месяце MM, содержит данные за **предыдущий** месяц (T+1 lag); reference month = `MM − 1` |
| Росстат `ipc_mes_MM-YYYY.xlsx` (CPI) | публикуется ~5 числа MM, данные за месяц `MM − 1` |
| Росстат `Nedel_ipc.xlsx` | актуализируется ежесреду; HTML-бюллетени публикуются в среду за прошедшую неделю |
| Минфин CSV | публикуется ~25 числа MM, данные за месяц `MM − 1` |

---

## Версионирование и архивы

- **Asset-hash trap**: при правке этого файла **не нужно** пересобирать backend/frontend — это документация, не код.
- **Schema drift**: если Росстат меняет имя файла (например, `ind_baza_2023_*.xlsx` → `ind_baza_2028_*.xlsx`) — парсер падает с понятной ошибкой, **обновить и здесь, и в `rosstat_sdds_fetcher.py`** одновременно.
- **SDDS deprecated** (ADR-0004): любые упоминания `*_GR.xlsx`, `Population_RUS.xlsx`, `Indprod_RUS.xlsx`, `Labor_RUS.xlsx`, `PPI_RUS.xlsx`, `HousePrices_RUS.xlsx` — это историческая SDDS-схема. **Не использовать**, удалена 2026-05-10.

---

## Когда обновлять этот файл

**Обязательно обновить**, если:

- Меняется URL/имя файла источника (Росстат сменил slug, ЦБ перенёс endpoint).
- Добавляется новый source-индикатор (новая строка в соответствующей таблице).
- Удаляется/депрекается индикатор (вычеркнуть из таблицы).
- Меняется `dataservice` блок (`publicationId`, `datasetId`, `element_id`, `measureId`).
- Меняется `gdp_sheet`/`gdp_history_sheet`/`ind_sheet`/`demo_file` в `model_config_json`.
- Меняется publication convention (lag, offset).

**После обновления:**
1. `Last updated` сверху → актуальная дата.
2. Синхронно обновить docstring соответствующего парсера в `backend/app/services/*_parser.py` (parser internals: source URL, лист, row/col, model_config schema, traps).
3. Если правка архитектурная (новый паттерн merge/chain) — добавить в ADR-0004 «Subsequent additions» или создать новый ADR.
