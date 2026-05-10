# ADR 0004 — Rosstat русский основной источник, SDDS English deprecated

- **Date:** 2026-05-10
- **Status:** Accepted + complete (pilot, rollout, cleanup, GDP history extension до 1995 — все done)
- **Last verified:** 2026-05-10 (GDP history extension через ratio-splice: 5/5 GDP индикаторов 60 → 124 точки, 1995-Q1 → 2025-Q4. Pipeline test gdp-nominal Q4 2025 = 62354.1 ✓ matchит rosstat publication; housing Q1 2026 primary 346.82 / secondary 228.44 ✓).
- **Author:** аудит категорий «Цены» и «ВВП» 2026-05-08/2026-05-10 + конкретный жалобный случай руководителя на расхождение GDP Q4 2025 (60516.7 в нашей DB vs 62354.1 в rosstat publication).
- **Part of:** [`../../CONTEXT.md`](../../CONTEXT.md) (раздел `Source` + trap «SDDS English vs Rosstat русский»).
- **Related:** [ADR-0002](0002-derived-always-reflects-source.md) (идемпотентный bulk_upsert делает миграцию обратимой), [ADR-0001](0001-derived-indicators-engine-shape.md) (derived подхватятся через `scripts/rebuild-all-derived.py`).
- **Code anchors:** `backend/app/services/rosstat_sdds_fetcher.py::DATASET_URLS` (deprecated), `ROSSTAT_STATIC_URLS` (новый canonical), `backend/app/services/rosstat_gdp_parser.py::parse_rosstat_gdp_quarter_grid_xlsx`, `backend/seed_data.py` (`gdp-nominal` config).

## Context

Часть rosstat-индикаторов исторически парсилась из **SDDS-English** XLSX-зеркала на `eng.rosstat.gov.ru` (`SDDS_*.xlsx`). SDDS — это IMF-стандарт, формат «base year = 100 chained cumulative index», публикуется с лагом ~год относительно русской публикации (комментарий в `rosstat_sdds_fetcher.py:6-9`: «Год в URL обычно = текущий-1»).

Аудит 2026-05-08 (категория «Цены») и 2026-05-10 (категория «ВВП») зафиксировал три класса проблем у SDDS-индикаторов:

1. **Format mismatch с публикацией Росстата.** Rosstat русский публикует MoM/QoQ % индексы (100 = пред. период) или абсолютные значения текущих цен. SDDS пересчитывает в 2010=100 chained cumulative index. Когда руководитель открывает rosstat и сравнивает с нашим API — видит **разные числа**. Конкретный case: `gdp-nominal` Q4 2025 — 60516.7 (наш DB из SDDS) vs **62354.1** (rosstat sheet 2 of `VVP_kvartal_s_1995-2025.xlsx`). Разница **-3.0%** — стабильная, не revision noise. Аналогично diff на Q1-Q3 2025 в диапазоне 0.17%-2.47%.

2. **Короткая история.** SDDS даёт PPI с 2011, Housing с 2016, GDP с 2011 — потому что 2010=100 base. Русский Росстат публикует:
   - `cpi`: monthly с 1991-01 (в SDDS не тянем, в нашем `rosstat_cpi_xlsx` уже правильно).
   - `gdp-nominal`: quarterly с **1995** (`VVP_kvartal_s_1995-2025.xlsx`).
   - `ppi`: MoM monthly с **1998** (`Proizvoditeli_Ind_VED_*.xlsx`).
   - housing: annual с **1998** (`dinamika_1998-2025.xlsx`), quarterly с 2016+.
   - consumption / government / investment: с **1995** (`GDP-quarters-of-use-1995-4kv-2025.xls`).

3. **Stale latest.** SDDS публикует с лагом → последние 1-2 квартала могут быть приближённые/missing когда у Росстата уже опубликовано final.

Аудит CPI отдельно подтвердил: `rosstat_cpi_xlsx` (тянет `ipc_mes_*.xlsx` с rosstat русского) — 4/4 индикаторов категории Цены 100% совпадают с rosstat по последним 5 точкам. **Pattern «русский canonical» работает уже сегодня** для CPI.

## Decision

**Russian rosstat publication is canonical** для всех индикаторов с `source = "Росстат"`. SDDS-English **deprecated** — используется только как fallback, если русский эквивалент недоступен (на момент 2026-05-10 такого случая в категориях Цены и ВВП не найдено).

Конкретно:

1. **Источник** — для каждого rosstat-индикатора в `seed_data.model_config_json` зафиксирован canonical файл из раздела `rosstat.gov.ru/statistics/<section>/`. Парсер тянет именно его через `fetch_rosstat_static_xlsx(key)` (см. `rosstat_sdds_fetcher.py::ROSSTAT_STATIC_URLS`).
2. **Формат** — какой публикует Росстат, такой и в DB. Для абсолютных значений (ВВП в текущих ценах, расходы домохозяйств) — те же млрд руб. Для индексов (CPI, PPI) — MoM monthly index (100 = пред. месяц), не cumulative chain.
3. **История** — расширяется до самой ранней публикации Росстата (1995 для GDP, 1998 для PPI/housing). Sheet-сшивка между методологическими break-ями (ОКВЭД2007 → ОКВЭД2 в 2011 для GDP) — отдельная задача per-indicator, не в рамках этого ADR.
4. **`fetch_sdds_xlsx`** — функция остаётся в коде как escape hatch на случай если для какого-то нового индикатора у Росстата нет русского эквивалента в основной публикации. Не используется для тех индикаторов, для которых найден русский canonical.

## Migration pattern (single-indicator pilot)

Pilot выполнен для `gdp-nominal` 2026-05-10:

1. **Findings phase** (read-only, ~2 часа):
   - `curl --cacert backend/certs/russiantrustedca2024.pem https://rosstat.gov.ru/statistics/accounts -o page.html && grep -oE 'href="[^"]*\.xlsx?"' page.html` → 50 XLSX в разделе.
   - Скачать кандидат → инспектировать sheets/rows через openpyxl → найти точное соответствие нашему индикатору.
   - Three-way diff: rosstat live vs наш парсер (код) vs наша DB (API).

2. **Code change** (минимальный):
   - Если структура файла совместима с существующим парсером → только seed config:
     ```python
     "model_config_json": {
         "gdp_source": "official_quarterly",
         "gdp_sheet": "2",
         ...
     }
     ```
   - Иначе — расширить парсер новой ветки (например, для `GDP-quarters-of-use-*.xls` потребовалась бы ветка `gdp_source: "official_use"` + новый row_index_map).
   - Add unit test (`backend/tests/test_rosstat_*.py`) на новый sheet/format.

3. **Local validation**:
   - `docker cp backend/seed_data.py rosstat-backend-1:/app/seed_data.py`
   - `docker exec rosstat-backend-1 python seed_data.py` — idempotent re-seed обновит `indicators.model_config_json`.
   - `docker cp backend/app/services/rosstat_gdp_parser.py rosstat-backend-1:/app/...` (если код менялся).
   - `docker exec rosstat-backend-1 python -c "import asyncio; from app.tasks.scheduler import run_etl_for_indicator; asyncio.run(run_etl_for_indicator('<code>'))"` — single-indicator ETL.
   - Verify: `curl http://127.0.0.1:8000/api/v1/indicators/<code>/data?limit=5` → числа matchят rosstat.
   - `docker exec rosstat-backend-1 python /tmp/rebuild-all-derived.py` (см. ADR-0002 «pure-revision day» — `records_added=0` блокирует автоматический derived-каскад).
   - Verify derived: `curl .../indicators/gdp-yoy/data?limit=3`.

4. **Deploy to prod** — отдельным регламентом (см. `docs/workflow.md::Прод-деплой`). Никаких schema-changes, только `seed_data.py` (config update) + опционально `parser.py` extension. Бэкап через `scripts/pg-backup.sh` обязателен.

## Consequences

**Positive**:

- Trust restored: цифры в нашем API будут matchить rosstat XLSX bit-for-bit (last 5 точек, smoke test).
- История расширяется до самой ранней публикации Росстата (для GDP с 2011 → потенциально с 1995, требует sheet 1+2 chain).
- Убран SDDS-lag — последний квартал в нашей DB равен последнему опубликованному в rosstat.
- UI provenance footer становится правдивым (источник = rosstat.gov.ru/statistics/...).

**Negative / Risks**:

- **Format change для frontend**. Если унит в DB меняется (например, PPI 2010=100 → MoM monthly index), value formatter и chart unit на frontend нужно обновлять синхронно с парсером. Для `gdp-nominal` (млрд руб → млрд руб) этого риска нет, для PPI/Housing — будет, при их миграции.
- **Forecast model retrain.** Существующие модели обучены на старом формате. После миграции — обязательный retrain `retrain_indicator_forecast(<code>)` + cascade derived; `redis-cli FLUSHDB`. Для `gdp-nominal` — не критично (использует `approved_forecast_values` от Никиты, не auto-train; cascade derived retrain'нулся успешно в pilot).
- **Methodology break.** Sheet 1 (ОКВЭД2007, 1995-2010) и Sheet 2 (ОКВЭД2, 2011+) `VVP_kvartal_s_1995-2025.xlsx` — разные методологии, прямой concatenation создаст jump на 2011-Q1. Для индикаторов, где нужна история глубже SDDS-окна, требуется per-period chain operation. В этом ADR не делается — отдельный track.

**Reversible**: при ошибке миграции `git revert` + ETL прогон возвращает старые SDDS значения через идемпотентный `bulk_upsert` (ADR-0002). Откат за 5-10 минут.

## Subsequent additions (after acceptance)

### 2026-05-10 — Rollout to gdp-consumption / gdp-government / gdp-investment

Расширение pilot на оставшиеся 3 SDDS-индикатора категории «ВВП и рост»:

- **Новый источник** добавлен в `ROSSTAT_STATIC_URLS["gdp_use_quarterly"] = "GDP-quarters-of-use-1995-4kv-2025.xls"`. Это **legacy .xls** (OLE2 binary), не xlsx — для парсинга расширен `fetch_rosstat_static_xlsx` (теперь принимает оба magic byte: `PK\x03\x04` и `\xd0\xcf\x11\xe0`) и добавлен новый парсер `parse_rosstat_gdp_use_xls` (xlrd-based, multi-row layout).
- **Новая ветка парсера**: `cfg["gdp_source"] == "official_use"` в `RosstatGdpParser._fetch_and_parse`.
- **Seed config update** для трёх индикаторов (`gdp-consumption`, `gdp-government`, `gdp-investment`):
  ```python
  "gdp_source": "official_use",
  "gdp_sheet": "2",  # ОКВЭД2 2011+
  "gdp_row_index": 7  # 7=consumption(HH), 8=government, 11=GFCF
  ```
- **Tests** добавлены: `TestParseRosstatGdpUseXls` (4 теста: consumption/government/investment/sorting) — synthetic .xls fixture через `xlwt`. `xlwt==1.3.0` добавлен в `requirements.txt`.
- **Pipeline test** на локальном docker stack: 3/3 индикатора → `Upserted 0 new, 0 updated` для каждого. Это **best-case migration**: SDDS на момент миграции уже подтянул rosstat значения, так что bit-by-bit совпадение между rosstat XLS и текущей DB. Никаких изменений данных не произошло, derived recompute не нужен. Migration — **проактивная защита** от будущих SDDS-лагов и переключение на canonical source без disruption.
- **Status**: Accepted. Категория «ВВП» полностью мигрирована — все 4 source-индикатора (`gdp-nominal` через `gdp_quarterly`, `gdp-real` через `gdp_quarterly` sheet 9, `gdp-consumption`/`gdp-government`/`gdp-investment` через `gdp_use_quarterly`) теперь читают из rosstat русского. SDDS branch (`fetch_sdds_xlsx("gdp")`) больше не используется ни одним active индикатором — остаётся в коде как escape hatch.

### 2026-05-10 — Rollout to Population (4 indicators)

`population` / `population-rural` / `population-urban` / `birth-rate-total` мигрированы на canonical Rosstat XLSX:
- `Popul_1897+.xlsx` — annual history с 1897.
- `Popul components_1990+.xlsx` — годовые компоненты (sex/urban/rural) с 1990.
- `OkPopul_Comp{YYYY}_Site.xlsx` — последняя текущая публикация (динамическое year fallback на YYYY-1).

Парсер `rosstat_population_parser.py` рефакторнут: `parse_sdds_population_xlsx` удалён, `merge_population_sources(*sources)` сшивает три ряда с `later precedence`. **Trap**: Rosstat файлы содержат смешанные кириллические/латинские символы в «Российская Федеpация» (Latin `p`!) — `parse_ok_popul_xlsx` использует `cell.startswith("российская")` для robust match. Regression test добавлен. Commit `cf08878`.

### 2026-05-10 — Rollout to IPI (industrial production index)

`ipi` мигрирован на 2 canonical XLSX от Rosstat (`rosstat.gov.ru/enterprise_industrial`):
- `ind_baza_2018_12-2025.xlsx` — historical 2018-base MoM%.
- `ind_baza_2023_{MM}-{YYYY}.xlsx` — current 2023-base MoM% (динамический fetcher tries last 6 месяцев).

**Path P (compat) применён**: парсер извлекает MoM% из обоих файлов, merge'ит через `merge_mom_dicts` (current overrides historical при overlap), затем `chain_mom_to_index_2023_base` строит cumulative index с нормализацией так что 2023 annual mean = 100.0 (matchит существующий формат БД 2023=100). Bit-for-bit совпадение с DB после migration → zero-disruption. Commit `13a0251`.

### 2026-05-10 — Rollout to Labor (4 indicators)

`unemployment` / `wages-nominal` / `labor-force` / `employment` мигрированы на **socioeconomic PDF report** (`osn-{MM}-{YYYY}.pdf` с `rosstat.gov.ru/folder/210`). Comprehensive monthly XLSX по labor отсутствует на rosstat сайте → PDF (раньше supplementary) промотан до primary source.

`rosstat_labor_parser.py` рефакторнут полностью: `parse_report_month_from_url` извлекает T-1 reference month из URL (publication lag, year wrap handled), `_parse_labor_force_table` тянет labor force / employment / unemployment rate из таблицы, `_parse_wages_summary` извлекает nominal wage из summary (один datapoint per PDF run). Один новый datapoint per ETL run на индикатор. Manual cleanup для `wages-nominal` (один stale point) выполнен. Commit `5317421`.

### 2026-05-10 — Rollout to PPI (producer price index)

`ppi` мигрирован на тот же socioeconomic PDF report. Dedicated PPI XLSX на rosstat сайте не нашёлся → **path P** через PDF: `parse_ppi_mom_from_report` извлекает MoM% из строки «Индекс цен производителей промышленных товаров», парсер queryит DB на last cumulative value, chains через `last × MoM/100` → новый monthly datapoint. Гладкая миграция: один новый datapoint per ETL run, исторический ряд остаётся от прошлой SDDS-стадии, divergence от старых SDDS значений ожидаема. Commit `0dc61b8`.

### 2026-05-10 — Rollout to Housing (2 indicators)

`housing-price-primary` / `housing-price-secondary` мигрированы на **тот же socioeconomic PDF report** (раздел 4.2 «РЫНОК ЖИЛЬЯ»). Quarterly XLSX отдельно не найден на сайте → path P через PDF.

`rosstat_housing_parser.py` рефакторнут полностью: `parse_housing_qoq_pair` извлекает пару (primary, secondary) QoQ% из summary-строки «составили соответственно P% и S%»; `parse_housing_reference_quarter` парсит reference quarter из табличного заголовка «I квартал YYYY г. в % к IV кварталу YYYY-1 г.». Section-anchor `4.2. РЫНОК ЖИЛЬЯ` (case-sensitive uppercase) отсекает TOC-ложные совпадения. `_normalize_year_text` склеивает разорванный PDF-extract год («202 6» → «2026»). Парсер queryит DB на last cumulative value по индикатору, умножает на QoQ/100 → один новый quarterly datapoint per ETL run на каждый индикатор. Pipeline test (Q1 2026): primary 333.80 × 103.9% = **346.82**, secondary 224.40 × 101.8% = **228.44**. Match с rosstat publication ✓. 10 unit-тестов. Commit pending.

### 2026-05-10 — GDP history extension до 1995 (ratio-splice)

Все 5 GDP source-индикаторов (`gdp-nominal`, `gdp-real`, `gdp-consumption`, `gdp-government`, `gdp-investment`) продлены с 60 точек (2011-Q1 → 2025-Q4) до **124 точек** (1995-Q1 → 2025-Q4). Закрыта прямая жалоба руководителя 08.05.2026 «у Росстата с 1995, у нас почему-то с 2011».

**Стратегия — ratio-splice через overlap-год 2011** (стандартная economic-series splice техника, используется ОЭСР/МВФ при re-basing): pure-функция `splice_at_overlap(history, modern, overlap_year)` калибрует `ratio = mean(modern_2011) / mean(history_2011)`, умножает все historical-точки (year < 2011) на этот ratio. Получаем непрерывный ряд в base modern-методологии (ОКВЭД2 для nominal/use-components, в ценах 2021 для real). Modern-данные на overlap-году имеют приоритет.

Конфиг per индикатор:
```python
"model_config_json": {
    "gdp_source": "official_quarterly",  # или "official_use"
    "gdp_sheet": "2",                    # modern (ОКВЭД2)
    "gdp_history_sheet": "1",            # ОКВЭД2007 (или "3" для real)
    "gdp_overlap_year": 2011,
}
```

**Калибровочные ratios** (наблюдаемые на live данных):
- nominal (sheet1 → sheet2): `1.0741` (~7.4% step) — совпадает с независимым ОКВЭД2007→ОКВЭД2 GDP rebasing
- real в ценах 2008 (sheet3) → real в ценах 2021 (sheet9): `~2.81`
- use-components: примерно те же ~1.07 порядка

**Trap, которая выловилась только на real-данных**: Rosstat Excel хранит часть значений как СТРОКИ с Russian decimal + footnote suffix («1662,82)» = 1662,8 + footnote 2). Чистый `float()` падал → весь 2011-год для `gdp-investment` row 11 sheet 1 был null → `splice_at_overlap` падал на «history не содержит точек за overlap_year=2011». Добавлена pure-функция `_parse_ru_number` (handles `\d\)\s*$` footnote-strip + `,` → `.` + NBSP-strip). 8 unit-тестов на эту функцию + 8 на `splice_at_overlap`.

Pipeline test (live Rosstat XLSX, local docker stack):
- gdp-nominal Q1 1995 = **252.4** (= 234.98 × 1.074, expected 252.3 ✓)
- gdp-nominal Q4 2010 = **14231.0** (= 13249.3 × 1.074, expected 14225 ✓)
- gdp-nominal Q1 2011 = **13024.8** (modern verbatim ✓)
- gdp-nominal Q4 2025 = **62354.1** (modern verbatim, matchит rosstat publication ✓)
- 5/5 индикаторов: 60 → 124 точки. derived gdp-yoy/qoq/annual пересчитаны (288 точечных изменений). `gdp-nominal` / `gdp-real` forecasts retrain'нулись.

Commit pending.

### Open work

- **Cleanup** — был `b7117f7` 2026-05-10. SDDS код удалён, parser_types переименованы.

## Pilot evidence (2026-05-10)

`gdp-nominal` migration end-to-end на локальном docker stack:

| Точка | До (SDDS) | После (rosstat sheet 2) | Rosstat publication |
|---|---|---|---|
| 2025-12-01 | 60516.7 | **62354.1** | 62354.1 ✓ |
| 2025-09-01 | 53713.1 | 54671.8 | 54671.8 ✓ |
| 2025-06-01 | 50008.2 | 49284.8 | 49284.8 ✓ |
| 2025-03-01 | 47547.1 | 47950.4 | 47950.4 ✓ |
| 2024-12-01 | 57146.0 | 59271.0 | 59271.0 ✓ |
| 2011-03-01 | 13032.6 | 13024.8 | 13024.8 ✓ |

Все 60 точек переписаны (`Upserted 0 new, 60 updated`). Derived `gdp-yoy`, `gdp-qoq`, `gdp-nominal-annual` пересчитаны через `rebuild-all-derived.py` (127 точечных изменений в 3 рядах). Forecast cascade retrain'нулся: `gdp-nominal` (approved values сохранены), `gdp-yoy` (4 новых точки 8.93/9.82/4.28/2.12), `gdp-qoq` (4 новых), `gdp-nominal-annual` (1 новая). Redis cache invalidated.
