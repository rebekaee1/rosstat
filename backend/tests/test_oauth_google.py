"""Provider contract against Google's documented OIDC endpoints, without network calls."""
import asyncio
import base64
import json
import time
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest

from app.services.oauth import google


def _id_token(sub="stable-google-sub", aud="client-id"):
    claims = {
        "iss": "https://accounts.google.com", "aud": aud, "sub": sub,
        "iat": int(time.time()), "exp": int(time.time()) + 3600,
    }
    payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
    return f"e30.{payload}.signature"


def test_google_authorize_and_profile_exchange(monkeypatch):
    provider = google.GoogleProvider("client-id", "client-secret")
    authorize = provider.authorize_url(
        state="state-123", code_challenge="challenge-123",
        redirect_uri="https://forecasteconomy.com/api/v1/auth/oauth/google/callback",
    )
    assert urlsplit(authorize).netloc == "accounts.google.com"
    params = parse_qs(urlsplit(authorize).query)
    assert params["scope"] == ["openid email profile"]
    assert params["state"] == ["state-123"]
    assert params["code_challenge"] == ["challenge-123"]

    seen = []

    def handler(request):
        seen.append(request)
        if request.url.path == "/token":
            data = parse_qs(request.content.decode())
            assert data["code_verifier"] == ["verifier-123"]
            assert data["client_secret"] == ["client-secret"]
            return httpx.Response(200, json={
                "access_token": "access-123", "id_token": _id_token(),
            })
        assert request.url.path == "/v1/userinfo"
        assert request.headers["Authorization"] == "Bearer access-123"
        return httpx.Response(200, json={
            "sub": "stable-google-sub", "email": "member@example.com",
            "email_verified": True, "name": "Example Member",
            "picture": "https://example.com/photo.png",
        })

    original_client = httpx.AsyncClient
    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(google.httpx, "AsyncClient", lambda **kwargs: original_client(transport=transport, **kwargs))
    tokens = asyncio.run(provider.exchange_code(
        code="auth-code", code_verifier="verifier-123",
        redirect_uri="https://forecasteconomy.com/api/v1/auth/oauth/google/callback",
    ))
    profile = asyncio.run(provider.fetch_profile(tokens))
    assert len(seen) == 2
    assert (profile.provider, profile.sub, profile.email, profile.email_verified) == (
        "google", "stable-google-sub", "member@example.com", True,
    )
    assert profile.display_name == "Example Member"
    assert profile.avatar_url == "https://example.com/photo.png"


def test_google_rejects_wrong_audience_and_userinfo_subject(monkeypatch):
    provider = google.GoogleProvider("client-id", "client-secret")
    with pytest.raises(ValueError, match="claims rejected"):
        google._id_token_subject(_id_token(aud="other-client"), "client-id")

    def handler(request):
        return httpx.Response(200, json={"sub": "different-user"})

    original_client = httpx.AsyncClient
    monkeypatch.setattr(
        google.httpx, "AsyncClient",
        lambda **kwargs: original_client(transport=httpx.MockTransport(handler), **kwargs),
    )
    with pytest.raises(ValueError, match="subject differs"):
        asyncio.run(provider.fetch_profile({
            "access_token": "access-123", "id_token": _id_token(),
        }))
