# Backend mechanism inventory

Независимый синтаксический состав из Git tracked/index исходников. Это знаменатель сверки; смысл и приёмка — в [backend acceptance](code-review/backend-mechanism-acceptance-2026-09-30.md).

Полный машинный состав, поля, зависимости, ветвления и выражения — [mechanism-inventory.json](mechanism-inventory.json). Журнал reviews не является входом генератора.

- HTTP declarations: **144**
- HTTP reachable paths: **144**
- ORM tables: **57**
- DTO schemas (own fields + resolved inherited bases): **27**
- Settings fields: **160**
- Settings reads: **390**
- Direct environment reads: **29**
- Jobs: **39**
- Middleware: **5**
- Registry declarations: **843**
- Registry references: **1602**
- Migration operations: **348**
- Candidate effects: **1933**
- Unresolved syntax: **0**
- MCP tools: **7**

## Routes

| Methods | Path | Handler | Source |
| --- | --- | --- | --- |
| GET | /api/v1/indicators | app.api.indicators.list_indicators | [backend/app/api/indicators.py:149](../backend/app/api/indicators.py#L149) |
| GET | /api/v1/indicators/{code} | app.api.indicators.get_indicator | [backend/app/api/indicators.py:308](../backend/app/api/indicators.py#L308) |
| GET | /api/v1/indicators/{code}/data | app.api.indicators.get_indicator_data | [backend/app/api/indicators.py:409](../backend/app/api/indicators.py#L409) |
| GET | /api/v1/indicators/{code}/stats | app.api.indicators.get_indicator_stats | [backend/app/api/indicators.py:456](../backend/app/api/indicators.py#L456) |
| GET | /api/v1/indicators/{code}/forecast | app.api.forecasts.get_forecast | [backend/app/api/forecasts.py:62](../backend/app/api/forecasts.py#L62) |
| GET | /api/v1/indicators/{code}/inflation | app.api.forecasts.get_inflation | [backend/app/api/forecasts.py:135](../backend/app/api/forecasts.py#L135) |
| GET | /api/v1/health | app.api.system.health | [backend/app/api/system.py:30](../backend/app/api/system.py#L30) |
| GET | /api/v1/health/live | app.api.system.health | [backend/app/api/system.py:31](../backend/app/api/system.py#L31) |
| POST | /api/v1/scrape-challenge | app.api.system.scrape_challenge | [backend/app/api/system.py:37](../backend/app/api/system.py#L37) |
| GET | /api/v1/health/ready | app.api.system.health_ready | [backend/app/api/system.py:74](../backend/app/api/system.py#L74) |
| GET | /api/v1/metrics | app.api.system.prometheus_metrics | [backend/app/api/system.py:182](../backend/app/api/system.py#L182) |
| GET | /api/v1/system/status | app.api.system.system_status | [backend/app/api/system.py:298](../backend/app/api/system.py#L298) |
| GET | /api/v1/calendar | app.api.calendar.list_events | [backend/app/api/calendar.py:88](../backend/app/api/calendar.py#L88) |
| GET | /api/v1/calendar/upcoming | app.api.calendar.upcoming_events | [backend/app/api/calendar.py:151](../backend/app/api/calendar.py#L151) |
| GET | /api/v1/calendar/{event_id} | app.api.calendar.get_event | [backend/app/api/calendar.py:185](../backend/app/api/calendar.py#L185) |
| GET | /api/v1/calendar/export/ical | app.api.calendar.export_ical | [backend/app/api/calendar.py:213](../backend/app/api/calendar.py#L213) |
| GET | /api/v1/embed/spark/{code}.svg | app.api.embed.sparkline_svg | [backend/app/api/embed.py:155](../backend/app/api/embed.py#L155) |
| GET | /api/v1/embed/card/{code}.svg | app.api.embed.card_svg | [backend/app/api/embed.py:221](../backend/app/api/embed.py#L221) |
| GET | /api/v1/embed/badge/{code}.svg | app.api.embed.badge_svg | [backend/app/api/embed.py:337](../backend/app/api/embed.py#L337) |
| POST | /api/v1/embed/impression | app.api.embed.track_impression | [backend/app/api/embed.py:448](../backend/app/api/embed.py#L448) |
| GET | /api/v1/embed/pixel.gif | app.api.embed.tracking_pixel | [backend/app/api/embed.py:466](../backend/app/api/embed.py#L466) |
| GET | /api/v1/dashboard/coverage | app.api.dashboard.dashboard_coverage | [backend/app/api/dashboard.py:38](../backend/app/api/dashboard.py#L38) |
| GET | /api/v1/dashboard/sparklines | app.api.dashboard.dashboard_sparklines | [backend/app/api/dashboard.py:135](../backend/app/api/dashboard.py#L135) |
| GET | /api/v1/demographics/structure | app.api.demographics.age_structure | [backend/app/api/demographics.py:10](../backend/app/api/demographics.py#L10) |
| GET | /api/v1/analytics/health | app.api.analytics.analytics_health | [backend/app/api/analytics.py:100](../backend/app/api/analytics.py#L100) |
| POST | /api/v1/analytics/query/metrika | app.api.analytics.query_metrika | [backend/app/api/analytics.py:131](../backend/app/api/analytics.py#L131) |
| GET | /api/v1/analytics/pages | app.api.analytics.analytics_pages | [backend/app/api/analytics.py:153](../backend/app/api/analytics.py#L153) |
| GET | /api/v1/analytics/search-phrases | app.api.analytics.analytics_search_phrases | [backend/app/api/analytics.py:163](../backend/app/api/analytics.py#L163) |
| GET | /api/v1/analytics/anomalies | app.api.analytics.analytics_anomalies | [backend/app/api/analytics.py:173](../backend/app/api/analytics.py#L173) |
| GET | /api/v1/analytics/deploy-impact | app.api.analytics.analytics_deploy_impact | [backend/app/api/analytics.py:179](../backend/app/api/analytics.py#L179) |
| GET | /api/v1/analytics/experiments/bootstrap | app.api.analytics.experiments_bootstrap | [backend/app/api/analytics.py:184](../backend/app/api/analytics.py#L184) |
| POST | /api/v1/analytics/actions/propose | app.api.analytics.propose_action | [backend/app/api/analytics.py:205](../backend/app/api/analytics.py#L205) |
| POST | /api/v1/analytics/actions/{action_id}/apply | app.api.analytics.apply_action | [backend/app/api/analytics.py:230](../backend/app/api/analytics.py#L230) |
| POST | /api/v1/analytics/events | app.api.analytics.collect_event | [backend/app/api/analytics.py:258](../backend/app/api/analytics.py#L258) |
| POST | /api/v1/analytics/behavior | app.api.analytics.collect_behavior_batch | [backend/app/api/analytics.py:558](../backend/app/api/analytics.py#L558) |
| GET | /api/v1/ticker/live | app.api.ticker.get_live_ticker | [backend/app/api/ticker.py:83](../backend/app/api/ticker.py#L83) |
| POST | /api/v1/auth/register | app.api.auth.register | [backend/app/api/auth.py:117](../backend/app/api/auth.py#L117) |
| POST | /api/v1/auth/login | app.api.auth.login | [backend/app/api/auth.py:165](../backend/app/api/auth.py#L165) |
| POST | /api/v1/auth/logout | app.api.auth.logout | [backend/app/api/auth.py:208](../backend/app/api/auth.py#L208) |
| GET | /api/v1/auth/me | app.api.auth.me | [backend/app/api/auth.py:216](../backend/app/api/auth.py#L216) |
| POST | /api/v1/auth/set-password | app.api.auth.set_password | [backend/app/api/auth.py:251](../backend/app/api/auth.py#L251) |
| DELETE | /api/v1/auth/identities/{identity_id} | app.api.auth.unlink_identity | [backend/app/api/auth.py:289](../backend/app/api/auth.py#L289) |
| POST | /api/v1/auth/logout-all | app.api.auth.logout_all | [backend/app/api/auth.py:311](../backend/app/api/auth.py#L311) |
| POST | /api/v1/auth/feedback | app.api.auth.submit_feedback | [backend/app/api/auth.py:357](../backend/app/api/auth.py#L357) |
| PATCH | /api/v1/auth/account/profile | app.api.auth.update_profile | [backend/app/api/auth.py:388](../backend/app/api/auth.py#L388) |
| POST | /api/v1/auth/account/newsletter | app.api.auth.update_newsletter | [backend/app/api/auth.py:401](../backend/app/api/auth.py#L401) |
| GET | /api/v1/auth/account/export | app.api.auth.export_account | [backend/app/api/auth.py:417](../backend/app/api/auth.py#L417) |
| DELETE | /api/v1/auth/account | app.api.auth.delete_account | [backend/app/api/auth.py:442](../backend/app/api/auth.py#L442) |
| GET | /api/v1/auth/oauth/providers | app.api.oauth.oauth_providers | [backend/app/api/oauth.py:254](../backend/app/api/oauth.py#L254) |
| GET | /api/v1/auth/oauth/{provider}/start | app.api.oauth.oauth_start | [backend/app/api/oauth.py:260](../backend/app/api/oauth.py#L260) |
| GET | /api/v1/auth/oauth/fake/authorize | app.api.oauth.fake_authorize | [backend/app/api/oauth.py:346](../backend/app/api/oauth.py#L346) |
| GET | /api/v1/auth/oauth/{provider}/callback | app.api.oauth.oauth_callback | [backend/app/api/oauth.py:363](../backend/app/api/oauth.py#L363) |
| GET | /api/v1/export/quota | app.api.export.export_quota | [backend/app/api/export.py:289](../backend/app/api/export.py#L289) |
| POST | /api/v1/export/table | app.api.export.export_table | [backend/app/api/export.py:307](../backend/app/api/export.py#L307) |
| GET | /api/v1/regions | app.api.regions.regions_landing | [backend/app/api/regions.py:131](../backend/app/api/regions.py#L131) |
| GET | /api/v1/regions/catalog | app.api.regions.regions_catalog | [backend/app/api/regions.py:206](../backend/app/api/regions.py#L206) |
| GET | /api/v1/regions/heatmap/{code} | app.api.regions.regions_heatmap | [backend/app/api/regions.py:239](../backend/app/api/regions.py#L239) |
| GET | /api/v1/regions/heatmap-series/{code} | app.api.regions.regions_heatmap_series | [backend/app/api/regions.py:292](../backend/app/api/regions.py#L292) |
| GET | /api/v1/regions/vs/{slug_a}/{slug_b} | app.api.regions.regions_compare | [backend/app/api/regions.py:345](../backend/app/api/regions.py#L345) |
| GET | /api/v1/regions/{slug} | app.api.regions.region_profile | [backend/app/api/regions.py:363](../backend/app/api/regions.py#L363) |
| GET | /api/v1/regions/{slug}/i/{code} | app.api.regions.region_indicator_detail | [backend/app/api/regions.py:464](../backend/app/api/regions.py#L464) |
| GET | /api/v1/regions/{slug}/i/{code}/monthly | app.api.regions.region_indicator_monthly | [backend/app/api/regions.py:575](../backend/app/api/regions.py#L575) |
| GET | /api/v1/admin/bi/dashboard | app.api.admin_bi.bi_dashboard | [backend/app/api/admin_bi.py:216](../backend/app/api/admin_bi.py#L216) |
| GET | /api/v1/admin/bi/slices/meta | app.api.admin_bi.slices_meta | [backend/app/api/admin_bi.py:275](../backend/app/api/admin_bi.py#L275) |
| GET | /api/v1/admin/bi/slices | app.api.admin_bi.slices_query | [backend/app/api/admin_bi.py:299](../backend/app/api/admin_bi.py#L299) |
| GET | /api/v1/world/countries | app.api.world.list_countries | [backend/app/api/world.py:870](../backend/app/api/world.py#L870) |
| GET | /api/v1/world/rating/concepts | app.api.world.world_rating_concepts | [backend/app/api/world.py:971](../backend/app/api/world.py#L971) |
| GET | /api/v1/world/compare/catalog | app.api.world.world_compare_catalog | [backend/app/api/world.py:1003](../backend/app/api/world.py#L1003) |
| GET | /api/v1/world/compare/series/{country_slug}/{concept_slug} | app.api.world.world_compare_series | [backend/app/api/world.py:1161](../backend/app/api/world.py#L1161) |
| GET | /api/v1/world/compare/snapshot/{concept_slug} | app.api.world.world_compare_snapshot | [backend/app/api/world.py:1218](../backend/app/api/world.py#L1218) |
| GET | /api/v1/world/compare/map-series/{concept_slug} | app.api.world.world_compare_map_series | [backend/app/api/world.py:1305](../backend/app/api/world.py#L1305) |
| GET | /api/v1/world/compare/average/{concept_slug} | app.api.world.world_compare_average_series | [backend/app/api/world.py:1397](../backend/app/api/world.py#L1397) |
| GET | /api/v1/world/countries/{slug} | app.api.world.country_detail | [backend/app/api/world.py:1560](../backend/app/api/world.py#L1560) |
| GET | /api/v1/world/indicators/{slug}/{code} | app.api.world.indicator_meta | [backend/app/api/world.py:1879](../backend/app/api/world.py#L1879) |
| GET | /api/v1/world/indicators/{slug}/{code}/data | app.api.world.indicator_data | [backend/app/api/world.py:2113](../backend/app/api/world.py#L2113) |
| GET | /api/v1/world/search | app.api.world.search_world | [backend/app/api/world.py:2322](../backend/app/api/world.py#L2322) |
| GET | /api/v1/world/{country_slug}/regions | app.api.world_subnational.list_regions | [backend/app/api/world_subnational.py:170](../backend/app/api/world_subnational.py#L170) |
| GET | /api/v1/world/{country_slug}/regions/map/{code} | app.api.world_subnational.map_values | [backend/app/api/world_subnational.py:246](../backend/app/api/world_subnational.py#L246) |
| GET | /api/v1/world/{country_slug}/regions/region/{slug} | app.api.world_subnational.region_profile | [backend/app/api/world_subnational.py:344](../backend/app/api/world_subnational.py#L344) |
| GET | /api/v1/world/{country_slug}/regions/region/{slug}/{code} | app.api.world_subnational.region_indicator | [backend/app/api/world_subnational.py:454](../backend/app/api/world_subnational.py#L454) |
| GET | /api/v1/world/{country_slug}/regions/region/{slug}/{code}/forecast | app.api.world_subnational.region_indicator_forecast | [backend/app/api/world_subnational.py:591](../backend/app/api/world_subnational.py#L591) |
| GET | /api/auth/{provider}/start | app.api.oauth.oauth_start | [backend/app/api/oauth.py:475](../backend/app/api/oauth.py#L475) |
| GET | /api/auth/{provider}/callback | app.api.oauth.oauth_callback | [backend/app/api/oauth.py:476](../backend/app/api/oauth.py#L476) |
| GET/HEAD | /sitemap.xml | app.api.sitemap.sitemap_index | [backend/app/api/sitemap.py:271](../backend/app/api/sitemap.py#L271) |
| GET/HEAD | /sitemap-{section}.xml | app.api.sitemap.sitemap_section | [backend/app/api/sitemap.py:325](../backend/app/api/sitemap.py#L325) |
| GET/HEAD | /sitemap-stats.json | app.api.sitemap.sitemap_stats | [backend/app/api/sitemap.py:476](../backend/app/api/sitemap.py#L476) |
| GET/HEAD | /robots.txt | app.api.sitemap.robots_txt | [backend/app/api/sitemap.py:496](../backend/app/api/sitemap.py#L496) |
| GET/HEAD | /llms.txt | app.api.sitemap.llms_txt | [backend/app/api/sitemap.py:511](../backend/app/api/sitemap.py#L511) |
| GET/HEAD | /feed.xml | app.api.sitemap.rss_feed | [backend/app/api/sitemap.py:526](../backend/app/api/sitemap.py#L526) |
| GET | /api/v1/og-image/indicator/{code}.png | app.api.sitemap.og_image_indicator | [backend/app/api/sitemap.py:639](../backend/app/api/sitemap.py#L639) |
| GET | /api/v1/og-image/indicator/{code}/{period}.png | app.api.sitemap.og_image_indicator_month | [backend/app/api/sitemap.py:724](../backend/app/api/sitemap.py#L724) |
| GET | /api/v1/og-image/indicator/{code}/{year}.png | app.api.sitemap.og_image_indicator_year | [backend/app/api/sitemap.py:843](../backend/app/api/sitemap.py#L843) |
| GET | /api/v1/og-image/region/{slug}/{code}.png | app.api.sitemap.og_image_region_indicator | [backend/app/api/sitemap.py:984](../backend/app/api/sitemap.py#L984) |
| GET | /api/v1/og-image/region/{slug}/{code}/{year}.png | app.api.sitemap.og_image_region_indicator_year | [backend/app/api/sitemap.py:1093](../backend/app/api/sitemap.py#L1093) |
| GET | /api/v1/og-image/region-rating/{code}.png | app.api.sitemap.og_image_region_rating | [backend/app/api/sitemap.py:1199](../backend/app/api/sitemap.py#L1199) |
| GET | /api/v1/og-image/today.png | app.api.sitemap.og_image_today_hub | [backend/app/api/sitemap.py:1277](../backend/app/api/sitemap.py#L1277) |
| GET | /api/v1/og-image/region-vs/{slug_a}-vs-{slug_b}.png | app.api.sitemap.og_image_region_vs | [backend/app/api/sitemap.py:1320](../backend/app/api/sitemap.py#L1320) |
| GET | /api/v1/og-image/world-vs/{slug_a}-vs-{slug_b}/{concept_slug}.png | app.api.sitemap.og_image_world_vs | [backend/app/api/sitemap.py:1394](../backend/app/api/sitemap.py#L1394) |
| GET | /api/v1/og-image/world/{slug}.png | app.api.sitemap.og_image_world_country | [backend/app/api/sitemap.py:1542](../backend/app/api/sitemap.py#L1542) |
| GET | /api/v1/og-image/world-rating/{concept_slug}.png | app.api.sitemap.og_image_world_rating | [backend/app/api/sitemap.py:1674](../backend/app/api/sitemap.py#L1674) |
| GET | /api/v1/og-image/world-rating/{concept_slug}/{year}.png | app.api.sitemap.og_image_world_rating_year | [backend/app/api/sitemap.py:1729](../backend/app/api/sitemap.py#L1729) |
| GET | /api/v1/og-image/world/{slug}/{code}.png | app.api.sitemap.og_image_world_indicator | [backend/app/api/sitemap.py:1796](../backend/app/api/sitemap.py#L1796) |
| GET | /api/v1/og-image/world/{country_slug}/{code}/{year}.png | app.api.sitemap.og_image_world_indicator_year | [backend/app/api/sitemap.py:1890](../backend/app/api/sitemap.py#L1890) |
| GET | /api/v1/og-image/world-region-vs/{country}/{slug_a}-vs-{slug_b}.png | app.api.sitemap.og_image_world_region_vs | [backend/app/api/sitemap.py:2049](../backend/app/api/sitemap.py#L2049) |
| GET | /api/v1/og-image/world-region/{country}/{region}/{indicator}/{year}.png | app.api.sitemap.og_image_world_region_indicator_year | [backend/app/api/sitemap.py:2121](../backend/app/api/sitemap.py#L2121) |
| GET | /api/v1/og-image/world-region/{country}/{region}/{indicator}.png | app.api.sitemap.og_image_world_region_indicator | [backend/app/api/sitemap.py:2201](../backend/app/api/sitemap.py#L2201) |
| GET | /api/v1/og-image/world-region/{country}/{region}.png | app.api.sitemap.og_image_world_region_profile | [backend/app/api/sitemap.py:2287](../backend/app/api/sitemap.py#L2287) |
| GET | /api/v1/og-image/world-regions/{country}.png | app.api.sitemap.og_image_world_regions_hub | [backend/app/api/sitemap.py:2423](../backend/app/api/sitemap.py#L2423) |
| GET | /api/v1/og/indicator/{code} | app.api.sitemap.og_indicator | [backend/app/api/sitemap.py:2529](../backend/app/api/sitemap.py#L2529) |
| GET | /api/v1/og/category/{slug} | app.api.sitemap.og_category | [backend/app/api/sitemap.py:2536](../backend/app/api/sitemap.py#L2536) |
| GET | /api/v1/og/page/{page} | app.api.sitemap.og_page | [backend/app/api/sitemap.py:2543](../backend/app/api/sitemap.py#L2543) |
| GET | /api/v1/og-image/demographics.png | app.api.sitemap.og_image_demographics | [backend/app/api/sitemap.py:2552](../backend/app/api/sitemap.py#L2552) |
| GET/HEAD | /seo/not-found | app.api.seo_pages.seo_not_found | [backend/app/api/seo_pages.py:296](../backend/app/api/seo_pages.py#L296) |
| GET/HEAD | /seo/page/home | app.api.seo_pages.seo_home | [backend/app/api/seo_pages.py:302](../backend/app/api/seo_pages.py#L302) |
| GET/HEAD | /seo/page/{page} | app.api.seo_pages.seo_page | [backend/app/api/seo_pages.py:314](../backend/app/api/seo_pages.py#L314) |
| GET/HEAD | /seo/category | app.api.seo_pages.seo_categories_hub | [backend/app/api/seo_pages.py:324](../backend/app/api/seo_pages.py#L324) |
| GET/HEAD | /seo/category/{slug} | app.api.seo_pages.seo_category | [backend/app/api/seo_pages.py:330](../backend/app/api/seo_pages.py#L330) |
| GET/HEAD | /seo/indicator/{code} | app.api.seo_pages.seo_indicator | [backend/app/api/seo_pages.py:339](../backend/app/api/seo_pages.py#L339) |
| GET/HEAD | /seo/regions | app.api.seo_pages.seo_regions | [backend/app/api/seo_pages.py:371](../backend/app/api/seo_pages.py#L371) |
| GET/HEAD | /seo/regions/map/{code} | app.api.seo_pages.seo_regions_map | [backend/app/api/seo_pages.py:387](../backend/app/api/seo_pages.py#L387) |
| GET/HEAD | /seo/region/{slug} | app.api.seo_pages.seo_region | [backend/app/api/seo_pages.py:414](../backend/app/api/seo_pages.py#L414) |
| GET/HEAD | /seo/region/{slug}/{code} | app.api.seo_pages.seo_region_indicator | [backend/app/api/seo_pages.py:428](../backend/app/api/seo_pages.py#L428) |
| GET/HEAD | /seo/region-rating | app.api.seo_pages.seo_region_ratings_hub | [backend/app/api/seo_pages.py:444](../backend/app/api/seo_pages.py#L444) |
| GET/HEAD | /seo/region-rating/{code} | app.api.seo_pages.seo_region_rating | [backend/app/api/seo_pages.py:454](../backend/app/api/seo_pages.py#L454) |
| GET/HEAD | /seo/region-vs/{slug_a}-vs-{slug_b} | app.api.seo_pages.seo_region_vs | [backend/app/api/seo_pages.py:464](../backend/app/api/seo_pages.py#L464) |
| GET/HEAD | /seo/today | app.api.seo_pages.seo_today_hub | [backend/app/api/seo_pages.py:476](../backend/app/api/seo_pages.py#L476) |
| GET/HEAD | /seo/today/{code} | app.api.seo_pages.seo_today_indicator | [backend/app/api/seo_pages.py:482](../backend/app/api/seo_pages.py#L482) |
| GET/HEAD | /seo/calendar-month/{year}/{month} | app.api.seo_pages.seo_calendar_month | [backend/app/api/seo_pages.py:494](../backend/app/api/seo_pages.py#L494) |
| GET/HEAD | /seo/indicator-year/{code}/{year} | app.api.seo_pages.seo_indicator_year | [backend/app/api/seo_pages.py:502](../backend/app/api/seo_pages.py#L502) |
| GET/HEAD | /seo/indicator-month/{code}/{period} | app.api.seo_pages.seo_indicator_month | [backend/app/api/seo_pages.py:537](../backend/app/api/seo_pages.py#L537) |
| GET/HEAD | /seo/world | app.api.seo_pages.seo_world_home | [backend/app/api/seo_pages.py:559](../backend/app/api/seo_pages.py#L559) |
| GET/HEAD | /seo/world/rating | app.api.seo_pages.seo_world_rating_default | [backend/app/api/seo_pages.py:569](../backend/app/api/seo_pages.py#L569) |
| GET/HEAD | /seo/world/rating/{concept_slug} | app.api.seo_pages.seo_world_rating | [backend/app/api/seo_pages.py:589](../backend/app/api/seo_pages.py#L589) |
| GET/HEAD | /seo/world/rating/{concept_slug}/{year} | app.api.seo_pages.seo_world_rating_year | [backend/app/api/seo_pages.py:627](../backend/app/api/seo_pages.py#L627) |
| GET/HEAD | /seo/world/{slug}/regions | app.api.seo_pages.seo_world_subnational_hub | [backend/app/api/seo_pages.py:653](../backend/app/api/seo_pages.py#L653) |
| GET/HEAD | /seo/world/{slug}/region-vs/{slug_a}-vs-{slug_b} | app.api.seo_pages.seo_world_subnational_compare | [backend/app/api/seo_pages.py:665](../backend/app/api/seo_pages.py#L665) |
| GET/HEAD | /seo/world/{slug}/region/{region_slug}/{code}/{year} | app.api.seo_pages.seo_world_subnational_indicator_year | [backend/app/api/seo_pages.py:687](../backend/app/api/seo_pages.py#L687) |
| GET/HEAD | /seo/world/{slug}/region/{region_slug}/{code} | app.api.seo_pages.seo_world_subnational_indicator | [backend/app/api/seo_pages.py:707](../backend/app/api/seo_pages.py#L707) |
| GET/HEAD | /seo/world/{slug}/region/{region_slug} | app.api.seo_pages.seo_world_subnational_region | [backend/app/api/seo_pages.py:725](../backend/app/api/seo_pages.py#L725) |
| GET/HEAD | /seo/world/{slug} | app.api.seo_pages.seo_world_country | [backend/app/api/seo_pages.py:740](../backend/app/api/seo_pages.py#L740) |
| GET/HEAD | /seo/world/{slug}/{code} | app.api.seo_pages.seo_world_indicator | [backend/app/api/seo_pages.py:754](../backend/app/api/seo_pages.py#L754) |
| GET/HEAD | /seo/world-indicator-year/{slug}/{code}/{year} | app.api.seo_pages.seo_world_indicator_year | [backend/app/api/seo_pages.py:788](../backend/app/api/seo_pages.py#L788) |
| GET/HEAD | /seo/world-vs/{pair}/{concept} | app.api.seo_pages.seo_world_vs | [backend/app/api/seo_pages.py:821](../backend/app/api/seo_pages.py#L821) |
| GET/HEAD | /seo/region-indicator-year/{slug}/{code}/{year} | app.api.seo_pages.seo_region_indicator_year | [backend/app/api/seo_pages.py:854](../backend/app/api/seo_pages.py#L854) |

## Middleware registration (last registered is outermost custom layer)

| Order | Class | Source |
| --- | --- | --- |
| 1 | app.main.RateLimitMiddleware | [backend/app/main.py:1625](../backend/app/main.py#L1625) |
| 2 | app.main.HttpStatusCounterMiddleware | [backend/app/main.py:1626](../backend/app/main.py#L1626) |
| 3 | app.main.ScrapeGuardMiddleware | [backend/app/main.py:1627](../backend/app/main.py#L1627) |
| 4 | fastapi.middleware.cors.CORSMiddleware | [backend/app/main.py:1628](../backend/app/main.py#L1628) |
| 5 | app.main.LocaleMiddleware | [backend/app/main.py:1644](../backend/app/main.py#L1644) |

## Table `indicators`

| Python / SQL | Type | Nullable | Column arguments / options | Source |
| --- | --- | --- | --- | --- |
| id / id | Mapped[int] | False | [] {'primary_key': 'True'} | [backend/app/models.py:25](../backend/app/models.py#L25) |
| code / code | Mapped[str] | False | ['String(50)'] {'unique': 'True', 'nullable': 'False', 'index': 'True'} | [backend/app/models.py:26](../backend/app/models.py#L26) |
| name / name | Mapped[str] | False | ['String(200)'] {'nullable': 'False'} | [backend/app/models.py:27](../backend/app/models.py#L27) |
| name_en / name_en | Mapped[str \| None] | True | ['String(200)'] {} | [backend/app/models.py:28](../backend/app/models.py#L28) |
| unit / unit | Mapped[str] | False | ['String(20)'] {'nullable': 'False', 'default': "'%'"} | [backend/app/models.py:29](../backend/app/models.py#L29) |
| frequency / frequency | Mapped[str] | False | ['String(50)'] {'nullable': 'False', 'default': "'monthly'"} | [backend/app/models.py:30](../backend/app/models.py#L30) |
| source / source | Mapped[str] | False | ['String(100)'] {'nullable': 'False', 'default': "'Росстат'"} | [backend/app/models.py:31](../backend/app/models.py#L31) |
| source_url / source_url | Mapped[str \| None] | True | ['String(500)'] {} | [backend/app/models.py:32](../backend/app/models.py#L32) |
| description / description | Mapped[str \| None] | True | ['Text'] {} | [backend/app/models.py:33](../backend/app/models.py#L33) |
| methodology / methodology | Mapped[str \| None] | True | ['Text'] {} | [backend/app/models.py:34](../backend/app/models.py#L34) |
| parser_type / parser_type | Mapped[str] | False | ['String(50)'] {'nullable': 'False', 'default': "'rosstat_cpi_xlsx'"} | [backend/app/models.py:35](../backend/app/models.py#L35) |
| model_config_json / model_config | Mapped[dict \| None] | True | ["'model_config'", 'JSON'] {} | [backend/app/models.py:36](../backend/app/models.py#L36) |
| is_active / is_active | Mapped[bool] | False | ['Boolean'] {'default': 'True'} | [backend/app/models.py:37](../backend/app/models.py#L37) |
| category / category | Mapped[str \| None] | True | ['String(100)'] {} | [backend/app/models.py:38](../backend/app/models.py#L38) |
| excel_sheet / excel_sheet | Mapped[str \| None] | True | ['String(10)'] {} | [backend/app/models.py:39](../backend/app/models.py#L39) |
| seo_title / seo_title | Mapped[str \| None] | True | ['String(300)'] {} | [backend/app/models.py:40](../backend/app/models.py#L40) |
| seo_description / seo_description | Mapped[str \| None] | True | ['Text'] {} | [backend/app/models.py:41](../backend/app/models.py#L41) |
| seo_keywords / seo_keywords | Mapped[str \| None] | True | ['Text'] {} | [backend/app/models.py:42](../backend/app/models.py#L42) |
| seo_blocks / seo_blocks | Mapped[list \| None] | True | ['JSON'] {} | [backend/app/models.py:43](../backend/app/models.py#L43) |
| is_listed / is_listed | Mapped[bool] | False | ['Boolean'] {'nullable': 'False', 'default': 'True', 'server_default': "'true'"} | [backend/app/models.py:44](../backend/app/models.py#L44) |
| created_at / created_at | Mapped[datetime] | False | ['DateTime'] {'default': 'lambda: datetime.now(timezone.utc).replace(tzinfo=None)'} | [backend/app/models.py:45](../backend/app/models.py#L45) |
| updated_at / updated_at | Mapped[datetime] | False | ['DateTime'] {'default': 'lambda: datetime.now(timezone.utc).replace(tzinfo=None)', 'onupdate': 'lambda: datetime.now(timezone.utc).replace(tzinfo=None)'} | [backend/app/models.py:46](../backend/app/models.py#L46) |

Constraints: `[{'path': 'backend/app/models.py', 'line': 23, 'end_line': 23, 'owner': 'Indicator', 'conditions': [], 'definition': "(Index('ix_indicators_category', 'category'),)"}]`

Relationships: `[{'path': 'backend/app/models.py', 'line': 48, 'end_line': 48, 'owner': 'Indicator', 'conditions': [], 'attribute': 'data_points', 'annotation': "Mapped[list['IndicatorData']]", 'definition': "relationship(back_populates='indicator', cascade='all, delete-orphan')"}, {'path': 'backend/app/models.py', 'line': 49, 'end_line': 49, 'owner': 'Indicator', 'conditions': [], 'attribute': 'forecasts', 'annotation': "Mapped[list['Forecast']]", 'definition': "relationship(back_populates='indicator', cascade='all, delete-orphan')"}, {'path': 'backend/app/models.py', 'line': 50, 'end_line': 50, 'owner': 'Indicator', 'conditions': [], 'attribute': 'fetch_logs', 'annotation': "Mapped[list['FetchLog']]", 'definition': "relationship(back_populates='indicator', cascade='all, delete-orphan')"}]`

## Table `indicator_data`

| Python / SQL | Type | Nullable | Column arguments / options | Source |
| --- | --- | --- | --- | --- |
| id / id | Mapped[int] | False | [] {'primary_key': 'True'} | [backend/app/models.py:60](../backend/app/models.py#L60) |
| indicator_id / indicator_id | Mapped[int] | False | ["ForeignKey('indicators.id', ondelete='CASCADE')"] {'nullable': 'False'} | [backend/app/models.py:61](../backend/app/models.py#L61) |
| date / date | Mapped[date] | False | ['Date'] {'nullable': 'False'} | [backend/app/models.py:62](../backend/app/models.py#L62) |
| value / value | Mapped[float] | False | ['Numeric(12, 4)'] {'nullable': 'False'} | [backend/app/models.py:63](../backend/app/models.py#L63) |
| created_at / created_at | Mapped[datetime] | False | ['DateTime'] {'default': 'lambda: datetime.now(timezone.utc).replace(tzinfo=None)'} | [backend/app/models.py:64](../backend/app/models.py#L64) |

Constraints: `[{'path': 'backend/app/models.py', 'line': 55, 'end_line': 58, 'owner': 'IndicatorData', 'conditions': [], 'definition': "(UniqueConstraint('indicator_id', 'date', name='uq_indicator_date'), Index('ix_indicator_data_lookup', 'indicator_id', 'date'))"}]`

Relationships: `[{'path': 'backend/app/models.py', 'line': 66, 'end_line': 66, 'owner': 'IndicatorData', 'conditions': [], 'attribute': 'indicator', 'annotation': "Mapped['Indicator']", 'definition': "relationship(back_populates='data_points')"}]`

## Table `regions`

| Python / SQL | Type | Nullable | Column arguments / options | Source |
| --- | --- | --- | --- | --- |
| id / id | Mapped[int] | False | [] {'primary_key': 'True'} | [backend/app/models.py:80](../backend/app/models.py#L80) |
| slug / slug | Mapped[str] | False | ['String(80)'] {'unique': 'True', 'nullable': 'False', 'index': 'True'} | [backend/app/models.py:81](../backend/app/models.py#L81) |
| name / name | Mapped[str] | False | ['String(150)'] {'nullable': 'False'} | [backend/app/models.py:82](../backend/app/models.py#L82) |
| kind / kind | Mapped[str] | False | ['String(20)'] {'nullable': 'False', 'default': "'region'"} | [backend/app/models.py:84](../backend/app/models.py#L84) |
| district_slug / district_slug | Mapped[str \| None] | True | ['String(80)'] {'index': 'True'} | [backend/app/models.py:85](../backend/app/models.py#L85) |
| sort_order / sort_order | Mapped[int] | False | ['Integer'] {'nullable': 'False', 'default': '0'} | [backend/app/models.py:86](../backend/app/models.py#L86) |

Constraints: `[]`

Relationships: `[{'path': 'backend/app/models.py', 'line': 88, 'end_line': 90, 'owner': 'Region', 'conditions': [], 'attribute': 'data_points', 'annotation': "Mapped[list['RegionDataPoint']]", 'definition': "relationship(back_populates='region', cascade='all, delete-orphan', passive_deletes=True)"}]`

## Table `region_indicators`

| Python / SQL | Type | Nullable | Column arguments / options | Source |
| --- | --- | --- | --- | --- |
| id / id | Mapped[int] | False | [] {'primary_key': 'True'} | [backend/app/models.py:96](../backend/app/models.py#L96) |
| code / code | Mapped[str] | False | ['String(120)'] {'unique': 'True', 'nullable': 'False', 'index': 'True'} | [backend/app/models.py:97](../backend/app/models.py#L97) |
| table_code / table_code | Mapped[str] | False | ['String(20)'] {'nullable': 'False'} | [backend/app/models.py:98](../backend/app/models.py#L98) |
| section_num / section_num | Mapped[int] | False | ['Integer'] {'nullable': 'False', 'index': 'True'} | [backend/app/models.py:99](../backend/app/models.py#L99) |
| section_name / section_name | Mapped[str] | False | ['String(150)'] {'nullable': 'False'} | [backend/app/models.py:100](../backend/app/models.py#L100) |
| name / name | Mapped[str] | False | ['String(300)'] {'nullable': 'False'} | [backend/app/models.py:101](../backend/app/models.py#L101) |
| unit / unit | Mapped[str] | False | ['String(120)'] {'nullable': 'False', 'default': "''"} | [backend/app/models.py:102](../backend/app/models.py#L102) |
| note / note | Mapped[str \| None] | True | ['Text'] {} | [backend/app/models.py:103](../backend/app/models.py#L103) |
| source_note / source_note | Mapped[str \| None] | True | ['String(200)'] {} | [backend/app/models.py:104](../backend/app/models.py#L104) |
| year_min / year_min | Mapped[int \| None] | True | ['Integer'] {} | [backend/app/models.py:105](../backend/app/models.py#L105) |
| year_max / year_max | Mapped[int \| None] | True | ['Integer'] {} | [backend/app/models.py:106](../backend/app/models.py#L106) |
| is_listed / is_listed | Mapped[bool] | False | ['Boolean'] {'nullable': 'False', 'default': 'True', 'server_default': "'true'"} | [backend/app/models.py:107](../backend/app/models.py#L107) |

Constraints: `[]`

Relationships: `[{'path': 'backend/app/models.py', 'line': 109, 'end_line': 111, 'owner': 'RegionIndicator', 'conditions': [], 'attribute': 'data_points', 'annotation': "Mapped[list['RegionDataPoint']]", 'definition': "relationship(back_populates='indicator', cascade='all, delete-orphan', passive_deletes=True)"}]`

## Table `region_data`

| Python / SQL | Type | Nullable | Column arguments / options | Source |
| --- | --- | --- | --- | --- |
| id / id | Mapped[int] | False | [] {'primary_key': 'True'} | [backend/app/models.py:125](../backend/app/models.py#L125) |
| indicator_id / indicator_id | Mapped[int] | False | ["ForeignKey('region_indicators.id', ondelete='CASCADE')"] {'nullable': 'False'} | [backend/app/models.py:126](../backend/app/models.py#L126) |
| region_id / region_id | Mapped[int] | False | ["ForeignKey('regions.id', ondelete='CASCADE')"] {'nullable': 'False'} | [backend/app/models.py:129](../backend/app/models.py#L129) |
| year / year | Mapped[int] | False | ['Integer'] {'nullable': 'False'} | [backend/app/models.py:132](../backend/app/models.py#L132) |
| value / value | Mapped[float] | False | ['Numeric(18, 4)'] {'nullable': 'False'} | [backend/app/models.py:133](../backend/app/models.py#L133) |

Constraints: `[{'path': 'backend/app/models.py', 'line': 116, 'end_line': 123, 'owner': 'RegionDataPoint', 'conditions': [], 'definition': "(UniqueConstraint('indicator_id', 'region_id', 'year', name='uq_region_data_point'), Index('ix_region_data_indicator_year', 'indicator_id', 'year'), Index('ix_region_data_region', 'region_id'), Index('ix_region_data_region_indicator_year', 'region_id', 'indicator_id', 'year'))"}]`

Relationships: `[{'path': 'backend/app/models.py', 'line': 135, 'end_line': 135, 'owner': 'RegionDataPoint', 'conditions': [], 'attribute': 'indicator', 'annotation': "Mapped['RegionIndicator']", 'definition': "relationship(back_populates='data_points')"}, {'path': 'backend/app/models.py', 'line': 136, 'end_line': 136, 'owner': 'RegionDataPoint', 'conditions': [], 'attribute': 'region', 'annotation': "Mapped['Region']", 'definition': "relationship(back_populates='data_points')"}]`

## Table `region_monthly_data`

| Python / SQL | Type | Nullable | Column arguments / options | Source |
| --- | --- | --- | --- | --- |
| id / id | Mapped[int] | False | [] {'primary_key': 'True'} | [backend/app/models.py:155](../backend/app/models.py#L155) |
| indicator_id / indicator_id | Mapped[int] | False | ["ForeignKey('region_indicators.id', ondelete='CASCADE')"] {'nullable': 'False'} | [backend/app/models.py:156](../backend/app/models.py#L156) |
| region_id / region_id | Mapped[int] | False | ["ForeignKey('regions.id', ondelete='CASCADE')"] {'nullable': 'False'} | [backend/app/models.py:159](../backend/app/models.py#L159) |
| month / month | Mapped[int] | False | ['Integer'] {'nullable': 'False'} | [backend/app/models.py:162](../backend/app/models.py#L162) |
| value / value | Mapped[float] | False | ['Numeric(18, 4)'] {'nullable': 'False'} | [backend/app/models.py:163](../backend/app/models.py#L163) |

Constraints: `[{'path': 'backend/app/models.py', 'line': 149, 'end_line': 153, 'owner': 'RegionMonthlyPoint', 'conditions': [], 'definition': "(UniqueConstraint('indicator_id', 'region_id', 'month', name='uq_region_monthly_point'), Index('ix_region_monthly_indicator_month', 'indicator_id', 'month'), Index('ix_region_monthly_region_indicator_month', 'region_id', 'indicator_id', 'month'))"}]`

Relationships: `[{'path': 'backend/app/models.py', 'line': 165, 'end_line': 165, 'owner': 'RegionMonthlyPoint', 'conditions': [], 'attribute': 'indicator', 'annotation': "Mapped['RegionIndicator']", 'definition': 'relationship()'}, {'path': 'backend/app/models.py', 'line': 166, 'end_line': 166, 'owner': 'RegionMonthlyPoint', 'conditions': [], 'attribute': 'region', 'annotation': "Mapped['Region']", 'definition': 'relationship()'}]`

## Table `world_countries`

| Python / SQL | Type | Nullable | Column arguments / options | Source |
| --- | --- | --- | --- | --- |
| id / id | Mapped[int] | False | [] {'primary_key': 'True'} | [backend/app/models.py:175](../backend/app/models.py#L175) |
| code / code | Mapped[str] | False | ['String(8)'] {'unique': 'True', 'nullable': 'False', 'index': 'True'} | [backend/app/models.py:176](../backend/app/models.py#L176) |
| slug / slug | Mapped[str] | False | ['String(80)'] {'unique': 'True', 'nullable': 'False', 'index': 'True'} | [backend/app/models.py:177](../backend/app/models.py#L177) |
| name_ru / name_ru | Mapped[str] | False | ['String(150)'] {'nullable': 'False'} | [backend/app/models.py:178](../backend/app/models.py#L178) |
| name_en / name_en | Mapped[str] | False | ['String(150)'] {'nullable': 'False'} | [backend/app/models.py:179](../backend/app/models.py#L179) |
| region_ru / region_ru | Mapped[str] | False | ['String(80)'] {'nullable': 'False', 'default': "'Европа'"} | [backend/app/models.py:180](../backend/app/models.py#L180) |
| is_active / is_active | Mapped[bool] | False | ['Boolean'] {'nullable': 'False', 'default': 'True', 'server_default': "'true'"} | [backend/app/models.py:181](../backend/app/models.py#L181) |
| sort_order / sort_order | Mapped[int] | False | ['Integer'] {'nullable': 'False', 'default': '0'} | [backend/app/models.py:182](../backend/app/models.py#L182) |

Constraints: `[]`

Relationships: `[{'path': 'backend/app/models.py', 'line': 184, 'end_line': 186, 'owner': 'WorldCountry', 'conditions': [], 'attribute': 'indicators', 'annotation': "Mapped[list['WorldIndicator']]", 'definition': "relationship(back_populates='country', cascade='all, delete-orphan', passive_deletes=True)"}]`

## Table `world_indicators`

| Python / SQL | Type | Nullable | Column arguments / options | Source |
| --- | --- | --- | --- | --- |
| id / id | Mapped[int] | False | [] {'primary_key': 'True'} | [backend/app/models.py:233](../backend/app/models.py#L233) |
| country_id / country_id | Mapped[int] | False | ["ForeignKey('world_countries.id', ondelete='CASCADE')"] {'nullable': 'False'} | [backend/app/models.py:234](../backend/app/models.py#L234) |
| provider / provider | Mapped[str] | False | ['String(50)'] {'nullable': 'False', 'default': "'eurostat'", 'server_default': "'eurostat'"} | [backend/app/models.py:239](../backend/app/models.py#L239) |
| code / code | Mapped[str] | False | ['String(120)'] {'nullable': 'False'} | [backend/app/models.py:242](../backend/app/models.py#L242) |
| dataset_id / dataset_id | Mapped[str] | False | ['String(160)'] {'nullable': 'False', 'index': 'True'} | [backend/app/models.py:243](../backend/app/models.py#L243) |
| slice_json / slice_json | Mapped[dict \| None] | True | ['JSON'] {} | [backend/app/models.py:244](../backend/app/models.py#L244) |
| slice_hash / slice_hash | Mapped[str] | False | ['String(64)'] {'nullable': 'False'} | [backend/app/models.py:245](../backend/app/models.py#L245) |
| name_ru / name_ru | Mapped[str] | False | ['String(400)'] {'nullable': 'False'} | [backend/app/models.py:246](../backend/app/models.py#L246) |
| name_en / name_en | Mapped[str \| None] | True | ['String(400)'] {} | [backend/app/models.py:247](../backend/app/models.py#L247) |
| name_quality / name_quality | Mapped[str] | False | ['String(20)'] {'nullable': 'False', 'default': "'raw'", 'server_default': "'raw'"} | [backend/app/models.py:249](../backend/app/models.py#L249) |
| unit / unit | Mapped[str] | False | ['String(80)'] {'nullable': 'False', 'default': "''"} | [backend/app/models.py:252](../backend/app/models.py#L252) |
| unit_ru / unit_ru | Mapped[str] | False | ['String(80)'] {'nullable': 'False', 'default': "''"} | [backend/app/models.py:253](../backend/app/models.py#L253) |
| frequency / frequency | Mapped[str] | False | ['String(20)'] {'nullable': 'False'} | [backend/app/models.py:254](../backend/app/models.py#L254) |
| category_ru / category_ru | Mapped[str] | False | ['String(80)'] {'nullable': 'False', 'default': "''"} | [backend/app/models.py:255](../backend/app/models.py#L255) |
| source / source | Mapped[str] | False | ['String(100)'] {'nullable': 'False', 'default': "'Eurostat'"} | [backend/app/models.py:256](../backend/app/models.py#L256) |
| source_url / source_url | Mapped[str \| None] | True | ['String(500)'] {} | [backend/app/models.py:257](../backend/app/models.py#L257) |
| description / description | Mapped[str \| None] | True | ['Text'] {} | [backend/app/models.py:258](../backend/app/models.py#L258) |
| methodology / methodology | Mapped[str \| None] | True | ['Text'] {} | [backend/app/models.py:259](../backend/app/models.py#L259) |
| history_start / history_start | Mapped[date \| None] | True | ['Date'] {} | [backend/app/models.py:260](../backend/app/models.py#L260) |
| history_end / history_end | Mapped[date \| None] | True | ['Date'] {} | [backend/app/models.py:261](../backend/app/models.py#L261) |
| points_count / points_count | Mapped[int] | False | ['Integer'] {'nullable': 'False', 'default': '0'} | [backend/app/models.py:262](../backend/app/models.py#L262) |
| is_listed / is_listed | Mapped[bool] | False | ['Boolean'] {'nullable': 'False', 'default': 'False', 'server_default': "'false'"} | [backend/app/models.py:263](../backend/app/models.py#L263) |
| seo_title / seo_title | Mapped[str \| None] | True | ['String(300)'] {} | [backend/app/models.py:264](../backend/app/models.py#L264) |
| seo_description / seo_description | Mapped[str \| None] | True | ['Text'] {} | [backend/app/models.py:265](../backend/app/models.py#L265) |
| seo_keywords / seo_keywords | Mapped[str \| None] | True | ['Text'] {} | [backend/app/models.py:266](../backend/app/models.py#L266) |

Constraints: `[{'path': 'backend/app/models.py', 'line': 191, 'end_line': 231, 'owner': 'WorldIndicator', 'conditions': [], 'definition': "(UniqueConstraint('provider', 'country_id', 'dataset_id', 'slice_hash', name='uq_world_ind_provider_slice'), Index('ix_world_indicators_country_category', 'country_id', 'category_ru'), Index('ix_world_indicators_provider_dataset', 'provider', 'dataset_id'), Index('ix_world_indicators_code', 'code', unique=True), Index('ix_world_indicators_listed_signal', 'country_id', postgresql_include=('id', 'code', 'name_ru'), postgresql_where=text('is_listed')), Index('ix_world_indicators_card_lookup', 'country_id', 'provider', 'dataset_id', postgresql_ops={'dataset_id': 'varchar_pattern_ops'}), Index('ix_world_indicators_search_text_trgm', 'code', 'name_ru', 'name_en', 'seo_keywords', postgresql_using='gin', postgresql_ops={'code': 'gin_trgm_ops', 'name_ru': 'gin_trgm_ops', 'name_en': 'gin_trgm_ops', 'seo_keywords': 'gin_trgm_ops'}))"}]`

Relationships: `[{'path': 'backend/app/models.py', 'line': 268, 'end_line': 268, 'owner': 'WorldIndicator', 'conditions': [], 'attribute': 'country', 'annotation': "Mapped['WorldCountry']", 'definition': "relationship(back_populates='indicators')"}, {'path': 'backend/app/models.py', 'line': 269, 'end_line': 271, 'owner': 'WorldIndicator', 'conditions': [], 'attribute': 'data_points', 'annotation': "Mapped[list['WorldDataPoint']]", 'definition': "relationship(back_populates='indicator', cascade='all, delete-orphan', passive_deletes=True)"}, {'path': 'backend/app/models.py', 'line': 272, 'end_line': 274, 'owner': 'WorldIndicator', 'conditions': [], 'attribute': 'forecasts', 'annotation': "Mapped[list['WorldForecast']]", 'definition': "relationship(back_populates='indicator', cascade='all, delete-orphan', passive_deletes=True)"}]`

## Table `world_data_points`

| Python / SQL | Type | Nullable | Column arguments / options | Source |
| --- | --- | --- | --- | --- |
| id / id | Mapped[int] | False | [] {'primary_key': 'True'} | [backend/app/models.py:295](../backend/app/models.py#L295) |
| indicator_id / indicator_id | Mapped[int] | False | ["ForeignKey('world_indicators.id', ondelete='CASCADE')"] {'nullable': 'False'} | [backend/app/models.py:296](../backend/app/models.py#L296) |
| date / date | Mapped[date] | False | ['Date'] {'nullable': 'False'} | [backend/app/models.py:299](../backend/app/models.py#L299) |
| value / value | Mapped[float] | False | ['Numeric(20, 6)'] {'nullable': 'False'} | [backend/app/models.py:300](../backend/app/models.py#L300) |

Constraints: `[{'path': 'backend/app/models.py', 'line': 279, 'end_line': 293, 'owner': 'WorldDataPoint', 'conditions': [], 'definition': "(UniqueConstraint('indicator_id', 'date', name='uq_world_data_point'), Index('ix_world_data_points_nonzero_indicator', 'indicator_id', postgresql_where=text('value <> 0')))"}]`

Relationships: `[{'path': 'backend/app/models.py', 'line': 302, 'end_line': 302, 'owner': 'WorldDataPoint', 'conditions': [], 'attribute': 'indicator', 'annotation': "Mapped['WorldIndicator']", 'definition': "relationship(back_populates='data_points')"}]`

## Table `world_dataset_state`

| Python / SQL | Type | Nullable | Column arguments / options | Source |
| --- | --- | --- | --- | --- |
| provider / provider | Mapped[str] | False | ['String(50)'] {'primary_key': 'True', 'default': "'eurostat'", 'server_default': "'eurostat'"} | [backend/app/models.py:314](../backend/app/models.py#L314) |
| dataset_id / dataset_id | Mapped[str] | False | ['String(160)'] {'primary_key': 'True'} | [backend/app/models.py:317](../backend/app/models.py#L317) |
| last_update_of_data / last_update_of_data | Mapped[date \| None] | True | ['Date'] {} | [backend/app/models.py:318](../backend/app/models.py#L318) |
| last_structure_change / last_structure_change | Mapped[date \| None] | True | ['Date'] {} | [backend/app/models.py:319](../backend/app/models.py#L319) |
| last_slice_hash / last_slice_hash | Mapped[str \| None] | True | ['String(64)'] {} | [backend/app/models.py:320](../backend/app/models.py#L320) |
| status / status | Mapped[str] | False | ['String(20)'] {'nullable': 'False', 'default': "'ok'"} | [backend/app/models.py:321](../backend/app/models.py#L321) |
| last_success_at / last_success_at | Mapped[datetime \| None] | True | ['DateTime'] {} | [backend/app/models.py:322](../backend/app/models.py#L322) |
| last_error / last_error | Mapped[str \| None] | True | ['Text'] {} | [backend/app/models.py:323](../backend/app/models.py#L323) |

Constraints: `[]`

Relationships: `[]`

## Table `world_ingest_runs`

| Python / SQL | Type | Nullable | Column arguments / options | Source |
| --- | --- | --- | --- | --- |
| id / id | Mapped[int] | False | [] {'primary_key': 'True'} | [backend/app/models.py:332](../backend/app/models.py#L332) |
| source / source | Mapped[str] | False | ['String(50)'] {'nullable': 'False', 'default': "'eurostat'"} | [backend/app/models.py:333](../backend/app/models.py#L333) |
| status / status | Mapped[str] | False | ['String(20)'] {'nullable': 'False', 'default': "'running'"} | [backend/app/models.py:334](../backend/app/models.py#L334) |
| is_shadow / is_shadow | Mapped[bool] | False | ['Boolean'] {'nullable': 'False', 'default': 'True'} | [backend/app/models.py:335](../backend/app/models.py#L335) |
| datasets_selected / datasets_selected | Mapped[int] | False | ['Integer'] {'nullable': 'False', 'default': '0'} | [backend/app/models.py:336](../backend/app/models.py#L336) |
| datasets_succeeded / datasets_succeeded | Mapped[int] | False | ['Integer'] {'nullable': 'False', 'default': '0'} | [backend/app/models.py:337](../backend/app/models.py#L337) |
| datasets_failed / datasets_failed | Mapped[int] | False | ['Integer'] {'nullable': 'False', 'default': '0'} | [backend/app/models.py:338](../backend/app/models.py#L338) |
| started_at / started_at | Mapped[datetime] | False | ['DateTime'] {'nullable': 'False', 'default': '_utcnow_naive'} | [backend/app/models.py:339](../backend/app/models.py#L339) |
| completed_at / completed_at | Mapped[datetime \| None] | True | ['DateTime'] {} | [backend/app/models.py:340](../backend/app/models.py#L340) |
| error_message / error_message | Mapped[str \| None] | True | ['Text'] {} | [backend/app/models.py:341](../backend/app/models.py#L341) |

Constraints: `[{'path': 'backend/app/models.py', 'line': 330, 'end_line': 330, 'owner': 'WorldIngestRun', 'conditions': [], 'definition': "(Index('ix_world_ingest_runs_started', 'started_at'),)"}]`

Relationships: `[]`

## Table `world_ingest_dataset_logs`

| Python / SQL | Type | Nullable | Column arguments / options | Source |
| --- | --- | --- | --- | --- |
| id / id | Mapped[int] | False | [] {'primary_key': 'True'} | [backend/app/models.py:359](../backend/app/models.py#L359) |
| run_id / run_id | Mapped[int] | False | ["ForeignKey('world_ingest_runs.id', ondelete='CASCADE')"] {'nullable': 'False'} | [backend/app/models.py:360](../backend/app/models.py#L360) |
| provider / provider | Mapped[str] | False | ['String(50)'] {'nullable': 'False', 'default': "'eurostat'", 'server_default': "'eurostat'"} | [backend/app/models.py:363](../backend/app/models.py#L363) |
| dataset_id / dataset_id | Mapped[str] | False | ['String(160)'] {'nullable': 'False'} | [backend/app/models.py:366](../backend/app/models.py#L366) |
| status / status | Mapped[str] | False | ['String(20)'] {'nullable': 'False'} | [backend/app/models.py:367](../backend/app/models.py#L367) |
| source_updated_at / source_updated_at | Mapped[date \| None] | True | ['Date'] {} | [backend/app/models.py:368](../backend/app/models.py#L368) |
| structure_changed_at / structure_changed_at | Mapped[date \| None] | True | ['Date'] {} | [backend/app/models.py:369](../backend/app/models.py#L369) |
| slice_hash / slice_hash | Mapped[str \| None] | True | ['String(64)'] {} | [backend/app/models.py:370](../backend/app/models.py#L370) |
| rows_fetched / rows_fetched | Mapped[int] | False | ['Integer'] {'nullable': 'False', 'default': '0'} | [backend/app/models.py:371](../backend/app/models.py#L371) |
| rows_inserted / rows_inserted | Mapped[int] | False | ['Integer'] {'nullable': 'False', 'default': '0'} | [backend/app/models.py:372](../backend/app/models.py#L372) |
| rows_updated / rows_updated | Mapped[int] | False | ['Integer'] {'nullable': 'False', 'default': '0'} | [backend/app/models.py:373](../backend/app/models.py#L373) |
| rows_removed / rows_removed | Mapped[int] | False | ['Integer'] {'nullable': 'False', 'default': '0'} | [backend/app/models.py:374](../backend/app/models.py#L374) |
| error_message / error_message | Mapped[str \| None] | True | ['Text'] {} | [backend/app/models.py:375](../backend/app/models.py#L375) |

Constraints: `[{'path': 'backend/app/models.py', 'line': 348, 'end_line': 357, 'owner': 'WorldIngestDatasetLog', 'conditions': [], 'definition': "(UniqueConstraint('run_id', 'provider', 'dataset_id', name='uq_world_ingest_run_provider_dataset'), Index('ix_world_ingest_dataset_log_provider_dataset', 'provider', 'dataset_id', 'status'))"}]`

Relationships: `[{'path': 'backend/app/models.py', 'line': 377, 'end_line': 377, 'owner': 'WorldIngestDatasetLog', 'conditions': [], 'attribute': 'run', 'annotation': "Mapped['WorldIngestRun']", 'definition': 'relationship()'}]`

## Table `world_forecasts`

| Python / SQL | Type | Nullable | Column arguments / options | Source |
| --- | --- | --- | --- | --- |
| id / id | Mapped[int] | False | [] {'primary_key': 'True'} | [backend/app/models.py:393](../backend/app/models.py#L393) |
| world_indicator_id / world_indicator_id | Mapped[int] | False | ["ForeignKey('world_indicators.id', ondelete='CASCADE')"] {'nullable': 'False'} | [backend/app/models.py:394](../backend/app/models.py#L394) |
| strategy / strategy | Mapped[str] | False | ['String(50)'] {'nullable': 'False'} | [backend/app/models.py:397](../backend/app/models.py#L397) |
| model_name / model_name | Mapped[str] | False | ['String(120)'] {'nullable': 'False'} | [backend/app/models.py:398](../backend/app/models.py#L398) |
| model_params / model_params | Mapped[dict \| None] | True | ['JSON'] {} | [backend/app/models.py:399](../backend/app/models.py#L399) |
| gate_status / gate_status | Mapped[str] | False | ['String(20)'] {'nullable': 'False'} | [backend/app/models.py:400](../backend/app/models.py#L400) |
| gate_reason / gate_reason | Mapped[str \| None] | True | ['String(300)'] {} | [backend/app/models.py:401](../backend/app/models.py#L401) |
| mase / mase | Mapped[float \| None] | True | ['Numeric(12, 6)'] {} | [backend/app/models.py:402](../backend/app/models.py#L402) |
| baseline_mase / baseline_mase | Mapped[float \| None] | True | ['Numeric(12, 6)'] {} | [backend/app/models.py:403](../backend/app/models.py#L403) |
| origins / origins | Mapped[int] | False | ['Integer'] {'nullable': 'False', 'default': '0'} | [backend/app/models.py:404](../backend/app/models.py#L404) |
| horizon / horizon | Mapped[int] | False | ['Integer'] {'nullable': 'False'} | [backend/app/models.py:405](../backend/app/models.py#L405) |
| is_current / is_current | Mapped[bool] | False | ['Boolean'] {'nullable': 'False', 'default': 'False', 'server_default': "'false'"} | [backend/app/models.py:406](../backend/app/models.py#L406) |
| created_at / created_at | Mapped[datetime] | False | ['DateTime'] {'nullable': 'False', 'default': '_utcnow_naive'} | [backend/app/models.py:409](../backend/app/models.py#L409) |

Constraints: `[{'path': 'backend/app/models.py', 'line': 384, 'end_line': 391, 'owner': 'WorldForecast', 'conditions': [], 'definition': "(Index('ix_world_forecasts_indicator_current', 'world_indicator_id', postgresql_where=text('is_current = true')), Index('ix_world_forecasts_gate_created', 'gate_status', 'created_at'))"}]`

Relationships: `[{'path': 'backend/app/models.py', 'line': 411, 'end_line': 411, 'owner': 'WorldForecast', 'conditions': [], 'attribute': 'indicator', 'annotation': "Mapped['WorldIndicator']", 'definition': "relationship(back_populates='forecasts')"}, {'path': 'backend/app/models.py', 'line': 412, 'end_line': 414, 'owner': 'WorldForecast', 'conditions': [], 'attribute': 'values', 'annotation': "Mapped[list['WorldForecastValue']]", 'definition': "relationship(back_populates='forecast', cascade='all, delete-orphan', passive_deletes=True)"}]`

## Table `world_forecast_values`

| Python / SQL | Type | Nullable | Column arguments / options | Source |
| --- | --- | --- | --- | --- |
| id / id | Mapped[int] | False | [] {'primary_key': 'True'} | [backend/app/models.py:424](../backend/app/models.py#L424) |
| forecast_id / forecast_id | Mapped[int] | False | ["ForeignKey('world_forecasts.id', ondelete='CASCADE')"] {'nullable': 'False'} | [backend/app/models.py:425](../backend/app/models.py#L425) |
| date / date | Mapped[date] | False | ['Date'] {'nullable': 'False'} | [backend/app/models.py:428](../backend/app/models.py#L428) |
| value / value | Mapped[float] | False | ['Numeric(20, 6)'] {'nullable': 'False'} | [backend/app/models.py:429](../backend/app/models.py#L429) |
| lower_bound / lower_bound | Mapped[float \| None] | True | ['Numeric(20, 6)'] {} | [backend/app/models.py:430](../backend/app/models.py#L430) |
| upper_bound / upper_bound | Mapped[float \| None] | True | ['Numeric(20, 6)'] {} | [backend/app/models.py:431](../backend/app/models.py#L431) |

Constraints: `[{'path': 'backend/app/models.py', 'line': 419, 'end_line': 422, 'owner': 'WorldForecastValue', 'conditions': [], 'definition': "(UniqueConstraint('forecast_id', 'date', name='uq_world_forecast_value'), Index('ix_world_forecast_values_forecast_date', 'forecast_id', 'date'))"}]`

Relationships: `[{'path': 'backend/app/models.py', 'line': 433, 'end_line': 433, 'owner': 'WorldForecastValue', 'conditions': [], 'attribute': 'forecast', 'annotation': "Mapped['WorldForecast']", 'definition': "relationship(back_populates='values')"}]`

## Table `subnational_regions`

| Python / SQL | Type | Nullable | Column arguments / options | Source |
| --- | --- | --- | --- | --- |
| id / id | Mapped[int] | False | [] {'primary_key': 'True'} | [backend/app/models.py:450](../backend/app/models.py#L450) |
| country_code / country_code | Mapped[str] | False | ['String(8)'] {'nullable': 'False'} | [backend/app/models.py:451](../backend/app/models.py#L451) |
| slug / slug | Mapped[str] | False | ['String(80)'] {'nullable': 'False'} | [backend/app/models.py:452](../backend/app/models.py#L452) |
| name_en / name_en | Mapped[str] | False | ['String(150)'] {'nullable': 'False'} | [backend/app/models.py:453](../backend/app/models.py#L453) |
| name_ru / name_ru | Mapped[str] | False | ['String(150)'] {'nullable': 'False'} | [backend/app/models.py:454](../backend/app/models.py#L454) |
| kind / kind | Mapped[str] | False | ['String(20)'] {'nullable': 'False', 'default': "'state'"} | [backend/app/models.py:456](../backend/app/models.py#L456) |
| geo_code / geo_code | Mapped[str] | False | ['String(16)'] {'nullable': 'False', 'default': "''"} | [backend/app/models.py:457](../backend/app/models.py#L457) |
| fips / fips | Mapped[str \| None] | True | ['String(8)'] {} | [backend/app/models.py:458](../backend/app/models.py#L458) |
| sort_order / sort_order | Mapped[int] | False | ['Integer'] {'nullable': 'False', 'default': '0'} | [backend/app/models.py:459](../backend/app/models.py#L459) |

Constraints: `[{'path': 'backend/app/models.py', 'line': 445, 'end_line': 448, 'owner': 'SubnationalRegion', 'conditions': [], 'definition': "(UniqueConstraint('country_code', 'slug', name='uq_subnational_region_country_slug'), Index('ix_subnational_regions_country', 'country_code'))"}]`

Relationships: `[{'path': 'backend/app/models.py', 'line': 461, 'end_line': 463, 'owner': 'SubnationalRegion', 'conditions': [], 'attribute': 'data_points', 'annotation': "Mapped[list['SubnationalDataPoint']]", 'definition': "relationship(back_populates='region', cascade='all, delete-orphan', passive_deletes=True)"}]`

## Table `subnational_indicators`

| Python / SQL | Type | Nullable | Column arguments / options | Source |
| --- | --- | --- | --- | --- |
| id / id | Mapped[int] | False | [] {'primary_key': 'True'} | [backend/app/models.py:473](../backend/app/models.py#L473) |
| country_code / country_code | Mapped[str] | False | ['String(8)'] {'nullable': 'False'} | [backend/app/models.py:474](../backend/app/models.py#L474) |
| code / code | Mapped[str] | False | ['String(120)'] {'nullable': 'False'} | [backend/app/models.py:475](../backend/app/models.py#L475) |
| name_en / name_en | Mapped[str] | False | ['String(400)'] {'nullable': 'False'} | [backend/app/models.py:476](../backend/app/models.py#L476) |
| name_ru / name_ru | Mapped[str] | False | ['String(400)'] {'nullable': 'False'} | [backend/app/models.py:477](../backend/app/models.py#L477) |
| unit / unit | Mapped[str] | False | ['String(80)'] {'nullable': 'False', 'default': "''"} | [backend/app/models.py:478](../backend/app/models.py#L478) |
| unit_ru / unit_ru | Mapped[str] | False | ['String(80)'] {'nullable': 'False', 'default': "''"} | [backend/app/models.py:479](../backend/app/models.py#L479) |
| unit_en / unit_en | Mapped[str] | False | ['String(80)'] {'nullable': 'False', 'default': "''"} | [backend/app/models.py:480](../backend/app/models.py#L480) |
| frequency / frequency | Mapped[str] | False | ['String(20)'] {'nullable': 'False', 'default': "'annual'"} | [backend/app/models.py:481](../backend/app/models.py#L481) |
| section_en / section_en | Mapped[str] | False | ['String(80)'] {'nullable': 'False', 'default': "''"} | [backend/app/models.py:482](../backend/app/models.py#L482) |
| section_ru / section_ru | Mapped[str] | False | ['String(80)'] {'nullable': 'False', 'default': "''"} | [backend/app/models.py:483](../backend/app/models.py#L483) |
| provider / provider | Mapped[str] | False | ['String(50)'] {'nullable': 'False', 'default': "'fred'"} | [backend/app/models.py:484](../backend/app/models.py#L484) |
| series_template / series_template | Mapped[str] | False | ['String(160)'] {'nullable': 'False'} | [backend/app/models.py:485](../backend/app/models.py#L485) |
| aggregation / aggregation | Mapped[str] | False | ['String(20)'] {'nullable': 'False', 'default': "'last'"} | [backend/app/models.py:486](../backend/app/models.py#L486) |
| description_en / description_en | Mapped[str \| None] | True | ['Text'] {} | [backend/app/models.py:487](../backend/app/models.py#L487) |
| description_ru / description_ru | Mapped[str \| None] | True | ['Text'] {} | [backend/app/models.py:488](../backend/app/models.py#L488) |
| methodology_en / methodology_en | Mapped[str \| None] | True | ['Text'] {} | [backend/app/models.py:489](../backend/app/models.py#L489) |
| methodology_ru / methodology_ru | Mapped[str \| None] | True | ['Text'] {} | [backend/app/models.py:490](../backend/app/models.py#L490) |
| source_en / source_en | Mapped[str] | False | ['String(120)'] {'nullable': 'False', 'default': "''"} | [backend/app/models.py:491](../backend/app/models.py#L491) |
| source_ru / source_ru | Mapped[str] | False | ['String(120)'] {'nullable': 'False', 'default': "''"} | [backend/app/models.py:492](../backend/app/models.py#L492) |
| source_url_template / source_url_template | Mapped[str \| None] | True | ['String(500)'] {} | [backend/app/models.py:493](../backend/app/models.py#L493) |
| is_listed / is_listed | Mapped[bool] | False | ['Boolean'] {'nullable': 'False', 'default': 'True', 'server_default': "'true'"} | [backend/app/models.py:494](../backend/app/models.py#L494) |
| national_code / national_code | Mapped[str \| None] | True | ['String(120)'] {} | [backend/app/models.py:495](../backend/app/models.py#L495) |
| better_is_low / better_is_low | Mapped[bool] | False | ['Boolean'] {'nullable': 'False', 'default': 'False', 'server_default': "'false'"} | [backend/app/models.py:496](../backend/app/models.py#L496) |

Constraints: `[{'path': 'backend/app/models.py', 'line': 468, 'end_line': 471, 'owner': 'SubnationalIndicator', 'conditions': [], 'definition': "(UniqueConstraint('country_code', 'code', name='uq_subnational_indicator_country_code'), Index('ix_subnational_indicators_country', 'country_code'))"}]`

Relationships: `[{'path': 'backend/app/models.py', 'line': 498, 'end_line': 500, 'owner': 'SubnationalIndicator', 'conditions': [], 'attribute': 'data_points', 'annotation': "Mapped[list['SubnationalDataPoint']]", 'definition': "relationship(back_populates='indicator', cascade='all, delete-orphan', passive_deletes=True)"}]`

## Table `subnational_data_points`

| Python / SQL | Type | Nullable | Column arguments / options | Source |
| --- | --- | --- | --- | --- |
| id / id | Mapped[int] | False | [] {'primary_key': 'True'} | [backend/app/models.py:518](../backend/app/models.py#L518) |
| indicator_id / indicator_id | Mapped[int] | False | ["ForeignKey('subnational_indicators.id', ondelete='CASCADE')"] {'nullable': 'False'} | [backend/app/models.py:519](../backend/app/models.py#L519) |
| region_id / region_id | Mapped[int] | False | ["ForeignKey('subnational_regions.id', ondelete='CASCADE')"] {'nullable': 'False'} | [backend/app/models.py:522](../backend/app/models.py#L522) |
| period / period | Mapped[date] | False | ['Date'] {'nullable': 'False'} | [backend/app/models.py:525](../backend/app/models.py#L525) |
| value / value | Mapped[float] | False | ['Numeric(20, 6)'] {'nullable': 'False'} | [backend/app/models.py:526](../backend/app/models.py#L526) |

Constraints: `[{'path': 'backend/app/models.py', 'line': 505, 'end_line': 516, 'owner': 'SubnationalDataPoint', 'conditions': [], 'definition': "(UniqueConstraint('indicator_id', 'region_id', 'period', name='uq_subnational_data_point'), Index('ix_subnational_data_indicator_period', 'indicator_id', 'period'), Index('ix_subnational_data_region', 'region_id'), Index('ix_subnational_data_region_indicator_period', 'region_id', 'indicator_id', 'period'))"}]`

Relationships: `[{'path': 'backend/app/models.py', 'line': 528, 'end_line': 528, 'owner': 'SubnationalDataPoint', 'conditions': [], 'attribute': 'indicator', 'annotation': "Mapped['SubnationalIndicator']", 'definition': "relationship(back_populates='data_points')"}, {'path': 'backend/app/models.py', 'line': 529, 'end_line': 529, 'owner': 'SubnationalDataPoint', 'conditions': [], 'attribute': 'region', 'annotation': "Mapped['SubnationalRegion']", 'definition': "relationship(back_populates='data_points')"}]`

## Table `forecasts`

| Python / SQL | Type | Nullable | Column arguments / options | Source |
| --- | --- | --- | --- | --- |
| id / id | Mapped[int] | False | [] {'primary_key': 'True'} | [backend/app/models.py:543](../backend/app/models.py#L543) |
| indicator_id / indicator_id | Mapped[int] | False | ["ForeignKey('indicators.id', ondelete='CASCADE')"] {'nullable': 'False'} | [backend/app/models.py:544](../backend/app/models.py#L544) |
| model_name / model_name | Mapped[str] | False | ['String(100)'] {'nullable': 'False'} | [backend/app/models.py:545](../backend/app/models.py#L545) |
| model_params / model_params | Mapped[dict \| None] | True | ['JSON'] {} | [backend/app/models.py:546](../backend/app/models.py#L546) |
| aic / aic | Mapped[float \| None] | True | ['Numeric(10, 2)'] {} | [backend/app/models.py:547](../backend/app/models.py#L547) |
| bic / bic | Mapped[float \| None] | True | ['Numeric(10, 2)'] {} | [backend/app/models.py:548](../backend/app/models.py#L548) |
| is_current / is_current | Mapped[bool] | False | ['Boolean'] {'default': 'True'} | [backend/app/models.py:549](../backend/app/models.py#L549) |
| created_at / created_at | Mapped[datetime] | False | ['DateTime'] {'default': 'lambda: datetime.now(timezone.utc).replace(tzinfo=None)'} | [backend/app/models.py:550](../backend/app/models.py#L550) |

Constraints: `[{'path': 'backend/app/models.py', 'line': 535, 'end_line': 541, 'owner': 'Forecast', 'conditions': [], 'definition': "(Index('ix_forecasts_indicator_current', 'indicator_id', postgresql_where=text('is_current = true')),)"}]`

Relationships: `[{'path': 'backend/app/models.py', 'line': 552, 'end_line': 552, 'owner': 'Forecast', 'conditions': [], 'attribute': 'indicator', 'annotation': "Mapped['Indicator']", 'definition': "relationship(back_populates='forecasts')"}, {'path': 'backend/app/models.py', 'line': 553, 'end_line': 553, 'owner': 'Forecast', 'conditions': [], 'attribute': 'values', 'annotation': "Mapped[list['ForecastValue']]", 'definition': "relationship(back_populates='forecast', cascade='all, delete-orphan')"}]`

## Table `forecast_values`

| Python / SQL | Type | Nullable | Column arguments / options | Source |
| --- | --- | --- | --- | --- |
| id / id | Mapped[int] | False | [] {'primary_key': 'True'} | [backend/app/models.py:559](../backend/app/models.py#L559) |
| forecast_id / forecast_id | Mapped[int] | False | ["ForeignKey('forecasts.id', ondelete='CASCADE')"] {'nullable': 'False'} | [backend/app/models.py:560](../backend/app/models.py#L560) |
| date / date | Mapped[date] | False | ['Date'] {'nullable': 'False'} | [backend/app/models.py:561](../backend/app/models.py#L561) |
| value / value | Mapped[float] | False | ['Numeric(12, 4)'] {'nullable': 'False'} | [backend/app/models.py:562](../backend/app/models.py#L562) |
| lower_bound / lower_bound | Mapped[float \| None] | True | ['Numeric(12, 4)'] {} | [backend/app/models.py:563](../backend/app/models.py#L563) |
| upper_bound / upper_bound | Mapped[float \| None] | True | ['Numeric(12, 4)'] {} | [backend/app/models.py:564](../backend/app/models.py#L564) |

Constraints: `[{'path': 'backend/app/models.py', 'line': 568, 'end_line': 570, 'owner': 'ForecastValue', 'conditions': [], 'definition': "(Index('ix_forecast_values_forecast_date', 'forecast_id', 'date'),)"}]`

Relationships: `[{'path': 'backend/app/models.py', 'line': 566, 'end_line': 566, 'owner': 'ForecastValue', 'conditions': [], 'attribute': 'forecast', 'annotation': "Mapped['Forecast']", 'definition': "relationship(back_populates='values')"}]`

## Table `economic_events`

| Python / SQL | Type | Nullable | Column arguments / options | Source |
| --- | --- | --- | --- | --- |
| id / id | Mapped[int] | False | [] {'primary_key': 'True'} | [backend/app/models.py:586](../backend/app/models.py#L586) |
| title / title | Mapped[str] | False | ['String(300)'] {'nullable': 'False'} | [backend/app/models.py:587](../backend/app/models.py#L587) |
| title_en / title_en | Mapped[str \| None] | True | ['String(300)'] {} | [backend/app/models.py:588](../backend/app/models.py#L588) |
| event_type / event_type | Mapped[str] | False | ['String(30)'] {'nullable': 'False'} | [backend/app/models.py:589](../backend/app/models.py#L589) |
| source / source | Mapped[str] | False | ['String(20)'] {'nullable': 'False'} | [backend/app/models.py:590](../backend/app/models.py#L590) |
| indicator_id / indicator_id | Mapped[int \| None] | True | ["ForeignKey('indicators.id', ondelete='SET NULL')"] {'nullable': 'True'} | [backend/app/models.py:591](../backend/app/models.py#L591) |
| scheduled_date / scheduled_date | Mapped[date] | False | ['Date'] {'nullable': 'False'} | [backend/app/models.py:594](../backend/app/models.py#L594) |
| scheduled_time / scheduled_time | Mapped[str \| None] | True | ['String(5)'] {} | [backend/app/models.py:595](../backend/app/models.py#L595) |
| is_estimated / is_estimated | Mapped[bool] | False | ['Boolean'] {'default': 'False'} | [backend/app/models.py:596](../backend/app/models.py#L596) |
| actual_date / actual_date | Mapped[date \| None] | True | ['Date'] {} | [backend/app/models.py:597](../backend/app/models.py#L597) |
| reference_period / reference_period | Mapped[str \| None] | True | ['String(80)'] {} | [backend/app/models.py:598](../backend/app/models.py#L598) |
| importance / importance | Mapped[int] | False | ['Integer'] {'default': '2'} | [backend/app/models.py:599](../backend/app/models.py#L599) |
| previous_value / previous_value | Mapped[str \| None] | True | ['String(50)'] {} | [backend/app/models.py:600](../backend/app/models.py#L600) |
| forecast_value / forecast_value | Mapped[str \| None] | True | ['String(50)'] {} | [backend/app/models.py:601](../backend/app/models.py#L601) |
| actual_value / actual_value | Mapped[str \| None] | True | ['String(50)'] {} | [backend/app/models.py:602](../backend/app/models.py#L602) |
| status / status | Mapped[str] | False | ['String(20)'] {'default': "'scheduled'"} | [backend/app/models.py:603](../backend/app/models.py#L603) |
| description / description | Mapped[str \| None] | True | ['Text'] {} | [backend/app/models.py:604](../backend/app/models.py#L604) |
| source_url / source_url | Mapped[str \| None] | True | ['String(500)'] {} | [backend/app/models.py:605](../backend/app/models.py#L605) |
| event_key / event_key | Mapped[str \| None] | True | ['String(200)'] {} | [backend/app/models.py:606](../backend/app/models.py#L606) |
| date_confidence / date_confidence | Mapped[str] | False | ['String(30)'] {'default': "'estimated'"} | [backend/app/models.py:607](../backend/app/models.py#L607) |
| source_event_uid / source_event_uid | Mapped[str \| None] | True | ['String(300)'] {} | [backend/app/models.py:608](../backend/app/models.py#L608) |
| source_hash / source_hash | Mapped[str \| None] | True | ['String(64)'] {} | [backend/app/models.py:609](../backend/app/models.py#L609) |
| last_seen_at / last_seen_at | Mapped[datetime \| None] | True | ['DateTime'] {} | [backend/app/models.py:610](../backend/app/models.py#L610) |
| metadata_json / metadata_json | Mapped[dict \| None] | True | ['JSON'] {} | [backend/app/models.py:611](../backend/app/models.py#L611) |
| created_at / created_at | Mapped[datetime \| None] | True | ['DateTime'] {} | [backend/app/models.py:612](../backend/app/models.py#L612) |
| updated_at / updated_at | Mapped[datetime \| None] | True | ['DateTime'] {} | [backend/app/models.py:613](../backend/app/models.py#L613) |

Constraints: `[{'path': 'backend/app/models.py', 'line': 575, 'end_line': 584, 'owner': 'EconomicEvent', 'conditions': [], 'definition': "(UniqueConstraint('source', 'event_type', 'scheduled_date', 'indicator_id', name='uq_event_natural_key'), UniqueConstraint('source', 'event_type', 'event_key', name='uq_event_stable_key'), Index('ix_event_scheduled', 'scheduled_date'), Index('ix_event_source', 'source'), Index('ix_event_upcoming', 'scheduled_date', 'importance'), Index('ix_event_confidence', 'date_confidence'))"}]`

Relationships: `[{'path': 'backend/app/models.py', 'line': 615, 'end_line': 615, 'owner': 'EconomicEvent', 'conditions': [], 'attribute': 'indicator', 'annotation': "Mapped['Indicator \| None']", 'definition': 'relationship()'}]`

## Table `fetch_log`

| Python / SQL | Type | Nullable | Column arguments / options | Source |
| --- | --- | --- | --- | --- |
| id / id | Mapped[int] | False | [] {'primary_key': 'True'} | [backend/app/models.py:621](../backend/app/models.py#L621) |
| indicator_id / indicator_id | Mapped[int] | False | ["ForeignKey('indicators.id', ondelete='CASCADE')"] {'nullable': 'False'} | [backend/app/models.py:622](../backend/app/models.py#L622) |
| status / status | Mapped[str] | False | ['String(20)'] {'nullable': 'False'} | [backend/app/models.py:623](../backend/app/models.py#L623) |
| source_url / source_url | Mapped[str \| None] | True | ['String(500)'] {} | [backend/app/models.py:624](../backend/app/models.py#L624) |
| records_added / records_added | Mapped[int] | False | ['Integer'] {'default': '0'} | [backend/app/models.py:625](../backend/app/models.py#L625) |
| records_updated / records_updated | Mapped[int] | False | ['Integer'] {'default': '0'} | [backend/app/models.py:628](../backend/app/models.py#L628) |
| error_message / error_message | Mapped[str \| None] | True | ['Text'] {} | [backend/app/models.py:629](../backend/app/models.py#L629) |
| started_at / started_at | Mapped[datetime] | False | ['DateTime'] {'default': 'lambda: datetime.now(timezone.utc).replace(tzinfo=None)'} | [backend/app/models.py:630](../backend/app/models.py#L630) |
| completed_at / completed_at | Mapped[datetime \| None] | True | ['DateTime'] {} | [backend/app/models.py:631](../backend/app/models.py#L631) |

Constraints: `[]`

Relationships: `[{'path': 'backend/app/models.py', 'line': 633, 'end_line': 633, 'owner': 'FetchLog', 'conditions': [], 'attribute': 'indicator', 'annotation': "Mapped['Indicator']", 'definition': "relationship(back_populates='fetch_logs')"}]`

## Table `analytics_sync_runs`

| Python / SQL | Type | Nullable | Column arguments / options | Source |
| --- | --- | --- | --- | --- |
| id / id | Mapped[int] | False | [] {'primary_key': 'True'} | [backend/app/models.py:643](../backend/app/models.py#L643) |
| source / source | Mapped[str] | False | ['String(50)'] {'nullable': 'False'} | [backend/app/models.py:644](../backend/app/models.py#L644) |
| job_type / job_type | Mapped[str] | False | ['String(80)'] {'nullable': 'False'} | [backend/app/models.py:645](../backend/app/models.py#L645) |
| status / status | Mapped[str] | False | ['String(20)'] {'nullable': 'False', 'default': "'running'"} | [backend/app/models.py:646](../backend/app/models.py#L646) |
| date_from / date_from | Mapped[date \| None] | True | ['Date'] {} | [backend/app/models.py:647](../backend/app/models.py#L647) |
| date_to / date_to | Mapped[date \| None] | True | ['Date'] {} | [backend/app/models.py:648](../backend/app/models.py#L648) |
| request_hash / request_hash | Mapped[str \| None] | True | ['String(80)'] {} | [backend/app/models.py:649](../backend/app/models.py#L649) |
| records_processed / records_processed | Mapped[int] | False | ['Integer'] {'default': '0'} | [backend/app/models.py:650](../backend/app/models.py#L650) |
| error_message / error_message | Mapped[str \| None] | True | ['Text'] {} | [backend/app/models.py:651](../backend/app/models.py#L651) |
| metadata_json / metadata_json | Mapped[dict \| None] | True | ['JSON'] {} | [backend/app/models.py:652](../backend/app/models.py#L652) |
| started_at / started_at | Mapped[datetime] | False | ['DateTime'] {'default': 'lambda: datetime.now(timezone.utc).replace(tzinfo=None)'} | [backend/app/models.py:653](../backend/app/models.py#L653) |
| completed_at / completed_at | Mapped[datetime \| None] | True | ['DateTime'] {} | [backend/app/models.py:654](../backend/app/models.py#L654) |

Constraints: `[{'path': 'backend/app/models.py', 'line': 638, 'end_line': 641, 'owner': 'AnalyticsSyncRun', 'conditions': [], 'definition': "(Index('ix_analytics_sync_runs_source', 'source', 'status'), Index('ix_analytics_sync_runs_started', 'started_at'))"}]`

Relationships: `[]`

## Table `analytics_watermarks`

| Python / SQL | Type | Nullable | Column arguments / options | Source |
| --- | --- | --- | --- | --- |
| id / id | Mapped[int] | False | [] {'primary_key': 'True'} | [backend/app/models.py:663](../backend/app/models.py#L663) |
| source / source | Mapped[str] | False | ['String(50)'] {'nullable': 'False'} | [backend/app/models.py:664](../backend/app/models.py#L664) |
| resource_key / resource_key | Mapped[str] | False | ['String(150)'] {'nullable': 'False'} | [backend/app/models.py:665](../backend/app/models.py#L665) |
| last_success_date / last_success_date | Mapped[date \| None] | True | ['Date'] {} | [backend/app/models.py:666](../backend/app/models.py#L666) |
| last_success_at / last_success_at | Mapped[datetime \| None] | True | ['DateTime'] {} | [backend/app/models.py:667](../backend/app/models.py#L667) |
| metadata_json / metadata_json | Mapped[dict \| None] | True | ['JSON'] {} | [backend/app/models.py:668](../backend/app/models.py#L668) |
| updated_at / updated_at | Mapped[datetime] | False | ['DateTime'] {'default': 'lambda: datetime.now(timezone.utc).replace(tzinfo=None)', 'onupdate': 'lambda: datetime.now(timezone.utc).replace(tzinfo=None)'} | [backend/app/models.py:669](../backend/app/models.py#L669) |

Constraints: `[{'path': 'backend/app/models.py', 'line': 659, 'end_line': 661, 'owner': 'AnalyticsWatermark', 'conditions': [], 'definition': "(UniqueConstraint('source', 'resource_key', name='uq_analytics_watermark'),)"}]`

Relationships: `[]`

## Table `metrika_counter_snapshots`

| Python / SQL | Type | Nullable | Column arguments / options | Source |
| --- | --- | --- | --- | --- |
| id / id | Mapped[int] | False | [] {'primary_key': 'True'} | [backend/app/models.py:678](../backend/app/models.py#L678) |
| counter_id / counter_id | Mapped[str] | False | ['String(30)'] {'nullable': 'False'} | [backend/app/models.py:679](../backend/app/models.py#L679) |
| name / name | Mapped[str \| None] | True | ['String(200)'] {} | [backend/app/models.py:680](../backend/app/models.py#L680) |
| site / site | Mapped[str \| None] | True | ['String(300)'] {} | [backend/app/models.py:681](../backend/app/models.py#L681) |
| status / status | Mapped[str \| None] | True | ['String(50)'] {} | [backend/app/models.py:682](../backend/app/models.py#L682) |
| permission / permission | Mapped[str \| None] | True | ['String(50)'] {} | [backend/app/models.py:683](../backend/app/models.py#L683) |
| webvisor_enabled / webvisor_enabled | Mapped[bool \| None] | True | ['Boolean'] {} | [backend/app/models.py:684](../backend/app/models.py#L684) |
| ecommerce_enabled / ecommerce_enabled | Mapped[bool \| None] | True | ['Boolean'] {} | [backend/app/models.py:685](../backend/app/models.py#L685) |
| clickmap_enabled / clickmap_enabled | Mapped[bool \| None] | True | ['Boolean'] {} | [backend/app/models.py:686](../backend/app/models.py#L686) |
| raw_json / raw_json | Mapped[dict \| None] | True | ['JSON'] {} | [backend/app/models.py:687](../backend/app/models.py#L687) |
| captured_at / captured_at | Mapped[datetime] | False | ['DateTime'] {'default': 'lambda: datetime.now(timezone.utc).replace(tzinfo=None)'} | [backend/app/models.py:688](../backend/app/models.py#L688) |

Constraints: `[{'path': 'backend/app/models.py', 'line': 674, 'end_line': 676, 'owner': 'MetrikaCounterSnapshot', 'conditions': [], 'definition': "(Index('ix_metrika_counter_snapshots_counter', 'counter_id', 'captured_at'),)"}]`

Relationships: `[]`

## Table `metrika_goal_snapshots`

| Python / SQL | Type | Nullable | Column arguments / options | Source |
| --- | --- | --- | --- | --- |
| id / id | Mapped[int] | False | [] {'primary_key': 'True'} | [backend/app/models.py:698](../backend/app/models.py#L698) |
| counter_id / counter_id | Mapped[str] | False | ['String(30)'] {'nullable': 'False'} | [backend/app/models.py:699](../backend/app/models.py#L699) |
| goal_id / goal_id | Mapped[str] | False | ['String(50)'] {'nullable': 'False'} | [backend/app/models.py:700](../backend/app/models.py#L700) |
| name / name | Mapped[str \| None] | True | ['String(200)'] {} | [backend/app/models.py:701](../backend/app/models.py#L701) |
| goal_type / goal_type | Mapped[str \| None] | True | ['String(80)'] {} | [backend/app/models.py:702](../backend/app/models.py#L702) |
| is_favorite / is_favorite | Mapped[bool \| None] | True | ['Boolean'] {} | [backend/app/models.py:703](../backend/app/models.py#L703) |
| raw_json / raw_json | Mapped[dict \| None] | True | ['JSON'] {} | [backend/app/models.py:704](../backend/app/models.py#L704) |
| captured_at / captured_at | Mapped[datetime] | False | ['DateTime'] {'default': 'lambda: datetime.now(timezone.utc).replace(tzinfo=None)'} | [backend/app/models.py:705](../backend/app/models.py#L705) |

Constraints: `[{'path': 'backend/app/models.py', 'line': 693, 'end_line': 696, 'owner': 'MetrikaGoalSnapshot', 'conditions': [], 'definition': "(UniqueConstraint('counter_id', 'goal_id', 'captured_at', name='uq_metrika_goal_snapshot'), Index('ix_metrika_goal_counter', 'counter_id', 'goal_id'))"}]`

Relationships: `[]`

## Table `metrika_report_snapshots`

| Python / SQL | Type | Nullable | Column arguments / options | Source |
| --- | --- | --- | --- | --- |
| id / id | Mapped[int] | False | [] {'primary_key': 'True'} | [backend/app/models.py:715](../backend/app/models.py#L715) |
| counter_id / counter_id | Mapped[str] | False | ['String(30)'] {'nullable': 'False'} | [backend/app/models.py:716](../backend/app/models.py#L716) |
| report_type / report_type | Mapped[str] | False | ['String(80)'] {'nullable': 'False'} | [backend/app/models.py:717](../backend/app/models.py#L717) |
| query_hash / query_hash | Mapped[str] | False | ['String(80)'] {'nullable': 'False'} | [backend/app/models.py:718](../backend/app/models.py#L718) |
| date_from / date_from | Mapped[date \| None] | True | ['Date'] {} | [backend/app/models.py:719](../backend/app/models.py#L719) |
| date_to / date_to | Mapped[date \| None] | True | ['Date'] {} | [backend/app/models.py:720](../backend/app/models.py#L720) |
| sampled / sampled | Mapped[bool \| None] | True | ['Boolean'] {} | [backend/app/models.py:721](../backend/app/models.py#L721) |
| sample_share / sample_share | Mapped[float \| None] | True | ['Numeric(10, 6)'] {} | [backend/app/models.py:722](../backend/app/models.py#L722) |
| contains_sensitive_data / contains_sensitive_data | Mapped[bool \| None] | True | ['Boolean'] {} | [backend/app/models.py:723](../backend/app/models.py#L723) |
| query_json / query_json | Mapped[dict \| None] | True | ['JSON'] {} | [backend/app/models.py:724](../backend/app/models.py#L724) |
| response_json / response_json | Mapped[dict \| None] | True | ['JSON'] {} | [backend/app/models.py:725](../backend/app/models.py#L725) |
| captured_at / captured_at | Mapped[datetime] | False | ['DateTime'] {'default': 'lambda: datetime.now(timezone.utc).replace(tzinfo=None)'} | [backend/app/models.py:726](../backend/app/models.py#L726) |

Constraints: `[{'path': 'backend/app/models.py', 'line': 710, 'end_line': 713, 'owner': 'MetrikaReportSnapshot', 'conditions': [], 'definition': "(UniqueConstraint('counter_id', 'report_type', 'query_hash', 'date_from', 'date_to', name='uq_metrika_report_snapshot'), Index('ix_metrika_report_counter_dates', 'counter_id', 'date_from', 'date_to'))"}]`

Relationships: `[]`

## Table `metrika_daily_page_metrics`

| Python / SQL | Type | Nullable | Column arguments / options | Source |
| --- | --- | --- | --- | --- |
| id / id | Mapped[int] | False | [] {'primary_key': 'True'} | [backend/app/models.py:736](../backend/app/models.py#L736) |
| counter_id / counter_id | Mapped[str] | False | ['String(30)'] {'nullable': 'False'} | [backend/app/models.py:737](../backend/app/models.py#L737) |
| date / date | Mapped[date] | False | ['Date'] {'nullable': 'False'} | [backend/app/models.py:738](../backend/app/models.py#L738) |
| url / url | Mapped[str] | False | ['String(1000)'] {'nullable': 'False'} | [backend/app/models.py:739](../backend/app/models.py#L739) |
| source / source | Mapped[str \| None] | True | ['String(100)'] {} | [backend/app/models.py:740](../backend/app/models.py#L740) |
| visits / visits | Mapped[int] | False | ['Integer'] {'default': '0'} | [backend/app/models.py:741](../backend/app/models.py#L741) |
| users / users | Mapped[int] | False | ['Integer'] {'default': '0'} | [backend/app/models.py:742](../backend/app/models.py#L742) |
| pageviews / pageviews | Mapped[int] | False | ['Integer'] {'default': '0'} | [backend/app/models.py:743](../backend/app/models.py#L743) |
| bounce_rate / bounce_rate | Mapped[float \| None] | True | ['Numeric(8, 4)'] {} | [backend/app/models.py:744](../backend/app/models.py#L744) |
| depth / depth | Mapped[float \| None] | True | ['Numeric(8, 4)'] {} | [backend/app/models.py:745](../backend/app/models.py#L745) |
| avg_duration_seconds / avg_duration_seconds | Mapped[float \| None] | True | ['Numeric(12, 2)'] {} | [backend/app/models.py:746](../backend/app/models.py#L746) |
| metadata_json / metadata_json | Mapped[dict \| None] | True | ['JSON'] {} | [backend/app/models.py:747](../backend/app/models.py#L747) |
| created_at / created_at | Mapped[datetime] | False | ['DateTime'] {'default': 'lambda: datetime.now(timezone.utc).replace(tzinfo=None)'} | [backend/app/models.py:748](../backend/app/models.py#L748) |

Constraints: `[{'path': 'backend/app/models.py', 'line': 731, 'end_line': 734, 'owner': 'MetrikaDailyPageMetric', 'conditions': [], 'definition': "(UniqueConstraint('counter_id', 'date', 'url', 'source', name='uq_metrika_daily_page_metric'), Index('ix_metrika_daily_page_date', 'date', 'url'))"}]`

Relationships: `[]`

## Table `metrika_search_phrases`

| Python / SQL | Type | Nullable | Column arguments / options | Source |
| --- | --- | --- | --- | --- |
| id / id | Mapped[int] | False | [] {'primary_key': 'True'} | [backend/app/models.py:758](../backend/app/models.py#L758) |
| counter_id / counter_id | Mapped[str] | False | ['String(30)'] {'nullable': 'False'} | [backend/app/models.py:759](../backend/app/models.py#L759) |
| date / date | Mapped[date] | False | ['Date'] {'nullable': 'False'} | [backend/app/models.py:760](../backend/app/models.py#L760) |
| phrase / phrase | Mapped[str] | False | ['String(500)'] {'nullable': 'False'} | [backend/app/models.py:761](../backend/app/models.py#L761) |
| landing_url / landing_url | Mapped[str \| None] | True | ['String(1000)'] {} | [backend/app/models.py:762](../backend/app/models.py#L762) |
| search_engine / search_engine | Mapped[str \| None] | True | ['String(100)'] {} | [backend/app/models.py:763](../backend/app/models.py#L763) |
| visits / visits | Mapped[int] | False | ['Integer'] {'default': '0'} | [backend/app/models.py:764](../backend/app/models.py#L764) |
| users / users | Mapped[int] | False | ['Integer'] {'default': '0'} | [backend/app/models.py:765](../backend/app/models.py#L765) |
| bounce_rate / bounce_rate | Mapped[float \| None] | True | ['Numeric(8, 4)'] {} | [backend/app/models.py:766](../backend/app/models.py#L766) |
| metadata_json / metadata_json | Mapped[dict \| None] | True | ['JSON'] {} | [backend/app/models.py:767](../backend/app/models.py#L767) |
| created_at / created_at | Mapped[datetime] | False | ['DateTime'] {'default': 'lambda: datetime.now(timezone.utc).replace(tzinfo=None)'} | [backend/app/models.py:768](../backend/app/models.py#L768) |

Constraints: `[{'path': 'backend/app/models.py', 'line': 753, 'end_line': 756, 'owner': 'MetrikaSearchPhrase', 'conditions': [], 'definition': "(UniqueConstraint('counter_id', 'date', 'phrase', 'landing_url', 'search_engine', name='uq_metrika_search_phrase'), Index('ix_metrika_search_phrase_date', 'date', 'phrase'))"}]`

Relationships: `[]`

## Table `raw_metrika_visits`

| Python / SQL | Type | Nullable | Column arguments / options | Source |
| --- | --- | --- | --- | --- |
| id / id | Mapped[int] | False | [] {'primary_key': 'True'} | [backend/app/models.py:779](../backend/app/models.py#L779) |
| counter_id / counter_id | Mapped[str] | False | ['String(30)'] {'nullable': 'False'} | [backend/app/models.py:780](../backend/app/models.py#L780) |
| visit_id / visit_id | Mapped[str] | False | ['String(100)'] {'nullable': 'False'} | [backend/app/models.py:781](../backend/app/models.py#L781) |
| client_id_hash / client_id_hash | Mapped[str \| None] | True | ['String(80)'] {} | [backend/app/models.py:782](../backend/app/models.py#L782) |
| visit_date / visit_date | Mapped[date \| None] | True | ['Date'] {} | [backend/app/models.py:783](../backend/app/models.py#L783) |
| start_time / start_time | Mapped[datetime \| None] | True | ['DateTime'] {} | [backend/app/models.py:784](../backend/app/models.py#L784) |
| start_url / start_url | Mapped[str \| None] | True | ['String(1000)'] {} | [backend/app/models.py:785](../backend/app/models.py#L785) |
| referer / referer | Mapped[str \| None] | True | ['String(1000)'] {} | [backend/app/models.py:786](../backend/app/models.py#L786) |
| traffic_source / traffic_source | Mapped[str \| None] | True | ['String(100)'] {} | [backend/app/models.py:787](../backend/app/models.py#L787) |
| search_engine / search_engine | Mapped[str \| None] | True | ['String(100)'] {} | [backend/app/models.py:788](../backend/app/models.py#L788) |
| search_phrase / search_phrase | Mapped[str \| None] | True | ['String(500)'] {} | [backend/app/models.py:789](../backend/app/models.py#L789) |
| duration_seconds / duration_seconds | Mapped[int \| None] | True | ['Integer'] {} | [backend/app/models.py:790](../backend/app/models.py#L790) |
| goals_json / goals_json | Mapped[dict \| None] | True | ['JSON'] {} | [backend/app/models.py:791](../backend/app/models.py#L791) |
| raw_json / raw_json | Mapped[dict \| None] | True | ['JSON'] {} | [backend/app/models.py:792](../backend/app/models.py#L792) |
| row_hash / row_hash | Mapped[str] | False | ['String(80)'] {'nullable': 'False'} | [backend/app/models.py:793](../backend/app/models.py#L793) |
| ingested_at / ingested_at | Mapped[datetime] | False | ['DateTime'] {'default': 'lambda: datetime.now(timezone.utc).replace(tzinfo=None)'} | [backend/app/models.py:794](../backend/app/models.py#L794) |

Constraints: `[{'path': 'backend/app/models.py', 'line': 773, 'end_line': 777, 'owner': 'RawMetrikaVisit', 'conditions': [], 'definition': "(UniqueConstraint('counter_id', 'visit_id', name='uq_raw_metrika_visit'), Index('ix_raw_metrika_visit_date', 'visit_date'), Index('ix_raw_metrika_visit_client', 'client_id_hash'))"}]`

Relationships: `[]`

## Table `raw_metrika_hits`

| Python / SQL | Type | Nullable | Column arguments / options | Source |
| --- | --- | --- | --- | --- |
| id / id | Mapped[int] | False | [] {'primary_key': 'True'} | [backend/app/models.py:805](../backend/app/models.py#L805) |
| counter_id / counter_id | Mapped[str] | False | ['String(30)'] {'nullable': 'False'} | [backend/app/models.py:806](../backend/app/models.py#L806) |
| hit_id / hit_id | Mapped[str \| None] | True | ['String(100)'] {} | [backend/app/models.py:807](../backend/app/models.py#L807) |
| visit_id / visit_id | Mapped[str \| None] | True | ['String(100)'] {} | [backend/app/models.py:808](../backend/app/models.py#L808) |
| page_view_id / page_view_id | Mapped[str \| None] | True | ['String(100)'] {} | [backend/app/models.py:809](../backend/app/models.py#L809) |
| hit_date / hit_date | Mapped[date \| None] | True | ['Date'] {} | [backend/app/models.py:810](../backend/app/models.py#L810) |
| event_time / event_time | Mapped[datetime \| None] | True | ['DateTime'] {} | [backend/app/models.py:811](../backend/app/models.py#L811) |
| url / url | Mapped[str \| None] | True | ['String(1000)'] {} | [backend/app/models.py:812](../backend/app/models.py#L812) |
| referer / referer | Mapped[str \| None] | True | ['String(1000)'] {} | [backend/app/models.py:813](../backend/app/models.py#L813) |
| title / title | Mapped[str \| None] | True | ['String(500)'] {} | [backend/app/models.py:814](../backend/app/models.py#L814) |
| event_name / event_name | Mapped[str \| None] | True | ['String(150)'] {} | [backend/app/models.py:815](../backend/app/models.py#L815) |
| raw_json / raw_json | Mapped[dict \| None] | True | ['JSON'] {} | [backend/app/models.py:816](../backend/app/models.py#L816) |
| row_hash / row_hash | Mapped[str] | False | ['String(80)'] {'nullable': 'False'} | [backend/app/models.py:817](../backend/app/models.py#L817) |
| ingested_at / ingested_at | Mapped[datetime] | False | ['DateTime'] {'default': 'lambda: datetime.now(timezone.utc).replace(tzinfo=None)'} | [backend/app/models.py:818](../backend/app/models.py#L818) |

Constraints: `[{'path': 'backend/app/models.py', 'line': 799, 'end_line': 803, 'owner': 'RawMetrikaHit', 'conditions': [], 'definition': "(UniqueConstraint('counter_id', 'hit_id', 'row_hash', name='uq_raw_metrika_hit'), Index('ix_raw_metrika_hit_date', 'hit_date'), Index('ix_raw_metrika_hit_url', 'url'))"}]`

Relationships: `[]`

## Table `webmaster_diagnostics`

| Python / SQL | Type | Nullable | Column arguments / options | Source |
| --- | --- | --- | --- | --- |
| id / id | Mapped[int] | False | [] {'primary_key': 'True'} | [backend/app/models.py:828](../backend/app/models.py#L828) |
| host / host | Mapped[str] | False | ['String(300)'] {'nullable': 'False'} | [backend/app/models.py:829](../backend/app/models.py#L829) |
| problem_code / problem_code | Mapped[str] | False | ['String(150)'] {'nullable': 'False'} | [backend/app/models.py:830](../backend/app/models.py#L830) |
| severity / severity | Mapped[str \| None] | True | ['String(50)'] {} | [backend/app/models.py:831](../backend/app/models.py#L831) |
| url / url | Mapped[str \| None] | True | ['String(1000)'] {} | [backend/app/models.py:832](../backend/app/models.py#L832) |
| status / status | Mapped[str \| None] | True | ['String(50)'] {} | [backend/app/models.py:833](../backend/app/models.py#L833) |
| raw_json / raw_json | Mapped[dict \| None] | True | ['JSON'] {} | [backend/app/models.py:834](../backend/app/models.py#L834) |
| first_seen_at / first_seen_at | Mapped[datetime] | False | ['DateTime'] {'default': 'lambda: datetime.now(timezone.utc).replace(tzinfo=None)'} | [backend/app/models.py:835](../backend/app/models.py#L835) |
| last_seen_at / last_seen_at | Mapped[datetime] | False | ['DateTime'] {'default': 'lambda: datetime.now(timezone.utc).replace(tzinfo=None)'} | [backend/app/models.py:836](../backend/app/models.py#L836) |
| resolved_at / resolved_at | Mapped[datetime \| None] | True | ['DateTime'] {} | [backend/app/models.py:837](../backend/app/models.py#L837) |

Constraints: `[{'path': 'backend/app/models.py', 'line': 823, 'end_line': 826, 'owner': 'WebmasterDiagnostic', 'conditions': [], 'definition': "(UniqueConstraint('host', 'problem_code', 'url', 'first_seen_at', name='uq_webmaster_diagnostic'), Index('ix_webmaster_diagnostic_host', 'host', 'severity'))"}]`

Relationships: `[]`

## Table `webmaster_search_queries`

| Python / SQL | Type | Nullable | Column arguments / options | Source |
| --- | --- | --- | --- | --- |
| id / id | Mapped[int] | False | [] {'primary_key': 'True'} | [backend/app/models.py:847](../backend/app/models.py#L847) |
| host / host | Mapped[str] | False | ['String(300)'] {'nullable': 'False'} | [backend/app/models.py:848](../backend/app/models.py#L848) |
| date / date | Mapped[date] | False | ['Date'] {'nullable': 'False'} | [backend/app/models.py:849](../backend/app/models.py#L849) |
| query / query | Mapped[str] | False | ['String(500)'] {'nullable': 'False'} | [backend/app/models.py:850](../backend/app/models.py#L850) |
| url / url | Mapped[str \| None] | True | ['String(1000)'] {} | [backend/app/models.py:851](../backend/app/models.py#L851) |
| impressions / impressions | Mapped[int \| None] | True | ['Integer'] {} | [backend/app/models.py:852](../backend/app/models.py#L852) |
| clicks / clicks | Mapped[int \| None] | True | ['Integer'] {} | [backend/app/models.py:853](../backend/app/models.py#L853) |
| ctr / ctr | Mapped[float \| None] | True | ['Numeric(8, 4)'] {} | [backend/app/models.py:854](../backend/app/models.py#L854) |
| position / position | Mapped[float \| None] | True | ['Numeric(8, 2)'] {} | [backend/app/models.py:855](../backend/app/models.py#L855) |
| raw_json / raw_json | Mapped[dict \| None] | True | ['JSON'] {} | [backend/app/models.py:856](../backend/app/models.py#L856) |
| created_at / created_at | Mapped[datetime] | False | ['DateTime'] {'default': 'lambda: datetime.now(timezone.utc).replace(tzinfo=None)'} | [backend/app/models.py:857](../backend/app/models.py#L857) |

Constraints: `[{'path': 'backend/app/models.py', 'line': 842, 'end_line': 845, 'owner': 'WebmasterSearchQuery', 'conditions': [], 'definition': "(UniqueConstraint('host', 'date', 'query', 'url', name='uq_webmaster_search_query'), Index('ix_webmaster_query_date', 'date', 'query'))"}]`

Relationships: `[]`

## Table `webmaster_indexing_daily`

| Python / SQL | Type | Nullable | Column arguments / options | Source |
| --- | --- | --- | --- | --- |
| id / id | Mapped[int] | False | [] {'primary_key': 'True'} | [backend/app/models.py:868](../backend/app/models.py#L868) |
| host / host | Mapped[str] | False | ['String(300)'] {'nullable': 'False'} | [backend/app/models.py:869](../backend/app/models.py#L869) |
| day / day | Mapped[date] | False | ['Date'] {'nullable': 'False'} | [backend/app/models.py:870](../backend/app/models.py#L870) |
| in_search / in_search | Mapped[int \| None] | True | ['Integer'] {} | [backend/app/models.py:871](../backend/app/models.py#L871) |
| crawled_2xx / crawled_2xx | Mapped[int \| None] | True | ['Integer'] {} | [backend/app/models.py:872](../backend/app/models.py#L872) |
| crawled_3xx / crawled_3xx | Mapped[int \| None] | True | ['Integer'] {} | [backend/app/models.py:873](../backend/app/models.py#L873) |
| crawled_4xx / crawled_4xx | Mapped[int \| None] | True | ['Integer'] {} | [backend/app/models.py:874](../backend/app/models.py#L874) |
| crawled_5xx / crawled_5xx | Mapped[int \| None] | True | ['Integer'] {} | [backend/app/models.py:875](../backend/app/models.py#L875) |
| appeared / appeared | Mapped[int \| None] | True | ['Integer'] {} | [backend/app/models.py:876](../backend/app/models.py#L876) |
| excluded / excluded | Mapped[int \| None] | True | ['Integer'] {} | [backend/app/models.py:877](../backend/app/models.py#L877) |
| sitemap_errors / sitemap_errors | Mapped[int \| None] | True | ['Integer'] {} | [backend/app/models.py:878](../backend/app/models.py#L878) |
| raw_json / raw_json | Mapped[dict \| None] | True | ['JSON'] {} | [backend/app/models.py:879](../backend/app/models.py#L879) |
| created_at / created_at | Mapped[datetime] | False | ['DateTime'] {'default': 'lambda: datetime.now(timezone.utc).replace(tzinfo=None)'} | [backend/app/models.py:880](../backend/app/models.py#L880) |

Constraints: `[{'path': 'backend/app/models.py', 'line': 863, 'end_line': 866, 'owner': 'WebmasterIndexingDaily', 'conditions': [], 'definition': "(UniqueConstraint('host', 'day', name='uq_webmaster_indexing_daily'), Index('ix_webmaster_indexing_daily_day', 'day'))"}]`

Relationships: `[]`

## Table `gsc_search_queries`

| Python / SQL | Type | Nullable | Column arguments / options | Source |
| --- | --- | --- | --- | --- |
| id / id | Mapped[int] | False | [] {'primary_key': 'True'} | [backend/app/models.py:891](../backend/app/models.py#L891) |
| date / date | Mapped[date] | False | ['Date'] {'nullable': 'False'} | [backend/app/models.py:892](../backend/app/models.py#L892) |
| query / query | Mapped[str] | False | ['String(500)'] {'nullable': 'False'} | [backend/app/models.py:893](../backend/app/models.py#L893) |
| page / page | Mapped[str \| None] | True | ['String(1000)'] {} | [backend/app/models.py:894](../backend/app/models.py#L894) |
| impressions / impressions | Mapped[int \| None] | True | ['Integer'] {} | [backend/app/models.py:895](../backend/app/models.py#L895) |
| clicks / clicks | Mapped[int \| None] | True | ['Integer'] {} | [backend/app/models.py:896](../backend/app/models.py#L896) |
| ctr / ctr | Mapped[float \| None] | True | ['Numeric(8, 4)'] {} | [backend/app/models.py:897](../backend/app/models.py#L897) |
| position / position | Mapped[float \| None] | True | ['Numeric(8, 2)'] {} | [backend/app/models.py:898](../backend/app/models.py#L898) |
| raw_json / raw_json | Mapped[dict \| None] | True | ['JSON'] {} | [backend/app/models.py:899](../backend/app/models.py#L899) |
| created_at / created_at | Mapped[datetime] | False | ['DateTime'] {'default': 'lambda: datetime.now(timezone.utc).replace(tzinfo=None)'} | [backend/app/models.py:900](../backend/app/models.py#L900) |

Constraints: `[{'path': 'backend/app/models.py', 'line': 886, 'end_line': 889, 'owner': 'GscSearchQuery', 'conditions': [], 'definition': "(UniqueConstraint('date', 'query', 'page', name='uq_gsc_search_query'), Index('ix_gsc_query_date', 'date', 'query'))"}]`

Relationships: `[]`

## Table `seo_page_snapshots`

| Python / SQL | Type | Nullable | Column arguments / options | Source |
| --- | --- | --- | --- | --- |
| id / id | Mapped[int] | False | [] {'primary_key': 'True'} | [backend/app/models.py:910](../backend/app/models.py#L910) |
| url / url | Mapped[str] | False | ['String(1000)'] {'nullable': 'False'} | [backend/app/models.py:911](../backend/app/models.py#L911) |
| status_code / status_code | Mapped[int \| None] | True | ['Integer'] {} | [backend/app/models.py:912](../backend/app/models.py#L912) |
| title / title | Mapped[str \| None] | True | ['String(500)'] {} | [backend/app/models.py:913](../backend/app/models.py#L913) |
| description / description | Mapped[str \| None] | True | ['Text'] {} | [backend/app/models.py:914](../backend/app/models.py#L914) |
| canonical / canonical | Mapped[str \| None] | True | ['String(1000)'] {} | [backend/app/models.py:915](../backend/app/models.py#L915) |
| h1_count / h1_count | Mapped[int \| None] | True | ['Integer'] {} | [backend/app/models.py:916](../backend/app/models.py#L916) |
| json_ld_count / json_ld_count | Mapped[int \| None] | True | ['Integer'] {} | [backend/app/models.py:917](../backend/app/models.py#L917) |
| internal_links_count / internal_links_count | Mapped[int \| None] | True | ['Integer'] {} | [backend/app/models.py:918](../backend/app/models.py#L918) |
| content_hash / content_hash | Mapped[str] | False | ['String(80)'] {'nullable': 'False'} | [backend/app/models.py:919](../backend/app/models.py#L919) |
| facts_json / facts_json | Mapped[dict \| None] | True | ['JSON'] {} | [backend/app/models.py:920](../backend/app/models.py#L920) |
| captured_at / captured_at | Mapped[datetime] | False | ['DateTime'] {'default': 'lambda: datetime.now(timezone.utc).replace(tzinfo=None)'} | [backend/app/models.py:921](../backend/app/models.py#L921) |

Constraints: `[{'path': 'backend/app/models.py', 'line': 905, 'end_line': 908, 'owner': 'SeoPageSnapshot', 'conditions': [], 'definition': "(UniqueConstraint('url', 'content_hash', name='uq_seo_page_snapshot'), Index('ix_seo_page_snapshot_url', 'url', 'captured_at'))"}]`

Relationships: `[]`

## Table `agent_findings`

| Python / SQL | Type | Nullable | Column arguments / options | Source |
| --- | --- | --- | --- | --- |
| id / id | Mapped[int] | False | [] {'primary_key': 'True'} | [backend/app/models.py:931](../backend/app/models.py#L931) |
| finding_type / finding_type | Mapped[str] | False | ['String(80)'] {'nullable': 'False'} | [backend/app/models.py:932](../backend/app/models.py#L932) |
| title / title | Mapped[str] | False | ['String(300)'] {'nullable': 'False'} | [backend/app/models.py:933](../backend/app/models.py#L933) |
| summary / summary | Mapped[str \| None] | True | ['Text'] {} | [backend/app/models.py:934](../backend/app/models.py#L934) |
| evidence_json / evidence_json | Mapped[dict \| None] | True | ['JSON'] {} | [backend/app/models.py:935](../backend/app/models.py#L935) |
| affected_urls_json / affected_urls_json | Mapped[dict \| None] | True | ['JSON'] {} | [backend/app/models.py:936](../backend/app/models.py#L936) |
| confidence / confidence | Mapped[float \| None] | True | ['Numeric(5, 4)'] {} | [backend/app/models.py:937](../backend/app/models.py#L937) |
| priority / priority | Mapped[int] | False | ['Integer'] {'default': '3'} | [backend/app/models.py:938](../backend/app/models.py#L938) |
| status / status | Mapped[str] | False | ['String(30)'] {'default': "'open'"} | [backend/app/models.py:939](../backend/app/models.py#L939) |
| created_at / created_at | Mapped[datetime] | False | ['DateTime'] {'default': 'lambda: datetime.now(timezone.utc).replace(tzinfo=None)'} | [backend/app/models.py:940](../backend/app/models.py#L940) |
| resolved_at / resolved_at | Mapped[datetime \| None] | True | ['DateTime'] {} | [backend/app/models.py:941](../backend/app/models.py#L941) |

Constraints: `[{'path': 'backend/app/models.py', 'line': 926, 'end_line': 929, 'owner': 'AgentFinding', 'conditions': [], 'definition': "(Index('ix_agent_finding_status', 'status', 'priority'), Index('ix_agent_finding_created', 'created_at'))"}]`

Relationships: `[]`

## Table `agent_action_audit`

| Python / SQL | Type | Nullable | Column arguments / options | Source |
| --- | --- | --- | --- | --- |
| id / id | Mapped[int] | False | [] {'primary_key': 'True'} | [backend/app/models.py:951](../backend/app/models.py#L951) |
| action_type / action_type | Mapped[str] | False | ['String(100)'] {'nullable': 'False'} | [backend/app/models.py:952](../backend/app/models.py#L952) |
| safety_class / safety_class | Mapped[str] | False | ['String(30)'] {'nullable': 'False'} | [backend/app/models.py:953](../backend/app/models.py#L953) |
| status / status | Mapped[str] | False | ['String(30)'] {'nullable': 'False', 'default': "'proposed'"} | [backend/app/models.py:954](../backend/app/models.py#L954) |
| target_json / target_json | Mapped[dict \| None] | True | ['JSON'] {} | [backend/app/models.py:955](../backend/app/models.py#L955) |
| payload_json / payload_json | Mapped[dict \| None] | True | ['JSON'] {} | [backend/app/models.py:956](../backend/app/models.py#L956) |
| diff_json / diff_json | Mapped[dict \| None] | True | ['JSON'] {} | [backend/app/models.py:957](../backend/app/models.py#L957) |
| reason / reason | Mapped[str \| None] | True | ['Text'] {} | [backend/app/models.py:958](../backend/app/models.py#L958) |
| approval_token_hash / approval_token_hash | Mapped[str \| None] | True | ['String(100)'] {} | [backend/app/models.py:959](../backend/app/models.py#L959) |
| response_json / response_json | Mapped[dict \| None] | True | ['JSON'] {} | [backend/app/models.py:960](../backend/app/models.py#L960) |
| error_message / error_message | Mapped[str \| None] | True | ['Text'] {} | [backend/app/models.py:961](../backend/app/models.py#L961) |
| created_at / created_at | Mapped[datetime] | False | ['DateTime'] {'default': 'lambda: datetime.now(timezone.utc).replace(tzinfo=None)'} | [backend/app/models.py:962](../backend/app/models.py#L962) |
| applied_at / applied_at | Mapped[datetime \| None] | True | ['DateTime'] {} | [backend/app/models.py:963](../backend/app/models.py#L963) |

Constraints: `[{'path': 'backend/app/models.py', 'line': 946, 'end_line': 949, 'owner': 'AgentActionAudit', 'conditions': [], 'definition': "(Index('ix_agent_action_status', 'status', 'safety_class'), Index('ix_agent_action_created', 'created_at'))"}]`

Relationships: `[]`

## Table `frontend_events`

| Python / SQL | Type | Nullable | Column arguments / options | Source |
| --- | --- | --- | --- | --- |
| id / id | Mapped[int] | False | [] {'primary_key': 'True'} | [backend/app/models.py:973](../backend/app/models.py#L973) |
| event_name / event_name | Mapped[str] | False | ['String(120)'] {'nullable': 'False'} | [backend/app/models.py:974](../backend/app/models.py#L974) |
| session_id_hash / session_id_hash | Mapped[str \| None] | True | ['String(80)'] {} | [backend/app/models.py:975](../backend/app/models.py#L975) |
| visitor_id_hash / visitor_id_hash | Mapped[str \| None] | True | ['String(80)'] {'index': 'True'} | [backend/app/models.py:978](../backend/app/models.py#L978) |
| user_id / user_id | Mapped[str \| None] | True | ['String(36)'] {'index': 'True'} | [backend/app/models.py:982](../backend/app/models.py#L982) |
| authed / authed | Mapped[bool] | False | ['Boolean'] {'default': 'False', 'nullable': 'False', 'server_default': "'false'"} | [backend/app/models.py:983](../backend/app/models.py#L983) |
| url / url | Mapped[str \| None] | True | ['String(1000)'] {} | [backend/app/models.py:984](../backend/app/models.py#L984) |
| referrer / referrer | Mapped[str \| None] | True | ['String(1000)'] {} | [backend/app/models.py:985](../backend/app/models.py#L985) |
| params_json / params_json | Mapped[dict \| None] | True | ['JSON'] {} | [backend/app/models.py:986](../backend/app/models.py#L986) |
| occurred_at / occurred_at | Mapped[datetime] | False | ['DateTime'] {'default': 'lambda: datetime.now(timezone.utc).replace(tzinfo=None)'} | [backend/app/models.py:987](../backend/app/models.py#L987) |
| ingested_at / ingested_at | Mapped[datetime] | False | ['DateTime'] {'default': 'lambda: datetime.now(timezone.utc).replace(tzinfo=None)'} | [backend/app/models.py:988](../backend/app/models.py#L988) |

Constraints: `[{'path': 'backend/app/models.py', 'line': 968, 'end_line': 971, 'owner': 'FrontendEvent', 'conditions': [], 'definition': "(Index('ix_frontend_event_name_time', 'event_name', 'occurred_at'), Index('ix_frontend_event_url', 'url'))"}]`

Relationships: `[]`

## Table `behavior_events`

| Python / SQL | Type | Nullable | Column arguments / options | Source |
| --- | --- | --- | --- | --- |
| id / id | Mapped[int] | False | ["BigInteger().with_variant(Integer, 'sqlite')"] {'primary_key': 'True'} | [backend/app/models.py:1007](../backend/app/models.py#L1007) |
| event_type / event_type | Mapped[str] | False | ['String(20)'] {'nullable': 'False'} | [backend/app/models.py:1010](../backend/app/models.py#L1010) |
| session_id_hash / session_id_hash | Mapped[str \| None] | True | ['String(80)'] {} | [backend/app/models.py:1011](../backend/app/models.py#L1011) |
| visitor_id_hash / visitor_id_hash | Mapped[str \| None] | True | ['String(80)'] {'index': 'True'} | [backend/app/models.py:1012](../backend/app/models.py#L1012) |
| page_load_id / page_load_id | Mapped[str \| None] | True | ['String(40)'] {} | [backend/app/models.py:1013](../backend/app/models.py#L1013) |
| user_id / user_id | Mapped[str \| None] | True | ['String(36)'] {} | [backend/app/models.py:1014](../backend/app/models.py#L1014) |
| authed / authed | Mapped[bool] | False | ['Boolean'] {'default': 'False', 'nullable': 'False', 'server_default': "'false'"} | [backend/app/models.py:1015](../backend/app/models.py#L1015) |
| page / page | Mapped[str \| None] | True | ['String(500)'] {} | [backend/app/models.py:1016](../backend/app/models.py#L1016) |
| element_path / element_path | Mapped[str \| None] | True | ['String(400)'] {} | [backend/app/models.py:1017](../backend/app/models.py#L1017) |
| element_text / element_text | Mapped[str \| None] | True | ['String(120)'] {} | [backend/app/models.py:1018](../backend/app/models.py#L1018) |
| x / x | Mapped[int \| None] | True | ['Integer'] {} | [backend/app/models.py:1019](../backend/app/models.py#L1019) |
| y / y | Mapped[int \| None] | True | ['Integer'] {} | [backend/app/models.py:1020](../backend/app/models.py#L1020) |
| is_dead / is_dead | Mapped[bool] | False | ['Boolean'] {'default': 'False', 'nullable': 'False', 'server_default': "'false'"} | [backend/app/models.py:1021](../backend/app/models.py#L1021) |
| is_rage / is_rage | Mapped[bool] | False | ['Boolean'] {'default': 'False', 'nullable': 'False', 'server_default': "'false'"} | [backend/app/models.py:1022](../backend/app/models.py#L1022) |
| params_json / params_json | Mapped[dict \| None] | True | ['JSON'] {} | [backend/app/models.py:1023](../backend/app/models.py#L1023) |
| occurred_at / occurred_at | Mapped[datetime] | False | ['DateTime'] {'default': 'lambda: datetime.now(timezone.utc).replace(tzinfo=None)'} | [backend/app/models.py:1024](../backend/app/models.py#L1024) |
| ingested_at / ingested_at | Mapped[datetime] | False | ['DateTime'] {'default': 'lambda: datetime.now(timezone.utc).replace(tzinfo=None)'} | [backend/app/models.py:1025](../backend/app/models.py#L1025) |

Constraints: `[{'path': 'backend/app/models.py', 'line': 1000, 'end_line': 1003, 'owner': 'BehaviorEvent', 'conditions': [], 'definition': "(Index('ix_behavior_type_time', 'event_type', 'occurred_at'), Index('ix_behavior_page_time', 'page', 'occurred_at'))"}]`

Relationships: `[]`

## Table `behavior_sessions`

| Python / SQL | Type | Nullable | Column arguments / options | Source |
| --- | --- | --- | --- | --- |
| session_id_hash / session_id_hash | Mapped[str] | False | ['String(80)'] {'primary_key': 'True'} | [backend/app/models.py:1043](../backend/app/models.py#L1043) |
| visitor_id_hash / visitor_id_hash | Mapped[str \| None] | True | ['String(80)'] {'index': 'True'} | [backend/app/models.py:1044](../backend/app/models.py#L1044) |
| ym_client_id / ym_client_id | Mapped[str \| None] | True | ['String(80)'] {} | [backend/app/models.py:1049](../backend/app/models.py#L1049) |
| user_id / user_id | Mapped[str \| None] | True | ['String(36)'] {} | [backend/app/models.py:1050](../backend/app/models.py#L1050) |
| authed / authed | Mapped[bool] | False | ['Boolean'] {'default': 'False', 'nullable': 'False', 'server_default': "'false'"} | [backend/app/models.py:1051](../backend/app/models.py#L1051) |
| started_at / started_at | Mapped[datetime] | False | ['DateTime'] {'nullable': 'False'} | [backend/app/models.py:1052](../backend/app/models.py#L1052) |
| entry_page / entry_page | Mapped[str \| None] | True | ['String(500)'] {} | [backend/app/models.py:1053](../backend/app/models.py#L1053) |
| referrer / referrer | Mapped[str \| None] | True | ['String(1000)'] {} | [backend/app/models.py:1054](../backend/app/models.py#L1054) |
| referrer_host / referrer_host | Mapped[str \| None] | True | ['String(200)'] {} | [backend/app/models.py:1055](../backend/app/models.py#L1055) |
| channel / channel | Mapped[str \| None] | True | ['String(20)'] {} | [backend/app/models.py:1058](../backend/app/models.py#L1058) |
| utm_source / utm_source | Mapped[str \| None] | True | ['String(120)'] {} | [backend/app/models.py:1059](../backend/app/models.py#L1059) |
| utm_medium / utm_medium | Mapped[str \| None] | True | ['String(120)'] {} | [backend/app/models.py:1060](../backend/app/models.py#L1060) |
| utm_campaign / utm_campaign | Mapped[str \| None] | True | ['String(200)'] {} | [backend/app/models.py:1061](../backend/app/models.py#L1061) |
| utm_term / utm_term | Mapped[str \| None] | True | ['String(200)'] {} | [backend/app/models.py:1062](../backend/app/models.py#L1062) |
| utm_content / utm_content | Mapped[str \| None] | True | ['String(200)'] {} | [backend/app/models.py:1063](../backend/app/models.py#L1063) |
| yclid / yclid | Mapped[str \| None] | True | ['String(64)'] {} | [backend/app/models.py:1064](../backend/app/models.py#L1064) |
| country / country | Mapped[str \| None] | True | ['String(60)'] {} | [backend/app/models.py:1066](../backend/app/models.py#L1066) |
| geo_region / geo_region | Mapped[str \| None] | True | ['String(120)'] {} | [backend/app/models.py:1067](../backend/app/models.py#L1067) |
| city / city | Mapped[str \| None] | True | ['String(120)'] {} | [backend/app/models.py:1068](../backend/app/models.py#L1068) |
| ua_raw / ua_raw | Mapped[str \| None] | True | ['String(500)'] {} | [backend/app/models.py:1069](../backend/app/models.py#L1069) |
| browser / browser | Mapped[str \| None] | True | ['String(40)'] {} | [backend/app/models.py:1070](../backend/app/models.py#L1070) |
| browser_version / browser_version | Mapped[str \| None] | True | ['String(20)'] {} | [backend/app/models.py:1071](../backend/app/models.py#L1071) |
| os / os | Mapped[str \| None] | True | ['String(30)'] {} | [backend/app/models.py:1072](../backend/app/models.py#L1072) |
| os_version / os_version | Mapped[str \| None] | True | ['String(30)'] {} | [backend/app/models.py:1073](../backend/app/models.py#L1073) |
| device_type / device_type | Mapped[str \| None] | True | ['String(12)'] {} | [backend/app/models.py:1074](../backend/app/models.py#L1074) |
| screen_w / screen_w | Mapped[int \| None] | True | ['Integer'] {} | [backend/app/models.py:1075](../backend/app/models.py#L1075) |
| screen_h / screen_h | Mapped[int \| None] | True | ['Integer'] {} | [backend/app/models.py:1076](../backend/app/models.py#L1076) |
| viewport_w / viewport_w | Mapped[int \| None] | True | ['Integer'] {} | [backend/app/models.py:1077](../backend/app/models.py#L1077) |
| viewport_h / viewport_h | Mapped[int \| None] | True | ['Integer'] {} | [backend/app/models.py:1078](../backend/app/models.py#L1078) |
| dpr / dpr | Mapped[float \| None] | True | ['Numeric(4, 2)'] {} | [backend/app/models.py:1079](../backend/app/models.py#L1079) |
| language / language | Mapped[str \| None] | True | ['String(16)'] {} | [backend/app/models.py:1080](../backend/app/models.py#L1080) |
| timezone / timezone | Mapped[str \| None] | True | ['String(60)'] {} | [backend/app/models.py:1081](../backend/app/models.py#L1081) |
| touch / touch | Mapped[bool \| None] | True | ['Boolean'] {} | [backend/app/models.py:1082](../backend/app/models.py#L1082) |
| conn_type / conn_type | Mapped[str \| None] | True | ['String(16)'] {} | [backend/app/models.py:1084](../backend/app/models.py#L1084) |
| downlink / downlink | Mapped[float \| None] | True | ['Numeric(6, 2)'] {} | [backend/app/models.py:1085](../backend/app/models.py#L1085) |
| device_memory / device_memory | Mapped[float \| None] | True | ['Numeric(5, 1)'] {} | [backend/app/models.py:1086](../backend/app/models.py#L1086) |
| cpu_cores / cpu_cores | Mapped[int \| None] | True | ['Integer'] {} | [backend/app/models.py:1087](../backend/app/models.py#L1087) |
| color_scheme / color_scheme | Mapped[str \| None] | True | ['String(10)'] {} | [backend/app/models.py:1088](../backend/app/models.py#L1088) |
| orientation / orientation | Mapped[str \| None] | True | ['String(12)'] {} | [backend/app/models.py:1089](../backend/app/models.py#L1089) |
| is_webdriver / is_webdriver | Mapped[bool \| None] | True | ['Boolean'] {} | [backend/app/models.py:1090](../backend/app/models.py#L1090) |
| is_synthetic / is_synthetic | Mapped[bool] | False | ['Boolean'] {'default': 'False', 'nullable': 'False', 'server_default': "'false'"} | [backend/app/models.py:1094](../backend/app/models.py#L1094) |

Constraints: `[{'path': 'backend/app/models.py', 'line': 1039, 'end_line': 1041, 'owner': 'BehaviorSession', 'conditions': [], 'definition': "(Index('ix_behavior_sessions_started', 'started_at'),)"}]`

Relationships: `[]`

## Table `identity_links`

| Python / SQL | Type | Nullable | Column arguments / options | Source |
| --- | --- | --- | --- | --- |
| id / id | Mapped[int] | False | [] {'primary_key': 'True'} | [backend/app/models.py:1110](../backend/app/models.py#L1110) |
| user_id / user_id | Mapped[str] | False | ['String(36)'] {'nullable': 'False', 'index': 'True'} | [backend/app/models.py:1111](../backend/app/models.py#L1111) |
| visitor_id_hash / visitor_id_hash | Mapped[str] | False | ['String(80)'] {'nullable': 'False'} | [backend/app/models.py:1112](../backend/app/models.py#L1112) |
| first_seen / first_seen | Mapped[datetime] | False | ['DateTime'] {'nullable': 'False', 'default': 'lambda: datetime.now(timezone.utc).replace(tzinfo=None)'} | [backend/app/models.py:1113](../backend/app/models.py#L1113) |
| last_seen / last_seen | Mapped[datetime] | False | ['DateTime'] {'nullable': 'False', 'default': 'lambda: datetime.now(timezone.utc).replace(tzinfo=None)'} | [backend/app/models.py:1114](../backend/app/models.py#L1114) |

Constraints: `[{'path': 'backend/app/models.py', 'line': 1105, 'end_line': 1108, 'owner': 'IdentityLink', 'conditions': [], 'definition': "(UniqueConstraint('user_id', 'visitor_id_hash', name='uq_identity_user_visitor'), Index('ix_identity_visitor', 'visitor_id_hash'))"}]`

Relationships: `[]`

## Table `metrika_goals`

| Python / SQL | Type | Nullable | Column arguments / options | Source |
| --- | --- | --- | --- | --- |
| goal_id / goal_id | Mapped[int] | False | ["BigInteger().with_variant(Integer, 'sqlite')"] {'primary_key': 'True'} | [backend/app/models.py:1126](../backend/app/models.py#L1126) |
| name / name | Mapped[str \| None] | True | ['String(300)'] {} | [backend/app/models.py:1127](../backend/app/models.py#L1127) |
| event_name / event_name | Mapped[str \| None] | True | ['String(120)'] {'index': 'True'} | [backend/app/models.py:1128](../backend/app/models.py#L1128) |
| tier / tier | Mapped[str \| None] | True | ['String(20)'] {} | [backend/app/models.py:1129](../backend/app/models.py#L1129) |
| deleted / deleted | Mapped[bool] | False | ['Boolean'] {'default': 'False', 'server_default': "'false'", 'nullable': 'False'} | [backend/app/models.py:1132](../backend/app/models.py#L1132) |
| synced_at / synced_at | Mapped[datetime] | False | ['DateTime'] {'default': 'lambda: datetime.now(timezone.utc).replace(tzinfo=None)'} | [backend/app/models.py:1133](../backend/app/models.py#L1133) |

Constraints: `[]`

Relationships: `[]`

## Table `direct_costs`

| Python / SQL | Type | Nullable | Column arguments / options | Source |
| --- | --- | --- | --- | --- |
| id / id | Mapped[int] | False | [] {'primary_key': 'True'} | [backend/app/models.py:1148](../backend/app/models.py#L1148) |
| day / day | Mapped[date] | False | ['Date'] {'nullable': 'False', 'index': 'True'} | [backend/app/models.py:1149](../backend/app/models.py#L1149) |
| campaign / campaign | Mapped[str] | False | ['String(300)'] {'nullable': 'False'} | [backend/app/models.py:1150](../backend/app/models.py#L1150) |
| cost_rub / cost_rub | Mapped[float] | False | ['Numeric(12, 2)'] {'nullable': 'False', 'default': '0'} | [backend/app/models.py:1151](../backend/app/models.py#L1151) |
| clicks / clicks | Mapped[int] | False | ['Integer'] {'nullable': 'False', 'default': '0'} | [backend/app/models.py:1152](../backend/app/models.py#L1152) |
| synced_at / synced_at | Mapped[datetime] | False | ['DateTime'] {'default': 'lambda: datetime.now(timezone.utc).replace(tzinfo=None)'} | [backend/app/models.py:1153](../backend/app/models.py#L1153) |

Constraints: `[{'path': 'backend/app/models.py', 'line': 1144, 'end_line': 1146, 'owner': 'DirectCost', 'conditions': [], 'definition': "(UniqueConstraint('day', 'campaign', name='uq_direct_cost_day_campaign'),)"}]`

Relationships: `[]`

## Table `partner_revenue`

| Python / SQL | Type | Nullable | Column arguments / options | Source |
| --- | --- | --- | --- | --- |
| id / id | Mapped[int] | False | [] {'primary_key': 'True'} | [backend/app/models.py:1168](../backend/app/models.py#L1168) |
| day / day | Mapped[date] | False | ['Date'] {'nullable': 'False', 'index': 'True'} | [backend/app/models.py:1169](../backend/app/models.py#L1169) |
| shows / shows | Mapped[int] | False | ['Integer'] {'nullable': 'False', 'default': '0'} | [backend/app/models.py:1170](../backend/app/models.py#L1170) |
| hits / hits | Mapped[int] | False | ['Integer'] {'nullable': 'False', 'default': '0'} | [backend/app/models.py:1171](../backend/app/models.py#L1171) |
| revenue_rub / revenue_rub | Mapped[float] | False | ['Numeric(12, 2)'] {'nullable': 'False', 'default': '0'} | [backend/app/models.py:1172](../backend/app/models.py#L1172) |
| synced_at / synced_at | Mapped[datetime] | False | ['DateTime'] {'default': 'lambda: datetime.now(timezone.utc).replace(tzinfo=None)'} | [backend/app/models.py:1173](../backend/app/models.py#L1173) |

Constraints: `[{'path': 'backend/app/models.py', 'line': 1164, 'end_line': 1166, 'owner': 'PartnerRevenue', 'conditions': [], 'definition': "(UniqueConstraint('day', name='uq_partner_revenue_day'),)"}]`

Relationships: `[]`

## Table `server_sessions`

| Python / SQL | Type | Nullable | Column arguments / options | Source |
| --- | --- | --- | --- | --- |
| id / id | Mapped[int] | False | ["BigInteger().with_variant(Integer, 'sqlite')"] {'primary_key': 'True'} | [backend/app/models.py:1190](../backend/app/models.py#L1190) |
| day / day | Mapped[date] | False | ['Date'] {'nullable': 'False'} | [backend/app/models.py:1191](../backend/app/models.py#L1191) |
| visitor_id_hash / visitor_id_hash | Mapped[str] | False | ['String(80)'] {'nullable': 'False'} | [backend/app/models.py:1192](../backend/app/models.py#L1192) |
| user_id / user_id | Mapped[str \| None] | True | ['String(36)'] {} | [backend/app/models.py:1193](../backend/app/models.py#L1193) |
| started_at / started_at | Mapped[datetime] | False | ['DateTime'] {'nullable': 'False'} | [backend/app/models.py:1194](../backend/app/models.py#L1194) |
| ended_at / ended_at | Mapped[datetime] | False | ['DateTime'] {'nullable': 'False'} | [backend/app/models.py:1195](../backend/app/models.py#L1195) |
| duration_ms / duration_ms | Mapped[int] | False | ["BigInteger().with_variant(Integer, 'sqlite')"] {'default': '0'} | [backend/app/models.py:1196](../backend/app/models.py#L1196) |
| active_ms / active_ms | Mapped[int] | False | ["BigInteger().with_variant(Integer, 'sqlite')"] {'default': '0'} | [backend/app/models.py:1197](../backend/app/models.py#L1197) |
| pageviews / pageviews | Mapped[int] | False | ['Integer'] {'default': '0'} | [backend/app/models.py:1198](../backend/app/models.py#L1198) |
| clicks / clicks | Mapped[int] | False | ['Integer'] {'default': '0'} | [backend/app/models.py:1199](../backend/app/models.py#L1199) |
| max_scroll_pct / max_scroll_pct | Mapped[int] | False | ['Integer'] {'default': '0'} | [backend/app/models.py:1200](../backend/app/models.py#L1200) |
| entry_page / entry_page | Mapped[str \| None] | True | ['String(500)'] {} | [backend/app/models.py:1201](../backend/app/models.py#L1201) |
| exit_page / exit_page | Mapped[str \| None] | True | ['String(500)'] {} | [backend/app/models.py:1202](../backend/app/models.py#L1202) |
| channel / channel | Mapped[str \| None] | True | ['String(20)'] {} | [backend/app/models.py:1203](../backend/app/models.py#L1203) |
| device / device | Mapped[str \| None] | True | ['String(20)'] {} | [backend/app/models.py:1204](../backend/app/models.py#L1204) |
| is_new_visitor / is_new_visitor | Mapped[bool] | False | ['Boolean'] {'default': 'False', 'nullable': 'False', 'server_default': "'false'"} | [backend/app/models.py:1205](../backend/app/models.py#L1205) |
| is_engaged / is_engaged | Mapped[bool] | False | ['Boolean'] {'default': 'False', 'nullable': 'False', 'server_default': "'false'"} | [backend/app/models.py:1206](../backend/app/models.py#L1206) |
| micro_goals / micro_goals | Mapped[int] | False | ['Integer'] {'default': '0'} | [backend/app/models.py:1207](../backend/app/models.py#L1207) |
| macro_goals / macro_goals | Mapped[int] | False | ['Integer'] {'default': '0'} | [backend/app/models.py:1208](../backend/app/models.py#L1208) |
| is_bot / is_bot | Mapped[bool] | False | ['Boolean'] {'default': 'False', 'nullable': 'False', 'server_default': "'false'"} | [backend/app/models.py:1209](../backend/app/models.py#L1209) |
| bot_score / bot_score | Mapped[int] | False | ['Integer'] {'default': '0', 'nullable': 'False', 'server_default': "'0'"} | [backend/app/models.py:1211](../backend/app/models.py#L1211) |
| is_internal / is_internal | Mapped[bool] | False | ['Boolean'] {'default': 'False', 'nullable': 'False', 'server_default': "'false'"} | [backend/app/models.py:1214](../backend/app/models.py#L1214) |
| computed_at / computed_at | Mapped[datetime] | False | ['DateTime'] {'default': 'lambda: datetime.now(timezone.utc).replace(tzinfo=None)'} | [backend/app/models.py:1215](../backend/app/models.py#L1215) |

Constraints: `[{'path': 'backend/app/models.py', 'line': 1185, 'end_line': 1188, 'owner': 'ServerSession', 'conditions': [], 'definition': "(UniqueConstraint('visitor_id_hash', 'started_at', name='uq_server_session_visitor_start'), Index('ix_server_session_day', 'day'))"}]`

Relationships: `[]`

## Table `daily_traffic`

| Python / SQL | Type | Nullable | Column arguments / options | Source |
| --- | --- | --- | --- | --- |
| id / id | Mapped[int] | False | [] {'primary_key': 'True'} | [backend/app/models.py:1226](../backend/app/models.py#L1226) |
| day / day | Mapped[date] | False | ['Date'] {'nullable': 'False', 'index': 'True'} | [backend/app/models.py:1227](../backend/app/models.py#L1227) |
| channel / channel | Mapped[str] | False | ['String(40)'] {'nullable': 'False', 'default': "''"} | [backend/app/models.py:1228](../backend/app/models.py#L1228) |
| device / device | Mapped[str] | False | ['String(20)'] {'nullable': 'False', 'default': "''"} | [backend/app/models.py:1229](../backend/app/models.py#L1229) |
| is_new / is_new | Mapped[bool] | False | ['Boolean'] {'nullable': 'False', 'default': 'False'} | [backend/app/models.py:1230](../backend/app/models.py#L1230) |
| visits / visits | Mapped[int] | False | ['Integer'] {'default': '0'} | [backend/app/models.py:1231](../backend/app/models.py#L1231) |
| visitors / visitors | Mapped[int] | False | ['Integer'] {'default': '0'} | [backend/app/models.py:1232](../backend/app/models.py#L1232) |
| pageviews / pageviews | Mapped[int] | False | ['Integer'] {'default': '0'} | [backend/app/models.py:1233](../backend/app/models.py#L1233) |
| goal_visits / goal_visits | Mapped[int] | False | ['Integer'] {'default': '0'} | [backend/app/models.py:1234](../backend/app/models.py#L1234) |
| total_duration_sec / total_duration_sec | Mapped[int] | False | ["BigInteger().with_variant(Integer, 'sqlite')"] {'default': '0'} | [backend/app/models.py:1235](../backend/app/models.py#L1235) |
| bounces / bounces | Mapped[int] | False | ['Integer'] {'default': '0'} | [backend/app/models.py:1236](../backend/app/models.py#L1236) |
| computed_at / computed_at | Mapped[datetime] | False | ['DateTime'] {'default': 'lambda: datetime.now(timezone.utc).replace(tzinfo=None)'} | [backend/app/models.py:1237](../backend/app/models.py#L1237) |

Constraints: `[{'path': 'backend/app/models.py', 'line': 1222, 'end_line': 1224, 'owner': 'DailyTraffic', 'conditions': [], 'definition': "(UniqueConstraint('day', 'channel', 'device', 'is_new', name='uq_daily_traffic_key'),)"}]`

Relationships: `[]`

## Table `daily_goals`

| Python / SQL | Type | Nullable | Column arguments / options | Source |
| --- | --- | --- | --- | --- |
| id / id | Mapped[int] | False | [] {'primary_key': 'True'} | [backend/app/models.py:1247](../backend/app/models.py#L1247) |
| day / day | Mapped[date] | False | ['Date'] {'nullable': 'False', 'index': 'True'} | [backend/app/models.py:1248](../backend/app/models.py#L1248) |
| event_name / event_name | Mapped[str] | False | ['String(120)'] {'nullable': 'False'} | [backend/app/models.py:1249](../backend/app/models.py#L1249) |
| tier / tier | Mapped[str] | False | ['String(20)'] {'nullable': 'False', 'default': "'engagement'"} | [backend/app/models.py:1250](../backend/app/models.py#L1250) |
| count / count | Mapped[int] | False | ['Integer'] {'default': '0'} | [backend/app/models.py:1251](../backend/app/models.py#L1251) |
| sessions / sessions | Mapped[int] | False | ['Integer'] {'default': '0'} | [backend/app/models.py:1252](../backend/app/models.py#L1252) |
| authed_count / authed_count | Mapped[int] | False | ['Integer'] {'default': '0'} | [backend/app/models.py:1253](../backend/app/models.py#L1253) |
| computed_at / computed_at | Mapped[datetime] | False | ['DateTime'] {'default': 'lambda: datetime.now(timezone.utc).replace(tzinfo=None)'} | [backend/app/models.py:1254](../backend/app/models.py#L1254) |

Constraints: `[{'path': 'backend/app/models.py', 'line': 1243, 'end_line': 1245, 'owner': 'DailyGoal', 'conditions': [], 'definition': "(UniqueConstraint('day', 'event_name', name='uq_daily_goal_key'),)"}]`

Relationships: `[]`

## Table `daily_pages`

| Python / SQL | Type | Nullable | Column arguments / options | Source |
| --- | --- | --- | --- | --- |
| id / id | Mapped[int] | False | [] {'primary_key': 'True'} | [backend/app/models.py:1264](../backend/app/models.py#L1264) |
| day / day | Mapped[date] | False | ['Date'] {'nullable': 'False', 'index': 'True'} | [backend/app/models.py:1265](../backend/app/models.py#L1265) |
| page / page | Mapped[str] | False | ['String(500)'] {'nullable': 'False'} | [backend/app/models.py:1266](../backend/app/models.py#L1266) |
| views / views | Mapped[int] | False | ['Integer'] {'default': '0'} | [backend/app/models.py:1267](../backend/app/models.py#L1267) |
| visitors / visitors | Mapped[int] | False | ['Integer'] {'default': '0'} | [backend/app/models.py:1268](../backend/app/models.py#L1268) |
| total_dwell_ms / total_dwell_ms | Mapped[int] | False | ["BigInteger().with_variant(Integer, 'sqlite')"] {'default': '0'} | [backend/app/models.py:1269](../backend/app/models.py#L1269) |
| total_active_ms / total_active_ms | Mapped[int] | False | ["BigInteger().with_variant(Integer, 'sqlite')"] {'default': '0'} | [backend/app/models.py:1270](../backend/app/models.py#L1270) |
| avg_scroll_pct / avg_scroll_pct | Mapped[float \| None] | True | ['Numeric(5, 1)'] {} | [backend/app/models.py:1271](../backend/app/models.py#L1271) |
| dead_clicks / dead_clicks | Mapped[int] | False | ['Integer'] {'default': '0'} | [backend/app/models.py:1272](../backend/app/models.py#L1272) |
| computed_at / computed_at | Mapped[datetime] | False | ['DateTime'] {'default': 'lambda: datetime.now(timezone.utc).replace(tzinfo=None)'} | [backend/app/models.py:1273](../backend/app/models.py#L1273) |

Constraints: `[{'path': 'backend/app/models.py', 'line': 1260, 'end_line': 1262, 'owner': 'DailyPage', 'conditions': [], 'definition': "(UniqueConstraint('day', 'page', name='uq_daily_page_key'),)"}]`

Relationships: `[]`

## Table `hypotheses`

| Python / SQL | Type | Nullable | Column arguments / options | Source |
| --- | --- | --- | --- | --- |
| id / id | Mapped[int] | False | [] {'primary_key': 'True'} | [backend/app/models.py:1291](../backend/app/models.py#L1291) |
| statement / statement | Mapped[str] | False | ['String(500)'] {'nullable': 'False'} | [backend/app/models.py:1292](../backend/app/models.py#L1292) |
| rationale / rationale | Mapped[str \| None] | True | ['Text'] {} | [backend/app/models.py:1293](../backend/app/models.py#L1293) |
| verdict / verdict | Mapped[bool \| None] | True | ['Boolean'] {} | [backend/app/models.py:1294](../backend/app/models.py#L1294) |
| confidence / confidence | Mapped[float \| None] | True | ['Numeric(4, 3)'] {} | [backend/app/models.py:1295](../backend/app/models.py#L1295) |
| source / source | Mapped[str] | False | ['String(40)'] {'nullable': 'False', 'default': "'pulse_llm'"} | [backend/app/models.py:1296](../backend/app/models.py#L1296) |
| evidence_json / evidence_json | Mapped[dict \| None] | True | ['JSON'] {} | [backend/app/models.py:1297](../backend/app/models.py#L1297) |
| created_at / created_at | Mapped[datetime] | False | ['DateTime'] {'default': 'lambda: datetime.now(timezone.utc).replace(tzinfo=None)'} | [backend/app/models.py:1298](../backend/app/models.py#L1298) |
| updated_at / updated_at | Mapped[datetime] | False | ['DateTime'] {'default': 'lambda: datetime.now(timezone.utc).replace(tzinfo=None)', 'onupdate': 'lambda: datetime.now(timezone.utc).replace(tzinfo=None)'} | [backend/app/models.py:1299](../backend/app/models.py#L1299) |

Constraints: `[{'path': 'backend/app/models.py', 'line': 1287, 'end_line': 1289, 'owner': 'Hypothesis', 'conditions': [], 'definition': "(Index('ix_hypothesis_verdict', 'verdict', 'updated_at'),)"}]`

Relationships: `[]`

## Table `telegram_outbox`

| Python / SQL | Type | Nullable | Column arguments / options | Source |
| --- | --- | --- | --- | --- |
| id / id | Mapped[int] | False | ["BigInteger().with_variant(Integer, 'sqlite')"] {'primary_key': 'True'} | [backend/app/models.py:1322](../backend/app/models.py#L1322) |
| sent_at / sent_at | Mapped[datetime] | False | ['DateTime'] {'nullable': 'False', 'default': 'lambda: datetime.now(timezone.utc).replace(tzinfo=None)'} | [backend/app/models.py:1325](../backend/app/models.py#L1325) |
| chat_id / chat_id | Mapped[str] | False | ['String(32)'] {'nullable': 'False'} | [backend/app/models.py:1329](../backend/app/models.py#L1329) |
| method / method | Mapped[str] | False | ['String(30)'] {'nullable': 'False'} | [backend/app/models.py:1330](../backend/app/models.py#L1330) |
| kind / kind | Mapped[str] | False | ['String(40)'] {'nullable': 'False', 'default': "'generic'"} | [backend/app/models.py:1331](../backend/app/models.py#L1331) |
| text / text | Mapped[str \| None] | True | ['Text'] {} | [backend/app/models.py:1332](../backend/app/models.py#L1332) |
| payload_json / payload_json | Mapped[dict \| None] | True | ['JSON'] {} | [backend/app/models.py:1333](../backend/app/models.py#L1333) |
| file_name / file_name | Mapped[str \| None] | True | ['String(200)'] {} | [backend/app/models.py:1334](../backend/app/models.py#L1334) |
| file_content / file_content | Mapped[bytes \| None] | True | ['LargeBinary'] {} | [backend/app/models.py:1335](../backend/app/models.py#L1335) |
| ok / ok | Mapped[bool] | False | ['Boolean'] {'nullable': 'False', 'default': 'False'} | [backend/app/models.py:1336](../backend/app/models.py#L1336) |
| telegram_message_id / telegram_message_id | Mapped[int \| None] | True | ['BigInteger'] {} | [backend/app/models.py:1337](../backend/app/models.py#L1337) |
| error / error | Mapped[str \| None] | True | ['String(300)'] {} | [backend/app/models.py:1338](../backend/app/models.py#L1338) |

Constraints: `[{'path': 'backend/app/models.py', 'line': 1317, 'end_line': 1320, 'owner': 'TelegramOutbox', 'conditions': [], 'definition': "(Index('ix_tg_outbox_ts', 'sent_at'), Index('ix_tg_outbox_kind', 'kind', 'sent_at'))"}]`

Relationships: `[]`

## Table `seed_state`

| Python / SQL | Type | Nullable | Column arguments / options | Source |
| --- | --- | --- | --- | --- |
| key / key | Mapped[str] | False | ['String(64)'] {'primary_key': 'True'} | [backend/app/models.py:1351](../backend/app/models.py#L1351) |
| value / value | Mapped[str] | False | ['Text'] {'nullable': 'False'} | [backend/app/models.py:1352](../backend/app/models.py#L1352) |
| updated_at / updated_at | Mapped[datetime] | False | ['DateTime'] {'nullable': 'False', 'default': 'lambda: datetime.now(timezone.utc).replace(tzinfo=None)'} | [backend/app/models.py:1353](../backend/app/models.py#L1353) |

Constraints: `[]`

Relationships: `[]`

## Table `experiments`

| Python / SQL | Type | Nullable | Column arguments / options | Source |
| --- | --- | --- | --- | --- |
| id / id | Mapped[int] | False | [] {'primary_key': 'True'} | [backend/app/models.py:1365](../backend/app/models.py#L1365) |
| key / key | Mapped[str] | False | ['String(120)'] {'nullable': 'False'} | [backend/app/models.py:1366](../backend/app/models.py#L1366) |
| status / status | Mapped[str] | False | ['String(30)'] {'default': "'draft'"} | [backend/app/models.py:1367](../backend/app/models.py#L1367) |
| variants_json / variants_json | Mapped[dict \| None] | True | ['JSON'] {} | [backend/app/models.py:1368](../backend/app/models.py#L1368) |
| traffic_split_json / traffic_split_json | Mapped[dict \| None] | True | ['JSON'] {} | [backend/app/models.py:1369](../backend/app/models.py#L1369) |
| started_at / started_at | Mapped[datetime \| None] | True | ['DateTime'] {} | [backend/app/models.py:1370](../backend/app/models.py#L1370) |
| ended_at / ended_at | Mapped[datetime \| None] | True | ['DateTime'] {} | [backend/app/models.py:1371](../backend/app/models.py#L1371) |
| created_at / created_at | Mapped[datetime] | False | ['DateTime'] {'default': 'lambda: datetime.now(timezone.utc).replace(tzinfo=None)'} | [backend/app/models.py:1372](../backend/app/models.py#L1372) |

Constraints: `[{'path': 'backend/app/models.py', 'line': 1361, 'end_line': 1363, 'owner': 'Experiment', 'conditions': [], 'definition': "(UniqueConstraint('key', name='uq_experiment_key'),)"}]`

Relationships: `[]`

## Table `users`

| Python / SQL | Type | Nullable | Column arguments / options | Source |
| --- | --- | --- | --- | --- |
| id / id | Mapped[uuid.UUID] | False | ['Uuid()'] {'primary_key': 'True', 'default': 'uuid.uuid4'} | [backend/app/models.py:1384](../backend/app/models.py#L1384) |
| status / status | Mapped[str] | False | ['String(20)'] {'nullable': 'False', 'default': "'active'", 'server_default': "'active'"} | [backend/app/models.py:1385](../backend/app/models.py#L1385) |
| display_name / display_name | Mapped[str \| None] | True | ['String(200)'] {} | [backend/app/models.py:1386](../backend/app/models.py#L1386) |
| created_at / created_at | Mapped[datetime] | False | ['DateTime'] {'nullable': 'False', 'default': '_utcnow_naive'} | [backend/app/models.py:1387](../backend/app/models.py#L1387) |

Constraints: `[]`

Relationships: `[{'path': 'backend/app/models.py', 'line': 1389, 'end_line': 1391, 'owner': 'User', 'conditions': [], 'attribute': 'oauth_identities', 'annotation': "Mapped[list['OAuthIdentity']]", 'definition': "relationship(back_populates='user', cascade='all, delete-orphan')"}, {'path': 'backend/app/models.py', 'line': 1392, 'end_line': 1394, 'owner': 'User', 'conditions': [], 'attribute': 'email_credential', 'annotation': "Mapped['EmailCredential \| None']", 'definition': "relationship(back_populates='user', cascade='all, delete-orphan', uselist=False)"}, {'path': 'backend/app/models.py', 'line': 1395, 'end_line': 1397, 'owner': 'User', 'conditions': [], 'attribute': 'consents', 'annotation': "Mapped[list['Consent']]", 'definition': "relationship(back_populates='user', cascade='all, delete-orphan')"}]`

## Table `oauth_identities`

| Python / SQL | Type | Nullable | Column arguments / options | Source |
| --- | --- | --- | --- | --- |
| id / id | Mapped[int] | False | [] {'primary_key': 'True'} | [backend/app/models.py:1407](../backend/app/models.py#L1407) |
| user_id / user_id | Mapped[uuid.UUID] | False | ["ForeignKey('users.id', ondelete='CASCADE')"] {'nullable': 'False'} | [backend/app/models.py:1408](../backend/app/models.py#L1408) |
| provider / provider | Mapped[str] | False | ['String(30)'] {'nullable': 'False'} | [backend/app/models.py:1411](../backend/app/models.py#L1411) |
| provider_user_id / provider_user_id | Mapped[str] | False | ['String(200)'] {'nullable': 'False'} | [backend/app/models.py:1412](../backend/app/models.py#L1412) |
| email / email | Mapped[str \| None] | True | ['String(320)'] {} | [backend/app/models.py:1413](../backend/app/models.py#L1413) |
| email_verified / email_verified | Mapped[bool] | False | ['Boolean'] {'nullable': 'False', 'default': 'True'} | [backend/app/models.py:1414](../backend/app/models.py#L1414) |
| phone / phone | Mapped[str \| None] | True | ['String(32)'] {} | [backend/app/models.py:1417](../backend/app/models.py#L1417) |
| display_name / display_name | Mapped[str \| None] | True | ['String(200)'] {} | [backend/app/models.py:1418](../backend/app/models.py#L1418) |
| avatar_url / avatar_url | Mapped[str \| None] | True | ['String(500)'] {} | [backend/app/models.py:1419](../backend/app/models.py#L1419) |
| locale / locale | Mapped[str \| None] | True | ['String(35)'] {} | [backend/app/models.py:1420](../backend/app/models.py#L1420) |
| created_at / created_at | Mapped[datetime] | False | ['DateTime'] {'nullable': 'False', 'default': '_utcnow_naive'} | [backend/app/models.py:1421](../backend/app/models.py#L1421) |
| last_login_at / last_login_at | Mapped[datetime \| None] | True | ['DateTime'] {} | [backend/app/models.py:1422](../backend/app/models.py#L1422) |

Constraints: `[{'path': 'backend/app/models.py', 'line': 1402, 'end_line': 1405, 'owner': 'OAuthIdentity', 'conditions': [], 'definition': "(UniqueConstraint('provider', 'provider_user_id', name='uq_oauth_provider_subject'), Index('ix_oauth_identity_user', 'user_id'))"}]`

Relationships: `[{'path': 'backend/app/models.py', 'line': 1424, 'end_line': 1424, 'owner': 'OAuthIdentity', 'conditions': [], 'attribute': 'user', 'annotation': "Mapped['User']", 'definition': "relationship(back_populates='oauth_identities')"}]`

## Table `email_credentials`

| Python / SQL | Type | Nullable | Column arguments / options | Source |
| --- | --- | --- | --- | --- |
| id / id | Mapped[int] | False | [] {'primary_key': 'True'} | [backend/app/models.py:1433](../backend/app/models.py#L1433) |
| user_id / user_id | Mapped[uuid.UUID] | False | ["ForeignKey('users.id', ondelete='CASCADE')"] {'nullable': 'False', 'unique': 'True'} | [backend/app/models.py:1434](../backend/app/models.py#L1434) |
| email / email | Mapped[str] | False | ['String(320)'] {'nullable': 'False'} | [backend/app/models.py:1437](../backend/app/models.py#L1437) |
| password_hash / password_hash | Mapped[str] | False | ['String(255)'] {'nullable': 'False'} | [backend/app/models.py:1438](../backend/app/models.py#L1438) |
| email_verified / email_verified | Mapped[bool] | False | ['Boolean'] {'nullable': 'False', 'default': 'False'} | [backend/app/models.py:1439](../backend/app/models.py#L1439) |
| created_at / created_at | Mapped[datetime] | False | ['DateTime'] {'nullable': 'False', 'default': '_utcnow_naive'} | [backend/app/models.py:1440](../backend/app/models.py#L1440) |

Constraints: `[{'path': 'backend/app/models.py', 'line': 1429, 'end_line': 1431, 'owner': 'EmailCredential', 'conditions': [], 'definition': "(UniqueConstraint('email', name='uq_email_credential_email'),)"}]`

Relationships: `[{'path': 'backend/app/models.py', 'line': 1442, 'end_line': 1442, 'owner': 'EmailCredential', 'conditions': [], 'attribute': 'user', 'annotation': "Mapped['User']", 'definition': "relationship(back_populates='email_credential')"}]`

## Table `consents`

| Python / SQL | Type | Nullable | Column arguments / options | Source |
| --- | --- | --- | --- | --- |
| id / id | Mapped[int] | False | [] {'primary_key': 'True'} | [backend/app/models.py:1451](../backend/app/models.py#L1451) |
| user_id / user_id | Mapped[uuid.UUID] | False | ["ForeignKey('users.id', ondelete='CASCADE')"] {'nullable': 'False'} | [backend/app/models.py:1452](../backend/app/models.py#L1452) |
| kind / kind | Mapped[str] | False | ['String(30)'] {'nullable': 'False'} | [backend/app/models.py:1455](../backend/app/models.py#L1455) |
| version / version | Mapped[str] | False | ['String(20)'] {'nullable': 'False'} | [backend/app/models.py:1456](../backend/app/models.py#L1456) |
| granted_at / granted_at | Mapped[datetime] | False | ['DateTime'] {'nullable': 'False', 'default': '_utcnow_naive'} | [backend/app/models.py:1457](../backend/app/models.py#L1457) |
| ip / ip | Mapped[str \| None] | True | ['String(64)'] {} | [backend/app/models.py:1458](../backend/app/models.py#L1458) |
| user_agent / user_agent | Mapped[str \| None] | True | ['String(500)'] {} | [backend/app/models.py:1459](../backend/app/models.py#L1459) |

Constraints: `[{'path': 'backend/app/models.py', 'line': 1447, 'end_line': 1449, 'owner': 'Consent', 'conditions': [], 'definition': "(Index('ix_consent_user', 'user_id'),)"}]`

Relationships: `[{'path': 'backend/app/models.py', 'line': 1461, 'end_line': 1461, 'owner': 'Consent', 'conditions': [], 'attribute': 'user', 'annotation': "Mapped['User']", 'definition': "relationship(back_populates='consents')"}]`

## Table `auth_audit`

| Python / SQL | Type | Nullable | Column arguments / options | Source |
| --- | --- | --- | --- | --- |
| id / id | Mapped[int] | False | [] {'primary_key': 'True'} | [backend/app/models.py:1470](../backend/app/models.py#L1470) |
| user_id / user_id | Mapped[uuid.UUID \| None] | True | ["ForeignKey('users.id', ondelete='CASCADE')"] {'nullable': 'True'} | [backend/app/models.py:1474](../backend/app/models.py#L1474) |
| event / event | Mapped[str] | False | ['String(30)'] {'nullable': 'False'} | [backend/app/models.py:1477](../backend/app/models.py#L1477) |
| ip / ip | Mapped[str \| None] | True | ['String(64)'] {} | [backend/app/models.py:1478](../backend/app/models.py#L1478) |
| user_agent / user_agent | Mapped[str \| None] | True | ['String(500)'] {} | [backend/app/models.py:1479](../backend/app/models.py#L1479) |
| detail / detail | Mapped[str \| None] | True | ['String(200)'] {} | [backend/app/models.py:1480](../backend/app/models.py#L1480) |
| ts / ts | Mapped[datetime] | False | ['DateTime'] {'nullable': 'False', 'default': '_utcnow_naive'} | [backend/app/models.py:1481](../backend/app/models.py#L1481) |

Constraints: `[{'path': 'backend/app/models.py', 'line': 1466, 'end_line': 1468, 'owner': 'AuthAudit', 'conditions': [], 'definition': "(Index('ix_auth_audit_user', 'user_id', 'ts'),)"}]`

Relationships: `[]`

## Scheduler jobs

| Job id | Callable | Trigger / conditions | Distributed lock | Source |
| --- | --- | --- | --- | --- |
| daily_etl | app.tasks.scheduler.daily_update_job | CronTrigger(hour=settings.scheduler_cron_hour, minute=settings.scheduler_cron_minute, timezone='Europe/Moscow') ['settings.scheduler_enabled'] | {'id_expression': "'daily_etl'", 'ttl_expression': '3 * 3600'} | [backend/app/main.py:544](../backend/app/main.py#L544) |
| evening_etl | app.tasks.scheduler.daily_update_job | CronTrigger(hour=settings.scheduler_evening_hour, minute=settings.scheduler_evening_minute, timezone='Europe/Moscow') ['settings.scheduler_enabled'] | {'id_expression': "'evening_etl'", 'ttl_expression': '3 * 3600'} | [backend/app/main.py:559](../backend/app/main.py#L559) |
| calendar_refresh | app.main._calendar_refresh_job | CronTrigger(hour=3, minute=0, timezone='Europe/Moscow') ['settings.scheduler_enabled'] | unresolved | [backend/app/main.py:570](../backend/app/main.py#L570) |
| late_minfin_etl | app.tasks.scheduler.late_minfin_etl_job | CronTrigger(hour=15, minute=0, timezone='Europe/Moscow') ['settings.scheduler_enabled'] | {'id_expression': "'late_minfin_etl'", 'ttl_expression': '3600'} | [backend/app/main.py:582](../backend/app/main.py#L582) |
| late_fred_etl | app.tasks.scheduler.late_fred_etl_job | CronTrigger(hour=settings.scheduler_late_fred_hour, minute=settings.scheduler_late_fred_minute, timezone='Europe/Moscow') ['settings.scheduler_enabled'] | {'id_expression': "'late_fred_etl'", 'ttl_expression': '3600'} | [backend/app/main.py:591](../backend/app/main.py#L591) |
| emiss_regional | app.tasks.scheduler.emiss_regional_job | CronTrigger(hour=7, minute=40, day=25, timezone='Europe/Moscow') ['settings.scheduler_enabled'] | {'id_expression': "'emiss_regional'", 'ttl_expression': '2 * 3600'} | [backend/app/main.py:608](../backend/app/main.py#L608) |
| world_national_core | app.services.world_national_ingest.run_national_core_ingest | CronTrigger(hour=settings.world_eurostat_ingest_hour, minute=10, timezone='Europe/Moscow') ['settings.scheduler_enabled'] | {'id_expression': "'world_national_core'", 'ttl_expression': '3 * 3600'} | [backend/app/main.py:624](../backend/app/main.py#L624) |
| staleness_check | app.tasks.scheduler.staleness_check_job | CronTrigger(hour=10, minute=0, timezone='Europe/Moscow') ['settings.scheduler_enabled'] | unresolved | [backend/app/main.py:813](../backend/app/main.py#L813) |
| ticker_live_pull | app.tasks.ticker_worker.ticker_pull_job | IntervalTrigger(seconds=settings.ticker_pull_interval_seconds) ['settings.scheduler_enabled'] | unresolved | [backend/app/main.py:822](../backend/app/main.py#L822) |
| analytics_rollups_15min | app.tasks.analytics_rollups.rollups_15min_job | IntervalTrigger(minutes=15, start_date=_analytics_start) ['settings.scheduler_enabled'] | {'id_expression': "'analytics_rollups_15min'", 'ttl_expression': '14 * 60'} | [backend/app/main.py:1063](../backend/app/main.py#L1063) |
| analytics_rollups_daily | app.tasks.analytics_rollups.rollups_daily_job | CronTrigger(hour=4, minute=50, timezone='Europe/Moscow') ['settings.scheduler_enabled'] | unresolved | [backend/app/main.py:1072](../backend/app/main.py#L1072) |
| sitemap_build | app.services.sitemap_static.sitemap_build_job | CronTrigger(hour=3, minute=10, timezone='Europe/Moscow') ['settings.scheduler_enabled'] | {'id_expression': "'sitemap_build'", 'ttl_expression': '3 * 3600'} | [backend/app/main.py:1122](../backend/app/main.py#L1122) |
| webmaster_indexing_daily | app.services.webmaster_indexing_daily.webmaster_indexing_daily_job | CronTrigger(hour=8, minute=50, timezone='Europe/Moscow') ['settings.scheduler_enabled'] | {'id_expression': "'webmaster_indexing_daily'", 'ttl_expression': '1800'} | [backend/app/main.py:1133](../backend/app/main.py#L1133) |
| gsc_search_queries | app.services.gsc_client.gsc_search_queries_job | CronTrigger(hour=9, minute=10, timezone='Europe/Moscow') ['settings.scheduler_enabled'] | {'id_expression': "'gsc_search_queries'", 'ttl_expression': '1800'} | [backend/app/main.py:1144](../backend/app/main.py#L1144) |
| world_eurostat_ingest | app.services.world_eurostat_ingest.world_eurostat_ingest_job | CronTrigger(hour=settings.world_eurostat_ingest_hour, minute=settings.world_eurostat_ingest_minute, timezone='Europe/Moscow') ['settings.scheduler_enabled', 'settings.world_eurostat_ingest_enabled'] | {'id_expression': "'world_eurostat_ingest'", 'ttl_expression': '6 * 3600'} | [backend/app/main.py:647](../backend/app/main.py#L647) |
| world_eurostat_ingest_afternoon | app.main.afternoon_eurostat_ingest | CronTrigger(hour=14, minute=20, timezone='Europe/Moscow') ['settings.scheduler_enabled', 'settings.world_eurostat_ingest_enabled'] | {'id_expression': "'world_eurostat_ingest'", 'ttl_expression': '6 * 3600'} | [backend/app/main.py:668](../backend/app/main.py#L668) |
| world_forecast | app.services.world_forecast_pipeline.scheduled_world_forecast_job | CronTrigger(hour=settings.world_forecast_hour, minute=settings.world_forecast_minute, timezone='Europe/Moscow') ['settings.scheduler_enabled', 'settings.world_forecast_enabled'] | {'id_expression': "'world_forecast'", 'ttl_expression': 'WORLD_FORECAST_JOB_LOCK_TTL_SECONDS'} | [backend/app/main.py:688](../backend/app/main.py#L688) |
| us_world_forecast | app.main.scheduled_us_world_forecasts | CronTrigger(hour=5, minute=20, timezone='Europe/Moscow') ['settings.scheduler_enabled', 'settings.us_world_forecast_enabled and (not settings.world_forecast_enabled)'] | {'id_expression': "'us_world_forecast'", 'ttl_expression': 'WORLD_FORECAST_JOB_LOCK_TTL_SECONDS'} | [backend/app/main.py:720](../backend/app/main.py#L720) |
| europe_world_forecast | app.main.scheduled_europe_world_forecasts | CronTrigger(hour=21, minute=0, timezone='Europe/Moscow') ['settings.scheduler_enabled', 'settings.europe_world_forecast_enabled and (not settings.world_forecast_enabled)'] | {'id_expression': "'europe_world_forecast'", 'ttl_expression': 'WORLD_FORECAST_JOB_LOCK_TTL_SECONDS'} | [backend/app/main.py:753](../backend/app/main.py#L753) |
| world_subnational_ingest | app.services.world_subnational_ingest.world_subnational_ingest_job | CronTrigger(hour=settings.world_subnational_ingest_hour, minute=settings.world_subnational_ingest_minute, timezone='Europe/Moscow') ['settings.scheduler_enabled', 'settings.world_subnational_ingest_enabled'] | {'id_expression': "'world_subnational_ingest'", 'ttl_expression': '4 * 3600'} | [backend/app/main.py:770](../backend/app/main.py#L770) |
| world_bea_regional | app.services.world_bea_regional.world_bea_regional_job | CronTrigger(day_of_week='tue', hour=settings.world_bea_regional_ingest_hour, minute=settings.world_bea_regional_ingest_minute, timezone='Europe/Moscow') ['settings.scheduler_enabled', 'settings.world_bea_regional_ingest_enabled'] | {'id_expression': "'world_bea_regional'", 'ttl_expression': '6 * 3600'} | [backend/app/main.py:791](../backend/app/main.py#L791) |
| analytics_hourly | app.tasks.analytics_scheduler.analytics_hourly_job | CronTrigger(minute=15, timezone='Europe/Moscow') ['settings.scheduler_enabled', 'settings.analytics_scheduler_enabled'] | unresolved | [backend/app/main.py:845](../backend/app/main.py#L845) |
| analytics_daily | app.tasks.analytics_scheduler.analytics_daily_job | CronTrigger(hour=settings.analytics_scheduler_cron_hour, minute=settings.analytics_scheduler_cron_minute, timezone='Europe/Moscow') ['settings.scheduler_enabled', 'settings.analytics_scheduler_enabled'] | unresolved | [backend/app/main.py:852](../backend/app/main.py#L852) |
| acquisition_daily | app.tasks.analytics_scheduler.acquisition_daily_job | CronTrigger(hour='8,14,20', minute=20, timezone='Europe/Moscow') ['settings.scheduler_enabled', 'settings.analytics_enabled and settings.yandex_metrika_read_token'] | unresolved | [backend/app/main.py:878](../backend/app/main.py#L878) |
| webmaster_recrawl | app.services.webmaster_recrawl.recrawl_daily_job | CronTrigger(hour=9, minute=10, timezone='Europe/Moscow') ['settings.scheduler_enabled', 'settings.webmaster_recrawl_enabled and settings.yandex_webmaster_token'] | unresolved | [backend/app/main.py:893](../backend/app/main.py#L893) |
| partner_revenue_daily | app.tasks.analytics_scheduler.partner_revenue_daily_job | CronTrigger(hour=8, minute=30, timezone='Europe/Moscow') ['settings.scheduler_enabled', 'partner_configured()'] | unresolved | [backend/app/main.py:933](../backend/app/main.py#L933) |
| webmaster_queries_daily | app.tasks.analytics_scheduler.webmaster_queries_daily_job | CronTrigger(hour=8, minute=40, timezone='Europe/Moscow') ['settings.scheduler_enabled', 'settings.yandex_webmaster_token'] | unresolved | [backend/app/main.py:946](../backend/app/main.py#L946) |
| indexing_report_weekly | app.services.webmaster_indexing_report.indexing_report_job | CronTrigger(day_of_week='mon', hour=9, minute=30, timezone='Europe/Moscow') ['settings.scheduler_enabled', 'settings.yandex_webmaster_token'] | unresolved | [backend/app/main.py:959](../backend/app/main.py#L959) |
| indexnow_drain | app.services.indexnow.indexnow_drain_job | CronTrigger(minute='*/10', timezone='Europe/Moscow') ['settings.scheduler_enabled', 'settings.indexnow_enabled and settings.indexnow_key'] | unresolved | [backend/app/main.py:975](../backend/app/main.py#L975) |
| indexnow_warm | app.services.indexnow.indexnow_warm_job | CronTrigger(day_of_week='tue', hour=6, minute=40, timezone='Europe/Moscow') ['settings.scheduler_enabled', 'settings.indexnow_enabled and settings.indexnow_key'] | unresolved | [backend/app/main.py:982](../backend/app/main.py#L982) |
| indexnow_history | app.services.indexnow.indexnow_history_job | CronTrigger(hour=4, minute=30, timezone='Europe/Moscow') ['settings.scheduler_enabled', 'settings.indexnow_enabled and settings.indexnow_key'] | unresolved | [backend/app/main.py:989](../backend/app/main.py#L989) |
| telegram_daily_digest | app.tasks.analytics_scheduler.telegram_daily_digest_job | CronTrigger(hour=settings.telegram_digest_cron_hour, minute=settings.telegram_digest_cron_minute, timezone='Europe/Moscow') ['settings.scheduler_enabled', 'settings.telegram_digest_enabled'] | unresolved | [backend/app/main.py:1002](../backend/app/main.py#L1002) |
| pulse_snapshot | app.services.pulse_report.pulse_snapshot_job | CronTrigger(hour=23, minute=57, timezone='Europe/Moscow') ['settings.scheduler_enabled', 'settings.pulse_enabled'] | unresolved | [backend/app/main.py:1021](../backend/app/main.py#L1021) |
| pulse_report | app.services.pulse_report.pulse_report_job | CronTrigger(hour=settings.pulse_report_cron_hour, minute=settings.pulse_report_cron_minute, timezone='Europe/Moscow') ['settings.scheduler_enabled', 'settings.pulse_enabled'] | unresolved | [backend/app/main.py:1028](../backend/app/main.py#L1028) |
| behavior_retention | app.tasks.analytics_scheduler.behavior_retention_job | CronTrigger(hour=4, minute=10, timezone='Europe/Moscow') ['settings.scheduler_enabled', 'settings.behavior_events_enabled'] | unresolved | [backend/app/main.py:1047](../backend/app/main.py#L1047) |
| geoip_monthly_update | app.services.geoip.download_geoip_db | CronTrigger(day=3, hour=5, minute=0, timezone='Europe/Moscow') ['settings.scheduler_enabled', 'settings.geoip_auto_download'] | unresolved | [backend/app/main.py:1085](../backend/app/main.py#L1085) |
| clickhouse_sync | app.services.clickhouse_sync.clickhouse_sync_job | IntervalTrigger(minutes=15, start_date=_analytics_start) ['settings.scheduler_enabled', 'settings.clickhouse_enabled'] | {'id_expression': "'clickhouse_sync'", 'ttl_expression': '14 * 60'} | [backend/app/main.py:1097](../backend/app/main.py#L1097) |
| telegram_poll | app.services.telegram_bot.telegram_poll_job | IntervalTrigger(seconds=30) ['settings.scheduler_enabled', 'settings.telegram_poller_enabled'] | unresolved | [backend/app/main.py:1110](../backend/app/main.py#L1110) |
| webmaster_recrawl_ru | app.services.webmaster_recrawl.recrawl_daily_job | CronTrigger(hour=9, minute=15, timezone='Europe/Moscow') ['settings.scheduler_enabled', 'settings.webmaster_recrawl_enabled and settings.yandex_webmaster_token', 'settings.apex_locale_en'] | unresolved | [backend/app/main.py:906](../backend/app/main.py#L906) |

## Settings declarations

| Environment | Type / default | Read sites | Source |
| --- | --- | --- | --- |
| RUSTATS_APP_NAME | str = 'Forecast Economy API' | 2 | [backend/app/config.py:7](../backend/app/config.py#L7) |
| RUSTATS_DEBUG | bool = False | 9 | [backend/app/config.py:8](../backend/app/config.py#L8) |
| RUSTATS_PUBLIC_BASE_URL | str = 'https://forecasteconomy.com' | 3 | [backend/app/config.py:12](../backend/app/config.py#L12) |
| RUSTATS_APEX_LOCALE_EN | bool = False | 10 | [backend/app/config.py:14](../backend/app/config.py#L14) |
| RUSTATS_GEO_LOCALE_REDIRECT_ENABLED | bool = False | 1 | [backend/app/config.py:16](../backend/app/config.py#L16) |
| RUSTATS_GEO_RU_COUNTRY_CODES | str = 'RU,BY,KZ,UA,AM,AZ,GE,KG,TJ,TM,UZ,MD' | 1 | [backend/app/config.py:18](../backend/app/config.py#L18) |
| RUSTATS_BROWSER_LANG_REDIRECT_ENABLED | bool = False | 0 | [backend/app/config.py:22](../backend/app/config.py#L22) |
| RUSTATS_BROWSER_LANG_MIN_QUALITY | float = 0.6 | 0 | [backend/app/config.py:23](../backend/app/config.py#L23) |
| RUSTATS_LOCALE_PREFERENCE_COOKIE | str = 'fe_locale_pref' | 2 | [backend/app/config.py:24](../backend/app/config.py#L24) |
| RUSTATS_DATABASE_URL | str = 'postgresql+asyncpg://rustats:rustats@localhost:5432/rustats' | 6 | [backend/app/config.py:27](../backend/app/config.py#L27) |
| RUSTATS_DATABASE_ECHO | bool = False | 2 | [backend/app/config.py:28](../backend/app/config.py#L28) |
| RUSTATS_DB_POOL_SIZE | int = 10 | 1 | [backend/app/config.py:38](../backend/app/config.py#L38) |
| RUSTATS_DB_MAX_OVERFLOW | int = 15 | 2 | [backend/app/config.py:39](../backend/app/config.py#L39) |
| RUSTATS_DB_POOL_TIMEOUT | int = 3 | 1 | [backend/app/config.py:40](../backend/app/config.py#L40) |
| RUSTATS_DB_STATEMENT_TIMEOUT_MS | int = 30000 | 1 | [backend/app/config.py:41](../backend/app/config.py#L41) |
| RUSTATS_DB_IDLE_IN_TRANSACTION_TIMEOUT_MS | int = 120000 | 1 | [backend/app/config.py:42](../backend/app/config.py#L42) |
| RUSTATS_ANALYTICS_DB_POOL_SIZE | int = 2 | 1 | [backend/app/config.py:45](../backend/app/config.py#L45) |
| RUSTATS_ANALYTICS_DB_MAX_OVERFLOW | int = 2 | 2 | [backend/app/config.py:46](../backend/app/config.py#L46) |
| RUSTATS_ANALYTICS_DB_POOL_TIMEOUT | int = 15 | 1 | [backend/app/config.py:47](../backend/app/config.py#L47) |
| RUSTATS_ANALYTICS_DB_STATEMENT_TIMEOUT_MS | int = 60000 | 1 | [backend/app/config.py:48](../backend/app/config.py#L48) |
| RUSTATS_ANALYTICS_DB_IDLE_IN_TRANSACTION_TIMEOUT_MS | int = 120000 | 1 | [backend/app/config.py:49](../backend/app/config.py#L49) |
| RUSTATS_SITEMAP_DIR | str = '/var/www/sitemaps' | 1 | [backend/app/config.py:51](../backend/app/config.py#L51) |
| RUSTATS_GOOGLE_SITE_VERIFICATION | str = '' | 2 | [backend/app/config.py:53](../backend/app/config.py#L53) |
| RUSTATS_BING_SITE_VERIFICATION | str = '' | 2 | [backend/app/config.py:55](../backend/app/config.py#L55) |
| RUSTATS_GSC_ACCESS_TOKEN | str = '' | 3 | [backend/app/config.py:57](../backend/app/config.py#L57) |
| RUSTATS_GSC_CREDENTIALS_FILE | str = '' | 3 | [backend/app/config.py:59](../backend/app/config.py#L59) |
| RUSTATS_GSC_SITE_URL | str = '' | 1 | [backend/app/config.py:61](../backend/app/config.py#L61) |
| RUSTATS_SCRAPE_BLOCK_COUNTRIES | str = '' | 1 | [backend/app/config.py:65](../backend/app/config.py#L65) |
| RUSTATS_SCRAPE_BIND_ENABLED | bool = True | 1 | [backend/app/config.py:68](../backend/app/config.py#L68) |
| RUSTATS_SCRAPE_BIND_SECRET | str = '' | 1 | [backend/app/config.py:69](../backend/app/config.py#L69) |
| RUSTATS_SCRAPE_BLOCK_HOSTING | bool = False | 0 | [backend/app/config.py:72](../backend/app/config.py#L72) |
| RUSTATS_SCRAPE_CHALLENGE_ENABLED | bool = True | 1 | [backend/app/config.py:74](../backend/app/config.py#L74) |
| RUSTATS_SCRAPE_CHALLENGE_MIN_CORES | int = 48 | 1 | [backend/app/config.py:75](../backend/app/config.py#L75) |
| RUSTATS_REDIS_URL | str = 'redis://localhost:6379/0' | 4 | [backend/app/config.py:78](../backend/app/config.py#L78) |
| RUSTATS_STATE_REDIS_URL | str = '' | 2 | [backend/app/config.py:82](../backend/app/config.py#L82) |
| RUSTATS_CACHE_TTL_DATA | int = 3600 | 15 | [backend/app/config.py:83](../backend/app/config.py#L83) |
| RUSTATS_CACHE_TTL_META | int = 300 | 2 | [backend/app/config.py:84](../backend/app/config.py#L84) |
| RUSTATS_CBR_BASE_URL | str = 'https://www.cbr.ru' | 7 | [backend/app/config.py:87](../backend/app/config.py#L87) |
| RUSTATS_CBR_REQUEST_TIMEOUT | int = 90 | 7 | [backend/app/config.py:88](../backend/app/config.py#L88) |
| RUSTATS_MINFIN_BASE_URL | str = 'https://minfin.gov.ru' | 0 | [backend/app/config.py:89](../backend/app/config.py#L89) |
| RUSTATS_ROSSTAT_BASE_URL | str = 'https://rosstat.gov.ru/storage/mediabank' | 1 | [backend/app/config.py:92](../backend/app/config.py#L92) |
| RUSTATS_ROSSTAT_CPI_TEMPLATE | str = 'ipc_mes_{mm}-{yyyy}.xlsx' | 1 | [backend/app/config.py:93](../backend/app/config.py#L93) |
| RUSTATS_ROSSTAT_CA_CERT | str = str(Path(__file__).parent.parent / 'certs' / 'russiantrustedca2024.pem') | 7 | [backend/app/config.py:94](../backend/app/config.py#L94) |
| RUSTATS_ROSSTAT_MAX_MONTHS_BACK | int = 6 | 2 | [backend/app/config.py:95](../backend/app/config.py#L95) |
| RUSTATS_ROSSTAT_REQUEST_TIMEOUT | int = 30 | 9 | [backend/app/config.py:96](../backend/app/config.py#L96) |
| RUSTATS_SCHEDULER_ENABLED | bool = True | 2 | [backend/app/config.py:99](../backend/app/config.py#L99) |
| RUSTATS_SCHEDULER_CRON_HOUR | int = 6 | 2 | [backend/app/config.py:100](../backend/app/config.py#L100) |
| RUSTATS_SCHEDULER_CRON_MINUTE | int = 0 | 2 | [backend/app/config.py:101](../backend/app/config.py#L101) |
| RUSTATS_SCHEDULER_EVENING_HOUR | int = 20 | 2 | [backend/app/config.py:104](../backend/app/config.py#L104) |
| RUSTATS_SCHEDULER_EVENING_MINUTE | int = 0 | 2 | [backend/app/config.py:105](../backend/app/config.py#L105) |
| RUSTATS_SCHEDULER_LATE_FRED_HOUR | int = 23 | 1 | [backend/app/config.py:110](../backend/app/config.py#L110) |
| RUSTATS_SCHEDULER_LATE_FRED_MINUTE | int = 30 | 1 | [backend/app/config.py:111](../backend/app/config.py#L111) |
| RUSTATS_TICKER_PULL_INTERVAL_SECONDS | int = 8 | 2 | [backend/app/config.py:112](../backend/app/config.py#L112) |
| RUSTATS_WORLD_EUROSTAT_INGEST_ENABLED | bool = True | 1 | [backend/app/config.py:117](../backend/app/config.py#L117) |
| RUSTATS_WORLD_EUROSTAT_INGEST_SHADOW | bool = False | 1 | [backend/app/config.py:120](../backend/app/config.py#L120) |
| RUSTATS_WORLD_EUROSTAT_INGEST_HOUR | int = 2 | 2 | [backend/app/config.py:121](../backend/app/config.py#L121) |
| RUSTATS_WORLD_EUROSTAT_INGEST_MINUTE | int = 20 | 1 | [backend/app/config.py:122](../backend/app/config.py#L122) |
| RUSTATS_WORLD_FORECAST_ENABLED | bool = False | 3 | [backend/app/config.py:125](../backend/app/config.py#L125) |
| RUSTATS_US_WORLD_FORECAST_ENABLED | bool = True | 1 | [backend/app/config.py:128](../backend/app/config.py#L128) |
| RUSTATS_EUROPE_WORLD_FORECAST_ENABLED | bool = True | 1 | [backend/app/config.py:129](../backend/app/config.py#L129) |
| RUSTATS_US_WORLD_FORECAST_DAILY_LIMIT | int = 500 | 1 | [backend/app/config.py:130](../backend/app/config.py#L130) |
| RUSTATS_EUROPE_WORLD_FORECAST_DAILY_LIMIT | int = 3000 | 1 | [backend/app/config.py:131](../backend/app/config.py#L131) |
| RUSTATS_WORLD_FORECAST_HOUR | int = 4 | 1 | [backend/app/config.py:132](../backend/app/config.py#L132) |
| RUSTATS_WORLD_FORECAST_MINUTE | int = 20 | 1 | [backend/app/config.py:133](../backend/app/config.py#L133) |
| RUSTATS_WORLD_FORECAST_MAX_AGE_DAYS | int = 30 | 1 | [backend/app/config.py:136](../backend/app/config.py#L136) |
| RUSTATS_WORLD_FORECAST_CACHE_BUMP_EVERY | int = 200 | 1 | [backend/app/config.py:138](../backend/app/config.py#L138) |
| RUSTATS_WORLD_FORECAST_PRIORITY_COUNTRIES | str = 'united-states,germany,france,united-kingdom,italy,spain,austria,canada,japan,china,india,brazil,mexico,australia,south-korea,netherlands,poland' | 1 | [backend/app/config.py:141](../backend/app/config.py#L141) |
| RUSTATS_WORLD_SUBNATIONAL_INGEST_ENABLED | bool = True | 1 | [backend/app/config.py:146](../backend/app/config.py#L146) |
| RUSTATS_WORLD_SUBNATIONAL_INGEST_HOUR | int = 3 | 1 | [backend/app/config.py:147](../backend/app/config.py#L147) |
| RUSTATS_WORLD_SUBNATIONAL_INGEST_MINUTE | int = 40 | 1 | [backend/app/config.py:148](../backend/app/config.py#L148) |
| RUSTATS_WORLD_BEA_REGIONAL_INGEST_ENABLED | bool = True | 1 | [backend/app/config.py:149](../backend/app/config.py#L149) |
| RUSTATS_WORLD_BEA_REGIONAL_INGEST_HOUR | int = 4 | 1 | [backend/app/config.py:150](../backend/app/config.py#L150) |
| RUSTATS_WORLD_BEA_REGIONAL_INGEST_MINUTE | int = 20 | 1 | [backend/app/config.py:151](../backend/app/config.py#L151) |
| RUSTATS_CALENDAR_ROSSTAT_PLAN_ENABLED | bool = True | 1 | [backend/app/config.py:156](../backend/app/config.py#L156) |
| RUSTATS_TELEGRAM_BOT_TOKEN | str = '' | 5 | [backend/app/config.py:159](../backend/app/config.py#L159) |
| RUSTATS_TELEGRAM_CHAT_ID | str = '' | 3 | [backend/app/config.py:160](../backend/app/config.py#L160) |
| RUSTATS_FORECAST_STEPS | int = 12 | 2 | [backend/app/config.py:163](../backend/app/config.py#L163) |
| RUSTATS_SEO_APP_SHELL_URL | str = 'http://frontend/__spa-index.html' | 2 | [backend/app/config.py:166](../backend/app/config.py#L166) |
| RUSTATS_INDEXNOW_ENABLED | bool = True | 7 | [backend/app/config.py:170](../backend/app/config.py#L170) |
| RUSTATS_INDEXNOW_KEY | str = 'a7c41d92e85f4b06b3d8f17c29e6a504' | 11 | [backend/app/config.py:171](../backend/app/config.py#L171) |
| RUSTATS_INDEXNOW_ENDPOINT | str = 'https://yandex.com/indexnow' | 2 | [backend/app/config.py:172](../backend/app/config.py#L172) |
| RUSTATS_INDEXNOW_DAILY_SEND_CAP | int = 30000 | 1 | [backend/app/config.py:174](../backend/app/config.py#L174) |
| RUSTATS_INDEXNOW_HISTORY_DAILY_CAP | int = 30000 | 1 | [backend/app/config.py:177](../backend/app/config.py#L177) |
| RUSTATS_INDEXNOW_HISTORY_YEAR_MIN | int = 2018 | 1 | [backend/app/config.py:178](../backend/app/config.py#L178) |
| RUSTATS_WEBMASTER_RECRAWL_ENABLED | bool = True | 1 | [backend/app/config.py:182](../backend/app/config.py#L182) |
| RUSTATS_METRICS_TOKEN | str = '' | 2 | [backend/app/config.py:185](../backend/app/config.py#L185) |
| RUSTATS_FRONTEND_EVENTS_ENABLED | bool = True | 1 | [backend/app/config.py:192](../backend/app/config.py#L192) |
| RUSTATS_BEHAVIOR_EVENTS_ENABLED | bool = True | 2 | [backend/app/config.py:198](../backend/app/config.py#L198) |
| RUSTATS_BEHAVIOR_BATCH_MAX_EVENTS | int = 500 | 1 | [backend/app/config.py:199](../backend/app/config.py#L199) |
| RUSTATS_BEHAVIOR_RAW_RETENTION_DAYS | int = 0 | 1 | [backend/app/config.py:200](../backend/app/config.py#L200) |
| RUSTATS_GEOIP_DB_PATH | str = '/app/geoip/dbip-city-lite.mmdb' | 3 | [backend/app/config.py:205](../backend/app/config.py#L205) |
| RUSTATS_GEOIP_DOWNLOAD_URL_TEMPLATE | str = 'https://download.db-ip.com/free/dbip-city-lite-{yyyy}-{mm}.mmdb.gz' | 1 | [backend/app/config.py:206](../backend/app/config.py#L206) |
| RUSTATS_GEOIP_ASN_DB_PATH | str = '/app/geoip/dbip-asn-lite.mmdb' | 2 | [backend/app/config.py:209](../backend/app/config.py#L209) |
| RUSTATS_GEOIP_ASN_DOWNLOAD_URL_TEMPLATE | str = 'https://download.db-ip.com/free/dbip-asn-lite-{yyyy}-{mm}.mmdb.gz' | 1 | [backend/app/config.py:210](../backend/app/config.py#L210) |
| RUSTATS_GEOIP_AUTO_DOWNLOAD | bool = True | 1 | [backend/app/config.py:213](../backend/app/config.py#L213) |
| RUSTATS_CLICKHOUSE_ENABLED | bool = False | 6 | [backend/app/config.py:217](../backend/app/config.py#L217) |
| RUSTATS_CLICKHOUSE_HOST | str = 'clickhouse' | 1 | [backend/app/config.py:218](../backend/app/config.py#L218) |
| RUSTATS_CLICKHOUSE_PORT | int = 8123 | 1 | [backend/app/config.py:219](../backend/app/config.py#L219) |
| RUSTATS_CLICKHOUSE_DB | str = 'analytics' | 1 | [backend/app/config.py:220](../backend/app/config.py#L220) |
| RUSTATS_CLICKHOUSE_USER | str = 'default' | 1 | [backend/app/config.py:221](../backend/app/config.py#L221) |
| RUSTATS_CLICKHOUSE_PASSWORD | str = '' | 1 | [backend/app/config.py:222](../backend/app/config.py#L222) |
| RUSTATS_DIRECT_API_TOKEN | str = '' | 1 | [backend/app/config.py:225](../backend/app/config.py#L225) |
| RUSTATS_YANDEX_PARTNER_CLIENT_ID | str = '' | 0 | [backend/app/config.py:227](../backend/app/config.py#L227) |
| RUSTATS_YANDEX_PARTNER_CLIENT_SECRET | str = '' | 0 | [backend/app/config.py:228](../backend/app/config.py#L228) |
| RUSTATS_YANDEX_PARTNER_TOKEN | str = '' | 1 | [backend/app/config.py:229](../backend/app/config.py#L229) |
| RUSTATS_ANALYTICS_ENABLED | bool = False | 7 | [backend/app/config.py:232](../backend/app/config.py#L232) |
| RUSTATS_ANALYTICS_SCHEDULER_ENABLED | bool = False | 2 | [backend/app/config.py:233](../backend/app/config.py#L233) |
| RUSTATS_ANALYTICS_SCHEDULER_CRON_HOUR | int = 7 | 2 | [backend/app/config.py:234](../backend/app/config.py#L234) |
| RUSTATS_ANALYTICS_SCHEDULER_CRON_MINUTE | int = 20 | 2 | [backend/app/config.py:235](../backend/app/config.py#L235) |
| RUSTATS_ANALYTICS_API_TOKEN | str = '' | 3 | [backend/app/config.py:236](../backend/app/config.py#L236) |
| RUSTATS_ANALYTICS_BASE_URL | str = 'https://forecasteconomy.com' | 2 | [backend/app/config.py:239](../backend/app/config.py#L239) |
| RUSTATS_ANALYTICS_ALLOWED_COUNTER_IDS | str = '107136069' | 9 | [backend/app/config.py:240](../backend/app/config.py#L240) |
| RUSTATS_ANALYTICS_ALLOWED_HOSTS | str = 'forecasteconomy.com,ru.forecasteconomy.com' | 2 | [backend/app/config.py:241](../backend/app/config.py#L241) |
| RUSTATS_ANALYTICS_DEFAULT_RETENTION_DAYS | int = 180 | 0 | [backend/app/config.py:242](../backend/app/config.py#L242) |
| RUSTATS_ANALYTICS_RAW_LOG_RETENTION_DAYS | int = 90 | 0 | [backend/app/config.py:243](../backend/app/config.py#L243) |
| RUSTATS_ANALYTICS_BACKFILL_DAYS | int = 30 | 0 | [backend/app/config.py:244](../backend/app/config.py#L244) |
| RUSTATS_ANALYTICS_REQUEST_TIMEOUT | int = 30 | 1 | [backend/app/config.py:245](../backend/app/config.py#L245) |
| RUSTATS_ANALYTICS_LIVE_WRITES_ENABLED | bool = False | 2 | [backend/app/config.py:246](../backend/app/config.py#L246) |
| RUSTATS_YANDEX_METRIKA_READ_TOKEN | str = '' | 9 | [backend/app/config.py:248](../backend/app/config.py#L248) |
| RUSTATS_YANDEX_METRIKA_WRITE_TOKEN | str = '' | 3 | [backend/app/config.py:249](../backend/app/config.py#L249) |
| RUSTATS_YANDEX_WEBMASTER_TOKEN | str = '' | 10 | [backend/app/config.py:250](../backend/app/config.py#L250) |
| RUSTATS_AUTH_SESSION_TTL_SECONDS | int = 60 * 60 * 24 * 30 | 3 | [backend/app/config.py:253](../backend/app/config.py#L253) |
| RUSTATS_AUTH_COOKIE_SECURE | bool = False | 7 | [backend/app/config.py:254](../backend/app/config.py#L254) |
| RUSTATS_AUTH_COOKIE_DOMAIN | str = '' | 4 | [backend/app/config.py:255](../backend/app/config.py#L255) |
| RUSTATS_AUTH_OAUTH_STATE_TTL_SECONDS | int = 600 | 2 | [backend/app/config.py:256](../backend/app/config.py#L256) |
| RUSTATS_AUTH_LOGIN_MAX_FAILS | int = 8 | 1 | [backend/app/config.py:257](../backend/app/config.py#L257) |
| RUSTATS_AUTH_LOGIN_LOCKOUT_SECONDS | int = 900 | 1 | [backend/app/config.py:258](../backend/app/config.py#L258) |
| RUSTATS_AUTH_FAKE_PROVIDER_ENABLED | bool = False | 3 | [backend/app/config.py:260](../backend/app/config.py#L260) |
| RUSTATS_AUTH_PUBLIC_BASE_URL | str = 'http://localhost:5173' | 4 | [backend/app/config.py:262](../backend/app/config.py#L262) |
| RUSTATS_OAUTH_GOOGLE_CLIENT_ID | str = '' | 2 | [backend/app/config.py:265](../backend/app/config.py#L265) |
| RUSTATS_OAUTH_GOOGLE_CLIENT_SECRET | str = '' | 2 | [backend/app/config.py:266](../backend/app/config.py#L266) |
| RUSTATS_OAUTH_GOOGLE_REDIRECT_URI | str = '' | 0 | [backend/app/config.py:267](../backend/app/config.py#L267) |
| RUSTATS_OAUTH_YANDEX_CLIENT_ID | str = '' | 2 | [backend/app/config.py:270](../backend/app/config.py#L270) |
| RUSTATS_OAUTH_YANDEX_CLIENT_SECRET | str = '' | 2 | [backend/app/config.py:271](../backend/app/config.py#L271) |
| RUSTATS_OAUTH_YANDEX_SCOPE | str = '' | 1 | [backend/app/config.py:272](../backend/app/config.py#L272) |
| RUSTATS_OAUTH_VK_CLIENT_ID | str = '' | 2 | [backend/app/config.py:274](../backend/app/config.py#L274) |
| RUSTATS_OAUTH_VK_CLIENT_SECRET | str = '' | 0 | [backend/app/config.py:275](../backend/app/config.py#L275) |
| RUSTATS_OAUTH_VK_SERVICE_KEY | str = '' | 0 | [backend/app/config.py:276](../backend/app/config.py#L276) |
| RUSTATS_OAUTH_VK_SCOPE | str = '' | 1 | [backend/app/config.py:277](../backend/app/config.py#L277) |
| RUSTATS_OAUTH_YANDEX_REDIRECT_URI | str = '' | 0 | [backend/app/config.py:280](../backend/app/config.py#L280) |
| RUSTATS_OAUTH_VK_REDIRECT_URI | str = '' | 0 | [backend/app/config.py:281](../backend/app/config.py#L281) |
| RUSTATS_DOWNLOAD_ANON_LIMIT | int = 0 | 4 | [backend/app/config.py:284](../backend/app/config.py#L284) |
| RUSTATS_DOWNLOAD_ANON_WINDOW_SECONDS | int = 60 * 60 * 24 | 2 | [backend/app/config.py:285](../backend/app/config.py#L285) |
| RUSTATS_DOWNLOAD_ANON_HISTORY_YEARS | int = 3 | 2 | [backend/app/config.py:289](../backend/app/config.py#L289) |
| RUSTATS_TELEGRAM_DIGEST_ENABLED | bool = False | 1 | [backend/app/config.py:292](../backend/app/config.py#L292) |
| RUSTATS_TELEGRAM_DIGEST_CRON_HOUR | int = 9 | 2 | [backend/app/config.py:293](../backend/app/config.py#L293) |
| RUSTATS_TELEGRAM_DIGEST_CRON_MINUTE | int = 0 | 2 | [backend/app/config.py:294](../backend/app/config.py#L294) |
| RUSTATS_TELEGRAM_DIGEST_CHAT_IDS | str = '' | 1 | [backend/app/config.py:298](../backend/app/config.py#L298) |
| RUSTATS_TELEGRAM_REALTIME_ALERTS_ENABLED | bool = True | 3 | [backend/app/config.py:301](../backend/app/config.py#L301) |
| RUSTATS_PULSE_ENABLED | bool = False | 1 | [backend/app/config.py:305](../backend/app/config.py#L305) |
| RUSTATS_PULSE_CHAT_ID | str = '' | 5 | [backend/app/config.py:306](../backend/app/config.py#L306) |
| RUSTATS_PULSE_REPORT_CRON_HOUR | int = 9 | 2 | [backend/app/config.py:307](../backend/app/config.py#L307) |
| RUSTATS_PULSE_REPORT_CRON_MINUTE | int = 5 | 2 | [backend/app/config.py:308](../backend/app/config.py#L308) |
| RUSTATS_OPENROUTER_API_KEY | str = '' | 2 | [backend/app/config.py:310](../backend/app/config.py#L310) |
| RUSTATS_OPENROUTER_MODEL | str = 'anthropic/claude-sonnet-5' | 1 | [backend/app/config.py:311](../backend/app/config.py#L311) |
| RUSTATS_OPENROUTER_PROXY_URL | str = '' | 2 | [backend/app/config.py:317](../backend/app/config.py#L317) |
| RUSTATS_ETL_HTTP_PROXY_URL | str = '' | 1 | [backend/app/config.py:321](../backend/app/config.py#L321) |
| RUSTATS_ETL_SOCKS_PROXY_URL | str = '' | 1 | [backend/app/config.py:324](../backend/app/config.py#L324) |
| RUSTATS_TELEGRAM_POLLER_ENABLED | bool = False | 1 | [backend/app/config.py:326](../backend/app/config.py#L326) |
| RUSTATS_ADMIN_EMAILS | str = 'admin_forecasteconomy@forecasteconomy.com' | 3 | [backend/app/config.py:330](../backend/app/config.py#L330) |

## Registries and declarations

| Symbol | Kind | Literal keys / dynamic expansion | Source |
| --- | --- | --- | --- |
| alembic.versions.20260510_rename_rosstat_sdds_parser_types._RENAMES | List | sequence/source expression | [backend/alembic/versions/20260510_rename_rosstat_sdds_parser_types.py:35](../backend/alembic/versions/20260510_rename_rosstat_sdds_parser_types.py#L35) |
| app.api.admin_bi._DASHBOARD_LOCK | Call | computed source expression | [backend/app/api/admin_bi.py:60](../backend/app/api/admin_bi.py#L60) |
| app.api.admin_bi._INFLIGHT | Dict | sequence/source expression | [backend/app/api/admin_bi.py:71](../backend/app/api/admin_bi.py#L71) |
| app.api.admin_bi._LAST_ERROR | Dict | sequence/source expression | [backend/app/api/admin_bi.py:72](../backend/app/api/admin_bi.py#L72) |
| app.api.analytics._BEHAVIOR_COLUMN_KEYS | Set | sequence/source expression | [backend/app/api/analytics.py:294](../backend/app/api/analytics.py#L294) |
| app.api.analytics._BEHAVIOR_TYPES | Set | sequence/source expression | [backend/app/api/analytics.py:297](../backend/app/api/analytics.py#L297) |
| app.api.analytics._CLOCK_PAST_LIMIT | Call | computed source expression | [backend/app/api/analytics.py:521](../backend/app/api/analytics.py#L521) |
| app.api.analytics._CLOCK_FUTURE_LIMIT | Call | computed source expression | [backend/app/api/analytics.py:522](../backend/app/api/analytics.py#L522) |
| app.api.auth._EMAIL_RE | Call | computed source expression | [backend/app/api/auth.py:33](../backend/app/api/auth.py#L33) |
| app.api.calendar.PUBLIC_CONFIDENCES | Tuple | sequence/source expression | [backend/app/api/calendar.py:20](../backend/app/api/calendar.py#L20) |
| app.api.dashboard.FLAGSHIP_MAP | Dict | 'prices', 'rates', 'finance', 'labor', 'gdp', 'population', 'trade', 'business', 'science' | [backend/app/api/dashboard.py:21](../backend/app/api/dashboard.py#L21) |
| app.api.embed._CODE_RE | Call | computed source expression | [backend/app/api/embed.py:32](../backend/app/api/embed.py#L32) |
| app.api.embed._COLOR_RE | Call | computed source expression | [backend/app/api/embed.py:33](../backend/app/api/embed.py#L33) |
| app.api.export._MSK | Call | computed source expression | [backend/app/api/export.py:34](../backend/app/api/export.py#L34) |
| app.api.forecasts._CODE_RE | Call | computed source expression | [backend/app/api/forecasts.py:21](../backend/app/api/forecasts.py#L21) |
| app.api.forecasts.DERIVED_CPI_FORECASTS | Set | sequence/source expression | [backend/app/api/forecasts.py:23](../backend/app/api/forecasts.py#L23) |
| app.api.indicators._YOY_TARGET | Dict | 'monthly', 'quarterly', 'annual', 'weekly', 'daily' | [backend/app/api/indicators.py:33](../backend/app/api/indicators.py#L33) |
| app.api.indicators._YOY_TOLERANCE | Call | computed source expression | [backend/app/api/indicators.py:40](../backend/app/api/indicators.py#L40) |
| app.api.indicators._CODE_RE | Call | computed source expression | [backend/app/api/indicators.py:294](../backend/app/api/indicators.py#L294) |
| app.api.oauth._REDIRECT_OVERRIDES | Dict | 'google', 'yandex', 'vk' | [backend/app/api/oauth.py:109](../backend/app/api/oauth.py#L109) |
| app.api.regions.HEADLINE_TABLES | Dict | '1.1', '3.4', '2.10.1', '8.1', '8.2', '10.1', '20.1', '3.12' | [backend/app/api/regions.py:32](../backend/app/api/regions.py#L32) |
| app.api.regions.HEADLINE_TABLES_EN | Dict | '1.1', '3.4', '2.10.1', '8.1', '8.2', '10.1', '20.1', '3.12' | [backend/app/api/regions.py:43](../backend/app/api/regions.py#L43) |
| app.api.regions.HEADLINE_INDEX_TO_GROWTH | Dict | '20.1' | [backend/app/api/regions.py:58](../backend/app/api/regions.py#L58) |
| app.api.regions.HEADLINE_INDEX_TO_GROWTH_EN | Dict | '20.1' | [backend/app/api/regions.py:62](../backend/app/api/regions.py#L62) |
| app.api.regions.LANDING_TABLES | Tuple | sequence/source expression | [backend/app/api/regions.py:67](../backend/app/api/regions.py#L67) |
| app.api.regions.MONTH_NAMES_RU | Tuple | sequence/source expression | [backend/app/api/regions.py:569](../backend/app/api/regions.py#L569) |
| app.api.seo_pages._RENDER_SEM | Call | computed source expression | [backend/app/api/seo_pages.py:153](../backend/app/api/seo_pages.py#L153) |
| app.api.sitemap._ANNUAL_SUMMARY_EN | Dict | 'Рост цен за год', 'Итог за год (сумма)', 'Значение на конец года', 'Среднее за год' | [backend/app/api/sitemap.py:90](../backend/app/api/sitemap.py#L90) |
| app.api.sitemap._OG_INDICATOR_ALIASES | Dict | 'inflation', 'gdp' | [backend/app/api/sitemap.py:632](../backend/app/api/sitemap.py#L632) |
| app.api.system._START_TIME | Call | computed source expression | [backend/app/api/system.py:16](../backend/app/api/system.py#L16) |
| app.api.ticker.TICKER_SET_RUSSIA | Tuple | sequence/source expression | [backend/app/api/ticker.py:59](../backend/app/api/ticker.py#L59) |
| app.api.ticker.TICKER_SET_WORLD | Tuple | sequence/source expression | [backend/app/api/ticker.py:67](../backend/app/api/ticker.py#L67) |
| app.api.ticker.TICKER_SETS | Dict | 'russia', 'world' | [backend/app/api/ticker.py:75](../backend/app/api/ticker.py#L75) |
| app.api.ticker.TICKER_CODES | Call | computed source expression | [backend/app/api/ticker.py:80](../backend/app/api/ticker.py#L80) |
| app.api.world._MEDIAN_BENCHMARK_CONCEPTS | Call | computed source expression | [backend/app/api/world.py:644](../backend/app/api/world.py#L644) |
| app.api.world._AVERAGE_CONCEPTS | Call | computed source expression | [backend/app/api/world.py:651](../backend/app/api/world.py#L651) |
| app.api.world._AGGREGATION_SOURCE_TO_TARGET | Dict | 'daily', 'weekly', 'monthly', 'quarterly' | [backend/app/api/world.py:713](../backend/app/api/world.py#L713) |
| app.core.cache._WORLD_COUNTRIES_KEY_RE | Call | computed source expression | [backend/app/core/cache.py:385](../backend/app/core/cache.py#L385) |
| app.data.bi_targets.NORTH_STAR_MILESTONES | List | sequence/source expression | [backend/app/data/bi_targets.py:12](../backend/app/data/bi_targets.py#L12) |
| app.data.bi_targets.TARGETS | Dict | 'visits_per_day', 'acquisition_search_share', 'engagement_rate', 'micro_conversion_rate', 'macro_conversion_rate', 'retention_7d' | [backend/app/data/bi_targets.py:14](../backend/app/data/bi_targets.py#L14) |
| app.data.cpi_provenance.CPI_YOY_CODES | Call | computed source expression | [backend/app/data/cpi_provenance.py:2](../backend/app/data/cpi_provenance.py#L2) |
| app.data.eurostat_country_visibility.EUROSTAT_SUPPRESS_LISTED_CODES | Call | computed source expression | [backend/app/data/eurostat_country_visibility.py:25](../backend/app/data/eurostat_country_visibility.py#L25) |
| app.data.eurostat_deep_expand.NEVER_EXPAND_DIMS | Call | computed source expression | [backend/app/data/eurostat_deep_expand.py:15](../backend/app/data/eurostat_deep_expand.py#L15) |
| app.data.eurostat_deep_expand.EXPANDABLE_DIMS | Call | computed source expression | [backend/app/data/eurostat_deep_expand.py:20](../backend/app/data/eurostat_deep_expand.py#L20) |
| app.data.eurostat_deep_expand.TOTALISH_BASE | Call | computed source expression | [backend/app/data/eurostat_deep_expand.py:30](../backend/app/data/eurostat_deep_expand.py#L30) |
| app.data.eurostat_dim_labels_en.NACE_EN | Dict | 'A', 'B', 'C', 'D', 'E', 'F', 'G', 'G47', 'G47_FOOD', 'G47_NFOOD', 'G47_NFOOD_X_G473', 'G47_X_G473', 'G473', 'M_STS', 'H-N_X_K', 'F_CC11_X_CC113', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'B-D', 'B-E', 'B-E36', 'B-S_X_O', 'B-S_X_O_S94', 'B-N', 'B-S', 'G-J', 'G-N', 'K-N', 'O-S', 'P-S_X_S94', 'C10', 'C10-C12', 'C13-C15', 'C16-C18', 'C19', 'C20', 'C21', 'C22-C23', 'C24-C25', 'C26', 'C27', 'C28', 'C29-C30', 'C31-C33', 'D35', 'E36', 'F41', 'F42', 'F43', 'G45', 'G46', 'H49', 'H50', 'H51', 'H52', 'H53', 'I55', 'I56', 'J58', 'J59-J60', 'J61', 'J62-J63', 'K64', 'K65', 'K66', 'M69-M71', 'M72', 'M73-M75', 'N77', 'N78', 'N79', 'N80-N82' | [backend/app/data/eurostat_dim_labels_en.py:13](../backend/app/data/eurostat_dim_labels_en.py#L13) |
| app.data.eurostat_dim_labels_en.INDIC_BT_EN | Dict | 'REG', 'BKRT', 'BPRM_DW', 'BPRM_SQM', 'EMP', 'PRD', 'HW', 'WAGE', 'COST', 'NETTUR', 'NETTUR_DOM', 'NETTUR_NDOM', 'NETTUR_NDOM_EU', 'PRC_PRR', 'PRC_PRR_DOM', 'PRC_PRR_NDOM', 'PRC_PRR_B2B', 'PRC_IMP', 'VOL_SLS' | [backend/app/data/eurostat_dim_labels_en.py:101](../backend/app/data/eurostat_dim_labels_en.py#L101) |
| app.data.eurostat_dim_labels_en.SEX_EN | Dict | 'M', 'F' | [backend/app/data/eurostat_dim_labels_en.py:123](../backend/app/data/eurostat_dim_labels_en.py#L123) |
| app.data.eurostat_dim_labels_en.AGE_EN | Dict | 'Y15-24', 'Y15-74', 'Y25-74', 'Y15-64', 'Y20-64', 'Y_LT25', 'Y25-54', 'Y55-64', 'Y65-74' | [backend/app/data/eurostat_dim_labels_en.py:128](../backend/app/data/eurostat_dim_labels_en.py#L128) |
| app.data.eurostat_dim_labels_en.CPA2_1_EN | Dict | 'CPA_F41001', 'CPA_F41001_41002', 'CPA_F41001_X_410014', 'CPA_F410011', 'CPA_F410012_410013', 'CPA_F410014', 'CPA_F41002', 'CPA_F41002_X_410023', 'CPA_F410023', 'CPA_B-E36' | [backend/app/data/eurostat_dim_labels_en.py:140](../backend/app/data/eurostat_dim_labels_en.py#L140) |
| app.data.eurostat_dim_labels_en.LABELS_BY_DIM | Dict | 'nace_r2', 'nace_r1', 'indic_bt', 'sex', 'age', 'cpa2_1' | [backend/app/data/eurostat_dim_labels_en.py:153](../backend/app/data/eurostat_dim_labels_en.py#L153) |
| app.data.eurostat_dim_labels_en._TOTALISH | Call | computed source expression | [backend/app/data/eurostat_dim_labels_en.py:162](../backend/app/data/eurostat_dim_labels_en.py#L162) |
| app.data.eurostat_dim_labels_en._NACE_BY_ACTIVITY_TAIL | Call | computed source expression | [backend/app/data/eurostat_dim_labels_en.py:164](../backend/app/data/eurostat_dim_labels_en.py#L164) |
| app.data.eurostat_dim_labels_en._AGE_RANGE | Call | computed source expression | [backend/app/data/eurostat_dim_labels_en.py:169](../backend/app/data/eurostat_dim_labels_en.py#L169) |
| app.data.eurostat_dim_labels_en._AGE_GE | Call | computed source expression | [backend/app/data/eurostat_dim_labels_en.py:170](../backend/app/data/eurostat_dim_labels_en.py#L170) |
| app.data.eurostat_dim_labels_en._AGE_LT | Call | computed source expression | [backend/app/data/eurostat_dim_labels_en.py:171](../backend/app/data/eurostat_dim_labels_en.py#L171) |
| app.data.eurostat_dim_labels_en._AGE_YEAR | Call | computed source expression | [backend/app/data/eurostat_dim_labels_en.py:172](../backend/app/data/eurostat_dim_labels_en.py#L172) |
| app.data.eurostat_dim_labels_ru.SEX_RU | Dict | 'M', 'F' | [backend/app/data/eurostat_dim_labels_ru.py:15](../backend/app/data/eurostat_dim_labels_ru.py#L15) |
| app.data.eurostat_dim_labels_ru.HHCOMP_RU | Dict | 'A1', 'A1_DCH', 'A1_LT64', 'A1_GE65', 'A2', 'A2_DCH1', 'A2_DCH2', 'A2_DCH_GE3', 'A2_2LT65', 'A2_GE1_GE65', 'A_GE2_DCH', 'A_GE2_NDCH', 'A_GE3', 'A_GE3_DCH', 'DCH', 'NDCH', 'M1', 'F1', 'HH_NOCHILD', 'HH_CHILD' | [backend/app/data/eurostat_dim_labels_ru.py:24](../backend/app/data/eurostat_dim_labels_ru.py#L24) |
| app.data.eurostat_dim_labels_ru.AGE_RU | Dict | 'Y15-24', 'Y15-74', 'Y25-74', 'Y15-64', 'Y20-64', 'Y_GT20', 'UNK', 'Y18-24', 'Y18-64', 'Y18-74', 'Y16-64', 'Y16-74', 'Y25-64', 'Y25-54', 'Y25-49', 'Y35-49', 'Y50-64', 'Y55-64', 'Y65-74', 'Y15-19', 'Y16-19', 'Y20-24', 'Y25-29', 'Y25-34', 'Y30-34', 'Y35-39', 'Y40-44', 'Y45-49', 'Y50-54', 'Y55-59', 'Y60-64', 'Y0-4', 'Y0-14', 'Y0-15', 'Y0-17', 'Y0-29', 'Y5-9', 'Y5-14', 'Y5-29', 'Y10-14', 'Y15-29', 'Y15-34', 'Y16-18', 'Y_LT1', 'Y_LT5', 'Y_LT6', 'Y_LT15', 'Y_LT18', 'Y_LT20', 'Y_LT25', 'Y_GE15', 'Y_GE18', 'Y_GE25', 'Y_GE45', 'Y_GE50', 'Y_GE55', 'Y_GE60', 'Y_GE65', 'Y_GE75', 'Y_GE80', 'Y_GE85', 'Y1', 'Y4', 'Y14', 'Y15', 'Y16', 'Y17', 'Y18', 'Y19', 'Y20', 'Y21', 'Y22', 'Y23', 'Y24', 'Y25', 'Y26', 'D0', 'D1', 'D1-6', 'D7-27', 'D28-364', 'D_LT7', 'D_LT28', 'LFD' | [backend/app/data/eurostat_dim_labels_ru.py:51](../backend/app/data/eurostat_dim_labels_ru.py#L51) |
| app.data.eurostat_dim_labels_ru.NACE_RU | Dict | 'A', 'B', 'C', 'D', 'E', 'F', 'G', 'G47', 'G47_FOOD', 'G47_NFOOD', 'G47_NFOOD_X_G473', 'G47_X_G473', 'G473', 'M_STS', 'H-N_X_K', 'F_CC11_X_CC113', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'B-D', 'B-E', 'B-E36', 'B-S_X_O', 'B-S_X_O_S94', 'B-N', 'B-S', 'G-J', 'G-N', 'K-N', 'O-S', 'P-S_X_S94', 'C10', 'C10-C12', 'C13-C15', 'C16-C18', 'C19', 'C20', 'C21', 'C22-C23', 'C24-C25', 'C26', 'C27', 'C28', 'C29-C30', 'C31-C33', 'D35', 'E36', 'F41', 'F42', 'F43', 'G45', 'G46', 'H49', 'H50', 'H51', 'H52', 'H53', 'I55', 'I56', 'J58', 'J59-J60', 'J61', 'J62-J63', 'K64', 'K65', 'K66', 'M69-M71', 'M72', 'M73-M75', 'N77', 'N78', 'N79', 'N80-N82' | [backend/app/data/eurostat_dim_labels_ru.py:146](../backend/app/data/eurostat_dim_labels_ru.py#L146) |
| app.data.eurostat_dim_labels_ru.INDIC_BT_RU | Dict | 'REG', 'BKRT', 'BPRM_DW', 'BPRM_SQM', 'EMP', 'PRD', 'HW', 'WAGE', 'COST', 'NETTUR', 'NETTUR_DOM', 'NETTUR_NDOM', 'NETTUR_NDOM_EU', 'PRC_PRR', 'PRC_PRR_DOM', 'PRC_PRR_NDOM', 'PRC_PRR_B2B', 'PRC_IMP', 'VOL_SLS' | [backend/app/data/eurostat_dim_labels_ru.py:238](../backend/app/data/eurostat_dim_labels_ru.py#L238) |
| app.data.eurostat_dim_labels_ru.CPA2_1_RU | Dict | 'CPA_F41001', 'CPA_F41001_41002', 'CPA_F41001_X_410014', 'CPA_F410011', 'CPA_F410012_410013', 'CPA_F410014', 'CPA_F41002', 'CPA_F41002_X_410023', 'CPA_F410023', 'CPA_B-E36' | [backend/app/data/eurostat_dim_labels_ru.py:263](../backend/app/data/eurostat_dim_labels_ru.py#L263) |
| app.data.eurostat_dim_labels_ru.INDIC_RU | Dict | 'BS-ESI-I', 'BS-CCI-BAL', 'BS-ICI', 'BS-ICI-BAL', 'BS-SCI', 'BS-SCI-BAL', 'BS-RCI', 'BS-RCI-BAL', 'BS-CSMCI', 'BS-CSMCI-BAL', 'BS-FCI', 'BS-BCI', 'BS-FS-LY', 'BS-FS-NY', 'BS-PBH-NTY', 'BS-HI-NY', 'BS-EEI-I', 'BS-OTEB', 'BS-RPBS', 'BS-SABC', 'BS-CTA-BAL', 'BS-IPT', 'BS-LHI-I', 'BS-INO-BAL', 'BS-ICU-PC', 'BS-IEME', 'BS-IEME-BAL', 'BS-CEME-BAL', 'BS-REM', 'BS-REM-BAL', 'BS-SEEM', 'BS-IOB', 'BS-IEOB', 'BS-COB-BAL', 'BS-CPE-BAL', 'BS-IPE', 'BS-ISFP', 'BS-ISPE', 'BS-ICPC-BAL', 'BS-SAEM', 'BS-SARM', 'BS-REBS', 'BS-ROP', 'BS-RPE', 'BS-RAS', 'BS-QP-PC', 'BS-CP3M-EXEU-BAL', 'BS-CP3M-FMIEU-BAL', 'BS-GES-LY', 'BS-GES-NY', 'BS-PT-LY', 'BS-PT-NY', 'BS-PE3M', 'BS-MP-NY', 'BS-MP-PR', 'BS-SV-NY', 'BS-UE-NY', 'BS-SFSH', 'BS-FLB1-PC', 'BS-FLB2-PC', 'BS-FLB3-PC', 'BS-FLB4-PC', 'BS-FLB5-PC', 'BS-FLB6-PC', 'BS-FLP1-PC', 'BS-FLP2-PC', 'BS-FLP3-PC', 'BS-FLP4-PC', 'BS-FLP5-PC', 'BS-FLP6-PC', 'BS-FLBA1-PC', 'BS-FLBA2-PC', 'BS-FLBA3-PC', 'BS-FLBA4-PC', 'BS-FLBA5-PC', 'BS-FLBA6-PC', 'BS-FLBA7-PC', 'IS-IP', 'IS-IP-SCA', 'IS-PPI', 'IS-EPI', 'IS-IMPR', 'IS-WSI', 'IS-HWI', 'LM-LCI-TOT', 'LM-LCI-SAL', 'LM-UN-T-TOT', 'JVR', 'ET-T', 'ACT', 'EMP', 'EMP_LFS', 'LTU', 'VLTU', 'LM-LCI-OTH', 'EXP_PPS_EU27_2020_HAB', 'VI_PPS_EU27_2020_HAB', 'MF-LTGBY-RT', 'MF-DDI-RT', 'MF-3MI-RT', 'NEER37', 'NEER42', 'REER37CPI', 'REER42CPI', 'CP-HIE', 'CP-HI00XE', 'CP-HI00XEF', 'CP-HI00XEFU', 'CP-HI00XES', 'CP-HI00XTB', 'CP-HI01', 'CP-HI02', 'CP-HI03', 'CP-HI04', 'CP-HI05', 'CP-HI06', 'CP-HI07', 'CP-HI08', 'CP-HI09', 'CP-HI10', 'CP-HI11', 'CP-HI12', 'CP-HI13', 'CP-HIF', 'CP-HIFU', 'CP-HIG', 'CP-HIIG', 'CP-HIIGXE', 'CP-HIS', 'INV_TOT', 'INV_GOV', 'INV_BSN', 'INV_HH' | [backend/app/data/eurostat_dim_labels_ru.py:278](../backend/app/data/eurostat_dim_labels_ru.py#L278) |
| app.data.eurostat_dim_labels_ru.INDIC_DE_RU | Dict | 'DEATHRATE', 'DEATH', 'DEATH_NR', 'GBIRTHRT', 'GDEATHRT', 'LIFEXP', 'TOTFERRT', 'JAN', 'FJAN', 'MJAN', 'AVG', 'FAVG', 'MAVG', 'FDEATH', 'MDEATH', 'FLBIRTH', 'MLBIRTH', 'AGEMOTH', 'AGEMOTH1', 'AGEMOTH2', 'AGEMOTH3', 'AGEMOTH4_MAX', 'MEDAGEMOTH', 'MARRIAGE', 'MAR', 'NMAR', 'NMARPCT', 'GNUPRT', 'GDIVRT', 'DIV', 'DIVMARPCT', 'INFMORRT', 'NEOMORRT', 'ENEOMORRT', 'LFOEMORRT', 'PERIMORRT', 'LBIRTH', 'LBIRTH_NR', 'DEPRATIO1', 'OLDDEP1', 'NATGROWRT', 'NATGROW', 'NATT', 'NATTRT', 'CNMIGRATRT', 'CNMIGRAT', 'MIGT', 'MIGTRT', 'POPT', 'POPTRT', 'GROWRT', 'GROW', 'POPSHARE_EU27_2020', 'POPSHARE', 'PC_Y0_14', 'PC_Y15_24', 'PC_Y25_49', 'PC_Y50_64', 'PC_Y65_79', 'PC_Y65_MAX', 'PC_Y80_MAX', 'FMAR1CUM', 'MMAR1CUM', 'MAGEMAR1', 'FAGEMAR1', 'FMAR1PC', 'MMAR1PC', 'PROBDEATH', 'PROBSURV', 'LBIRTHR1PC', 'LBIRTHR2PC', 'LBIRTHR3PC', 'LBIRTHR4_MAXPC', 'GBIRTHRT_THSP', 'GDEATHRT_THSP', 'TOTPYLIVED', 'PYLIVED', 'UNK' | [backend/app/data/eurostat_dim_labels_ru.py:420](../backend/app/data/eurostat_dim_labels_ru.py#L420) |
| app.data.eurostat_dim_labels_ru.BOP_ITEM_RU | Dict | 'S', 'D1', 'SDA1', 'D752W', 'R1WR', 'D61Z', 'D5Z' | [backend/app/data/eurostat_dim_labels_ru.py:501](../backend/app/data/eurostat_dim_labels_ru.py#L501) |
| app.data.eurostat_dim_labels_ru.SECTOR_RU | Dict | 'S1', 'S13', 'TOT_SEC' | [backend/app/data/eurostat_dim_labels_ru.py:511](../backend/app/data/eurostat_dim_labels_ru.py#L511) |
| app.data.eurostat_dim_labels_ru.SIEC_RU | Dict | 'TOTAL', 'G3000', 'G3100', 'G3200', 'O4000', 'O4000XBIO', 'O4100_TOT', 'O4100_TOT_4200-4500', 'O4200', 'O4630', 'O4640', 'O4651', 'O4652', 'O4652XR5210B', 'O4661', 'O4661XR5230B', 'O4669', 'O4671', 'O46711', 'O46712', 'O4680', 'O4681', 'O4682', 'O4694', 'E7000', 'C0000', 'C0000X0350-0370', 'C0100', 'C0110', 'C0121', 'C0129', 'C0210', 'C0220', 'P1100', 'S2000', 'R5210B' | [backend/app/data/eurostat_dim_labels_ru.py:518](../backend/app/data/eurostat_dim_labels_ru.py#L518) |
| app.data.eurostat_dim_labels_ru.NRG_BAL_RU | Dict | 'GID_OBS', 'GEP', 'TI', 'IMP', 'EXP', 'FC_E', 'IPRD', 'PRD', 'PPRD', 'TI_EHG_MAP', 'DL', 'STATDIFF', 'STK_CHG', 'TOS', 'REN', 'REN_ELC', 'REN_TRA', 'REN_HEAT_CL', 'FC_OTH_HH_E', 'FC_TRA_E' | [backend/app/data/eurostat_dim_labels_ru.py:557](../backend/app/data/eurostat_dim_labels_ru.py#L557) |
| app.data.eurostat_dim_labels_ru.RSKPOVTH_RU | Dict | 'B_40', 'B_50', 'B_60', 'A_40', 'A_50', 'A_60' | [backend/app/data/eurostat_dim_labels_ru.py:580](../backend/app/data/eurostat_dim_labels_ru.py#L580) |
| app.data.eurostat_dim_labels_ru.PLANT_TEC_RU | Dict | 'CAP_NET_ELC' | [backend/app/data/eurostat_dim_labels_ru.py:589](../backend/app/data/eurostat_dim_labels_ru.py#L589) |
| app.data.eurostat_dim_labels_ru.PPP_CAT_RU | Dict | 'GDP' | [backend/app/data/eurostat_dim_labels_ru.py:593](../backend/app/data/eurostat_dim_labels_ru.py#L593) |
| app.data.eurostat_dim_labels_ru.CURRENCY_RU | Dict | 'MIO_EUR', 'EUR', 'NAC' | [backend/app/data/eurostat_dim_labels_ru.py:597](../backend/app/data/eurostat_dim_labels_ru.py#L597) |
| app.data.eurostat_dim_labels_ru.QUANT_INC_RU | Dict | 'Q1', 'Q2', 'Q3', 'Q4', 'Q5' | [backend/app/data/eurostat_dim_labels_ru.py:603](../backend/app/data/eurostat_dim_labels_ru.py#L603) |
| app.data.eurostat_dim_labels_ru.LEV_DIFF_RU | Dict | 'GRT_DIF_SOME', 'GRT_DIF', 'SOME_DIF' | [backend/app/data/eurostat_dim_labels_ru.py:611](../backend/app/data/eurostat_dim_labels_ru.py#L611) |
| app.data.eurostat_dim_labels_ru.AGEDEF_RU | Dict | 'COMPLET', 'REACH' | [backend/app/data/eurostat_dim_labels_ru.py:617](../backend/app/data/eurostat_dim_labels_ru.py#L617) |
| app.data.eurostat_dim_labels_ru.C_BIRTH_RU | Dict | 'NAT', 'FOR', 'UNK', 'EU27_2020_FOR', 'EU28_FOR', 'NEU27_2020_FOR', 'NEU28_FOR' | [backend/app/data/eurostat_dim_labels_ru.py:622](../backend/app/data/eurostat_dim_labels_ru.py#L622) |
| app.data.eurostat_dim_labels_ru.N_ITEM_RU | Dict | '0' | [backend/app/data/eurostat_dim_labels_ru.py:632](../backend/app/data/eurostat_dim_labels_ru.py#L632) |
| app.data.eurostat_dim_labels_ru.MONTH_RU | Dict | 'M01', 'M02', 'M03', 'M04', 'M05', 'M06', 'M07', 'M08', 'M09', 'M10', 'M11', 'M12', 'UNK' | [backend/app/data/eurostat_dim_labels_ru.py:636](../backend/app/data/eurostat_dim_labels_ru.py#L636) |
| app.data.eurostat_dim_labels_ru.MIG_RU | Dict | 'MIG_CAG', 'MIG_COG', 'MIG_DCOG', 'MIG_NDCOG', 'MIG_ING', 'MIG_NRG' | [backend/app/data/eurostat_dim_labels_ru.py:653](../backend/app/data/eurostat_dim_labels_ru.py#L653) |
| app.data.eurostat_dim_labels_ru.ISCED11_RU | Dict | 'ED0', 'ED01', 'ED0-2', 'ED0-8', 'ED02-8', 'ED1', 'ED1_2', 'ED2', 'ED24', 'ED25', 'ED3', 'ED3SW', 'ED3_4', 'ED3-4', 'ED3-8', 'ED4', 'ED44', 'ED45', 'ED5', 'ED54', 'ED5SW', 'ED5-8', 'ED02', 'ED34', 'ED35', 'ED55', 'ED64', 'ED65', 'ED74', 'ED75', 'ED6', 'ED6-8', 'ED7', 'ED7-8', 'ED8', 'NAP', 'NRP', 'UNK' | [backend/app/data/eurostat_dim_labels_ru.py:666](../backend/app/data/eurostat_dim_labels_ru.py#L666) |
| app.data.eurostat_dim_labels_ru.WSTATUS_RU | Dict | 'EMP', 'UNE', 'INAC', 'NEMP', 'SAL', 'NSAL', 'SELF', 'CFAM', 'NSEEK', 'SEEK', 'UNK' | [backend/app/data/eurostat_dim_labels_ru.py:711](../backend/app/data/eurostat_dim_labels_ru.py#L711) |
| app.data.eurostat_dim_labels_ru.CITIZEN_RU | Dict | 'NAT', 'FOR', 'STLS', 'EU27_2020_FOR', 'NEU27_2020_FOR', 'EU28_FOR', 'NEU28_FOR', 'FOR_EU', 'FOR_NEU', 'EUR_FOR', 'NEUR_FOR', 'UNK' | [backend/app/data/eurostat_dim_labels_ru.py:729](../backend/app/data/eurostat_dim_labels_ru.py#L729) |
| app.data.eurostat_dim_labels_ru.DEG_URB_RU | Dict | 'DEG1', 'DEG2', 'DEG3' | [backend/app/data/eurostat_dim_labels_ru.py:748](../backend/app/data/eurostat_dim_labels_ru.py#L748) |
| app.data.eurostat_dim_labels_ru.WORKTIME_RU | Dict | 'FT', 'PT', 'TOT_FTE' | [backend/app/data/eurostat_dim_labels_ru.py:758](../backend/app/data/eurostat_dim_labels_ru.py#L758) |
| app.data.eurostat_dim_labels_ru.STATINFO_RU | Dict | 'MEAN_EI', 'MED_EI', 'MEAN', 'MED', 'SHARE', 'GINI_HND', 'GINI', 'S80_S20', 'QSR', 'TC', 'R_GE60', 'R_GE40', 'R_GE50', 'R_GE70', 'AVG', 'PC', 'NR', 'THS', 'END' | [backend/app/data/eurostat_dim_labels_ru.py:768](../backend/app/data/eurostat_dim_labels_ru.py#L768) |
| app.data.eurostat_dim_labels_ru.STK_FLOW_RU | Dict | 'CRE', 'DEB', 'BAL', 'BAL_RT', 'NET', 'ASS', 'LIAB', 'CREDIT', 'DEBIT' | [backend/app/data/eurostat_dim_labels_ru.py:794](../backend/app/data/eurostat_dim_labels_ru.py#L794) |
| app.data.eurostat_dim_labels_ru.SIZECLAS_RU | Dict | '0-1', '0-9', '1-9', '2-9', '10-19', '10-49', '20-49', '50-249', 'GE10', 'GE50', 'GE250', 'LT10', 'LT50', 'SME', 'NSME' | [backend/app/data/eurostat_dim_labels_ru.py:810](../backend/app/data/eurostat_dim_labels_ru.py#L810) |
| app.data.eurostat_dim_labels_ru.COICOP_RU | Dict | 'CP01', 'CP02', 'CP03', 'CP04', 'CP05', 'CP06', 'CP07', 'CP08', 'CP09', 'CP10', 'CP11', 'CP12', 'TOT_X_NRG', 'TOT_X_NRG_FOOD', 'TOT_X_FOOD_S', 'FOOD', 'NRG', 'SERV', 'IGD_NNRG' | [backend/app/data/eurostat_dim_labels_ru.py:832](../backend/app/data/eurostat_dim_labels_ru.py#L832) |
| app.data.eurostat_dim_labels_ru.DURATION_RU | Dict | 'M_LT1', 'M1', 'M1-2', 'M1-3', 'M3-5', 'M3-6', 'M6-11', 'M6-12', 'M_GE12', 'M_GE24', 'Y_LT1', 'Y1', 'Y1-2', 'Y_GE1', 'Y_GE2', 'Y2', 'Y3', 'Y4', 'Y5', 'Y_LT5', 'Y5-9', 'Y6', 'Y7', 'Y8', 'Y9', 'NLTMP', 'TEMP', 'W0-20', 'W21', 'W22', 'W23', 'W24', 'W25', 'W26', 'W27', 'W28', 'W29', 'W30', 'W31', 'W32', 'W33', 'W34', 'W35', 'W36', 'W37', 'W38', 'W39', 'W_GE40', 'UNK' | [backend/app/data/eurostat_dim_labels_ru.py:858](../backend/app/data/eurostat_dim_labels_ru.py#L858) |
| app.data.eurostat_dim_labels_ru.PARTNER_RU | Dict | 'WORLD', 'FOR', 'NAT', 'EXT_EU', 'EXT_EU27_2020', 'EXT_EU28', 'INTRA_EU', 'INTRA_EU27_2020', 'INTRA_EU28', 'EU27_2020', 'EU28', 'EA', 'EA19', 'EA20', 'EU27_2020_EXTRA', 'EU27_2020_INTRA', 'UNK', 'STLS' | [backend/app/data/eurostat_dim_labels_ru.py:915](../backend/app/data/eurostat_dim_labels_ru.py#L915) |
| app.data.eurostat_dim_labels_ru.MARSTA_RU | Dict | 'SIN', 'MAR', 'DIV', 'WID', 'SEP', 'UNM', 'REP', 'LUN', 'ENDLUN', 'DTHLUN', 'DISLUN', 'UNK' | [backend/app/data/eurostat_dim_labels_ru.py:940](../backend/app/data/eurostat_dim_labels_ru.py#L940) |
| app.data.eurostat_dim_labels_ru.NA_ITEM_RU | Dict | 'B1GQ', 'B1G', 'B1GQ_R_POP', 'P3', 'P3_S13', 'P31', 'P31_S13', 'P31_S14', 'P31_S15', 'P31_S14_S15', 'P32', 'P32_S13', 'P41', 'P5', 'P51G', 'P52', 'P53', 'P6', 'P61', 'P62', 'P7', 'P71', 'P72', 'B11', 'B111', 'B112', 'B2A3G', 'B3G', 'B5G', 'B6G', 'B9', 'B9_T3', 'B9F', 'NLG_B9', 'NET_LEND', 'GD', 'GD_NAC', 'TE', 'TR', 'D1', 'D11', 'D12', 'D2', 'D21', 'D3', 'D4', 'D41', 'D5', 'D6', 'D61', 'D62', 'D7', 'D8', 'D9', 'P2', 'P1', 'YA0', 'F2', 'F3', 'F4', 'F5', 'F6', 'F7', 'F8' | [backend/app/data/eurostat_dim_labels_ru.py:959](../backend/app/data/eurostat_dim_labels_ru.py#L959) |
| app.data.eurostat_dim_labels_ru.LABELS_BY_DIM | Dict | 'sex', 'hhcomp', 'age', 'nace_r2', 'nace_r1', 'indic_bt', 'indic', 'indic_n', 'indic_sb', 'indic_em', 'indic_de', 'indic_ppp', 'cpa2_1', 'bop_item', 'sector', 'siec', 'nrg_bal', 'rskpovth', 'plant_tec', 'ppp_cat18', 'ppp_cat', 'currency', 'quant_inc', 'lev_diff', 'agedef', 'c_birth', 'n_item', 'month', 'isced11', 'isced11f', 'wstatus', 'citizen', 'deg_urb', 'worktime', 'statinfo', 'stk_flow', 'sizeclas', 'coicop', 'coicop18', 'duration', 'partner', 'marsta', 'na_item' | [backend/app/data/eurostat_dim_labels_ru.py:1030](../backend/app/data/eurostat_dim_labels_ru.py#L1030) |
| app.data.eurostat_dim_labels_ru._GLOBAL_TOTALISH | Call | computed source expression | [backend/app/data/eurostat_dim_labels_ru.py:1077](../backend/app/data/eurostat_dim_labels_ru.py#L1077) |
| app.data.eurostat_dim_labels_ru._DIM_TOTALISH | Dict | 'sex', 'age', 'hhcomp', 'nace_r2', 'nace_r1', 'isced11', 'isced11f', 'wstatus', 'citizen', 'deg_urb', 'worktime', 'statinfo', 'stk_flow', 'sizeclas', 'coicop', 'coicop18', 'duration', 'partner', 'marsta', 'na_item', 'sector', 'indic', 'indic_de' | [backend/app/data/eurostat_dim_labels_ru.py:1087](../backend/app/data/eurostat_dim_labels_ru.py#L1087) |
| app.data.eurostat_dim_labels_ru._AGE_RANGE_RE | Call | computed source expression | [backend/app/data/eurostat_dim_labels_ru.py:1113](../backend/app/data/eurostat_dim_labels_ru.py#L1113) |
| app.data.eurostat_dim_labels_ru._AGE_LT_RE | Call | computed source expression | [backend/app/data/eurostat_dim_labels_ru.py:1114](../backend/app/data/eurostat_dim_labels_ru.py#L1114) |
| app.data.eurostat_dim_labels_ru._AGE_GE_RE | Call | computed source expression | [backend/app/data/eurostat_dim_labels_ru.py:1115](../backend/app/data/eurostat_dim_labels_ru.py#L1115) |
| app.data.eurostat_dim_labels_ru._AGE_SINGLE_RE | Call | computed source expression | [backend/app/data/eurostat_dim_labels_ru.py:1116](../backend/app/data/eurostat_dim_labels_ru.py#L1116) |
| app.data.eurostat_dim_labels_ru._DAY_RANGE_RE | Call | computed source expression | [backend/app/data/eurostat_dim_labels_ru.py:1117](../backend/app/data/eurostat_dim_labels_ru.py#L1117) |
| app.data.eurostat_dim_labels_ru._DAY_SINGLE_RE | Call | computed source expression | [backend/app/data/eurostat_dim_labels_ru.py:1118](../backend/app/data/eurostat_dim_labels_ru.py#L1118) |
| app.data.eurostat_headline.HEADLINE_MEMBER_OVERRIDES | Dict | 'gov_10dd_edpt1', 'gov_10a_main', 'gov_10dd_slgd', 'nama_10_gdp', 'namq_10_gdp', 'nrg_cb_sffm', 'nrg_cb_sff', 'nrg_cb_em', 'nrg_cb_h', 'nrg_cb_oil', 'nrg_cb_gas', 'nrg_te_bio', 'nrg_te_gas', 'nrg_te_gasm', 'nrg_te_sff', 'nrg_ti_bio', 'nrg_ti_gas', 'nrg_inf_lbpc' | [backend/app/data/eurostat_headline.py:16](../backend/app/data/eurostat_headline.py#L16) |
| app.data.eurostat_listing.LISTING_MIN_POINTS_BY_FREQUENCY | Dict | 'monthly', 'quarterly', 'annual', 'yearly', 'weekly', 'daily' | [backend/app/data/eurostat_listing.py:24](../backend/app/data/eurostat_listing.py#L24) |
| app.data.eurostat_listing.LISTING_MIN_HISTORY_END | Call | computed source expression | [backend/app/data/eurostat_listing.py:37](../backend/app/data/eurostat_listing.py#L37) |
| app.data.eurostat_listing._CORE_SLICE_KEYS | Call | computed source expression | [backend/app/data/eurostat_listing.py:42](../backend/app/data/eurostat_listing.py#L42) |
| app.data.eurostat_listing._RELEASE_SLICE_KEYS | Call | computed source expression | [backend/app/data/eurostat_listing.py:48](../backend/app/data/eurostat_listing.py#L48) |
| app.data.eurostat_listing._DATASET_FREQ_SUFFIX | Call | computed source expression | [backend/app/data/eurostat_listing.py:51](../backend/app/data/eurostat_listing.py#L51) |
| app.data.eurostat_listing.VARIANT_WHITELIST_STEMS | Call | computed source expression | [backend/app/data/eurostat_listing.py:54](../backend/app/data/eurostat_listing.py#L54) |
| app.data.eurostat_listing.VARIANT_STEM_ALIASES | Tuple | sequence/source expression | [backend/app/data/eurostat_listing.py:63](../backend/app/data/eurostat_listing.py#L63) |
| app.data.eurostat_listing.CATALOG_STEM_ALIASES | Tuple | sequence/source expression | [backend/app/data/eurostat_listing.py:76](../backend/app/data/eurostat_listing.py#L76) |
| app.data.eurostat_listing._GLUED_FREQ_LAST_TOKEN | Call | computed source expression | [backend/app/data/eurostat_listing.py:100](../backend/app/data/eurostat_listing.py#L100) |
| app.data.eurostat_listing.FREQ_ORDER | Tuple | sequence/source expression | [backend/app/data/eurostat_listing.py:103](../backend/app/data/eurostat_listing.py#L103) |
| app.data.eurostat_listing._ALL_ITEMS_COICOP | Call | computed source expression | [backend/app/data/eurostat_listing.py:255](../backend/app/data/eurostat_listing.py#L255) |
| app.data.eurostat_listing._INDEX_UNITS | Call | computed source expression | [backend/app/data/eurostat_listing.py:260](../backend/app/data/eurostat_listing.py#L260) |
| app.data.eurostat_listing._CHANGE_UNITS | Call | computed source expression | [backend/app/data/eurostat_listing.py:269](../backend/app/data/eurostat_listing.py#L269) |
| app.data.eurostat_listing._UNEMP_DS | Call | computed source expression | [backend/app/data/eurostat_listing.py:457](../backend/app/data/eurostat_listing.py#L457) |
| app.data.eurostat_listing._EMP_DS | Call | computed source expression | [backend/app/data/eurostat_listing.py:461](../backend/app/data/eurostat_listing.py#L461) |
| app.data.eurostat_listing._LISTING_DECISIONS_PATH | Call | computed source expression | [backend/app/data/eurostat_listing.py:537](../backend/app/data/eurostat_listing.py#L537) |
| app.data.eurostat_listing._HEADLINE_IDENTITY_DIMS | Call | computed source expression | [backend/app/data/eurostat_listing.py:540](../backend/app/data/eurostat_listing.py#L540) |
| app.data.eurostat_listing.DEEP_DATASET_SLICES | Dict | 'une_rt_m', 'une_rt_q', 'une_rt_a', 'ilc_di04', 'prc_hicp_minr', 'prc_hicp_ainr' | [backend/app/data/eurostat_listing.py:644](../backend/app/data/eurostat_listing.py#L644) |
| app.data.eurostat_substance.SUBSTANCE_DIMS | Tuple | sequence/source expression | [backend/app/data/eurostat_substance.py:16](../backend/app/data/eurostat_substance.py#L16) |
| app.data.eurostat_substance.NA_ITEM_SUBJECT_RU | Dict | 'B1GQ', 'B1G', 'B9', 'B9_T3', 'B9F', 'NLG_B9', 'NET_LEND', 'P3', 'P31_S13', 'P51G', 'P52_P53', 'B11', 'D41', 'D41PAY', 'TE', 'TR', 'GD' | [backend/app/data/eurostat_substance.py:27](../backend/app/data/eurostat_substance.py#L27) |
| app.data.eurostat_substance.INDIC_SUBJECT_RU | Dict | 'MF-DDI-RT', 'MF-LTGBY-RT', 'MF-NBRATE-RT', 'EXP_PPS_EU27_2020_HAB', 'EXP_PPS_HAB' | [backend/app/data/eurostat_substance.py:48](../backend/app/data/eurostat_substance.py#L48) |
| app.data.eurostat_substance._NAME_CONCEPT_RULES | List | sequence/source expression | [backend/app/data/eurostat_substance.py:58](../backend/app/data/eurostat_substance.py#L58) |
| app.data.eurostat_substance._SLICE_CONCEPT_FORBIDDEN_NAME | List | sequence/source expression | [backend/app/data/eurostat_substance.py:73](../backend/app/data/eurostat_substance.py#L73) |
| app.data.eurostat_titles_ru.CATEGORY_BY_PREFIX | List | sequence/source expression | [backend/app/data/eurostat_titles_ru.py:28](../backend/app/data/eurostat_titles_ru.py#L28) |
| app.data.eurostat_titles_ru.UNIT_RU | Dict | 'I15', 'I15_Q', 'I15_A_AVG', 'I10', 'I05', 'I96', 'I2015', 'I2021', 'I21', 'I21_SCA', 'I25', 'I25_NSA', 'INX', 'INX_A_AVG', 'INDEX', 'RCH_A', 'RCH_M', 'RCH_MV12MAVR', 'RT1', 'RT1-SCA', 'RT_M_DIF', 'PCH_SM', 'PCH_PRE', 'PCH_SAME', 'PC', 'PC_ACT', 'PC_POP', 'PC_GDP', 'PC_EU27_2020_HAB_MEUR_CP', 'PM', 'BAL', 'RT', 'YR', 'PER_KM2', 'MIO_EUR', 'MIO_EUR_SCA', 'MIO-EUR-SA', 'MIO_NAC', 'CLV15_MEUR', 'CLV10_MEUR', 'CP_MEUR', 'CP_EUR_HAB', 'THS_PER', 'THS', 'THS_EUR', 'NR', 'EUR' | [backend/app/data/eurostat_titles_ru.py:68](../backend/app/data/eurostat_titles_ru.py#L68) |
| app.data.eurostat_titles_ru._LEVEL_UNITS | Call | computed source expression | [backend/app/data/eurostat_titles_ru.py:124](../backend/app/data/eurostat_titles_ru.py#L124) |
| app.data.eurostat_titles_ru._DERIVED_UNITS | Call | computed source expression | [backend/app/data/eurostat_titles_ru.py:131](../backend/app/data/eurostat_titles_ru.py#L131) |
| app.data.eurostat_titles_ru._FREQ_TAIL_RE | Call | computed source expression | [backend/app/data/eurostat_titles_ru.py:136](../backend/app/data/eurostat_titles_ru.py#L136) |
| app.data.eurostat_titles_ru._AGE_RU | Dict | 'Y15-24', 'Y_LT25', 'Y25-74', 'Y15-64', 'Y20-64', 'Y18-64', 'Y18-24', 'Y16-19', 'Y0-29', 'Y18', 'Y_LT6', 'Y_GE15', 'Y_GE25', 'Y_LT1', 'Y_LT5', 'D0', 'D1', 'D1-6', 'D7-27', 'D28-364', 'Y1', 'Y_LT15', 'Y15-74' | [backend/app/data/eurostat_titles_ru.py:140](../backend/app/data/eurostat_titles_ru.py#L140) |
| app.data.eurostat_titles_ru._SEX_RU | Dict | 'M', 'F' | [backend/app/data/eurostat_titles_ru.py:166](../backend/app/data/eurostat_titles_ru.py#L166) |
| app.data.eurostat_titles_ru._NARROWING_NAME_DIMS | Call | computed source expression | [backend/app/data/eurostat_titles_ru.py:174](../backend/app/data/eurostat_titles_ru.py#L174) |
| app.data.eurostat_titles_ru._NARROWING_DIM_TOTALS | Dict | 'age', 'sex', 'hhcomp', 'coicop', 'coicop18' | [backend/app/data/eurostat_titles_ru.py:180](../backend/app/data/eurostat_titles_ru.py#L180) |
| app.data.eurostat_titles_ru.SUBJECT_TERMS | List | sequence/source expression | [backend/app/data/eurostat_titles_ru.py:203](../backend/app/data/eurostat_titles_ru.py#L203) |
| app.data.eurostat_titles_ru.DIM_TERMS | List | sequence/source expression | [backend/app/data/eurostat_titles_ru.py:338](../backend/app/data/eurostat_titles_ru.py#L338) |
| app.data.eurostat_titles_ru.WORD_TERMS | Dict | 'and', 'of', 'in', 'by', 'for', 'the', 'a', 'an', 'to', 'from', 'with', 'without', 'on', 'at', 'or', 'vs', 'new', 'total', 'domestic', 'market', 'monthly', 'quarterly', 'annual', 'yearly', 'weekly', 'daily', 'data', 'index', 'rate', 'rates', 'change', 'average', 'main', 'components', 'other', 'all', 'items', 'area', 'euro', 'european', 'union', 'member', 'states', 'state', 'national', 'international', 'external', 'internal', 'real', 'nominal', 'seasonally', 'adjusted', 'unadjusted', 'constant', 'current', 'prices', 'price', 'consumer', 'producer', 'industrial', 'business', 'confidence', 'sentiment', 'survey', 'results', 'indicator', 'indicators', 'growth', 'volume', 'value', 'turnover', 'sales', 'production', 'industry', 'construction', 'services', 'service', 'trade', 'retail', 'wholesale', 'unemployment', 'employment', 'labour', 'labor', 'input', 'cost', 'costs', 'wage', 'wages', 'population', 'demography', 'birth', 'death', 'migration', 'energy', 'electricity', 'gas', 'fuel', 'food', 'housing', 'house', 'building', 'buildings', 'permits', 'bankruptcy', 'registration', 'export', 'exports', 'import', 'imports', 'balance', 'payments', 'payment', 'investment', 'investments', 'position', 'positions', 'flow', 'flows', 'income', 'debt', 'deficit', 'surplus', 'revenue', 'expenditure', 'government', 'general', 'bond', 'bonds', 'yield', 'yields', 'maturity', 'interest', 'money', 'market', 'exchange', 'effective', 'conversion', 'factors', 'factor', 'currency', 'currencies', 'countries', 'country', 'partner', 'partners', 'product', 'products', 'group', 'groups', 'sector', 'sectors', 'activity', 'activities', 'type', 'types', 'sex', 'age', 'size', 'class', 'share', 'shares', 'percent', 'percentage', 'points', 'point', 'contribution', 'contributions', 'first', 'published', 'released', 'tax', 'taxes', 'harmonised', 'detailed', 'geographical', 'breakdown', 'outside', 'extra', 'intra', 'world', 'global', 'unit', 'labour', 'hoarding', 'expectations', 'climate', 'consumers', 'consumer', 'vacancy', 'job', 'persons', 'person', 'thousand', 'number', 'level', 'levels', 'comparative', 'purchasing', 'power', 'parities', 'parity', 'correction', 'coefficients', 'monitoring', 'tool', 'years', 'year', 'month', 'months', 'quarter', 'day', 'days', 'education', 'educational', 'aged', 'social', 'status', 'region', 'regions', 'regional', 'household', 'households', 'poverty', 'pupils', 'students', 'enrolled', 'attainment', 'intensity', 'living', 'degree', 'consumption', 'transport', 'risk', 'accommodation', 'goods', 'births', 'deaths', 'mortality', 'fertility', 'expectancy', 'median', 'crude', 'density', 'renewable', 'fossil', 'oil', 'petroleum', 'natural', 'solid', 'heat', 'capacity', 'capacities', 'motorways', 'roads', 'cars', 'vehicles', 'physicians', 'hospital', 'beds', 'medical', 'examination', 'corruption', 'research', 'development', 'capita', 'relative', 'gap', 'transfers', 'monetary', 'elderly', 'older', 'gender', 'exclusion', 'deprivation', 'material', 'january', 'structure', 'broad', 'mother', 'infant', 'marriage', 'marriages', 'divorce', 'divorces', 'duration', 'previous', 'citizenship', 'weight', 'abortion', 'abortions', 'excess', 'table', 'life', 'dependency', 'proportion', 'mean', 'women', 'childbirth', 'child', 'participation', 'institution', 'programme', 'tertiary', 'primary', 'secondary', 'compulsory', 'early', 'childhood', 'school', 'work', 'distribution', 'internet', 'road', 'afford', 'disability', 'children', 'freight', 'nuts', 'quintile', 'nace', 'health', 'care', 'who', 'urbanisation', 'limitation', 'cannot', 'added', 'hicp', 'people', 'very', 'their', 'low', 'personal', 'ict', 'volumes', 'transitions', 'individuals', 'tkm', 'tenure', 'experimental', 'statistics', 'pensions', 'capital', 'vehicle', 'orientation', 'graduates', 'tourist', 'establishments', 'eu', 'spent', 'mobile', 'least', 'home', 'parents', 'excluding', 'nights', 'corresponding', 'selected', 'abroad', 'self-reported', 'unmet', 'severe', 'before', 'buses', 'formal', 'than', 'needs', 'disposable', 'reason', 'onwards', 'declared', 'situation', 'strategy', 'technology', 'information', 'traffic', 'teachers', 'overcrowding', 'in-work', 'surveys', 'benefits', 'specialists', 'communications', 'bed-places', 'transition', 'self-perceived', 'inability', 'most', 'fixed', 'supplementary', 'derived', 'combustible', 'non-combustible', 'fuels', 'operator', 'motorcycles', 'engine', 'coaches', 'trolley', 'trams', 'inhabitants', 'inhabitant', 'consultation', 'dentist', 'bedrooms', 'net', 'greenhouse', 'emissions', 'land', 'forestry', 'self-reliance', 'diversity', 'supply', 'available', 'hospitals', 'seats', 'berths', 'durability', 'nursing', 'residential', 'long-term', 'facilities', 'remaining', 'working', 'issue', 'accounts', 'aggregates', 'arrivals', 'stocks', 'stock', 'asset', 'based', 'purpose', 'threshold', 'excluded', 'ability', 'make', 'ends', 'meet', 'composition', 'distance', 'field', 'over', 'per', 'as', 'starting', 'old', 'under', 'lower', 'upper', 'adult', 'vocational', 'programmes', 'completion', 'trains', 'inland', 'passenger', 'leavers', 'training', 'learning', 'ratio', 'non-financial', 'productivity', 'discharges', 'inpatient', 'curative', 'ownership', 'mopeds', 'pumps', 'ambient', 'heat', 'rev' | [backend/app/data/eurostat_titles_ru.py:406](../backend/app/data/eurostat_titles_ru.py#L406) |
| app.data.eurostat_titles_ru.FREQ_SUFFIX | Dict | 'monthly', 'quarterly', 'annual', 'yearly', 'weekly', 'daily' | [backend/app/data/eurostat_titles_ru.py:884](../backend/app/data/eurostat_titles_ru.py#L884) |
| app.data.eurostat_titles_ru.PAREN_RULES | List | sequence/source expression | [backend/app/data/eurostat_titles_ru.py:894](../backend/app/data/eurostat_titles_ru.py#L894) |
| app.data.eurostat_titles_ru._NRG_BAL_RU | Dict | 'GID_OBS', 'GID_CAL', 'AIM', 'ID', 'IPRD', 'IMP', 'EXP', 'FC_E', 'GIC', 'DL', 'TI_EHG_MAP' | [backend/app/data/eurostat_titles_ru.py:984](../backend/app/data/eurostat_titles_ru.py#L984) |
| app.data.eurostat_titles_ru._SIEC_RU | Dict | 'C0100', 'C0200', 'C0311', 'E7000', 'H8000', 'G3000', 'P1100', 'S2000' | [backend/app/data/eurostat_titles_ru.py:998](../backend/app/data/eurostat_titles_ru.py#L998) |
| app.data.eurostat_titles_ru.DATASET_TITLES_EN | Dict | 'prc_hicp_minr', 'prc_hicp_ainr', 'prc_hicp_midx', 'prc_hicp_aind' | [backend/app/data/eurostat_titles_ru.py:1382](../backend/app/data/eurostat_titles_ru.py#L1382) |
| app.data.eurostat_titles_ru.COUNTRY_PREPOSITIONAL | Dict | 'austria', 'belgium', 'bulgaria', 'croatia', 'cyprus', 'czechia', 'denmark', 'estonia', 'finland', 'france', 'germany', 'greece', 'hungary', 'ireland', 'italy', 'latvia', 'lithuania', 'luxembourg', 'malta', 'netherlands', 'poland', 'portugal', 'romania', 'slovakia', 'slovenia', 'spain', 'sweden', 'iceland', 'norway', 'switzerland', 'united-kingdom', 'turkey', 'serbia', 'montenegro', 'north-macedonia', 'albania', 'bosnia', 'kosovo', 'ukraine', 'moldova', 'georgia', 'armenia', 'azerbaijan', 'united-states', 'canada', 'japan', 'south-korea', 'china', 'india', 'brazil', 'mexico', 'australia', 'new-zealand', 'south-africa', 'israel' | [backend/app/data/eurostat_titles_ru.py:1405](../backend/app/data/eurostat_titles_ru.py#L1405) |
| app.data.eurostat_titles_ru._MONTH_GENITIVE | Tuple | sequence/source expression | [backend/app/data/eurostat_titles_ru.py:1463](../backend/app/data/eurostat_titles_ru.py#L1463) |
| app.data.eurostat_titles_ru._MONTH_NOMINATIVE | Tuple | sequence/source expression | [backend/app/data/eurostat_titles_ru.py:1469](../backend/app/data/eurostat_titles_ru.py#L1469) |
| app.data.eurostat_titles_ru._FREQ_TAIL_MARKERS | Tuple | sequence/source expression | [backend/app/data/eurostat_titles_ru.py:1474](../backend/app/data/eurostat_titles_ru.py#L1474) |
| app.data.eurostat_titles_ru.TEMPLATE_STUB_RE | Call | computed source expression | [backend/app/data/eurostat_titles_ru.py:1483](../backend/app/data/eurostat_titles_ru.py#L1483) |
| app.data.eurostat_titles_ru.DATASET_EXPLAINERS_RU | Dict | 'prc_hpi_cow', 'prc_hpi_oocow', 'prc_hpi_inw', 'prc_hpi_ooinw', 'prc_hpi_q', 'prc_hpi_a', 'prc_hpi_ooq', 'lfsq_sup_age', 'nrg_ind_ep', 'nrg_ind_esr', 'road_eqs_carhab', 'ilc_li10', 'ilc_pnp2', 'nama_10_fcs', 'sdg_13_10', 'lfsi_dwl_a', 'prc_hicp_minr', 'prc_hicp_ainr' | [backend/app/data/eurostat_titles_ru.py:1551](../backend/app/data/eurostat_titles_ru.py#L1551) |
| app.data.eurostat_units_ru.SENSITIVE_TOPIC_DATASET_IDS | Call | computed source expression | [backend/app/data/eurostat_units_ru.py:32](../backend/app/data/eurostat_units_ru.py#L32) |
| app.data.eurostat_units_ru._VAGUE_EN_LABELS | Call | computed source expression | [backend/app/data/eurostat_units_ru.py:40](../backend/app/data/eurostat_units_ru.py#L40) |
| app.data.eurostat_units_ru.DATASET_UNIT_RU | Dict | 'demo_minfind', 'demo_r_minfind', 'tps00027', 'demo_frate', 'demo_r_frate2', 'tps00199', 'tps00206', 'tps00019', 'tps00204', 'tps00029', 'demo_pjan', 'demo_pjanbroad', 'demo_pjangroup', 'demo_pjanedu', 'demo_pjanmarsta', 'demo_urespop', 'demo_fmonth', 'demo_mmonth', 'demo_fagec', 'demo_fager', 'demo_fasec', 'demo_fordagec', 'demo_facbc', 'demo_faczc', 'demo_faeduc', 'demo_magec', 'demo_mager', 'demo_macbc', 'demo_maczc', 'demo_maeduc', 'demo_marstac', 'demo_minf', 'demo_minfs', 'demo_r_minf', 'demo_r_births', 'demo_r_deaths', 'demo_nmsta', 'demo_nmsta2', 'demo_ndivdur', 'demo_nsinagec', 'demo_marcb', 'demo_marcz', 'demo_divcb', 'demo_divcz', 'demo_fweight', 'demo_pjanind', 'demo_r_pjanind2', 'demo_r_pjanind3', 'tps00198', 'tps00028', 'demo_ndivind', 'demo_nind', 'demo_nsinrt', 'demo_mlifetable', 'demo_r_mlife', 'demo_gind', 'demo_mexrt', 'demo_r_d3dens', 'sdg_16_50', 'educ_uoe_enra01', 'educ_uoe_enra02', 'educ_uoe_enrp01', 'educ_uoe_enrp02', 'educ_uoe_enrp04', 'educ_uoe_enrp05', 'educ_uoe_enrs01', 'educ_uoe_enrs04', 'educ_uoe_enrt01', 'educ_uoe_enrt02', 'educ_uoe_ent01', 'hlth_rs_phys', 'hlth_rs_bds1', 'sdg_10_10', 'ei_mfir_m', 'irt_st_m', 'irt_lt_mcby_m', 'irt_lt_mcby_q', 'irt_lt_mcby_a', 'nama_10_pc', 'ei_lmjv_q_r2', 'ei_lmjv_m_r2', 'ilc_di11', 'ilc_di12', 'ei_bsee_m_r2', 'ei_bslh_m_r2', 'ei_bsin_q_r2', 'ei_bsbu_m_r2', 'ei_bssi_m_r2', 'teibs030', 'educ_uoe_enra07', 'demo_fordager', 'hlth_rs_grd2', 'hlth_rs_prs2', 'prc_hpi_hsnq', 'prc_hpi_cow', 'prc_hpi_inw', 'prc_hpi_oocow', 'prc_hpi_ooinw', 'nrg_chdd_m', 'nrg_chdd_a', 'nrg_chddr2_m', 'nrg_chddr2_a', 'nrg_stk_oem', 'road_eqs_busage', 'road_eqs_busveh', 'road_eqs_carage', 'road_eqs_carmot', 'road_eqs_carpda', 'road_eqs_unlweig', 'road_eqr_carmot', 'road_eqr_unlweig', 'lfsi_abt_q', 'lfsi_lea_q', 'lfsi_sta_q', 'lfsi_long_q', 'lfsq_ewhais', 'lfsq_ewhan2', 'lfsq_ewhuis', 'lfsq_ewhun2', 'lfsq_ewh2n2', 'nrg_cb_cosm', 'teibp010', 'teibp040', 'teibp041', 'teibp050', 'teibp110' | [backend/app/data/eurostat_units_ru.py:56](../backend/app/data/eurostat_units_ru.py#L56) |
| app.data.eurostat_units_ru.INDIC_UNIT_RU | Dict | 'INFMORRT', 'NEOMORRT', 'ENEOMORRT', 'PERIMORRT', 'LFOEMORRT', 'TOTFERRT', 'GNUPRT', 'GBIRTHRT', 'GDEATHRT', 'GROWRT', 'NATGROWRT', 'CNMIGRATRT', 'AGEMOTH', 'AGEMOTH1', 'AGEMOTH2', 'AGEMOTH3', 'AGEMOTH4_MAX', 'MEDAGEMOTH', 'FAGEMAR1', 'MAGEMAR1', 'LBIRTHR1PC', 'LBIRTHR2PC', 'LBIRTHR3PC', 'LBIRTHR4_MAXPC', 'NMARPCT', 'FMAR1PC', 'MMAR1PC', 'FMAR1CUM', 'MMAR1CUM', 'POPSHARE', 'POPSHARE_EU27_2020', 'JAN', 'FJAN', 'MJAN', 'AVG', 'FAVG', 'MAVG', 'LBIRTH', 'FLBIRTH', 'MLBIRTH', 'DEATH', 'FDEATH', 'MDEATH', 'GROW', 'NATGROW', 'CNMIGRAT', 'MARRIAGE', 'DEPRATIO1', 'DEPRATIO2', 'DEPRATIO3', 'DEPRATIO4', 'OLDDEP1', 'OLDDEP2', 'OLDDEP3', 'OLDDEP4', 'YOUNGDEP1', 'YOUNGDEP2', 'YOUNGDEP3', 'YOUNGDEP4', 'MEDAGEPOP', 'FMEDAGEPOP', 'MMEDAGEPOP', 'PC_Y65_MAX', 'PC_FM', 'MF-DDI-RT', 'MF-LTGBY-RT', 'MF-NBRATE-RT', 'JVR', 'BS-EEI-I', 'BS-ESI-I', 'BS-ICI-I', 'BS-CCI-I', 'BS-RCI-I', 'BS-CSMCI-I', 'GINI_HND', 'MF-LON-RT', 'EXP_PPS_EU27_2020_HAB', 'EXP_PPS_HAB', 'PPS_EU27_2020_HAB', 'PPS_HAB' | [backend/app/data/eurostat_units_ru.py:208](../backend/app/data/eurostat_units_ru.py#L208) |
| app.data.eurostat_units_ru._NON_APPENDABLE_PREFIXES | Tuple | sequence/source expression | [backend/app/data/eurostat_units_ru.py:528](../backend/app/data/eurostat_units_ru.py#L528) |
| app.data.global_market_indicators.GLOBAL_MARKET_INDICATOR_BASES | Call | computed source expression | [backend/app/data/global_market_indicators.py:11](../backend/app/data/global_market_indicators.py#L11) |
| app.data.global_market_indicators.COUNTRY_MARKET_INDICATOR_CODES | Dict | 'united-states' | [backend/app/data/global_market_indicators.py:43](../backend/app/data/global_market_indicators.py#L43) |
| app.data.housing_historical.PRIMARY_YOY_PCT | Dict | 1998, 1999, 2000, 2001, 2002, 2003, 2004, 2005, 2006, 2007, 2008, 2009, 2010, 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019 | [backend/app/data/housing_historical.py:27](../backend/app/data/housing_historical.py#L27) |
| app.data.housing_historical.SECONDARY_YOY_PCT | Dict | 1998, 1999, 2000, 2001, 2002, 2003, 2004, 2005, 2006, 2007, 2008, 2009, 2010, 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019 | [backend/app/data/housing_historical.py:35](../backend/app/data/housing_historical.py#L35) |
| app.data.housing_historical.SPECS | Tuple | sequence/source expression | [backend/app/data/housing_historical.py:58](../backend/app/data/housing_historical.py#L58) |
| app.data.i18n.en_catalog.EN_EXACT_PATHS | Call | computed source expression | [backend/app/data/i18n/en_catalog.py:23](../backend/app/data/i18n/en_catalog.py#L23) |
| app.data.i18n.en_catalog.EN_PATH_PREFIXES | Tuple | sequence/source expression | [backend/app/data/i18n/en_catalog.py:44](../backend/app/data/i18n/en_catalog.py#L44) |
| app.data.i18n.glossary_en.GLOSSARY_EN | Dict | 'Инфляция', 'ИПЦ', 'Индекс потребительских цен', 'Ключевая ставка', 'Безработица', 'Уровень безработицы', 'ВВП', 'Номинальный ВВП', 'Реальный ВВП', 'Заработная плата', 'г/г', 'м/м', 'кв/кв', 'Росстат', 'Банк России', 'Минфин', 'Минфин России', 'Московская биржа', 'Евростат', 'Международный валютный фонд', 'Всемирный банк', 'Рыночные котировки', 'Статистическое управление Канады', 'Банк Канады', 'Австралийское бюро статистики', 'Резервный банк Австралии', 'Управление национальной статистики Великобритании', 'Банк Англии', 'Федеральный резервный банк Сент-Луиса', 'Бюро трудовой статистики США', 'Бюро экономического анализа США', 'Банк Японии', 'Статистическое бюро Японии', 'Банк Кореи', 'Банк Бразилии', 'Банк Мексики', 'Национальное статистическое бюро Китая', 'Китайская система валютных торгов', 'Министерство статистики и программной реализации Индии', 'Резервный банк Индии', 'Бюро переписи населения США', 'Бразильский институт географии и статистики (IBGE)', 'Россия', 'Регионы', 'Регионы России', 'Сравнение', 'Прогноз', 'Методология', 'Источник' | [backend/app/data/i18n/glossary_en.py:10](../backend/app/data/i18n/glossary_en.py#L10) |
| app.data.i18n.indicator_copy_en.INDICATOR_COPY_EN | Dict | 'cpi', 'cpi-food', 'cpi-nonfood', 'cpi-services', 'key-rate', 'usd-rub', 'eur-rub', 'cny-rub', 'ruonia', 'm0', 'm2', 'mortgage-rate', 'deposit-rate', 'auto-loan-rate', 'credit-rate-corp-short', 'credit-rate-ind-short', 'unemployment', 'wages-nominal', 'gdp-nominal', 'gdp-real', 'wages-real', 'housing-affordability', 'm1', 'consumer-credit', 'business-credit', 'deposits-individual', 'deposits-business', 'budget-deficit', 'housing-price-primary', 'housing-price-secondary', 'ipi', 'ipi-mining', 'ipi-manufacturing', 'ipi-energy', 'ipi-water', 'population', 'population-natural-growth', 'population-total-growth', 'population-migration', 'current-account', 'ppi', 'exports', 'imports', 'trade-balance', 'international-reserves', 'external-debt', 'gdp-consumption', 'gdp-government', 'gdp-investment', 'labor-force', 'employment', 'budget-revenue', 'budget-expenditure', 'services-exports', 'services-imports', 'fdi-net', 'births', 'deaths', 'birth-rate', 'death-rate', 'working-age-population', 'pop-under-working-age', 'pop-over-working-age', 'pensioners', 'retail-trade', 'construction-work', 'capital-investment', 'housing-commissioned', 'depreciation-rate', 'grad-students', 'doctoral-students', 'rd-organizations', 'rd-personnel', 'innovation-activity', 'tech-innovation-share', 'small-business-innovation', 'gold-price', 'btc-usd', 'eth-usd', 'sol-usd', 'imoex', 'mcftr', 'rtsi', 'rgbi', 'corp-bond-index', 'usd-index', 'eur-usd', 'gbp-eur', 'cny-eur', 'gbp-usd', 'usd-cny', 'ust-10y', 'brent', 'copper', 'silver', 'natural-gas', 'wheat', 'soybean', 'coal', 'fuel-ai92', 'deposit-rate-medium', 'deposit-rate-long', 'credit-rate-corp-1to3y', 'credit-rate-corp-over3y', 'credit-rate-ind-1to3y', 'credit-rate-ind-over3y', 'wages-nominal-annual', 'wages-nominal-annual-yoy', 'wages-index', 'housing-affordability-primary', 'gdp-yoy', 'gdp-qoq', 'gdp-real-yoy', 'gdp-real-qoq', 'gdp-nominal-annual', 'gdp-real-annual', 'inflation-quarterly', 'inflation-annual', 'cpi-food-quarterly', 'cpi-food-annual', 'cpi-food-yoy', 'cpi-food-qoq', 'cpi-food-period-weekly', 'cpi-food-period-monthly', 'cpi-nonfood-quarterly', 'cpi-nonfood-annual', 'cpi-nonfood-yoy', 'cpi-nonfood-qoq', 'cpi-nonfood-period-weekly', 'cpi-nonfood-period-monthly', 'cpi-services-quarterly', 'cpi-services-annual', 'cpi-services-yoy', 'cpi-services-qoq', 'cpi-services-period-weekly', 'cpi-services-period-monthly', 'cpi-yoy', 'cpi-qoq', 'cpi-period-weekly', 'cpi-period-monthly', 'inflation-weekly', 'inflation-weekly-food', 'inflation-weekly-nonfood', 'inflation-weekly-services', 'housing-qoq-secondary', 'housing-yoy-primary', 'housing-qoq-primary', 'housing-yoy-secondary', 'housing-annual-primary', 'housing-annual-secondary', 'unemployment-quarterly', 'unemployment-annual', 'current-account-yoy-abs', 'trade-balance-yoy-abs', 'current-account-yoy', 'ipi-yoy', 'exports-monthly', 'imports-monthly', 'trade-balance-monthly', 'exports-yoy', 'imports-yoy', 'exports-qoq', 'imports-qoq', 'services-exports-monthly', 'services-imports-monthly', 'ppi-yoy', 'ppi-qoq', 'ppi-mom', 'ppi-annual', 'wages-yoy', 'steel', 'fuel-ai95', 'fuel-diesel', 'weo-gdp-usd', 'weo-gdp-per-capita-usd', 'weo-budget-balance-gdp', 'weo-government-debt-gdp' | [backend/app/data/i18n/indicator_copy_en.py:24](../backend/app/data/i18n/indicator_copy_en.py#L24) |
| app.data.i18n.region_indicators_en.REGION_INDICATORS_EN | Dict | 'ceni-dt', 'roznica-dt', 'opt-benzin', 'opt-dt', 'ceni-ai92', 'ceni-ai95', 'chislennost-naseleniya', 'srednegodovaya-chislennost-naseleniya', 'udelnyy-ves-gorodskogo-naseleniya-v-obschey-chislennosti', 'udelnyy-ves-selskogo-naseleniya-v-obschey-chislennosti', 'sootnoshenie-muzhchin-i-zhenschin', 'vozrastnoy-sostav-naseleniya-naselenie-molozhe-trudosposobnogo-vozrasta', 'vozrastnoy-sostav-naseleniya-naselenie-v-trudosposobnom-vozraste', 'vozrastnoy-sostav-naseleniya-naselenie-starshe-trudosposobnogo-vozrasta', 'koeffitsienty-demograficheskoy-nagruzki-vsego', 'koeffitsienty-demograficheskoy-nagruzki-molozhe-trudosposobnogo-vozrasta', 'koeffitsienty-demograficheskoy-nagruzki-starshe-trudosposobnogo-vozrasta', 'tempy-prirosta-chislennosti-naseleniya', 'obschie-koeffitsienty-rozhdaemosti', 'obschie-koeffitsienty-smertnosti', 'smertnost-naseleniya-v-trudosposobnom-vozraste', 'smertnost-naseleniya-bez-pokazatelya-smertnosti-ot-vneshnih', 'koeffitsienty-mladencheskoy-smertnosti', 'koeffitsienty-estestvennogo-prirosta-naseleniya-na-1000-chelovek', 'summarnyy-koeffitsient-rozhdaemosti', 'ozhidaemaya-prodolzhitelnost-zhizni-pri-rozhdenii-vse-naselenie', 'ozhidaemaya-prodolzhitelnost-zhizni-pri-rozhdenii-muzhchiny', 'ozhidaemaya-prodolzhitelnost-zhizni-pri-rozhdenii-zhenschiny', 'obschie-koeffitsienty-brachnosti-na-1000-chelovek-naseleniya', 'obschie-koeffitsienty-razvodimosti-na-1000-chelovek-naseleniya', 'sootnoshenie-brakov-i-razvodov', 'koeffitsienty-migratsionnogo-prirosta-na-10-000-chelovek', 'raspredelenie-chisla-pribyvshih-po-napravleniyam-peredvizheniya-v', 'raspredelenie-chisla-pribyvshih-po-napravleniyam-peredvizheniya-iz', 'raspredelenie-chisla-pribyvshih-po-napravleniyam-peredvizheniya-iz-1-21-3', 'raspredelenie-chisla-vybyvshih-po-napravleniyam-peredvizheniya-v', 'raspredelenie-chisla-vybyvshih-po-napravleniyam-peredvizheniya-v-1-22-2', 'raspredelenie-chisla-vybyvshih-po-napravleniyam-peredvizheniya-za', 'chislennost-vynuzhdennyh-pereselentsev', 'chislennost-bezhentsev', 'chislennost-lits-poluchivshih-vremennoe-ubezhische', 'chislennost-rabochey-sily', 'uroven-uchastiya-v-sostave-rabochey-sily', 'srednegodovaya-chislennost-zanyatyh', 'izmenenie-srednegodovoy-chislennosti-zanyatyh', 'uroven-zanyatosti-naseleniya', 'uroven-zanyatosti-naseleniya-v-trudosposobnom-vozraste', 'chislennost-bezrabotnyh', 'chislennost-zaregistrirovannyh-bezrabotnyh', 'chislennost-nezanyatyh-grazhdan-sostoyaschih-na-uchete-v', 'uroven-bezrabotitsy', 'uroven-bezrabotitsy-uroven-bezrabotitsy-v-trudosposobnom-vozraste', 'uroven-bezrabotitsy-uroven-zaregistrirovannoy-bezrabotitsy', 'potrebnost-v-rabotnikah-zayavlennaya-rabotodatelyami-v-organy', 'nagruzka-nezanyatogo-naseleniya-sostoyaschego-na-registratsionnom-uchete', 'chislennost-inostrannyh-grazhdan-imevshih-deystvuyuschee-razreshenie-na', 'chislennost-inostrannyh-grazhdan-imevshih-deystvuyuschiy-patent-na', 'realnye-denezhnye-dohody-realnye-dohody-naseleniya', 'realnye-denezhnye-dohody-realnaya-nachislennaya-zarabotnaya-plata', 'realnye-denezhnye-dohody-realnyy-razmer-naznachennyh-pensiy', 'srednedushevye-denezhnye-dohody-naseleniya', 'mediannyy-srednedushevoy-denezhnyy-dohod-naseleniya', 'srednemesyachnaya-nominalnaya-nachislennaya-zarabotnaya-plata-rabotnikov-organizatsiy', 'mediannaya-zarabotnaya-plata-rabotnikov-organizatsiy', 'sredniy-razmer-naznachennyh-pensiy', 'chislennost-pensionerov-vsego', 'chislennost-pensionerov-na-1000-chelovek-naseleniya', 'chislennost-zanyatyh-prihodyaschihsya-na-odnogo-pensionera', 'struktura-denezhnyh-dohodov-naseleniya', 'velichina-prozhitochnogo-minimuma-ustanovlennaya-v-tselom-po', 'velichina-prozhitochnogo-minimuma-ustanovlennaya-v-tselom-po-3-11', 'chislennost-naseleniya-s-denezhnymi-dohodami-nizhe-granitsy', 'granitsa-bednosti', 'potrebitelskie-rashody-v-srednem-na-dushu-naseleniya', 'struktura-ispolzovaniya-denezhnyh-dohodov-naseleniya', 'struktura-potrebitelskih-rashodov-domashnih-hozyaystv', 'chislo-sobstvennyh-legkovyh-avtomobiley-na-1000-chelovek', 'potreblenie-myasa-i-myasoproduktov-vklyuchaya-subprodukty-ii', 'potreblenie-moloka-i-molochnyh-produktov-na-dushu', 'potrebleniya-yaits-na-dushu-naseleniya', 'potrebleniya-sahara-na-dushu-naseleniya', 'potreblenie-rastitelnogo-masla-na-dushu-naseleniya', 'potreblenie-hlebnyh-produktov-na-dushu-naseleniya', 'zhilischnyy-fond-vsego', 'zhilischnyy-fond-gorodskoy-zhilischnyy-fond', 'zhilischnyy-fond-selskiy-zhilischnyy-fond', 'obschaya-ploschad-zhilyh-pomescheniy-prihodyaschayasya-v-srednem', 'predostavlenie-grazhdanam-zhilyh-pomescheniy-chislo-semey-sostoyavshih', 'predostavlenie-grazhdanam-zhilyh-pomescheniy-udelnyy-ves-semey', 'predostavlenie-grazhdanam-zhilyh-pomescheniy-chislo-semey-poluchivshih', 'predostavlenie-grazhdanam-zhilyh-pomescheniy-udelnyy-ves-semey-3-26-4', 'udelnyy-ves-rashodov-domashnih-hozyaystv-na-oplatu', 'udelnyy-ves-rashodov-domashnih-hozyaystv-na-oplatu-3-27-2', 'predostavlenie-grazhdanam-subsidiy-na-oplatu-zhilogo-pomescheniya', 'predostavlenie-grazhdanam-subsidiy-na-oplatu-zhilogo-pomescheniya-3-28-2', 'predostavlenie-grazhdanam-subsidiy-na-oplatu-zhilogo-pomescheniya-3-28-3', 'predostavlenie-grazhdanam-sotsialnoy-podderzhki-lgot-po-oplate', 'predostavlenie-grazhdanam-sotsialnoy-podderzhki-lgot-po-oplate-3-29-2', 'predostavlenie-grazhdanam-sotsialnoy-podderzhki-lgot-po-oplate-3-29-3', 'chislennost-vospitannikov-organizatsiy-osuschestvlyayuschih-obrazovatelnuyu-deyatelnost-po', 'valovoy-koeffitsient-ohvata-doshkolnym-obrazovaniem', 'obespechennost-detey-doshkolnogo-vozrasta-mestami-v-organizatsiyah', 'chislennost-uchiteley-organizatsiy-osuschestvlyayuschih-obrazovatelnuyu-deyatelnost-po', 'chislennost-obuchayuschihsya-organizatsiy-osuschestvlyayuschih-obrazovatelnuyu-deyatelnost-po', 'udelnyy-ves-obuchayuschihsya-vo-vtoruyu-i-tretyu', 'vypusk-obuchayuschihsya-organizatsiyami-osuschestvlyayuschih-obrazovatelnuyu-deyatelnost-po', 'vypusk-obuchayuschihsya-organizatsiyami-osuschestvlyayuschih-obrazovatelnuyu-deyatelnost-po-4-7-2', 'prepodavateli-i-mastera-proizvodstvennogo-obucheniya-realizuyuschie-programmy', 'prepodavateli-i-mastera-proizvodstvennogo-obucheniya-realizuyuschie-programmy-4-8-2', 'prepodavateli-i-mastera-proizvodstvennogo-obucheniya-realizuyuschie-programmy-4-9-1', 'prepodavateli-i-mastera-proizvodstvennogo-obucheniya-realizuyuschie-programmy-4-9-2', 'chislennost-studentov-obuchayuschihsya-po-programmam-podgotovki-kvalifitsirovannyh', 'priem-na-obuchenie-po-programmam-podgotovki-kvalifitsirovannyh', 'vypusk-kvalifitsirovannyh-rabochih-i-sluzhaschih', 'chislennost-studentov-obuchayuschihsya-po-programmam-podgotovki-spetsialistov', 'chislennost-studentov-gosudarstvennyh-i-munitsipalnyh-professionalnyh-obrazovatelnyh', 'priem-na-obuchenie-po-programmam-podgotovki-spetsialistov', 'vypusk-spetsialistov-srednego-zvena', 'chislennost-professorsko-prepodavatelskogo-personala-osuschestvlyayuschego-obrazovatelnuyu-deyatelnost', 'chislennost-studentov-obuchayuschihsya-po-programmam-bakalavriata-spetsialiteta', 'chislennost-studentov-obuchayuschihsya-po-programmam-bakalavriata-spetsialiteta-4-19', 'priem-na-obuchenie-po-programmam-bakalavriata-spetsialiteta', 'vypusk-bakalavrov-spetsialistov-magistrov', 'chislennost-aspirantov', 'chislennost-ordinatorov-i-assistentov-stazherov-chislennost-ordinatorov', 'chislennost-ordinatorov-i-assistentov-stazherov-chislennost-assistentov', 'chislennost-doktorantov', 'chislo-bolnichnyh-koek-vsego', 'chislo-bolnichnyh-koek-na-10000-chelovek-naseleniya', 'chislennost-naseleniya-na-odnu-bolnichnuyu-koyku', 'moschnost-ambulatorno-poliklinicheskih-organizatsiy-vsego', 'moschnost-ambulatorno-poliklinicheskih-organizatsiy-na-10000-chelovek', 'chislennost-vrachey-vseh-spetsialnostey-vsego', 'chislennost-vrachey-vseh-spetsialnostey-na-10000-chelovek', 'nagruzka-na-rabotnikov-sfery-zdravoohraneniya-chislennost-naseleniya', 'nagruzka-na-rabotnikov-sfery-zdravoohraneniya-chislennost-naseleniya-5-5-2', 'chislennost-srednego-meditsinskogo-personala-vsego', 'chislennost-srednego-meditsinskogo-personala-na-10000-chelovek', 'beremennosti-s-abortivnym-ishodom-na-1000-zhenschin', 'beremennosti-s-abortivnym-ishodom-na-100-rodov', 'zabolevaemost-na-1000-chelovek-naseleniya', 'zabolevaemost-na-1000-chelovek-naseleniya-po-osnovnym', 'zabolevaemost-na-1000-chelovek-naseleniya-po-osnovnym-5-9-2', 'zabolevaemost-na-1000-chelovek-naseleniya-po-osnovnym-5-9-3', 'zabolevaemost-na-1000-chelovek-naseleniya-po-osnovnym-5-9-4', 'zabolevaemost-na-1000-chelovek-naseleniya-po-osnovnym-5-9-5', 'zabolevaemost-na-1000-chelovek-naseleniya-po-osnovnym-5-9-6', 'zabolevaemost-na-1000-chelovek-naseleniya-po-osnovnym-5-9-7', 'zabolevaemost-na-1000-chelovek-naseleniya-po-osnovnym-5-9-8', 'zabolevaemost-na-1000-chelovek-naseleniya-po-osnovnym-5-9-9', 'zabolevaemost-na-1000-chelovek-naseleniya-po-osnovnym-5-9-10', 'zabolevaemost-na-1000-chelovek-naseleniya-po-osnovnym-5-9-11', 'zabolevaemost-na-1000-chelovek-naseleniya-po-osnovnym-5-9-12', 'zabolevaemost-na-1000-chelovek-naseleniya-po-osnovnym-5-9-13', 'zabolevaemost-na-1000-chelovek-naseleniya-po-osnovnym-5-9-14', 'zabolevaemost-na-1000-chelovek-naseleniya-po-osnovnym-5-9-15', 'zabolevaemost-na-1000-chelovek-naseleniya-po-osnovnym-5-9-16', 'chislennost-zriteley-teatrov-i-chislo-posescheniy-muzeev', 'chislennost-zriteley-teatrov-i-chislo-posescheniy-muzeev-6-1-2', 'chislo-sportivnyh-sooruzheniy-stadiony-s-tribunami-na', 'chislo-sportivnyh-sooruzheniy-ploskostnye-sportivnye-sooruzheniya-ploschadki', 'chislo-sportivnyh-sooruzheniy-sportivnye-zaly', 'chislo-sportivnyh-sooruzheniy-plavatelnye-basseyny', 'obschedostupnye-biblioteki-bibliotechnyy-fond-na-1000-chelovek', 'obschedostupnye-biblioteki-chislennost-polzovateley', 'vypusk-gazet-na-1000-chelovek-naseleniya', 'detskie-ozdorovitelnye-lagerya-chislo-detskih-ozdorovitelnyh-lagerey', 'detskie-ozdorovitelnye-lagerya-chislennost-detey-otdohnuvshih-v', 'chislennost-otdohnuvshih-detey-v-subekte-rossiyskoy-federatsii', 'kollektivnye-sredstva-razmescheniya-chislo-kollektivnyh-sredstv-razmescheniya', 'kollektivnye-sredstva-razmescheniya-chislennost-razmeschennyh-lits', 'turistskie-firmy-chislo-turistskih-firm', 'turistskie-firmy-chislo-turpaketov-realizovannyh-naseleniyu', 'chislennost-rossiyskih-turistov-obsluzhennyh-turistskimi-firmami-chislennost', 'chislennost-rossiyskih-turistov-obsluzhennyh-turistskimi-firmami-chislennost-6-9-2', 'zemelnaya-ploschad-po-vidam-ugodiy-selskohozyaystvennye-ugodya', 'zemelnaya-ploschad-po-vidam-ugodiy-lesnye-zemli', 'zemelnaya-ploschad-po-vidam-ugodiy-poverhnostnye-vody', 'vybrosy-zagryaznyayuschih-veschestv-v-atmosfernyy-vozduh-othodyaschih', 'ulavlivanie-zagryaznyayuschih-atmosferu-veschestv-othodyaschih-ot-statsionarnyh', 'dolya-ulovlennyh-i-obezvrezhennyh-zagryaznyayuschih-atmosferu-veschestv', 'ispolzovanie-svezhey-vody', 'obem-oborotnoy-i-posledovatelno-ispolzuemoy-vody', 'sbros-zagryaznennyh-stochnyh-vod-v-poverhnostnye-vodnye', 'valovoy-regionalnyy-produkt', 'valovoy-regionalnyy-produkt-na-dushu-naseleniya', 'indeks-fizicheskogo-obema-valovogo-regionalnogo-produkta', 'fakticheskoe-konechnoe-potreblenie-domashnih-hozyaystv-na-territorii', 'fakticheskoe-konechnoe-potreblenie-domashnih-hozyaystv-na-territorii-8-4-2', 'fakticheskoe-konechnoe-potreblenie-domashnih-hozyaystv-na-territorii-8-4-3', 'fakticheskoe-konechnoe-potreblenie-domashnih-hozyaystv-na-dushu', 'valovoe-nakoplenie-osnovnogo-kapitala-v-2000-2015', 'stoimost-osnovnyh-fondov', 'vvod-v-deystvie-osnovnyh-fondov', 'stepen-iznosa-osnovnyh-fondov', 'udelnyy-ves-polnostyu-iznoshennyh-osnovnyh-fondov-v', 'investitsii-v-osnovnoy-kapital', 'investitsii-v-osnovnoy-kapital-na-dushu-naseleniya', 'indeks-fizicheskogo-obema-investitsiy-v-osnovnoy-kapital', 'chislo-organizatsiy', 'oborot-organizatsiy', 'saldirovannyy-finansovyy-rezultat-pribyl-ubytok-do-nalogooblozheniya', 'udelnyy-ves-ubytochnyh-organizatsiy', 'kreditorskaya-zadolzhennost-organizatsiy-vsego', 'kreditorskaya-zadolzhennost-organizatsiy-prosrochennaya', 'debitorskaya-zadolzhennost-organizatsiy-vsego', 'debitorskaya-zadolzhennost-organizatsiy-prosrochennaya', 'chislennost-rabotnikov-pered-kotorymi-organizatsiya-imeet-prosrochennuyu', 'prosrochennaya-zadolzhennost-po-zarabotnoy-plate-rabotnikam-organizatsiy', 'prosrochennaya-zadolzhennost-po-zarabotnoy-plate-v-raschete', 'itogi-vyborochnyh-obsledovaniy-srednyaya-chislennost-rabotnikov-malyh', 'itogi-vyborochnyh-obsledovaniy-oborot-malyh-predpriyatiy', 'itogi-sploshnyh-nablyudeniy-chislo-malyh-predpriyatiy-v', 'itogi-sploshnyh-nablyudeniy-chislo-malyh-predpriyatiy-na', 'itogi-sploshnyh-nablyudeniy-srednespisochnaya-chislennost-rabotnikov-bez', 'itogi-sploshnyh-nablyudeniy-vyruchka-ot-realizatsii-tovarov', 'itogi-vyborochnyh-obsledovaniy-chislennost-fakticheski-deystvuyuschih-individualnyh', 'itogi-vyborochnyh-obsledovaniy-chislennost-zanyatyh-v-biznese', 'itogi-vyborochnyh-obsledovaniy-obem-vyruchki-ot-prodazhi', 'itogi-sploshnyh-nablyudeniy-chislo-individualnyh-predprinimateley-v', 'itogi-sploshnyh-nablyudeniy-chislo-individualnyh-predprinimateley-na', 'itogi-sploshnyh-nablyudeniy-srednyaya-chislennost-rabotnikov-v', 'itogi-sploshnyh-nablyudeniy-vyruchka-ot-realizatsii-tovarov-11-13-4', 'obem-promyshlennoy-produktsii-v-2000-2004-gg', 'obem-otgruzhennyh-tovarov-sobstvennogo-proizvodstva-vypolnennyh-rabot', 'obem-otgruzhennyh-tovarov-sobstvennogo-proizvodstva-vypolnennyh-rabot-12-2-2', 'obem-otgruzhennyh-tovarov-sobstvennogo-proizvodstva-vypolnennyh-rabot-12-2-3', 'obem-otgruzhennyh-tovarov-sobstvennogo-proizvodstva-vypolnennyh-rabot-12-2-4', 'obem-otgruzhennyh-tovarov-sobstvennogo-proizvodstva-vypolnennyh-rabot-12-2-5', 'obem-otgruzhennyh-tovarov-sobstvennogo-proizvodstva-vypolnennyh-rabot-12-2-6', 'obem-otgruzhennyh-tovarov-sobstvennogo-proizvodstva-vypolnennyh-rabot-12-2-7', 'indeksy-promyshlennogo-proizvodstva-v-sootvetstvii-s-okved', 'indeksy-promyshlennogo-proizvodstva-v-sootvetstvii-s-okved2', 'indeksy-proizvodstva-po-vidu-ekonomicheskoy-deyatelnosti-dobycha', 'indeksy-proizvodstva-po-vidu-ekonomicheskoy-deyatelnosti-dobycha-12-4-2', 'indeksy-proizvodstva-po-vidu-ekonomicheskoy-deyatelnosti-obrabatyvayuschie', 'indeksy-proizvodstva-po-vidu-ekonomicheskoy-deyatelnosti-obrabatyvayuschie-12-5-2', 'indeksy-proizvodstva-po-vidu-ekonomicheskoy-deyatelnosti-proizvodstvo', 'indeksy-proizvodstva-po-vidu-ekonomicheskoy-deyatelnosti-obespechenie', 'indeksy-proizvodstva-po-vidu-ekonomicheskoy-deyatelnosti-vodosnabzhenie', 'moschnost-elektrostantsiy', 'proizvodstvo-elektroenergii', 'produktsiya-selskogo-hozyaystva', 'indeksy-proizvodstva-produktsii-selskogo-hozyaystva-vsego', 'indeksy-proizvodstva-produktsii-selskogo-hozyaystva-produktsiya-rastenievodstva', 'indeksy-proizvodstva-produktsii-selskogo-hozyaystva-produktsiya-zhivotnovodstva', 'osnovnye-finansovye-pokazateli-organizatsiy-osuschestvlyayuschih-deyatelnost-v', 'osnovnye-finansovye-pokazateli-organizatsiy-osuschestvlyayuschih-deyatelnost-v-13-3-2', 'osnovnye-finansovye-pokazateli-organizatsiy-osuschestvlyayuschih-deyatelnost-v-13-3-3', 'osnovnye-finansovye-pokazateli-organizatsiy-osuschestvlyayuschih-deyatelnost-v-13-3-4', 'posevnye-ploschadi-selskohozyaystvennyh-kultur', 'posevnye-ploschadi-zernovyh-i-zernobobovyh-kultur', 'posevnye-ploschadi-saharnoy-svekly', 'posevnye-ploschadi-podsolnechnika', 'posevnye-ploschadi-kartofelya', 'posevnye-ploschadi-ovoschey', 'valovoy-sbor-zerna-v-vese-posle-dorabotki', 'urozhaynost-zernovyh-i-zernobobovyh-kultur-v-vese', 'valovoy-sbor-saharnoy-svekly', 'urozhaynost-saharnoy-svekly', 'valovoy-sbor-semyan-podsolnechnika-v-vese-posle', 'urozhaynost-podsolnechnika', 'valovoy-sbor-kartofelya', 'urozhaynost-kartofelya', 'valovoy-sbor-ovoschey', 'urozhaynost-ovoschey', 'valovoy-sbor-plodov-i-yagod', 'vnesenie-udobreniy-na-odin-gektar-poseva-selskohozyaystvennyh', 'vnesenie-udobreniy-na-odin-gektar-poseva-selskohozyaystvennyh-13-21-2', 'pogolove-krupnogo-rogatogo-skota', 'pogolove-sviney', 'pogolove-ovets-i-koz', 'proizvodstvo-skota-i-ptitsy-na-uboy-v', 'proizvodstvo-moloka', 'nadoy-moloka-na-odnu-korovu-v-selskohozyaystvennyh', 'proizvodstvo-yaits', 'srednyaya-godovaya-yaytsenoskost-kur-nesushek-v-selskohozyaystvennyh', 'proizvodstvo-shersti', 'sredniy-godovoy-nastrig-shersti-s-odnoy-ovtsy', 'proizvodstvo-meda', 'rashod-kormov-v-raschete-na-odnu-uslovnuyu', 'lesnye-resursy-ploschad-zemel-lesnogo-fonda-i', 'lesnye-resursy-ploschad-pokrytaya-lesom', 'lesnye-resursy-lesistost-territoriy', 'lesnye-resursy-obschiy-zapas-drevesiny', 'lesovosstanovlenie', 'lesnye-pozhary-na-zemlyah-lesnogo-fonda-i', 'lesnye-pozhary-na-zemlyah-lesnogo-fonda-i-13-36-2', 'osnovnye-pokazateli-po-vidu-deyatelnosti-lesozagotovki-chislo', 'osnovnye-pokazateli-po-vidu-deyatelnosti-lesozagotovki-srednespisochnaya', 'osnovnye-pokazateli-po-vidu-deyatelnosti-lesozagotovki-saldirovannyy', 'osnovnye-pokazateli-po-vidu-deyatelnosti-lesozagotovki-udelnyy', 'proizvodstvo-lesomaterialov-neobrabotannyh', 'osnovnye-pokazateli-po-vidu-ekonomicheskoy-deyatelnosti-rybolovstvo', 'osnovnye-pokazateli-po-vidu-ekonomicheskoy-deyatelnosti-rybolovstvo-13-39-2', 'osnovnye-pokazateli-po-vidu-ekonomicheskoy-deyatelnosti-rybolovstvo-13-39-3', 'osnovnye-pokazateli-po-vidu-ekonomicheskoy-deyatelnosti-rybolovstvo-13-39-4', 'osnovnye-pokazateli-po-vidu-ekonomicheskoy-deyatelnosti-rybovodstvo', 'osnovnye-pokazateli-po-vidu-ekonomicheskoy-deyatelnosti-rybovodstvo-13-40-2', 'osnovnye-pokazateli-po-vidu-ekonomicheskoy-deyatelnosti-rybovodstvo-13-40-3', 'osnovnye-pokazateli-po-vidu-ekonomicheskoy-deyatelnosti-rybovodstvo-13-40-4', 'ulov-ryby-i-dobycha-drugih-vodnyh-bioresursov', 'obem-rabot-vypolnennyh-po-vidu-ekonomicheskoy-deyatelnosti', 'vvod-v-deystvie-zdaniy-zhilogo-i-nezhilogo', 'vvod-v-deystvie-zdaniy-zhilogo-i-nezhilogo-14-2-2', 'vvod-v-deystvie-zhilyh-domov-vsego', 'vvod-v-deystvie-zhilyh-domov-na-1000', 'vvod-v-deystvie-kvartir-vsego', 'vvod-v-deystvie-kvartir-na-1000-chelovek', 'vvod-v-deystvie-zhilyh-domov-postroennyh-zhilischno', 'vvod-v-deystvie-zhilyh-domov-postroennyh-naseleniem', 'chislo-zdaniy-i-sooruzheniy-nahodyaschihsya-v-nezavershennom', 'zhilye-doma-nahodyaschiesya-v-nezavershennom-stroitelstve', 'udelnyy-ves-zhilyh-domov-postroennyh-naseleniem-za', 'vvod-v-deystvie-moschnostey-obscheobrazovatelnyh-organizatsiy-obscheobrazovatelnye', 'vvod-v-deystvie-moschnostey-obscheobrazovatelnyh-organizatsiy-doshkolnye', 'vvod-v-deystvie-moschnostey-bolnichnyh-organizatsiy-vsego', 'vvod-v-deystvie-moschnostey-bolnichnyh-organizatsiy-na', 'vvod-v-deystvie-moschnostey-ambulatorno-poliklinicheskih-organizatsiy', 'vvod-v-deystvie-moschnostey-ambulatorno-poliklinicheskih-organizatsiy-14-12-2', 'oborot-roznichnoy-torgovli', 'indeksy-fizicheskogo-obema-oborota-roznichnoy-torgovli', 'oborot-roznichnoy-torgovli-na-dushu-naseleniya', 'prodazha-tovarov-na-roznichnyh-rynkah-i-yarmarkah', 'oborot-roznichnoy-torgovli-po-torgovym-setyam', 'struktura-oborota-roznichnoy-torgovli-pischevye-produkty-vklyuchaya', 'struktura-oborota-roznichnoy-torgovli-neprodovolstvennye-tovary', 'oborot-obschestvennogo-pitaniya', 'oborot-obschestvennogo-pitaniya-na-dushu-naseleniya', 'oborot-optovoy-torgovli-vsego', 'oborot-optovoy-torgovli-oborot-optovoy-torgovli-organizatsiy', 'obem-platnyh-uslug-naseleniyu-vsego', 'obem-platnyh-uslug-naseleniyu-indeksy-fizicheskogo-obema', 'obem-platnyh-uslug-naseleniyu-na-dushu-naseleniya', 'obem-bytovyh-uslug-naseleniyu-vsego', 'obem-bytovyh-uslug-naseleniyu-na-dushu-naseleniya', 'obem-transportnyh-uslug-naseleniyu-vsego', 'obem-transportnyh-uslug-naseleniyu-na-dushu-naseleniya', 'obem-telekommunikatsionnyh-uslug-naseleniyu-vsego', 'obem-telekommunikatsionnyh-uslug-naseleniyu-na-dushu-naseleniya', 'obem-kommunalnyh-uslug-naseleniyu-vsego', 'obem-kommunalnyh-uslug-naseleniyu-na-dushu-naseleniya', 'otpravlenie-passazhirov-zheleznodorozhnym-transportom-obschego-polzovaniya', 'plotnost-zheleznodorozhnyh-putey-obschego-polzovaniya', 'perevozki-gruzov-avtomobilnym-transportom-organizatsiy-vseh-vidov', 'gruzooborot-avtomobilnogo-transporta-organizatsiy-vseh-vidov-deyatelnosti', 'perevozki-passazhirov-avtobusami-obschego-polzovaniya', 'passazhirooborot-avtobusov-obschego-polzovaniya', 'udelnyy-ves-avtomobilnyh-dorog-s-tverdym-pokrytiem', 'udelnyy-ves-avtomobilnyh-dorog-s-usovershenstvovannym-pokrytiem', 'plotnost-avtomobilnyh-dorog-obschego-polzovaniya-s-tverdym', 'chislo-avtobusov-obschego-polzovaniya-na-100000-chelovek', 'chislo-dorozhno-transportnyh-proisshestviy-na-100000-chelovek', 'chislo-lits-pogibshih-v-dorozhno-transportnyh-proisshestviyah', 'ispolzovanie-tsifrovyh-tehnologiy-v-organizatsiyah-organizatsii-ispolzovavshie', 'ispolzovanie-tsifrovyh-tehnologiy-v-organizatsiyah-organizatsii-ispolzovavshie-17-1-2', 'ispolzovanie-tsifrovyh-tehnologiy-v-organizatsiyah-organizatsii-ispolzovavshie-17-1-3', 'ispolzovanie-tsifrovyh-tehnologiy-v-organizatsiyah-organizatsii-ispolzovavshie-17-1-4', 'ispolzovanie-tsifrovyh-tehnologiy-v-organizatsiyah-organizatsii-ispolzovavshie-17-1-5', 'ispolzovanie-tsifrovyh-tehnologiy-v-organizatsiyah-organizatsii-ispolzovavshie-17-1-6', 'ispolzovanie-tsifrovyh-tehnologiy-v-organizatsiyah-organizatsii-ispolzovavshie-17-1-7', 'ispolzovanie-tsifrovyh-tehnologiy-v-organizatsiyah-organizatsii-ispolzovavshie-17-1-8', 'ispolzovanie-tsifrovyh-tehnologiy-v-organizatsiyah-organizatsii-ispolzovavshie-17-1-9', 'ispolzovanie-organizatsiyami-mobilnogo-i-fiksirovannogo-interneta', 'ispolzovanie-shirokopolosnogo-dostupa-k-seti-internet-v', 'organizatsii-imevshie-veb-sayt', 'ispolzovanie-elektronnogo-dokumentooborota-v-organizatsiyah-organizatsii-ispolzovavshie', 'ispolzovanie-elektronnogo-dokumentooborota-v-organizatsiyah-organizatsii-ispolzovavshie-17-5-2', 'ispolzovanie-kompyuterov-i-seti-internet-v-domashnih', 'ispolzovanie-kompyuterov-i-seti-internet-v-domashnih-17-6-2', 'ispolzovanie-kompyuterov-i-seti-internet-v-domashnih-17-6-3', 'ispolzovanie-seti-internet-naseleniem-naselenie-ispolzovavshee-set', 'ispolzovanie-seti-internet-naseleniem-naselenie-ispolzovavshee-set-17-7-2', 'ispolzovanie-seti-internet-naseleniem-naselenie-ispolzovavshee-set-17-7-3', 'chislo-podklyuchennyh-abonentskih-ustroystv-mobilnoy-svyazi-na', 'chislennost-aktivnyh-abonentov-fiksirovannogo-i-mobilnogo-shirokopolosnogo', 'chislennost-aktivnyh-abonentov-fiksirovannogo-i-mobilnogo-shirokopolosnogo-17-9-2', 'organizatsii-vypolnyavshie-nauchnye-issledovaniya-i-razrabotki', 'chislennost-personala-zanyatogo-nauchnymi-issledovaniyami-i-razrabotkami', 'chislennost-personala-zanyatogo-nauchnymi-issledovaniyami-i-razrabotkami-18-3-1', 'chislennost-personala-zanyatogo-nauchnymi-issledovaniyami-i-razrabotkami-18-3-2', 'chislennost-personala-zanyatogo-nauchnymi-issledovaniyami-i-razrabotkami-18-3-3', 'chislennost-personala-zanyatogo-nauchnymi-issledovaniyami-i-razrabotkami-18-3-4', 'chislennost-issledovateley-s-uchenymi-stepenyami-vsego', 'chislennost-issledovateley-s-uchenymi-stepenyami-s-uchenoy', 'chislennost-issledovateley-s-uchenymi-stepenyami-s-uchenoy-18-4-3', 'vnutrennie-zatraty-na-nauchnye-issledovaniya-i-razrabotki', 'vnutrennie-tekuschie-zatraty-na-nauchnye-issledovaniya-i', 'vnutrennie-tekuschie-zatraty-na-nauchnye-issledovaniya-i-18-6-2', 'vnutrennie-tekuschie-zatraty-na-nauchnye-issledovaniya-i-18-6-3', 'vnutrennie-tekuschie-zatraty-na-nauchnye-issledovaniya-i-18-6-4', 'vnutrennie-tekuschie-zatraty-na-nauchnye-issledovaniya-i-18-6-5', 'vnutrennie-tekuschie-zatraty-na-nauchnye-issledovaniya-i-18-6-6', 'kapitalnye-zatraty-na-nauchnye-issledovaniya-i-razrabotki', 'vnutrennie-tekuschie-zatraty-na-nauchnye-issledovaniya-i-18-8-1', 'vnutrennie-tekuschie-zatraty-na-nauchnye-issledovaniya-i-18-8-2', 'vnutrennie-tekuschie-zatraty-na-nauchnye-issledovaniya-i-18-8-3', 'vnutrennie-tekuschie-zatraty-na-nauchnye-issledovaniya-i-18-8-4', 'postuplenie-patentnyh-zayavok-i-vydacha-patentov-v', 'postuplenie-patentnyh-zayavok-i-vydacha-patentov-v-18-9-2', 'postuplenie-patentnyh-zayavok-i-vydacha-patentov-v-18-9-3', 'postuplenie-patentnyh-zayavok-i-vydacha-patentov-v-18-9-4', 'razrabotannye-peredovye-proizvodstvennye-tehnologii', 'ispolzuemye-peredovye-proizvodstvennye-tehnologii', 'innovatsionnaya-aktivnost-organizatsii-uroven-innovatsionnoy-aktivnosti-organizatsiy', 'innovatsionnaya-aktivnost-organizatsii-udelnyy-ves-organizatsiy-osuschestvlyavshih', 'zatraty-na-innovatsionnuyu-deyatelnost-organizatsiy-vsego', 'zatraty-na-innovatsionnuyu-deyatelnost-organizatsiy-v-protsentah', 'obem-innovatsionnyh-tovarov-rabot-uslug-vsego', 'obem-innovatsionnyh-tovarov-rabot-uslug-v-protsentah', 'dohody-konsolidirovannyh-byudzhetov-subektov-rossiyskoy-federatsii', 'rashody-konsolidirovannyh-byudzhetov-subektov-rossiyskoy-federatsii', 'rashody-konsolidirovannyh-byudzhetov-subektov-rossiyskoy-federatsii-na', 'ispolnenie-byudzheta-pensionnogo-fonda-rossiyskoy-federatsii-v', 'ispolnenie-byudzheta-pensionnogo-fonda-rossiyskoy-federatsii-v-19-4-2', 'ispolnenie-byudzheta-fonda-sotsialnogo-strahovaniya-rossiyskoy-federatsii', 'ispolnenie-byudzheta-fonda-sotsialnogo-strahovaniya-rossiyskoy-federatsii-19-5-2', 'ispolnenie-byudzheta-fonda-pensionnogo-i-sotsialnogo-strahovaniya', 'ispolnenie-byudzhetov-territorialnyh-fondov-obyazatelnogo-meditsinskogo-strahovaniya', 'ispolnenie-byudzhetov-territorialnyh-fondov-obyazatelnogo-meditsinskogo-strahovaniya-19-7-2', 'chislo-deystvuyuschih-kreditnyh-organizatsiy', 'chislo-deystvuyuschih-filialov-kreditnyh-organizatsiy-v-subekte', 'sredstva-vklady-yuridicheskih-i-fizicheskih-lits-v', 'sredstva-vklady-yuridicheskih-i-fizicheskih-lits-v-19-10-2', 'sredstva-vklady-yuridicheskih-i-fizicheskih-lits-v-19-11-1', 'sredstva-vklady-yuridicheskih-i-fizicheskih-lits-v-19-11-2', 'sredstva-vklady-fizicheskih-lits-na-rublevyh-schetah', 'sredstva-vklady-fizicheskih-lits-na-valyutnyh-schetah', 'zadolzhennost-po-kreditam-v-rublyah-predostavlennym-kreditnymi', 'zadolzhennost-po-kreditam-v-rublyah-predostavlennym-kreditnymi-19-15-1', 'zadolzhennost-po-kreditam-v-rublyah-predostavlennym-kreditnymi-19-15-2', 'zadolzhennost-po-kreditam-v-rublyah-predostavlennym-kreditnymi-19-15-3', 'zadolzhennost-po-kreditam-v-inostrannoy-valyute-predostavlennym', 'zadolzhennost-po-kreditam-v-inostrannoy-valyute-predostavlennym-19-17-1', 'zadolzhennost-po-kreditam-v-inostrannoy-valyute-predostavlennym-19-17-2', 'zadolzhennost-po-kreditam-v-inostrannoy-valyute-predostavlennym-19-17-3', 'otdelnye-pokazateli-deyatelnosti-strahovschikov-strahovye-premii-vznosy', 'otdelnye-pokazateli-deyatelnosti-strahovschikov-vyplaty-po-dogovoram', 'otdelnye-pokazateli-deyatelnosti-strahovschikov-ishodya-iz-mesta', 'otdelnye-pokazateli-deyatelnosti-strahovschikov-ishodya-iz-mesta-19-19-2', 'indeksy-potrebitelskih-tsen', 'stoimost-uslovnogo-minimalnogo-nabora-produktov-pitaniya-stoimost', 'stoimost-uslovnogo-minimalnogo-nabora-produktov-pitaniya-stoimost-20-2-2', 'stoimost-uslovnogo-minimalnogo-nabora-produktov-pitaniya-izmenenie', 'stoimost-fiksirovannogo-nabora-potrebitelskih-tovarov-i-uslug', 'stoimost-fiksirovannogo-nabora-potrebitelskih-tovarov-i-uslug-20-3-2', 'stoimost-fiksirovannogo-nabora-potrebitelskih-tovarov-i-uslug-20-3-3', 'indeksy-potrebitelskih-tsen-na-prodovolstvennye-tovary', 'indeksy-potrebitelskih-tsen-na-neprodovolstvennye-tovary', 'indeksy-potrebitelskih-tsen-tarifov-na-uslugi', 'indeksy-tsen-na-pervichnom-rynke-zhilya', 'indeksy-tsen-na-vtorichnom-rynke-zhilya', 'srednie-tseny-na-pervichnom-rynke-zhilya', 'srednie-tseny-na-vtorichnom-rynke-zhilya', 'indeksy-tsen-proizvoditeley-promyshlennyh-tovarov-po-vidam', 'indeksy-tsen-proizvoditeley-promyshlennyh-tovarov-po-vidam-20-11-2', 'indeksy-tsen-proizvoditeley-promyshlennyh-tovarov-po-vidam-20-11-3', 'indeksy-tsen-proizvoditeley-promyshlennyh-tovarov-po-vidam-20-11-4', 'indeksy-tsen-proizvoditeley-promyshlennyh-tovarov-po-vidam-20-11-5', 'indeksy-tsen-proizvoditeley-promyshlennyh-tovarov-po-vidam-20-11-6', 'indeksy-tsen-proizvoditeley-promyshlennyh-tovarov-po-vidam-20-11-7', 'indeksy-tsen-proizvoditeley-promyshlennyh-tovarov-po-vidam-20-11-8', 'indeksy-tsen-proizvoditeley-promyshlennyh-tovarov-po-vidam-20-11-9', 'indeksy-tsen-proizvoditeley-selskohozyaystvennoy-produktsii-i-priobreteniya', 'indeksy-tsen-proizvoditeley-selskohozyaystvennoy-produktsii-i-priobreteniya-20-12-2', 'indeksy-tsen-proizvoditeley-na-stroitelnuyu-produktsiyu', 'indeksy-tarifov-na-gruzovye-perevozki', 'chislennost-gosudarstvennyh-grazhdanskih-munitsipalnyh-sluzhaschih-gosudarstvennyh-organov', 'chislennost-gosudarstvennyh-grazhdanskih-sluzhaschih-territorialnyh-organov-federalnyh', 'chislennost-gosudarstvennyh-grazhdanskih-munitsipalnyh-sluzhaschih-organov-ispolnitelnoy', 'chislennost-munitsipalnyh-sluzhaschih-organov-mestnogo-samoupravleniya-vsego', 'chislennost-munitsipalnyh-sluzhaschih-organov-mestnogo-samoupravleniya-v', 'chislennost-munitsipalnyh-sluzhaschih-organov-mestnogo-samoupravleniya-v-2-18-3', 'srednemesyachnaya-nachislennaya-zarabotnaya-plata-rabotnikov-organov-mestnogo', 'srednemesyachnaya-nachislennaya-zarabotnaya-plata-rabotnikov-organov-mestnogo-3-5-2', 'srednemesyachnaya-nachislennaya-zarabotnaya-plata-rabotnikov-organov-mestnogo-3-5-3', 'velichina-prozhitochnogo-minimuma-pensionera-v-tselyah-ustanovleniya', 'postuplenie-pryamyh-inostrannyh-investitsiy-v-rossiyskuyu-federatsiyu', 'postuplenie-pryamyh-inostrannyh-investitsiy-v-rossiyskuyu-federatsiyu-10-4-2', 'postuplenie-pryamyh-inostrannyh-investitsiy-v-rossiyskuyu-federatsiyu-10-4-3', 'posevnye-ploschadi-lna-dolguntsa', 'valovoy-sbor-lnovolokna', 'urozhaynost-lna-dolguntsa', 'otpravlenie-gruzov-zheleznodorozhnym-transportom-obschego-polzovaniya', 'vneshnyaya-torgovlya-so-stranami-dalnego-zarubezhya-eksport', 'vneshnyaya-torgovlya-so-stranami-dalnego-zarubezhya-import', 'vneshnyaya-torgovlya-so-stranami-sng-eksport', 'vneshnyaya-torgovlya-so-stranami-sng-import', 'izmenenie-chislennosti-naseleniya', 'organizatsii-ispolzovavshie-set-internet', 'chislo-personalnyh-kompyuterov-na-100-rabotnikov-vsego', 'chislo-personalnyh-kompyuterov-na-100-rabotnikov-s', 'chislo-zaregistrirovannyh-prestupleniy-na-100000', 'chislo-zaregistrirovannyh-ubiystv-i-pokusheniy-na-ubiystvo', 'chislo-prestupleniy-nesovershennoletnih' | [backend/app/data/i18n/region_indicators_en.py:12](../backend/app/data/i18n/region_indicators_en.py#L12) |
| app.data.i18n.regions_en.REGIONS_EN | Dict | 'russia', 'cfo', 'szfo', 'ufo-south', 'skfo', 'pfo', 'urfo', 'sfo', 'dfo', 'belgorodskaya-oblast', 'bryanskaya-oblast', 'vladimirskaya-oblast', 'voronezhskaya-oblast', 'ivanovskaya-oblast', 'kaluzhskaya-oblast', 'kostromskaya-oblast', 'kurskaya-oblast', 'lipetskaya-oblast', 'moskovskaya-oblast', 'orlovskaya-oblast', 'ryazanskaya-oblast', 'smolenskaya-oblast', 'tambovskaya-oblast', 'tverskaya-oblast', 'tulskaya-oblast', 'yaroslavskaya-oblast', 'moskva', 'respublika-kareliya', 'respublika-komi', 'arhangelskaya-oblast', 'nenetskiy-ao', 'vologodskaya-oblast', 'kaliningradskaya-oblast', 'leningradskaya-oblast', 'murmanskaya-oblast', 'novgorodskaya-oblast', 'pskovskaya-oblast', 'sankt-peterburg', 'respublika-adygeya', 'respublika-kalmykiya', 'respublika-krym', 'krasnodarskiy-kray', 'astrahanskaya-oblast', 'volgogradskaya-oblast', 'rostovskaya-oblast', 'sevastopol', 'respublika-dagestan', 'respublika-ingushetiya', 'kabardino-balkarskaya-respublika', 'karachaevo-cherkesskaya-respublika', 'respublika-severnaya-osetiya', 'chechenskaya-respublika', 'stavropolskiy-kray', 'respublika-bashkortostan', 'respublika-mariy-el', 'respublika-mordoviya', 'respublika-tatarstan', 'udmurtskaya-respublika', 'chuvashskaya-respublika', 'permskiy-kray', 'kirovskaya-oblast', 'nizhegorodskaya-oblast', 'orenburgskaya-oblast', 'penzenskaya-oblast', 'samarskaya-oblast', 'saratovskaya-oblast', 'ulyanovskaya-oblast', 'kurganskaya-oblast', 'sverdlovskaya-oblast', 'tyumenskaya-oblast', 'hanty-mansiyskiy-ao', 'yamalo-nenetskiy-ao', 'chelyabinskaya-oblast', 'respublika-altay', 'respublika-tyva', 'respublika-hakasiya', 'altayskiy-kray', 'krasnoyarskiy-kray', 'irkutskaya-oblast', 'kemerovskaya-oblast', 'novosibirskaya-oblast', 'omskaya-oblast', 'tomskaya-oblast', 'respublika-buryatiya', 'respublika-saha', 'zabaykalskiy-kray', 'kamchatskiy-kray', 'primorskiy-kray', 'habarovskiy-kray', 'amurskaya-oblast', 'magadanskaya-oblast', 'sahalinskaya-oblast', 'evreyskaya-ao', 'chukotskiy-ao', 'arhangelskaya-oblast-bez-ao', 'tyumenskaya-oblast-bez-ao' | [backend/app/data/i18n/regions_en.py:16](../backend/app/data/i18n/regions_en.py#L16) |
| app.data.i18n.regions_en.FEDERAL_DISTRICTS_EN | Dict | 'cfo', 'szfo', 'ufo-south', 'skfo', 'pfo', 'urfo', 'sfo', 'dfo' | [backend/app/data/i18n/regions_en.py:116](../backend/app/data/i18n/regions_en.py#L116) |
| app.data.i18n.regions_en.CONTESTED_REGION_NAMES_EN | List | sequence/source expression | [backend/app/data/i18n/regions_en.py:128](../backend/app/data/i18n/regions_en.py#L128) |
| app.data.i18n.seo_en.CATEGORY_META_EN | Dict | 'prices', 'rates', 'currencies', 'indices', 'finance', 'commodities', 'labor', 'gdp', 'population', 'trade', 'business', 'science' | [backend/app/data/i18n/seo_en.py:27](../backend/app/data/i18n/seo_en.py#L27) |
| app.data.i18n.seo_en.PAGE_META_EN | Dict | 'home', 'about', 'methodology', 'privacy', 'terms', 'compare', 'calculator', 'calculator-mortgage', 'calculator-compound', 'calendar', 'demographics', 'widgets', 'russia', 'russia-categories' | [backend/app/data/i18n/seo_en.py:268](../backend/app/data/i18n/seo_en.py#L268) |
| app.data.i18n.seo_en.HOME_TEMPLATES_EN | Dict | 'eyebrow', 'h2_countries', 'h2_flagships', 'h2_tools', 'itemlist_countries', 'itemlist_flagships' | [backend/app/data/i18n/seo_en.py:687](../backend/app/data/i18n/seo_en.py#L687) |
| app.data.i18n.seo_en.PAGE_TEMPLATES_EN | Dict | 'h2_related', 'h2_categories', 'h2_section_indicators' | [backend/app/data/i18n/seo_en.py:701](../backend/app/data/i18n/seo_en.py#L701) |
| app.data.i18n.seo_en.WORLD_TEMPLATES_EN | Dict | 'country_title', 'country_h1', 'country_desc_national', 'country_desc_eurostat', 'indicator_title', 'indicator_desc', 'indicator_h1', 'rating_title', 'rating_title_year', 'rating_title_for_year', 'rating_desc', 'rating_intro', 'n_indicators_one', 'n_indicators_many', 'keywords_rating', 'keywords_country', 'keywords_indicator', 'rating_eyebrow', 'rating_th_rank', 'rating_th_country', 'rating_th_value', 'rating_th_unit', 'rating_th_period', 'rating_h2_full', 'rating_h2_missing', 'rating_missing_p', 'rating_h2_other', 'rating_h2_years', 'rating_h2_source', 'rating_source_p', 'rating_tile_first', 'rating_tile_last', 'rating_tile_with_data', 'rating_tile_last_date', 'rating_no_data', 'rating_unit_fallback', 'rating_of_total', 'rating_money_guard', 'rating_index_guard', 'rating_with_data', 'rating_without_data', 'country_eyebrow_national', 'country_eyebrow_eurostat', 'country_lead_national', 'country_lead_eurostat', 'country_h2_key', 'country_h2_source', 'country_source_national', 'country_source_eurostat', 'country_figcaption', 'country_h2_neighbors', 'country_image_name', 'country_section_total', 'country_h2_russia', 'country_russia_p', 'th_indicator', 'th_value', 'th_period', 'indicator_tile_last', 'indicator_tile_date', 'indicator_tile_period', 'indicator_tile_source', 'indicator_table_h2', 'indicator_h2_source', 'indicator_source_p', 'indicator_h2_russia', 'indicator_russia_p', 'indicator_lead', 'indicator_desc_fallback', 'indicator_unit_clause', 'indicator_period_line', 'indicator_period_line_freq', 'indicator_h2_peers', 'indicator_h2_siblings', 'indicator_open_source', 'indicator_unit_fallback', 'indicator_alt', 'indicator_figcaption', 'indicator_dataset_desc', 'period_year', 'freq_monthly', 'freq_quarterly', 'freq_annual', 'freq_daily', 'freq_weekly' | [backend/app/data/i18n/seo_en.py:715](../backend/app/data/i18n/seo_en.py#L715) |
| app.data.i18n.seo_en.TODAY_SPECS_EN | Dict | 'usd-rub', 'eur-rub', 'cny-rub', 'key-rate', 'cpi', 'gold-price', 'fuel-ai92', 'fuel-ai95', 'fuel-diesel', 'imoex' | [backend/app/data/i18n/seo_en.py:902](../backend/app/data/i18n/seo_en.py#L902) |
| app.data.i18n.seo_en.TODAY_TEMPLATES_EN | Dict | 'title_fresh', 'title_stale', 'desc', 'stale_clause', 'fresh_clause', 'h1_fresh', 'h1_stale', 'keywords', 'change_flat', 'change_up_pp', 'change_down_pp', 'change_up', 'change_down', 'badge_flat', 'faq_h2', 'faq_answer_last', 'faq_answer_change', 'faq_freq_q', 'faq_freq_a', 'eyebrow_fresh', 'eyebrow_stale', 'stale_note', 'tile_prev', 'tile_min', 'tile_max', 'tile_updated', 'on_date', 'source_meta', 'body_lead', 'chart_alt', 'chart_caption', 'cta_chart', 'table_h2', 'th_date', 'th_value', 'range_note', 'history_h2', 'history_p', 'hub_eyebrow', 'hub_lead', 'hub_h2', 'hub_more_h2', 'hub_more_p', 'hub_item_today', 'hub_keywords', 'hub_alt', 'hub_caption' | [backend/app/data/i18n/seo_en.py:945](../backend/app/data/i18n/seo_en.py#L945) |
| app.data.i18n.seo_en.CALENDAR_TEMPLATES_EN | Dict | 'title', 'desc_future', 'desc_past', 'h1', 'intro', 'keywords', 'eyebrow', 'tile_publications', 'tile_rosstat', 'tile_cbr', 'tile_other', 'h2_month', 'h2_neighbors', 'th_date', 'th_publication', 'th_agency', 'th_status', 'status_expected', 'status_dash', 'actual_prefix', 'interactive', 'source_rosstat', 'source_cbr', 'source_minfin', 'months' | [backend/app/data/i18n/seo_en.py:1037](../backend/app/data/i18n/seo_en.py#L1037) |
| app.data.i18n.seo_en.REGIONAL_TEMPLATES_EN | Dict | 'regions_hub.title', 'regions_hub.description', 'regions_hub.h1', 'regions_hub.eyebrow', 'regions_hub.lead', 'regions_hub.ratings_h2', 'regions_hub.ratings_p', 'regions_hub.ratings_h3', 'regions_hub.map_h3', 'regions_hub.keywords', 'region_profile.title', 'region_profile.description', 'region_profile.h1', 'region_profile.eyebrow', 'region_profile.lead', 'region_profile.catalog_partial', 'region_profile.catalog_full', 'region_profile.see_also', 'region_profile.all_regions', 'region_profile.russia_summary', 'region_profile.top_demand', 'region_profile.keywords', 'region_indicator.title', 'region_indicator.description', 'region_indicator.h1', 'region_indicator.p1', 'region_indicator.p1_change', 'region_indicator.p2_5y', 'region_indicator.p2_full', 'region_indicator.p3', 'region_indicator.p3_rf', 'region_indicator.rel_above', 'region_indicator.rel_below', 'region_indicator.rel_level', 'region_indicator.rating_full', 'region_indicator.rating_table', 'region_indicator.p4', 'region_indicator.checkpoints_h2', 'region_indicator.checkpoint_item', 'region_indicator.faq_h2', 'region_indicator.faq_value_q', 'region_indicator.faq_value_a', 'region_indicator.faq_rank_q', 'region_indicator.faq_rank_a', 'region_indicator.faq_list_q', 'region_indicator.faq_list_a', 'region_indicator.faq_change_q', 'region_indicator.faq_change_a', 'region_indicator.faq_source_q', 'region_indicator.faq_source_a', 'region_indicator.macro_h2', 'region_indicator.macro_p', 'region_indicator.neighbors_h2', 'region_indicator.table_h2', 'region_indicator.th_year', 'region_indicator.th_value', 'region_indicator.alt', 'region_indicator.caption', 'region_indicator.siblings_h2', 'region_indicator.rank_bit_achievement', 'region_indicator.rank_bit_list', 'region_indicator.rank_bit_none', 'region_indicator.keywords', 'region_indicator.pct_flat', 'region_indicator.pct_up', 'region_indicator.pct_down', 'region_indicator.pct_by', 'region_indicator.pct_times', 'region_indicator.times_word', 'region_indicator.rank_top3', 'region_indicator.rank_top10', 'region_indicator.rank_bottom', 'region_indicator.rank_place', 'region_indicator.list_top3', 'region_indicator.list_top10', 'region_indicator.list_bottom', 'region_indicator.list_place', 'region_rating_hub.title', 'region_rating_hub.description', 'region_rating_hub.h1', 'region_rating_hub.eyebrow', 'region_rating_hub.lead', 'region_rating_hub.keywords', 'region_rating.title', 'region_rating.description', 'region_rating.h1', 'region_vs.title', 'region_vs.description', 'region_vs.h1', 'region_vs.intro', 'region_vs.eyebrow', 'region_vs.alt', 'region_vs.caption', 'region_vs.table_h2', 'region_vs.th_indicator', 'region_vs.th_year', 'region_vs.section_dynamics', 'region_vs.rating_link', 'region_vs.profiles_h2', 'region_vs.profiles_p', 'region_vs.keywords', 'region_vs.jsonld_name', 'region_vs.image_name', 'region_rating.alt', 'region_rating.russia_tile', 'region_rating.data_for', 'region_rating.year_suffix', 'region_rating.regions_n', 'region_rating.th_region', 'region_rating.faq_h2', 'region_rating.faq_year_q', 'region_rating.faq_year_a', 'region_rating.map_h2', 'region_rating.map_p', 'region_rating.macro_h2', 'region_rating.macro_p', 'region_rating.source_h2', 'region_rating.source_p', 'region_rating.keywords', 'region_rating.image_name', 'region_rating.siblings_rankings', 'region_rating.siblings_indicators', 'region_rating.source_label', 'region_map.title', 'region_map.description', 'region_map.h1', 'region_map.eyebrow', 'region_map.lead', 'region_map.year_note', 'region_map.year_note_stale', 'region_map.tile_year', 'region_map.tile_regions', 'region_map.leaders_h2', 'region_map.rating_h2', 'region_map.rating_p', 'region_map.rating_label_achievement', 'region_map.rating_label_list', 'region_map.years_h2', 'region_map.source_h2', 'region_map.source_p', 'region_map.caption', 'region_map.alt', 'region_map.crumb', 'region_map.overview_title', 'region_map.overview_desc', 'region_map.overview_h1', 'region_map.overview_eyebrow', 'region_map.overview_lead', 'region_map.overview_popular_h2', 'region_map.overview_rankings_h2', 'region_map.overview_rankings_p', 'region_map.overview_keywords', 'region_map.keywords' | [backend/app/data/i18n/seo_en.py:1099](../backend/app/data/i18n/seo_en.py#L1099) |
| app.data.i18n.seo_en.YEAR_TEMPLATES_EN | Dict | 'title_annual_current', 'title_annual', 'title_ytd', 'title_single', 'title_quarterly', 'title_weekly', 'title_daily', 'title_monthly', 'desc_single', 'desc_multi', 'period_note_ytd', 'summary_as_of', 'summary_annual_value', 'summary_value', 'summary_chain', 'summary_sum', 'summary_last', 'summary_avg', 'h2_single', 'h2_single_as_of', 'h2_ytd', 'h2_totals', 'h2_neighbors', 'h2_all_values', 'h2_chart', 'h2_other_years', 'chart_p', 'year_link', 'chart_alt_single', 'chart_alt_multi', 'chart_caption_single', 'chart_caption_multi', 'image_caption_single', 'image_caption_multi', 'jsonld_name', 'keywords', 'th_year', 'th_date', 'th_value', 'th_value_unit', 'th_cpi_change', 'li_value_date', 'li_source', 'li_summary', 'li_year_start', 'li_year_end', 'li_latest', 'li_range', 'li_obs', 'range_minmax', 'range_cpi', 'change_value', 'change_no_prev', 'change_no_data', 'change_vs', 'change_zero_base', 'hist_insufficient', 'hist_no_data', 'hist_above', 'hist_below', 'hist_at', 'hist_position', 'hist_max_sole', 'hist_max_tie', 'hist_max_other', 'hist_min_sole', 'hist_min_tie', 'hist_min_other', 'gap_ago' | [backend/app/data/i18n/seo_en.py:1399](../backend/app/data/i18n/seo_en.py#L1399) |
| app.data.i18n.seo_en.INDICATOR_TEMPLATES_EN | Dict | 'title', 'description_fallback', 'intro_fallback', 'chart_caption', 'chart_alt', 'image_name', 'forecast_image_name', 'methodology_fallback', 'block_what', 'block_why', 'block_read', 'block_freq', 'block_method', 'block_source', 'block_why_body', 'block_read_body', 'block_freq_body', 'block_source_body', 'freq_daily', 'freq_weekly', 'freq_monthly', 'freq_quarterly', 'freq_annual', 'section_current', 'section_methodology', 'section_latest', 'section_related', 'section_years', 'year_link', 'li_latest', 'li_date', 'li_frequency', 'li_source', 'li_points', 'li_period', 'th_date', 'th_value', 'th_value_unit', 'th_cpi_change', 'keywords', 'forecast_desc_tail', 'forecast_chart_note', 'forecast_link' | [backend/app/data/i18n/seo_en.py:1496](../backend/app/data/i18n/seo_en.py#L1496) |
| app.data.indicator_seo.CATEGORY_KEYWORDS_RU | Dict | 'Цены', 'Ставки', 'Финансы', 'ВВП', 'Рынок труда', 'Население', 'Торговля', 'Бизнес', 'Наука' | [backend/app/data/indicator_seo.py:16](../backend/app/data/indicator_seo.py#L16) |
| app.data.indicator_seo.FORECAST_SSR_PILOT_CODES | Call | computed source expression | [backend/app/data/indicator_seo.py:33](../backend/app/data/indicator_seo.py#L33) |
| app.data.indicator_seo.INDICATOR_SEO_KEYWORDS | Dict | 'cpi', 'cpi-food', 'cpi-nonfood', 'cpi-services', 'inflation-quarterly', 'inflation-annual', 'cpi-food-annual', 'cpi-nonfood-annual', 'cpi-services-annual', 'inflation-weekly', 'inflation-weekly-food', 'inflation-weekly-nonfood', 'inflation-weekly-services', 'ppi', 'ppi-yoy', 'ppi-mom', 'ppi-annual', 'key-rate', 'usd-rub', 'eur-rub', 'cny-rub', 'ruonia', 'm0', 'm2', 'mortgage-rate', 'auto-loan-rate', 'credit-rate-corp-short', 'credit-rate-corp-1to3y', 'credit-rate-corp-over3y', 'credit-rate-ind-short', 'credit-rate-ind-1to3y', 'credit-rate-ind-over3y', 'deposit-rate-medium', 'deposit-rate-long', 'deposit-rate', 'budget-deficit', 'budget-revenue', 'budget-expenditure', 'consumer-credit', 'deposits-individual', 'external-debt', 'business-credit', 'ipi-mining', 'ipi-manufacturing', 'ipi-energy', 'ipi-water', 'fuel-ai92', 'fuel-ai95', 'fuel-diesel', 'gold-price', 'btc-usd', 'eth-usd', 'sol-usd', 'imoex', 'mcftr', 'rtsi', 'rgbi', 'corp-bond-index', 'usd-index', 'ust-10y', 'eur-usd', 'gbp-usd', 'usd-cny', 'weo-gdp-usd', 'weo-gdp-per-capita-usd', 'weo-budget-balance-gdp', 'weo-government-debt-gdp', 'brent', 'copper', 'silver', 'natural-gas', 'wheat', 'soybean', 'coal', 'steel', 'gdp-nominal', 'gdp-nominal-annual', 'gdp-real', 'gdp-real-annual', 'gdp-yoy', 'gdp-qoq', 'gdp-real-yoy', 'gdp-real-qoq', 'gdp-consumption', 'gdp-government', 'housing-price-primary', 'housing-price-secondary', 'housing-yoy-primary', 'housing-yoy-secondary', 'housing-annual-primary', 'housing-annual-secondary', 'unemployment', 'labor-force', 'employment', 'wages', 'wages-real', 'population', 'births', 'deaths', 'retail-trade', 'construction-work', 'capital-investment', 'ipi', 'depreciation-rate', 'housing-commissioned', 'gdp-investment', 'birth-rate', 'death-rate', 'pensioners', 'pop-over-working-age', 'pop-under-working-age', 'working-age-population', 'population-migration', 'population-natural-growth', 'population-total-growth', 'doctoral-students', 'grad-students', 'innovation-activity', 'rd-organizations', 'rd-personnel', 'small-business-innovation', 'tech-innovation-share', 'wages-nominal', 'current-account', 'exports', 'imports', 'services-exports', 'services-imports', 'trade-balance', 'fdi-net', 'deposits-business', 'international-reserves', 'm1', 'housing-affordability' | [backend/app/data/indicator_seo.py:102](../backend/app/data/indicator_seo.py#L102) |
| app.data.indicator_seo.INDICATOR_SEO | Dict | 'cpi', 'cpi-food', 'cpi-nonfood', 'cpi-services', 'key-rate', 'usd-rub', 'eur-rub', 'cny-rub', 'ruonia', 'm0', 'm2', 'mortgage-rate', 'deposit-rate', 'auto-loan-rate', 'credit-rate-corp-short', 'credit-rate-corp-1to3y', 'credit-rate-corp-over3y', 'credit-rate-ind-short', 'credit-rate-ind-1to3y', 'credit-rate-ind-over3y', 'inflation-quarterly', 'inflation-annual', 'cpi-food-annual', 'cpi-nonfood-annual', 'cpi-services-annual', 'ppi-annual', 'gdp-real-annual', 'gdp-nominal-annual', 'unemployment', 'wages-nominal', 'wages-real', 'housing-affordability', 'gdp-nominal', 'gdp-real', 'gdp-yoy', 'gdp-qoq', 'gdp-real-yoy', 'gdp-real-qoq', 'm1', 'consumer-credit', 'business-credit', 'deposits-individual', 'deposits-business', 'budget-deficit', 'inflation-weekly', 'inflation-weekly-food', 'inflation-weekly-nonfood', 'inflation-weekly-services', 'unemployment-quarterly', 'unemployment-annual', 'housing-price-primary', 'housing-price-secondary', 'housing-yoy-primary', 'housing-yoy-secondary', 'housing-annual-primary', 'housing-annual-secondary', 'ipi', 'ipi-yoy', 'population', 'population-natural-growth', 'population-total-growth', 'population-migration', 'current-account', 'current-account-yoy', 'ppi', 'ppi-yoy', 'ppi-mom', 'exports', 'imports', 'trade-balance', 'exports-yoy', 'imports-yoy', 'international-reserves', 'external-debt', 'gdp-consumption', 'gdp-government', 'gdp-investment', 'labor-force', 'employment', 'wages-yoy', 'budget-revenue', 'budget-expenditure', 'services-exports', 'services-imports', 'fdi-net', 'gold-price', 'btc-usd', 'eth-usd', 'sol-usd', 'imoex', 'mcftr', 'rtsi', 'rgbi', 'corp-bond-index', 'ipi-mining', 'ipi-manufacturing', 'ipi-energy', 'ipi-water', 'fuel-ai92', 'fuel-ai95', 'fuel-diesel', 'brent', 'usd-index', 'ust-10y', 'eur-usd', 'gbp-usd', 'usd-cny', 'weo-gdp-usd', 'weo-gdp-per-capita-usd', 'weo-budget-balance-gdp', 'weo-government-debt-gdp', 'copper', 'silver', 'natural-gas', 'wheat', 'soybean', 'coal', 'steel', 'exports-qoq', 'imports-qoq', 'births', 'deaths', 'birth-rate', 'death-rate', 'working-age-population', 'pensioners', 'retail-trade', 'housing-commissioned', 'depreciation-rate', 'grad-students', 'doctoral-students', 'rd-organizations', 'rd-personnel', 'innovation-activity', 'tech-innovation-share', 'small-business-innovation', 'construction-work', 'capital-investment', 'pop-under-working-age', 'pop-over-working-age' | [backend/app/data/indicator_seo.py:507](../backend/app/data/indicator_seo.py#L507) |
| app.data.indicator_seo.INDICATOR_HIDDEN_FROM_LISTING | Set | sequence/source expression | [backend/app/data/indicator_seo.py:1272](../backend/app/data/indicator_seo.py#L1272) |
| app.data.indicator_seo.INDICATOR_SEO_BLOCKS | Dict | 'cpi', 'cpi-food', 'cpi-nonfood', 'cpi-services', 'mortgage-rate', 'auto-loan-rate', 'credit-rate-corp-short', 'credit-rate-corp-1to3y', 'credit-rate-corp-over3y', 'credit-rate-ind-short', 'credit-rate-ind-1to3y', 'credit-rate-ind-over3y', 'deposit-rate', 'deposit-rate-medium', 'deposit-rate-long', 'gold-price', 'brent', 'usd-index', 'ust-10y', 'btc-usd', 'eth-usd', 'sol-usd', 'imoex', 'mcftr', 'rtsi', 'rgbi', 'corp-bond-index', 'ruonia', 'key-rate', 'inflation', 'gdp-nominal', 'gdp-real', 'unemployment', 'eur-rub', 'cny-rub', 'usd-rub', 'ppi', 'housing-price-primary', 'housing-price-secondary', 'ipi', 'wages-nominal', 'wages-real', 'budget-deficit', 'budget-revenue', 'budget-expenditure', 'business-credit', 'm0', 'm1', 'm2', 'employment', 'labor-force', 'consumer-credit', 'deposits-individual', 'international-reserves', 'gdp-consumption', 'gdp-government', 'external-debt', 'exports', 'population', 'births', 'deaths', 'birth-rate', 'death-rate', 'population-natural-growth', 'population-migration', 'population-total-growth', 'working-age-population', 'pop-under-working-age', 'pop-over-working-age', 'pensioners', 'grad-students', 'doctoral-students', 'rd-organizations', 'rd-personnel', 'innovation-activity', 'tech-innovation-share', 'small-business-innovation', 'imports', 'trade-balance', 'current-account', 'services-exports', 'services-imports', 'capital-investment', 'gdp-investment', 'fdi-net', 'retail-trade', 'construction-work', 'housing-commissioned', 'depreciation-rate', 'deposits-business', 'housing-affordability', 'housing-affordability-primary' | [backend/app/data/indicator_seo.py:1751](../backend/app/data/indicator_seo.py#L1751) |
| app.data.indicator_seo._COMMODITY_BLOCK_SPECS | Dict | 'copper', 'silver', 'natural-gas', 'wheat', 'soybean', 'coal' | [backend/app/data/indicator_seo.py:8513](../backend/app/data/indicator_seo.py#L8513) |
| app.data.indicator_seo._IPI_COMPONENT_BLOCK_SPECS | Dict | 'ipi-mining', 'ipi-manufacturing', 'ipi-energy', 'ipi-water' | [backend/app/data/indicator_seo.py:8713](../backend/app/data/indicator_seo.py#L8713) |
| app.data.indicator_seo._FUEL_BLOCK_SPECS | Dict | 'fuel-ai92', 'fuel-ai95', 'fuel-diesel' | [backend/app/data/indicator_seo.py:8820](../backend/app/data/indicator_seo.py#L8820) |
| app.data.indicator_seo._WEO_BLOCK_SPECS | Dict | 'weo-gdp-usd', 'weo-gdp-per-capita-usd', 'weo-budget-balance-gdp', 'weo-government-debt-gdp' | [backend/app/data/indicator_seo.py:8894](../backend/app/data/indicator_seo.py#L8894) |
| app.data.legacy_redirects.LEGACY_INDICATOR_REDIRECTS | Dict | 'inflation', 'gasoline-ai92', 'gasoline-ai95', 'gdp-deflator', 'refinancing-rate', 'steel' | [backend/app/data/legacy_redirects.py:37](../backend/app/data/legacy_redirects.py#L37) |
| app.data.legacy_redirects._BESPOKE_UNLISTED_CANONICAL | Dict | 'unemployment-quarterly', 'unemployment-annual', 'trade-balance-yoy-abs', 'current-account-yoy-abs', 'inflation-weekly', 'inflation-annual', 'inflation-quarterly', 'inflation-weekly-food', 'inflation-weekly-nonfood', 'inflation-weekly-services', 'housing-yoy-primary', 'housing-yoy-secondary', 'housing-qoq-primary', 'housing-qoq-secondary', 'housing-annual-primary', 'housing-annual-secondary', 'ppi-yoy', 'ppi-qoq', 'ppi-mom', 'ppi-annual', 'cpi-period-weekly', 'cpi-food-period-weekly', 'cpi-nonfood-period-weekly', 'cpi-services-period-weekly' | [backend/app/data/legacy_redirects.py:50](../backend/app/data/legacy_redirects.py#L50) |
| app.data.legacy_redirects._SIBLING_SUFFIXES | Tuple | sequence/source expression | [backend/app/data/legacy_redirects.py:84](../backend/app/data/legacy_redirects.py#L84) |
| app.data.legacy_redirects.LEGACY_REGION_SLUG_PREFIXES | Tuple | sequence/source expression | [backend/app/data/legacy_redirects.py:91](../backend/app/data/legacy_redirects.py#L91) |
| app.data.legacy_redirects._WORLD_FREQ_SUFFIX_RE | Call | computed source expression | [backend/app/data/legacy_redirects.py:93](../backend/app/data/legacy_redirects.py#L93) |
| app.data.legacy_redirects._WORLD_FREQ_RANK | Dict | 'monthly', 'quarterly', 'annual', 'weekly', 'daily' | [backend/app/data/legacy_redirects.py:101](../backend/app/data/legacy_redirects.py#L101) |
| app.data.legacy_redirects._MERGE_MODE_TYPE_BY_UNIT | Dict | 'RCH_A', 'PCH_SM', 'PCH_SAME', 'RCH_MV12MAVR', 'RCH_A_AVG', 'RCH_M', 'RT1', 'RT1_SCA', 'PCH_PRE', 'RT_M_DIF' | [backend/app/data/legacy_redirects.py:425](../backend/app/data/legacy_redirects.py#L425) |
| app.data.region_indicator_polarity.LOWER_BETTER_CODES | Call | computed source expression | [backend/app/data/region_indicator_polarity.py:24](../backend/app/data/region_indicator_polarity.py#L24) |
| app.data.region_indicator_polarity.LOWER_BETTER_TABLE_CODES | Call | computed source expression | [backend/app/data/region_indicator_polarity.py:78](../backend/app/data/region_indicator_polarity.py#L78) |
| app.data.view_model_families.GRAN_ORDER | Tuple | sequence/source expression | [backend/app/data/view_model_families.py:44](../backend/app/data/view_model_families.py#L44) |
| app.data.view_model_families.GRAN_LABEL | Dict | 'day', 'week', 'month', 'quarter', 'year' | [backend/app/data/view_model_families.py:46](../backend/app/data/view_model_families.py#L46) |
| app.data.view_model_families.GRAN_FREQUENCY | Dict | 'day', 'week', 'month', 'quarter', 'year' | [backend/app/data/view_model_families.py:55](../backend/app/data/view_model_families.py#L55) |
| app.data.view_model_families.NATIVE_GRAN | Dict | 'daily', 'weekly', 'monthly', 'quarterly', 'annual' | [backend/app/data/view_model_families.py:64](../backend/app/data/view_model_families.py#L64) |
| app.data.view_model_families._SUFFIX_NAME | Dict | 'eop-week', 'eop-month', 'eop-quarter', 'eop-year', 'avg-week', 'avg-month', 'avg-quarter', 'avg-year', 'sum-month', 'sum-quarter', 'sum-year', 'mom', 'qoq', 'yoy', 'yoy-quarter', 'yoy-year', 'index', 'rolling-12m' | [backend/app/data/view_model_families.py:126](../backend/app/data/view_model_families.py#L126) |
| app.data.view_model_families._SUFFIX_NAME_EN | Dict | 'eop-week', 'eop-month', 'eop-quarter', 'eop-year', 'avg-week', 'avg-month', 'avg-quarter', 'avg-year', 'sum-month', 'sum-quarter', 'sum-year', 'mom', 'qoq', 'yoy', 'yoy-quarter', 'yoy-year', 'index', 'rolling-12m' | [backend/app/data/view_model_families.py:150](../backend/app/data/view_model_families.py#L150) |
| app.data.view_model_families._G_EOP | Call | computed source expression | [backend/app/data/view_model_families.py:382](../backend/app/data/view_model_families.py#L382) |
| app.data.view_model_families._G_AVG | Call | computed source expression | [backend/app/data/view_model_families.py:383](../backend/app/data/view_model_families.py#L383) |
| app.data.view_model_families._G_POP | Call | computed source expression | [backend/app/data/view_model_families.py:384](../backend/app/data/view_model_families.py#L384) |
| app.data.view_model_families._G_YOY | Call | computed source expression | [backend/app/data/view_model_families.py:385](../backend/app/data/view_model_families.py#L385) |
| app.data.view_model_families._G_YOY_MULTI | Call | computed source expression | [backend/app/data/view_model_families.py:389](../backend/app/data/view_model_families.py#L389) |
| app.data.view_model_families._G_FLOW | Call | computed source expression | [backend/app/data/view_model_families.py:390](../backend/app/data/view_model_families.py#L390) |
| app.data.view_model_families._G_GDP_LEVEL | Call | computed source expression | [backend/app/data/view_model_families.py:391](../backend/app/data/view_model_families.py#L391) |
| app.data.view_model_families._G_POP_LEVEL | Call | computed source expression | [backend/app/data/view_model_families.py:392](../backend/app/data/view_model_families.py#L392) |
| app.data.view_model_families._G_INDEX | Call | computed source expression | [backend/app/data/view_model_families.py:393](../backend/app/data/view_model_families.py#L393) |
| app.data.view_model_families._BUILDERS | Dict | 'T1', 'T2', 'T2y', 'T3', 'T4', 'T5', 'T6', 'T7', 'T8', 'T9', 'T9s', 'T10', 'T10a', 'T12' | [backend/app/data/view_model_families.py:664](../backend/app/data/view_model_families.py#L664) |
| app.data.view_model_families._FAMILY_DEFS | List | sequence/source expression | [backend/app/data/view_model_families.py:711](../backend/app/data/view_model_families.py#L711) |
| app.data.view_model_families.FAMILIES | Call | computed source expression | [backend/app/data/view_model_families.py:971](../backend/app/data/view_model_families.py#L971) |
| app.data.view_model_families.FAMILY_BY_BASE | DictComp | computed source expression | [backend/app/data/view_model_families.py:972](../backend/app/data/view_model_families.py#L972) |
| app.data.view_model_families._FORECAST_PROPAGATE_FREQ | Call | computed source expression | [backend/app/data/view_model_families.py:998](../backend/app/data/view_model_families.py#L998) |
| app.data.view_model_families._BUCKET_MIN_PERIODS | Dict | ('monthly', 'quarter'), ('monthly', 'year'), ('quarterly', 'year') | [backend/app/data/view_model_families.py:1002](../backend/app/data/view_model_families.py#L1002) |
| app.data.wages_historical.ANNUAL_NOMINAL_WAGES_RUB | Dict | 1991, 1992, 1993, 1994, 1995, 1996, 1997, 1998, 1999, 2000, 2001, 2002, 2003, 2004, 2005, 2006, 2007, 2008, 2009, 2010, 2011, 2012, 2013, 2014 | [backend/app/data/wages_historical.py:46](../backend/app/data/wages_historical.py#L46) |
| app.data.wages_historical.MONTHLY_GAP_FILL | Dict | 'wages-nominal' | [backend/app/data/wages_historical.py:92](../backend/app/data/wages_historical.py#L92) |
| app.data.wages_historical.SPEC | Call | computed source expression | [backend/app/data/wages_historical.py:106](../backend/app/data/wages_historical.py#L106) |
| app.data.world_aggregation._VALID_POLICIES | Call | computed source expression | [backend/app/data/world_aggregation.py:23](../backend/app/data/world_aggregation.py#L23) |
| app.data.world_aggregation._CURATED_POLICIES | Dict | ('prc_hicp_midx', 'I15'), ('prc_fpmt_m', 'I25'), ('prc_hicp_cind', 'I15'), ('prc_hicp_ct', 'I15'), ('prc_hicp_fp', 'I15'), ('prc_hicp_fpd', 'I15'), ('prc_hicp_minr', 'I15'), ('prc_ipc_g20', 'I15'), ('ei_isbu_m', 'I2015'), ('ei_isrt_m', 'I15'), ('ei_issp_m', 'I21'), ('ei_mfef_m', 'I15'), ('ert_eff_ic_m', 'I15'), ('ei_bsee_m_r2', 'INX'), ('ei_bslh_m_r2', 'INX'), ('ei_bsbu_m_r2', ''), ('ei_bssi_m_r2', ''), ('ei_bsco_m', 'BAL'), ('ei_bsin_m_r2', 'BAL'), ('ei_bsrt_m_r2', 'BAL'), ('ei_bsse_m_r2', 'BAL'), ('sts_cobp_m', 'I15'), ('sts_colb_m', 'I15'), ('sts_copi_m', 'I15'), ('sts_copr_m', 'I15'), ('sts_inlb_m', 'I15'), ('sts_inpi_m', 'I15'), ('sts_inpp_m', 'I15'), ('sts_inppd_m', 'I15'), ('sts_inppnd_m', 'I15'), ('sts_inpr_m', 'I15'), ('sts_intv_m', 'I15'), ('sts_intvd_m', 'I15'), ('sts_intvnd_m', 'I15'), ('sts_rb_m', 'I15'), ('sts_selb_m', 'I15'), ('sts_trlb_m', 'I15'), ('sts_trtu_m', 'I15'), ('ei_mfir_m', ''), ('irt_lt_mcby_m', ''), ('irt_st_m', ''), ('une_rt_m', 'PC_ACT'), ('une_rt_m', 'THS_PER'), ('ei_lmhr_m', 'PC_ACT'), ('ei_lmhu_m', 'THS_PER'), ('tour_occ_mnor', 'PC'), ('ei_etea_m', 'MIO_EUR_SA'), ('ei_eteu27_2020_m', 'MIO_EUR_SA'), ('nrg_cb_cosm', ''), ('nrg_cb_eim', 'GWH'), ('nrg_cb_em', 'GWH'), ('nrg_cb_gasm', 'MIO_M3'), ('nrg_cb_oilm', 'THS_T'), ('nrg_cb_sffm', 'THS_T'), ('nrg_chdd_m', 'NR'), ('nrg_chddr2_m', 'NR'), ('nrg_te_gasm', 'MIO_M3'), ('nrg_te_oilm', 'THS_T'), ('nrg_ti_gasm', 'MIO_M3'), ('nrg_ti_oilm', 'THS_T'), ('nrg_stk_gasm', 'MIO_M3'), ('nrg_stk_oem', 'NR'), ('nrg_stk_oilm', 'THS_T'), ('nrg_stk_oom', 'THS_T') | [backend/app/data/world_aggregation.py:26](../backend/app/data/world_aggregation.py#L26) |
| app.data.world_aggregation._QUARTERLY_MEAN_BY_UNIT | Dict | '', 'BAL', 'I15', 'I15_Q', 'I21', 'I2021', 'I2015', 'I25_NSA', 'PC_ACT', 'PC_POP', 'PC', 'HR', 'THS', 'THS_PER' | [backend/app/data/world_aggregation.py:101](../backend/app/data/world_aggregation.py#L101) |
| app.data.world_aggregation._QUARTERLY_SUM_BY_UNIT | Dict | 'CLV15_MEUR', 'EUR', 'NR', 'THS_T' | [backend/app/data/world_aggregation.py:166](../backend/app/data/world_aggregation.py#L166) |
| app.data.world_aggregation._FLOW_DATASET_PREFIXES | Tuple | sequence/source expression | [backend/app/data/world_aggregation.py:191](../backend/app/data/world_aggregation.py#L191) |
| app.data.world_aggregation._VOLUME_UNITS | Call | computed source expression | [backend/app/data/world_aggregation.py:206](../backend/app/data/world_aggregation.py#L206) |
| app.data.world_aggregation._DIRECT_AGGREGATION | Call | computed source expression | [backend/app/data/world_aggregation.py:323](../backend/app/data/world_aggregation.py#L323) |
| app.data.world_aggregation._VIA_MONTHLY | Call | computed source expression | [backend/app/data/world_aggregation.py:330](../backend/app/data/world_aggregation.py#L330) |
| app.data.world_concept_national.NATIONAL_CONCEPT_INDICATOR_CODES | Dict | 'unemployment-rate', 'population', 'activity-rate', 'long-term-interest-rate', 'hicp-index' | [backend/app/data/world_concept_national.py:14](../backend/app/data/world_concept_national.py#L14) |
| app.data.world_concept_national.HICP_NATIONAL_YOY_KIND | Dict | 'cn-cpi-all', 'br-cpi-ipca-yoy' | [backend/app/data/world_concept_national.py:72](../backend/app/data/world_concept_national.py#L72) |
| app.data.world_concept_national._CONCEPT_BY_NATIONAL_CODE | DictComp | computed source expression | [backend/app/data/world_concept_national.py:88](../backend/app/data/world_concept_national.py#L88) |
| app.data.world_concept_russia.RUSSIA_CONCEPT_LINKS | Dict | 'unemployment-rate', 'hicp-index', 'population', 'gdp-usd', 'gdp-per-capita-usd', 'budget-balance-gdp', 'government-debt-gdp' | [backend/app/data/world_concept_russia.py:37](../backend/app/data/world_concept_russia.py#L37) |
| app.data.world_concept_russia.RUSSIA_COUNTRY_PAYLOAD | Dict | 'code', 'slug', 'name', 'name_en', 'name_ru', 'region', 'region_ru', 'indicators_count', 'is_active' | [backend/app/data/world_concept_russia.py:193](../backend/app/data/world_concept_russia.py#L193) |
| app.data.world_concept_russia._RUSSIA_CARD_ALIASES | Dict | 'cpi' | [backend/app/data/world_concept_russia.py:232](../backend/app/data/world_concept_russia.py#L232) |
| app.data.world_concept_russia._RUSSIA_CODE_TO_CONCEPT | Dict | **unpack, **unpack | [backend/app/data/world_concept_russia.py:236](../backend/app/data/world_concept_russia.py#L236) |
| app.data.world_concepts._RATING_SURFACES | Call | computed source expression | [backend/app/data/world_concepts.py:40](../backend/app/data/world_concepts.py#L40) |
| app.data.world_concepts.WORLD_CONCEPTS | Tuple | sequence/source expression | [backend/app/data/world_concepts.py:42](../backend/app/data/world_concepts.py#L42) |
| app.data.world_concepts.CONCEPT_BY_SLUG | DictComp | computed source expression | [backend/app/data/world_concepts.py:264](../backend/app/data/world_concepts.py#L264) |
| app.data.world_concepts._NON_SEMANTIC_SLICE_KEYS | Call | computed source expression | [backend/app/data/world_concepts.py:265](../backend/app/data/world_concepts.py#L265) |
| app.data.world_concepts._COICOP_DIMS | Call | computed source expression | [backend/app/data/world_concepts.py:266](../backend/app/data/world_concepts.py#L266) |
| app.data.world_concepts._ALL_ITEMS_COICOP | Call | computed source expression | [backend/app/data/world_concepts.py:267](../backend/app/data/world_concepts.py#L267) |
| app.data.world_country_area.WORLD_COUNTRY_AREA | Dict | 'AL', 'AT', 'BE', 'BG', 'CH', 'CY', 'CZ', 'DE', 'DK', 'EE', 'EL', 'ES', 'FI', 'FR', 'HR', 'HU', 'IE', 'IS', 'IT', 'LT', 'LU', 'LV', 'ME', 'MK', 'MT', 'NL', 'NO', 'PL', 'PT', 'RO', 'SE', 'SI', 'SK', 'TR', 'UK', 'RS', 'BA', 'MD', 'GE', 'US', 'CA', 'JP', 'CN', 'IN', 'BR', 'MX', 'AU' | [backend/app/data/world_country_area.py:28](../backend/app/data/world_country_area.py#L28) |
| app.data.world_country_population.WORLD_COUNTRY_POPULATION | Dict | 'US', 'JP', 'CN', 'IN', 'BR', 'MX', 'AU' | [backend/app/data/world_country_population.py:29](../backend/app/data/world_country_population.py#L29) |
| app.data.world_forecast_policy._FREQ_STRATEGIES | Dict | 'monthly', 'quarterly', 'annual' | [backend/app/data/world_forecast_policy.py:48](../backend/app/data/world_forecast_policy.py#L48) |
| app.data.world_forecast_policy._FREQ_MIN_POINTS | Dict | 'monthly', 'quarterly', 'annual' | [backend/app/data/world_forecast_policy.py:53](../backend/app/data/world_forecast_policy.py#L53) |
| app.data.world_forecast_policy.WORLD_FORECAST_HORIZONS | Dict | 'monthly', 'quarterly', 'annual' | [backend/app/data/world_forecast_policy.py:54](../backend/app/data/world_forecast_policy.py#L54) |
| app.data.world_forecast_policy._FREQ_SEASONS | Dict | 'monthly', 'quarterly', 'annual' | [backend/app/data/world_forecast_policy.py:55](../backend/app/data/world_forecast_policy.py#L55) |
| app.data.world_forecast_policy._FREQ_MAX_AGE_DAYS | Dict | 'monthly', 'quarterly', 'annual' | [backend/app/data/world_forecast_policy.py:56](../backend/app/data/world_forecast_policy.py#L56) |
| app.data.world_forecast_policy._OFFICIAL_PROVIDERS | Tuple | sequence/source expression | [backend/app/data/world_forecast_policy.py:72](../backend/app/data/world_forecast_policy.py#L72) |
| app.data.world_forecast_policy.OFFICIAL_PROVIDER_POLICIES | DictComp | computed source expression | [backend/app/data/world_forecast_policy.py:96](../backend/app/data/world_forecast_policy.py#L96) |
| app.data.world_indicator_titles_ru.TITLE_BY_CODE | Dict | 'br-cpi-ipca', 'br-cpi-ipca-yoy', 'br-gdp-ibc-br', 'cn-shibor-1w', 'cn-shibor-on', 'cn-lpr-1y', 'cn-lpr-5y', 'mx-tiie-28', 'mx-fx-usd-mxn', 'ca-m2-plus', 'jp-m2', 'jp-m3' | [backend/app/data/world_indicator_titles_ru.py:17](../backend/app/data/world_indicator_titles_ru.py#L17) |
| app.data.world_indicator_titles_ru._LATIN_CLEANUPS | List | sequence/source expression | [backend/app/data/world_indicator_titles_ru.py:33](../backend/app/data/world_indicator_titles_ru.py#L33) |
| app.database._PUBLIC_SERVER_SETTINGS | Dict | 'statement_timeout', 'idle_in_transaction_session_timeout' | [backend/app/database.py:25](../backend/app/database.py#L25) |
| app.database._ANALYTICS_SERVER_SETTINGS | Dict | 'statement_timeout', 'idle_in_transaction_session_timeout' | [backend/app/database.py:48](../backend/app/database.py#L48) |
| app.main._TRUSTED_PROXY_NETS | Call | computed source expression | [backend/app/main.py:44](../backend/app/main.py#L44) |
| app.main._GEO_EXCLUDED_PREFIXES | Tuple | sequence/source expression | [backend/app/main.py:1286](../backend/app/main.py#L1286) |
| app.main._GEO_EXCLUDED_EXACT | Call | computed source expression | [backend/app/main.py:1289](../backend/app/main.py#L1289) |
| app.services.action_policy.DENIED_ACTIONS | Set | sequence/source expression | [backend/app/services/action_policy.py:22](../backend/app/services/action_policy.py#L22) |
| app.services.action_policy.HIGH_RISK_ACTIONS | Set | sequence/source expression | [backend/app/services/action_policy.py:33](../backend/app/services/action_policy.py#L33) |
| app.services.action_policy.LOW_RISK_WRITE_ACTIONS | Set | sequence/source expression | [backend/app/services/action_policy.py:42](../backend/app/services/action_policy.py#L42) |
| app.services.admin_bi._GOAL_EVENTS | Set | sequence/source expression | [backend/app/services/admin_bi.py:58](../backend/app/services/admin_bi.py#L58) |
| app.services.admin_bi._DOWNLOAD_EVENTS | Set | sequence/source expression | [backend/app/services/admin_bi.py:63](../backend/app/services/admin_bi.py#L63) |
| app.services.admin_bi._ERROR_EVENTS | Set | sequence/source expression | [backend/app/services/admin_bi.py:67](../backend/app/services/admin_bi.py#L67) |
| app.services.admin_bi._METRIKA_JSON_KEYS | Tuple | sequence/source expression | [backend/app/services/admin_bi.py:92](../backend/app/services/admin_bi.py#L92) |
| app.services.alerting._DEGRADED_LABELS | Dict | 'parsed_zero', 'fallback_used' | [backend/app/services/alerting.py:272](../backend/app/services/alerting.py#L272) |
| app.services.analytics_alerts.COLLECTION_SILENCE_AFTER | Call | computed source expression | [backend/app/services/analytics_alerts.py:34](../backend/app/services/analytics_alerts.py#L34) |
| app.services.analytics_alerts._COLLECTION_PROBE_WINDOW | Call | computed source expression | [backend/app/services/analytics_alerts.py:35](../backend/app/services/analytics_alerts.py#L35) |
| app.services.analytics_alerts._THIRD_PARTY_HOST_SUFFIXES | Tuple | sequence/source expression | [backend/app/services/analytics_alerts.py:42](../backend/app/services/analytics_alerts.py#L42) |
| app.services.analytics_alerts._JS_URL_RE | Call | computed source expression | [backend/app/services/analytics_alerts.py:45](../backend/app/services/analytics_alerts.py#L45) |
| app.services.analytics_marts.METRIKA_DEVICE | Dict | '1', '2', '3', '4' | [backend/app/services/analytics_marts.py:57](../backend/app/services/analytics_marts.py#L57) |
| app.services.analytics_marts.METRIKA_BROWSER | Dict | 'yandex_browser', 'yandexsearch', 'yandexbrowsercorp', 'chrome', 'chromemobile', 'safari', 'safari_mobile', 'mobile_safari', 'firefox', 'firefox_mobile', 'edge', 'edgin', 'opera', 'opera_mobile', 'samsung_internet', 'android_browser', 'mi_browser', 'huawei_browser' | [backend/app/services/analytics_marts.py:61](../backend/app/services/analytics_marts.py#L61) |
| app.services.analytics_marts.METRIKA_OS | Dict | 'windows', 'android', 'ios', 'ios_double', 'mac_os', 'macos', 'gnu_linux', 'linux' | [backend/app/services/analytics_marts.py:81](../backend/app/services/analytics_marts.py#L81) |
| app.services.analytics_marts.SECTION_RULES | List | sequence/source expression | [backend/app/services/analytics_marts.py:93](../backend/app/services/analytics_marts.py#L93) |
| app.services.analytics_period.MSK | Call | computed source expression | [backend/app/services/analytics_period.py:20](../backend/app/services/analytics_period.py#L20) |
| app.services.analytics_period.MSK_OFFSET | Call | computed source expression | [backend/app/services/analytics_period.py:21](../backend/app/services/analytics_period.py#L21) |
| app.services.analytics_period.PRESETS | Tuple | sequence/source expression | [backend/app/services/analytics_period.py:23](../backend/app/services/analytics_period.py#L23) |
| app.services.analytics_period._PRESET_LABELS | Dict | 'today', 'yesterday', '7d', '30d', '90d' | [backend/app/services/analytics_period.py:25](../backend/app/services/analytics_period.py#L25) |
| app.services.analytics_report_bundle._DOWNLOAD_EVENTS | Set | sequence/source expression | [backend/app/services/analytics_report_bundle.py:33](../backend/app/services/analytics_report_bundle.py#L33) |
| app.services.analytics_report_bundle._ERROR_EVENTS | Set | sequence/source expression | [backend/app/services/analytics_report_bundle.py:37](../backend/app/services/analytics_report_bundle.py#L37) |
| app.services.attribution_query.ATTR_QUERY_KEYS | Tuple | sequence/source expression | [backend/app/services/attribution_query.py:19](../backend/app/services/attribution_query.py#L19) |
| app.services.attribution_query.AI_UTM_REFERRER | Dict | 'chatgpt.com', 'openai', 'chat.openai.com', 'perplexity', 'perplexity.ai' | [backend/app/services/attribution_query.py:40](../backend/app/services/attribution_query.py#L40) |
| app.services.base_parser.DEGRADED_STATUSES | Tuple | sequence/source expression | [backend/app/services/base_parser.py:85](../backend/app/services/base_parser.py#L85) |
| app.services.binance_btcusdt_parser._HOSTS | List | sequence/source expression | [backend/app/services/binance_btcusdt_parser.py:52](../backend/app/services/binance_btcusdt_parser.py#L52) |
| app.services.bot_score._BOT_UA_RE | Call | computed source expression | [backend/app/services/bot_score.py:29](../backend/app/services/bot_score.py#L29) |
| app.services.bot_score.HEURISTICS | Tuple | sequence/source expression | [backend/app/services/bot_score.py:103](../backend/app/services/bot_score.py#L103) |
| app.services.brent_fred_parser._DEFAULT_BACKFILL_FROM | Call | computed source expression | [backend/app/services/brent_fred_parser.py:40](../backend/app/services/brent_fred_parser.py#L40) |
| app.services.calculation_engine.DERIVED_SPECS | List | sequence/source expression | [backend/app/services/calculation_engine.py:66](../backend/app/services/calculation_engine.py#L66) |
| app.services.calendar_seed.CBR_MEETINGS_2026 | List | sequence/source expression | [backend/app/services/calendar_seed.py:51](../backend/app/services/calendar_seed.py#L51) |
| app.services.calendar_seed.CBR_MEETINGS_2027_TENTATIVE | List | sequence/source expression | [backend/app/services/calendar_seed.py:65](../backend/app/services/calendar_seed.py#L65) |
| app.services.calendar_seed.ROSSTAT_MONTHLY_RELEASES | Dict | 'cpi', 'ipi', 'unemployment', 'wages-nominal', 'retail-trade', 'housing-commissioned', 'ppi', 'construction-work' | [backend/app/services/calendar_seed.py:75](../backend/app/services/calendar_seed.py#L75) |
| app.services.calendar_seed.ROSSTAT_QUARTERLY_RELEASES | Dict | 'gdp-nominal', 'gdp-real' | [backend/app/services/calendar_seed.py:127](../backend/app/services/calendar_seed.py#L127) |
| app.services.calendar_seed.CBR_STAT_MONTHLY | Dict | 'm2', 'international-reserves', 'external-debt', 'current-account' | [backend/app/services/calendar_seed.py:146](../backend/app/services/calendar_seed.py#L146) |
| app.services.calendar_seed.MINFIN_MONTHLY | Dict | 'budget-revenue', 'budget-expenditure' | [backend/app/services/calendar_seed.py:177](../backend/app/services/calendar_seed.py#L177) |
| app.services.calendar_seed.WEEKLY_SPECS | List | sequence/source expression | [backend/app/services/calendar_seed.py:210](../backend/app/services/calendar_seed.py#L210) |
| app.services.calendar_seed.MONTH_NAMES_RU | List | sequence/source expression | [backend/app/services/calendar_seed.py:256](../backend/app/services/calendar_seed.py#L256) |
| app.services.calendar_seed.MONTH_NAMES_EN | List | sequence/source expression | [backend/app/services/calendar_seed.py:261](../backend/app/services/calendar_seed.py#L261) |
| app.services.calendar_sources.common.OFFICIAL_CONFIDENCES | Tuple | sequence/source expression | [backend/app/services/calendar_sources/common.py:15](../backend/app/services/calendar_sources/common.py#L15) |
| app.services.calendar_sources.enrichment.MONTH_NAMES_RU | List | sequence/source expression | [backend/app/services/calendar_sources/enrichment.py:21](../backend/app/services/calendar_sources/enrichment.py#L21) |
| app.services.calendar_sources.enrichment._MONTH_REF_RE | Call | computed source expression | [backend/app/services/calendar_sources/enrichment.py:26](../backend/app/services/calendar_sources/enrichment.py#L26) |
| app.services.calendar_sources.enrichment._QUARTER_REF_RE | Call | computed source expression | [backend/app/services/calendar_sources/enrichment.py:31](../backend/app/services/calendar_sources/enrichment.py#L31) |
| app.services.calendar_sources.enrichment._QUARTER_STORE_MONTH | Dict | 1, 2, 3, 4 | [backend/app/services/calendar_sources/enrichment.py:34](../backend/app/services/calendar_sources/enrichment.py#L34) |
| app.services.calendar_sources.official_calendar.MONTH_NAMES_RU | List | sequence/source expression | [backend/app/services/calendar_sources/official_calendar.py:39](../backend/app/services/calendar_sources/official_calendar.py#L39) |
| app.services.calendar_sources.official_calendar.INDICATOR_CALENDAR_CONTEXT | Dict | 'cpi', 'cpi-food', 'cpi-nonfood', 'cpi-services', 'ipi', 'unemployment', 'wages-nominal', 'retail-trade', 'housing-commissioned', 'ppi', 'construction-work', 'gdp-nominal', 'gdp-real', 'budget-revenue', 'budget-expenditure', 'budget-deficit', 'usd-rub', 'eur-rub', 'cny-rub', 'gold-price', 'ruonia', 'key-rate', 'international-reserves', 'm2', 'm1', 'm0', 'business-credit', 'consumer-credit', 'deposits-business', 'deposits-individual', 'deposit-rate', 'credit-rate-corp-short', 'credit-rate-corp-1to3y', 'credit-rate-corp-over3y', 'credit-rate-ind-short', 'credit-rate-ind-1to3y', 'credit-rate-ind-over3y', 'mortgage-rate', 'auto-loan-rate', 'exports', 'imports', 'trade-balance', 'services-exports', 'services-imports', 'current-account', 'external-debt', 'fdi-net' | [backend/app/services/calendar_sources/official_calendar.py:48](../backend/app/services/calendar_sources/official_calendar.py#L48) |
| app.services.calendar_sources.official_calendar.ROSSTAT_MONTHLY_RULES | List | sequence/source expression | [backend/app/services/calendar_sources/official_calendar.py:112](../backend/app/services/calendar_sources/official_calendar.py#L112) |
| app.services.calendar_sources.official_calendar.ROSSTAT_GDP_RULES | List | sequence/source expression | [backend/app/services/calendar_sources/official_calendar.py:214](../backend/app/services/calendar_sources/official_calendar.py#L214) |
| app.services.calendar_sources.official_calendar.MINFIN_RULES | List | sequence/source expression | [backend/app/services/calendar_sources/official_calendar.py:231](../backend/app/services/calendar_sources/official_calendar.py#L231) |
| app.services.calendar_sources.official_calendar.CBR_KEY_RATE_MEETINGS_2026 | List | sequence/source expression | [backend/app/services/calendar_sources/official_calendar.py:252](../backend/app/services/calendar_sources/official_calendar.py#L252) |
| app.services.calendar_sources.official_calendar.CBR_DAILY_RULES | List | sequence/source expression | [backend/app/services/calendar_sources/official_calendar.py:263](../backend/app/services/calendar_sources/official_calendar.py#L263) |
| app.services.calendar_sources.official_calendar.CBR_EVENT_RULES | List | sequence/source expression | [backend/app/services/calendar_sources/official_calendar.py:311](../backend/app/services/calendar_sources/official_calendar.py#L311) |
| app.services.calendar_sources.rosstat_plan._SCHEDULE_CARD_RE | Call | computed source expression | [backend/app/services/calendar_sources/rosstat_plan.py:44](../backend/app/services/calendar_sources/rosstat_plan.py#L44) |
| app.services.calendar_sources.rosstat_plan._SCHEDULE_DOC_HREF_RE | Call | computed source expression | [backend/app/services/calendar_sources/rosstat_plan.py:45](../backend/app/services/calendar_sources/rosstat_plan.py#L45) |
| app.services.calendar_sources.rosstat_plan._MONTH_HEADER_RE | Call | computed source expression | [backend/app/services/calendar_sources/rosstat_plan.py:49](../backend/app/services/calendar_sources/rosstat_plan.py#L49) |
| app.services.calendar_sources.rosstat_plan._MONTH_NUM | Dict | 'ЯНВАРЬ', 'ФЕВРАЛЬ', 'МАРТ', 'АПРЕЛЬ', 'МАЙ', 'ИЮНЬ', 'ИЮЛЬ', 'АВГУСТ', 'СЕНТЯБРЬ', 'ОКТЯБРЬ', 'НОЯБРЬ', 'ДЕКАБРЬ' | [backend/app/services/calendar_sources/rosstat_plan.py:52](../backend/app/services/calendar_sources/rosstat_plan.py#L52) |
| app.services.calendar_sources.rosstat_plan._MONTH_DATIVE_NUM | Dict | 'января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря' | [backend/app/services/calendar_sources/rosstat_plan.py:56](../backend/app/services/calendar_sources/rosstat_plan.py#L56) |
| app.services.calendar_sources.rosstat_plan._DATE_IN_ROW_RE | Call | computed source expression | [backend/app/services/calendar_sources/rosstat_plan.py:60](../backend/app/services/calendar_sources/rosstat_plan.py#L60) |
| app.services.calendar_sources.rosstat_plan._QUARTER_REF_RE | Call | computed source expression | [backend/app/services/calendar_sources/rosstat_plan.py:65](../backend/app/services/calendar_sources/rosstat_plan.py#L65) |
| app.services.calendar_sources.rosstat_plan._MONTH_RANGE_REF_RE | Call | computed source expression | [backend/app/services/calendar_sources/rosstat_plan.py:68](../backend/app/services/calendar_sources/rosstat_plan.py#L68) |
| app.services.calendar_sources.rosstat_plan._MONTH_REF_RE | Call | computed source expression | [backend/app/services/calendar_sources/rosstat_plan.py:75](../backend/app/services/calendar_sources/rosstat_plan.py#L75) |
| app.services.calendar_sources.rosstat_plan._MONTH_NAMES_RU | List | sequence/source expression | [backend/app/services/calendar_sources/rosstat_plan.py:79](../backend/app/services/calendar_sources/rosstat_plan.py#L79) |
| app.services.calendar_sources.rosstat_plan._MONTH_STEMS | List | sequence/source expression | [backend/app/services/calendar_sources/rosstat_plan.py:83](../backend/app/services/calendar_sources/rosstat_plan.py#L83) |
| app.services.calendar_sources.rosstat_plan._TOPIC_RULES | Tuple | sequence/source expression | [backend/app/services/calendar_sources/rosstat_plan.py:107](../backend/app/services/calendar_sources/rosstat_plan.py#L107) |
| app.services.calendar_sources.working_calendar.WORKING_CALENDAR_SOURCES | Dict | 2026 | [backend/app/services/calendar_sources/working_calendar.py:6](../backend/app/services/calendar_sources/working_calendar.py#L6) |
| app.services.calendar_sources.working_calendar.NON_WORKING_DAYS | Dict | 2026 | [backend/app/services/calendar_sources/working_calendar.py:11](../backend/app/services/calendar_sources/working_calendar.py#L11) |
| app.services.cbr_bop_parser._Q_RE | Call | computed source expression | [backend/app/services/cbr_bop_parser.py:31](../backend/app/services/cbr_bop_parser.py#L31) |
| app.services.cbr_bop_parser.QUARTER_MONTH | Dict | 1, 2, 3, 4 | [backend/app/services/cbr_bop_parser.py:33](../backend/app/services/cbr_bop_parser.py#L33) |
| app.services.cbr_dataservice_parser.MONTH_MAP | Dict | 'январь', 'февраль', 'март', 'апрель', 'май', 'июнь', 'июль', 'август', 'сентябрь', 'октябрь', 'ноябрь', 'декабрь' | [backend/app/services/cbr_dataservice_parser.py:55](../backend/app/services/cbr_dataservice_parser.py#L55) |
| app.services.cbr_fx_parser.CURRENCY_MAP | Dict | 'usd-rub', 'eur-rub', 'cny-rub' | [backend/app/services/cbr_fx_parser.py:25](../backend/app/services/cbr_fx_parser.py#L25) |
| app.services.cbr_fx_parser.DEFAULT_BACKFILL_FROM | Call | computed source expression | [backend/app/services/cbr_fx_parser.py:31](../backend/app/services/cbr_fx_parser.py#L31) |
| app.services.cbr_gold_parser.DEFAULT_BACKFILL_FROM | Call | computed source expression | [backend/app/services/cbr_gold_parser.py:26](../backend/app/services/cbr_gold_parser.py#L26) |
| app.services.cbr_gold_parser.METAL_CODES | Dict | 'gold', 'silver', 'platinum', 'palladium' | [backend/app/services/cbr_gold_parser.py:29](../backend/app/services/cbr_gold_parser.py#L29) |
| app.services.cbr_keyrate._ROW_RE | Call | computed source expression | [backend/app/services/cbr_keyrate.py:29](../backend/app/services/cbr_keyrate.py#L29) |
| app.services.cbr_keyrate._RU_MONTHS | Dict | 'января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря' | [backend/app/services/cbr_keyrate.py:110](../backend/app/services/cbr_keyrate.py#L110) |
| app.services.cbr_keyrate._RATE_FROM_HEADLINE | Call | computed source expression | [backend/app/services/cbr_keyrate.py:120](../backend/app/services/cbr_keyrate.py#L120) |
| app.services.cbr_keyrate._DECISION_DATE_RE | Call | computed source expression | [backend/app/services/cbr_keyrate.py:125](../backend/app/services/cbr_keyrate.py#L125) |
| app.services.cbr_keyrate_parser.DEFAULT_BACKFILL_FROM | Call | computed source expression | [backend/app/services/cbr_keyrate_parser.py:38](../backend/app/services/cbr_keyrate_parser.py#L38) |
| app.services.cbr_monetary_agg_parser.ROW_MAP | Dict | 'M0', 'M1', 'M2', 'M2X', 'deposits-business', 'deposits-individual' | [backend/app/services/cbr_monetary_agg_parser.py:67](../backend/app/services/cbr_monetary_agg_parser.py#L67) |
| app.services.cbr_monetary_parser.DEFAULT_BACKFILL_FROM | Call | computed source expression | [backend/app/services/cbr_monetary_parser.py:26](../backend/app/services/cbr_monetary_parser.py#L26) |
| app.services.cbr_monetary_parser._ROW_RE | Call | computed source expression | [backend/app/services/cbr_monetary_parser.py:28](../backend/app/services/cbr_monetary_parser.py#L28) |
| app.services.cbr_reserves_parser._DATE_RE | Call | computed source expression | [backend/app/services/cbr_reserves_parser.py:30](../backend/app/services/cbr_reserves_parser.py#L30) |
| app.services.cbr_reserves_parser.DEFAULT_BACKFILL_FROM | Call | computed source expression | [backend/app/services/cbr_reserves_parser.py:32](../backend/app/services/cbr_reserves_parser.py#L32) |
| app.services.cbr_ruonia_parser._DATE_RE | Call | computed source expression | [backend/app/services/cbr_ruonia_parser.py:25](../backend/app/services/cbr_ruonia_parser.py#L25) |
| app.services.cbr_ruonia_parser.DEFAULT_BACKFILL_FROM | Call | computed source expression | [backend/app/services/cbr_ruonia_parser.py:27](../backend/app/services/cbr_ruonia_parser.py#L27) |
| app.services.cbr_trade_goods_monthly_parser._MONTH_RU | Dict | 'янв', 'фев', 'мар', 'апр', 'май', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек' | [backend/app/services/cbr_trade_goods_monthly_parser.py:56](../backend/app/services/cbr_trade_goods_monthly_parser.py#L56) |
| app.services.cbr_trade_goods_monthly_parser._TARGET_COL | Dict | 'exports-monthly', 'imports-monthly', 'trade-balance-monthly' | [backend/app/services/cbr_trade_goods_monthly_parser.py:61](../backend/app/services/cbr_trade_goods_monthly_parser.py#L61) |
| app.services.cbr_trade_services_monthly_parser._MONTH_RU_SHORT | Dict | 'янв', 'фев', 'мар', 'апр', 'май', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек' | [backend/app/services/cbr_trade_services_monthly_parser.py:43](../backend/app/services/cbr_trade_services_monthly_parser.py#L43) |
| app.services.cbr_trade_services_monthly_parser._TARGET_LABEL | Dict | 'services-exports-monthly', 'services-imports-monthly' | [backend/app/services/cbr_trade_services_monthly_parser.py:48](../backend/app/services/cbr_trade_services_monthly_parser.py#L48) |
| app.services.cbr_trade_services_monthly_parser._HEADER_STR_RE | Call | computed source expression | [backend/app/services/cbr_trade_services_monthly_parser.py:53](../backend/app/services/cbr_trade_services_monthly_parser.py#L53) |
| app.services.clickhouse_sync._DDL | List | sequence/source expression | [backend/app/services/clickhouse_sync.py:63](../backend/app/services/clickhouse_sync.py#L63) |
| app.services.clickhouse_sync._COLUMN_GUARDS | List | sequence/source expression | [backend/app/services/clickhouse_sync.py:118](../backend/app/services/clickhouse_sync.py#L118) |
| app.services.clickhouse_sync._EVENT_COLUMNS | List | sequence/source expression | [backend/app/services/clickhouse_sync.py:251](../backend/app/services/clickhouse_sync.py#L251) |
| app.services.clickhouse_sync._FRONTEND_COLUMNS | List | sequence/source expression | [backend/app/services/clickhouse_sync.py:256](../backend/app/services/clickhouse_sync.py#L256) |
| app.services.clickhouse_sync._VISIT_JSON_KEYS | Tuple | sequence/source expression | [backend/app/services/clickhouse_sync.py:344](../backend/app/services/clickhouse_sync.py#L344) |
| app.services.clickhouse_sync._SESSION_COLUMNS | List | sequence/source expression | [backend/app/services/clickhouse_sync.py:372](../backend/app/services/clickhouse_sync.py#L372) |
| app.services.clickhouse_sync._SERVER_SESSION_COLUMNS | List | sequence/source expression | [backend/app/services/clickhouse_sync.py:378](../backend/app/services/clickhouse_sync.py#L378) |
| app.services.clickhouse_sync._VISIT_COLUMNS | List | sequence/source expression | [backend/app/services/clickhouse_sync.py:385](../backend/app/services/clickhouse_sync.py#L385) |
| app.services.clickhouse_sync.SLICE_METRICS | Dict | 'sessions', 'visitors', 'pageviews', 'clicks', 'engaged_sessions', 'micro_goals', 'macro_goals', 'metrika_visits', 'metrika_goal_visits' | [backend/app/services/clickhouse_sync.py:604](../backend/app/services/clickhouse_sync.py#L604) |
| app.services.clickhouse_sync.SLICE_DIMENSIONS | Dict | 'server_sessions', 'behavior_events', 'raw_metrika_visits' | [backend/app/services/clickhouse_sync.py:616](../backend/app/services/clickhouse_sync.py#L616) |
| app.services.demand_router._SYNONYMS | Tuple | sequence/source expression | [backend/app/services/demand_router.py:36](../backend/app/services/demand_router.py#L36) |
| app.services.demand_router._STOP_TOKENS | Call | computed source expression | [backend/app/services/demand_router.py:107](../backend/app/services/demand_router.py#L107) |
| app.services.demand_router._YEAR_RE | Call | computed source expression | [backend/app/services/demand_router.py:113](../backend/app/services/demand_router.py#L113) |
| app.services.demographics.AGE_GROUP_CODES | List | sequence/source expression | [backend/app/services/demographics.py:9](../backend/app/services/demographics.py#L9) |
| app.services.derived_ops._QUARTER_END_MONTHS | Tuple | sequence/source expression | [backend/app/services/derived_ops.py:58](../backend/app/services/derived_ops.py#L58) |
| app.services.derived_ops._GRANULARITIES | Tuple | sequence/source expression | [backend/app/services/derived_ops.py:286](../backend/app/services/derived_ops.py#L286) |
| app.services.derived_ops._POP_MAX_GAP_DAYS | Dict | 'month', 'quarter', 'year' | [backend/app/services/derived_ops.py:467](../backend/app/services/derived_ops.py#L467) |
| app.services.display._MSK | Call | computed source expression | [backend/app/services/display.py:22](../backend/app/services/display.py#L22) |
| app.services.display.CPI_INDEX_CODES | Call | computed source expression | [backend/app/services/display.py:36](../backend/app/services/display.py#L36) |
| app.services.display._PERIOD_LABEL | Dict | 'weekly', 'monthly', 'quarterly', 'annual' | [backend/app/services/display.py:52](../backend/app/services/display.py#L52) |
| app.services.display._PERIOD_LABEL_EN | Dict | 'weekly', 'monthly', 'quarterly', 'annual' | [backend/app/services/display.py:58](../backend/app/services/display.py#L58) |
| app.services.display._UNIT_EN | Dict | 'руб.', 'руб', 'млн руб.', 'млн руб', 'млрд руб.', 'млрд руб', 'трлн руб.', 'трлн руб', 'руб./л', 'руб./г', 'тыс. руб.', 'тыс. руб', 'км²', 'км2', 'человек', 'чел. на км²', 'п.п.', 'п.п', 'п. п.', 'пункт', 'пункты', 'пунктов', 'изменение за месяц, п.п.', 'изменение за месяц', 'изменение за квартал, п.п.', 'изменение за год, п.п.', '% ВВП', 'млн евро', 'в текущих ценах, млн евро', 'в постоянных ценах 2015 года, млн евро', 'в постоянных ценах 2010 года, млн евро', 'ППС на душу населения', 'тысяча рублей', 'тысяч рублей', 'тысяч тонн', 'рублей за литр', 'тыс. тонн', 'тыс. т н. э.', 'кг н. э.', 'евро за кг н. э.', 'евро', 'тыс. евро', 'млн евро, с сезонной корректировкой', 'млн евро, в постоянных ценах', 'в постоянных ценах 2020 года, евро на душу населения', 'на душу населения, евро', '% экономически активного населения', '% населения', '% населения ЕС', '% занятости', '% от итога', '% к ожидаемому уровню', 'изменение к предыдущему периоду', 'изменение к тому же периоду прошлого года', 'темп изменения к предыдущему периоду', 'темп изменения, с сезонной корректировкой', 'изменение, %', 'изменение за год', 'изменение за год, %', 'среднее изменение за 12 месяцев', 'сальдо', 'ГВт·ч', 'МВт', 'ТДж', 'млн м³', 'тыс. м²', 'км', 'тыс. баррелей', 'лет', 'часов в неделю', 'штук', 'тыс. единиц', 'автомобилей', 'койко-мест', 'сделок', 'дней запаса', 'градусо-сутки', 'балл индекса', 'пунктов индекса Джини', 'раз', 'индекс', 'индекс, среднегодовой', 'вероятность / лет', 'детей на женщину', 'на 1000 женщин соответствующего возраста', 'на 1000 человек населения', 'на 1000 человек соответствующего возраста', 'на 1000 живорождённых', 'на 1000 жителей', 'на одного жителя', 'на одну женщину', 'на одного мужчину', '‰ от суммарных весов стран ЕС', '‰ от суммарных весов категорий', 'индекс (2015 = 100)', 'индекс (2015 = 100), с сезонной корректировкой', 'индекс (2015 = 100), среднегодовой', 'индекс (2021 = 100)', 'индекс (2020 = 100)', 'индекс (2025 = 100)', 'индекс (2005 = 100)', 'индекс (2017 = 100)', 'индекс (1982–84 = 100)', 'индекс (2011–12 = 100)', 'индекс (2012 = 100)', 'индекс (2002 = 100)', 'индекс (2-я половина июля 2018 = 100)', 'индекс (среднее 1995 = 100)', 'индекс (тот же месяц прошлого года = 100)', 'тыс. человек', 'тысяч человек', 'млн долларов США', 'млрд долларов США (цены 2017)', 'тыс. долларов США', 'млрд $', '$ на человека', 'иены', 'млрд иен', 'иен за 1 доллар США', 'юаней за 1 доллар США', '100 млн юаней', 'тыс. канадских долларов', 'млн канадских долларов', 'млн канадских долларов (цены 2017)', 'канадских долларов за 1 доллар США', 'млн австралийских долларов', 'млн австралийских долларов (цепные объёмы)', 'долларов США за 1 австралийский доллар', 'млн фунтов стерлингов', 'млн фунтов стерлингов (цепные объёмы)', 'долларов США за 1 фунт стерлингов', 'долларов США за 1 евро', 'млрд долларов США', 'долларов США', 'долларов США за галлон', 'долларов США за баррель', 'долларов США в час', 'долларов США (цены 2017) на человека', 'тыс. единиц', 'тыс. единиц в год', 'млн автомобилей в год', 'индекс (1982 = 100)', 'индекс (1 кв. 1991 = 100)', 'вон за 1 доллар США', 'млрд вон', 'млрд вон (цены 2020)', 'мексиканских песо за 1 доллар США', 'млн мексиканских песо (постоянные цены 2018)', 'бразильских реалов за 1 доллар США', 'крор рупий', 'рупий за 1 доллар США', 'тыс. долл.', 'тыс. долл', 'млн долл.', 'млн долл', 'млн долл., текущие цены', 'млн долл. 2017 г.', 'долл.', 'долл', 'долл. 2017 г.', 'текущие цены', 'рабочих мест', 'отношение' | [backend/app/services/display.py:66](../backend/app/services/display.py#L66) |
| app.services.display._RU_MONTHS_GEN | Tuple | sequence/source expression | [backend/app/services/display.py:239](../backend/app/services/display.py#L239) |
| app.services.display._RU_MONTHS_NOM | Tuple | sequence/source expression | [backend/app/services/display.py:243](../backend/app/services/display.py#L243) |
| app.services.display._CYRILLIC_RE | Call | computed source expression | [backend/app/services/display.py:317](../backend/app/services/display.py#L317) |
| app.services.display._EN_MONTHS_NOM | Tuple | sequence/source expression | [backend/app/services/display.py:438](../backend/app/services/display.py#L438) |
| app.services.display._TEMPLATE_ANNUAL_KIND | Dict | 'T3', 'T4', 'T5', 'T6', 'T7', 'T9', 'T9s' | [backend/app/services/display.py:540](../backend/app/services/display.py#L540) |
| app.services.emiss_regional_parser.PRICE_FUELS | Dict | '1709730', '1709750', '1755196' | [backend/app/services/emiss_regional_parser.py:70](../backend/app/services/emiss_regional_parser.py#L70) |
| app.services.emiss_regional_parser.MONTH_OIDS | Dict | '1540283', '1540282', '1540236', '1540229', '1540235', '1540234', '1540233', '1540228', '1540276', '1540273', '1540272', '1540230' | [backend/app/services/emiss_regional_parser.py:77](../backend/app/services/emiss_regional_parser.py#L77) |
| app.services.eurostat_parser.HEADLINE_PRIORITY | Dict | 'unit', 's_adj', 'nace_r2', 'nace_r1', 'coicop', 'coicop18', 'sex', 'age', 'na_item', 'geo', 'time', 'freq', 'indic', 'indic_bt', 'indic_sb', 'indic_de', 'cpa2_1', 'sizeclas', 'worktime', 'citizen', 'wstatus', 'isced11', 'currency', 'stk_flow', 'partner', 'sitc06', 'nrg_bal', 'siec' | [backend/app/services/eurostat_parser.py:91](../backend/app/services/eurostat_parser.py#L91) |
| app.services.eurostat_parser._SKIP_DIMS | Call | computed source expression | [backend/app/services/eurostat_parser.py:140](../backend/app/services/eurostat_parser.py#L140) |
| app.services.eurostat_parser.FREQ_MAP | Dict | 'M', 'Q', 'A', 'W', 'D', 'S' | [backend/app/services/eurostat_parser.py:142](../backend/app/services/eurostat_parser.py#L142) |
| app.services.eurostat_parser.EXCLUDED_GEO_CODES | Call | computed source expression | [backend/app/services/eurostat_parser.py:157](../backend/app/services/eurostat_parser.py#L157) |
| app.services.eurostat_parser.WORLD_COUNTRIES | Dict | 'AT', 'BE', 'BG', 'HR', 'CY', 'CZ', 'DK', 'EE', 'FI', 'FR', 'DE', 'EL', 'GR', 'HU', 'IE', 'IT', 'LV', 'LT', 'LU', 'MT', 'NL', 'PL', 'PT', 'RO', 'SK', 'SI', 'ES', 'SE', 'IS', 'NO', 'CH', 'UK', 'GB', 'TR', 'RS', 'ME', 'MK', 'AL', 'BA', 'XK', 'UA', 'MD', 'GE', 'AM', 'AZ', 'US', 'CA', 'JP', 'KR', 'CN', 'IN', 'BR', 'MX', 'AU', 'NZ', 'ZA', 'IL' | [backend/app/services/eurostat_parser.py:167](../backend/app/services/eurostat_parser.py#L167) |
| app.services.eurostat_parser._NON_RETRYABLE_STATUS | Call | computed source expression | [backend/app/services/eurostat_parser.py:257](../backend/app/services/eurostat_parser.py#L257) |
| app.services.eurostat_parser._SDMX_NS | Dict | 'm', 's', 'c' | [backend/app/services/eurostat_parser.py:572](../backend/app/services/eurostat_parser.py#L572) |
| app.services.export_render._LIMITER | Call | computed source expression | [backend/app/services/export_render.py:15](../backend/app/services/export_render.py#L15) |
| app.services.export_render._SLOTS | Call | computed source expression | [backend/app/services/export_render.py:16](../backend/app/services/export_render.py#L16) |
| app.services.forecast_strategies.cpi_combined.CPI_DERIVED_CODES | Dict | 'cpi', 'cpi-food', 'cpi-nonfood', 'cpi-services' | [backend/app/services/forecast_strategies/cpi_combined.py:31](../backend/app/services/forecast_strategies/cpi_combined.py#L31) |
| app.services.forecast_strategies.cpi_combined.CPI_DERIVED_TARGETS | SetComp | computed source expression | [backend/app/services/forecast_strategies/cpi_combined.py:38](../backend/app/services/forecast_strategies/cpi_combined.py#L38) |
| app.services.forecast_strategies.registry.STRATEGIES | Dict | 'annual_auto', 'approved', 'cpi_combined', 'derived_from_source', 'generic_ols', 'generic_quarterly', 'gdp_consumption_quarterly', 'gdp_government_quarterly', 'gdp_nominal_quarterly', 'gdp_real_quarterly', 'housing_quarterly', 'monthly_auto', 'ppi_monthly', 'signed_quarterly' | [backend/app/services/forecast_strategies/registry.py:40](../backend/app/services/forecast_strategies/registry.py#L40) |
| app.services.forecaster.CPI_INDICATOR_CODES | Set | sequence/source expression | [backend/app/services/forecaster.py:21](../backend/app/services/forecaster.py#L21) |
| app.services.forecaster._INFLATION_BLEND_WEIGHTS | Dict | 1, 2, 3, 4 | [backend/app/services/forecaster.py:371](../backend/app/services/forecaster.py#L371) |
| app.services.forecaster._DEFAULT_BLEND | List | sequence/source expression | [backend/app/services/forecaster.py:377](../backend/app/services/forecaster.py#L377) |
| app.services.forecaster._BLEND_M12 | List | sequence/source expression | [backend/app/services/forecaster.py:378](../backend/app/services/forecaster.py#L378) |
| app.services.goal_taxonomy.TIERS | Tuple | sequence/source expression | [backend/app/services/goal_taxonomy.py:33](../backend/app/services/goal_taxonomy.py#L33) |
| app.services.goal_taxonomy.TIER_WEIGHTS | Dict | TIER_MACRO, TIER_MICRO, TIER_INTENT, TIER_ENGAGEMENT, TIER_TECHNICAL | [backend/app/services/goal_taxonomy.py:36](../backend/app/services/goal_taxonomy.py#L36) |
| app.services.goal_taxonomy._MACRO | Set | sequence/source expression | [backend/app/services/goal_taxonomy.py:45](../backend/app/services/goal_taxonomy.py#L45) |
| app.services.goal_taxonomy._MICRO | Set | sequence/source expression | [backend/app/services/goal_taxonomy.py:52](../backend/app/services/goal_taxonomy.py#L52) |
| app.services.goal_taxonomy._INTENT | Set | sequence/source expression | [backend/app/services/goal_taxonomy.py:74](../backend/app/services/goal_taxonomy.py#L74) |
| app.services.goal_taxonomy._ENGAGEMENT | Set | sequence/source expression | [backend/app/services/goal_taxonomy.py:85](../backend/app/services/goal_taxonomy.py#L85) |
| app.services.goal_taxonomy._TECHNICAL | Set | sequence/source expression | [backend/app/services/goal_taxonomy.py:149](../backend/app/services/goal_taxonomy.py#L149) |
| app.services.goal_taxonomy._WEIGHT_OVERRIDES | Dict | 'signup', 'newsletter_opt_in', 'feedback_submit', 'login_success', 'download_csv', 'download_excel', 'chart_image_download', 'regions_map_gif_download', 'oauth_start', 'header_register_click', 'forecast_view', 'search_select' | [backend/app/services/goal_taxonomy.py:170](../backend/app/services/goal_taxonomy.py#L170) |
| app.services.http_client._RETRY_STRATEGY | Call | computed source expression | [backend/app/services/http_client.py:26](../backend/app/services/http_client.py#L26) |
| app.services.http_client._PROXY_FALLBACK_STATUSES | Call | computed source expression | [backend/app/services/http_client.py:33](../backend/app/services/http_client.py#L33) |
| app.services.http_client._PROXY_FALLBACK_EXC | Tuple | sequence/source expression | [backend/app/services/http_client.py:34](../backend/app/services/http_client.py#L34) |
| app.services.identity.consents.NEWSLETTER_KINDS | Tuple | sequence/source expression | [backend/app/services/identity/consents.py:5](../backend/app/services/identity/consents.py#L5) |
| app.services.imf_weo_adapter.WEO_SERIES | Dict | WEO_NGDPD, WEO_NGDPDPC, WEO_GGXCNL_NGDP, WEO_GGXWDG_NGDP, WEO_LP, WEO_LUR, WEO_PCPIPCH | [backend/app/services/imf_weo_adapter.py:88](../backend/app/services/imf_weo_adapter.py#L88) |
| app.services.imf_weo_adapter.WEO_METHODOLOGY_BY_CODE | Dict | WEO_NGDPD, WEO_NGDPDPC, WEO_GGXCNL_NGDP, WEO_GGXWDG_NGDP, WEO_LP, WEO_LUR, WEO_PCPIPCH | [backend/app/services/imf_weo_adapter.py:223](../backend/app/services/imf_weo_adapter.py#L223) |
| app.services.imf_weo_adapter.WEO_ISO3_BY_ISO2 | Dict | 'AL', 'AM', 'AT', 'AU', 'AZ', 'BA', 'BE', 'BG', 'BR', 'CA', 'CH', 'CN', 'CY', 'CZ', 'DE', 'DK', 'EE', 'EL', 'ES', 'FI', 'FR', 'GB', 'GE', 'GR', 'HR', 'HU', 'IE', 'IL', 'IN', 'IS', 'IT', 'JP', 'KR', 'LT', 'LU', 'LV', 'MD', 'ME', 'MK', 'MT', 'MX', 'NL', 'NO', 'NZ', 'PL', 'PT', 'RO', 'RS', 'RU', 'SE', 'SI', 'SK', 'TR', 'UA', 'UK', 'US', 'ZA' | [backend/app/services/imf_weo_adapter.py:289](../backend/app/services/imf_weo_adapter.py#L289) |
| app.services.imf_weo_adapter.WEO_YEAR_POLICY_BY_CODE | Dict | WEO_NGDPD, WEO_NGDPDPC, WEO_GGXCNL_NGDP, WEO_GGXWDG_NGDP, WEO_LP, WEO_LUR, WEO_PCPIPCH | [backend/app/services/imf_weo_adapter.py:368](../backend/app/services/imf_weo_adapter.py#L368) |
| app.services.locale.PRODUCTION_APEX_HOSTS | Call | computed source expression | [backend/app/services/locale.py:35](../backend/app/services/locale.py#L35) |
| app.services.locale._PREVIEW_IN_URL | Call | computed source expression | [backend/app/services/locale.py:37](../backend/app/services/locale.py#L37) |
| app.services.metrika_acquisition._VISIT_FIELDS | List | sequence/source expression | [backend/app/services/metrika_acquisition.py:63](../backend/app/services/metrika_acquisition.py#L63) |
| app.services.metrika_acquisition._OPTIONAL_FIELDS | List | sequence/source expression | [backend/app/services/metrika_acquisition.py:97](../backend/app/services/metrika_acquisition.py#L97) |
| app.services.metrika_acquisition._ACQ_REPORTS | List | sequence/source expression | [backend/app/services/metrika_acquisition.py:340](../backend/app/services/metrika_acquisition.py#L340) |
| app.services.minfin_budget_parser._DATA_RE | Call | computed source expression | [backend/app/services/minfin_budget_parser.py:49](../backend/app/services/minfin_budget_parser.py#L49) |
| app.services.minfin_budget_parser._RU_OPENDATA_RE | Call | computed source expression | [backend/app/services/minfin_budget_parser.py:54](../backend/app/services/minfin_budget_parser.py#L54) |
| app.services.minfin_budget_parser._MINFIN_RETRY | Call | computed source expression | [backend/app/services/minfin_budget_parser.py:63](../backend/app/services/minfin_budget_parser.py#L63) |
| app.services.minfin_budget_parser.PRESS_TITLE_RE | Call | computed source expression | [backend/app/services/minfin_budget_parser.py:81](../backend/app/services/minfin_budget_parser.py#L81) |
| app.services.minfin_budget_parser.PRESS_PERIOD_RE | Call | computed source expression | [backend/app/services/minfin_budget_parser.py:85](../backend/app/services/minfin_budget_parser.py#L85) |
| app.services.minfin_budget_parser.MONTH_MAP | Dict | 'январь', 'февраль', 'март', 'апрель', 'май', 'июнь', 'июль', 'август', 'сентябрь', 'октябрь', 'ноябрь', 'декабрь' | [backend/app/services/minfin_budget_parser.py:89](../backend/app/services/minfin_budget_parser.py#L89) |
| app.services.minfin_budget_parser.MONTH_GENITIVE_MAP | Dict | 'января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря' | [backend/app/services/minfin_budget_parser.py:95](../backend/app/services/minfin_budget_parser.py#L95) |
| app.services.oauth.google._TIMEOUT | Call | computed source expression | [backend/app/services/oauth/google.py:21](../backend/app/services/oauth/google.py#L21) |
| app.services.oauth.registry.SUPPORTED | Tuple | sequence/source expression | [backend/app/services/oauth/registry.py:14](../backend/app/services/oauth/registry.py#L14) |
| app.services.oauth.registry.PUBLIC_PROVIDERS | Tuple | sequence/source expression | [backend/app/services/oauth/registry.py:17](../backend/app/services/oauth/registry.py#L17) |
| app.services.oauth.vk._TIMEOUT | Call | computed source expression | [backend/app/services/oauth/vk.py:22](../backend/app/services/oauth/vk.py#L22) |
| app.services.oauth.yandex._TIMEOUT | Call | computed source expression | [backend/app/services/oauth/yandex.py:20](../backend/app/services/oauth/yandex.py#L20) |
| app.services.og_image._RASTER_SPACES | Call | computed source expression | [backend/app/services/og_image.py:47](../backend/app/services/og_image.py#L47) |
| app.services.og_image.DARK0 | Tuple | sequence/source expression | [backend/app/services/og_image.py:70](../backend/app/services/og_image.py#L70) |
| app.services.og_image.DARK1 | Tuple | sequence/source expression | [backend/app/services/og_image.py:71](../backend/app/services/og_image.py#L71) |
| app.services.og_image.GOLD | Tuple | sequence/source expression | [backend/app/services/og_image.py:72](../backend/app/services/og_image.py#L72) |
| app.services.og_image.GOLD_BRIGHT | Tuple | sequence/source expression | [backend/app/services/og_image.py:73](../backend/app/services/og_image.py#L73) |
| app.services.og_image.GOLD_SOFT | Tuple | sequence/source expression | [backend/app/services/og_image.py:74](../backend/app/services/og_image.py#L74) |
| app.services.og_image.IVORY | Tuple | sequence/source expression | [backend/app/services/og_image.py:75](../backend/app/services/og_image.py#L75) |
| app.services.og_image.MUT | Tuple | sequence/source expression | [backend/app/services/og_image.py:76](../backend/app/services/og_image.py#L76) |
| app.services.og_image.AXIS_TXT | Tuple | sequence/source expression | [backend/app/services/og_image.py:77](../backend/app/services/og_image.py#L77) |
| app.services.og_image.PILL_TEXT | Tuple | sequence/source expression | [backend/app/services/og_image.py:78](../backend/app/services/og_image.py#L78) |
| app.services.og_image._LEGACY_BG | Tuple | sequence/source expression | [backend/app/services/og_image.py:80](../backend/app/services/og_image.py#L80) |
| app.services.og_image.TEXT_PRIMARY | Tuple | sequence/source expression | [backend/app/services/og_image.py:81](../backend/app/services/og_image.py#L81) |
| app.services.og_image.CHAMPAGNE | Tuple | sequence/source expression | [backend/app/services/og_image.py:82](../backend/app/services/og_image.py#L82) |
| app.services.og_image.TEXT_SECONDARY | Tuple | sequence/source expression | [backend/app/services/og_image.py:86](../backend/app/services/og_image.py#L86) |
| app.services.og_image.TEXT_TERTIARY | Tuple | sequence/source expression | [backend/app/services/og_image.py:87](../backend/app/services/og_image.py#L87) |
| app.services.og_image.RU_MONTH_NOM | Tuple | sequence/source expression | [backend/app/services/og_image.py:89](../backend/app/services/og_image.py#L89) |
| app.services.og_image.RU_MONTH_DAT | Tuple | sequence/source expression | [backend/app/services/og_image.py:91](../backend/app/services/og_image.py#L91) |
| app.services.og_image.EN_MONTH_SHORT | Tuple | sequence/source expression | [backend/app/services/og_image.py:96](../backend/app/services/og_image.py#L96) |
| app.services.og_image.EN_MONTHS_NOM | Tuple | sequence/source expression | [backend/app/services/og_image.py:98](../backend/app/services/og_image.py#L98) |
| app.services.og_image.RU_MONTH_SHORT | Tuple | sequence/source expression | [backend/app/services/og_image.py:149](../backend/app/services/og_image.py#L149) |
| app.services.og_image._CACHE | Dict | sequence/source expression | [backend/app/services/og_image.py:185](../backend/app/services/og_image.py#L185) |
| app.services.og_image._CACHE_LOCK | Call | computed source expression | [backend/app/services/og_image.py:189](../backend/app/services/og_image.py#L189) |
| app.services.og_image._FONT_CACHE | Dict | sequence/source expression | [backend/app/services/og_image.py:193](../backend/app/services/og_image.py#L193) |
| app.services.og_image._FONT_FILE_BYTES | Dict | sequence/source expression | [backend/app/services/og_image.py:194](../backend/app/services/og_image.py#L194) |
| app.services.og_image._DISK_TTL | Call | computed source expression | [backend/app/services/og_image.py:1818](../backend/app/services/og_image.py#L1818) |
| app.services.og_image._DISK_TTL_HISTORICAL | Call | computed source expression | [backend/app/services/og_image.py:1819](../backend/app/services/og_image.py#L1819) |
| app.services.og_image._DISK_MAX_BYTES | Call | computed source expression | [backend/app/services/og_image.py:1820](../backend/app/services/og_image.py#L1820) |
| app.services.og_render._EXECUTOR | Call | computed source expression | [backend/app/services/og_render.py:17](../backend/app/services/og_render.py#L17) |
| app.services.og_render._SLOTS | Call | computed source expression | [backend/app/services/og_render.py:18](../backend/app/services/og_render.py#L18) |
| app.services.parser.MONTH_MAP | Dict | 'январь', 'февраль', 'март', 'апрель', 'май', 'июнь', 'июль', 'август', 'сентябрь', 'октябрь', 'ноябрь', 'декабрь' | [backend/app/services/parser.py:20](../backend/app/services/parser.py#L20) |
| app.services.pulse._DOWNLOAD_EVENTS | Set | sequence/source expression | [backend/app/services/pulse.py:52](../backend/app/services/pulse.py#L52) |
| app.services.pulse._ERROR_EVENTS | Set | sequence/source expression | [backend/app/services/pulse.py:56](../backend/app/services/pulse.py#L56) |
| app.services.pulse.ETL_ERROR_STATUSES | Tuple | sequence/source expression | [backend/app/services/pulse.py:62](../backend/app/services/pulse.py#L62) |
| app.services.rosstat_cpi_parser.PARSER_REGISTRY | Dict | RosstatCpiParser.parser_type, CbrKeyRateParser.parser_type, CbrFxParser.parser_type, CbrRuoniaParser.parser_type, CbrMonetaryParser.parser_type, CbrDataServiceParser.parser_type, RosstatLaborParser.parser_type, RosstatGdpParser.parser_type, CbrDataServiceSumParser.parser_type, MinfinBudgetParser.parser_type, RosstatWeeklyCpiParser.parser_type, RosstatIpiParser.parser_type, RosstatHousingParser.parser_type, RosstatPopulationParser.parser_type, RosstatPpiParser.parser_type, CbrBopParser.parser_type, CbrTradeGoodsMonthlyParser.parser_type, CbrTradeServicesMonthlyParser.parser_type, CbrReservesParser.parser_type, CbrDebtParser.parser_type, CbrGoldParser.parser_type, RosstatDemoParser.parser_type, RosstatIndParser.parser_type, RosstatScienceParser.parser_type, RosstatFixedAssetsParser.parser_type, BinanceBtcUsdtParser.parser_type, BrentDailyFredParser.parser_type, FredCsvParser.parser_type, WorldBankPinkSheetParser.parser_type, EcbFxParser.parser_type, ImfWeoParser.parser_type, CbrMonetaryAggParser.parser_type, MoexIndexParser.parser_type, RosstatWeeklyPriceParser.parser_type | [backend/app/services/rosstat_cpi_parser.py:91](../backend/app/services/rosstat_cpi_parser.py#L91) |
| app.services.rosstat_demo_parser.DEMO_FILES | Dict | 'births', 'deaths', 'birth-rate', 'death-rate', 'working-age-population', 'pop-under-working-age', 'pop-over-working-age', 'pensioners' | [backend/app/services/rosstat_demo_parser.py:277](../backend/app/services/rosstat_demo_parser.py#L277) |
| app.services.rosstat_gdp_parser._Q_RE | Call | computed source expression | [backend/app/services/rosstat_gdp_parser.py:46](../backend/app/services/rosstat_gdp_parser.py#L46) |
| app.services.rosstat_gdp_parser._YEAR_RE | Call | computed source expression | [backend/app/services/rosstat_gdp_parser.py:47](../backend/app/services/rosstat_gdp_parser.py#L47) |
| app.services.rosstat_gdp_parser.QUARTER_MONTH | Dict | 1, 2, 3, 4 | [backend/app/services/rosstat_gdp_parser.py:56](../backend/app/services/rosstat_gdp_parser.py#L56) |
| app.services.rosstat_gdp_parser._FOOTNOTE_SUFFIX_RE | Call | computed source expression | [backend/app/services/rosstat_gdp_parser.py:72](../backend/app/services/rosstat_gdp_parser.py#L72) |
| app.services.rosstat_gdp_parser._QUARTER_NAME_TO_MONTH | Dict | 'i квартал', 'ii квартал', 'iii квартал', 'iv квартал' | [backend/app/services/rosstat_gdp_parser.py:114](../backend/app/services/rosstat_gdp_parser.py#L114) |
| app.services.rosstat_housing_parser._ROMAN_TO_QUARTER | Dict | 'I', 'II', 'III', 'IV' | [backend/app/services/rosstat_housing_parser.py:57](../backend/app/services/rosstat_housing_parser.py#L57) |
| app.services.rosstat_housing_parser._QUARTER_END_MONTH | Dict | 1, 2, 3, 4 | [backend/app/services/rosstat_housing_parser.py:58](../backend/app/services/rosstat_housing_parser.py#L58) |
| app.services.rosstat_housing_parser._QOQ_PAIR_COMPACT_RE | Call | computed source expression | [backend/app/services/rosstat_housing_parser.py:63](../backend/app/services/rosstat_housing_parser.py#L63) |
| app.services.rosstat_housing_parser._HOUSING_SECTION_COMPACT_RE | Call | computed source expression | [backend/app/services/rosstat_housing_parser.py:70](../backend/app/services/rosstat_housing_parser.py#L70) |
| app.services.rosstat_housing_parser._QUARTER_HEADER_RE | Call | computed source expression | [backend/app/services/rosstat_housing_parser.py:71](../backend/app/services/rosstat_housing_parser.py#L71) |
| app.services.rosstat_housing_parser._INDICATOR_TO_PAIR_INDEX | Dict | 'housing-price-primary', 'housing-price-secondary' | [backend/app/services/rosstat_housing_parser.py:189](../backend/app/services/rosstat_housing_parser.py#L189) |
| app.services.rosstat_ind_parser._QUARTER_START_MONTH | Dict | 0, 1, 2, 3 | [backend/app/services/rosstat_ind_parser.py:144](../backend/app/services/rosstat_ind_parser.py#L144) |
| app.services.rosstat_ind_parser.SHEET_MAP | Dict | 'retail-trade', 'housing-commissioned', 'construction-work', 'capital-investment' | [backend/app/services/rosstat_ind_parser.py:200](../backend/app/services/rosstat_ind_parser.py#L200) |
| app.services.rosstat_ipi_parser._MONTH_NAME_TO_NUM | Dict | 'январь', 'февраль', 'март', 'апрель', 'май', 'июнь', 'июль', 'август', 'сентябрь', 'октябрь', 'ноябрь', 'декабрь' | [backend/app/services/rosstat_ipi_parser.py:48](../backend/app/services/rosstat_ipi_parser.py#L48) |
| app.services.rosstat_ipi_parser._YEAR_RE | Call | computed source expression | [backend/app/services/rosstat_ipi_parser.py:53](../backend/app/services/rosstat_ipi_parser.py#L53) |
| app.services.rosstat_ipi_parser._MONTH_PREFIX_RE | Call | computed source expression | [backend/app/services/rosstat_ipi_parser.py:54](../backend/app/services/rosstat_ipi_parser.py#L54) |
| app.services.rosstat_labor_parser.MONTHS_RU | Dict | 'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь', 'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь' | [backend/app/services/rosstat_labor_parser.py:62](../backend/app/services/rosstat_labor_parser.py#L62) |
| app.services.rosstat_labor_parser._MONTH_NUM_RE | Call | computed source expression | [backend/app/services/rosstat_labor_parser.py:67](../backend/app/services/rosstat_labor_parser.py#L67) |
| app.services.rosstat_labor_parser._AGG_ROW_RE | Call | computed source expression | [backend/app/services/rosstat_labor_parser.py:204](../backend/app/services/rosstat_labor_parser.py#L204) |
| app.services.rosstat_labor_parser._MONTH_ROW_RE | Call | computed source expression | [backend/app/services/rosstat_labor_parser.py:205](../backend/app/services/rosstat_labor_parser.py#L205) |
| app.services.rosstat_labor_parser.INDICATOR_SERIES_MAP | Dict | 'unemployment', 'wages-nominal', 'labor-force', 'employment' | [backend/app/services/rosstat_labor_parser.py:300](../backend/app/services/rosstat_labor_parser.py#L300) |
| app.services.rosstat_population_parser._YEAR_RE | Call | computed source expression | [backend/app/services/rosstat_population_parser.py:48](../backend/app/services/rosstat_population_parser.py#L48) |
| app.services.rosstat_population_parser.INDICATOR_SOURCE_MAP | Dict | 'population', 'population-total-growth', 'population-natural-growth', 'population-migration' | [backend/app/services/rosstat_population_parser.py:245](../backend/app/services/rosstat_population_parser.py#L245) |
| app.services.rosstat_population_parser.COMPONENT_SERIES_MAP | Dict | 'population-total-growth', 'population-natural-growth', 'population-migration' | [backend/app/services/rosstat_population_parser.py:252](../backend/app/services/rosstat_population_parser.py#L252) |
| app.services.rosstat_ppi_parser.MONTHS_LOCATIVE_RU | Dict | 'январе', 'феврале', 'марте', 'апреле', 'мае', 'июне', 'июле', 'августе', 'сентябре', 'октябре', 'ноябре', 'декабре' | [backend/app/services/rosstat_ppi_parser.py:58](../backend/app/services/rosstat_ppi_parser.py#L58) |
| app.services.rosstat_ppi_parser._PPI_MOM_COMPACT_RE | Call | computed source expression | [backend/app/services/rosstat_ppi_parser.py:65](../backend/app/services/rosstat_ppi_parser.py#L65) |
| app.services.rosstat_science_parser.SCIENCE_CONFIG | Dict | 'grad-students', 'doctoral-students', 'rd-organizations', 'rd-personnel', 'innovation-activity', 'tech-innovation-share', 'small-business-innovation' | [backend/app/services/rosstat_science_parser.py:219](../backend/app/services/rosstat_science_parser.py#L219) |
| app.services.rosstat_sdds_fetcher._MEDIA_HREF_RE | Call | computed source expression | [backend/app/services/rosstat_sdds_fetcher.py:40](../backend/app/services/rosstat_sdds_fetcher.py#L40) |
| app.services.rosstat_sdds_fetcher._YEAR_IN_NAME_RE | Call | computed source expression | [backend/app/services/rosstat_sdds_fetcher.py:44](../backend/app/services/rosstat_sdds_fetcher.py#L44) |
| app.services.rosstat_sdds_fetcher.ROSSTAT_STATIC_URLS | Dict | 'popul_components', 'population_history', 'gdp_quarterly', 'gdp_use_quarterly', 'ipi_historical_2018', 'age_groups' | [backend/app/services/rosstat_sdds_fetcher.py:46](../backend/app/services/rosstat_sdds_fetcher.py#L46) |
| app.services.rosstat_weekly_inflation_parser.BULLETIN_URL_RE | Call | computed source expression | [backend/app/services/rosstat_weekly_inflation_parser.py:67](../backend/app/services/rosstat_weekly_inflation_parser.py#L67) |
| app.services.rosstat_weekly_inflation_parser._MONTH_MAP | Dict | 'января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря' | [backend/app/services/rosstat_weekly_inflation_parser.py:69](../backend/app/services/rosstat_weekly_inflation_parser.py#L69) |
| app.services.rosstat_weekly_inflation_parser._BULLETIN_RANGE_RE | Call | computed source expression | [backend/app/services/rosstat_weekly_inflation_parser.py:78](../backend/app/services/rosstat_weekly_inflation_parser.py#L78) |
| app.services.rosstat_weekly_inflation_parser._BULLETIN_VALUE_RE | Call | computed source expression | [backend/app/services/rosstat_weekly_inflation_parser.py:82](../backend/app/services/rosstat_weekly_inflation_parser.py#L82) |
| app.services.rosstat_weekly_inflation_parser._HEADER_RE | Call | computed source expression | [backend/app/services/rosstat_weekly_inflation_parser.py:84](../backend/app/services/rosstat_weekly_inflation_parser.py#L84) |
| app.services.rosstat_weekly_inflation_parser.WEEKLY_SEGMENT_CODES | Dict | 'food', 'nonfood', 'services' | [backend/app/services/rosstat_weekly_inflation_parser.py:98](../backend/app/services/rosstat_weekly_inflation_parser.py#L98) |
| app.services.rosstat_weekly_inflation_parser._CPI_BULLETIN_TITLE_RE | Call | computed source expression | [backend/app/services/rosstat_weekly_inflation_parser.py:349](../backend/app/services/rosstat_weekly_inflation_parser.py#L349) |
| app.services.rosstat_weekly_inflation_parser._BULLETIN_PUB_DATE_RE | Call | computed source expression | [backend/app/services/rosstat_weekly_inflation_parser.py:494](../backend/app/services/rosstat_weekly_inflation_parser.py#L494) |
| app.services.rosstat_weekly_price_parser._FUEL_BULLETIN_TITLE_RE | Call | computed source expression | [backend/app/services/rosstat_weekly_price_parser.py:71](../backend/app/services/rosstat_weekly_price_parser.py#L71) |
| app.services.rosstat_weekly_price_parser._BULLETIN_HREF_RE | Call | computed source expression | [backend/app/services/rosstat_weekly_price_parser.py:74](../backend/app/services/rosstat_weekly_price_parser.py#L74) |
| app.services.rosstat_weekly_price_parser._REG_DATE_RE | Call | computed source expression | [backend/app/services/rosstat_weekly_price_parser.py:77](../backend/app/services/rosstat_weekly_price_parser.py#L77) |
| app.services.rosstat_weekly_price_parser._BULLETIN_ROW_BY_LABEL | Dict | 'бензин автомобильный марки аи-92, л', 'бензин автомобильный марки аи-95, л', 'дизельное топливо, л' | [backend/app/services/rosstat_weekly_price_parser.py:82](../backend/app/services/rosstat_weekly_price_parser.py#L82) |
| app.services.scrape_guard._SEARCH_UA_RE | Call | computed source expression | [backend/app/services/scrape_guard.py:23](../backend/app/services/scrape_guard.py#L23) |
| app.services.scrape_guard._NOISE_UA_RE | Call | computed source expression | [backend/app/services/scrape_guard.py:35](../backend/app/services/scrape_guard.py#L35) |
| app.services.scrape_guard._HOSTING_ASN | Call | computed source expression | [backend/app/services/scrape_guard.py:38](../backend/app/services/scrape_guard.py#L38) |
| app.services.scrape_guard._HOSTING_ORG_RE | Call | computed source expression | [backend/app/services/scrape_guard.py:66](../backend/app/services/scrape_guard.py#L66) |
| app.services.scrape_guard._SKIP_PREFIXES | Tuple | sequence/source expression | [backend/app/services/scrape_guard.py:85](../backend/app/services/scrape_guard.py#L85) |
| app.services.scrape_guard._TELEMETRY_PREFIXES | Tuple | sequence/source expression | [backend/app/services/scrape_guard.py:110](../backend/app/services/scrape_guard.py#L110) |
| app.services.scrape_guard._AUTH_PREFIXES | Tuple | sequence/source expression | [backend/app/services/scrape_guard.py:119](../backend/app/services/scrape_guard.py#L119) |
| app.services.scrape_guard._HEADLESS_GL_RE | Call | computed source expression | [backend/app/services/scrape_guard.py:125](../backend/app/services/scrape_guard.py#L125) |
| app.services.seo_calendar._MONTHS_NOM | Tuple | sequence/source expression | [backend/app/services/seo_calendar.py:29](../backend/app/services/seo_calendar.py#L29) |
| app.services.seo_calendar._MONTHS_GEN | Tuple | sequence/source expression | [backend/app/services/seo_calendar.py:33](../backend/app/services/seo_calendar.py#L33) |
| app.services.seo_calendar._SOURCE_NAMES | Dict | 'rosstat', 'cbr', 'minfin' | [backend/app/services/seo_calendar.py:38](../backend/app/services/seo_calendar.py#L38) |
| app.services.seo_content.CATEGORY_META | Dict | 'prices', 'rates', 'currencies', 'indices', 'finance', 'commodities', 'labor', 'gdp', 'population', 'trade', 'business', 'science' | [backend/app/services/seo_content.py:49](../backend/app/services/seo_content.py#L49) |
| app.services.seo_content.CATEGORIES | Call | computed source expression | [backend/app/services/seo_content.py:242](../backend/app/services/seo_content.py#L242) |
| app.services.seo_content.STATIC_PAGES | List | sequence/source expression | [backend/app/services/seo_content.py:244](../backend/app/services/seo_content.py#L244) |
| app.services.seo_content.PAGE_META | Dict | 'home', 'about', 'methodology', 'privacy', 'terms', 'compare', 'calculator', 'calculator-mortgage', 'calculator-compound', 'calendar', 'demographics', 'widgets', 'russia', 'russia-categories' | [backend/app/services/seo_content.py:259](../backend/app/services/seo_content.py#L259) |
| app.services.seo_content.GLOBAL_INDICATOR_BLOCKS | Tuple | sequence/source expression | [backend/app/services/seo_content.py:608](../backend/app/services/seo_content.py#L608) |
| app.services.seo_crawler.TRACKING_PARAMS | Set | sequence/source expression | [backend/app/services/seo_crawler.py:15](../backend/app/services/seo_crawler.py#L15) |
| app.services.seo_i18n._VIEW_MODE_LABEL_EN | Dict | 'На конец периода', 'Средняя за период', 'К прошлому периоду', 'К году', 'К соотв. периоду пред. года', 'Г/г', 'Год к году', 'Кв/Кв', 'М/м', 'Н/н', 'По месяцам', 'По кварталам', 'По годам', 'По неделям', 'По дням', 'Уровень', 'Индекс', 'За период', 'Помесячно', 'Сглаживание', '12М среднее', 'Уровень ставки', 'Ежедневно', 'Понедельно', 'Поквартально', 'Годово', 'Частота отображения', 'Режим отображения', 'К прошлому году' | [backend/app/services/seo_i18n.py:45](../backend/app/services/seo_i18n.py#L45) |
| app.services.seo_i18n._HERO_LABEL_EN | Dict | 'Год к году', 'Изменение г/г' | [backend/app/services/seo_i18n.py:77](../backend/app/services/seo_i18n.py#L77) |
| app.services.seo_i18n._WORLD_CATEGORY_EN_EXTRA | Dict | 'Общество', 'Прочее', 'Национальные счета', 'Статистика', 'Государственные финансы', 'Бизнес и инвестиции', 'Внешняя торговля', 'разделе' | [backend/app/services/seo_i18n.py:86](../backend/app/services/seo_i18n.py#L86) |
| app.services.seo_i18n._RU_MONTH_TO_EN | Dict | 'января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря', 'январь', 'февраль', 'март', 'апрель', 'май', 'июнь', 'июль', 'август', 'сентябрь', 'октябрь', 'ноябрь', 'декабрь' | [backend/app/services/seo_i18n.py:299](../backend/app/services/seo_i18n.py#L299) |
| app.services.seo_indicator_month._EN_MONTHS | Tuple | sequence/source expression | [backend/app/services/seo_indicator_month.py:50](../backend/app/services/seo_indicator_month.py#L50) |
| app.services.seo_regional.MACRO_BY_TABLE | Dict | '1.1', '3.4', '2.10.1', '20.1', '8.1', '10.1', '16.20', '16.21', '16.22' | [backend/app/services/seo_regional.py:49](../backend/app/services/seo_regional.py#L49) |
| app.services.seo_regional._MONTH_NAMES_GEN | Tuple | sequence/source expression | [backend/app/services/seo_regional.py:1281](../backend/app/services/seo_regional.py#L1281) |
| app.services.seo_regional_year._ALLOWED_REGION_KINDS | Tuple | sequence/source expression | [backend/app/services/seo_regional_year.py:64](../backend/app/services/seo_regional_year.py#L64) |
| app.services.seo_regional_year._YEAR_TEMPLATES_EN | Dict | 'h1', 'alt', 'caption', 'desc_main', 'change_vs', 'change_vs_pct', 'rf_h2', 'rf_para', 'rf_note', 'rank_h2', 'rank_full_link', 'rank_sentence', 'dyn_h2_by_year', 'dyn_h2_neighbors', 'checkpoints_h2', 'checkpoint_item', 'decade_h2', 'cta_h2', 'cta_link', 'cta_p', 'other_years_h2', 'other_year_link', 'trail_last', 'rank_desc', 'rank_desc_none', 'jsonld_name', 'keywords' | [backend/app/services/seo_regional_year.py:74](../backend/app/services/seo_regional_year.py#L74) |
| app.services.seo_renderer.FREQUENCY_LABELS_RU | Dict | 'daily', 'weekly', 'monthly', 'quarterly', 'annual', 'yearly' | [backend/app/services/seo_renderer.py:889](../backend/app/services/seo_renderer.py#L889) |
| app.services.seo_renderer.FREQUENCY_LABELS_EN | Dict | 'daily', 'weekly', 'monthly', 'quarterly', 'annual', 'yearly' | [backend/app/services/seo_renderer.py:898](../backend/app/services/seo_renderer.py#L898) |
| app.services.seo_renderer.FLAGSHIP_CODES | Call | computed source expression | [backend/app/services/seo_renderer.py:907](../backend/app/services/seo_renderer.py#L907) |
| app.services.seo_renderer.YANDEX_VERIFICATION_CODES | Tuple | sequence/source expression | [backend/app/services/seo_renderer.py:998](../backend/app/services/seo_renderer.py#L998) |
| app.services.seo_renderer.AUTOLINK_TERMS | Tuple | sequence/source expression | [backend/app/services/seo_renderer.py:1406](../backend/app/services/seo_renderer.py#L1406) |
| app.services.seo_renderer.HOME_FLAGSHIP_CODES_EN | Tuple | sequence/source expression | [backend/app/services/seo_renderer.py:1578](../backend/app/services/seo_renderer.py#L1578) |
| app.services.seo_renderer._SSR_VS_COUNTRY_LABELS | Dict | 'germany', 'united-states', 'france', 'china', 'japan', 'russia' | [backend/app/services/seo_renderer.py:3024](../backend/app/services/seo_renderer.py#L3024) |
| app.services.seo_today._MONTHS_GEN | Tuple | sequence/source expression | [backend/app/services/seo_today.py:49](../backend/app/services/seo_today.py#L49) |
| app.services.seo_today._STALE_AFTER_DAYS | Dict | 'daily', 'weekly', 'monthly', 'quarterly', 'annual' | [backend/app/services/seo_today.py:95](../backend/app/services/seo_today.py#L95) |
| app.services.seo_today.TODAY_SPECS | DictComp | computed source expression | [backend/app/services/seo_today.py:127](../backend/app/services/seo_today.py#L127) |
| app.services.seo_today.TODAY_CODES | Call | computed source expression | [backend/app/services/seo_today.py:141](../backend/app/services/seo_today.py#L141) |
| app.services.seo_world._WORLD_HEAVY_TEXT_COLUMNS | Tuple | sequence/source expression | [backend/app/services/seo_world.py:73](../backend/app/services/seo_world.py#L73) |
| app.services.seo_world._WORLD_RATING_LOW_FIRST | Call | computed source expression | [backend/app/services/seo_world.py:90](../backend/app/services/seo_world.py#L90) |
| app.services.seo_world._WORLD_RATING_MONEY_CONCEPTS | Call | computed source expression | [backend/app/services/seo_world.py:91](../backend/app/services/seo_world.py#L91) |
| app.services.seo_world.COUNTRY_GENITIVE | Dict | 'austria', 'belgium', 'bulgaria', 'croatia', 'cyprus', 'czechia', 'denmark', 'estonia', 'finland', 'france', 'germany', 'greece', 'hungary', 'ireland', 'italy', 'latvia', 'lithuania', 'luxembourg', 'malta', 'netherlands', 'poland', 'portugal', 'romania', 'slovakia', 'slovenia', 'spain', 'sweden', 'iceland', 'norway', 'switzerland', 'united-kingdom', 'turkey', 'serbia', 'montenegro', 'north-macedonia', 'albania', 'bosnia', 'kosovo', 'ukraine', 'moldova', 'georgia', 'armenia', 'azerbaijan', 'united-states', 'canada', 'japan', 'south-korea', 'china', 'india', 'brazil', 'mexico', 'australia', 'new-zealand', 'south-africa', 'israel' | [backend/app/services/seo_world.py:102](../backend/app/services/seo_world.py#L102) |
| app.services.seo_world._FREQ_RU | Dict | 'monthly', 'quarterly', 'annual', 'daily', 'weekly' | [backend/app/services/seo_world.py:197](../backend/app/services/seo_world.py#L197) |
| app.services.seo_world._FREQ_EN | Dict | 'monthly', 'quarterly', 'annual', 'daily', 'weekly' | [backend/app/services/seo_world.py:205](../backend/app/services/seo_world.py#L205) |
| app.services.seo_world._KEY_CATEGORY_ORDER | Tuple | sequence/source expression | [backend/app/services/seo_world.py:214](../backend/app/services/seo_world.py#L214) |
| app.services.seo_world._FREQ_LINK_LABEL_RU | Dict | 'monthly', 'quarterly', 'annual', 'weekly', 'daily' | [backend/app/services/seo_world.py:291](../backend/app/services/seo_world.py#L291) |
| app.services.seo_world._FREQ_LINK_LABEL_EN | Dict | 'monthly', 'quarterly', 'annual', 'weekly', 'daily' | [backend/app/services/seo_world.py:299](../backend/app/services/seo_world.py#L299) |
| app.services.seo_world._SOURCE_BY_PROVIDER | Dict | 'eurostat', 'statcan', 'boc_valet', 'abs', 'rba', 'ons', 'boe_iadb', 'fred', 'bls', 'bea', 'boj', 'estat', 'ecos', 'bcb_sgs', 'banxico_sie', 'nbs', 'cfets', 'mospi', 'rbi', 'imf', 'census', 'ibge' | [backend/app/services/seo_world.py:399](../backend/app/services/seo_world.py#L399) |
| app.services.seo_world._PROVIDER_OPEN_LABEL | DictComp | computed source expression | [backend/app/services/seo_world.py:493](../backend/app/services/seo_world.py#L493) |
| app.services.seo_world_subnational._NOT_FOUND | Tuple | sequence/source expression | [backend/app/services/seo_world_subnational.py:37](../backend/app/services/seo_world_subnational.py#L37) |
| app.services.site_paths.RESERVED_FIRST_SEGMENTS | Call | computed source expression | [backend/app/services/site_paths.py:57](../backend/app/services/site_paths.py#L57) |
| app.services.site_paths._CURRENCY_BASE_CODES | Tuple | sequence/source expression | [backend/app/services/site_paths.py:151](../backend/app/services/site_paths.py#L151) |
| app.services.site_urls._STATIC_WITHOUT_DATA_LASTMOD | Call | computed source expression | [backend/app/services/site_urls.py:82](../backend/app/services/site_urls.py#L82) |
| app.services.site_urls.SITEMAP_LASTMOD_MIN | Call | computed source expression | [backend/app/services/site_urls.py:96](../backend/app/services/site_urls.py#L96) |
| app.services.site_urls._W3C_LASTMOD | Call | computed source expression | [backend/app/services/site_urls.py:98](../backend/app/services/site_urls.py#L98) |
| app.services.site_urls._PUBLIC_REGION_KINDS | Tuple | sequence/source expression | [backend/app/services/site_urls.py:107](../backend/app/services/site_urls.py#L107) |
| app.services.site_urls._REGIONAL_PAIR_DATA | Call | computed source expression | [backend/app/services/site_urls.py:439](../backend/app/services/site_urls.py#L439) |
| app.services.site_urls._REG_PAIRS_COUNT | Call | computed source expression | [backend/app/services/site_urls.py:1763](../backend/app/services/site_urls.py#L1763) |
| app.services.site_urls._REG_YEARS_COUNT | Call | computed source expression | [backend/app/services/site_urls.py:1765](../backend/app/services/site_urls.py#L1765) |
| app.services.site_urls._WORLD_CARDS_COUNT | Call | computed source expression | [backend/app/services/site_urls.py:1777](../backend/app/services/site_urls.py#L1777) |
| app.services.site_urls._WORLD_YEARS_COUNT | Call | computed source expression | [backend/app/services/site_urls.py:1786](../backend/app/services/site_urls.py#L1786) |
| app.services.site_urls._SIMPLE_SECTION_ORDER | List | sequence/source expression | [backend/app/services/site_urls.py:1796](../backend/app/services/site_urls.py#L1796) |
| app.services.site_urls._CHUNKED_SOURCES | Dict | 'months-', 'world-indicators-', 'regional-', 'regional-years-', 'world-years-', 'world-region-years-' | [backend/app/services/site_urls.py:1891](../backend/app/services/site_urls.py#L1891) |
| app.services.site_urls._SIMPLE_SECTION_BUILDERS | Dict | 'core', 'today', 'ratings', 'maps', 'regions', 'region-vs', 'world-ratings', 'world', 'world-regions', 'world-region-vs', 'calendar', 'world-vs', 'years' | [backend/app/services/site_urls.py:1932](../backend/app/services/site_urls.py#L1932) |
| app.services.site_urls.SECTION_BUILDERS | Dict | sequence/source expression | [backend/app/services/site_urls.py:1985](../backend/app/services/site_urls.py#L1985) |
| app.services.sitemap_images._SEGMENT | Call | computed source expression | [backend/app/services/sitemap_images.py:16](../backend/app/services/sitemap_images.py#L16) |
| app.services.sitemap_images._WORLD_CODE | Call | computed source expression | [backend/app/services/sitemap_images.py:17](../backend/app/services/sitemap_images.py#L17) |
| app.services.sitemap_static._GENERATION | Call | computed source expression | [backend/app/services/sitemap_static.py:35](../backend/app/services/sitemap_static.py#L35) |
| app.services.sitemap_static._SECTION | Call | computed source expression | [backend/app/services/sitemap_static.py:36](../backend/app/services/sitemap_static.py#L36) |
| app.services.sitemap_static._LOC | Call | computed source expression | [backend/app/services/sitemap_static.py:107](../backend/app/services/sitemap_static.py#L107) |
| app.services.telegram_bot._BLOCKQUOTE_RE | Call | computed source expression | [backend/app/services/telegram_bot.py:89](../backend/app/services/telegram_bot.py#L89) |
| app.services.telegram_bot._BLOCKQUOTE_OPEN_RE | Call | computed source expression | [backend/app/services/telegram_bot.py:90](../backend/app/services/telegram_bot.py#L90) |
| app.services.ticker_sources.binance._HOSTS | List | sequence/source expression | [backend/app/services/ticker_sources/binance.py:26](../backend/app/services/ticker_sources/binance.py#L26) |
| app.services.ticker_sources.moex_iss._FX_INSTRUMENTS | List | sequence/source expression | [backend/app/services/ticker_sources/moex_iss.py:48](../backend/app/services/ticker_sources/moex_iss.py#L48) |
| app.services.traffic_channel._SEARCH_HOSTS | Tuple | sequence/source expression | [backend/app/services/traffic_channel.py:24](../backend/app/services/traffic_channel.py#L24) |
| app.services.traffic_channel._YANDEX_SERVICE_PREFIXES | Tuple | sequence/source expression | [backend/app/services/traffic_channel.py:29](../backend/app/services/traffic_channel.py#L29) |
| app.services.traffic_channel._NOT_SEARCH_HOSTS | Tuple | sequence/source expression | [backend/app/services/traffic_channel.py:44](../backend/app/services/traffic_channel.py#L44) |
| app.services.traffic_channel._ASSISTANT_HOSTS | Tuple | sequence/source expression | [backend/app/services/traffic_channel.py:54](../backend/app/services/traffic_channel.py#L54) |
| app.services.traffic_channel._ASSISTANT_UTM | Dict | 'chatgpt.com', 'openai', 'chat.openai.com', 'perplexity', 'perplexity.ai' | [backend/app/services/traffic_channel.py:65](../backend/app/services/traffic_channel.py#L65) |
| app.services.traffic_channel._SOCIAL_HOSTS | Tuple | sequence/source expression | [backend/app/services/traffic_channel.py:72](../backend/app/services/traffic_channel.py#L72) |
| app.services.traffic_channel._OWN_HOSTS | Tuple | sequence/source expression | [backend/app/services/traffic_channel.py:77](../backend/app/services/traffic_channel.py#L77) |
| app.services.traffic_channel._AD_MEDIUMS | Set | sequence/source expression | [backend/app/services/traffic_channel.py:78](../backend/app/services/traffic_channel.py#L78) |
| app.services.traffic_channel.CHANNELS | Tuple | sequence/source expression | [backend/app/services/traffic_channel.py:80](../backend/app/services/traffic_channel.py#L80) |
| app.services.traffic_channel._ENGINE_NAMES | Tuple | sequence/source expression | [backend/app/services/traffic_channel.py:84](../backend/app/services/traffic_channel.py#L84) |
| app.services.ua_parser._BROWSERS | List | sequence/source expression | [backend/app/services/ua_parser.py:14](../backend/app/services/ua_parser.py#L14) |
| app.services.ua_parser._BOT_RE | Call | computed source expression | [backend/app/services/ua_parser.py:25](../backend/app/services/ua_parser.py#L25) |
| app.services.ua_parser._OSES | List | sequence/source expression | [backend/app/services/ua_parser.py:30](../backend/app/services/ua_parser.py#L30) |
| app.services.ua_parser._OS_VERSION | Dict | 'Windows', 'macOS', 'iOS', 'Android' | [backend/app/services/ua_parser.py:40](../backend/app/services/ua_parser.py#L40) |
| app.services.ua_parser._WINDOWS_NAMES | Dict | '10.0', '6.3', '6.2', '6.1' | [backend/app/services/ua_parser.py:48](../backend/app/services/ua_parser.py#L48) |
| app.services.us_pop_adapter.NATIONAL_ROWS_URLS | Tuple | sequence/source expression | [backend/app/services/us_pop_adapter.py:94](../backend/app/services/us_pop_adapter.py#L94) |
| app.services.world_adapters._SESSION_ATTRS | Tuple | sequence/source expression | [backend/app/services/world_adapters/__init__.py:9](../backend/app/services/world_adapters/__init__.py#L9) |
| app.services.world_adapters.abs_data._DEFAULT_DATE_FROM | Call | computed source expression | [backend/app/services/world_adapters/abs_data.py:54](../backend/app/services/world_adapters/abs_data.py#L54) |
| app.services.world_adapters.abs_data.FREQ_CODE_MAP | Dict | 'A', 'Y', 'Q', 'M', 'W', 'D', 'B', 'S', 'H' | [backend/app/services/world_adapters/abs_data.py:57](../backend/app/services/world_adapters/abs_data.py#L57) |
| app.services.world_adapters.abs_data._PERIOD_QUARTER | Call | computed source expression | [backend/app/services/world_adapters/abs_data.py:69](../backend/app/services/world_adapters/abs_data.py#L69) |
| app.services.world_adapters.abs_data._PERIOD_MONTH | Call | computed source expression | [backend/app/services/world_adapters/abs_data.py:70](../backend/app/services/world_adapters/abs_data.py#L70) |
| app.services.world_adapters.abs_data._PERIOD_YEAR | Call | computed source expression | [backend/app/services/world_adapters/abs_data.py:71](../backend/app/services/world_adapters/abs_data.py#L71) |
| app.services.world_adapters.abs_data._PERIOD_SEMESTER | Call | computed source expression | [backend/app/services/world_adapters/abs_data.py:72](../backend/app/services/world_adapters/abs_data.py#L72) |
| app.services.world_adapters.abs_data._PERIOD_WEEK | Call | computed source expression | [backend/app/services/world_adapters/abs_data.py:73](../backend/app/services/world_adapters/abs_data.py#L73) |
| app.services.world_adapters.abs_data.DEFAULT_ABS_SERIES | Tuple | sequence/source expression | [backend/app/services/world_adapters/abs_data.py:108](../backend/app/services/world_adapters/abs_data.py#L108) |
| app.services.world_adapters.banxico_sie._DEFAULT_DATE_FROM | Call | computed source expression | [backend/app/services/world_adapters/banxico_sie.py:55](../backend/app/services/world_adapters/banxico_sie.py#L55) |
| app.services.world_adapters.banxico_sie._MISSING | Set | sequence/source expression | [backend/app/services/world_adapters/banxico_sie.py:56](../backend/app/services/world_adapters/banxico_sie.py#L56) |
| app.services.world_adapters.banxico_sie.DEFAULT_BANXICO_SERIES | Tuple | sequence/source expression | [backend/app/services/world_adapters/banxico_sie.py:76](../backend/app/services/world_adapters/banxico_sie.py#L76) |
| app.services.world_adapters.bcb_sgs._DEFAULT_DATE_FROM | Call | computed source expression | [backend/app/services/world_adapters/bcb_sgs.py:53](../backend/app/services/world_adapters/bcb_sgs.py#L53) |
| app.services.world_adapters.bcb_sgs.DEFAULT_BCB_SERIES | Tuple | sequence/source expression | [backend/app/services/world_adapters/bcb_sgs.py:90](../backend/app/services/world_adapters/bcb_sgs.py#L90) |
| app.services.world_adapters.bea_api.DEFAULT_BEA_SERIES | Tuple | sequence/source expression | [backend/app/services/world_adapters/bea_api.py:74](../backend/app/services/world_adapters/bea_api.py#L74) |
| app.services.world_adapters.bls_api.DEFAULT_BLS_SERIES | Tuple | sequence/source expression | [backend/app/services/world_adapters/bls_api.py:61](../backend/app/services/world_adapters/bls_api.py#L61) |
| app.services.world_adapters.boc_valet._DEFAULT_DATE_FROM | Call | computed source expression | [backend/app/services/world_adapters/boc_valet.py:49](../backend/app/services/world_adapters/boc_valet.py#L49) |
| app.services.world_adapters.boc_valet.DEFAULT_BOC_SERIES | Tuple | sequence/source expression | [backend/app/services/world_adapters/boc_valet.py:70](../backend/app/services/world_adapters/boc_valet.py#L70) |
| app.services.world_adapters.boe_iadb._DEFAULT_DATE_FROM | Call | computed source expression | [backend/app/services/world_adapters/boe_iadb.py:56](../backend/app/services/world_adapters/boe_iadb.py#L56) |
| app.services.world_adapters.boe_iadb._FALLBACK_DATE_FROM | Tuple | sequence/source expression | [backend/app/services/world_adapters/boe_iadb.py:57](../backend/app/services/world_adapters/boe_iadb.py#L57) |
| app.services.world_adapters.boe_iadb._MONTH_ABBR | Dict | 'jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec' | [backend/app/services/world_adapters/boe_iadb.py:65](../backend/app/services/world_adapters/boe_iadb.py#L65) |
| app.services.world_adapters.boe_iadb._DMY_MON | Call | computed source expression | [backend/app/services/world_adapters/boe_iadb.py:80](../backend/app/services/world_adapters/boe_iadb.py#L80) |
| app.services.world_adapters.boe_iadb._DMY_SLASH | Call | computed source expression | [backend/app/services/world_adapters/boe_iadb.py:81](../backend/app/services/world_adapters/boe_iadb.py#L81) |
| app.services.world_adapters.boe_iadb.DEFAULT_BOE_SERIES | Tuple | sequence/source expression | [backend/app/services/world_adapters/boe_iadb.py:101](../backend/app/services/world_adapters/boe_iadb.py#L101) |
| app.services.world_adapters.boj_stat._DEFAULT_DATE_FROM | Call | computed source expression | [backend/app/services/world_adapters/boj_stat.py:40](../backend/app/services/world_adapters/boj_stat.py#L40) |
| app.services.world_adapters.boj_stat.DEFAULT_BOJ_SERIES | Tuple | sequence/source expression | [backend/app/services/world_adapters/boj_stat.py:62](../backend/app/services/world_adapters/boj_stat.py#L62) |
| app.services.world_adapters.cfets_chinamoney._DEFAULT_DATE_FROM | Call | computed source expression | [backend/app/services/world_adapters/cfets_chinamoney.py:50](../backend/app/services/world_adapters/cfets_chinamoney.py#L50) |
| app.services.world_adapters.cfets_chinamoney._ENDPOINT_BY_DATASET | Dict | 'ccpr', 'lpr', 'shibor' | [backend/app/services/world_adapters/cfets_chinamoney.py:58](../backend/app/services/world_adapters/cfets_chinamoney.py#L58) |
| app.services.world_adapters.cfets_chinamoney.DEFAULT_CFETS_SERIES | Tuple | sequence/source expression | [backend/app/services/world_adapters/cfets_chinamoney.py:80](../backend/app/services/world_adapters/cfets_chinamoney.py#L80) |
| app.services.world_adapters.ecos_bok._DEFAULT_DATE_FROM | Call | computed source expression | [backend/app/services/world_adapters/ecos_bok.py:44](../backend/app/services/world_adapters/ecos_bok.py#L44) |
| app.services.world_adapters.ecos_bok.DEFAULT_ECOS_SERIES | Tuple | sequence/source expression | [backend/app/services/world_adapters/ecos_bok.py:65](../backend/app/services/world_adapters/ecos_bok.py#L65) |
| app.services.world_adapters.estat_api._DEFAULT_DATE_FROM | Call | computed source expression | [backend/app/services/world_adapters/estat_api.py:43](../backend/app/services/world_adapters/estat_api.py#L43) |
| app.services.world_adapters.estat_api._TIME_RE | Call | computed source expression | [backend/app/services/world_adapters/estat_api.py:45](../backend/app/services/world_adapters/estat_api.py#L45) |
| app.services.world_adapters.estat_api.DEFAULT_ESTAT_SERIES | Tuple | sequence/source expression | [backend/app/services/world_adapters/estat_api.py:69](../backend/app/services/world_adapters/estat_api.py#L69) |
| app.services.world_adapters.fred_stlouis._DEFAULT_DATE_FROM | Call | computed source expression | [backend/app/services/world_adapters/fred_stlouis.py:50](../backend/app/services/world_adapters/fred_stlouis.py#L50) |
| app.services.world_adapters.fred_stlouis.DEFAULT_FRED_SERIES | Tuple | sequence/source expression | [backend/app/services/world_adapters/fred_stlouis.py:71](../backend/app/services/world_adapters/fred_stlouis.py#L71) |
| app.services.world_adapters.mospi_api._MONTH_NAME_TO_NUM | Dict | 'january', 'february', 'march', 'april', 'may', 'june', 'july', 'august', 'september', 'october', 'november', 'december', 'jan', 'feb', 'mar', 'apr', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec' | [backend/app/services/world_adapters/mospi_api.py:46](../backend/app/services/world_adapters/mospi_api.py#L46) |
| app.services.world_adapters.mospi_api._QUARTER_TO_MONTH | Dict | 'Q1', 'Q2', 'Q3', 'Q4', '1', '2', '3', '4' | [backend/app/services/world_adapters/mospi_api.py:72](../backend/app/services/world_adapters/mospi_api.py#L72) |
| app.services.world_adapters.mospi_api.DEFAULT_MOSPI_SERIES | Tuple | sequence/source expression | [backend/app/services/world_adapters/mospi_api.py:111](../backend/app/services/world_adapters/mospi_api.py#L111) |
| app.services.world_adapters.nbs_stats._PERIOD_MONTH | Call | computed source expression | [backend/app/services/world_adapters/nbs_stats.py:72](../backend/app/services/world_adapters/nbs_stats.py#L72) |
| app.services.world_adapters.nbs_stats._PERIOD_QUARTER | Call | computed source expression | [backend/app/services/world_adapters/nbs_stats.py:73](../backend/app/services/world_adapters/nbs_stats.py#L73) |
| app.services.world_adapters.nbs_stats._PERIOD_YEAR | Call | computed source expression | [backend/app/services/world_adapters/nbs_stats.py:74](../backend/app/services/world_adapters/nbs_stats.py#L74) |
| app.services.world_adapters.nbs_stats._STREAM_CODE | Call | computed source expression | [backend/app/services/world_adapters/nbs_stats.py:75](../backend/app/services/world_adapters/nbs_stats.py#L75) |
| app.services.world_adapters.nbs_stats._DBCODE_FREQ | Dict | 'hgyd', 'hgjd', 'hgnd' | [backend/app/services/world_adapters/nbs_stats.py:77](../backend/app/services/world_adapters/nbs_stats.py#L77) |
| app.services.world_adapters.nbs_stats.STREAM_SERIES | Dict | 'A01010G01', 'cpi-all', 'A01030101', 'UNEMPLOYMENT', 'A0E0101', 'urban-unemployment', 'GDP_REAL_Q', 'A0101', 'gdp-real' | [backend/app/services/world_adapters/nbs_stats.py:85](../backend/app/services/world_adapters/nbs_stats.py#L85) |
| app.services.world_adapters.nbs_stats.DEFAULT_NBS_SERIES | Tuple | sequence/source expression | [backend/app/services/world_adapters/nbs_stats.py:165](../backend/app/services/world_adapters/nbs_stats.py#L165) |
| app.services.world_adapters.ons_timeseries._MONTH_NAME | Dict | 'jan', 'january', 'feb', 'february', 'mar', 'march', 'apr', 'april', 'may', 'jun', 'june', 'jul', 'july', 'aug', 'august', 'sep', 'sept', 'september', 'oct', 'october', 'nov', 'november', 'dec', 'december' | [backend/app/services/world_adapters/ons_timeseries.py:43](../backend/app/services/world_adapters/ons_timeseries.py#L43) |
| app.services.world_adapters.ons_timeseries._PERIOD_QUARTER | Call | computed source expression | [backend/app/services/world_adapters/ons_timeseries.py:70](../backend/app/services/world_adapters/ons_timeseries.py#L70) |
| app.services.world_adapters.ons_timeseries._PERIOD_YEAR | Call | computed source expression | [backend/app/services/world_adapters/ons_timeseries.py:71](../backend/app/services/world_adapters/ons_timeseries.py#L71) |
| app.services.world_adapters.ons_timeseries._PERIOD_MONTH_TOKEN | Call | computed source expression | [backend/app/services/world_adapters/ons_timeseries.py:72](../backend/app/services/world_adapters/ons_timeseries.py#L72) |
| app.services.world_adapters.ons_timeseries.DEFAULT_ONS_SERIES | Tuple | sequence/source expression | [backend/app/services/world_adapters/ons_timeseries.py:102](../backend/app/services/world_adapters/ons_timeseries.py#L102) |
| app.services.world_adapters.rba_stats._DEFAULT_DATE_FROM | Call | computed source expression | [backend/app/services/world_adapters/rba_stats.py:49](../backend/app/services/world_adapters/rba_stats.py#L49) |
| app.services.world_adapters.rba_stats._KNOWN_CSV_FILENAMES | Dict | 'F1', 'F1.1', 'F11', 'F11.1' | [backend/app/services/world_adapters/rba_stats.py:58](../backend/app/services/world_adapters/rba_stats.py#L58) |
| app.services.world_adapters.rba_stats._MONTH_ABBR | Dict | 'jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec' | [backend/app/services/world_adapters/rba_stats.py:65](../backend/app/services/world_adapters/rba_stats.py#L65) |
| app.services.world_adapters.rba_stats._LABEL_TO_FIELD | Dict | 'title', 'description', 'frequency', 'type', 'units', 'source', 'publication date', 'series id', 'mnemonic' | [backend/app/services/world_adapters/rba_stats.py:80](../backend/app/services/world_adapters/rba_stats.py#L80) |
| app.services.world_adapters.rba_stats._DMY_SLASH | Call | computed source expression | [backend/app/services/world_adapters/rba_stats.py:92](../backend/app/services/world_adapters/rba_stats.py#L92) |
| app.services.world_adapters.rba_stats._DMY_MON | Call | computed source expression | [backend/app/services/world_adapters/rba_stats.py:93](../backend/app/services/world_adapters/rba_stats.py#L93) |
| app.services.world_adapters.rba_stats.DEFAULT_RBA_SERIES | Tuple | sequence/source expression | [backend/app/services/world_adapters/rba_stats.py:115](../backend/app/services/world_adapters/rba_stats.py#L115) |
| app.services.world_adapters.rbi_rates._REPO_CANDIDATE_URLS | Tuple | sequence/source expression | [backend/app/services/world_adapters/rbi_rates.py:51](../backend/app/services/world_adapters/rbi_rates.py#L51) |
| app.services.world_adapters.rbi_rates._REPO_ROW_RE | Call | computed source expression | [backend/app/services/world_adapters/rbi_rates.py:57](../backend/app/services/world_adapters/rbi_rates.py#L57) |
| app.services.world_adapters.rbi_rates.DEFAULT_RBI_SERIES | Tuple | sequence/source expression | [backend/app/services/world_adapters/rbi_rates.py:80](../backend/app/services/world_adapters/rbi_rates.py#L80) |
| app.services.world_adapters.statcan_wds._DEFAULT_DATE_FROM | Call | computed source expression | [backend/app/services/world_adapters/statcan_wds.py:56](../backend/app/services/world_adapters/statcan_wds.py#L56) |
| app.services.world_adapters.statcan_wds.FREQUENCY_CODE_MAP | Dict | 1, 2, 4, 6, 7, 9, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21 | [backend/app/services/world_adapters/statcan_wds.py:59](../backend/app/services/world_adapters/statcan_wds.py#L59) |
| app.services.world_bank_pink_sheet_parser._MONTHLY_XLSX_RE | Call | computed source expression | [backend/app/services/world_bank_pink_sheet_parser.py:43](../backend/app/services/world_bank_pink_sheet_parser.py#L43) |
| app.services.world_bank_pink_sheet_parser._PERIOD_RE | Call | computed source expression | [backend/app/services/world_bank_pink_sheet_parser.py:47](../backend/app/services/world_bank_pink_sheet_parser.py#L47) |
| app.services.world_bank_pink_sheet_parser._MISSING | Set | sequence/source expression | [backend/app/services/world_bank_pink_sheet_parser.py:48](../backend/app/services/world_bank_pink_sheet_parser.py#L48) |
| app.services.world_bea_regional.TABLES_BY_ARCHIVE | Dict | 'SAGDP', 'SAINC', 'SQGDP', 'SQINC', 'SAPCE', 'SARPP', 'SASUMMARY' | [backend/app/services/world_bea_regional.py:47](../backend/app/services/world_bea_regional.py#L47) |
| app.services.world_bea_regional._PERIOD | Call | computed source expression | [backend/app/services/world_bea_regional.py:57](../backend/app/services/world_bea_regional.py#L57) |
| app.services.world_bea_regional._FOOTNOTE | Call | computed source expression | [backend/app/services/world_bea_regional.py:58](../backend/app/services/world_bea_regional.py#L58) |
| app.services.world_cards.MODE_TYPES | Tuple | sequence/source expression | [backend/app/services/world_cards.py:38](../backend/app/services/world_cards.py#L38) |
| app.services.world_cards.MODE_FREQS | Tuple | sequence/source expression | [backend/app/services/world_cards.py:39](../backend/app/services/world_cards.py#L39) |
| app.services.world_cards.HIGH_FREQS | Tuple | sequence/source expression | [backend/app/services/world_cards.py:40](../backend/app/services/world_cards.py#L40) |
| app.services.world_cards.ALL_FREQS | Tuple | sequence/source expression | [backend/app/services/world_cards.py:41](../backend/app/services/world_cards.py#L41) |
| app.services.world_cards._FORECAST_SOURCE_FREQS | Call | computed source expression | [backend/app/services/world_cards.py:42](../backend/app/services/world_cards.py#L42) |
| app.services.world_cards.TYPE_GROUP | Dict | 'level', 'step', 'yoy', 'yoyabs', 'index' | [backend/app/services/world_cards.py:44](../backend/app/services/world_cards.py#L44) |
| app.services.world_cards.FREQ_LABEL | Dict | 'daily', 'weekly', 'monthly', 'quarterly', 'annual' | [backend/app/services/world_cards.py:52](../backend/app/services/world_cards.py#L52) |
| app.services.world_cards.STEP_LABEL | Dict | 'daily', 'weekly', 'monthly', 'quarterly', 'annual' | [backend/app/services/world_cards.py:60](../backend/app/services/world_cards.py#L60) |
| app.services.world_cards._LEGACY_TO_COMPOSITE | Dict | 'level', 'mom', 'qoq', 'yoy', 'yoy_abs', 'index_first', 'avg_quarter', 'avg_year' | [backend/app/services/world_cards.py:69](../backend/app/services/world_cards.py#L69) |
| app.services.world_compare.MONEY_COMPARE_CONCEPTS | Call | computed source expression | [backend/app/services/world_compare.py:39](../backend/app/services/world_compare.py#L39) |
| app.services.world_compare._COMPARE_VIEW_SPEC | Dict | 'hicp-index', 'unemployment-rate', 'population', 'gdp-usd', 'gdp-per-capita-usd', 'budget-balance-gdp', 'government-debt-gdp' | [backend/app/services/world_compare.py:48](../backend/app/services/world_compare.py#L48) |
| app.services.world_compare._SSR_VS_COUNTRIES | Tuple | sequence/source expression | [backend/app/services/world_compare.py:90](../backend/app/services/world_compare.py#L90) |
| app.services.world_eurostat_ingest.LOADER_FREQUENCIES | Tuple | sequence/source expression | [backend/app/services/world_eurostat_ingest.py:48](../backend/app/services/world_eurostat_ingest.py#L48) |
| app.services.world_eurostat_ingest._VERDICT_RE | Call | computed source expression | [backend/app/services/world_eurostat_ingest.py:295](../backend/app/services/world_eurostat_ingest.py#L295) |
| app.services.world_forecast_pipeline.WORLD_FORECAST_CACHE_NAMESPACES | Tuple | sequence/source expression | [backend/app/services/world_forecast_pipeline.py:48](../backend/app/services/world_forecast_pipeline.py#L48) |
| app.services.world_forecast_pipeline._FREQ_RANK | Dict | 'monthly', 'quarterly', 'annual' | [backend/app/services/world_forecast_pipeline.py:52](../backend/app/services/world_forecast_pipeline.py#L52) |
| app.services.world_forecaster.PUBLISHED_GATE_STATUSES | Call | computed source expression | [backend/app/services/world_forecaster.py:22](../backend/app/services/world_forecaster.py#L22) |
| app.services.world_national_ingest.PUBLIC_SOURCE_RU | Dict | 'statcan', 'boc_valet', 'abs', 'rba', 'ons', 'boe_iadb', 'fred', 'bls', 'bea', 'boj', 'estat', 'ecos', 'bcb_sgs', 'banxico_sie', 'nbs', 'cfets', 'mospi', 'rbi' | [backend/app/services/world_national_ingest.py:47](../backend/app/services/world_national_ingest.py#L47) |
| app.services.world_national_ingest._ADAPTER_MODULES | Dict | 'statcan', 'boc_valet', 'abs', 'rba', 'ons', 'boe_iadb', 'fred', 'bls', 'bea', 'boj', 'estat', 'ecos', 'bcb_sgs', 'banxico_sie', 'nbs', 'cfets', 'mospi', 'rbi' | [backend/app/services/world_national_ingest.py:75](../backend/app/services/world_national_ingest.py#L75) |
| app.services.world_national_ingest._FREQ_ALIASES | Dict | 'm', 'q', 'a', 'y', 'yearly', 'd', 'w', 'monthly', 'quarterly', 'annual', 'daily', 'weekly' | [backend/app/services/world_national_ingest.py:96](../backend/app/services/world_national_ingest.py#L96) |
| app.services.world_national_ingest._FREQ_ADJ_RU | Dict | 'monthly', 'quarterly', 'annual', 'weekly', 'daily' | [backend/app/services/world_national_ingest.py:111](../backend/app/services/world_national_ingest.py#L111) |
| app.services.world_national_ingest._CODE_RE | Call | computed source expression | [backend/app/services/world_national_ingest.py:119](../backend/app/services/world_national_ingest.py#L119) |
| app.services.world_national_ingest._COUNTRY_DEFAULTS | Dict | 'CA', 'AU', 'UK', 'US', 'JP', 'KR', 'BR', 'MX', 'CN', 'IN' | [backend/app/services/world_national_ingest.py:950](../backend/app/services/world_national_ingest.py#L950) |
| app.services.world_national_ingest.NATIONAL_CORE_COUNTRIES | Tuple | sequence/source expression | [backend/app/services/world_national_ingest.py:1133](../backend/app/services/world_national_ingest.py#L1133) |
| app.services.world_rank_values._FORCE_YOY_CONCEPTS | Call | computed source expression | [backend/app/services/world_rank_values.py:48](../backend/app/services/world_rank_values.py#L48) |
| app.services.world_rank_values._FLOW_RANK_CONCEPTS | Call | computed source expression | [backend/app/services/world_rank_values.py:57](../backend/app/services/world_rank_values.py#L57) |
| app.services.world_rank_values.WORLD_RATING_QUERY_NAMES | Dict | 'hicp-index', 'unemployment-rate', 'budget-balance-gdp', 'government-debt-gdp', 'population', 'long-term-interest-rate', 'activity-rate', 'gdp-per-capita-eu', 'gdp-usd', 'gdp-per-capita-usd' | [backend/app/services/world_rank_values.py:236](../backend/app/services/world_rank_values.py#L236) |
| app.services.world_rank_values.WORLD_RATING_QUERY_NAMES_EN | Dict | 'hicp-index', 'unemployment-rate', 'budget-balance-gdp', 'government-debt-gdp', 'population', 'long-term-interest-rate', 'activity-rate', 'gdp-per-capita-eu', 'gdp-usd', 'gdp-per-capita-usd' | [backend/app/services/world_rank_values.py:250](../backend/app/services/world_rank_values.py#L250) |
| app.services.world_rank_values._WORLD_REGION_EN | Dict | 'Европа', 'Азия', 'Америка', 'Африка', 'Океания' | [backend/app/services/world_rank_values.py:263](../backend/app/services/world_rank_values.py#L263) |
| app.services.world_russia_rank._GDP_USD_METHOD_CONCEPTS | Call | computed source expression | [backend/app/services/world_russia_rank.py:40](../backend/app/services/world_russia_rank.py#L40) |
| app.services.world_subnational_forecast.FREQUENCIES | Dict | 'annual', 'quarterly', 'monthly' | [backend/app/services/world_subnational_forecast.py:17](../backend/app/services/world_subnational_forecast.py#L17) |
| app.services.world_subnational_ingest._REAL_INCOME_UNITS_RE | Call | computed source expression | [backend/app/services/world_subnational_ingest.py:47](../backend/app/services/world_subnational_ingest.py#L47) |
| app.services.world_view_modes._TRANSFORMS | Dict | 'level', 'mom', 'mom_abs', 'qoq', 'qoq_abs', 'yoy', 'yoy_abs', 'index_first', 'avg_quarter', 'avg_year' | [backend/app/services/world_view_modes.py:139](../backend/app/services/world_view_modes.py#L139) |
| app.services.yandex_clean_param.CLEAN_PARAM_RULES | Tuple | sequence/source expression | [backend/app/services/yandex_clean_param.py:14](../backend/app/services/yandex_clean_param.py#L14) |
| app.services.yandex_clean_param.CONTENT_PARAMS | Call | computed source expression | [backend/app/services/yandex_clean_param.py:25](../backend/app/services/yandex_clean_param.py#L25) |
| app.tasks.analytics_rollups._SESSION_EVENT_TYPES | Tuple | sequence/source expression | [backend/app/tasks/analytics_rollups.py:53](../backend/app/tasks/analytics_rollups.py#L53) |
| app.tasks.analytics_rollups._TRAFFIC_JSON_KEYS | Tuple | sequence/source expression | [backend/app/tasks/analytics_rollups.py:57](../backend/app/tasks/analytics_rollups.py#L57) |
| app.tasks.analytics_rollups.METRIKA_SOURCE_TO_CHANNEL | Dict | 'organic', 'direct', 'ad', 'referral', 'internal', 'social', 'messenger', 'email', 'recommend', 'saved', 'undefined' | [backend/app/tasks/analytics_rollups.py:64](../backend/app/tasks/analytics_rollups.py#L64) |
| app.tasks.scheduler.ETL_TIMEOUT_BY_PARSER | Dict | 'rosstat_weekly_cpi', 'minfin_budget_csv' | [backend/app/tasks/scheduler.py:33](../backend/app/tasks/scheduler.py#L33) |
| app.tasks.scheduler.STALENESS_SLA_DAYS | Dict | 'daily', 'weekly', 'monthly', 'quarterly', 'annual' | [backend/app/tasks/scheduler.py:454](../backend/app/tasks/scheduler.py#L454) |
| app.tasks.ticker_worker._SERIES_TICKER_SPECS | Tuple | sequence/source expression | [backend/app/tasks/ticker_worker.py:43](../backend/app/tasks/ticker_worker.py#L43) |
| scripts.audit-groups-submodes.ACTIVE | SetComp | computed source expression | [backend/scripts/audit-groups-submodes.py:25](../backend/scripts/audit-groups-submodes.py#L25) |
| scripts.audit-groups-submodes.NAME | DictComp | computed source expression | [backend/scripts/audit-groups-submodes.py:26](../backend/scripts/audit-groups-submodes.py#L26) |
| scripts.audit-groups-submodes.GROUP_LABELS | Dict | 'level', 'avg', 'flow', 'pop', 'yoy', 'index', 'inflation', 'step' | [backend/scripts/audit-groups-submodes.py:28](../backend/scripts/audit-groups-submodes.py#L28) |
| scripts.audit-world-eurostat-underslice.SKIP_DIMS | Call | computed source expression | [backend/scripts/audit-world-eurostat-underslice.py:54](../backend/scripts/audit-world-eurostat-underslice.py#L54) |
| scripts.audit-world-eurostat-underslice.TOTALISH_BASE | Call | computed source expression | [backend/scripts/audit-world-eurostat-underslice.py:55](../backend/scripts/audit-world-eurostat-underslice.py#L55) |
| scripts.audit-world-eurostat-underslice.OUT_DIR_CANDIDATES | Tuple | sequence/source expression | [backend/scripts/audit-world-eurostat-underslice.py:58](../backend/scripts/audit-world-eurostat-underslice.py#L58) |
| scripts.audit-world-titles._RATE_PER_THOUSAND_NAME_RE | Call | computed source expression | [backend/scripts/audit-world-titles.py:46](../backend/scripts/audit-world-titles.py#L46) |
| scripts.backfill-metrika-history._CLIP_LIMITS | Dict | 'ym:s:startURL', 'ym:s:referer', 'ym:s:lastTrafficSource', 'ym:s:lastSearchEngine', 'ym:s:lastSearchEngineRoot', 'ym:s:lastSearchPhrase' | [backend/scripts/backfill-metrika-history.py:61](../backend/scripts/backfill-metrika-history.py#L61) |
| scripts.check-migration-drift._FATAL | Set | sequence/source expression | [backend/scripts/check-migration-drift.py:24](../backend/scripts/check-migration-drift.py#L24) |
| scripts.export-design-gallery.BASE | List | sequence/source expression | [backend/scripts/export-design-gallery.py:29](../backend/scripts/export-design-gallery.py#L29) |
| scripts.export-design-gallery.TITLE_EN | Dict | 'inflation', 'policy', 'housing', 'industry', 'commodity', 'population-history', 'germany-year', 'us-employment', 'california', 'california-housing', 'rating', 'comparison', 'region-comparison', 'today', 'us-country', 'us-states', 'us-state-profile', 'demographics' | [backend/scripts/export-design-gallery.py:52](../backend/scripts/export-design-gallery.py#L52) |
| scripts.export_seo_demand_quarter.OUT | Call | computed source expression | [backend/scripts/export_seo_demand_quarter.py:20](../backend/scripts/export_seo_demand_quarter.py#L20) |
| scripts.export_seo_demand_quarter.Q_FROM | Call | computed source expression | [backend/scripts/export_seo_demand_quarter.py:23](../backend/scripts/export_seo_demand_quarter.py#L23) |
| scripts.export_seo_demand_quarter.Q_TO | Call | computed source expression | [backend/scripts/export_seo_demand_quarter.py:24](../backend/scripts/export_seo_demand_quarter.py#L24) |
| scripts.export_seo_demand_quarter.BUCKET_RULES | List | sequence/source expression | [backend/scripts/export_seo_demand_quarter.py:26](../backend/scripts/export_seo_demand_quarter.py#L26) |
| scripts.gen-forecast-snapshots.TARGETS | Dict | 'ppi_monthly', 'gdp_nominal_quarterly', 'generic_quarterly', 'signed_quarterly', 'generic_ols' | [backend/scripts/gen-forecast-snapshots.py:31](../backend/scripts/gen-forecast-snapshots.py#L31) |
| scripts.indexnow-ping-all._VOLATILE_PREFIXES | Tuple | sequence/source expression | [backend/scripts/indexnow-ping-all.py:50](../backend/scripts/indexnow-ping-all.py#L50) |
| scripts.load-world-eurostat.PRIORITY_PREFIXES | Tuple | sequence/source expression | [backend/scripts/load-world-eurostat.py:88](../backend/scripts/load-world-eurostat.py#L88) |
| scripts.metrika-goals-redesign._GOAL_NAMES | Dict | 'signup', 'newsletter_opt_in', 'feedback_submit', 'login_success', 'download_csv', 'download_excel', 'download_ical', 'demographics_csv', 'chart_image_download', 'compare_image_download', 'compare_add', 'compare_change', 'region_compare_add', 'calc_share', 'calc_copy_result', 'calc_mortgage', 'calc_compound', 'embed_code_copy', 'contact_email' | [backend/scripts/metrika-goals-redesign.py:39](../backend/scripts/metrika-goals-redesign.py#L39) |
| scripts.metrika-goals-redesign._FUNNELS | List | sequence/source expression | [backend/scripts/metrika-goals-redesign.py:61](../backend/scripts/metrika-goals-redesign.py#L61) |
| scripts.repair-world-listing._NATIONAL_PASSPORT_CODES | Call | computed source expression | [backend/scripts/repair-world-listing.py:513](../backend/scripts/repair-world-listing.py#L513) |
| scripts.repair_ppi_housing_2026.PPI_BASE_MONTH | Call | computed source expression | [backend/scripts/repair_ppi_housing_2026.py:81](../backend/scripts/repair_ppi_housing_2026.py#L81) |
| scripts.repair_ppi_housing_2026.PPI_REPORTS | ListComp | computed source expression | [backend/scripts/repair_ppi_housing_2026.py:82](../backend/scripts/repair_ppi_housing_2026.py#L82) |
| scripts.repair_ppi_housing_2026.PPI_EXPECTED_MONTHS | ListComp | computed source expression | [backend/scripts/repair_ppi_housing_2026.py:83](../backend/scripts/repair_ppi_housing_2026.py#L83) |
| scripts.repair_ppi_housing_2026.HOUSING_QUARTER | Call | computed source expression | [backend/scripts/repair_ppi_housing_2026.py:85](../backend/scripts/repair_ppi_housing_2026.py#L85) |
| scripts.repair_ppi_housing_2026.HOUSING_BASE | Call | computed source expression | [backend/scripts/repair_ppi_housing_2026.py:86](../backend/scripts/repair_ppi_housing_2026.py#L86) |
| scripts.repair_ppi_housing_2026.HOUSING_CODES | Tuple | sequence/source expression | [backend/scripts/repair_ppi_housing_2026.py:87](../backend/scripts/repair_ppi_housing_2026.py#L87) |
| scripts.repair_ppi_housing_2026.SOURCE_CODES | List | sequence/source expression | [backend/scripts/repair_ppi_housing_2026.py:88](../backend/scripts/repair_ppi_housing_2026.py#L88) |
| scripts.repair_ppi_housing_2026.SHOW_FROM | Call | computed source expression | [backend/scripts/repair_ppi_housing_2026.py:89](../backend/scripts/repair_ppi_housing_2026.py#L89) |
| scripts.verify-world-deep-expand.OUT | Call | computed source expression | [backend/scripts/verify-world-deep-expand.py:27](../backend/scripts/verify-world-deep-expand.py#L27) |
| seed_data.INDICATORS | List | sequence/source expression | [backend/seed_data.py:53](../backend/seed_data.py#L53) |
| seed_data._PARENT_META | DictComp | computed source expression | [backend/seed_data.py:4948](../backend/seed_data.py#L4948) |
| seed_data._EXISTING_CODES | Call | computed source expression | [backend/seed_data.py:4949](../backend/seed_data.py#L4949) |
| seed_data._GRAN_PERIOD | Dict | 'week', 'month', 'quarter', 'year' | [backend/seed_data.py:4951](../backend/seed_data.py#L4951) |
| seed_data._GRAN_EOP | Dict | 'week', 'month', 'quarter', 'year' | [backend/seed_data.py:4954](../backend/seed_data.py#L4954) |
| seed_data._FCAST_STEPS_BY_FREQ | Dict | 'monthly', 'quarterly', 'annual' | [backend/seed_data.py:5056](../backend/seed_data.py#L5056) |
| seed_data.MONTHLY_AUTO_FORECAST_CODES | Set | sequence/source expression | [backend/seed_data.py:5122](../backend/seed_data.py#L5122) |
| seed_data.ANNUAL_AUTO_FORECAST_CODES | Set | sequence/source expression | [backend/seed_data.py:5165](../backend/seed_data.py#L5165) |
| scripts.audit-code-documentation.EXCLUDED_FILES | Set | sequence/source expression | [scripts/audit-code-documentation.py:27](../scripts/audit-code-documentation.py#L27) |
| scripts.audit-code-documentation.TEXT_REVIEW | Set | sequence/source expression | [scripts/audit-code-documentation.py:31](../scripts/audit-code-documentation.py#L31) |
| scripts.audit-code-documentation.DATA_REVIEW | Set | sequence/source expression | [scripts/audit-code-documentation.py:32](../scripts/audit-code-documentation.py#L32) |
| scripts.audit-code-documentation.ASSET_REVIEW | Set | sequence/source expression | [scripts/audit-code-documentation.py:33](../scripts/audit-code-documentation.py#L33) |
| scripts.audit-code-documentation.CODE_EXTENSIONS | Set | sequence/source expression | [scripts/audit-code-documentation.py:35](../scripts/audit-code-documentation.py#L35) |
| scripts.audit-code-documentation.JS_EXTENSIONS | Set | sequence/source expression | [scripts/audit-code-documentation.py:36](../scripts/audit-code-documentation.py#L36) |
| scripts.audit-compare-representations.FAMILIES | Call | computed source expression | [scripts/audit-compare-representations.py:20](../scripts/audit-compare-representations.py#L20) |
| scripts.audit-compare-representations._COUNTS | Dict | sequence/source expression | [scripts/audit-compare-representations.py:39](../scripts/audit-compare-representations.py#L39) |
| scripts.audit-compare-representations._META | Dict | sequence/source expression | [scripts/audit-compare-representations.py:40](../scripts/audit-compare-representations.py#L40) |
| scripts.audit-compare-representations.CPI_CODES | Set | sequence/source expression | [scripts/audit-compare-representations.py:57](../scripts/audit-compare-representations.py#L57) |
| scripts.audit-compare-representations.HOUSING_CODES | Set | sequence/source expression | [scripts/audit-compare-representations.py:58](../scripts/audit-compare-representations.py#L58) |
| scripts.audit-doc-counters.PATTERNS | List | sequence/source expression | [scripts/audit-doc-counters.py:60](../scripts/audit-doc-counters.py#L60) |
| scripts.audit-doc-counters.DOCS | List | sequence/source expression | [scripts/audit-doc-counters.py:81](../scripts/audit-doc-counters.py#L81) |
| scripts.audit-indicator-unification.CPI_BESPOKE | Set | sequence/source expression | [scripts/audit-indicator-unification.py:96](../scripts/audit-indicator-unification.py#L96) |
| scripts.audit-indicator-unification.PPI_BESPOKE | Set | sequence/source expression | [scripts/audit-indicator-unification.py:97](../scripts/audit-indicator-unification.py#L97) |
| scripts.audit-indicator-unification.HOUSING_BESPOKE | Set | sequence/source expression | [scripts/audit-indicator-unification.py:98](../scripts/audit-indicator-unification.py#L98) |
| scripts.audit-indicator-unification.CBR_TERM_SLICE_BESPOKE | Set | sequence/source expression | [scripts/audit-indicator-unification.py:101](../scripts/audit-indicator-unification.py#L101) |
| scripts.audit-indicator-unification.VARIANT_GROUPS | List | sequence/source expression | [scripts/audit-indicator-unification.py:110](../scripts/audit-indicator-unification.py#L110) |
| scripts.audit-indicator-unification.VARIANT_GROUP_BY_CODE | Dict | sequence/source expression | [scripts/audit-indicator-unification.py:144](../scripts/audit-indicator-unification.py#L144) |
| scripts.audit-indicator-unification.BY_CODE | DictComp | computed source expression | [scripts/audit-indicator-unification.py:152](../scripts/audit-indicator-unification.py#L152) |
| scripts.audit-indicator-unification.SIBLING_INFO | DictComp | computed source expression | [scripts/audit-indicator-unification.py:153](../scripts/audit-indicator-unification.py#L153) |
| scripts.audit-indicator-unification.DERIVED_MODE_CODES | Call | computed source expression | [scripts/audit-indicator-unification.py:157](../scripts/audit-indicator-unification.py#L157) |
| scripts.audit-knowledge-materials.GENERATED | Set | sequence/source expression | [scripts/audit-knowledge-materials.py:20](../scripts/audit-knowledge-materials.py#L20) |
| scripts.audit-knowledge-materials.ROOT_MATERIALS | Set | sequence/source expression | [scripts/audit-knowledge-materials.py:24](../scripts/audit-knowledge-materials.py#L24) |
| scripts.audit-knowledge-materials.SHA256 | Call | computed source expression | [scripts/audit-knowledge-materials.py:25](../scripts/audit-knowledge-materials.py#L25) |
| scripts.audit-public-language.INTERNAL_PATTERNS | List | sequence/source expression | [scripts/audit-public-language.py:29](../scripts/audit-public-language.py#L29) |
| scripts.audit-public-language.INTERNAL_RE | Call | computed source expression | [scripts/audit-public-language.py:39](../scripts/audit-public-language.py#L39) |
| scripts.audit-public-language.PRODUCT_CLAIM_PATTERNS | List | sequence/source expression | [scripts/audit-public-language.py:42](../scripts/audit-public-language.py#L42) |
| scripts.audit-public-language.PRODUCT_CLAIM_RE | Call | computed source expression | [scripts/audit-public-language.py:59](../scripts/audit-public-language.py#L59) |
| scripts.audit-public-language.PUBLIC_FIELDS | Tuple | sequence/source expression | [scripts/audit-public-language.py:61](../scripts/audit-public-language.py#L61) |
| scripts.audit-public-language.INTERNAL_SURFACES | Tuple | sequence/source expression | [scripts/audit-public-language.py:63](../scripts/audit-public-language.py#L63) |
| scripts.audit-public-language.PRODUCT_SURFACES | Tuple | sequence/source expression | [scripts/audit-public-language.py:69](../scripts/audit-public-language.py#L69) |
| scripts.audit-public-language.PRODUCT_CLAIM_ONLY_SURFACES | Tuple | sequence/source expression | [scripts/audit-public-language.py:79](../scripts/audit-public-language.py#L79) |
| scripts.audit-public-language.EN_NO_CYRILLIC | Tuple | sequence/source expression | [scripts/audit-public-language.py:94](../scripts/audit-public-language.py#L94) |
| scripts.audit-public-language.EN_CYRILLIC_ALLOW | Dict | 'frontend/src/i18n/messages.en.js' | [scripts/audit-public-language.py:99](../scripts/audit-public-language.py#L99) |
| scripts.audit-public-language.CYRILLIC_RE | Call | computed source expression | [scripts/audit-public-language.py:102](../scripts/audit-public-language.py#L102) |
| scripts.audit-public-language._URL_EXT | Call | computed source expression | [scripts/audit-public-language.py:138](../scripts/audit-public-language.py#L138) |
| scripts.audit-public-language._COMMENT_RE | Call | computed source expression | [scripts/audit-public-language.py:139](../scripts/audit-public-language.py#L139) |
| scripts.audit-world-country-coverage.TODAY | Call | computed source expression | [scripts/audit-world-country-coverage.py:29](../scripts/audit-world-country-coverage.py#L29) |
| scripts.audit-world-country-coverage.EUROSTAT_CORE_GEOS | Set | sequence/source expression | [scripts/audit-world-country-coverage.py:32](../scripts/audit-world-country-coverage.py#L32) |
| scripts.audit-world-country-coverage.EUROSTAT_ENLARGEMENT | Set | sequence/source expression | [scripts/audit-world-country-coverage.py:39](../scripts/audit-world-country-coverage.py#L39) |
| scripts.audit-world-country-coverage.PARTNER_GEOS | Set | sequence/source expression | [scripts/audit-world-country-coverage.py:44](../scripts/audit-world-country-coverage.py#L44) |
| scripts.audit-world-country-coverage.RESEARCH_XLSX | Dict | 'US', 'CN', 'JP', 'KR', 'IN', 'BR', 'TR', 'FR', 'DE', 'UK' | [scripts/audit-world-country-coverage.py:48](../scripts/audit-world-country-coverage.py#L48) |
| scripts.audit-world-eurostat-source.REQUIRED_TOPICS | Set | sequence/source expression | [scripts/audit-world-eurostat-source.py:38](../scripts/audit-world-eurostat-source.py#L38) |
| scripts.audit-world-plausibility.TODAY | Call | computed source expression | [scripts/audit-world-plausibility.py:36](../scripts/audit-world-plausibility.py#L36) |
| scripts.audit-world-plausibility.EXPECTED_GAP | Dict | 'monthly', 'quarterly', 'annual', 'weekly', 'daily' | [scripts/audit-world-plausibility.py:48](../scripts/audit-world-plausibility.py#L48) |
| scripts.audit-world-titles._RATE_PER_THOUSAND_NAME_RE | Call | computed source expression | [scripts/audit-world-titles.py:46](../scripts/audit-world-titles.py#L46) |
| scripts.audit_world_lib.POP_MILLIONS_APPROX | Dict | 'DE', 'FR', 'IT', 'ES', 'PL', 'RO', 'NL', 'BE', 'CZ', 'SE', 'PT', 'HU', 'AT', 'CH', 'BG', 'DK', 'FI', 'SK', 'NO', 'IE', 'HR', 'LT', 'SI', 'LV', 'EE', 'CY', 'LU', 'MT', 'IS', 'AL', 'RS', 'BA', 'MK', 'ME', 'XK', 'TR', 'UA', 'MD', 'GE', 'AM', 'AZ', 'UK', 'US', 'CN', 'JP', 'KR', 'IN', 'BR', 'MX', 'CA', 'AU', 'NZ', 'ZA', 'IL' | [scripts/audit_world_lib.py:29](../scripts/audit_world_lib.py#L29) |
| scripts.audit_world_lib.TOPIC_PATTERNS | List | sequence/source expression | [scripts/audit_world_lib.py:41](../scripts/audit_world_lib.py#L41) |
| scripts.backfill-keyrate-history.REFINANCING_HISTORY | List | sequence/source expression | [scripts/backfill-keyrate-history.py:63](../scripts/backfill-keyrate-history.py#L63) |
| scripts.backfill-keyrate-history.CUTOFF | Call | computed source expression | [scripts/backfill-keyrate-history.py:155](../scripts/backfill-keyrate-history.py#L155) |
| scripts.build-indicator-index._LEGACY_FILE_MARKERS | Tuple | sequence/source expression | [scripts/build-indicator-index.py:55](../scripts/build-indicator-index.py#L55) |
| scripts.build-indicator-index.SKIP_DIRS | Set | sequence/source expression | [scripts/build-indicator-index.py:159](../scripts/build-indicator-index.py#L159) |
| scripts.build-indicator-index.SKIP_SUFFIXES | Set | sequence/source expression | [scripts/build-indicator-index.py:163](../scripts/build-indicator-index.py#L163) |
| scripts.build-indicator-index.SKIP_NAMES | Set | sequence/source expression | [scripts/build-indicator-index.py:169](../scripts/build-indicator-index.py#L169) |
| scripts.build-indicator-index.SKIP_RELPATHS | Set | sequence/source expression | [scripts/build-indicator-index.py:171](../scripts/build-indicator-index.py#L171) |
| scripts.build-indicator-index.CPI_BASE | Set | sequence/source expression | [scripts/build-indicator-index.py:295](../scripts/build-indicator-index.py#L295) |
| scripts.build-project-terrain.GENERATED | Set | sequence/source expression | [scripts/build-project-terrain.py:29](../scripts/build-project-terrain.py#L29) |
| scripts.build-project-terrain.CODE | Set | sequence/source expression | [scripts/build-project-terrain.py:34](../scripts/build-project-terrain.py#L34) |
| scripts.build-project-terrain.DOCS | Set | sequence/source expression | [scripts/build-project-terrain.py:35](../scripts/build-project-terrain.py#L35) |
| scripts.build-project-terrain.LAYERS | List | sequence/source expression | [scripts/build-project-terrain.py:39](../scripts/build-project-terrain.py#L39) |
| scripts.build-rid-listing.FILES | List | sequence/source expression | [scripts/build-rid-listing.py:30](../scripts/build-rid-listing.py#L30) |
| scripts.build-us-bea-catalog.TABLE_LABELS | Dict | 'SASUMMARY', 'SAGDP1', 'SAGDP2', 'SAGDP3', 'SAGDP4', 'SAGDP5', 'SAGDP6', 'SAGDP7', 'SAGDP8', 'SAGDP9', 'SAGDP11', 'SQGDP1', 'SQGDP2', 'SQGDP8', 'SQGDP9', 'SQGDP11', 'SAINC1', 'SAINC4', 'SAINC5N', 'SAINC6N', 'SAINC7N', 'SAINC11', 'SAINC12', 'SAINC30', 'SAINC35', 'SAINC40', 'SAINC50', 'SAINC51', 'SAINC70', 'SQINC1', 'SQINC4', 'SQINC5N', 'SQINC6N', 'SQINC7N', 'SQINC11', 'SQINC12', 'SQINC35', 'SAPCE1', 'SAPCE2', 'SAPCE3', 'SAPCE4', 'SAPCE5', 'SARPP', 'SARPI', 'SAIRPD' | [scripts/build-us-bea-catalog.py:32](../scripts/build-us-bea-catalog.py#L32) |
| scripts.build-us-bea-catalog.UNIT_RU | Dict | 'Thousands of dollars', 'Millions of current dollars', 'Millions of chained 2017 dollars', 'Millions of constant 2017 dollars', 'Millions of dollars', 'Constant 2017 dollars', 'Dollars', 'Number of persons', 'Number of jobs', 'Quantity index', 'Index', 'Percentage points', 'Percent change', 'Ratio' | [scripts/build-us-bea-catalog.py:80](../scripts/build-us-bea-catalog.py#L80) |
| scripts.catalog-harvest._SSL | Call | computed source expression | [scripts/catalog-harvest.py:48](../scripts/catalog-harvest.py#L48) |
| scripts.catalog-harvest._FREQ_BY_PERIOD | List | sequence/source expression | [scripts/catalog-harvest.py:97](../scripts/catalog-harvest.py#L97) |
| scripts.catalog-harvest._IBGE_FREQ | Dict | 'mensal', 'trimestral', 'anual', 'semestral', 'decenal', 'quinquenal', 'bienal', 'diaria', 'semanal', 'irregular' | [scripts/catalog-harvest.py:152](../scripts/catalog-harvest.py#L152) |
| scripts.catalog-harvest._ONS_FREQ | Dict | 'monthly', 'quarterly', 'annual', 'annually', 'weekly', 'daily', 'yearly' | [scripts/catalog-harvest.py:212](../scripts/catalog-harvest.py#L212) |
| scripts.catalog-harvest.HARVESTERS | Dict | 'eurostat', 'ibge', 'ons' | [scripts/catalog-harvest.py:273](../scripts/catalog-harvest.py#L273) |
| scripts.completeness.TOP_ORDER | List | sequence/source expression | [scripts/completeness.py:49](../scripts/completeness.py#L49) |
| scripts.completeness.TOP_LABEL | Dict | TOP_VALUE, TOP_POP, TOP_YOY, TOP_INDEX | [scripts/completeness.py:50](../scripts/completeness.py#L50) |
| scripts.completeness.FREQ_ORDER | List | sequence/source expression | [scripts/completeness.py:57](../scripts/completeness.py#L57) |
| scripts.completeness.FREQ_LABEL | Dict | 'day', 'week', 'month', 'quarter', 'year' | [scripts/completeness.py:58](../scripts/completeness.py#L58) |
| scripts.completeness._GROUP_TO_TOP | Dict | 'level', 'avg', 'flow', 'eop', 'pop', 'yoy', 'index' | [scripts/completeness.py:61](../scripts/completeness.py#L61) |
| scripts.completeness._FREQ_OF | Dict | 'daily', 'weekly', 'monthly', 'quarterly', 'annual' | [scripts/completeness.py:66](../scripts/completeness.py#L66) |
| scripts.completeness._NATURE_BY_TEMPLATE | Dict | 'T1', 'T2', 'T2y', 'T3', 'T4', 'T5', 'T6', 'T7', 'T8', 'T9', 'T9s', 'T10', 'T10a', 'T12' | [scripts/completeness.py:72](../scripts/completeness.py#L72) |
| scripts.dual-host-release-gate.DATA_IMAGE_PATHS | Call | computed source expression | [scripts/dual-host-release-gate.py:16](../scripts/dual-host-release-gate.py#L16) |
| scripts.dual-host-release-gate.DEFAULT_PATHS | Tuple | sequence/source expression | [scripts/dual-host-release-gate.py:22](../scripts/dual-host-release-gate.py#L22) |
| scripts.dual-host-release-gate.CYRILLIC | Call | computed source expression | [scripts/dual-host-release-gate.py:35](../scripts/dual-host-release-gate.py#L35) |
| scripts.dual-host-release-gate.OG_429_RETRY_DELAYS | Tuple | sequence/source expression | [scripts/dual-host-release-gate.py:36](../scripts/dual-host-release-gate.py#L36) |
| scripts.frontend-asset-archive.HASHED_ASSET | Call | computed source expression | [scripts/frontend-asset-archive.py:19](../scripts/frontend-asset-archive.py#L19) |
| scripts.insert-gdp-q1-2026-estimate.BASE_DATE | Call | computed source expression | [scripts/insert-gdp-q1-2026-estimate.py:40](../scripts/insert-gdp-q1-2026-estimate.py#L40) |
| scripts.insert-gdp-q1-2026-estimate.TARGET_DATE | Call | computed source expression | [scripts/insert-gdp-q1-2026-estimate.py:41](../scripts/insert-gdp-q1-2026-estimate.py#L41) |
| scripts.locate-indicator.SKIP_DIRS | Set | sequence/source expression | [scripts/locate-indicator.py:27](../scripts/locate-indicator.py#L27) |
| scripts.locate-indicator.SKIP_SUFFIXES | Set | sequence/source expression | [scripts/locate-indicator.py:31](../scripts/locate-indicator.py#L31) |
| scripts.locate-indicator.SKIP_NAMES | Set | sequence/source expression | [scripts/locate-indicator.py:37](../scripts/locate-indicator.py#L37) |
| scripts.locate-indicator.KIND_ORDER | List | sequence/source expression | [scripts/locate-indicator.py:40](../scripts/locate-indicator.py#L40) |
| scripts.locate-indicator.KIND_TITLE | Dict | 'seed', 'parser', 'derived', 'family', 'seo', 'variants', 'tests', 'other' | [scripts/locate-indicator.py:41](../scripts/locate-indicator.py#L41) |
| scripts.metrika-baseline-snapshot.START | Call | computed source expression | [scripts/metrika-baseline-snapshot.py:28](../scripts/metrika-baseline-snapshot.py#L28) |
| scripts.metrika-goals-audit.GOAL_NAMES | Dict | 'indicator_view', 'region_indicator_view', 'frequency_switch', 'chart_mode_change', 'chart_range_change', 'chart_zoom', 'forecast_toggle', 'forecast_view', 'methodology_click', 'table_search', 'table_sort', 'table_page', 'compare_open', 'compare_change', 'compare_range', 'download_ical', 'calc_direction', 'calc_preset', 'calc_share', 'calc_copy_result', 'calc_chart_mode', 'calc_breakdown', 'faq_toggle', 'calendar_month_nav', 'calendar_source_filter', 'calendar_day_select', 'calendar_clear_day', 'demographics_chart_type', 'demographics_csv', 'embed_type_change', 'embed_indicator_select', 'embed_period_change', 'embed_theme_change', 'embed_size_change', 'embed_option_toggle', 'embed_code_tab', 'embed_code_copy', 'embed_runtime_view', 'nav_category_open', 'nav_mobile_toggle', 'nav_link_click', 'home_category_click', 'home_indicator_click', 'category_tile_click', 'related_indicator_click', 'related_link_click', 'breadcrumb_click', 'source_link_click', 'scroll_depth', 'outbound_link', 'contact_email', 'consent_update', 'api_retry', 'error_reload', 'empty_state', 'api_load_error', 'experiment_exposure', 'newsletter_opt_out', 'feedback_nudge_view', 'register_nudge_view', 'regions_view_toggle', 'regions_map_metric', 'regions_map_select', 'region_compare_add', 'region_crosslink_click' | [scripts/metrika-goals-audit.py:34](../scripts/metrika-goals-audit.py#L34) |
| scripts.metrika_daily_report.BASELINE_START | Call | computed source expression | [scripts/metrika_daily_report.py:34](../scripts/metrika_daily_report.py#L34) |
| scripts.metrika_daily_report.CHANNEL_ORDER | List | sequence/source expression | [scripts/metrika_daily_report.py:36](../scripts/metrika_daily_report.py#L36) |
| scripts.metrika_daily_report.CHANNEL_RU | Dict | 'Ad traffic', 'Search engine traffic', 'Direct traffic', 'Internal traffic', 'Link traffic', 'Social network traffic' | [scripts/metrika_daily_report.py:44](../scripts/metrika_daily_report.py#L44) |
| scripts.metrika_daily_report.CHANNEL_COLORS | Dict | 'Ad traffic', 'Search engine traffic', 'Direct traffic', 'Internal traffic', 'Link traffic', 'Social network traffic' | [scripts/metrika_daily_report.py:52](../scripts/metrika_daily_report.py#L52) |
| scripts.read-project-workbooks.NS | Dict | 'm' | [scripts/read-project-workbooks.py:19](../scripts/read-project-workbooks.py#L19) |
| scripts.repo-inventory.SKIP_DIRS | Set | sequence/source expression | [scripts/repo-inventory.py:56](../scripts/repo-inventory.py#L56) |
| scripts.repo-inventory.SKIP_SUFFIXES | Set | sequence/source expression | [scripts/repo-inventory.py:63](../scripts/repo-inventory.py#L63) |
| scripts.repo-inventory.SKIP_NAMES | Set | sequence/source expression | [scripts/repo-inventory.py:71](../scripts/repo-inventory.py#L71) |
| scripts.repo-inventory.SKIP_RELPATHS | Set | sequence/source expression | [scripts/repo-inventory.py:75](../scripts/repo-inventory.py#L75) |
| scripts.seo-audit.TRACKING_PARAMS | Set | sequence/source expression | [scripts/seo-audit.py:20](../scripts/seo-audit.py#L20) |
| scripts.sync-local-from-prod._HERE | Call | computed source expression | [scripts/sync-local-from-prod.py:32](../scripts/sync-local-from-prod.py#L32) |
| scripts.sync-local-from-prod._CANDIDATES | List | sequence/source expression | [scripts/sync-local-from-prod.py:33](../scripts/sync-local-from-prod.py#L33) |
| scripts.verify-data-loaded.KNOWN_STRUCTURAL_EMPTY | Set | sequence/source expression | [scripts/verify-data-loaded.py:47](../scripts/verify-data-loaded.py#L47) |

## MCP tools

| Name | HTTP expressions | Source |
| --- | --- | --- |
| analytics_status | [{'method': 'GET', 'path_expression': '/health', 'dynamic': False}] | [mcp/forecast-analytics-mcp/src/index.ts:37](../mcp/forecast-analytics-mcp/src/index.ts#L37) |
| page_performance_deep_dive | [{'method': 'GET', 'path_expression': '/pages?limit=${limit}', 'dynamic': True}] | [mcp/forecast-analytics-mcp/src/index.ts:47](../mcp/forecast-analytics-mcp/src/index.ts#L47) |
| search_query_cluster_analysis | [{'method': 'GET', 'path_expression': '/search-phrases?limit=${limit}', 'dynamic': True}] | [mcp/forecast-analytics-mcp/src/index.ts:59](../mcp/forecast-analytics-mcp/src/index.ts#L59) |
| detect_anomalies | [{'method': 'GET', 'path_expression': '/anomalies', 'dynamic': False}] | [mcp/forecast-analytics-mcp/src/index.ts:71](../mcp/forecast-analytics-mcp/src/index.ts#L71) |
| compare_deploy_impact | [{'method': 'GET', 'path_expression': '/deploy-impact', 'dynamic': False}] | [mcp/forecast-analytics-mcp/src/index.ts:81](../mcp/forecast-analytics-mcp/src/index.ts#L81) |
| metrika_stat_query | [{'method': 'POST', 'path_expression': '/query/metrika', 'dynamic': False}] | [mcp/forecast-analytics-mcp/src/index.ts:91](../mcp/forecast-analytics-mcp/src/index.ts#L91) |
| propose_analytics_action | [{'method': 'POST', 'path_expression': '/actions/propose', 'dynamic': False}] | [mcp/forecast-analytics-mcp/src/index.ts:110](../mcp/forecast-analytics-mcp/src/index.ts#L110) |

## Unresolved syntax

| Kind | Source / symbol | Expression |
| --- | --- | --- |

## Limits

- Syntax inventory is an independent denominator, not semantic review or deployment proof.
- Router paths reflect decorators/includes; framework-generated debug OpenAPI/docs routes are separately declared in FastAPI constructor.
- Aliases with collisions, computed mounts and unmounted routes are explicit unresolved records.
- ORM nullable inference records Python Mapped annotations, not observed migrated database state; migration operations are listed separately.
- Effect names and model references are candidate links; object dispatch, raw SQL, runtime branch configuration and transaction outcome require contracts/read or fixture proof.
- Registry comprehensions/builders retain syntax previews, explicit truncation/AST hashes and exact full-source ranges; computed entry cardinality is not evaluated.
- Scheduler branch gates/triggers/lock wrappers are source facts; actual enabled process and resource limits belong to ops evidence.
- MCP parser reads literal registration blocks only, preserving URL interpolations; no TypeScript evaluation or network.
