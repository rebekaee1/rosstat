#!/usr/bin/env python3
"""Самопроверка failregex фильтров fail2ban против реальных строк лога.

Локальный аналог `fail2ban-regex` (на macOs его нет): те же паттерны, что
в deploy/fail2ban/filter.d-*.conf, против примеров строк, которые породит
наш log_format. Запуск: python3 deploy/test-fail2ban-filters.py
"""
import re

SECURITY_LINE = '2026-08-27T10:15:26+00:00 1.2.3.4 429 "GET /russia/region/moskva/valovoy-regionalnyy-produkt HTTP/1.1" "Mozilla/5.0 research/1.0"'
HONEYPOT_LINE = '2026-08-27T10:16:00+00:00 5.6.7.8 403 "GET /russia/util/links-exchange HTTP/1.1" "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"'

# failregex из filter.d-nginx-429.conf и filter.d-honeytrap.conf:
# fail2ban заменяет <HOST> на группу IP; якорь конца строки после статуса.
patterns = {
    'nginx-429': re.compile(r'^\S+ (?P<host>\S+) 429\b'),
    'honeytrap': re.compile(r'^\S+ (?P<host>\S+) 403\b'),
}

cases = [
    ('nginx-429', SECURITY_LINE, '1.2.3.4'),
    ('honeytrap', HONEYPOT_LINE, '5.6.7.8'),
    # Негативные: 200 не должен матчиться в 429-фильтр
    ('nginx-429', SECURITY_LINE.replace(' 429 ', ' 200 '), None),
    ('honeytrap', SECURITY_LINE, None),  # 429 не матчится в honeypot-фильтр
]

fail = 0
for name, line, expected_ip in cases:
    m = patterns[name].search(line)
    got_ip = m.group('host') if m else None
    ok = (got_ip == expected_ip)
    status = 'OK ' if ok else 'FAIL'
    if not ok:
        fail += 1
    print(f'{status} {name}: matched={bool(m)} ip={got_ip} (expected {expected_ip})')

print()
print('OK: все фильтры соответствуют формату лога' if fail == 0 else f'{fail} case(s) FAILED')
raise SystemExit(1 if fail else 0)
