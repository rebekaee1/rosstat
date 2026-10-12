#!/usr/bin/env bash
# Поведенческая проверка ограничения частоты картинок /og/ (нужен docker).
# Поднимает фиктивный backend (0,4 с на ответ) и nginx с конфигом из репозитория,
# шлёт по 40 одновременных запросов от (1) проверенного Googlebot-Image
# (сеть Google + UA), (2) подделки (UA без сети), (3) обычного посетителя.
# Ожидание: (1) все 200, (2) и (3) в основном 429 (общий потолок картинок
# остаётся для всех, кроме проверенного индексирующего робота).
# Контекст: 12.10.2026 Googlebot-Image получал 429 (113 из 1365).
set -euo pipefail
cd "$(dirname "$0")/.."
IMAGE="${IMAGE:-nginx:alpine}"
T="$(mktemp -d)"; trap 'docker rm -f ogup ogngx >/dev/null 2>&1; docker network rm ognet >/dev/null 2>&1; rm -rf "$T"' EXIT
cat > "$T/up.py" <<'PY'
import time
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
class H(BaseHTTPRequestHandler):
    def do_GET(self):
        time.sleep(0.4)
        self.send_response(200); self.send_header("Content-Type", "image/png"); self.send_header("Content-Length", "4"); self.end_headers(); self.wfile.write(b"PNG!")
    def log_message(self, *a): pass
ThreadingHTTPServer(("0.0.0.0", 8000), H).serve_forever()
PY
docker network create ognet >/dev/null
docker run -d --rm --name ogup --network ognet --network-alias backend -v "$T/up.py:/up.py:ro" python:3.12-slim python /up.py >/dev/null
docker run -d --rm --name ogngx --network ognet \
  -v "$PWD/frontend/nginx.conf:/etc/nginx/conf.d/default.conf:ro" \
  -v "$PWD/frontend/search-crawlers.conf:/etc/nginx/search-crawlers.conf:ro" \
  "$IMAGE" sh -c 'mkdir -p /usr/share/nginx/html /var/log/nginx/security; touch /var/log/nginx/security/security.log /var/log/nginx/security/honeypot.log; nginx -g "daemon off;"' >/dev/null
sleep 3
docker exec ogngx nginx -t
burst() {  # $1 ip, $2 user-agent
  docker run --rm --network ognet curlimages/curl sh -c "for i in \$(seq 1 40); do (curl -s -o /dev/null -w '%{http_code}\n' -m 60 -H 'X-Forwarded-For: $1' -A '$2' http://ogngx/og/world/germany/cpi\$i.png &); done; sleep 25" | sort | uniq -c | tr '\n' ' '
}
g=$(burst 66.249.66.168 'Mozilla/5.0 (Linux; Android 6.0.1) Googlebot-Image/1.0 (compatible; Googlebot/2.1)'); echo "verified Googlebot-Image: $g"
sleep 12
f=$(burst 1.2.3.4 'Googlebot-Image/1.0'); echo "spoofed Googlebot-Image : $f"
sleep 12
h=$(burst 5.6.7.8 'Mozilla/5.0 Safari'); echo "ordinary visitor        : $h"
case "$g" in *429*) echo "FAIL: проверенный робот получил 429"; exit 1;; esac
case "$f" in *429*) ;; *) echo "FAIL: подделка не ограничена"; exit 1;; esac
echo "OK"
