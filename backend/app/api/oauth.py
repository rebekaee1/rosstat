"""OAuth start/callback (ADR-0007).

GET /auth/oauth/{provider}/start  → 302 на провайдера (state в Redis + fe_oauth-cookie).
GET /auth/oauth/{provider}/callback → обмен кода, резолв, сессия, 302 на next.
Callback — чистый 302 без HTML/JS (требование VK ID).
"""
import json
import logging
import secrets
from html import escape
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.services import session as session_svc
from app.services.oauth.base import generate_pkce, pkce_challenge_s256
from app.services.oauth.registry import get_provider, enabled_public_providers
from app.services.oauth import state as oauth_state
from app.services.oauth.fake import FakeProvider, encode_code
from app.services.identity.resolve import resolve_oauth, IdentityConflict, LinkRequiresAuth
from app.security.auth import (
    get_optional_user, set_session_cookies, current_session,
    effective_auth_cookie_domain,
)
from app.api.auth import audit, AUTH_CONSENT_VERSION
from app.models import Consent

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth/oauth", tags=["auth"])

OAUTH_COOKIE = session_svc.OAUTH_COOKIE


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


def _allowed_return_host(host: str | None) -> bool:
    """Same-site hosts only: apex / www / ru. / en. / localhost (tests)."""
    from app.services.locale import apex_host

    h = (host or "").strip().lower()
    if not h:
        return False
    if h in {"localhost", "127.0.0.1", "testserver", "test"}:
        return True
    apex = apex_host()
    return h == apex or h == f"www.{apex}" or h.endswith(f".{apex}")


def _safe_next(value: str | None) -> str:
    """Post-login redirect: relative path or absolute same-site URL.

    OAuth callback живёт на apex (кабинет провайдера), а вход часто
    стартует с ``ru.``. Относительный ``/account`` после callback оставляет
    пользователя на английском apex — фронт передаёт абсолютный next
    с хоста старта; здесь принимаем только same-site.
    """
    if not value:
        return "/account"
    value = value.strip()
    if value.startswith("/") and not value.startswith("//"):
        return value
    parsed = urlparse(value)
    if parsed.scheme not in ("http", "https") or not _allowed_return_host(parsed.hostname):
        return "/account"
    path = parsed.path or "/account"
    if not path.startswith("/") or path.startswith("//"):
        path = "/account"
    netloc = parsed.hostname or ""
    if parsed.port and parsed.port not in (80, 443):
        netloc = f"{netloc}:{parsed.port}"
    query = f"?{parsed.query}" if parsed.query else ""
    fragment = f"#{parsed.fragment}" if parsed.fragment else ""
    return f"{parsed.scheme}://{netloc}{path}{query}{fragment}"


def _path_on_next_origin(safe_next: str, path: str) -> str:
    """``/login`` / ``/account`` на том же origin, что и абсолютный next."""
    if not path.startswith("/") or path.startswith("//"):
        path = "/login"
    parsed = urlparse(safe_next)
    if parsed.scheme in ("http", "https") and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}{path}"
    return path


def _redirect_with_error(to: str, error: str) -> str:
    sep = "&" if "?" in to else "?"
    return f"{to}{sep}error={error}"


_REDIRECT_OVERRIDES = {
    "google": "oauth_google_redirect_uri",
    "yandex": "oauth_yandex_redirect_uri",
    "vk": "oauth_vk_redirect_uri",
}


def _redirect_uri(provider: str) -> str:
    # Полный override из кабинета провайдера (нестандартный путь/порт), иначе
    # строим стандартный same-origin callback из публичного базового URL.
    override_attr = _REDIRECT_OVERRIDES.get(provider)
    if override_attr:
        override = getattr(settings, override_attr, "")
        if override:
            return override
    base = settings.auth_public_base_url.rstrip("/")
    return f"{base}/api/v1/auth/oauth/{provider}/callback"


def _request_hostname(request: Request) -> str:
    raw = request.headers.get("x-forwarded-host") or request.headers.get("host") or ""
    return raw.split(",")[0].split(":")[0].strip().lower()


def _vk_callback_hostname() -> str:
    return (urlparse(_redirect_uri("vk")).hostname or "").lower()


def _vk_base_domain_hop(request: Request, provider: str) -> RedirectResponse | None:
    """Согнать старт VK на хост callback (обычно apex).

    Кабинет VK ID знает ``forecasteconomy.com``, не ``ru.``. Один 302
    Referer не меняет: браузер тащит origin документа через цепочку.
    Hop нужен, чтобы следующий ответ (HTML-мост) отдался уже с apex.
    """
    if provider != "vk":
        return None
    want = _vk_callback_hostname()
    got = _request_hostname(request)
    if not want or not got or got == want:
        return None
    apex = want.removeprefix("www.")
    if got != f"www.{apex}" and not got.endswith(f".{apex}"):
        return None
    public = urlparse(_redirect_uri("vk"))
    dest = f"{public.scheme}://{want}{request.url.path}"
    if request.url.query:
        dest = f"{dest}?{request.url.query}"
    return RedirectResponse(dest, status_code=302)


def _vk_authorize_bridge(authorize_url: str) -> HTMLResponse:
    """Документ на хосте callback → location.replace на id.vk.ru.

    После этого Referer для VK = apex, не ``ru.``. Чистый 302 с ``ru.``
    оставлял ``document.referrer=https://ru.forecasteconomy.com/``.
    """
    parsed = urlparse(authorize_url)
    if parsed.scheme != "https" or (parsed.hostname or "") not in {"id.vk.ru", "id.vk.com"}:
        raise ValueError("vk authorize host refused")
    href = escape(authorize_url, quote=True)
    js = json.dumps(authorize_url)
    html = (
        "<!doctype html><html lang=\"ru\"><head>"
        "<meta charset=\"utf-8\">"
        "<meta name=\"referrer\" content=\"origin\">"
        f"<meta http-equiv=\"refresh\" content=\"0;url={href}\">"
        "<title>VK ID</title></head><body>"
        f"<script>location.replace({js});</script>"
        f"<a href=\"{href}\">Continue</a>"
        "</body></html>"
    )
    return HTMLResponse(
        html,
        headers={
            "Cache-Control": "no-store",
            "Referrer-Policy": "origin",
        },
    )


def _oauth_cookie_kwargs() -> dict:
    kw = {"httponly": True, "secure": settings.auth_cookie_secure, "samesite": "lax", "path": "/"}
    domain = effective_auth_cookie_domain()
    if domain:
        kw["domain"] = domain
    return kw


def _fail(error: str, *, to: str = "/login") -> RedirectResponse:
    resp = RedirectResponse(_redirect_with_error(to, error), status_code=302)
    resp.delete_cookie(OAUTH_COOKIE, path="/", domain=effective_auth_cookie_domain() or None)
    return resp


def _attach_oauth_cookie(resp, state: str) -> None:
    resp.set_cookie(
        OAUTH_COOKIE,
        state,
        max_age=settings.auth_oauth_state_ttl_seconds,
        **_oauth_cookie_kwargs(),
    )


async def _mint_oauth_tx(
    *,
    provider: str,
    intent: str,
    safe_next: str,
    newsletter: bool,
    request: Request,
) -> tuple[str, str]:
    """Создать Redis-транзит + PKCE. Возвращает (state, code_challenge)."""
    state = secrets.token_urlsafe(32)
    verifier, challenge = generate_pkce()
    from app.services.locale import get_locale

    payload = {
        "provider": provider,
        "code_verifier": verifier,
        "intent": intent,
        "next": safe_next,
        "newsletter": bool(newsletter),
        # Язык хоста старта. Callback всегда на apex, Host там не про версию.
        "locale": get_locale(),
    }
    if intent == "link":
        sess = await current_session(request)
        payload["user_id"] = sess["user_id"] if sess else None
    await oauth_state.store_state(state, payload)
    return state, challenge


async def _fail_login_from_state(state: str | None) -> str:
    """Куда слать oauth_state/denied, если cookie уже потеряна, а state в query жив."""
    tx = await oauth_state.peek_state(state or "")
    if not tx:
        return "/login"
    return _path_on_next_origin(_safe_next(tx.get("next")), "/login")


@router.get("/providers")
async def oauth_providers():
    """Список включённых OAuth-провайдеров — фронт скрывает несконфигурированные."""
    return {"providers": enabled_public_providers()}


@router.get("/{provider}/start")
async def oauth_start(provider: str, request: Request, intent: str = "login", next: str = "/account", newsletter: int = 0, consent: int = 0):
    if intent not in ("login", "link"):
        intent = "login"
    if provider == "google" and intent == "login" and consent != 1:
        return _fail("consent_required")
    safe_next = _safe_next(next)
    prov = get_provider(provider)

    # VK: mint + fe_oauth на хосте старта (ru.), затем hop на apex.
    # Cookie только на apex HTML-мосту Chrome/Safari bounce-tracking снимает
    # → callback без fe_oauth → error=oauth_state на английском /login.
    hop = _vk_base_domain_hop(request, provider)
    if hop is not None:
        if prov is None:
            return _fail("oauth_disabled")
        if intent == "link":
            sess = await current_session(request)
            if not sess:
                return _fail("oauth_disabled")
        state, _challenge = await _mint_oauth_tx(
            provider=provider,
            intent=intent,
            safe_next=safe_next,
            newsletter=bool(newsletter),
            request=request,
        )
        _attach_oauth_cookie(hop, state)
        return hop

    if prov is None:
        return _fail("oauth_disabled")

    if intent == "link":
        sess = await current_session(request)
        if not sess:
            return _fail("oauth_disabled")  # связывание требует сессии

    # Apex после hop: reuse state из cookie, мост БЕЗ нового Set-Cookie
    # (повторная запись на bounce-документе снова попадает под ITP).
    existing = request.cookies.get(OAUTH_COOKIE)
    existing_tx = await oauth_state.peek_state(existing) if existing else None
    if (
        provider == "vk"
        and existing
        and existing_tx
        and existing_tx.get("provider") == provider
        and existing_tx.get("code_verifier")
        and _request_hostname(request) == _vk_callback_hostname()
    ):
        if (
            existing_tx.get("next") != safe_next
            or bool(existing_tx.get("newsletter")) != bool(newsletter)
            or existing_tx.get("intent") != intent
        ):
            existing_tx = {
                **existing_tx,
                "next": safe_next,
                "newsletter": bool(newsletter),
                "intent": intent,
            }
            await oauth_state.store_state(existing, existing_tx)
        challenge = pkce_challenge_s256(existing_tx["code_verifier"])
        url = prov.authorize_url(
            state=existing,
            code_challenge=challenge,
            redirect_uri=_redirect_uri(provider),
        )
        return _vk_authorize_bridge(url)

    state, challenge = await _mint_oauth_tx(
        provider=provider,
        intent=intent,
        safe_next=safe_next,
        newsletter=bool(newsletter),
        request=request,
    )
    url = prov.authorize_url(state=state, code_challenge=challenge, redirect_uri=_redirect_uri(provider))
    if provider == "vk" and _request_hostname(request) == _vk_callback_hostname():
        resp = _vk_authorize_bridge(url)
    else:
        resp = RedirectResponse(url, status_code=302)
    _attach_oauth_cookie(resp, state)
    return resp


@router.get("/fake/authorize")
async def fake_authorize(request: Request, state: str, redirect_uri: str):
    """Dev/test: мгновенный 302 обратно на callback с закодированным профилем."""
    if not (settings.auth_fake_provider_enabled and settings.debug):
        return RedirectResponse("/login?error=oauth_disabled", status_code=302)
    qp = request.query_params
    profile = {
        "sub": qp.get("sub", "fake-sub-1"),
        "email": qp.get("email", "fakeuser@example.com"),
        "email_verified": qp.get("email_verified", "true").lower() == "true",
        "name": qp.get("name", "Fake User"),
    }
    code = encode_code(profile)
    sep = "&" if "?" in redirect_uri else "?"
    return RedirectResponse(f"{redirect_uri}{sep}code={code}&state={state}", status_code=302)


@router.get("/{provider}/callback")
async def oauth_callback(provider: str, request: Request, db: AsyncSession = Depends(get_db)):
    qp = request.query_params
    state = qp.get("state")
    # next живёт в Redis по state: даже при потере fe_oauth уводим на ru./login,
    # а не на английский apex (кабинет callback всегда на forecasteconomy.com).
    if qp.get("error"):
        return _fail("oauth_denied", to=await _fail_login_from_state(state))

    code = qp.get("code")
    cookie_state = request.cookies.get(OAUTH_COOKIE)
    if not state or not code or not cookie_state or cookie_state != state:
        return _fail("oauth_state", to=await _fail_login_from_state(state))

    tx = await oauth_state.consume_state(state)
    if tx is None or tx.get("provider") != provider:
        fail_to = (
            _path_on_next_origin(_safe_next(tx.get("next")), "/login")
            if tx
            else "/login"
        )
        return _fail("oauth_state", to=fail_to)

    intent = tx.get("intent", "login")
    safe_next = _safe_next(tx.get("next"))
    fail_login = _path_on_next_origin(safe_next, "/login")
    fail_account = _path_on_next_origin(safe_next, "/account")

    prov = get_provider(provider)
    if prov is None:
        return _fail("oauth_disabled", to=fail_login)

    current_user = None
    if intent == "link":
        current_user = await get_optional_user(request, db)
        if current_user is None:
            return _fail("oauth_state", to=fail_login)

    try:
        tokens = await prov.exchange_code(
            code=code, code_verifier=tx["code_verifier"],
            redirect_uri=_redirect_uri(provider),
            extra={"device_id": qp.get("device_id")},
        )
        profile = await prov.fetch_profile(tokens)
        if provider == "google":
            from app.services.locale import locale_from_absolute_url
            start_locale = tx.get("locale")
            profile.locale = (
                start_locale if start_locale in ("ru", "en")
                else locale_from_absolute_url(safe_next)
            )
    except Exception:
        logger.exception("OAuth exchange/userinfo failed for provider=%s", provider)
        return _fail("oauth_failed", to=fail_login)

    try:
        user, created = await resolve_oauth(db, profile, intent, current_user)
    except IdentityConflict:
        await db.rollback()
        return _fail("link_conflict", to=fail_account)
    except LinkRequiresAuth:
        await db.rollback()
        return _fail("oauth_state", to=fail_login)

    newsletter = bool(tx.get("newsletter"))
    if created and intent == "login":
        # Выбор чекбоксов сделан во всплывающем окне перед редиректом.
        # Фиксируем версию/ip/ua; заранее отмеченная рассылка сама по себе
        # не доказывает действительное согласие для юрисдикций с opt-in.
        ip = request.client.host if request.client else "unknown"
        ua = (request.headers.get("user-agent") or "")[:500]
        db.add(Consent(user_id=user.id, kind="pd", version=AUTH_CONSENT_VERSION, ip=ip, user_agent=ua))
        if newsletter:
            db.add(Consent(user_id=user.id, kind="newsletter", version=AUTH_CONSENT_VERSION, ip=ip, user_agent=ua))

    await audit(db, user.id, intent if intent == "link" else "login", request, detail=provider)
    await db.commit()

    from app.services.locale import locale_from_absolute_url

    signup_locale = tx.get("locale")
    if signup_locale not in ("ru", "en"):
        signup_locale = locale_from_absolute_url(safe_next)
    auth_info = {
        "method": f"OAuth ({provider})",
        "email": profile.email,
        "phone": profile.phone,
        "display_name": profile.display_name,
        "newsletter": newsletter,
        "locale": signup_locale,
        "ip": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent"),
        "user_id": str(user.id),
    }
    if created:
        await _notify_new_user_safe(auth_info)
    elif intent == "login":
        await _notify_login_safe(auth_info)

    resp = RedirectResponse(safe_next, status_code=302)
    if intent == "login":
        sid, csrf = await session_svc.create_session(str(user.id))
        set_session_cookies(resp, sid, csrf)
    resp.delete_cookie(OAUTH_COOKIE, path="/", domain=effective_auth_cookie_domain() or None)
    return resp


# Compat-роутер: некоторые кабинеты провайдеров регистрируют callback по пути
# /api/auth/{provider}/callback (без /v1). Маршруты делегируют тем же хендлерам;
# совпадение redirect_uri обеспечивается override'ами в settings (см. _redirect_uri).
compat_router = APIRouter(prefix="/api", tags=["auth"])
compat_router.add_api_route("/auth/{provider}/start", oauth_start, methods=["GET"])
compat_router.add_api_route("/auth/{provider}/callback", oauth_callback, methods=["GET"])
