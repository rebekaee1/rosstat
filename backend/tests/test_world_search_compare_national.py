"""T1/T2/T3 world.py: национальные CPI в compare, бейджи расчётных частот, поиск.

Герметично (auth_env: SQLite + fakeredis) — без внешних postgres/redis.
Национальные коды кроссворка берутся из реального
``world_concept_national.NATIONAL_CONCEPT_INDICATOR_CODES`` — тест одновременно
охраняет сам crosswalk от переименований.
"""

from __future__ import annotations

import pytest

from app.data.world_concept_national import national_codes_for_concept


def _hicp_concept():
    from app.data.world_concepts import CONCEPT_BY_SLUG

    return CONCEPT_BY_SLUG["hicp-index"]


# --- T1: национальные ряды в калькуляторе (compare catalog + series) --------


@pytest.fixture
def national_world_client(auth_env):
    """US + Австралия (национальные CPI) + Германия (eurostat HICP).

    У США рядом с национальным есть и unlisted eurostat-дубль — проверяем,
    что национальный имеет приоритет и 409 не возникает.
    """
    import asyncio
    from datetime import date
    from fastapi.testclient import TestClient
    from app.models import WorldCountry, WorldDataPoint, WorldIndicator

    async def _seed():
        async with auth_env["session_maker"]() as db:
            us = WorldCountry(
                code="US", slug="united-states", name_ru="США",
                name_en="United States", region_ru="Америка", sort_order=10,
            )
            au = WorldCountry(
                code="AU", slug="australia", name_ru="Австралия",
                name_en="Australia", region_ru="Океания", sort_order=11,
            )
            de = WorldCountry(
                code="DE", slug="germany", name_ru="Германия",
                name_en="Germany", region_ru="Европа", sort_order=1,
            )
            db.add_all([us, au, de])
            await db.flush()

            us_cpi = WorldIndicator(
                country_id=us.id,
                code="us-cpi-all",
                dataset_id="CPIAUCSL",
                slice_json={},
                slice_hash="us-cpi",
                name_ru="Индекс потребительских цен (CPI)",
                name_en="Consumer Price Index for All Urban Consumers",
                name_quality="curated",
                unit="INDEX",
                unit_ru="индекс (1982–84 = 100)",
                frequency="monthly",
                category_ru="Цены",
                source="ФРС Сент-Луиса (FRED)",
                history_start=date(2023, 1, 1),
                history_end=date(2025, 12, 1),
                points_count=36,
                is_listed=True,
            )
            # Eurostat-дубль US должен проиграть национальному ряду.
            us_hicp = WorldIndicator(
                country_id=us.id,
                code="us-prc_hicp_midx-cp00-i15",
                dataset_id="prc_hicp_midx",
                slice_json={"unit": "I15", "coicop": "CP00", "freq": "M"},
                slice_hash="us-hicp",
                name_ru="Гармонизированный индекс потребительских цен",
                name_en="HICP - monthly data (index)",
                name_quality="curated",
                unit="I15",
                unit_ru="индекс 2015=100",
                frequency="monthly",
                category_ru="Цены",
                source="Евростат",
                history_start=date(2024, 1, 1),
                history_end=date(2025, 12, 1),
                points_count=24,
                is_listed=False,
            )
            au_cpi = WorldIndicator(
                country_id=au.id,
                code="au-cpi-all",
                dataset_id="CPI",
                slice_json={},
                slice_hash="au-cpi",
                name_ru="Индекс потребительских цен",
                name_en="Consumer Price Index",
                name_quality="curated",
                unit="INDEX",
                unit_ru="индекс",
                frequency="quarterly",
                category_ru="Цены",
                source="Австралийское статистическое бюро",
                history_start=date(2024, 1, 1),
                history_end=date(2025, 10, 1),
                points_count=8,
                is_listed=True,
            )
            de_hicp = WorldIndicator(
                country_id=de.id,
                code="de-prc_hicp_midx-cp00-i15",
                dataset_id="prc_hicp_midx",
                slice_json={"unit": "I15", "coicop": "CP00", "freq": "M"},
                slice_hash="de-hicp",
                name_ru="Гармонизированный индекс потребительских цен",
                name_en="HICP - monthly data (index)",
                name_quality="curated",
                unit="I15",
                unit_ru="индекс 2015=100",
                frequency="monthly",
                category_ru="Цены",
                source="Евростат",
                history_start=date(2024, 1, 1),
                history_end=date(2025, 12, 1),
                points_count=24,
                is_listed=True,
            )
            db.add_all([us_cpi, us_hicp, au_cpi, de_hicp])
            await db.flush()

            for i in range(36):
                db.add(WorldDataPoint(
                    indicator_id=us_cpi.id,
                    date=date(2023 + i // 12, i % 12 + 1, 1),
                    value=300.0 + i * 0.5,
                ))
            for i in range(24):
                db.add(WorldDataPoint(
                    indicator_id=us_hicp.id,
                    date=date(2024 + i // 12, i % 12 + 1, 1),
                    value=100.0 + i * 0.2,
                ))
            for i in range(8):
                db.add(WorldDataPoint(
                    indicator_id=au_cpi.id,
                    date=date(2024 + i // 4, (i % 4) * 3 + 1, 1),
                    value=130.0 + i,
                ))
            for i in range(24):
                db.add(WorldDataPoint(
                    indicator_id=de_hicp.id,
                    date=date(2024 + i // 12, i % 12 + 1, 1),
                    value=110.0 + i * 0.2,
                ))
            await db.commit()

    asyncio.run(_seed())
    with TestClient(auth_env["app"]) as tc:
        yield tc


def test_compare_catalog_includes_national_cpi(national_world_client):
    body = national_world_client.get("/api/v1/world/compare/catalog").json()
    assert body["total"] >= 3
    hicp = [
        item for item in body["items"]
        if item["concept_slug"] == "hicp-index"
    ]
    by_country = {item["country_slug"]: item for item in hicp}

    assert {"united-states", "australia", "germany"} <= set(by_country)
    us = by_country["united-states"]
    assert us["indicator_code"] == "us-cpi-all"
    # Родной юнит из метаданных ряда, не eurostat-заглушка.
    assert "2015" not in us["unit"]
    au = by_country["australia"]
    assert au["indicator_code"] == "au-cpi-all"
    # Частота — родная для национального ряда.
    assert us["frequency"] == "monthly"
    assert au["frequency"] == "quarterly"


def test_compare_series_us_hicp_not_404(national_world_client):
    r = national_world_client.get("/api/v1/world/compare/series/united-states/hicp-index")
    assert r.status_code == 200
    body = r.json()
    assert body["meta"]["indicator_code"] == "us-cpi-all"
    assert body["meta"]["country_slug"] == "united-states"
    assert len(body["data"]) == 36
    assert body["data"][0]["value"] == 300.0


def test_compare_series_national_beats_eurostat_duplicate(national_world_client):
    # Национальный crosswalk приоритетнее eurostat-дубля (пусть даже unlisted):
    # никакого 409 «Неоднозначный состав ряда».
    r = national_world_client.get("/api/v1/world/compare/series/united-states/hicp-index")
    assert r.status_code == 200
    assert r.json()["meta"]["indicator_code"] == "us-cpi-all"


def test_compare_series_eurostat_country_unchanged(national_world_client):
    r = national_world_client.get("/api/v1/world/compare/series/germany/hicp-index")
    assert r.status_code == 200
    meta = r.json()["meta"]
    assert meta["indicator_code"] == "de-prc_hicp_midx-cp00-i15"
    assert meta["unit"] == "индекс 2015=100"


# --- T2: бейджи расчётных частот на плитках страны --------------------------


@pytest.fixture
def aggregation_world_client(auth_env):
    """Месячный индекс с политикой mean → quarterly/annual расчётные."""
    import asyncio
    from datetime import date
    from fastapi.testclient import TestClient
    from app.models import WorldCountry, WorldDataPoint, WorldIndicator

    async def _seed():
        async with auth_env["session_maker"]() as db:
            de = WorldCountry(
                code="DE", slug="germany", name_ru="Германия",
                name_en="Germany", region_ru="Европа", sort_order=1,
            )
            db.add(de)
            await db.flush()
            ind = WorldIndicator(
                country_id=de.id,
                code="de-prc_hicp_midx-cp00-i15",
                dataset_id="prc_hicp_midx",
                slice_json={"unit": "I15", "coicop": "CP00", "freq": "M"},
                slice_hash="abc",
                name_ru="Гармонизированный индекс потребительских цен",
                name_en="HICP - monthly data (index)",
                name_quality="curated",
                unit="I15",
                unit_ru="индекс 2015=100",
                frequency="monthly",
                category_ru="Цены",
                source="Евростат",
                history_start=date(2024, 1, 1),
                history_end=date(2026, 6, 1),
                points_count=30,
                is_listed=True,
            )
            db.add(ind)
            await db.flush()
            for i in range(30):
                db.add(WorldDataPoint(
                    indicator_id=ind.id,
                    date=date(2024 + i // 12, i % 12 + 1, 1),
                    value=100.0 + i,
                ))
            await db.commit()

    asyncio.run(_seed())
    with TestClient(auth_env["app"]) as tc:
        yield tc


def test_country_detail_aggregated_frequencies_badge(aggregation_world_client):
    body = aggregation_world_client.get("/api/v1/world/countries/germany").json()
    cats = [c for c in body["categories"] if c["name"] == "Цены"]
    assert cats, body["categories"]
    item = next(
        i for c in cats for i in c["indicators"]
        if i["code"] == "de-prc_hicp_midx-cp00-i15"
    )
    # Официальная частота одна; формат frequencies не изменился (список строк).
    assert item["frequencies"] == ["monthly"]
    assert all(isinstance(f, str) for f in item["frequencies"])
    # prc_hicp_midx/I15 — mean: quarterly и annual достижимы агрегацией.
    assert set(item["aggregated_frequencies"]) == {"quarterly", "annual"}


def test_aggregated_frequencies_absent_without_policy(auth_env):
    """Ряд без курируемой политики не получает расчётных частот."""
    from app.api.world import _aggregated_frequencies_for_card

    class FakeInd:
        frequency = "monthly"
        points_count = 100

        def __init__(self, dataset_id, unit):
            self.dataset_id = dataset_id
            self.unit = unit

    unpolicyable = [FakeInd("zz_unknown_flux", "")]
    assert _aggregated_frequencies_for_card(unpolicyable) == []
    policyable = [FakeInd("prc_hicp_midx", "I15")]
    assert _aggregated_frequencies_for_card(policyable) == ["quarterly", "annual"]


# --- T3: поиск ---------------------------------------------------------------


@pytest.fixture
def search_world_client(auth_env):
    """Цепочка рангов для весового ранжирования (ASCII — SQLite не фолдит кириллицу).

    Ожидаемый порядок на «gas»:
      gas-pipeline-throughput (код-префикс) →
      xx-gas-reserves (вхождение в код) →
      gas storage levels (префикс имени_en) →
      energy widget (вхождение в имя_en)
    """
    import asyncio
    from datetime import date
    from fastapi.testclient import TestClient
    from app.models import WorldCountry, WorldDataPoint, WorldIndicator

    async def _seed():
        async with auth_env["session_maker"]() as db:
            xx = WorldCountry(
                code="XX", slug="testland", name_ru="Тестланд",
                name_en="Testland", region_ru="Тест", sort_order=99,
            )
            db.add(xx)
            await db.flush()

            def _ind(code, name_en, *, listed=True, kw=None):
                return WorldIndicator(
                    country_id=xx.id,
                    code=code,
                    dataset_id="zz_misc",
                    slice_json={},
                    slice_hash=f"h-{code}",
                    name_ru=f"Показатель {code}",
                    name_en=name_en,
                    name_quality="curated",
                    unit="",
                    unit_ru="",
                    frequency="monthly",
                    category_ru="Прочее",
                    source="Евростат",
                    history_start=date(2024, 1, 1),
                    history_end=date(2025, 12, 1),
                    points_count=24,
                    is_listed=listed,
                    seo_keywords=kw,
                )

            pipeline = _ind(
                "gas-pipeline-throughput", "Pipeline transport volumes",
            )
            reserves = _ind(
                "xx-gas-reserves", "Proven reserves statistics",
            )
            storage = _ind("xx-storage-levels", "gas storage levels")
            # Вхождение только в имени_en — замыкает цепочку рангов.
            energy = _ind(
                "xx-energy-widget", "Monthly energy market gas balance",
                kw=None,
            )
            # Только keywords — должен уступить всем прямым совпадениям.
            kw_only = _ind(
                "xx-widmark-bravo", "Unrelated widget bravo",
                kw="gas notes",
            )
            db.add_all([pipeline, reserves, storage, energy, kw_only])
            await db.flush()
            for ind in (pipeline, reserves, storage, energy, kw_only):
                for i in range(24):
                    db.add(WorldDataPoint(
                        indicator_id=ind.id,
                        date=date(2024 + i // 12, i % 12 + 1, 1),
                        value=100.0 + i,
                    ))
            await db.commit()

    asyncio.run(_seed())
    with TestClient(auth_env["app"]) as tc:
        yield tc


def test_search_weighted_ranking_chain(search_world_client):
    body = search_world_client.get(
        "/api/v1/world/search", params={"q": "gas"}
    ).json()
    codes = [row["code"] for row in body["results"]]
    # Префикс кода → вхождение кода → префикс имени → вхождение имени;
    # keywords-only ряд не входит до исчерпания прямых совпадений.
    assert codes[:3] == [
        "gas-pipeline-throughput",
        "xx-gas-reserves",
        "xx-storage-levels",
    ]
    assert "xx-energy-widget" in codes
    # Keywords-only — последний среди найденных.
    if "xx-widmark-bravo" in codes:
        assert codes[-1] == "xx-widmark-bravo"


def test_search_limit_ceiling_matches_constant(search_world_client):
    from app.api.world import WORLD_GLOBAL_SEARCH_LIMIT

    over = search_world_client.get(
        "/api/v1/world/search", params={"q": "а", "limit": WORLD_GLOBAL_SEARCH_LIMIT + 50}
    )
    assert over.status_code == 422
    ok = search_world_client.get(
        "/api/v1/world/search", params={"q": "а", "limit": WORLD_GLOBAL_SEARCH_LIMIT}
    )
    assert ok.status_code == 200


def test_search_default_limit_is_global_constant(search_world_client):
    """Дефолт лимита эндпоинта — константа WORLD_GLOBAL_SEARCH_LIMIT."""
    import inspect

    from app.api.world import WORLD_GLOBAL_SEARCH_LIMIT, search_world

    signature = inspect.signature(search_world)
    default = signature.parameters["limit"].default
    # FastAPI оборачивает дефолт в Query(...) — распаковываем.
    actual = getattr(default, "default", default)
    assert actual == WORLD_GLOBAL_SEARCH_LIMIT


def test_search_contract_fields_stable(search_world_client):
    body = search_world_client.get(
        "/api/v1/world/search", params={"q": "gas"}
    ).json()
    row = body["results"][0]
    assert {
        "code", "name", "name_ru", "country_slug", "country_name",
        "category", "frequency",
    } <= set(row)


def test_crosswalk_codes_present_for_all_concepts():
    """Crosswalk-инвариант: известные concept'ы с национальными рядами."""

    for concept_slug, expected_members in (
        ("hicp-index", {"us-cpi-all", "uk-cpi-all", "jp-cpi-all", "kr-cpi-all"}),
        ("unemployment-rate", {"us-unemployment-rate", "jp-unemployment-rate"}),
        ("population", {"au-population", "ca-population", "uk-population"}),
        ("activity-rate", {"au-participation-rate", "uk-participation-rate"}),
    ):
        codes = set(national_codes_for_concept(concept_slug))
        assert expected_members <= codes, concept_slug


def test_map_series_uses_unlisted_eurostat_when_national_missing(auth_env):
    """Карта: eurostat-срез без is_listed, если national-core ряда ещё нет.

    JP unemployment живёт в une_rt_m, но unlist_eurostat_on_national_passports
    снимает его с каталога страны до ingest e-Stat. Рейтинг/карта всё равно
    должны показать Японию.
    """
    import asyncio
    from datetime import date
    from fastapi.testclient import TestClient
    from app.models import WorldCountry, WorldDataPoint, WorldIndicator

    async def _seed():
        async with auth_env["session_maker"]() as db:
            jp = WorldCountry(
                code="JP", slug="japan", name_ru="Япония",
                name_en="Japan", region_ru="Азия", sort_order=20,
            )
            de = WorldCountry(
                code="DE", slug="germany", name_ru="Германия",
                name_en="Germany", region_ru="Европа", sort_order=1,
            )
            db.add_all([jp, de])
            await db.flush()
            jp_une = WorldIndicator(
                country_id=jp.id,
                code="jp-une_rt_m-total-sa-t-pc-act",
                provider="eurostat",
                dataset_id="une_rt_m",
                slice_json={
                    "age": "TOTAL", "sex": "T", "s_adj": "SA",
                    "unit": "PC_ACT", "freq": "M",
                },
                slice_hash="jp-une",
                name_ru="Уровень безработицы",
                name_en="Unemployment rate",
                name_quality="curated",
                unit="PC_ACT",
                unit_ru="% экономически активного населения",
                frequency="monthly",
                category_ru="Рынок труда",
                source="Евростат",
                history_start=date(2024, 1, 1),
                history_end=date(2025, 6, 1),
                points_count=18,
                is_listed=False,
            )
            de_une = WorldIndicator(
                country_id=de.id,
                code="de-une_rt_m-total-sa-t-pc-act",
                provider="eurostat",
                dataset_id="une_rt_m",
                slice_json={
                    "age": "TOTAL", "sex": "T", "s_adj": "SA",
                    "unit": "PC_ACT", "freq": "M",
                },
                slice_hash="de-une",
                name_ru="Уровень безработицы",
                name_en="Unemployment rate",
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
            db.add_all([jp_une, de_une])
            await db.flush()
            for ind in (jp_une, de_une):
                for i in range(18):
                    db.add(WorldDataPoint(
                        indicator_id=ind.id,
                        date=date(2024 + i // 12, i % 12 + 1, 1),
                        value=2.5 + i * 0.01,
                    ))
            await db.commit()

    asyncio.run(_seed())
    with TestClient(auth_env["app"]) as tc:
        body = tc.get("/api/v1/world/compare/map-series/unemployment-rate").json()
        year = str(max(body["years"]))
        codes = set(body["values_by_year"][year])
        assert "JP" in codes
        assert "DE" in codes
        jp_page = tc.get("/api/v1/world/countries/japan").json()
        listed_codes = {
            row["code"]
            for cat in jp_page.get("categories") or []
            for row in cat.get("indicators") or []
        }
        assert "jp-une_rt_m-total-sa-t-pc-act" not in listed_codes
