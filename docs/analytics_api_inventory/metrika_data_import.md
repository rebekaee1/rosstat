# Yandex Metrika Data Import API Inventory

Base URL: `https://api-metrika.yandex.net`.

Scopes:

- `metrika:offline_data` for offline conversions, calls and CRM-like data.
- `metrika:expenses` for expenses.
- `metrika:user_params` for user parameters.
- `metrika:write` grants broad access, but narrower scopes are preferred.

| Resource | Operation | Safety | Storage | MCP tool | Fixture |
| --- | --- | --- | --- | --- | --- |
| Offline conversions | validate CSV locally | read_only | none | `import_validate_csv` | `tests/fixtures/metrika/offline_conversions.csv` |
| Offline conversions | upload CSV | low_risk_write | `metrika_import_uploads`, `agent_action_audit` | `import_upload_offline_conversions` | `tests/fixtures/metrika/offline_upload.json` |
| Offline conversions | upload status | read_only | `metrika_import_uploads`, `metrika_import_errors` | `import_upload_status` | `tests/fixtures/metrika/offline_status.json` |
| Expenses | list uploads/status | read_only | `metrika_import_uploads` | `import_expenses_status` | `tests/fixtures/metrika/expenses.json` |
| Expenses | upload | low_risk_write | `metrika_import_uploads`, `agent_action_audit` | `import_upload_expenses` | `tests/fixtures/metrika/expenses_upload.json` |
| Calls | upload/status | low_risk_write | `metrika_import_uploads`, `agent_action_audit` | `import_upload_calls` | `tests/fixtures/metrika/calls_upload.json` |
| User parameters | validate schema | read_only | `frontend_event_catalog` | `import_user_params_plan` | `tests/fixtures/metrika/user_params.json` |
| User parameters | upload | high_risk_write | `metrika_import_uploads`, `agent_action_audit` | `import_upload_user_params` | `tests/fixtures/metrika/user_params_upload.json` |
| CRM/customer/order data | design/status/upload where exposed | high_risk_write | `metrika_import_uploads`, `agent_action_audit` | `import_crm_plan` | `tests/fixtures/metrika/crm_upload.json` |

Required validation:

- CSV UTF-8 encoding.
- File size within documented limit.
- At least one supported identifier: `ClientID`, `UserID`, `yclid`, `PurchaseId`, as applicable.
- Date/time format normalized before upload.
- Linkage failures and `user_not_found` style counters stored.
- No raw personal data upload without explicit privacy design.

Live smoke:

```bash
python scripts/analytics-smoke.py metrika-import-status --counter-id 107136069
```
