# Yandex Webmaster API Inventory

Base URL: `https://api.webmaster.yandex.net`.

Scope: Webmaster OAuth scope required by Yandex for verified site access.

Host allowlist: `forecasteconomy.com`.

| Endpoint | Operation | Safety | Storage | MCP tool | Fixture |
| --- | --- | --- | --- | --- | --- |
| `GET /user/` | get user id | read_only | `webmaster_hosts` | `webmaster_hosts` | `tests/fixtures/webmaster/user.json` |
| `GET /user/{user-id}/hosts/` | list hosts | read_only | `webmaster_hosts` | `webmaster_hosts` | `tests/fixtures/webmaster/hosts.json` |
| `GET /user/{user-id}/hosts/{host-id}/` | host info | read_only | `webmaster_hosts` | `webmaster_host_summary` | `tests/fixtures/webmaster/host.json` |
| `GET /user/{user-id}/hosts/{host-id}/summary/` | host summary | read_only | `webmaster_host_summaries` | `webmaster_host_summary` | `tests/fixtures/webmaster/summary.json` |
| `GET /user/{user-id}/hosts/{host-id}/important-urls/` | important URLs | read_only | `webmaster_important_urls` | `webmaster_important_urls` | `tests/fixtures/webmaster/important_urls.json` |
| `GET /user/{user-id}/hosts/{host-id}/important-urls/history/` | important URL history | read_only | `webmaster_important_urls` | `webmaster_important_urls` | `tests/fixtures/webmaster/important_urls_history.json` |
| `GET /user/{user-id}/hosts/{host-id}/verification/` | verification info | read_only | `webmaster_hosts` | `webmaster_hosts` | `tests/fixtures/webmaster/verification.json` |
| `POST /user/{user-id}/hosts/{host-id}/verification/` | start verification | high_risk_write | `agent_action_audit` | `webmaster_verification_start` | `tests/fixtures/webmaster/verification_start.json` |
| `GET /user/{user-id}/hosts/{host-id}/owners/` | owners | read_only | `webmaster_owners` | `webmaster_owners` | `tests/fixtures/webmaster/owners.json` |
| `GET /user/{user-id}/hosts/{host-id}/sitemaps/` | all sitemaps | read_only | `webmaster_sitemaps` | `webmaster_sitemaps` | `tests/fixtures/webmaster/sitemaps.json` |
| `GET /user/{user-id}/hosts/{host-id}/sitemaps/{sitemap-id}/` | sitemap details | read_only | `webmaster_sitemaps` | `webmaster_sitemaps` | `tests/fixtures/webmaster/sitemap_detail.json` |
| `GET /user/{user-id}/hosts/{host-id}/user-added-sitemaps/` | user sitemaps | read_only | `webmaster_sitemaps` | `webmaster_sitemaps` | `tests/fixtures/webmaster/user_sitemaps.json` |
| `POST /user/{user-id}/hosts/{host-id}/user-added-sitemaps/` | add sitemap | low_risk_write | `agent_action_audit`, `webmaster_sitemaps` | `webmaster_sitemap_add` | `tests/fixtures/webmaster/sitemap_add.json` |
| `GET /user/{user-id}/hosts/{host-id}/user-added-sitemaps/{sitemap-id}/` | user sitemap detail | read_only | `webmaster_sitemaps` | `webmaster_sitemaps` | `tests/fixtures/webmaster/user_sitemap_detail.json` |
| `DELETE /user/{user-id}/hosts/{host-id}/user-added-sitemaps/{sitemap-id}/` | remove sitemap | high_risk_write | `agent_action_audit` | `webmaster_sitemap_delete` | `tests/fixtures/webmaster/sitemap_delete.json` |
| `GET /user/{user-id}/hosts/{host-id}/sqi_history/` | SQI/IKS history | read_only | `webmaster_sqi_history` | `webmaster_sqi_history` | `tests/fixtures/webmaster/sqi_history.json` |
| `GET /user/{user-id}/hosts/{host-id}/search-queries/popular/` | popular queries | read_only | `webmaster_search_queries` | `webmaster_search_queries` | `tests/fixtures/webmaster/search_popular.json` |
| `GET /user/{user-id}/hosts/{host-id}/search-queries/all/history/` | all query history | read_only | `webmaster_search_queries` | `webmaster_search_queries` | `tests/fixtures/webmaster/search_all_history.json` |
| `GET /user/{user-id}/hosts/{host-id}/search-queries/{query-id}/history/` | query history | read_only | `webmaster_search_queries` | `webmaster_search_queries` | `tests/fixtures/webmaster/search_query_history.json` |
| `GET /user/{user-id}/hosts/{host-id}/recrawl/queue/` | recrawl queue | read_only | `webmaster_recrawl_tasks` | `webmaster_reindex_plan` | `tests/fixtures/webmaster/recrawl_queue.json` |
| `POST /user/{user-id}/hosts/{host-id}/recrawl/queue/` | submit recrawl | low_risk_write | `agent_action_audit`, `webmaster_recrawl_tasks` | `webmaster_apply_reindex` | `tests/fixtures/webmaster/recrawl_submit.json` |
| `GET /user/{user-id}/hosts/{host-id}/recrawl/quota/` | recrawl quota | read_only | `webmaster_recrawl_tasks` | `webmaster_reindex_plan` | `tests/fixtures/webmaster/recrawl_quota.json` |
| `GET /user/{user-id}/hosts/{host-id}/recrawl/queue/{task-id}/` | recrawl task status | read_only | `webmaster_recrawl_tasks` | `webmaster_reindex_plan` | `tests/fixtures/webmaster/recrawl_task.json` |
| `GET /user/{user-id}/hosts/{host-id}/diagnostics/` | diagnostics | read_only | `webmaster_diagnostics` | `webmaster_diagnostics` | `tests/fixtures/webmaster/diagnostics.json` |
| `GET /user/{user-id}/hosts/{host-id}/indexing/history/` | indexing history | read_only | `webmaster_index_history` | `webmaster_indexing_status` | `tests/fixtures/webmaster/indexing_history.json` |
| `GET /user/{user-id}/hosts/{host-id}/indexing/samples/` | downloaded samples | read_only | `webmaster_index_history` | `webmaster_indexing_status` | `tests/fixtures/webmaster/indexing_samples.json` |
| `GET /user/{user-id}/hosts/{host-id}/search-urls/in-search/history/` | pages in search history | read_only | `webmaster_index_history` | `webmaster_indexing_status` | `tests/fixtures/webmaster/in_search_history.json` |
| `GET /user/{user-id}/hosts/{host-id}/search-urls/in-search/samples/` | pages in search samples | read_only | `webmaster_index_history` | `webmaster_indexing_status` | `tests/fixtures/webmaster/in_search_samples.json` |
| `GET /user/{user-id}/hosts/{host-id}/search-urls/events/history/` | search URL event history | read_only | `webmaster_search_url_events` | `webmaster_search_url_events` | `tests/fixtures/webmaster/search_events_history.json` |
| `GET /user/{user-id}/hosts/{host-id}/search-urls/events/samples/` | search URL event samples | read_only | `webmaster_search_url_events` | `webmaster_search_url_events` | `tests/fixtures/webmaster/search_events_samples.json` |
| `GET /user/{user-id}/hosts/{host-id}/links/internal/broken/samples/` | broken internal links | read_only | `webmaster_internal_broken_links` | `webmaster_links_audit` | `tests/fixtures/webmaster/internal_broken_samples.json` |
| `GET /user/{user-id}/hosts/{host-id}/links/internal/broken/history/` | broken internal link history | read_only | `webmaster_internal_broken_links` | `webmaster_links_audit` | `tests/fixtures/webmaster/internal_broken_history.json` |
| `GET /user/{user-id}/hosts/{host-id}/links/external/samples/` | external links | read_only | `webmaster_external_links` | `webmaster_links_audit` | `tests/fixtures/webmaster/external_links_samples.json` |
| `GET /user/{user-id}/hosts/{host-id}/links/external/history/` | external link history | read_only | `webmaster_external_links` | `webmaster_links_audit` | `tests/fixtures/webmaster/external_links_history.json` |

Live smoke:

```bash
python scripts/analytics-smoke.py webmaster --host forecasteconomy.com
```
