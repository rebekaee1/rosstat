"""API личного кабинета: регистрация/вход/выход/профиль (ADR-0007).

Phase 1: email+пароль (этот файл) + OAuth (oauth.py). С 14.11.2026 (ADR-0032) —
подтверждение адреса и сброс пароля письмом (`services/mail`); пока почта выключена
(`RUSTATS_MAIL_ENABLED=false`) письма только записываются в журнал `mail_outbox`.
"""
import re
import logging
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import (
    User, Consent, AuthAudit, EmailCredential, OAuthIdentity, PushSubscription,
    UserSavedItem, UserWatch, UserExport, UserPreference, MailMessage, MailSuppression,
)
from app.services import session as session_svc
from app.services.identity.service import (
    register_email, authenticate_email, serialize_user, EmailAlreadyExists,
)
from app.services.identity.passwords import hash_password, normalize_email
from app.security import lockout
from app.security.auth import (
    get_current_user, require_csrf, set_session_cookies, clear_session_cookies,
)
from app.services.api_i18n import api_detail

logger = logging.getLogger(__name__)
from app.services.newsletter_personal import store as newsletter_store  # noqa: E402

router = APIRouter(prefix="/auth", tags=["auth"])

# Версия согласия = дата действующей редакции политики (152-ФЗ).
AUTH_CONSENT_VERSION = "2026-09-24"
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class RegisterIn(BaseModel):
    email: str
    password: str
    consent: bool = False
    newsletter: bool = False  # опциональное согласие на информационную рассылку

    @field_validator("email")
    @classmethod
    def _email_ok(cls, v: str) -> str:
        v = (v or "").strip()
        if not _EMAIL_RE.match(v):
            raise ValueError(api_detail("Некорректный email", "Invalid email"))
        return v

    @field_validator("password")
    @classmethod
    def _password_ok(cls, v: str) -> str:
        if v is None or len(v) < 8:
            raise ValueError(api_detail(
                "Пароль не короче 8 символов",
                "Password must be at least 8 characters",
            ))
        if len(v) > 256:
            raise ValueError(api_detail("Слишком длинный пароль", "Password is too long"))
        return v


class LoginIn(BaseModel):
    email: str
    password: str


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def audit(db: AsyncSession, user_id, event: str, request: Request, detail: str | None = None) -> None:
    db.add(AuthAudit(
        user_id=user_id,
        event=event,
        ip=_client_ip(request),
        user_agent=(request.headers.get("user-agent") or "")[:500],
        detail=detail,
    ))


async def _notify_new_user_safe(info: dict) -> None:
    from app.services.alerting import notify_new_user
    try:
        await notify_new_user(info)
    except Exception:
        logger.warning("notify_new_user failed", exc_info=True)


async def _notify_login_safe(info: dict) -> None:
    from app.services.alerting import notify_login
    try:
        await notify_login(info)
    except Exception:
        logger.warning("notify_login failed", exc_info=True)


async def _start_session(response: Response, user: User) -> None:
    sid, csrf = await session_svc.create_session(str(user.id))
    set_session_cookies(response, sid, csrf)


async def _serialize_with_admin(db: AsyncSession, user: User) -> dict:
    """serialize_user + is_admin. Обязателен и в /login, и в /me: логин-гейт
    /admin/bi кладёт ответ логина в auth-контекст как есть — без is_admin
    админ после входа получал «404 — страница не найдена»."""
    payload = await serialize_user(db, user)
    from app.api.admin_bi import user_is_admin
    if await user_is_admin(db, user):
        payload["is_admin"] = True
    return payload


@router.post("/register", status_code=201)
async def register(body: RegisterIn, request: Request, response: Response, background: BackgroundTasks,
                   db: AsyncSession = Depends(get_db)):
    if not body.consent:
        raise HTTPException(
            status_code=422,
            detail=api_detail(
                "Требуется согласие на обработку персональных данных",
                "Consent to personal data processing is required",
            ),
        )
    try:
        user = await register_email(db, body.email, body.password)
    except EmailAlreadyExists:
        raise HTTPException(
            status_code=409,
            detail=api_detail(
                "Пользователь с таким email уже существует",
                "An account with this email already exists",
            ),
        )
    ua = (request.headers.get("user-agent") or "")[:500]
    ip = _client_ip(request)
    db.add(Consent(
        user_id=user.id, kind="pd", version=AUTH_CONSENT_VERSION, ip=ip, user_agent=ua,
    ))
    if body.newsletter:
        db.add(Consent(
            user_id=user.id, kind="newsletter", version=AUTH_CONSENT_VERSION, ip=ip, user_agent=ua,
        ))
    await audit(db, user.id, "register", request)
    await db.commit()
    await _start_session(response, user)
    from app.services.locale import get_locale
    from app.services.signup_attribution import record_signup

    # Круг 11: как пришёл человек (метод, язык сайта, страна, рассылка) пишем здесь же,
    # в запросе регистрации; остальное дополнит задача атрибуции. Не роняет регистрацию.
    await record_signup(
        db, user_id=user.id, method="email", site_locale=get_locale(),
        newsletter=body.newsletter, ip=ip,
    )
    await _notify_new_user_safe({
        "method": "Email + пароль",
        "email": body.email,
        "phone": None,
        "display_name": user.display_name,
        "newsletter": body.newsletter,
        "locale": get_locale(),
        "ip": ip,
        "user_agent": ua,
        "user_id": str(user.id),
    })
    # ADR-0032: письмо «подтвердите адрес» — после ответа, не задерживая регистрацию.
    _queue_verify_mail(background, user.id, normalize_email(body.email), get_locale())
    return {"user": await serialize_user(db, user)}


def _queue_verify_mail(background: BackgroundTasks, user_id, email: str, locale: str) -> None:
    from app.services.mail import account as mail_account, service as mail_service
    from app.services.mail.tokens import TokenSecretMissing

    try:
        rendered = mail_account.verify_mail(user_id, email, locale)
    except TokenSecretMissing:
        logger.warning("verify mail skipped: RUSTATS_MAIL_TOKEN_SECRET is not set")
        return
    background.add_task(mail_service.send_now, kind="verify_email", to=email, locale=locale,
                        rendered=rendered, user_id=user_id)


@router.post("/login")
async def login(body: LoginIn, request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    ident = normalize_email(body.email)
    ip = _client_ip(request)
    if await lockout.is_locked("login", ident, ip):
        raise HTTPException(
            status_code=423,
            detail=api_detail(
                "Слишком много попыток. Повторите позже",
                "Too many attempts. Try again later",
            ),
        )
    user = await authenticate_email(db, body.email, body.password)
    if user is None:
        await lockout.record_failure("login", ident, ip)
        raise HTTPException(
            status_code=401,
            detail=api_detail(
                "Неверный email или пароль",
                "Invalid email or password",
            ),
        )
    if user.status != "active":
        raise HTTPException(
            status_code=403,
            detail=api_detail("Аккаунт недоступен", "Account unavailable"),
        )
    await lockout.reset("login", ident, ip)
    await audit(db, user.id, "login", request)
    await db.commit()
    await _start_session(response, user)
    await _notify_login_safe({
        "method": "Email + пароль",
        "email": ident,
        "phone": None,
        "display_name": user.display_name,
        "ip": ip,
        "user_agent": (request.headers.get("user-agent") or "")[:500],
        "user_id": str(user.id),
    })
    return {"user": await _serialize_with_admin(db, user)}


@router.post("/logout", status_code=204, dependencies=[Depends(require_csrf)])
async def logout(request: Request, response: Response):
    sid = request.cookies.get(session_svc.SESSION_COOKIE)
    await session_svc.destroy_session(sid)
    clear_session_cookies(response)
    response.status_code = 204


@router.get("/me")
async def me(
    request: Request,
    response: Response,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Sliding cookie: Redis-TTL продлевается на каждом запросе, а вот max_age
    # куки был заморожен датой логина — активный пользователь «слетал» через
    # 30 дней. /me дёргается при каждой загрузке SPA — переустанавливаем куки.
    sess = getattr(request.state, "session", None)
    if sess:
        set_session_cookies(response, sess["sid"], sess["csrf"])
    # Признак админа — для показа BI-раздела в кабинете (/admin/bi).
    # Обычным пользователям поле не отдаём вовсе: раздел для них не существует.
    payload = await _serialize_with_admin(db, user)
    # Круг 11: аккаунт создан меньше двух минут назад — фронт отличает «зарегистрировался»
    # от «вошёл» после возврата с провайдера (событие signup для OAuth).
    created = user.created_at
    payload["is_new"] = bool(
        created and (datetime.now(timezone.utc).replace(tzinfo=None) - created) < timedelta(minutes=2)
    )
    return {"user": payload}


class SetPasswordIn(BaseModel):
    password: str
    email: str | None = None

    @field_validator("password")
    @classmethod
    def _ok(cls, v: str) -> str:
        if v is None or len(v) < 8:
            raise ValueError(api_detail(
                "Пароль не короче 8 символов",
                "Password must be at least 8 characters",
            ))
        if len(v) > 256:
            raise ValueError(api_detail("Слишком длинный пароль", "Password is too long"))
        return v


@router.post("/set-password", dependencies=[Depends(require_csrf)])
async def set_password(body: SetPasswordIn, request: Request, background: BackgroundTasks,
                       user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    cred = await db.scalar(select(EmailCredential).where(EmailCredential.user_id == user.id))
    if cred is not None:
        cred.password_hash = hash_password(body.password)
        await audit(db, user.id, "set_password", request)
        await db.commit()
        return {"user": await serialize_user(db, user)}
    # OAuth-only: нужен email (из формы или подтверждённой привязки)
    email = normalize_email(body.email) if body.email else None
    if not email:
        ident = await db.scalar(
            select(OAuthIdentity).where(OAuthIdentity.user_id == user.id, OAuthIdentity.email.isnot(None))
        )
        email = normalize_email(ident.email) if ident and ident.email else None
    if not email:
        raise HTTPException(
            status_code=422,
            detail=api_detail("Укажите email", "Email is required"),
        )
    taken = await db.scalar(select(EmailCredential).where(EmailCredential.email == email))
    if taken is not None:
        raise HTTPException(
            status_code=409,
            detail=api_detail("Этот email уже используется", "This email is already in use"),
        )
    # Адрес, уже подтверждённый провайдером входа (Яндекс, Google), повторно не подтверждаем.
    oauth_verified = await db.scalar(select(OAuthIdentity).where(
        OAuthIdentity.user_id == user.id, func.lower(OAuthIdentity.email) == email,
        OAuthIdentity.email_verified.is_(True),
    ))
    db.add(EmailCredential(user_id=user.id, email=email, password_hash=hash_password(body.password),
                           email_verified=oauth_verified is not None))
    await audit(db, user.id, "set_password", request)
    await db.commit()
    if oauth_verified is None:
        from app.services.locale import get_locale
        _queue_verify_mail(background, user.id, email, get_locale())
    return {"user": await serialize_user(db, user)}


async def _login_methods_count(db: AsyncSession, user_id) -> int:
    n_ident = await db.scalar(select(func.count(OAuthIdentity.id)).where(OAuthIdentity.user_id == user_id))
    has_cred = await db.scalar(select(func.count(EmailCredential.id)).where(EmailCredential.user_id == user_id))
    return int(n_ident or 0) + (1 if has_cred else 0)


@router.delete("/identities/{identity_id}", dependencies=[Depends(require_csrf)])
async def unlink_identity(identity_id: int, request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    ident = await db.get(OAuthIdentity, identity_id)
    if ident is None or ident.user_id != user.id:
        raise HTTPException(
            status_code=404,
            detail=api_detail("Способ входа не найден", "Sign-in method not found"),
        )
    if await _login_methods_count(db, user.id) <= 1:
        raise HTTPException(
            status_code=400,
            detail=api_detail(
                "Нельзя удалить последний способ входа",
                "Cannot remove the last sign-in method",
            ),
        )
    await db.delete(ident)
    await audit(db, user.id, "unlink", request, detail=ident.provider)
    await db.commit()
    return {"user": await serialize_user(db, user)}


@router.post("/logout-all", dependencies=[Depends(require_csrf)])
async def logout_all(request: Request, response: Response, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await session_svc.destroy_user_sessions(str(user.id))
    await audit(db, user.id, "logout_all", request)
    await db.commit()
    # Текущее устройство остаётся в системе — минтим свежую сессию.
    sid, csrf = await session_svc.create_session(str(user.id))
    set_session_cookies(response, sid, csrf)
    return {"ok": True}


class FeedbackIn(BaseModel):
    message: str
    contact: str | None = None

    @field_validator("message")
    @classmethod
    def _msg_ok(cls, v: str) -> str:
        v = (v or "").strip()
        if len(v) < 5:
            raise ValueError(api_detail(
                "Сообщение слишком короткое",
                "Message is too short",
            ))
        if len(v) > 4000:
            raise ValueError(api_detail(
                "Сообщение слишком длинное",
                "Message is too long",
            ))
        return v

    @field_validator("contact")
    @classmethod
    def _contact_ok(cls, v: str | None) -> str | None:
        v = (v or "").strip()
        return v[:200] if v else None


async def _notify_feedback_safe(info: dict) -> None:
    from app.services.alerting import notify_feedback
    try:
        await notify_feedback(info)
    except Exception:
        logger.warning("notify_feedback failed", exc_info=True)


@router.post("/feedback", dependencies=[Depends(require_csrf)])
async def submit_feedback(body: FeedbackIn, request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Обратная связь от авторизованного пользователя → мгновенно в Telegram + audit."""
    profile = await serialize_user(db, user)
    await audit(db, user.id, "feedback", request, detail=body.message[:200])
    await db.commit()
    await _notify_feedback_safe({
        "email": profile.get("email"),
        "display_name": user.display_name,
        "user_id": str(user.id),
        "message": body.message,
        "contact": body.contact,
    })
    return {"ok": True}


class ProfileIn(BaseModel):
    display_name: str | None = None

    @field_validator("display_name")
    @classmethod
    def _name_ok(cls, v: str | None) -> str | None:
        v = (v or "").strip()
        if len(v) > 120:
            raise ValueError(api_detail(
                "Имя не длиннее 120 символов",
                "Name must be at most 120 characters",
            ))
        return v or None


@router.patch("/account/profile", dependencies=[Depends(require_csrf)])
async def update_profile(body: ProfileIn, request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Смена отображаемого имени из кабинета. Пустое значение очищает поле."""
    user.display_name = body.display_name
    await audit(db, user.id, "profile_update", request, detail=(body.display_name or "")[:120])
    await db.commit()
    return {"user": await serialize_user(db, user)}


class NewsletterIn(BaseModel):
    subscribe: bool


@router.post("/account/newsletter", dependencies=[Depends(require_csrf)])
async def update_newsletter(body: NewsletterIn, request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Подписка/отписка на информационную рассылку из кабинета (152-ФЗ: журнал
    согласий append-only — пишем новую запись, не удаляем прошлые)."""
    db.add(Consent(
        user_id=user.id,
        kind="newsletter" if body.subscribe else "newsletter_revoked",
        version=AUTH_CONSENT_VERSION,
        ip=_client_ip(request),
        user_agent=(request.headers.get("user-agent") or "")[:500],
    ))
    await audit(db, user.id, "newsletter_on" if body.subscribe else "newsletter_off", request)
    await db.commit()
    return {"user": await serialize_user(db, user)}


@router.get("/account/export")
async def export_account(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """152-ФЗ: выгрузка персональных данных пользователя в JSON."""
    profile = await serialize_user(db, user)
    consents = (await db.scalars(select(Consent).where(Consent.user_id == user.id))).all()
    events = (await db.scalars(select(AuthAudit).where(AuthAudit.user_id == user.id))).all()
    # Кабинет (круг 11): данные человека, которые он сам накопил. Токен личной ленты
    # календаря не выгружаем (в БД только его хэш), даём лишь признак «выпущен».
    saved = (await db.scalars(
        select(UserSavedItem).where(UserSavedItem.user_id == user.id).order_by(UserSavedItem.created_at))).all()
    watches = (await db.scalars(
        select(UserWatch).where(UserWatch.user_id == user.id).order_by(UserWatch.created_at))).all()
    exports = (await db.scalars(
        select(UserExport).where(UserExport.user_id == user.id).order_by(UserExport.created_at))).all()
    prefs = await db.get(UserPreference, user.id)
    mails = (await db.scalars(
        select(MailMessage).where(MailMessage.user_id == user.id).order_by(MailMessage.created_at))).all()
    payload = {
        "user": profile,
        "consents": [
            {"kind": c.kind, "version": c.version,
             "granted_at": c.granted_at.isoformat() if c.granted_at else None}
            for c in consents
        ],
        "auth_events": [
            {"event": e.event, "detail": e.detail,
             "ts": e.ts.isoformat() if e.ts else None}
            for e in events
        ],
        "saved_items": [
            {"kind": r.kind, "item_key": r.item_key, "title": r.title, "payload": r.payload,
             "created_at": r.created_at.isoformat() if r.created_at else None}
            for r in saved
        ],
        "watches": [
            {"subject_kind": w.subject_kind, "subject_key": w.subject_key, "channel": w.channel,
             "last_seen_date": w.last_seen_date.isoformat() if w.last_seen_date else None,
             "created_at": w.created_at.isoformat() if w.created_at else None}
            for w in watches
        ],
        "exports": [
            {"source": x.source, "subject_key": x.subject_key, "format": x.format, "params": x.params,
             "rows_count": x.rows_count, "created_at": x.created_at.isoformat() if x.created_at else None}
            for x in exports
        ],
        # ADR-0032: какие письма сайт вам отправлял (тема и итог, без текста письма).
        "emails": [
            {"kind": m.kind, "subject": m.subject, "to": m.to_email, "status": m.status,
             "created_at": m.created_at.isoformat() if m.created_at else None,
             "sent_at": m.sent_at.isoformat() if m.sent_at else None}
            for m in mails
        ],
        "preferences": {
            "data": (prefs.data if prefs else {}) or {},
            "calendar_feed_active": bool(prefs and prefs.feed_token_hash),
        },
        # ADR-0033: профиль интересов для персонального выпуска и что в личных выпусках было подобрано.
        "newsletter_personal": await newsletter_store.account_export(db, user.id),
    }
    return JSONResponse(
        payload,
        headers={"Content-Disposition": 'attachment; filename="forecasteconomy-my-data.json"'},
    )


@router.delete("/account", dependencies=[Depends(require_csrf)])
async def delete_account(request: Request, response: Response, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """152-ФЗ: полное удаление аккаунта и ПДн (Postgres + Redis)."""
    uid = user.id
    # Явное удаление (не полагаемся на FK CASCADE: в SQLite он off по умолчанию).
    await db.execute(delete(OAuthIdentity).where(OAuthIdentity.user_id == uid))
    await db.execute(delete(EmailCredential).where(EmailCredential.user_id == uid))
    await db.execute(delete(Consent).where(Consent.user_id == uid))
    await db.execute(delete(AuthAudit).where(AuthAudit.user_id == uid))
    # Кабинет (круг 11) и подписки web-push: тоже ПДн, удаляем явно, а не только каскадом.
    await db.execute(delete(UserSavedItem).where(UserSavedItem.user_id == uid))
    await db.execute(delete(UserWatch).where(UserWatch.user_id == uid))
    await db.execute(delete(UserExport).where(UserExport.user_id == uid))
    await db.execute(delete(UserPreference).where(UserPreference.user_id == uid))
    await db.execute(delete(PushSubscription).where(PushSubscription.user_id == uid))
    # ADR-0032: журнал писем хранит адрес получателя — тоже ПДн.
    await db.execute(delete(MailMessage).where(MailMessage.user_id == uid))
    await db.execute(delete(MailSuppression).where(MailSuppression.user_id == uid))
    # ADR-0033: профиль интересов и снимки личных выпусков — производные от действий человека.
    await newsletter_store.account_erase(db, uid)
    # Круг 11 (152-ФЗ): аналитические следы — user_signups, identity_links, user_id в
    # frontend_events сразу; большие таблицы без индекса обнулит ночная уборка.
    from app.services.account_erasure import erase_analytics_now
    await erase_analytics_now(db, uid)
    await db.execute(delete(User).where(User.id == uid))
    # Анонимный маркер факта удаления (без PII / без user_id).
    db.add(AuthAudit(user_id=None, event="account_deleted"))
    await db.commit()
    # Purge Redis: все сессии и счётчики попыток.
    await session_svc.destroy_user_sessions(str(uid))
    clear_session_cookies(response)
    return {"ok": True}


# --- Почта аккаунта (ADR-0032): подтверждение адреса и сброс пароля ------------------

class TokenIn(BaseModel):
    token: str


class ForgotIn(BaseModel):
    email: str


class ResetIn(BaseModel):
    token: str
    password: str

    @field_validator("password")
    @classmethod
    def _ok(cls, v: str) -> str:
        return SetPasswordIn._ok(v)


def _bad_link(code: str) -> HTTPException:
    return HTTPException(status_code=400, detail={
        "code": code,
        "message": api_detail(
            "Ссылка устарела или уже использована. Запросите новое письмо.",
            "The link has expired or was already used. Request a new email.",
        ),
    })


def _uuid_or_none(value: str):
    try:
        return uuid.UUID(value)
    except (ValueError, TypeError, AttributeError):
        return None


@router.post("/email/verify")
async def verify_email(body: TokenIn, request: Request, db: AsyncSession = Depends(get_db)):
    """Подтверждение адреса по ссылке из письма. Без сессии: ссылку открывают и на телефоне."""
    from app.services.mail import tokens

    try:
        tok = tokens.verify("verify", body.token)
    except tokens.TokenError as exc:
        raise _bad_link("expired" if str(exc) == "expired" else "invalid_link")
    except tokens.TokenSecretMissing:
        raise _bad_link("invalid_link")
    uid = _uuid_or_none(tok.user_id)
    cred = await db.scalar(select(EmailCredential).where(EmailCredential.user_id == uid)) if uid else None
    if cred is None or tokens.fingerprint(cred.email) != tok.fingerprint:
        raise _bad_link("invalid_link")
    if not cred.email_verified:
        cred.email_verified = True
        await audit(db, cred.user_id, "email_verified", request)
        await db.commit()
    return {"ok": True}


@router.post("/email/verify/resend", dependencies=[Depends(require_csrf)])
async def resend_verify_email(request: Request, background: BackgroundTasks,
                              user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    from app.services.locale import get_locale
    from app.services.mail import service as mail_service

    cred = await db.scalar(select(EmailCredential).where(EmailCredential.user_id == user.id))
    if cred is None or cred.email_verified:
        return {"ok": True, "sent": False}
    if not await mail_service.rate_ok("verify", str(user.id), limit=3, window_seconds=3600):
        raise HTTPException(status_code=423, detail=api_detail(
            "Письмо уже отправлено. Новое можно запросить через час.",
            "The email was already sent. You can request a new one in an hour.",
        ))
    _queue_verify_mail(background, user.id, cred.email, get_locale())
    await audit(db, user.id, "verify_resend", request)
    await db.commit()
    return {"ok": True, "sent": True}


@router.post("/password/forgot")
async def forgot_password(body: ForgotIn, request: Request, background: BackgroundTasks,
                          db: AsyncSession = Depends(get_db)):
    """Письмо со ссылкой на новый пароль. Ответ всегда одинаковый: по нему нельзя узнать,
    есть ли такой адрес на сайте."""
    from app.services.locale import get_locale
    from app.services.mail import account as mail_account, service as mail_service
    from app.services.mail.tokens import TokenSecretMissing

    ok = {"ok": True}
    email = normalize_email(body.email or "")
    if not _EMAIL_RE.match(email):
        raise HTTPException(status_code=422, detail=api_detail("Некорректный email", "Invalid email"))
    ip = _client_ip(request)
    if not await mail_service.rate_ok("forgot_ip", ip, limit=10, window_seconds=3600):
        raise HTTPException(status_code=423, detail=api_detail(
            "Слишком много запросов. Попробуйте через час.", "Too many requests. Try again in an hour.",
        ))
    if not await mail_service.rate_ok("forgot_email", email, limit=3, window_seconds=3600):
        return ok
    cred = await db.scalar(select(EmailCredential).where(EmailCredential.email == email))
    locale = get_locale()
    if cred is None:
        # Пароля нет, но адрес известен по входу через провайдера: подсказываем, как войти.
        ident = await db.scalar(select(OAuthIdentity).where(
            func.lower(OAuthIdentity.email) == email, OAuthIdentity.email_verified.is_(True)))
        if ident is not None:
            try:
                rendered = mail_account.oauth_hint_mail(ident.provider, locale)
            except TokenSecretMissing:  # pragma: no cover — письмо без подписанных ссылок
                return ok
            await audit(db, ident.user_id, "password_reset_oauth_hint", request)
            await db.commit()
            background.add_task(mail_service.send_now, kind="oauth_hint", to=email,
                                locale=locale, rendered=rendered, user_id=ident.user_id)
        return ok
    try:
        rendered = mail_account.reset_mail(cred.user_id, cred.password_hash, locale)
    except TokenSecretMissing:
        logger.warning("reset mail skipped: RUSTATS_MAIL_TOKEN_SECRET is not set")
        return ok
    await audit(db, cred.user_id, "password_reset_requested", request)
    await db.commit()
    background.add_task(mail_service.send_now, kind="password_reset", to=cred.email,
                        locale=locale, rendered=rendered, user_id=cred.user_id)
    return ok


@router.post("/password/reset")
async def reset_password(body: ResetIn, request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    """Новый пароль по ссылке из письма: старые сессии закрываются, адрес считается
    подтверждённым (человек открыл письмо), счётчик неудачных входов сбрасывается."""
    from app.services.mail import tokens

    try:
        tok = tokens.verify("reset", body.token)
    except tokens.TokenError as exc:
        raise _bad_link("expired" if str(exc) == "expired" else "invalid_link")
    except tokens.TokenSecretMissing:
        raise _bad_link("invalid_link")
    uid = _uuid_or_none(tok.user_id)
    cred = await db.scalar(select(EmailCredential).where(EmailCredential.user_id == uid)) if uid else None
    if cred is None or tokens.fingerprint(cred.password_hash) != tok.fingerprint:
        raise _bad_link("invalid_link")
    cred.password_hash = hash_password(body.password)
    cred.email_verified = True
    await audit(db, cred.user_id, "password_reset", request)
    await db.commit()
    await session_svc.destroy_user_sessions(str(cred.user_id))
    await lockout.reset("login", cred.email, _client_ip(request))
    clear_session_cookies(response)
    return {"ok": True}
