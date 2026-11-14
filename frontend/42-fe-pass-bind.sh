#!/bin/sh
# Привязка пропуска fe_pass к сети /24 и UA (14.11.2026, дополнение ADR-0026). По умолчанию включена (server в
# nginx.conf задаёт set $fe_pass_bind_on "1"). FE_PASS_BIND=0 - этот файл ставит "0": подпись прежняя, без привязки.
# Откат без пересборки: FE_PASS_BIND=0 в .env и пересоздание контейнера frontend (выданные пропуска станут
# недействительны, страница 429 выдаст новые сама).
set -eu
out=/etc/nginx/fe-pass/pass-bind.conf
rm -f "$out"
case "${FE_PASS_BIND:-1}" in
  0|off|false|no)
    printf 'set $fe_pass_bind_on "0";\n' > "$out"
    echo "fe-pass-bind: привязка пропуска выключена"
    ;;
  *)
    echo "fe-pass-bind: привязка пропуска включена"
    ;;
esac
