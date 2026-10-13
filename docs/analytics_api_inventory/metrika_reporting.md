# Yandex Metrika Reporting API Inventory

**Last verified:** 2026-05-22 (sanity-check, статус без изменений).
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

## 2026-10-12 — отчёты Метрики пусты с 11.10 (круг 13)

Наблюдение зоны R-SEO: отчёт по часам обычен (20–40 визитов/ч) до 11.10 03:20 МСК, дальше нули; счётчик 107136069 по management API `status: Active`, `code_status: CS_ERR_UNKNOWN` (то же значение уже в снимке 29.09); запросы Logs API за 11.10 (61737482, 61744378) стоят в состоянии `created` больше суток. На нашей стороне тег исправен (`tag.js` 200, `watch/107136069/1` GET и POST 200, cookie `_ym_uid` ставится, CSP не мешает, мобильные профили WebKit и Chromium), код на боевом между 09.10 и 12.10 не менялся. Решение владельца: сторона Яндекса, ничего не делать, перепроверить через 2–3 дня; публичных сообщений Яндекса об инциденте не найдено. Вызов management API без параметров `GET /management/v1/counter/107136069` работает (400 давало `field=code`). Метрика остаётся источником целей в старом блоке дайджеста; в недельный и месячный отчёты цели Метрики не добавлены (нужен токен на стенде или `render-telegram-reports.py --metrika` на боевом).
