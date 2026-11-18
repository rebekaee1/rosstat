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

## 2026-11-18 — «в поиске» 105 480 → 29 306: перерыв данных Яндекса, а не исключение страниц

Разбор пункта 7 Пульса за 17.11 (API Вебмастера и боевые таблицы, только чтение; подробно — [backlog](../backlog.md#yandex-in-search-2026-11-18)).

- **Причина перерыва — сторона Яндекса.** Аварии дата-центров Яндекса 8–11.10.2026 ([сообщение компании](https://yandex.ru/company/news/09-10-2026-01)); в разделе «Страницы в поиске» до сих пор плашка «временно недоступны графики и выгрузка отчётов, данные могут обновляться с задержкой». У всех четырёх хостов аккаунта точки `in-search/history` идут 02.10, 05.10, 07.10 и сразу 13.11. История обхода (`indexing/history`) у обоих наших хостов кончается 10.10, `sitemaps.last_access_date` — 09–10.10, `indexing/samples` 18.11 обрывает соединение без ответа. `summary` отдавал замороженные 105 480 / 756 исключённых до 16.11 (недельный отчёт 16.11 — «без изменений»), к 17.11 — 29 306 / 6 078.
- **Что в цифрах.** apex: 105 480 (07.10) → 29 306 (13.11); `ru.`: 9 543 → 27 365; оба хоста: 115 023 → 56 671. События обновления 13.11 (`events/samples`, 4 002 записи, полная выборка): apex +3 267 появилось, −658 исключено, все 658 — `LOW_QUALITY` (английские страницы о России и сравнения стран, перечитаны роботом в ноябре). Пятинедельной разницы в событиях нет: промежуточные обновления базы Вебмастер не записал. Исключённых по `summary` 6 078 — значит, ~70 тыс. адресов apex выпали из счёта Яндекса без статуса; причину по адресам API не отдаёт.
- **Что сейчас в поиске apex** (`in-search/samples`, все 29 383): 13,7 тыс. страниц России, 7,9 тыс. старых русских адресов `/region/…` и 1,6 тыс. `/indicator/…` (с 11.11 отдают 301 на `ru.`, ADR-0029), иностранных стран — единицы тысяч. `last_access` у 99 % — июль–сентябрь: в поиске старые снимки, база после аварии почти не перечитана. `ru.` (27 542): 25,8 тыс. страниц России, 15,9 тыс. — годовые страницы регионов.
- **Сайт отвечает Яндексу нормально.** Журнал nginx за 17.11: 27 956 запросов YandexBot из проверенных сетей (`cls=crawler`), 99 % — 200, 131 — 301, 47 — 502, 29 — 404, ни одного 429. `robots.txt` обоих хостов открыт для Yandex; образцы страниц — 200, свой canonical, `robots index` (`googlebot noindex` только для Google, ADR-0029/0031).
- **Люди из Яндекса не ушли.** Сессии с переходом из выдачи Яндекса (`behavior_sessions`, `channel='search'`): 1,4–1,8 тыс. в неделю в сентябре–октябре, 2 363 за неделю 09–15.11, 385–418 в будни 16–17.11 против 300–400 до 13.11.

**Что изменено (18.11).** `services/webmaster_freshness.py`: дата последней и предыдущей точки «в поиске», перерыв (`data_gap` — больше 7 дней) и остановка истории обхода. Пульс получает `seo.in_search_freshness`, `seo.yandex_data_gap` и по хосту в `summary_by_host`, в память — `seo_in_search_date`; подсказка запрещает называть разницу через перерыв падением. Недельный отчёт подписывает число обеими датами и пишет, с какого дня стоит история обхода. Запись `yandex-dc-outage` в `pulse_context.yaml`. Тест — `tests/test_webmaster_freshness.py`.

**Не проверено.** Какие именно ~70 тыс. адресов apex ушли из счёта: выгрузка и графики исключённых в Вебмастере недоступны, `indexing/samples` не отвечает. Повторить, когда Яндекс снимет плашку: `events/samples` и выгрузка «Исключённые страницы» в интерфейсе.

## 2026-11-13 — токен выпущен заново

Токен выдаёт приложение «Forecast Economy Webmaster» (создано 10.05.2026, права «Яндекс.Вебмастер», почта оповещений rebeka.ee). Прежний токен прожил ровно 180 суток: 10.05 → 06.11.2026. Новый выпущен 13.11.2026 по слову владельца («можешь пользоваться моим компом и сделать и сохранить себе сразу»): страница `oauth.yandex.ru/authorize?response_type=token&client_id=<id приложения>` в браузере владельца, кнопка «Войти как…», токен со страницы `verification_code` записан в `RUSTATS_YANDEX_WEBMASTER_TOKEN` боевого `.env` (копия прежнего файла — `.env.bak-20261113-wmtoken`), пересоздан только контейнер `scheduler`. Проверка: `GET /v4/user` → 200, `webmaster_queries_daily_job` на боевом прошёл. Следующее истечение — около 12.05.2027; напоминание заранее не настроено. Значение токена в репозитории и документах не хранится.

## 2026-11-09 — токен истёк

С 06.11.2026 `RUSTATS_YANDEX_WEBMASTER_TOKEN` недействителен: `login.yandex.ru/info` — 401 `expired_token`, `GET /v4/user/` — 403 `INVALID_OAUTH_TOKEN`. Токен Метрики (`RUSTATS_YANDEX_METRIKA_READ_TOKEN`, аккаунт rebeka.ee) жив, но его приложение без прав Вебмастера (403 `ACCESS_FORBIDDEN`, «application scopes: []»). Обновления токена без человека в проекте нет: новый выдаётся входом владельца в Яндекс. Пока токен не обновлён, задачи `webmaster_queries_daily`, переобход и SEO-срез Пульса пишут одно сообщение `token_expired` в сутки (`backend/app/services/yandex_token_alert.py`) вместо сбоя задачи и двух `recrawl_alert`. Владелец 09.11.2026 обновить токен не может («они больше не показывают ничего нормально»): сообщение приходит один раз на истёкший токен, данные Вебмастера (запросы, индексация, переобход) до нового токена не собираются.

## 2026-10-12 — доступность API и след сбоя (круг 13)

Наблюдение зоны R-SEO: TCP-соединение с `api.webmaster.yandex.net:443` (213.180.193.61 и 2a02:6b8::2:61) и `:80` не устанавливается с боевого сервера, тестового стенда и ноутбука, остальные хосты Яндекса (`webmaster.yandex.ru`, `oauth.yandex.ru`, `passport.yandex.ru`, `api-metrika.yandex.net`) отвечают; токен ни при чём (до рукопожатия не доходит). Последний успешный синк `daily_search_queries` 10.10 05:40 UTC (6 655 строк; данные запросов по 06.10, лаг API 3 дня). Наша часть: задания 08:40 вызывали API до записи о запуске, поэтому 11 и 12.10 следа не осталось; теперь `analytics_sync_runs` создаётся до обращения, в `error_message` пишется тип исключения (`ConnectTimeout` приходит с пустым текстом), дневной снимок индексации при сбое пишет строку `failed` и проверка свежести идёт и без строки за день (`analytics_ingestion.py`, `analytics_backfill.py`, `webmaster_indexing_daily.py`, тест `tests/test_webmaster_failure_trace.py`). Из-за недоступности API недельный SEO-отчёт показывает прямое предупреждение при данных старше трёх суток. Состав ≈ 220 неопознанных ошибок sitemap `ru.` и 74 тыс. на `.com` смотреть только в интерфейсе Вебмастера. Не проверено: причина сетевой недоступности (не ответ поддержки), поведение API после её устранения.
