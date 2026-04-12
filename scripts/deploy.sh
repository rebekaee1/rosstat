#!/usr/bin/env bash
# Deploy forecasteconomy.com — pull, build, sync Caddy, restart.
# Usage: ssh root@5.129.204.194 'bash /opt/rosstat/scripts/deploy.sh'
set -euo pipefail

cd /opt/rosstat

echo "==> git pull"
git pull origin main

echo "==> docker compose build"
docker compose build frontend backend

echo "==> sync Caddyfile → /etc/caddy/"
if ! diff -q /opt/rosstat/Caddyfile /etc/caddy/Caddyfile >/dev/null 2>&1; then
  cp /opt/rosstat/Caddyfile /etc/caddy/Caddyfile
  echo "    Caddyfile updated, reloading Caddy..."
  systemctl reload caddy
  echo "    Caddy reloaded"
else
  echo "    Caddyfile unchanged, skip"
fi

echo "==> docker compose up -d"
docker compose up -d frontend backend

echo "==> waiting for healthy..."
sleep 5
docker compose ps --format 'table {{.Name}}\t{{.Status}}'

echo "==> smoke test"
curl -sf http://localhost:8000/api/v1/health || { echo "FAIL: backend health"; exit 1; }
echo ""
curl -sf http://localhost:3000/health || { echo "FAIL: frontend health"; exit 1; }
echo ""

echo "==> deploy complete"
