#!/bin/bash
# Чередующийся замер «до/после» (A/B) в одинаковых условиях: страницы идут парами base→new, чтобы шум машины делился поровну.
# Нужны два perf-serve: --port 5290 (до) и --port 5293 (после) с общим --cache и --snap.
#   scripts/dev/perf-ab.sh OUT_DIR [normal|human] [runs] ["lang:path lang:path ..."]
# Результат: OUT_DIR/<mode>/<variant>__<lang>__<path>.json; сводка — scripts/dev/perf-ab-report.py OUT_DIR.
set -u
OUT=${1:?out dir}
MODE=${2:-normal}
RUNS=${3:-2}
PAGES=${4:-"ru:/ en:/ ru:/russia en:/russia ru:/russia/indicator/cpi en:/russia/indicator/cpi ru:/compare en:/compare ru:/world/rating/gdp-usd en:/world/rating/gdp-usd ru:/germany en:/germany"}
HUMAN=""; [ "$MODE" = human ] && HUMAN="--human"
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
mkdir -p "$OUT/$MODE"
for page in $PAGES; do
  lang=${page%%:*}; path=${page#*:}
  slug=$(echo "$path" | tr '/' '_')
  for variant in base new; do
    port=5290; [ $variant = new ] && port=5293
    f="$OUT/$MODE/${variant}__${lang}__${slug}.json"
    [ -s "$f" ] && continue
    node "$ROOT/scripts/dev/perf-mobile.mjs" --base "https://$lang.localhost:$port" --paths "$path" --runs "$RUNS" $HUMAN --label "$variant $MODE" --out "$f" > /dev/null 2>&1
  done
  echo "готово $lang $path" >&2
done
echo finished >&2
