#!/usr/bin/env bash
# F08: установить на ХОСТ конфиг ротации nginx-логов из репозитория (rename + USR1, 7 дней без сжатия).
# Запускать на сервере из /opt/rosstat под root. Сначала dry-run (`logrotate -d`), старый конфиг сохраняется.
#   scripts/install-host-logrotate.sh            # dry-run + установка
#   scripts/install-host-logrotate.sh --dry-run  # только показать
set -euo pipefail
cd "$(dirname "$0")/.."
SRC=deploy/fail2ban/logrotate-rosstat-nginx
DST=/etc/logrotate.d/rosstat-nginx
[[ -f "$SRC" ]] || { echo "нет $SRC" >&2; exit 1; }
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
