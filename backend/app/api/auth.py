"""API личного кабинета: регистрация/вход/выход/профиль (ADR-0007).

Phase 1: email+пароль (этот файл) + OAuth (oauth.py). Почты нет — без
подтверждения email и сброса пароля.
"""
import re
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User, Consent, AuthAudit, EmailCredential, OAuthIdentity
from app.services import session as session_svc
from app.services.identity.service import (
    register_email, authenticate_email, serialize_user, EmailAlreadyExists,
)
from app.services.identity.passwords import hash_password, normalize_email
from app.security import lockout
from app.security.auth import (
    get_current_user, require_csrf, set_session_cookies, clear_session_cookies,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])

# Версия согласия = дата действующей редакции политики (152-ФЗ).
AUTH_CONSENT_VERSION = "2026-06-19"
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
            raise ValueError("Некорректный email")
        return v

    @field_validator("password")
    @classmethod
    def _password_ok(cls, v: str) -> str:
        if v is None or len(v) < 8:
            raise ValueError("Пароль не короче 8 символов")
        if len(v) > 256:
            raise ValueError("Слишком длинный пароль")
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


async def _start_session(response: Response, user: User) -> None:
    sid, csrf = await session_svc.create_session(str(user.id))
    set_session_cookies(response, sid, csrf)


@router.post("/register", status_code=201)
async def register(body: RegisterIn, request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    if not body.consent:
        raise HTTPException(status_code=422, detail="Требуется согласие на обработку персональных данных")
    try:
        user = await register_email(db, body.email, body.password)
    except EmailAlreadyExists:
        raise HTTPException(status_code=409, detail="Пользователь с таким email уже существует")
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
    await _notify_new_user_safe({
        "method": "Email + пароль",
        "email": body.email,
        "phone": None,
        "display_name": user.display_name,
        "newsletter": body.newsletter,
        "ip": ip,
        "user_agent": ua,
        "user_id": str(user.id),
    })
    return {"user": await serialize_user(db, user)}


@router.post("/login")
async def login(body: LoginIn, request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    ident = normalize_email(body.email)
    ip = _client_ip(request)
    if await lockout.is_locked("login", ident, ip):
        raise HTTPException(status_code=423, detail="Слишком много попыток. Повторите позже")
    user = await authenticate_email(db, body.email, body.password)
    if user is None:
        await lockout.record_failure("login", ident, ip)
        raise HTTPException(status_code=401, detail="Неверный email или пароль")
    if user.status != "active":
        raise HTTPException(status_code=403, detail="Аккаунт недоступен")
    await lockout.reset("login", ident, ip)
    await audit(db, user.id, "login", request)
    await db.commit()
    await _start_session(response, user)
    return {"user": await serialize_user(db, user)}


@router.post("/logout", status_code=204, dependencies=[Depends(require_csrf)])
async def logout(request: Request, response: Response):
    sid = request.cookies.get(session_svc.SESSION_COOKIE)
    await session_svc.destroy_session(sid)
    clear_session_cookies(response)
    response.status_code = 204


@router.get("/me")
async def me(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return {"user": await serialize_user(db, user)}


class SetPasswordIn(BaseModel):
    password: str
    email: str | None = None

    @field_validator("password")
    @classmethod
    def _ok(cls, v: str) -> str:
        if v is None or len(v) < 8:
            raise ValueError("Пароль не короче 8 символов")
        if len(v) > 256:
            raise ValueError("Слишком длинный пароль")
        return v


@router.post("/set-password", dependencies=[Depends(require_csrf)])
async def set_password(body: SetPasswordIn, request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
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
        raise HTTPException(status_code=422, detail="Укажите email")
    taken = await db.scalar(select(EmailCredential).where(EmailCredential.email == email))
    if taken is not None:
        raise HTTPException(status_code=409, detail="Этот email уже используется")
    db.add(EmailCredential(user_id=user.id, email=email, password_hash=hash_password(body.password), email_verified=False))
    await audit(db, user.id, "set_password", request)
    await db.commit()
    return {"user": await serialize_user(db, user)}


async def _login_methods_count(db: AsyncSession, user_id) -> int:
    n_ident = await db.scalar(select(func.count(OAuthIdentity.id)).where(OAuthIdentity.user_id == user_id))
    has_cred = await db.scalar(select(func.count(EmailCredential.id)).where(EmailCredential.user_id == user_id))
    return int(n_ident or 0) + (1 if has_cred else 0)


@router.delete("/identities/{identity_id}", dependencies=[Depends(require_csrf)])
async def unlink_identity(identity_id: int, request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    ident = await db.get(OAuthIdentity, identity_id)
    if ident is None or ident.user_id != user.id:
        raise HTTPException(status_code=404, detail="Способ входа не найден")
    if await _login_methods_count(db, user.id) <= 1:
        raise HTTPException(status_code=400, detail="Нельзя удалить последний способ входа")
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
            raise ValueError("Сообщение слишком короткое")
        if len(v) > 4000:
            raise ValueError("Сообщение слишком длинное")
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
    await db.execute(delete(User).where(User.id == uid))
    # Анонимный маркер факта удаления (без PII / без user_id).
    db.add(AuthAudit(user_id=None, event="account_deleted"))
    await db.commit()
    # Purge Redis: все сессии и счётчики попыток.
    await session_svc.destroy_user_sessions(str(uid))
    clear_session_cookies(response)
    return {"ok": True}
