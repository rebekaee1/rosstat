"""Structured data describes the published page without claiming source rights."""

import asyncio
import json

from bs4 import BeautifulSoup

from app.services.locale import (
    reset_locale,
    reset_request_origin,
    set_locale,
    set_request_origin,
)
from app.services.seo_renderer import (
    AppAssets,
    _breadcrumbs,
    _complete_structured,
    _site_json_ld,
    build_document,
)


def test_nested_dataset_description_preserves_provenance_and_license():
    locale = set_locale("ru")
    origin = set_request_origin("https://ru.forecasteconomy.com")
    try:
        source_license = "https://source.example/terms/data-v1"
        raw = {"@type": "CollectionPage", "mainEntity": [
            {"@type": "Dataset", "name": "ИПЦ", "description": "Цены.",
             "creator": {"@type": "Organization", "name": "Росстат"}},
            {"@type": "Dataset", "name": "Ряд без сведений об авторе",
             "license": source_license},
        ]}
        result = _complete_structured(raw)
    finally:
        reset_request_origin(origin)
        reset_locale(locale)
    first, second = result["mainEntity"]
    assert 50 <= len(first["description"]) <= 5000
    assert "Росстат" in first["description"]
    assert first["creator"]["name"] == "Росстат"
    assert "license" not in first
    assert "creator" not in second
    assert second["license"] == source_license
    assert raw["mainEntity"][0]["description"] == "Цены."


def test_only_generated_charts_get_site_image_rights():
    origin = set_request_origin("https://ru.forecasteconomy.com")
    try:
        chart = _complete_structured({
            "@type": "ImageObject",
            "contentUrl": "https://ru.forecasteconomy.com/og/russia/cpi.png",
        })
        logo = _complete_structured({
            "@type": "ImageObject",
            "contentUrl": "https://ru.forecasteconomy.com/yandex-app-icon-512.png",
        })
        external = _complete_structured({
            "@type": "ImageObject",
            "contentUrl": "https://source.example/og/chart.png",
        })
    finally:
        reset_request_origin(origin)
    assert chart["creator"]["name"] == "Forecast Economy"
    assert chart["license"] == "https://ru.forecasteconomy.com/terms"
    assert chart["acquireLicensePage"] == chart["license"]
    assert chart["copyrightNotice"].endswith("(chart only)")
    assert "license" not in logo
    assert "license" not in external


def test_site_identity_and_root_breadcrumbs():
    locale = set_locale("en")
    origin = set_request_origin("https://forecasteconomy.com")
    try:
        site = _site_json_ld()
        root = _breadcrumbs([("/", "Home")])
        trail = _breadcrumbs([("/", "Home"), ("/germany", "Germany")])
    finally:
        reset_request_origin(origin)
        reset_locale(locale)
    website, organization = site["@graph"]
    assert website["inLanguage"] == "en"
    assert website["publisher"]["@id"] == organization["@id"]
    assert organization["logo"]["contentUrl"].endswith("/yandex-app-icon-512.png")
    assert organization["contactPoint"]["email"] == organization["email"]
    assert root is None
    assert len(trail["itemListElement"]) == 2
    assert all(item["item"] == item["url"] for item in trail["itemListElement"])


def test_document_serializes_nested_dataset_without_site_license(monkeypatch):
    async def assets():
        return AppAssets("", "")

    monkeypatch.setattr("app.services.seo_renderer.get_app_assets", assets)
    origin = set_request_origin("https://ru.forecasteconomy.com")
    try:
        html = asyncio.run(build_document(
            title="Категория", description="Официальная статистика",
            canonical_path="/russia/category/prices", body="<main>Цены</main>",
            json_ld=[None, {"@context": "https://schema.org", "@type": "CollectionPage",
                            "mainEntity": [{"@type": "Dataset", "name": "ИПЦ",
                                            "creator": {"@type": "Organization", "name": "Росстат"}}]}],
            include_app=False,
        ))
    finally:
        reset_request_origin(origin)
    blocks = [json.loads(tag.string) for tag in BeautifulSoup(html, "html.parser").select(
        'script[type="application/ld+json"]')]
    dataset = blocks[0]["mainEntity"][0]
    assert 50 <= len(dataset["description"]) <= 5000
    assert dataset["creator"]["name"] == "Росстат"
    assert "license" not in dataset


def test_document_licenses_generated_image_but_not_its_dataset(monkeypatch):
    async def assets():
        return AppAssets("", "")

    monkeypatch.setattr("app.services.seo_renderer.get_app_assets", assets)
    origin = set_request_origin("https://ru.forecasteconomy.com")
    try:
        chart_url = "https://ru.forecasteconomy.com/og/russia/cpi.png"
        html = asyncio.run(build_document(
            title="ИПЦ", description="Индекс потребительских цен",
            canonical_path="/russia/indicator/cpi", body="<main>ИПЦ</main>",
            json_ld=[
                {"@type": "Dataset", "name": "ИПЦ", "creator": {
                    "@type": "Organization", "name": "Росстат"}},
                {"@type": "ImageObject", "contentUrl": chart_url},
            ],
            og_image=chart_url, include_app=False,
        ))
    finally:
        reset_request_origin(origin)
    blocks = [json.loads(tag.string) for tag in BeautifulSoup(html, "html.parser").select(
        'script[type="application/ld+json"]')]
    dataset, image, webpage = blocks
    assert "license" not in dataset
    assert image["license"] == "https://ru.forecasteconomy.com/terms"
    assert webpage["primaryImageOfPage"]["license"] == image["license"]
