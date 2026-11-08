#!/bin/sh
# Пропуск человека (08.11.2026, ADR-0026 доп.): секрет подписи cookie fe_pass из FE_HUMAN_PASS_SECRET в конфиг nginx.
# Тот же секрет у backend (RUSTATS_FE_HUMAN_PASS_SECRET). Пусто или недопустимые символы - файла нет, пропуск выключен,
# nginx работает как раньше. Допустимо только [A-Za-z0-9_-]{32,}: значение попадает в строку конфига nginx.
set -eu
out=/etc/nginx/fe-pass/secret.conf
rm -f "$out"
secret="${FE_HUMAN_PASS_SECRET:-}"
if [ -z "$secret" ]; then
  echo "fe-human-pass: FE_HUMAN_PASS_SECRET не задан - пропуск выключен"
  exit 0
fi
if ! printf '%s' "$secret" | grep -Eq '^[A-Za-z0-9_-]{32,}$'; then
  echo "fe-human-pass: FE_HUMAN_PASS_SECRET должен быть [A-Za-z0-9_-] не короче 32 знаков - пропуск выключен" >&2
  exit 0
fi
printf 'set $fe_pass_secret "%s";\n' "$secret" > "$out"
echo "fe-human-pass: пропуск включён"
