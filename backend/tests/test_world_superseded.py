"""Один показатель — один смысл: остановленный у источника дубль ведёт на живой канон.

Образец (12.10.2026): Франция, «Harmonised consumer price index at constant tax
rates» (prc_hicp_cind) закончился декабрём 2025 у самого Евростата, а основной
индекс (prc_hicp_minr) идёт до августа 2026; человек решил, что за 2026 год
данных нет.
"""
import asyncio
from datetime import date

from app.data.legacy_redirects import resolve_world_superseded
from app.data.world_superseded import (
    SUPERSEDED_WORLD_DATASETS,
    is_superseded_dataset,
    superseded_dataset_ids,
    superseded_target,
)
from app.models import WorldCountry, WorldDataPoint, WorldIndicator


def test_pure_rule_maps_headline_slice_to_canonical_card():
    assert superseded_target(
        "prc_hicp_cind", "fr-prc_hicp_cind-cp00-i15", {"unit": "I15", "coicop": "CP00"}, "I15",
    ) == ("fr-prc_hicp_minr-total-i15", None)
    assert superseded_target(
        "prc_hicp_cann", "de-prc_hicp_cann-cp00-rch_a", {"unit": "RCH_A", "coicop": "CP00"}, "RCH_A",
    ) == ("de-prc_hicp_minr-total-i15", "yoy")
    assert superseded_target(
        "prc_hicp_cmon", "it-prc_hicp_cmon-cp00-rch_m", {"coicop": "CP00"}, "RCH_M",
    ) == ("it-prc_hicp_minr-total-i15", "step")


def test_subgroups_and_live_datasets_are_not_redirected():
    # подгруппа ECOICOP ver.1 не имеет аналога под тем же кодом
    assert superseded_target(
        "prc_hicp_cind", "fr-prc_hicp_cind-cp01-i15", {"coicop": "CP01"}, "I15",
    ) is None
    # живой набор (ECOICOP ver.2 при постоянных налогах) в списке не состоит
    assert not is_superseded_dataset("prc_hicp_ct")
    assert not is_superseded_dataset("prc_hicp_minr")
    # слитые с карточкой minr наборы сюда не входят (у них своё слияние и 301)
    from app.data.eurostat_listing import CATALOG_STEM_ALIASES

    merged = set().union(*CATALOG_STEM_ALIASES)
    # Исключение: prc_hicp_fp стоит в alias-группе, но ключ слияния его среза (CP00 + release=FIN)
    # не совпадает ни с одним листингованным членом группы, поэтому ряд жил отдельной карточкой.
    assert not (set(SUPERSEDED_WORLD_DATASETS) & merged - {"prc_hicp_fp"})
    # поиск исключает целиком только наборы, закрытые полностью; остальные отсекает is_listed
    assert set(superseded_dataset_ids()) == {"prc_hicp_cind", "prc_hicp_cann", "prc_hicp_cmon"}


def _seed(db, *, canonical_listed=True):
    country = WorldCountry(code="FR", slug="france", name_ru="Франция", name_en="France", is_active=True)
    db.add(country)
    return country


def test_resolver_redirects_stale_cind_to_listed_canonical(auth_env):
    async def go():
        async with auth_env["session_maker"]() as db:
            country = _seed(db)
            await db.flush()
            old = WorldIndicator(
                country_id=country.id, code="fr-prc_hicp_cind-cp00-i15", dataset_id="prc_hicp_cind",
                slice_json={"unit": "I15", "coicop": "CP00"}, slice_hash="old", frequency="monthly",
                name_ru="ИПЦ при постоянных налогах", name_en="HICP at constant tax rates",
                unit="I15", unit_ru="индекс", is_listed=True, points_count=2,
                history_end=date(2025, 12, 1),
            )
            new = WorldIndicator(
                country_id=country.id, code="fr-prc_hicp_minr-total-i15", dataset_id="prc_hicp_minr",
                slice_json={"unit": "I15", "coicop18": "TOTAL"}, slice_hash="new", frequency="monthly",
                name_ru="ГИПЦ", name_en="HICP", unit="I15", unit_ru="индекс",
                is_listed=True, points_count=2, history_end=date(2026, 8, 1),
            )
            db.add_all([old, new])
            await db.flush()
            db.add_all([
                WorldDataPoint(indicator_id=new.id, date=date(2025, 12, 1), value=127.0),
                WorldDataPoint(indicator_id=new.id, date=date(2026, 8, 1), value=129.5),
            ])
            await db.commit()
        async with auth_env["session_maker"]() as db:
            level = await resolve_world_superseded(db, "france", "fr-prc_hicp_cind-cp00-i15")
            assert level == "/france/indicator/fr-prc_hicp_minr-total-i15"
            # год есть у канона -> годовая страница тоже ведёт на канон
            assert await resolve_world_superseded(
                db, "france", "fr-prc_hicp_cind-cp00-i15", 2026,
            ) == "/france/indicator/fr-prc_hicp_minr-total-i15/2026"
            # года у канона нет -> не редиректим в пустоту
            assert await resolve_world_superseded(
                db, "france", "fr-prc_hicp_cind-cp00-i15", 1999,
            ) is None
            # канон сам не редиректится, чужой/несуществующий код -> None
            assert await resolve_world_superseded(db, "france", "fr-prc_hicp_minr-total-i15") is None
            assert await resolve_world_superseded(db, "france", "nope") is None
            assert await resolve_world_superseded(db, "atlantis", "x") is None

    asyncio.run(go())


def test_resolver_keeps_page_when_country_has_no_live_canonical(auth_env):
    async def go():
        async with auth_env["session_maker"]() as db:
            country = _seed(db)
            await db.flush()
            db.add(WorldIndicator(
                country_id=country.id, code="fr-prc_hicp_cind-cp00-i15", dataset_id="prc_hicp_cind",
                slice_json={"unit": "I15", "coicop": "CP00"}, slice_hash="old", frequency="monthly",
                name_ru="x", unit="I15", unit_ru="индекс", is_listed=True, points_count=2,
            ))
            await db.commit()
        async with auth_env["session_maker"]() as db:
            assert await resolve_world_superseded(db, "france", "fr-prc_hicp_cind-cp00-i15") is None

    asyncio.run(go())


def _seed_pair(auth_env):
    async def go():
        async with auth_env["session_maker"]() as db:
            country = _seed(db)
            await db.flush()
            old = WorldIndicator(
                country_id=country.id, code="fr-prc_hicp_cind-cp00-i15", dataset_id="prc_hicp_cind",
                slice_json={"unit": "I15", "coicop": "CP00"}, slice_hash="old", frequency="monthly",
                name_ru="ИПЦ при постоянных налогах", name_en="HICP at constant tax rates",
                unit="I15", unit_ru="индекс", is_listed=True, points_count=2,
                history_end=date(2025, 12, 1),
            )
            new = WorldIndicator(
                country_id=country.id, code="fr-prc_hicp_minr-total-i15", dataset_id="prc_hicp_minr",
                slice_json={"unit": "I15", "coicop18": "TOTAL"}, slice_hash="new", frequency="monthly",
                name_ru="ГИПЦ", name_en="HICP", unit="I15", unit_ru="индекс",
                is_listed=True, points_count=2, history_end=date(2026, 8, 1),
            )
            db.add_all([old, new])
            await db.flush()
            db.add_all([
                WorldDataPoint(indicator_id=old.id, date=date(2025, 12, 1), value=127.0),
                WorldDataPoint(indicator_id=new.id, date=date(2026, 8, 1), value=129.5),
            ])
            await db.commit()

    asyncio.run(go())


def test_ssr_route_answers_301_to_canonical_and_api_gives_redirect_to(auth_env, auth_client):
    _seed_pair(auth_env)
    r = auth_client.get("/seo/world/france/fr-prc_hicp_cind-cp00-i15", follow_redirects=False)
    assert r.status_code == 301
    assert r.headers["location"].endswith("/france/indicator/fr-prc_hicp_minr-total-i15")

    api = auth_client.get("/api/v1/world/indicators/france/fr-prc_hicp_cind-cp00-i15")
    assert api.status_code == 200
    body = api.json()
    assert body["primary_code"] == "fr-prc_hicp_minr-total-i15"
    assert body["redirect_to"] == "/france/indicator/fr-prc_hicp_minr-total-i15"


def test_unlist_script_unlists_only_with_live_canonical(auth_env, monkeypatch):
    import importlib.util
    from pathlib import Path

    _seed_pair(auth_env)
    spec = importlib.util.spec_from_file_location(
        "unlist_superseded", Path(__file__).resolve().parents[1] / "scripts" / "unlist-superseded-world.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "async_session", auth_env["session_maker"])

    async def noop(*_a, **_k):
        return None

    monkeypatch.setattr(module, "bump_namespaces", noop)
    assert asyncio.run(module.run(apply=False)) == 1

    async def listed():
        from sqlalchemy import select

        async with auth_env["session_maker"]() as db:
            return (await db.execute(
                select(WorldIndicator.is_listed).where(WorldIndicator.code == "fr-prc_hicp_cind-cp00-i15")
            )).scalar_one()

    assert asyncio.run(listed()) is True        # сухой прогон ничего не меняет
    assert asyncio.run(module.run(apply=True)) == 1
    assert asyncio.run(listed()) is False
    assert asyncio.run(module.run(apply=True)) == 0   # идемпотентно
