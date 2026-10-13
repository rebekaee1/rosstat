"""Круг 13: остаток дублей по Франции — первые публикации ГИПЦ, ППС, подписи ct и minr.

Слова владельца: «всегда надо чтобы у нас один показатель все показывал по смыслу и правильно».
"""
import asyncio
from datetime import date

import pytest

from app.data.legacy_redirects import resolve_world_superseded
from app.data.world_indicator_titles_ru import (
    public_indicator_name,
    title_override_en_for_code,
)
from app.data.world_superseded import (
    SUPERSEDED_WORLD_DATASETS,
    should_unlist_superseded,
    successor_dataset_of,
    superseded_target,
)
from app.models import WorldCountry, WorldDataPoint, WorldIndicator
from app.services.freshness_note import _same_subject, world_freshness_note

TODAY = date(2026, 10, 12)


def test_pure_rule_for_first_publications_and_ppp():
    assert superseded_target(
        "prc_hicp_fp", "fr-prc_hicp_fp-cp00-fin-i15",
        {"unit": "I15", "coicop": "CP00", "release": "FIN"}, "I15",
    ) == ("fr-prc_hicp_fpd-total-fin-i15", None)
    # ППС: заголовочный срез GDP, хвост кода сохраняется
    assert superseded_target(
        "prc_ppp_ind", "de-prc_ppp_ind-exp-pps-eu27-2020-hab-gdp",
        {"na_item": "EXP_PPS_EU27_2020_HAB", "ppp_cat": "GDP"}, None,
    ) == ("de-prc_ppp_ind_1-exp-pps-eu27-2020-hab-gdp", None)
    # подгруппа COICOP 1999 не имеет гарантированного аналога в COICOP 2018
    assert superseded_target(
        "prc_ppp_ind", "de-prc_ppp_ind-ppp-eu27-2020-a01",
        {"na_item": "PPP_EU27_2020", "ppp_cat": "A01"}, None,
    ) is None
    assert successor_dataset_of("prc_hicp_fp") == "prc_hicp_fpd"
    assert successor_dataset_of("prc_ppp_ind") == "prc_ppp_ind_1"
    assert successor_dataset_of("prc_hicp_minr") is None
    # среднегодовой индекс не объявлен дублем: у ainr база 2025=100, у aind 2015=100
    assert "prc_hicp_aind" not in SUPERSEDED_WORLD_DATASETS


def test_same_subject_treats_renamed_classification_dimensions_as_one_subject():
    v1 = {"freq": "M", "unit": "I15", "coicop": "CP00", "release": "FIN"}
    v2 = {"freq": "M", "unit": "I15", "coicop18": "TOTAL", "release": "FIN"}
    assert _same_subject(v1, v2)
    # подгруппа и заголовочный срез — разные предметы
    assert not _same_subject({"coicop": "CP01"}, {"coicop18": "TOTAL"})
    assert not _same_subject({"coicop": "CP00", "release": "FIN"}, {"coicop18": "TOTAL"})
    # ППС: те же измерения под новыми именами
    assert _same_subject(
        {"na_item": "PPP_EU27_2020", "ppp_cat": "GDP"},
        {"indic_ppp": "PPP_EU27_2020", "ppp_cat18": "GDP"},
    )
    assert not _same_subject({}, {})


def _fr(db):
    country = WorldCountry(code="FR", slug="france", name_ru="Франция", name_en="France", is_active=True)
    db.add(country)
    return country


def _mk(country_id, code, dataset, slice_json, he, *, listed=True, unit="I15", points=2):
    return WorldIndicator(
        country_id=country_id, code=code, dataset_id=dataset, slice_json=slice_json,
        slice_hash=code, frequency="monthly", name_ru=code, name_en=code, unit=unit,
        unit_ru="индекс (2015 = 100)", is_listed=listed, points_count=points, history_end=he,
    )


def _seed_fp_fpd(auth_env, *, with_successor=True):
    async def go():
        async with auth_env["session_maker"]() as db:
            country = _fr(db)
            await db.flush()
            old = _mk(
                country.id, "fr-prc_hicp_fp-cp00-fin-i15", "prc_hicp_fp",
                {"freq": "M", "unit": "I15", "coicop": "CP00", "release": "FIN"}, date(2025, 12, 1),
            )
            db.add(old)
            if with_successor:
                new = _mk(
                    country.id, "fr-prc_hicp_fpd-total-fin-i15", "prc_hicp_fpd",
                    {"freq": "M", "unit": "I15", "release": "FIN", "coicop18": "TOTAL"}, date(2026, 8, 1),
                )
                db.add(new)
                await db.flush()
                db.add_all([
                    WorldDataPoint(indicator_id=new.id, date=date(2025, 12, 1), value=124.43),
                    WorldDataPoint(indicator_id=new.id, date=date(2026, 8, 1), value=129.11),
                ])
            await db.commit()
            return country.id

    return asyncio.run(go())


def test_stale_first_publications_card_leads_to_live_twin(auth_env):
    _seed_fp_fpd(auth_env)

    async def go():
        async with auth_env["session_maker"]() as db:
            assert await resolve_world_superseded(
                db, "france", "fr-prc_hicp_fp-cp00-fin-i15",
            ) == "/france/indicator/fr-prc_hicp_fpd-total-fin-i15"
            assert await resolve_world_superseded(
                db, "france", "fr-prc_hicp_fp-cp00-fin-i15", 2026,
            ) == "/france/indicator/fr-prc_hicp_fpd-total-fin-i15/2026"
            assert await resolve_world_superseded(
                db, "france", "fr-prc_hicp_fp-cp00-fin-i15", 1999,
            ) is None
            old = (await db.execute(
                WorldIndicator.__table__.select().where(WorldIndicator.code == "fr-prc_hicp_fp-cp00-fin-i15")
            )).first()
            assert await should_unlist_superseded(
                db, old.country_id, old.dataset_id, old.code, old.slice_json, old.unit,
            ) is True

    asyncio.run(go())


def test_card_is_kept_when_country_has_no_live_twin(auth_env):
    _seed_fp_fpd(auth_env, with_successor=False)

    async def go():
        async with auth_env["session_maker"]() as db:
            assert await resolve_world_superseded(db, "france", "fr-prc_hicp_fp-cp00-fin-i15") is None
            old = (await db.execute(
                WorldIndicator.__table__.select().where(WorldIndicator.code == "fr-prc_hicp_fp-cp00-fin-i15")
            )).first()
            assert await should_unlist_superseded(
                db, old.country_id, old.dataset_id, old.code, old.slice_json, old.unit,
            ) is False

    asyncio.run(go())


def test_freshness_block_names_nearest_across_classification_versions(auth_env):
    """Раньше `nearest` был null: срезы cp00 и total не считались одним предметом."""
    _seed_fp_fpd(auth_env)

    async def go():
        async with auth_env["session_maker"]() as db:
            old = (await db.execute(
                WorldIndicator.__table__.select().where(WorldIndicator.code == "fr-prc_hicp_fp-cp00-fin-i15")
            )).first()
            ind = await db.get(WorldIndicator, old.id)
            note = await world_freshness_note(db, ind, today=TODAY, country_slug="france")
            assert note is not None
            nearest = note["nearest"]
            assert nearest and nearest["code"] == "fr-prc_hicp_fpd-total-fin-i15"
            assert nearest["url"] == "/france/indicator/fr-prc_hicp_fpd-total-fin-i15"
            assert nearest["last_period"] == "2026-08-01"

    asyncio.run(go())


def test_ppp_headline_slices_lead_to_2018_classification(auth_env):
    async def go():
        async with auth_env["session_maker"]() as db:
            country = _fr(db)
            await db.flush()
            old_slice = {"freq": "A", "na_item": "EXP_PPS_EU27_2020", "ppp_cat": "GDP"}
            new_slice = {"freq": "A", "indic_ppp": "EXP_PPS_EU27_2020", "ppp_cat18": "GDP"}
            old = _mk(country.id, "fr-prc_ppp_ind-exp-pps-eu27-2020-gdp", "prc_ppp_ind", old_slice, date(2024, 1, 1), unit=None)
            old.frequency = "annual"
            new = _mk(country.id, "fr-prc_ppp_ind_1-exp-pps-eu27-2020-gdp", "prc_ppp_ind_1", new_slice, date(2025, 1, 1), unit=None)
            new.frequency = "annual"
            eu15 = _mk(country.id, "fr-prc_ppp_ind-exp-pps-eu15-hab-gdp", "prc_ppp_ind",
                       {"freq": "A", "na_item": "EXP_PPS_EU15_HAB", "ppp_cat": "GDP"}, date(2020, 1, 1), unit=None)
            eu15.frequency = "annual"
            db.add_all([old, new, eu15])
            await db.flush()
            db.add(WorldDataPoint(indicator_id=new.id, date=date(2025, 1, 1), value=1.0))
            await db.commit()
        async with auth_env["session_maker"]() as db:
            assert await resolve_world_superseded(
                db, "france", "fr-prc_ppp_ind-exp-pps-eu27-2020-gdp",
            ) == "/france/indicator/fr-prc_ppp_ind_1-exp-pps-eu27-2020-gdp"
            # старый состав ЕС аналога не имеет и остаётся как есть
            assert await resolve_world_superseded(db, "france", "fr-prc_ppp_ind-exp-pps-eu15-hab-gdp") is None

    asyncio.run(go())


@pytest.mark.parametrize("country", ["fr", "de", "it", "es"])
def test_ct_and_minr_have_different_public_names(country):
    ct_db = "Гармонизированный индекс потребительских цен, индекс (2015 = 100)"
    minr_db = "Гармонизированный индекс потребительских цен, индекс (2015 = 100)"
    ct = public_indicator_name(ct_db, f"{country}-prc_hicp_ct-total-i15")
    minr = public_indicator_name(minr_db, f"{country}-prc_hicp_minr-total-i15")
    fpd = public_indicator_name(minr_db, f"{country}-prc_hicp_fpd-total-fin-i15")
    assert ct == "Гармонизированный индекс потребительских цен при постоянных налоговых ставках"
    assert len({ct, minr, fpd}) == 3
    # среднегодовой индекс: база 2015=100 у aind и 2025=100 у ainr (проверено по данным 34 и 36 стран)
    aind = public_indicator_name("Гармонизированный индекс потребительских цен, среднегодовой",
                                 f"{country}-prc_hicp_aind-cp00-inx-a-avg")
    ainr = public_indicator_name("Гармонизированный индекс потребительских цен, среднегодовой",
                                 f"{country}-prc_hicp_ainr-total-inx-a-avg")
    assert aind.endswith("(2015 = 100)") and ainr.endswith("(2025 = 100)")
    assert title_override_en_for_code(f"{country}-prc_hicp_ct-total-i15") == (
        "Harmonised index of consumer prices at constant tax rates"
    )
    assert title_override_en_for_code(f"{country}-prc_hicp_minr-total-i15") is None
    # ctr / ctrb — другие наборы, фрагмент с дефисом их не задевает
    assert public_indicator_name("x, помесячно", f"{country}-prc_hicp_ctr-total-i15") == "x"


def test_consumption_by_purpose_v1_leads_to_v2_total_only():
    assert superseded_target(
        "nama_10_co3_p3", "fr-nama_10_co3_p3-total-pc-gdp",
        {"freq": "A", "unit": "PC_GDP", "coicop": "TOTAL"}, "PC_GDP",
    ) == ("fr-nama_10_cp18-total-pc-gdp", None)
    assert superseded_target(
        "nama_10_co3_p3", "fr-nama_10_co3_p3-cp01-pc-gdp",
        {"freq": "A", "unit": "PC_GDP", "coicop": "CP01"}, "PC_GDP",
    ) is None


def test_card_stays_when_live_twin_has_shorter_history(auth_env):
    """Дания: у набора ver.2 история с 1995, у ver.1 с 1975. Уход на канон отнял бы 20 лет."""

    async def go():
        async with auth_env["session_maker"]() as db:
            country = _fr(db)
            await db.flush()
            old = _mk(country.id, "fr-prc_hicp_fp-cp00-fin-i15", "prc_hicp_fp",
                      {"freq": "M", "unit": "I15", "coicop": "CP00", "release": "FIN"}, date(2025, 12, 1))
            old.history_start = date(1996, 1, 1)
            new = _mk(country.id, "fr-prc_hicp_fpd-total-fin-i15", "prc_hicp_fpd",
                      {"freq": "M", "unit": "I15", "release": "FIN", "coicop18": "TOTAL"}, date(2026, 8, 1))
            new.history_start = date(2005, 1, 1)
            db.add_all([old, new])
            await db.commit()
        async with auth_env["session_maker"]() as db:
            assert await resolve_world_superseded(db, "france", "fr-prc_hicp_fp-cp00-fin-i15") is None
            row = (await db.execute(
                WorldIndicator.__table__.select().where(WorldIndicator.code == "fr-prc_hicp_fp-cp00-fin-i15")
            )).first()
            assert await should_unlist_superseded(
                db, row.country_id, row.dataset_id, row.code, row.slice_json, row.unit, row.history_start,
            ) is False

    asyncio.run(go())
