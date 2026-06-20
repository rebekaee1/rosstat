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
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/opt/rosstat/backups}"
KEEP_DAYS="${KEEP_DAYS:-14}"
DB_NAME="rustats"
DB_USER="rustats"
COMPOSE_DIR="${COMPOSE_DIR:-/opt/rosstat}"
IDENTITY_TABLES="users email_credentials oauth_identities consents auth_audit"

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

# Ротация: чистим всё старше KEEP_DAYS.
find "$BACKUP_DIR" -name "*.dump" -mtime +"$KEEP_DAYS" -delete
find "$BACKUP_DIR" -name "*.sql.gz" -mtime +"$KEEP_DAYS" -delete
echo "[$(date)] Cleaned backups older than $KEEP_DAYS days"
