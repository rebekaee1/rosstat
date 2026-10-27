#!/bin/bash
# Ежедневный бэкап Postgres с ротацией (ADR-0007 Phase 2).
#
# Делает два артефакта:
#   1) Полный custom-dump всей БД (.dump) — основной бэкап для восстановления.
#   2) Отдельный data-only SQL identity-таблиц (.identity.sql.gz) — подстраховка
#      «пользователи никогда не теряются» (users / email_credentials /
#      oauth_identities / consents / auth_audit + кабинет: user_saved_items /
#      user_watches / user_exports / user_preferences). Plain SQL читается глазами и
#      требует заранее созданной совместимой схемы и проверки связности.
#
# Персистентность БД между редеплоями обеспечивает docker volume `postgres_data`
# (см. docker-compose.yml). Этот скрипт — дополнительный слой на случай порчи тома.
#
# Проверочное восстановление — в отдельный изолированный контейнер/том,
# не поверх рабочей БД. Полный рецепт: docs/workflow.md::Git и окружения.
# Identity SQL требует отдельной чистой совместимой схемы.
#
# Cron (снимок 2026-09-27): 0 4 * * * /opt/rosstat/scripts/pg-backup.sh
# Host timezone Etc/UTC: это 04:00 UTC / 07:00 МСК; TZ backend cron не меняет.
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
IDENTITY_TABLES="users email_credentials oauth_identities consents auth_audit user_saved_items user_watches user_exports user_preferences"

# Telegram-креды: из окружения или из .env compose-каталога.
if [ -z "${RUSTATS_TELEGRAM_BOT_TOKEN:-}" ] && [ -f "$COMPOSE_DIR/.env" ]; then
  RUSTATS_TELEGRAM_BOT_TOKEN=$(grep -E '^RUSTATS_TELEGRAM_BOT_TOKEN=' "$COMPOSE_DIR/.env" | cut -d= -f2- || true)
  RUSTATS_TELEGRAM_CHAT_ID=$(grep -E '^RUSTATS_TELEGRAM_CHAT_ID=' "$COMPOSE_DIR/.env" | cut -d= -f2- || true)
fi

if [ -z "${RUSTATS_TELEGRAM_PROXY_URL:-}" ] && [ -f "$COMPOSE_DIR/.env" ]; then
  RUSTATS_TELEGRAM_PROXY_URL=$(grep -E '^RUSTATS_TELEGRAM_PROXY_URL=' "$COMPOSE_DIR/.env" | cut -d= -f2- || true)
  # .env may quote the URL. Read it as data, never source/eval credentials.
  case "$RUSTATS_TELEGRAM_PROXY_URL" in
    \'*\'|\"*\") RUSTATS_TELEGRAM_PROXY_URL="${RUSTATS_TELEGRAM_PROXY_URL:1:${#RUSTATS_TELEGRAM_PROXY_URL}-2}" ;;
  esac
fi

tg_notify() {
  # $1 — текст. Никогда не роняет бэкап: сбой отправки игнорируется.
  [ -n "${RUSTATS_TELEGRAM_BOT_TOKEN:-}" ] && [ -n "${RUSTATS_TELEGRAM_CHAT_ID:-}" ] || return 0
  local proxy_option="${RUSTATS_TELEGRAM_PROXY_URL:-}" proxy_config=""
  if [ -n "$proxy_option" ]; then
    proxy_option=${proxy_option//\\/\\\\}
    proxy_option=${proxy_option//\"/\\\"}
    proxy_config="proxy = \"${proxy_option}\""$'\n'
  fi
  # Proxy credentials travel on stdin, not in process-list arguments.
  printf '%s' "$proxy_config" | curl --config - --fail -sS -m 10 -o /dev/null \
    "https://api.telegram.org/bot${RUSTATS_TELEGRAM_BOT_TOKEN}/sendMessage" \
    -d chat_id="${RUSTATS_TELEGRAM_CHAT_ID}" \
    --data-urlencode text="$1" || true
}

# Ротация: чистим всё старше KEEP_DAYS. Только после успешного дампа: при череде сбоев
# ротация стёрла бы последние рабочие копии, а новых бы не появилось.
rotate_old() {
  find "$BACKUP_DIR" -name "*.dump" -mtime +"$KEEP_DAYS" -delete
  find "$BACKUP_DIR" -name "*.sql.gz" -mtime +"$KEEP_DAYS" -delete
}

on_error() {
  # Незавершённый дамп этого запуска (.partial) удаляем сразу: полный файл .dump появляется
  # только после успешного pg_dump.
  rm -f "${FILE:-/nonexistent}.partial" "${IDENTITY_FILE:-/nonexistent}.partial" 2>/dev/null || true
  tg_notify "🔴 pg-backup FAILED on $(hostname) at $(date '+%F %T') (line $1). Проверь /var/log/pg-backup.log"
}
trap 'on_error $LINENO' ERR

mkdir -p "$BACKUP_DIR"

STAMP=$(date +%Y%m%d_%H%M%S)
FILE="$BACKUP_DIR/${DB_NAME}_${STAMP}.dump"
IDENTITY_FILE="$BACKUP_DIR/${DB_NAME}_${STAMP}.identity.sql.gz"

# Не функция: ERR-trap bash не срабатывает на падение вызова функции под set -e, и сбой pg_dump
# тогда не шлёт алерт и не запускает on_error. Прямой вызов docker — обычная команда, trap срабатывает.
DC=(docker compose -f "$COMPOSE_DIR/docker-compose.yml")

# 1) Полный бэкап всей БД (включает identity-таблицы).
# Записи сессий посетителей (session_replay_chunks) — крупные, короткоживущие (retention) и
# воспроизводимы из событий только частично; в ежедневный дамп и в его копию на Mac они
# не попадают: структура таблицы сохраняется, строки — нет (docs/research/session-replay-review-2026-10-04.md).
"${DC[@]}" exec -T postgres pg_dump -Fc -U "$DB_USER" --exclude-table-data=session_replay_chunks "$DB_NAME" > "$FILE.partial"
mv "$FILE.partial" "$FILE"
SIZE=$(du -h "$FILE" | cut -f1)
echo "[$(date)] Full backup: $FILE ($SIZE)"

# 2) Подстраховка: data-only dump только identity-таблиц в plain SQL.
TABLE_FLAGS=""
for t in $IDENTITY_TABLES; do TABLE_FLAGS="$TABLE_FLAGS -t $t"; done
# shellcheck disable=SC2086
"${DC[@]}" exec -T postgres pg_dump -U "$DB_USER" "$DB_NAME" --data-only --no-owner --column-inserts $TABLE_FLAGS \
  | gzip > "$IDENTITY_FILE.partial"
mv "$IDENTITY_FILE.partial" "$IDENTITY_FILE"
ISIZE=$(du -h "$IDENTITY_FILE" | cut -f1)
echo "[$(date)] Identity backup: $IDENTITY_FILE ($ISIZE)"

# О-1: offsite-копия в S3-совместимое хранилище (Яндекс Object Storage и т. п.).
# Бэкапы на том же диске, что и БД, — потеря диска теряет всё; offsite чинит.
# Включение — две переменные в /opt/rosstat/.env (или окружении cron):
#   OFFSITE_S3_BUCKET=s3://имя-бакета/pg-backups
#   OFFSITE_S3_ENDPOINT=https://storage.yandexcloud.net
#   + креды для aws cli (AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY в env,
#     либо профиль в ~/.aws/credentials). Пошагово: docs/offsite-backup-runbook.md.
# Без переменных шаг пропускается (dev). Сбой offsite НЕ роняет скрипт (локальный дамп уже
# есть, deploy.sh не должен вставать из-за чужого хранилища), но и не выдаётся за успех:
# вместо зелёного heartbeat уходит жёлтое сообщение с причиной (OFFSITE_NOTE).
if [ -z "${OFFSITE_S3_BUCKET:-}" ] && [ -f "$COMPOSE_DIR/.env" ]; then
  OFFSITE_S3_BUCKET=$(grep -E '^OFFSITE_S3_BUCKET=' "$COMPOSE_DIR/.env" | cut -d= -f2- || true)
  OFFSITE_S3_ENDPOINT=$(grep -E '^OFFSITE_S3_ENDPOINT=' "$COMPOSE_DIR/.env" | cut -d= -f2- || true)
fi

# Заливает файл и сверяет размер объекта с локальным. Возвращает 0 только если оба прошли.
offsite_upload() {
  local file="$1" name remote_size local_size
  name=$(basename "$file")
  aws s3 cp "$file" "$OFFSITE_S3_BUCKET/" ${OFFSITE_S3_ENDPOINT:+--endpoint-url "$OFFSITE_S3_ENDPOINT"} --only-show-errors || return 1
  remote_size=$(aws s3 ls "$OFFSITE_S3_BUCKET/$name" ${OFFSITE_S3_ENDPOINT:+--endpoint-url "$OFFSITE_S3_ENDPOINT"} | awk '{print $3}' | head -1)
  local_size=$(wc -c < "$file" | tr -d ' ')
  [ -n "$remote_size" ] && [ "$remote_size" = "$local_size" ] || { echo "[$(date)] Offsite size mismatch for $name: remote=${remote_size:-none} local=$local_size" >&2; return 1; }
}

OFFSITE_NOTE=""
if [ -n "${OFFSITE_S3_BUCKET:-}" ]; then
  if ! command -v aws >/dev/null 2>&1; then
    OFFSITE_NOTE="offsite НЕ выполнен: aws cli не установлен"
  elif offsite_upload "$FILE" && offsite_upload "$IDENTITY_FILE"; then
    echo "[$(date)] Offsite copy uploaded and size-checked: $OFFSITE_S3_BUCKET"
    OFFSITE_NOTE="offsite ok"
  else
    OFFSITE_NOTE="offsite НЕ выполнен: загрузка в $OFFSITE_S3_BUCKET не прошла или размер не совпал"
  fi
  case "$OFFSITE_NOTE" in
    *"НЕ выполнен"*) echo "[$(date)] WARN: $OFFSITE_NOTE" >&2 ;;
  esac
fi

rotate_old
echo "[$(date)] Cleaned backups older than $KEEP_DAYS days"

# Heartbeat: успех виден в Telegram, а не только в логе на сервере.
case "$OFFSITE_NOTE" in
  *"НЕ выполнен"*) tg_notify "🟡 pg-backup: локально ok (full $SIZE, identity $ISIZE), но $OFFSITE_NOTE ($(date '+%F %T'))" ;;
  "offsite ok") tg_notify "🟢 pg-backup ok: full $SIZE, identity $ISIZE, offsite ok ($(date '+%F %T'))" ;;
  *) tg_notify "🟢 pg-backup ok: full $SIZE, identity $ISIZE ($(date '+%F %T'))" ;;
esac

# Durable operational state: cache Redis is cleared during deployments. Use
# the application's canonical state-Redis URL (dedicated service OR logical DB1).
# A backend outage must not invalidate an otherwise successful database backup.
if ! "${DC[@]}" exec -T backend python -c '
import time
from app.core.cache import get_state_redis_sync
get_state_redis_sync().set("fe:ops:pg_backup_last_ok", str(time.time()))
' >/dev/null 2>&1; then
  echo "[$(date)] WARN: pg_backup heartbeat SET в state Redis не прошёл (не влияет на бэкап)" >&2
fi
