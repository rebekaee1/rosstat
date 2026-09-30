# Backend: состав и механизмы, 30 сентября 2026

## Основание и статус

База: локальная `main` **05302ff1c4dbe104850116e6206d168ec4fa91d3**. Runtime-код, production, main DB и внешние API в этом проходе не изменялись. Новые файлы досье и генератор пока находятся в рабочем дереве. Старые материалы и причины решений сохранены.

Прочитан [readiness-criteria](readiness-criteria.md) целиком. Этот пакет закрывает независимый состав backend/CLI, связывает его с прежним содержательным чтением и уточняет K02–K06. Он не доказывает безошибочность реализации, состояние production или измеренные свойства платформы. Физическая БД, процессы, ресурсы и внешний доступ сверяются с отдельной ops-приёмкой.

Источники:

- [Генератор](../../scripts/build-mechanism-inventory.py) — Python stdlib AST; без импорта приложения, сетевых вызовов и ledger во входах.
- [Полный JSON](../mechanism-inventory.json) и [человеческий индекс](../mechanism-inventory.md): все исходные декларации, условия, поля, регистрации, возможные обращения к моделям/SQL/кэшу с `path:line` и SHA исходников.
- [Сверка с ledger](backend-mechanism-crosscheck-2026-09-30.json) выполнена **после** построения состава. Рецензии не задают знаменатель.
- [Исполняемые изолированные probes](backend-mechanism-probes-2026-09-30.py) и [результаты](backend-mechanism-probes-2026-09-30.json): реальные выбранные AST-тела функций, явные in-memory doubles, восемь проверок, ноль внешних вызовов.
- Прежняя полная рецензия + неизменённые тела + прочитанная delta: [backend delta](backend-delta-2026-09-30.md), [contracts](../data-contracts.md), [findings](../code-review-findings.md), [ledger](reviews.jsonl). Совпадение SHA сохраняет прежнее основание чтения; оно не означает повторного чтения каждого неизменённого тела сегодня.

## 1. Независимые знаменатели K02

| Состав | Источник / количество | Результат последующей сверки |
|---|---|---|
| Implementation / declared data | 403 tracked/index файла: `backend/app/**/*.py`, backend CLI/seed, Alembic, корневые `scripts/*.py` кроме тестов и самого генератора, runtime JSON/YAML, MCP source/package/lock | 403/403 имеют текущий SHA и authored review; missing/stale=0 |
| Python именованные определения | 3642 функции/метода/класса, в том числе вложенные; собственный AST-знаменатель | 3642/3642 локализованы в существующих содержательных аннотациях |
| HTTP | 21 router/app declaration, 20 include edges, **144 reachable declarations**, в том числе 2 explicit OAuth compat registrations | Каждый handler локализован в review. Повторяющихся пар method+path=0. Ни одна декларация не осталась unmounted/unresolved |
| Methods | GET126, HEAD38, POST15, DELETE2, PATCH1; один route может иметь GET+HEAD | Это 182 method/path пары, а не 182 разных handler |
| Middleware | 5 registrations: RateLimit, HttpStatusCounter, ScrapeGuard, CORS, Locale | Последний зарегистрирован снаружи остальных custom middleware. Framework exception/error layers не объявляются нашими middleware |
| ORM | **57 таблиц / 626 mapped columns / 34 relationships** | Каждый столбец: Python/SQL имя, тип, nullable inference/explicit, default/server_default, FK, unique/index; отдельные table constraints. Это source schema |
| DTO | 27 Pydantic classes, включая inherited bases и собственные поля | HTTP signature/default/Depends/response options + DTO отдельно. Произвольные JSON payload не превращены в фиктивный DTO |
| Migration operations | 348 AST-вызовов Alembic `op.*` | Upgrade/downgrade/conditions сохранены; количество операций не равно количеству миграций или действующих объектов |
| Scheduler | **39 add_job registrations**, trigger/args/flags/lock wrapper/TTL expressions | Включение всех зависит от `scheduler_enabled` и вложенных flags. Регистрации не означают 39 реально активных jobs |
| Settings | 160 declared fields, 390 Settings/property/dynamic read sites, 29 direct environment calls | Неизвестный `getattr` сохранён. Настройки с нулём статических readers остаются в составе, а не объявлены dead |
| Registries / constants | 842 структурированные объявления; 23 mutations/register candidates; 1584 resolved references | Включены parser/derived/family/forecast/provider/SEO/redirect/passport/config. Крупные выражения имеют явный truncated flag, AST SHA и полный source range |
| Storage / effects | 1881 candidate calls, 180 `text(...)` SQL callsites, model/field references | `execute/set/add` без диспетчеризации не объявляются автоматически записью в БД. Полный source trace требует owner/contract |
| MCP | **7 registerTool** с точными schema/handler lines и HTTP expressions | Все семь ведут к существующим token-protected `/api/v1/analytics/*` |

`--check` заново строит состав из tracked/index текущих байтов и сравнивает оба generated файла. Изменение/удаление исходника, новое tracked включение, syntax error или отсутствующий tracked файл нарушает сверку. Untracked `assets/`, `.artifacts/` и чужая рабочая документация не становятся автоматически main.

**Последний рабочий снимок:** параллельная root-правка `scripts/build-project-terrain.py` добавила одно определение: теперь Python definitions3643. Crosscheck отдельно сохраняет этот stale SHA и шесть сдвинувшихся/новых annotation locations до обновления authored root rows. HTTP/ORM/jobs/settings counts выше не изменились. Начальная сверка403/403 и3642/3642 относится к захваченному baseline до этой правки; она не скрывает нынешнюю delta. После объединения rows root повторяет сверку.

**Исключённое из этого знаменателя:** Python tests (отдельное verification evidence), shell/nginx/Caddy/Compose/systemd (ops inventory), client React/JS (client inventory), generated JSON/MD самого состава, reviews ledger. Файлы исторической документации не включаются как исполняемая backend-механика и сохраняются в materials registry. Неизвестных router path/mount expressions в текущем наборе нет; это не заявление об отсутствии любых динамических связей.

## 2. HTTP: путь до handler и middleware

[main.py](../../backend/app/main.py#L1650) включает `/api/v1` router, OAuth compat, root sitemap и SSR routers. [router.py](../../backend/app/api/router.py) включает 16 API families. Полный перечень пути/метода/параметров/dependency/handler находится в JSON; порядок includes и route options сохранены.

| API family (declarations) | Назначение и публичная граница | Основной контракт / source |
|---|---|---|
| indicators4 / forecasts2 / dashboard2 / demographics1 | Каталог/detail/data, nullable forecast, dashboard/latest, demographics | [indicators](../../backend/app/api/indicators.py), [forecasts](../../backend/app/api/forecasts.py), [schemas](../../backend/app/schemas.py); [contracts §1](../data-contracts.md#1-федеральный-факт-derived-и-прогноз) |
| world11 / world_subnational5 / regions8 | Страны/рейтинги/сравнение/карточки и отдельные оси региона/периода | [world](../../backend/app/api/world.py), [world_subnational](../../backend/app/api/world_subnational.py), [regions](../../backend/app/api/regions.py); [contracts §§2–4](../data-contracts.md#2-регионы-россии) |
| calendar4 / ticker1 / embed5 | Официальные события/iCal, live ticker, iframe/экспорт/embed | [calendar](../../backend/app/api/calendar.py), [ticker](../../backend/app/api/ticker.py), [embed](../../backend/app/api/embed.py) |
| export2 | CSV/XLSX из переданных клиентом точек; backend форматирует/ограничивает/рендерит, не удостоверяет происхождение каждого значения | [export](../../backend/app/api/export.py), [render admission](../../backend/app/services/export_render.py#L16); guest auth/quota + 100000 point limit |
| auth12 / oauth6 | Email/account/consents + OAuth start/callback/unlink/compat | [auth](../../backend/app/api/auth.py), [OAuth](../../backend/app/api/oauth.py), [ADR0007](../adr/0007-identity-user-accounts.md) |
| analytics11 / admin_bi3 | Collectors; token API/actions; admin session BI | [analytics](../../backend/app/api/analytics.py), [BI](../../backend/app/api/admin_bi.py), [contracts §6](../data-contracts.md#6-пользователь-сессия-и-аналитические-числа) |
| system6 | liveness/ready/metrics/status/challenge | [system](../../backend/app/api/system.py); liveness не проверяет зависимости, ready hard dependency failures503 / stale/FD soft degraded; metrics требует token |
| sitemap29 / SEO32 | XML/stats/robots/llms/feed/OG/SSR and redirects | [sitemap](../../backend/app/api/sitemap.py), [seo_pages](../../backend/app/api/seo_pages.py); HTTP routes backend могут быть internal `/seo/*`, публичный rewrite принадлежит nginx |

Middleware [main.py:65–237, 1542–1647](../../backend/app/main.py#L65): trusted-proxy выбор IP для общего API rate limit (120/min; embed600/min), Lua INCR+TTL; Redis failure fail-open с process counters/алертом; pool timeout503/Retry-After5; scrape/bind и locale redirects до handler, request context reset в finally. HTTP/metrics counters, locale lock/semaphore и alert dedup являются process-local. [Locale](../../backend/app/main.py#L1177) учитывает host/query/cookie/referrer, dual-host redirects и preview; header не переопределяет production host.

CORS [main.py:1628](../../backend/app/main.py#L1628) разрешает несколько origins, credentials, `GET/OPTIONS` methods. **POST auth/analytics через отличающийся origin с preflight** не проходит объявленную CORS method policy. Same-origin public proxy не требует CORS; это условный предел dev/cross-origin, не доказательство общего отказа production. Debug OpenAPI/docs/redoc `/api/openapi.json`, `/api/docs`, `/api/redoc` — условные framework routes из FastAPI constructor, отдельно от 144 наших declarations.

## 3. ORM / запись / потребитель K03–K05

Полные поля всех 57 моделей и constraints представлены в JSON/MD. Ни одна таблица не сведена к одному агрегированному счётчику. Следующие owners объясняют семейства всех таблиц; named ORM references и raw SQL дают направления к фактическим callsites.

| Таблицы | Владелец записи → основной потребитель / identity |
|---|---|
| `indicators`, `indicator_data`, `forecasts`, `forecast_values`, `fetch_log`, `seed_state` | seed metadata/hash; BaseParser+bulk_upsert; CalculationEngine; forecast pipeline; ETL logs → API/SSR/OG/derived/forecast; `(indicator_id,date)`, forecast parent/id, seed key. [models19/532/618/1341](../../backend/app/models.py#L19) |
| `regions`, `region_indicators`, `region_data`, `region_monthly_data` | artifact seed + EMISS monthly → regional API/SSR/maps/ratings; annual `(indicator,region,year)`, monthly `(indicator,region,YYYYMM)`; два писателя monthly, отдельного version/owner column нет. [models77](../../backend/app/models.py#L77) |
| `world_countries`, `world_indicators`, `world_data_points`, `world_dataset_state`, `world_ingest_runs`, `world_ingest_dataset_logs`, `world_forecasts`, `world_forecast_values` | national/Eurostat/BEA loaders, state/run logs, quality forecast → world catalogue/detail/compare/SSR; indicator identity `(provider,country,dataset,slice_hash)`, facts `(indicator,date)`, dataset `(provider,dataset)`. [models172](../../backend/app/models.py#L172) |
| `subnational_regions`, `subnational_indicators`, `subnational_data_points` | passport/FRED/BLS/BEA → subnational API/SSR/forecast; metadata country+slug/code; facts `(indicator,region,period date)`. [models443](../../backend/app/models.py#L443) |
| `economic_events` | official calendar source + seed/promote → calendar/upcoming/iCal/SSR; stable event key and provenance, public source guard. [models573](../../backend/app/models.py#L573), [calendar_seed](../../backend/app/services/calendar_seed.py#L493) |
| `users`, `oauth_identities`, `email_credentials`, `consents`, `auth_audit` | identity/auth/OAuth/account → session/account/export/admin; UUID user, provider+subject, normalized email; append-only consent kinds/version, audit. [models1381](../../backend/app/models.py#L1381) |
| `frontend_events`, `behavior_events`, `behavior_sessions`, `identity_links`, `server_sessions` | anonymous/authed collectors; stable hashes; portraits and user×visitor links; sessionize window rebuild → behavior/BI/Pulse; browser/session, visitor, account и computed session не одна identity. [models966](../../backend/app/models.py#L966) |
| `analytics_sync_runs`, `analytics_watermarks`, `metrika_counter_snapshots`, `metrika_goal_snapshots`, `metrika_report_snapshots`, `metrika_daily_page_metrics`, `metrika_search_phrases`, `raw_metrika_visits`, `raw_metrika_hits` | reporting/management/Logs import + watermarks → analytics_features/rollup/marts/BI; request hash, counter+visit/hit и interval/date собственные keys. [models636](../../backend/app/models.py#L636) |
| `webmaster_diagnostics`, `webmaster_search_queries`, `webmaster_indexing_daily`, `gsc_search_queries`, `seo_page_snapshots` | external analytics readers/snapshots → search demand/indexing/SEO views/Pulse; host/date/query/page keys и лаги отдельных источников. Submitted sitemap ≠ indexed pages. [models821](../../backend/app/models.py#L821) |
| `metrika_goals`, `direct_costs`, `partner_revenue`, `daily_traffic`, `daily_goals`, `daily_pages` | goals dictionary, optional cost/revenue connector, rollups → marts/BI/Pulse; visits Метрики, own events/pageviews, cost и revenue разных единиц и populations. [models1117](../../backend/app/models.py#L1117) |
| `agent_findings`, `agent_action_audit`, `experiments`, `hypotheses`, `telegram_outbox` | analytics proposals/executor, controlled experiments, Pulse hypothesis updates, Telegram archive → owner BI/bot/LLM context; proposed/approved/applied/error и nullable verdict различать. [models924](../../backend/app/models.py#L924), [models1276](../../backend/app/models.py#L1276) |

**Поле не равно внешнему обещанию.** Numeric precision/unit находятся в schema+metadata; date/period/frequency не взаимозаменяемы. DateTime conventions — naive UTC; публичные дни/границы аналитики — MSK. ORM nullable inference и defaults — исходный контракт SQLAlchemy; действующий PostgreSQL schema/version/owners/ACL сверяются ops отдельно. Миграционная декларация и наличие файла не доказывают применённую миграцию.

## 4. Реестры и lifecycle

- Parser registry [rosstat_cpi_parser.py:91](../../backend/app/services/rosstat_cpi_parser.py#L91): **34 class references** → parser_type literal в классе → factory/get_parser → BaseParser. Старый docstring BaseParser «24 parsers» не текущий счётчик. Unknown parser → log+None, caller решает статус.
- [DERIVED_SPECS:66/271/444](../../backend/app/services/calculation_engine.py#L66): handwritten specs + generated FamilyDef pipelines + `engine.register`. [FamilyDef list711](../../backend/app/data/view_model_families.py#L711) → builders964/1118 → backend seed/derived + generated frontend JSON. Список source expressions и mutations сохранён; computed entries не притворяются literal registry.
- [STRATEGIES](../../backend/app/services/forecast_strategies/registry.py): 14 explicit strategies. Unknown name → warning+None/legacy fallback; valid registry key не доказывает разрешённость частоты/истории/численную пригодность.
- National `_ADAPTER_MODULES` [world_national_ingest.py:76](../../backend/app/services/world_national_ingest.py#L76): 18 providers. Resolver поддерживает preferred class / `ADAPTER` / factory / matching provider; отсутствующий/несконфигурированный adapter → error/state, а не молчаливые опубликованные нули. YAML parsers [national276](../../backend/app/services/world_national_ingest.py#L276)/[subnational284](../../backend/app/services/world_subnational_ingest.py#L284) валидируют required fields, uniqueness, featured/default relationships. YAML identity в генераторе fingerprinted; семантический parse принадлежит этим валидаторам и прежним рецензиям.
- OAuth [registry.py](../../backend/app/services/oauth/registry.py): supported fake/google/yandex/vk, public3; actual available по credentials; fake только enabled+debug и startup assert. [SEO curated](../../backend/app/data/indicator_seo.py), [legacy redirects](../../backend/app/data/legacy_redirects.py), [site_urls](../../backend/app/services/site_urls.py) не являются списками безопасного удаления.
- Settings construction [config.py](../../backend/app/config.py): Pydantic `RUSTATS_`, `.env`, extraignore. Вычисляемые `public_origin/public_host/webmaster_host_id*` — методы/properties, не недостающие env fields. OAuth dynamic provider flag readers сохраняются как dynamic. Banxico [resolve_token:133](../../backend/app/services/world_adapters/banxico_sie.py#L133): explicit → `os.environ` RUSTATS/BANXICO/BMX → optional undeclared Settings attr → empty. `.env` extraignore не экспортирует неизвестное имя в `os.environ`; Docker должен передать его как environment. Это поправка activation, а не объявление adapter недействующим.
- Startup [main.py:488](../../backend/app/main.py#L488) config assertions → scheduler registrations → geoIP background/startup cleanup/catch-up empty source→forecast→sitemap. Job flags/triggers/lock TTLs доступны отдельно по каждому из39. Cron timezone преимущественно MSK, intervals/runtime start_date отдельно. Catch-up task не зарегистрирован cron и не делает startup-ready доказательством наличия данных.
- Shutdown [main.py:1156](../../backend/app/main.py#L1156): `_shutting_down`, scheduler waitFalse, public/analytics engine.dispose, Redis close. Interrupted-job alerts suppressed during shutdown; атомарный sitemap current не переключается на неполное поколение.
- Locks [main.py:243](../../backend/app/main.py#L243): state Redis SET NX EX + token-checked release; held skip; Redis failure **fail-open**; renewal нет. max_instances/coalesce — in-process APScheduler. Daily/evening ETL имеют разные Redis keys, shared local `_running_locks` защищает code лишь в одном процессе. World forecast CLI имеет отдельный `_WorldForecastLock` с refresh [pipeline260](../../backend/app/services/world_forecast_pipeline.py#L260); scheduled wrappers передают acquire_lockFalse и полагаются на outer TTL24h. Эти механизмы различаются.

## 5. Семейства сценариев K06

| Семейство | Успешный путь / empty / partial / error / retry / concurrency |
|---|---|
| Federal ingest | Active code→parser factory→fetch/validate→prune при replace_series→bulk_upsert→forecast/hooks→invalidate→commit. Empty различает parsed_zero/expected no_new_data. Fallback сохраняет более новые даты keep_after, помечает fallback_used. Exception rollback+failed log commit; CancelledError scheduler пишет timeout. Daily/late wait_for per-parser timeout, local code locks и derived closure. [BaseParser148](../../backend/app/services/base_parser.py#L148), [scheduler76/132](../../backend/app/tasks/scheduler.py#L76). BM01/BM02 ниже |
| Derived / forecast / CLI | Changed-code closure в CalculationEngine; `_execute` отсутствующий input или пустой computed output возвращает0 **без удаления старого derived**. Nonempty pruning/upsert caller commits. Full CLI [rebuild-all-derived](../../scripts/rebuild-all-derived.py) проходит все specs, commit потом invalidate; ошибки per-spec caught без savepoint — SQL abort нельзя считать изолированным успехом. [World CLI](../../backend/scripts/rebuild-world-forecasts.py) dry-run plan/filter/force/eligible, source-ready+quality gates/fingerprint; annual horizon1, null forecast допустим. [pipeline384/711](../../backend/app/services/world_forecast_pipeline.py#L384) |
| National ingest | Passport→adapter/ref/observations scale→metadata identity→reconcile→extent→dataset state; per-series savepoint и per-country commit; adapter error отдельный status. Run partial при series/cache error; commit не откатывается из-за последующей cache failure. [ingest815](../../backend/app/services/world_national_ingest.py#L815), [run1078](../../backend/app/services/world_national_ingest.py#L1078). Nonempty response не несёт completeness bool: BM01 |
| Eurostat | TOC/date/state→changed/quarantine→loader structure verdict→remap commit→per parsed slice atomic transaction→final world/catalog/SSR bump; state/log отдельно. Exact geo/hash kept без numeric compare; replacement требует same geo/frequency,≥6 overlap,≥90%close, unique best/one-to-one. Orphans сохраняют old history, автоматически не скрываются. [structure](../../backend/app/services/eurostat_structure.py#L89), [loader431/515/536](../../backend/scripts/load-world-eurostat.py#L431). BM04 |
| Russian regions | Artifact metadata commit; equal count skip else TRUNCATE annual+monthly/COPY transaction; EMISS monthly upsert и commit каждого месяца, terminal bump regions при changes. API fixed TTL keys; SSR namespace другой. Содержание artifact не сравнивается count guard; later-month exception оставляет earlier commit до terminal bump. [seed81](../../backend/seed_regional.py#L81), [EMISS252](../../backend/app/services/emiss_regional_parser.py#L252). BM03 |
| Foreign subnational / BEA | Passport→FRED/BLS merged+scale→metadata IS DISTINCT FROM→pair commits; partial country writes учтены для invalidation; metadata changes включают catalog bump. BEA archive/download state и transactional archive ingest отличаются. [subnational594](../../backend/app/services/world_subnational_ingest.py#L594), [BEA](../../backend/app/services/world_bea_regional.py); cache/partial contracts сохранены в §4 data-contracts |
| Read cache / catalogue | cache_get/set errors → miss/fail-open counters; namespaces have local5s memo. World-catalog uses state generation, fresh API key, cross-worker cold lock/versioned mirror, bounded stale/no-store, absent fallback503; typed invalidation3attempts then raises after committed data. [cache245/297](../../backend/app/core/cache.py#L245), [world850](../../backend/app/api/world.py#L850). Fixed legacy keys/SSR namespaces отдельные; broad bump не универсальный freshness proof |
| Identity / account | Email normalization+password verify/rehash, User/Credential/Consent/AuthAudit transaction commit→new stateRedis session→cookies; state failure может случиться после user commit. State slidingTTL + legacy cache migration; CSRF header matches session token on mutations; lockout namespace/IP/ident. OAuth state+cookie/PKCE→provider→provider-subject resolve; no auto-link merely by email. [auth135](../../backend/app/api/auth.py#L135), [session](../../backend/app/services/session.py), [security](../../backend/app/security/auth.py), [resolve](../../backend/app/services/identity/resolve.py) |
| Collectors / BI | First-party frontend+behavior flags независимы analytics integration flag. UA gate, hashed session/visitor, authenticated user from state session, batch dedup/portrait, identity link→commit. Client timestamps/anonymous payload имеют собственные validation bounds. Window delete+insert/commit phases→server sessions/goals/page/traffic marts; source populations/robot filters различаются; UI labels должны это отражать. [analytics261/321](../../backend/app/api/analytics.py#L261), [sessionize83](../../backend/app/tasks/analytics_rollups.py#L83), [run_rollups684](../../backend/app/tasks/analytics_rollups.py#L684). BM05 |
| ClickHouse | PG is source; event selected columns→closePG→thread executor CH insert→persist id cursor; replacing partitions5000 holdPG during inserts; identity_links full list. Failure soft versus site; insert-success/cursor-failure can retry samebatch, CH eventual replacement не inferred exactly-once. [sync185](../../backend/app/services/clickhouse_sync.py#L185), [stream262](../../backend/app/services/clickhouse_sync.py#L262). BM06 |
| SEO / sitemap / queue | Request host/locale/canonical redirects→SSR cache miss releasing DB before lock/semaphore→renderer/assets sig→HTML cache/OG. Sitemap source registry→bounded shards→generation+atomic current; reuse/content_changed dates retained. All existing canonical pages remain eligible per owner20Sep, no demand/age deletion policy. IndexNow state SPOP→debounce→HTTP→success marker or re-add on normal error; crash/re-add Redis failure lacks durable ack. [SSR200](../../backend/app/api/seo_pages.py#L200), [sitemap288](../../backend/app/services/sitemap_static.py#L288), [drain658](../../backend/app/services/indexnow.py#L658). Sitemap→SSR conditions still differ for today/<2points and compare/no commonperiod, source defect remains |
| Calendar / live ticker / export | Official source provenance gate and stable keys; events linking/promote differs forecast facts. Ticker MOEX/Binance snapshot Redis, stale/source/date/currency caveats remain. Export uses submitted displayed points, format/meta/history/quota gates and thread admission ownership on cancellation. [calendar](../../backend/app/api/calendar.py), [tickerworker](../../backend/app/tasks/ticker_worker.py), [export](../../backend/app/api/export.py), [admission16](../../backend/app/services/export_render.py#L16) |
| Outbound retry | Shared requests adapter total3/backoff2 statuses408/500/502/504, allowedGET/POST; default timeout60. Direct403/407/429/503 or network error trigger HTTP→SOCKS fallback; **proxy-hop network error with caller_proxies raises**, while proxy ban-status may continue to nexthop. Not all adapters use this client. [http_client28/100](../../backend/app/services/http_client.py#L28). External API version/quota/actual token availability belongs separate K09 proof |

### MCP: каждая связь

[index.ts](../../mcp/forecast-analytics-mcp/src/index.ts) stdio server → `api(path,init)` → `FORECAST_ANALYTICS_API_URL` default local8000 `/api/v1/analytics` → `X-Analytics-Token` из `FORECAST_ANALYTICS_API_TOKEN`. Backend [_require_analytics_token](../../backend/app/api/analytics.py#L25) допускает только непустой configured equality token. Missing client token, fetch failure, invalid JSON, non-2xx produce tool error; empty body→{}. Explicit timeout/abort/retry нет.

| Tool / schema / handler | HTTP / backend handler | Смысл и эффект |
|---|---|---|
| analytics_status39/43/44 | GET health / analytics_health110 | Health + last10sync runs/failed count; read |
| page_performance_deep_dive49/52/56 | GET pages / analytics_pages153 | limit integer1..500 default50; top_pages SQL read |
| search_query_cluster_analysis61/64/68 | GET search-phrases / analytics_search_phrases164 | default100; top_search_phrases read |
| detect_anomalies73/77/78 | GET anomalies / analytics_anomalies176 | detect_page_opportunities read; название не означает production anomaly monitoring |
| compare_deploy_impact83/87/88 | GET deploy-impact / analytics_deploy_impact182 | recent sync runs evidence, не измеренный causal deploy effect |
| metrika_stat_query93/96/107 | POST query/metrika / query_metrika137 | schema counter/metrics/dimensions/date/filter/limit→controlled reporting client; внешний read, reporting credentials/allowlist |
| propose_analytics_action112/115/123 | POST actions/propose / propose_action205 | policy classification + AgentActionAudit status proposed commit; внешнее изменение не выполняется |

Backend `/actions/{id}/apply` — **отдельный** route [analytics.py:229](../../backend/app/api/analytics.py#L229), equality approval_token + reevaluated policy + executor; это не восьмой MCP tool. Executor [action_executor.py](../../backend/app/services/action_executor.py) поддерживает только goal.create/update, recrawl.submit и finding.create; policy allow ≠ registered executor. Внешний успешный write предшествует audit final commit и не является общей транзакцией с PostgreSQL. Повтор применения/сбой записи аудита требует отдельного idempotency контракта; не объявлено безопасным exactly-once.

## 6. Реестр подтверждённых механизмов и границ

| ID / класс | Условие → подтверждённый результат | Доказательство / что осталось наблюдать |
|---|---|---|
| BM01 / нарушение полноты replace | stored2020/21/22, normalized **nonempty** response только2022 → отсутствующие2 даты удалены; empty[] сохраняет историю | Actual `reconcile_points` AST executed; [partial_replace](backend-mechanism-probes-2026-09-30.json). Completeness marker отсутствует в WorldSeriesPayload. Реальную неполноту источника/продовую потерю история не утверждает |
| BM02 / cache publication ordering | `BaseParser.run` invalidate→reader→commit; reader кладёт old committed1 в новую generation, commit publishes2 → stale cache possible | Actual run trace + explicit visibility double. Доказан порядок и условная ветвь; livePG/Redis race/frequency не измерены. Чистка кэша вручную не закрывает контракт |
| BM03 / regional owner+cache mismatch | Equal artifact/DB counts пропускают content revision; EMISS terminal `bump_namespaces('regions')` не меняет `fe:regions:monthly:v1:*`; SSR has separate namespace | Actual seed count skip + actual bump + exact API key assignment probe. При mismatch seed TRUNCATE обоих stores может заменить live monthly additions; этот source branch не запускался. Production source precedence/fixture fresh API послеTTL ещё отдельно |
| BM04 / Eurostat split publication | Accepted remap commit, slice1 success, slice2 raises → remap+slice1 остаются, loader final bump bypassed | Actual `run/apply_remaps` body with controlled persister failure. Real slice transaction established source, doubles commit; no production incident claim. Dataset/state retry может увидеть уже новые metadata |
| BM05 / session window semantics | Samevisitor pageviews4min по сторонам MSK chunk border → wholewindow1session vs separately2 | Actual `sessionize` body; finalizer/admin/SQL doubles. SESSIONIZE_WINDOW_DAYS3/run_rollups independent calls do not carry chunk. Leading non-pageview tail discarded; fixture covers pageview branch. Реальный вклад в BI на истории не измерен |
| BM06 / CH cursor late commit | id1 allocated earlier/invisible; committedid2 copied→cursor2; id1 becomes visible→next `id>2` skips1 | Actual `_sync_events` body and controlled visibility ordering. Source SQL/sequence permits order, no livePG/CH proof. Error retry/replacing merges/recovery/backfill and missed-history volume ещё не приняты |
| BM07 / scheduler lease | Samejob firstfn remainsrunning beyondTTL; another wrapper executes → peak2; held beforeTTL skips | Actual `locked_job` AST, fake atomicNX/time/token release. Renewal absent; Redis-down fail-open and different daily/evening keys статически установлены. Не заявлено фактического overlap продовых jobs |
| BM08 / conditional CORS | Different-origin POST with preflight → method policy GET/OPTIONS declines | Source declaration + existing POSTroutes. Sameorigin frontend proxy может исключать этот путь. Проверять конкретный dev profile, не blanket production failure |
| BM09 / action external side effect | Executor succeeds before DB audit commit, apply repeat not forbidden by status guard | [analytics apply229](../../backend/app/api/analytics.py#L229), [executor](../../backend/app/services/action_executor.py). Static publication boundary; no external calls. Нужны idempotency key/status/reconciliation semantics перед внешним automated apply |
| BM10 / measurement properties | p99/load/capacity/RTO/reliable restore app workflow/data history consistency cannot follow from source inventory | Ops evidence отдельно. Это недостаток измерений, не неопределённость перечисленного устройства; критерии приёмки находятся в readiness/ops protocols |

Предлагаемые точные актуализации canonical docs, без удаления истории:

1. `data-contracts.md` §2: сохранить старое «не воспроизводился» как состояние27Sep; дописать ссылку BM03 и новый статус isolated count/key proof30Sep. Live values и source ownership audit не объявлять закрытыми.
2. §«Непроверенные риски» п1/п2: дописать actual-body probes BM01–BM07 с premises; отдельно назвать ещё не выполненное livePG/Redis/CH multi-process acceptance. Старое «порядок кода» уточнить новым доказательством, не заменить на production incident.
3. Eurostat/window/CH dated contract table: remap/slice/final-bump failure, 4-minute cross-window case2vs1, late-id1>cursor2 case теперь объяснены и воспроизведены изолированно.
4. Identity/analytics/API/MCP §6: добавить ссылку на этот trace и отдельную proposal→apply boundary BM09; не называть всю analyticsAPI read-only.
5. README/architecture/workflow: entry link → independent inventory JSON/MD → acceptance/unknowns → canonical contracts/history/ops. Обязательный `python3 scripts/build-mechanism-inventory.py --check` вместе с существующими knowledge guards; при изменении source `--build` до последних hashes. Генератор не повышает review status.

## 7. Что выполнено и что не объявляется закрытым

Выполнено: независимый tracked состав, HTTP composition без пропусков, все ORM поля/constraints/relationships, jobs/flags/triggers/locks, settings/env readers, registry mutations/source links, Python CLI source scope, семь MCP traces, cross-ledger identity/localization сверка, восемь narrowly isolated probes, `--build/--check` и diff check.

K02 source coverage установлена для указанной области. K03–K06 содержательное основание — прежние ручные reviews + текущие источники/контракты + этот mechanism reconciliation. Machine syntax не объявляется полным пониманием каждого dynamic value. Источники внешних данных, реальный deployment, multi-process поведение, source data completeness и измеренные свойства принимаются по своим evidence protocols. Раздел6 содержит конкретные premises подтверждённых механик; «нужно разобраться» без условия/наблюдаемого результата не используется.

Перед объединением root должен проверить новые tool/review rows, сохранить SHA evidence в materials registry, регенерировать карты и провести cold-start verification с этим документом. В этом пакете нет коммита, выкладки или runtime исправления.

## 8. Итоговая сверка после объединения рецензий — 30 сентября 2026

Сверка выполнена повторно после root fixes и объединения workbook-reader row.
Предыдущий baseline403 и промежуточная запись с изменившимся terrain source
сохранены в [crosscheck JSON](backend-mechanism-crosscheck-2026-09-30.json);
текущее основание находится в `final_reconciliation_2026_09_30` с точными SHA
inventory/ledger и временем.

- **405/405** source SHA совпадают с текущими файлами и ручными рецензиями.
- **3655/3655** именованных Python definitions имеют точные name/line/end_line
  и содержательное purpose в соответствующей рецензии.
- **144/144** HTTP handler annotations согласованы;182 method/path pairs без
  дубликатов.57 ORM tables,626 fields,34 relationships,27 DTO,39 jobs,
  160 Settings и7 MCP tools сохранены; unresolved0.
- Missing/stale source rows, unmatched definitions/handlers и duplicate ledger
  paths: **0**. Новый reader имеет7 отдельных function annotations от владельца
  содержательного чтения материалов.

Это сверка идентичности и адресов поверх сохранённого ручного чтения, а не
повторное чтение неизменённых тел или доказательство правильности всех executions.
Actual-body mechanics сохраняют пределы §6; server/restore/materials имеют
собственные протоколы. [Независимая проверка knowledge tools](final-dossier-review-2026-09-30.md)
нашла3 guard/overlay дефекта и1 неточный счётчик; fixes повторно проверены.
Окончательная общая пересборка/gates и material identity registry принадлежат root.

## 9. Финальные байты после исправления tracked/index scope — 30 сентября 2026

Точное сравнение повторено после исправления двух генераторов и окончательной root-пересборки: backend inventory → indicator index → authored/generated ledger. Предыдущие snapshots, включая §8 и сравнение до CLI guard reader, сохранены. Последний срез — `final_reconciliation_2026_09_30` в [crosscheck JSON](backend-mechanism-crosscheck-2026-09-30.json).

- **405/405** source SHA согласованы между текущими байтами, независимым inventory и рецензиями; **3655/3655** именованных definitions и **144/144** handlers имеют точные name/line/end_line и непустой ручной purpose. Missing/stale/unmatched/duplicate paths: **0**.
- HTTP **182** method/path пары без повторов; ORM **57/626/34**, DTO **27**, jobs **39**, Settings **160**, MCP **7**, unresolved **0**. `python3 scripts/build-mechanism-inventory.py --check`: exit **0**; оба generated файла соответствуют источникам.
- Indicator map: **947** кодов до и после; **189** records изменились **только в `files`**. `summary` и `completeness` совпадают с HEAD. Число453 относилось к диагностической временной копии с untracked-материалами; оно не является delta итоговой карты.
- У `build-indicator-index.py` и `repo-inventory.py` default — Git tracked/index; `--include-untracked` включает необязательный рабочий срез, fallback без Git описан. Адресный regression проверяет оба генератора: untracked исключён, новый `git add` включён без commit, optional включает untracked. Семь targeted tests ранее прошли с теми же source SHA; общие app tests здесь повторно не запускались.

SHA-256 inventory: `7687c54b746bb9f907c504d8ac566fdfbcabecd7d9d7d87646382ffe2663244e`.

SHA-256 замороженного ledger: `33c2d25e5d59669003e73da0098587eead6deed668ecee49657c56056f6b25af`.

Сверка подтверждает точную идентичность источников и локализацию ручных аннотаций. Неизменённые тела заново не объявляются прочитанными; выводы о runtime/production и actual-body probes сохраняют границы предыдущих разделов.

## 10. Окончательная заморозка после HTML serialization fix — 30 сентября 2026

Root устранил расхождение порядка JSON keys между `refresh` и `--check`: HTML рендерится из сохранённого JSON. После root-пересборки выполнено окончательное сравнение текущих байтов и аннотаций. Предыдущая сверка §9 сохранена в `previous_final_reconciliation_before_html_serialization_fix`; итог — `final_reconciliation_2026_09_30` в [crosscheck JSON](backend-mechanism-crosscheck-2026-09-30.json).

- **405/405** исходников, **3655/3655** definitions, **144/144** handlers согласованы по SHA/name/line/end_line/purpose; missing/stale/unmatched/duplicate ledger paths и method/path pairs — **0**. Независимый состав:182 method/path pairs,57 tables/626 fields/34 relationships,27 DTO,39 jobs,160 Settings,7 MCP, unresolved0.
- Итоговый indicator index подтверждён отдельно:947 codes,189 changed records только`files`; summary/completeness совпадают с HEAD. Историческое временное число453 относится к untracked-inclusive диагностике.
- Root сообщил sourceledger **1312/1312**, **8474/8474** definition annotations, восьмой targeted regression и terrain`--check`PASS. Это root evidence; этот агент повторил только точную backend-сверку, не общие application tests.

Окончательный SHA inventory: `abf29662200b1745d2bb8a4599d518addcfe1e12d62f6730eb62201e5af2d867`.

Окончательный SHA ledger: `658f0cfa9eea3e6cd04ac13282112f749d66ba13dfe44627377b95765ba50e9b`.

Смысловая основа неизменённых тел — сохранённое ручное чтение. Эта final byte-сверка не заменяет runtime/production acceptance и не повышает уровень уверенности в механиках сверх §6. Два backend report файла заморожены; source, ledger и tool inventories здесь не изменялись.
