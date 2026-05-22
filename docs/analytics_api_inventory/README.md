# Analytics API Inventory

**Last verified:** 2026-05-22 (sanity-check: `metrika_data_import.md` удалён — был `planned, no code`; остальные 6 файлов актуальны по статусу).
**Part of:** [`../../AGENTS.md`](../../AGENTS.md), [`../../CONTEXT.md`](../../CONTEXT.md) (раздел `Forecast Analytics OS`).
**Code anchors:** `backend/app/services/yandex_*.py` (clients), `backend/app/services/analytics_*.py` (ingestion + features), `backend/app/api/analytics.py` (REST), `mcp/forecast-analytics-mcp/` (MCP server).

This directory is the implementation checklist for Forecast Analytics OS.
Every Yandex API client must be mapped here before code is allowed to call it.

## Implementation status as of 2026-05-22

The inventory is the **long-term contract** of which Yandex APIs the platform may
touch. Actual implementation is partial; live integrations require an OAuth token
in `.env` (`YANDEX_METRIKA_TOKEN` / `YANDEX_METRIKA_WRITE_TOKEN` /
`YANDEX_WEBMASTER_TOKEN`) and `analytics_live_writes_enabled=true` for any
non-`read_only` operation. Without tokens the analytics scheduler is a no-op
and `analytics-smoke.py` exits with `enabled=false`.

| File | Code module | Status (2026-05-22) |
|------|-------------|---------------------|
| `frontend_instrumentation.md` | `frontend/src/lib/track.js`, `utm.js`, `cleanUrl.js`, `useScrollDepth.js`, `index.html`; backend collector `app/api/analytics.py::events_collector` → `FrontendEvent` | `implemented` — Webvisor 2 + form analytics включены, ~60 целей в `events`, UTM helper + taxonomy. Канонический документ для frontend goals и share-ссылок. |
| `metrika_logs.md` | `app/services/yandex_metrika_logs.py` | `partial` — `list_requests`, `create_request`, `request_info`, `download_part`, `clean_request`. Missing: fields catalog. |
| `metrika_management.md` | `app/services/yandex_metrika_management.py` | `partial` — read of counters/goals/filters/grants + goal create/update/delete behind approval. Missing: counter writes, filter writes, segments/labels/notes/direct-links. |
| `metrika_reporting.md` | `app/services/yandex_metrika_reporting.py` | `implemented` — все JSON-варианты `table` / `bytime` / `drilldown` / `comparison` / `comparison_drilldown`. CSV-варианты пока только через ручной HTTP. |
| `yandex_webmaster.md` | `app/services/yandex_webmaster_client.py` | `partial` — host info/summary, diagnostics, sitemaps read, search queries popular, indexing history, recrawl queue + submit, internal broken links. Missing: important URLs, owners, SQI history, sitemap add/delete, search-URLs/events, external links. |

Activation cheat-sheet:

- Без `RUSTATS_ANALYTICS_API_TOKEN` (защищающего внутренний REST) endpoints
  `/api/v1/analytics/*` отвечают 401. Это отдельный токен от Yandex OAuth.
- `analytics_scheduler_enabled=true` в `.env` включает hourly + daily jobs;
  без Yandex OAuth-токенов они выполняются вхолостую и пишут предупреждение.
- Live writes (`low_risk_write` / `high_risk_write`) требуют `analytics_live_writes_enabled=true`
  + одобренной записи в `agent_action_audit`.

Each endpoint row records:

- method and path;
- official documentation URL;
- OAuth scopes;
- required/optional parameters;
- response fields consumed by the app;
- limits, quotas, lag, sampling/privacy flags;
- retry/error handling;
- warehouse destination;
- protected Analytics API endpoint;
- MCP tool mapping;
- safety class;
- fixture/smoke coverage.

Safety classes:

- `read_only`: can run without approval if credentials and target are allowlisted.
- `low_risk_write`: requires an approved action record before live execution.
- `high_risk_write`: requires explicit manual approval and detailed before/after diff.
- `denied`: not executable by the agent.

Implementation rule: a client module is not complete until every endpoint family in
its inventory has a storage/API/MCP decision and at least one fixture.
