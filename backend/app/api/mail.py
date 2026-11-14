"""Отписка от рассылки по ссылке из письма (ADR-0032).

Без входа на сайт: полномочие — подписанная ссылка (`services/mail/tokens.py`, назначение
``unsub``). Три пути:
  * ``POST /mail/unsubscribe?t=…`` — кнопка «Отписаться» в интерфейсе почты
    (заголовки List-Unsubscribe + List-Unsubscribe-Post, RFC 8058; тело формы
    ``List-Unsubscribe=One-Click``) и страница сайта ``/account/unsubscribe``;
  * ``GET /mail/unsubscribe?t=…`` — только состояние (подписан ли, маска адреса);
    GET ничего не меняет: почтовые сканеры ссылок открывают ссылки сами;
  * ``POST /mail/resubscribe`` — «Подписаться снова» на той же странице.
Ссылки двух списков: рассылка (``unsub``) и письма о новых значениях по «колокольчику»
(``unsub_watch``, журнал ``watch_mail`` / ``watch_mail_revoked``); ответ несёт ``list``.
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


# Два списка: рассылка (назначение ссылки unsub) и письма о новых значениях по
# «колокольчику» (unsub_watch). Список определяет назначение ссылки, а не параметр запроса.
LISTS = {
    "unsub": ("newsletter", "newsletter", "newsletter_revoked"),
    "unsub_watch": ("watch", "watch_mail", "watch_mail_revoked"),
    # «Письма без персональной подборки»: выпуск остаётся, подборка по действиям выключается.
    "unpers": ("personal", "mail_personal", "mail_personal_revoked"),
}
PERSONAL_KINDS = ("mail_personal", "mail_personal_revoked")


async def _user_from(token: str | None, db: AsyncSession) -> tuple[str, User | None]:
    """(назначение ссылки, пользователь или None, если аккаунт удалён)."""
    for purpose in LISTS:
        try:
            tok = tokens.verify(purpose, token or "")
            break
        except tokens.TokenError:
            continue
        except tokens.TokenSecretMissing:
            raise _bad()
    else:
        raise _bad()
    try:
        uid = uuid.UUID(tok.user_id)
    except ValueError:
        raise _bad()
    return purpose, await db.get(User, uid)


async def _personal_on(db: AsyncSession, user_id) -> bool:
    """Персональная подборка включена, пока последняя запись не отзыв (по умолчанию — включена)."""
    from sqlalchemy import select

    last = await db.scalar(select(Consent.kind).where(Consent.user_id == user_id, Consent.kind.in_(PERSONAL_KINDS))
                           .order_by(Consent.granted_at.desc(), Consent.id.desc()).limit(1))
    return last != "mail_personal_revoked"


async def _subscribed(db: AsyncSession, purpose: str, user: User) -> bool:
    if purpose == "unpers":
        return await _personal_on(db, user.id)
    if purpose == "unsub_watch":
        from app.services.mail.watch_digest import watch_mail_on
        return await watch_mail_on(db, user.id)
    return await audience.is_subscribed(db, user.id)


async def _state(db: AsyncSession, purpose: str, user: User | None) -> dict:
    name = LISTS[purpose][0]
    if user is None:
        return {"subscribed": False, "email": "", "list": name}
    rec = await audience.resolve(db, user.id)
    return {"subscribed": await _subscribed(db, purpose, user), "email": mask_email(rec.email if rec else ""),
            "list": name}


async def _write(db: AsyncSession, request: Request, user: User, kind: str) -> None:
    from app.api.auth import AUTH_CONSENT_VERSION, _client_ip, audit

    if kind in PERSONAL_KINDS:
        # Журнал персонализации ведёт агент персонализации; если его функция есть — пишем через неё.
        try:
            from app.services.personalization import set_mail_personalization  # type: ignore
        except ImportError:
            set_mail_personalization = None
        if set_mail_personalization is not None:
            await set_mail_personalization(db, user.id, enabled=(kind == "mail_personal"), request=request,
                                           source="mail_link")
            await db.commit()
            return

    db.add(Consent(user_id=user.id, kind=kind, version=AUTH_CONSENT_VERSION, ip=_client_ip(request),
                   user_agent=(request.headers.get("user-agent") or "")[:500]))
    event = {"newsletter_revoked": "newsletter_off", "newsletter": "newsletter_on",
             "watch_mail_revoked": "watch_mail_off", "watch_mail": "watch_mail_on",
             "mail_personal_revoked": "mail_personal_off", "mail_personal": "mail_personal_on"}[kind]
    await audit(db, user.id, event, request, detail="mail_link")
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
    purpose, user = await _user_from(t, db)
    return await _state(db, purpose, user)


@router.post("/unsubscribe")
async def unsubscribe(request: Request, t: str | None = None, db: AsyncSession = Depends(get_db)):
    purpose, user = await _user_from(await _token_from(request, t), db)
    if user is not None and await _subscribed(db, purpose, user):
        await _write(db, request, user, LISTS[purpose][2])
    return {"ok": True, **(await _state(db, purpose, user))}


@router.post("/resubscribe")
async def resubscribe(body: TokenBody, request: Request, db: AsyncSession = Depends(get_db)):
    purpose, user = await _user_from(body.t, db)
    if user is not None and user.status == "active" and not await _subscribed(db, purpose, user):
        await _write(db, request, user, LISTS[purpose][1])
    return {"ok": True, **(await _state(db, purpose, user))}
