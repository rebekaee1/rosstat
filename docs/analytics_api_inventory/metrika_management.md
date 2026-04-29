# Yandex Metrika Management API Inventory

Base URL: `https://api-metrika.yandex.net`.

Read scope: `metrika:read`.

Write scope: `metrika:write`, only through the action policy gateway.

| Resource | Operations | Safety | Storage | MCP tool | Fixture |
| --- | --- | --- | --- | --- | --- |
| Counters | list/get | read_only | `metrika_counters`, `metrika_counter_snapshots` | `management_counter_snapshot` | `tests/fixtures/metrika/counters.json` |
| Counters | create/edit | high_risk_write | `agent_action_audit`, `metrika_config_diffs` | `management_counter_diff` | `tests/fixtures/metrika/counter_update.json` |
| Counters | delete/restore | denied | `agent_action_audit` | none | `tests/fixtures/metrika/counter_delete_denied.json` |
| Counter code/options | get | read_only | `metrika_counter_snapshots` | `management_counter_snapshot` | `tests/fixtures/metrika/counter_code.json` |
| Goals | list/get | read_only | `metrika_goals` | `management_goals_snapshot` | `tests/fixtures/metrika/goals.json` |
| Goals | create/update | low_risk_write | `agent_action_audit`, `metrika_config_diffs` | `management_apply_goal` | `tests/fixtures/metrika/goal_update.json` |
| Goals | delete | high_risk_write | `agent_action_audit`, `metrika_config_diffs` | `management_apply_goal` | `tests/fixtures/metrika/goal_delete.json` |
| Filters | list/get | read_only | `metrika_filters` | `management_filters_snapshot` | `tests/fixtures/metrika/filters.json` |
| Filters | create/update | low_risk_write | `agent_action_audit`, `metrika_config_diffs` | `management_apply_filter` | `tests/fixtures/metrika/filter_update.json` |
| Filters | delete | high_risk_write | `agent_action_audit` | `management_apply_filter` | `tests/fixtures/metrika/filter_delete.json` |
| Operations | list/get/create/update/delete if available | high_risk_write for writes | `metrika_operations`, `agent_action_audit` | `management_operations` | `tests/fixtures/metrika/operations.json` |
| Grants/access/representatives | read | read_only | `metrika_grants` | `management_access_audit` | `tests/fixtures/metrika/grants.json` |
| Grants/access/representatives | write | denied | `agent_action_audit` | none | `tests/fixtures/metrika/access_write_denied.json` |
| Labels | read/write where available | low_risk_write for writes | `metrika_config_diffs` | `management_labels` | `tests/fixtures/metrika/labels.json` |
| Segments | read/write where available | low_risk_write for writes | `metrika_config_diffs` | `management_segments` | `tests/fixtures/metrika/segments.json` |
| Notes/annotations | read/write where available | low_risk_write for writes | `deploy_events`, `metrika_config_diffs` | `management_notes` | `tests/fixtures/metrika/notes.json` |
| Yandex Direct links | read/write where available | high_risk_write for writes | `metrika_config_diffs` | `management_direct_links` | `tests/fixtures/metrika/direct_links.json` |

Policy defaults:

- Delete/restore counter is denied.
- Grant/revoke access is denied.
- Counter edits require manual approval and before/after diff.
- Goal/filter edits require an approved action id.
- All writes require `settings.analytics_live_writes_enabled=true`.

Live smoke:

```bash
python scripts/analytics-smoke.py metrika-management --counter-id 107136069
```
