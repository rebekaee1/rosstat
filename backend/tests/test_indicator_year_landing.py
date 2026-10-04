"""Годовые landing `/indicator/{code}/{year}`: порог 1 точка + согласованность sitemap.

Регрессии:
- годовой ряд с одной точкой за год отдавал 404 (упущено ~537 URL);
- sitemap и SSR расходились по порогу числа точек;
- OG mode-sibling (`usd-index-yoy`) на карточке `?mode=yoy`.
"""

from __future__ import annotations

import asyncio
import json
import re
from datetime import date
from urllib.parse import parse_qs, urlsplit

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


def test_year_landing_min_points_matches_live_ssr():
    assert YEAR_LANDING_MIN_POINTS == 1


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
            # Месячный год с данными существует в SSR и включается в sitemap.
            assert "/russia/indicator/cpi/2024" in paths
            # Месячный 2025: одна точка — тоже живая индексируемая страница.
            assert "/russia/indicator/cpi/2025" in paths
            assert "/russia/indicator/population/2010" not in paths

            for path in sorted(paths):
                parsed = urlsplit(path)
                m = re.fullmatch(r"/russia/indicator/([a-z0-9-]+)/(\d{4})", parsed.path)
                assert m, path
                code, year = m.group(1), int(m.group(2))
                mode = parse_qs(parsed.query).get("mode", [None])[0]
                status, _html = await render_indicator_year_html(code, year, db, mode=mode)
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


def test_main_card_omits_year_links_and_year_lookup(year_landing_client, auth_env, monkeypatch):
    from app.services import seo_renderer

    async def unexpected_year_lookup(*_args, **_kwargs):
        raise AssertionError("main card should not query years")

    monkeypatch.setattr(seo_renderer, "indicator_data_years", unexpected_year_lookup)

    async def render():
        async with auth_env["session_maker"]() as db:
            return await seo_renderer.render_indicator_html("cpi", db)

    status, html = asyncio.run(render())
    assert status == 200
    assert 'href="/russia/indicator/cpi/2024"' not in html
    assert "Индекс потребительских цен по годам" not in html


def test_main_card_chart_rights_cover_og_url(year_landing_client, auth_env):
    from app.services.seo_renderer import render_indicator_html

    async def render():
        async with auth_env["session_maker"]() as db:
            return await render_indicator_html("cpi", db)

    status, html = asyncio.run(render())
    assert status == 200
    structured = [json.loads(raw) for raw in re.findall(
        r'<script type="application/ld\+json">(.*?)</script>', html, re.S,
    )]
    chart = next(item for item in structured if item.get("@type") == "ImageObject")
    assert chart["contentUrl"].endswith("/og/russia/cpi.png")
    assert chart["copyrightNotice"] == "Forecast Economy (chart only)"
    assert chart["license"].endswith("/terms")
    assert chart["acquireLicensePage"].endswith("/terms")


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


def test_year_landing_does_not_promise_a_forecast_or_invent_coverage(year_landing_client, auth_env):
    """A historical daily series has only June/July observations and no forecast."""
    import json
    from app.services.locale import set_locale, reset_locale

    async def render(locale):
        token = set_locale(locale)
        try:
            async with auth_env['session_maker']() as db:
                return await render_indicator_year_html('usd-index', 2024, db)
        finally:
            reset_locale(token)

    for locale, heading, false_heading in (
        ('ru', 'Полная история и график', 'График и прогноз'),
        ('en', 'Full history and chart', 'Chart and forecast'),
    ):
        status, html = asyncio.run(render(locale))
        assert status == 200
        assert f'<h2>{heading}</h2>' in html
        assert f'<h2>{false_heading}</h2>' not in html
        datasets = [json.loads(raw) for raw in re.findall(
            r'<script type="application/ld\+json">(.*?)</script>', html, re.S)]
        dataset = next(d for d in datasets if d.get('@type') == 'Dataset')
        assert dataset['temporalCoverage'] == '2024-06-01/2024-07-01'


def test_old_year_links_keep_neighbouring_years(year_landing_client, auth_env):
    from sqlalchemy import select

    async def render():
        async with auth_env['session_maker']() as db:
            indicator = (await db.execute(select(Indicator).where(
                Indicator.code == 'population'))).scalar_one()
            for year in range(2000, 2016):
                db.add(IndicatorData(indicator_id=indicator.id, date=date(year, 1, 1), value=140))
            await db.commit()
            return await render_indicator_year_html('population', 2005, db)

    status, html = asyncio.run(render())
    assert status == 200
    other_years = html.split('<h2>Другие годы</h2>')[1].split('</section>')[0]
    assert '/population/2004' in other_years
    assert '/population/2006' in other_years
    assert '/population/2025' not in other_years


def test_derived_cpi_provenance_follows_rendered_series(year_landing_client, auth_env):
    from app.services.seo_renderer import render_indicator_html
    from app.services.locale import set_locale, reset_locale

    async def render(locale):
        token = set_locale(locale)
        try:
            async with auth_env['session_maker']() as db:
                yoy = Indicator(code='cpi-yoy', name='Годовая инфляция', name_en='Annual inflation',
                                frequency='monthly', unit='%', source='Росстат', category='Цены',
                                is_active=True, is_listed=True)
                db.add(yoy)
                await db.flush()
                for month, value in ((1, 5.5), (2, 6.0)):
                    db.add(IndicatorData(indicator_id=yoy.id, date=date(2024, month, 1), value=value))
                await db.flush()
                derived = await render_indicator_html('cpi-yoy', db)
                year = await render_indicator_year_html('cpi-yoy', 2024, db)
                base = await render_indicator_html('cpi', db)
                # Roll back this locale's seed to allow the second locale to use the same code.
                return derived, year, base
        finally:
            reset_locale(token)

    for locale, notice in (('ru', 'Расчёт Forecast Economy'), ('en', 'Calculated by Forecast Economy')):
        derived, year, base = asyncio.run(render(locale))
        for status, html in (derived, year):
            assert status == 200
            assert notice in html
            assert 'class="seo-data-provenance"' in html
        assert base[0] == 200
        assert 'class="seo-data-provenance"' not in base[1]


def test_annual_og_hero_matches_annual_answer_and_phone_cache_is_separate(year_landing_client, monkeypatch):
    from app.services import og_image
    from app.services.display import annual_summary
    captured, keys = [], []
    monkeypatch.setattr(og_image, "cached_og", lambda key, **_kw: None)
    monkeypatch.setattr(og_image, "store_og", lambda key, image, **_kw: keys.append(key))
    monkeypatch.setattr(og_image, "render_indicator_og", lambda **kw: captured.append(kw) or b"png")
    for query in ("", "?portrait=1"):
        response = year_landing_client.get("/api/v1/og-image/indicator/cpi/2024.png" + query)
        assert response.status_code == 200
    assert captured[0]["value_text"] == annual_summary("cpi", [100 + m * .1 for m in range(1, 7)], "%")[1]
    assert captured[0]["value_text"] != "+0,60"
    assert captured[0]["portrait"] is False and captured[1]["portrait"] is True
    assert keys[0] != keys[1]
    assert len(captured[0]["values"]) == len(captured[0]["point_dates"]) == 6


def test_historical_og_selects_requested_year_among_neighbors(year_landing_client, monkeypatch):
    from app.services import og_image
    captured = []
    monkeypatch.setattr(og_image, "cached_og", lambda key, **_kw: None)
    monkeypatch.setattr(og_image, "store_og", lambda *args, **_kw: None)
    monkeypatch.setattr(og_image, "render_indicator_og", lambda **kw: captured.append(kw) or b"png")
    response = year_landing_client.get("/api/v1/og-image/indicator/population/2023.png")
    assert response.status_code == 200
    data = captured[0]
    assert data["point_dates"][data["selected_index"]].year == 2023
    assert data["point_dates"][-1].year == 2025


# ── Вид страницы года (critic2 №5/№6/№9) ─────────────────────────────────────


@pytest.fixture
def key_rate_year_html(year_landing_client, auth_env):
    """Дневная ставка за 2024: 40 значений с редкими изменениями (16 → 21)."""
    from datetime import timedelta

    async def render():
        async with auth_env["session_maker"]() as db:
            ind = Indicator(
                code="key-rate", name="Ключевая ставка ЦБ РФ", unit="%",
                frequency="daily", category="Процентные ставки",
                source="Банк России", is_active=True, is_listed=True,
            )
            db.add(ind)
            await db.flush()
            day = date(2024, 1, 3)
            for i in range(40):
                db.add(IndicatorData(
                    indicator_id=ind.id, date=day + timedelta(days=i),
                    value=16.0 if i < 20 else 17.5 if i < 30 else 21.0,
                ))
            await db.commit()
            return await render_indicator_year_html("key-rate", 2024, db)

    status, html = asyncio.run(render())
    assert status == 200
    return html


def test_year_page_headline_and_number_appear_once(key_rate_year_html):
    """Заголовок и главное число — в одной крупной карточке, без пересказа."""
    html = key_rate_year_html
    assert html.count("<h1>") == 1
    # В видимом тексте (без alt/JSON-LD/meta) название не повторяется абзацем.
    visible = re.sub(r"<script.*?</script>|<img[^>]*>|<head>.*?</head>", "", html, flags=re.S)
    assert visible.count("Ключевая ставка ЦБ РФ в 2024 году") <= 3  # H1 + крошка + якорь
    assert "40 значений за 2024 год. Источник: Банк России." in html
    assert "среднее за год — " not in visible


def test_year_page_totals_are_tiles_not_bullets(key_rate_year_html):
    html = key_rate_year_html
    tiles = re.search(r'<div class="seo-tiles seo-year-tiles">(.*?)</div></section>', html, re.S)
    assert tiles, "итоги должны быть плитками"
    for label in ("На начало года", "На конец года", "Минимум", "Максимум"):
        assert f"<span>{label}</span>" in tiles.group(1)
    # Даты у плиток — человекочитаемые.
    assert "3 января 2024" in tiles.group(1)
    assert "Количество наблюдений" not in html
    assert "<ul>\n<li>Среднее за год" not in html


def test_year_page_numbers_have_one_format(key_rate_year_html):
    """«17,62 %» в карточке и «16,00 %» в таблице: одно число знаков, запятая, пробел перед %."""
    html = key_rate_year_html
    cells = re.findall(r"<td>([\d,]+) %</td>", html)
    assert len(cells) == 40
    assert {len(c.split(",")[1]) for c in cells} == {2}
    assert "17,62\u00a0%" not in html  # главное число — с обычным пробелом, как в мета
    tiles = re.search(r'<div class="seo-tiles seo-year-tiles">(.*?)</section>', html, re.S).group(1)
    nums = re.findall(r"<b>([\d,]+)", tiles)
    assert nums == ["16,00", "21,00", "16,00", "21,00"]
    assert not re.search(r"<td>\d+</td>", html)  # «16» без знаков — нет


def test_year_page_long_table_is_collapsed_with_all_rows_in_markup(key_rate_year_html):
    html = key_rate_year_html
    section = html.split("Все значения за 2024 год</h2>")[1].split("</section>")[0]
    first_table, rest = section.split('<details class="seo-more">')
    assert 12 <= first_table.count("<tr><td>") <= 20
    assert first_table.count("<tr><td>") == 12
    assert "Показать ещё 28 значений" in rest
    assert rest.count("<tr><td>") == 28  # остаток остаётся в HTML для поисковика


def test_year_page_short_table_is_not_collapsed(year_landing_client, auth_env):
    async def render():
        async with auth_env["session_maker"]() as db:
            return await render_indicator_year_html("cpi", 2024, db)

    status, html = asyncio.run(render())
    assert status == 200
    assert "<details class=\"seo-more\">" not in html


def test_year_page_has_glass_chrome_and_collapsing_menu(key_rate_year_html):
    html = key_rate_year_html
    assert '<header class="seo-topbar">' in html
    assert 'id="seo-menu-toggle"' in html and 'for="seo-menu-toggle"' in html
    # Меню не обрезается краем экрана: на телефоне — сетка за кнопкой «Меню».
    assert "overflow-x:auto" not in re.search(
        r"body\.seo-fast \.seo-topnav\{[^}]*\}", html
    ).group(0)
    # Прежние ссылки навигации на месте (перелинковка не потеряна).
    for href in ('href="/russia"', 'href="/russia/region"', 'href="/compare"', 'href="/about"'):
        assert href in html


def test_year_page_keeps_seo_markup(key_rate_year_html):
    html = key_rate_year_html
    assert '<link rel="canonical" href="https://forecasteconomy.com/russia/indicator/key-rate/2024">' in html
    assert '"@type": "Dataset"' in html or '"@type":"Dataset"' in html
    assert '"@type": "BreadcrumbList"' in html or '"@type":"BreadcrumbList"' in html
    assert 'property="og:image"' in html
    assert 'src="/og/russia/key-rate/2024.png"' in html
    assert "seo-chart-brand" not in html.split('<figure class="seo-chart"')[1].split("</figure>")[0]


def test_year_page_single_value_facts_are_cards(year_landing_client, auth_env):
    async def render():
        async with auth_env["session_maker"]() as db:
            return await render_indicator_year_html("population", 2025, db)

    _status, html = asyncio.run(render())
    assert '<ul class="seo-facts">' in html
    facts = html.split('<ul class="seo-facts">')[1].split("</ul>")[0]
    assert "Изменение к 2024 году" in facts
    assert "Положение в истории" in facts
    assert "Значение:" not in facts  # само значение уже в крупной карточке
    assert "истории ряда" not in html and "историю ряда" not in html
