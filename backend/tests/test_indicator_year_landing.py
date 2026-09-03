"""Годовые landing `/indicator/{code}/{year}`: порог 1 точка + согласованность sitemap.

Регрессии:
- годовой ряд с одной точкой за год отдавал 404 (упущено ~537 URL);
- sitemap и SSR расходились по порогу числа точек;
- OG mode-sibling (`usd-index-yoy`) на карточке `?mode=yoy`.
"""

from __future__ import annotations

import asyncio
import re
from datetime import date

import pytest

from app.models import Indicator, IndicatorData
from app.services.seo_renderer import (
    neighbor_year_window,
    render_indicator_year_html,
    year_change_lines,
    year_history_position_lines,
)
from app.services.site_urls import YEAR_LANDING_MIN_POINTS, _year_urls


@pytest.fixture
def year_landing_client(auth_env):
    """Посев: годовой ряд (1 точка/год) + месячный (несколько точек) + пустой год."""

    async def _seed():
        async with auth_env["session_maker"]() as db:
            population = Indicator(
                code="population",
                name="Численность населения",
                unit="млн чел.",
                frequency="annual",
                category="Демография",
                source="Росстат",
                is_active=True,
                is_listed=True,
            )
            cpi = Indicator(
                code="cpi",
                name="Индекс потребительских цен",
                unit="%",
                frequency="monthly",
                category="Цены",
                source="Росстат",
                is_active=True,
                is_listed=True,
            )
            usd = Indicator(
                code="usd-index",
                name="Индекс доллара США",
                unit="пунктов",
                frequency="daily",
                category="Индексы",
                source="ФРС",
                is_active=True,
                is_listed=True,
            )
            usd_yoy = Indicator(
                code="usd-index-yoy",
                name="Индекс доллара США (г/г)",
                unit="%",
                frequency="monthly",
                category="Индексы",
                source="ФРС",
                is_active=True,
                is_listed=False,
            )
            db.add_all([population, cpi, usd, usd_yoy])
            await db.flush()

            for y, v in (
                (2016, 146.5),
                (2017, 146.8),
                (2018, 146.9),
                (2019, 146.8),
                (2020, 146.7),
                (2021, 146.2),
                (2022, 147.0),
                (2023, 146.4),
                (2024, 146.15),
                (2025, 146.12),
            ):
                db.add(IndicatorData(
                    indicator_id=population.id, date=date(y, 1, 1), value=v,
                ))

            for m in range(1, 7):
                db.add(IndicatorData(
                    indicator_id=cpi.id,
                    date=date(2024, m, 1),
                    value=100.0 + m * 0.1,
                ))
            # Один месяц 2025 — раньше такие годы отсекались порогом ≥2.
            db.add(IndicatorData(
                indicator_id=cpi.id, date=date(2025, 1, 1), value=100.5,
            ))

            db.add(IndicatorData(
                indicator_id=usd.id, date=date(2024, 6, 1), value=104.0,
            ))
            db.add(IndicatorData(
                indicator_id=usd.id, date=date(2024, 7, 1), value=105.0,
            ))
            db.add(IndicatorData(
                indicator_id=usd_yoy.id, date=date(2024, 7, 1), value=-1.2,
            ))
            await db.commit()

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_seed())
    finally:
        loop.close()

    from fastapi.testclient import TestClient

    with TestClient(auth_env["app"]) as tc:
        yield tc


def test_year_landing_min_points_is_six():
    assert YEAR_LANDING_MIN_POINTS == 6


def test_year_change_and_history_copy():
    lines = year_change_lines(
        year=2025,
        value=146.12,
        prev_value=146.15,
        prev_year=2024,
        code="population",
        unit="млн чел.",
    )
    assert lines[0].startswith("Значение:")
    assert "2024" in lines[1]
    assert "%" in lines[1]

    series = [
        (y, float(v), date(y, 1, 1))
        for y, v in (
            (2020, 100.0),
            (2021, 110.0),
            (2022, 120.0),
            (2023, 115.0),
            (2024, 118.0),
            (2025, 119.0),
        )
    ]
    hist = year_history_position_lines(
        year=2025, value=119.0, series=series, code="x", unit="ед.",
    )
    assert any("среднего" in line for line in hist)
    assert any("Максимум" in line or "максимум" in line for line in hist)


def test_neighbor_year_window_centers():
    series = [(y, float(y), date(y, 1, 1)) for y in range(2000, 2030)]
    window = neighbor_year_window(series, 2015, size=10)
    years = [y for y, _v, _d in window]
    assert len(years) == 10
    assert 2015 in years
    assert years[0] <= 2015 <= years[-1]


def test_single_point_annual_year_page(year_landing_client, auth_env):
    async def _render():
        async with auth_env["session_maker"]() as db:
            return await render_indicator_year_html("population", 2025, db)

    status, html = asyncio.run(_render())
    assert status == 200
    assert "<title>Численность населения в 2025 году — значение и динамика" in html
    assert "Сравнение с прошлым годом" in html
    assert "Динамика соседних лет" in html
    assert "<strong>2025</strong>" in html
    assert "Изменение к 2024 году" in html
    assert "Положение в истории" in html
    assert 'property="og:image" content="https://forecasteconomy.com/og/russia/population/2025.png"' in html
    assert '"@type": "Dataset"' in html or '"@type":"Dataset"' in html
    assert "temporalCoverage" in html
    assert "/russia/indicator/population" in html
    assert "Другие годы" in html
    # Не «данные по месяцам» для годового ряда.
    assert "данные по месяцам" not in html


def test_sitemap_years_match_ssr_200(year_landing_client, auth_env):
    """В sitemap years попадает ровно то, что render отдаёт 200."""

    async def _check():
        async with auth_env["session_maker"]() as db:
            urls = await _year_urls(db, date(2026, 8, 16))
            paths = {u.path for u in urls}
            # Годовой ряд: одна точка за год = полная страница, в sitemap.
            assert "/russia/indicator/population/2025" in paths
            assert "/russia/indicator/population/2016" in paths
            # Месячный 2024: 6 точек — порог INDEX_POLICY.
            assert "/russia/indicator/cpi/2024" in paths
            # Месячный 2025: одна точка — живая страница, не в sitemap.
            assert "/russia/indicator/cpi/2025" not in paths
            assert "/russia/indicator/population/2010" not in paths

            for path in sorted(paths):
                m = re.fullmatch(r"/russia/indicator/([a-z0-9-]+)/(\d{4})", path)
                assert m, path
                code, year = m.group(1), int(m.group(2))
                status, _html = await render_indicator_year_html(code, year, db)
                assert status == 200, f"{path} in sitemap but SSR={status}"

            # Обратно: известный 200 не забыт в sitemap (listed only).
            st, _ = await render_indicator_year_html("population", 2025, db)
            assert st == 200
            assert "/russia/indicator/population/2025" in paths

            # Пустой год — 404 и не в sitemap.
            st404, _ = await render_indicator_year_html("population", 2010, db)
            assert st404 == 404
            assert "/russia/indicator/population/2010" not in paths

    asyncio.run(_check())


def test_mode_og_uses_base_card_code(year_landing_client, auth_env):
    """Карточка ?mode=yoy запрашивает /og/russia/{base}.png, не sibling."""
    from app.services.seo_renderer import render_indicator_html

    async def _render():
        async with auth_env["session_maker"]() as db:
            return await render_indicator_html("usd-index", db, mode="yoy")

    status, html = asyncio.run(_render())
    assert status == 200
    assert "/og/russia/usd-index.png" in html
    assert "/og/usd-index-yoy.png" not in html
    assert "/og/russia/usd-index-yoy.png" not in html


def test_year_og_single_point_returns_png(year_landing_client):
    r = year_landing_client.get("/api/v1/og-image/indicator/population/2025.png")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/png")
    assert len(r.content) > 1000
