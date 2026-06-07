# Data sources — точная карта индикатор → файл/endpoint

**Last updated:** 2026-05-31 (T13: данный файл стал основным местом хранения технических деталей источников — имена файлов, листы, строки/колонки, API-id; публичные `methodology` полей индикаторов в `seed_data.py` теперь не выдают этих внутренностей, см. правило [`.cursor/rules/methodology-language.mdc`](../.cursor/rules/methodology-language.mdc)).
**Part of:** [`AGENTS.md`](../AGENTS.md), [`CONTEXT.md`](../CONTEXT.md).
**Related:** docstrings парсеров `backend/app/services/{cbr_*,minfin_*,rosstat_*}_parser.py` (per-parser internals: traps, схема `model_config_json`, особенности формата), [`docs/adr/0004`](adr/0004-rosstat-russian-canonical-sdds-deprecated.md) (Rosstat русский canonical).

> **Single source of truth** для актуальных URL/файлов, откуда тянется каждый из 75 source-индикаторов. Если меняется источник в коде парсера или `seed_data.py` — **обязательно** актуализировать этот файл (см. [`AGENTS.md::Шаг 4`](../AGENTS.md#шаг-4--протокол-актуализации-документации-критично)).
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

| Индикатор | VAL_NM_RQ |
|-----------|-----------|
| `usd-rub` | `R01235` |
| `eur-rub` | `R01239` |
| `cny-rub` | `R01375` |

## ЦБ РФ — драгметаллы (CbrGoldParser)

| Индикатор | Endpoint |
|-----------|----------|
| `gold-price` | `cbr.ru/scripts/xml_metall.asp?date_req1={from}&date_req2={to}` |

## Binance — BTC/USD daily (BinanceBtcUsdtParser)

| Индикатор | Endpoint |
|-----------|----------|
| `btc-usd` | `api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1d` — поле `close`, дата = календарный торговый день (UTC). Backfill ~1500 дней. Live-тикер — отдельно `ticker_sources/binance.py`. |

## Brent — daily (BrentDailyFredParser, `parser_type=moex_brent_daily`)

| Индикатор | Endpoint |
|-----------|----------|
| `brent` | `query1.finance.yahoo.com/v8/finance/chart/BZ=F?interval=1d` — поле `close`, дневные бары. Backfill с 2020. Live-тикер — MOEX FORTS `BR-*` через `ticker_sources/moex_iss.py`. |

## ЦБ РФ — HTML-таблицы (CbrKeyRateParser, CbrReservesParser, CbrRuoniaParser)

| Индикатор | URL |
|-----------|-----|
| `key-rate` | `cbr.ru/hd_base/KeyRate/` |
| `international-reserves` | `cbr.ru/hd_base/mrrf/mrrf_7d/` |
| `ruonia` | `cbr.ru/hd_base/ruonia/dynamics/` |

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

**Сумма-композит** (CbrDataServiceSumParser, `dataservice_components` массив):

| Индикатор | Components (pub/ds/element_id) |
|-----------|--------------------------------|
| `deposits-business` | sum(5/6/15, 5/7/21, 5/8/25) |
| `deposits-individual` | sum(5/6/16, 5/7/22, 5/8/26) |

## Минфин — федеральный бюджет (MinfinBudgetParser)

Каталог OpenData: `minfin.gov.ru/opendata/7710168360-fedbud_month/` → находит latest CSV → парсит.

**Trap (in-place content update)**: timestamp в имени CSV (`data-YYYYMMDDTHHMM-structure-…csv`) — это дата создания паспорта, а **не** snapshot content. Минфин дополняет тот же URL новыми месяцами в течение дня. Поэтому утренний `daily_update_job` (03:00 MSK) может получить ещё «вчерашнюю» версию того же URL. Контрмеры: `late_minfin_etl_job` (APScheduler 15:00 MSK) перезапускает все `parser_type=minfin_budget_csv` индикаторы; парсер логирует `last_parsed_date` + `last_db_date`. См. `docs/enterprise_resilience.md::Парсеры и источники`.

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
| `gdp-nominal` | official_quarterly | `mediabank/VVP_kvartal_s_1995-2026.xlsx` | `2` | `1` | — |
| `gdp-real` | official_quarterly | `mediabank/VVP_kvartal_s_1995-2026.xlsx` | `9` | `3` | — |
| `gdp-consumption` | official_use | `mediabank/GDP-quarters-of-use-1995-4kv-2025.xls` | `2` | `1` | 7 |
| `gdp-government` | official_use | `mediabank/GDP-quarters-of-use-1995-4kv-2025.xls` | `2` | `1` | 8 |
| `gdp-investment` | official_use | `mediabank/GDP-quarters-of-use-1995-4kv-2025.xls` | `2` | `1` | 11 |

История ВВП: 1995-Q1 → present (~124 точки на каждый индикатор).

## Росстат — промышленность (RosstatIpiParser)

Chain MoM% из двух XLSX (база 2018 + база 2023).

| Индикатор | Files |
|-----------|-------|
| `ipi` | `mediabank/ind_baza_2018_12-2025.xlsx` (history) + `mediabank/ind_baza_2023_{MM}-{YYYY}.xlsx` (current) |

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
| `capital-investment` | `1.6 ` |
| `construction-work` | `1.7 ` |
| `housing-commissioned` | `1.8 ` |
| `retail-trade` | `1.12 ` |

## Росстат — основные фонды (RosstatFixedAssetsParser)

| Индикатор | File template |
|-----------|---------------|
| `depreciation-rate` | `mediabank/St_izn_of_{YYYY}.xlsx` (probe last N years for latest) |

## Росстат — демография (RosstatDemoParser)

| Индикатор | demo_file | File |
|-----------|-----------|------|
| `births` | `demo21` | `mediabank/demo21_{YYYY}.xlsx` |
| `deaths` | `demo21` | `mediabank/demo21_{YYYY}.xlsx` |
| `birth-rate` | `demo21` | `mediabank/demo21_{YYYY}.xlsx` |
| `death-rate` | `demo21` | `mediabank/demo21_{YYYY}.xlsx` |
| `working-age-population` | `demo14` | `mediabank/demo14.xlsx` |
| `pop-under-working-age` | `demo14` | `mediabank/demo14.xlsx` |
| `pop-over-working-age` | `demo14` | `mediabank/demo14.xlsx` |
| `pensioners` | `pensioners` | `mediabank/Sp_2.1_{YYYY}.xlsx` |

## Росстат — население (RosstatPopulationParser)

Multi-source merge: история (1897+) + components (1990+) + latest актуальный год.

| Индикатор | Files |
|-----------|-------|
| `population` | `mediabank/Popul_1897+.xlsx` + `mediabank/Popul components_1990+.xlsx` + `mediabank/OkPopul_Comp{YYYY}_Site.xlsx` |
| `population-total-growth` | `mediabank/Popul components_1990+.xlsx` |
| `population-natural-growth` | `mediabank/Popul components_1990+.xlsx` |
| `population-migration` | `mediabank/Popul components_1990+.xlsx` |

## Росстат — наука и инновации (RosstatScienceParser)

| Индикатор | File | Sheet/Row |
|-----------|------|-----------|
| `grad-students` | `mediabank/Kadry_VO.xls` | sheet 1 |
| `doctoral-students` | `mediabank/Kadry_VO.xls` | sheet 4 |
| `rd-organizations` | `mediabank/Nauka_1.xls` | sheet 1, "всего" row |
| `rd-personnel` | `mediabank/nauka_2.xls` | sheet 1, "всего" row |
| `innovation-activity` | `mediabank/innov_1_{YYYY}.xls` | sheet 1, RF row |
| `tech-innovation-share` | `mediabank/innov_2_{YYYY}.xls` | sheet 1, RF row |
| `small-business-innovation` | `mediabank/innov-mp_1.xls` | sheet 5, RF row |

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
