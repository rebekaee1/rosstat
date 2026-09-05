"""Анти-скрейп: привязка сессии к IP-префиксу + опциональный гео-блок.

Ферма 2026-09-03/04: headless Chrome, ротация IP на каждый запрос
(SG → PL → CN/FR/BR). Гео-блок ловил только перечисленные страны — гидра
уходила в другие. Bind ломает кросс-IP сессию: кука HMAC(prefix, день)
с HTML/API не подходит запросу с другого /24 (IPv6 /48).

Правила bind:
- поисковики и соцкраулеры по UA не режутся;
- приватный/невалидный IP (тесты, localhost) — skip;
- куки нет — HTML: JS-ворота; API: 403;
- кука от другого префикса — API 403, HTML снова ворота
  (не пустой 403: живой человек после смены соты/VPN должен пройти);
- ``location.reload()`` после ворот, не ``replace``: иначе Метрика
  видит внутренний переход и теряет organic/search;
- пустой ``RUSTATS_SCRAPE_BLOCK_COUNTRIES`` выключает гео-слой;
- хостинговые ASN (Hetzner/OVH/Alibaba/AWS/…) режутся флагом
  ``RUSTATS_SCRAPE_BLOCK_HOSTING`` (по умолчанию вкл); жилые прокси
  этим слоем не покрыты;
- ``Chrome/N.0.0.0 Safari/537.36`` — это reduced UA живого Chrome
  (с 101), его нельзя банить: ферма шлёт ту же строку;
- гидра 1 IP = 1 хит: бан по IP и «второй запрос» бесполезны. HTML без
  ``fe_bind`` — заглушка, кука после JS (ядра / WebGL / webdriver).
  Поисковики по UA сразу получают SSR. Ферма 2026-09-04 светит 64–192
  ядра — живой ноутбук так не врёт.
"""
from __future__ import annotations

import hashlib
import hmac
import ipaddress
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from starlette.responses import Response

from app.config import settings
from app.services.geoip import lookup as geo_lookup
from app.services.geoip import lookup_asn

# Совпадает с nginx $ssr_limit_key плюс соцкраулеры OG и соседние Google/Amazon.
_SEARCH_UA_RE = re.compile(
    r"yandex|googlebot|googleother|google-inspectiontool|adsbot-google|"
    r"bingbot|mail\.ru|duckduckbot|applebot|gptbot|"
    r"petalbot|amazonbot|amzn-searchbot|claudebot|perplexitybot|youbot|"
    r"meta-externalagent|facebookexternalhit|twitterbot|telegrambot|"
    r"slackbot|linkedinbot|whatsapp|discordbot|vkshare",
    re.IGNORECASE,
)

# Cursor-вкладка и headless-ферма не должны писать behavior/events.
_NOISE_UA_RE = re.compile(r"HeadlessChrome|Cursor/", re.IGNORECASE)

# Хостинг / облако: бан сетей, не стран. 15169 Google и 13238 Яндекс
# сюда не входят — поисковики и так пропускаются по UA.
_HOSTING_ASN = frozenset({
    16509, 14618, 7224,  # Amazon
    396982,  # Google Cloud
    8075,  # Microsoft
    14061,  # DigitalOcean
    16276, 35540,  # OVH
    24940, 213230,  # Hetzner
    20473,  # Choopa / Vultr
    63949,  # Linode / Akamai Connected Cloud
    45102, 37963, 55990,  # Alibaba
    132203, 45090,  # Tencent
    31898,  # Oracle
    51167,  # Contabo
    60068, 212238,  # Datacamp
    9009,  # M247
    12876,  # Scaleway
    36352,  # ColoCrossing
    40676,  # Psychz
    53667,  # FranTech
    8100,  # QuadraNet
    28753, 30633, 60781,  # Leaseweb
    8560,  # IONOS
    47583,  # Hostinger
    202053,  # UpCloud
    199524,  # Gcore
    54825,  # Equinix Metal
})

_HOSTING_ORG_RE = re.compile(
    r"hetzner|ovhcloud|\bovh\b|digitalocean|linode|vultr|contabo|"
    r"leaseweb|\bm247\b|datacamp|choopa|alibaba|alicloud|tencent|"
    r"scaleway|colocrossing|psychz|frantech|quadranet|"
    r"amazon-0[2-3]|amazon-aes|amazonaws|amazon\.com|"
    r"google.?cloud|\bgcp\b|microsoft.?azure|\bazure\b|"
    r"oracle.?cloud|oracle.?bmc|huawei.?cloud|"
    r"akamai.?connected|hostinger|\bionos\b|upcloud|\bgcore\b",
    re.IGNORECASE,
)


def is_hosting_network(asn: int | None, org: str | None) -> bool:
    if isinstance(asn, int) and asn in _HOSTING_ASN:
        return True
    if org and _HOSTING_ORG_RE.search(org):
        return True
    return False

_SKIP_PREFIXES = (
    "/api/v1/health",
    "/metrics",
    "/api/docs",
    "/api/redoc",
    "/api/openapi.json",
)

# HTML-заглушка и публичные эмбеды не требуют прошедший challenge.
_CHALLENGE_EXEMPT_PREFIXES = _SKIP_PREFIXES + (
    "/api/v1/scrape-challenge",
    "/api/v1/embed",
    "/embed",
    "/og/",
    "/assets/",
    "/fonts/",
    "/favicon",
    "/robots.txt",
    "/sitemap",
    "/consent.js",
    "/llms.txt",
    "/feed",
)

# Ферма 2026-09-04: 64–192 ядра. 16c/32t Ryzen репортит 32 — ниже порога.
_HEADLESS_GL_RE = re.compile(
    r"swiftshader|llvmpipe|virtualbox|vmware|microsoft basic render",
    re.IGNORECASE,
)

COOKIE_NAME = "fe_bind"
_COOKIE_MAX_AGE = 86_400
_HMAC_HEX_LEN = 16


def blocked_country_codes() -> frozenset[str]:
    raw = (settings.scrape_block_countries or "").strip()
    if not raw:
        return frozenset()
    return frozenset(part.strip().upper() for part in raw.split(",") if part.strip())


def is_search_bot_ua(ua: str | None) -> bool:
    return bool(ua and _SEARCH_UA_RE.search(ua))


def is_noise_client_ua(ua: str | None) -> bool:
    return bool(ua and _NOISE_UA_RE.search(ua))


def ip_network_prefix(ip: str) -> str | None:
    """IPv4 /24, IPv6 /48. None — не глобальный адрес (localhost, тесты)."""
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return None
    if not addr.is_global:
        return None
    if isinstance(addr, ipaddress.IPv4Address):
        net = ipaddress.ip_network(f"{addr}/24", strict=False)
        return str(net.network_address)
    net = ipaddress.ip_network(f"{addr}/48", strict=False)
    return str(net.network_address)


def _secret_bytes() -> bytes:
    raw = (settings.scrape_bind_secret or "").strip()
    if raw:
        return raw.encode("utf-8")
    return f"{settings.public_base_url}|fe_bind_v1".encode("utf-8")


def _ymd_utc(when: datetime | None = None) -> str:
    now = when or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return now.astimezone(timezone.utc).strftime("%Y%m%d")


def issue_token(ip: str, when: datetime | None = None) -> str | None:
    prefix = ip_network_prefix(ip)
    if prefix is None:
        return None
    ymd = _ymd_utc(when)
    digest = hmac.new(
        _secret_bytes(), f"{prefix}|{ymd}".encode("utf-8"), hashlib.sha256
    ).hexdigest()[:_HMAC_HEX_LEN]
    return f"{ymd}.{digest}"


def verify_token(token: str | None, ip: str, when: datetime | None = None) -> bool:
    if not token or "." not in token:
        return False
    prefix = ip_network_prefix(ip)
    if prefix is None:
        return False
    ymd, _, digest = token.partition(".")
    if len(ymd) != 8 or len(digest) != _HMAC_HEX_LEN:
        return False
    now = when or datetime.now(timezone.utc)
    allowed = {_ymd_utc(now), _ymd_utc(now - timedelta(days=1))}
    if ymd not in allowed:
        return False
    expected = hmac.new(
        _secret_bytes(), f"{prefix}|{ymd}".encode("utf-8"), hashlib.sha256
    ).hexdigest()[:_HMAC_HEX_LEN]
    return hmac.compare_digest(digest, expected)


def should_block(*, ip: str, ua: str | None, path: str) -> str | None:
    """Причина блока: HOSTING / ISO-страна, или None."""
    path = path or "/"
    if any(path.startswith(p) for p in _SKIP_PREFIXES):
        return None
    if is_search_bot_ua(ua):
        return None
    if settings.scrape_block_hosting:
        info = lookup_asn(ip)
        asn = info.get("asn")
        org = info.get("org")
        if is_hosting_network(
            asn if isinstance(asn, int) else None,
            org if isinstance(org, str) else None,
        ):
            return "HOSTING"
    codes = blocked_country_codes()
    if not codes:
        return None
    geo = geo_lookup(ip)
    cc = (geo.get("country_code") or "").upper()
    if cc and cc in codes:
        return cc
    return None


def is_bind_protected_path(path: str) -> bool:
    """HTML и API, кроме health/metrics/docs. Чужая кука не перевыпускается."""
    path = path or "/"
    return not any(path.startswith(p) for p in _SKIP_PREFIXES)


def is_challenge_exempt_path(path: str) -> bool:
    path = path or "/"
    return any(path.startswith(p) for p in _CHALLENGE_EXEMPT_PREFIXES)


def _ua_family(ua: str | None) -> str | None:
    text = ua or ""
    if re.search(r"Macintosh|Mac OS X|iPhone|iPad", text, re.I):
        return "mac"
    if re.search(r"Windows", text, re.I):
        return "win"
    if re.search(r"Android", text, re.I):
        return "android"
    if re.search(r"Linux|X11", text, re.I):
        return "linux"
    return None


def _plat_family(plat: str | None) -> str | None:
    text = (plat or "").lower()
    if not text:
        return None
    if "mac" in text or text in {"iphone", "ipad"}:
        return "mac"
    if "win" in text:
        return "win"
    if "linux" in text or "x11" in text:
        return "linux"
    if "android" in text:
        return "android"
    return None


def automation_reason(payload: dict, ua: str | None) -> str | None:
    """Почему JS-ворота не пропускают. None — человек."""
    if payload.get("wd") in (1, True, "1"):
        return "WEBDRIVER"
    try:
        cores = int(payload.get("hc") or 0)
    except (TypeError, ValueError):
        cores = 0
    limit = int(getattr(settings, "scrape_challenge_min_cores", 48) or 48)
    if cores >= limit:
        return "CORES"
    gl = str(payload.get("webgl") or "")
    if gl and _HEADLESS_GL_RE.search(gl):
        return "WEBGL"
    ua_os = _ua_family(ua)
    plat_os = _plat_family(str(payload.get("plat") or ""))
    if ua_os and plat_os and ua_os != plat_os:
        return "PLATFORM"
    return None


CHALLENGE_HTML = """<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="robots" content="noindex">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Forecast Economy</title>
<style>
html,body{margin:0;height:100%;background:#0e1116;color:#c8c2b4;font:14px/1.4 system-ui,sans-serif}
body{display:flex;align-items:center;justify-content:center}
</style>
</head>
<body>
<script>
(function(){
  var gl='';
  try{
    var c=document.createElement('canvas');
    var g=c.getContext('webgl');
    if(g){
      var x=g.getExtension('WEBGL_debug_renderer_info');
      gl=x?String(g.getParameter(x.UNMASKED_RENDERER_WEBGL)||''):'';
    }
  }catch(e){}
  var tz='';
  try{tz=Intl.DateTimeFormat().resolvedOptions().timeZone||'';}catch(e){}
  fetch('/api/v1/scrape-challenge',{
    method:'POST',
    credentials:'same-origin',
    headers:{'content-type':'application/json'},
    body:JSON.stringify({
      hc:navigator.hardwareConcurrency||0,
      dm:navigator.deviceMemory||0,
      tz:tz,
      lang:navigator.language||'',
      plat:navigator.platform||'',
      webgl:gl.slice(0,120),
      wd:navigator.webdriver?1:0
    })
  }).then(function(r){
    if(!r.ok) return;
    try {
      var ref = document.referrer || '';
      if (ref) {
        var rh = new URL(ref).hostname.replace(/^www\\./,'');
        var host = (location.hostname || '').replace(/^www\\./,'');
        var apex = host.replace(/^ru\\./,'');
        if (rh && rh !== host && rh !== apex && rh !== 'ru.' + apex) {
          var u = new URL(location.href);
          if (!u.searchParams.get('utm_referrer')) {
            u.searchParams.set('utm_referrer', ref.slice(0, 2000));
            history.replaceState(null, '', u.pathname + u.search + u.hash);
          }
        }
      }
    } catch (e) {}
    location.reload();
  }).catch(function(){});
})();
</script>
</body>
</html>
"""


@dataclass(frozen=True)
class BindDecision:
    block: bool
    set_cookie: bool
    challenge: bool = False


def bind_decision(
    *, ip: str, ua: str | None, path: str, cookie: str | None
) -> BindDecision:
    if not settings.scrape_bind_enabled:
        return BindDecision(block=False, set_cookie=False)
    if is_search_bot_ua(ua):
        return BindDecision(block=False, set_cookie=False)
    if not is_bind_protected_path(path):
        return BindDecision(block=False, set_cookie=False)
    if path.startswith("/api/v1/scrape-challenge"):
        return BindDecision(block=False, set_cookie=False)
    if ip_network_prefix(ip) is None:
        return BindDecision(block=False, set_cookie=False)
    if not cookie:
        if settings.scrape_challenge_enabled and not is_challenge_exempt_path(path):
            if path.startswith("/api/"):
                return BindDecision(block=True, set_cookie=False)
            return BindDecision(block=False, set_cookie=False, challenge=True)
        return BindDecision(block=False, set_cookie=True)
    if verify_token(cookie, ip):
        return BindDecision(block=False, set_cookie=True)
    # Чужой /24: API режем (ферма крутит IP), HTML — снова ворота.
    # Иначе живой человек после смены соты/VPN получает пустой 403,
    # а location.replace на заглушке превращал Яндекс во «внутренний переход».
    if settings.scrape_challenge_enabled and not is_challenge_exempt_path(path):
        if path.startswith("/api/"):
            return BindDecision(block=True, set_cookie=False)
        return BindDecision(block=False, set_cookie=False, challenge=True)
    return BindDecision(block=True, set_cookie=False)


def attach_bind_cookie(response: Response, ip: str) -> None:
    token = issue_token(ip)
    if not token:
        return
    from app.security.auth import effective_auth_cookie_domain

    kw: dict = {
        "httponly": True,
        "secure": settings.auth_cookie_secure,
        "samesite": "lax",
        "path": "/",
        "max_age": _COOKIE_MAX_AGE,
    }
    domain = effective_auth_cookie_domain()
    if domain:
        kw["domain"] = domain
    response.set_cookie(COOKIE_NAME, token, **kw)
