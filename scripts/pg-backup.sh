#!/bin/bash
set -euo pipefail

BACKUP_DIR="/opt/rosstat/backups"
KEEP_DAYS=14
CONTAINER="rosstat-postgres-1"
DB_NAME="rustats"
DB_USER="rustats"

mkdir -p "$BACKUP_DIR"

STAMP=$(date +%Y%m%d_%H%M%S)
FILE="$BACKUP_DIR/${DB_NAME}_${STAMP}.sql.gz"

docker exec "$CONTAINER" pg_dump -U "$DB_USER" "$DB_NAME" | gzip > "$FILE"

SIZE=$(du -h "$FILE" | cut -f1)
echo "[$(date)] Backup: $FILE ($SIZE)"

find "$BACKUP_DIR" -name "*.sql.gz" -mtime +"$KEEP_DAYS" -delete
echo "[$(date)] Cleaned backups older than $KEEP_DAYS days"
