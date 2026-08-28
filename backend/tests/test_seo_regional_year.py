"""Годовые лендинги регионов /russia/region/{slug}/{code}/{year}: SSR + sitemap.

Проверки:
- 200: H1/титул с регионом-показателем-годом, ранг-фраза за выбранный год,
  сравнение со средним по России, таблица по годам, CTA на карточку,
  canonical/og:image/Dataset JSON-LD;
- EN-локаль (X-FE-Locale: en): EN h1/таблица/ранг-фраза/динамика/CTA/мета,
  отсутствие русских слов, числа с десятичной точкой;
- 404: мусорный slug/code/год вне ряда; slug='russia' → 200 без ранга;
- канонизация короткого слага («tatarstan» → «respublika-tatarstan»), 301
  с сохранением кода и года;
- публичная грамматика: без mid-dot и внутренних идентификаторов.
"""

from __future__ import annotations

import asyncio
import json
import re
from datetime import date

import pytest
from fastapi.testclient import TestClient


CODE = "chislennost-naseleniya"  # нейтральная полярность: сортировка desc
# Таблица сборника 1.1 (население) — полярность None: нейтральная подача ранга.
TABLE_CODE = "1.1"
SECTION = "Население"
IND_NAME = "Численность населения на 1 января"
LOCALE_HEADER = {"X-FE-Locale": "en"}


@pytest.fixture
def region_year_client(auth_env):
    """Три субъекта kind='region' (ранг по 3 субъектам) + 'russia'
    (kind='country') + показатель с годами 2018–2023."""

    async def _seed():
        from app.models import (
            Region,
            RegionDataPoint,
            RegionIndicator,
        )

        async with auth_env["session_maker"]() as db:
            moskva = Region(
                slug="moskva", name="Москва", kind="region", sort_order=1,
                district_slug="central",
            )
            tatarstan = Region(
                slug="respublika-tatarstan", name="Республика Татарстан",
                kind="region", sort_order=2, district_slug="volga",
            )
            perm = Region(
                slug="permskiy-kray", name="Пермский край",
                kind="region", sort_order=3, district_slug="volga",
            )
            rf = Region(
                slug="russia", name="Российская Федерация",
                kind="country", sort_order=0,
            )
            db.add_all([moskva, tatarstan, perm, rf])
            await db.flush()

            ind = RegionIndicator(
                code=CODE,
                table_code=TABLE_CODE,
                section_num=1,
                section_name=SECTION,
                name=IND_NAME,
                unit="человек",
                year_min=2018,
                year_max=2023,
                is_listed=True,
            )
            db.add(ind)
            await db.flush()

            base = {
                moskva.id: 13_100_000,
                tatarstan.id: 4_000_000,
                perm.id: 2_600_000,
                rf.id: 146_700_000,
            }
            for reg, lvl in base.items():
                for i, y in enumerate(range(2018, 2024)):
                    db.add(RegionDataPoint(
                        region_id=reg, indicator_id=ind.id,
                        year=y, value=lvl + i * 10_000,
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


def test_year_page_200_core_blocks(region_year_client):
    """200: H1, ранг года, сравнение с РФ, таблица, CTA, мета и JSON-LD."""
    r = region_year_client.get(f"/seo/region-indicator-year/moskva/{CODE}/2023")
    assert r.status_code == 200
    html = r.text

    h1 = re.search(r"<h1>([^<]+)</h1>", html).group(1)
    assert "Численность населения" in h1
    assert "в регионе Москва" in h1
    assert "2023" in h1

    # Значение года: 13_100_000 + 5 * 10_000 = 13 150 000.
    assert "13\u202f150\u202f000" in html

    # Ранг именно за выбранный год: 3 субъекта, Москва — первая по величине.
    # Полярность нейтральная (table_code 1.1 не в LOWER_BETTER) → list-фраза.
    assert "Место среди регионов России" in html
    assert re.search(
        r"В 2023 году Москва входит в тройку регионов", html
    ), "ожидалась ранг-фраза нейтральной подачи"
    assert "из 3" in html

    # Сравнение со средним по России за тот же год (Москва ниже общероссийского).
    assert "Сравнение со средним по России" in html
    assert "В среднем по России в 2023 году" in html
    assert "ниже среднероссийского" in html

    # Таблица динамики: короткий ряд (<16) — все годы с заголовком по имени.
    assert f"{IND_NAME} в регионе Москва по годам" in html
    # Обычные строки + выделенная строка выбранного года (<strong>).
    rows = re.findall(r"<tr><td>(?:<strong>)?(\d{4})(?:</strong>)?</td>", html)
    assert sorted(int(y) for y in rows) == list(range(2018, 2024))
    assert "<tr><td><strong>2023</strong></td>" in html  # выбранный год выделен

    # CTA на живую карточку.
    assert f'href="/russia/region/moskva/{CODE}"' in html
    assert "Полная история, интерактивный график" in html

    # Мета и машинная разметка.
    assert (
        'rel="canonical" href="https://forecasteconomy.com'
        f'/russia/region/moskva/{CODE}/2023"'
    ) in html
    assert (
        'property="og:image" content="https://forecasteconomy.com'
        f'/og/russia/region/moskva/{CODE}/2023.png"'
    ) in html
    assert f'src="/og/russia/region/moskva/{CODE}/2023.png"' in html

    datasets = [b for b in _jsonld(html) if b.get("@type") == "Dataset"]
    assert datasets, "нет Dataset JSON-LD"
    ds = datasets[0]
    assert ds["temporalCoverage"] == "2023-01-01/2023-12-31"
    assert ds["spatialCoverage"] == "Москва"


def test_russia_page_200_without_rank(region_year_client):
    """slug='russia': страница отдаётся 200 и БЕЗ ранга (инвариант рендерера)."""
    r = region_year_client.get(f"/seo/region-indicator-year/russia/{CODE}/2022")
    assert r.status_code == 200
    html = r.text

    assert "Российская Федерация" in html
    h1 = re.search(r"<h1>([^<]+)</h1>", html).group(1)
    assert "Численность населения" in h1
    assert "2022" in h1

    assert "Место среди регионов России" not in html
    assert "Рейтинг регионов и значения по годам" in html
    # Сравнение с РФ для самой РФ не строится.
    assert "Сравнение со средним по России" not in html


def test_404_cases(region_year_client):
    base = "/seo/region-indicator-year"
    # Мусорный slug и код.
    assert region_year_client.get(
        f"{base}/no-such-region/{CODE}/2023"
    ).status_code == 404
    assert region_year_client.get(
        f"{base}/moskva/no-such-code/2023"
    ).status_code == 404
    # Год вне ряда (и мусорный формат года отсекается роутом).
    assert region_year_client.get(
        f"{base}/moskva/{CODE}/2017"
    ).status_code == 404
    assert region_year_client.get(
        f"{base}/moskva/{CODE}/2024"
    ).status_code == 404
    assert region_year_client.get(
        f"{base}/moskva/{CODE}/20x4"
    ).status_code == 404


def test_short_slug_redirects_to_canonical_with_year(region_year_client):
    """Короткий слаг → 301 на канонический с префиксом, год сохранён."""
    redir = region_year_client.get(
        f"/seo/region-indicator-year/tatarstan/{CODE}/2021",
        follow_redirects=False,
    )
    assert redir.status_code == 301
    assert redir.headers["location"] == (
        f"/russia/region/respublika-tatarstan/{CODE}/2021"
    )


def test_public_grammar_no_mid_dot_no_internals(region_year_client):
    """Публичный язык: без mid-dot и без внутренних идентификаторов."""
    r = region_year_client.get(f"/seo/region-indicator-year/moskva/{CODE}/2023")
    assert r.status_code == 200
    html = r.text
    assert "·" not in html
    for leak in ("парсер", "bulk_upsert", "RegionDataPoint", "table_code",
                 "source_note"):
        assert leak not in html


def test_sitemap_regional_years_matches_ssr(region_year_client, auth_env):
    """Двусторонняя сверка sitemap-секции regional-years ↔ SSR."""
    from app.services.seo_regional_year import render_region_indicator_year_html
    from app.services.site_urls import _regional_year_urls

    async def _check():
        async with auth_env["session_maker"]() as db:
            urls = await _regional_year_urls(db, date.today())
            paths_list = sorted(u.path for u in urls)

            # moskva и tatarstan — kind=region, все 6 лет в карте.
            for slug in ("moskva", "respublika-tatarstan"):
                for y in range(2018, 2024):
                    assert f"/russia/region/{slug}/{CODE}/{y}" in paths_list
            # lastmod = 31 декабря СВОЕГО года (регионы обновляются раз в год).
            assert all(
                u.lastmod == f"{u.path.rsplit('/', 1)[1]}-12-31" for u in urls
            )
            # Перми тоже есть — по всем трем субъектам.
            assert f"/russia/region/permskiy-kray/{CODE}/2020" in paths_list

            # Каждая карта-URL рендерится 200.
            for path in paths_list:
                m = re.fullmatch(r"/russia/region/([^/]+)/([^/]+)/(\d{4})", path)
                assert m, path
                status, _html = await render_region_indicator_year_html(
                    m.group(1), m.group(2), int(m.group(3)), db
                )
                assert status == 200, f"{path} in sitemap but SSR={status}"

            # Обратно: известный 200 не забыт в карте.
            assert f"/russia/region/moskva/{CODE}/2023" in paths_list

    asyncio.run(_check())


def test_sitemap_regional_years_http_section(region_year_client):
    """HTTP-грань: индекс содержит regional-years-секцию, секция — URL."""
    idx = region_year_client.get("/sitemap.xml")
    assert idx.status_code == 200
    assert "sitemap-regional-years-" in idx.text

    section = region_year_client.get("/sitemap-regional-years-1.xml")
    assert section.status_code == 200
    assert (
        f"https://forecasteconomy.com/russia/region/moskva/{CODE}/2023"
        in section.text
    )


# ---------------------------------------------------------------------------
# EN-локаль (X-FE-Locale: en) — двуязычность Фазы 9A
# ---------------------------------------------------------------------------

RU_LEAKS = ("в регионе", "Сравнение со средним", "Контрольные годы",
            "Другие годы", "в 2023 году", "в 2022 году", "год —")


def _get_en(client, path: str) -> str:
    r = client.get(path, headers=LOCALE_HEADER)
    assert r.status_code == 200, (r.status_code, r.text[:200])
    return r.text


def test_en_year_page_core_blocks(region_year_client):
    """EN: h1, значения с точкой-разделителем, таблица, ранг, РФ-сравнение."""
    html = _get_en(region_year_client, f"/seo/region-indicator-year/moskva/{CODE}/2023")

    h1 = re.search(r"<h1>([^<]+)</h1>", html).group(1)
    assert "Population" in h1
    assert "Moscow" in h1
    assert "2023" in h1

    # Числа в EN-типографике: десятичная точка, групповые запятые.
    assert "13,150,000" in html
    assert "13\u202f150" not in html  # русский формат не просачивается

    # Таблица с EN-заголовком «Year».
    assert "<th>Year</th>" in html
    assert "Год" not in html

    # Ранг нейтральной подачи (3 субъекта): EN list-фраза.
    assert "Place among Russian regions" in html
    assert re.search(
        r"In 2023, Moscow is among the three regions", html
    ), "ожидалась EN ранг-фраза нейтральной подачи"

    # Сравнение с РФ (Москва ниже общероссийского).
    assert "Comparison with the Russian average" in html
    assert "The Russian average in 2023" in html
    assert "below the national average" in html

    # CTA и «Другие годы».
    assert "Chart and full data" in html
    assert "Full history, an interactive chart" in html
    assert "Other years" in html
    assert f"Population in 2022" in html


def test_en_year_page_no_russian_leaks(region_year_client):
    """EN-HTML: ни одного ключевого русского слова из тела страницы."""
    html = _get_en(region_year_client, f"/seo/region-indicator-year/moskva/{CODE}/2023")

    body = html.split("</head>", 1)[-1]
    for leak in RU_LEAKS:
        assert leak not in body, leak

    # И мета-данные EN: титул/description/keywords без кириллицы.
    title = re.search(r"<title>(.*?)</title>", html, re.S).group(1)
    assert not re.search(r"[А-Яа-яЁё]", title), title
    desc = re.search(r'name="description" content="([^"]*)"', html).group(1)
    assert not re.search(r"[А-Яа-яЁё]", desc), desc
    kw = re.search(r'name="keywords" content="([^"]*)"', html).group(1)
    assert not re.search(r"[А-Яа-яЁё]", kw), kw

    # Единица показателя — из EN-каталога (population; unit "thousand people").
    # Тест-фикстура задаёт RU-юнит «человек» → EN-каталог даёт свой EN-юнит.
    assert "thousand people" in html


def test_en_change_and_jsonld(region_year_client):
    """EN: изменение к прошлому году, Dataset name/creator, trail-крошка."""
    html = _get_en(region_year_client, f"/seo/region-indicator-year/moskva/{CODE}/2023")

    assert "Change versus 2022" in html
    assert re.search(r"indicator\s+rose", html) or "rose" in html

    datasets = [b for b in _jsonld(html) if b.get("@type") == "Dataset"]
    assert datasets
    ds = datasets[0]
    assert ds["name"] == "Population — Moscow, 2023"
    assert ds["creator"]["name"] == "Rosstat"
    assert ds["spatialCoverage"] == "Moscow"

    crumbs_html = re.search(
        r'<nav aria-label="Breadcrumb">(.*?)</nav>', html, re.S
    )
    assert crumbs_html, "нет EN-крошек"
    assert "Population in Moscow, 2023" in crumbs_html.group(1)


def test_en_russia_page_without_rank(region_year_client):
    """EN: slug='russia' — без ранг-секции, EN-описание и EN-таблица."""
    html = _get_en(region_year_client, f"/seo/region-indicator-year/russia/{CODE}/2022")

    assert "Place among Russian regions" not in html
    assert "Regional rankings and values by year" in html
    assert "Russian Federation" in html
    assert "<th>Year</th>" in html
    assert "Год" not in html
    for leak in ("в 2022 году", "в регионе"):
        assert leak not in html


def test_en_number_typography_punct(region_year_client):
    """EN: типографский минус и EN-группировка в изменении к прошлому году."""
    html = _get_en(region_year_client, f"/seo/region-indicator-year/moskva/{CODE}/2022")

    # 2022: 13_110_000 − 13_100_000 = +10 000.
    assert "Change versus 2021: +10,000" in html
    assert "thousand people" in html  # EN-юнит из каталога
