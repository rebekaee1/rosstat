# Приёмка навигации нового агента — аналитика, 30.09.2026

Ниже сохранён ответ агента без истории чата, составленный при незавершённых
общих gates. После этого root завершил `check-all.sh`: backend3198passed/9skip,
frontend924passed, lint0errors/5warnings, build и knowledge guards зелёные.
Источники отчёта не изменились; 11 приведённых SHA-256 совпали. Независимый
финальный review и уборка тестового окружения записаны в
[итоговом свидетельстве](analytics-boundaries-evidence-2026-09-30.json).
Датированные pending-состояния в исходном ответе сохранены как история чтения.
Это приёмка одного сценария навигации, не гарантия знания всех ветвей проекта.

---

# BI / PostgreSQL / ClickHouse — независимый сценарий чтения

Срез: **30.09.2026, 20:30 UTC**. Репозиторий прочитан без истории чата.
`main`, HEAD `83c455556998821ac3dcdc140e35b549dad064ec`, ahead `origin/main` на 5.
Аналитические исходники и документы изменены локально; четыре новых теста уже
в index. Это не новый commit, push, deploy или live acceptance. В этом проходе
не запускались application jobs, тесты, resync, SSH или deploy. Единственная
запись — данный отчёт. Свидетельства чужих прогонов ниже прочитаны, а не повторены.

## Почему цифры расходятся после поздних событий

Путь установлен по исходникам: публичные collectors
`api/analytics.py::{collect_event,collect_behavior_batch}` → PostgreSQL
`frontend_events` / `behavior_events` →
`tasks/analytics_rollups.py::sessionize` → `server_sessions` → PostgreSQL
`analytics_marts.py::mart_metric_tree` / другие BI-витрины. «Срезы» идут отдельно:
`AdminBI.jsx::SlicesTab` → admin-only
`api/admin_bi.py::{slices_meta,slices_query}` →
`clickhouse_sync.py::run_slice` → производная ClickHouse-копия. Служебный
analytics token collectors не требуется; BI требует активного пользователя и
email в `admin_emails` (`require_admin`: 401/404). Auth state живёт в state Redis.

1. **F05 исправлен локально в PG layer.** `sessionize` выбирает посетителей окна,
   SQL восстанавливает их сохранённую историю до cutoff, затем staging/delete
   старых splits/insert итогов коммитятся вместе. Backfill способен объединить
   два visitor/start key или сдвинуть старт. `run_rollups` коммитит каждое окно
   отдельно; весь 60-дневный run не атомарен. Gap `>=30min` разделяет bursts,
   но pageviewless tail присоединяется назад: это прежняя политика, а не визит
   «по любому событию каждые 30 минут». Ordinary lookback — 2 суток, daily — 60;
   произвольный старый backfill автоматически не обнаруживается.
2. **F06 исправлен локально для существующих automatic append writers.** ID
   выделяется до commit. Прежнее `id>cursor` пропускало меньший ID, который
   закоммитился после большего. `_event_ceiling` теперь берёт короткий
   `SHARE NOWAIT`, проверяет READ COMMITTED/default-or-identity/CACHE1/+1/no-cycle,
   затем получает committed ceiling; занятый writer даёт deferred без cursor
   advance. v2 cursor перечитывает сохранённую историю по 4×20k каждой таблицы
   на job. CH insert precedes ACK: физические replay-дубли возможны, поэтому
   `SLICE_METRICS` pageviews/clicks используют `uniqExactIf(id,...)`.
3. **F05b открыт и сам воспроизведён на final source.** CH `server_sessions` —
   ReplacingMergeTree с `ORDER BY(visitor_id_hash,started_at)`, без tombstone.
   `_sync_replacing(days=2)` читает только `started_at>=now−2days`: PG delete
   старого logical key в CH не передаётся, обновление старого carry пропускается.
   `run_slice` использует FINAL; он дедуплицирует одинаковый key, но не удаляет
   другой key. После чистой исходной копии late bridge: source 1 session/3 PV,
   CH FINAL 2/4. Carry со start три дня назад: source active_ms=25000, CH=0.
   Разовый resync исправляет исходный снимок, но следующий late bridge повторяет
   механизм. Увеличение days также не передаёт deletes.

Для сверки нужны одинаковые период, единицы и population. PG `mart_metric_tree`
считает `Period.start_date..end_date` и исключает bot/internal; `run_slice` задаёт
`>=today()-days`, не использует общий Period и применяет bot/internal только к
server_sessions. Pageviews/clicks берутся из event layer, а не суммы session PV.
`visitors` в CH использует `uniq`, PG — exact distinct. Одно различие чисел само
по себе ещё не устанавливает, какой из этих механизмов его вызвал.

## Как восстановить CH в рамках действующего механизма

Это операторский maintenance сценарий, **не выполненный здесь**:

1. Проверить целевой PostgreSQL DSN, CH database и state Redis, сохранность
   PostgreSQL сырья и наличие восстановимой PG-копии; установить фактически
   исполняемую ревизию. Локальные pending/cursor safeguards ещё не являются
   доказанно выпущенными на production. Не очищать PG или Redis ради CH.
2. Исключить overlapping incremental sync, включая уже начавшийся job, и
   согласовать rollup publication на время сверяемого снимка. `locked_job`
   (`main.py:243`) не продлевает TTL и fail-open при Redis error; pending marker
   не является fencing lease и не останавливает уже идущую копию.
3. На проверенной версии вызвать `resync()` отдельно: сначала durable
   `fe:ch:resync_pending:v2`, очистка success/progress и **обоих** event cursors,
   затем DROP+CREATE шести derived таблиц, последовательный event replay до
   captured ceilings и `_sync_replacing(days=3650)`. Недоступный writer/ошибка
   оставляет pending; ordinary job пропускается, slices/meta unavailable,
   slice HTTP503. Требуется контролируемый operator retry. Самовольно снимать
   pending и продолжать обычный sync после частичного DROP нельзя.
4. После успеха сверить distinct source IDs/CH IDs и метрики на одном cutoff,
   schema, replacing данные с FINAL; проверить оба progress, job log и age.
   Pending снимается только при success, затем можно вернуть штатное расписание.
   Heartbeat/`available=true` не доказывают session deletes или commits после
   capture; ошибка до записи progress может оставить предыдущий capture.

Фактическая гарантия ограничена: state Redis должен сохраниться; atomic commit
между Redis и CH отсутствует. Replacing rebuild имеет cutoff 3650 суток и не
берёт единый snapshot всех PG таблиц. Полная DR-приёмка с original AOF и всеми
replacing слоями отсутствует. Будущее решение F05b (durable deletion/dirty
generation + tombstones либо coherent snapshot/ACK/fencing) пока рекомендация.

## Прочитанное локальное свидетельство

Основной источник — `docs/code-review/analytics-boundaries-evidence-2026-09-30.json`.
На момент чтения `integration_gates`, final review и cleanup ещё **pending**;
общие gates нельзя объявлять зелёными по этому срезу.

| Проверка | Установленный результат / граница |
|---|---|
| F05 RED → GREEN | Actual caller до fix: 4 failed/2 passed; focused 65 passed и real PG 12 passed на предшествующем SHA с тем же исполняемым телом; final SHA ниже отличается docstring. |
| F05 final benchmark | PG16 1 CPU/512MiB; 100k events, 5k portraits/goals: continuous 2,696s, three-day caller 5,488s; одинаковый content hash, 5001 stored sessions/5000 owned starts, peak Python RSS108,75MiB включает imports/loader. |
| F06 focused | 25 passed (17 PG,6 native CH,2 старых) на final SHA; late-lower-ID/retry/unsafe sequence/progress проверены в заявленных fixture границах. |
| F06 real PG/CH/Redis | 100k IDs после ACK fault дают physical120k/logical100k; ordinary jobs80k+20k; actual slices50kPV/50kclicks. Это point/warm-after-seed observation, CH768MiB/1CPU, а не production448MiB/0,5CPU. |
| Interrupted resync | Реальные PG16/CH24.8/Redis7 DB15: injected second-DROP error → оба cursors0/pendingtrue/no heartbeat, ordinary job/slice blocked; retry возвращает обе event таблицы и success. `_sync_replacing` в этом сценарии no-op double: полный rebuild остальных слоёв не доказан. |
| F05b final repro | Настоящий CH24.8 и actual sessionize/replacing, PG-side temporary SQLite; оба расхождения выше воспроизведены. Это не full real-PG→CH приёмка, дефект также прямо следует из key/filter кода. |

Raw retention default0 подтверждён `config.py` и
`analytics_scheduler.py::behavior_retention_job`; ненулевое значение удаляет
старые BehaviorEvent. Replay восстанавливает только сохранённое PG сырьё.
SQL historical scan/temp disk, admin identity sets, exact-distinct memory и
physical replay disk не ограничены размером Python batch. Browser delivery loss,
clock skew и concurrent writer/process/network chaos этой приёмкой не закрыты.

## Production, 4 CPU и локальный запуск

Датированная ops-приёмка 30.09 14:59–15:26UTC наблюдала production checkout
`367ff336a307ad57d528b26078ca35883ec3de68`:402 backend payload SHA совпали
у web/scheduler с checkout,264 frontend dist-files проверены; это не выпуск
нынешнего F05/F06 и не проверка loaded Python state. На общем4vCPU:
web quota3 + scheduler1 + frontend0,5 + CH0,5 =5CPU; PG/Redis/host конкурируют
дополнительно. RAM limits7616MiB против физической7941MiB — арифметический
остаток≈325MiB, не reservation/свободная память. Максимальные app pools73;
app-role superuser может занимать reserved connections. Shared capacity,
p95/p99/пиковая память под ETL+SSR+BI и provider IO/SLA не измерены.

PG backup restore локально проверен отдельно (первый data/schema154,885s;
owners/ACL182,967s + HTTP/email auth/state-session/nginx SSR; clean startup
34 migrations/seeds/readiness200). Полный browser/external OAuth/original
Redis AOF/CH failover/RTO/RPO из этого не следуют.

Для dev `workflow.md` явно различает Compose:3000 nginx/SSR и Vite:5173 CSR.
Root `.env` только Compose interpolation: неизвестный RUSTATS key не попадает
в контейнер без mapping. Settings прямого Python читает cwd dotenv; container
Python не bind-mounted. После backend change нужен rebuild/recreate; Vite
default API proxy ведёт на production **всеми HTTP methods**, для local нужен
explicit localhost. Compose scheduler env задаёт true литералом: исключение
его из `up` не останавливает уже работающий scheduler. Прямой Python default
5432/6379 не равен host Compose5434/6380; state Redis host port не опубликован.

Исторические расхождения документов различены: ADR-0010 раннее «state DB1»
не описывает observed production `redis-state:/0`; «resync вся история» имеет
указанный3650-day replacing cutoff. `_sync_replacing` docstring «идемпотентный»
не означает delete reconciliation. Старое описание macOS14.5 из переданного
входа против dated snapshot27.09 macOS26.6.2; новую live OS-проверку я не делал.
Попытка прочитать `~/.Codex/user-profile.md` дала missing file; актуальный
репозиторный AGENTS прочитан. Graph locators первоначально старые, при повторном
чтении после параллельной регенерации уже соответствовали final source; это не
оставленный дефект карты. Static graph/review/hash и healthy не равны исполнению.

## Действительно прочитанные основания и подпись исходников

Прочитаны: `AGENTS.md`, analytics acceptance MD (до/после обновления),
analytics inventory README. По относящимся разделам: project-terrain MD
(scope/покрытие/смысл связей), knowledge-workflow MD (цикл/guards/cold-start);
README начало/dev; CONTEXT начало/analytics traps;
architecture analytics/runtime/dev; data-contracts F05/F06/F05b;
architecture-history analytics; knowledge-unknowns F05/F06/F05b/U01–U08;
workflow analytics/activation/dev/recovery; enterprise_resilience resource/recovery;
ADR0007 identity, ADR0009 collectors/retention, ADR0010 OLAP/history/30.09.
Прочитаны выбранные строки `reviews.jsonl` (hash текущих3 analytics files
совпал), runtime-inventory JSON dated fields, ops-mechanism acceptance MD/JSON,
analytics-boundaries evidence JSON, `.artifacts/f05-evidence.json`, F05/F06
benchmarks/focused logs, F05b/resync repro final sections. Из existing graph
прочитаны vocabulary и непосредственные связи sessionize/replacing/run_slice.
Чтение исходников — названные выше функции, producer/consumer/settings/locks.
Это принятие данного сценария, не обещание полного понимания всего проекта.

SHA-256 файлов рабочего дерева, снятые 20:30UTC (Git HEAD указан в начале):

| Путь | SHA-256 |
|---|---|
| backend/app/tasks/analytics_rollups.py | `51b65469da05ab9a68a1e997e90fab433b8ae03b5ce7cef4953fc1684c26220d` |
| backend/app/services/clickhouse_sync.py | `09d60144066d7cc7fc291a4afdc41fbbbb5742b3e661abd0806b5d0468acf84e` |
| backend/app/api/admin_bi.py | `94ad7cde603c4b2c03c16d9605134baebb5c479a02969ebe3f344187e8ac5a4f` |
| backend/app/services/analytics_marts.py | `2438fc13878f93e512853745cfab39bc3c717b97c9c75968e9810876eeb91965` |
| backend/app/api/analytics.py | `8c5eeb16e9ef591997d64d70b1d1ae3033d61bc715b0c794f40ac49bfe2212d7` |
| backend/app/database.py | `43140d01ff51be8f47c45aedff77d049d7f3da63f789df30bd78bd8bab5306a8` |
| backend/app/config.py | `ad369a89256c4b3651384cf754d7dda3c7cc8a83faf7b9301681f227f027d994` |
| backend/app/main.py | `a4177428b5a080d6bb8a66669259655750f0a3191437d0a84c71d429855e68a8` |
| frontend/src/pages/AdminBI.jsx | `5912858bea6a4381e37661668bd99ac74fa6bda42dd3f9f5fa6dad2808ec0158` |
| docker-compose.yml | `cc0c45af675f4e3f1877a1f085ce8e2087595572621862de7794e608d3c88720` |
| clickhouse/low-memory-users.xml | `080f86dcb363402e39661016991bd3476b535dc80bc6984dc2111e046a62cbff` |
