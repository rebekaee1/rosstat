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


def sign(expires: int, pass_id: str, secret: str) -> str:
    digest = hashlib.md5(f"{expires}{pass_id} {secret}".encode()).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


def issue(secret: str, now: float | None = None) -> str:
    expires = int(now if now is not None else time.time()) + max(1, settings.fe_human_pass_days) * 86400
    pass_id = secrets.token_hex(8)
    return f"{sign(expires, pass_id, secret)}.{expires}.{pass_id}"


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
        issue(secret),
        max_age=max(1, settings.fe_human_pass_days) * 86400,
        path="/",
        secure=host not in {"localhost", "127.0.0.1"},
        httponly=True,
        samesite="lax",
    )
    return response
