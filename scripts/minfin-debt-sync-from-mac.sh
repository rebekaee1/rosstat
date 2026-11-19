#!/usr/bin/env bash
# Доставка файлов Минфина «ФНБ», «госдолг внутренний», «госдолг внешний» с Mac владельца на прод (19.11.2026).
#
# Зачем: minfin.gov.ru отвечает 503/403 адресам Timeweb (прод, релей), а Mac открывает сайт. Источник остаётся
# официальным — те же файлы со страниц Минфина; Mac лишь доставляет их. Схема та же, что у бюджета
# (scripts/minfin-sync-from-mac.sh): парсер на проде читает снимок app/data/minfin/<файл>, если живой путь закрыт.
#
# Что делает (идемпотентно, безопасно запускать хоть каждый час), для каждого из трёх источников:
#   1. Берёт страницу Минфина, находит ссылку на самый свежий файл (тем же правилом, что парсер).
#   2. Скачивает его и проверяет парсером: точки есть, ни одна дата текущего прод-снимка не пропала.
#   3. Если sha256 совпадает с файлом в контейнере scheduler — пропускает источник.
#   4. Иначе кладёт файл в контейнеры scheduler и backend и прогоняет ETL рядов этого источника.
#      Пересоздание контейнера вернёт снимок из образа; следующий запуск снова доставит свежий файл, а точки
#      новее снимка BaseParser не удаляет.
#
# Запуск вручную:  scripts/minfin-debt-sync-from-mac.sh  (MINFIN_SYNC_FORCE=1 — залить и прогнать без изменений)
# По расписанию:   launchd-агент com.forecasteconomy.minfin-sync (копия в scripts/mac/), вместе с бюджетом.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="$ROOT/backend/.venv/bin/python"
HOST="${MINFIN_SYNC_HOST:-fe-prod}"
REMOTE_DIR="${MINFIN_SYNC_REMOTE_DIR:-/opt/rosstat}"
STATE="${MINFIN_SYNC_DIR:-$HOME/Library/Application Support/ForecastEconomy/minfin-sync}"
UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0 Safari/537.36"
REMOTE_SNAP_DIR="/app/app/data/minfin"

mkdir -p "$STATE"
LOG="$STATE/sync.log"
log() { printf '%s [debt] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" | tee -a "$LOG"; }
fail() {
  log "ОШИБКА: $*"
  osascript -e "display notification \"$*\" with title \"Минфин ФНБ/госдолг → прод: сбой\"" >/dev/null 2>&1 || true
  exit 1
}

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# key|страница|снимок|коды рядов — читается из реестра, чтобы скрипт и парсер не расходились.
sources="$(cd "$ROOT/backend" && "$PY" -c '
from app.data.minfin_debt import SERIES, SOURCES
for key, src in SOURCES.items():
    codes = ",".join(s.code for s in SERIES if s.source == key)
    print(f"{key}|{src.page}|{src.snapshot}|{codes}")
')" || fail "не прочитан реестр app/data/minfin_debt.py"

changed_codes=""
summary=""
while IFS='|' read -r key page snapshot codes; do
  [ -n "$key" ] || continue
  html="$(curl -fsS -m 60 -A "$UA" "$page")" || fail "$key: страница Минфина недоступна с Mac"
  url="$(cd "$ROOT/backend" && printf '%s' "$html" | "$PY" -c '
import sys
from app.data.minfin_debt import SOURCES
from app.services.minfin_debt_parser import latest_link
print(latest_link(sys.stdin.read(), SOURCES[sys.argv[1]]) or "")
' "$key")"
  [ -n "$url" ] || fail "$key: на странице нет ссылки на файл (сменилась вёрстка?)"
  curl -fsS -m 180 -A "$UA" -o "$TMP/$snapshot" "$url" || fail "$key: не скачался $url"

  ssh -o BatchMode=yes -o ConnectTimeout=20 "$HOST" \
    "cd $REMOTE_DIR && docker compose exec -T scheduler cat $REMOTE_SNAP_DIR/$snapshot" > "$TMP/prod-$snapshot" \
    || fail "$key: не прочитан текущий снимок на проде"

  new_sha="$(shasum -a 256 "$TMP/$snapshot" | cut -d' ' -f1)"
  prod_sha="$(shasum -a 256 "$TMP/prod-$snapshot" | cut -d' ' -f1)"
  if [ "$new_sha" = "$prod_sha" ] && [ -z "${MINFIN_SYNC_FORCE:-}" ]; then
    log "$key: актуально (${url##*/})"
    continue
  fi

  check="$(cd "$ROOT/backend" && "$PY" - "$TMP/$snapshot" "$TMP/prod-$snapshot" "$codes" 2>"$TMP/check.err" <<'PY'
import sys
from app.services.minfin_debt_parser import parse_series

new = open(sys.argv[1], "rb").read()
old = open(sys.argv[2], "rb").read()
parts = []
for code in sys.argv[3].split(","):
    fresh = {p.date for p in parse_series(code, new)}
    if not fresh:
        sys.exit(f"{code}: парсер не нашёл ни одной точки")
    try:
        before = {p.date for p in parse_series(code, old)} if old else set()
    except Exception:  # noqa: BLE001 — старый снимок не разобрался: сравнивать не с чем
        before = set()
    lost = sorted(before - fresh)
    if lost:
        sys.exit(f"{code}: в новом файле пропали даты {lost[:3]}")
    parts.append(f"{code} до {max(fresh):%Y-%m} (+{len(fresh - before)})")
print("; ".join(parts))
PY
)" || fail "$key: проверка файла не прошла: $(tail -1 "$TMP/check.err")"

  scp -q -o BatchMode=yes "$TMP/$snapshot" "$HOST:/tmp/fe-minfin-$snapshot" || fail "$key: scp на прод"
  ssh -o BatchMode=yes "$HOST" "set -e; cd $REMOTE_DIR
    for svc in scheduler backend; do
      docker cp /tmp/fe-minfin-$snapshot \"\$(docker compose ps -q \$svc)\":$REMOTE_SNAP_DIR/$snapshot
    done
    rm -f /tmp/fe-minfin-$snapshot
    docker compose exec -T scheduler sha256sum $REMOTE_SNAP_DIR/$snapshot" > "$TMP/after.txt" \
    || fail "$key: загрузка на прод"
  grep -q "$new_sha" "$TMP/after.txt" || fail "$key: после загрузки sha в контейнере не совпал"
  cp "$TMP/$snapshot" "$STATE/$snapshot"
  changed_codes="${changed_codes:+$changed_codes,}$codes"
  summary="${summary:+$summary; }$check"
done <<< "$sources"

[ -n "$changed_codes" ] || exit 0

ssh -o BatchMode=yes "$HOST" "cd $REMOTE_DIR && docker compose exec -T scheduler python -c '
import asyncio
from app.tasks.scheduler import run_etl_for_indicator
async def main():
    for code in \"$changed_codes\".split(\",\"):
        await run_etl_for_indicator(code)
asyncio.run(main())
' >/dev/null 2>&1" || fail "прогон ETL $changed_codes"
log "обновлено → прод: $summary"
