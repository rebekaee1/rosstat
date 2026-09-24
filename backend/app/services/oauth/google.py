"""Google OpenID Connect sign-in using the shared state + PKCE flow.

Only the basic identity scopes are requested. Google UserInfo is fetched once
during sign-in; access and refresh tokens are never stored.
The ID token comes directly from Google's TLS-protected token endpoint, so OIDC
Core 3.1.3.7 permits issuer validation by TLS in place of a signature check.
"""
import base64
import binascii
import json
import time
from urllib.parse import urlencode

import httpx

from app.services.oauth.base import OAuthProfile, OAuthProvider

_AUTHORIZE = "https://accounts.google.com/o/oauth2/v2/auth"
_TOKEN = "https://oauth2.googleapis.com/token"
_USERINFO = "https://openidconnect.googleapis.com/v1/userinfo"
_TIMEOUT = httpx.Timeout(10.0)


def _id_token_subject(token: str, client_id: str) -> str:
    """Check claims from the authenticated token response before using UserInfo."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError("Invalid Google ID token format")
        payload = parts[1]
        claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    except (ValueError, UnicodeError, binascii.Error) as exc:
        raise ValueError("Invalid Google ID token") from exc
    if not isinstance(claims, dict):
        raise ValueError("Invalid Google ID token claims")
    now = time.time()
    if (
        claims.get("iss") not in ("https://accounts.google.com", "accounts.google.com")
        or claims.get("aud") != client_id
        or (claims.get("azp") is not None and claims["azp"] != client_id)
        or type(claims.get("exp")) is not int or claims["exp"] <= now
        or type(claims.get("iat")) is not int or claims["iat"] > now + 60
    ):
        raise ValueError("Google ID token claims rejected")
    sub = claims.get("sub")
    if not isinstance(sub, str) or not sub or len(sub) > 200:
        raise ValueError("Google ID token has no valid subject")
    return sub


class GoogleProvider(OAuthProvider):
    name = "google"

    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret

    def authorize_url(self, *, state: str, code_challenge: str, redirect_uri: str) -> str:
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "scope": "openid email profile",
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
        return f"{_AUTHORIZE}?{urlencode(params)}"

    async def exchange_code(self, *, code, code_verifier, redirect_uri, extra=None) -> dict:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as cli:
            response = await cli.post(_TOKEN, data={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "redirect_uri": redirect_uri,
                "code_verifier": code_verifier,
            })
            response.raise_for_status()
            return response.json()

    async def fetch_profile(self, tokens: dict) -> OAuthProfile:
        id_sub = _id_token_subject(tokens["id_token"], self.client_id)
        access_token = tokens["access_token"]
        async with httpx.AsyncClient(timeout=_TIMEOUT) as cli:
            response = await cli.get(
                _USERINFO,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            response.raise_for_status()
            info = response.json()
        sub = info.get("sub")
        if not isinstance(sub, str) or not sub or len(sub) > 200:
            raise ValueError("Google UserInfo has no valid subject")
        if sub != id_sub:
            raise ValueError("Google UserInfo subject differs from ID token")
        return OAuthProfile(
            provider="google",
            sub=sub,
            email=info.get("email"),
            email_verified=info.get("email_verified") is True,
            display_name=info.get("name"),
            avatar_url=info.get("picture"),
        )
