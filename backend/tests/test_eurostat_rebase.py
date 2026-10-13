"""Смена базы индекса Евростата (I15 → I21): один показатель, актуальные данные.

Образец (12.10.2026): `sts_trtu_m` и ещё 60 наборов. Евростат с 2024 ведёт индексы на
базе 2021=100; наши срезы закреплены на 2015=100 и стоят на декабре 2023, хотя у
источника есть данные до 2026-08.
"""
import asyncio
from datetime import date

from app.data.legacy_redirects import resolve_world_superseded
from app.models import (
    WorldCountry,
    WorldDataPoint,
    WorldForecast,
    WorldIndicator,
)
from app.services.eurostat_parser import (
    choose_headline_slice,
    extract_live_members,
    index_base_year,
    index_unit_suffix,
    replace_dead_index_unit,
)
from app.services.eurostat_rebase import (
    REBASE_EVENTS,
    RebaseContext,
    describe_summary,
    fit_rebase,
    rebase_twin_slice,
    summarize_events,
)
from app.services.eurostat_structure import ExistingSlice, plan_structure_migration


def _monthly(values, start=(2010, 1)):
    out, y, m = [], start[0], start[1]
    for v in values:
        out.append((date(y, m, 1), float(v)))
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


def _wave(n, base=100.0):
    return [round(base + 10 * ((i * 7) % 13) / 13 + i * 0.3, 1) for i in range(n)]


def test_base_year_and_suffix():
    assert index_base_year("I15") == 2015
    assert index_base_year("I21") == 2021
    assert index_base_year("I2015") == 2015
    assert index_base_year("I96") == 1996
    assert index_base_year("I21_SCA") == 2021
    assert index_base_year("PCH_SM") is None
    assert index_base_year("INX") is None
    assert index_base_year(None) is None
    assert index_unit_suffix("I15_Q") == "Q"
    assert index_unit_suffix("I21") == ""


def test_dead_index_unit_is_replaced_by_newest_live_base():
    members = ["I21", "I15", "I10", "PCH_PRE", "PCH_SM"]
    live = {"I21", "PCH_PRE", "PCH_SM"}
    assert replace_dead_index_unit("I15", members, live) == "I21"
    # живая единица не меняется (оба индекса живы: привычная база остаётся)
    assert replace_dead_index_unit("I15", members, live | {"I15"}) == "I15"
    # нет проб живости -> прежнее поведение
    assert replace_dead_index_unit("I15", members, None) == "I15"
    assert replace_dead_index_unit("I15", members, set()) == "I15"
    # не индекс не трогаем
    assert replace_dead_index_unit("PCH_SM", members, live) == "PCH_SM"
    # хвост единицы (квартальная I15_Q) не смешивается с годовой/обычной
    assert replace_dead_index_unit("I15_Q", ["I15_Q", "I21"], {"I21"}) == "I15_Q"
    # нет более новой живой базы -> остаётся
    assert replace_dead_index_unit("I21", ["I21", "I15"], {"I15"}) == "I21"


def test_extract_live_members_decodes_flat_index():
    payload = {
        "id": ["freq", "unit", "geo", "time"],
        "size": [1, 3, 2, 1],
        "dimension": {
            "freq": {"category": {"index": {"M": 0}}},
            "unit": {"category": {"index": {"I21": 0, "I15": 1, "PCH_SM": 2}}},
            "geo": {"category": {"index": {"DE": 0, "FR": 1}}},
            "time": {"category": {"index": {"2026-08": 0}}},
        },
        "value": {"0": 99.0, "1": 98.0, "4": 1.2},
    }
    assert extract_live_members(payload, "unit") == {"I21", "PCH_SM"}
    assert extract_live_members({**payload, "value": [5.0] + [None] * 5}, "unit") == {"I21"}
    assert extract_live_members(payload, "nope") == set()


def test_headline_slice_moves_to_live_base():
    dims = {
        "freq": ["M"], "indic_bt": ["VOL_SLS"], "nace_r2": ["G47"], "s_adj": ["SCA"],
        "unit": ["I21", "I15", "I10", "PCH_PRE", "PCH_SM"], "geo": [], "time": [],
    }
    old = choose_headline_slice(dims, dataset_id="sts_trtu_m")
    assert old["unit"] == "I15", "без проб живости срез остаётся прежним"
    moved = choose_headline_slice(dims, dataset_id="sts_trtu_m", live={"unit": {"I21", "PCH_SM"}})
    assert moved["unit"] == "I21"
    assert {k: v for k, v in moved.items() if k != "unit"} == {k: v for k, v in old.items() if k != "unit"}


def test_fit_accepts_exact_rebase_and_rounding():
    old = _monthly(_wave(120))
    factor = 0.8123
    new = [(d, round(v / factor, 1)) for d, v in old] + _monthly([130.0, 131.0], start=(2020, 1))
    fit = fit_rebase(old, new)
    assert fit.ok, fit
    assert abs(fit.factor - factor) < 0.01
    assert fit.coverage == 1.0


def test_fit_accepts_revised_seasonally_adjusted_history():
    """SCA-ряды пересчитываются целиком: медианное отклонение от множителя 2 %, хвосты до 30 %."""
    old = _monthly(_wave(240))
    new = []
    for i, (d, v) in enumerate(old):
        wobble = 1 + (0.03 if i % 7 == 0 else -0.015 if i % 5 == 0 else 0.0) * ((-1) ** i)
        new.append((d, round(v / 0.62 * wobble, 1)))
    fit = fit_rebase(old, new)
    assert fit.ok and fit.share < 1.0, fit
    assert fit.level_corr > 0.9


def test_fit_rejects_other_series_and_lost_history():
    old = _monthly(_wave(120))
    different = [(d, 100 + ((i * 11) % 17) * 3.0 - i * 0.2) for i, (d, _) in enumerate(old)]
    assert not fit_rebase(old, different).ok, "другой ряд не принимается за пересчёт"
    short = [(d, v / 0.8) for d, v in old[60:]]
    fit = fit_rebase(old, short)
    assert not fit.ok and "короче" in fit.reason, "короткая история не склеивается"
    assert not fit_rebase(old, []).ok
    assert not fit_rebase([], old).ok


def test_twin_slice_requires_only_the_base_to_differ():
    a = {"freq": "M", "unit": "I15", "nace_r2": "G47", "s_adj": "SCA"}
    b = {**a, "unit": "I21"}
    assert rebase_twin_slice(a, b)
    assert not rebase_twin_slice(b, a), "назад на старую базу не переезжаем"
    assert not rebase_twin_slice(a, {**b, "nace_r2": "G46"})
    assert not rebase_twin_slice(a, {**b, "extra": "x"})
    assert not rebase_twin_slice(a, {**a, "unit": "PCH_SM"})
    assert not rebase_twin_slice({**a, "unit": "I15_Q"}, b), "квартальная и обычная меры разные"


def test_structure_check_treats_base_change_as_expected_event():
    """Раньше такой набор уходил в карантин: все публичные карточки «без среза»."""
    old_slice = {"freq": "M", "unit": "I15", "nace_r2": "G47"}
    new_slice = {**old_slice, "unit": "I21"}
    history = _monthly(_wave(48))
    existing = [
        ExistingSlice(i, geo, old_slice, "h_old", True)
        for i, geo in enumerate(["DE", "FR", "IT", "ES", "PL"], start=1)
    ]
    new_series = {
        (geo, "h_new"): (new_slice, [(d, v / 0.9) for d, v in history])
        for geo in ["DE", "FR", "IT", "ES", "PL"]
    }
    verdict = plan_structure_migration(
        existing, new_series, old_points={e.indicator_id: history for e in existing},
    )
    assert verdict.accept
    assert len(verdict.rebased) == 5 and not verdict.orphans and not verdict.remapped
    assert verdict.as_dict()["rebased"] == 5
    # без пары на новой базе набор по-прежнему считается разломом
    broken = plan_structure_migration(existing, {}, old_points={})
    assert not broken.accept


def _seed(auth_env, *, new_points, old_points):
    async def go():
        async with auth_env["session_maker"]() as db:
            country = WorldCountry(code="DE", slug="germany", name_ru="Германия", name_en="Germany", is_active=True)
            db.add(country)
            await db.flush()
            old = WorldIndicator(
                country_id=country.id, provider="eurostat", code="de-sts_trtu_m-g47-i15-sca",
                dataset_id="sts_trtu_m",
                slice_json={"freq": "M", "unit": "I15", "nace_r2": "G47"}, slice_hash="h15",
                frequency="monthly", name_ru="Розничная торговля", unit="I15", unit_ru="индекс",
                is_listed=True, points_count=len(old_points), history_end=old_points[-1][0],
            )
            db.add(old)
            await db.flush()
            db.add_all(WorldDataPoint(indicator_id=old.id, date=d, value=v) for d, v in old_points)
            db.add(WorldForecast(
                world_indicator_id=old.id, strategy="x", model_name="m", gate_status="ok",
                horizon=6, is_current=True,
            ))
            await db.commit()
            return old.id, country.id

    return asyncio.run(go())


def test_card_moves_to_new_base_in_place_and_keeps_history(auth_env):
    old_pts = _monthly(_wave(120))
    new_pts = [(d, round(v / 0.8, 1)) for d, v in old_pts] + _monthly([140.0, 141.0, 142.0], start=(2020, 1))
    old_id, country_id = _seed(auth_env, new_points=new_pts, old_points=old_pts)
    new_slice = {"freq": "M", "unit": "I21", "nace_r2": "G47"}
    REBASE_EVENTS.clear()

    async def go():
        async with auth_env["session_maker"]() as db:
            ctx = await RebaseContext.load(db, "sts_trtu_m", new_slice, "h21")
            assert ctx is not None
            event = await ctx.retarget(db, country_id=country_id, points=new_pts)
            await db.commit()
            return event

    event = asyncio.run(go())
    assert event is not None and event.kind == "rebased" and event.indicator_id == old_id

    async def check():
        async with auth_env["session_maker"]() as db:
            ind = await db.get(WorldIndicator, old_id)
            assert ind.slice_hash == "h21" and ind.slice_json["unit"] == "I21"
            assert ind.code == "de-sts_trtu_m-g47-i15-sca", "адрес страницы не меняется"
            fc = (await db.execute(
                WorldForecast.__table__.select().where(WorldForecast.world_indicator_id == old_id)
            )).all()
            assert fc and not any(row.is_current for row in fc), "прогноз в старом масштабе снят"

    asyncio.run(check())
    summary = summarize_events(REBASE_EVENTS)
    assert summary[0]["rebased"] == 1 and "I15→I21" in describe_summary(summary[0])


def test_unconfirmed_rebase_replaces_card_and_redirects_old_to_new(auth_env):
    old_pts = _monthly(_wave(120))
    # новая база с короткой историей: ряды не склеиваем
    new_pts = [(d, round(v / 0.8, 1)) for d, v in old_pts[80:]] + _monthly([140.0, 141.0], start=(2020, 1))
    old_id, country_id = _seed(auth_env, new_points=new_pts, old_points=old_pts)
    new_slice = {"freq": "M", "unit": "I21", "nace_r2": "G47"}
    REBASE_EVENTS.clear()

    async def go():
        async with auth_env["session_maker"]() as db:
            ctx = await RebaseContext.load(db, "sts_trtu_m", new_slice, "h21")
            event = await ctx.retarget(db, country_id=country_id, points=new_pts)
            assert event.kind == "twin" and "короче" in event.fit.reason
            new = WorldIndicator(
                country_id=country_id, provider="eurostat", code="de-sts_trtu_m-g47-i21-sca",
                dataset_id="sts_trtu_m", slice_json=new_slice, slice_hash="h21", frequency="monthly",
                name_ru="Розничная торговля", unit="I21", unit_ru="индекс", is_listed=True,
                points_count=len(new_pts), history_end=new_pts[-1][0],
            )
            db.add(new)
            await db.flush()
            db.add_all(WorldDataPoint(indicator_id=new.id, date=d, value=v) for d, v in new_pts)
            await ctx.retire_twins(db, event, new_id=new.id, new_listed=True, new_end=new_pts[-1][0])
            await db.commit()

    asyncio.run(go())

    async def check():
        async with auth_env["session_maker"]() as db:
            old = await db.get(WorldIndicator, old_id)
            assert old.is_listed is False and old.slice_hash == "h15"
            to = await resolve_world_superseded(db, "germany", "de-sts_trtu_m-g47-i15-sca")
            assert to == "/germany/indicator/de-sts_trtu_m-g47-i21-sca"
            # года, которого нет у двойника, редиректить некуда
            assert await resolve_world_superseded(
                db, "germany", "de-sts_trtu_m-g47-i15-sca", 2012,
            ) is None
            # листингованный двойник сам не редиректится
            assert await resolve_world_superseded(db, "germany", "de-sts_trtu_m-g47-i21-sca") is None

    asyncio.run(check())


def test_live_units_are_withheld_until_the_flag_is_on(monkeypatch):
    """Релиз в два шага: пока флаг выключен, срез выбирается по прежнему приоритету."""
    import app.services.eurostat_parser as parser
    from app.config import settings

    probe = ({"unit": ["I21", "I15"]}, {"unit": {"I21"}})
    monkeypatch.setattr(parser, "_fetch_structure_live", lambda *a, **k: probe)
    monkeypatch.setattr(settings, "eurostat_rebase_enabled", False)
    assert parser.fetch_dataset_structure_live("sts_trtu_m")[1] == {}
    assert parser.fetch_dataset_structure_live("sts_trtu_m", honor_flag=False)[1] == {"unit": {"I21"}}
    monkeypatch.setattr(settings, "eurostat_rebase_enabled", True)
    assert parser.fetch_dataset_structure_live("sts_trtu_m")[1] == {"unit": {"I21"}}


def test_new_base_that_ended_earlier_does_not_spawn_a_stale_twin(auth_env):
    old_pts = _monthly(_wave(120))
    # у источника новая база кончилась раньше прежней карточки и по форме не совпадает
    new_pts = [(d, 100 + ((i * 11) % 17) * 3.0) for i, (d, _) in enumerate(old_pts[:60])]
    old_id, country_id = _seed(auth_env, new_points=new_pts, old_points=old_pts)
    REBASE_EVENTS.clear()

    async def go():
        async with auth_env["session_maker"]() as db:
            ctx = await RebaseContext.load(db, "sts_trtu_m", {"freq": "M", "unit": "I21", "nace_r2": "G47"}, "h21")
            return await ctx.retarget(db, country_id=country_id, points=new_pts)

    event = asyncio.run(go())
    assert event.kind == "skipped"
    summary = summarize_events(REBASE_EVENTS)[0]
    assert summary["skipped"] == 1 and "кончился раньше" in describe_summary(summary)


def test_unknown_liveness_with_several_index_bases_is_retried_not_guessed(monkeypatch):
    import pytest

    import app.services.eurostat_parser as parser
    from app.config import settings

    monkeypatch.setattr(settings, "eurostat_rebase_enabled", True)
    monkeypatch.setattr(parser, "_fetch_structure_live",
                        lambda *a, **k: ({"unit": ["I21", "I15", "PCH_SM"]}, {}))
    with pytest.raises(RuntimeError, match="живая база индекса не определена"):
        parser.fetch_dataset_structure_live("sts_trtu_m")
    # одна база индекса — гадать не о чем
    monkeypatch.setattr(parser, "_fetch_structure_live",
                        lambda *a, **k: ({"unit": ["I21", "PCH_SM"]}, {}))
    assert parser.fetch_dataset_structure_live("sts_inpi_q")[1] == {}


def test_base_move_with_many_failed_slices_is_retried(monkeypatch):
    import pytest

    import app.services.eurostat_parser as parser

    dims = {"freq": ["M"], "nace_r2": ["G47", "G46", "G45"], "s_adj": ["SCA"],
            "unit": ["I21", "I15"], "geo": [], "time": []}
    monkeypatch.setattr(parser, "fetch_dataset_structure_live",
                        lambda *a, **k: (dims, {"unit": {"I21"}}))
    calls = {"n": 0}

    def fake_fetch(dataset_id, **kw):
        calls["n"] += 1
        if calls["n"] > 1:
            raise RuntimeError("timeout")
        return parser.DatasetParseResult(dataset_id, "t", "monthly", kw["forced_slice"], "h", "I21", {}, "u")

    monkeypatch.setattr(parser, "fetch_and_parse_dataset", fake_fetch)
    assert parser._base_moved(dims, "sts_trtu_m", {"unit": {"I21"}})
    with pytest.raises(RuntimeError, match="повтор позже"):
        parser.fetch_deep_slices("sts_trtu_m")
