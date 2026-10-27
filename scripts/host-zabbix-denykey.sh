#!/usr/bin/env bash
# Zabbix-агент хоста не должен читать файлы-секреты приложения. ПОДГОТОВКА — на проде не применялось.
#
# Причина (замер 2026-10-27, только чтение). Файл /etc/rosstat-secrets/gsc-oauth.json (OAuth Google
# Search Console, монтируется в scheduler через /opt/rosstat/docker-compose.override.yml) принадлежит
# uid 999, режим 0600. 999 — это uid пользователя `appuser` ВНУТРИ контейнера: приложение
# (backend/app/services/gsc_client.py) требует режим 0600 и должно прочитать файл, поэтому владелец
# обязан быть 999. На ХОСТЕ тот же номер 999 занят `zabbix` (zabbix_agentd работает от него, а группа
# 999 = systemd-journal). Значит владелец «zabbix» — совпадение номеров, а не назначение; но агент
# фактически может читать файл. В zabbix_agentd.conf запрещён только system.run[*]; ключи
# vfs.file.contents/regexp/regmatch разрешены, и любой элемент с сервера мониторинга
# (92.53.116.12/111/119) мог бы вытащить секрет. Смена владельца файла на root сломает чтение
# приложением, поэтому мера — запретить агенту эти ключи.
#
# Режимы (по умолчанию --dry-run):
#   scripts/host-zabbix-denykey.sh --dry-run
#   scripts/host-zabbix-denykey.sh --apply       резервная копия, 3 строки DenyKey, перезапуск агента, проверка
#   scripts/host-zabbix-denykey.sh --verify
#   scripts/host-zabbix-denykey.sh --rollback    вернуть конфиг из резервной копии
# Оговорка: конфиг ведёт Timeweb (UserParameter=timeweb_config_version). Если провайдер перепишет
# файл, строки пропадут — повторить --apply. Шаблоны провайдера, использующие vfs.file.contents,
# получат «not supported» (проверить в панели мониторинга после применения).
set -euo pipefail

MODE="${1:---dry-run}"
CONF="${ZABBIX_CONF:-/etc/zabbix/zabbix_agentd.conf}"
BACKUP="${CONF}.before-denykey"
MARK="# rosstat: агент не читает файлы-секреты (scripts/host-zabbix-denykey.sh)"
KEYS=('vfs.file.contents[*]' 'vfs.file.regexp[*]' 'vfs.file.regmatch[*]')
SERVICE="${ZABBIX_SERVICE:-zabbix-agent}"

log() { echo "[host-zabbix-denykey] $*"; }
need_root() { [[ $EUID -eq 0 ]] || { echo "нужен root" >&2; exit 1; }; }

# Безопасная проверка: читаем безвредный файл (/etc/hostname), секрет не затрагивается.
probe() {
  local out
  out="$(zabbix_agentd -c "$CONF" -t 'vfs.file.contents[/etc/hostname]' 2>&1 || true)"
  if grep -qiE 'not (allowed|supported)|ZBX_NOTSUPPORTED' <<<"$out"; then
    log "vfs.file.contents запрещён: ok"; return 0
  fi
  log "vfs.file.contents по-прежнему доступен (или агент недоступен)"; return 1
}

case "$MODE" in
  --dry-run)
    log "Конфиг: $CONF; DenyKey сейчас:"; grep -n '^DenyKey' "$CONF" || true
    log "Агент работает от: $(ps -o user= -C zabbix_agentd | sort -u | tr '\n' ' ')"
    log "Секрет: $(stat -c '%a %u:%g' /etc/rosstat-secrets/gsc-oauth.json 2>/dev/null || echo 'нет файла')"
    log "Будет добавлено после строки DenyKey=system.run[*]:"
    printf '  %s\n' "$MARK"; for k in "${KEYS[@]}"; do printf '  DenyKey=%s\n' "$k"; done
    log "Затем: systemctl restart $SERVICE; проверка на /etc/hostname (секрет не читается)"
    ;;
  --apply)
    need_root
    [[ -f "$BACKUP" ]] || cp -p "$CONF" "$BACKUP"
    if grep -qF "$MARK" "$CONF"; then log "уже применено"; else
      {
        printf '%s\n' "$MARK"
        for k in "${KEYS[@]}"; do printf 'DenyKey=%s\n' "$k"; done
      } > "${CONF}.denykey.tmp"
      # Вставка сразу после существующей DenyKey=system.run[*]; если её нет — в конец файла.
      if grep -q '^DenyKey=system.run' "$CONF"; then
        sed -i "/^DenyKey=system.run/r ${CONF}.denykey.tmp" "$CONF"
      else
        cat "${CONF}.denykey.tmp" >> "$CONF"
      fi
      rm -f "${CONF}.denykey.tmp"
    fi
    zabbix_agentd -c "$CONF" -t agent.ping >/dev/null 2>&1 || { log "ОШИБКА: конфиг не разбирается — откат"; cp -p "$BACKUP" "$CONF"; exit 1; }
    systemctl restart "$SERVICE"
    sleep 2
    systemctl is-active --quiet "$SERVICE" || { log "ОШИБКА: агент не запустился — откат"; cp -p "$BACKUP" "$CONF"; systemctl restart "$SERVICE"; exit 1; }
    probe || { log "проверка не прошла — откат"; cp -p "$BACKUP" "$CONF"; systemctl restart "$SERVICE"; exit 1; }
    log "Готово. Проверьте в панели мониторинга Timeweb, что метрики хоста приходят."
    ;;
  --verify)
    systemctl is-active "$SERVICE"; grep -n '^DenyKey' "$CONF"; probe
    ;;
  --rollback)
    need_root
    [[ -f "$BACKUP" ]] || { echo "нет $BACKUP" >&2; exit 1; }
    cp -p "$BACKUP" "$CONF"
    systemctl restart "$SERVICE"
    log "Конфиг возвращён, агент $(systemctl is-active "$SERVICE")"
    ;;
  *)
    echo "Использование: $0 [--dry-run|--apply|--verify|--rollback]" >&2; exit 2 ;;
esac
