#!/usr/bin/env bash
# Deploy forecasteconomy.com — backup, ff-only pull, build, smoke, rollback.
# Usage: ssh -i ~/.ssh/id_ed25519_fe_prod root@201.51.11.170 'bash /opt/rosstat/scripts/deploy.sh'
#
# Волна 4 (О-2..О-7): preflight-бэкап БД (hard fail), git ff-only + dirty-guard,
# версионированные образы (тег = SHA) с автооткатом при провале smoke,
# расширенный smoke (data-endpoint, SSR asset-hash, HTTPS через Caddy),
# Caddy reload — ПОСЛЕ успешного smoke, не до.
set -euo pipefail

cd /opt/rosstat

# Serialize publication, container replacement and pruning across deploys.
exec 9>/var/lock/rosstat-deploy.lock
flock -n 9 || { echo "FAIL: другой деплой уже выполняется"; exit 1; }

# ── 1. Preflight: бэкап БД перед миграциями (О-2) ─────────────────────
echo "==> preflight: pg backup"
./scripts/pg-backup.sh || { echo "FAIL: backup failed — деплой остановлен"; exit 1; }

# ── 2. Git: чистое дерево + только fast-forward (О-3) ─────────────────
echo "==> git fetch + ff-only"
if [ -n "$(git status --porcelain)" ]; then
  echo "FAIL: рабочее дерево на проде грязное — разберись руками:"
  git status --porcelain
  exit 1
fi
PREV_SHA=$(git rev-parse --short HEAD)
git fetch origin main
git merge --ff-only origin/main || { echo "FAIL: ff-only merge невозможен (история разошлась)"; exit 1; }
NEW_SHA=$(git rev-parse --short HEAD)
echo "    ${PREV_SHA} -> ${NEW_SHA}"

# ── 2b. Scope guard: выкатываем только одобренные SHA (инцидент 2026-08-27) ──
# Прод ≠ main: ff-only тянет ВСЮ пачку коммитов между продом и целью, включая
# фичи, которых владелец не заказывал. Деплой разрешён только если целевой SHA
# внесён в deploy/approved-shas.txt (полные хэши, по одному на строку).
# Пустой/отсутствующий файл = деплой запрещён. Пополнение списка — только
# явным подтверждением владельца («деплой до <sha>»).
# pwd, не $0: скрипт иногда копируют в /tmp, чтобы self-update не сдвигал
# остаток файла после ff-only merge (этот коммит как раз меняет deploy.sh).
APPROVED_FILE="$(pwd)/deploy/approved-shas.txt"
FULL_SHA=$(git rev-parse HEAD)
if [ ! -s "${APPROVED_FILE}" ]; then
  echo "FAIL: deploy/approved-shas.txt пуст или отсутствует — скоуп деплоя не одобрен."
  echo "      Владелец должен явно подтвердить цель деплоя (SHA ${NEW_SHA}), затем"
  echo "      добавить её в deploy/approved-shas.txt. Пачка коммитов:"
  git log --oneline "${PREV_SHA}..${NEW_SHA}" | head -40
  git reset --hard "${PREV_SHA}" >/dev/null 2>&1
  exit 1
fi
approved_sha() {
  sed 's/#.*//' "${APPROVED_FILE}" | sed 's/[[:space:]]*$//' | grep -qx "$1"
}
# Approval lives in git, therefore a commit cannot contain its own SHA. The only
# permitted bootstrap wrapper is one direct child that changes only the approval
# file and this guard itself; runtime target remains the explicitly approved parent tree.
APPROVED_TARGET="${FULL_SHA}"
if ! approved_sha "${FULL_SHA}"; then
  PARENT_SHA=$(git rev-parse "${FULL_SHA}^")
  WRAPPER_FILES=$(git diff --name-only "${PARENT_SHA}" "${FULL_SHA}")
  # Wrapper может менять только файл одобрения ИЛИ файл одобрения + этот скрипт
  # ( bootstrap: скрипт-гард эволюционирует вместе с правилами одобрения).
  if approved_sha "${PARENT_SHA}" && {
     [ "${WRAPPER_FILES}" = "deploy/approved-shas.txt" ] ||
     [ "${WRAPPER_FILES}" = "deploy/approved-shas.txt
scripts/deploy.sh" ]; }; then
    APPROVED_TARGET="${PARENT_SHA}"
  else
    echo "FAIL: SHA ${NEW_SHA} (${FULL_SHA}) и его approval-only parent не одобрены."
    echo "      Пачка, которую потянуло бы (прод → цель):"
    git log --oneline "${PREV_SHA}..${NEW_SHA}" | head -40
    git reset --hard "${PREV_SHA}" >/dev/null 2>&1
    exit 1
  fi
fi
echo "==> scope: approved runtime target ${APPROVED_TARGET} — ок"

# ── 2c. Migration-direction guard: downgrade схемой деплоя не делаем ────────
# Разгон схемы необратим для отката кода: после него старый код не стартует.
# Новые (up) миграции — ок, entrypoint сам прогонит alembic upgrade. А вот
# если целевой коммит УДАЛЯЕТ файлы миграций, которые есть на проде — это
# downgrade-путь, деплой abort (рецепт восстановления в CONTEXT.md::traps).
for f in $(git diff --name-status "${PREV_SHA}" "${NEW_SHA}" -- backend/alembic/versions/ | awk '$1=="D" {print $2}'); do
  echo "FAIL: коммит удаляет миграцию ${f} — это downgrade-путь, схемой деплоя не делаем."
  echo "      Восстановление — CONTEXT.md::Deploy-scope trap. Откатываю merge."
  git reset --hard "${PREV_SHA}" >/dev/null 2>&1
  exit 1
done

# ── 3. Build: версионированные образы для отката (О-4) ────────────────
echo "==> docker compose build (tag=${NEW_SHA})"
# Retain the actual running images, not whatever 'latest' a previous build left.
for service in backend frontend; do
  container=$(docker compose ps -q "$service")
  [ -n "$container" ] || { echo "FAIL: running ${service} required for rollback"; exit 1; }
  image=$(docker inspect --format '{{.Image}}' "$container")
  docker tag "$image" "rosstat-${service}:${PREV_SHA}"
  if [ "$service" = frontend ]; then PREV_FRONTEND_IMAGE="$image"; else PREV_BACKEND_IMAGE="$image"; fi
done
preparation_failed() {
  trap - ERR
  git reset --hard "${PREV_SHA}"
  docker tag "${PREV_BACKEND_IMAGE}" rosstat-backend
  docker tag "${PREV_FRONTEND_IMAGE}" rosstat-frontend
  echo "FAIL: подготовка релиза не завершена; работающие контейнеры не менялись"
  exit 1
}
trap preparation_failed ERR
docker compose build --build-arg "VITE_BUILD_ID=${APPROVED_TARGET}" frontend backend
docker tag rosstat-backend "rosstat-backend:${NEW_SHA}"
docker tag rosstat-frontend "rosstat-frontend:${NEW_SHA}"

# Compose resolves .env too: use its effective mount rather than a different
# shell default. Keep a helper copy because rollback restores the previous git.
ASSET_ARCHIVE=$(docker compose config --format json | python3 -c '
import json, sys
volumes = json.load(sys.stdin)["services"]["frontend"]["volumes"]
print(next(v["source"] for v in volumes if v["target"] == "/var/cache/frontend-assets"))')
ASSET_WORK=$(mktemp -d)
cp scripts/frontend-asset-archive.py "${ASSET_WORK}/archive.py"
cleanup_assets() { stop_backend_log; rm -rf "${ASSET_WORK}"; }
trap cleanup_assets EXIT
publish_frontend_assets() {
  local image="$1" container result=0
  container=$(docker create "$image") || return 1
  mkdir -p "${ASSET_WORK}/html"
  docker cp "${container}:/usr/share/nginx/html/." "${ASSET_WORK}/html" || result=1
  docker rm "$container" >/dev/null || result=1
  if [ "$result" = 0 ]; then
    python3 "${ASSET_WORK}/archive.py" publish --archive "$ASSET_ARCHIVE" --source "${ASSET_WORK}/html" || result=1
  fi
  rm -rf "${ASSET_WORK}/html"
  return "$result"
}
# Complete old+new asset publication precedes exposing new HTML. Prune only
# after acceptance so both rollback and old tabs remain safe during the watch.
PREV_ASSET_RELEASE=$(publish_frontend_assets "${PREV_FRONTEND_IMAGE}")
NEW_ASSET_RELEASE=$(publish_frontend_assets "rosstat-frontend:${NEW_SHA}")
RETAINED_PROBE=$(python3 - "$ASSET_ARCHIVE" "$PREV_ASSET_RELEASE" "$NEW_ASSET_RELEASE" <<'PY'
import json, pathlib, sys
root = pathlib.Path(sys.argv[1]) / "releases"
previous = json.loads((root / f"{sys.argv[2]}.json").read_text())
current = set(json.loads((root / f"{sys.argv[3]}.json").read_text()))
# Prefer a path absent in the new image to actually exercise nginx's fallback.
print(next((name for name in previous if name not in current), previous[0]))
PY
)

# ── Кэш релиза (2026-09-26): вместо FLUSHDB всего DB 0 — только SSR HTML ──
# FLUSHDB обнулял и дорогие data-кэши (каталог стран, world/regions API),
# ticker и rate-limit: холодный backend под краулерами (~10k req/h) исчерпывал
# QueuePool и watch откатывал релиз. Инвалидировать на релизе нужно только
# SSR HTML: ключ `fe:{ns}:v{N}:ssr:{hash}:{asset_sig}` (seo_pages._ssr_key).
# Смена фронта и так меняет asset_sig, но смена рендер-кода backend при том же
# фронте — нет, поэтому SSR удаляем явно. SCAN + UNLINK батчами (не KEYS, не
# блокирующий DEL). `fe:ver:*` НЕ трогаем: сброс версии воскресил бы ключи v0.
# Доп. паттерны / бамп namespace'ов data-кэша — через env при запуске:
#   DEPLOY_CACHE_EXTRA_PATTERNS="fe:world:*"  DEPLOY_CACHE_BUMP_NAMESPACES="world"
REDIS_PASSWORD="$(grep '^REDIS_PASSWORD=' .env 2>/dev/null | cut -d= -f2- | tr -d '\"' | tr -d "'" || true)"
invalidate_release_cache() {
  docker compose exec -T \
    -e REDISCLI_AUTH="${REDIS_PASSWORD:-changeme}" \
    -e PATTERNS="fe:*:ssr:* ${DEPLOY_CACHE_EXTRA_PATTERNS:-}" \
    -e BUMP_NS="${DEPLOY_CACHE_BUMP_NAMESPACES:-}" \
    redis sh -ec '
      set -f  # паттерны не глобить по файлам /data контейнера
      for pat in $PATTERNS; do
        case "$pat" in fe:ver:*|"*"|fe:\*) echo "    skip unsafe pattern $pat"; continue;; esac
        f=/tmp/release-cache-keys.$$
        redis-cli -n 0 --scan --pattern "$pat" --count 1000 > "$f"
        n=$(wc -l < "$f" | tr -d " ")
        xargs -r -n 500 redis-cli -n 0 UNLINK < "$f" > /dev/null
        rm -f "$f"
        echo "    unlinked ${n} keys matching ${pat}"
      done
      for ns in $BUMP_NS; do
        v=$(redis-cli -n 0 INCR "fe:ver:${ns}")
        echo "    bumped fe:ver:${ns} -> ${v}"
      done
    '
}

# Логи backend на время cutover+watch: `compose up`/rollback пересоздают
# контейнер, и json-file лог нового backend пропадает вместе с ним.
BACKEND_LOG_PID=""
start_backend_log() {
  local log="${DEPLOY_LOG_DIR:-/tmp}/backend-${NEW_SHA}.log"
  nohup docker compose logs -f --no-color --timestamps backend >> "$log" 2>&1 &
  BACKEND_LOG_PID=$!
  echo "    backend logs -> ${log} (pid ${BACKEND_LOG_PID})"
}
stop_backend_log() {
  if [ -n "${BACKEND_LOG_PID}" ]; then
    kill "${BACKEND_LOG_PID}" 2>/dev/null || true
    BACKEND_LOG_PID=""
  fi
}

rollback() {
  trap - ERR
  echo "==> ROLLBACK to ${PREV_SHA}"
  git reset --hard "${PREV_SHA}"
  docker tag "${PREV_BACKEND_IMAGE}" rosstat-backend
  docker tag "${PREV_FRONTEND_IMAGE}" rosstat-frontend
  # Снимок логов упавшего backend до пересоздания контейнера.
  docker compose logs --no-color --timestamps backend > "${DEPLOY_LOG_DIR:-/tmp}/backend-${NEW_SHA:-unknown}-rollback.log" 2>&1 || true
  stop_backend_log || true
  docker compose up -d frontend backend
  # HTML, отрендеренный новым кодом при том же asset_sig, не должен остаться
  # у старого backend. Best effort: провал не блокирует откат.
  invalidate_release_cache || echo "    WARN: не удалось инвалидировать SSR-кэш после отката"
  # Mark the restored release as newest before pruning, including when rolling
  # back after repeated unsuccessful deploy attempts.
  publish_frontend_assets "${PREV_FRONTEND_IMAGE}"
  python3 "${ASSET_WORK}/archive.py" prune --archive "$ASSET_ARCHIVE" --keep 3
  echo "    откат выполнен (образы ${PREV_SHA})"
  exit 1
}
# ERR catches compose/up failures too; previously set -e skipped rollback.
trap rollback ERR

# ── 4. Up + ожидание readiness (реальный /health/ready, Н-1) ──────────
echo "==> anti-scrape: каталог логов nginx для fail2ban (uid 101 = nginx)"
install -d -m 0755 /var/log/rosstat-nginx
chown 101:101 /var/log/rosstat-nginx

echo "==> docker compose up -d (все сервисы; тома postgres/redis-state не трогаем)"
# Не `down -v` и не `--renew-anon-volumes`: postgres_data и redis_state_data
# держат БД пользователей и сессии. Пересоздаются только сервисы, чей
# compose-конфиг изменился (лимиты backend/ClickHouse, том sitemap).
docker compose up -d
start_backend_log

# #13 cutover: frontend иногда оставался Created (не слушает :3000), а Caddy
# уже проксировал → публичный 502. Не ждём 180s «healthy» в пустоту —
# сразу start, и cutover успешен только при Running+healthy+local :3000.
ensure_frontend_running() {
  local cid state port_ok=0
  cid=$(docker compose ps -q frontend 2>/dev/null || true)
  if [ -z "$cid" ]; then
    echo "    frontend missing — compose up -d --no-deps frontend"
    docker compose up -d --no-deps frontend
    return
  fi
  state=$(docker inspect --format '{{.State.Status}}' "$cid" 2>/dev/null || echo unknown)
  # :3000 refuse while Status=running still means public 502 via Caddy.
  if [ "$state" = "running" ] && curl -sf -o /dev/null --max-time 2 http://127.0.0.1:3000/; then
    port_ok=1
  fi
  if [ "$state" = "running" ] && [ "$port_ok" = "1" ]; then
    return
  fi
  case "$state" in
    created|exited|dead|paused|running)
      echo "    frontend state=${state} :3000_ok=${port_ok} — compose up -d --no-deps frontend"
      docker compose up -d --no-deps frontend
      ;;
    *)
      echo "    frontend unexpected state=${state} :3000_ok=${port_ok} — compose up -d --no-deps frontend"
      docker compose up -d --no-deps frontend
      ;;
  esac
}
ensure_frontend_running

echo "==> waiting for readiness (до 300s: миграции + seed)"
ready=""
for _ in $(seq 1 60); do
  if curl -sf http://localhost:8000/api/v1/health/ready >/dev/null 2>&1; then
    ready=1; break
  fi
  sleep 5
done
[ -n "$ready" ] || { echo "FAIL: backend не стал ready за 300s"; docker compose logs backend --tail=50; rollback; }

# Frontend healthy до smoke: readiness-цикл выше ждёт только backend, а
# frontend пересоздаётся секундами позже — первый HTTPS-пробег гонки
# «health: starting» ловил 502/000 и ложно откатывал годный релиз.
echo "==> waiting for frontend Started+healthy+listening :3000 (до 180s)"
fe_ok=""
for _ in $(seq 1 36); do
  ensure_frontend_running
  fe_st=$(docker inspect --format '{{.State.Status}}' rosstat-frontend-1 2>/dev/null || echo unknown)
  fe=$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' rosstat-frontend-1 2>/dev/null || echo unknown)
  if [ "$fe_st" = "running" ] && [ "$fe" = "healthy" ] \
     && curl -sf -o /dev/null --max-time 3 http://127.0.0.1:3000/; then
    fe_ok=1; break
  fi
  echo "    frontend status=${fe_st} health=${fe} (ожидаем running+healthy+:3000)"
  sleep 5
done
if [ -z "$fe_ok" ]; then
  echo "FAIL: frontend не Started+healthy+listening за 180s"
  docker inspect --format 'status={{.State.Status}} health={{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' rosstat-frontend-1 2>/dev/null || true
  docker compose ps frontend || true
  docker compose logs frontend --tail=50
  rollback
fi

echo "==> cache Redis DB 0: SCAN+UNLINK только SSR HTML (fe:*:ssr:*); data-кэши, redis-state и DB 1 не трогаем"
invalidate_release_cache \
  || { echo "FAIL: не удалось инвалидировать SSR-кэш Redis DB 0"; rollback; }

docker compose ps --format 'table {{.Name}}\t{{.Status}}'

# ── 5. Расширенный smoke (О-6) ─────────────────────────────────────────
echo "==> smoke: data endpoint"
curl -sf http://localhost:8000/api/v1/indicators/cpi/data | head -c 200 | grep -q '"data"' \
  || { echo "FAIL: data endpoint пуст/сломан"; rollback; }
echo " ok"

echo "==> smoke: SSR asset-hash consistency"
# Asset-hash trap: SSR HTML обязан ссылаться на ассеты, реально лежащие в frontend-образе.
ASSET=$(curl -sf -A 'Mozilla/5.0 (compatible; YandexBot/3.0)' http://localhost:3000/ \
  | grep -o '/assets/[a-zA-Z0-9._-]*\.js' | head -1)
if [ -z "$ASSET" ]; then echo "FAIL: SSR HTML без ассетов"; rollback; fi
curl -sf -o /dev/null "http://localhost:3000${ASSET}" \
  || { echo "FAIL: SSR ссылается на несуществующий ассет ${ASSET} (asset-hash trap)"; rollback; }
echo "    ok (${ASSET})"

echo "==> smoke: previous release asset"
curl -sf -o "${ASSET_WORK}/retained-probe" "http://localhost:3000/assets/${RETAINED_PROBE}" \
  && cmp -s "${ASSET_WORK}/retained-probe" "${ASSET_ARCHIVE}/assets/${RETAINED_PROBE}" \
  || { echo "FAIL: старый ассет недоступен или заменён HTML: ${RETAINED_PROBE}"; rollback; }
echo "    ok (${RETAINED_PROBE})"

echo "==> smoke: OG image"
curl -sf -o /dev/null http://localhost:3000/og/cpi.png || { echo "FAIL: OG image"; rollback; }
echo "    ok"

# ── 6. Caddy reload — только после успешного smoke (О-7) ──────────────
echo "==> sync Caddyfile"
if ! diff -q /opt/rosstat/Caddyfile /etc/caddy/Caddyfile >/dev/null 2>&1; then
  cp /opt/rosstat/Caddyfile /etc/caddy/Caddyfile
  systemctl reload caddy
  echo "    Caddy reloaded"
else
  echo "    Caddyfile unchanged, skip"
fi

echo "==> smoke: HTTPS dual-host через Caddy"
# Ретраи: одиночный 000/502 (транзиент TLS/рестарт Caddy-апстрима) не должен
# откатывать годный релиз; реальная деградация не пройдёт 4 пробы подряд.
https_probe() {
  local url="$1" pattern="$2" attempt
  for attempt in 1 2 3 4; do
    if [ -n "$pattern" ]; then
      curl -sf -m 30 -A 'YandexBot/3.0' "$url" | grep -q "$pattern" && return 0
    else
      curl -sf -m 30 -o /dev/null "$url" && return 0
    fi
    sleep 5
  done
  return 1
}
for host in forecasteconomy.com ru.forecasteconomy.com; do
  https_probe "https://${host}/api/v1/health" "" \
    || { echo "FAIL: HTTPS smoke ${host}"; rollback; }
done
# Canonical: apex всегда self. ru. до cutover каноничен на apex (Р-А);
# после apex EN — self на ru. (hreflang тоже содержит apex URL — не greпать его).
https_probe "https://forecasteconomy.com/russia/indicator/cpi" \
  'rel="canonical" href="https://forecasteconomy.com/russia/indicator/cpi"' \
  || { echo "FAIL: canonical/SSR smoke apex"; rollback; }
RU_CANON='rel="canonical" href="https://forecasteconomy.com/russia/indicator/cpi"'
if grep -qE '^RUSTATS_APEX_LOCALE_EN=(true|1)' .env; then
  RU_CANON='rel="canonical" href="https://ru.forecasteconomy.com/russia/indicator/cpi"'
fi
https_probe "https://ru.forecasteconomy.com/russia/indicator/cpi" "${RU_CANON}" \
  || { echo "FAIL: canonical/SSR smoke ru."; rollback; }
# Гейт-скрипту нужны httpx/bs4: берём выделенный venv на хосте (вне репозитория,
# чтобы не грязнить git-дерево), системный python3 — фолбэк.
GATE_PY="python3"
for candidate in /opt/gate-venv/bin/python /opt/rosstat/.venv/bin/python; do
  if [ -x "$candidate" ] && "$candidate" -c "import httpx, bs4" >/dev/null 2>&1; then
    GATE_PY="$candidate"; break
  fi
done
"$GATE_PY" scripts/dual-host-release-gate.py \
  --ru-origin=https://ru.forecasteconomy.com \
  --en-origin=https://forecasteconomy.com \
  || { echo "FAIL: dual-host release gate"; rollback; }

# ── 6b. 15-минутный post-deploy watch (инцидент 2026-09-03: OOM после smoke) ──
# 2026-09-04: один curl -m 5 на /health/ready во время всплеска SSR (ферма)
# дал ready=0 при живом сайте (TTFB 4.5 с) и откатил зелёный MJ12-деплой.
# Min 14 того же окна: TTFB 6.7 с при ready=1 и RSS ~870MiB (скачок памяти
# ~11-й минуты, пересечение с 15-мин rollup) — снова ложный откат.
# Ready — до 3 попыток по 8 с; TTFB — до 3 замеров, откат только если все ≥5 с.
# OOM по-прежнему мгновенный откат.
echo "==> post-deploy watch 15 min"
WATCH_FAIL=0
for i in $(seq 1 15); do
  TTFB=99
  HOME_DIAG=""
  for _try in 1 2 3; do
    # rc 28 = таймаут -m 8 (висит), 7 = connection refused, 52/56 = обрыв.
    rc=0
    out=$(curl -o /dev/null -s -w '%{http_code} %{time_starttransfer}' -m 8 -A 'YandexBot/3.0' https://forecasteconomy.com/) || rc=$?
    code=${out%% *}
    t=${out##* }
    [ "$rc" = 0 ] || t=99
    HOME_DIAG="${HOME_DIAG}${HOME_DIAG:+,}rc=${rc}/http=${code:-000}/t=${t}"
    TTFB=$t
    python3 - "$t" <<'PY' && break
import sys
try:
    sys.exit(0 if float(sys.argv[1]) < 5 else 1)
except ValueError:
    sys.exit(1)
PY
    sleep 2
  done
  READY=0
  READY_DIAG=""
  for _try in 1 2 3; do
    rc=0
    body=$(curl -s -m 8 -w '\n%{http_code} %{time_total}' http://127.0.0.1:8000/api/v1/health/ready) || rc=$?
    meta=${body##*$'\n'}
    READY_DIAG="${READY_DIAG}${READY_DIAG:+,}rc=${rc}/http=${meta%% *}/t=${meta##* }"
    if [ "$rc" = 0 ] && printf '%s' "$body" | grep -qE '"status": ?"ok"'; then
      READY=1
      break
    fi
    # Какая проверка не прошла (db/redis/scheduler) — в лог, не только ready=0.
    printf '%s' "$body" | grep -o '"checks":{[^}]*}' | head -c 300 | sed 's/^/      ready checks: /' || true
    sleep 2
  done
  OOM=$(docker inspect rosstat-backend-1 --format '{{.State.OOMKilled}}' 2>/dev/null || echo unknown)
  MEM=$(docker stats --no-stream --format '{{.MemUsage}}' rosstat-backend-1 2>/dev/null || echo n/a)
  echo "    min ${i}: ttfb=${TTFB}s ready=${READY} oom=${OOM} mem=${MEM} home[${HOME_DIAG}] ready[${READY_DIAG}]"
  python3 - "${TTFB}" <<'PY' || WATCH_FAIL=1
import sys
try:
    t = float(sys.argv[1])
except ValueError:
    sys.exit(1)
sys.exit(0 if t < 5 else 1)
PY
  if [ "${READY}" != "1" ]; then WATCH_FAIL=1; fi
  if [ "${OOM}" = "true" ]; then WATCH_FAIL=1; fi
  if [ "${WATCH_FAIL}" = "1" ]; then
    echo "FAIL: post-deploy watch"; rollback; exit 1
  fi
  sleep 60
done
echo "    watch ok"
stop_backend_log

echo "==> assets: retain three accepted/recent frontend builds"
python3 "${ASSET_WORK}/archive.py" prune --archive "$ASSET_ARCHIVE" --keep 3
trap - ERR

# ── 7. Чистка старых версионированных образов (держим 3 последних) ────
docker images 'rosstat-backend' --format '{{.Tag}}' | grep -v '^latest$' | tail -n +4 \
  | xargs -r -I{} docker rmi "rosstat-backend:{}" "rosstat-frontend:{}" 2>/dev/null || true

echo "==> deploy ${NEW_SHA} complete"
