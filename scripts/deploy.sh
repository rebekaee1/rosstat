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

echo "==> docker compose up -d"
docker compose up -d frontend backend

echo "==> waiting for readiness (до 300s: миграции + seed)"
ready=""
for _ in $(seq 1 60); do
  if curl -sf http://localhost:8000/api/v1/health/ready >/dev/null 2>&1; then
    ready=1; break
  fi
  sleep 5
done
[ -n "$ready" ] || { echo "FAIL: backend не стал ready за 300s"; docker compose logs backend --tail=50; rollback; }
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

echo "==> smoke: HTTPS через Caddy"
curl -sf -o /dev/null https://forecasteconomy.com/api/v1/health \
  || echo "WARN: HTTPS smoke не прошёл (проверь Caddy руками)"

# ── 7. Чистка старых версионированных образов (держим 3 последних) ────
docker images 'rosstat-backend' --format '{{.Tag}}' | grep -v '^latest$' | tail -n +4 \
  | xargs -r -I{} docker rmi "rosstat-backend:{}" "rosstat-frontend:{}" 2>/dev/null || true

echo "==> deploy ${NEW_SHA} complete"
