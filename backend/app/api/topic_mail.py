"""Подписка на показатель по почте (совет 19.11.2026): «Присылать новые значения на почту».

Механика и правила — `services/mail/topic_subscribe.py`. Ручки:
  * ``GET  /topic-mail/config``      — включено ли (всегда отвечает; сайт по нему рисует форму);
  * ``POST /topic-mail/subscribe``   — вошедший: слежение сразу (нужен CSRF); гость: адрес и согласие →
                                       письмо «подтвердите»; ответ гостю всегда одинаковый;
  * ``GET  /topic-mail/confirm?t=``  — только состояние заявки (название ряда, маска адреса), ничего не меняет;
  * ``POST /topic-mail/confirm``     — подтверждение нажатием кнопки на странице `/account/topic-confirm`.
Флаг ``RUSTATS_TOPIC_MAIL_ENABLED`` выключен — всё, кроме config, отвечает 404.
"""
from __future__ import annotations

import logging
import re

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import User
from app.security.auth import get_optional_user, require_csrf
from app.services.api_i18n import api_detail
from app.services.mail import service as mail_service
from app.services.mail import topic_subscribe as svc
from app.services.mail.account import mask_email

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/topic-mail", tags=["mail"])

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

_MESSAGES = {
    "subject_not_found": ("Этот показатель нельзя выбрать для писем.", "This indicator cannot be chosen for emails."),
    "invalid_key": ("Этот показатель нельзя выбрать для писем.", "This indicator cannot be chosen for emails."),
    "limit_reached": ("Достигнут предел слежений. Снимите лишние в личном кабинете.",
                      "You have reached the watch limit. Remove some in your account."),
    "consent_required": ("Нужно согласие на обработку адреса.", "Consent to process your address is required."),
    "invalid_email": ("Проверьте адрес почты.", "Please check the email address."),
    "rate_limited": ("Слишком много запросов. Попробуйте через час.", "Too many requests. Try again in an hour."),
    "expired": ("Ссылка устарела или уже сработала. Подпишитесь ещё раз на странице показателя.",
                "The link has expired or was already used. Subscribe again on the indicator page."),
    "in_progress": ("Подписка уже подтверждается. Обновите страницу через минуту.",
                    "The subscription is already being confirmed. Refresh the page in a minute."),
    "unavailable": ("Подписка временно недоступна. Попробуйте позже.",
                    "Subscriptions are temporarily unavailable. Please try again later."),
    "invalid_link": ("Ссылка повреждена. Подпишитесь ещё раз на странице показателя.",
                     "The link is broken. Subscribe again on the indicator page."),
}


def _err(code: str, status: int) -> HTTPException:
    ru, en = _MESSAGES.get(code, ("Не получилось. Попробуйте ещё раз.", "Something went wrong. Please try again."))
    return HTTPException(status_code=status, detail={"code": code, "message": api_detail(ru, en)})


def _require_enabled() -> None:
    if not settings.topic_mail_enabled:
        raise HTTPException(status_code=404, detail=api_detail("Не найдено", "Not found"))


class SubscribeIn(BaseModel):
    code: str
    email: str | None = None
    consent: bool = False
    page: str | None = None


class ConfirmIn(BaseModel):
    t: str | None = None


@router.get("/config")
async def config():
    return {"enabled": bool(settings.topic_mail_enabled)}


def _client(request: Request) -> tuple[str, str]:
    from app.api.auth import _client_ip

    return _client_ip(request), (request.headers.get("user-agent") or "")[:500]


@router.post("/subscribe", dependencies=[Depends(_require_enabled)])
async def subscribe(body: SubscribeIn, request: Request, background: BackgroundTasks,
                    user: User | None = Depends(get_optional_user), db: AsyncSession = Depends(get_db)):
    from app.services.locale import get_locale

    locale = "en" if get_locale() == "en" else "ru"
    ip, ua = _client(request)
    try:
        title = await svc.series_title(db, body.code, locale)
    except svc.TopicMailError as err:
        raise _err(err.code, err.status)

    if user is not None:
        await require_csrf(request)
        return await _subscribe_signed_in(db, request, background, user, body.code, locale, ip, ua)

    email = mail_service.normalize(body.email or "")
    if not _EMAIL_RE.match(email) or len(email) > 320:
        raise _err("invalid_email", 422)
    if not body.consent:
        raise _err("consent_required", 422)
    if not await mail_service.rate_ok("topic_ip", ip, limit=10, window_seconds=3600):
        raise _err("rate_limited", 423)
    sent = {"ok": True, "status": "confirm_sent", "title": title}
    # Адрес получает не больше трёх писем «подтвердите» в час; ответ тот же — без подсказки, что адрес известен.
    if not await mail_service.rate_ok("topic_email", email, limit=3, window_seconds=3600):
        return sent
    if await mail_service.is_suppressed(db, email):
        return sent
    try:
        item = await svc.save_pending(email=email, code=body.code.strip(), locale=locale, ip=ip, user_agent=ua,
                                      page=body.page)
    except svc.TopicMailError as err:
        raise _err(err.code, err.status)
    try:
        rendered = svc.confirm_mail(item, title)
    except Exception:  # noqa: BLE001 — нет секрета ссылок: письмо не формируется, ответ тот же
        logger.warning("topic mail confirm skipped: link secret is not set")
        return sent
    background.add_task(mail_service.send_now, kind="topic_confirm", to=item.email, locale=locale, rendered=rendered)
    return sent


async def _subscribe_signed_in(db, request, background, user: User, code: str, locale: str, ip: str, ua: str):
    from app.api.auth import _queue_verify_mail, audit
    from app.services.mail import audience

    try:
        _row, created = await svc.add_subject(db, user.id, code)
    except svc.TopicMailError as err:
        await db.rollback()
        raise _err(err.code, err.status)
    await svc.ensure_watch_mail_on(db, user.id, ip=ip, user_agent=ua)
    await audit(db, user.id, "topic_mail_on", request, detail=code[:120])
    await db.commit()
    rec = await audience.resolve(db, user.id)
    if rec is None:
        return {"ok": True, "status": "no_email", "created": created}
    if rec.verified:
        return {"ok": True, "status": "subscribed", "created": created, "email": mask_email(rec.email)}
    if await mail_service.rate_ok("verify", str(user.id), limit=3, window_seconds=3600):
        _queue_verify_mail(background, user.id, rec.email, locale)
    return {"ok": True, "status": "confirm_email", "created": created, "email": mask_email(rec.email)}


@router.get("/confirm", dependencies=[Depends(_require_enabled)])
async def confirm_state(t: str | None = None, db: AsyncSession = Depends(get_db)):
    try:
        item = await svc.pending_from_token(t or "")
        title = await svc.series_title(db, item.code, item.locale)
    except svc.TopicMailError as err:
        raise _err(err.code, err.status)
    return {"ok": True, "title": title, "email": mask_email(item.email), "code": item.code}


@router.post("/confirm", dependencies=[Depends(_require_enabled)])
async def confirm(body: ConfirmIn, request: Request, db: AsyncSession = Depends(get_db)):
    try:
        item = await svc.pending_from_token(body.t or "")
        title = await svc.series_title(db, item.code, item.locale)
        await svc.claim(item.id)
    except svc.TopicMailError as err:
        raise _err(err.code, err.status)
    try:
        user, created_account = await _confirm_claimed(db, request, item)
    except Exception:
        await db.rollback()
        await svc.release(item.id)
        raise
    await svc.drop_pending(item.id)
    if created_account:
        await svc.mark_signup(db, item, user)
        await db.commit()
        from app.api.auth import _notify_new_user_safe

        await _notify_new_user_safe({
            "method": "Подписка на показатель по почте", "email": item.email, "phone": None,
            "display_name": None, "newsletter": False, "locale": item.locale, "ip": item.ip or "",
            "user_agent": item.user_agent or "", "user_id": str(user.id),
        })
    return {"ok": True, "status": "subscribed", "title": title, "code": item.code,
            "new_account": created_account, "email": mask_email(item.email)}


async def _confirm_claimed(db: AsyncSession, request: Request, item: svc.Pending) -> tuple[User, bool]:
    """Подтверждение под замком: аккаунт (найденный или новый), адрес подтверждён, слежение, согласие, commit."""
    from app.api.auth import audit

    user, cred = await svc.user_by_email(db, item.email)
    created_account = False
    if user is not None and user.status != "active":
        raise _err("invalid_link", 400)
    if user is None:
        user, created_account = await svc.create_account(db, item)
        if created_account:
            await audit(db, user.id, "register", request, detail="topic_mail")
    elif cred is not None and not cred.email_verified:
        # Человек открыл письмо на этот адрес: адрес его.
        cred.email_verified = True
        await audit(db, user.id, "email_verified", request, detail="topic_mail")
    try:
        await svc.add_subject(db, user.id, item.code)
    except svc.TopicMailError as err:
        raise _err(err.code, err.status)
    await svc.ensure_watch_mail_on(db, user.id, ip=item.ip, user_agent=item.user_agent)
    await audit(db, user.id, "topic_mail_on", request, detail=item.code[:120])
    await db.commit()
    return user, created_account
