# Tor HTTP bridge — установка и ротация (F10)

Датировано 2026-10-04. Хост: `fe-prod`. Сервис `tor-http-bridge` — **горячий резерв** для Pulse/LLM-egress: слушает только
`172.18.0.1:8888` (шлюз docker-сети) и проксирует `CONNECT` в локальный Tor (`127.0.0.1:9050`). Боевой путь Pulse —
внешний relay из `RUSTATS_OPENROUTER_PROXY_URL` (отдельный сервер, пароль там свой); мост включается сменой хоста в этом URL.

Что исправляет F10 (`docs/knowledge-unknowns.md`): (1) логин/пароль были зашиты в файл `/opt/tor-http-bridge/tor_http_bridge.py`
(права 0644); (2) каждый запрос логировал первые 400 байт заголовков, включая `Proxy-Authorization` (7 таких строк в журнале на 2026-10-04).

Файлы репозитория: `tor_http_bridge.py` (секреты только из окружения, заголовки не логируются, сравнение за постоянное время),
`tor-http-bridge.service` (читает `/etc/tor-http-bridge.env`, права 0600). Тесты: `scripts/tests/test_tor_http_bridge.py`.

## Выполнение на сервере (требует разрешения владельца; около 3 минут, окна простоя нет — резерв не на боевом пути)

```bash
ssh fe-prod
cd /opt/tor-http-bridge
cp tor_http_bridge.py tor_http_bridge.py.before-f10            # откат: вернуть файл и unit, systemctl restart
# 1. новые файлы из репозитория (scp с рабочей машины): tor_http_bridge.py, tor-http-bridge.service
install -m 755 /tmp/tor_http_bridge.py /opt/tor-http-bridge/tor_http_bridge.py
install -m 644 /tmp/tor-http-bridge.service /etc/systemd/system/tor-http-bridge.service
# 2. НОВЫЙ пароль (старый скомпрометирован — он был в файле и в журнале); пароль не печатать
umask 077
printf 'BRIDGE_AUTH_USER=pulse_relay\nBRIDGE_AUTH_PASS=%s\n' "$(openssl rand -hex 24)" > /etc/tor-http-bridge.env
chmod 600 /etc/tor-http-bridge.env
systemctl daemon-reload && systemctl restart tor-http-bridge && systemctl is-active tor-http-bridge
# 3. убрать след старого пароля из журнала (он уже недействителен)
journalctl --rotate && journalctl --vacuum-time=1d
```

## Проверка

- `systemctl status tor-http-bridge` — active; `journalctl -u tor-http-bridge -n 20` — нет `Proxy-Authorization`/`HEAD b'` в строках.
- Без пароля: `curl -s -o /dev/null -w '%{http_code}\n' -x http://172.18.0.1:8888 https://example.org` → `407`.
- С новым паролем (подставить из `/etc/tor-http-bridge.env`, не копировать в историю shell): ответ `200`/`301` от внешнего сайта через Tor.
- Клиенты: боевой Pulse не затронут (идёт через relay). Для переключения на резерв:
  `RUSTATS_OPENROUTER_PROXY_URL=http://pulse_relay:<новый пароль>@172.18.0.1:8888` в `/opt/rosstat/.env`, затем `docker compose up -d --force-recreate scheduler`.
