#!/bin/sh
# Служебный пропуск наших агентов (15.11.2026, дополнение ADR-0026): флаг класса staff в nginx.conf ($fe_staff_pass).
# По умолчанию включено (server задаёт set $fe_staff_pass_on "1"). FE_STAFF_PASS=0 - этот файл переопределяет значение
# на "0": служебные пропуска (id 57aff000…) действуют как обычный пропуск человека (класс human, fail2ban их считает).
# Откат без пересборки: FE_STAFF_PASS=0 в .env и пересоздание контейнера frontend.
set -eu
out=/etc/nginx/fe-pass/staff-pass.conf
rm -f "$out"
case "${FE_STAFF_PASS:-1}" in
  0|off|false|no)
    printf 'set $fe_staff_pass_on "0";\n' > "$out"
    echo "fe-staff-pass: служебный пропуск выключен"
    ;;
  *)
    echo "fe-staff-pass: служебный пропуск включён"
    ;;
esac
