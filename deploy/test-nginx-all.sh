#!/usr/bin/env bash
# Все поведенческие проверки nginx (14.11.2026). Зачем: тесты deploy/test-*.sh нигде не запускались сами, и
# test-og-crawler-limit.sh пролежал сломанным с 05.10 до 14.11 незамеченным.
#   --quick  только быстрые (секунды): синтаксис конфига в nginx:alpine и фильтры fail2ban против формата логов;
#   без ключа - полный набор (замер 14.11.2026 на Mac M3, образы в кэше: около 5 минут: config 1 с, anon-cold 119 с, og 104 с, bot-classes 82 с; основное время -
#            паузы на восстановление общих бюджетов внутри тестов). Полный набор обязателен в CI (job nginx).
# Нужен Docker. Тесты используют фиксированные имена контейнеров и сетей - запускать последовательно, не параллельно.
set -euo pipefail
cd "$(dirname "$0")/.."
mode="${1:-full}"
quick=(deploy/test-nginx-config.sh)
full=(deploy/test-nginx-config.sh deploy/test-anon-cold-limit.sh deploy/test-og-crawler-limit.sh deploy/test-bot-classes.sh)
case "$mode" in
  --quick) list=("${quick[@]}") ;;
  full|--full) list=("${full[@]}") ;;
  *) echo "usage: $0 [--quick]" >&2; exit 2 ;;
esac
failed=()
for t in "${list[@]}"; do
  start=$(date +%s)
  log="$(mktemp)"
  if bash "$t" >"$log" 2>&1; then
    echo "OK   $t ($(( $(date +%s) - start )) с)"
  else
    echo "FAIL $t ($(( $(date +%s) - start )) с)"; tail -20 "$log"
    failed+=("$t")
  fi
  rm -f "$log"
done
start=$(date +%s)
if python3 deploy/test-fail2ban-filters.py >/dev/null 2>&1; then
  echo "OK   deploy/test-fail2ban-filters.py ($(( $(date +%s) - start )) с)"
else
  echo "FAIL deploy/test-fail2ban-filters.py"; python3 deploy/test-fail2ban-filters.py || true
  failed+=(deploy/test-fail2ban-filters.py)
fi
if [ "${#failed[@]}" -gt 0 ]; then
  echo "nginx-тесты: провалено ${#failed[@]}: ${failed[*]}"; exit 1
fi
echo "nginx-тесты: все прошли (${mode#--})"
