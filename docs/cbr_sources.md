# Внешние не-Росстат источники: ЦБ РФ и Минфин

**Last updated:** 2026-05-10.
**Part of:** [`../AGENTS.md`](../AGENTS.md), [`../CONTEXT.md`](../CONTEXT.md) (раздел `Parser` + `Source`).
**See also:** [`adr/0002-derived-always-reflects-source.md`](adr/0002-derived-always-reflects-source.md) (инвариант `bulk_upsert`).
**Code anchors:** `backend/app/services/cbr_*.py`, `backend/app/services/minfin_budget_parser.py`, `backend/app/services/upsert.py::bulk_upsert`, `backend/seed_data.py`.

Этот файл документирует все источники, **отличные от Росстата**, которые подтягиваются в систему. Росстат-парсеры (`rosstat_cpi_xlsx`, `rosstat_sdds_*`, `rosstat_ind_monthly`, `rosstat_population`, `rosstat_demo`, `rosstat_weekly_cpi`, `rosstat_fixed_assets`, `rosstat_science`) описаны в `CONTEXT.md` и не дублируются здесь.

В `seed_data.py` источник `Банк России` (канонически — именно так, кириллицей) задаёт сорс для всех CBR-индикаторов; источник `Министерство финансов` — для бюджетных. Оба source используются и для авторских ссылок в SEO-блоках на детальной странице.

## Идемпотентность вставки — общая для всех

Все парсеры (CBR + Minfin + Rosstat) пишут в `data_points` через `bulk_upsert` (`backend/app/services/upsert.py`):

```python
INSERT … ON CONFLICT (indicator_id, date) DO UPDATE SET value = excluded.value
WHERE data_points.value <> excluded.value
RETURNING id
```

Поведение:

- **Новая дата** — `INSERT` (`records_added += 1`).
- **Существующая дата с тем же значением** — guard `value <> excluded.value` срабатывает, `RETURNING` ничего не возвращает, `records_added/updated` не увеличиваются.
- **Существующая дата с другим значением** (ЦБ опубликовал ревизию) — `UPDATE` (`records_updated += 1`).

То есть прежнее заявление «`ON CONFLICT DO NOTHING`, для редких ревизий нужна отдельная процедура» — **устаревшее и неверное**. Ревизия ЦБ или Минфина подхватывается автоматически при ближайшем ETL.

См. `ADR-0002` для полной формулировки инварианта «derived всегда отражает source».

## ЦБ РФ — обзор

| Парсер (`parser_type`) | Источник | Формат | Метод | Индикаторы (codes) |
|------------------------|----------|--------|-------|---------------------|
| `cbr_keyrate_html` | `cbr.ru/hd_base/KeyRate/` + `cbr.ru/press/keypr/` | HTML (UniDbQuery) + HTML | GET | `key-rate` |
| `cbr_fx_xml` | `cbr.ru/scripts/XML_dynamic.asp` | XML | GET с диапазоном дат | `usd-rub`, `eur-rub`, `cny-rub` |
| `cbr_ruonia_html` | `cbr.ru/hd_base/ruonia/dynamics/` | HTML-таблица | GET с диапазоном | `ruonia` |
| `cbr_dataservice_json` | `cbr.ru/dataservice/data?pub=&ds=&el=` | JSON REST | GET по `(pub, ds, el)` | M0, M1, M2, ставки кредитов и депозитов (физ./юр., разные сроки), задолженность по кредитам физ./юр. лиц, авто-кредиты, current account balance, и др. (~16 индикаторов) |
| `cbr_dataservice_sum` | то же API, агрегатор | JSON REST | сумма нескольких `el` | сводные «вклады физлиц», «депозиты НФО» |
| `cbr_bop_xlsx` | `cbr.ru/vfs/statistics/credit_statistics/bop/bal_of_payments_standart.xlsx` | XLSX | GET | `exports`, `imports`, `trade-balance`, `services-exports`, `services-imports`, `fdi-net` |
| `cbr_reserves_html` | `cbr.ru/hd_base/mrrf/mrrf_7d/` | HTML-таблица | GET | `intl-reserves` (еженедельно) |
| `cbr_debt_xlsx` | `cbr.ru/vfs/statistics/credit_statistics/debt/debt_new.xlsx` | XLSX | GET | `external-debt` |
| `cbr_gold_html` | `cbr.ru/scripts/xml_metall.asp` | XML | GET | `gold-price` (учётная цена на золото) |
| `cbr_monetary_html` | `cbr.ru/hd_base/mb_nd/mb_nd_month/` | HTML-таблица | GET | **(зарегистрирован, но индикаторов сейчас нет)** — используется как fallback, если в будущем потребуется монетарная база |

## ЦБ РФ — детали по парсерам

### `cbr_keyrate_html` — Ключевая ставка

| Поле | Значение |
|------|----------|
| Парсер | `app/services/cbr_keyrate.py`, `cbr_keyrate_parser.py` |
| Метод | HTTP GET на `hd_base/KeyRate/` (форма UniDbQuery с диапазоном дат) |
| Окно | первичное — с **2013-09-13**; повторные ETL — окно **~150 дней** |

Особенность: `_post_upsert` дополнительно ходит на `cbr.ru/press/keypr/` и парсит ссылку на последний пресс-релиз Совета директоров — это переезжает в `indicator.last_decision_url`/`last_decision_date` для отображения на странице.

### `cbr_fx_xml` — Курсы валют (USD/EUR/CNY)

`cbr_fx_parser.py`. Эндпоинт `XML_dynamic.asp?date_req1=DD/MM/YYYY&date_req2=DD/MM/YYYY&VAL_NM_RQ=<id>`. Идентификаторы валют: USD `R01235`, EUR `R01239`, CNY `R01375`. Возвращает диапазонный XML — парсер преобразует курсы в `(date, value)` пары.

### `cbr_ruonia_html` — Ruonia

`cbr_ruonia_parser.py`. HTML-таблица с RUONIA по дням, парсится BeautifulSoup. Окно — 60 дней.

### `cbr_dataservice_json` — REST API ЦБ DataService

`cbr_dataservice_parser.py`. Универсальный JSON-парсер: ходит по тройке `(publicationId, datasetId, element_id)` (плюс `measureId`), которые задаются в `model_config_json` индикатора при seed'е. Пример (ставка по автокредитам, физ. лица, RUB, до 1 года):

```json
{
  "publicationId": 14,
  "datasetId": 25,
  "measureId": 2,
  "element_id": 7
}
```

Этот парсер обслуживает 16+ индикаторов: денежные агрегаты M0/M1/M2, портфельные задолженности по кредитам физ./юр. лиц, средневзвешенные ставки по кредитам и депозитам разных сегментов, квартальные сальдо платёжного баланса.

**Trap:** в начале мая 2026 поле `element_id` для ставок по автокредитам было перепутано (`6` вместо `7`) — индикатор показывал ставку по другому продукту. Любая правка `element_id` в seed'е требует прогона `daily_update_job` и проверки 5–10 последних точек глазами.

### `cbr_dataservice_sum` — агрегатор по нескольким элементам

`cbr_dataservice_sum_parser.py`. То же API, но в `model_config_json` указан **массив** `element_ids`, и парсер суммирует значения по всем элементам за каждую дату. Используется для сводных рядов «вклады физлиц всех типов», «депозиты НФО всех типов».

### `cbr_bop_xlsx` — Платёжный баланс (XLSX)

`cbr_bop_parser.py`. Скачивает `bal_of_payments_standart.xlsx` (XLSX, ~150 KB), читает квартальные строки. В `model_config_json` индикатора указывается, какую строку и какой знак (для импорта/балансов) брать. Покрывает: `exports`, `imports`, `trade-balance`, `services-exports`, `services-imports`, `fdi-net`. Также есть внутренние варианты для торговли услугами и FDI.

### `cbr_reserves_html` — Международные резервы (еженедельно)

`cbr_reserves_parser.py`. HTML-таблица с резервами на каждую отчётную дату (пятницы). Окно — последние ~52 недели.

### `cbr_debt_xlsx` — Внешний долг

`cbr_debt_parser.py`. `debt_new.xlsx`, квартальные значения совокупного внешнего долга РФ (общий, госсектор, банки, прочий) с 2003 года. Сейчас seed подключает только агрегат — остальные строки можно добавить точечно.

### `cbr_gold_html` — Цена на золото

`cbr_gold_parser.py`. XML-эндпоинт `scripts/xml_metall.asp` — учётная цена на золото (металл `1`), руб./грамм, ежедневно.

### `cbr_monetary_html` — Денежная база (зарегистрирован, не используется)

`cbr_monetary_parser.py`. HTML-таблица `hd_base/mb_nd/mb_nd_month/` с месячными значениями денежной базы. Парсер зарегистрирован в `PARSER_REGISTRY`, но в seed'e нет ни одного индикатора с `parser_type='cbr_monetary_html'`. Стратегически — можно подключить при необходимости, тестировать через локальный seed.

## Минфин РФ — обзор

| Парсер (`parser_type`) | Источник | Формат | Метод | Индикаторы (codes) |
|------------------------|----------|--------|-------|---------------------|
| `minfin_budget_csv` | `minfin.gov.ru/opendata/7710168360-fedbud_month/` | CSV (через каталог open-data) | GET | `budget-revenues`, `budget-expenditures`, `budget-balance` (вычисляется как derived) |

### `minfin_budget_csv` — Федеральный бюджет

`minfin_budget_parser.py`. Заходит на каталоговую страницу open-data Минфина, находит ссылку на актуальный CSV (HTML-парсинг каталога BeautifulSoup'ом), скачивает CSV. Логика:

1. CSV публикуется как **нарастающий итог с начала года** (year-to-date).
2. Парсер пересчитывает в **месячные значения** через дельту YTD\[m\] − YTD\[m−1\] (для января — равно YTD\[1\]).
3. Месячные значения уходят в `data_points`.

Это значит: при ревизии прошлых месяцев (Минфин иногда корректирует YTD задним числом) `bulk_upsert` обновит соответствующие месячные точки.

`budget-balance` (доходы − расходы) **не парсится напрямую**, а вычисляется через derived (`subtract` в `DERIVED_SPECS`), поэтому он автоматически следует ревизиям доходов/расходов через ADR-0002.

## Расписание

Те же `daily_update_job` и `calendar_refresh` из `app/tasks/scheduler.py` (см. `enterprise_resilience.md` и `CONTEXT.md`). Daily ETL обходит **все** индикаторы с `is_active=true`, включая описанные выше CBR/Минфин — отдельных расписаний нет.

Calendar publication dates are source-bound (ADR-0005):

- CBR daily official-rule events use `cbr.ru/statistics/indcalendar/` + versioned Russian working calendar for `usd-rub`, `eur-rub`, `cny-rub`, `gold-price`, `ruonia`.
- CBR monthly/quarterly/weekly publication dates use official `vCalendar.ics` from the same page for M0/M1/M2, reserves, credits/deposits, credit/deposit rates, mortgage, goods/services trade, current account, external debt, FDI.
- CBR key-rate meeting/summary dates use official monetary-policy calendar `cbr.ru/dkp/cal_mp/`.
- Minfin budget dates use official `minfin.gov.ru/ru/statistics/schedule`; revenue/expenditure/deficit share the 14th-working-day release.

`auto-loan-rate` remains uncovered by calendar until an official calendar row/rule is found; estimated dates are not published.

## Ручной запуск отдельного индикатора

```bash
docker compose exec backend python -c \
  "import asyncio; from app.tasks.scheduler import run_etl_for_indicator; \
   asyncio.run(run_etl_for_indicator('key-rate'))"
```

Заменить `'key-rate'` на любой `code` индикатора. Скрипт логирует всё в JSON-формате через `JsonFormatter`. Для повторной перекачки полной истории — установить флаг через ручную правку SQL (`UPDATE indicators SET model_config_json = jsonb_set(model_config_json, '{full_refresh}', 'true')`) и прогнать; парсер должен это поддерживать (не все поддерживают полный перезалив — для CBR DataService/BOP — да, для других проще пересоздать через `seed_data.py` с очисткой `data_points`).
