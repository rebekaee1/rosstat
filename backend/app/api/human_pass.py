"""Пропуск человека `fe_pass` (08.11.2026, дополнение ADR-0026).

Зачем. Ферма 08.11.2026 (55 тысяч запросов за 2 часа с 53,5 тысяч IP на глубокие страницы без Referer) не исполняет
JavaScript: 99 % её адресов не загрузили ни одного скрипта. Человек, открывший такую страницу без Referer (закладка,
мессенджер), в волну фермы делил с ней общий бюджет nginx `anoncold` и получал 429. Страница 429 теперь из JavaScript
просит пропуск здесь и перезагружается; с действующим пропуском nginx относит запрос к классу `human` со своим бюджетом
на каждый пропуск (`passcold`).

Это не «ворота» на входе (их сняли 20.09.2026, коммит 07936473: они резали людей). Пропуск никого не блокирует: без
него всё работает как раньше, он только выводит человека из общего бюджета фермы в момент, когда тот уже получил бы 429.

Формат cookie: `<md5 base64url без '=', 22 знака>.<срок, unix-секунды, 10 цифр>.<id, 16 hex>`; подпись -
md5(f"{срок}{id} {секрет}") - ровно то, что проверяет `secure_link_md5` в nginx. Секрет общий с nginx
(`FE_HUMAN_PASS_SECRET`); пустой секрет - эндпоинт отвечает 404, страница 429 остаётся прежней.
"""
from __future__ import annotations

import base64
import hashlib
import re
import secrets
import time

from fastapi import APIRouter, Request, Response

from app.config import settings

router = APIRouter(tags=["human-pass"])

COOKIE = "fe_pass"
REQUEST_HEADER = "x-fe-pass-request"
_SECRET_RE = re.compile(r"^[A-Za-z0-9_-]{32,}$")


def _secret() -> str | None:
    value = settings.fe_human_pass_secret or ""
    return value if _SECRET_RE.match(value) else None


# Привязка (14.11.2026): nginx передаёт в X-FE-Pass-Bind ровно ту строку, что вписывает в secure_link_md5
# ("<сеть /24>|<UA> " или пусто при FE_PASS_BIND=0). Заголовок Starlette декодирует как latin-1: обратное кодирование
# даёт исходные байты, как их видит nginx.
BIND_HEADER = "x-fe-pass-bind"
# Наблюдение (приёмка 14.11.2026): nginx передаёт сеть выдачи (IPv4 /24 или четыре группы IPv6) в X-FE-Pass-Net;
# backend кладёт её в cookie fe_pass_net, nginx пишет в pass-observe.log, совпала бы привязка по сети на каждом запросе.
NET_HEADER = "x-fe-pass-net"
NET_COOKIE = "fe_pass_net"
_NET_RE = re.compile(r"^[0-9A-Fa-f.:]{1,45}$")


def sign(expires: int, pass_id: str, secret: str, bind: str = "") -> str:
    raw = f"{expires}{pass_id} ".encode() + bind.encode("latin-1", "replace") + secret.encode()
    digest = hashlib.md5(raw).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


def issue(secret: str, now: float | None = None, bind: str = "") -> str:
    expires = int(now if now is not None else time.time()) + max(1, settings.fe_human_pass_days) * 86400
    pass_id = secrets.token_hex(8)
    return f"{sign(expires, pass_id, secret, bind)}.{expires}.{pass_id}"


# Служебный пропуск наших агентов (15.11.2026, дополнение ADR-0026). Редактор рассылки и проверка писем перед выпуском -
# агенты без JavaScript: страница отказа не может выдать им пропуск, а без Referer они делили с фермой общий бюджет и
# получали 429. Служебный пропуск - тот же формат и та же подпись, но id начинается с STAFF_ID_PREFIX: nginx относит
# такой запрос к классу staff (бюджет как у человека, fail2ban его не считает). Выдаёт только тот, у кого есть секрет
# (scripts/ops/staff-pass.sh на сервере). Срок короткий: по умолчанию 7 суток, не больше 30.
STAFF_ID_PREFIX = "57aff000"
STAFF_DAYS_DEFAULT = 7
STAFF_DAYS_MAX = 30


def issue_staff(secret: str, days: int = STAFF_DAYS_DEFAULT, bind: str = "", now: float | None = None) -> str:
    if not 1 <= days <= STAFF_DAYS_MAX:
        raise ValueError(f"срок служебного пропуска 1..{STAFF_DAYS_MAX} суток, получено {days}")
    expires = int(now if now is not None else time.time()) + days * 86400
    pass_id = STAFF_ID_PREFIX + secrets.token_hex(4)
    return f"{sign(expires, pass_id, secret, bind)}.{expires}.{pass_id}"


def _staff_main(argv: list[str] | None = None) -> int:
    """python -m app.api.human_pass --days 7 [--net 1.2.3 --ua "..."] - печатает cookie служебного пропуска."""
    import argparse
    from datetime import datetime, timezone

    ap = argparse.ArgumentParser(description="Служебный пропуск fe_pass для наших агентов (класс staff в nginx)")
    ap.add_argument("--days", type=int, default=STAFF_DAYS_DEFAULT)
    ap.add_argument("--net", default="", help="сеть агента, как её видит nginx: IPv4 /24 (1.2.3) или 4 группы IPv6")
    ap.add_argument("--ua", default="", help="точная строка User-Agent агента (нужна вместе с --net)")
    args = ap.parse_args(argv)
    secret = _secret()
    if secret is None:
        print("секрет FE_HUMAN_PASS_SECRET не задан или неверного вида: пропуск не выдан")
        return 2
    if bool(args.net) != bool(args.ua):
        print("--net и --ua задаются вместе (привязка FE_PASS_BIND=1) или не задаются вовсе")
        return 2
    bind = f"{args.net}|{args.ua} " if args.net else ""
    try:
        value = issue_staff(secret, args.days, bind)
    except ValueError as exc:
        print(exc)
        return 2
    until = datetime.fromtimestamp(int(value.split(".")[1]), timezone.utc)
    print(f"fe_pass={value}")
    print(f"действует до {until:%Y-%m-%d %H:%M} UTC; привязка: {'сеть ' + args.net if bind else 'нет'}")
    return 0


@router.post("/human-pass", status_code=204, include_in_schema=False)
async def human_pass(request: Request) -> Response:
    secret = _secret()
    if secret is None:
        return Response(status_code=404, headers={"Cache-Control": "no-store"})
    # Обычная ссылка, форма или робот без JavaScript такой заголовок не пошлют; это не защита от фермы с JS
    # (её держит общий потолок выдачи passmint в nginx), а отсечка случайных запросов.
    if request.headers.get(REQUEST_HEADER) != "1":
        return Response(status_code=400, headers={"Cache-Control": "no-store"})
    response = Response(status_code=204, headers={"Cache-Control": "no-store", "X-Robots-Tag": "noindex"})
    host = (request.headers.get("host") or "").split(":")[0]
    response.set_cookie(
        COOKIE,
        issue(secret, bind=request.headers.get(BIND_HEADER, "")),
        max_age=max(1, settings.fe_human_pass_days) * 86400,
        path="/",
        secure=host not in {"localhost", "127.0.0.1"},
        httponly=True,
        samesite="lax",
    )
    net = request.headers.get(NET_HEADER, "")
    if _NET_RE.match(net):
        response.set_cookie(
            NET_COOKIE, net,
            max_age=max(1, settings.fe_human_pass_days) * 86400,
            path="/",
            secure=host not in {"localhost", "127.0.0.1"},
            httponly=True,
            samesite="lax",
        )
    return response


if __name__ == "__main__":  # служебный пропуск: scripts/ops/staff-pass.sh
    raise SystemExit(_staff_main())
