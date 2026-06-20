# AGENTS.md — точка входа для AI-агента

**Last updated:** 2026-05-22 (документация-ревизия: `cbr_sources.md` мигрирован в docstrings парсеров и удалён; `plan.md`/`recap.md` мигрированы и удалены; синхронизированы дубли записей про ADR-0004/0005; чеклист «новый индикатор» = 7 пунктов; `_catch_up_empty_indicators` упомянут в Шаге 4).

Этот файл — первое, что читает любой новый AI-агент (Cursor, Claude Code, Codex, Gemini, любой другой), подключённый к этому репозиторию. Здесь живёт **карта документации**, **режим работы** и **протокол актуализации** этих самых документов.

Задача проекта в одну строку: публичная аналитическая платформа `forecasteconomy.com` — собирает 100+ экономических индикаторов России (Росстат, ЦБ РФ, Минфин), считает derived-ряды и forecast'ы, отдаёт фронтенду + ботам + embed-виджетам.

---

## Шаг 1 — что прочесть в первую очередь

В этом порядке (5–10 минут):

1. **[`CONTEXT.md`](CONTEXT.md)** — domain glossary и архитектурный язык. **Spine**, без неё нельзя обсуждать архитектуру. Читать целиком — он сжатый.
2. **[`README.md`](README.md)** — карта стека, ключевые группы endpoint'ов, индикаторы, deploy. Высокоуровневый обзор.
3. **[`docs/data_sources.md`](docs/data_sources.md)** — точная карта «индикатор → файл/endpoint» (75 source-индикаторов). Канонический справочник, откуда тянется каждый ряд. Parser internals — в docstrings соответствующего `backend/app/services/*_parser.py`.
4. **[`docs/workflow.md`](docs/workflow.md)** — модель работы, локальный dev, ручной ETL recipe, прод-деплой, smoke C.
5. **[`docs/enterprise_resilience.md`](docs/enterprise_resilience.md)** — операционные инварианты, чеклист канарейки 6/6 (другой от чеклиста «новый индикатор» 7/7 ниже).
6. **`docs/adr/`** — архитектурные решения (нумерованные ADR, читать в порядке номеров):
   - `0001-derived-indicators-engine-shape.md` — engine shape derived (29 specs + 10 pure ops + 2 client-side transforms).
   - `0002-derived-always-reflects-source.md` — инвариант идемпотентности `bulk_upsert`.
   - `0003-seo-single-source-server-rendered.md` — SSR через backend, asset discovery от Vite shell.
   - `0004-rosstat-russian-canonical-sdds-deprecated.md` — Rosstat русский canonical, SDDS English deprecated. Migration pattern + pilot evidence (gdp-nominal, 2026-05-10).
   - `0005-official-calendar-source-bound.md` — public calendar только official dates с provenance; estimated скрыты.
   - `0006-indicator-card-unification.md` — ось декомпозиции «карточка vs derived vs variant vs frequency» + 7-проверочный чеклист «новый индикатор» (звонок 2026-05-22 + ревизия).
 - `0007-identity-user-accounts.md` — личный кабинет Phase 1: идентичность (User/OAuthIdentity/EmailCredential), сессии в Redis, OAuth (Яндекс/VK/email, без Authlib), резолв против pre-hijack, 152-ФЗ. Alembic-ревизия `20260619_identity`. Boevые OAuth-креды — pre-prod чеклист в ADR.

После этих файлов агент способен ответить на ~90% вопросов и делать осмысленные правки.

---

## Шаг 2 — где искать конкретное

| Вопрос | Файл/папка |
|--------|------------|
| Как работает парсер X? | **docstring** `backend/app/services/<X>_parser.py` (canonical: source URL, лист, row/col mapping, `model_config_json` schema, traps) + `CONTEXT.md::Parser` (template-method обзор `BaseParser`) |
| Откуда берётся индикатор X? | **[`docs/data_sources.md`](docs/data_sources.md)** — точный URL/файл/endpoint по каждому из 75 source |
| Какие источники, кроме Росстата? | [`docs/data_sources.md`](docs/data_sources.md) (полная карта для всех 75 sources, включая CBR + Минфин) + docstrings парсеров `backend/app/services/{cbr_*,minfin_*}_parser.py` |
| Как считается derived-индикатор Y? | `DERIVED_SPECS` в `backend/app/services/calculation_engine.py` + ADR-0001 |
| Какая стратегия forecast у индикатора Z? | `Indicator.model_config_json.forecast_strategy` в БД + реестр `backend/app/services/forecast_strategies/registry.py` + таблица в `CONTEXT.md::Forecast` |
| Как собирается SEO/мета? | `backend/app/services/seo_renderer.py` + `seo_content.py` + ADR-0003 |
| Какие endpoints есть в API? | Swagger `/api/docs` (только при `DEBUG=true`, на проде отключён) + краткая сводка групп в `README.md::API` |
| Yandex Metrika / Webmaster | [`docs/analytics_api_inventory/`](docs/analytics_api_inventory/) — каждый файл начинается со status block (`partial` / `implemented` / `planned`) |
| Что менять при правке UI? | `frontend/src/...` + `docs/workflow.md::Браузерная проверка` (cursor-ide-browser + headless E2E) |
| Какие traps подстерегают? | Раздел «Operational invariants and traps» в `CONTEXT.md` (12 пунктов) |
| Что мы НЕ извлекаем из источников? | [`docs/missed_data_audit.md`](docs/missed_data_audit.md) — TOP-25 P0-индикаторов, доступных без новых источников |
| Какие правки в работе прямо сейчас? | [`docs/backlog.md`](docs/backlog.md) — живой бэклог: ID/затронутые файлы/риски/приоритет. Источник — звонки с Никитой |
| Как довести **семейство** индикаторов (не один код)? | **[`docs/indicator-family-playbook.md`](docs/indicator-family-playbook.md)** — продуктовая модель + фазы A–G; эталоны **ИПЦ** (макс.) и **жильё** (variant + custom view-mode); ADR-0006 + `AGENTS.md::Шаг 4` для отдельных кодов |
| Как делать прод-деплой? | `docs/workflow.md::Прод-деплой` + `enterprise_resilience.md` |

---

## Шаг 3 — режим работы

**Запреты (всегда):**
- **Не пушить на прод-сервер** (`5.129.204.194`, `/opt/rosstat`) без явной команды пользователя.
- **Не пушить на `main`** без зелёного `./scripts/check-all.sh` (pytest + lint + vitest + vite build).
- **Не редактировать `git config`**, не делать `--force` push, не амендить коммиты, которые уже на remote.
- **Не создавать новые .md файлы**, если можно обновить существующий. Документация консолидирована — фрактальная сеть выстроена; новые файлы только если возникает действительно новая категория знания.
- **Не мерджить «полу-готовое»** в `main`. Регламент канарейки 6/6 в `enterprise_resilience.md` — обязателен.
- **Не выдавать «внутренности» в публичных текстах** (`methodology`, `description`, `seo_*`, `categories.js`, любые user-visible payloads). Имена файлов источников, parser-жаргон, API-id, ADR-ссылки, координаты Excel — всё это живёт в `docs/data_sources.md`, docstrings парсеров и `CONTEXT.md`, а не на сайте. Полное правило — [`.cursor/rules/methodology-language.mdc`](.cursor/rules/methodology-language.mdc).

**Стандартная сессия:**
1. Понять, на каком уровне работаешь: оперативная правка (`fix/...`, `feat/...`) vs архитектурный кандидат (`refactor/...`, требует ADR).
2. Прочесть релевантные файлы из таблицы выше.
3. Сделать правку. Прогнать локальные проверки (`./scripts/check-all.sh`).
4. Если правка касается UI — обязательно браузер-snapshot через `cursor-ide-browser` (см. `docs/workflow.md::Браузерная проверка`).
5. Закоммитить **только** по явной команде пользователя.

**Доступные ресурсы:**
- `scripts/check-all.sh` — CI-эквивалент.
- `scripts/sync-local-from-prod.py` — read-only sync с прода.
- `scripts/rebuild-all-derived.py` — полный пересчёт derived (после правок `derived_ops.py` или `DERIVED_SPECS`).
- `scripts/seo-audit.py` — проверка SSR-meta на ключевых URL.
- `scripts/pg-backup.sh` — бэкап перед прод-деплоем.

---

## Шаг 4 — протокол актуализации документации (КРИТИЧНО)

**Документация — это код**. При архитектурных изменениях агент **обязан** актуализировать соответствующие файлы. Без этого фрактальная система деградирует, и следующий агент будет работать со stale-картой.

### Правила обновления

| Изменение в коде | Куда писать |
|------------------|-------------|
| **Любое изменение источника данных** (URL, имя файла, sheet, dataservice блок, file template) | **`docs/data_sources.md`** — single source of truth «индикатор → актуальный файл/endpoint» + **docstring** парсера `backend/app/services/<name>_parser.py` (parser-internals: source URL, layout, schema конфигурации, traps). ОБЯЗАТЕЛЬНО при любой правке парсера или `model_config_json` |
| Новый source-парсер (Rosstat/CBR/Минфин/иной) | `docs/data_sources.md` (per-indicator маппинг) + docstring парсера в `backend/app/services/<name>_parser.py` (canonical parser-internals) + регистрация в `PARSER_REGISTRY` + строка в `seed_data.py`. `CONTEXT.md::Parser` обновлять только если меняется обзорное число парсеров. |
| Новый derived-индикатор | `DERIVED_SPECS` в `calculation_engine.py` + `seed_data.py` + раздел в `CONTEXT.md::Derived indicator` (счётчики и категории) |
| Новая чистая op в `derived_ops.py` | ADR-0001 (раздел «Subsequent additions») + `CONTEXT.md::Derived indicator` (список ops) |
| Новая forecast-стратегия | `forecast_strategies/registry.py` + таблица в `CONTEXT.md::Forecast` + строка в `README.md::Прогнозы` |
| Новый API endpoint | Swagger (автоматически из FastAPI route); если новая группа endpoint'ов — обновить сводку в `README.md::API` |
| Новый категория или slug | `frontend/src/lib/categories.js` **и** `seo_content.py::CATEGORY_META` (синхронно — см. ADR-0003) + строка в `README.md::Индикаторы` |
| Изменение rate-limit / CORS / CSP | `enterprise_resilience.md::API и backend` + `enterprise_resilience.md::Frontend и кэш` |
| Новая операционная trap, обнаруженная в проде | `CONTEXT.md::Operational invariants and traps` (раздел traps) |
| Новое архитектурное решение | **Создать новый ADR** `docs/adr/<NNNN>-<kebab-name>.md` (следующий свободный номер); добавить ссылку в шапку `CONTEXT.md::Документы рядом` и в `AGENTS.md::Шаг 1` |
| Новый view-mode family / variant / virtual transform | `frontend/src/lib/viewModeFamilies.js` (реестр семей) **или** `lib/indicatorVariants.js` (variants). Тест в `viewModeFamilies.test.js`. ADR-0006 «Subsequent additions» если добавляется новый паттерн (не просто новый member существующего паттерна). Крупное семейство (несколько фаз) — чеклист в [`docs/indicator-family-playbook.md`](docs/indicator-family-playbook.md) |
| Изменение существующего ADR | Не редактировать body «как если бы решение было таким». Добавить раздел «Subsequent additions (after acceptance)» с датой и описанием. Status в шапке менять только при формальной депрекации |
| Новый Yandex API client | `docs/analytics_api_inventory/<service>.md` (если файл уже есть — обновить status block) или новый файл при новом сервисе + строка в `analytics_api_inventory/README.md::Implementation status` |
| Новая roadmap-задача / правка от пользователя | `docs/backlog.md` (приоритеты + ID + затронутые файлы + риски). Когда закрыто — переносим в раздел «История» с SHA коммита. Никаких параллельных `plan.md` — всё в одном backlog. |

### Когда создавать новый ADR vs обновлять старый

**Создавать новый ADR**, если:
- Меняется фундаментальный инвариант (например, переход с monorepo на микросервисы).
- Появляется новая ось декомпозиции, которой раньше не было (например, multi-tenancy).
- Решение **противоречит** существующему ADR (тогда новый ADR должен явно депрекать старый).

**Обновлять существующий ADR (раздел «Subsequent additions»)**, если:
- Эволюция в рамках принятого решения (например, добавили `december_to_december` op в систему derived — это эволюция ADR-0001, не новое решение).
- Уточнение границ инварианта (например, формулировка «pure-revision day limitation» в ADR-0002).
- Корректировка `Last verified` даты после ревизии.

### Чеклист «я закончил архитектурную правку»

Перед тем, как считать задачу завершённой:

- [ ] Код изменён, тесты добавлены/обновлены, `./scripts/check-all.sh` зелёный.
- [ ] Если правка меняет публичный интерфейс (API, парсер, derived-список, стратегия, операция): соответствующий .md обновлён по таблице выше.
- [ ] Если решение архитектурное: новый ADR создан или существующий дополнен.
- [ ] `Last updated` / `Last verified` дата обновлена в каждом изменённом .md.
- [ ] Cross-links целы: новые ADR упомянуты в `CONTEXT.md::Документы рядом` и в `AGENTS.md::Шаг 1`.
- [ ] Браузер-snapshot, если правка задела UI.

### Чеклист «новый индикатор» (КРИТИЧНО)

Перед добавлением **любого** нового индикатора (source-парсер, derived, manual seed) пройти все 7 проверок. Без них вероятен один из задокументированных trap'ов из `CONTEXT.md::Operational invariants and traps`. См. ADR-0006 «Indicator card unification».

| # | Проверка | Что делаем |
|---|----------|------------|
| 1 | **Source-depth invariant** | Какую максимальную глубину истории даёт источник? Если в seed_data залит **меньший** ряд — заводим `<name>_historical.py` immutable seed (как `housing_historical.py`, `refinancing_rate_historical.py`, `wages_historical.py`). НЕ оставляем огрызок. |
| 2 | **Frequency consistency** (КРИТИЧНО) | Перед `bulk_upsert` сверить `target.frequency` с фактической частотой добавляемых точек. Если расхождение (annual → monthly indicator) — заводим **отдельный sibling indicator** с правильной `frequency` и `is_listed=false`, добавляем режим в `viewModeFamilies`. См. trap `Annual-in-monthly mixing` в `CONTEXT.md`. |
| 2b | **Initial ETL trigger** | Закрыто автоматикой в `app/main.py::_catch_up_empty_indicators()` — при startup backend сам триггерит ETL для всех source-индикаторов с 0 точек. После deploy с новым indicator достаточно `docker compose up -d backend` — данные подтянутся в фоне. Если в логах `Startup catch-up: <code> failed: ...` — источник битый, чинить парсер. См. trap `New indicator initial ETL trap` в `CONTEXT.md`. |
| 3 | **View-mode family оценка** | Если ряд > 100 точек и есть осмысленные derived'ы (YoY/QoQ/MoM/aggregation) — заводим через `frontend/src/lib/viewModeFamilies.js::VIEW_MODE_FAMILIES`, **не** отдельную карточку в каталоге. Derived'ы скрываем через `INDICATOR_HIDDEN_FROM_LISTING`. |
| 4 | **Variant decomposition** | Если индикатор имеет варианты по срезу (срок, регион, подгруппа, тип) — это **разные индикаторы со своими рядами** → `VariantGroupPicker` (см. `lib/indicatorVariants.js`). Не путать с view-mode (один ряд, разные представления). |
| 5 | **Negative-capable check** | Если значения могут быть отрицательными (`trade-balance`, `current-account`, `budget-deficit`, `*-migration`) — использовать `yoy_abs` (разница в единицах источника), **не** `yoy_pct` (% от базы с переходом через ноль = визуальный мусор и тысячи процентов). |
| 6 | **Frequency strategy** | Daily-индикатор: aggregation (week/month/quarter/year avg) — `applyAggregateTransform` на фронте, **backend derived не заводим**. Monthly counterpart существующего quarterly — отдельный индикатор с MoM%-режимом через виртуальный `transform: 'mom'`. |
| 7 | **Listing visibility ≠ searchability** | Если индикатор скрыт из каталога (`is_listed=false` через `INDICATOR_HIDDEN_FROM_LISTING`) — он всё равно ищется через `?include_unlisted=true` в `IndicatorSearch.jsx`. Search haystack включает `seo_keywords` — в новом индикаторе всегда задаём osmysленные ключевые корни на русском (зарпл/инфля/безраб и т.п.). |
| 8 | **SEO-автоматика — ничего руками** | Sitemap (lastmod/priority), related-блоки, годовые landing'и `/indicator/{code}/{year}`, OG-превью `/og/{code}.png`, RSS `/feed.xml`, IndexNow-пинг — всё подтянет новый индикатор из БД само (ADR-0003 «Subsequent additions», `CONTEXT.md::SEO meta bundle`). Единственное ручное: curated `seo_keywords` + `seo_title`/`seo_description` в `app/data/indicator_seo.py` (иначе сработает generic fallback). При смене дизайн-токенов фронта — синхронизировать `SEO_CRITICAL_CSS` в `seo_renderer.py`. |

**После прохождения чеклиста** — обновить `seed_data.py` + соответствующие mappings (variant/view-mode), прогнать `./scripts/check-all.sh`, обновить `CONTEXT.md::Operational invariants and traps` если открыли новую trap.

---

## Шаг 5 — карта папок проекта

```
rosstat/
├── AGENTS.md                       ← вы здесь
├── CONTEXT.md                      ← spine: glossary + invariants
├── README.md                       ← high-level overview
├── docs/
│   ├── adr/                        ← architectural decisions (ADR-0001..0006)
│   ├── analytics_api_inventory/    ← Yandex API контракт + status (6 файлов)
│   ├── data_sources.md             ← single source of truth: индикатор → файл/endpoint (75 source)
│   ├── missed_data_audit.md        ← reference: ещё не извлечённые поля в source files (TOP-25 P0)
│   ├── backlog.md                  ← живой бэклог (приоритеты + roadmap + история)
│   ├── workflow.md                 ← процесс, dev, ручной ETL, deploy
│   └── enterprise_resilience.md    ← операционные инварианты + канарейка 6/6
├── backend/
│   ├── app/
│   │   ├── api/                    ← FastAPI routes (indicators, forecasts, calendar, embed, ticker, analytics, …)
│   │   ├── services/               ← parsers (24 типа), forecaster, calculation_engine, derived_ops, seo_renderer
│   │   │                           ←   parser internals в docstrings *_parser.py (canonical)
│   │   ├── tasks/                  ← APScheduler jobs
│   │   ├── analytics/              ← Yandex clients + warehouse
│   │   ├── models.py, config.py, main.py, database.py
│   │   └── data/indicator_seo.py   ← per-indicator SEO defaults
│   ├── alembic/                    ← миграции
│   ├── seed_data.py                ← idempotent seeder (100+ индикаторов)
│   └── tests/                      ← pytest, snapshot-тесты forecast'ов
├── frontend/
│   ├── src/
│   │   ├── components/, pages/, lib/
│   │   └── lib/categories.js       ← синхронно с seo_content.py::CATEGORY_META
│   └── nginx.conf                  ← SPA + SSR-proxy + asset hashing
├── scripts/                        ← CI, deploy, sync, audit, backup
├── mcp/forecast-analytics-mcp/     ← отдельный MCP-сервер
├── Caddyfile                       ← edge HTTPS + CSP
└── docker-compose.yml
```

---

## Финал

Если ты дочитал до сюда, ты знаешь, **где** живёт знание, **как** его читать, **как** его обновлять, и **что нельзя делать**.

Если что-то в этом файле или в любом другом .md устарело или противоречит коду — это твоя зона ответственности обновить. Не оставляй stale-доку для следующего агента: он на тебя положится.
