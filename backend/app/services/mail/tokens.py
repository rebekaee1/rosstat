"""Подписанные ссылки в письмах (ADR-0032).

Формат: ``<payload>.<sig>``, где payload — base64url(JSON), sig — первые 32 знака
base64url(HMAC-SHA256(mail_token_secret, purpose|payload)). Назначение входит в
подпись: токен отписки нельзя предъявить как токен сброса пароля.

Назначения:
  unsub  — отписка от рассылки; без срока (ссылка из старого письма должна работать);
  unsub_watch — отписка только от писем о новых значениях (колокольчик); без срока;
  unpers — «письма без персональной подборки» (выпуск остаётся, подборка по действиям — нет); без срока;
  verify — подтверждение адреса; 7 суток; привязан к адресу (смена адреса гасит ссылку);
  open   — пиксель открытия письма (ADR-0034): в поле человека стоит номер строки журнала писем; без срока;
  reset  — сброс пароля; 1 час; привязан к отпечатку текущего хэша пароля, поэтому
           одноразовый: после смены пароля та же ссылка не подходит.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass

from app.config import settings

PURPOSES = ("unsub", "unsub_watch", "unpers", "verify", "reset", "open")
TTL_SECONDS = {"unsub": None, "unsub_watch": None, "unpers": None, "verify": 7 * 24 * 3600, "reset": 3600,
               "open": None}
_SIG_LEN = 32


class TokenError(Exception):
    """Ссылка повреждена, просрочена или выпущена другим секретом."""


class TokenSecretMissing(RuntimeError):
    """Секрет ссылок не задан: письма со ссылками не формируются."""


@dataclass(frozen=True)
class MailToken:
    purpose: str
    user_id: str
    fingerprint: str
    expires_at: int | None


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _unb64(text: str) -> bytes:
    pad = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + pad)


def _secret() -> bytes:
    secret = (settings.mail_token_secret or "").strip()
    if len(secret) < 16:
        raise TokenSecretMissing("RUSTATS_MAIL_TOKEN_SECRET is not set")
    return secret.encode("utf-8")


def fingerprint(value: str | None) -> str:
    """Короткий отпечаток (адрес или хэш пароля); само значение в ссылку не попадает."""
    return hashlib.sha256((value or "").encode("utf-8")).hexdigest()[:16]


def _sign(purpose: str, payload: str) -> str:
    mac = hmac.new(_secret(), f"{purpose}|{payload}".encode("utf-8"), hashlib.sha256).digest()
    return _b64(mac)[:_SIG_LEN]


def issue(purpose: str, user_id: str, fp: str = "", *, now: float | None = None) -> str:
    if purpose not in PURPOSES:
        raise ValueError(purpose)
    ttl = TTL_SECONDS[purpose]
    exp = int((now if now is not None else time.time()) + ttl) if ttl else None
    body = {"u": str(user_id), "f": fp}
    if exp is not None:
        body["x"] = exp
    payload = _b64(json.dumps(body, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    return f"{payload}.{_sign(purpose, payload)}"


def verify(purpose: str, token: str, *, now: float | None = None) -> MailToken:
    if purpose not in PURPOSES:
        raise ValueError(purpose)
    if not token or token.count(".") != 1 or len(token) > 600:
        raise TokenError("malformed")
    payload, sig = token.split(".", 1)
    if not hmac.compare_digest(sig, _sign(purpose, payload)):
        raise TokenError("signature")
    try:
        body = json.loads(_unb64(payload))
    except Exception as exc:  # noqa: BLE001 — любой мусор = неверная ссылка
        raise TokenError("payload") from exc
    if not isinstance(body, dict) or not isinstance(body.get("u"), str):
        raise TokenError("payload")
    exp = body.get("x")
    if exp is not None:
        if not isinstance(exp, int):
            raise TokenError("payload")
        if (now if now is not None else time.time()) > exp:
            raise TokenError("expired")
    return MailToken(purpose=purpose, user_id=body["u"], fingerprint=str(body.get("f") or ""), expires_at=exp)
