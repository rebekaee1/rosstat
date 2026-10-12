"""WebP-версия OG-карточек (`?fmt=webp&w=…`, круг 12 SPEED2): тот же кадр, меньше байт, прежний PNG без параметра."""
from __future__ import annotations

import io

from PIL import Image
from starlette.applications import Starlette
from starlette.responses import Response
from starlette.routing import Route
from starlette.testclient import TestClient

from app.services.og_webp import OG_PREFIX, OgWebpMiddleware, png_to_webp


def _png(width=1080, height=1350) -> bytes:
    image = Image.new("RGB", (width, height), (240, 242, 247))
    for x in range(0, width, 7):
        for y in range(40, 80):
            image.putpixel((x, y), (30, 30, 60))
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def test_png_to_webp_resizes_and_caches():
    png = _png()
    full = png_to_webp(png)
    small = png_to_webp(png, 720)
    assert Image.open(io.BytesIO(full)).format == "WEBP"
    assert Image.open(io.BytesIO(small)).size == (720, 900)
    assert png_to_webp(png, 720) is small, "повторный вызов берётся из кэша процесса"


def _client(png: bytes) -> TestClient:
    async def card(request):
        return Response(png, media_type="image/png", headers={"Cache-Control": "public, max-age=3600"})

    async def missing(request):
        return Response("no", status_code=404)

    app = Starlette(routes=[
        Route(OG_PREFIX + "world/germany.png", card),
        Route(OG_PREFIX + "world/none.png", missing),
        Route("/other.png", card),
    ])
    app.add_middleware(OgWebpMiddleware)
    return TestClient(app)


def test_middleware_converts_only_on_request_and_keeps_headers():
    png = _png()
    client = _client(png)
    plain = client.get(OG_PREFIX + "world/germany.png?portrait=1")
    assert plain.headers["content-type"] == "image/png" and plain.content == png
    webp = client.get(OG_PREFIX + "world/germany.png?portrait=1&fmt=webp&w=720")
    assert webp.headers["content-type"] == "image/webp"
    assert webp.headers["cache-control"] == "public, max-age=3600"
    assert Image.open(io.BytesIO(webp.content)).size == (720, 900)
    # недопустимая ширина — полный размер, а не произвольное увеличение/уменьшение по запросу
    odd = client.get(OG_PREFIX + "world/germany.png?fmt=webp&w=9999")
    assert Image.open(io.BytesIO(odd.content)).size == (1080, 1350)


def test_middleware_ignores_other_paths_and_errors():
    client = _client(_png())
    assert client.get("/other.png?fmt=webp").headers["content-type"] == "image/png"
    assert client.get(OG_PREFIX + "world/none.png?fmt=webp").status_code == 404
