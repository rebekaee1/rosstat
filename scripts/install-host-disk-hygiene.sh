#!/usr/bin/env bash
# Диск боевого хоста: потолок journald, еженедельная уборка кэша сборки Docker.
# Запускать на сервере из /opt/rosstat под root. Идемпотентен.
#   scripts/install-host-disk-hygiene.sh --dry-run   # показать, что будет установлено
#   scripts/install-host-disk-hygiene.sh             # установить
#   scripts/install-host-disk-hygiene.sh --rollback  # убрать drop-in journald и cron (удалённые журналы и кэш не вернуть)
#
# Основание (замеры 2026-10-27, диск 77 ГБ, занято 88 %): кэш сборки Docker 16,1 ГБ
# без единой активной записи (docker-cleanup.sh не стоял в cron и не чистил без -a),
# journald 2,0 ГБ без явного предела (journald.conf пуст), fail2ban.log ~800 МБ
# (см. deploy/fail2ban/fail2ban.local).
#
# Что НЕ делает: не трогает тома с данными, бэкапы, nginx-логи; первую большую
# чистку кэша (~4–16 ГБ) делает владелец вручную: scripts/docker-cleanup.sh
set -euo pipefail
cd "$(dirname "$0")/.."

DRY=0
[[ "${1:-}" == "--dry-run" ]] && DRY=1

JOURNALD_DROPIN=/etc/systemd/journald.conf.d/rosstat.conf
CRON_FILE=/etc/cron.d/rosstat-docker-cleanup

if [[ "${1:-}" == "--rollback" ]]; then
  [[ $EUID -eq 0 ]] || { echo "нужен root" >&2; exit 1; }
  rm -f "$JOURNALD_DROPIN" "$CRON_FILE"
  systemctl restart systemd-journald
  echo "Убраны $JOURNALD_DROPIN и $CRON_FILE; journald снова с лимитами по умолчанию."
  exit 0
fi

JOURNALD_BODY='[Journal]
# Потолок журнала systemd: 2,0 ГБ без предела на диске, общем с Postgres.
SystemMaxUse=500M
MaxRetentionSec=14day
'
# Воскресенье 05:00 UTC — после ночного pg-backup (04:00). Если идёт деплой,
# скрипт сам выходит (lock /var/lock/rosstat-deploy.lock).
CRON_BODY='0 5 * * 0 root cd /opt/rosstat && ./scripts/docker-cleanup.sh >> /var/log/docker-cleanup.log 2>&1
'

echo "== диск сейчас"; df -h / | tail -1; journalctl --disk-usage || true
echo "== будет записано: $JOURNALD_DROPIN"; printf '%s' "$JOURNALD_BODY"
echo "== будет записано: $CRON_FILE"; printf '%s' "$CRON_BODY"
[[ $DRY -eq 1 ]] && exit 0

[[ $EUID -eq 0 ]] || { echo "нужен root" >&2; exit 1; }
install -d -m 0755 /etc/systemd/journald.conf.d
printf '%s' "$JOURNALD_BODY" > "$JOURNALD_DROPIN"; chmod 0644 "$JOURNALD_DROPIN"
printf '%s' "$CRON_BODY" > "$CRON_FILE"; chmod 0644 "$CRON_FILE"
systemctl restart systemd-journald
# Вакуум стирает самые старые журналы systemd (в том числе строки ssh/сервисов) сверх 500 МБ — это и есть цель.
journalctl --vacuum-size=500M || true
echo "Готово. Диск:"; df -h / | tail -1
echo "Первую большую чистку кэша сборки Docker (4–16 ГБ) делает владелец вручную и с замером:"
echo "  scripts/docker-cleanup.sh --dry-run   # затем   scripts/docker-cleanup.sh   и   df -h /" 
