#!/usr/bin/env bash
# Служебный пропуск fe_pass для наших агентов (15.11.2026, дополнение ADR-0026).
#
# Зачем. Редактор рассылки и проверка писем перед выпуском - агенты без JavaScript. Без Referer они делят с фермой
# общий бюджет страниц и получают 429 «подождите» (замер 08-14.11: 70 отказов Claude-User, 377 curl), а fail2ban
# после 30 отказов или 80 страниц за 10 минут банит их адрес на сутки. С этим пропуском nginx относит запрос к классу
# staff: бюджет как у человека с пропуском (2 страницы в секунду, запас 20), плюс обычный лимит по адресу; fail2ban
# такие строки не считает.
#
# Запуск на сервере из каталога проекта (секрет есть только там):
#   scripts/ops/staff-pass.sh                    # пропуск на 7 суток
#   scripts/ops/staff-pass.sh --days 3
#   scripts/ops/staff-pass.sh --net 1.2.3 --ua "Mozilla/5.0 ..."   # нужно, если включена привязка FE_PASS_BIND=1
# Печатает строку `fe_pass=...` - её агент передаёт как cookie (curl -b 'fe_pass=...'); Referer не важен (служебный
# пропуск сильнее). Темп агента - не выше 1 страницы в секунду. Пропуск - ключ: не класть в репозиторий и в письма.
# Откат: FE_STAFF_PASS=0 в .env и пересоздание frontend - пропуск станет обычным пропуском человека; отозвать все
# пропуска сразу - сменить FE_HUMAN_PASS_SECRET (frontend и backend).
set -euo pipefail
cd "$(dirname "$0")/../.."
bind_conf=$(docker compose exec -T frontend sh -c 'cat /etc/nginx/fe-pass/pass-bind.conf 2>/dev/null' || true)
if printf '%s' "$bind_conf" | grep -q '"1"'; then
  case " $* " in
    *" --net "*) ;;
    *) echo "на сервере включена привязка пропуска (FE_PASS_BIND=1): задайте --net <сеть агента> и --ua <UA агента>" >&2
       exit 2 ;;
  esac
fi
exec docker compose exec -T backend python -m app.api.human_pass "$@"
