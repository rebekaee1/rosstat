"""WebP-версия OG-карточек для видимых картинок SSR (круг 12, зона SPEED2).

Замер 12.10.2026: карточка страны `/og/world/germany.png?portrait=1` весит 307 КБ, ландшафтная — 410 КБ; на телефоне
(1,6 Мбит/с) это 1,5–2 с канала, которые делились с CSS и JS. Видимая в SSR картинка отдаётся теперь через
`<picture>` с WebP (`?fmt=webp&w=720|1080|1200`, качество 90 — на глаз неотличимо, портрет 720 px: 85 КБ вместо 307),
запасной вариант — прежний PNG. Сами PNG (og:image, ImageObject) не меняются.

Преобразование лежит в одном месте — ASGI-прослойке по адресу `/api/v1/og-image/…`: рендер карточек остаётся в
своих обработчиках (их десятки), а результат конвертируется из уже готового PNG и кэшируется в процессе.
"""
from __future__ import annotations

import asyncio
import hashlib
import io
import threading
from collections import OrderedDict

from PIL import Image
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

OG_PREFIX = "/api/v1/og-image/"
ALLOWED_WIDTHS = frozenset({720, 1080, 1200})
WEBP_QUALITY = 90

_CACHE: OrderedDict[tuple[bytes, int], bytes] = OrderedDict()
_CACHE_LOCK = threading.Lock()
_CACHE_MAX_ENTRIES = 256


def png_to_webp(png: bytes, width: int | None = None, *, quality: int = WEBP_QUALITY) -> bytes:
    """PNG → WebP; `width` (если меньше исходной) уменьшает кадр пропорционально фильтром Ланцоша."""
    key = (hashlib.blake2b(png, digest_size=12).digest(), width or 0)
    with _CACHE_LOCK:
        hit = _CACHE.get(key)
        if hit is not None:
            _CACHE.move_to_end(key)
            return hit
    with Image.open(io.BytesIO(png)) as source:
        image = source.convert("RGB")
    if width and width < image.width:
        image = image.resize((width, max(1, round(image.height * width / image.width))), Image.LANCZOS)
    buf = io.BytesIO()
    image.save(buf, format="WEBP", quality=quality, method=4)
    out = buf.getvalue()
    with _CACHE_LOCK:
        _CACHE[key] = out
        while len(_CACHE) > _CACHE_MAX_ENTRIES:
            _CACHE.popitem(last=False)
    return out


class OgWebpMiddleware(BaseHTTPMiddleware):
    """`…?fmt=webp[&w=720]` на адресах OG-карточек возвращает WebP вместо PNG; всё остальное проходит как есть."""

    async def dispatch(self, request: Request, call_next):
        if not request.url.path.startswith(OG_PREFIX) or request.query_params.get("fmt") != "webp":
            return await call_next(request)
        response = await call_next(request)
        if response.status_code != 200 or response.headers.get("content-type", "").split(";")[0] != "image/png":
            return response
        body = b"".join([chunk async for chunk in response.body_iterator])
        try:
            raw_width = int(request.query_params.get("w", "0"))
        except ValueError:
            raw_width = 0
        width = raw_width if raw_width in ALLOWED_WIDTHS else None
        try:
            webp = await asyncio.to_thread(png_to_webp, body, width)
        except Exception:  # noqa: BLE001 — не получилось: отдаём исходный PNG (браузер возьмёт запасной вариант)
            return Response(content=body, media_type="image/png", headers={
                k: v for k, v in response.headers.items() if k.lower() not in ("content-length", "content-type")
            })
        headers = {k: v for k, v in response.headers.items() if k.lower() not in ("content-length", "content-type")}
        return Response(content=webp, media_type="image/webp", headers=headers)
