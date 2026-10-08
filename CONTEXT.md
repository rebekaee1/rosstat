# Forecast Economy — Project Context

## Логическая сессия и состояние копии аналитики — 2026-09-30

Локальное уточнение F05/F06 после `main 83c4555`:

- **Логическая сессия** — последовательность событий посетителя с разрывом
  менее 30 минут. Разрыв ровно 30 минут начинает новый burst; burst без
  pageview присоединяется к предыдущему с pageview, если он существует.
  Ключ — `(visitor_id_hash, started_at)`, день — МСК-день первоначального старта.
- **Расчётное окно** — объём обработки, а не новая граница визита. SQL
  восстанавливает историю посетителей окна; поток и компактный накопитель
  ограничивают Python-память. Окно ремонтирует и затронутую сессию слева.
- **Атрибуция** — связанный client SID имеет приоритет, если portrait start
  не позже logical end; fallback-портрет
  выбирается для логической сессии между `started_at−1 сутки` и `ended_at`.
  Будущий fallback другого окна больше не меняет старую сессию.
- **Прогресс event-копии** — cursor/committed ceiling/caught_up/deferred
  отдельно для двух таблиц. Это состояние конечного SQL-среза, не обещание
  отсутствия новых событий после его чтения. Старые cursor/heartbeat не
  доказывают завершённость нового replay.

[Основной контракт](docs/data-contracts.md#аналитические-окна-и-репликация-f05f06--2026-09-30),
[ADR-0010](docs/adr/0010-analytics-contour-identity-goals-marts-olap.md#2026-09-30--логическая-граница-сессии-и-committed-ceiling),
[проверки](docs/code-review/analytics-boundaries-acceptance-2026-09-30.md).
**F05b остаётся открытым:** current CH session copier не передаёт удаления
старых ключей и пропускает обновления старта вне двух суток. Правильный
PostgreSQL-результат не означает правильную CH session-витрину. Исторические
memory-pressure причины ниже сохраняются; общая capacity 4 vCPU не измерена.

## Региональная история и права обновления — 2026-09-30

Локальный контракт F03 после `main c2a883d`:

- **Годовой артефакт** — исходная история и ревизии имеющихся в файле ключей.
  Отсутствие старого года в новой редакции не отменяет сохранённое наблюдение.
- **Месячная начальная история** — артефакт, который заполняет отсутствующие
  месяцы. Существующее значение сохраняется, поскольку происхождение каждой
  точки в нынешней схеме не записано.
- **Живое месячное обновление** — ЕМИСС добавляет и пересматривает полученные
  точки. Год и месяц остаются разными осями хранения; пропуск в ответе не
  является удалением. Пределы истории относятся ко всему сохранённому ряду.
- **Публикация** — видимость записанной транзакции для API/SSR/OG после commit;
  ошибка последующего месяца не отменяет уже записанные месяцы.

Это уточняет старое «артефакт — единственный источник»: после живых обновлений
полная история включает БД и её резервную копию. Месячные ревизии нового
артефакта автоматически не заменяют существующие значения.
[Контракт](docs/data-contracts.md#региональный-контур-f03--2026-09-30),
[основание](docs/adr/0008-regional-bounded-context.md#2026-09-30--права-записи-артефакта-и-емисс),
[проверки и пределы](docs/code-review/regional-publication-acceptance-2026-09-30.md).
До отдельного выпуска это не поведение production.

## Защита истории и публикация после commit — 2026-09-30

Локальное исправление F01/F02/F04 после `main 506122b`:
national partial response означает merge, не удаление отсутствующих дат.
Replacement требует явно полного включительного окна; extent/автотекст
берутся из сохранённой БД. Федеральный CalculationEngine пишет SQL и возвращает
changed codes; commit owner публикует source/derived после успешной записи.
Eurostat сохраняет отдельные country/remap/slice транзакции и публикует каждую
после commit. Partial loader failure не продвигает applied TOC.

[Действующие контракты](docs/data-contracts.md),
[регрессии и пределы](docs/code-review/history-publication-acceptance-2026-09-30.md).
До отдельного выпуска это не поведение production. PostgreSQL/Redis outbox,
unknown commit outcome, DB0 outage и 4-vCPU capacity остаются отдельной работой.

**Last updated:** 2026-10-05 (волны правок интерфейса 04–05.10, календарь и категории сверены с кодом). Ранее 2026-09-30 (содержательная сверка frontend/docs на `main 972579f`; цикл знаний, валютные canonical, ticker и РСЯ; production этим проходом не опрашивался). Ранее 2026-09-27 (ночной I/O stall при ротации nginx-лога, `fe:ver:*` под `allkeys-lru` — operational traps ниже; текущий статус и границы доказательства — [backlog](docs/backlog.md#2026-09-27--проверка-выпуска-3-web-worker--scheduler)). Ранее 2026-09-25 (sitemap: потолок 50 000 URL, lastmod по содержанию, шард без полной пересборки — `CONTEXT.md::Sitemap protocol trap`).

> **Историческая хроника:** следующий абзац сохраняет решения на указанные даты. Поздние дополнения ADR и текущий код могут их уточнять или отменять; указатель сверок — [architecture-history](docs/architecture-history.md).

**Previous:** 2026-09-19 (**люди не 403 по fe_bind** — HTML и API данных ставят/перевыпускают куку, ферму режем UA и лимитами nginx, не страной и не чужим /24. Ранее 2026-09-06 (**вход без fe_bind** — `/api/v1/auth/*` не режем: SPA `/register` куку не ставит, callback VK меняет /24. Ранее тем же днём (**HTML без заглушки, VPN/хостинг не 403** — человек всегда получает страницу, `fe_bind` на этом ответе; API данных без куки режем. Ранее 2026-09-04, день (**backend cgroup 1536M** на хосте 8 ГБ. Ранее тем же днём (**инцидент: Chrome UA reduction ≠ Playwright** — `Chrome/N.0.0.0` это заголовок живого Chrome с 101, правило 403-ило людей; снято. Ранее тем же днём (**антискрейп: bind на HTML + хостинговые ASN** — чужая `fe_bind` больше не перевыпускается на страницах; режем Hetzner/OVH/Alibaba/AWS по ASN, не по стране. Гео пуст. Ранее тем же днём (**bind-cookie вместо гео-блока** — ферма крутит страны; `fe_bind` = HMAC(/24|/48, день). Гео `SCRAPE_BLOCK_COUNTRIES` пуст, аварийный рычаг). Ранее той же ночью (**BI-in-request trap: дашборд в фоне (202/SWR), индекс соседей мировой карточки, postgres 2,5G** — открытие BI ставило диск и весь сайт; `CONTEXT.md::BI-in-request trap`). Ранее тем же днём (**fail2ban: `backend=polling` + volume только HTML-каталог, ханипот убран из sitemap** — иначе jail банит Яндекс; `CONTEXT.md::Anti-scrape`). Ранее тем же днём (**РСЯ: гейт «реклама только человеку» + обновление блока на SPA-навигации** — робот просил объявление и не показывал, `fillrate` 97%→11,5% при неизменной выручке; `CONTEXT.md::Yandex.RSY`). Ранее 2026-09-03 (**индексация: analytics_engine, статические sitemap, INDEX_POLICY, гео-блок SG,PL**; живые счётчики URL — `/sitemap-stats.json` и `docs/site-inventory.json`). Ранее 2026-08-27, поздний вечер (**восстановление прода завершено по recovery-рецепту** — сайт жив на `774e615`: контейнеры из образов `:774e615`, БД откачена до `20260713_partner_rev`, git выровнен; живой прогон дал 3 поправки в рецепт: мигратор только через `docker run` с URL из `.env`, после downgrade перетегировать движущие теги образов в старые SHA + force-recreate (иначе entrypoint нового образа повторно накатит схему), после восстановления сверять счётчики per-indicator против бэкапа — окно работы нового кода успело усечь историю 5 товарных YoY-рядов (−9 643 точки, восстановлены upsert'ом ADR-0002); детали — `CONTEXT.md::Deploy-scope trap`). Ранее вечером (**Deploy-scope trap: «main» ≠ «одобрено к выкладке»** — инцидент: деплой «анти-скрейпинг» вытянул ff-only весь накопившийся `main` с незаказанной мировой экономикой; автооткат против разогнанной схемы БД = backend crash-loop, сайт 502 ~40 мин; правила: `deploy/approved-shas.txt` (пустой = запрет), предупреждение о миграциях в пачке, migration-direction guard в `scripts/deploy.sh`; рецепт recovery — `CONTEXT.md::Deploy-scope trap`). Ранее 2026-08-27 (LLM-egress trap: внешний OpenRouter-релей молча умер 2026-08-22 после ручного kill — Пульс шесть дней ходил в фолбэк; tinyproxy восстановлен + `Restart=always`, горячий резерв `tor-http-bridge` на проде; details в `CONTEXT.md::traps`). Ранее 2026-08-16 (ADR-0013 Proposed: страна = первый сегмент URL, регионы внутри `/russia`, path-cut на `.com` затем path-identical переезд на `.ru`; карта и счётчики — `docs/backlog.md::Карта миграции URL`). Ранее тем же днём (мировой оперативный срез на официальных первоисточниках: новый парсер-тип `fred_csv` — спотовый Brent Управления энергетической информации США, индекс доллара и доходность десятилетних госбумаг Федрезерва; площадь и население в профиле территории страны — курируемый справочник `app/data/world_country_area.py` плюс concept `population`; страница рейтинга стран только по сопоставимым показателям. Ранее 2026-08-06 — ADR-0011: Eurostat-мир — отдельный TOC-driven data plane с shadow/provenance; до доказанной `sum|avg|last` synthetic частоты карточек fail-closed). Ранее 2026-07-06, вечер (CTO-аудит, дозакрытие хвостов: trap «nginx map с capture-группой» добавлен в traps; adjacency-guard `period_over_period{,_abs}`; батч-hero каталога; COPY-сидер регионов; полная матрица покрытия — `docs/backlog.md::2026-07-06`. Ранее Волна 5: сверены счётчики рядов, source, derived, парсер-типов, ops и generic-семей — актуальные цифры живут в разделах «Indicator» и «Parser» ниже (2026-07-08: минус один авто-сиблинг `wages-nominal-avg-year` после `overrides={"avg-year": "wages-nominal-annual"}` — созвон «На правки 13»); derived-пересчёт стал инкрементальным по dependency-графу в topo-порядке (П-2), «пересчитывает все 31» — история. Ранее 2026-06-24: Фаза 3 — углублена история source-рядов до пола источника: `usd-rub`/`cny-rub`/`gold-price`→1998, `eur-rub`→1999, `m2`→1992, `current-account`→1998 (через `backfill_from`/`backfill_from_year`, деноминация-aware floor; каскад протянул на все уровни матрицы); знаковые квартальные прогнозы закрыты — `trade-balance` тождеством `exports−imports` (`derived_from_source` op=`subtract`, 2-source), `current-account` стратегией `signed_quarterly` (level-diff); skip-лист рядов на полу источника — `docs/backlog.md::A0.3`. Ранее — новая стратегия `generic_quarterly` для положительных квартальных рядов — `exports`/`imports`/`external-debt` получили квартальный прогноз; каскад заполнил прогноз новых yoy-кв/год sibling'ов A0.1. Ранее 2026-06-23 (прогноз во всех режимах: `_mode_forecastable` в `view_model_families` — флаг режима выводится из частоты базы (`yoy/mom/qoq` показывают derived-прогноз, не хардкод False); `monthly_auto` = 36 (+`housing-affordability`/`-primary` собственной моделью на ряде отношения, ретрейн через `scheduler._retrain_self_modeled_derived`); `hero_change` (ускорение Г/г в п.п.) на индекс-карточках; фикс key-rate `_handle_forecasts`). Ранее 2026-06-22 (forecast registry: `monthly_auto` обновлённый алгоритм, 34 ряда).
**Part of:** [`AGENTS.md`](AGENTS.md) (точка входа для AI-агента).
**See also:** [`README.md`](README.md), [`docs/workflow.md`](docs/workflow.md), [`docs/enterprise_resilience.md`](docs/enterprise_resilience.md), [`docs/data_sources.md`](docs/data_sources.md), [`docs/analytics_api_inventory/`](docs/analytics_api_inventory/), [`docs/adr/`](docs/adr/). Parser internals (CBR/Минфин/Rosstat) живут в docstrings `backend/app/services/*_parser.py`.

> Domain glossary for the project. Every architectural discussion, ADR, and refactoring proposal should use the terms defined here. If a discussion needs a new term, add it to this file before finishing.

## Документы рядом

| Файл | Назначение |
|------|------------|
| [`AGENTS.md`](AGENTS.md) | Точка входа для AI-агента: с чего начать, как читать документацию, как её актуализировать |
| [`README.md`](README.md) | Высокоуровневая карта стека, API, indicators, deploy |
| [`docs/workflow.md`](docs/workflow.md) | Модель работы, локальный dev, прод-деплой, smoke C |
| [`docs/search.md`](docs/search.md) | Поисковое намерение, федеративное discovery, области локальных полей, покрытие, состояния и границы исторической телеметрии |
| [`docs/enterprise_resilience.md`](docs/enterprise_resilience.md) | Rate-limit, CSP, asset-hash trap, бэкапы, чеклист канарейки |
| [`docs/data_sources.md`](docs/data_sources.md) | Точная карта «индикатор → файл/endpoint» для всех 118 source-индикаторов. Single source of truth — обязательно обновлять при правке источника |
| `backend/app/services/*_parser.py` docstrings | Parser internals (CBR / Минфин / Rosstat): source URL, лист, row/col mapping, `model_config_json` schema, traps. Канонично живёт рядом с кодом |
| [`docs/analytics_api_inventory/`](docs/analytics_api_inventory/) | Инвентарь Yandex API (Metrika, Webmaster) + статус реализации |
| [`docs/adr/0001`](docs/adr/0001-derived-indicators-engine-shape.md) | Engine shape: 829 derived через `DERIVED_SPECS` (44 ручных + 785 generic) + 28 чистых ops |
| [`docs/adr/0002`](docs/adr/0002-derived-always-reflects-source.md) | Инвариант: derived всегда отражает source (`bulk_upsert` идемпотентен) |
| [`docs/adr/0003`](docs/adr/0003-seo-single-source-server-rendered.md) | SEO single-source: backend SSR через `__spa-index.html` + Vite asset discovery |
| [`docs/adr/0004`](docs/adr/0004-rosstat-russian-canonical-sdds-deprecated.md) | Rosstat русский canonical, SDDS English deprecated. Pilot: gdp-nominal end-to-end 2026-05-10 |
| [`docs/adr/0005`](docs/adr/0005-official-calendar-source-bound.md) | Calendar source-bound: public dates only from official source/rule with provenance |
| [`docs/adr/0006`](docs/adr/0006-indicator-card-unification.md) | Indicator card unification: ось «карточка vs derived vs variant vs frequency» (звонок 2026-05-22) |
| [`docs/adr/0008`](docs/adr/0008-regional-bounded-context.md) | Региональный блок: bounded context `регион × показатель × год`, артефакт вместо ETL, дособор из архивных редакций |
| [`docs/adr/0009`](docs/adr/0009-behavior-stream-first-party.md) | Поведенческий поток first-party: `behavior.js` автосбор (клики/мышь/скролл/dwell/copy) → `behavior_events`, retention сырья + вечные агрегаты в Пульсе |
| [`docs/adr/0010`](docs/adr/0010-analytics-contour-identity-goals-marts-olap.md) | Аналитический контур: visitor_id + identity_links, серверные сессии (30 мин), таксономия целей, rollup'ы, единый слой витрин `analytics_marts`, OLAP-копия ClickHouse |
| [`docs/adr/0011`](docs/adr/0011-world-eurostat-data-plane.md) | Eurostat-мир: отдельный TOC-driven data plane, shadow/provenance и fail-closed частоты |
| [`docs/adr/0012`](docs/adr/0012-world-multi-provider-official-first-forecasts.md) | Multi-provider world: только официальные первоисточники, provider-aware identity, единый adapter contract и quality-gated прогнозы |
| [`docs/adr/0013`](docs/adr/0013-country-first-url-architecture.md) | Страна = первый сегмент URL; регионы внутри `/russia`; path-миграция на `.com`, затем path-identical переезд на `.ru` |
| [`docs/adr/0014`](docs/adr/0014-subnational-regions-generic.md) | Субнациональные регионы (штаты США и далее) — generic bounded context страна × регион × показатель × период; Россия остаётся в ADR-0008 |
| [`docs/adr/0015`](docs/adr/0015-us-bea-regional-catalog.md) | Массовый каталог официальных BEA-рядов по США и штатам: полная история, проверка охвата, еженедельные пересмотры |
| [`docs/adr/0016`](docs/adr/0016-federated-public-search.md) | Глобальное discovery четырёх контуров без объединения хранилищ; явная география, понятие и период обязательны |
| [`docs/adr/0018`](docs/adr/0018-crystal-without-borders-design-system.md) | Ось интерфейса: «хрусталь без границ» (слои стекла вместо рамок, бюджет блюра, сцена света, ассеты бренда); основной документ — [`docs/design-system.md`](docs/design-system.md) |
| [`docs/indicator-family-playbook.md`](docs/indicator-family-playbook.md) | Семейство до продакшена: продуктовая модель, уровни UI A/B/C; эталоны **ИПЦ** (4×10) и **жильё** (2×3); фазы A–G |

---

## History-access-reliability (2026-09-20)

Локальная реализация в `fix/history-access-reliability`, не утверждение о состоянии прода. Статус и оставшаяся приёмка — [backlog](docs/backlog.md#history-access-reliability-2026-09-20).

- **История и индекс (решение владельца 2026-09-20):** все действующие публичные canonical-страницы отражаются в sitemap; отдельного отбора по curated dataset, возрасту, популярности или числу наблюдений сверх условий самого SSR нет. Мировые годы включают национальные источники; год РФ достаточно одной существующей точки. Региональные хабы/карточки/годы включают доступные SSR виды `region/district/country` и unlisted-ряды; помесячные региональные карточки учитываются наряду с годовыми. Сравнения содержат все пары, удовлетворяющие общим с SSR условиям данных, а не топ регионов/соседние страны; все непустые недефолтные годы мировых рейтингов включены. Listing сохраняется только там, где SSR сам возвращает 404 для unlisted. Редиректы, дубли, пустые/несуществующие периоды, неактивные страны, служебные поверхности и query-перестановки не создают дополнительных страниц. Диапазоны формата года совпадают с текущими SSR-роутами. `months-N`, `regional-N`, `world-years-N` и потоковая сборка сохраняют всё покрытие; после смены политики ключи chunk bounds/count имеют версию `public-v3`. Sitemap-счётчик отражает опубликованную генерацию, а не поисковый индекс; актуальные числа — `/sitemap-stats.json`. IndexNow отправляет длинный хвост ограниченными порциями и останавливается на 429.

- **Доступ:** `fe_bind` — совместимая необязательная cookie, не доказательство человека; отсутствие/несовпадение, страна и хостинговый ASN не дают 403. nginx SSR/OG per-IP лимиты действуют для всех UA, включая заявленных поисковиков. Общий SSR-бакет убран; отдельный общий OG-потолок сохранён. Малоскоростной скрейпер с браузерным UA этим не отличим от человека. Исторические правила ниже не описывают новую реализацию.
- **Ассеты:** старые и новые hashed-ассеты публикуются до нового HTML; на успешном пути очистка до трёх релизов — после watch, при откате — после повторной публикации восстановленного релиза. Совместная сборка backend/frontend и `no-store` HTML остаются обязательными. Детали — [workflow](docs/workflow.md#прод-деплой) и [enterprise_resilience](docs/enterprise_resilience.md#frontend-и-кэш).
- **Пульс:** UTM-строки не означают число активных рекламных кампаний; `traffic_sources.id=ad` — платное привлечение, не обязательно Директ; органический поиск и доход площадки РСЯ — отдельные показатели. `missing/failed/stale/invalid` не превращаются в ноль. Период, основной счётчик, время снимка и семплирование сохраняются в metadata; доход РСЯ за день берётся только из совпадающей даты, не из суммы окна.

## Рельеф и основания архитектурных выводов

Сверка документации с кодом: **2026-09-27**, baseline `b684290067bf`.
[Graphify-срез](docs/project-terrain.md) хранит полный инвентарь Git-файлов,
извлечённые связи, границы покрытия и контрольные суммы. [Архитектура](docs/architecture.md)
объясняет контуры, [контракты](docs/data-contracts.md) — переходы между ними,
[история](docs/architecture-history.md) — причины решений и поздние уточнения.
Динамические связи через HTTP/БД/Redis проверяются по контрактам; статический путь
в графе сам по себе не доказывает поток данных или runtime-дефект.

## Приёмка собранной реализации — 2026-09-30

[Досье](docs/project-knowledge-acceptance.md) связывает независимые inventory
элементов/связей, текущие рецензии, сценарии, внешний исторический материал и
проверенные startup/restore/auth. Конфигурация 4vCPU и действующий host Tor bridge
описаны в ops evidence. Known defect, unavailable source и unmeasured capacity
различаются в [реестре](docs/knowledge-unknowns.md). Сбор текущей доступной реализации
завершён; полный failover, числовая истина каждого upstream и вся недоступная история
не объявляются принятыми.

## Цикл знаний и текущие уточнения — 2026-09-30

Каждая обычная задача включает чтение затронутого кода, прежних рецензий,
ADR и истории, проверку producer/consumer и актуализацию основного документа,
рецензий и карт. Порядок и условия завершения — [knowledge-workflow](docs/knowledge-workflow.md).
Короткий вход — [AGENTS](AGENTS.md); действующие рецепты владельца —
[agent-recipes](docs/agent-recipes.md). Прежний AGENTS сохранён побайтово в
[архиве](docs/code-review/source-documents/AGENTS-before-knowledge-workflow-2026-09-30.md);
его старые ссылки/номера строк относятся к исходному расположению в корне.
Архив и хроника объясняют причины, текущая инструкция находится в тематическом документе.

Основание этого дополнения — локальная `main 972579f0b95b70d0ac8d4293331cd8d18c2521fe`
и прочитанная дельта после точных версий прежних рецензий. [Отчёт и ограничения](docs/code-review/frontend-docs-delta-2026-09-30.md)
различают полное чтение, прежнее чтение с новой дельтой и метаданные.
Датированные prod-наблюдения 27–29 сентября сохраняются как свидетельства своего времени;
наличие механизма в main не устанавливает текущий production или полноту K01–K12.

- **Валюты — исключение из country-first URL:** `/currencies`,
  `/currencies/indicator/{code}` и периоды. Список валютных баз и производных
  задают `site_paths.py` и frontend `sitePaths.js`; старые `/indicator` и
  `/russia/indicator` ведут через серверную карту редиректов. Сырьё вроде Brent
  этим исключением не становится валютой. Поиск, breadcrumbs и generated page meta
  должны пользоваться тем же построителем пути.
- **Сравнение:** одна concept-группа допускает страны с доказанной сопоставимостью.
  Различающиеся базовые годы индексов цен требуют общей базы 100 на первой общей
  положительной дате фактических наблюдений внутри выбранного окна; нет такой даты —
  empty state. Процентные и знакопеременные ряды к базе 100 не приводятся.
  Мировые ряды сохраняют официальную частоту. Источники: `compareRepresentation.js`,
  `ComparePage.jsx`, `useCountryComparison.js` и связанные компонентные тесты.
- **Отображение источника:** основная карточка при отсутствии точного URL показывает
  имя источника текстом; ложный fallback на российский хаб убран в
  `IndicatorMethodologyPanel.jsx`. У быстрых страниц свой контракт внутренней
  навигации; внешний source URL в provenance/JSON-LD не отменяется.
- **Охват главной и каталог:** RU-блок отдельно считает региональные ряды России
  (`russia_regional_indicators_count`, совместимый fallback старого payload),
  EN сохраняет мировой охват и подпись штатов. Огромный каталог любой страны
  ограничивает начальный DOM и предлагает «Показать ещё»; список данных доступен
  через разделы и поиск, это не удаление рядов. Пустой EN-поиск начинает с
  curated US-пула; при вводе подключаются другие страны. **Позднее уточнение
  30.09, локальная новая версия:** ввод использует единый `/search` для стран,
  территорий и рядов всех четырёх контуров; empty suggestions сохраняются.
  [Контракт и границы](docs/search.md), выпуск отдельно от реализации.
- **Backend — датированная связь с новым разбором:** [backend-дельта](docs/code-review/backend-delta-2026-09-30.md)
  подтверждает `annual horizon=1` в изменённых seed/strategy/API/world/territory
  путях; допустимая поправка неполного годового факта сохраняется. Годовая
  fingerprint требует будущей перетренировки старой двухлетней модели, но её
  исполнение на сервере этим чтением не установлено. Python `visit_is_robot`,
  SQL `metrika_visit_not_headless` и CH raw visits используют разные выборки;
  их агрегаты нельзя автоматически считать одинаковым человеческим трафиком.
  Eurostat loader фиксирует remap metadata отдельным commit, факты — транзакцией
  каждого parsed slice, а cache namespace bump — лишь в конце loader. Это
  несколько границ записи, а не атомарная замена всего dataset; ошибка после
  remap может оставить прежние факты под новым slice до следующей записи.

## What this is

`forecasteconomy.com` — публичная аналитическая платформа официальной макроэкономической статистики по странам. Собирает данные национальных статистических ведомств, центральных банков, Евростата и МВФ; по России покрытие особенно глубокое (Росстат, Банк России, Минфин). Считает производные ряды и прогнозы, отдаёт фронтенду + поисковикам + соцботам + embed-виджетам.

Английский канон — apex `forecasteconomy.com`; русский — `ru.forecasteconomy.com` (ADR-0013).

- **Backend**: Python 3.12, FastAPI 0.115 + Uvicorn, SQLAlchemy 2.0 (async, asyncpg), Alembic, APScheduler, statsmodels (forecaster + SARIMA-семейство), pandas/openpyxl/xlrd (parsers), beautifulsoup4 (HTML), requests/httpx (HTTP), Redis 7 (cache).
- **Frontend**: React 19, Vite 7, Tailwind 4, Recharts 3, TanStack React Query 5, GSAP 3, React Router 7, Axios, Lucide, серверный Excel/CSV-экспорт через `api/export.py`, `@sentry/react` (только фронт — backend без Sentry).
- **Infra**: Docker Compose × 7 (backend: 3 web worker, scheduler: отдельный процесс, frontend, postgres-16, redis-7, redis-state, clickhouse), Caddy reverse-proxy на хосте (HTTPS + CSP с десятками `mc.yandex.*` доменов + `frame-ancestors *` для embed), Nginx внутри контейнера frontend (роутинг между SPA-shell и backend SSR), Yandex.Metrika (counter `107136069`) + Yandex.Webmaster, Telegram alerts (`alerting.py`), кастомный Forecast Analytics MCP (`mcp/forecast-analytics-mcp/`).
- **Прод**: `201.51.11.170` (Timeweb Cloud, Ubuntu 24.04).

---

## Domain glossary

### Indicator

Отслеживаемый экономический показатель. Каждый индикатор имеет:

- `code` — slug (`cpi`, `usd-rub`, `gdp-nominal`, `inflation-annual`).
- `name`, `name_en`, `description`, `methodology` — для UI и SEO.
- `unit` — `%`, `руб.`, `млрд руб.`, `млн чел.`, `индекс`, `‰`, `ед.`, ...
- `frequency` — `daily`, `weekly`, `monthly`, `quarterly`, `annual`.
- `source` — `Росстат` / `Банк России` / `Минфин`. Хранится строкой; используется фронтом для подписи и SEO. Терминология «ЦБ РФ» допускается в текстах, но в БД канон — «Банк России».
- `parser_type` — какой парсер обновляет ряд (`rosstat_cpi_xlsx`, `cbr_fx_xml`, `derived`, ...).
- `category` — русская строка категории (`Цены`, `Ставки`, ...). Маппится на `slug` фронта (`prices`, `rates`).
- `model_config_json` — все остальные параметры: `forecast_steps`, `backfill_from_year`, специфика парсера (`dataservice` блок, `bop_target` блок, `element_id`), `approved_forecast_values`, `forecast_strategy` (диспатчинг в реестр стратегий), `derived_forecast` блок (для прогноза-производного-от-источника), `forecast_transform` (для frontend re-scaling, например `cpi_index`).
- **Editorial поля для SEO** (живут в БД, редактируются без деплоя):
  - `seo_title`, `seo_description` — meta для индикатора, fallback к шаблону.
  - `seo_keywords` — meta keywords (37 ручных override + `default_keywords()` fallback).
  - `seo_blocks` — JSON-массив `{title, body}` дополнительных секций под графиком.
  - `is_listed` — boolean: показывать ли карточку индикатора в листинге категории. По умолчанию `true`. `false` — карточка скрыта из листинга, но ряд должен оставаться достижим через generic sibling, variant, frequency switcher или bespoke resolve (anti-orphan); один из вариантов — `VariantGroupPicker` внутри родительского индикатора (например, `cpi-food-quarterly` скрыт, виден только при выборе «Состав индекса → продовольственные → квартально» на странице `cpi`).

Хранится в таблице `Indicator`. **Текущее количество (2026-08-29):** 947 рядов в seed; точное число — в `seed_data.py` и `/api/v1/system/status`. Из них 118 source-индикаторов (через 34 парсер-типа) и 829 derived (через `DERIVED_SPECS`: 44 ручных + 785 сгенерированных generic view-mode-семьями, см. `view_model_families.py`).

### DataPoint

Одна точка временного ряда для индикатора. `(date, value)`. Хранится в `IndicatorData` с `UniqueConstraint(indicator_id, date)`.

### Source

Официальный поставщик данных:

- **Росстат** (`rosstat.gov.ru`, `eng.rosstat.gov.ru`). Форматы: SDDS XLSX (стандарт IMF), КЭП XLSX (`ind_MM-YYYY.xlsx`), HTML-бюллетени (недельный CPI), демографические XLSX, годовые XLS (наука/инновации, основные фонды).
- **Банк России** (`cbr.ru`). XML (FX, gold), HTML/UniDbQuery (KeyRate, RUONIA, monetary, reserves), DataService JSON (rates по срочности — mortgage/deposit/auto-loan/credit-rate-corp/ind, M2, current account, exports/imports), XLSX (BOP, debt).
- **Минфин** (`minfin.gov.ru`). CSV для бюджета (revenue, expenditure, deficit).

Каждый источник требует свой SSL/CA setup (Росстат — русские CA-сертификаты, `backend/certs/russiantrustedca2024.pem` через `RUSTATS_ROSSTAT_CA_CERT`).

**Доступ к rosstat.gov.ru из tooling/curl/python**: всегда через `--cacert backend/certs/russiantrustedca2024.pem` (или `verify=` в requests). Без сертификата `rosstat.gov.ru` отдаёт SSL-handshake error / Chrome `chrome-error://chromewebdata/`. `eng.rosstat.gov.ru` работает по стандартному cert, но это SDDS-зеркало и лагает на год (см. trap «SDDS English vs Rosstat русский»).

**Перечисление файлов раздела rosstat**: для категории `/statistics/<section>` (например `/statistics/price`) — `curl --cacert <cert> https://rosstat.gov.ru/statistics/price -o page.html && grep -oE 'href="[^"]*\.xlsx?"' page.html | sort -u` даёт полный список XLSX в разделе. Для `/statistics/price` (категория «Цены») — **94 XLSX** (audit 2026-05-08).

**Политика канонического источника (2026-05-10)**: для индикаторов с источником в Росстате — **only** русский XLSX из `rosstat.gov.ru/statistics/<section>/`, **never** SDDS-английский (`eng.rosstat.gov.ru/storage/mediabank/SDDS_*.xlsx`). См. trap «SDDS English vs Rosstat русский» и план миграции.

### Parser

Конкретная реализация ETL для одного формата источника. Базовый класс `BaseParser` (`backend/app/services/base_parser.py`) — **template-method**: финальный `run()` оркеструет fetch → parse → validate → upsert → forecast retrain → cache invalidate в одном месте. Дочерние классы реализуют `_fetch_and_parse(db, indicator, cfg, fetch_log) -> (points, source_url)` (обязательно) + опциональные hooks `_validate(points, cfg)`, `_post_upsert(...)`, `_handle_forecasts(...)`. Это устранило ~1100 строк boilerplate, унифицировало статусы `fetch_log` и каскад retrain'а.

**Текущее количество (2026-08-22):** 34 парсер-типа в `PARSER_REGISTRY` (см. `rosstat_cpi_parser.py`, регистрируется как singleton-импорт из исторических соображений — артефакт). Включают Rosstat-парсеры (`rosstat_*_parser.py`, в т.ч. demo/ind/science/fixed_assets/weekly_price), CBR (`cbr_*_parser.py` + `cbr_keyrate.py` helper), Минфин (`minfin_budget_parser.py`), Binance (`BinanceBtcUsdtParser`, BTC/ETH/SOL), MOEX (`MoexIndexParser` — индексы и товарные, `BrentDailyFredParser` — legacy-имя, источник MOEX ISS), FRED-CSV (`fred_csv` — публичные ряды первоисточников без ключа: спотовый Brent Управления энергетической информации США, индекс доллара и доходность десятилетних госбумаг Федрезерва). Два типа зарегистрированы, но в seed не используются (задел, не удалять без ревизии прод-БД): `cbr_dataservice_sum`, `cbr_monetary_html`. Файл `rosstat_sdds_fetcher.py` существует, но в PARSER_REGISTRY не зарегистрирован — deprecated (ADR-0004). Один парсер обычно обслуживает несколько индикаторов одного источника: CbrFxParser → 3 валюты; RosstatCpiParser → 4 листа CPI; CbrDataServiceParser → 16+ ставок и агрегатов ЦБ.

### Derived indicator

Индикатор без собственного источника. Считается чистой функцией от других индикаторов. `parser_type = "derived"`. Запускается из `CalculationEngine.run_for_updated_sources` после daily ETL.

**Инвариант (ADR-0002):** *derived[t] всегда выводимо из текущего state source-рядов на момент последнего ETL-батча с новыми строками или ревизиями* (`records_added > 0` или `records_updated > 0`). CalculationEngine пересчитывает derived от первой до последней точки (idempotent — `bulk_upsert` записывает только реально изменившиеся значения). С 2026-07-06 (П-2 CTO-аудита) пересчёт **инкрементальный**: dependency-index строит транзитивное замыкание зависимых от реально обновившихся source и обходит его в топологическом порядке (цепочки derived-от-derived до 4 уровней); полный прогон всех спецификаций — только `scripts/rebuild-all-derived.py`. Не «инкрементальный накопительный снимок», а чистая функция source. Если source ревизуется задним числом — derived перетягиваются автоматически тем же прогоном (см. ADR-0002 «Limit of the invariant — pure-revision day»).

**Граница инварианта.** Инвариант односторонний: `bulk_upsert`-only. Если source-точка **удаляется** вручную (DELETE из IndicatorData), соответствующая derived-точка остаётся в БД как осиротевшая — engine не знает, что нужно её удалить. Это явный compromise (см. ADR-0002): автоматическое удаление derived создавало бы риск массовой потери данных при ошибке pure op. Ручные коррекции source требуют ручной чистки derived или прогона `scripts/rebuild-all-derived.py`.

Реестр операций (`backend/app/services/derived_ops.py`) — **28 публичных чистых функций** без `db`/`async` (актуализация 2026-08-22; полный список — сам модуль; orphaned `annual_inflation` / `affordability_index` / `rebase_to_index` удалены в чистке 2026-06-24; 2026-08-22 добавлен `series_ratio` для кросс-курсов ЕЦБ). Ядро:
- `quarterly_index` — chained product 3 месячных индексов CPI (для `*-quarterly`).
- `december_to_december` — годовая инфляция «Dec_Y / Dec_{Y-1} − 1» (для CPI-семьи и PPI `*-annual`; пришла на смену rolling-12M в 2026-05-06, см. ADR-0001 «Subsequent additions»).
- `annual_sum` — сумма квартальных или 12 месячных значений (для `gdp-{nominal,real}-annual`).
- `yoy`, `qoq` — рост к 12 мес назад / к предыдущему кварталу (в %).
- `yoy_abs` — **абсолютная** разница к 12 мес назад в единицах источника (звонок 2026-05-22, для balances со знаком, где % бессмыслен).
- `quarterly_avg`, `rolling_avg` — для unemployment.
- `wages_real` — особая, 2 источника (`wages-nominal`, `cpi`).

Реестр спецификаций (`calculation_engine.DERIVED_SPECS`) — **829 entries** (44 ручных + 785 из `view_model_families.iter_derived_specs()`). Ручное ядро:

- **CPI семейство:** `inflation-quarterly` ← `cpi`, `inflation-annual` ← `cpi`, и аналоги для `cpi-food/nonfood/services` (8 spec'ов).
- **PPI:** `ppi-yoy`, `ppi-annual`.
- **GDP:** `gdp-{yoy,qoq}` ← `gdp-nominal`, `gdp-real-{yoy,qoq}` ← `gdp-real`, `gdp-{nominal,real}-annual` (annual_sum).
- **Wages/Unemployment:** `wages-real`, `wages-yoy`, `unemployment-{quarterly,annual}`.
- **Trade/External:** `exports-{yoy,qoq}`, `imports-{yoy,qoq}`, `trade-balance-yoy-abs`, `current-account-yoy-abs`. Старый `current-account-yoy` (%) **депрекейтнут** в seed_data как `is_active=false`, в DERIVED_SPECS убран — для balances со знаком процент YoY бессмыслен.
- **Other:** `ipi-yoy`, `housing-yoy-{primary,secondary}`.

**Исторический frontend-only механизм (звонок 2026-05-22).** Первоначальный реестр `frontend/src/lib/viewModeFamilies.js::VIEW_MODE_FAMILIES` маппил parent → массив `modes[]`: `{mode, label, code, unit?, transform?}`; `findViewModeFamily(code)` разрешал `?mode=…`. Ниже сохранены фазы и причины этого решения. **Текущий generic-путь (сверка 2026-09-27)** — `FamilyDef` → generated JSON → `viewModeEngine` → `GenericIndicatorView`; новые generic-семьи добавлять туда. Legacy-модули сохраняют shared resolve/content и старые canonical redirects, поэтому исторический статус не означает возможность удаления.

Frontend-only трансформации:
- `applyMoMTransform(points)` — MoM% для `*-monthly` (Phase 1): `(val_t/val_{t-1} − 1) * 100`, backend spec сознательно не заводится.
- `applyAggregateTransform(points, granularity)` — bucket-avg для daily-индикаторов (Phase 5): `granularity ∈ {week, month, quarter, year}` → среднее по bucket'у с датой = конец bucket'а. Применяется к любому `indicator.frequency === 'daily'` (`key-rate`, `ruonia`, `cbr-fx-*`, `gold-price`, `brent`, `btc-usd`) без новых backend-derived.

Phases:
- Phase 1 — trade (4 quarterly + 4 monthly семьи).
- Phase 2 — labour: `wages-nominal` (4 режима: Номинальная / Реальная / YoY / Индекс), `unemployment` (3 режима: Месячно / Квартально / 12М avg).
- Phase 3 — housing prices (Уровень индекса / YoY %).
- Phase 5 — daily aggregation (виртуальные week/month/quarter/year avg).

Phase 4 (ставки) НЕ использует viewModeFamilies: `credit-rate-corp-short`, `credit-rate-ind-short`, `deposit-rate` — единые карточки с **VariantGroupPicker** (срок: До 1 года / 1-3 года / Свыше 3 лет). Это не «режим отображения», а отдельные индикаторы по сроку.

### Матрица представлений (representation matrix)

Каноническая модель «полноты» индикатора, эталон — двухуровневый переключатель ИПЦ (`frontend/src/lib/cpiViewModeGroups.js`). Полнота — это **матрица из двух осей**:

- **Верхняя ось — ТИП представления** (что показываем): `value` уровень/средняя/на конец/за период · `pop` к прошлому периоду (Н/н·М/м·Кв/Кв·Г/г-календарный) · `yoy` к соотв. периоду пред. года (rolling) · `index` индекс (rebase к базе).
- **Нижняя ось — ЧАСТОТА** (за какой промежуток): `week` · `month` · `quarter` · `year`.

Каждая «ячейка» (тип × частота) — либо есть у индикатора (режим/sibling-код), либо пуста. Пустая ячейка относительно **ожидаемого по природе ряда** — это пробел (кандидат на добавление режима, не дефект: для ставки `index` не нужен, у годового счётного ряда нет `pop`).

**Природа ряда** (детерминированно из билдер-типа `view_model_families.py` или `unit`): `rate` (T1/T2/T2y) · `stock` (T3/T4/T5) · `flow` (T6) · `signed-flow` (T7/T9s, baланс со знаком → `yoy_abs`, нет `index`) · `avg-level` (T8 зарплата/занятость) · `gdp` (T9) · `annual-count`/`annual-signed` (T10/T10a) · `ratio-index` (T12, отношение индексов — уровень-ряд, без rebase-группы) · `index` (ИПЦ/ИЦП/ИПП, `unit=индекс` — уровень ряда = сам индекс, величину закрывает группа `index`).

**Ожидаемая матрица** на природу — единая точка истины: `expected_matrix(nature, native)` в `scripts/completeness.py`. **Present** generic-семей берётся из билдеров (authoritative), bespoke (cpi/ppi/housing) — из их режим-реестров.

**Аудит полноты** (read-only) генерируется в `docs/indicator-index.json::completeness` + срез в `docs/indicator-index.md` (модуль `scripts/completeness.py`, вызывается из `build-indicator-index.py`, под guard `--check`). На каждый КОРЕНЬ-семейство: `present`/`expected`/`missing`-ячейки, `matrix_score` и 4 измерения паспорта — `texts` (description+methodology в seed; **у ИПЦ-семьи методология живёт в `cpiViewModeContent.jsx`**, не в seed → `partial` там ожидаем), `forecast`, `grouping`, `seo`. Системный вывод первого прогона (2026-06-24): доминирующий пробел — `yoy:quarter`/`yoy:year` почти у всех sub-annual семей (rolling Г/г есть только на нативной частоте).

**Заполнение матрицы (2026-06-24).** Доминирующий пробел закрыт: группа «Г/г» стала **многоуровневой** (по месяцам/кварталам/годам) во всех generic-билдерах через единый helper `view_model_families.py::_yoy_modes(base, freq, ov, method=, abs_delta=)`. Метод свода суб-периодов к кварталу/году — по природе ряда: `last` (ставки/запасы/индекс), `avg` (зарплата/занятость, индекс-отношение T8/T12), `sum` (потоки/ВВП/сальдо; для знаковых — `abs_delta=True` → `yoy_abs`). Пайплайн `(period_<method> gran → yoy[_abs])` исполняется в `calculation_engine`; неполный текущий квартал/год отбрасывается (`derived_ops._aggregate`), прогноз протягивается `_mode_forecast_meta` (guard полноты bucket'а). +105 sibling-рядов (104 yoy-кв/год + `international-reserves-mom`), все авто-seed + авто-скрыты из листинга, тексты — period-aware в `seed_data._sibling_texts`. Правдивость сверена независимо (`budget-revenue-yoy-year`, `m2-yoy-quarter`). Аудит после заполнения: 78/91 корней complete; остаток 13 — bespoke-канон CPI/ПЦП/жильё (свои тексты/реестры, не трогаем без отдельного решения) + by-design (`wages-nominal-annual` — историч. режим карточки, не каталог; `ipi`/housing `pop:year` ≈ `yoy:year`).

### Forecast

Прогноз индикатора на N шагов. Хранится в `Forecast` (метаданные + `is_current`) + `ForecastValue` (точки `(date, value, lower_bound, upper_bound)`).

**Диапазона прогноза пользователь не видит (решение владельца, 2026-10-06).** Прогноз показывается только точечно: линия прогноза и значение через год. Колонки `lower_bound`/`upper_bound` остаются во внутренних расчётах и в БД (клэмпинг, снимки стратегий), но публичные API (`/indicators/{code}/forecast`, `/indicators/{code}/inflation`, `/forecasts/showcase`, world `forecast.points`, субнациональный прогноз), графики, таблицы, SSR и тексты их не отдают и не выводят: ни «коридора», ни «интервала», ни полосы вокруг линии. Новых мест с диапазоном не добавляем.

**Реестр стратегий** (`backend/app/services/forecast_strategies/registry.py`) — диспетчеризует прогноз-генерацию по полю `Indicator.model_config_json.forecast_strategy`:

| Имя | Когда применяется | Что делает |
|---|---|---|
| `cpi_combined` | `cpi`, `cpi-food`, `cpi-nonfood`, `cpi-services` | Гонит `train_monthly_cpi` (помесячный) + `train_inflation_12m` (12-мес скользящий) и каскадит результат на `*-quarterly` derived |
| `housing_quarterly` | `housing-price-primary`, `housing-price-secondary` | `train_quarterly_housing` — 1:1 port `Прогнозы_цены_на_жилье (1).ipynb` Никиты (multi-window OLS на log-diff + outlier-clip + corr-filter + iv-weighted blend + per-step median). Byte-exact с notebook'ом |
| `gdp_nominal_quarterly` | `gdp-nominal` | `train_gdp_nominal_quarterly` (multi-window OLS на log-diff, без блендинга) — 1:1 port `Прогноз_номинальный_ВВП.ipynb` |
| `gdp_real_quarterly` | `gdp-real` | `train_gdp_real_quarterly` — то же ядро `_train_gdp_quarterly_port` на ряду реального ВВП; byte-exact с notebook'ом |
| `gdp_consumption_quarterly` | `gdp-consumption` | `train_gdp_consumption_quarterly` — то же ядро `_train_gdp_quarterly_port` на ряду расходов домохозяйств (методология семьи ВВП по просьбе Никиты; отдельного notebook'а нет) |
| `gdp_government_quarterly` | `gdp-government` | `train_gdp_government_quarterly` — то же ядро `_train_gdp_quarterly_port` на ряду гос.потребления |
| `generic_quarterly` | `exports`, `imports`, `external-debt` (2026-06-24) | `train_generic_quarterly` — то же ядро `_train_gdp_quarterly_port` (log-diff семьи ВВП) для **положительных** квартальных рядов без своего notebook'а; model_name из кода. Закрыл запрос созвона «квартальным тоже нужны прогнозы». **Не для знаковых** (сальдо/счёт — log-diff неопределён) |
| `signed_quarterly` | `current-account` (2026-06-24) | `train_signed_quarterly` — то же ядро `_train_gdp_quarterly_port`, но `transform="level"` (multi-window OLS на **первой разности уровня**, аддитивная реконструкция). Знако-устойчива — для квартальных сальдо/счетов со сменой знака, где log-diff неопределён. `trade-balance` сюда НЕ входит: он прогнозируется тождеством (см. `derived_from_source` op=`subtract`) |
| `ppi_monthly` | `ppi` | `train_ppi_monthly` (k=1..4, monthly lags log-diff) — 1:1 port `Прогноз_ИЦП.ipynb` |
| `monthly_auto` | 40 месячных рядов (`MONTHLY_AUTO_FORECAST_CODES` в `seed_data`): wages, unemployment, M0/M2, доходы/расходы/дефицит бюджета, торговый баланс, экс/имп товаров и услуг, **construction-work / retail-trade / ipi** (2026-06-22), **housing-affordability / -primary** (2026-06-23, derived-ряд отношения, собственная модель) и др. **Кроме ИПЦ-семьи** (своя `cpi_combined`) | `train_monthly_auto` — ADF-автотрансформ (level/dif/log) + multi-window OLS по лагам `[m,m+1,m+2,12]`. Обновление 2026-06-22 (`Прогноз_месячных_данных.ipynb`): rolling(m)-сглаживание изменений для нестационарных рядов + пер-горизонтная реконструкция `последнее + m·aux[m]`. Срезы `-mom`/`-yoy` тянутся через `derived_from_source`. **Видимость прогноза в режиме** карточки определяет `_mode_forecastable` (фронт-флаг = частота базы протягивает прогноз), а не per-mode хардкод. Derived с собственной моделью (доступность жилья) ретрейнятся в `scheduler._retrain_self_modeled_derived` после движка (источниковый каскад их не покрывает) |
| `annual_auto` | 20 годовых source-рядов (`ANNUAL_AUTO_FORECAST_CODES` в `seed_data`): население, рождаемость/смертность, миграция, наука/инновации, износ фондов. **Не WEO и не годовые агрегаты биржи/крипты** | `train_annual_auto` — порт `Прогноз_годовых_данных.ipynb`: ADF-трансформ + multi-window OLS, окна `k∈[1, max(n//15,2))`, лаги m∈{1,2,3}→`[m,m+1]` / m=4→`[m]`, горизонт ≤4 (в seed 2 года). Для знаковых рядов лог недопустим. Г/г протягивается `derived_from_source` (`_FORECAST_PROPAGATE_FREQ` включает `annual`) |
| `approved` | исторически: `cpi-*`, `gdp-nominal`, `ppi`, `housing-price-*` | Использует ручные значения из `model_config_json.approved_forecast_values` (массив `{date, value}`) без переобучения. **В live-конфиге не используется** — все индикаторы переведены на свои live-стратегии (`ppi → ppi_monthly`, 2026-05-16). Strategy сохраняется в registry для обратной совместимости и тестовых сценариев |
| `derived_from_source` | Все *-yoy, *-qoq, *-annual derived с `derived_forecast: {source_code, operation, model_name}` (включая `housing-yoy-primary`, `housing-yoy-secondary`); **`trade-balance`** (op=`subtract`, 2026-06-24) | Применяет ту же чистую op (yoy / qoq / december_to_december / annual_sum / real_from_yoy / **subtract**) к **прогнозу** source-индикатора. `subtract` берёт ДВА источника (`source_code` + `source_code_2`) — тождество `trade-balance = exports − imports`, согласовано с прогнозами компонент. Каскадный retrain срабатывает после успеха любого из источников |
| `generic_ols` | `inflation-weekly`, fallback | `train_and_forecast` (multi-window OLS с inverse-variance weighting); универсальная модель |

**Поля связки:**

- `model_config_json.forecast_strategy` — имя стратегии (если не задано — fallback `legacy_resolve(indicator)`).
- `model_config_json.derived_forecast` — `{source_code, operation, model_name}` для `derived_from_source` стратегии.
- `model_config_json.forecast_transform` — например `cpi_index` для `inflation-weekly`: значения возвращаются как уровень индекса 100.x; фронт пересчитывает в delta через `adjustCpiForecastDisplay`.
- `model_config_json.approved_forecast_values` — массив для approved-стратегии.
- `model_config_json.forecast_steps` — горизонт. По умолчанию 12 (`RUSTATS_FORECAST_STEPS`).

**Каскадный retrain.** После успешного retrain индикатора-источника (в `forecast_pipeline.retrain_indicator_forecast`) ищем все индикаторы, у которых `derived_forecast.source_code == this.code`, и retrain их рекурсивно с защитой от циклов. Это заменило старый side-effect `_propagate_cpi_forecast_to_derived`, который остался для cascade `cpi → cpi-{food,nonfood,services}-quarterly`, но `*-annual` (Dec-to-Dec) теперь живут отдельной стратегией.

**World job** (`world_forecast_pipeline.world_forecast_job`): listed M/Q/A `world_indicators`, инкрементально по отпечатку `history_end`/`points_count`/`WORLD_FORECAST_METHOD_VERSION`, обход по приоритету стран и концепт-рядов; `bump_namespaces("world", "ssr-world")` каждые N успехов.

### ETL run

Запуск одного парсера для одного индикатора. Записывается в `FetchLog`:

- `status` ∈ `running` / `success` / `no_new_data` / `failed` / `timeout`.
- `started_at`, `completed_at` (TIMESTAMP WITHOUT TIME ZONE — все datetime tz-naive!).
- `records_added`, `error_message`, `source_url`.

Внимание: `fetch_log.records_added` записывает **только новые строки**, не in-place revisions. `bulk_upsert` возвращает `(records_added, records_updated)`, но в `BaseParser.run()` поле в БД заполняется только из `records_added`. Это влияет на dispatch derived (см. ADR-0002 «Limit of the invariant — pure-revision day»).

Daily ETL (06:00 МСК, `RUSTATS_SCHEDULER_CRON_HOUR/MINUTE`) запускает все `is_active=True` non-derived индикаторы → `CalculationEngine.run_for_updated_sources` для derived (если хотя бы один parser добавил новые строки) → `_promote_past_events` для календаря.

**Calendar refresh** (`calendar_refresh` job): отдельный daily cron 03:00 МСК прокатывает `seed_calendar(months_ahead=12)`, который теперь вызывает official calendar ingest (`calendar_sources.official_calendar`). Public API отдаёт только source-bound rows: `date_confidence IN ('official_explicit', 'official_rule')`, `is_estimated = false`, заполнены `event_key`, `source_url`, `source_hash`, `last_seen_at`. Estimated rows и legacy backfill без provenance остаются внутренним fallback и скрыты (см. термин «Calendar event» и ADR-0005).

**Analytics scheduler** (опционально): если `RUSTATS_ANALYTICS_SCHEDULER_ENABLED=true` — два дополнительных cron-а: hourly :15 (Yandex Metrika reporting sync) и daily (management snapshot). По умолчанию выключен.

### Category

Функциональная группа индикаторов: Цены, Ставки, Валюты, Индексы, Финансы, Товарные рынки, **Рынок труда**, ВВП, Население, Торговля, Бизнес, Наука. Двенадцать штук (источник: `CATEGORY_META_EN` и русские названия в `seo_content.py`; сверено 05.10.2026). На главной — сетка карточек, на `/category/{slug}` — список индикаторов в категории.

В БД хранится русское имя (`Цены`, `Рынок труда`); URL использует slug (`prices`, `labor`). Маппинг — `frontend/src/lib/categories.js` (включает `seoTitle`/`seoDescription`, идентичные backend `seo_content.py::CATEGORY_META.title/description` — это **зеркало backend SSR**, не источник правды; см. ADR-0003).

### Calendar event

Запись в `EconomicEvent` для расписания публикаций (релиз CPI Росстата, заседание совета директоров ЦБ, недельный ИПЦ Росстата, международные резервы РФ). После ADR-0005 public calendar **source-bound**: событие показывается пользователю только если `date_confidence = official_explicit` (официальная дата из календаря/ICS/страницы) или `official_rule` (дата рассчитана по опубликованному правилу + versioned `ru_working_calendar` с source_url), `is_estimated = false`, и заполнены `event_key`, `source_url`, `source_hash`, `last_seen_at`. `estimated` rows и миграционные legacy rows без provenance скрыты из `/api/v1/calendar`, `/upcoming` и iCal. Переносы обновляются по stable `event_key`, старая дата хранится в `metadata_json.reschedule_audit`. Прошедшая дата сама по себе не означает выпуск: статус `released` ставится только при наличии `actual_value` (его заполняет enrichment из опубликованных данных), а API (`_effective_status`) показывает для прошедшего события без факта `awaiting_confirmation`. Задача `_promote_past_events` не продвигает статус по дате, а откатывает прежние необоснованные `released` без факта обратно в `scheduled` (обновлено 05.10.2026 по чтению `scheduler.py` и `api/calendar.py`).

### Embed widget

Внешний виджет, встраиваемый по `<iframe>` (5 типов: chart, card, table, ticker, compare) или SVG-эндпойнтам (`/api/v1/embed/spark/{code}.svg`, `/card/{code}.svg`, `/badge/{code}.svg`). Имеют отдельный CSP в Caddy (`frame-ancestors *`), отдельный rate limit (600/мин в `RateLimitMiddleware`), impression tracking (`/api/v1/embed/impression`, `/pixel.gif`).

### Approved forecast

Ручные прогнозные значения от Никиты (партнёр), хранящиеся в `Indicator.model_config_json.approved_forecast_values` (массив `{date, value}`). Применяются стратегией `approved` в forecast registry без переобучения модели.

### SEO meta bundle

Пакет meta-данных для индикатора/категории/страницы: `seo_title`, `seo_description`, `seo_keywords`, `canonical`, JSON-LD, OG image, twitter card.

**Принцип хранения (ADR-0003 — Accepted, см. файл):** разделение по природе.

- **Редакционный контент** живёт в БД (`Indicator.seo_title`, `seo_description`, `seo_keywords`, `seo_blocks`, `is_listed`). Меняется людьми, без деплоя — через прямой UPDATE или будущий admin-UI.
- **Шаблоны и fallback** живут в коде: правила генерации seo_title для индикаторов, у которых ручной override пуст (`backend/app/services/seo_renderer.py` + `default_keywords()`); общие SEO-блоки для всех индикаторов; форматирование. Меняются через деплой.
- **Frontend читает из API и зеркалит SSR** — никаких локальных констант не осталось (`SEO_MAP`, `INDICATOR_BLOCKS`, `HIDDEN_FROM_LISTING` удалены в Шаге 4 фазы 2). Backend-SSR через `/seo/page/*`, `/seo/category/{slug}`, `/seo/indicator/{code}` — единственный источник правды; frontend `useDocumentMeta(null)` no-op до подгрузки данных, потом ставит то же, что лежит в SSR.

**SEO-автоматика (2026-06-12, ADR-0003 «Subsequent additions») — всё data-driven из БД, при добавлении индикатора руками ничего не делать:** sitemap (lastmod из последней точки, priority по `is_listed`), related-блоки (flagship-first, только listed), годовые landing'и `/indicator/{code}/{year}` (SSR без React-bundle), OG-превью `/og/{code}.png` (Pillow-спарклайн), RSS `/feed.xml`, IndexNow-пинг после daily ETL (`services/indexnow.py`), ETag/304 на SSR, autolink терминов в seo_blocks (`AUTOLINK_TERMS`), critical CSS (`SEO_CRITICAL_CSS` — синхронизировать при смене дизайн-токенов). Обязательное ручное действие — только осмысленные `seo_keywords` (fallback `default_keywords()` сработает, но curated лучше).
- **`/__spa-index.html`** — raw Vite SPA shell с заголовком `X-Robots-Tag: noindex, nofollow`. Используется backend SSR-renderer'ом для discover текущих hashed JS/CSS asset-имён. Не индексируется.

Исторически (до Шага 4 фазы 2, 2026-05-05) дублировалось в 4 местах: `seed_data.py`, `SEO_MAP` (frontend), `INDICATOR_BLOCKS` (backend), `categories.js HIDDEN_FROM_LISTING`. Сейчас — один источник в БД + код-fallback.

### Forecast Analytics OS

Отдельный backend-слой для интеграции с Yandex.Metrika / Yandex.Webmaster / SEO crawler. Включает:

- **Yandex клиенты:** `app/services/yandex_metrika_management.py`, `yandex_metrika_reporting.py`, `yandex_metrika_logs.py`, `yandex_webmaster_client.py`, `yandex_client.py`.
- **Ingestion / backfill / features:** `analytics_ingestion.py`, `analytics_backfill.py`, `analytics_features.py`.
- **Action policy / executor:** `action_policy.py`, `action_executor.py` — safety classes (read_only / low_risk_write / high_risk_write / denied).
- **API:** `app/api/analytics.py` (10 endpoints под заголовком `X-Analytics-Token: ${RUSTATS_ANALYTICS_API_TOKEN}` (403 без него)).
- **Warehouse models:** `AnalyticsSyncRun`, `AnalyticsWatermark`, `MetrikaCounterSnapshot`, `MetrikaGoalSnapshot`, `MetrikaReportSnapshot`, `MetrikaDailyPageMetric`, `MetrikaSearchPhrase`, `RawMetrikaVisit`, `RawMetrikaHit`, `WebmasterDiagnostic`, `WebmasterSearchQuery`, `SeoPageSnapshot`, `AgentFinding`, `AgentActionAudit`, `FrontendEvent`, `Experiment`.
- **MCP:** `mcp/forecast-analytics-mcp/` (Node.js, 7 tools), интегрирован в Cursor через `~/.cursor/mcp.json`. Нужен для агента-аналитика; ходит в backend `/api/v1/analytics`.
- **Scope:** read-only Metrika tools работают; live writes выключены флагом `RUSTATS_ANALYTICS_LIVE_WRITES_ENABLED=false`. Webmaster и data-import API — endpoint-ы перечислены в `docs/analytics_api_inventory/`, но требуют дополнительных OAuth scopes (см. inventory README header).
- **Frontend instrumentation:** init-параметры Метрики, таксономия goals (`reachGoal`), UTM-разметка share-ссылок и URL cleanup описаны в [`docs/analytics_api_inventory/frontend_instrumentation.md`](docs/analytics_api_inventory/frontend_instrumentation.md). Webvisor 2 + form analytics включены через `webvisor:true, triggerEvent:true, childIframe:true` (2026-05-10). Каждый клик в `lib/track.js::events` дублируется в `frontend_events` через `POST /api/v1/analytics/events`.

### User / Identity (ADR-0007, Phase 1+2 реализованы локально 2026-06-19)

Словарь акторов для личного кабинета (lead-gen, звонок-стратегия). Phase 1 (email+пароль, OAuth Яндекс/VK + fake, сессии в Redis, 152-ФЗ-минимум) реализована: `app/api/{auth,oauth}.py`, `app/services/{session.py,identity/,oauth/}`, `app/security/`, Alembic `20260619_identity`. Боевые Яндекс/VK требуют реальных app-кредов (pre-prod чеклист в ADR-0007). **Phase 2 (2026-06-19):** серверный download-gate (`app/api/export.py`, гость 2 выгрузки/сессия через cookie `fe_dl` + Redis `fe:dl:*`, авторизованный — безлимит), телефон в `OAuthIdentity.phone` (Alembic `20260619_oauth_phone`), согласие на рассылку (`Consent kind="newsletter"`), `GET /auth/oauth/providers` + брендовые кнопки, redirect-override + compat-роутер, Telegram-бот (уведомление о регистрации `notify_new_user` + ежедневный дайджест `telegram_daily_digest_job` со статистикой Метрики/целей-CTA), UI (хедер-блок авторизации, инлайн-поиск, `RegisterNudge`). См. ADR-0007 «Subsequent additions».

- **Visitor** — анонимный посетитель без идентичности. Дефолт всего публичного сайта (ADR-0003, SEO). Остаётся таким: никаких wall'ов на контент/графики/прогнозы.
- **User** — человек, у которого есть хотя бы одна `OAuthIdentity`. Появляется только после входа. Доменная сущность; e-mail не PK (PK — внутренний id).
- **OAuthIdentity** — привязка `(provider, provider_user_id, verified_email)`. У одного `User` может быть несколько (Яндекс + VK = один `User`, две привязки). Провайдеры — реестр в стиле `PARSER_REGISTRY` (не if-else). **Phase 1 провайдеры: Яндекс ID, VK ID** (у VK email не гарантирован → `User` может быть без email) **+ email+пароль**. Mail.ru и прочие — потом, одной записью в реестре.
- **Фазность (звонок-грилл 2026-06-19).** **Phase 1 (локально, всё E2E):** регистрация/вход (Яндекс, VK, email+пароль) + личный кабинет + сквозные user-path'ы. Почты на Phase 1 **нет вообще** → нет подтверждения email, сброса пароля, double-opt-in, рассылок. **Phase 2+:** почтовый провайдер (за `NotificationChannel`), download-gate (домен Export), подписки/рассылки (домен Notifications), монетизация.
- **Инвариант на будущее (Phase 2): рассылка — только double-opt-in.** Регистрация по email остаётся без подтверждения (низкое трение, вход и выгрузка сразу), но в список рассылки — только подтверждённый email (ст. 18 ФЗ «О рекламе» + защита деливерабилити: неподтверждённые → bounce → бан sending-домена). Транзакционную почту вводим в Phase 2 вместе с рассылками.
- **Личный кабинет** — UI-поверхность (`/account`), не отдельная сущность. В домене оперируем `User`. Весь `/account/*` — `noindex`, вне sitemap.
- **Partner/Admin** (Никита) — отдельный актор, **не** обычный `User`. Сейчас неявно живёт в `Approved forecast`. OAuth-регистрация Visitor'а **не** даёт editorial-прав.
- **Резолв идентичности (инвариант).** Email не живёт на `User` (нет глобальной уникальности `User.email`) — он атрибут способа входа: `OAuthIdentity` (ключ `(provider, provider_user_id)`) либо `EmailCredential` (`email` уникален, `email_verified=false` на Phase 1). Автосвязывание разных способов в один `User` — **только когда оба email верифицированы и равны**; парольный (неверифиц.) аккаунт никогда не мерджится автоматически; кросс-способ связывание — вручную из кабинета под активной сессией. Это закрывает pre-hijack (нельзя подменить аккаунт жертвы, заранее заняв её email паролем без подтверждения).
- **Трап: публичный кэш не варьировать по auth-куке.** `fe_sess` cookie летит на все same-origin запросы, но публичные эндпоинты (`/api/v1/indicators/...`, SSR) сессию **не читают** и кэш по куке **не варьируют** — иначе общий Redis-кэш дробится по юзерам и убивает SEO-трафик. Сессию читают только `/auth/*`, `/account/*` и приватные ручки.

Не путать с `RUSTATS_ANALYTICS_API_TOKEN` (Forecast Analytics OS) — это машинный bearer-токен для MCP-агента, не идентичность конечного пользователя.

Цель кабинета — **lead-gen**: вход через OAuth открывает полную выгрузку рядов (gate только на download, см. домен Export) и собирает согласие на рассылки о выходе данных (домен Notifications). Не монетизация, не платный wall. Детали — ADR-0007 (в работе).

**Согласие на рассылку — решение владельца 2026-10-05.** Галочка «Согласен на информационную рассылку» снова отмечена по умолчанию в регистрации по почте и в окне перед входом через Яндекс/VK/Google; человек может её снять, выбор пишется в журнал согласий. Серверный default остаётся «нет» (без явной передачи с формы рассылки нет). Юридический риск предотмеченной галочки (opt-in юрисдикции, ЕС) владельцу озвучен и принят — [ADR-0007, дополнение 2026-10-05](docs/adr/0007-identity-user-accounts.md). Согласие с соглашением и политикой остаётся отдельной, не предотмеченной галочкой.

### Установка как приложение (PWA), подготовка web-push, замер спроса на API (локально 2026-10-05, не выпущено)

Три связанных пакета, выпущенных одной серией коммитов (`4dbc613`, `95373b2`, `0ebe34c`, `a51b5a0`, правка `65035788`); боевой сервер их не получал. Основной контракт — [data-contracts §6](docs/data-contracts.md), события — [frontend_instrumentation](docs/analytics_api_inventory/frontend_instrumentation.md), статус и остаток — [backlog](docs/backlog.md) (якоря `pwa-install-2026-10-05`, `push-prep-2026-10-05`, `api-interest-fake-door-2026-10-05`).

- **PWA.** Манифест `/manifest.webmanifest` и офлайн-страница `/offline.html` отдаёт backend (`api/pwa.py`) отдельно для каждого origin (язык по Host; apex = en, `ru.` = ru). Service worker `/sw.js` статический (`frontend/public/sw.js`, версия кэша подставляется Vite), **не кэширует ни HTML, ни API, ни данные**: единственный кэш — офлайн-страница и иконка, перехватываются только навигации. Приглашение установить (`lib/pwaPolicy.js`, `lib/pwa.js`, `PwaInstall*.jsx`) — после полезного действия или второго захода, с откладыванием 3 → 7 → 14 → 30 дней; состояние в `localStorage` (`fe:pwa:v1`). Выключатели без пересборки фронта: `RUSTATS_PWA_ENABLED` (снимает service worker у всех), `RUSTATS_PWA_INSTALL_PROMPT_ENABLED`.
- **Web-push — только подготовка.** Таблица `push_subscriptions` (Alembic `20261005_push_subscriptions`, модель `PushSubscription`), эндпоинты `/api/v1/push/*` за флагом (404 пока выключено), сервис `services/web_push.py` (отказывает, сухой прогон по умолчанию), клиент `lib/pushSubscription.js` (не подключён к UI) и обработчики `push`/`notificationclick` в `sw.js`. Ни одно задание планировщика отправку не вызывает. Адрес подписки — **персональные данные**.
- **Замер платного спроса («фальшивая дверь»).** Ссылка «API и выгрузка с прогнозом» + форма заявки (`ApiInterestLink`/`ApiInterestModal`, `api/api_interest.py`) за флагом `RUSTATS_API_INTEREST_ENABLED`. Заявки **нигде не хранятся**: уходят в Telegram (`alerting.notify_api_interest`, `kind=api_interest`), единственный след почты — текст в `telegram_outbox`.

Инварианты и ловушки: (1) service worker не должен получить кэш HTML/API — иначе посетитель увидит устаревшие экономические цифры без признака устаревания; офлайн показывается только страница-заглушка. (2) `Caddyfile` с `worker-src`/`child-src`/`manifest-src` надо выкатить до или вместе с фронтом, иначе service worker блокируется CSP (сайт при этом работает как раньше). (3) Для web-push отправка требует одновременно `push_send_enabled=true`, `push_dry_run=false` и ключей VAPID из окружения; до включения подписки нужно обновить публичную Политику конфиденциальности. (4) Установленное с apex приложение для посетителя из РФ уйдёт на другой origin (`ru.`) из-за гео-редиректа. (5) Миграция `20261005_push_subscriptions` не применялась на проде; перед выкладкой — штатный `alembic upgrade head`.

### Мировой multi-provider блок (ADR-0011/0012)

Отдельный bounded context с осью `provider × страна × dataset × slice × период`.
Eurostat — первый адаптер, а не универсальный источник для всех стран.

- **Official-first** — ряд поступает только из официального национального ведомства,
  центрального банка, таможни, министерства, официальной биржи или
  наднационального статистического органа. Национальный первоисточник имеет
  приоритет; коммерческие и новостные агрегаторы запрещены.
- **Provider** — машинный код издателя (`eurostat`, далее `bea`, `bls`, `ibge`,
  `mospi`, `nbs` после отдельной проверки). Он входит в identity и provenance;
  публичное поле `source` — человекочитаемое имя организации.
- **WorldSourceAdapter** — единый контракт catalogue → series identity →
  dimensions/frequency/unit → observations/revision metadata. Product-слои не
  знают wire-формат ведомства.
- **WorldConcept** — вручную доказанная семантическая связь рядов разных стран и
  providers. Совпадение названия/единицы само по себе сравнение не открывает.
- **WorldForecast** — отдельный от России прогнозный контур. Публичен только для
  свежего регулярного M/Q primary-series, где rolling-origin `MASE < 1` и модель
  минимум на 2% точнее seasonal-naive. Не прошедший gate ряд корректно остаётся
  без прогнозной линии.

### Региональный блок (ADR-0008, реализован локально 2026-07-02)

> Следующий блок сохраняет состояние июля. Помесячный слой добавлен в августе,
> живой ЕМИСС и новые права seed уточнены [выше](#региональная-история-и-права-обновления--2026-09-30).
> Фраза «планировщик региональные данные не трогает» ниже относится к годовой
> сетке того решения; месячные топливные точки обновляет отдельный job.

Отдельный bounded context с осью `регион × показатель × год` — НЕ часть макро-каталога. Источник — годовой сборник Росстата «Регионы России. Социально-экономические показатели» (Excel-приложение с 2024, ранее Word).

- **Region** — территория: РФ, 8 федеральных округов, 85 субъектов, 2 агрегата-остатка (Архангельская/Тюменская без АО). Канонический реестр + нормализация имён строк Росстата — `scripts/regional/regions_registry.py`.
- **RegionIndicator** — показатель сборника (489 штук, 22 раздела; разделы 21 «Внешняя торговля» и 22 «Правонарушения» дособраны из архивных редакций). Кода макро-`Indicator` не касается.
- **RegionDataPoint** — годовая точка `(indicator, region, year)`; 960 926 точек, 1990–2024.
- **Артефакт вместо ETL**: `scripts/regional/parse_pril_2025.py` → `backfill_pril_2022_2023.py` → `backfill_word.py` пишут `backend/app/data/regional/` (коммитится); `seed_regional.py` идемпотентно заливает из entrypoint. Планировщик региональные данные не трогает; обновление — раз в год руками по новому архиву.
- **Прогнозов и derived нет** намеренно: годовая частота, полный пересмотр издания. Динамика Г/г считается на лету.
- UI: `/regions` → `/region/{slug}` → `/region/{slug}/{code}`; SSR/sitemap/OG — по ADR-0003 (`seo_regional.py`).

---

### Поисковое намерение и область (ADR-0016, локально 2026-09-30)

**Search intent** — нормализованный текст плюс экономическое понятие, явная
страна/регион и поддерживаемый период. **Search candidate** — конкретная
доступная территория или ряд с bounded key, единицей, частотой и готовым
canonical путём. **Search scope** — глобальное discovery либо supplied
eligible pool локального инструмента; таблица ограничена загруженными точками.
Общий matcher не меняет сопоставимость, права, listing или реальные факты.

V2 разворачивает обычную формулировку в предмет, роль, явные quantity/frequency
facets и geography. Нативные полные имена/коды защищены от внутренних дат;
typed guards для покрытых понятий отличают число от доли, реальные от
номинальных величин и предмет от слова в знаменателе; набор не исчерпывающий.
Каталожные aliases и bounded title-IDF не
являются обученной ML-моделью. Исторические click labels не устанавливают
correctness: [replay и независимые проверки](docs/research/search-history-replay-2026-09-30.md).

`/api/v1/search` федеративно читает российские, world, региональные и
субнациональные модели; разделение ADR-0008/0011/0014 сохраняется. Явная
география/период/frequency проверяются до candidate limit; все содержательные группы
обязательны. `total` — число выданных строк, `has_more` — возможное усечение,
не обещание exhaustive ranking. Семейства/варианты/режимы разрешаются через
действующие canonical helpers. Неподдержанный период не заменяется другим.
`search_paths` пакетно разрешает world destinations и сохраняет requested
family group; annual региональная ссылка требует annual факта, hidden
world document period закрыт без listed SSR eligibility. Native level
может быть процентной мерой. DXY/US10Y из общего Indicator контура имеют
US issuer exception по действующему registry, сохраняя storage и URL.

Новая версия использует детерминированный lexical score, алиасы, ограниченные
опечатки/раскладку и PostgreSQL word similarity. Обученной ML-модели нет.
Исторический read-only экспорт сохранил 3 905 PG search events; анализ 919
технических сессий и подробный разбор 150 реальных human_supported путей
не восстанавливают все нажатия и не доказывают релевантность выбора.
Возвращённые/отрисованные keys глобального поиска не доказывают viewport
impression каждой строки. Основной источник — [search.md](docs/search.md),
фактические числа/ограничения — [отчёт](docs/research/search-history-2026-09-30.md).

## Operational invariants and traps

Вещи, которые ломаются неочевидно. Каждый пункт — проверенный пост-мортем.

### RSY-page-disabled trap: рекламы нет, а код исправен (2026-09-29)

Баннер пропал везде (SPA и быстрые ссылки), при этом `consent.js`,
`context.js` и очередь `yaContextCb` работали. Диагноз по шагам:
(1) у владельца `context.js` падал за 3 мс с кодом 503 и на example.com —
это блокировщик рекламы в браузере (в хите Метрики `adb:1`), не сайт;
(2) в чистом браузере запрос `https://yandex.ru/ads/meta/19489903?...`
отвечал **404 с телом `<!-- Page 19489903 disabled -->`** — площадка РСЯ
выключена на стороне Яндекса; (3) почасовая Partner Statistics
(`dimension_field=date|hour`) показывает, когда показы остановились.
Код тут не правится: статус площадки и причину видно только в кабинете
partner.yandex.ru (OAuth-токен статистики к `restapi/v1` доступа не даёт).
Проверка без браузера владельца: Playwright с
`--disable-blink-features=AutomationControlled` (иначе гейт считает его
роботом), движение мыши и колесо, затем ответ `ads/meta`.

### nginx-logrotate I/O trap: ротация совпала с задержкой Postgres (2026-09-27)

`frontend/nginx.conf` пишет все запросы в host-level `security.log` для
fail2ban. При 228 МБ в сутки `compress + delaycompress + copytruncate` заняли
00:00:03–00:05:49 UTC; все 48 SQL statement timeout пришлись на этот интервал,
а `sar` показал 131 мс disk await и 43,95% iowait. Совпадение сильное, но
исторического per-process I/O нет: строгая причинность не доказана. Конфиг
`deploy/fail2ban/logrotate-rosstat-nginx` подготовлен с rename/create/USR1 и
семью несжатыми архивами. **Изменение файла в Git само не обновляет
`/etc/logrotate.d/rosstat-nginx` на хосте**; требуется отдельная установка
после допуска SHA, проверка reopen nginx и fail2ban `backend=polling`, затем
контроль места на диске и следующей ночной ротации.

### Cache-version eviction trap: `fe:ver:*` без TTL (2026-09-27)

Версия `fe:ver:{namespace}` управляет ключами `fe:{namespace}:vN:*`.
`allkeys-lru` может вытеснить версию при заполненном cache-Redis; тогда
`_ns_version()` вернёт v0 и старый кэш способен вновь стать видимым.
На проде вытеснение версии не зафиксировано, но сценарий воспроизведён
локально. В текущем DB 0 все остальные ключи имеют TTL, поэтому
`volatile-lru` защищает пять версий и продолжает вытеснять обычный кэш.
Продовый `.env` явно задаёт `REDIS_CACHE_POLICY=allkeys-lru`: compose-default
не переключит его сам. При выпуске изменить env адресно, проверить
`CONFIG GET maxmemory-policy` после restart и контролировать долю ключей
без TTL/ошибки записи; рост неистекающих ключей нарушит предпосылку.

### Too-many-open-files trap: плановые job'ы копят fd до Errno 24 (2026-09-20)

Контейнер backend с Docker-дефолтом `ulimit -n = 1024` на тестовом VPS три
ночи подряд ронял `world_national_core`: `us.yaml` не открылся —
`[Errno 24] Too many open files`. HTTP-путь (десятки запросов API/SSR) fd
почти не растил: текли периодические job'ы внутри того же uvicorn.

Что текло: `requests.Session` мировых адаптеров создавался на каждый
провайдер/страну и не закрывался — urllib3 `HTTPAdapter.__del__` держит
пулы в GC-циклах, сокеты остаются. Плюс `ImageFont.truetype` на каждый
OG-рендер открывал файл шрифта; `openpyxl.load_workbook` без `close()` на
файловом zip держит REG. Ловить: gauge `fe_process_open_fds` в `/metrics`,
поле `open_fds` в `/health/ready` (degraded при >80% soft RLIMIT_NOFILE),
строка fd в staleness-алерте. Починено: `close_http_resources` после
ingest страны, owned-session в Eurostat HTTP, `wb.close()`, кэш шрифтов,
`ulimits.nofile: 65536` у сервиса backend.

### Analytics-pool trap: аналитика делит пул и память с витриной (2026-09-03)

Rollups / Pulse / BI / ClickHouse-синк держали `idle in transaction` по 20 мин
на том же engine, что SSR. Пул 5+10 и лимит backend 1 ГиБ → хост в свопе,
главная 5–30 с. Канон: отдельный `analytics_engine` (pool 2+2, statement 60 с,
idle-in-tx 120 с); публичный engine — timeout 30 с. Короткие сессии по фазам.
Лимит backend на хосте 8 ГБ — 1536M (2026-09-04); ClickHouse 448M.

### BI-in-request trap: сборка дольше клиентского таймаута = сайт встал (2026-09-04)

Дашборд `/admin/bi` строился внутри HTTP-запроса: 7d ≈ 36 с на проде против
axios-таймаута 15 с. Клиент рвал (nginx 499) и ретраил, оборванные корутины
доигрывали сборку под замком — очередь сканов `behavior_events` (0,5 ГБ) на
минуты. Одновременно `world_card_siblings` на каждой мировой карточке читал
~5,5k широких страниц (LIKE по `stem_%` без экранирования `_` → префикс
индекса «ei»), при 1,7 запр/с ботов — терабайт чтений диска за 4 часа при
`shared_buffers=128MB` в cgroup 1G. Диск встал, тикер и рейтинг стран ушли в
таймауты. Канон: тяжёлые админ-витрины — только фоновой задачей
(single-flight на ключ, 202 «считаем», stale-while-revalidate сутки, `wait=`
для тестов); индекс `ix_world_indicators_card_lookup` (pattern_ops) +
экранированный LIKE (`_like_escape`); postgres 2,5G / `shared_buffers=640MB`
через env compose. Любой новый эндпоинт, который считает секунды, — не в
запросе.

### Sitemap-chunk trap: чанки на запросе робота = 504 (2026-09-03)

Холодный `_chunk_bounds` по ~787 тыс. групп не укладывался в
`proxy_read_timeout 30s` — 80 секций `world-years-*` отдавали 504, индекс
16 с. Канон: ночная gzip-сборка в `/var/www/sitemaps`, nginx `try_files` +
`if_modified_since off`. Живые счётчики — `/sitemap-stats.json`, не хроника
AGENTS.md.

### Crawl-budget trap: noindex не бережёт 5 млн URL (2026-09-25)

На хост ~5,04 млн loc в sitemap (509 шардов; EN и RU — отдельные хосты).
Google скачивает страницу, чтобы увидеть noindex, поэтому каталог остаётся
`index,follow` (`index_policy.py`). Неканонические дубли (`/compare?`,
`?mode=`, `?view=`, метки рекламы) и `/embed/` закрыты в robots у `*` и
`Googlebot`: своя секция Googlebot не наследует `*`. У Яндекса тех же query
нет в Disallow — склейка через Clean-param (`codes` только на `/compare`,
`view` по сайту); при конфликте побеждает Disallow и сигналы теряются.
`?year=` на карте регионов — канон, открыт. `?preview_locale=` открыт, чтобы
был виден 301. `/login` `/register` `/account` открыты: конечный набор,
noindex должен быть прочитан. `/assets/` не закрываем.

### Sitemap protocol trap: 50 000 URL и lastmod индекса (2026-09-25)

Один файл sitemap — не больше 50 000 URL и 50 МиБ несжатого (sitemaps.org,
Google, Яндекс). На хост сейчас 509 дочерних файлов и около 5,04 млн `<loc>`
(EN и RU — те же имена, вместе около 10,08 млн записей). `world-regions` как
простой раздел перерос потолок (~96 тыс. URL при ~33 МиБ). Публикация режет
любой простой раздел сверх лимита на `{name}-N` шагом 10 000; сборка
отказывается писать файл больше потолка и URL с `noindex`. Запрос одного
шарда не собирает реестр: `world-regions-N` читается страницей, а не списком
всех субнациональных URL.

В индексе `lastmod` дочернего файла — максимальная достоверная дата его URL,
не время ночной сборки: иначе все 509 файлов выглядят свежими каждую ночь и
инкрементальный обход индекса не отличает историю от живых разделов. Это и
есть реализм бюджета обхода при 5 млн URL: каноны остаются в индексе, но
неизменившийся шард не помечается свежим. Дата страницы без наблюдения
(статика, будущий месяц календаря) в urlset не пишется.

Ночная публикация не переписывает шард, чей отпечаток (путь, lastmod,
changefreq, priority, ревизия разметки) совпал с прошлой генерацией: файлы
обоих хостов становятся жёсткими ссылками. Сканирование БД по шардам остаётся
— иначе не отличить тихую правку ряда. Первая сборка после смены разметки
переписывает всё (`SITEMAP_RENDER_REV`).

### Canonical-rating-year trap: один контент — один URL (2026-08-28)

Годовые рейтинги стран живут в канонической модели «база = дефолтный год»:
`/world/rating/{concept}` — self-canonical дефолтного года (свежий год с
существенным покрытием); `/world/rating/{concept}/{year}` — self-canonical
каждого не-дефолтного года. Нарушения модели = индексный мусор:

1. **Два self-canonical на один контент** — если бы база и path-URL дефолтного
года оба канонизировали себя, поисковик видел бы дубль. Дефолтный год в path
уходит 301 на базу (`seo_pages.seo_world_rating_year`), в sitemap не попадает
(`site_urls._world_rating_urls` пропускает `active_year`), в блоке «Другие
годы» ссылается на базу.
2. **Софт-404 (подмена года)** — рендер на год без данных обязан отдавать
честную 404, а не «удобно» показывать дефолтный год: URL с чужим годом в
выдаче = пустая страница с чужим контентом. OG-картинка рейтинга тоже
годовая: `/og/world/rating/{concept}/{year}.png` рендерит именно этот год и
404 на пустой год — Алиса/Нейро берут картинку из DOM, несовпадение года на
картинке и в таблице = обман среза.
3. **Легаси `?year=`** — 301 сразу в конечную точку (на базу для дефолтного
года, на path-канон для остальных), без двойных редиректов.

Дефолтный год вычисляется по данным (`resolve_default_coverage_year`: пик
покрытия × доля) и меняется при обновлении рядов — при появлении полного
2026-го у всех концептов 301-модель перестроится сама, руками ничего.

### hreflang-catalog trap: обещанный EN-твин должен существовать (2026-08-28)

`en_catalog.has_en_path()` — единственный gate, решающий, объявлять ли
`hreflang="en"` на SSR-странице. Новая программатик-форма URL ОБЯЗАНА быть
добавлена в каталог до включения cutover (`apex_locale_en=true`), иначе две
ошибки по-тихому:

1. **Обещание 404** — `has_en_path` отдаёт True по широкому префиксу, а EN-твина
   под этим URL нет (или он отдаёт 404 для части стран/годов): поисковик
   получает hreflang на несуществующую страницу. Нестрановые/мусорные формы
   валидируются против статического каталога слагов (`_country_slugs` из
   `WORLD_COUNTRIES`), а не по префиксу.
2. **Противоречие канон-модели** — тесты hreflang пишутся против старой модели
   URL (например `?year=` или path дефолтного года как 200) и молча ломаются
   после перехода на 301-модель; при добавлении нового годового типа страницы
   сверять тесты с `CONTEXT.md::Canonical-rating-year trap`.

Контракт: `apex_locale_en=false` → hreflang-блок не рендерится вовсе; True →
тройка ru/en/x-default только для форм, перечисленных в `en_catalog.py`.
Тесты — `backend/tests/test_en_catalog.py` (фикстура обязана сеить данные для
КАЖДОГО тестируемого URL — падение «404 в hreflang-тесте» = дыра в фиксстуре,
не повод снимать проверку).

### Locale-host trap: ботов не редиректим, людей из РФ — на ru. (2026-09-03)

Язык страницы = хост (`ru.` → ru, apex → en, localhost → ru). После cutover
людей с IP России/СНГ с английского apex уводим на `ru.`; cookie `en` /
`stay-en` важнее гео. `Accept-Language` **не** редиректит (VPN/браузер
путали язык в 2026-08-31). Поисковые и ИИ-краулеры, API, sitemap, OG, RSS,
embed отвечают на запрошенном хосте — иначе cloaking. Флажок «Русский»
на проде = `https://ru.forecasteconomy.com` + cookie `fe_locale_pref=ru`.

### Anti-scrape stack (nginx + honeypot + fail2ban + bind-cookie)

**Уточнение 2026-09-20:** список ниже — история прежней конфигурации, не инструкция для новой ветки. `$bad_bot` и UA-освобождение от лимитов сняты; `fe_bind`/гео/ASN не блокируют доступ. Текущие локальные инварианты — [выше](#history-access-reliability-2026-09-20); изменения nginx не означают, что конфигурация host-level fail2ban уже изменена на проде.

2026-08-27: США — Cloudflare WARP `research/1.0` и Oracle stealth-Chrome.
2026-09-03: Сингапур — 1788 робот-визитов за день (Метрика `isRobot=yes`)
против 347 живых из РФ; Chrome/Windows, 1 страница, бездействие, ротация IP.
2026-09-04: гео-блок SG,PL поймал ~половину запросов фермы; остальные ушли
в CN/FR/BR (гидра). HTML с FR, API с SG — одна сессия с разных IP.

1. **nginx UA-фильтр** (`$bad_bot` → 403): `research`, `scrapy`, `aiohttp`, `okhttp`, `headlesschrome`, пустой UA. **Не** матчить `Chrome/N.0.0.0 Safari/537.36$`: с Chrome 101 это reduced UA **живого** Chrome ([UA Reduction](https://www.chromium.org/updates/ua-reduction/)); ферма копирует ту же строку. Полный build (`145.0.7632.xx`) живёт только в Client Hints. Инцидент 2026-09-04: правило 403-ило всех людей в Chrome, включая владельца в инкогнито.
2. **Ханипот** `/russia/util/links-exchange` и `/__honeypot__/trap` — 403 в nginx, **не** в sitemap и без ссылки в HTML (2026-09-25: скрытый анкор «обмен ссылками» убран — Google считает спрятанные ссылки спамом). Прямой запрос = 403 + `X-Robots-Tag: noindex` + jail `honeytrap`; поисковики в `ignoreregex`. Recrawl skip обоих путей.
3. **Rate-limit** `ssrstrict` 2 r/s на региональное семейство; `ssr` 5 r/s; `limit_conn 8` —
   на клиентский IP, ключ `$crawler_limit_key`. **Исключение одно (2026-10-04, по команде
   владельца): проверенный индексирующий краулер** — Googlebot/Google-InspectionTool,
   bingbot, YandexBot/MobileBot/Images/RenderResourcesBot/Webmaster — получает пустой ключ
   (nginx его не считает) **только если** IP клиента лежит в сети поисковика
   (`frontend/search-crawlers.conf`, генерируется `scripts/refresh-search-crawler-ranges.py`
   из списков Google/Bing и rDNS-проверенных /24 Яндекса) **и** UA называет его индексирующего
   бота. UA без сети, сеть без UA, GoogleOther/BingPreview/ИИ-краулеры — обычный лимит.
   Причина: 2026-10-03 настоящий Googlebot получил ≥3 573 ответов 429, все на региональных
   страницах (`/united-states/region/*` 3 289, `/russia/region/*` 281); Google по 429
   замедляет обход всего сайта. Список надо обновлять примерно раз в месяц; устаревший список
   безопасен (незнакомый IP просто лимитируется, как раньше).
   На `/og/` дополнительно **глобальный** бакет `ogall` 8 r/s + `ogconn` 4 соединения
   на хост — он не per-IP, проверенных краулеров не освобождает: пачка живых PNG ~700 КБ
   кладёт backend (инцидент 2026-09-04: главная «нет данных», axios 15 с, RSS 940MiB/1GiB;
   тогда причиной был обход per-IP лимита ИИ-краулерами по UA). Кэш PNG — следующий слой,
   не вместо потолка. История: до 2026-09-10 поисковики определялись по UA
   (`$ssr_limit_key`), это подделывалось и было убрано; 2026-10-04 исключение возвращено,
   но по сети, а не по UA.
4. **fail2ban**: jails читают файлы только с `backend = polling` (Ubuntu 24 дефолт — systemd journal, `logpath` молчит). failregex — **после** снятия ISO8601-даты (`^\s*<HOST> …`), иначе 0 матчей на живом логе. `nginx-429` / **`nginx-volume`** только HTML-каталог (не `/api/`, не тикер); `honeytrap`; `recidive`. Гидра «1 хит — новый IP» этим слоем не покрыта.
5. **Bind-cookie** `fe_bind` = HMAC(IPv4 /24 или IPv6 /48, UTC-день). HTML и API данных всегда 200: нет куки / чужой /24 — ставим новую. 403 по префиксу резал людей на VPN/CGNAT (пустой график). `/api/v1/auth/*` и `/api/auth/*` не режем. Поисковики по UA не режутся; приватный IP — skip. Гео `RUSTATS_SCRAPE_BLOCK_COUNTRIES` — аварийный рычаг (пусто = выкл). Ферму режем UA nginx + per-IP/host rate-limit, не страной.
6. **Гигиена аналитики**: `behavior.js`/`track.js` молчат при `navigator.webdriver`, `HeadlessChrome`, `Cursor/`; сервер на `/analytics/behavior` и `/analytics/events` отвечает `accepted: false`.
7. **MJ12bot** — `Disallow: /` в robots.txt (уважает robots; fail2ban банить незачем).
8. **Хостинговые ASN** больше не 403 (2026-09-06): VPN/облако — живые люди, страница должна открыться. Классификатор `is_hosting_network` остаётся для аналитики.
9. **HTML не прячем заглушкой.** Человек без `fe_bind` сразу получает страницу и данные графика, куку ставим на этом ответе. Тёмные JS-ворота с выдачи теряли клики (2026-09-04/05). Гидра видит SSR с первого хита — следующий слой: rate-limit / fail2ban, не пустой экран и не 403 VPN.

Проверенные поисковики — пустой `$crawler_limit_key` (п. 3). Проверка: `curl -A "Mozilla/5.0 research/1.0" -I https://forecasteconomy.com/` → 403; после `deploy/fail2ban-install.sh` на хосте `fail2ban-client get nginx-volume logpath` не пустой.

### Deploy-scope trap: «main» ≠ «одобрено к выкладке» (инцидент 2026-08-27, сайт лежал ~40 мин)

2026-08-27: задача «задеплой анти-скрейпинг» была выполнена как «задеплой `origin/main`». Прод до этого стоял на `774e615` (деплой от ~2026-07-15) — за месяц `main` накопил мировую экономику (Eurostat `/world*`, миграции `20260728_world`…`20260806_world_multi_provider_forecasts`), которую владелец выкладывать **не просил и не одобрял**. Пользователь увидел живой прод с чужой фичей и новыми URL: «я не хотел выгружать мировую экономику». Последовательность инцидента: (1) деплой `f15068e` тянет всю пачку ff-only; (2) frontend уходит в restart-loop (причина деплоя не в нём — smoke не различил), smoke fail → автооткат к `774e615`; (3) alembic уже накатил мировые миграции → старый код не знает головы → **backend crash-loop `Can't locate revision`**, сайт 502; (4) восстановление = forward-fix потом ручной откат: `alembic downgrade` трёх миграций отдельным контейнером нового образа + `git checkout 774e615` + up. Мировые таблицы были пустые — downgrade чистый; при налитых таблицах это был бы потери-инцидент.

**Правила (все три — жёсткие):**
1. **Скоуп деплоя = конкретный SHA из `deploy/approved-shas.txt`**, а не «main». ff-only тянет ВСЁ между продом и целью — перед деплоем показать владельцу `git log --oneline ПРОД..ЦЕЛЬ` и спросить подтверждение на пачку целиком, особенно если там фичи, к деплою задачи не относящиеся. Пустой/отсутствующий `approved-shas.txt` = деплой запрещён.
2. **Миграции в пачке — отдельное предупреждение.** Разгон схемы делает откат кода невозможным (старый код против новой головы = crash-loop). Есть новые `alembic/versions` в диапазоне — сказать владельцу до запуска, не после.
3. **Deploy.sh guard** (реализован): деплой продолжается только если NEW_SHA есть в `deploy/approved-shas.txt`; downgrade-миграций в диапазоне — деплой abort (downgrade схемой деплоя не делается никогда).

**Recovery-рецепт (если схема обогнала код)** — проверен живьём 2026-08-27, работает с тремя поправками ниже: НЕ рестартовать backend по кругу; (а) свежий `pg-backup.sh`; (б) `docker compose stop backend`; (в) `alembic downgrade <голова_старого_кода>` отдельным контейнером НОВОГО образа (он знает цепочку). Голову смотреть в репо-коммите, с которого катались (для `774e615` это `20260713_partner_rev`, НЕ «partner_revenue»). Рабочая форма запуска — именно `docker run`, а не `compose run`: нужен сетевой алиас и честный URL БД. Мировые миграции downgrade безопасны только при пустых таблицах — проверять `SELECT count(*)` ДО downgrade, при данных — стоп и ручное решение.

Поправки по живому прогону 2026-08-27:
1. **Запуск мигратора**: `ssh fe-prod 'cd /opt/rosstat && DBURL=$(grep "^RUSTATS_DATABASE_URL=" .env | cut -d= -f2-) && INNET=$(printf "%s" "$DBURL" | sed "s/@localhost:5434/@postgres:5432/") && docker run --rm --network rosstat_default -e RUSTATS_DATABASE_URL="$INNET" --entrypoint python rosstat-backend:<NEW_SHA> -m alembic downgrade <head>'`. `compose run --no-deps backend …` без этого env падает на подключении (env.py берёт URL из settings, а `.env` хоста внутрь не попадает); пароль БД из `.env` прода не равен дефолту — всегда тащить URL из файла.
2. **Движущий тег образа может указывать куда угодно** после прерванного деплоя/восстановления. После downgrade ОБЯЗАТЕЛЬНО перетегировать оба образа в старые SHA-теги (`docker tag rosstat-backend:<OLD_SHA> rosstat-backend`, то же для frontend) и поднимать через `docker compose up -d --force-recreate frontend backend`. Только `up -d` поднимет контейнер из образа, которым последний раз был затёрт движущий тег (на инциденте это был НОВЫЙ код) — и его entrypoint немедленно повторно накатит схему вперёд (alembic upgrade head), сведя даунгрейд на нет. Это случилось дважды за один вечер. Верификация — код ВНУТРИ контейнера, не healthcheck: `docker exec rosstat-backend-1 sh -c 'ls /app/alembic/versions | grep -c world'` (ожидаем 0) + `select * from alembic_version`.
3. **После восстановления сверять счётчики по каждому индикатору против бэкапа**, а не только общий total: короткое окно работы нового кода успело усечь историю пяти товарных YoY-derived (`coal/copper/silver/soybean/wheat-yoy`, −9 643 точки) пересчётом по свежему окну. Ремонт: `pg_restore` дампа во временную базу → `\copy` точек этих рядов в TSV → temp-таблица в живой базе → upsert ADR-0002 (`INSERT … ON CONFLICT (indicator_id,date) DO UPDATE SET value=… WHERE indicator_data.value <> EXCLUDED.value`, `created_at = now() at time zone 'utc'` — колонка NOT NULL без серверного дефолта). Общий diff по всем 984 рядам после ремонта = только новые точки ETL сверх дампа.
Финал восстановления: git прода `git reset --hard <OLD_SHA>` (иначе дерево опережает работающий код — ловушка для следующих откатов), `FLUSHDB DB 0` кэш-Redis (с паролем `-a "$(grep '^REDIS_PASSWORD=' .env | cut -d= -f2-)"`; DB 1 state — не трогать), smoke: front 200, `/api/v1/health/ready` 200, SSR региона 200, sitemap 200.

### Asset-hash mismatch trap

После `docker compose build frontend` без перезапуска backend — backend SEO renderer возвращает HTML со ссылками на удалённые `/assets/*-OLD-HASH.js`. Причина: `seo_renderer._APP_ASSETS` кэширует discover'ные имена файлов в памяти процесса.

**Правило:** при rebuild фронта всегда делать `docker compose up -d backend frontend` одновременно (backend перезапустится, кэш сбросится). Альтернатива: `docker compose restart backend && redis-cli -n 0 FLUSHDB` (только DB 0 — кэш; в DB 1 живут сессии/квоты, их не трогать).

### Pure-revision day

**Уточнение 2026-09-30:** следующий абзац — прежний предел, отменённый
дополнением ADR-0002. Текущий `scheduler.py::_fetch_changed` признаёт `success`
изменением; для `fallback_used` проверяет и `records_added`, и `records_updated`.
Чистая ревизия входит в каскад. `fetch_log.records_added` сам по себе не измеряет
все изменения; трактовка ниже «dispatch только по added» историческая.

Описано в ADR-0002. Если в ETL-батч ни один парсер не добавил новые строки (только in-place revisions), `run_for_updated_sources` не сработает; derived останутся stale до следующего «обычного» дня. Митигируется тем, что `cbr-fx`/`cbr-ruonia`/`gold-price`/`key-rate` — daily-источники. На практике pure-revision day без `records_added > 0` — крайне редкое явление. Жёсткий триггер ручного катчапа: `scripts/rebuild-all-derived.py`.

### Derived-forecast ordering trap (прогноз поверх свежего факта)

Инцидент 2026-08-05: на карточках «ВВП и рост» режим «К прошлому периоду» рисовал свежий факт Q1-2026 как ПРОГНОЗ. Причина — гонка двух каскадов: source-ETL ретрейнит `derived_from_source` siblings (`_retrain_dependents`) ДО того, как CalculationEngine досчитал их собственный факт. Фильтр `derived_from_source._select_forecast_points` отсекает прошлое по stale-факту derived-ряда → прогноз получает точку на дате, которая минутой позже становится фактом, а collision-policy фронта (`chartForecastMerge.js`: «на последней дате факта прогноз побеждает» — нужна для partial-bucket агрегатов) рисует её как прогноз.

**Правило:** прогноз derived-ряда валиден только относительно СВЕЖЕГО собственного факта. Поэтому после `calculation_engine.run_for_updated_sources` вызывается `_retrain_recalculated_derived` (scheduler.py), ретрейнящий ВСЕ пересчитанные derived с активной стратегией — включая `derived_from_source` (исключение для них отсюда убрано 2026-08-05). Исключение-не-дефект: конфиги с `monthly_tail_extrapolate`/`period_sum` легально держат ОДНУ прогнозную точку на якоре текущего незакрытого bucket'а (nowcast). Тот же класс бага был у сегментов weekly-CPI: primary-прогон пишет sibling-ряды в обход их `_handle_forecasts` — теперь `_post_upsert` сам ретрейнит сегменты с `forecast_steps>0`.

**Диагностика**: прогноз, у которого `min(forecast date) <= max(fact date)` у ряда без anchor-конфига = stale. Ремонт — ретрейн таких рядов (`retrain_indicator_forecast`), данные трогать не нужно.

### auto-loan-rate `element_id` (ЦБ DataService)

Декабрь 2025: ЦБ переразложил dataset 28 (auto-loan-rate). Исторические `element_id 2/4/5/6/7/9/10/11` больше не публикуются, остался только агрегированный `element_id=110` («По всем срокам»). Парсер с `element_id=11` тихо возвращал 0 точек 5 месяцев. Текущий `seed_data.py` хранит `"element_id": 110`. Если ЦБ снова переразложит другой dataset — симптом тот же: ETL `success` + `records_added=0` несколько недель подряд.

### CBR DataService date semantics + 1-month lag за XLSX (M0/M1/M2/deposits)

ЦБ DataService API (`/dataservice/data?publicationId=5&datasetId=*`) для денежных агрегатов имеет **две независимые ловушки**:

1. **Date offset**: ЦБ записывает «остаток на 1-е число» (т.е. dt=`2026-04-01` = состояние **конца марта**). Без `date_offset_months: -1` в конфиге индикатора последняя точка отображается на месяц вперёд («март как апрель»). Правка 2026-05-25 (Никита: «данные за март выдаются как данные за апрель»).
2. **Lag за XLSX**: DataService отстаёт на 2–4 недели от файла `https://www.cbr.ru/vfs/statistics/credit_statistics/monetary_agg.xlsx`. На 25 мая 2026 DataService отдавал последнюю точку 2026-04-01 (=март), а XLSX уже содержал 2026-05-01 (=апрель, M2=131989.8). Trading Economics берёт из XLSX → у нас был «отстающий» индикатор на 1 публикацию. Правка 2026-05-25 (Никита: «теперь стало за март, но апреля все ещё нет, а на trading economics уже есть»).

**Решение**: для `m0`/`m1`/`m2`/`deposits-individual`/`deposits-business` переключены на парсер `cbr_monetary_agg_xlsx` (`backend/app/services/cbr_monetary_agg_parser.py`) — читает XLSX напрямую, мапит rows (M0=row2, M1=row9, M2=row14, deposits-individual=row6+13+18, deposits-business=row5+12+17), применяет `date_offset_months: -1`. Один XLSX покрывает 5 индикаторов одной HTTP-выгрузкой.

**Что осталось на DataService**: `consumer-credit`/`business-credit` (publicationId=20/22) — другие публикации, не в `monetary_agg.xlsx`. Если у них всплывёт аналогичный лаг — нужен XLSX или альтернативная страница ЦБ.

**Регрессионный признак**: симптом «у trading economics уже опубликовано, у нас нет» для денежных индикаторов = вероятно ЦБ обновил `monetary_agg.xlsx`, а DataService ещё нет. Проверка: `curl -sI https://www.cbr.ru/vfs/statistics/credit_statistics/monetary_agg.xlsx | grep last-modified`.

### inflation-weekly: ETL_TIMEOUT_SECONDS vs полный crawl Rosstat-архива

`scheduler.run_etl_for_indicator` использует жёсткий per-indicator timeout = `ETL_TIMEOUT_SECONDS = 300` (`backend/app/tasks/scheduler.py`). Парсер `rosstat_weekly_cpi` исторически делал «толстый» прогон каждый день: crawl до 70 страниц `central-news`, `search` × 12 месяцев × все годы [2023..today.year], full GET каждого найденного bulletin (~150 на момент 2026-05), плюс XLSX (~110 продов + `ipc_spr_MM-YYYY.xlsx`). По мере накопления bulletin'ов общий wall-time приближался к лимиту: 24 мая 2026 ещё успел, 25-27 мая — `status=timeout` 4 дня подряд, точка 2026-05-25 (bulletin 77 от 27-05) не подхватилась. Никита: «недельная инфляция не обновилась, вчера вышла вечером, а у нас старые данные» (2026-05-28).

**Решение** (`backend/app/services/rosstat_weekly_inflation_parser.py`):

1. **Steady-state guard**: `_fetch_and_parse` выбирает `IndicatorData.date` для своего indicator → `existing_dates: set[date]`. Если есть хотя бы одна точка за прошлый год — backfill точно сделан, парсер качает **только `today.year`** (1 год вместо 4-х).
2. **Skip bulletin GETs**: для каждого URL вытаскиваем pub_date через regex `_BULLETIN_PUB_DATE_RE`. Если `pub_date < max(existing_dates) - 14d`, week-end такого bulletin'а заведомо в БД — `continue` без GET'a.
3. **XLSX-fallback только при cold-start**: в steady-state XLSX-приближение покрывает только историю до `weekly_cutoff_date`, которая уже в БД. Качать `nedel_Ipc.xlsx` + `ipc_spr` смысла нет.

Эффект: cold-start ≈ 5+ минут (мог не уложиться в 300с), steady-state — **~28 секунд**.

**Регрессионный признак**: `fetch_log.status='timeout'` несколько дней подряд для `inflation-weekly` при том, что bulletin на `rosstat.gov.ru/central-news?page=1` уже есть. Проверка: `curl -sk https://rosstat.gov.ru/central-news?page=1 | grep -oE 'storage/mediabank/\d+_\d{2}-\d{2}-\d{4}\.html' | head -5` — должен быть bulletin за позавчера-вчера.

**Что делать если опять отвалится**: запустить ETL вручную: `docker compose exec backend python -c "import asyncio; from app.tasks.scheduler import run_etl_for_indicator; asyncio.run(run_etl_for_indicator('inflation-weekly'))"`. Если внутри парсера за 10+ минут не приходит свежий bulletin — значит изменился layout `rosstat.gov.ru/central-news` или `/search`, нужна правка discovery (см. `_find_bulletin_urls_central_news` / `_find_bulletin_urls`).

**Subsequent (2026-06-07)**: на проде daily ETL 1–7 июня давал `timeout` ровно на 300с — парсер до steady-state деплоя укладывался в 295–328с. Доработки: (1) сегменты food/nonfood/services фильтруются по своим `existing_dates`, не upsert всей истории XLSX; (2) steady-state central-news max 12 страниц, search — 2 месяца; (3) XLSX парсится только за текущий (±январь) год; (4) `ETL_TIMEOUT_BY_PARSER['rosstat_weekly_cpi']=600` в `scheduler.py`.

### Rate limit policy

`RateLimitMiddleware` в `backend/app/main.py`: 120 req/min на обычные `/api/...` пути, **600 req/min** на `/api/v1/embed/*`, окно 60s, ключ — `X-Forwarded-For` (Caddy/Nginx добавляют). При превышении — `429 Retry-After: 60`. Если Redis недоступен — middleware пропускает запросы (graceful degradation).

### CSP whitelist для Yandex.Metrika

`Caddyfile` явно перечисляет десятки доменов `mc.yandex.{ru,by,...}`, `mc.webvisor.com`, `*.ingest.sentry.io` в `script-src` / `connect-src` / `child-src`. Любой новый Yandex-домен (например, `mc.yandex.kz` для Казахстана) — в whitelist через PR в Caddyfile, без него браузеры блокируют скрипт счётчика.

### Yandex.RSY (РСЯ floor-ad) — отдельный CSP-набор доменов

**Текущая сверка 2026-09-30:** React-обвязка `YandexRSY.jsx` и чистые SSR-страницы
(`behavior-standalone.js`) ставят в `yaContextCb` общий `lib/rsyFloorAd.js::renderFloorAd`.
Consent/robot/human gate остаётся в `consent.js`. `data-no-ads` исключает 404
из standalone-очереди; admin/embed исключаются в SPA. Таймерное уничтожение
пустого shell **отключено** (`AUTO_DESTROY_DISABLED`, `EMPTY_CHECK_MS=3600000`);
детектор через 8 секунд лишь проверяет fill для цели. Автоматический cleanup
только по явному SDK `onError`; refresh маршрута отдельно делает destroy/render
с cooldown 15 секунд. Поэтому пункт 5 ниже о сносе по `.needsclick`/таймеру —
исторический. Отсутствие объявления из-за выключенной площадки у провайдера
([RSY-page-disabled trap](#rsy-page-disabled-trap-рекламы-нет-а-код-исправен-2026-09-29))
не доказывает дефект очереди; состояние кабинета этим проходом не проверено.

Контекстная реклама РСЯ — **независимый от Метрики** домен-граф (официальный CSP partner docs + наш Caddyfile):
- `script-src https://yandex.ru https://an.yandex.ru https://yastatic.net https://*.yandex.ru https://*.adfox.ru` — `context.js` / AdvManager.
- `img-src` + `media-src` для `yandex.ru` / `*.yandex.ru` / `*.yandex.net` / `*.adfox.ru` / `yastatic.net` / `blob:` / `data:` — картинки и **видео** Floor Ad (touch).
- `connect-src` + `blob:` для телеметрии показов/кликов и adfox.
- `frame-src` + `child-src`: `yandex.ru` / `an.yandex.ru` / `*.yandex.ru` / `*.yandex.net` / `yandexadexchange.net` / `*.yandexadexchange.net` / `*.adfox.ru` — рекламный iframe.
- `style-src https://yastatic.net`, `font-src https://yastatic.net data:` — стили блока.

Точка инициализации:
1. **Loader** (`context.js`) грузится из consent-bootstrap `frontend/public/consent.js::loadAds()`. С 2026-06-16 модель — **подразумеваемое согласие** (152-ФЗ, ст. 9 ч. 1: согласие действием): Метрика и реклама грузятся **всем по умолчанию** при первом заходе, если в `localStorage['fe:consent:v1']` нет явного opt-out текущей версии. Баннер `CookieConsent.jsx` стал информационным («Продолжая пользоваться сайтом, вы соглашаетесь…»), отзыв/настройка — кнопка «Настройки cookie» в подвале; Политика и Соглашение переписаны под это (фикс падения статистики Метрики и дохода РСЯ после прежнего opt-in). И SPA shell (`index.html`), и SSR (`seo_renderer.py::_consent_bootstrap()`) подключают один и тот же `/consent.js` (nginx отдаёт с no-cache). Loader один на документ, независимо от количества блоков.
2. **Рендер блоков** — фронт-компонент `frontend/src/components/YandexRSY.jsx`, массив `RSY_BLOCKS`. Рендерится **только** блок текущей платформы через `AdvManager.getPlatform()`. Монтируется в `App.jsx::AppRoutes`. Embed-routes (`/embed/*`) **не** включают РСЯ.
3. **Гейт «только человек»** (2026-09-03) — `context.js` грузится **не** сразу: `armAdsGate()` в `frontend/public/consent.js` ждёт первого доверенного жеста (`pointerdown/pointermove/touchstart/wheel/scroll/keydown`, `isTrusted`), а роботов (`navigator.webdriver`, bot-UA) не слушает вовсе. Явный клик по баннеру согласия открывает гейт сразу (`__feApplyConsent(record, {explicit:true})`). Зачем: до гейта SSR-страницы просили объявление за каждого бота — 1985 запросов/день против 248 показов, `fillrate` 97% → 11,5% (27.08). Деньги и показы при этом не падали: платит человек, а не бот. Состояние наружу — `window.__feAdsGate` (`armed`/`requested`/`robot`/`signal`), тесты `frontend/src/lib/consentAdsGate.component.test.jsx`.
4. **Обновление на SPA-навигации** — `renderFloorAd({refresh:true})` при смене `pathname`: `destroy` прежнего блока + новый `render` с инкрементом `pageNumber` (официальный рецепт РСЯ для динамического контента). Кулдаун `REFRESH_COOLDOWN_MS = 15_000` — ниже медианы живого перехода на 2-ю страницу (18,8 с). Раньше 60 с оставляли без нового объявления 4 из 5 таких переходов; ещё раньше `window.__rsyFloorAdRendered` жёстко блокировал повторный render → одно объявление на весь визит.
5. **Empty-state** — если SDK оставил серый chrome без креатива (`onError` / пустой `.needsclick` ~2 с), вызываем `destroy` + force-remove шелла; goal `rsy_floor_render` — только при непустом fill.

Активные блоки (2026-06-23):
- `R-A-19489903-2` тип `floorAd` платформа `touch` (мобильные).
- `R-A-19489903-1` тип `floorAd` платформа `desktop` (десктоп).

Trap-симптомы при ломанной CSP:
- Консоль: `Refused to load the script 'https://yandex.ru/ads/system/context.js' ...` → не хватает `yandex.ru` в `script-src`.
- Объявление загружается, но iframe пустой → `frame-src` / `child-src` режут `*.yandex.net` / `yandexadexchange.net`.
- Креативы битые → `img-src` режет `avatars.mds.yandex.net`.
- **Пустой серый Floor Ad «РЕКЛАМА»+X на iPhone без креатива** → нет `media-src` (fallback на `default-src 'self'` режет video Floor Ad). Фикс 2026-07-14.

Goal в Метрике: `rsy_floor_render` — успешный непустой render.

Маркировку «Реклама» (+ домен/erid рекламодателя) несёт сам креатив РСЯ — отдельный оверлей-ярлык мы не рисуем (убран 2026-06-24: floorAd переменной высоты, фиксированный ярлык попадал в середину объявления).

### Отдельный scheduler и analytics-scheduler флаг

В проде `scheduler` — отдельный Compose-сервис; web worker не регистрируют
фоновые job'ы. Актуальный перечень и CronTrigger — в `backend/app/main.py`:
помимо `daily_etl` и `ticker_live_pull` там есть вечерний и поздние ETL,
мировые ingest/forecast, rollup'ы, отчёты и другие задачи. `calendar_refresh`
запускается **ежедневно в 03:00 МСК**, а не первого числа. Дополнительные
`analytics_hourly`/`analytics_daily` включаются через
`RUSTATS_ANALYTICS_SCHEDULER_ENABLED=true`. Ошибка job должна доходить до
APScheduler `EVENT_JOB_ERROR`, иначе штатный алерт не сработает.

**Блокировки job'ов (F07, 2026-10-04).** `locked_job` держит lease в state-Redis:
ключ `sched:lock:{группа или job_id}`, значение — токен владельца, heartbeat раз
в TTL/3, снятие только владельцем. Потеря lease отменяет задачу и бросает
`JobLeaseLostError` (алерт через `EVENT_JOB_ERROR`). `daily_etl`, `evening_etl`,
`late_minfin_etl`, `late_fred_etl` делят один ключ `sched:lock:etl`
(`JOB_LOCK_GROUPS` в `services/job_lease.py`). Долгий синхронный код в `to_thread`
отмена не прерывает.

### Live ticker: MOEX-приоритет с CBR-fallback для FX

**Текущая сверка 2026-09-30:** старое описание ниже сохраняет происхождение
FX-fallback. `ticker.py` выбирает шесть кодов по lane: RU — рублёвые пары,
BTC, Brent и золото; EN — EUR/USD, GBP/USD, USD/CNY, BTC, Brent и золото в ₽/г.
Lane определяется locale (`tickerLane.js`), не URL. `ticker_worker.py` берёт
Brent (EIA), золото (Банк России) и EN-кроссы (ЕЦБ) из тех же дневных DB-рядов,
что карточки; MOEX Brent/gold отбрасываются. Текущий TTL Redis — **90 секунд**,
локальная память дневных рядов — 300 секунд. `tickerPoll.js` обычно опрашивает
раз в 4 секунды, при 429 ждёт retry-after/60 секунд, при другой ошибке — 16 секунд.
Старые «пять snapshot», «TTL30» и гарантированный лаг ≤9с не описывают нынешний
код: задержка источника и ошибки не ограничены такой оценкой. Дата/источник
дневного значения и fetched_at внутридневного различаются. Это чтение кода,
нового замера источников или runtime в данном проходе нет.

Источники (`backend/app/services/ticker_sources/`):
- **MOEX ISS** — USD/RUB (`USD000UTSTOM`), CNY/RUB (`CNYRUB_TOM`), Brent (ближайший фьючерс `BR-X.Y` на FORTS, динамически определяется по `LASTTRADEDATE`). ISS возвращает 4 строки marketdata по бордам — реальные сделки на **CETS**, остальные пустые.
- **Binance public** — BTC/USDT (`/api/v3/ticker/24hr`).
- **ЦБ XML_daily fallback** (звонок 2026-05-22) — для FX когда MOEX отдал `LAST=None` на всех бордах. EUR/RUB на MOEX после санкций ЕС март-2024 **фактически мёртв** — у `EUR_RUB__TOM` LAST всегда null. Fallback тянет `https://www.cbr.ru/scripts/XML_daily.asp` (сегодня + вчера для % change) и подмешивает с пометкой `market_open=False, source="ЦБ РФ"`.

Frontend (`frontend/src/components/LiveTicker.jsx`): `useQuery` polling 4с, sticky-bar над Navbar (`fixed top-0 z-[110]`). Типографика **единая** для всех пяти snapshot'ов — `text-text-primary font-semibold` независимо от `market_open` и `source` (различие источника живёт в `title`-тултипе). Цена показывается всегда если `price > 0`, чтобы CBR-fallback не визуально ломал ряд.

Эндпоинт `/api/v1/ticker/live` (`backend/app/api/ticker.py`) читает Redis-снапшоты с TTL 90s (`REDIS_TTL_SECONDS` в `ticker_worker.py`). APScheduler job `ticker_pull_job` пишет их каждые `ticker_pull_interval_seconds` (по умолчанию 8s) — TTL намного больше интервала, пропущенный проход не обнуляет бегущую строку.

### `is_listed` vs VariantGroupPicker

Скрытие индикатора через `is_listed=False` — это **только** про карточку в `/category/{slug}`. Сам индикатор по-прежнему доступен по `/indicator/{code}`, отдаётся API, индексируется поисковиками, попадает в sitemap. Если нужно полностью убрать индикатор — это другой механизм (`is_active=False` + ручная чистка sitemap-генератора).

### Frequency switcher: пары индикаторов разной частоты

T3 (2026-05-12): для индикаторов внешней торговли публикуем одновременно квартальные (history с 1994) и месячные (history с 1997 для goods, с 2018 для services) ряды. Чтобы UI/SEO не плодили дубли — единая модель:

- **Primary** (родитель) = quarterly индикатор, `is_listed=True`, появляется в категориях и sitemap. В `model_config_json` ставится `alternate_frequencies = {"monthly": "<code>-monthly"}`.
- **Secondary** (counterpart) = monthly индикатор `<code>-monthly`, `is_listed=False`, `forecast_steps=0`, скрыт из категорийного листинга через `INDICATOR_HIDDEN_FROM_LISTING`. В `model_config_json` ставится `primary_indicator_code = "<parent_code>"`.

Backend контракт:
- `IndicatorRead` отдаёт оба поля (`alternate_frequencies`, `primary_indicator_code`). См. `backend/app/schemas.py`.
- `seo_renderer.render_indicator_html` рендерит `<link rel="alternate" hreflang="ru-RU">` на counterpart URL — поисковики видят семантическую пару `/indicator/exports` ↔ `/indicator/exports-monthly`.

Frontend контракт:
- Чистая логика — `frontend/src/lib/frequencySwitcher.js::buildFrequencyItems`. На неё опирается `FrequencySwitcher.jsx`, который рисует tabs «Квартальные / Месячные» над графиком (рядом с `VariantGroupPicker`/`CpiViewModePicker`).
- Переключение URL-based: каждая частота — отдельная карточка с собственным SSR canonical (SEO-благоприятно). `IndicatorChart`, telemetry, datatable читают `indicator.frequency` → автоматически адаптируются под помесячный/поквартальный formatter без отдельной логики.
- Yandex.Metrika goal `frequency_switch` (см. `track.js::events.FREQUENCY_SWITCH`) — каждый клик switcher логируется с `from/to/fromFrequency/toFrequency/indicatorCategory`.

Trap для будущих расширений: если добавляешь третью частоту в пару (например `inflation-weekly` к существующим `cpi`/`cpi-monthly`) — поле `alternate_frequencies` это map `{[freqKey]: code}`, поддерживает любое количество ключей. UI отрисует столько tabs, сколько entries (тест `frequencySwitcher.test.js::handles 3-way switcher` — фиксирует контракт).

### CPI level «Индекс» режим (frontend)

Фронт строит cumulative index с базы `2000-01 = 100` через `frontend/src/lib/useIndicatorViewModeData.js::buildCumulativeIndex`. История 1991–1999 обрезается: январь 1992 = 345% месячный → цепное произведение через 9 лет даёт сотни тысяч и шкала становится нечитаемой. Это **не** ошибка, это осознанный cutoff.

### `/api/docs` (Swagger) на проде

`main.py` регистрирует Swagger только если `settings.debug=True`. На проде `RUSTATS_DEBUG=false` (см. `docker-compose.yml`) — Swagger недоступен. Локально для разработки: `RUSTATS_DEBUG=true` в `.env` → доступно `/api/docs`, `/api/redoc`, `/api/openapi.json`.

### Forecast retrain после деплоя (новые derived)

Когда деплой добавляет **новые derived-индикаторы** (через правки `seed_data.py` + `DERIVED_SPECS`), `entrypoint.sh` идемпотентно отрабатывает seed (создаёт/обновляет строки `indicator`), но **forecast retrain не запускается автоматически**. Daily ETL-job переобучает прогнозы только тех индикаторов, у которых на этом тике добавились новые точки в `data_points` — для свежесозданного derived это произойдёт только после следующего ревизии источника.

Симптом: `/api/v1/indicators/<new-derived-code>/forecast` возвращает `null` несколько часов или дней. Так было 2026-05-07 после деплоя GDP nominal/real split — три из восьми GDP-индикаторов отдавали `null` до ручного `--forecast-only` retrain.

Mitigation: после любого деплоя, добавляющего derived, выполнить ручной retrain в правильном порядке (источники → derived):

```bash
docker compose exec backend python -c \
  "import asyncio; from app.services.forecast_pipeline import retrain_indicator_forecast; \
   asyncio.run(retrain_indicator_forecast('<source_code>'))"
```

Каскадный retrain `derived_from_source` стратегии подхватит зависимые индикаторы. После — `redis-cli -n 0 FLUSHDB` для сброса `fe:*:forecast` ключей (только DB 0: DB 1 хранит сессии пользователей — с 2026-07-02 они изолированы от кэша, FLUSHDB кэша больше никого не разлогинивает).

### Inflation-weekly: семантика и источник

`inflation-weekly` ряд = **недельный прирост ИПЦ к предыдущей неделе** (`100.XX` означает «×1.00XX»), **не** накопленная с начала месяца. Парсер `rosstat_weekly_cpi` ходит за HTML-бюллетенями Росстата только за `today.year`; для 2022–2025 — XLSX-fallback (~110 продов × веса корзины). HTML перезаписывает XLSX при коллизии. В `indicator_data` нет колонки `data_source` — различить «из бюллетеня» vs «из приближения» можно только косвенно через `fetch_log`.

Январский трёхнедельный «выпад» (одна точка с 23 декабря по 12 января ~100.45/101.26) — штатный новогодний бюллетень Росстата, а не баг.

### SDDS English vs Rosstat русский

**Trap**: SDDS-XLSX на `eng.rosstat.gov.ru` (`SDDS_*.xlsx`) — это IMF-зеркало в формате «2010 = 100 chained cumulative index», публикуется с лагом ~год (комментарий в `rosstat_sdds_fetcher.py:6-9`). Парсеры `rosstat_sdds_ppi`, `rosstat_sdds_housing`, `rosstat_sdds_gdp`, `rosstat_sdds_labor`, `rosstat_sdds_ipi`, `rosstat_population` (часть) тянут оттуда. Но **первичная публикация Росстата** — на `rosstat.gov.ru/statistics/<section>/` в формате MoM/QoQ % (100 = предыдущий период) и с историей с 1998+ (для PPI), 1991+ (для CPI), 1995+ (для ВВП).

**Симптомы расхождения с rosstat**:
1. **Format mismatch**: наша DB хранит cumulative index (PPI = 311.40), руководитель открывает rosstat и видит MoM (PPI = 100.6%) — разные числа, кажется баг.
2. **Короткая история**: SDDS даёт PPI с 2011, Housing с 2016, ВВП с 2011 — потому что 2010=100 base. Русский Росстат — глубже.
3. **Stale latest**: SDDS лагает на год. Текущий месяц/квартал в SDDS может отсутствовать или быть приближённым.

**Audit категории «Цены и инфляция» (2026-05-10)** (см. также chat-уровень): CPI 4/4 индикаторов 100% совпадают с rosstat (парсер `rosstat_cpi_xlsx` → `ipc_mes_*.xlsx` правильный). PPI и Housing (3 индикатора) — все из SDDS, требуют миграции на русский Росстат.

**Политика**: для всех новых индикаторов и при правке существующих SDDS-парсеров — переключение на русский Росстат. SDDS используется **только** как fallback, если русский эквивалент недоступен (на момент 2026-05-10 не известно ни одного такого случая в категории Цены). См. [ADR-0004](docs/adr/0004-rosstat-russian-canonical-sdds-deprecated.md) — содержит migration pattern и pilot evidence для `gdp-nominal`.

**Migration trap для ETL/forecast**: при замене source формата (2010=100 → MoM%) одного и того же `code` все исторические точки переписываются через `bulk_upsert WHERE value <> excluded.value` (ADR-0002). Frontend value formatter / chart unit и forecast model обучены на старом формате — оба требуют обновления одновременно с парсером (см. trap «Forecast retrain после деплоя» — здесь применяется тот же mitigation). Для unit-preserving миграций (например, `gdp-nominal` млрд руб → млрд руб) frontend трогать не нужно, retrain прогноза идёт каскадно автоматически из `run_etl_for_indicator`.

**Pilot подтверждение pattern (2026-05-10)**: `gdp-nominal` мигрирован end-to-end на локальном docker stack. Переключение `gdp_source: "official_quarterly", gdp_sheet: "2"` в `seed_data.py` → 60/60 точек переписаны (Q4 2025: 60516.7 → **62354.1** = rosstat publication ✓), derived gdp-yoy/qoq/annual пересчитаны через `rebuild-all-derived.py` (127 точечных изменений), forecast cascade retrain автоматически. Никаких изменений в коде парсера не потребовалось — `parse_rosstat_gdp_quarter_grid_xlsx` уже умеет произвольный sheet через config.

**Категория «ВВП» полностью мигрирована (2026-05-10)**: pilot (`gdp-nominal`) + rollout (`gdp-consumption`, `gdp-government`, `gdp-investment`). Для use-компонентов потребовался новый источник `GDP-quarters-of-use-1995-4kv-2025.xls` (legacy .xls binary, OLE2) → расширен `fetch_rosstat_static_xlsx` (теперь принимает оба magic — XLSX `PK\x03\x04` и XLS `\xd0\xcf\x11\xe0`), новая ветка парсера `gdp_source: "official_use"` (xlrd, multi-row layout), 4 unit-теста через synthetic .xls fixture (`xlwt==1.3.0` в requirements). Rollout pipeline test: `0 new, 0 updated` для всех 3 индикаторов — best-case migration, SDDS уже подтянул rosstat, миграция проактивная (защита от будущих лагов + canonical source policy без disruption). SDDS-ветка `fetch_sdds_xlsx("gdp")` больше не используется ни одним active индикатором.

**Категории «Демография», «Промышленность», «Труд», «Цены» полностью мигрированы (2026-05-10)**: 11 индикаторов переведены на canonical русские источники (commits cf08878 / 13a0251 / 5317421 / 0dc61b8 + housing pending). Pattern «path P (compat)» закрепился: для индикаторов где canonical Rosstat публикует только MoM/QoQ% (без cumulative index), парсер читает последнюю DB-точку и chains новый relative change → один новый datapoint per ETL run, исторический ряд от прошлой SDDS-стадии остаётся, gradual migration, frontend/forecast model не требуют изменений. Применён в `rosstat_ipi_parser` (chain monthly, нормализация 2023=100), `rosstat_ppi_parser` (chain monthly из PDF), `rosstat_housing_parser` (chain quarterly из PDF, primary+secondary). Для labor (4 индикатора) — sociomonomic PDF report повышен из supplementary до primary source (нет comprehensive monthly XLSX по labor на rosstat сайте). Подробности по каждой категории — в [ADR-0004 «Subsequent additions»](docs/adr/0004-rosstat-russian-canonical-sdds-deprecated.md).

**GDP history extension до 1995 (2026-05-10)**: 5/5 GDP source-индикаторов продлены с 60 до **124 точек** (1995-Q1 → 2025-Q4) через **ratio-splice на overlap-году 2011** — pure-функция `splice_at_overlap(history, modern, overlap_year)` в `rosstat_gdp_parser.py`. Калибрует `ratio = mean(modern_2011) / mean(history_2011)`, scale'ит historical-точки (year < 2011) к base modern-методологии (для nominal: ОКВЭД2007 → ОКВЭД2, ratio ~1.074; для real: в ценах 2008 → в ценах 2021, ratio ~2.81). Standard economic-series splice техника (ОЭСР/МВФ practice). Конфиг per индикатор — `gdp_history_sheet` + `gdp_overlap_year` в `model_config_json`. Закрыта прямая жалоба руководителя 08.05.2026 «у Росстата с 1995, у нас почему-то с 2011». Trap, выловленная на data: Rosstat Excel хранит часть значений как СТРОКИ с Russian decimal + footnote suffix («1662,82)» = 1662,8 + footnote 2) → добавлен `_parse_ru_number` хелпер.

### Source-depth trap (новый индикатор)

Парсер фетчит N лет, БД хранит M < N. Симптом — `/indicator/<code>` начинается с 2020 (или 2015), хотя источник публикует с 1991/1995. Это видно только пользователю, который сравнивает с публикацией Росстата/ЦБ; внутренний мониторинг молчит.

**Примеры обнаруженных пробелов** (звонок 2026-05-22):
- `wages-nominal` начинался с 2015 → Росстат публикует с 1991. Закрыто через `wages_historical.py` (immutable seed годовых точек 1991-2014).
- `key-rate` начинался с 2013-09 → ставка рефинансирования ЦБ с 1992. Закрыто через splice на overlap-точке 2013-09-13 (`refinancing_rate_historical.py`).
- `gdp-*` начиналось с 2011 → Росстат публикует с 1995 (ОКВЭД2007). Закрыто через ratio-splice на overlap-year 2011.
- `housing-price-{primary,secondary}` — backfill 1998-2014 через `housing_historical.py`.
- `inflation-weekly` начинается с 2022-01-10 → Росстат публикует с 2003, но **архив до 2022 утерян** (gks.ru не работает, Wayback не имеет нужных URL); это технический предел, не наша недоработка.

**Правило:** при добавлении любого нового парсера / индикатора — **обязательная проверка по чеклисту в `AGENTS.md::Шаг 4`** (`Source-depth invariant`). Если источник даёт глубже чем в seed — заводим `<name>_historical.py` immutable seed.

### Browser-cache trap при rebuild frontend

После `docker compose build frontend && up -d frontend` пользователь в обычном окне Chrome может видеть **unstyled HTML** (чёрный фон, синие подчёркнутые ссылки). Причина — браузер держит старый HTML в **disk cache** и пытается загрузить ассеты со старыми hashes, которые в новом контейнере отсутствуют → 404 → React shell не загрузился → unstyled.

Это **не** asset-hash trap (см. выше) — backend и frontend синхронизированы, ассеты на свежих hashes отдаются 200. Проблема в кеше **самого браузера** пользователя.

**Правило:** после rebuild frontend для демонстрации — открывать в **incognito** или делать **Cmd+Shift+R** (hard reload, минует disk cache). В DevTools → Network → Disable cache на время тестирования.

### New indicator initial ETL trap (закрыт автоматикой 2026-05-22)

После `seed_data.upsert_indicators()` создаёт новый indicator с `parser_type != "derived"` и `is_active=true`, **первый ETL** по нему ранее не запускался автоматически. Daily ETL job ходит в 06:00 МСК — между deploy и 06:00 новый индикатор стоял пустой, frontend показывал «нет данных».

**Случай 2026-05-22:** `deposit-rate-medium` и `deposit-rate-long` (звонок 21-05, правка C3) — оба добавлены в seed_data 21-05, daily-job не успел отработать, при ревизии 22-05 у обоих было 0 точек. Триггернул вручную → 147 точек 2014-2026.

**Закрытие:** в `app/main.py::lifespan` добавлен background task `_catch_up_empty_indicators()` — при startup ищет все `is_active=True AND parser_type != "derived"` индикаторы с `COUNT(indicator_data) = 0` и триггерит ETL для них. Запускается как `asyncio.create_task(...)`, не блокирует uvicorn ready. Применяется один раз при каждом старте контейнера. Derived подхватятся cascade'ом после source.

**Правило:** ничего не делать вручную. Если контейнер был запущен, а у нового source-индикатора всё ещё 0 точек — смотреть логи backend на `Startup catch-up: <code> failed: ...` (источник недоступен, конфиг битый и т.п.).

### Annual-in-monthly mixing trap (backfill в чужую частоту)

Парсер добавляет в indicator с `frequency=monthly` годовые точки (1 января каждого года). Frontend chart label остаётся «помесячно» (из `frequency`), а на графике рывок: 24 точки за 24 года выглядят как 24 month-точки с гэпами. Пользователь видит ложную динамику, фигуры месяц-к-месяцу несравнимы с годом.

**Случай 2026-05-22:** `wages-nominal` (frequency=monthly с 2015) → backfill 24 годовых точек 1991-2014. График показывал «ПОМЕСЯЧНО» + рваный ряд. **Фикс:** годовая история вынесена в отдельный `wages-nominal-annual` (`frequency=annual`, `is_listed=false`), доступна как режим «Годовое (с 1991)» через `viewModeFamilies`. Monthly indicator теперь содержит только monthly-точки.

**Доводка 2026-07-01:** `wages-nominal-annual` из manual_historical seed переведён в **derived** через op `annual_mean_with_prefix` (immutable хвост 1991-2014 + annual mean месячного ряда 2015+) — движок продолжает годовой ряд сам при закрытии года, ручной `scripts/backfill-wages-history.py` удалён (см. ADR-0001 «Subsequent additions»). Попутно закрыта дыра `wages-nominal` 2022-12 (декабрь пропущен в разовой заливке monthly-ряда; из-за неё 2022 выпадал из годового среднего): точка 88 468 ₽ добавлена в `MONTHLY_GAP_FILL` (`wages_historical.py`), идемпотентный gap-fill в `seed_data.py` льёт её ДО пересчёта derived. **Внутренние дыры месячного ряда должны быть закрыты gap-fill'ом**, иначе annual mean года с пропуском занижен — общее ограничение любого annual-mean sibling'а.

**Правило:** **никогда** не лить точки чужой частоты в существующий indicator. Если source даёт annual до 1998 и monthly с 2015 — это **два разных indicator'а** с одним visual entry (через view-mode family). Аналогично quarterly история + monthly свежак, weekly прошлое + daily настоящее, и т.п.

**Проверка при backfill:** перед `bulk_upsert` сверить `target.frequency` с фактической частотой добавляемых точек. Если расхождение — заводим sibling indicator + добавляем режим в `viewModeFamilies`. См. чеклист в `AGENTS.md::Шаг 4` (новый пункт «Frequency consistency»).

### Annual-in-quarterly trap (кросс-каденс QoQ/MoM даёт годовой прирост под видом квартального)

Родственник trap'а выше, но на слое derived-приростов, а не backfill. Если ряд-**источник** сам смешивает годовую историю и квартальный современный сегмент (обычная ситуация для индексов цен Росстата: годовые точки до ребейза, квартальные после), то `qoq()`/`mom()`, считающие % «к предыдущей точке любой ценой», между двумя годовыми точками возвращают **годовой** прирост, ошибочно подписанный как квартальный.

**Случай 2026-07 (G2-аудит):** `housing-price-primary/secondary` — годовые точки 1998-2014, квартальные с 2015. `housing-qoq-*` рисовал 46 %, 25 %, 18 %… (годовые скачки) на всём отрезке до 2015, а затем обрыв до ±1 % — визуальный мусор. **Фикс:** чистая op `qoq_adjacent(series, max_gap_days=110)` считает % **только между соседними кварталами** (интервал ≤110 дн ≈ квартал + запас; годовой ~365 дн отбрасывается). Ряд `housing-qoq-*` теперь стартует 2015-03, макс |QoQ| ~8 %.

**Правило:** для QoQ/MoM поверх ряда, чья история может менять частоту, использовать cadence-aware op (`qoq_adjacent`), а не «слепой» `qoq()`. SQL-аудит на смешение: медианный интервал между точками не совпадает с объявленной `frequency`, либо в quarterly/monthly ряду есть annual-размерные гэпы.

### Incomplete-period aggregation trap (неполный текущий год/квартал)

Годовой/квартальный режим строится агрегацией под-периодов: backend `derived_ops._aggregate` (`period_sum`/`period_avg`/`period_last` для семей `viewModeFamilies`), `annual_sum` (ВВП), и client-side `viewModeFamilies.applyAggregateTransform` (daily-индикаторы Phase 5). Если текущий год не завершён, агрегат неполного года рисуется точкой факта: сумма (инвестиции за 1 квартал 2026) обваливается вниз, среднее за полгода занижено, «на конец года» подменяется YTD-значением.

**Случай 2026-06-15** (созвон: «инвестиции за 2026 не показывать — год же не закончился, проверь все индикаторы»): `capital-investment-sum-year` показывал обвал 2026 из одного квартала. Фикс — `_aggregate` отбрасывает bucket, в котором уникальных под-периодов меньше ожидаемого (`_expected_subperiods`: месячный источник → 12, квартальный → 4; quarter → 3). **Полнота считается по уникальным месяцам, а не по числу сырых точек** — иначе у дневного источника ~250 точек в году всегда «проходили» порог 12, и неполный год дневных агрегаций (ключевая ставка, валюты, золото, Brent, резервы) не отсекался. Тот же месяц-based порог продублирован на фронте в `applyAggregateTransform` (year→12, quarter→3 уникальных месяцев).

**Trap внутри trap (idempotent upsert не удаляет):** пересчёт через `_aggregate` отдаёт меньше точек, но `bulk_upsert` — INSERT…ON CONFLICT, он **не** удаляет устаревшую точку 2026. Чистит её `_execute` через `prune_indicator_dates_not_in` (даты, которых нет в свежем ряду). Поэтому после правки агрегации обязателен полный `scripts/rebuild-all-derived.py` (он зовёт `_execute`), а не только проверка значений — иначе обвальная точка остаётся в БД.

**Случай 2026-06-16** (доводка той же правки): `_expected_subperiods` определял частоту источника по «макс. числу месяцев в каком-то году». У weekly-ряда с КОРОТКОЙ историей (`international-reserves`: ~66 точек, старт ~март 2025 из-за бага формата дат UniDbQuery — см. trap ниже, самый полный год = 10 месяцев) это давало `mx=10 → ожидание 4` (как у квартального), и неполный 2026 (6 месяцев ≥ 4) снова проходил фильтр. Фикс — частота определяется по **медианному интервалу между точками** (`≤45 дн → 12/3`, `≤100 дн → 4/None`, иначе None), что устойчиво к длине истории. Следствие: если у источника нет ни одного полного календарного года, годовой агрегат корректно пуст.

**CBR UniDbQuery monthpicker trap (2026-08-10).** Страница `cbr.ru/hd_base/mrrf/mrrf_7d/` использует monthpicker: `UniDbQuery.From`/`To` = `MM.YYYY` (например `05.1998`). Формат `DD.MM.YYYY` (как у KeyRate/RUONIA) сайт молча игнорирует и отдаёт дефолтное окно ~последний год → в БД оставался огрызок с середины 2025 при доступной истории с 29.05.1998. Фикс: `format_unidb_month` + `backfill_from=1998-05-01` + self-heal `[floor, earliest)`. Не путать с daily-фильтрами KeyRate/RUONIA — там по-прежнему `DD.MM.YYYY`.

**Правило:** любую новую годовую/квартальную агрегацию (backend op или client transform) проверять на неполный текущий период; порог полноты — в уникальных под-периодах (месяцах), не в сырых точках; частоту источника определять по ритму (медиана интервалов), не по «макс. месяцев в году».

### View-mode template change orphans (сироты при смене шаблона)

**Уточнение 2026-09-30:** нижний рецепт удаления относится к конкретному инциденту 2026-06-06. Само отсутствие кода в новом seed не разрешает удалять исторический ряд: сначала проверить consumers, variant/frequency reachability и оба canonical/301 пути по `docs/dead-code-report.md` и текущим рецептам. Флаги карты — кандидаты на расследование; сохранность истории и индексируемых URL остаётся обязательной.

При смене view-mode шаблона индикатора, при которой **исчезают режимы** (T3→T8 убрал «на конец периода» у зарплаты/labor-force/employment; Tidx→Tidxq убрал «М/м» у `housing-affordability`), sibling-коды старых режимов (`*-eop-quarter`, `*-mom`, …) перестают генерироваться конфигом, но **остаются в БД** с прошлого seed. Seed не удаляет строки и сбрасывает `is_listed=True` для всех, пряча обратно только коды из `INDICATOR_HIDDEN_FROM_LISTING`. Сироты в этот набор не попадают → **всплывают карточками в каталоге**.

**Случай 2026-06-06:** перевод зарплаты/labor-force/employment на T8 оставил 6 сирот `*-eop-quarter/-year` → «Рынок труда» показал 10 карточек вместо 4.

**Правило:** после reseed, изменившего шаблоны, удалять коды, которых нет в текущем `seed_data.INDICATORS` (`IndicatorData` + `Forecast` + `Indicator`). Идемпотентно; чистит и каталог, и пересчёт derived. Не полагаться на то, что seed «сам уберёт» — он только upsert.

### View-mode family metadata leak (downstream-протекание родительских полей)

**Текущий generic-механизм (сверка 2026-09-27):** `FamilyDef` в `view_model_families.py`, экспорт JSON, `GenericIndicatorView`/`useGenericViewModeData`. Ниже сохранён исходный legacy-инцидент и его исправление; инвариант частоты/единиц/методологии остаётся общим.

При добавлении нового члена в семью `viewModeFamilies.js` (real sibling с другой частотой или единицей) недостаточно прописать `code` — нужно протянуть **все** поля, от которых зависят downstream-компоненты `IndicatorDetail.jsx`. Иначе родительские метаданные «протекают»: pill и заголовок графика читают `indicator.frequency` родителя, секция «Методология» читает обобщённый CPI-блок из `cpiViewModeContent.jsx`, и пользователь видит чужой смысл.

**Случай 2026-05-22:** `/indicator/wages-nominal?mode=annual` (target = `wages-nominal-annual` с `frequency=annual`):
- Pill показывал «ПОМЕСЯЧНО», заголовок графика — «— помесячно» (frequency leak — `effectiveIndicator` подменял `unit`/`name`, но не `frequency`).
- Секция «Методология» отдавала текст CPI: «Годовая инфляция декабрь к декабрю» (methodology leak — `getViewModeContent()` отдавал блок `ANNUAL` для любого `safeViewMode === 'annual'` без проверки `isPriceCategory`).

**Фикс:**
1. `effectiveIndicator` в `IndicatorDetail.jsx` дополнительно подменяет `frequency` из `familyModeMeta.frequency` (для real siblings) или `DAILY_AGG_FREQUENCY[granularity]` (для daily-aggregation Phase 5).
2. `IndicatorDetailHeader.jsx` принимает отдельный prop `displayFrequency`, чтобы pill отражал actual frequency, при сохранении родительского `name`/`category` для H1/breadcrumbs.
3. `getViewModeContent()` в `cpiViewModeContent.jsx` обёрнут в `if (isPriceCategory)`. Не-CPI индикаторы падают в fallback `{ description: indicator.description, methodology: indicator.methodology }`.

**Правило legacy-реестра `viewModeFamilies.js` (исторический фикс 2026-05-22):** у каждого **не-`level`** mode (real sibling) задаём явный `frequency` ИЛИ `transform`. Виртуальные transforms (`mom`) сохраняют родительскую частоту — `frequency` опускаем. Инвариант покрыт тестом `viewModeFamilies.test.js::каждый не-level mode имеет frequency или transform`.

**Правило для новых mode-specific блоков в `cpiViewModeContent.jsx`:** если блок применим только к CPI-семейству (Index, Annual, Weekly, Quarterly, CPI-monthly, Inflation), его условие должно быть **внутри** `if (isPriceCategory)`. Для не-CPI индикаторов с теми же режимами (`wages-nominal?mode=annual`, `unemployment?mode=quarterly`) функция должна падать в fallback на `indicator.{description, methodology}` из БД.

### Calendar source coverage

Legacy `WeeklySpec` / `typical_day` builders в `calendar_seed.py` оставлены только для debug/tests старой плотности календаря. Public ingest идёт через `calendar_sources.official_calendar`: CBR official daily rules (`indcalendar`) для FX/RUONIA/gold; CBR official ICS (`indcalendar` / `vCalendar.ics`) для резервов, M0/M1/M2, кредитов/депозитов, ставок, ипотеки, внешнего сектора, долга; CBR official monetary-policy schedule (`cbr.ru/dkp/cal_mp/`) для заседаний и резюме по ключевой ставке; Rosstat/Minfin rule-events только по опубликованным правилам и versioned working calendar. После добора 2026-05-10 local source-bound coverage: 46/76 source codes, 1208 public events, `bad_public_rows=0`. Если источника/правила нет — событие не показывается, пока не будет донабрано через official parser/rule.

### Telegram-уведомления: env-precedence + флаг (двойной .env trap)

Уведомления о новых пользователях/обратной связи (`alerting.notify_new_user` / `notify_feedback`, call-sites в `api/auth.py::register` и `api/oauth.py::oauth_callback`, оба `await`-ятся до ответа) уходят **только** при `settings.telegram_realtime_alerts_enabled=true` И наличии `telegram_bot_token`+`telegram_chat_id`. Сам код-путь рабочий; молчание почти всегда — **конфиг**.

**Trap 1 — два `.env` и precedence.** Есть корневой `./.env` (docker-compose читает его для `${VAR}`-интерполяции в блоке `environment:`) и `backend/.env` (pydantic `env_file` ВНУТРИ контейнера). Для переменной, перечисленной в `environment:` с **непустым** дефолтом (`RUSTATS_TELEGRAM_REALTIME_ALERTS_ENABLED: ${...:-true}`), compose всегда инжектит непустое значение → оно **перекрывает** `backend/.env` (OS env > env_file в pydantic). Для переменной с **пустым** дефолтом (`${...:-}`) инжектится `""` → pydantic игнорирует → выигрывает `backend/.env`. Вывод: **realtime/digest-флаги меняй в корневом `./.env`**, не в `backend/.env` (там правка молча не применится). Проверка факта: `docker compose exec backend printenv RUSTATS_TELEGRAM_REALTIME_ALERTS_ENABLED`.

**Trap 2 — локалка должна зеркалить прод.** Если глушишь алерты на локалке (`realtime=false`) ради тестового шума — это рвёт паритет «локалка = прод» и выглядит как «уведомления сломаны»: на `localhost` регистрация молчит by design. Правильный паритет — `realtime=true` и на локалке, и на проде (оба `./.env`). Тестовый шум гасить не флагом, а дисциплиной (не гонять лишние E2E-регистрации) либо опциональным suppression по test-email-паттерну. Прод-факт на момент 2026-06-20: `realtime=true`, `digest=true` (дайджест 09:00 МСК), `chat_id=433221767`, токен задан, `debug=false`.

**Уточнение 2026-09-30:** правило «только создание» ниже историческое. Текущий email-login в `api/auth.py` вызывает `_notify_login_safe`; рабочее соглашение 2 сентября требует уведомлять повторные входы через `notify_login` и хранить сообщения в `telegram_outbox`. Для конкретного OAuth-пути проверять callback и outbox; здесь новая доставка не выполнялась.

**Trap 3 — что НЕ триггерит пинг.** Уведомление шлётся только на **создание нового** пользователя (`created=True`); повторный вход существующим аккаунтом — тишина. И `sendMessage` доставит, только если получатель раньше нажал Start у бота (иначе HTTP 403 «can't initiate conversation»). Быстрый E2E канала: `curl -s "https://api.telegram.org/bot<token>/sendMessage" -d chat_id=<id> -d text=ping` → ждём `{"ok":true}`. Узнать реальный `chat_id` получателя: `getUpdates` после его `/start`.

**Уточнение 2026-10-04 (повтор и досылка).** `send_telegram` и `telegram_bot._api` повторяют отправку при сетевых сбоях/429/5xx (до 3 попыток, потолок 45 с; 400/403/404 — нет), а `telegram_resend_job` (scheduler, каждые 5 мин) досылает недоставленные важные виды из `telegram_outbox` и закрывает `pending` старше часа итоговым статусом. Состав и ограничения — [backlog](docs/backlog.md#telegram-resend-2026-10-04). Сообщение, не дошедшее из-за IPv6/ConnectTimeout, больше не теряется молча; смотреть причину — `telegram_outbox.error`.

**Trap 4 — прод не достаёт Telegram по IPv6 (главная причина «с сайта не шлётся»).** На прод-сервере `api.telegram.org` резолвится **только в IPv6**, а IPv6-маршрут до Telegram у хостера мёртвый → `httpx.ConnectTimeout` (15s), который глушится в `_notify_*_safe`/`send_telegram` (warning в логах). Симптом: тест из dev-окружения приходит, а **с прода и дайджест — нет**. Диагностика: `docker compose exec backend python -c "import socket; socket.create_connection(('149.154.167.220',443),5)"` — рабочий IPv4 Telegram DC. Фикс — `extra_hosts: api.telegram.org:${TELEGRAM_API_IP:-149.154.167.220}` у backend в `docker-compose.yml` (пишет `/etc/hosts` контейнера на уровне C-резолвера; Python-monkeypatch `socket.getaddrinfo` НЕ помогает — httpx/anyio резолвит мимо него). Проверка из контейнера: `docker compose exec backend curl --resolve api.telegram.org:443:149.154.167.220 -s ".../getMe"` → `{"ok":true}`.

### View-mode `shadowed_legacy` ≠ мёртвый код (расследование 2026-06-24)

**Уточнение 2026-09-30:** серверный `legacy_redirects.py` и `seo_pages.py` теперь также отдают canonical 301 до рендера. «ТОЛЬКО на легаси» в следующем историческом пункте описывает старый SPA-механизм. Проверять нужно серверный и клиентский путь; bespoke content по-прежнему может иметь consumers. См. датированную сверку в `docs/architecture-history.md`.

Карта (`docs/indicator-index.json`) ставит `shadowed_legacy` / `in_both_viewmode_systems` для кодов, чья **standalone-ветка рендера** в `IndicatorDetail.jsx` перекрыта generic-движком (early-return `getViewModeFamily` ПЕРВЫМ). Флаг ловит только shadowing рендера и **НЕ доказывает**, что легаси-файл можно удалить. Подтверждено на cbr-term / unemployment / trade двумя независимыми причинами:

- **Живые canonical-редиректы старых URL.** Старые derived-коды `trade-balance-yoy-abs`, `current-account-yoy-abs`, `unemployment-quarterly`, `unemployment-annual` **отсутствуют** в `viewModelFamilies.generated.json` → их редирект на родительскую карточку держится ТОЛЬКО на легаси `viewModeCanonicalTarget` / `unemploymentCanonicalTarget` (каскад в `IndicatorDetail.jsx`). Эти URL в sitemap и **индексируются** — удаление редиректа = тихий 404 со старых ссылок и просадка SEO, чего `check-all`/тесты НЕ ловят.
- **bespoke content переиспользуется живыми секциями.** `cbrTermSliceRate*` / `unemploymentViewMode*` импортируются в `IndicatorChartSection`, `IndicatorDataTableSection`, `cpiViewModeContent`, `useIndicatorViewModeData`, picker-groups — заголовки графика/таблицы и резолв режимов живут через общие секции, а не только через standalone-ветку.

**Mitigation:** перед удалением любого view-mode-легаси — (1) `grep` по `viewModelFamilies.generated.json`: покрывает ли движок старый URL; (2) проверить импорты экспортов по `frontend/src`. Если редирект живой — сперва вынести его в явную redirect-карту, и только потом чистить рендер. `docs/dead-code-report.md` переписан под это (список на расследование, НЕ delete-list). Сама консолидация старых `*-yoy-abs` URL в движок — backlog A3 (требует продуктового решения по 301-карте).

### nginx `map` с capture-группой перетирает `$1` location-регекспов (2026-07-06)

`map $http_user_agent $ssr_limit_key { ~*(yandex|googlebot|…) ""; }` для SSR rate-limit (П-22): nginx вычисляет map лениво — в момент обращения к переменной внутри location. Если regex map'а содержит **capture-группу**, её совпадение перезаписывает нумерованные `$1/$2` регекспа location → `proxy_pass http://backend:8000/seo/indicator/$1` уходил на `/seo/indicator/Yandex` и боты получали 404 на всех SSR-страницах (симптом виден ТОЛЬКО под бот-UA; человеческий curl-смоук проходит). Фикс двойной: в map — только non-capturing `(?:…)`, а все SSR-локации переведены на **именованные капчеры** `(?<ind_code>…)` — им чужие числовые группы не страшны.

**Правило:** в nginx-конфиге этого проекта числовые `$1/$2` в proxy_pass запрещены, если в запросе участвует любая map-переменная с regex; смоук новых SSR-правил гонять и обычным UA, и `-A "Mozilla/5.0 (compatible; YandexBot/3.0)"`.

### LLM-egress trap: ручной kill внешнего OpenRouter-релея без автоперезапуска (2026-08-27)

`pulse_report._llm_summary` ходит в OpenRouter **только** через `RUSTATS_OPENROUTER_PROXY_URL`, без цепочки `ProxyFallbackSession` (та — только у ETL). Внешний HTTP-релей tinyproxy на не-РФ хосте (`5.129.210.89:8888`, Amsterdam, egress через Cloudflare WARP) молча умер 2026-08-22 12:43 UTC: живая root-SSH-сессия сделала `kill -9` процесса через 3 минуты после его рестарта (судя по журналу — ручная работа на хосте), а `Restart=` у юнита настроено не было. Симптом — ежедневный «Пульс» шесть дней подряд уходил в детерминированный фолбэк «LLM-аналитик недоступен»: сообщение исправно доставлялось и job рапортовал success, никто не заметил. Диагностическая ловушка того же инцидента: TCP-соединение до 8888 «успешно» принимается SYN-proxy защитой хостера даже на мёртвом порту — проверять надо CONNECT/POST, не tcp-ping.

Прямой доступ с прода к openrouter.ai закрыт гео-WAF («Access denied by security policy», HTTP 403). Хост-Tor (`127.0.0.1:9050`) до OpenRouter с прода работает (200 за ~5 c).

**Фикс 2026-08-27:** tinyproxy на релей-хосте перезапущен, юниту добавлен drop-in `Restart=always` (+10 s); `RUSTATS_OPENROUTER_PROXY_URL` возвращён на `http://pulse_relay:…@5.129.210.89:8888`. Как горячий резерв на самом проде остаётся локальный мост `/opt/tor-http-bridge/tor_http_bridge.py` (`tor-http-bridge.service`, systemd): asyncio HTTP CONNECT-proxy с той же Basic-авторизацией → host-Tor SOCKS5, слушает только `172.18.0.1:8888` (docker gateway, наружу недоступен) — переключение одной строкой `.env`.

**Правило:** фактическое состояние egress-цепочки проверять сквозным POST с реальным ключом из контейнера backend (или ручным запуском `pulse_report_job`), а не tcp-ping'ом порта — SYN-proxy маскирует мёртвый сервис. Не полагаться на одиночный тест Tor-пути: первая цепочка бывает медленнее таймаута 75–90 c → единичный `ConnectTimeout` штатен, повторный прогон проходит. Кандидат в backlog: алерт «N дней подряд LLM-fallback» — иначе сбой виден только глазами.

### DHCP-lease trap: хост теряет публичный IP через сутки после сорванного продления (2026-09-29)

Прод получает `201.51.11.170` по DHCP от хостера (`LIFETIME=1d`, T1=12h). 2026-09-28 02:09:41 UTC хост был в давке (commit 104%, своп, iowait 20–35%, healthcheck'и docker по таймауту; `%steal` 0,1–0,2% — гипервизор ни при чём): `systemd-networkd` не дождался netlink при продлении — `eth0: Could not set DHCPv4 address: Connection timed out` → `eth0: Failed`. В состоянии Failed networkd больше не продлевает аренду, адрес живёт остаток lifetime. Ровно через сутки, 2026-09-29 02:09 UTC, ядро сняло адрес: сайт, SSH, исходящий DNS/ACME/Telegram встали на ~4,7 ч, контейнеры и БД при этом работали. Диагностическая ловушка: TCP к 22/443 «принимается» SYN-proxy хостера, SSH падает на баннере — похоже на зависание, а это отсутствие IP. Утренний ETL 06:00 МСК шёл без сети и оборвался ребутом — после восстановления прогонять вручную.

**Фикс 2026-09-29 (на хосте, не в репо):** `/etc/netplan/60-eth0-keep-lease.yaml` — `critical: true` для eth0 → `KeepConfiguration=true`, адрес `valid_lft forever`. Первопричина ночной давки не доказана. Вклад известен: с 2026-09-26 headless-ферма Alibaba Cloud Singapore (AS45102, ~1k IP по ~23 запроса — ниже порогов fail2ban; Метрика видит `headlesschrome`, ~15–17 тыс. «прямых» визитов в сутки, 0 с, отказы 99%; обход страниц штатов США по алфавиту, вкладки часами опрашивают `/api/v1/ticker/live`) закрыта по сетям в `frontend/nginx.conf::$deny_scraper_net` (403, кроме robots.txt; по IP, не по UA). Внутренние алерты при потере сети не уходят — нужен внешний uptime-монитор.

**Правило:** после ребута/переустановки хоста проверять `ip -4 addr show eth0` → `valid_lft forever`; сигнатуру `eth0: Failed` в `journalctl -u systemd-networkd` считать инцидентом с таймером на сутки.

### Scheduler memory-starvation trap: «Timeout reading from redis-state» — не Redis (2026-09-29)

Десятки алертов `telegram_poll` / `indexnow_drain` «Timeout reading from redis-state:6379», параллельно BrokenPipe/statement timeout Postgres и пустые сбои MOEX/Telegram в той же секунде. Redis здоров (slowlog ≤ 25 мс). Причина — процесс `scheduler` замирает: cgroup 1 ГиБ достигнут 17 050 раз за 2 ч после старта (`memory.events: max`), своп, `memory.pressure full` ~15%, в логе дыра ~70 с. Все ожидания I/O внутри event loop одновременно истекают. Источники памяти и блокировок: (1) `clickhouse_sync` каждые 15 мин грузил ~130k ORM-объектов (сессии + визиты Метрики за 2 суток, раздутые бот-фермой) и вызывал синхронный `ch.insert` прямо в event loop; (2) ночной `rollups_daily` (60 дней) грузил ~255k портретов ORM + ~845k событий и строил список всех сессий — ни разу не завершился (в `server_sessions` нет строк старше 3 дней с ночным `computed_at`). Своп scheduler давал iowait хоста — та же «давка», при которой сорвалось продление DHCP.

**Фикс:** синк CH — колонки вместо ORM, потоковые пачки по 5k, `ch.insert` в thread executor; `sessionize(since, until)` + ночной пересчёт окнами по 3 МСК-дня; портреты — только нужные поля; «известные посетители» — только из окна; визиты Метрики — только нужные ключи `raw_json` потоком. Антиспам алертов планировщика: одна ошибка джобы — не чаще раза в час (in-process, без Redis).

**Правило:** синхронный сетевой клиент (clickhouse_connect, requests, openpyxl-разбор) из корутины — только через `run_in_executor`/`to_thread`. Пакетное чтение аналитики — выборка колонок + `db.stream(...yield_per)`, не `select(Model).scalars().all()`. При «таймаутах Redis» сначала смотреть `memory.events`/`memory.pressure` cgroup scheduler и дыры в его логе.

### Scheduler event-loop block: синхронный fetch Росстата съел утренние отчёты (2026-10-07)

07.10.2026 утренние Telegram-дайджест (09:00) и Пульс (09:05) не пришли. В 08:38–10:05 МСК `RosstatIndParser` (`capital-investment`, затем `construction-work`) качал `ind_MM-YYYY.xlsx`, rosstat.gov.ru не отвечал: 6 кандидатов × (ретраи по 90 с + fallback через socks5h) ≈ час на индикатор. Вызов `requests` шёл прямо в `async _fetch_and_parse` — весь `AsyncIOScheduler` стоял. В 10:05 обе задачи ушли в misfire (допуск 3600 с; Пульс опоздал на 3629 с), за ними посыпались таймауты Redis/Postgres у остальных job — следствие той же остановки, не отказ хранилищ.

**Фикс (2026-10-08):** сетевой fetch и разбор в `rosstat_ind/demo/science/fixedassets` — через `asyncio.to_thread`; страж `backend/tests/test_parser_fetch_off_event_loop.py` (AST: в `async _fetch_and_parse` нет прямых `create_session`/`resolve_mediabank_file`/`_fetch_*`/`session.get`). `misfire_grace_time` 6 ч для `telegram_daily_digest` и `pulse_report` (`main.py::DAILY_REPORT_MISFIRE_GRACE_S`); снапшот Пульса 23:57 оставлен на часе — после полуночи `date.today()` указывал бы на следующий день.

**Фикс 2, `http_client` (2026-10-08):** час на индикатор давал сам клиент. `timeout=90` у requests действует и на connect; urllib3 `Retry(total=3)` повторял connect 4 раза, затем то же через SOCKS, × 6 файлов-кандидатов `ind`. Теперь connect ограничен 15 с напрямую / 30 с через прокси (read — от вызывающего), `Retry(connect=1)`, а хост, не принявший соединение ни по одному хопу, 20 мин отвечает мгновенной `ConnectionError` без сети (`HOST_BREAKER_COOLDOWN_S`, в пределах процесса; read timeout, HTTP-статусы и `SSLError` предохранитель не взводят). Попутно: `_TimeoutAdapter` делал `setdefault("timeout")`, но requests всегда передаёт `timeout=None` — default timeout не применялся никогда. Внешнее свидетельство сбоя самого Росстата 07.10 — жалобы «не загружается сайт» с 06:24 на detector404; окна недоступности по `fetch_log` (UTC): 06.10 ~17:00–18:45, 07.10 ~03:00–11:30.

**Tor-fallback не работает (наблюдение 2026-10-08):** `ExitNodes {ru},{by},{kz}` + `StrictNodes 1`, в журнале host-Tor один выход (`eden`) с «We tried for 15 seconds to connect»; свежие временные экземпляры Tor (RU/BY/KZ и без ограничения выходов) не проходят bootstrap — сеть Tor с хоста недоступна. Минфин явно банит прод-IP (страница «Доступ к сайту временно ограничен владельцем веб-ресурса»); последняя живая загрузка `minfin_budget_csv` — 2026-08-19, дальше снимок из репозитория (обновлён 2026-10-08, ряды `budget-*` по август 2026). В консенсусе Tor остался один RU-выход — обход через Tor исчерпан; свежий CSV доставляет с Mac владельца `scripts/minfin-sync-from-mac.sh` по launchd. Подробно — `data_sources.md` (Минфин, состояние 2026-10-08).

**Правило:** см. предыдущий раздел — синхронный сетевой клиент из корутины только через `to_thread`. Признак в логе: одна-две строки в 1,5 мин (`urllib3 Retrying … ConnectTimeout`) и тишина остальных job, затем лавина «Execution of job … skipped/missed».

### Sitemap-index lastmod trap: исправленный шард Яндекс не перечитывает (2026-09-29)

Ошибки Вебмастера по sitemap (до 91k на хост) — `<lastmod>` раньше 1970 у годовых страниц 1929–1969 (справочник Яндекса: «неверная дата»). Код исправлен 2026-09-26 (`SITEMAP_LASTMOD_MIN`), но `lastmod` шарда в индексе считался как max(lastmod URL) — у исторических шардов он не сдвинулся, и робот не перечитывал исправленные файлы. API v4 отдаёт только `errors_count`, тип ошибки виден лишь в интерфейсе.

**Фикс:** `lastmod` файла в индексе = max(дата данных, дата смены содержимого по отпечатку шарда); история — `section_changed` в `sitemap-stats.json`. Первая сборка после выката помечает все шарды изменёнными один раз. Алерт «ошибок sitemap» — только при росте счётчика.

**Правило:** любое изменение разметки/дат в шардах должно менять отпечаток (`section_fingerprint` берёт lastmod после нормализации) — тогда дата смены в индексе сдвинется сама.

---

## Architectural language (from improve-codebase-architecture skill)

- **Module** — anything with an interface and an implementation (function, class, package).
- **Interface** — everything a caller must know: types, invariants, error modes, ordering, config. Not just signature.
- **Implementation** — code inside.
- **Depth** — leverage at the interface: many behaviours behind a small interface.
- **Shallow** — interface complexity ≈ implementation complexity (e.g. wrapper function that just binds two args).
- **Seam** — where an interface lives; place to alter behaviour without editing in place.
- **Adapter** — concrete thing satisfying an interface at a seam.
- **Leverage** — what callers gain from depth.
- **Locality** — what maintainers gain from depth: change concentrated in one place.
- **Deletion test** — imagine deleting the module. If complexity vanishes, it was a pass-through. If complexity reappears across N callers, it was earning its keep.

When suggesting refactors, use this language. Use the **Indicator/DataPoint/Derived/Forecast/Parser/Strategy** vocabulary above for the domain.


## Liquid-glass presentation contract (2026-09-24)

Shared brand tokens and Manrope connect the SPA, pure SSR fast pages and PNG
renderers. Economic values, labels and source provenance remain deterministic
data, while the 17 generated thematic artworks are decoration. See
`docs/design/README.md` for implementation, reproducible gallery and acceptance.
Fast-page clickable sources stay inside ForecastEconomy; JSON-LD preserves
official source URLs. Historical pages preserve the requested period. World
ratings use `?view=interactive&year=YYYY#chart` to enter the SPA without cycling
through the legacy `?year` redirect; canonical stays on the year path (or base
for the default year). PNG font drawing normalizes Unicode space separators
for both measurement and painting. Cached images/SSR use design version 6.
Local preview is compose :3000. RU/EN preview does not change the live host
cutover flag. No local test or sitemap submission proves index inclusion.

### Хрусталь без границ и платформенные контракты раундов 2–4 (локально 2026-10-05, не выпущено)

**Принципы владельца 06.10.2026 приоритетнее описанного ниже** ([design-system](docs/design-system.md#принципы-владельца-приоритет-выше-всех-остальных): люксовый взрослый дизайн без «игровых» элементов, сдержанная палитра с тонким золотом, фон не пустой, без рамок, в прогнозах никогда диапазон, картинки без пикселя); процесс работы с агентами — [agent-orchestration](docs/agent-orchestration.md).

**Статус палитры 24.09.** Жемчужная палитра и золотая кромка панели заменены: действует [дизайн-система «хрусталь без границ»](docs/design-system.md)
([ADR-0018](docs/adr/0018-crystal-without-borders-design-system.md)): слои стекла L0–L3, **рамок нет** (список исключений закрыт и проверяется
`frontend/src/styles/no-borders.test.js`), бюджет блюра 12 слоёв на компьютере и 6 на телефоне, сцена света `LightScene`, растровые бренд-кадры `public/brand/*` (сгенерированы моделью через
OpenRouter, ключ в репозитории не хранится). От 24.09 действуют Manrope, логотип F, серверные PNG и принцип «подписи рисуются из данных».
**Палитра с круга 6 (06.10.2026) холодная:** фон `#F4F5F7` (вместо тёплой бумаги `#F6F2EA`), основа — графит `#1E2638`/`#2A3550` и глубокий синий `#1E3A6E`/`#2C4A8A`, **золото только тонким акцентом** (линия, точка, линия прогноза) и **единственной золотой заливкой — CTA регистрации**; «игровые» элементы (бусины, самоцветы, медали, камни, глянцевые капсулы, свечения) сняты, всё плоское. Токены с «gold»/«champagne»/«sapphire» в имени (`--fe-gold-soft`, `--color-champagne-ink`, `CHART_THEME.gold*`) сохранили имена, но по значению синие или графитовые. График: **факт — холодная синяя лента, прогноз — тонкое золото** (`lib/chartTheme.js`: новые `forecast`, `forecastInk`). `theme-color`, манифест PWA, серверная заставка и статические 404/429/50x переведены на `#F4F5F7`; быстрые SSR-страницы (`body.seo-fast` в `seo_renderer.SEO_CRITICAL_CSS`; фон `html` уже `#F4F5F7`), серверные PNG и сравнение `/compare` остались в прежних цветах (список — [design-system, раздел 15](docs/design-system.md#15-неизвестное-и-пределы-на-2026-10-06)). Растры допускаются только в разрешении не ниже 2× от показа (`public/brand/manifest.json`, стражи `no-lowres.test.js` и `scripts/dev/check-raster-dpr.py`). Ничего из этого не измерялось на экране исполнителями и не выпущено.

**Новые контракты этих раундов** (подробности — [data-contracts](docs/data-contracts.md), [architecture](docs/architecture.md)):
- **Страница «Прогнозы» `/forecasts`** (платформенная страница наравне с `/compare`, `/calculator`; ADR-0003/0013, `site_paths.forecasts()`, зарезервированный первый сегмент) и API `GET /api/v1/forecasts/showcase`:
  только ряды, которые платформа прогнозирует сама (Россия: инфляция за 12 месяцев, реальный ВВП, безработица, ипотека, зарплата; мир: цены, безработица, реальный ВВП до 4 стран на тему, прошедшие проверку на истории).
  **Проекции МВФ не хранятся и не пересказываются**; горизонт «через год» (9–15 месяцев между последним фактом и концом прогноза), пустая витрина честно пишет «появятся здесь».
- **Лента курсов и основа курса.** Каждый снимок `/api/v1/ticker/live` несёт `source_kind` (`market | central_bank | ecb | official`), `source_label` («Биржа», «ЦБ», «ЕЦБ» по языку хоста), `as_of`, ответ — `lane`, `Vary: Host, X-FE-Locale` (с `204af55a` все ответы `/api/` несут `Vary: X-FE-Locale`, [контракт](docs/data-contracts.md#api-vary-locale));
  новый `GET /api/v1/ticker/rates/{usd-rub|eur-rub|cny-rub}` отдаёт два числа с честными подписями (`central_bank` — курс ЦБ на дату, `market` — биржа или `null`); если биржа недоступна и воркер подставил ЦБ, он больше не выдаётся как рынок. **Клиент этих полей и `/ticker/rates` пока не использует** (`LiveTicker` определяет «биржа»/«ЦБ» по `snapshot.source`).
- **Страница страны: «Главное» в серверном HTML и предзагрузке.** SSR добавляет секцию `#key-figures` («Главное», до четырёх строк человеческим текстом) и в `<head>` `<script type="application/json" id="fe-country-bootstrap">` (`v:1`, страна, `overview` с точками мини-графика).
  Клиент (`lib/countryBootstrap.js`) использует предзагрузку, пока дата и значение совпадают с каталогом, иначе идёт в сеть. Источник — Redis-каталог страны `world / country:v18:{slug}:{locale}`; кэш HTML `ssr-world` 6 ч.
- **404 в общей оболочке.** Неизвестный адрес получает от backend документ приложения со статусом 404 и флагом `window.__feNotFound=true`; клиент (`ServerNotFoundGate` в `App.jsx`) на этом pathname рисует `NotFound`, а не маршруты. Без бандла остаётся прежняя самодостаточная страница.
  nginx отдаёт фирменные статические `429.html/.json` и `50x.html/.json` (JSON для `/api/`); `/search?q=…` — 301 на главную с тем же `q`.
- **Лимиты API.** `RateLimitMiddleware` читает `RUSTATS_API_RATE_LIMIT` (по умолчанию 120 запросов в минуту на адрес) и `RUSTATS_EMBED_RATE_LIMIT` (600) из окружения; боевые значения прежние. Тестовый стенд поднимает оба до 6000 и генерирует свой nginx-конфиг
  (лимиты ×100/×10, `limit_conn perip` 8000): все проверяющие приходят с одного адреса — [workflow, «Тестовый сервер»](docs/workflow.md).
- **Поиск.** `headline` (годовая инфляция) и `simple_name` (понятное имя ряда) в ответах API (клиент их пока не читает); правила одной буквы и приоритета годовой инфляции; клиент ⌘K — группы «Ещё: …», строка «Открываем: …» — [search](docs/search.md).

**Ловушки.** (1) Имя `.fe-sheet` занято шторкой тем в `w6f-pages.css` (`position: fixed`); общая шторка называется `.fe-bsheet`. (2) `backdrop-filter` на предке делает его контейнером для `position: fixed`: шторки и диалоги выносятся порталом в `body`.
(3) Горизонтальный градиент ленты графика строится в координатах графика (`userSpaceOnUse`), иначе плоский ряд исчезает. (4) Страница страны больше не «пустая до ответа API»: скелет рисует реальные карточки из предзагрузки; при расхождении снимка и каталога клиент всегда идёт в сеть.
(5) Имя `og-image-v3.png` зашито в `seo_content.OG_IMAGE`: соцсети кэшируют картинку по URL, смена содержимого без смены имени не обновит превью.


### Уточнение поиска 01.10: единицы, срезы и годовой режим

Намерение различает процент/процентный пункт, меру/частоту наблюдений и
конкретные структурированные оси Eurostat. Их доказательство — реальные
native unit, provider и slice_json; другая ось TOTAL или SEO не заменяют
нужный член. Целое каталожное имя защищает внутренние даты/географию/%;
внешние уточнения сохраняются. Это конечный разбор, без обученной ML-модели.
Контракты, нормативные источники и границы — [поиск](docs/search.md).

Годовой режим России разрешается shared resolver в точный materialized code,
читает его конечные факты и сохраняет mode в standalone canonical, locale,
графике и соседних годах. Такие canonical задуманы входящими в sitemap (**с 2026-10-04 публикация отложена**, реестр и robots как на сервере); обычная карточка
по-прежнему убирает mode. World year-mode и derived monthly document остаются
неподдержанными. Основание — [ADR-0003](docs/adr/0003-seo-single-source-server-rendered.md).

### Уточнение V5 01.10: частота источника, база цен и полный native witness

Source/output frequency и observation/base year — независимые роли.
Registered source mode и terminal pipeline определяют source/end-of-period
identity; world observation frequency её не выдумывает. Monetary valuation
доказывается одним полным title/code либо одной полной native unit подписью,
без соединения частичных полей/переводов. Price subject у commodity family
требует фактической денежной единицы на физическое количество. Новые exact
named Eurostat members и axis-specific totals требуют строкового member JSON;
TOTAL другой оси не заменяет intent. [Контракты](docs/data-contracts.md#уточнение-v5-0110-независимые-роли-и-нативные-свидетельства)
и [измерения](docs/research/search-history-replay-2026-09-30.md) сохраняют
отрицательные blind результаты; повтор после разбора является development.
