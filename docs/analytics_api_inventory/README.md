# Analytics API Inventory

**Last verified:** 2026-07-06 (ревизия CTO-аудита: статусы файлов актуальны; с 2026-05-22 добавились потребители существующих клиентов — `metrika_acquisition.py` (повизитная выгрузка Logs API + агрегаты Reporting в `raw_metrika_visits`/снапшоты, cron 08:20/14:20/20:20 МСК), `webmaster_recrawl.py` (автоподача переобхода 09:10 МСК), `webmaster_indexing_report.py` (еженедельный отчёт индексации, пн 09:30 МСК), admin-BI (`admin_bi.py` читает выгрузки как референс). Сами клиенты (`yandex_*_client.py`) без изменений — таблица статусов ниже верна. Ранее 2026-05-22: `metrika_data_import.md` удалён — был `planned, no code`.)
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
| `yandex_webmaster.md` | `app/services/yandex_webmaster_client.py` | `partial` — host/summary, diagnostics, sitemaps read+delete, search queries, indexing + in-search/events history, recrawl. Missing: important URLs, owners, SQI, sitemap add, external links. |
| `google_search_console.md` | `app/services/gsc_client.py` | `live local API verified, 2026-09-21` — read-only OAuth refresh, Sites (`siteFullUser`), Sitemaps status and daily web/image Search Analytics exports accepted. Bounded URL Inspection is implemented/tested but not live-probed. CLI `backend/scripts/google-search-console.py`; production credential mount/scheduler activation not part of this setup. |

**Круг 11 (09.10.2026, локально, не выпущено):** внутренний аналитический контур дополнен таблицами `user_signups` и `daily_goal_dims`, колонкой `site_locale`, витринами регистраций и воронки и четырьмя выключенными по умолчанию Telegram-отчётами; внешних API Яндекса и Google это не касается. События входа, регистрации и языка описаны в [frontend_instrumentation](frontend_instrumentation.md#дополнение-2026-10-09-круг-11-вход-регистрация-язык-новые-функции), контракт данных — [data-contracts](../data-contracts.md#c11-analytics-2026-10-09).

Activation cheat-sheet:

- `RUSTATS_ANALYTICS_API_TOKEN` защищает внутренние analytics REST endpoints
  (в частности `/api/v1/analytics/health`) через `X-Analytics-Token`.
  Публичные POST collectors `/analytics/events` и `/analytics/behavior` имеют
  отдельные проверки и этот служебный токен не требуют. Это не Yandex OAuth.
  Сверено 2026-09-27: `backend/app/api/analytics.py`; см. [контракты](../data-contracts.md).
- `analytics_scheduler_enabled=true` в `.env` включает hourly + daily jobs;
  без Yandex OAuth-токенов они выполняются вхолостую и пишут предупреждение.
- Live writes (`low_risk_write` / `high_risk_write`) требуют `analytics_live_writes_enabled=true`
  + одобренной записи в `agent_action_audit`.
  Статусы записи при `apply`: `proposed` → `applying` (намерение закоммичено до внешнего
  вызова) → `approved` | `failed`; повторный apply из `approved`/`applying` — 409, `applying`
  без итога требует ручной сверки с внешней системой (2026-10-04, F14).

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

## 2026-09-30 — local event-copy progress

`GET /api/v1/admin/bi/slices/meta` remains admin-only and adds `sync_progress`:
per-source `cursor`, captured committed `ceiling`, `caught_up`, `deferred`.
This is the last stored capture; failure before its write can leave an older
result. Read it with sync age and job logs, not as live PostgreSQL state.
`resync_pending` reports unfinished rebuild; metadata returns unavailable
with a reason, and slice reads defer until controlled rebuild completes.
The revised heartbeat does not assert commits after capture, correct CH
session deletions, or complete external integration coverage. Event replay
does not call Metrika/Direct APIs. [Canonical contract](../data-contracts.md#аналитические-окна-и-репликация-f05f06--2026-09-30)
and [local evidence/limits](../code-review/analytics-boundaries-acceptance-2026-09-30.md).
