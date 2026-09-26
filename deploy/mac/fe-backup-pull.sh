#!/bin/bash
# Pull the newest completed daily Postgres dump from fe-prod to this Mac.
# Server: /opt/rosstat/backups, cron 04:00 UTC (07:00 MSK) pg-backup.sh writes
#   rustats_YYYYMMDD_04MMSS.dump  then  rustats_YYYYMMDD_04MMSS.identity.sql.gz
# The identity file is written AFTER the full dump finishes, so "identity file
# exists and both files older than MIN_AGE_MIN" == dump complete.
# Read-only on the server. launchd: ~/Library/LaunchAgents/com.forecasteconomy.backup-pull.plist
set -uo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

HOST="${FE_HOST:-fe-prod}"
REMOTE_DIR="/opt/rosstat/backups"
DEST="${FE_BACKUP_DEST:-$HOME/Backups/forecasteconomy}"
KEEP="${FE_BACKUP_KEEP:-14}"
MIN_AGE_MIN=10
LOG="$DEST/pull.log"
SSH_OPTS=(-o BatchMode=yes -o ConnectTimeout=20 -o ServerAliveInterval=30)

mkdir -p "$DEST"
exec >>"$LOG" 2>&1
log() { echo "[$(date '+%F %T %Z')] $*"; }
fail() {
  log "ERROR: $*"
  osascript -e "display notification \"$*\" with title \"FE backup pull FAILED\" sound name \"Basso\"" >/dev/null 2>&1 || true
  exit 1
}

LOCK="$DEST/.pull.lock"
if ! mkdir "$LOCK" 2>/dev/null; then
  if [ -n "$(find "$LOCK" -maxdepth 0 -mmin +180 2>/dev/null)" ]; then rm -rf "$LOCK"; mkdir "$LOCK" || exit 0
  else log "another run in progress, exit"; exit 0; fi
fi
trap 'rm -rf "$LOCK"' EXIT

log "=== start (host=$HOST)"
# Newest daily (04xxxx UTC) dump that has its identity file and both are older than MIN_AGE_MIN.
BASE=$(ssh "${SSH_OPTS[@]}" "$HOST" "cd $REMOTE_DIR && find . -maxdepth 1 -name 'rustats_*_04????.identity.sql.gz' -mmin +$MIN_AGE_MIN -printf '%f\n' | sort | while read -r f; do b=\${f%.identity.sql.gz}; [ -s \"\$b.dump\" ] && [ -n \"\$(find \"\$b.dump\" -mmin +$MIN_AGE_MIN)\" ] && echo \"\$b\"; done | tail -1") \
  || fail "ssh to $HOST failed"
[ -n "$BASE" ] || fail "no completed daily dump found on $HOST:$REMOTE_DIR"
[[ "$BASE" =~ ^rustats_[0-9]{8}_04[0-9]{4}$ ]] || fail "unexpected name '$BASE'"
DUMP="$BASE.dump"; IDENT="$BASE.identity.sql.gz"
log "newest completed daily: $BASE"

if [ -s "$DEST/$DUMP" ] && [ -s "$DEST/$IDENT" ] && [ -f "$DEST/$BASE.verified" ]; then
  log "already present and verified, skip"
  exit 0
fi

df -h "$DEST" | tail -1 | awk '{print "disk free before: "$4" ("$5" used)"}' | while read -r l; do log "$l"; done

for f in "$DUMP" "$IDENT"; do
  rsync -t --partial --inplace --timeout=300 -e "ssh ${SSH_OPTS[*]}" "$HOST:$REMOTE_DIR/$f" "$DEST/$f.part" || fail "rsync $f failed"
done

# Verify size + sha256 against the server.
REMOTE_SUMS=$(ssh "${SSH_OPTS[@]}" "$HOST" "cd $REMOTE_DIR && stat -c '%s %n' $DUMP $IDENT && sha256sum $DUMP $IDENT") || fail "remote checksum failed"
for f in "$DUMP" "$IDENT"; do
  rsize=$(awk -v f="$f" 'NF==2 && $2==f && $1 ~ /^[0-9]+$/ {print $1; exit}' <<<"$REMOTE_SUMS")
  rsum=$(awk -v f="$f" 'length($1)==64 && $2==f {print $1; exit}' <<<"$REMOTE_SUMS")
  lsize=$(stat -f %z "$DEST/$f.part")
  lsum=$(shasum -a 256 "$DEST/$f.part" | awk '{print $1}')
  [ "$rsize" = "$lsize" ] || fail "$f size mismatch remote=$rsize local=$lsize"
  [ "$rsum" = "$lsum" ] || fail "$f sha256 mismatch remote=$rsum local=$lsum"
  mv -f "$DEST/$f.part" "$DEST/$f"
  log "$f ok: $lsize bytes sha256=$lsum (matches server)"
done

# Readability: pg_restore --list (local binary, else docker postgres:16-alpine).
PGR_OUT="$DEST/$BASE.toc.txt"
if command -v pg_restore >/dev/null 2>&1; then
  pg_restore --list "$DEST/$DUMP" >"$PGR_OUT" 2>&1; rc=$?; how="local pg_restore"
elif command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
  docker run --rm -v "$DEST:/b:ro" postgres:16-alpine pg_restore --list "/b/$DUMP" >"$PGR_OUT" 2>&1; rc=$?; how="docker postgres:16-alpine"
else
  rc=-1; how="none"
fi
if [ "$rc" = "-1" ]; then
  log "WARN: pg_restore unavailable (no local binary, docker not running) — readability NOT checked"
elif [ "$rc" -ne 0 ]; then
  fail "pg_restore --list failed ($how, rc=$rc), see $PGR_OUT"
else
  n=$(grep -cv '^;' "$PGR_OUT"); t=$(grep -c ' TABLE DATA ' "$PGR_OUT")
  log "pg_restore --list ok via $how: $n TOC entries, $t TABLE DATA"
fi
gzip -t "$DEST/$IDENT" || fail "$IDENT gzip test failed"
date '+%F %T %Z' >"$DEST/$BASE.verified"

# Retention: keep newest $KEEP dumps (and their companions).
ls -1 "$DEST"/rustats_*.dump 2>/dev/null | sort -r | tail -n +$((KEEP+1)) | while read -r old; do
  b="${old%.dump}"; rm -f "$old" "$b.identity.sql.gz" "$b.toc.txt" "$b.verified"; log "retention: removed $(basename "$b")"
done
rm -f "$DEST"/*.part.old 2>/dev/null
df -h "$DEST" | tail -1 | awk '{print "disk free after: "$4" ("$5" used)"}' | while read -r l; do log "$l"; done
log "=== done: $DUMP"
