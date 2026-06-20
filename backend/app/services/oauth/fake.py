"""Fake OAuth-провайдер для dev/test (ADR-0007).

НЕ ходит в сеть. `code` несёт base64url(json(profile)); authorize-эндпоинт
(`/auth/oauth/fake/authorize`) сразу 302-ит обратно на callback. На проде
запрещён (assert на старте + реестр не отдаёт его при debug=false).
"""
import base64
import json
from urllib.parse import urlencode

from app.config import settings
from app.services.oauth.base import OAuthProvider, OAuthProfile


def encode_code(profile: dict) -> str:
    raw = json.dumps(profile).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode_code(code: str) -> dict:
    pad = "=" * (-len(code) % 4)
    return json.loads(base64.urlsafe_b64decode(code + pad))


class FakeProvider(OAuthProvider):
    name = "fake"

    def authorize_url(self, *, state: str, code_challenge: str, redirect_uri: str) -> str:
        base = settings.auth_public_base_url.rstrip("/")
        params = urlencode({"state": state, "redirect_uri": redirect_uri})
        return f"{base}/api/v1/auth/oauth/fake/authorize?{params}"

    async def exchange_code(self, *, code, code_verifier, redirect_uri, extra=None) -> dict:
        return {"_code": code}

    async def fetch_profile(self, tokens: dict) -> OAuthProfile:
        data = decode_code(tokens["_code"])
        return OAuthProfile(
            provider="fake",
            sub=str(data["sub"]),
            email=data.get("email"),
            email_verified=bool(data.get("email_verified", False)),
            display_name=data.get("name"),
            avatar_url=data.get("avatar"),
        )
