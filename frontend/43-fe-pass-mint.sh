#!/bin/sh
# Лимит выдачи пропуска fe_pass на сеть клиента (14.11.2026, дополнение ADR-0026): 3 в минуту на IPv4 /24 или на
# первые четыре группы IPv6. По умолчанию включён (nginx.conf: set $fe_pass_mint_net_on "1"). FE_PASS_MINT_NET_LIMIT=0 -
# этот файл ставит "0", остаётся только общий потолок выдачи и лимит по IP. Откат без пересборки: .env и пересоздание frontend.
set -eu
out=/etc/nginx/fe-pass/pass-mint.conf
rm -f "$out"
case "${FE_PASS_MINT_NET_LIMIT:-1}" in
  0|off|false|no)
    printf 'set $fe_pass_mint_net_on "0";\n' > "$out"
    echo "fe-pass-mint: лимит выдачи пропуска на сеть выключен"
    ;;
  *)
    echo "fe-pass-mint: лимит выдачи пропуска на сеть включён"
    ;;
esac
