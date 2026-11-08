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
        time.sleep(0.05); self._send((self.headers.get("X-FE-Client-Class") or "none").encode())
    def do_POST(self):
        self._send(b"minted:" + (self.headers.get("X-FE-Client-Class") or "none").encode())
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
# Подпись так же, как backend (app/api/human_pass.py): base64url(md5("<срок><id> <секрет>")) без '='
mkpass() {  # $1 срок unix, $2 id, $3 секрет
  python3 -c 'import base64,hashlib,sys; e,i,s=sys.argv[1:]; print(base64.urlsafe_b64encode(hashlib.md5(f"{e}{i} {s}".encode()).digest()).decode().rstrip("=")+f".{e}.{i}")' "$1" "$2" "$3"
}
NOW=$(date +%s)
GOOD=$(mkpass $((NOW+86400)) 0123456789abcdef "$SECRET")
FORGED=$(mkpass $((NOW+86400)) 0123456789abcdef "wrong_secret_0123456789abcdefghijklmn")
EXPIRED=$(mkpass $((NOW-60)) 0123456789abcdef "$SECRET")
URL="http://bcngx/united-states/region/texas/bea-sagdp1-1/2008"
cls() {  # $1 XFF, $2 UA, $3 cookie fe_pass или пусто
  docker run --rm --network bcnet -e XFF="$1" -e UA="$2" -e PASS="$3" -e URL="$URL" curlimages/curl sh -c '
    set -- -s -m 30 -A "$UA" -H "X-Forwarded-For: $XFF"
    [ -z "$PASS" ] || set -- "$@" -b "fe_pass=$PASS"
    curl "$@" "$URL"'
}
B='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
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
cp=$(burst 95.20.1 "$B" 60 "$GOOD"); echo "один пропуск на 60 адресах    : $cp"
case "$cp" in *429*) ;; *) echo "FAIL: скопированный пропуск не ограничен"; exit 1;; esac
# (5) выдача пропуска проходит до backend
m=$(docker run --rm --network bcnet curlimages/curl -s -m 30 -X POST -H 'X-Forwarded-For: 96.1.1.1' -H 'X-FE-Pass-Request: 1' -A "$B" http://bcngx/api/v1/human-pass)
[ "$m" = "minted:anon" ] || { echo "FAIL: выдача пропуска: $m"; exit 1; }
echo "OK"
