from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

import httpx

from app.config import settings


class YandexApiError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None, payload: Any | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


@dataclass(frozen=True)
class YandexResponse:
    data: Any
    status_code: int
    request_hash: str
    sampled: bool | None = None
    sample_share: float | None = None
    contains_sensitive_data: bool | None = None


def stable_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class YandexOAuthClient:
    def __init__(self, token: str, base_url: str, timeout: int | None = None):
        if not token:
            raise YandexApiError("Missing Yandex OAuth token")
        self.token = token
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout or settings.analytics_request_timeout

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        data: Any | None = None,
        files: Any | None = None,
        headers: dict[str, str] | None = None,
    ) -> YandexResponse:
        url = f"{self.base_url}/{path.lstrip('/')}"
        request_fingerprint = {
            "method": method.upper(),
            "url": url,
            "params": params or {},
            "json": json_body or {},
        }
        merged_headers = {
            "Authorization": f"OAuth {self.token}",
            "Accept": "application/json",
            **(headers or {}),
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.request(
                method,
                url,
                params=params,
                json=json_body,
                data=data,
                files=files,
                headers=merged_headers,
            )
        if response.status_code >= 400:
            try:
                payload = response.json()
            except ValueError:
                payload = response.text
            raise YandexApiError(
                f"Yandex API returned HTTP {response.status_code} for {method.upper()} {path}",
                status_code=response.status_code,
                payload=payload,
            )
        content_type = response.headers.get("content-type", "")
        if "application/json" in content_type:
            payload = response.json()
        else:
            payload = response.text
        return YandexResponse(
            data=payload,
            status_code=response.status_code,
            request_hash=stable_hash(request_fingerprint),
            sampled=payload.get("sampled") if isinstance(payload, dict) else None,
            sample_share=payload.get("sample_share") if isinstance(payload, dict) else None,
            contains_sensitive_data=payload.get("contains_sensitive_data") if isinstance(payload, dict) else None,
        )
