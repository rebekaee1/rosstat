# Yandex Metrika Logs API Inventory

**Сверка реализации:** 2026-09-27, локальная main; live API в этом проходе не запрашивался.
**Implementation status:** `partial` — транспорт `app/services/yandex_metrika_logs.py`
реализует `list_requests`, `create_request`, `request_info`, `download_part`, `clean_request`.
Нормализация **visits уже реализована** в `metrika_acquisition.py::parse_visits_tsv`,
`_upsert_visit`, `sync_visits_for_day`: TSV → `raw_metrika_visits`, хэширование client ID,
повторяемый upsert по counter/visit ID. Scheduler вызывает acquisition sync при
соответствующих флагах; наличие кода не означает, что job включён в каждом окружении.
Fields catalog и полноценный ingest `raw_metrika_hits` остаются отдельным пробелом.
Таблица ниже сохраняет исходный целевой inventory API; названия MCP tools в ней
не означают, что каждый метод опубликован нынешним MCP сервером (его реестр —
`mcp/forecast-analytics-mcp/src/index.ts`). Прежняя запись 2026-05-22 о том, что весь
TSV ingest ещё предстоит написать, устарела для visits.

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
