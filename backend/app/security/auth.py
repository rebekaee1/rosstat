"""Куки-хелперы, current-user и CSRF-зависимости (ADR-0007).

Cookie `fe_sess` — httpOnly+Secure+SameSite=Lax (опаковый id сессии).
Cookie `XSRF-TOKEN` — НЕ httpOnly (читается JS) для double-submit CSRF.
Публичные эндпоинты сессию не читают (инвариант: кэш не варьировать по куке).
"""
from typing import Optional

from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import User
from app.services import session as session_svc
from app.services.api_i18n import api_detail
from app.services.identity.service import get_user


def effective_auth_cookie_domain() -> str:
    """Cookie Domain shared by apex and ru. so OAuth state survives the hop.

    Host-only ``fe_oauth`` / ``fe_sess`` dies when login starts on
    ``ru.forecasteconomy.com`` and the provider returns to apex (or the
    reverse). Explicit ``RUSTATS_AUTH_COOKIE_DOMAIN`` wins; production
    apex defaults to ``.forecasteconomy.com``; localhost stays host-only.
    """
    if settings.auth_cookie_domain:
        return settings.auth_cookie_domain
    if settings.debug:
        return ""
    host = (settings.public_host or "").removeprefix("www.")
    if host.endswith("forecasteconomy.com"):
        return ".forecasteconomy.com"
    return ""


def _cookie_kwargs() -> dict:
    kw = {
        "httponly": True,
        "secure": settings.auth_cookie_secure,
        "samesite": "lax",
        "path": "/",
    }
    domain = effective_auth_cookie_domain()
    if domain:
        kw["domain"] = domain
    return kw


def set_session_cookies(response: Response, session_id: str, csrf_token: str) -> None:
    ttl = settings.auth_session_ttl_seconds
    response.set_cookie(
        session_svc.SESSION_COOKIE, session_id, max_age=ttl, **_cookie_kwargs()
    )
    # CSRF-кука читается JS → httponly=False
    csrf_kw = _cookie_kwargs()
    csrf_kw["httponly"] = False
    response.set_cookie(session_svc.CSRF_COOKIE, csrf_token, max_age=ttl, **csrf_kw)


def clear_session_cookies(response: Response) -> None:
    path = "/"
    domain = effective_auth_cookie_domain() or None
    response.delete_cookie(session_svc.SESSION_COOKIE, path=path, domain=domain)
    response.delete_cookie(session_svc.CSRF_COOKIE, path=path, domain=domain)


async def current_session(request: Request) -> Optional[dict]:
    sid = request.cookies.get(session_svc.SESSION_COOKIE)
    return await session_svc.load_session(sid)


async def get_optional_user(
    request: Request, db: AsyncSession = Depends(get_db)
) -> Optional[User]:
    sess = await current_session(request)
    if not sess:
        return None
    user = await get_user(db, sess["user_id"])
    if user is None or user.status != "active":
        return None
    request.state.session = sess
    return user


async def get_current_user(
    request: Request, db: AsyncSession = Depends(get_db)
) -> User:
    user = await get_optional_user(request, db)
    if user is None:
        raise HTTPException(
            status_code=401,
            detail=api_detail("Не авторизован", "Not authenticated"),
        )
    return user


async def require_csrf(request: Request) -> None:
    """Double-submit: заголовок X-XSRF-TOKEN обязан совпасть с csrf сессии."""
    sess = await current_session(request)
    if not sess:
        raise HTTPException(
            status_code=401,
            detail=api_detail("Не авторизован", "Not authenticated"),
        )
    header = request.headers.get(session_svc.CSRF_HEADER)
    if not header or header != sess.get("csrf"):
        raise HTTPException(
            status_code=403,
            detail=api_detail("CSRF-токен недействителен", "Invalid CSRF token"),
        )
