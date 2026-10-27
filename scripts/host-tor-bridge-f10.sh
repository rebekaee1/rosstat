#!/usr/bin/env bash
# F10: Tor HTTP-мост на хосте прода без зашитого пароля и без логирования заголовков.
# ПОДГОТОВКА — на проде не применялось. Пошаговый текст — deploy/tor-http-bridge/README.md.
#
# Замер 2026-10-27 (только чтение):
#   * на хосте работает СТАРЫЙ мост: /opt/tor-http-bridge/tor_http_bridge.py (0644, root) с зашитыми
#     AUTH_USER/AUTH_PASS, unit без EnvironmentFile, /etc/tor-http-bridge.env нет;
#   * в журнале юнита 7 строк с Proxy-Authorization (все от 2026-08-27);
#   * мост простаивает (в последний час 0 строк, установленных соединений на :8888 нет) — это резерв;
#   * ВАЖНО: пароль из RUSTATS_OPENROUTER_PROXY_URL (боевой relay 5.129.210.89:8888) ТОЖЕ САМЫЙ, что зашит
#     в старом мосте (сравнение хэшей на хосте, значение не выводилось). Смена пароля только на хосте
#     скомпрометированный пароль relay не отменяет: relay надо менять отдельно (см. вывод --apply).
#
# Режимы (по умолчанию --dry-run: ничего не меняет):
#   scripts/host-tor-bridge-f10.sh --dry-run
#   scripts/host-tor-bridge-f10.sh --apply [--purge-journal]
#   scripts/host-tor-bridge-f10.sh --verify
#   scripts/host-tor-bridge-f10.sh --rollback     вернуть старые файлы (возвращает и СТАРЫЙ пароль в файле)
# Запускать на сервере под root из каталога с репозиторием (по умолчанию /opt/rosstat).
set -euo pipefail

MODE="${1:---dry-run}"
PURGE="${2:-}"
REPO="${REPO:-/opt/rosstat}"
SRC_PY="$REPO/deploy/tor-http-bridge/tor_http_bridge.py"
SRC_UNIT="$REPO/deploy/tor-http-bridge/tor-http-bridge.service"
DST_DIR="${DST_DIR:-/opt/tor-http-bridge}"
DST_PY="$DST_DIR/tor_http_bridge.py"
DST_UNIT="${DST_UNIT:-/etc/systemd/system/tor-http-bridge.service}"
ENV_FILE="${ENV_FILE:-/etc/tor-http-bridge.env}"
BRIDGE_HOST="${BRIDGE_HOST:-172.18.0.1}"
BRIDGE_PORT="${BRIDGE_PORT:-8888}"
SUFFIX=".before-f10"

log() { echo "[host-tor-bridge-f10] $*"; }
need_root() { [[ $EUID -eq 0 ]] || { echo "нужен root" >&2; exit 1; }; }

# Проверка моста сырым CONNECT: без пароля обязан быть 407; с паролем из env-файла — 200 (через Tor).
# Пароль читается процессом и не печатается.
probe() {
  python3 - "$BRIDGE_HOST" "$BRIDGE_PORT" "$ENV_FILE" <<'PY'
import base64, socket, sys
host, port, env_path = sys.argv[1], int(sys.argv[2]), sys.argv[3]

def status(extra=""):
    s = socket.create_connection((host, port), timeout=15)
    s.sendall(f"CONNECT example.org:443 HTTP/1.1\r\nHost: example.org:443\r\n{extra}\r\n".encode())
    line = s.recv(200).split(b"\r\n", 1)[0].decode(errors="replace")
    s.close()
    return line

no_auth = status()
print("без пароля:", no_auth)
ok = " 407 " in no_auth + " "
env = dict(l.strip().split("=", 1) for l in open(env_path) if "=" in l and not l.startswith("#"))
token = base64.b64encode(f"{env['BRIDGE_AUTH_USER']}:{env['BRIDGE_AUTH_PASS']}".encode()).decode()
with_auth = status(f"Proxy-Authorization: Basic {token}\r\n")
print("с паролем из env-файла:", with_auth)
ok = ok and " 200" in with_auth
sys.exit(0 if ok else 1)
PY
}

leak_lines() {
  # Строки журнала юнита, где есть заголовок авторизации (вообще, не только новые).
  journalctl -u tor-http-bridge --no-pager -o cat 2>/dev/null | grep -c "Proxy-Authorization" || true
}

case "$MODE" in
  --dry-run)
    log "Исходники: $SRC_PY, $SRC_UNIT — $( [[ -f $SRC_PY && -f $SRC_UNIT ]] && echo найдены || echo 'НЕТ (скопируйте deploy/tor-http-bridge/ на сервер)' )"
    [[ -f $SRC_PY ]] && python3 -m py_compile "$SRC_PY" && log "синтаксис tor_http_bridge.py: ok"
    log "Сейчас: unit $(systemctl is-active tor-http-bridge 2>/dev/null || true); env-файл: $( [[ -f $ENV_FILE ]] && stat -c '%a %U' "$ENV_FILE" || echo нет ); файл моста: $(stat -c '%a %U' "$DST_PY" 2>/dev/null || echo нет)"
    log "Строк журнала моста с Proxy-Authorization: $(leak_lines)"
    log "Будет выполнено:"
    cat <<EOF
  cp -p $DST_PY ${DST_PY}${SUFFIX};  cp -p $DST_UNIT ${DST_UNIT}${SUFFIX}
  install -m 755 $SRC_PY $DST_PY;  install -m 644 $SRC_UNIT $DST_UNIT
  новый пароль: openssl rand -hex 24 -> $ENV_FILE (0600, пользователь pulse_relay), на экран не выводится
  systemctl daemon-reload && systemctl restart tor-http-bridge
  проверка: без пароля 407, с паролем 200; в новых строках журнала нет Proxy-Authorization
  [--purge-journal] journalctl --rotate && journalctl --vacuum-time=14d  (только записи старше 14 суток)
EOF
    ;;
  --apply)
    need_root
    [[ -f $SRC_PY && -f $SRC_UNIT ]] || { echo "нет $SRC_PY / $SRC_UNIT" >&2; exit 1; }
    python3 -m py_compile "$SRC_PY"
    [[ -f ${DST_PY}${SUFFIX} ]] || cp -p "$DST_PY" "${DST_PY}${SUFFIX}"
    [[ -f ${DST_UNIT}${SUFFIX} ]] || cp -p "$DST_UNIT" "${DST_UNIT}${SUFFIX}"
    install -m 755 "$SRC_PY" "$DST_PY"
    install -m 644 "$SRC_UNIT" "$DST_UNIT"
    ( umask 077
      printf 'BRIDGE_AUTH_USER=pulse_relay\nBRIDGE_AUTH_PASS=%s\n' "$(openssl rand -hex 24)" > "$ENV_FILE" )
    chmod 600 "$ENV_FILE"
    systemctl daemon-reload
    systemctl restart tor-http-bridge
    sleep 3
    systemctl is-active --quiet tor-http-bridge || { log "ОШИБКА: unit не запустился — journalctl -u tor-http-bridge -n 30; откат: --rollback"; exit 1; }
    if probe; then log "проверка моста: ok"; else log "ПРОВЕРКА НЕ ПРОШЛА — откат: --rollback"; exit 1; fi
    NEW="$(journalctl -u tor-http-bridge --since '-2min' --no-pager -o cat | grep -c 'Proxy-Authorization' || true)"
    log "Proxy-Authorization в новых строках журнала: $NEW (должно быть 0)"
    if [[ "$PURGE" == "--purge-journal" ]]; then
      journalctl --rotate
      journalctl --vacuum-time=14d
      log "Строк журнала моста с Proxy-Authorization после чистки: $(leak_lines)"
    else
      log "Журнал не чистился (старые 7 строк от 2026-08-27 уйдут с --purge-journal или по лимиту journald, см. install-host-disk-hygiene.sh)"
    fi
    cat <<EOF

ВАЖНО (владельцу): старый пароль моста СОВПАДАЕТ с паролем боевого relay в RUSTATS_OPENROUTER_PROXY_URL
(${BRIDGE_HOST} — резерв, relay — 5.129.210.89:8888). Новый пароль моста относится только к резерву.
Чтобы закрыть утечку на боевом пути, на САМОМ relay задайте новый пароль и затем обновите
RUSTATS_OPENROUTER_PROXY_URL в /opt/rosstat/.env и пересоздайте scheduler:
  docker compose up -d --force-recreate scheduler
Переключение на резервный мост: RUSTATS_OPENROUTER_PROXY_URL=http://pulse_relay:<пароль из $ENV_FILE>@${BRIDGE_HOST}:${BRIDGE_PORT}
EOF
    ;;
  --verify)
    log "unit: $(systemctl is-active tor-http-bridge)"
    probe
    log "Proxy-Authorization в журнале (всего): $(leak_lines)"
    ;;
  --rollback)
    need_root
    [[ -f ${DST_PY}${SUFFIX} && -f ${DST_UNIT}${SUFFIX} ]] || { echo "нет резервных копий ${SUFFIX}" >&2; exit 1; }
    cp -p "${DST_PY}${SUFFIX}" "$DST_PY"
    cp -p "${DST_UNIT}${SUFFIX}" "$DST_UNIT"
    rm -f "$ENV_FILE"
    systemctl daemon-reload
    systemctl restart tor-http-bridge
    log "Откат выполнен: вернулись старый файл (с зашитым паролем) и старый unit; unit $(systemctl is-active tor-http-bridge)"
    ;;
  *)
    echo "Использование: $0 [--dry-run|--apply [--purge-journal]|--verify|--rollback]" >&2
    exit 2
    ;;
esac
