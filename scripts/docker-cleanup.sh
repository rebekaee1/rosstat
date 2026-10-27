#!/bin/bash
# Уборка Docker-хоста: висячие образы и КЭШ СБОРКИ.
#
# История: до 2026-10-27 скрипт звал `docker builder prune` без `-a`. Без `-a`
# удаляется только висячий кэш; кэш слоёв, к которому не привязан работающий
# контейнер, оставался навсегда: на проде 352 записи, 16,1 ГБ «reclaimable»
# (0 активных), каждая выкатка добавляла ~0,7 ГБ. Скрипт при этом не стоял в cron.
#
# Использование:
#   scripts/docker-cleanup.sh --dry-run   # только показать команды и занятое место
#   scripts/docker-cleanup.sh             # убрать
# Переменные:
#   BUILD_CACHE_MAX_AGE   (168h)  кэш сборки, не использованный дольше, удаляется
#   BUILD_CACHE_RESERVED  (3GB)   столько кэша сохранить всегда — следующая сборка
#                                 не начнётся с нуля (pip/npm-слои)
#   IMAGE_MAX_AGE         (72h)   висячие образы
#
# Работающие контейнеры, их образы и тома с данными не затрагиваются. Пока идёт
# выкатка (scripts/deploy.sh держит /var/lock/rosstat-deploy.lock), скрипт ничего
# не делает.
set -euo pipefail

BUILD_CACHE_MAX_AGE="${BUILD_CACHE_MAX_AGE:-168h}"
BUILD_CACHE_RESERVED="${BUILD_CACHE_RESERVED:-3GB}"
IMAGE_MAX_AGE="${IMAGE_MAX_AGE:-72h}"

if [ "${1:-}" = "--dry-run" ]; then
  echo "[$(date)] Dry-run. Было бы выполнено:"
  echo "  docker image prune -f --filter until=${IMAGE_MAX_AGE}"
  echo "  docker builder prune -a -f --filter until=${BUILD_CACHE_MAX_AGE} --reserved-space ${BUILD_CACHE_RESERVED}"
  docker system df
  df -h / | tail -1
  exit 0
fi

# Не мешаем выкатке: тот же lock, что берёт scripts/deploy.sh.
exec 9>/var/lock/rosstat-deploy.lock
flock -n 9 || { echo "[$(date)] Идёт деплой (lock занят) — уборка пропущена"; exit 0; }

BEFORE=$(df --output=avail -B1 / | tail -1 | tr -d ' ')
echo "[$(date)] Docker cleanup: висячие образы старше ${IMAGE_MAX_AGE}, кэш сборки старше ${BUILD_CACHE_MAX_AGE} (резерв ${BUILD_CACHE_RESERVED})..."
docker image prune -f --filter "until=${IMAGE_MAX_AGE}"
docker builder prune -a -f --filter "until=${BUILD_CACHE_MAX_AGE}" --reserved-space "${BUILD_CACHE_RESERVED}"
AFTER=$(df --output=avail -B1 / | tail -1 | tr -d ' ')
echo "[$(date)] Done. Освобождено: $(( (AFTER - BEFORE) / 1024 / 1024 )) МиБ. Диск:"
df -h / | tail -1
