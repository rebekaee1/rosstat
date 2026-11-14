#!/bin/sh
# Ферма с подставленным Referer Google (14.11.2026, дополнение ADR-0026): флаг правила в nginx.conf ($fe_google_farm).
# По умолчанию правило включено (server задаёт set $fe_google_farm_limit "1"). FE_GOOGLE_FARM_LIMIT=0 - этот файл
# переопределяет значение на "0", правило выключено. Откат без пересборки: FE_GOOGLE_FARM_LIMIT=0 в .env и
# пересоздание контейнера frontend.
set -eu
out=/etc/nginx/fe-pass/google-farm.conf
rm -f "$out"
case "${FE_GOOGLE_FARM_LIMIT:-1}" in
  0|off|false|no)
    printf 'set $fe_google_farm_limit "0";\n' > "$out"
    echo "fe-google-farm: правило выключено"
    ;;
  *)
    echo "fe-google-farm: правило включено"
    ;;
esac
