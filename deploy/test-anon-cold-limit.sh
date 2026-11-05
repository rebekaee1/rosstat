#!/usr/bin/env bash
# Поведенческая проверка общего потолка для безымянного трафика на страницы длинного хвоста (нужен docker).
# Поднимает фиктивный backend (0,2 с на ответ) и nginx с конфигом из репозитория, шлёт по 40 одновременных
# запросов на /united-states/region/texas/bea-sagdp1-1/2008, каждый с НОВОГО IP (как резидентная ферма):
#   (1) браузерный UA, без Referer          -> в основном 429 (общий бюджет 2 r/s + burst 10);
#   (2) тот же UA, Referer из поиска        -> все 200;
#   (3) проверенный Googlebot (сеть + UA)   -> все 200;
#   (4) bingbot-UA с чужого IP              -> все 200 (честный робот не входит в общий бюджет);
#   (5) без XFF, из сети docker (прогрев)   -> все 200.
# Затем класс клиента, который nginx передаёт в backend (X-FE-Client-Class, ADR-0026): anon, referred, crawler, robot,
# internal, и подделка заголовка клиентом не проходит.
# Контекст: 05.11.2026 ферма с 39,7 тысяч IP довела сайт до 503/504 (46 тысяч запросов за 53 минуты).
set -euo pipefail
cd "$(dirname "$0")/.."
IMAGE="${IMAGE:-nginx:alpine}"
T="$(mktemp -d)"; trap 'docker rm -f acup acngx >/dev/null 2>&1; docker network rm acnet >/dev/null 2>&1; rm -rf "$T"' EXIT
cat > "$T/up.py" <<'PY'
import time
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
class H(BaseHTTPRequestHandler):
    def do_GET(self):
        time.sleep(0.2)
        body = (self.headers.get("X-FE-Client-Class") or "none").encode()
        self.send_response(200); self.send_header("Content-Type", "text/html"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
    def log_message(self, *a): pass
ThreadingHTTPServer(("0.0.0.0", 8000), H).serve_forever()
PY
docker network create acnet >/dev/null
docker run -d --rm --name acup --network acnet --network-alias backend -v "$T/up.py:/up.py:ro" python:3.12-slim python /up.py >/dev/null
docker run -d --rm --name acngx --network acnet \
  -v "${CONF:-$PWD/frontend/nginx.conf}:/etc/nginx/conf.d/default.conf:ro" \
  -v "$PWD/frontend/search-crawlers.conf:/etc/nginx/search-crawlers.conf:ro" \
  "$IMAGE" sh -c 'mkdir -p /usr/share/nginx/html /var/log/nginx/security; echo busy > /usr/share/nginx/html/429.html; touch /var/log/nginx/security/security.log /var/log/nginx/security/honeypot.log; nginx -g "daemon off;"' >/dev/null
sleep 3
docker exec acngx nginx -t
PATH_URL="http://acngx/united-states/region/texas/bea-sagdp1-1/2008"
# $1 префикс IP (каждый запрос получает свой адрес), $2 UA, $3 Referer или пусто, $4 "noxff" - без заголовка XFF
burst() {
  docker run --rm --network acnet -e IP="$1" -e UA="$2" -e REF="$3" -e NOXFF="${4:-}" -e URL="$PATH_URL" curlimages/curl sh -c '
    for i in $(seq 1 40); do
      ( set -- -s -o /dev/null -w "%{http_code}\n" -m 30 -A "$UA"
        [ -n "$NOXFF" ] || set -- "$@" -H "X-Forwarded-For: $IP.$i"
        [ -z "$REF" ] || set -- "$@" -H "Referer: $REF"
        curl "$@" "$URL" ) &
    done; sleep 12' | sort | uniq -c | tr '\n' ' '
}
UA_BROWSER='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
a=$(burst 81.20.3 "$UA_BROWSER" '' ''); echo "ферма (браузер, без Referer)   : $a"
sleep 8
b=$(burst 82.20.3 "$UA_BROWSER" 'https://www.google.com/' ''); echo "человек из поиска (Referer)    : $b"
sleep 8
c=$(burst 66.249.66 'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)' '' ''); echo "проверенный Googlebot          : $c"
sleep 8
d=$(burst 83.20.3 'Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)' '' ''); echo "bingbot-UA с чужого IP         : $d"
sleep 8
# Внутренний прогрев: 6 контейнеров (у каждого свой адрес в сети docker) по 5 запросов без XFF, браузерный UA, без Referer.
# На адрес приходится меньше burst'а персональной квоты, поэтому любой 429 здесь - от общего бюджета, а он внутренним не положен.
for k in 1 2 3 4 5 6; do
  docker run --rm --network acnet curlimages/curl sh -c "for i in 1 2 3 4 5; do (curl -s -o /dev/null -w '%{http_code}\n' -m 30 -A '$UA_BROWSER' $PATH_URL &); done; sleep 8" > "$T/int$k.txt" &
done
wait
e=$(cat "$T"/int*.txt | sort | uniq -c | tr '\n' ' '); echo "внутренний прогрев (без XFF)   : $e"
# Один внутренний адрес, 40 запросов разом: персональный лимит по IP (ssrstrict 2 r/s, burst 10) внутренним тоже не положен.
w=$(docker run --rm --network acnet curlimages/curl sh -c "for i in \$(seq 1 40); do (curl -s -o /dev/null -w '%{http_code}\\n' -m 30 -A 'ForecastEconomy-ssr-warm/1' $PATH_URL &); done; sleep 10" | sort | uniq -c | tr '\n' ' ')
echo "прогрев с одного адреса (40)   : $w"
# Обратная проверка: один ВНЕШНИЙ адрес с Referer (вне общего бюджета) по-прежнему упирается в персональный лимит.
o=$(docker run --rm --network acnet curlimages/curl sh -c "for i in \$(seq 1 40); do (curl -s -o /dev/null -w '%{http_code}\\n' -m 30 -H 'X-Forwarded-For: 95.1.2.3' -H 'Referer: https://ya.ru/' -A 'Mozilla/5.0 Safari' $PATH_URL &); done; sleep 10" | sort | uniq -c | tr '\n' ' ')
echo "один внешний IP (40, Referer)  : $o"
case "$o" in *429*) ;; *) echo "FAIL: персональный лимит по IP не работает"; exit 1;; esac
# Класс клиента (по одному запросу, на другой адрес, чтобы не задеть бюджеты)
cls() {  # $1 XFF или пусто, $2 UA, $3 Referer или пусто, $4 подделка заголовка или пусто
  docker run --rm --network acnet -e XFF="$1" -e UA="$2" -e REF="$3" -e FAKE="$4" curlimages/curl sh -c '
    set -- -s -m 30 -A "$UA"
    [ -z "$XFF" ] || set -- "$@" -H "X-Forwarded-For: $XFF"
    [ -z "$REF" ] || set -- "$@" -H "Referer: $REF"
    [ -z "$FAKE" ] || set -- "$@" -H "X-FE-Client-Class: $FAKE"
    curl "$@" http://acngx/russia/region/moskva/vrp/2020'
}
sleep 2
c1=$(cls 91.1.1.1 "$UA_BROWSER" '' ''); c2=$(cls 91.1.1.2 "$UA_BROWSER" 'https://ya.ru/' '')
c3=$(cls 66.249.66.1 'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)' '' '')
c4=$(cls 91.1.1.3 'Mozilla/5.0 (compatible; Applebot/0.1)' '' ''); c5=$(cls '' "$UA_BROWSER" '' '')
c6=$(cls 91.1.1.4 "$UA_BROWSER" '' 'crawler')
echo "класс: ферма=$c1 из_поиска=$c2 googlebot=$c3 applebot=$c4 прогрев=$c5 подделка=$c6"
[ "$c1 $c2 $c3 $c4 $c5 $c6" = "anon referred crawler robot internal anon" ] || { echo "FAIL: класс клиента"; exit 1; }
case "$a" in *429*) ;; *) echo "FAIL: ферма не ограничена"; exit 1;; esac
for r in "$b" "$c" "$d" "$e" "$w"; do case "$r" in *429*) echo "FAIL: законный трафик получил 429: $r"; exit 1;; esac; done
echo "OK"
