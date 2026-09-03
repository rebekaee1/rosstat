# Google Search Console API Inventory

**Last verified:** 2026-09-03.
**Implementation status:** `partial` — `app/services/gsc_client.py`.
Реализовано: Search Analytics query → таблица `gsc_search_queries` (job 09:10 МСК,
только если задан `RUSTATS_GSC_ACCESS_TOKEN`). Meta `google-site-verification`
в SSR, если задан `RUSTATS_GOOGLE_SITE_VERIFICATION`.
Не реализовано: Inspection API, sitemaps submit/list через API, Indexing API
(не строим — квота и риск). Domain property и TXT/HTML-токен — owner-action.

**Part of:** [`README.md`](README.md) в этой папке, ADR-0003, план индексации 2026-09-03.

Site URL в запросах: `sc-domain:forecasteconomy.com` (Domain property).

| Endpoint | Operation | Safety | Storage | Notes |
| --- | --- | --- | --- | --- |
| `POST /webmasters/v3/sites/{site}/searchAnalytics/query` | search analytics | read_only | `gsc_search_queries` | dimensions query/page/date, окно 7 дней |
| HTML meta `google-site-verification` | verification | n/a | SSR head | токен владельца в env |

OAuth: Google Cloud project, scope `https://www.googleapis.com/auth/webmasters.readonly`.
Токен кладётся в `RUSTATS_GSC_ACCESS_TOKEN` (не коммитить).

Bing Webmaster: верификация meta `msvalidate.01` (`RUSTATS_BING_SITE_VERIFICATION`);
импорт из GSC в кабинете Bing; IndexNow уже общий.
