# Traffic platform repair — 2026-09-10

## Evidence and scope

The owner authorized research followed by fixes, GitHub push and production deployment. The goal is 10,000 real daily visitors; this release does not establish that audience or certify production load capacity.

Reporting API, full precision, `ym:s:isRobot=='No'`, June 1–September 9: average daily unique visitors 151.9 / 176.3 / 275.2 / 350.4 for June / July / August / September 1–9; organic daily unique 28.0 / 67.6 / 142.8 / 193.3. Unique visitors over a month must not be divided by days to obtain average DAU. These are provider estimates, not individually verified humans.

775,926 nginx requests over September 8 00:00–September 10 16:18:48 MSK included 345,990 ClaudeBot requests, including 99,750 HTTP 404s. ClaudeBot bulk collection differs from Claude-User (49 requests) and Claude-SearchBot (8). HTTP, JS portraits, Metrika visits and unique people are separate populations.

Confirmed defects: sitemap files mode 0600 inaccessible to nginx; shared EN XML for RU host; missing public world-year PNG rewrite; unbounded disk-hit PNG cache promotion; synchronous image rendering on the ASGI loop; shared temporary PNG file race; Webmaster history/key/pagination parsing; sessions used as a proxy for the people target; initial/dwell-generated input attention; world-year RU metadata omitted country.

## Implementation

- Explicit training/archive agents ClaudeBot/GPTBot/meta-externalagent/CCBot: robots Disallow and edge 403 except robots.txt. Search and user fetchers retain access in nginx and scrape_guard. UA policy is not IP authentication.
- Sitemap: complete host-specific generations, 0644 XML/gzip, 0755 directories, nonblocking process lock, atomic current pointer, previous generation retained. API index uses the published manifest. Empty/failed builds do not replace a good generation.
- OG: canonical and legacy world-year routing; cache bounded by 600 entries AND 64 MiB; unique temporary files plus atomic replace. One off-loop render thread and four outstanding jobs per process, 503/Retry-After on saturation.
- Webmaster: actual history and HTTP fields, recursive child sitemap pagination, NULL for absent values, seven-day backfill, both-host alerting and provider freshness.
- Analytics: daily unique browser identities separate from sessions and period unique identities. Unknown sessions are not classified as certain humans. Reconciliation no longer tunes bot weights to a different population.
- Attention version 2: input-backed active_ms requires trusted input in a focused visible document. Passive visible_ms is recorded separately. Old attention cannot be reconstructed from historical aggregate payloads.
- Search intent: country in RU world-year titles; Bank of Russia key rate in shared EN copy; correct Russian monthly link grammar.

## Interpretation and remaining work

Changes in bot classification or attention are measurement changes, not user growth. Retrospective rows may use older classification. Do not use a pre/post jump in this metric as evidence of SEO uplift.

Demand exists: Yandex impressions grew from 10,272 in June to 177,956 in August. Most observed organic landings still concern Russian macro indicators. Expansion of URL inventory alone did not establish proportional demand. Compare fixed query/page cohorts, device, host and weekday over 28 complete days before/after; sitewide deployment alone is not a randomized causal experiment.

Current budget data ends June 2026. ETL recently used `artifact://fedbud_month.csv`; the official Minfin catalog returned 503 during investigation. This is a fallback freshness limitation, not proof that the source has no newer data. Preliminary cumulative press releases must not silently replace monthly observations.

GSC access token is absent in the available settings; Google index coverage remains unverified. Do not infer zero Google traffic from this.

Capacity planning assumption: 10k DAU × 1.3 sessions/person × 15% in peak hour × 20 dynamic requests/session ≈10.8 dynamic requests/sec, plus crawlers/background jobs. This is a scenario, not a measured capacity certificate. Renderer concurrency tests establish boundedness and loop responsiveness; they do not substitute for a full mixed-production workload test.

## Acceptance

Run `./scripts/check-all.sh` and `python3 scripts/test-crawler-routing.py`. Deploy using `scripts/deploy.sh` with the approved runtime commit and approval-only wrapper. Run `build_static_sitemaps()` in the backend container; verify every manifest section on both public hosts, host-correct loc, gzip, and repeated publication. Verify training403/robots200/search200, public PNG and landing metadata, readiness and current frontend assets. Run Webmaster sync with `alert=False` for manual verification so the audit does not send messages.

Historical sessionize has no upper bound: do not loop dates and call it a bounded rebuild. Use the conservative known-crawler repair if a historical correction is needed.
