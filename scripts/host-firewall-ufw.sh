#!/usr/bin/env bash
# Фаервол хоста прода: ufw с белым списком. ПОДГОТОВКА — на проде не применялось.
#
# Замер 2026-10-27 (только чтение): ufw inactive, iptables INPUT = ACCEPT (кроме цепочек
# fail2ban на 80/443). Снаружи слушают: 22/tcp (ssh), 80/tcp и 443/tcp+udp (Caddy, udp = HTTP/3),
# 10050/tcp (zabbix-agent, Server=92.53.116.12,92.53.116.111,92.53.116.119). Все порты Docker
# опубликованы на 127.0.0.1. Контейнеры ходят НА ХОСТ: 172.18.0.1:9050 (Tor SOCKS для ETL,
# RUSTATS_ETL_SOCKS_PROXY_URL) и 172.18.0.1:8888 (резервный HTTP-мост к Tor) — эти порты нужно
# оставить открытыми для сети rosstat_default, иначе ETL Росстата/Минфина потеряет Tor-маршрут.
#
# Режимы (по умолчанию --dry-run: ничего не меняет, только показывает план и проверки):
#   scripts/host-firewall-ufw.sh --dry-run    план и предпроверки
#   scripts/host-firewall-ufw.sh --apply      правила + включение; страховка: через FAILSAFE_MIN минут
#                                             ufw сам выключится, если не вызвать --confirm
#   scripts/host-firewall-ufw.sh --confirm    всё работает (ssh из второго окна, сайт, Tor) — снять страховку
#   scripts/host-firewall-ufw.sh --rollback   выключить ufw (правила остаются описанными, но не действуют)
#   scripts/host-firewall-ufw.sh --reset      выключить и удалить все правила ufw
#   scripts/host-firewall-ufw.sh --status
#
# ПОРЯДОК ПРИМЕНЕНИЯ: открыть ВТОРОЕ ssh-окно к хосту, --apply в первом, проверить во втором
# (новое подключение!), затем --confirm. Не запускать во время deploy.sh.
set -euo pipefail

MODE="${1:---dry-run}"
SSH_PORT="${SSH_PORT:-22}"
ZABBIX_SERVERS="${ZABBIX_SERVERS:-92.53.116.12 92.53.116.111 92.53.116.119}"
COMPOSE_NETWORK="${COMPOSE_NETWORK:-rosstat_default}"
FAILSAFE_MIN="${FAILSAFE_MIN:-10}"
FAILSAFE_UNIT="fe-ufw-failsafe"
TOR_BEFORE=unknown

log() { echo "[host-firewall-ufw] $*"; }
need_root() { [[ $EUID -eq 0 ]] || { echo "нужен root" >&2; exit 1; }; }

docker_subnet() {
  docker network inspect "$COMPOSE_NETWORK" --format '{{range .IPAM.Config}}{{.Subnet}}{{end}}' 2>/dev/null
}
docker_gateway() {
  docker network inspect "$COMPOSE_NETWORK" --format '{{range .IPAM.Config}}{{.Gateway}}{{end}}' 2>/dev/null
}

# Контейнер → хост:9050 (то, что ломается первым при ошибке в правилах).
tor_reachable_from_container() {
  local gw="$1"
  docker exec rosstat-scheduler-1 python -c "
import socket,sys
s=socket.socket(); s.settimeout(5)
try:
    s.connect(('$gw', 9050)); print('ok')
except Exception as e:
    print('fail', e); sys.exit(1)
" >/dev/null 2>&1
}

rules() {
  # Печатает правила одной командой на строку (общий источник для dry-run и apply).
  local subnet gw
  subnet="$(docker_subnet)"; gw="$(docker_gateway)"
  echo "ufw default deny incoming"
  echo "ufw default allow outgoing"
  # Docker сам управляет пересылкой пакетов контейнеров; ufw её не фильтрует, чтобы не сломать исходящий трафик.
  echo "ufw default allow routed"
  echo "ufw allow ${SSH_PORT}/tcp comment ssh"
  echo "ufw allow 80/tcp comment caddy-http"
  echo "ufw allow 443/tcp comment caddy-https"
  echo "ufw allow 443/udp comment caddy-http3"
  local ip
  for ip in $ZABBIX_SERVERS; do
    echo "ufw allow from ${ip} to any port 10050 proto tcp comment zabbix-agent"
  done
  echo "ufw allow from ${subnet} to ${gw} port 9050 proto tcp comment containers-to-host-tor"
  echo "ufw allow from ${subnet} to ${gw} port 8888 proto tcp comment containers-to-tor-http-bridge"
}

preflight() {
  command -v ufw >/dev/null || { echo "ufw не установлен (apt-get install -y ufw)" >&2; exit 1; }
  command -v docker >/dev/null || { echo "docker не найден" >&2; exit 1; }
  [[ -n "$(docker_subnet)" ]] || { echo "сеть $COMPOSE_NETWORK не найдена" >&2; exit 1; }
  local actual
  actual="$(sshd -T 2>/dev/null | awk '$1=="port"{print $2; exit}')"
  if [[ -n "$actual" && "$actual" != "$SSH_PORT" ]]; then
    echo "sshd слушает порт $actual, а в правиле $SSH_PORT — остановка (иначе потеря доступа)" >&2; exit 1
  fi
  log "ssh-порт: ${actual:-?}; ваш IP в этой сессии: ${SSH_CLIENT:-?} (доступ по 22 открыт всем, не только ему)"
  log "ufw сейчас: $(ufw status | head -1)"
  if tor_reachable_from_container "$(docker_gateway)"; then TOR_BEFORE=ok; else TOR_BEFORE=FAIL; fi
  log "Tor из контейнера до правил: $TOR_BEFORE"
}

case "$MODE" in
  --dry-run)
    preflight || true
    log "Будет выполнено (ничего не применено):"
    rules | sed 's/^/  /'
    echo "  systemd-run --unit=${FAILSAFE_UNIT} --on-active=${FAILSAFE_MIN}m ufw disable   # страховка до --confirm"
    echo "  ufw --force enable"
    ;;
  --apply)
    need_root
    preflight
    systemctl stop "${FAILSAFE_UNIT}.timer" 2>/dev/null || true
    # Страховка ставится ДО включения: потеряли доступ — через FAILSAFE_MIN минут ufw выключится сам.
    systemd-run --quiet --unit="$FAILSAFE_UNIT" --on-active="${FAILSAFE_MIN}m" /usr/sbin/ufw disable
    log "Страховка: ufw выключится через ${FAILSAFE_MIN} мин, если не вызвать --confirm"
    # shellcheck disable=SC2046
    while IFS= read -r cmd; do eval "$cmd" >/dev/null; done < <(rules)
    ufw --force enable >/dev/null
    log "ufw включён"
    sleep 2
    if [[ "$TOR_BEFORE" == ok ]] && ! tor_reachable_from_container "$(docker_gateway)"; then
      log "ОШИБКА: контейнер не достаёт до Tor ${COMPOSE_NETWORK} после включения — откат"
      ufw disable >/dev/null
      systemctl stop "${FAILSAFE_UNIT}.timer" 2>/dev/null || true
      exit 1
    fi
    if [[ "$TOR_BEFORE" == ok ]]; then
      log "Tor из контейнера после правил: ok"
    else
      log "ВНИМАНИЕ: Tor из контейнера не отвечал и ДО правил — проверьте tor.service отдельно (ufw ни при чём)"
    fi
    ufw status verbose
    log "Теперь из ВТОРОГО окна: новое ssh-подключение; https://forecasteconomy.com ; затем --confirm"
    ;;
  --confirm)
    need_root
    [[ "$(ufw status | head -1)" == "Status: active" ]] || { echo "ufw не активен" >&2; exit 1; }
    systemctl stop "${FAILSAFE_UNIT}.timer"
    log "Страховка снята, ufw остаётся включённым"
    ;;
  --rollback)
    need_root
    systemctl stop "${FAILSAFE_UNIT}.timer" 2>/dev/null || true
    ufw disable
    log "ufw выключен (правила сохранены: ufw status verbose; --reset удалит их)"
    ;;
  --reset)
    need_root
    systemctl stop "${FAILSAFE_UNIT}.timer" 2>/dev/null || true
    ufw --force reset
    log "ufw выключен, правила удалены"
    ;;
  --status)
    ufw status verbose
    systemctl list-timers "${FAILSAFE_UNIT}.timer" --no-pager 2>/dev/null | head -3 || true
    ;;
  *)
    echo "Использование: $0 [--dry-run|--apply|--confirm|--rollback|--reset|--status]" >&2
    exit 2
    ;;
esac
