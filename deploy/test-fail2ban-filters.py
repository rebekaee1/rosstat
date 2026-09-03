#!/usr/bin/env python3
"""Самопроверка failregex фильтров fail2ban против реальных строк лога.

Локальный аналог `fail2ban-regex` (на macOs его нет): те же паттерны, что
в deploy/fail2ban/filter.d-*.conf, против примеров строк, которые породит
наш log_format. Запуск: python3 deploy/test-fail2ban-filters.py
"""
import re

SECURITY_LINE = '2026-08-27T10:15:26+00:00 1.2.3.4 429 "GET /russia/region/moskva/valovoy-regionalnyy-produkt HTTP/1.1" "Mozilla/5.0 research/1.0"'
HONEYPOT_LINE = '2026-08-27T10:16:00+00:00 5.6.7.8 403 "GET /russia/util/links-exchange HTTP/1.1" "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"'
VOLUME_LINE = '2026-09-03T14:42:11+00:00 9.9.9.9 200 "GET /russia/indicator/cpi HTTP/1.1" "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"'
YANDEX_LINE = '2026-09-03T14:42:11+00:00 9.9.9.9 200 "GET /russia/indicator/cpi HTTP/1.1" "Mozilla/5.0 (compatible; YandexBot/3.0; +http://yandex.com/bots)"'

# failregex из filter.d-*.conf:
# fail2ban заменяет <HOST> на группу IP.
patterns = {
    'nginx-429': re.compile(r'^\S+ (?P<host>\S+) 429\b'),
    'honeytrap': re.compile(r'^\S+ (?P<host>\S+) 403\b'),
    'nginx-volume': re.compile(r'^\S+ (?P<host>\S+) (?:200|301|302|304) "GET /'),
}
ignore_search = re.compile(
    r'(?i)(?:yandex|googlebot|bingbot|mail\.ru|duckduckbot|applebot|gptbot|'
    r'petalbot|amazonbot|claudebot|perplexitybot|youbot)'
)

cases = [
    ('nginx-429', SECURITY_LINE, '1.2.3.4'),
    ('honeytrap', HONEYPOT_LINE, '5.6.7.8'),
    ('nginx-volume', VOLUME_LINE, '9.9.9.9'),
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

m_vol = patterns['nginx-volume'].search(YANDEX_LINE)
if m_vol and ignore_search.search(YANDEX_LINE):
    print('OK  nginx-volume: YandexBot ignored')
else:
    fail += 1
    print('FAIL nginx-volume: YandexBot should be ignored')

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
