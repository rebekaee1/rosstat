"""Google Dataset JSON-LD: description, creator, and the site terms URL."""

import asyncio
import json
import re

from app.services.locale import (
    reset_locale,
    reset_request_origin,
    set_locale,
    set_request_origin,
)
from app.services.seo_renderer import _complete_structured, build_document


def _bind(locale: str, origin: str):
    return set_locale(locale), set_request_origin(origin)


def _unbind(locale_token, origin_token) -> None:
    reset_locale(locale_token)
    reset_request_origin(origin_token)


def test_category_dataset_gains_description_creator_and_terms():
    """Before: category mainEntity Dataset had only name and url."""
    locale_token, origin_token = _bind("ru", "https://ru.forecasteconomy.com")
    try:
        raw = {
            "@context": "https://schema.org",
            "@type": "CollectionPage",
            "name": "Цены и инфляция в России",
            "mainEntity": [
                {
                    "@type": "Dataset",
                    "name": "Индекс потребительских цен",
                    "url": "https://ru.forecasteconomy.com/russia/indicator/cpi",
                    "creator": {"@type": "Organization", "name": "Росстат"},
                }
            ],
        }
        page = _complete_structured(raw)
    finally:
        _unbind(locale_token, origin_token)

    dataset = page["mainEntity"][0]
    assert dataset["@type"] == "Dataset"
    assert dataset["creator"] == {"@type": "Organization", "name": "Росстат"}
    assert dataset["license"] == "https://ru.forecasteconomy.com/terms"
    assert len(dataset["description"]) >= 50
    assert "Индекс потребительских цен" in dataset["description"]
    assert "Росстат" in dataset["description"]
    assert "description" not in raw["mainEntity"][0]
    assert page["name"] == raw["name"]


def test_existing_copy_kept_and_false_cc_license_replaced():
    locale_token, origin_token = _bind("en", "https://forecasteconomy.com")
    try:
        description = (
            "Consumer price index for Russia: monthly change in prices of a "
            "fixed basket of goods and services."
        )
        raw = {
            "@type": "Dataset",
            "name": "Consumer Price Index",
            "description": description,
            "url": "https://forecasteconomy.com/russia/indicator/cpi",
            "creator": {"@type": "Organization", "name": "Rosstat"},
            "license": "https://creativecommons.org/publicdomain/zero/1.0/",
            "isAccessibleForFree": True,
        }
        dataset = _complete_structured(raw)
    finally:
        _unbind(locale_token, origin_token)

    assert dataset["description"] == description
    assert dataset["creator"]["name"] == "Rosstat"
    assert dataset["license"] == "https://forecasteconomy.com/terms"
    assert dataset["isAccessibleForFree"] is True
    assert raw["license"].startswith("https://creativecommons.org/")


def test_missing_creator_defaults_to_forecast_economy():
    locale_token, origin_token = _bind("ru", "https://ru.forecasteconomy.com")
    try:
        dataset = _complete_structured({
            "@type": "Dataset",
            "name": "Сравнение регионов",
            "description": (
                "Сравнение двух регионов России по официальным показателям "
                "Росстата за доступные годы."
            ),
            "url": "https://ru.forecasteconomy.com/russia/region-vs/a-vs-b",
        })
    finally:
        _unbind(locale_token, origin_token)

    assert dataset["creator"] == {"@type": "Organization", "name": "Forecast Economy"}
    assert dataset["license"] == "https://ru.forecasteconomy.com/terms"
    assert dataset["description"].startswith("Сравнение двух регионов")


def test_short_description_is_extended_in_english():
    locale_token, origin_token = _bind("en", "https://forecasteconomy.com")
    try:
        dataset = _complete_structured({
            "@type": "Dataset",
            "name": "CPI",
            "description": "Monthly CPI.",
            "creator": {"@type": "Organization", "name": "Rosstat"},
        })
    finally:
        _unbind(locale_token, origin_token)

    assert dataset["description"].startswith("Monthly CPI.")
    assert "data series on Forecast Economy" in dataset["description"]
    assert len(dataset["description"]) >= 50
    assert len(dataset["description"]) <= 5000


def test_build_document_serializes_completed_dataset():
    locale_token, origin_token = _bind("ru", "https://ru.forecasteconomy.com")
    try:
        html = asyncio.run(build_document(
            title="ИПЦ",
            description="Тест карточки индикатора для проверки разметки набора данных.",
            canonical_path="/russia/indicator/cpi",
            body="<main><h1>ИПЦ</h1></main>",
            json_ld=[{
                "@context": "https://schema.org",
                "@type": "Dataset",
                "name": "Индекс потребительских цен",
                "url": "https://ru.forecasteconomy.com/russia/indicator/cpi",
                "creator": {"@type": "Organization", "name": "Росстат"},
            }],
            include_app=False,
        ))
    finally:
        _unbind(locale_token, origin_token)

    blocks = [
        json.loads(raw)
        for raw in re.findall(
            r'<script type="application/ld\+json">(.*?)</script>', html,
        )
    ]
    dataset = next(block for block in blocks if block.get("@type") == "Dataset")
    assert dataset["license"] == "https://ru.forecasteconomy.com/terms"
    assert dataset["creator"]["name"] == "Росстат"
    assert len(dataset["description"]) >= 50
