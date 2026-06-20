"""VK ID OAuth 2.1 (ADR-0007).

Public client + обязательный PKCE (без client_secret в обмене). На callback
приходит device_id — он обязателен в обмене кода. Email не гарантирован →
User может быть без email. Callback должен быть «чистым» backend-эндпоинтом
(без HTML/JS), иначе код утечёт через Referer (требование VK ID).
"""
from urllib.parse import urlencode

import httpx

from app.config import settings
from app.services.oauth.base import OAuthProvider, OAuthProfile

_AUTHORIZE = "https://id.vk.ru/authorize"
_TOKEN = "https://id.vk.ru/oauth2/auth"
_USERINFO = "https://id.vk.ru/oauth2/user_info"
# scope "phone" выдаёт телефон, только если приложение VK ID имеет разрешение.
_DEFAULT_SCOPE = "email"
_TIMEOUT = httpx.Timeout(10.0)


class VkProvider(OAuthProvider):
    name = "vk"

    def __init__(self, client_id: str, scope: str | None = None):
        self.client_id = client_id
        self.scope = scope or _DEFAULT_SCOPE

    def authorize_url(self, *, state: str, code_challenge: str, redirect_uri: str) -> str:
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "scope": self.scope,
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
        return f"{_AUTHORIZE}?{urlencode(params)}"

    async def exchange_code(self, *, code, code_verifier, redirect_uri, extra=None) -> dict:
        device_id = (extra or {}).get("device_id")
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "code_verifier": code_verifier,
            "client_id": self.client_id,
            "device_id": device_id,
            "redirect_uri": redirect_uri,
        }
        async with httpx.AsyncClient(timeout=_TIMEOUT) as cli:
            r = await cli.post(_TOKEN, data=data)
            r.raise_for_status()
            return r.json()

    async def fetch_profile(self, tokens: dict) -> OAuthProfile:
        access = tokens["access_token"]
        # email иногда приходит прямо в ответе токена.
        token_email = tokens.get("email")
        async with httpx.AsyncClient(timeout=_TIMEOUT) as cli:
            r = await cli.post(
                _USERINFO,
                data={"client_id": self.client_id, "access_token": access},
            )
            r.raise_for_status()
            payload = r.json()
        user = payload.get("user", payload)
        email = user.get("email") or token_email
        phone = user.get("phone") or tokens.get("phone")
        name = " ".join(x for x in [user.get("first_name"), user.get("last_name")] if x) or None
        return OAuthProfile(
            provider="vk",
            sub=str(user.get("user_id") or user.get("id") or tokens.get("user_id")),
            email=email,
            email_verified=bool(email),  # VK отдаёт только подтверждённый email
            phone=str(phone) if phone else None,
            display_name=name,
            avatar_url=user.get("avatar"),
        )
