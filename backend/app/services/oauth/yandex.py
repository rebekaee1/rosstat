"""Яндекс ID OAuth (ADR-0007).

authorize: oauth.yandex.ru/authorize, token: oauth.yandex.ru/token,
userinfo: login.yandex.ru/info (header Authorization: OAuth <token>).
Email от Яндекса считаем подтверждённым.
"""
from urllib.parse import urlencode

import httpx

from app.config import settings
from app.services.oauth.base import OAuthProvider, OAuthProfile

_AUTHORIZE = "https://oauth.yandex.ru/authorize"
_TOKEN = "https://oauth.yandex.ru/token"
_USERINFO = "https://login.yandex.ru/info"
# Scope конфигурируется (login:default_phone добавляется только если приложение
# имеет соответствующее разрешение в кабинете Яндекс ID — иначе authorize упадёт).
_DEFAULT_SCOPE = "login:email login:info login:avatar"
_TIMEOUT = httpx.Timeout(10.0)


class YandexProvider(OAuthProvider):
    name = "yandex"

    def __init__(self, client_id: str, client_secret: str, scope: str | None = None):
        self.client_id = client_id
        self.client_secret = client_secret
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
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": redirect_uri,
            "code_verifier": code_verifier,
        }
        async with httpx.AsyncClient(timeout=_TIMEOUT) as cli:
            r = await cli.post(_TOKEN, data=data)
            r.raise_for_status()
            return r.json()

    async def fetch_profile(self, tokens: dict) -> OAuthProfile:
        access = tokens["access_token"]
        async with httpx.AsyncClient(timeout=_TIMEOUT) as cli:
            r = await cli.get(
                _USERINFO,
                params={"format": "json"},
                headers={"Authorization": f"OAuth {access}"},
            )
            r.raise_for_status()
            info = r.json()
        avatar = None
        if info.get("default_avatar_id") and not info.get("is_avatar_empty"):
            avatar = f"https://avatars.yandex.net/get-yapic/{info['default_avatar_id']}/islands-200"
        email = info.get("default_email") or (info.get("emails") or [None])[0]
        # default_phone выдаётся только при scope login:default_phone.
        phone_obj = info.get("default_phone") or {}
        phone = phone_obj.get("number") if isinstance(phone_obj, dict) else None
        return OAuthProfile(
            provider="yandex",
            sub=str(info["id"]),
            email=email,
            email_verified=bool(email),  # Яндекс подтверждает почту аккаунта
            phone=phone,
            display_name=info.get("display_name") or info.get("real_name") or info.get("login"),
            avatar_url=avatar,
        )
