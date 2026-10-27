#!/usr/bin/env bash
# F08 (редакция 2026-10-27): установить на ХОСТ конфиг ротации nginx-логов из репозитория:
# rename + USR1 (без копирования), 14 суток, сжатие на следующие сутки с самым низким приоритетом
# CPU/диска (ionice -c3 + nice -n19 + gzip -6). Конфиг проверен на logrotate 3.21 (как на проде) в
# контейнере Ubuntu 24.04: разбор, rename, delaycompress, корректный gzip, владелец 101:101, USR1.
# Запускать на сервере из /opt/rosstat под root. Сначала dry-run (`logrotate -d`), старый конфиг сохраняется.
#   scripts/install-host-logrotate.sh            # dry-run + установка
#   scripts/install-host-logrotate.sh --dry-run  # только показать
#   scripts/install-host-logrotate.sh --rollback # вернуть самый свежий /etc/logrotate.d/rosstat-nginx.before-f08-*
set -euo pipefail
cd "$(dirname "$0")/.."
SRC=deploy/fail2ban/logrotate-rosstat-nginx
DST=/etc/logrotate.d/rosstat-nginx
if [[ "${1:-}" == "--rollback" ]]; then
  LAST="$(ls -1t "$DST".before-f08-* 2>/dev/null | head -1 || true)"
  [[ -n "$LAST" ]] || { echo "нет резервной копии $DST.before-f08-*" >&2; exit 1; }
  cp -a "$LAST" "$DST"
  echo "Возвращён $LAST -> $DST"
  exit 0
fi
[[ -f "$SRC" ]] || { echo "нет $SRC" >&2; exit 1; }
command -v ionice >/dev/null || { echo "нет ionice (util-linux): compresscmd конфига не сработает" >&2; exit 1; }
docker ps --format '{{.Names}}' | grep -qx rosstat-frontend-1 || { echo "контейнер rosstat-frontend-1 не запущен: postrotate не сможет послать USR1" >&2; exit 1; }
df -h /var/log | tail -1; df -i /var/log | tail -1
echo "== dry-run нового конфига"
logrotate -d "$SRC" 2>&1 | tail -15
[[ "${1:-}" == "--dry-run" ]] && exit 0
if [[ -f "$DST" ]] && ! cmp -s "$SRC" "$DST"; then
  cp -a "$DST" "$DST.before-f08-$(date +%Y%m%d)"
  echo "старый конфиг сохранён: $DST.before-f08-$(date +%Y%m%d)"
fi
install -m 644 "$SRC" "$DST"
echo "Установлено. Первая ротация — в 00:00 хоста (cron.daily/logrotate.timer). Проверка утром:"
echo "  ls -la /var/log/rosstat-nginx/; docker exec rosstat-frontend-1 nginx -t; fail2ban-client status | head"
