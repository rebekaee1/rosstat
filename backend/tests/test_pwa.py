"""PWA: манифест и офлайн-страница (host-aware), публичный конфиг флагов, SSR-head.

Манифест отдаётся каждым origin отдельно: apex = английский (при APEX_LOCALE_EN),
ru. = русский. Service worker статический (frontend/public/sw.js) — его
инварианты проверяются здесь же по тексту, чтобы никто не добавил кэш данных.
"""
import json
import re
from pathlib import Path

import pytest

from app.api.pwa import build_manifest, render_offline
from app.config import settings

ROOT = Path(__file__).resolve().parents[2]
SW = (ROOT / "frontend" / "public" / "sw.js").read_text(encoding="utf-8")


def test_manifest_shape_ru_and_en():
    ru = build_manifest("ru", "https://ru.forecasteconomy.com")
    en = build_manifest("en", "https://forecasteconomy.com")
    for m, lang in ((ru, "ru"), (en, "en")):
        assert m["lang"] == lang
        assert m["display"] == "standalone"
        assert m["start_url"] == "/" and m["scope"] == "/" and m["id"] == "/"
        assert m["name"] == "Forecast Economy"
        assert len(m["short_name"]) <= 12
        assert m["theme_color"] == m["background_color"] == "#EEF0F4"
    assert ru["description"] != en["description"]
    assert ru["shortcuts"][0]["name"] == "Россия" and en["shortcuts"][0]["name"] == "Russia"
    # Каждый origin ссылается на СВОЙ манифест (getInstalledRelatedApps).
    assert ru["related_applications"][0]["url"] == "https://ru.forecasteconomy.com/manifest.webmanifest"
    assert en["related_applications"][0]["url"] == "https://forecasteconomy.com/manifest.webmanifest"
    assert ru["prefer_related_applications"] is False


def test_manifest_icons_exist_and_include_maskable():
    icons = build_manifest("ru", "https://x.test")["icons"]
    purposes = {(i["sizes"], i["purpose"]) for i in icons}
    assert ("192x192", "any") in purposes and ("512x512", "any") in purposes
    assert ("512x512", "maskable") in purposes
    for icon in icons:
        path = ROOT / "frontend" / "public" / icon["src"].lstrip("/")
        assert path.is_file(), icon["src"]
    assert (ROOT / "frontend" / "public" / "apple-touch-icon.png").is_file()


def test_manifest_shortcut_urls_are_local_paths():
    for locale in ("ru", "en"):
        for item in build_manifest(locale, "https://x.test")["shortcuts"]:
            assert item["url"].startswith("/") and not item["url"].startswith("//")


def test_manifest_route_is_host_aware(client, monkeypatch):
    monkeypatch.setattr(settings, "apex_locale_en", True, raising=False)
    ru = client.get("/manifest.webmanifest", headers={"Host": "ru.forecasteconomy.com"})
    en = client.get("/manifest.webmanifest", headers={"Host": "forecasteconomy.com"})
    assert ru.status_code == en.status_code == 200
    assert ru.headers["content-type"].startswith("application/manifest+json")
    assert ru.headers["cache-control"] == "no-cache"
    assert ru.headers["vary"] == "Host"
    assert json.loads(ru.text)["lang"] == "ru"
    assert json.loads(en.text)["lang"] == "en"
    assert json.loads(en.text)["related_applications"][0]["url"].startswith("https://forecasteconomy.com/")


def test_offline_page_is_localized_static_and_data_free(client, monkeypatch):
    monkeypatch.setattr(settings, "apex_locale_en", True, raising=False)
    ru = client.get("/offline.html", headers={"Host": "ru.forecasteconomy.com"})
    en = client.get("/offline.html", headers={"Host": "forecasteconomy.com"})
    assert ru.status_code == en.status_code == 200
    assert "Нет соединения" in ru.text and "No connection" in en.text
    assert "noindex" in ru.headers["x-robots-tag"]
    assert "устаревшие цифры" in ru.text
    # Самодостаточна: ни внешних ссылок, ни запросов к API.
    assert "http" not in render_offline("ru").replace("http-equiv", "")
    assert "/api/" not in render_offline("en")


@pytest.mark.parametrize("pwa,prompt,expect_sw,expect_prompt", [
    (True, True, True, True),
    (True, False, True, False),
    (False, True, False, False),   # kill-switch SW гасит и приглашение
])
def test_config_flags(client, monkeypatch, pwa, prompt, expect_sw, expect_prompt):
    monkeypatch.setattr(settings, "pwa_enabled", pwa)
    monkeypatch.setattr(settings, "pwa_install_prompt_enabled", prompt)
    r = client.get("/api/v1/pwa/config")
    assert r.status_code == 200
    assert r.headers["cache-control"] == "no-store"
    body = r.json()
    assert body["sw_enabled"] is expect_sw and body["install_prompt_enabled"] is expect_prompt
    assert body["push_enabled"] is False and body["vapid_public_key"] is None  # push по умолчанию закрыт


def test_defaults_enable_install_prompt_with_emergency_off():
    # Требование владельца: приглашение включено по умолчанию, выключатель — переменной окружения.
    fields = settings.model_fields
    assert fields["pwa_enabled"].default is True
    assert fields["pwa_install_prompt_enabled"].default is True


def test_ssr_head_declares_manifest_and_ios_meta():
    from app.services import seo_renderer

    fallback = seo_renderer._fallback_assets().head_links
    assert '<link rel="manifest" href="/manifest.webmanifest">' in fallback
    assert 'rel="apple-touch-icon"' in fallback
    assert 'name="apple-mobile-web-app-capable"' in seo_renderer.PWA_HEAD_META
    shell = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert '<link rel="manifest" href="/manifest.webmanifest"' in shell
    assert 'rel="apple-touch-icon"' in shell
    for meta in re.findall(r'<meta name="(apple-mobile-web-app-[a-z-]+|mobile-web-app-capable)"', seo_renderer.PWA_HEAD_META):
        assert f'name="{meta}"' in shell


# ── инварианты service worker (статический файл) ──

def test_sw_never_caches_data_only_offline_page():
    assert "request.mode !== 'navigate'" in SW          # всё, кроме навигации, не перехватывается
    assert "cache.add" in SW and "PRECACHE = [OFFLINE_URL" in SW
    assert "cache.put" not in SW and "cache.addAll" not in SW
    assert "/api/" not in SW.replace("/api/v1/pwa/config", "")  # единственный API-запрос — конфиг kill-switch
    assert "stale-while-revalidate" not in SW.lower()


def test_sw_update_and_kill_switch_contract():
    assert "__SW_VERSION__" in SW                        # токен заменяет Vite на каждой сборке
    assert "skipWaiting" in SW and "clients.claim" in SW
    assert "n.startsWith('fe-') && n !== CACHE" in SW    # чистка старых версий
    assert "sw_enabled === false" in SW and "registration.unregister()" in SW


def test_vite_build_replaces_sw_version_token():
    cfg = (ROOT / "frontend" / "vite.config.js").read_text(encoding="utf-8")
    assert "swVersionPlugin" in cfg and "__SW_VERSION__" in cfg


def test_caddy_csp_allows_service_worker_in_both_blocks():
    caddy = (ROOT / "Caddyfile").read_text(encoding="utf-8")
    csp = [line for line in caddy.splitlines() if "Content-Security-Policy" in line and "default-src" in line]
    assert len(csp) == 2
    for line in csp:
        assert "worker-src 'self'" in line
    general = next(line for line in csp if "child-src" in line)
    assert "child-src 'self'" in general


def test_nginx_has_pwa_locations_with_safe_headers():
    conf = (ROOT / "frontend" / "nginx.conf").read_text(encoding="utf-8")
    sw = re.search(r"location = /sw\.js \{(.*?)\n    \}", conf, re.S).group(1)
    assert "no-cache, no-store, must-revalidate" in sw and "Service-Worker-Allowed" in sw
    for path in ("/manifest.webmanifest", "/offline.html"):
        block = re.search(r"location = %s \{(.*?)\n    \}" % re.escape(path), conf, re.S).group(1)
        assert "proxy_pass http://backend:8000" + path in block
        assert 'Cache-Control "no-cache"' in block
