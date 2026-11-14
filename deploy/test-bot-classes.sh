#!/usr/bin/env bash
# Поведенческая проверка классов роботов и пропуска человека (08.11.2026, дополнение ADR-0026; нужен docker).
# Фиктивный backend возвращает класс, который ему передал nginx (X-FE-Client-Class); nginx - конфиг из репозитория
# с секретом пропуска. Проверяется:
#   (1) Applebot/TelegramBot/OAI-SearchBot из своих официальных сетей -> goodbot, из чужих -> robot (самозванец);
#   (2) предпросмотр (facebookexternalhit) -> robot, честный робот -> robot, браузер без Referer -> anon;
#   (3) действующий пропуск fe_pass -> human; подделанная подпись, истёкший срок, мусор -> anon;
#   (4) общий бюджет роботов robotcold: 120 запросов с разных IP с UA «SomeBot» -> часть 429, проверенный Applebot
#       в те же секунды -> все 200; ферма без Referer с пропуском, скопированным на 40 адресов -> часть 429 (один бюджет);
#   (5) выдача пропуска POST /api/v1/human-pass доходит до backend; entrypoint-скрипт пишет секрет и отвергает плохой.
set -euo pipefail
cd "$(dirname "$0")/.."
IMAGE="${IMAGE:-nginx:alpine}"
SECRET="test_secret_0123456789abcdefghijklmnopqrstuv"
T="$(mktemp -d)"; trap 'docker rm -f bcup bcngx >/dev/null 2>&1; docker network rm bcnet >/dev/null 2>&1; rm -rf "$T"' EXIT
cat > "$T/up.py" <<'PY'
import time
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
class H(BaseHTTPRequestHandler):
    def _send(self, body):
        self.send_response(200); self.send_header("Content-Type", "text/html"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
    def do_GET(self):
        if self.path.startswith("/api/echo-bind"):  # что доходит до backend в X-FE-Pass-Bind по общему /api/
            return self._send(("bind=" + (self.headers.get("X-FE-Pass-Bind") or "")).encode("latin-1"))
        time.sleep(0.05); self._send((self.headers.get("X-FE-Client-Class") or "none").encode())
    def do_POST(self):
        self._send(b"minted:" + (self.headers.get("X-FE-Client-Class") or "none").encode()
                   + b"|bind=" + (self.headers.get("X-FE-Pass-Bind") or "").encode("latin-1"))
    def log_message(self, *a): pass
ThreadingHTTPServer(("0.0.0.0", 8000), H).serve_forever()
PY
mkdir -p "$T/fe-pass"
# entrypoint-скрипт: плохой секрет -> файла нет; хороший -> файл с set
docker run --rm -e FE_HUMAN_PASS_SECRET='bad"secret' -v "$PWD/frontend/40-fe-human-pass.sh:/s.sh:ro" -v "$T/fe-pass:/etc/nginx/fe-pass" "$IMAGE" sh /s.sh >/dev/null 2>&1
[ ! -e "$T/fe-pass/secret.conf" ] || { echo "FAIL: плохой секрет записан"; exit 1; }
docker run --rm -e FE_HUMAN_PASS_SECRET="$SECRET" -v "$PWD/frontend/40-fe-human-pass.sh:/s.sh:ro" -v "$T/fe-pass:/etc/nginx/fe-pass" "$IMAGE" sh /s.sh >/dev/null
grep -q "set \$fe_pass_secret \"$SECRET\";" "$T/fe-pass/secret.conf" || { echo "FAIL: секрет не записан"; exit 1; }
docker network create bcnet >/dev/null
docker run -d --rm --name bcup --network bcnet --network-alias backend -v "$T/up.py:/up.py:ro" python:3.12-slim python /up.py >/dev/null
docker run -d --rm --name bcngx --network bcnet \
  -v "$PWD/frontend/nginx.conf:/etc/nginx/conf.d/default.conf:ro" \
  -v "$PWD/frontend/search-crawlers.conf:/etc/nginx/search-crawlers.conf:ro" \
  -v "$T/fe-pass:/etc/nginx/fe-pass:ro" \
  "$IMAGE" sh -c 'mkdir -p /usr/share/nginx/html /var/log/nginx/security; echo busy > /usr/share/nginx/html/429.html; touch /var/log/nginx/security/security.log /var/log/nginx/security/honeypot.log; nginx -g "daemon off;"' >/dev/null
sleep 3
docker exec bcngx nginx -t 2>&1 | grep -q "test is successful"
# Подпись так же, как backend (app/api/human_pass.py): base64url(md5("<срок><id> <привязка><секрет>")) без '=';
# привязка (14.11.2026, FE_PASS_BIND=1 по умолчанию) - "<сеть /24>|<UA> ", без неё - пусто (прежняя подпись).
mkpass() {  # $1 срок unix, $2 id, $3 секрет, $4 привязка или пусто
  python3 -c 'import base64,hashlib,sys; e,i,s,b=sys.argv[1:]; print(base64.urlsafe_b64encode(hashlib.md5(f"{e}{i} {b}{s}".encode()).digest()).decode().rstrip("=")+f".{e}.{i}")' "$1" "$2" "$3" "${4:-}"
}
bindfor() {  # $1 IPv4, $2 UA -> строка привязки, как её собирает nginx
  printf '%s|%s ' "${1%.*}" "$2"
}
NOW=$(date +%s)
B='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
GOOD=$(mkpass $((NOW+86400)) 0123456789abcdef "$SECRET" "$(bindfor 93.1.1.6 "$B")")
FORGED=$(mkpass $((NOW+86400)) 0123456789abcdef "wrong_secret_0123456789abcdefghijklmn" "$(bindfor 93.1.1.7 "$B")")
EXPIRED=$(mkpass $((NOW-60)) 0123456789abcdef "$SECRET" "$(bindfor 93.1.1.8 "$B")")
COPIED=$(mkpass $((NOW+86400)) 0123456789abcdef "$SECRET" "$(bindfor 95.20.1.1 "$B")")
URL="http://bcngx/united-states/region/texas/bea-sagdp1-1/2008"
cls() {  # $1 XFF, $2 UA, $3 cookie fe_pass или пусто
  docker run --rm --network bcnet -e XFF="$1" -e UA="$2" -e PASS="$3" -e URL="$URL" curlimages/curl sh -c '
    set -- -s -m 30 -A "$UA" -H "X-Forwarded-For: $XFF"
    [ -z "$PASS" ] || set -- "$@" -b "fe_pass=$PASS"
    curl "$@" "$URL"'
}
r1=$(cls 17.241.208.161 'Mozilla/5.0 (Macintosh) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15 (Applebot/0.1)' '')
r2=$(cls 93.1.1.1 'Mozilla/5.0 (compatible; Applebot/0.1)' '')
r3=$(cls 149.154.161.1 'TelegramBot (like TwitterBot)' '')
r4=$(cls 93.1.1.2 'TelegramBot (like TwitterBot)' '')
OAI_IP=$(python3 -c 'import re,ipaddress;t=open("frontend/search-crawlers.conf").read();b=re.search(r"geo \$openai_bot_net \{(.*?)\n\}",t,re.S).group(1);n=ipaddress.ip_network(re.search(r"^\s+([0-9.]+/\d+) 1;",b,re.M).group(1));print(n.network_address+1)')
r5=$(cls "$OAI_IP" 'Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; OAI-SearchBot/1.3; +https://openai.com/searchbot' '')
r6=$(cls 93.1.1.3 'facebookexternalhit/1.1' '')
r7=$(cls 93.1.1.4 'Mozilla/5.0 (compatible; SomeBot/1.0)' '')
r8=$(cls 93.1.1.5 "$B" '')
r9=$(cls 93.1.1.6 "$B" "$GOOD")
r10=$(cls 93.1.1.7 "$B" "$FORGED")
r11=$(cls 93.1.1.8 "$B" "$EXPIRED")
r12=$(cls 93.1.1.9 "$B" 'garbage')
got="$r1 $r2 $r3 $r4 $r5 $r6 $r7 $r8 $r9 $r10 $r11 $r12"
echo "классы: $got"
[ "$got" = "goodbot robot goodbot robot goodbot robot robot anon human anon anon anon" ] || { echo "FAIL: классы"; exit 1; }
# (4) общий бюджет роботов и пропуск, скопированный на много адресов
burst() {  # $1 префикс IP, $2 UA, $3 число запросов, $4 cookie или пусто, $5 первый октет адреса (по умолчанию 1)
  docker run --rm --network bcnet -e IP="$1" -e UA="$2" -e N="$3" -e PASS="$4" -e OFF="${5:-1}" -e URL="$URL" curlimages/curl sh -c '
    for i in $(seq 1 $N); do
      ( set -- -s -o /dev/null -w "%{http_code}\n" -m 30 -A "$UA" -H "X-Forwarded-For: $IP.$((OFF + i % 250))"
        [ -z "$PASS" ] || set -- "$@" -b "fe_pass=$PASS"
        curl "$@" "$URL" ) &
    done; wait' | sort | uniq -c | tr '\n' ' '
}
sleep 2
(burst 94.10.1 'Mozilla/5.0 (compatible; SomeBot/1.0)' 120 '' > "$T/robots.txt") &
# Адреса 17.241.208.161-190 лежат в официальной сети Apple 17.241.208.160/27 (search-crawlers.conf).
(burst 17.241.208 'Mozilla/5.0 (Applebot/0.1)' 29 '' 161 > "$T/apple.txt") &
wait
rb=$(cat "$T/robots.txt"); ap=$(cat "$T/apple.txt")
echo "120 честных роботов разом     : $rb"; echo "Applebot в те же секунды (29) : $ap"
case "$rb" in *429*) ;; *) echo "FAIL: общий бюджет роботов не работает"; exit 1;; esac
case "$ap" in *429*) echo "FAIL: проверенный Applebot получил 429"; exit 1;; esac
sleep 12
cp=$(burst 95.20.1 "$B" 60 "$COPIED"); echo "один пропуск на 60 адресах    : $cp"
case "$cp" in *429*) ;; *) echo "FAIL: скопированный пропуск не ограничен"; exit 1;; esac
# (5) выдача пропуска проходит до backend
m=$(docker run --rm --network bcnet curlimages/curl -s -m 30 -X POST -H 'X-Forwarded-For: 96.1.1.1' -H 'X-FE-Pass-Request: 1' -A "$B" http://bcngx/api/v1/human-pass)
[ "$m" = "minted:anon|bind=96.1.1|$B " ] || { echo "FAIL: выдача пропуска: $m"; exit 1; }
# (6) ферма с подставленным Referer Google (14.11.2026): Linux Chrome + Referer ровно корень google.com + нет _ym_uid ->
#     класс gfarm со СВОИМ бюджетом gfarmcold (backend видит anon); cookie Метрики, путь в Referer, Windows, Edge -> referred;
#     с пропуском -> human; Googlebot -> crawler. Ферма шумит ~20 зап/с - прямой посетитель без Referer получает 200;
#     человек с отпечатком фермы после 429 получает пропуск (запрос страницы 429) и проходит; флаг 0 -> referred.
clsr() {  # $1 XFF, $2 UA, $3 Referer или пусто, $4 Cookie или пусто
  docker run --rm --network bcnet -e XFF="$1" -e UA="$2" -e REF="$3" -e CK="$4" -e URL="$URL" curlimages/curl sh -c '
    set -- -s -m 30 -A "$UA" -H "X-Forwarded-For: $XFF"
    [ -z "$REF" ] || set -- "$@" -e "$REF"
    [ -z "$CK" ] || set -- "$@" -b "$CK"
    curl "$@" "$URL"'
}
logcls() {  # класс nginx в security.log для адреса $1 (последняя строка)
  docker exec bcngx sh -c "grep ' $1 ' /var/log/nginx/security/security.log | tail -1 | sed 's/.*cls=//'"
}
LX='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/157.0.0.0 Safari/537.36'
EDGE_LX="$LX Edg/157.0.0.0"
G='https://www.google.com/'
GB_IP=$(python3 -c 'import re,ipaddress;t=open("frontend/search-crawlers.conf").read();m=re.search(r"^\s+(66\.249\.[0-9.]+/\d+) 1;",t,re.M);print(ipaddress.ip_network(m.group(1)).network_address+1)')
sleep 12
clsr 97.1.1.1 "$LX" "$G" '' >/dev/null
clsr 97.1.1.2 "$LX" "$G" '_ym_uid=1731500000123456789' >/dev/null
clsr 97.1.1.3 "$LX" 'https://www.google.com/search?q=x' '' >/dev/null
clsr 97.1.1.4 "$B" "$G" '' >/dev/null
clsr 97.1.1.5 "$EDGE_LX" "$G" '' >/dev/null
clsr 97.1.1.6 "$LX" "$G" "fe_pass=$(mkpass $((NOW+86400)) 00000000000000a6 "$SECRET" "$(bindfor 97.1.1.6 "$LX")")" >/dev/null
clsr "$GB_IP" 'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)' '' '' >/dev/null
gg="$(logcls 97.1.1.1) $(logcls 97.1.1.2) $(logcls 97.1.1.3) $(logcls 97.1.1.4) $(logcls 97.1.1.5) $(logcls 97.1.1.6) $(logcls "$GB_IP")"
echo "ферма с Referer Google        : $gg"
[ "$gg" = "gfarm referred referred referred referred human crawler" ] || { echo "FAIL: классы фермы с Referer Google"; exit 1; }
[ "$(clsr 97.1.1.7 "$LX" "$G" '')" = "anon" ] || { echo "FAIL: backend должен видеть ферму как anon"; exit 1; }
# Ферма шумит ~20 зап/с 4 секунды с разных адресов; в те же секунды прямой посетитель (без Referer) - раз в 0,6 с.
sleep 6
docker run --rm --network bcnet -e UA="$LX" -e URL="$URL" curlimages/curl sh -c '
  for i in $(seq 1 80); do curl -s -o /dev/null -w "%{http_code}\n" -m 30 -A "$UA" -e "https://www.google.com/" -H "X-Forwarded-For: 99.40.$((i / 200)).$((i % 200 + 1))" "$URL" & sleep 0.05; done; wait' \
  | sort | uniq -c | tr '\n' ' ' > "$T/gfarm.txt" &
FARM_PID=$!
direct=$(docker run --rm --network bcnet -e UA="$B" -e URL="$URL" curlimages/curl sh -c '
  for i in 1 2 3 4 5 6; do curl -s -o /dev/null -w "%{http_code}\n" -m 30 -A "$UA" -H "X-Forwarded-For: 98.50.1.$i" "$URL"; sleep 0.6; done' | sort | uniq -c | tr '\n' ' ')
wait $FARM_PID
gf=$(cat "$T/gfarm.txt")
echo "ферма ~20 зап/с (80)          : $gf"
echo "прямой посетитель в те же сек.: $direct"
case "$gf" in *429*) ;; *) echo "FAIL: ферма с Referer Google не ограничена своим бюджетом"; exit 1;; esac
case "$direct" in *429*) echo "FAIL: ферма вытеснила прямого посетителя"; exit 1;; esac
# Человек с Linux Chrome из Google без cookie Метрики (первый заход) под шумом фермы: 429 -> страница отказа сама берёт
# пропуск (POST /api/v1/human-pass, Referer - адрес нашей страницы) -> перезагрузка с пропуском -> human, 200.
sleep 6
hc=$(docker run --rm --network bcnet -e UA="$LX" -e URL="$URL" curlimages/curl sh -c '
  ( for i in $(seq 1 60); do curl -s -o /dev/null -m 30 -A "$UA" -e "https://www.google.com/" -H "X-Forwarded-For: 99.41.1.$i" "$URL" & sleep 0.05; done; wait ) &
  sleep 1.5
  for t in 1 2 3; do curl -s -o /dev/null -w "%{http_code} " -m 30 -A "$UA" -e "https://www.google.com/" -H "X-Forwarded-For: 97.2.2.2" "$URL"; sleep 0.3; done
  wait')
mint=$(docker run --rm --network bcnet curlimages/curl -s -m 30 -X POST -H 'X-Forwarded-For: 97.2.2.2' -H 'X-FE-Pass-Request: 1' -A "$LX" -e "$URL" http://bcngx/api/v1/human-pass)
case "$mint" in *"|bind=97.2.2|$LX ") ;; *) echo "FAIL: backend не получил привязку пропуска: $mint"; exit 1;; esac
after=$(clsr 97.2.2.2 "$LX" "$G" "fe_pass=$(mkpass $((NOW+86400)) 00000000000000b7 "$SECRET" "$(bindfor 97.2.2.2 "$LX")")")
echo "человек с отпечатком фермы    : первый заход $hc, выдача пропуска $mint, после пропуска $after"
# Три попытки в разгар шума: свободный слот бюджета появляется раз в 0,5 с, его может перехватить и человек.
case "$hc" in *429*) ;; *) echo "FAIL: под шумом фермы ожидался 429 у первого захода, получено $hc"; exit 1;; esac
case "$mint" in minted:*) ;; *) echo "FAIL: выдача пропуска не дошла до backend: $mint"; exit 1;; esac
[ "$after" = "human" ] || { echo "FAIL: с пропуском человек не прошёл: $after"; exit 1; }
# Флаг: FE_GOOGLE_FARM_LIMIT=0 -> entrypoint пишет переопределение, после reload правило выключено.
docker run --rm -e FE_GOOGLE_FARM_LIMIT=0 -v "$PWD/frontend/41-fe-google-farm.sh:/s.sh:ro" -v "$T/fe-pass:/etc/nginx/fe-pass" "$IMAGE" sh /s.sh >/dev/null
grep -q 'set $fe_google_farm_limit "0";' "$T/fe-pass/google-farm.conf" || { echo "FAIL: флаг не записан"; exit 1; }
docker exec bcngx nginx -s reload >/dev/null 2>&1; sleep 2
off=$(clsr 97.1.1.9 "$LX" "$G" '')
[ "$off" = "referred" ] || { echo "FAIL: флаг выключения не действует: $off"; exit 1; }
docker run --rm -e FE_GOOGLE_FARM_LIMIT=1 -v "$PWD/frontend/41-fe-google-farm.sh:/s.sh:ro" -v "$T/fe-pass:/etc/nginx/fe-pass" "$IMAGE" sh /s.sh >/dev/null
[ ! -e "$T/fe-pass/google-farm.conf" ] || { echo "FAIL: включённый флаг оставил файл"; exit 1; }
docker exec bcngx nginx -s reload >/dev/null 2>&1; sleep 2
# (7) привязка пропуска к сети /24 и UA (14.11.2026): ферма с JS, взявшая пропуск, не размножит его по адресам.
P7=$(mkpass $((NOW+86400)) 00000000000000c7 "$SECRET" "$(bindfor 93.7.7.7 "$B")")
b1=$(cls 93.7.7.7 "$B" "$P7")              # свой адрес
b2=$(cls 93.7.7.200 "$B" "$P7")            # та же сеть /24 (мобильный оператор сменил адрес в сети)
b3=$(cls 94.7.7.7 "$B" "$P7")              # чужой адрес - пропуск скопирован
b4=$(cls 93.7.7.7 "$LX" "$P7")             # другой UA
OLD=$(mkpass $((NOW+86400)) 00000000000000d7 "$SECRET")   # прежняя подпись без привязки
b5=$(cls 93.7.7.8 "$B" "$OLD")
P6=$(mkpass $((NOW+86400)) 00000000000000e7 "$SECRET" "2a00:1fa0:4:a1b2|$B ")   # IPv6: первые четыре группы
b6=$(cls 2a00:1fa0:4:a1b2::99 "$B" "$P6"); b7=$(cls 2a00:1fa0:4:ffff::1 "$B" "$P6")
bb="$b1 $b2 $b3 $b4 $b5 $b6 $b7"
echo "привязка пропуска             : $bb"
[ "$bb" = "human human anon anon anon human anon" ] || { echo "FAIL: привязка пропуска"; exit 1; }
spoof=$(docker run --rm --network bcnet curlimages/curl -s -m 30 -X POST -H 'X-Forwarded-For: 93.8.8.8' -H 'X-FE-Pass-Request: 1' -H 'X-FE-Pass-Bind: 1.1.1|evil ' -A "$B" http://bcngx/api/v1/human-pass)
[ "$spoof" = "minted:anon|bind=93.8.8|$B " ] || { echo "FAIL: клиент подменил привязку: $spoof"; exit 1; }
leak=$(docker run --rm --network bcnet curlimages/curl -s -m 30 -H 'X-FE-Pass-Bind: 1.1.1|evil ' http://bcngx/api/echo-bind)
[ "$leak" = "bind=" ] || { echo "FAIL: заголовок привязки прошёл через общий /api/: $leak"; exit 1; }
# Флаг FE_PASS_BIND=0: прежняя подпись снова действует, привязанная - нет; выдача без привязки.
docker run --rm -e FE_PASS_BIND=0 -v "$PWD/frontend/42-fe-pass-bind.sh:/s.sh:ro" -v "$T/fe-pass:/etc/nginx/fe-pass" "$IMAGE" sh /s.sh >/dev/null
grep -q 'set $fe_pass_bind_on "0";' "$T/fe-pass/pass-bind.conf" || { echo "FAIL: флаг привязки не записан"; exit 1; }
docker exec bcngx nginx -s reload >/dev/null 2>&1; sleep 2
o1=$(cls 93.7.7.8 "$B" "$OLD"); o2=$(cls 93.7.7.7 "$B" "$P7")
m0=$(docker run --rm --network bcnet curlimages/curl -s -m 30 -X POST -H 'X-Forwarded-For: 93.9.9.9' -H 'X-FE-Pass-Request: 1' -A "$B" http://bcngx/api/v1/human-pass)
echo "привязка выключена            : $o1 $o2 $m0"
[ "$o1 $o2 $m0" = "human anon minted:anon|bind=" ] || { echo "FAIL: флаг привязки"; exit 1; }
docker run --rm -e FE_PASS_BIND=1 -v "$PWD/frontend/42-fe-pass-bind.sh:/s.sh:ro" -v "$T/fe-pass:/etc/nginx/fe-pass" "$IMAGE" sh /s.sh >/dev/null
[ ! -e "$T/fe-pass/pass-bind.conf" ] || { echo "FAIL: включённая привязка оставила файл"; exit 1; }
echo "OK"
