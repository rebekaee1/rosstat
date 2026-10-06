"""Веб-приложение (PWA): манифест, офлайн-страница, публичный конфиг флагов.

Манифест и офлайн-страница отдаются КАЖДЫМ origin отдельно (apex = английский,
ru. = русский): язык берётся из LocaleMiddleware по Host, как у robots.txt.
Service worker (`frontend/public/sw.js`) статический; здесь только то, что зависит
от хоста и флагов. Аварийные выключатели (`pwa_enabled`,
`pwa_install_prompt_enabled`) читают и фронт, и сам service worker из
GET /api/v1/pwa/config — выключение не требует пересборки фронта.
"""
from __future__ import annotations

from html import escape

from fastapi import APIRouter, Request, Response

from app.config import settings
from app.services.locale import get_locale

# Манифест/офлайн — без /api/v1 (так их видят браузер и service worker).
router = APIRouter(tags=["pwa"], include_in_schema=False)
# Публичный конфиг — под /api/v1/pwa.
config_router = APIRouter(prefix="/pwa", tags=["pwa"])

THEME = "#F4F5F7"

_COPY = {
    "ru": {
        "description": "Официальная макроэкономическая статистика по странам, прогнозы и календарь публикаций.",
        "shortcuts": [("Россия", "/russia"), ("Календарь публикаций", "/russia/calendar"), ("Валюты", "/currencies")],
        "offline_title": "Нет соединения",
        "offline_body": "Похоже, интернет пропал. Данные не показываются из памяти устройства, чтобы вы не увидели устаревшие цифры. Проверьте сеть и повторите.",
        "offline_retry": "Повторить",
    },
    "en": {
        "description": "Official macroeconomic statistics by country, with forecasts and a release calendar.",
        "shortcuts": [("Russia", "/russia"), ("Release calendar", "/russia/calendar"), ("Currencies", "/currencies")],
        "offline_title": "No connection",
        "offline_body": "It looks like the internet is gone. Data is never shown from the device cache, so you cannot see outdated numbers. Check your network and try again.",
        "offline_retry": "Try again",
    },
}


def _copy(locale: str) -> dict:
    return _COPY["en" if locale == "en" else "ru"]


def build_manifest(locale: str, origin: str) -> dict:
    """Web App Manifest для одного origin и языка."""
    copy = _copy(locale)
    lang = "en" if locale == "en" else "ru"
    base = origin.rstrip("/")
    return {
        "id": "/",
        "name": "Forecast Economy",
        "short_name": "Forecast Economy",
        "description": copy["description"],
        "lang": lang,
        "dir": "ltr",
        "start_url": "/",
        "scope": "/",
        "display": "standalone",
        "background_color": THEME,
        "theme_color": THEME,
        "categories": ["finance", "business", "news"],
        "icons": [
            {"src": "/icons/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
            {"src": "/icons/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
            {"src": "/icons/icon-maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
        ],
        "shortcuts": [
            {"name": name, "url": url, "icons": [{"src": "/icons/icon-192.png", "sizes": "192x192", "type": "image/png"}]}
            for name, url in copy["shortcuts"]
        ],
        # Позволяет getInstalledRelatedApps() узнать, что приложение уже стоит (Chrome Android).
        "prefer_related_applications": False,
        "related_applications": [{"platform": "webapp", "url": f"{base}/manifest.webmanifest"}],
    }


def _origin(request: Request) -> str:
    from app.api.sitemap import _request_sitemap_origin  # лениво: общий host-aware хелпер

    return _request_sitemap_origin(request)


@router.api_route("/manifest.webmanifest", methods=["GET", "HEAD"])
async def manifest(request: Request):
    import json

    body = json.dumps(build_manifest(get_locale(), _origin(request)), ensure_ascii=False)
    return Response(
        content=body,
        media_type="application/manifest+json; charset=utf-8",
        # no-cache: браузер перепроверяет (ETag не нужен — файл крошечный), язык зависит от Host.
        headers={"Cache-Control": "no-cache", "Vary": "Host"},
    )


def render_offline(locale: str) -> str:
    c = _copy(locale)
    lang = "en" if locale == "en" else "ru"
    return f"""<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="robots" content="noindex, nofollow">
<meta name="theme-color" content="{THEME}">
<title>{escape(c['offline_title'])} — Forecast Economy</title>
<style>
html{{background:{THEME};color:#202A3C;font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}}
body{{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;padding:24px;box-sizing:border-box}}
main{{max-width:26rem;text-align:center}}
.mark{{width:64px;height:64px;border-radius:16px;background:#202A3C;margin:0 auto 20px;display:block}}
h1{{font-size:1.4rem;margin:0 0 .6rem}}
p{{margin:0 0 1.4rem;line-height:1.5;color:#4A5568}}
button{{font:inherit;font-weight:600;border:0;border-radius:12px;padding:.8rem 1.6rem;background:#7C6232;color:#fff;min-height:44px;cursor:pointer}}
</style>
</head>
<body>
<main>
<img class="mark" src="/icons/icon-192.png" alt="" width="64" height="64">
<h1>{escape(c['offline_title'])}</h1>
<p>{escape(c['offline_body'])}</p>
<button type="button" onclick="location.reload()">{escape(c['offline_retry'])}</button>
</main>
</body>
</html>
"""


@router.api_route("/offline.html", methods=["GET", "HEAD"])
async def offline_page():
    # Статичная страница для service worker: он кладёт её в кэш при установке
    # и отдаёт ТОЛЬКО когда сеть недоступна. Никаких данных на ней нет.
    return Response(
        content=render_offline(get_locale()),
        media_type="text/html; charset=utf-8",
        headers={"Cache-Control": "no-cache", "Vary": "Host", "X-Robots-Tag": "noindex, nofollow"},
    )


@config_router.get("/config")
async def pwa_config(response: Response):
    """Публичные флаги для фронта и service worker (без пересборки фронта)."""
    response.headers["Cache-Control"] = "no-store"
    # Подписка на push доступна клиенту только за флагом и при настроенном публичном ключе.
    push_ready = bool(settings.pwa_enabled and settings.push_subscribe_enabled and settings.vapid_public_key)
    return {
        "sw_enabled": bool(settings.pwa_enabled),
        "install_prompt_enabled": bool(settings.pwa_enabled and settings.pwa_install_prompt_enabled),
        "push_enabled": push_ready,
        "vapid_public_key": settings.vapid_public_key if push_ready else None,
    }
