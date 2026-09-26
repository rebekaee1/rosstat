#!/usr/bin/env bash
# perf batch 3 (2026-09-26): одноразовая DDL-чистка прод-БД ПОСЛЕ принятого
# деплоя (после 15-мин watch). По умолчанию — dry-run: только проверки и план.
#
#   bash scripts/db-cleanup-perf-batch3.sh                 # dry-run
#   bash scripts/db-cleanup-perf-batch3.sh --apply-index   # DROP дубль-индекса
#   bash scripts/db-cleanup-perf-batch3.sh --apply-fe-sync # dump + DROP fe_sync_*_20260924
#   (флаги можно совмещать)
#
# 1) ix_world_data_points_indicator_date (indicator_id, date) дублирует
#    уникальный uq_world_data_point на тех же колонках. Снимается только если
#    uq валиден, уникален и с тем же indkey. DROP INDEX CONCURRENTLY: без
#    блокировки записи; lock_timeout — не висеть за долгими транзакциями.
#    Прерванный DROP оставляет индекс INVALID — повторный запуск его добивает.
# 2) fe_sync_world_*_20260924 — остатки одноразовой синхронизации мира
#    (в коде не используются). Перед DROP — pg_dump -Fc в backups/ и проверка
#    оглавления дампа. DROP без CASCADE: зависимости → ошибка, а не тихий снос.
#
# Не трогает схему alembic: модель и 20260727_world_eurostat уже без индекса.
set -euo pipefail

cd "${COMPOSE_DIR:-/opt/rosstat}"
BACKUP_DIR="${BACKUP_DIR:-$(pwd)/backups}"
APPLY_INDEX=0
APPLY_FE_SYNC=0
for arg in "$@"; do
  case "$arg" in
    --apply-index) APPLY_INDEX=1 ;;
    --apply-fe-sync) APPLY_FE_SYNC=1 ;;
    *) echo "unknown arg: $arg"; exit 2 ;;
  esac
done

DUP_INDEX=ix_world_data_points_indicator_date
KEEP_INDEX=uq_world_data_point
FE_SYNC_PATTERN='fe_sync\_%\_20260924'

psql_q() { docker compose exec -T postgres psql -U rustats -d rustats -v ON_ERROR_STOP=1 -X "$@"; }

echo "==> world_data_points: индексы и сканы"
psql_q -P pager=off -c "
  SELECT s.indexrelname, x.indkey::text, x.indisunique, x.indisvalid, s.idx_scan,
         pg_size_pretty(pg_relation_size(s.indexrelid)) AS size
  FROM pg_stat_user_indexes s JOIN pg_index x ON x.indexrelid = s.indexrelid
  WHERE s.relname = 'world_data_points' ORDER BY 1"

DUP_STATE=$(psql_q -Atc "
  SELECT CASE
    WHEN d.indexrelid IS NULL THEN 'absent'
    WHEN k.indexrelid IS NOT NULL AND k.indisunique AND k.indisvalid AND k.indisready
         AND k.indkey::text = d.indkey::text
         AND k.indrelid = d.indrelid THEN 'covered'
    ELSE 'not-covered' END
  FROM (SELECT 1) one
  LEFT JOIN pg_index d ON d.indexrelid = to_regclass('public.${DUP_INDEX}')
  LEFT JOIN pg_index k ON k.indexrelid = to_regclass('public.${KEEP_INDEX}')")
echo "    ${DUP_INDEX}: ${DUP_STATE}"

echo "==> fe_sync-таблицы (${FE_SYNC_PATTERN})"
psql_q -P pager=off -c "
  SELECT c.relname, pg_size_pretty(pg_total_relation_size(c.oid)) AS total,
         c.reltuples::bigint AS rows, s.last_seq_scan, s.last_idx_scan
  FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace AND n.nspname = 'public'
  LEFT JOIN pg_stat_user_tables s ON s.relid = c.oid
  WHERE c.relkind = 'r' AND c.relname LIKE '${FE_SYNC_PATTERN}' ORDER BY 1"
FE_TABLES=$(psql_q -Atc "
  SELECT string_agg(c.relname, ' ' ORDER BY c.relname)
  FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace AND n.nspname = 'public'
  WHERE c.relkind = 'r' AND c.relname LIKE '${FE_SYNC_PATTERN}'")
FE_DEPS=$(psql_q -Atc "
  SELECT count(*) FROM pg_depend d
  JOIN pg_class t ON t.oid = d.refobjid AND t.relname LIKE '${FE_SYNC_PATTERN}'
  JOIN pg_rewrite r ON r.oid = d.objid
  JOIN pg_class v ON v.oid = r.ev_class AND v.oid <> t.oid")
echo "    таблицы: ${FE_TABLES:-нет}; зависимые view: ${FE_DEPS}"
CODE_REFS=$(git grep -l 'fe_sync' -- . ':!scripts/db-cleanup-perf-batch3.sh' 2>/dev/null || true)
echo "    упоминания fe_sync в коде: ${CODE_REFS:-нет}"

if [ "$APPLY_INDEX" = 0 ] && [ "$APPLY_FE_SYNC" = 0 ]; then
  echo
  echo "DRY-RUN. План:"
  echo "  --apply-index:   SET lock_timeout='5s'; DROP INDEX CONCURRENTLY IF EXISTS ${DUP_INDEX};  (только при state=covered)"
  echo "  --apply-fe-sync: pg_dump -Fc -t <каждая> > ${BACKUP_DIR}/fe_sync_20260924_<stamp>.dump; pg_restore -l проверка; DROP TABLE <все> (без CASCADE)"
  exit 0
fi

if [ "$APPLY_INDEX" = 1 ]; then
  case "$DUP_STATE" in
    absent) echo "==> ${DUP_INDEX} уже нет — пропуск" ;;
    covered)
      echo "==> DROP INDEX CONCURRENTLY ${DUP_INDEX}"
      # CONCURRENTLY нельзя в транзакции: отдельные -c, psql в autocommit.
      psql_q -c "SET lock_timeout = '5s'" -c "DROP INDEX CONCURRENTLY IF EXISTS public.${DUP_INDEX}"
      echo "    ok"
      ;;
    *) echo "FAIL: ${KEEP_INDEX} не покрывает ${DUP_INDEX} — индекс не трогаю"; exit 1 ;;
  esac
fi

if [ "$APPLY_FE_SYNC" = 1 ]; then
  if [ -z "$FE_TABLES" ]; then
    echo "==> fe_sync-таблиц нет — пропуск"
  else
    [ -z "$CODE_REFS" ] || { echo "FAIL: fe_sync упоминается в коде — не удаляю"; exit 1; }
    [ "$FE_DEPS" = 0 ] || { echo "FAIL: есть зависимые view — не удаляю"; exit 1; }
    mkdir -p "$BACKUP_DIR"
    DUMP="${BACKUP_DIR}/fe_sync_20260924_$(date +%Y%m%d_%H%M%S).dump"
    TABLE_ARGS=()
    for t in $FE_TABLES; do TABLE_ARGS+=(-t "public.${t}"); done
    echo "==> pg_dump -Fc ${FE_TABLES} -> ${DUMP}"
    docker compose exec -T postgres pg_dump -U rustats -d rustats -Fc "${TABLE_ARGS[@]}" > "$DUMP"
    TOC=$(docker compose exec -T postgres pg_restore -l < "$DUMP")
    for t in $FE_TABLES; do
      grep -q "TABLE DATA public ${t} " <<<"$TOC" || { echo "FAIL: в дампе нет данных ${t} — не удаляю"; exit 1; }
    done
    echo "    дамп ok ($(du -h "$DUMP" | cut -f1)); восстановление: docker compose exec -T postgres pg_restore -U rustats -d rustats < ${DUMP}"
    DROP_LIST=$(printf 'public.%s, ' $FE_TABLES); DROP_LIST=${DROP_LIST%, }
    psql_q -c "SET lock_timeout = '5s'" -c "DROP TABLE ${DROP_LIST}"
    echo "    dropped: ${FE_TABLES}"
  fi
fi
