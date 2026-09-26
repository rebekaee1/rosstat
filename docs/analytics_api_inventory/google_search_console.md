# Google Search Console API Inventory

**Last verified:** 2026-09-21 (live OAuth refresh, Sites, Sitemaps and Search Analytics).
**Implementation status:** local read-only API access verified after user consent.
The Search Console API is enabled; `sites` returned `sc-domain:forecasteconomy.com`
with `permissionLevel: siteFullUser`. `app/services/gsc_client.py` supports renewable
OAuth and the existing daily job (09:10 Moscow). Credentials are local; the
production scheduler/credential mount has **not** been activated by this setup.

**Provider UI, 2026-09-21:** `sc-domain:forecasteconomy.com` and the intended owner
account were verified in Search Console. The existing Google Cloud project's
OAuth Audience is **In production**, not Testing. The Russian sitemap was
submitted in the UI alongside the apex sitemap and then showed **Success**.
The subsequent API export confirms both sitemap indexes are processed
(`isPending: false`) with zero errors and warnings:

- Russian: `submitted: 839907`, downloaded `2026-09-20T21:04:11.381Z`
  (2026-09-21 00:04 Moscow).
- Apex: `submitted: 906780`, downloaded `2026-09-20T20:36:30.881Z`
  (2026-09-20 23:36 Moscow).

These are Google's sitemap snapshots, not the current complete site inventory or
indexed-page totals. The returned `contents[].indexed: 0` is a **deprecated field**
that Google explicitly says not to use; it does not mean zero indexed pages.
Search Console API has no equivalent of the UI's full Page indexing report or a
reliable total indexed-page counter. Use the UI for that report and bounded URL
Inspection samples for individual URLs.

**Initial private exports:** `analytics/gsc/{sites,sitemaps,web,image}.json`, all
mode `0600`, ignored by git. Both search exports cover 2026-08-21 through 2026-09-17
inclusive, 28 days in `America/Los_Angeles`, finalized data, dimensions
`query,page,date`. Web returned **20,253 rows across 28 nonempty days**; Image
returned **230 rows across 25 nonempty days**. Neither hit the configured daily
row cap. These are query/page/day rows, not unique URLs or a complete index count.

**Part of:** [`README.md`](README.md), ADR-0003.

## Access and credentials

Use the verified Domain property `sc-domain:forecasteconomy.com` to cover both apex
and `ru.`. `sites` lists the properties actually available to the authorized account;
a URL-prefix property only covers its own prefix. `RUSTATS_GSC_SITE_URL` can override
the default `sc-domain:<public_host>`.

The only requested scope is
`https://www.googleapis.com/auth/webmasters.readonly`. This client cannot submit
sitemaps, request indexing, alter properties or read Gmail. Service accounts are
not implemented. Legacy `RUSTATS_GSC_ACCESS_TOKEN` still works for one-off access,
but expires; persistent access uses `RUSTATS_GSC_CREDENTIALS_FILE` pointing to a
private `authorized_user` JSON with `client_id`, `client_secret`, `refresh_token`
and `scopes: ["https://www.googleapis.com/auth/webmasters.readonly"]`.

Default local credentials path: `~/.config/forecasteconomy/gsc-oauth.json`, mode
`0600`. The backend requires the path to be explicitly configured; the local CLI
uses this default directly. Secrets and exported search data never go into git.
In Docker, mount the file read-only and point `RUSTATS_GSC_CREDENTIALS_FILE` at the
**container** path; setting a laptop file path in Compose does not mount it.

OAuth requires the Search Console API to be enabled in the Google Cloud project
and an existing **Desktop** OAuth client. A Cloud login alone does not grant API
access to Search Console. The user's consent connects that client to their verified
property. External OAuth apps left in Testing can issue refresh tokens that expire
after seven days; project publication status must be checked before promising
unattended long-term access. Revocation and token expiry require authorization again.

## Local authorization and exports

Run from the repo root with the backend virtual environment. Global options go
**before** the subcommand. Never paste client secrets or refresh tokens into chat.

```bash
backend/.venv/bin/python backend/scripts/google-search-console.py authorize \
  --client-secrets /private/path/client_secret_desktop.json \
  --no-open --authorization-url-file /tmp/fe-gsc-auth-url.txt
```

Open the URL in that private file in the owner's browser. The helper generates
state and PKCE S256, listens only on `127.0.0.1` for ten minutes, validates state,
exchanges the code, then atomically saves credentials with mode `0600`. Callback
codes and tokens are not logged. Without `--no-open` it opens the system browser.

```bash
# Verify property permission and renewable credentials.
backend/.venv/bin/python backend/scripts/google-search-console.py sites

# Read submitted sitemap statuses (no submit/write operation).
backend/.venv/bin/python backend/scripts/google-search-console.py \
  --output analytics/gsc/sitemaps.json sitemaps

# Finalized query/page/date data, default 28 days ending three days ago (PT).
backend/.venv/bin/python backend/scripts/google-search-console.py \
  --output analytics/gsc/web.json search

# Image-search performance uses its own file/aggregation.
backend/.venv/bin/python backend/scripts/google-search-console.py \
  --output analytics/gsc/image.json search --type image

# Country/device breakdown, optional explicit date range.
backend/.venv/bin/python backend/scripts/google-search-console.py \
  --output analytics/gsc/country-device.json search \
  --dimensions date,country,device --start 2026-09-01 --end 2026-09-15

# A bounded sample, not an indexing request or a live URL test.
backend/.venv/bin/python backend/scripts/google-search-console.py \
  --output analytics/gsc/inspection.json inspect --urls /private/path/sample-urls.txt
```

## Coverage and storage

- `GET /webmasters/v3/sites`: available properties and permission levels.
- `POST /webmasters/v3/sites/{site}/searchAnalytics/query`: finalized daily search
  performance, 25,000 rows per API page, `startRow` pagination, local cap 50,000
  rows per day. The response records when the cap is reached. Search Console
  exposes top rows and can omit queries; this is **not** a complete inventory of
  indexed pages, and summing query-level rows is not a substitute for property totals.
- The scheduled sync refreshes the last seven days in Google's
  `America/Los_Angeles` timezone, persists only `web/query/page/date` in
  `gsc_search_queries`, and uses the existing uniqueness/upsert rule. Country,
  device and image results are separate exports so incompatible aggregations
  cannot overwrite that table. No schema migration is needed.
- `GET /webmasters/v3/sites/{site}/sitemaps`: read-only submitted sitemap status.
- `POST https://searchconsole.googleapis.com/v1/urlInspection/index:inspect`:
  indexed-version snapshots; the CLI deduplicates and limits each run to 20 URLs
  belonging to the chosen property. Google currently allows 2,000/day/property
  and 600/minute/property. All clients share that quota; the local cap is not a
  global daily ledger. Quota/permission errors stop the run without repeated retries.
- Meta `google-site-verification` remains available through
  `RUSTATS_GOOGLE_SITE_VERIFICATION`; this is separate from API authorization.

Indexing API is not implemented. Domain verification, DNS and publication settings
remain Google/owner configuration; the client does not mutate them. Bing meta
`msvalidate.01` remains `RUSTATS_BING_SITE_VERIFICATION`.

## Official references and verification

- [Native-app OAuth / PKCE / refresh](https://developers.google.com/identity/protocols/oauth2/native-app)
- [Refresh-token expiration](https://developers.google.com/identity/protocols/oauth2#expiration)
- [Search Analytics query](https://developers.google.com/webmaster-tools/v1/searchanalytics/query)
- [Sites list](https://developers.google.com/webmaster-tools/v1/sites/list)
- [Sitemaps list](https://developers.google.com/webmaster-tools/v1/sitemaps/list)
- [Sitemap resource: deprecated indexed field](https://developers.google.com/webmaster-tools/v1/sitemaps)
- [URL Inspection](https://developers.google.com/webmaster-tools/v1/urlInspection.index/inspect)
- [API quotas](https://developers.google.com/webmaster-tools/limits)

Local tests: `backend/.venv/bin/python -m pytest backend/tests/test_gsc_client.py -q`.
Provider acceptance passed locally on 2026-09-21: successful OAuth refresh followed
by real Sites, Sitemaps and web/image Search Analytics exports. URL Inspection is
implemented and unit-tested; it was not called in this initial live acceptance.
