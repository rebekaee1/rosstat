"""Сквозной SEO-страж серверных страниц обоих хостов (14.11.2026).

Каждый тип страницы на `forecasteconomy.com` (en) и `ru.forecasteconomy.com` (ru):

* один canonical — абсолютный адрес этой страницы на своём хосте;
* hreflang ru / en / x-default, ru → `ru.`, en и x-default → apex, свой язык совпадает с canonical,
  набор одинаковый на обоих хостах (взаимность);
* meta robots `index, follow`; meta googlebot — только где её ставит ADR-0029 (годовые страницы
  стран мира и их регионов на `ru.`); на apex без опубликованного списка спроса ADR-0031 — нигде;
* JSON-LD разбирается, `@context` — schema.org, типы и свойства — из списка schema.org, которыми
  сайт пользуется (новое поле — сознательное расширение списка, а не опечатка);
* title не повторяется у разных страниц одного хоста.
"""

from __future__ import annotations

import html
import json
import re
from collections import defaultdict

import pytest

from app.config import settings
from tests.test_indicator_year_landing import year_landing_client  # noqa: F401
from tests.test_seo_world_year import CODE_ANNUAL, CODE_MONTHLY, world_year_client  # noqa: F401
from tests.test_world_compare_frequency import frequency_client  # noqa: F401
from tests.test_world_subnational import subnational_client  # noqa: F401

APEX, RU = "forecasteconomy.com", "ru.forecasteconomy.com"
HOSTS = {"en": APEX, "ru": RU}

# fixture → [(тип, путь backend, публичный путь, googlebot на ru.)]
PAGES = {
    "world_year_client": [
        ("world-country", "/seo/world/germany", "/germany", False),
        ("world-card-annual", f"/seo/world/germany/{CODE_ANNUAL}", f"/germany/indicator/{CODE_ANNUAL}", False),
        ("world-card-monthly", f"/seo/world/germany/{CODE_MONTHLY}", f"/germany/indicator/{CODE_MONTHLY}", False),
        ("world-year-annual", f"/seo/world-indicator-year/germany/{CODE_ANNUAL}/2023",
         f"/germany/indicator/{CODE_ANNUAL}/2023", True),
        ("world-year-monthly", f"/seo/world-indicator-year/germany/{CODE_MONTHLY}/2024",
         f"/germany/indicator/{CODE_MONTHLY}/2024", True),
    ],
    "frequency_client": [
        ("world-vs", "/seo/world-vs/germany-vs-japan/hicp-index", "/germany-vs-japan/hicp-index", False),
    ],
    "subnational_client": [
        ("world-regions", "/seo/world/united-states/regions", "/united-states/regions", False),
        ("world-region", "/seo/world/united-states/region/california", "/united-states/region/california", False),
        ("world-region-indicator", "/seo/world/united-states/region/california/unemployment-rate",
         "/united-states/region/california/unemployment-rate", False),
        ("world-region-year", "/seo/world/united-states/region/california/unemployment-rate/2024",
         "/united-states/region/california/unemployment-rate/2024", True),
    ],
    "year_landing_client": [
        ("russia-card", "/seo/indicator/cpi", "/russia/indicator/cpi", False),
        ("russia-year", "/seo/indicator-year/cpi/2024", "/russia/indicator/cpi/2024", False),
        ("russia-year-annual", "/seo/indicator-year/population/2023", "/russia/indicator/population/2023", False),
    ],
}

# Типы и свойства schema.org, которыми пользуется SSR (проверено по schema.org 14.11.2026).
SCHEMA = {
    "WebSite": {"name", "alternateName", "description", "inLanguage", "publisher", "url"},
    "WebPage": {"name", "description", "url", "inLanguage", "isPartOf", "primaryImageOfPage", "dateModified"},
    "Organization": {"name", "url", "logo", "description", "email", "contactPoint"},
    "ContactPoint": {"contactType", "email", "availableLanguage"},
    "BreadcrumbList": {"itemListElement"},
    "ListItem": {"position", "name", "item", "url"},
    "ItemList": {"name", "description", "url", "itemListElement", "itemListOrder", "numberOfItems"},
    "Dataset": {"name", "description", "url", "creator", "dateModified", "distribution", "image",
                "inLanguage", "isAccessibleForFree", "keywords", "spatialCoverage", "temporalCoverage",
                "variableMeasured", "license", "isBasedOn", "measurementTechnique", "publisher"},
    "DataDownload": {"contentUrl", "encodingFormat"},
    "ImageObject": {"contentUrl", "url", "width", "height", "name", "caption", "description",
                    "representativeOfPage", "license", "acquireLicensePage", "creditText",
                    "copyrightNotice", "creator", "author"},
    "Country": {"name", "url"},
    "Place": {"name", "url"},
    "AdministrativeArea": {"name", "url", "containedInPlace"},
    "FAQPage": {"mainEntity"},
    "Question": {"name", "acceptedAnswer"},
    "Answer": {"text"},
    "Person": {"name", "url"},
}


@pytest.fixture
def split_hosts(monkeypatch):
    monkeypatch.setattr(settings, "apex_locale_en", True)
    monkeypatch.setattr(settings, "public_base_url", "https://forecasteconomy.com")


def _walk_ld(node, problems: list[str]) -> None:
    if isinstance(node, list):
        for item in node:
            _walk_ld(item, problems)
        return
    if not isinstance(node, dict):
        return
    kind = node.get("@type")
    if kind is not None:
        kinds = kind if isinstance(kind, list) else [kind]
        for name in kinds:
            allowed = SCHEMA.get(name)
            if allowed is None:
                problems.append(f"тип {name} вне списка")
                continue
            extra = {k for k in node if not k.startswith("@")} - allowed
            if extra:
                problems.append(f"{name}: свойства вне списка {sorted(extra)}")
    for value in node.values():
        _walk_ld(value, problems)


def _audit(client, path: str, public: str, googlebot_on_ru: bool) -> tuple[dict, dict]:
    titles, alternates = {}, {}
    for loc, host in HOSTS.items():
        response = client.get(path, headers={"Host": host, "X-FE-Locale": loc})
        assert response.status_code == 200, (loc, path, response.status_code)
        text = response.text
        canonical = re.findall(r'<link rel="canonical" href="([^"]+)"', text)
        assert canonical == [f"https://{host}{public}"], (loc, path, canonical)
        alts = dict(re.findall(r'<link rel="alternate" hreflang="([^"]+)" href="([^"]+)"', text))
        assert alts == {
            "ru": f"https://{RU}{public}",
            "en": f"https://{APEX}{public}",
            "x-default": f"https://{APEX}{public}",
        }, (loc, path, alts)
        alternates[loc] = alts
        robots = re.findall(r'<meta name="robots" content="([^"]+)"', text)
        assert len(robots) == 1 and robots[0].startswith("index, follow"), (loc, path, robots)
        googlebot = re.findall(r'<meta name="googlebot" content="([^"]+)"', text)
        expected = ["noindex, follow"] if (loc == "ru" and googlebot_on_ru) else []
        assert googlebot == expected, (loc, path, googlebot)
        problems: list[str] = []
        for raw in re.findall(r'<script type="application/ld\+json">(.*?)</script>', text, re.S):
            data = json.loads(raw)
            for item in data if isinstance(data, list) else [data]:
                assert item.get("@context") in ("https://schema.org", "http://schema.org"), (loc, path)
            _walk_ld(data, problems)
        assert not problems, (loc, path, problems)
        titles[loc] = html.unescape(re.search(r"<title>(.*?)</title>", text, re.S).group(1)).strip()
    assert alternates["ru"] == alternates["en"]
    return titles, alternates


@pytest.mark.parametrize("fixture_name", sorted(PAGES))
def test_ssr_pages_pass_seo_audit(fixture_name, request, split_hosts):
    client = request.getfixturevalue(fixture_name)
    seen: dict[tuple[str, str], list[str]] = defaultdict(list)
    for kind, path, public, googlebot_on_ru in PAGES[fixture_name]:
        titles, _alts = _audit(client, path, public, googlebot_on_ru)
        for loc, title in titles.items():
            seen[(loc, title)].append(kind)
    duplicates = {key: kinds for key, kinds in seen.items() if len(kinds) > 1}
    assert not duplicates, duplicates
