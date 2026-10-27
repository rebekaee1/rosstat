#!/bin/bash
# Pull the newest completed daily Postgres dump from fe-prod to this Mac.
# Server: /opt/rosstat/backups, cron 04:00 UTC (07:00 MSK) pg-backup.sh writes
#   rustats_YYYYMMDD_04MMSS.dump  then  rustats_YYYYMMDD_04MMSS.identity.sql.gz
# The identity file is written AFTER the full dump finishes, so "identity file
# exists and both files older than MIN_AGE_MIN" == dump complete.
# Read-only on the server.
# launchd: ~/Library/LaunchAgents/com.forecasteconomy.backup-pull.plist
#   (repo copy: scripts/mac/com.forecasteconomy.backup-pull.plist)
#
# 27.10.2026, why the copy was stale since 06.10: the Mac is a laptop with the lid
# closed on battery. It only wakes for ~2 s "DarkWake" windows every ~16 min
# (pmset -g log: "Sleep Service Back to Sleep"). A single 08:15 run hit such a window,
# opened the SSH session and was put back to sleep mid-transfer: the server
# saw the login (sshd "Accepted publickey" 05:22:14 UTC) and then nothing, the Mac
# reported "Timeout, server not responding" / "Connection closed" only after it woke.
# Each day is a new dump name, so the .part files (40-230 MB of ~550 MB) were never finished.
# What this version changes:
#   * holds a sleep assertion (caffeinate -i) for the life of the run;
#   * is meant to run often (launchd StartInterval 30 min). A run is free when today's
#     dump is already verified: it exits before opening SSH;
#   * retries ssh and rsync inside one run and resumes the .part (--partial --inplace);
#   * drops .part files of older dumps (they can never be completed);
#   * notifies only when the newest verified copy is older than STALE_HOURS (not on
#     every failed attempt, which is normal while the lid is closed).
set -uo pipefail
# FE_PATH_PREPEND exists only so tests can put fake ssh/rsync in front of the real ones.
export PATH="${FE_PATH_PREPEND:+$FE_PATH_PREPEND:}/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

HOST="${FE_HOST:-fe-prod}"
REMOTE_DIR="${FE_REMOTE_DIR:-/opt/rosstat/backups}"
DEST="${FE_BACKUP_DEST:-$HOME/Backups/forecasteconomy}"
KEEP="${FE_BACKUP_KEEP:-14}"
MIN_AGE_MIN="${FE_MIN_AGE_MIN:-10}"
SSH_TRIES="${FE_SSH_TRIES:-4}"
RSYNC_TRIES="${FE_RSYNC_TRIES:-8}"
RETRY_SLEEP="${FE_RETRY_SLEEP:-20}"
STALE_HOURS="${FE_STALE_HOURS:-36}"
NOTIFY_EVERY_HOURS="${FE_NOTIFY_EVERY_HOURS:-12}"
LOG_MAX_BYTES="${FE_LOG_MAX_BYTES:-1048576}"
LOG="$DEST/pull.log"
# Scheduled copies must not reuse an interactive SSH control socket.
# Bound dead connections separately from the rsync transfer timeout.
SSH_OPTS=(-o BatchMode=yes -o ControlMaster=no -o ControlPath=none -o ConnectTimeout=20 -o ServerAliveInterval=15 -o ServerAliveCountMax=2)

mkdir -p "$DEST"
# Keep one previous log, not an unbounded file (a run every 30 min writes a few lines).
if [ -f "$LOG" ] && [ "$(stat -f %z "$LOG" 2>/dev/null || echo 0)" -gt "$LOG_MAX_BYTES" ]; then
  mv -f "$LOG" "$LOG.1"
fi
exec >>"$LOG" 2>&1
log() { echo "[$(date '+%F %T %Z')] $*"; }

# Hours since the newest .verified marker (large number if none).
verified_age_hours() {
  local newest now mtime
  newest=$(ls -1t "$DEST"/rustats_*.verified 2>/dev/null | head -1)
  [ -n "$newest" ] || { echo 99999; return; }
  now=$(date +%s); mtime=$(stat -f %m "$newest")
  echo $(( (now - mtime) / 3600 ))
}

notify_if_stale() {
  # $1 = message. Only shout when the copy is really stale, at most every NOTIFY_EVERY_HOURS.
  local age stamp="$DEST/.last-notify" now last
  age=$(verified_age_hours)
  [ "$age" -ge "$STALE_HOURS" ] || return 0
  now=$(date +%s); last=0
  [ -f "$stamp" ] && last=$(stat -f %m "$stamp")
  [ $(( (now - last) / 3600 )) -ge "$NOTIFY_EVERY_HOURS" ] || return 0
  : >"$stamp"
  osascript -e "display notification \"Копия базы на Mac старше ${age} ч: $1\" with title \"FE backup pull\" sound name \"Basso\"" >/dev/null 2>&1 || true
}

fail() {
  log "ERROR: $*"
  notify_if_stale "$*"
  exit 1
}

# Expected newest daily dump date (UTC): the 04:00 UTC cron plus 10 min to finish.
EXPECT_DATE=$(date -u -v-4H -v-10M +%Y%m%d)
if [ "${FE_FORCE:-0}" != "1" ] && ls "$DEST"/rustats_"${EXPECT_DATE}"_04????.verified >/dev/null 2>&1; then
  exit 0   # today's dump is already here and verified: no SSH, no log noise
fi

LOCK="$DEST/.pull.lock"
if ! mkdir "$LOCK" 2>/dev/null; then
  if [ -n "$(find "$LOCK" -maxdepth 0 -mmin +180 2>/dev/null)" ]; then rm -rf "$LOCK"; mkdir "$LOCK" || exit 0
  else log "another run in progress, exit"; exit 0; fi
fi
trap 'rm -rf "$LOCK"' EXIT

# Keep the Mac awake for the life of this process (idle sleep and DarkWake->sleep).
# -w: caffeinate exits when this script exits, so nothing is left holding the assertion.
if command -v caffeinate >/dev/null 2>&1; then caffeinate -i -m -w $$ >/dev/null 2>&1 & fi

log "=== start (host=$HOST, expect daily ${EXPECT_DATE}, verified copy age $(verified_age_hours) h)"

# Newest daily (04xxxx UTC) dump that has its identity file and both are older than MIN_AGE_MIN.
REMOTE_FIND="cd $REMOTE_DIR && find . -maxdepth 1 -name 'rustats_*_04????.identity.sql.gz' -mmin +$MIN_AGE_MIN -printf '%f\n' | sort | while read -r f; do b=\${f%.identity.sql.gz}; [ -s \"\$b.dump\" ] && [ -n \"\$(find \"\$b.dump\" -mmin +$MIN_AGE_MIN)\" ] && echo \"\$b\"; done | tail -1"
BASE=""; ssh_ok=0
for ((i = 1; i <= SSH_TRIES; i++)); do
  if BASE=$(ssh "${SSH_OPTS[@]}" "$HOST" "$REMOTE_FIND"); then ssh_ok=1; break; fi
  log "ssh attempt $i/$SSH_TRIES failed"
  [ "$i" -lt "$SSH_TRIES" ] && sleep "$RETRY_SLEEP"
done
[ "$ssh_ok" = 1 ] || fail "ssh to $HOST failed"
[ -n "$BASE" ] || fail "no completed daily dump found on $HOST:$REMOTE_DIR"
[[ "$BASE" =~ ^rustats_[0-9]{8}_04[0-9]{4}$ ]] || fail "unexpected name '$BASE'"
DUMP="$BASE.dump"; IDENT="$BASE.identity.sql.gz"
log "newest completed daily: $BASE"

if [ -s "$DEST/$DUMP" ] && [ -s "$DEST/$IDENT" ] && [ -f "$DEST/$BASE.verified" ]; then
  log "already present and verified, skip"
  exit 0
fi

# Partials of older dumps can never be finished (a new name every day): free the disk.
for p in "$DEST"/rustats_*.part; do
  [ -e "$p" ] || continue
  case "$(basename "$p")" in "$DUMP.part"|"$IDENT.part") ;; *) rm -f "$p"; log "removed stale partial $(basename "$p")";; esac
done

df -h "$DEST" | tail -1 | awk '{print "disk free before: "$4" ("$5" used)"}' | while read -r l; do log "$l"; done

for f in "$DUMP" "$IDENT"; do
  done_f=0
  for ((i = 1; i <= RSYNC_TRIES; i++)); do
    before=$(stat -f %z "$DEST/$f.part" 2>/dev/null || echo 0)
    if rsync -t --partial --inplace --timeout=300 -e "ssh ${SSH_OPTS[*]}" "$HOST:$REMOTE_DIR/$f" "$DEST/$f.part"; then done_f=1; break; fi
    after=$(stat -f %z "$DEST/$f.part" 2>/dev/null || echo 0)
    log "rsync $f attempt $i/$RSYNC_TRIES interrupted: partial $before -> $after bytes (resumes)"
    [ "$i" -lt "$RSYNC_TRIES" ] && sleep "$RETRY_SLEEP"
  done
  [ "$done_f" = 1 ] || fail "rsync $f failed after $RSYNC_TRIES attempts (partial kept for the next run)"
done

# Verify size + sha256 against the server.
REMOTE_SUMS=$(ssh "${SSH_OPTS[@]}" "$HOST" "cd $REMOTE_DIR && stat -c '%s %n' $DUMP $IDENT && sha256sum $DUMP $IDENT") || fail "remote checksum failed"
for f in "$DUMP" "$IDENT"; do
  rsize=$(awk -v f="$f" 'NF==2 && $2==f && $1 ~ /^[0-9]+$/ {print $1; exit}' <<<"$REMOTE_SUMS")
  rsum=$(awk -v f="$f" 'length($1)==64 && $2==f {print $1; exit}' <<<"$REMOTE_SUMS")
  lsize=$(stat -f %z "$DEST/$f.part")
  lsum=$(shasum -a 256 "$DEST/$f.part" | awk '{print $1}')
  # A mismatch means a corrupt resume: drop the partial so the next run starts clean.
  [ "$rsize" = "$lsize" ] || { rm -f "$DEST/$f.part"; fail "$f size mismatch remote=$rsize local=$lsize (partial dropped)"; }
  [ "$rsum" = "$lsum" ] || { rm -f "$DEST/$f.part"; fail "$f sha256 mismatch remote=$rsum local=$lsum (partial dropped)"; }
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
