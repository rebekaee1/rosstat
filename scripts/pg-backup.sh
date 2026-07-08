#!/bin/bash
# Ежедневный бэкап Postgres с ротацией (ADR-0007 Phase 2).
#
# Делает два артефакта:
#   1) Полный custom-dump всей БД (.dump) — основной бэкап для восстановления.
#   2) Отдельный data-only SQL identity-таблиц (.identity.sql.gz) — подстраховка
#      «пользователи никогда не теряются» (users / email_credentials /
#      oauth_identities / consents / auth_audit). Plain SQL читается глазами и
#      грузится в любую новую БД независимо от схемы.
#
# Персистентность БД между редеплоями обеспечивает docker volume `postgres_data`
# (см. docker-compose.yml). Этот скрипт — дополнительный слой на случай порчи тома.
#
# Восстановление (полный dump):
#   docker compose exec -T postgres pg_restore -U rustats -d rustats --clean --if-exists < FILE.dump
# Восстановление только пользователей (identity SQL):
#   gunzip -c FILE.identity.sql.gz | docker compose exec -T postgres psql -U rustats -d rustats
#
# Cron (прод): 0 4 * * *  /opt/rosstat/scripts/pg-backup.sh >> /var/log/pg-backup.log 2>&1
#
# Наблюдаемость (Н-10): heartbeat в Telegram при успехе (размеры дампов) и
# алерт при любом сбое (trap ERR). Токен/чат берутся из .env compose-каталога
# (RUSTATS_TELEGRAM_BOT_TOKEN / RUSTATS_TELEGRAM_CHAT_ID); без них скрипт
# работает молча, как раньше.
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/opt/rosstat/backups}"
KEEP_DAYS="${KEEP_DAYS:-14}"
DB_NAME="rustats"
DB_USER="rustats"
COMPOSE_DIR="${COMPOSE_DIR:-/opt/rosstat}"
IDENTITY_TABLES="users email_credentials oauth_identities consents auth_audit"

# Telegram-креды: из окружения или из .env compose-каталога.
if [ -z "${RUSTATS_TELEGRAM_BOT_TOKEN:-}" ] && [ -f "$COMPOSE_DIR/.env" ]; then
  RUSTATS_TELEGRAM_BOT_TOKEN=$(grep -E '^RUSTATS_TELEGRAM_BOT_TOKEN=' "$COMPOSE_DIR/.env" | cut -d= -f2- || true)
  RUSTATS_TELEGRAM_CHAT_ID=$(grep -E '^RUSTATS_TELEGRAM_CHAT_ID=' "$COMPOSE_DIR/.env" | cut -d= -f2- || true)
fi

tg_notify() {
  # $1 — текст. Никогда не роняет бэкап: сбой отправки игнорируется.
  [ -n "${RUSTATS_TELEGRAM_BOT_TOKEN:-}" ] && [ -n "${RUSTATS_TELEGRAM_CHAT_ID:-}" ] || return 0
  curl -sS -m 10 -o /dev/null \
    "https://api.telegram.org/bot${RUSTATS_TELEGRAM_BOT_TOKEN}/sendMessage" \
    -d chat_id="${RUSTATS_TELEGRAM_CHAT_ID}" \
    --data-urlencode text="$1" || true
}

on_error() {
  tg_notify "🔴 pg-backup FAILED on $(hostname) at $(date '+%F %T') (line $1). Проверь /var/log/pg-backup.log"
}
trap 'on_error $LINENO' ERR

mkdir -p "$BACKUP_DIR"

STAMP=$(date +%Y%m%d_%H%M%S)
FILE="$BACKUP_DIR/${DB_NAME}_${STAMP}.dump"
IDENTITY_FILE="$BACKUP_DIR/${DB_NAME}_${STAMP}.identity.sql.gz"

dc() { docker compose -f "$COMPOSE_DIR/docker-compose.yml" "$@"; }

# 1) Полный бэкап всей БД (включает identity-таблицы).
dc exec -T postgres pg_dump -Fc -U "$DB_USER" "$DB_NAME" > "$FILE"
SIZE=$(du -h "$FILE" | cut -f1)
echo "[$(date)] Full backup: $FILE ($SIZE)"

# 2) Подстраховка: data-only dump только identity-таблиц в plain SQL.
TABLE_FLAGS=""
for t in $IDENTITY_TABLES; do TABLE_FLAGS="$TABLE_FLAGS -t $t"; done
# shellcheck disable=SC2086
dc exec -T postgres pg_dump -U "$DB_USER" "$DB_NAME" --data-only --no-owner --column-inserts $TABLE_FLAGS \
  | gzip > "$IDENTITY_FILE"
ISIZE=$(du -h "$IDENTITY_FILE" | cut -f1)
echo "[$(date)] Identity backup: $IDENTITY_FILE ($ISIZE)"

# О-1: offsite-копия в S3-совместимое хранилище (Яндекс Object Storage).
# Бэкапы на том же диске, что и БД, — потеря диска теряет всё; offsite чинит.
# Включение — три переменные в /opt/rosstat/.env (или окружении cron):
#   OFFSITE_S3_BUCKET=s3://имя-бакета/pg-backups
#   OFFSITE_S3_ENDPOINT=https://storage.yandexcloud.net
#   + креды для aws cli (AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY в env,
#     либо профиль в ~/.aws/credentials).
# Без переменных шаг пропускается (dev). Сбой заливки ловит trap ERR → алерт.
if [ -z "${OFFSITE_S3_BUCKET:-}" ] && [ -f "$COMPOSE_DIR/.env" ]; then
  OFFSITE_S3_BUCKET=$(grep -E '^OFFSITE_S3_BUCKET=' "$COMPOSE_DIR/.env" | cut -d= -f2- || true)
  OFFSITE_S3_ENDPOINT=$(grep -E '^OFFSITE_S3_ENDPOINT=' "$COMPOSE_DIR/.env" | cut -d= -f2- || true)
fi
if [ -n "${OFFSITE_S3_BUCKET:-}" ]; then
  if command -v aws >/dev/null 2>&1; then
    aws s3 cp "$FILE" "$OFFSITE_S3_BUCKET/" ${OFFSITE_S3_ENDPOINT:+--endpoint-url "$OFFSITE_S3_ENDPOINT"} --only-show-errors
    aws s3 cp "$IDENTITY_FILE" "$OFFSITE_S3_BUCKET/" ${OFFSITE_S3_ENDPOINT:+--endpoint-url "$OFFSITE_S3_ENDPOINT"} --only-show-errors
    echo "[$(date)] Offsite copy uploaded to $OFFSITE_S3_BUCKET"
  else
    tg_notify "🟡 pg-backup: OFFSITE_S3_BUCKET задан, но aws cli не установлен — offsite-копии нет"
  fi
fi

# Ротация: чистим всё старше KEEP_DAYS.
find "$BACKUP_DIR" -name "*.dump" -mtime +"$KEEP_DAYS" -delete
find "$BACKUP_DIR" -name "*.sql.gz" -mtime +"$KEEP_DAYS" -delete
echo "[$(date)] Cleaned backups older than $KEEP_DAYS days"

# Heartbeat: успех виден в Telegram, а не только в логе на сервере.
tg_notify "🟢 pg-backup ok: full $SIZE, identity $ISIZE ($(date '+%F %T'))"

# Н-25: machine-readable heartbeat в cache-Redis — /api/v1/health/ready
# помечает degraded, если бэкап старше 30 часов (cron не сработал/сломан crontab
# — Telegram-алерта не будет, trap ERR не запускавшийся скрипт не поймает).
# Дефолт "changeme" ЗЕРКАЛИТ docker-compose.yml (`${REDIS_PASSWORD:-changeme}`
# у команды redis-server) — без него на инсталляциях без явного REDIS_PASSWORD
# в .env (как прод на 2026-07-08) SET уходил в NOAUTH и молча проглатывался
# `|| true`: heartbeat никогда не писался, health/ready вечно отдавал "never".
REDIS_PASS=$(grep -E '^REDIS_PASSWORD=' "$COMPOSE_DIR/.env" 2>/dev/null | cut -d= -f2-)
REDIS_PASS="${REDIS_PASS:-changeme}"
if ! dc exec -T redis redis-cli -a "$REDIS_PASS" --no-auth-warning \
  SET fe:ops:pg_backup_last_ok "$(date +%s)" >/dev/null 2>&1; then
  echo "[$(date)] WARN: pg_backup heartbeat SET в Redis не прошёл (не влияет на бэкап)" >&2
fi
