#!/usr/bin/env bash
# Живая проверка защиты от ботов на боевом после выпуска (14.11.2026, ADR-0026 дополнения 14.11). ТОЛЬКО ЧТЕНИЕ:
# ничего не меняет, не перезапускает и не пишет; один короткий проход по ssh.
#   Использование: deploy/verify-bot-defense-live.sh [минут=15] [--expect-note]
#   HOST (по умолчанию fe-prod), SSH_OPTS - дополнительные ключи ssh (при VPN: "-o ProxyCommand='nc -b en0 %h %p'").
#   --expect-note - заметка bot_traffic за сутки обязательна (проверять с утра после первой ночи после выпуска).
# Что проверяется: флаги frontend и файлы /etc/nginx/fe-pass/ согласованы; nginx -t; журналы pass-observe.log и
# human429.log на месте; классы security.log за последние N минут (у проверенных поисковиков нет 429); сбор
# bot_traffic не падает; заметка bot_traffic в архиве Telegram за сутки. Выход: 0 - всё в порядке, 1 - есть провал.
set -euo pipefail
MINUTES="${1:-15}"
EXPECT_NOTE=0
for arg in "$@"; do [ "$arg" = "--expect-note" ] && EXPECT_NOTE=1; done
case "$MINUTES" in ''|*[!0-9]*) MINUTES=15 ;; esac
HOST="${HOST:-fe-prod}"
# shellcheck disable=SC2086
ssh -o ConnectTimeout=60 -o ServerAliveInterval=60 ${SSH_OPTS:-} "$HOST" \
  "MINUTES=$MINUTES EXPECT_NOTE=$EXPECT_NOTE bash -s" <<'REMOTE'
set -uo pipefail
cd /opt/rosstat || { echo "ПРОВАЛ: нет /opt/rosstat"; exit 1; }
fails=0; warns=0
ok()   { echo "  ок      $*"; }
warn() { echo "  внимание $*"; warns=$((warns + 1)); }
fail() { echo "  ПРОВАЛ  $*"; fails=$((fails + 1)); }
fe() { docker compose exec -T frontend "$@" </dev/null 2>/dev/null; }

echo "== флаги frontend и файлы /etc/nginx/fe-pass/"
files=$(fe ls /etc/nginx/fe-pass/ | tr '\n' ' ')
echo "  файлы: ${files:-нет}"
secret_set=$(fe sh -c '[ -n "${FE_HUMAN_PASS_SECRET:-}" ] && echo 1 || echo 0')
if [ "$secret_set" = 1 ]; then
  case " $files " in *" secret.conf "*) ok "пропуск человека включён (секрет задан, secret.conf есть)";; *) fail "секрет задан, а secret.conf нет - пропуск не действует";; esac
else
  warn "FE_HUMAN_PASS_SECRET не задан - пропуск человека выключен"
fi
check_flag() {  # $1 переменная, $2 значение по умолчанию, $3 файл, $4 значения, при которых файл должен быть
  local val; val=$(fe printenv "$1"); val="${val:-$2}"
  local want=0; case " $4 " in *" $val "*) want=1;; esac
  local has=0; case " $files " in *" $3 "*) has=1;; esac
  if [ "$want" = "$has" ]; then ok "$1=$val, файл $3 $([ "$has" = 1 ] && echo есть || echo нет) - как должно быть"
  else fail "$1=$val, а файл $3 $([ "$has" = 1 ] && echo есть || echo нет) - флаг не применён (пересоздать frontend)"; fi
}
check_flag FE_GOOGLE_FARM_LIMIT 1 google-farm.conf "0 off false no"
check_flag FE_PASS_BIND observe pass-bind.conf "0 off false no 1 on true yes"
check_flag FE_PASS_MINT_NET_LIMIT 1 pass-mint.conf "0 off false no"
bind=$(fe printenv FE_PASS_BIND); [ "${bind:-observe}" = 1 ] && warn "FE_PASS_BIND=1 - привязка действует; включать только по замеру (runbook, шаг 9)"

echo "== nginx"
if fe nginx -t >/dev/null 2>&1; then ok "nginx -t"; else fail "nginx -t не проходит"; fi
for zone in gfarmcold passmintnet; do
  if fe grep -q "zone=$zone" /etc/nginx/conf.d/default.conf; then ok "зона $zone в конфиге"; else fail "зоны $zone нет - выпущен старый frontend"; fi
done

echo "== журналы /var/log/rosstat-nginx"
for f in security.log pass-observe.log human429.log; do
  p=/var/log/rosstat-nginx/$f
  if [ -f "$p" ]; then ok "$f: $(wc -l < "$p") строк, изменён $(date -r "$p" '+%d.%m %H:%M')"
  else fail "$f нет - nginx не пишет журнал (старый конфиг или нет тома)"; fi
done
# Строку браузера (в кавычках) не смотрим: версия «Chrome/148.0.7778.97» похожа на IP (ложная тревога 15.11.2026).
if [ -f /var/log/rosstat-nginx/pass-observe.log ] && sed 's/"[^"]*"//g' /var/log/rosstat-nginx/pass-observe.log | grep -Eq '(^|[^0-9.])([0-9]{1,3}\.){3}[0-9]{1,3}([^0-9.]|$)'; then
  fail "в pass-observe.log есть IP целиком"
fi

echo "== классы security.log за последние $MINUTES мин"
since=$(date -u -d "-$MINUTES min" +%Y-%m-%dT%H:%M:%S)
tail -n 300000 /var/log/rosstat-nginx/security.log | awk -v s="$since" 'substr($1,1,19) >= s' > /tmp/vbd.$$ || true
total=$(wc -l < /tmp/vbd.$$)
echo "  запросов: $total"
grep -o 'cls=[a-z]*' /tmp/vbd.$$ | sort | uniq -c | sort -rn | sed 's/^/    /'
[ "$total" -gt 0 ] && ok "security.log пишется" || fail "за $MINUTES мин в security.log нет строк"
crawler429=$(grep -c ' 429 .*cls=crawler$' /tmp/vbd.$$ || true)
[ "${crawler429:-0}" = 0 ] && ok "проверенные поисковики без 429" || fail "проверенные поисковики получили 429: $crawler429"
gfarm=$(grep -c 'cls=gfarm$' /tmp/vbd.$$ || true)
linuxref=$(grep 'X11; Linux x86_64' /tmp/vbd.$$ | grep -c 'cls=referred$' || true)
if [ "${gfarm:-0}" -gt 0 ]; then ok "ферма с Referer Google видна как gfarm: $gfarm"
else warn "gfarm за $MINUTES мин нет (ферма могла уйти; Linux Chrome как referred: ${linuxref:-0})"; fi
rm -f /tmp/vbd.$$

echo "== сбор bot_traffic (scheduler)"
errs=$(docker compose logs --since 30m scheduler </dev/null 2>/dev/null | grep -c 'bot_traffic collect failed' || true)
[ "${errs:-0}" = 0 ] && ok "сбор без ошибок за 30 мин" || fail "сбор bot_traffic падал $errs раз за 30 мин"

echo "== заметка bot_traffic в утренней сводке"
note=$(docker compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "select count(*) from telegram_outbox where kind = '"'"'bot_traffic'"'"' and sent_at > now() - interval '"'"'26 hours'"'"'"' </dev/null 2>/dev/null | tr -d '[:space:]')
if [ "${note:-0}" -gt 0 ] 2>/dev/null; then ok "заметка bot_traffic за сутки есть ($note)"
elif [ "$EXPECT_NOTE" = 1 ]; then fail "заметки bot_traffic за сутки нет"
else warn "заметки bot_traffic пока нет (появляется после 08:45 МСК следующего дня; проверить с --expect-note)"; fi

echo
if [ "$fails" -gt 0 ]; then echo "ИТОГ: защита от ботов - есть провалы ($fails), внимание: $warns"; exit 1; fi
echo "ИТОГ: защита от ботов работает, замечаний: $warns"
REMOTE
