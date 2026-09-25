"""Logout and OAuth must delete cookies with the same flags they were set with."""

from starlette.responses import Response

from app.api.oauth import _clear_oauth_cookie
from app.config import settings
from app.security.auth import clear_session_cookies, set_session_cookies
from app.services import session as session_svc


def _flags(header: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for part in header.split(";")[1:]:
        part = part.strip()
        if not part:
            continue
        if "=" in part:
            key, value = part.split("=", 1)
            out[key.lower()] = value
        else:
            out[part.lower()] = ""
    return out


def _set_cookie_headers(response: Response) -> list[str]:
    return [
        value.decode()
        for key, value in response.raw_headers
        if key.lower() == b"set-cookie"
    ]


def test_clear_session_cookies_match_set_flags(monkeypatch):
    monkeypatch.setattr(settings, "auth_cookie_secure", True)
    monkeypatch.setattr(settings, "auth_cookie_domain", ".forecasteconomy.com")

    created = Response()
    set_session_cookies(created, "sid", "csrf")
    cleared = Response()
    clear_session_cookies(cleared)

    created_headers = _set_cookie_headers(created)
    cleared_headers = _set_cookie_headers(cleared)
    assert len(created_headers) == 2
    assert len(cleared_headers) == 2

    for name in (session_svc.SESSION_COOKIE, session_svc.CSRF_COOKIE):
        before = _flags(next(h for h in created_headers if h.startswith(f"{name}=")))
        after = _flags(next(h for h in cleared_headers if h.startswith(f"{name}=")))
        for flag in ("secure", "domain", "path", "samesite"):
            assert before.get(flag) == after.get(flag), name
        assert ("httponly" in before) == ("httponly" in after), name
        assert after.get("max-age") == "0"

    session = _flags(next(h for h in cleared_headers if h.startswith("fe_sess=")))
    csrf = _flags(next(h for h in cleared_headers if h.startswith("XSRF-TOKEN=")))
    assert "httponly" in session
    assert "httponly" not in csrf
    assert session["secure"] == ""
    assert session["domain"] == ".forecasteconomy.com"


def test_clear_oauth_cookie_matches_set_flags(monkeypatch):
    monkeypatch.setattr(settings, "auth_cookie_secure", True)
    monkeypatch.setattr(settings, "auth_cookie_domain", ".forecasteconomy.com")

    cleared = Response()
    _clear_oauth_cookie(cleared)
    header = _set_cookie_headers(cleared)[0]
    assert header.startswith("fe_oauth=")
    flags = _flags(header)
    assert "httponly" in flags
    assert flags["domain"] == ".forecasteconomy.com"
    assert "secure" in flags
    assert flags["samesite"].lower() == "lax"
    assert flags["max-age"] == "0"
