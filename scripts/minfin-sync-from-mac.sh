#!/usr/bin/env bash
# Синхронизация CSV Минфина «исполнение федерального бюджета» (fedbud_month)
# с Mac владельца на прод.
#
# Зачем: minfin.gov.ru явно банит прод-IP 201.51.11.170 («Доступ к сайту
# временно ограничен владельцем веб-ресурса»), а также адреса дата-центров,
# прокси и Tor-выходы; в сети Tor на 2026-10-08 остался один RU-выход, и он до
# Минфина не достаёт. С домашнего IP Mac сайт открывается. Источник остаётся
# официальным — тот же OpenData-набор Минфина; Mac лишь доставляет файл.
#
# Что делает (идемпотентно, безопасно запускать хоть каждый час):
#   1. Берёт каталог набора с minfin.gov.ru, находит самый свежий data-*.csv.
#   2. Скачивает его и проверяет парсером: тот же заголовок, ни одна дата из
#      текущего файла на проде не пропала, ряды не пустые.
#   3. Если sha256 совпадает с файлом в контейнере scheduler — выходит.
#   4. Иначе кладёт файл в контейнеры scheduler и backend (путь снимка парсера
#      app/data/minfin/fedbud_month.csv) и прогоняет budget-revenue/
#      -expenditure/-deficit. Пересоздание контейнера вернёт снимок из образа;
#      следующий запуск скрипта снова доставит свежий файл, а точки новее
#      снимка BaseParser не удаляет (keep_after).
#
# Запуск вручную:  scripts/minfin-sync-from-mac.sh  (MINFIN_SYNC_FORCE=1 — залить и прогнать даже без изменений)
# По расписанию:   launchd-агент com.forecasteconomy.minfin-sync (см.
#                  docs/data_sources.md, раздел Минфина).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="$ROOT/backend/.venv/bin/python"
HOST="${MINFIN_SYNC_HOST:-fe-prod}"
REMOTE_DIR="${MINFIN_SYNC_REMOTE_DIR:-/opt/rosstat}"
STATE="${MINFIN_SYNC_DIR:-$HOME/Library/Application Support/ForecastEconomy/minfin-sync}"
CATALOG="https://minfin.gov.ru/opendata/7710168360-fedbud_month/"
UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0 Safari/537.36"
SNAPSHOT="/app/app/data/minfin/fedbud_month.csv"

mkdir -p "$STATE"
log() { printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" | tee -a "$STATE/sync.log"; }
fail() {
  log "ОШИБКА: $*"
  osascript -e "display notification \"$*\" with title \"Минфин → прод: сбой синхронизации\"" >/dev/null 2>&1 || true
  exit 1
}

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

html="$(curl -fsS -m 60 -A "$UA" "$CATALOG")" || fail "каталог Минфина недоступен с Mac"
name="$(printf '%s' "$html" | grep -oE 'data-[0-9]{8}(T[0-9]{4})?-structure-[0-9]{8}(T[0-9]{4})?\.csv' | sort -u | tail -1)"
[ -n "$name" ] || fail "в каталоге не найден data-*.csv (сменилась вёрстка?)"
curl -fsS -m 180 -A "$UA" -o "$TMP/new.csv" "$CATALOG$name" || fail "не скачался $name"

ssh -o BatchMode=yes -o ConnectTimeout=20 "$HOST" \
  "cd $REMOTE_DIR && docker compose exec -T scheduler cat $SNAPSHOT" > "$TMP/prod.csv" \
  || fail "не прочитан текущий снимок на проде"

new_sha="$(shasum -a 256 "$TMP/new.csv" | cut -d' ' -f1)"
prod_sha="$(shasum -a 256 "$TMP/prod.csv" | cut -d' ' -f1)"
if [ "$new_sha" = "$prod_sha" ] && [ -z "${MINFIN_SYNC_FORCE:-}" ]; then
  log "актуально: $name (sha ${new_sha:0:12})"
  exit 0
fi

summary="$(cd "$ROOT/backend" && "$PY" - "$TMP/new.csv" "$TMP/prod.csv" 2>"$TMP/check.err" <<'PY'
import sys
from app.services.minfin_budget_parser import _parse_budget_csv

new_text = open(sys.argv[1], encoding="utf-8-sig").read()
old_text = open(sys.argv[2], encoding="utf-8-sig").read()
if new_text.splitlines()[0] != old_text.splitlines()[0]:
    sys.exit("заголовок CSV изменился — нужна ручная проверка парсера")
parts = []
for target in ("revenue", "expenditure", "deficit"):
    new = {p.date for p in _parse_budget_csv(new_text, target)}
    old = {p.date for p in _parse_budget_csv(old_text, target)}
    if not new:
        sys.exit(f"{target}: парсер не нашёл ни одной точки")
    lost = sorted(old - new)
    if lost:
        sys.exit(f"{target}: в новом файле пропали даты {lost[:3]}")
    parts.append(f"{target} до {max(new):%Y-%m} (+{len(new - old)})")
print("; ".join(parts))
PY
)" || fail "проверка файла не прошла: $(tail -1 "$TMP/check.err")"

scp -q -o BatchMode=yes "$TMP/new.csv" "$HOST:/tmp/fe-minfin-fedbud_month.csv" || fail "scp на прод"
ssh -o BatchMode=yes "$HOST" "set -e; cd $REMOTE_DIR
  for svc in scheduler backend; do
    docker cp /tmp/fe-minfin-fedbud_month.csv \"\$(docker compose ps -q \$svc)\":$SNAPSHOT
  done
  rm -f /tmp/fe-minfin-fedbud_month.csv
  docker compose exec -T scheduler python -c '
import asyncio
from app.tasks.scheduler import run_etl_for_indicator
async def main():
    for code in (\"budget-revenue\", \"budget-expenditure\", \"budget-deficit\"):
        await run_etl_for_indicator(code)
asyncio.run(main())
' >/dev/null 2>&1
  docker compose exec -T scheduler sha256sum $SNAPSHOT" > "$TMP/after.txt" || fail "загрузка на прод или прогон ETL"

grep -q "$new_sha" "$TMP/after.txt" || fail "после загрузки sha в контейнере не совпал"
cp "$TMP/new.csv" "$STATE/fedbud_month.latest.csv"
log "обновлено: $name → прод; $summary"
