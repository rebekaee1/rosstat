# Analytics API Inventory

This directory is the implementation checklist for Forecast Analytics OS.
Every Yandex API client must be mapped here before code is allowed to call it.

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
