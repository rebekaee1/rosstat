#!/usr/bin/env bash
# Локальная проверка анти-скрейп конфига nginx: docker run с конфигом из репо.
# Без сборки образа: монтируем конфиг как default.conf во временный контейнер.
# nginx -t валиден только с существующим /usr/share/nginx/html и лог-путями —
# создаём заглушки. Формат "main" объявляем как в реальном /etc/nginx/nginx.conf
# образа (иначе -t падает на undefined format).
set -euo pipefail
cd "$(dirname "$0")/.."

cat > /tmp/nginx-main-test.conf <<'EOF'
events {}
http {
    log_format main '$remote_addr - $remote_user [$time_local] "$request" '
                    '$status $body_bytes_sent "$http_referer" "$http_user_agent"';
    include /etc/nginx/conf.d/default.conf;
}
EOF

docker run --rm \
  --add-host backend:127.0.0.1 \
  -v "$PWD/frontend/nginx.conf:/etc/nginx/conf.d/default.conf:ro" \
  -v /tmp/nginx-main-test.conf:/tmp/nginx-main.conf:ro \
  nginx:alpine sh -c '
    mkdir -p /usr/share/nginx/html /var/log/nginx/security /var/log/nginx
    touch /var/log/nginx/security/security.log /var/log/nginx/security/honeypot.log
    chown -R nginx:nginx /var/log/nginx /var/cache/nginx 2>/dev/null || true
    nginx -t -c /tmp/nginx-main.conf -p /etc/nginx 2>&1
  '
echo "OK: nginx.conf валиден"
