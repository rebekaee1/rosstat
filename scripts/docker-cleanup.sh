#!/bin/bash
set -euo pipefail

echo "[$(date)] Docker cleanup: removing dangling images and build cache..."
docker image prune -f --filter "until=72h"
docker builder prune -f --filter "until=72h"
echo "[$(date)] Done. Disk usage:"
df -h / | tail -1
