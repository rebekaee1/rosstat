"""ИИ и цитаты (совет 19.11.2026, раздел 7): строка «Как цитировать», без DataDownload на закрытый /api/."""
from __future__ import annotations

import asyncio
from datetime import date

from app.services.seo_cite import cite_html, cite_text
from app.services.seo_renderer import render_indicator_html, render_indicator_year_html
from tests.test_indicator_year_landing import year_landing_client  # noqa: F401 — фикстура посева


def test_cite_text_ru_and_en():
    assert cite_text(name="Дизельное топливо", source="Росстат", url="https://ru.forecasteconomy.com/russia/indicator/fuel-diesel",
                     as_of=date(2026, 11, 9), locale="ru") == (
        "Forecast Economy. Дизельное топливо: источник данных — Росстат, на 9 ноября 2026. "
        "https://ru.forecasteconomy.com/russia/indicator/fuel-diesel")
    assert cite_text(name="X", source=None, url="https://a/b", as_of=None, locale="ru") == "Forecast Economy. X. https://a/b"
    html = cite_html(name="A <b>", source="Росстат", url="https://a/b", as_of=None, locale="ru")
    assert html.startswith('<p class="seo-cite"><span class="seo-cite__label">Как цитировать:</span>')
    assert "&lt;b&gt;" in html


def test_year_page_has_cite_line(year_landing_client, auth_env):  # noqa: F811
    async def _render():
        async with auth_env["session_maker"]() as db:
            return await render_indicator_year_html("population", 2025, db)

    status, html = asyncio.run(_render())
    assert status == 200
    assert 'class="seo-cite"' in html
    assert "Как цитировать:" in html
    assert "источник данных — Росстат, на 1 января 2025." in html
    assert "/russia/indicator/population/2025" in html.split('class="seo-cite"', 1)[1].split("</p>", 1)[0]


def test_card_has_cite_and_no_closed_api_download(year_landing_client, auth_env):  # noqa: F811
    async def _render():
        async with auth_env["session_maker"]() as db:
            return await render_indicator_html("population", db)

    status, html = asyncio.run(_render())
    assert status == 200
    assert "Как цитировать:" in html
    assert "DataDownload" not in html
    assert "/api/v1/indicators/" not in html
    assert '"@type": "Dataset"' in html or '"@type":"Dataset"' in html
