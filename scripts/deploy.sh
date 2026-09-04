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
docker compose build frontend backend
docker tag rosstat-backend "rosstat-backend:${NEW_SHA}"
docker tag rosstat-frontend "rosstat-frontend:${NEW_SHA}"

rollback() {
  echo "==> ROLLBACK to ${PREV_SHA}"
  git reset --hard "${PREV_SHA}"
  if docker image inspect "rosstat-backend:${PREV_SHA}" >/dev/null 2>&1; then
    docker tag "rosstat-backend:${PREV_SHA}" rosstat-backend
    docker tag "rosstat-frontend:${PREV_SHA}" rosstat-frontend
    docker compose up -d frontend backend
    echo "    откат выполнен (образы ${PREV_SHA})"
  else
    echo "    образов ${PREV_SHA} нет — пересобираю из git"
    docker compose build frontend backend && docker compose up -d frontend backend
  fi
  exit 1
}

# ── 4. Up + ожидание readiness (реальный /health/ready, Н-1) ──────────
echo "==> anti-scrape: каталог логов nginx для fail2ban (uid 101 = nginx)"
install -d -m 0755 /var/log/rosstat-nginx
chown 101:101 /var/log/rosstat-nginx

echo "==> docker compose up -d (все сервисы; тома postgres/redis-state не трогаем)"
# Не `down -v` и не `--renew-anon-volumes`: postgres_data и redis_state_data
# держат БД пользователей и сессии. Пересоздаются только сервисы, чей
# compose-конфиг изменился (лимиты backend/ClickHouse, том sitemap).
docker compose up -d

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
echo "==> waiting for frontend healthy (до 180s)"
fe_ok=""
for _ in $(seq 1 36); do
  fe=$(docker inspect --format '{{.State.Health.Status}}' rosstat-frontend-1 2>/dev/null || echo unknown)
  [ "$fe" = "healthy" ] && { fe_ok=1; break; }
  sleep 5
done
[ -n "$fe_ok" ] || { echo "FAIL: frontend не стал healthy за 180s"; docker compose logs frontend --tail=50; rollback; }

echo "==> cache Redis DB 0 FLUSHDB (SSR/asset-hash); redis-state и DB 1 не трогаем"
REDIS_PASSWORD="$(grep '^REDIS_PASSWORD=' .env | cut -d= -f2- | tr -d '\"' | tr -d "'")"
docker compose exec -T redis redis-cli -a "${REDIS_PASSWORD:-changeme}" -n 0 FLUSHDB >/dev/null \
  || { echo "FAIL: не удалось сбросить кэш Redis DB 0"; rollback; }

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
# Ready — до 3 попыток по 8 с; OOM и устойчивый TTFB≥5 с по-прежнему откат.
echo "==> post-deploy watch 15 min"
WATCH_FAIL=0
for i in $(seq 1 15); do
  TTFB=$(curl -o /dev/null -s -w '%{time_starttransfer}' -m 8 -A 'YandexBot/3.0' https://forecasteconomy.com/ || echo 99)
  READY=0
  for _try in 1 2 3; do
    if curl -sf -m 8 http://127.0.0.1:8000/api/v1/health/ready | grep -qE '"status": ?"ok"'; then
      READY=1
      break
    fi
    sleep 2
  done
  OOM=$(docker inspect rosstat-backend-1 --format '{{.State.OOMKilled}}' 2>/dev/null || echo unknown)
  MEM=$(docker stats --no-stream --format '{{.MemUsage}}' rosstat-backend-1 2>/dev/null || echo n/a)
  echo "    min ${i}: ttfb=${TTFB}s ready=${READY} oom=${OOM} mem=${MEM}"
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

# ── 7. Чистка старых версионированных образов (держим 3 последних) ────
docker images 'rosstat-backend' --format '{{.Tag}}' | grep -v '^latest$' | tail -n +4 \
  | xargs -r -I{} docker rmi "rosstat-backend:{}" "rosstat-frontend:{}" 2>/dev/null || true

echo "==> deploy ${NEW_SHA} complete"
