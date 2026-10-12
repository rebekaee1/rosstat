#!/usr/bin/env bash
# Ответы nginx поисковым роботам за последние N часов (по умолчанию 3): статусы по роботам
# и отдельно 429/502/503/504 по типу пути (страница / картинка /og/ / sitemap).
# Запускать на боевом хосте из /opt/rosstat: только чтение docker logs.
#   deploy/crawler-status.sh [часов]
set -euo pipefail
HOURS="${1:-3}"
docker compose logs --no-log-prefix --since "${HOURS}h" frontend 2>/dev/null \
 | grep -aiE 'googlebot|google-inspection|googleother|yandex|bingbot' \
 | awk '
   {
     if (match($0, /"(GET|HEAD) [^ ]+ HTTP[^"]*" [0-9]+/)) {
       split(substr($0, RSTART, RLENGTH), a, "\""); n = split(a[2], p, " "); path = p[2]
       split(substr($0, RSTART + RLENGTH - 3, 3), s, "")
       st = substr($0, RSTART + RLENGTH - 3, 3)
     } else next
     ua = tolower($0)
     bot = (ua ~ /googlebot-image/) ? "googlebot-image" : (ua ~ /googleother/) ? "googleother" : (ua ~ /googlebot|google-inspection/) ? "googlebot" : (ua ~ /yandex/) ? "yandex" : (ua ~ /bingbot/) ? "bing" : "other"
     kind = (path ~ /^\/og\//) ? "og" : (path ~ /sitemap/) ? "sitemap" : "page"
     tot[bot]++; cnt[bot, st]++
     if (st ~ /^(429|502|503|504)$/) bad[bot " " st " " kind]++
   }
   END {
     print "== ответы по роботам"
     for (b in tot) { line = b ": " tot[b] " запросов;"; for (k in cnt) { split(k, x, SUBSEP); if (x[1] == b) line = line " " x[2] "=" cnt[k] }; print line }
     print "== 429/502/503/504 (робот статус тип пути: число)"
     for (k in bad) print k ": " bad[k]
   }'
