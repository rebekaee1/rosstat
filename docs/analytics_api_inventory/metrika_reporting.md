# Yandex Metrika Reporting API Inventory

**Last verified:** 2026-05-07.
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
