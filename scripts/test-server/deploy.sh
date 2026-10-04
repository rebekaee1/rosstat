#!/usr/bin/env bash
# Выкладка коммита на ТЕСТОВЫЙ сервер (демо-стенд за Cloudflare). Порядок и причины — docs/workflow.md,
# раздел «Тестовый сервер». Без push: код едет git bundle поверх SHA, уже стоящего на сервере.
#
#   scripts/test-server/deploy.sh [REF]          # по умолчанию HEAD; собирает образы и перезапускает
#   scripts/test-server/deploy.sh REF --no-build # только переключить код и перезапустить
#
# Боевой сервер этим скриптом не трогается; адрес прода запрещён защитой ниже.
set -euo pipefail

HOST="${FE_TEST_HOST:-root@176.57.220.170}"
KEY="${FE_TEST_KEY:-$HOME/.ssh/id_ed25519_fe_demo}"
APP_DIR=/opt/rosstat
REF="${1:-HEAD}"
BUILD=1
[[ "${2:-}" == "--no-build" ]] && BUILD=0

case "$HOST" in *201.51.11.170*) echo "Отказ: это адрес боевого сервера." >&2; exit 2;; esac
cd "$(git rev-parse --show-toplevel)"
SSH=(ssh -o BatchMode=yes -o IdentitiesOnly=yes -o ConnectTimeout=20 -i "$KEY" "$HOST")
SCP=(scp -q -o BatchMode=yes -o IdentitiesOnly=yes -i "$KEY")

SHA="$(git rev-parse "$REF^{commit}")"
REMOTE_SHA="$("${SSH[@]}" "cd $APP_DIR && git rev-parse HEAD")"
echo "== сервер: ${REMOTE_SHA:0:9}  →  цель: ${SHA:0:9}"
if [[ "$REMOTE_SHA" == "$SHA" && $BUILD -eq 0 ]]; then echo "Уже на этом SHA."; fi

# 1. Код: инкрементальный bundle от SHA сервера (если он предок цели), иначе полный.
if [[ "$REMOTE_SHA" == "$SHA" ]]; then
  echo "Код уже на сервере — пропускаю передачу, только сборка и перезапуск."
else
  BR=fe-test-deploy
  git branch -f "$BR" "$SHA" >/dev/null
  WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"; git branch -D "$BR" >/dev/null 2>&1 || true' EXIT
  if git cat-file -e "$REMOTE_SHA^{commit}" 2>/dev/null && git merge-base --is-ancestor "$REMOTE_SHA" "$SHA"; then
    git bundle create "$WORK/fe.bundle" "$REMOTE_SHA..$BR" >/dev/null
  else
    echo "SHA сервера не предок цели — полный bundle"
    git bundle create "$WORK/fe.bundle" "$BR" >/dev/null
  fi
  "${SCP[@]}" "$WORK/fe.bundle" "$HOST:/root/fe-deploy.bundle"
  "${SSH[@]}" "cd $APP_DIR && git fetch -q /root/fe-deploy.bundle $BR:refs/heads/$BR --force && git checkout -q --detach $SHA && git rev-parse --short HEAD"
fi

# 2. Образы (host-сеть задана в docker-compose.override.yml; без неё pip/npm таймаутят) и перезапуск.
if [[ $BUILD -eq 1 ]]; then
  "${SSH[@]}" "cd $APP_DIR && docker compose build backend frontend" 2>&1 | tail -3
fi
"${SSH[@]}" "cd $APP_DIR && docker compose up -d backend scheduler frontend 2>&1 | tail -4"

# 3. Готовность и дымовая проверка по локальному порту и по туннелю.
for i in $(seq 1 40); do
  code="$("${SSH[@]}" "curl -s -m 5 -o /dev/null -w '%{http_code}' http://127.0.0.1/api/v1/health/ready" || true)"
  [[ "$code" == "200" ]] && break
  sleep 6
done
echo "ready: $code"
URL="$("${SSH[@]}" "cat /root/fe-demo-tunnel.url 2>/dev/null || true")"
echo "туннель: ${URL:-не найден}"
"${SSH[@]}" "cd $APP_DIR && docker compose ps --format 'table {{.Service}}\t{{.Status}}'"
[[ "$code" == "200" ]] || { echo "Backend не стал готов за 4 минуты — смотри docker compose logs backend." >&2; exit 1; }
