# Yandex Webmaster API Inventory

**Last verified:** 2026-09-03 (ежедневный синк in-search / indexing / events / sitemaps → `webmaster_indexing_daily`).
**Implementation status:** `partial` — `app/services/yandex_webmaster_client.py`.
Реализовано: `user`, `hosts`, `host`, `summary`, `diagnostics`, `sitemaps` (read + user-added delete),
`search_queries_popular` (ежедневный синк 08:40 МСК в `webmaster_search_queries`),
`recrawl_queue` / `recrawl_quota` / `submit_recrawl`,
`indexing_history`, `in_search_history`, `search_events_history` / `search_events_samples`,
`links_internal_broken_samples`. Ежедневный снимок: `webmaster_indexing_daily_job` 08:50 МСК.
Не реализовано: important-urls (+ history), owners, verification (read+start), sqi_history,
links/external, sitemap add (`POST user-added-sitemaps`). Эти строки таблицы
ниже — целевой контракт.

Base URL: `https://api.webmaster.yandex.net`.

Scope: Webmaster OAuth scope required by Yandex for verified site access.

Host allowlist: `forecasteconomy.com` и `ru.forecasteconomy.com` (после cutover оба свойства).
Языковой сплит — **не** «Переезд сайта»: Яндекс не переклеивает индекс apex→ru. целиком.
Канон RU живёт на `ru.` (hreflang + self-canonical); apex остаётся EN + x-default.
Документация: [локализованные страницы](https://yandex.ru/support/webmaster/ru/yandex-indexing/locale-pages).

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

## 2026-10-12 — доступность API и след сбоя (круг 13)

Наблюдение зоны R-SEO: TCP-соединение с `api.webmaster.yandex.net:443` (213.180.193.61 и 2a02:6b8::2:61) и `:80` не устанавливается с боевого сервера, тестового стенда и ноутбука, остальные хосты Яндекса (`webmaster.yandex.ru`, `oauth.yandex.ru`, `passport.yandex.ru`, `api-metrika.yandex.net`) отвечают; токен ни при чём (до рукопожатия не доходит). Последний успешный синк `daily_search_queries` 10.10 05:40 UTC (6 655 строк; данные запросов по 06.10, лаг API 3 дня). Наша часть: задания 08:40 вызывали API до записи о запуске, поэтому 11 и 12.10 следа не осталось; теперь `analytics_sync_runs` создаётся до обращения, в `error_message` пишется тип исключения (`ConnectTimeout` приходит с пустым текстом), дневной снимок индексации при сбое пишет строку `failed` и проверка свежести идёт и без строки за день (`analytics_ingestion.py`, `analytics_backfill.py`, `webmaster_indexing_daily.py`, тест `tests/test_webmaster_failure_trace.py`). Из-за недоступности API недельный SEO-отчёт показывает прямое предупреждение при данных старше трёх суток. Состав ≈ 220 неопознанных ошибок sitemap `ru.` и 74 тыс. на `.com` смотреть только в интерфейсе Вебмастера. Не проверено: причина сетевой недоступности (не ответ поддержки), поведение API после её устранения.
