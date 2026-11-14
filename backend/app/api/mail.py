"""Отписка от рассылки по ссылке из письма (ADR-0032).

Без входа на сайт: полномочие — подписанная ссылка (`services/mail/tokens.py`, назначение
``unsub``). Три пути:
  * ``POST /mail/unsubscribe?t=…`` — кнопка «Отписаться» в интерфейсе почты
    (заголовки List-Unsubscribe + List-Unsubscribe-Post, RFC 8058; тело формы
    ``List-Unsubscribe=One-Click``) и страница сайта ``/account/unsubscribe``;
  * ``GET /mail/unsubscribe?t=…`` — только состояние (подписан ли, маска адреса);
    GET ничего не меняет: почтовые сканеры ссылок открывают ссылки сами;
  * ``POST /mail/resubscribe`` — «Подписаться снова» на той же странице.
Журнал согласий append-only (152-ФЗ): новая запись newsletter / newsletter_revoked.
Неизвестный или удалённый человек получает тот же ответ, что и отписанный.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Consent, User
from app.services.api_i18n import api_detail
from app.services.mail import audience, tokens
from app.services.mail.account import mask_email

router = APIRouter(prefix="/mail", tags=["mail"])


class TokenBody(BaseModel):
    t: str | None = None


def _bad() -> HTTPException:
    return HTTPException(status_code=400, detail={
        "code": "invalid_link",
        "message": api_detail(
            "Ссылка повреждена. Отписаться можно в личном кабинете или ответом на письмо.",
            "The link is broken. You can unsubscribe in your account or by replying to the email.",
        ),
    })


async def _user_from(token: str | None, db: AsyncSession) -> tuple[uuid.UUID | None, User | None]:
    try:
        tok = tokens.verify("unsub", token or "")
    except (tokens.TokenError, tokens.TokenSecretMissing):
        raise _bad()
    try:
        uid = uuid.UUID(tok.user_id)
    except ValueError:
        raise _bad()
    return uid, await db.get(User, uid)


async def _state(db: AsyncSession, user: User | None) -> dict:
    if user is None:
        return {"subscribed": False, "email": ""}
    rec = await audience.resolve(db, user.id)
    return {"subscribed": await audience.is_subscribed(db, user.id), "email": mask_email(rec.email if rec else "")}


async def _write(db: AsyncSession, request: Request, user: User, kind: str) -> None:
    from app.api.auth import AUTH_CONSENT_VERSION, _client_ip, audit

    db.add(Consent(user_id=user.id, kind=kind, version=AUTH_CONSENT_VERSION, ip=_client_ip(request),
                   user_agent=(request.headers.get("user-agent") or "")[:500]))
    await audit(db, user.id, "newsletter_off" if kind == "newsletter_revoked" else "newsletter_on",
                request, detail="mail_link")
    await db.commit()


async def _token_from(request: Request, query_t: str | None) -> str | None:
    if query_t:
        return query_t
    ctype = request.headers.get("content-type", "")
    if "application/json" in ctype:
        try:
            body = await request.json()
            return body.get("t") if isinstance(body, dict) else None
        except Exception:  # noqa: BLE001
            return None
    return None


@router.get("/unsubscribe")
async def unsubscribe_state(t: str | None = None, db: AsyncSession = Depends(get_db)):
    _uid, user = await _user_from(t, db)
    return await _state(db, user)


@router.post("/unsubscribe")
async def unsubscribe(request: Request, t: str | None = None, db: AsyncSession = Depends(get_db)):
    _uid, user = await _user_from(await _token_from(request, t), db)
    if user is not None and await audience.is_subscribed(db, user.id):
        await _write(db, request, user, "newsletter_revoked")
    return {"ok": True, **(await _state(db, user))}


@router.post("/resubscribe")
async def resubscribe(body: TokenBody, request: Request, db: AsyncSession = Depends(get_db)):
    _uid, user = await _user_from(body.t, db)
    if user is not None and user.status == "active" and not await audience.is_subscribed(db, user.id):
        await _write(db, request, user, "newsletter")
    return {"ok": True, **(await _state(db, user))}
