"""SSR/SEO мирового блока: три типа страниц, sitemap listed-only, BreadcrumbList."""

from __future__ import annotations

import json
import re
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select


@pytest.fixture
def world_seo_client(auth_env):
    """Мини-датасет мирового блока (как test_world.world_client) + TestClient."""
    import asyncio

    from app.models import WorldCountry, WorldDataPoint, WorldIndicator

    async def _seed():
        async with auth_env["session_maker"]() as db:
            de = WorldCountry(
                code="DE", slug="germany", name_ru="Германия",
                name_en="Germany", region_ru="Европа", sort_order=1,
            )
            fr = WorldCountry(
                code="FR", slug="france", name_ru="Франция",
                name_en="France", region_ru="Европа", sort_order=2,
            )
            it = WorldCountry(
                code="IT", slug="italy", name_ru="Италия",
                name_en="Italy", region_ru="Европа", sort_order=3,
            )
            db.add_all([de, fr, it])
            await db.flush()
            listed = WorldIndicator(
                country_id=de.id,
                code="de-prc_hicp_midx-cp00-i15",
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
                source_url="https://ec.europa.eu/eurostat/databrowser/view/prc_hicp_midx",
                description=(
                    "Гармонизированный индекс потребительских цен в Германии — "
                    "официальный ряд Евростата."
                ),
                methodology="Источник данных — Евростат. Частота публикации — месячная.",
                history_start=date(2024, 1, 1),
                history_end=date(2025, 6, 1),
                points_count=18,
                is_listed=True,
            )
            listed_q = WorldIndicator(
                country_id=de.id,
                code="de-prc_hicp_qidx-cp00-i15",
                dataset_id="prc_hicp_qidx",
                slice_json={"unit": "I15", "coicop": "CP00", "freq": "Q"},
                slice_hash="abcq",
                name_ru="Гармонизированный индекс потребительских цен, поквартально",
                name_quality="curated",
                unit="I15",
                unit_ru="индекс 2015=100",
                frequency="quarterly",
                category_ru="Цены",
                source="Евростат",
                history_start=date(2024, 1, 1),
                history_end=date(2025, 4, 1),
                points_count=6,
                is_listed=True,
            )
            # Тот же card_key, что у monthly (stem prc_hicp_* → разный stem!)
            # Для теста 301 используем une_rt_m / une_rt_q с одинаковым срезом.
            une_m = WorldIndicator(
                country_id=de.id,
                code="de-une_rt_m-total-sa-t-pc-act",
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
                history_start=date(2020, 1, 1),
                history_end=date(2025, 6, 1),
                points_count=66,
                is_listed=True,
            )
            une_q = WorldIndicator(
                country_id=de.id,
                code="de-une_rt_q-y15-74-sa-t-pc-act",
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
                history_start=date(2020, 1, 1),
                history_end=date(2025, 4, 1),
                points_count=22,
                is_listed=True,
            )
            peer = WorldIndicator(
                country_id=fr.id,
                code="fr-prc_hicp_midx-cp00-i15",
                dataset_id="prc_hicp_midx",
                slice_json={"unit": "I15", "coicop": "CP00", "freq": "M"},
                slice_hash="abc",
                name_ru="Гармонизированный индекс потребительских цен, помесячно",
                name_quality="curated",
                unit="I15",
                unit_ru="индекс 2015=100",
                frequency="monthly",
                category_ru="Цены",
                source="Евростат",
                history_start=date(2024, 1, 1),
                history_end=date(2025, 6, 1),
                points_count=18,
                is_listed=True,
            )
            no_year_value = WorldIndicator(
                country_id=it.id,
                code="it-prc_hicp_midx-cp00-i15",
                dataset_id="prc_hicp_midx",
                slice_json={"unit": "I15", "coicop": "CP00", "freq": "M"},
                slice_hash="it-abc",
                name_ru="Гармонизированный индекс потребительских цен, помесячно",
                name_quality="curated",
                unit="I15",
                unit_ru="индекс 2015=100",
                frequency="monthly",
                category_ru="Цены",
                source="Евростат",
                history_start=date(2024, 1, 1),
                history_end=date(2025, 6, 1),
                points_count=0,
                is_listed=True,
            )
            population = WorldIndicator(
                country_id=de.id,
                code="de-demo_pjan-total-t-nr",
                dataset_id="demo_pjan",
                slice_json={"unit": "NR", "age": "TOTAL", "sex": "T"},
                slice_hash="pop1",
                name_ru="Численность населения",
                name_quality="curated",
                unit="NR",
                unit_ru="человек",
                frequency="annual",
                category_ru="Население",
                source="Евростат",
                history_start=date(2024, 1, 1),
                history_end=date(2025, 1, 1),
                points_count=2,
                is_listed=True,
            )
            budget = WorldIndicator(
                country_id=de.id,
                code="de-gov_10dd_edpt1-b9-s13-pc-gdp",
                dataset_id="gov_10dd_edpt1",
                slice_json={"unit": "PC_GDP", "na_item": "B9", "sector": "S13"},
                slice_hash="bud1",
                name_ru="Сальдо бюджета сектора государственного управления",
                name_quality="curated",
                unit="PC_GDP",
                unit_ru="% ВВП",
                frequency="annual",
                category_ru="Финансы",
                source="Евростат",
                history_start=date(2024, 1, 1),
                history_end=date(2025, 1, 1),
                points_count=2,
                is_listed=True,
            )
            gdp_annual = WorldIndicator(
                country_id=de.id,
                code="de-nama_10_gdp-b1gq-clv15-meur",
                dataset_id="nama_10_gdp",
                slice_json={"unit": "CLV15_MEUR", "na_item": "B1GQ"},
                slice_hash="gdp1",
                name_ru="Валовой внутренний продукт в постоянных ценах, год",
                name_quality="curated",
                unit="CLV15_MEUR",
                unit_ru="в постоянных ценах 2015 года, млн евро",
                frequency="annual",
                category_ru="Национальные счета",
                source="Евростат",
                history_start=date(2024, 1, 1),
                history_end=date(2025, 1, 1),
                points_count=2,
                is_listed=True,
            )
            long_rate = WorldIndicator(
                country_id=de.id,
                code="de-irt_lt_mcby_m-mcby",
                dataset_id="irt_lt_mcby_m",
                slice_json={"freq": "M", "int_rt": "MCBY"},
                slice_hash="irt1",
                name_ru="Доходность долгосрочных государственных облигаций",
                name_quality="curated",
                unit="",
                unit_ru="%",
                frequency="monthly",
                category_ru="Ставки",
                source="Евростат",
                history_start=date(2024, 1, 1),
                history_end=date(2025, 6, 1),
                points_count=18,
                is_listed=True,
            )
            activity = WorldIndicator(
                country_id=de.id,
                code="de-lfsi_emp_a-y15-64-act-t-pc-pop",
                dataset_id="lfsi_emp_a",
                slice_json={
                    "age": "Y15-64", "sex": "T", "freq": "A",
                    "unit": "PC_POP", "indic_em": "ACT",
                },
                slice_hash="act1",
                name_ru="Уровень экономической активности",
                name_quality="curated",
                unit="PC_POP",
                unit_ru="% населения",
                frequency="annual",
                category_ru="Рынок труда",
                source="Евростат",
                history_start=date(2024, 1, 1),
                history_end=date(2025, 1, 1),
                points_count=2,
                is_listed=True,
            )
            debt = WorldIndicator(
                country_id=de.id,
                code="de-gov_10dd_edpt1-gd-s13-pc-gdp",
                dataset_id="gov_10dd_edpt1",
                slice_json={"unit": "PC_GDP", "na_item": "GD", "sector": "S13"},
                slice_hash="debt1",
                name_ru="Государственный долг сектора государственного управления",
                name_quality="curated",
                unit="PC_GDP",
                unit_ru="% ВВП",
                frequency="annual",
                category_ru="Финансы",
                source="Евростат",
                history_start=date(2024, 1, 1),
                history_end=date(2025, 1, 1),
                points_count=2,
                is_listed=True,
            )
            weo_gdp = WorldIndicator(
                country_id=de.id,
                provider="imf",
                code="de-weo-ngdpd",
                dataset_id="WEO",
                slice_json={"weo_code": "NGDPD"},
                slice_hash="weo-ngdpd",
                name_ru="Валовой внутренний продукт в текущих ценах",
                name_quality="curated",
                unit="BN_USD",
                unit_ru="млрд $",
                frequency="annual",
                category_ru="Национальные счета",
                source="Международный валютный фонд",
                source_url="https://www.imf.org/en/Publications/WEO",
                history_start=date(2023, 1, 1),
                history_end=date(2025, 1, 1),
                points_count=3,
                is_listed=True,
            )
            weo_pc = WorldIndicator(
                country_id=de.id,
                provider="imf",
                code="de-weo-ngdpdpc",
                dataset_id="WEO",
                slice_json={"weo_code": "NGDPDPC"},
                slice_hash="weo-ngdpdpc",
                name_ru="Валовой внутренний продукт на душу населения в текущих ценах",
                name_quality="curated",
                unit="USD_PC",
                unit_ru="$ на человека",
                frequency="annual",
                category_ru="Национальные счета",
                source="Международный валютный фонд",
                source_url="https://www.imf.org/en/Publications/WEO",
                history_start=date(2023, 1, 1),
                history_end=date(2025, 1, 1),
                points_count=3,
                is_listed=True,
            )
            gdp_pc_eu = WorldIndicator(
                country_id=de.id,
                code="de-nama_10_pc-b1gq-pc-eu27-2020-hab-meur-cp",
                dataset_id="nama_10_pc",
                slice_json={
                    "freq": "A",
                    "unit": "PC_EU27_2020_HAB_MEUR_CP",
                    "na_item": "B1GQ",
                },
                slice_hash="gdppc1",
                name_ru="ВВП на душу населения относительно среднего по ЕС",
                name_quality="curated",
                unit="PC_EU27_2020_HAB_MEUR_CP",
                unit_ru="% от среднего по ЕС на душу населения",
                frequency="annual",
                category_ru="Национальные счета",
                source="Евростат",
                history_start=date(2024, 1, 1),
                history_end=date(2025, 1, 1),
                points_count=2,
                is_listed=True,
            )
            raw = WorldIndicator(
                country_id=de.id,
                code="de-zz_raw_stub",
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
            db.add_all([
                listed, listed_q, une_m, une_q, peer, no_year_value,
                population, budget, debt, gdp_annual, long_rate, activity,
                gdp_pc_eu, weo_gdp, weo_pc, raw,
            ])
            await db.flush()
            for ind in (listed, peer):
                for i in range(18):
                    y = 2024 + (i // 12)
                    m = (i % 12) + 1
                    db.add(WorldDataPoint(
                        indicator_id=ind.id,
                        date=date(y, m, 1),
                        value=100.0 + i,
                    ))
            for ind in (listed_q, une_q):
                for i in range(6):
                    y = 2024 + (i // 4)
                    q = (i % 4) + 1
                    db.add(WorldDataPoint(
                        indicator_id=ind.id,
                        date=date(y, (q - 1) * 3 + 1, 1),
                        value=100.0 + i,
                    ))
            for i in range(18):
                y = 2024 + (i // 12)
                m = (i % 12) + 1
                db.add(WorldDataPoint(
                    indicator_id=une_m.id,
                    date=date(y, m, 1),
                    value=3.0 + i * 0.1,
                ))
            # 4 страны-пира безработицы: годовой срез 2024 (не-дефолтный) получает
            # покрытие ≥ 5 (DE + 4 пира) и потому проходит порог sitemap, а 2025 —
            # дефолт (path-URL 301 на базу, в карту не идёт). FR/IT уже созданы
            # выше по фикстуре — переиспользуем их, ES/NL добавляем.
            existing = {"germany": de, "france": fr, "italy": it}

            def _ensure_country(code_, slug_, name_):
                if slug_ in existing:
                    return existing[slug_]
                c = WorldCountry(
                    code=code_, slug=slug_, name_ru=name_, name_en=name_.title(),
                    region_ru="Европа", sort_order=10 + len(existing),
                )
                db.add(c)
                existing[slug_] = c
                return c

            peer_unes = []
            peers = [
                ("FR", "france", "Франция", "fr-une_rt_m-total-sa-t-pc-act", 7.2),
                ("IT", "italy", "Италия", "it-une_rt_m-total-sa-t-pc-act", 6.4),
                ("ES", "spain", "Испания", "es-une_rt_m-total-sa-t-pc-act", 11.1),
                ("NL", "netherlands", "Нидерланды", "nl-une_rt_m-total-sa-t-pc-act", 3.6),
            ]
            for code_, slug_, name_, ind_code, base in peers:
                country = _ensure_country(code_, slug_, name_)
                peer_unes.append((country, ind_code, base))
            await db.flush()
            for country, code, base in peer_unes:
                db.add(WorldIndicator(
                    country_id=country.id,
                    code=code,
                    dataset_id="une_rt_m",
                    slice_json={"unit": "PC_ACT", "age": "TOTAL", "sex": "T", "s_adj": "SA"},
                    slice_hash=f"{code}-h",
                    name_ru="Безработица, % экономически активного населения, помесячно",
                    name_quality="curated",
                    unit="PC_ACT",
                    unit_ru="% экономически активного населения",
                    frequency="monthly",
                    category_ru="Рынок труда",
                    source="Евростат",
                    history_start=date(2024, 1, 1),
                    history_end=date(2025, 6, 1),
                    points_count=18,
                    is_listed=True,
                ))
                await db.flush()
                ind = (await db.execute(
                    select(WorldIndicator).where(WorldIndicator.code == code)
                )).scalar_one()
                for i in range(18):
                    y = 2024 + (i // 12)
                    m = (i % 12) + 1
                    db.add(WorldDataPoint(
                        indicator_id=ind.id,
                        date=date(y, m, 1),
                        value=base + i * 0.05,
                    ))
            for i in range(18):
                y = 2024 + (i // 12)
                m = (i % 12) + 1
                db.add(WorldDataPoint(
                    indicator_id=long_rate.id,
                    date=date(y, m, 1),
                    value=2.0 + i * 0.05,
                ))
            for ind, values in (
                (population, (83_000_000.0, 83_200_000.0)),
                (budget, (-2.1, -1.8)),
                (gdp_annual, (3_200_000.0, 3_250_000.0)),
                (activity, (78.1, 78.4)),
                (gdp_pc_eu, (122.0, 123.5)),
                (debt, (63.7, 62.5)),
                (weo_gdp, (4563.5, 4684.2, 5048.1)),
                (weo_pc, (54500.0, 55800.0, 60100.0)),
            ):
                for i, value in enumerate(values):
                    db.add(WorldDataPoint(
                        indicator_id=ind.id,
                        date=date(2024 + i, 1, 1),
                        value=value,
                    ))
            for i in range(8):
                db.add(WorldDataPoint(
                    indicator_id=raw.id,
                    date=date(2024, i + 1, 1),
                    value=1.0 + i,
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


def _breadcrumb_names(html: str) -> list[str]:
    for block in _jsonld(html):
        if block.get("@type") == "BreadcrumbList":
            items = sorted(
                block["itemListElement"], key=lambda x: x["position"]
            )
            return [it["name"] for it in items]
    return []


def _visible_root(html: str) -> str:
    # Vite-shell в тестах может отсутствовать — ищем .seo-page напрямую.
    body = re.search(r'<div class="seo-page">(.*)</div>\s*(?:<script|</div>)', html, re.S)
    if not body:
        body = re.search(r'<div id="root">(.*)</div>', html, re.S)
    assert body
    visible = re.sub(r"<script[^>]*>.*?</script>", "", body.group(1), flags=re.S)
    return visible


def test_seo_world_home_redirects_to_apex(world_seo_client):
    """Витрина мира снята: карта, рейтинг и каталог стран живут на главной."""
    r = world_seo_client.get("/seo/world", follow_redirects=False)
    assert r.status_code == 301
    assert r.headers["location"] == "/"


def test_seo_world_country(world_seo_client):
    r = world_seo_client.get("/seo/world/germany")
    assert r.status_code == 200
    html = r.text
    assert "Экономика Германии" in html
    title = re.search(r"<title>([^<]+)</title>", html).group(1)
    assert "Германии" in title
    for leak in ("Eurostat", "SDMX", "dataflow", "prc_hicp"):
        assert leak not in title
    assert 'src="/og/world/germany.png"' in html
    assert any("ImageObject" in json.dumps(b) for b in _jsonld(html))
    crumbs = _breadcrumb_names(html)
    assert crumbs == ["Главная", "Германия"]
    assert crumbs[0] == "Главная"

    # S4: блок «Источник данных» — дата последнего значения + официальные
    # сайты ведомств (Eurostat + IMF: у страны есть национальный WEO-ряд).
    source_section = html.split("<h2>Источник данных</h2>", 1)[1].split("</section>", 1)[0]
    assert "Данные на" in source_section
    assert 'href="https://ec.europa.eu/eurostat"' in source_section
    assert 'href="https://www.imf.org"' in source_section
    # Датированная срезка в блоке: «Данные на <месяц> <год>» без дня —
    # месячный индекс не привязан к конкретной дате.
    assert re.search(r"Данные на [а-яё]+ \d{4}", source_section)


def test_seo_world_country_locale_en(world_seo_client):
    r = world_seo_client.get("/seo/world/germany?preview_locale=en")
    assert r.status_code == 200
    html = r.text
    title = re.search(r"<title>([^<]+)</title>", html).group(1)
    assert title == "Economy of Germany: statistics and indicators"
    assert not re.search(r"[А-Яа-яЁё]", title)
    assert "<h1>Economy of Germany: statistics and indicators</h1>" in html
    assert "Eurostat" in html
    assert "Евростат" not in re.search(r"<h1>[^<]+</h1>", html).group(0)
    # RU regression intact without preview
    r_ru = world_seo_client.get("/seo/world/germany")
    assert "Экономика Германии" in r_ru.text


def test_seo_world_indicator(world_seo_client):
    code = "de-prc_hicp_midx-cp00-i15"
    r = world_seo_client.get(f"/seo/world/germany/{code}")
    assert r.status_code == 200
    html = r.text
    assert "Гармонизированный индекс потребительских цен" in html
    # H1: показатель в предложном падеже страны, без суффикса частоты
    assert "<h1>Гармонизированный индекс потребительских цен в Германии</h1>" in html
    assert "помесячно" not in re.search(r"<h1>[^<]+</h1>", html).group(0)
    assert "Германии" in html
    assert "Евростат" in html
    assert "по стране" not in html
    assert "в стране" not in html
    assert f'src="/og/germany/{code}.png"' in html
    assert "seo-chart" in html
    assert "117" in html  # последнее значение 100+17
    blocks = _jsonld(html)
    assert any(b.get("@type") == "Dataset" for b in blocks)
    assert any(b.get("@type") == "ImageObject" for b in blocks)
    ds = next(b for b in blocks if b.get("@type") == "Dataset")
    assert "temporalCoverage" in ds
    crumbs = _breadcrumb_names(html)
    assert crumbs[0] == "Главная"
    assert crumbs[1] == "Германия"
    assert "потребительских цен" in crumbs[2]
    assert 'href="/france"' in html or "/france/" in html
    visible = _visible_root(html)
    for leak in ("Eurostat", "SDMX", "dataflow"):
        assert leak not in visible

    # S4: блок источников индикатора — датированная срезка (ежемесячный ряд:
    # «Данные на …») + официальная ссылка на специфичный источник ряда
    # (databrowser), подписи выровнены.
    source_section = html.split("<h2>Источник данных</h2>", 1)[1].split("</section>", 1)[0]
    assert "Данные на июнь 2025" in source_section
    assert 'href="https://ec.europa.eu/eurostat/databrowser/view/prc_hicp_midx"' in source_section


def test_seo_world_unemployment_freq_links_and_301(world_seo_client):
    primary = "de-une_rt_m-total-sa-t-pc-act"
    quarterly = "de-une_rt_q-y15-74-sa-t-pc-act"

    r = world_seo_client.get(f"/seo/world/germany/{primary}")
    assert r.status_code == 200
    html = r.text
    assert "<h1>Безработица, % экономически активного населения в Германии</h1>" in html
    assert "mode=level-monthly" in html
    assert "mode=level-quarterly" in html
    assert "Частота наблюдений" in html
    assert "по стране" not in html
    assert "в стране" not in html

    redir = world_seo_client.get(
        f"/seo/world/germany/{quarterly}", follow_redirects=False
    )
    assert redir.status_code == 301
    loc = redir.headers["location"]
    assert f"/germany/indicator/{primary}" in loc
    assert "mode=level-quarterly" in loc


def test_seo_world_rating(world_seo_client):
    r = world_seo_client.get("/seo/world/rating/hicp-index")
    assert r.status_code == 200
    html = r.text
    assert "Рейтинг стран по изменению потребительских цен за год" in html
    assert "базовые периоды национальных индексов" in html
    assert 'canonical" href="https://forecasteconomy.com/world/rating/hicp-index"' in html
    assert 'src="/og/world/rating/hicp-index.png"' in html
    assert "seo-chart" in html
    assert "Германия" in html
    assert "Франция" in html
    assert "Италия" in html
    assert "Страны без данных" in html

    blocks = _jsonld(html)
    assert any(b.get("@type") == "ImageObject" for b in blocks)
    item_list = next(b for b in blocks if b.get("@type") == "ItemList")
    assert item_list["numberOfItems"] == 2
    assert item_list["itemListElement"][0]["position"] == 1
    assert "Германия" in item_list["itemListElement"][0]["name"]
    assert _breadcrumb_names(html) == [
        "Главная",
        "Рейтинг стран",
        "Изменение потребительских цен за год",
    ]

    visible = _visible_root(html)
    for leak in ("Eurostat", "SDMX", "dataflow", "concept", "provider", "dataset"):
        assert leak not in visible

    # S4: блок «Источник данных» — датированная срезка + официальный сайт
    # ведомства (Eurostat-ряды среза), единый паттерн с уровнем страны/индикатора.
    assert "<h2>Источник данных</h2>" in html
    source_section = html.split("<h2>Источник данных</h2>", 1)[1]
    source_section = source_section.split("</section>", 1)[0]
    assert "Данные на" in source_section  # дата последнего среза (last_date)
    assert 'href="https://ec.europa.eu/eurostat"' in source_section
    assert "<h2>Источник</h2>" not in html  # подписи выровнены
    # Датированная срезка блока — месяц плитки «Последняя дата в срезе»
    # (в блоке источников без дня: месячный индекс не привязан к дате).
    # «1 июня 2025» → родительный падеж в плитке vs именительный в подписи.
    tile_date_text = re.search(
        r"Последняя дата в срезе</span><b>([^<]+)</b>", html
    ).group(1)
    tile_year = tile_date_text.split()[-1]
    assert f"2025" == tile_year or tile_year in source_section
    assert re.search(r"Данные на [а-яё]+ \d{4}", source_section)


def test_seo_world_rating_default_redirect(world_seo_client):
    r = world_seo_client.get("/seo/world/rating", follow_redirects=False)
    assert r.status_code == 301
    assert r.headers["location"].endswith("/world/rating/gdp-usd")


def test_seo_world_rating_year_query_301_to_path(world_seo_client):
    """Легаси ?year= → 301 сразу в конечную точку (Фаза 10: один канон на год)."""
    # hicp-index в фикстуре имеет единственный год 2025 (дефолт) → 301 на базу.
    r = world_seo_client.get(
        "/seo/world/rating/hicp-index?year=2025", follow_redirects=False
    )
    assert r.status_code == 301
    assert r.headers["location"].endswith("/world/rating/hicp-index")
    # Не-дефолтный год unemployment-rate → 301 на path-канон.
    r2 = world_seo_client.get(
        "/seo/world/rating/unemployment-rate?year=2024", follow_redirects=False
    )
    assert r2.status_code == 301
    assert r2.headers["location"].endswith("/world/rating/unemployment-rate/2024")


def test_seo_world_rating_year_path_default_301_to_base(world_seo_client):
    """Path-URL дефолтного года — 301 на базу: база и есть его self-canonical."""
    r = world_seo_client.get(
        "/seo/world/rating/unemployment-rate/2025", follow_redirects=False
    )
    assert r.status_code == 301
    assert r.headers["location"].endswith("/world/rating/unemployment-rate")


def test_seo_world_rating_year_path_200(world_seo_client):
    """Path-URL не-дефолтного года — 200 с self-canonical на path."""
    r = world_seo_client.get("/seo/world/rating/unemployment-rate/2024")
    assert r.status_code == 200
    html = r.text
    assert (
        'canonical" href="https://forecasteconomy.com/world/rating/unemployment-rate/2024"'
        in html
    )
    # Ссылки «Другие годы» — без ?year=.
    assert "?year=" not in html


def test_seo_world_rating_year_without_data_404(world_seo_client):
    """Год без данных — честная 404, а не контент чужого года (софт-404)."""
    r = world_seo_client.get("/seo/world/rating/hicp-index/2024")
    assert r.status_code == 404
    r2 = world_seo_client.get("/seo/world/rating/unemployment-rate/2019")
    assert r2.status_code == 404


def test_seo_world_rating_year_og_matches_year(world_seo_client):
    """Годовая страница ссылается на OG-картинку своего года, база — на дефолт."""
    page = world_seo_client.get("/seo/world/rating/unemployment-rate/2024")
    assert page.status_code == 200
    assert "/og/world/rating/unemployment-rate/2024.png" in page.text
    base = world_seo_client.get("/seo/world/rating/unemployment-rate")
    assert base.status_code == 200
    assert "/og/world/rating/unemployment-rate.png" in base.text
    # Годовая OG-картинка существует и отдаёт PNG; чужой год — 404.
    og = world_seo_client.get("/api/v1/og-image/world-rating/unemployment-rate/2024.png")
    assert og.status_code == 200
    assert og.headers["content-type"] == "image/png"
    og_missing = world_seo_client.get("/api/v1/og-image/world-rating/hicp-index/2024.png")
    assert og_missing.status_code == 404


def test_sitemap_includes_world_rating_years(world_seo_client):
    """Годовые рейтинги в sitemap: не-дефолтные path-годы; дефолт не дублируется."""
    r = world_seo_client.get("/sitemap-world-ratings.xml")
    assert r.status_code == 200
    # Дефолтный (свежий) год представлен базой, не path-URL.
    assert "https://forecasteconomy.com/world/rating/hicp-index/2025" not in r.text
    assert "https://forecasteconomy.com/world/rating/unemployment-rate/2024" in r.text
    assert "https://forecasteconomy.com/world/rating/unemployment-rate/2025" not in r.text
    assert "?year=" not in r.text


def test_sitemap_rating_year_min_coverage(world_seo_client):
    """Годы рейтинга с покрытием < 5 стран — тонкий контент, в sitemap не идут.

    Нац. ряды (например, CPI Канады с 1914-го) дают срезы года с 1-2 странами;
    страницы остаются честными 200 по прямому URL, но не навязываются поисковику.
    """
    from app.services.site_urls import _RATING_YEAR_MIN_COUNTRIES

    assert _RATING_YEAR_MIN_COUNTRIES == 5
    r = world_seo_client.get("/sitemap-world-ratings.xml")
    assert r.status_code == 200
    for m in re.finditer(
        r"https://forecasteconomy\.com/world/rating/([a-z0-9-]+)/(\d{4})", r.text
    ):
        concept_slug, year = m.group(1), int(m.group(2))
        page = world_seo_client.get(f"/seo/world/rating/{concept_slug}/{year}")
        assert page.status_code == 200
        # Строк таблицы рейтинга ≥ 5 (min coverage) — проверяем счётчик стран
        # в ItemList JSON-LD (numberOfItems = число стран среза).
        jsonld = _jsonld(page.text)
        counts = [
            b.get("numberOfItems")
            for b in jsonld
            if b.get("@type") == "ItemList"
        ]
        assert counts and all(c >= _RATING_YEAR_MIN_COUNTRIES for c in counts), (
            concept_slug, year, counts,
        )


def test_world_rating_surface_nonempty_and_gated(world_seo_client):
    """Рейтинг by construction: только surface=rating, и у каждого снапшот непустой."""
    from app.data.world_concepts import WORLD_CONCEPTS

    rating_slugs = {
        concept.slug
        for concept in WORLD_CONCEPTS
        if "rating" in concept.enabled_surfaces
    }
    assert rating_slugs == {
        "hicp-index",
        "unemployment-rate",
        "budget-balance-gdp",
        "government-debt-gdp",
        "population",
        "long-term-interest-rate",
        "activity-rate",
        "gdp-per-capita-eu",
        "gdp-usd",
        "gdp-per-capita-usd",
    }
    assert "gdp-volume-annual" not in rating_slugs
    assert "gdp-volume-quarterly" not in rating_slugs

    catalog = world_seo_client.get("/api/v1/world/rating/concepts")
    assert catalog.status_code == 200
    catalog_slugs = {item["slug"] for item in catalog.json()["concepts"]}
    assert catalog_slugs == rating_slugs

    for slug in sorted(rating_slugs):
        snapshot = world_seo_client.get(f"/api/v1/world/compare/snapshot/{slug}")
        assert snapshot.status_code == 200, slug
        assert snapshot.json()["items"], f"пустой снапшот рейтинга: {slug}"
        ssr = world_seo_client.get(f"/seo/world/rating/{slug}")
        assert ssr.status_code == 200, slug
        assert "<table>" in ssr.text

    for slug in ("gdp-volume-annual", "gdp-volume-quarterly"):
        assert world_seo_client.get(f"/seo/world/rating/{slug}").status_code == 404
        assert slug not in catalog_slugs


def test_seo_world_unlisted_404(world_seo_client):
    assert world_seo_client.get("/seo/world/germany/de-zz_raw_stub").status_code == 404
    assert world_seo_client.get("/seo/world/no-such-country").status_code == 404


def test_world_sitemap_listed_only(world_seo_client):
    idx = world_seo_client.get("/sitemap.xml")
    assert idx.status_code == 200
    assert "sitemap-world.xml" in idx.text
    assert "sitemap-world-ratings.xml" in idx.text
    assert "sitemap-world-indicators-1.xml" in idx.text

    world = world_seo_client.get("/sitemap-world.xml")
    assert world.status_code == 200
    assert "https://forecasteconomy.com/germany" in world.text
    assert "https://forecasteconomy.com/france" in world.text

    ratings = world_seo_client.get("/sitemap-world-ratings.xml")
    assert ratings.status_code == 200
    assert "https://forecasteconomy.com/world/rating/hicp-index" in ratings.text
    assert "https://forecasteconomy.com/world/rating/unemployment-rate" in ratings.text
    assert "https://forecasteconomy.com/world/rating/population" in ratings.text
    assert "https://forecasteconomy.com/world/rating/budget-balance-gdp" in ratings.text
    assert "https://forecasteconomy.com/world/rating/government-debt-gdp" in ratings.text
    assert "https://forecasteconomy.com/world/rating/long-term-interest-rate" in ratings.text
    assert "https://forecasteconomy.com/world/rating/activity-rate" in ratings.text
    assert "https://forecasteconomy.com/world/rating/gdp-per-capita-eu" in ratings.text
    assert "https://forecasteconomy.com/world/rating/gdp-usd" in ratings.text
    assert "https://forecasteconomy.com/world/rating/gdp-per-capita-usd" in ratings.text
    assert "gdp-volume-annual" not in ratings.text
    assert "gdp-volume-quarterly" not in ratings.text

    inds = world_seo_client.get("/sitemap-world-indicators-1.xml")
    assert inds.status_code == 200
    assert "/germany/indicator/de-prc_hicp_midx-cp00-i15" in inds.text
    assert "/germany/indicator/de-une_rt_m-total-sa-t-pc-act" in inds.text
    # вторичная частота не в индексе
    assert "de-une_rt_q-y15-74-sa-t-pc-act" not in inds.text
    assert "de-zz_raw_stub" not in inds.text
    assert "<lastmod>2025-" in inds.text

def test_world_og_png(world_seo_client):
    code = "de-prc_hicp_midx-cp00-i15"
    country = world_seo_client.get("/api/v1/og-image/world/germany.png")
    assert country.status_code == 200
    assert country.headers["content-type"].startswith("image/png")
    assert country.content[:8] == b"\x89PNG\r\n\x1a\n"

    card = world_seo_client.get(f"/api/v1/og-image/world/germany/{code}.png")
    assert card.status_code == 200
    assert card.headers["content-type"].startswith("image/png")
    assert card.content[:8] == b"\x89PNG\r\n\x1a\n"

    rating = world_seo_client.get("/api/v1/og-image/world-rating/hicp-index.png")
    assert rating.status_code == 200
    assert rating.headers["content-type"].startswith("image/png")
    assert rating.content[:8] == b"\x89PNG\r\n\x1a\n"

    assert world_seo_client.get(
        "/api/v1/og-image/world/germany/de-zz_raw_stub.png"
    ).status_code == 404


def test_world_og_rating_locale_cache_and_labels(world_seo_client):
    """EN-локализация OG-постеров: разные ключи кэша и разные подписи.

    Регресс на залипание кэша: ключ world-rating раньше не включал локаль,
    а имя концепта строилось по get_locale() — первый запрос «вымораживал»
    язык картинки для всех последующих.
    """
    # Локаль bind'ится LocaleMiddleware на запрос: EN — заголовком X-FE-Locale.
    ru = world_seo_client.get("/api/v1/og-image/world-rating/hicp-index.png")
    assert ru.status_code == 200
    en = world_seo_client.get(
        "/api/v1/og-image/world-rating/hicp-index.png",
        headers={"X-FE-Locale": "en"},
    )
    assert en.status_code == 200
    assert en.content != ru.content  # не та же залитая картинка

    # Подписи рендера по локали: RU «рейтинг стран», EN «country ranking»
    from app.services.og_image import render_world_rating_og

    rows = [("Germany", 101.4), ("France", 100.9), ("Italy", 100.2)]
    png_ru = render_world_rating_og(
        name="Гармонизированный индекс потребительских цен", year=2025,
        unit="изменение за год, %", rows=rows, total=30,
        order_label="по убыванию",
    )
    png_en = render_world_rating_og(
        name="Harmonised index of consumer prices", year=2025,
        unit="%, year-over-year change", rows=rows, total=30,
        order_label="descending", locale="en",
    )
    assert png_ru != png_en

    # Ключи кэша различаются по локали — картинка EN не перезаписывает RU.
    from app.services.og_image import _CACHE

    assert "world-rating:ru:hicp-index" in _CACHE
    assert "world-rating:en:hicp-index" in _CACHE


@pytest.fixture
def russia_gdp_method_client(auth_env):
    """Каталог с национальными рядами расчёта ВВП РФ + один Eurostat-ряд.

    Мокает годовые ряды `gdp-nominal-annual`, `usd-rub-avg-year` и
    `population` (indicators) — приоритет национального расчёта в рейтинге
    gdp-usd/gdp-per-capita-usd перед МВФ-рядом (у МВФ-ряда России в этой
    фикстуре нет вовсе).
    """
    import asyncio

    from app.models import Indicator, IndicatorData

    async def _seed():
        async with auth_env["session_maker"]() as db:
            rows = {
                "gdp-nominal-annual": [
                    (date(2024, 1, 1), 200_039.0),
                    (date(2025, 1, 1), 214_261.1),
                ],
                "usd-rub-avg-year": [
                    (date(2024, 1, 1), 92.6567),
                    (date(2025, 1, 1), 83.2108),
                ],
                "population": [
                    (date(2024, 1, 1), 146.15),
                    (date(2025, 1, 1), 146.12),
                ],
            }
            for code, points in rows.items():
                ind = Indicator(
                    code=code,
                    name="Тестовый ряд расчёта",
                    unit="млрд руб." if "gdp" in code else "руб. за долл.",
                    frequency="annual",
                    source="Росстат",
                    parser_type="derived",
                    is_active=True,
                    is_listed=True,
                )
                db.add(ind)
                await db.flush()
                for d, value in points:
                    db.add(IndicatorData(
                        indicator_id=ind.id, date=d, value=value,
                    ))
            await db.commit()

    asyncio.run(_seed())
    with TestClient(auth_env["app"]) as tc:
        yield tc


def test_russia_gdp_ranking_uses_national_method(russia_gdp_method_client):
    """ВВП России в рейтинге — национальный расчёт: млрд руб. / среднегодовой курс.

    Значение = Росстат × курс Банка России, источник подписан российскими
    ведомствами; незакрывшийся год не попадает в снапшот. МВФ-ряд России
    в фикстуре нет — значение возникает только национальным расчётом.
    """
    from datetime import date as date_cls

    snap = russia_gdp_method_client.get("/api/v1/world/compare/snapshot/gdp-usd")
    assert snap.status_code == 200
    ru = next(
        (i for i in snap.json()["items"] if i["country_code"] == "RU"), None,
    )
    assert ru is not None
    # Снапшот берёт последний завершённый год (2025): 214261,1 млрд руб. /
    # 83,2108 руб. за доллар.
    expected = 214_261.1 / 83.2108
    assert ru["value"] == pytest.approx(expected, rel=1e-4)
    assert ru["indicator_code"] == "gdp-nominal-annual"
    assert ru["source"] == "Росстат, Банк России"
    # Только завершённые годы: текущий год в снапшот не попадает.
    assert date_cls.fromisoformat(ru["date"]).year == 2025
    assert date_cls.fromisoformat(ru["date"]).year < date_cls.today().year

    pc = russia_gdp_method_client.get(
        "/api/v1/world/compare/snapshot/gdp-per-capita-usd"
    )
    assert pc.status_code == 200
    ru_pc = next(
        (i for i in pc.json()["items"] if i["country_code"] == "RU"), None,
    )
    assert ru_pc is not None
    assert ru_pc["value"] == pytest.approx(expected * 1e9 / 146.12e6, rel=1e-3)
    assert ru_pc["source"] == "Росстат, Банк России"
