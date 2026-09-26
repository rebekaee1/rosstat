# AGENTS.md — инструкции для AI-агентов (Cursor, Claude Code, Codex, Copilot, Gemini)

Коротко и только то, что нужно в каждой сессии. Подробности — по ссылкам,
открывать под задачу, не целиком. **Первым делом прочитай
[`docs/STATE.md`](docs/STATE.md)** — где остановились, что в работе, что
нельзя трогать. В конце работы — обнови его (правило ниже).

## Проект в трёх строках

`forecasteconomy.com` (EN, apex) и `ru.forecasteconomy.com` (RU) — публичная
платформа официальной макростатистики по странам (Росстат, ЦБ, Минфин, 85
субъектов РФ; мир — нац. ведомства, Евростат, МВФ, FRED/BEA): ETL → Postgres →
derived-ряды и прогнозы → React SPA + серверные SSR-страницы для поисковиков/ИИ.
Владелец не программист, пишет по-русски; ~85% трафика — боты.

## Где что лежит

| Что | Где |
|-----|-----|
| Рабочая копия (Mac владельца) | `/Users/iprofi/tradingeconomics/rosstat`; соседние worktree `…/rosstat-*` |
| GitHub | `rebekaee1/rosstat`, ветка `main` (CI: `.github/workflows/ci.yml`) |
| Прод | `ssh fe-prod` (алиас в `~/.ssh/config`), `/opt/rosstat`, Docker Compose + Caddy на хосте |
| Локальный сайт | Vite `http://localhost:5173` (прокси `/api` на прод по умолчанию); полный стек compose — `http://localhost:3000` |
| Бэкапы | прод `/opt/rosstat/backups` (07:00 МСК), копия на Mac `~/Backups/forecasteconomy/` |
| Стек | Python 3.12 / FastAPI / SQLAlchemy async / APScheduler; Postgres 16; Redis 7 (кэш) + redis-state (сессии); React 19 / Vite 7 / Tailwind 4; nginx в frontend-контейнере |

## Команды

- `./scripts/check-all.sh` — эквивалент CI: pytest, vitest, eslint, vite build, карта индикаторов (`--check`), `audit-doc-counters.py`, `export-page-meta.py --check`, `audit-public-language.py`. Зелёный — обязателен до push.
- `python scripts/locate-indicator.py <code>` — где встречается индикатор; запись в `docs/indicator-index.json`.
- `python scripts/build-indicator-index.py` — регенерация карты после правок seed/парсеров/view-mode (иначе CI упадёт на `--check`).
- `cd frontend && npm ci && npm run dev` — фронт против прод-API; `docker compose up -d --build` — весь стек.
- `docker compose exec backend python /app/scripts/rebuild-all-derived.py` — полный пересчёт derived.

## Жёсткие правила

- **Push в `main` и прод-деплой — только по явной команде владельца.** Деплой = только SHA из `deploy/approved-shas.txt` (approval-only коммит), процедура — [`docs/workflow.md`](docs/workflow.md#прод-деплой). Прод ≠ `main`.
- Миграции alembic в диапазоне прод→цель — отдельно предупредить владельца до деплоя; откат образов схему не откатывает.
- **Не делать `FLUSHDB` кэш-Redis на проде** (холодный кэш под ботами = исчерпание пула БД и автооткат, 2026-09-26). Инвалидация — `cache_invalidate_indicator(code)` / `bump_namespaces()` / деплойная очистка `fe:*:ssr:*`. DB 1 / `redis-state` (сессии) не трогать никогда.
- БД пользователей: никаких `docker compose down -v`, заливки локальной БД на прод, смены имени тома/пользователя. Синк только прод → локаль.
- Не держать соединение БД во время ожидания (кэш, лок, семафор, рендер HTML/PNG) — см. CONTEXT, Cold-cache pool exhaustion trap.
- Не править `git config`, не `--force` на `main`, не амендить запушенное. Коммитить сразу после завершённой правки.
- Секреты, `.env`, ключи — не в git и не в чат.
- Публичные тексты — без внутренностей (имена файлов, парсеры, ADR): [`.cursor/rules/methodology-language.mdc`](.cursor/rules/methodology-language.mdc); RU/EN паритет: [`.cursor/rules/i18n-parity.mdc`](.cursor/rules/i18n-parity.mdc); без «·» в UI: [`.cursor/rules/no-middle-dot.mdc`](.cursor/rules/no-middle-dot.mdc).
- Прогнозы — только для рядов месяц и реже, не для бирж/крипты. На графике прогноз — простая линия: без доверительной полосы и без текста о прогнозе над графиком.
- Ссылка «Источник» в SPA ведёт на внешний сайт ведомства (`SourceLink`); быстрые SEO-страницы намеренно ведут на основной сайт.

## Предпочтения владельца

- Русский язык, простые слова, отчёт о каждом шаге по ходу работы (что сделано, что нашёл, что дальше); факты отдельно от гипотез.
- Работа с кодом — локально на Mac (не облачные агенты); параллельные агенты — в отдельных git worktree.
- Деплои — редко, крупными пачками (2–3), каждая с явным одобрением SHA.
- Автономность в реализации; вопросы — только на необратимых продуктовых развилках. Подробно — [`.cursor/rules/working-agreement.mdc`](.cursor/rules/working-agreement.mdc).

## Слои индикатора (где править)

| Слой | Механизм |
|------|----------|
| данные/парсер | `PARSER_REGISTRY` + `backend/app/services/*_parser.py` (internals — в docstring) |
| derived | `DERIVED_SPECS` (`calculation_engine.py`) + чистые ops `derived_ops.py` |
| прогноз | `forecast_strategies/registry.py` (`model_config_json.forecast_strategy`) |
| отрисовка/view-mode | `view_model_families.py` → `viewModelFamilies.generated.json` → `viewModeEngine.js`; bespoke только `cpi`/`housing`/`ppi` |
| SEO | `app/data/indicator_seo.py` + `seo_content.py` + `seo_renderer.py`; sitemap/OG/RSS — из БД |
| листинг | `INDICATOR_HIDDEN_FROM_LISTING` → `seed_data.py` (`is_listed`) |

Новый индикатор/категория/семейство — рецепты в [`docs/indicators.md`](docs/indicators.md).
Флаги `shadowed_legacy` в карте — не список на удаление ([`docs/dead-code-report.md`](docs/dead-code-report.md)).

## Карта документации (открывать по задаче)

| Вопрос | Файл |
|--------|------|
| Где остановились, что в работе | [`docs/STATE.md`](docs/STATE.md) |
| Глоссарий, инварианты, ловушки прода | [`CONTEXT.md`](CONTEXT.md) — точечно по разделу |
| Деплой, бэкапы, восстановление, runbooks, локальный dev | [`docs/workflow.md`](docs/workflow.md) |
| Откуда берётся ряд X | [`docs/data_sources.md`](docs/data_sources.md) + docstring парсера |
| Индикаторы, категории, семейства | [`docs/indicators.md`](docs/indicators.md), `docs/indicator-index.md/.json` (генерируется) |
| Архитектурные решения | [`docs/adr/`](docs/adr/) ADR-0001…0015 (нужный номер) |
| Метрика, Вебмастер, GSC, фронтовые события | [`docs/analytics.md`](docs/analytics.md) |
| Открытые задачи и последние разборы | [`docs/backlog.md`](docs/backlog.md) |
| Обзор для человека/владельца | [`README.md`](README.md) |
| Живые счётчики URL | `/sitemap-stats.json`, `docs/site-inventory.json` (не цитировать числа из истории) |

Генерируемые файлы — не править руками: `docs/indicator-index.*`,
`docs/dead-code-report.md`, `docs/repo-inventory.md`, `docs/site-inventory.json`.

## Как поддерживать документацию

- Правка меняет поведение → обнови один канонический документ из карты выше (не создавай параллельный). Источник данных → `data_sources.md` + docstring; новая ловушка прода → `CONTEXT.md` (раздел traps); новое архитектурное решение → новый ADR + строка в этой карте; операционка → `workflow.md`.
- Не вести changelog в документах: история — в git (`git log`, сообщения коммитов). Никаких «Last updated/Previous» хроник.
- Числа из кода (ряды seed, парсеры, спеки) в README/CONTEXT/data_sources проверяет `scripts/audit-doc-counters.py`.
- **В конце работы (обязательно):** обнови [`docs/STATE.md`](docs/STATE.md) — что сделано (SHA), что задеплоено, что в работе и где (ветка/worktree), что открыто. Коротко; устаревшее удаляй.
