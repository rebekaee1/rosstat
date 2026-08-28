"""Годовые лендинги мира /{country}/indicator/{code}/{year}: SSR + sitemap.

Проверки:
- annual-ряд (1 точка/год): 200, H1 с именем и годом, соседние годы,
  canonical/og:image/Dataset JSON-LD;
- monthly-год: итоги года и таблица всех наблюдений;
- 404: страна/unlisted/год вне данных/мусорный формат года;
- вторичная частота карточки → 301 на primary с сохранением года;
- EN-локаль (X-FE-Locale): EN-заголовок и крошка «{display} in {country}, {year}»;
- двусторонняя сверка sitemap-секции world-years ↔ SSR.
"""

from __future__ import annotations

import asyncio
import json
import re
from datetime import date

import pytest
from fastapi.testclient import TestClient


CODE_ANNUAL = "de-demo_pjan-total-t-nr"       # annual, по 1 точке за год
CODE_MONTHLY = "de-prc_hicp_midx-cp00-i15"    # monthly, 12 точек/год
CODE_SIBLING_M = "de-une_rt_m-total-sa-t-pc-act"  # primary карточки
CODE_SIBLING_Q = "de-une_rt_q-y15-74-sa-t-pc-act"  # вторичная частота
CODE_UNLISTED = "de-zz_raw_stub"


@pytest.fixture
def world_year_client(auth_env):
    """Страна + annual-ряд 2020–2024 (1 точка/год) + monthly-ряд 2023–2025
    + пара частот одной карточки (301-тест) + unlisted-ряд (404-тест)."""

    async def _seed():
        from app.models import WorldCountry, WorldDataPoint, WorldIndicator

        async with auth_env["session_maker"]() as db:
            de = WorldCountry(
                code="DE", slug="germany", name_ru="Германия",
                name_en="Germany", region_ru="Европа", sort_order=1,
            )
            db.add(de)
            await db.flush()

            annual = WorldIndicator(
                country_id=de.id,
                code=CODE_ANNUAL,
                dataset_id="demo_pjan",
                slice_json={"unit": "NR", "age": "TOTAL", "sex": "T"},
                slice_hash="pop1",
                name_ru="Численность населения",
                name_en="Population",
                name_quality="curated",
                unit="NR",
                unit_ru="человек",
                frequency="annual",
                category_ru="Население",
                source="Евростат",
                history_start=date(2020, 1, 1),
                history_end=date(2024, 1, 1),
                points_count=5,
                is_listed=True,
            )
            monthly = WorldIndicator(
                country_id=de.id,
                code=CODE_MONTHLY,
                dataset_id="prc_hicp_midx",
                slice_json={"unit": "I15", "coicop": "CP00", "freq": "M"},
                slice_hash="abc",
                name_ru="Гармонизированный индекс потребительских цен, помесячно",
                name_en="HICP",
                name_quality="curated",
                unit="I15",
                unit_ru="индекс 2015=100",
                frequency="monthly",
                category_ru="Цены",
                source="Евростат",
                history_start=date(2023, 1, 1),
                history_end=date(2025, 12, 1),
                points_count=36,
                is_listed=True,
            )
            une_m = WorldIndicator(
                country_id=de.id,
                code=CODE_SIBLING_M,
                dataset_id="une_rt_m",
                slice_json={"unit": "PC_ACT", "age": "TOTAL", "sex": "T", "s_adj": "SA"},
                slice_hash="une1",
                name_ru="Безработица, % экономически активного населения, помесячно",
                name_quality="curated",
                unit="PC_ACT",
                unit_ru="% экономически активного населения",
                frequency="monthly",
                category_ru="Рынок труда",
                source="Евростат",
                history_start=date(2023, 1, 1),
                history_end=date(2024, 12, 1),
                points_count=24,
                is_listed=True,
            )
            # Тот же card_key, что у monthly (возраст Y15-74 → TOTAL,
            # s_adj — служебное измерение): вторичная частота карточки.
            une_q = WorldIndicator(
                country_id=de.id,
                code=CODE_SIBLING_Q,
                dataset_id="une_rt_q",
                slice_json={"unit": "PC_ACT", "age": "Y15-74", "sex": "T", "s_adj": "SA"},
                slice_hash="une1q",
                name_ru="Безработица, % экономически активного населения, поквартально",
                name_quality="curated",
                unit="PC_ACT",
                unit_ru="% экономически активного населения",
                frequency="quarterly",
                category_ru="Рынок труда",
                source="Евростат",
                history_start=date(2023, 1, 1),
                history_end=date(2024, 10, 1),
                points_count=8,
                is_listed=True,
            )
            unlisted = WorldIndicator(
                country_id=de.id,
                code=CODE_UNLISTED,
                dataset_id="zz_raw",
                slice_json={},
                slice_hash="raw",
                name_ru="Экономический показатель",
                name_quality="raw",
                unit="",
                unit_ru="",
                frequency="monthly",
                category_ru="Прочее",
                source="Евростат",
                history_start=date(2024, 1, 1),
                history_end=date(2024, 8, 1),
                points_count=8,
                is_listed=False,
            )
            db.add_all([annual, monthly, une_m, une_q, unlisted])
            await db.flush()

            for i, y in enumerate(range(2020, 2025)):
                db.add(WorldDataPoint(
                    indicator_id=annual.id,
                    date=date(y, 1, 1), value=83_000_000.0 + i * 100_000,
                ))
            for i in range(36):
                db.add(WorldDataPoint(
                    indicator_id=monthly.id,
                    date=date(2023 + i // 12, i % 12 + 1, 1), value=100.0 + i,
                ))
            for i in range(24):
                db.add(WorldDataPoint(
                    indicator_id=une_m.id,
                    date=date(2023 + i // 12, i % 12 + 1, 1), value=3.0 + i * 0.1,
                ))
            for i in range(8):
                q = i % 4 + 1
                db.add(WorldDataPoint(
                    indicator_id=une_q.id,
                    date=date(2023 + i // 4, (q - 1) * 3 + 1, 1), value=6.0 + i * 0.2,
                ))
            for i in range(8):
                db.add(WorldDataPoint(
                    indicator_id=unlisted.id,
                    date=date(2024, i + 1, 1), value=1.0 + i,
                ))
            await db.commit()

    asyncio.run(_seed())
    with TestClient(auth_env["app"]) as tc:
        yield tc


def _jsonld(html: str) -> list[dict]:
    return [
        json.loads(m.group(1))
        for m in re.finditer(
            r'<script type="application/ld\+json">(.*?)</script>', html, re.S
        )
    ]


def test_annual_single_point_year_page(world_year_client):
    """Annual-год с одной точкой: H1, соседние годы, canonical/og/Dataset."""
    r = world_year_client.get(f"/seo/world-indicator-year/germany/{CODE_ANNUAL}/2023")
    assert r.status_code == 200
    html = r.text

    h1 = re.search(r"<h1>([^<]+)</h1>", html).group(1)
    assert "Численность населения" in h1
    assert "2023" in h1
    assert "<title>Численность населения в 2023 году — значение и динамика" in html

    assert "Динамика соседних лет" in html
    assert "<strong>2023</strong>" in html
    assert "Изменение к 2022 году" in html
    assert "среднего" in html  # положение в истории ряда

    assert (
        'rel="canonical" '
        f'href="https://forecasteconomy.com/germany/indicator/{CODE_ANNUAL}/2023"'
    ) in html
    assert (
        'property="og:image" '
        f'content="https://forecasteconomy.com/og/germany/{CODE_ANNUAL}/2023.png"'
    ) in html
    assert f'src="/og/germany/{CODE_ANNUAL}/2023.png"' in html

    datasets = [b for b in _jsonld(html) if b.get("@type") == "Dataset"]
    assert datasets, "нет Dataset JSON-LD"
    assert datasets[0]["temporalCoverage"] == "2023-01-01/2023-01-01"


def test_monthly_multi_point_year_page(world_year_client):
    """Monthly-год: итоги года и таблица всех точек года."""
    r = world_year_client.get(f"/seo/world-indicator-year/germany/{CODE_MONTHLY}/2024")
    assert r.status_code == 200
    html = r.text

    assert "Значение на начало года" in html
    assert "Значение на конец года" in html
    assert "Среднее за год" in html
    assert "Минимум и максимум" in html
    assert "Количество наблюдений: 12" in html

    h1 = re.search(r"<h1>([^<]+)</h1>", html).group(1)
    assert "Гармонизированный индекс потребительских цен" in h1
    assert "2024" in h1
    assert "помесячно" not in h1  # суффикс частоты вычищен из публичного имени

    assert "Все значения за 2024 год" in html
    rows_2024 = re.findall(r"<td>[^<]*2024</td>", html)
    assert len(rows_2024) >= 12, f"ожидались строки всех месяцев 2024, найдено {len(rows_2024)}"


def test_year_out_of_data_404(world_year_client):
    assert world_year_client.get(
        f"/seo/world-indicator-year/germany/{CODE_ANNUAL}/2019"
    ).status_code == 404
    assert world_year_client.get(
        f"/seo/world-indicator-year/germany/{CODE_MONTHLY}/2022"
    ).status_code == 404


def test_unknown_country_and_unlisted_404(world_year_client):
    assert world_year_client.get(
        f"/seo/world-indicator-year/no-such-country/{CODE_ANNUAL}/2023"
    ).status_code == 404
    assert world_year_client.get(
        f"/seo/world-indicator-year/germany/{CODE_UNLISTED}/2024"
    ).status_code == 404
    # Мусорный формат года отсекается роутом до рендера.
    assert world_year_client.get(
        f"/seo/world-indicator-year/germany/{CODE_ANNUAL}/20x4"
    ).status_code == 404


def test_secondary_frequency_sibling_redirects_with_year(world_year_client):
    """Вторичная частота → 301 на primary, год сохраняется в хвосте пути."""
    redir = world_year_client.get(
        f"/seo/world-indicator-year/germany/{CODE_SIBLING_Q}/2024",
        follow_redirects=False,
    )
    assert redir.status_code == 301
    assert redir.headers["location"] == (
        f"/germany/indicator/{CODE_SIBLING_M}/2024"
    )


def test_locale_en_title_and_breadcrumb(world_year_client):
    """EN (X-FE-Locale): формула «{display} in {country}, {year}», RU не задет."""
    en = world_year_client.get(
        f"/seo/world-indicator-year/germany/{CODE_ANNUAL}/2023",
        headers={"X-FE-Locale": "en"},
    )
    assert en.status_code == 200
    html = en.text
    assert (
        "<title>Population in Germany, 2023 — value and dynamics</title>" in html
    )
    # H1 — заголовок до первого « — »: формула с страной и годом, без кириллицы.
    h1 = re.search(r"<h1>([^<]+)</h1>", html).group(1)
    assert h1 == "Population in Germany, 2023"
    assert not re.search(r"[А-Яа-яЁё]", h1)

    ru = world_year_client.get(f"/seo/world-indicator-year/germany/{CODE_ANNUAL}/2023")
    assert ru.status_code == 200
    assert "Численность населения" in ru.text


def test_grammar_no_mid_dot_no_internals(world_year_client):
    """Публичная грамматика: без mid-dot и без внутренних идентификаторов."""
    r = world_year_client.get(f"/seo/world-indicator-year/germany/{CODE_ANNUAL}/2023")
    assert r.status_code == 200
    html = r.text
    assert "·" not in html
    for leak in ("SDMX", "dataflow", "slice_hash", "dataset_id", "парсер"):
        assert leak not in html


def test_sitemap_world_years_matches_ssr(world_year_client, auth_env):
    """Двусторонняя сверка sitemap-секции world-years ↔ SSR (мелкий датасет)."""
    from app.services.seo_world_year import render_world_indicator_year_html
    from app.services.site_urls import _world_year_urls

    async def _check():
        async with auth_env["session_maker"]() as db:
            urls = await _world_year_urls(db, date.today())
            paths = sorted(u.path for u in urls)

            # Основной ряд: все 5 лет; monthly: 2023–2025.
            for y in range(2020, 2025):
                assert f"/germany/indicator/{CODE_ANNUAL}/{y}" in paths
            for y in (2023, 2024, 2025):
                assert f"/germany/indicator/{CODE_MONTHLY}/{y}" in paths
            # Вторичная частота и unlisted в карту не попадают.
            assert all(CODE_SIBLING_Q not in p for p in paths)
            assert all(CODE_UNLISTED not in p for p in paths)

            # Каждая карта-URL рендерится 200.
            for path in paths:
                m = re.fullmatch(r"/germany/indicator/([^/]+)/(\d{4})", path)
                assert m, path
                status, _html = await render_world_indicator_year_html(
                    "germany", m.group(1), int(m.group(2)), db
                )
                assert status == 200, f"{path} in sitemap but SSR={status}"

            # Обратно: известный 200 не забыт в карте.
            assert f"/germany/indicator/{CODE_ANNUAL}/2023" in paths

    asyncio.run(_check())


def test_sitemap_world_years_http_section(world_year_client):
    """HTTP-грань: индекс содержит world-years-секцию, секция — годовые URL."""
    idx = world_year_client.get("/sitemap.xml")
    assert idx.status_code == 200
    assert "sitemap-world-years-" in idx.text

    section = world_year_client.get("/sitemap-world-years-1.xml")
    assert section.status_code == 200
    assert (
        f"https://forecasteconomy.com/germany/indicator/{CODE_ANNUAL}/2023"
        in section.text
    )
