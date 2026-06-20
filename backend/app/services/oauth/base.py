"""Контракт OAuth-провайдера + PKCE-утилиты (ADR-0007)."""
import base64
import hashlib
import secrets
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class OAuthProfile:
    """Нормализованный профиль из userinfo провайдера."""
    provider: str
    sub: str                 # стабильный provider_user_id
    email: str | None
    email_verified: bool
    display_name: str | None = None
    avatar_url: str | None = None
    phone: str | None = None  # default_phone (Яндекс) / phone (VK), если выдан scope'ом


def generate_pkce() -> tuple[str, str]:
    """Вернуть (code_verifier, code_challenge S256)."""
    verifier = secrets.token_urlsafe(64)[:128]
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return verifier, challenge


class OAuthProvider(ABC):
    name: str

    @abstractmethod
    def authorize_url(self, *, state: str, code_challenge: str, redirect_uri: str) -> str:
        ...

    @abstractmethod
    async def exchange_code(
        self, *, code: str, code_verifier: str, redirect_uri: str, extra: dict | None = None
    ) -> dict:
        ...

    @abstractmethod
    async def fetch_profile(self, tokens: dict) -> OAuthProfile:
        ...
