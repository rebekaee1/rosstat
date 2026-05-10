# AGENTS.md — точка входа для AI-агента

**Last updated:** 2026-05-10.

Этот файл — первое, что читает любой новый AI-агент (Cursor, Claude Code, Codex, Gemini, любой другой), подключённый к этому репозиторию. Здесь живёт **карта документации**, **режим работы** и **протокол актуализации** этих самых документов.

Задача проекта в одну строку: публичная аналитическая платформа `forecasteconomy.com` — собирает 104 экономических индикатора России (Росстат, ЦБ РФ, Минфин), считает derived-ряды и forecast'ы, отдаёт фронтенду + ботам + embed-виджетам.

---

## Шаг 1 — что прочесть в первую очередь

В этом порядке (5–10 минут):

1. **[`CONTEXT.md`](CONTEXT.md)** — domain glossary и архитектурный язык. **Spine**, без неё нельзя обсуждать архитектуру. Читать целиком — он сжатый.
2. **[`README.md`](README.md)** — карта стека, API, indicators, deploy. Высокоуровневый обзор.
3. **[`docs/data_sources.md`](docs/data_sources.md)** — точная карта «индикатор → файл/endpoint» (75 source-индикаторов). Канонический справочник, откуда тянется каждый ряд.
4. **[`docs/workflow.md`](docs/workflow.md)** — модель работы, локальный dev, прод-деплой, smoke C.
5. **[`docs/enterprise_resilience.md`](docs/enterprise_resilience.md)** — операционные инварианты, чеклист канарейки 6/6.
6. **`docs/adr/`** — архитектурные решения (нумерованные ADR, читать в порядке номеров):
   - `0001-derived-indicators-engine-shape.md` — engine shape derived (28 specs + 9 pure ops).
   - `0002-derived-always-reflects-source.md` — инвариант идемпотентности `bulk_upsert`.
   - `0003-seo-single-source-server-rendered.md` — SSR через backend, asset discovery от Vite shell.
 - `0004-rosstat-russian-canonical-sdds-deprecated.md` — Rosstat русский canonical, SDDS English deprecated. Migration pattern + pilot evidence (gdp-nominal, 2026-05-10).

После этих файлов агент способен ответить на ~90% вопросов и делать осмысленные правки.

---

## Шаг 2 — где искать конкретное

| Вопрос | Файл/папка |
|--------|------------|
| Как работает парсер X? | `backend/app/services/<X>_parser.py` + раздел в `CONTEXT.md::Parser` |
| Откуда берётся индикатор X? | **[`docs/data_sources.md`](docs/data_sources.md)** — точный URL/файл по каждому из 75 source |
| Какие источники, кроме Росстата? | [`docs/cbr_sources.md`](docs/cbr_sources.md) (CBR + Минфин, 10 парсеров — детально) |
| Как считается derived-индикатор Y? | `DERIVED_SPECS` в `backend/app/services/calculation_engine.py` + ADR-0001 |
| Какая стратегия forecast у индикатора Z? | `Indicator.model_config_json.forecast_strategy` в БД + реестр `backend/app/services/forecast_strategies/registry.py` + таблица в `CONTEXT.md::Forecast` |
| Как собирается SEO/мета? | `backend/app/services/seo_renderer.py` + `seo_content.py` + ADR-0003 |
| Какие endpoints есть в API? | Таблица в `README.md::API` + Swagger `/api/docs` (только при `RUSTATS_DEBUG=true`) |
| Yandex Metrika / Webmaster | [`docs/analytics_api_inventory/`](docs/analytics_api_inventory/) — каждый файл начинается со status block (`partial` / `implemented` / `planned`) |
| Что менять при правке UI? | `frontend/src/...` + `docs/workflow.md::Браузерная проверка` (cursor-ide-browser + headless E2E) |
| Какие traps подстерегают? | Раздел «Operational invariants and traps» в `CONTEXT.md` (12 пунктов) |
| Как делать прод-деплой? | `docs/workflow.md::Прод-деплой` + `enterprise_resilience.md` |

---

## Шаг 3 — режим работы

**Запреты (всегда):**
- **Не пушить на прод-сервер** (`5.129.204.194`, `/opt/rosstat`) без явной команды пользователя.
- **Не пушить на `main`** без зелёного `./scripts/check-all.sh` (pytest + lint + vitest + vite build).
- **Не редактировать `git config`**, не делать `--force` push, не амендить коммиты, которые уже на remote.
- **Не создавать новые .md файлы**, если можно обновить существующий. Документация консолидирована — фрактальная сеть выстроена; новые файлы только если возникает действительно новая категория знания.
- **Не мерджить «полу-готовое»** в `main`. Регламент канарейки 6/6 в `enterprise_resilience.md` — обязателен.

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
| **Любое изменение источника данных** (URL, имя файла, sheet, dataservice блок, file template) | **`docs/data_sources.md`** — single source of truth «индикатор → актуальный файл/endpoint». ОБЯЗАТЕЛЬНО при любой правке парсера или `model_config_json` |
| Новый source-парсер (CBR/Минфин/иной) | `docs/cbr_sources.md` (таблица + детальный раздел) + `docs/data_sources.md` + регистрация в `PARSER_REGISTRY` + строка в `seed_data.py` |
| Новый Rosstat-парсер | `CONTEXT.md::Parser` + `docs/data_sources.md` + `PARSER_REGISTRY` + `seed_data.py` |
| Новый derived-индикатор | `DERIVED_SPECS` в `calculation_engine.py` + `seed_data.py` + раздел в `CONTEXT.md::Derived indicator` (счётчики и категории) |
| Новая чистая op в `derived_ops.py` | ADR-0001 (раздел «Subsequent additions») + `CONTEXT.md::Derived indicator` (список ops) |
| Новая forecast-стратегия | `forecast_strategies/registry.py` + таблица в `CONTEXT.md::Forecast` + строка в `README.md::Прогнозы` |
| Новый API endpoint | Таблица `README.md::API` + Swagger (автоматически из FastAPI route) |
| Новый категория или slug | `frontend/src/lib/categories.js` **и** `seo_content.py::CATEGORY_META` (синхронно — см. ADR-0003) + строка в `README.md::Индикаторы` |
| Изменение rate-limit / CORS / CSP | `enterprise_resilience.md::API и backend` + `enterprise_resilience.md::Frontend и кэш` |
| Новая операционная trap, обнаруженная в проде | `CONTEXT.md::Operational invariants and traps` |
| Новое архитектурное решение | **Создать новый ADR** `docs/adr/<NNNN>-<kebab-name>.md` (следующий свободный номер); добавить ссылку в шапку `CONTEXT.md::Документы рядом` и в `AGENTS.md::Шаг 1` |
| Изменение существующего ADR | Не редактировать body «как если бы решение было таким». Добавить раздел «Subsequent additions (after acceptance)» с датой и описанием. Status в шапке менять только при формальной депрекации |
| Новый Yandex API client | `docs/analytics_api_inventory/<service>.md` (если файл уже есть — обновить status block) или новый файл при новом сервисе + строка в `analytics_api_inventory/README.md::Implementation status` |

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

---

## Шаг 5 — карта папок проекта

```
rosstat/
├── AGENTS.md                       ← вы здесь
├── CONTEXT.md                      ← spine: glossary + invariants
├── README.md                       ← high-level overview
├── docs/
│   ├── adr/                        ← architectural decisions (нумерованные)
│   ├── analytics_api_inventory/    ← Yandex API контракт + status
│   ├── data_sources.md             ← single source of truth: индикатор → файл/endpoint (75 source)
│   ├── cbr_sources.md              ← CBR + Минфин parsers (детально)
│   ├── workflow.md                 ← процесс, dev, deploy
│   └── enterprise_resilience.md    ← операционные инварианты
├── backend/
│   ├── app/
│   │   ├── api/                    ← FastAPI routes
│   │   ├── services/               ← parsers, forecaster, engine, SEO renderer
│   │   ├── tasks/                  ← APScheduler jobs
│   │   ├── analytics/              ← Yandex clients + warehouse
│   │   ├── models.py, config.py, main.py, database.py
│   │   └── data/indicator_seo.py   ← per-indicator SEO defaults
│   ├── alembic/                    ← миграции
│   ├── seed_data.py                ← idempotent seeder, 104 indicators
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
