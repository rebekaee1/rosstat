#!/usr/bin/env bash
# Auto-sync: watches for changes every 30s and pushes to GitHub
# Usage: bash auto-sync.sh

REPO_DIR="/Users/nikitamoiseev/Desktop/RuStats"
INTERVAL=30
LOG_FILE="$REPO_DIR/.auto-sync.log"

cd "$REPO_DIR" || { echo "ERROR: cannot cd to $REPO_DIR"; exit 1; }

# ── Check git user config ────────────────────────────────────────────────────
GIT_NAME=$(git config user.name || git config --global user.name)
GIT_EMAIL=$(git config user.email || git config --global user.email)

if [ -z "$GIT_NAME" ] || [ -z "$GIT_EMAIL" ]; then
  echo "ERROR: git user not configured. Run:"
  echo "  git config --global user.name  \"Your Name\""
  echo "  git config --global user.email \"you@example.com\""
  exit 1
fi

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

log "=== Auto-sync started (interval: ${INTERVAL}s, user: $GIT_NAME <$GIT_EMAIL>) ==="
echo "Watching $REPO_DIR — press Ctrl+C to stop"

while true; do
  if [ -n "$(git status --porcelain 2>/dev/null)" ]; then

    git add -A

    CHANGED=$(git diff --cached --name-only | head -5 | tr '\n' ', ' | sed 's/,$//')
    COUNT=$(git diff --cached --name-only | wc -l | tr -d ' ')
    MSG="auto: update $CHANGED"
    [ "$COUNT" -gt 5 ] && MSG="auto: update $COUNT files"

    if git commit -m "$MSG" >> "$LOG_FILE" 2>&1; then
      if git push >> "$LOG_FILE" 2>&1; then
        log "✓ Pushed: $MSG"
      else
        log "✗ Push failed — check GitHub credentials/network"
      fi
    fi
  fi

  sleep "$INTERVAL"
done
