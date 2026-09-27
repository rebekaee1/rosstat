"""Logout and OAuth clear both host and shared-domain cookies consistently."""

from starlette.responses import Response

from app.api.oauth import OAUTH_COOKIE, _attach_oauth_cookie, _clear_oauth_cookie
from app.config import settings
from app.security.auth import clear_session_cookies, set_session_cookies
from app.services import session as session_svc


def _headers(response: Response) -> dict[str, str]:
    return {
        value.decode().split("=", 1)[0]: value.decode()
        for key, value in response.raw_headers
        if key.lower() == b"set-cookie"
    }


def _matching_scope(created: str, cleared: str) -> None:
    for attr in ("domain=.forecasteconomy.com", "path=/", "samesite=lax", "secure"):
        assert attr in created.lower()
        assert attr in cleared.lower()
    assert "max-age=0" in cleared.lower()


def test_session_cookie_clear_matches_scope_and_http_only(monkeypatch):
    monkeypatch.setattr(settings, "auth_cookie_secure", True)
    monkeypatch.setattr(settings, "auth_cookie_domain", ".forecasteconomy.com")
    created = Response()
    cleared = Response()
    set_session_cookies(created, "sid", "csrf")
    clear_session_cookies(cleared)
    old, new = _headers(created), _headers(cleared)
    for cookie in (session_svc.SESSION_COOKIE, session_svc.CSRF_COOKIE):
        _matching_scope(old[cookie], new[cookie])
    assert "httponly" in new[session_svc.SESSION_COOKIE].lower()
    assert "httponly" not in new[session_svc.CSRF_COOKIE].lower()


def test_oauth_cookie_clear_matches_scope(monkeypatch):
    monkeypatch.setattr(settings, "auth_cookie_secure", True)
    monkeypatch.setattr(settings, "auth_cookie_domain", ".forecasteconomy.com")
    created = Response()
    cleared = Response()
    _attach_oauth_cookie(created, "state")
    _clear_oauth_cookie(cleared)
    old, new = _headers(created), _headers(cleared)
    _matching_scope(old[OAUTH_COOKIE], new[OAUTH_COOKIE])
    assert "httponly" in new[OAUTH_COOKIE].lower()
