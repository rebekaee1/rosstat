#!/bin/sh
# Привязка пропуска fe_pass к сети /24 и UA (14.11.2026, дополнение ADR-0026). Три режима:
#   observe (по умолчанию, файла нет: nginx.conf задаёт set $fe_pass_bind_on "observe") - подпись прежняя, а совпала бы
#           привязка по сети или нет, пишется в /var/log/nginx/security/pass-observe.log;
#   1       - привязка действует (пропуск не работает на чужой сети /24 и с другим UA);
#   0       - прежняя подпись, без наблюдения.
# Переключение без пересборки: FE_PASS_BIND в .env и пересоздание контейнера frontend. Переход 1 <-> (0|observe)
# делает выданные пропуска недействительными, страница 429 выдаёт новые сама.
set -eu
out=/etc/nginx/fe-pass/pass-bind.conf
rm -f "$out"
case "${FE_PASS_BIND:-observe}" in
  0|off|false|no)
    printf 'set $fe_pass_bind_on "0";\n' > "$out"
    echo "fe-pass-bind: привязка пропуска выключена"
    ;;
  1|on|true|yes)
    printf 'set $fe_pass_bind_on "1";\n' > "$out"
    echo "fe-pass-bind: привязка пропуска включена"
    ;;
  *)
    echo "fe-pass-bind: привязка пропуска в режиме наблюдения"
    ;;
esac
