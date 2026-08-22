"""Т-2: SSR-контракт-матрица по всем семействам страниц.

Реальные рендеры (без моков renderer'а) на посевных данных из route_client
(см. test_route_smoke.py): проверяем инварианты, слом которых = тихая
просадка SEO, которую не видно глазами:
- canonical указывает на прод-домен и правильный путь;
- JSON-LD присутствует и парсится;
- og:image объявлен;
- для карточки индикатора есть ВИДИМЫЙ <img> с графиком (Алиса/Нейро берут
  картинку из DOM, не из меты — AGENTS.md);
- кириллический title без плейсхолдеров.
"""

import json
import re

import pytest

from tests.test_route_smoke import route_client  # noqa: F401 — общий посев

DOMAIN = "https://forecasteconomy.com"


def _get(route_client, path):
    r = route_client.get(path)
    assert r.status_code == 200, f"{path} -> {r.status_code}"
    return r.text


def _canonical(html: str) -> str | None:
    m = re.search(r'<link rel="canonical" href="([^"]+)"', html)
    return m.group(1) if m else None


def _jsonld_blocks(html: str) -> list[dict]:
    out = []
    for m in re.finditer(
        r'<script type="application/ld\+json">(.*?)</script>', html, re.S
    ):
        out.append(json.loads(m.group(1)))
    return out


MATRIX = [
    # (путь SSR, ожидаемый canonical-путь; для главной canonical — домен без слэша)
    ("/seo/page/home", ""),
    ("/seo/category/prices", "/russia/category/prices"),
    ("/seo/indicator/cpi", "/russia/indicator/cpi"),
    ("/seo/regions", "/russia/region"),
    ("/seo/regions/map/naselenie", "/russia/region/map/naselenie"),
    ("/seo/region/moskva", "/russia/region/moskva"),
    ("/seo/region/moskva/naselenie", "/russia/region/moskva/naselenie"),
    ("/seo/region-rating/naselenie", "/russia/region-rating/naselenie"),
    ("/seo/region-vs/moskva-vs-tulskaya-oblast", "/russia/region-vs/moskva-vs-tulskaya-oblast"),
]


@pytest.mark.parametrize("path,canonical_path", MATRIX)
def test_ssr_page_contract(route_client, path, canonical_path):
    html = _get(route_client, path)

    canonical = _canonical(html)
    assert canonical == f"{DOMAIN}{canonical_path}", (
        f"canonical {canonical!r} != {DOMAIN}{canonical_path}"
    )

    blocks = _jsonld_blocks(html)
    assert blocks, f"{path}: нет JSON-LD"

    assert 'property="og:image"' in html, f"{path}: нет og:image"

    m = re.search(r"<title>([^<]+)</title>", html)
    assert m and len(m.group(1)) > 10
    assert "{" not in m.group(1) and "None" not in m.group(1)


def test_ssr_indicator_visible_chart_img(route_client):
    html = _get(route_client, "/seo/indicator/cpi")
    # Видимый график в DOM — ключ к картинке в Алисе/Нейро.
    assert re.search(r'<img[^>]+src="[^"]*/og/russia/cpi\.png"', html), "нет видимого <img> графика"
    assert 'href="/russia/indicator/cpi#chart"' in html
    assert 'https://forecasteconomy.com/og/' not in html.split("<figure")[1].split("</figure>")[0]
    # ImageObject в JSON-LD.
    assert any(
        "ImageObject" in json.dumps(b) for b in _jsonld_blocks(html)
    ), "нет schema.org/ImageObject"


def test_ssr_indicator_404_for_unknown(route_client):
    assert route_client.get("/seo/indicator/no-such-code").status_code == 404
    assert route_client.get("/seo/region/no-such-region").status_code == 404


def test_ssr_indicator_year_page(route_client):
    r = route_client.get("/seo/indicator-year/cpi/2025")
    assert r.status_code == 200
    html = r.text
    assert _canonical(html) == f"{DOMAIN}/russia/indicator/cpi/2025"
    assert "2025" in html


def test_ssr_today_page(route_client):
    html = _get(route_client, "/seo/today")
    assert _canonical(html) == f"{DOMAIN}/russia/today"
