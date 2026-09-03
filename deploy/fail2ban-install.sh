#!/usr/bin/env bash
# Установка anti-scrape стека на прод-хосте (Ubuntu 24.04).
# Запуск ОДИН РАЗ на хосте: apt-get install fail2ban, конфиги, logrotate,
# каталог логов с правами под nginx (uid 101 в контейнере frontend).
# Идемпотентен: повторный запуск безопасен.
set -euo pipefail

if [[ $EUID -ne 0 ]]; then echo "run as root"; exit 1; fi

echo "==> apt: fail2ban"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq fail2ban

echo "==> каталог логов /var/log/rosstat-nginx (uid 101 = nginx в контейнере)"
install -d -m 0755 /var/log/rosstat-nginx
# nginx в контейнере пишет под uid 101 (alpine nginx). Хостовый пользователь
# может отличаться — ставим 101:101 явно (inetuid image nginx:alpine).
chown 101:101 /var/log/rosstat-nginx

echo "==> конфиги fail2ban"
install -m 0644 deploy/fail2ban/jail.local /etc/fail2ban/jail.local
install -m 0644 deploy/fail2ban/filter.d-nginx-429.conf /etc/fail2ban/filter.d/nginx-429.conf
install -m 0644 deploy/fail2ban/filter.d-nginx-volume.conf /etc/fail2ban/filter.d/nginx-volume.conf
install -m 0644 deploy/fail2ban/filter.d-honeytrap.conf /etc/fail2ban/filter.d/honeytrap.conf
install -d -m 0755 /var/log/rosstat-nginx
touch /var/log/rosstat-nginx/security.log /var/log/rosstat-nginx/honeypot.log
chown 101:101 /var/log/rosstat-nginx /var/log/rosstat-nginx/security.log /var/log/rosstat-nginx/honeypot.log

echo "==> logrotate для security/honeypot"
install -m 0644 deploy/fail2ban/logrotate-rosstat-nginx /etc/logrotate.d/rosstat-nginx

echo "==> enable + restart fail2ban"
systemctl enable fail2ban
systemctl restart fail2ban

echo "==> статус"
fail2ban-client status
echo "OK: fail2ban активен; jails: nginx-429, nginx-volume, honeytrap, recidive"
