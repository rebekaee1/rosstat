"""Age composition must use a complete year and agree across API/SSR/PNG."""
import asyncio
from datetime import date
from io import BytesIO
import json

from bs4 import BeautifulSoup
from PIL import Image
import pytest

from app.models import Indicator, IndicatorData
from app.services.demographics import AGE_GROUP_CODES, complete_snapshot


def test_complete_snapshot_does_not_turn_missing_into_zero():
    data = {"meta": {code: {"unit": "млн чел."} for code in AGE_GROUP_CODES},
            "series": [{"year": 2023, **dict(zip(AGE_GROUP_CODES, [20., 80., 30.]))},
                       {"year": 2024, AGE_GROUP_CODES[0]: 21.}]}
    assert complete_snapshot(data)["year"] == 2023
    assert complete_snapshot(data, 2024) is None
    data["meta"][AGE_GROUP_CODES[1]]["unit"] = "человек"
    assert complete_snapshot(data) is None


def test_demographics_ssr_and_portrait_use_complete_observations(auth_env, auth_client):
    async def seed():
        async with auth_env["session_maker"]() as db:
            for code, value in zip(AGE_GROUP_CODES, [27.16, 83.44, 35.85]):
                indicator = Indicator(code=code, name=code, name_en=code, unit="млн чел.",
                                      frequency="annual", is_active=True, is_listed=True,
                                      source="Росстат", source_url="https://rosstat.gov.ru/")
                db.add(indicator)
                await db.flush()
                db.add(IndicatorData(indicator_id=indicator.id, date=date(2023, 1, 1), value=value))
                if code == AGE_GROUP_CODES[0]:
                    db.add(IndicatorData(indicator_id=indicator.id, date=date(2024, 1, 1), value=99.))
            await db.commit()
    asyncio.run(seed())
    response = auth_client.get("/seo/page/demographics")
    assert response.status_code == 200
    soup = BeautifulSoup(response.text, "html.parser")
    assert soup.select_one('meta[property="og:image"]')["content"].endswith('/og/russia/demographics.png')
    assert soup.select_one('picture source')["srcset"] == '/og/russia/demographics.png?portrait=1'
    datasets = [json.loads(s.string) for s in soup.select('script[type="application/ld+json"]')]
    dataset = next(d for d in datasets if d.get('@type') == 'Dataset')
    assert dataset['temporalCoverage'] == '2023'
    assert [p['value'] for p in dataset['variableMeasured']] == [27.16, 83.44, 35.85]
    assert dataset['isBasedOn'] == ['https://rosstat.gov.ru/']
    for suffix, size in [('', (1200, 630)), ('?portrait=1', (1080, 1350))]:
        image = auth_client.get('/api/v1/og-image/demographics.png' + suffix)
        assert image.status_code == 200
        assert Image.open(BytesIO(image.content)).size == size


def test_empty_demographic_image_is_404(auth_client):
    assert auth_client.get('/api/v1/og-image/demographics.png').status_code == 404
