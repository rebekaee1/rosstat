"""EN-каталог hreflang (app/data/i18n/en_catalog.py) + hreflang-голова SSR.

Проверки:
- has_en_path: точные пути и префиксы фаз 1–8 не сломаны; новые формы фаз
  3–6 — годовой лендинг страны /{country}/indicator/{code}/{year} (страна
  валидируется по статическому каталогу слагов), месячный лендинг РФ
  /russia/indicator/{code}/{year}-{mm}, годовой лендинг региона
  /russia/region/{slug}/{code}/{year}, годовой рейтинг мира
  /world/rating/{concept}/{year}, сравнения стран /{a}-vs-{b}/{concept};
- False для несуществующих стран/мусорных форм (hreflang не в 404);
- SSR-страницы новых типов с monkeypatch apex_locale_en=True содержат
  hreflang ru/en/x-default; при False — блок отсутствует.

Эталон стиля — test_seo_world_year.py / test_seo_regional_year.py.
"""

from __future__ import annotations

import asyncio
import json
import re
from datetime import date

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# has_en_path: формы фаз 3–9B
# ---------------------------------------------------------------------------


def test_catalog_russia_indicator_month_form_covered():
    """Месячный лендинг РФ /russia/indicator/{code}/{year}-{mm} покрыт
    префиксом /russia/indicator/ по форме: твин объявляется на той же
    основе, что и годовой лендинг."""
    from app.data.i18n.en_catalog import has_en_path

    assert has_en_path("/russia/indicator/cpi/2025-06") is True
    assert has_en_path("/russia/indicator/cpi/2025-1") is True  # форма, не валидация


def test_catalog_world_country_indicator_year_validates_country():
    """Годовой лендинг мира: EN объявляем только странам каталога слагов."""
    from app.data.i18n.en_catalog import has_en_path

    assert has_en_path("/germany/indicator/cpi/2023") is True
    assert has_en_path("/united-states/indicator/us-cpi-all/2024") is True
    # Не страна каталога (или произвольный первый сегмент) — EN не обещаем.
    assert has_en_path("/not-a-country/indicator/x/2023") is False
    assert has_en_path("/not-a-country") is False


def test_catalog_world_country_indicator_requires_indicator_segment():
    """Валидация страны распространяется только на /{country}/indicator/…:
    прочие ветки первого сегмента (/{country}/category/…) каталогом не
    покрыты — их EN-твинов ещё нет."""
    from app.data.i18n.en_catalog import has_en_path

    assert has_en_path("/germany") is False
    assert has_en_path("/germany/category/prices") is False


def test_catalog_region_year_and_world_rating_year_prefixes():
    """Годовой лендинг региона и годовой рейтинг мира покрыты префиксами."""
    from app.data.i18n.en_catalog import has_en_path

    assert has_en_path("/russia/region/moskva/chislennost-naseleniya/2023") is True
    assert has_en_path("/world/rating/population/2024") is True


def test_catalog_country_vs_country_pairs():
    """Сравнения стран: пара валидируется по каталогу слагов, разрез — по
    последнему «-vs-» (слаг с дефисом не разъедается)."""
    from app.data.i18n.en_catalog import has_en_path

    assert has_en_path("/russia-vs-germany/gdp") is True
    assert has_en_path("/germany-vs-france/unemployment-rate") is True
    # Слаг с дефисом: rsplit по последнему «-vs-».
    assert has_en_path("/united-states-vs-germany/population") is True
    # Не-страновые «-vs-» сегменты не объявляют EN.
    assert has_en_path("/not-a-country-vs-germany/gdp") is False
    assert has_en_path("/germany-vs-not-a-country/gdp") is False
    # Нет второго сегмента-концепта → форма не сравнение стран.
    assert has_en_path("/russia-vs-germany") is False


def test_catalog_existing_exact_paths_not_broken():
    """Точные пути и старые префиксы не сломаны (регресс на фазы 1–8)."""
    from app.data.i18n.en_catalog import has_en_path

    assert has_en_path("/") is True
    assert has_en_path("/about") is True
    assert has_en_path("/russia") is True
    assert has_en_path("/russia/today/cpi") is True
    assert has_en_path("/russia/indicator/cpi") is True
    assert has_en_path("/russia/indicator/cpi/2024") is True
    assert has_en_path("/russia/region-rating/chislennost-naseleniya") is True
    assert has_en_path("/russia/region-vs/moskva-vs-sankt-peterburg") is True
    assert has_en_path("/world/rating/population") is True


def test_hreflang_does_not_claim_random_path():
    from app.data.i18n.en_catalog import has_en_path

    assert has_en_path("/this-path-does-not-exist-xyz") is False
    assert has_en_path("/this-path-does-not-exist-xyz/indicator/x/2023") is False


def test_country_slugs_static_and_cached():
    """Каталог слагов — статический frozenset (без БД), кэшируется."""
    from app.data.i18n.en_catalog import _country_slugs

    slugs = _country_slugs()
    assert isinstance(slugs, frozenset)
    assert "germany" in slugs
    assert "united-states" in slugs
    assert "russia" in slugs
    assert _country_slugs() is slugs  # lru_cache: один и тот же объект


# ---------------------------------------------------------------------------
# hreflang-голова на SSR-страницах новых типов
# ---------------------------------------------------------------------------


def _hreflang_links(html: str) -> list[str]:
    return re.findall(
        r'<link rel="alternate" hreflang="([^"]+)" href="([^"]+)"', html
    )


@pytest.fixture
def world_year_hreflang_client(auth_env, monkeypatch):
    """Фикстура test_seo_world_year (сокращённая) с включённым cutover-флагом."""
    from app.config import settings

    monkeypatch.setattr(settings, "apex_locale_en", True)

    async def _seed():
        from app.models import WorldCountry, WorldDataPoint, WorldIndicator

        async with auth_env["session_maker"]() as db:
            de = WorldCountry(
                code="DE", slug="germany", name_ru="Германия",
                name_en="Germany", region_ru="Европа", sort_order=1,
            )
            fr = WorldCountry(
                code="FR", slug="france", name_ru="Франция",
                name_en="France", region_ru="Европа", sort_order=2,
            )
            db.add_all([de, fr])
            await db.flush()

            annual = WorldIndicator(
                country_id=de.id,
                code="de-demo_pjan-total-t-nr",
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
            hicp_de = WorldIndicator(
                country_id=de.id,
                code="de-prc_hicp_midx-cp00-i15",
                dataset_id="prc_hicp_midx",
                slice_json={"unit": "I15", "coicop": "CP00", "freq": "M"},
                slice_hash="de-hicp",
                name_ru="Гармонизированный индекс потребительских цен, помесячно",
                name_en="HICP",
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
            hicp_fr = WorldIndicator(
                country_id=fr.id,
                code="fr-prc_hicp_midx-cp00-i15",
                dataset_id="prc_hicp_midx",
                slice_json={"unit": "I15", "coicop": "CP00", "freq": "M"},
                slice_hash="fr-hicp",
                name_ru="Гармонизированный индекс потребительских цен, помесячно",
                name_en="HICP",
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
            fr_pop = WorldIndicator(
                country_id=fr.id,
                code="fr-demo_pjan-total-t-nr",
                dataset_id="demo_pjan",
                slice_json={"unit": "NR", "age": "TOTAL", "sex": "T"},
                slice_hash="pop2",
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
            une_de = WorldIndicator(
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
                history_start=date(2024, 1, 1),
                history_end=date(2025, 6, 1),
                points_count=18,
                is_listed=True,
            )
            une_fr = WorldIndicator(
                country_id=fr.id,
                code="fr-une_rt_m-total-sa-t-pc-act",
                dataset_id="une_rt_m",
                slice_json={"unit": "PC_ACT", "age": "TOTAL", "sex": "T", "s_adj": "SA"},
                slice_hash="une2",
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
            )
            db.add_all([annual, hicp_de, hicp_fr, fr_pop, une_de, une_fr])
            await db.flush()

            for i in range(5):
                db.add(WorldDataPoint(
                    indicator_id=annual.id,
                    date=date(2020 + i, 1, 1),
                    value=83_000_000.0 + i * 100_000,
                ))
                db.add(WorldDataPoint(
                    indicator_id=fr_pop.id,
                    date=date(2020 + i, 1, 1),
                    value=68_000_000.0 + i * 100_000,
                ))
            for ind in (hicp_de, hicp_fr):
                for i in range(18):
                    db.add(WorldDataPoint(
                        indicator_id=ind.id,
                        date=date(2024 + i // 12, i % 12 + 1, 1),
                        value=100.0 + i,
                    ))
            # Безработица в реалистичном масштабе %: на значениях тесты не
            # завязаны, но фикстура не должна показывать 118% безработицы.
            for ind, base in ((une_de, 3.1), (une_fr, 7.2)):
                for i in range(18):
                    db.add(WorldDataPoint(
                        indicator_id=ind.id,
                        date=date(2024 + i // 12, i % 12 + 1, 1),
                        value=base + i * 0.05,
                    ))
            await db.commit()

    asyncio.run(_seed())
    with TestClient(auth_env["app"]) as tc:
        yield tc


def test_hreflang_world_indicator_year_page(world_year_hreflang_client, monkeypatch):
    """Годовой лендинг мира: hreflang ru/en/x-default при cutover; без флага
    (переключение на лету, кэш ключуется на origin+локаль) — блока нет."""
    from app.config import settings

    r = world_year_hreflang_client.get(
        "/seo/world-indicator-year/germany/de-demo_pjan-total-t-nr/2023"
    )
    assert r.status_code == 200
    pairs = dict(_hreflang_links(r.text))
    assert pairs.get("ru") == (
        "https://ru.forecasteconomy.com/germany/indicator/de-demo_pjan-total-t-nr/2023"
    )
    assert pairs.get("en") == (
        "https://forecasteconomy.com/germany/indicator/de-demo_pjan-total-t-nr/2023"
    )
    assert pairs.get("x-default") == pairs.get("en")

    monkeypatch.setattr(
        __import__("app.config", fromlist=["settings"]).settings,
        "apex_locale_en",
        False,
    )
    r2 = world_year_hreflang_client.get(
        "/seo/world-indicator-year/germany/de-demo_pjan-total-t-nr/2023"
    )
    assert r2.status_code == 200
    assert 'hreflang="en"' not in r2.text


def test_hreflang_world_vs_page(world_year_hreflang_client):
    """Сравнение стран: /{a}-vs-{b}/{concept} отдаёт hreflang-тройку.

    Канонический URL — отсортированная пара (france < germany): запрос в
    обратном порядке даёт 301 на канон, hreflang проверяем на каноне."""
    r = world_year_hreflang_client.get("/seo/world-vs/france-vs-germany/population")
    assert r.status_code == 200
    pairs = dict(_hreflang_links(r.text))
    assert pairs.get("ru") == "https://ru.forecasteconomy.com/france-vs-germany/population"
    assert pairs.get("en") == "https://forecasteconomy.com/france-vs-germany/population"
    assert pairs.get("x-default") == pairs.get("en")

    swapped = world_year_hreflang_client.get(
        "/seo/world-vs/germany-vs-france/population", follow_redirects=False
    )
    assert swapped.status_code == 301
    assert swapped.headers["location"].endswith("/france-vs-germany/population")


@pytest.fixture
def region_year_hreflang_client(auth_env, monkeypatch):
    """Фикстура test_seo_regional_year с включённым cutover-флагом."""
    from app.config import settings

    monkeypatch.setattr(settings, "apex_locale_en", True)

    async def _seed():
        from app.models import Region, RegionDataPoint, RegionIndicator

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
            db.add_all([moskva, tatarstan, perm])
            await db.flush()

            ind = RegionIndicator(
                code="chislennost-naseleniya",
                table_code="1.1",
                section_num=1,
                section_name="Население",
                name="Численность населения на 1 января",
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


def test_hreflang_region_year_page(region_year_hreflang_client, monkeypatch):
    """Годовой лендинг региона: hreflang-тройка при cutover; без флага — нет."""
    r = region_year_hreflang_client.get(
        "/seo/region-indicator-year/moskva/chislennost-naseleniya/2023"
    )
    assert r.status_code == 200
    pairs = dict(_hreflang_links(r.text))
    assert pairs.get("ru") == (
        "https://ru.forecasteconomy.com/russia/region/moskva/"
        "chislennost-naseleniya/2023"
    )
    assert pairs.get("en") == (
        "https://forecasteconomy.com/russia/region/moskva/"
        "chislennost-naseleniya/2023"
    )
    assert pairs.get("x-default") == pairs.get("en")

    from app.config import settings

    monkeypatch.setattr(settings, "apex_locale_en", False)
    r2 = region_year_hreflang_client.get(
        "/seo/region-indicator-year/moskva/chislennost-naseleniya/2023"
    )
    assert r2.status_code == 200
    assert 'hreflang="en"' not in r2.text


def test_hreflang_world_rating_year_page(world_year_hreflang_client, monkeypatch):
    """Годовой рейтинг мира: hreflang-тройка при cutover; без флага — нет.

    Канон-модель Фазы 10: path-URL дефолтного года 301 на базу, поэтому
    200 с тройкой проверяем на не-дефолтном 2024."""
    r = world_year_hreflang_client.get("/seo/world/rating/unemployment-rate/2024")
    assert r.status_code == 200
    pairs = dict(_hreflang_links(r.text))
    assert pairs.get("ru") == (
        "https://ru.forecasteconomy.com/world/rating/unemployment-rate/2024"
    )
    assert pairs.get("en") == (
        "https://forecasteconomy.com/world/rating/unemployment-rate/2024"
    )
    assert pairs.get("x-default") == pairs.get("en")

    from app.config import settings

    monkeypatch.setattr(settings, "apex_locale_en", False)
    r2 = world_year_hreflang_client.get("/seo/world/rating/unemployment-rate/2024")
    assert r2.status_code == 200
    assert 'hreflang="en"' not in r2.text

    # Дефолтный год в path — 301 на базу (один контент — один URL).
    default = world_year_hreflang_client.get(
        "/seo/world/rating/unemployment-rate/2025", follow_redirects=False
    )
    assert default.status_code == 301
    assert default.headers["location"].endswith("/world/rating/unemployment-rate")