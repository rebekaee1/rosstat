"""Холодный расчёт каталога страны (19.11.2026): ответ тот же, база читается меньше, расчёт один на все запросы."""

from __future__ import annotations

import asyncio
from datetime import date

import pytest


_SERIES = {
    # код: точки (последние в конце)
    "de-prc_hicp_midx-cp00-i15": [(date(2026, 4, 1), 120.0), (date(2026, 5, 1), 121.5)],
    "de-une_rt_m-t-pc-act": [(date(2026, 4, 1), 3.4), (date(2026, 5, 1), 3.5)],
    # нули в конце, ненулевая точка раньше — ряд остаётся в каталоге
    "de-nrg_bal_c-gwh-total": [(date(2020, 1, 1), 5.0), (date(2021, 1, 1), 0.0), (date(2022, 1, 1), 0.0)],
    # одни нули — ряда в каталоге нет
    "de-ext_lt_zero-total": [(date(2021, 1, 1), 0.0), (date(2022, 1, 1), 0.0)],
    # точек нет — ряда в каталоге нет
    "de-sts_empty-total": [],
    # одна точка
    "de-gov_10dd_edpt1-gd-pc-gdp": [(date(2025, 1, 1), 62.4)],
}


@pytest.fixture
def seeded(auth_env):
    from app.models import WorldCountry, WorldDataPoint, WorldIndicator

    async def _seed():
        async with auth_env["session_maker"]() as db:
            de = WorldCountry(code="DE", slug="germany", name_ru="Германия", name_en="Germany",
                              region_ru="Европа", sort_order=1)
            db.add(de)
            await db.flush()
            ids = {}
            for n, (code, points) in enumerate(_SERIES.items()):
                dataset = code.split("-", 1)[1].rsplit("-", 1)[0].replace("-", "_")
                ind = WorldIndicator(
                    country_id=de.id, code=code, dataset_id=dataset, slice_json={}, slice_hash=f"h{n}",
                    name_ru=f"Показатель экономики Германии номер {n + 1}", name_en=f"Germany indicator {n + 1}",
                    name_quality="curated", unit="PC", unit_ru="%", frequency="monthly",
                    category_ru="Цены", source="Евростат",
                    history_start=points[0][0] if points else None,
                    history_end=points[-1][0] if points else None,
                    points_count=len(points), is_listed=True,
                )
                db.add(ind)
                await db.flush()
                ids[code] = ind.id
                db.add_all([WorldDataPoint(indicator_id=ind.id, date=d, value=v) for d, v in points])
            await db.commit()
            return ids

    return asyncio.run(_seed())


def test_nonzero_signal_from_tail_equals_full_check(auth_env, seeded):
    import app.api.world as w
    from app.services.world_subnational_queries import latest_world_point_series

    async def _check():
        async with auth_env["session_maker"]() as db:
            ids = list(seeded.values())
            recent = await latest_world_point_series(db, ids, limit=2)
            via_tail = await w._country_nonzero_signal(db, ids, recent)
            full = await w._ids_with_nonzero_signal(db, ids)
            return via_tail, full

    via_tail, full = asyncio.run(_check())
    assert via_tail == full
    assert seeded["de-nrg_bal_c-gwh-total"] in via_tail
    assert seeded["de-ext_lt_zero-total"] not in via_tail
    assert seeded["de-sts_empty-total"] not in via_tail


def test_nonzero_signal_asks_database_only_for_zero_tails(auth_env, seeded, monkeypatch):
    import app.api.world as w
    from app.services.world_subnational_queries import latest_world_point_series

    asked: list[list[int]] = []
    real = w._ids_with_nonzero_signal

    async def spy(db, ids):
        asked.append(sorted(ids))
        return await real(db, ids)

    monkeypatch.setattr(w, "_ids_with_nonzero_signal", spy)

    async def _run():
        async with auth_env["session_maker"]() as db:
            ids = list(seeded.values())
            recent = await latest_world_point_series(db, ids, limit=2)
            return await w._country_nonzero_signal(db, ids, recent)

    asyncio.run(_run())
    assert asked == [sorted([seeded["de-nrg_bal_c-gwh-total"], seeded["de-ext_lt_zero-total"]])]


def test_country_payload_same_as_full_signal_check(auth_env, seeded, monkeypatch):
    """Каталог с отбором по последним точкам совпадает с каталогом по полной проверке ненулевых точек."""
    import app.api.world as w

    async def _build():
        async with auth_env["session_maker"]() as db:
            return await w._build_country_detail_payload("germany", db, "test:new")

    new = asyncio.run(_build())
    # Чтение последних точек частями даёт тот же каталог.
    monkeypatch.setattr(w, "_LATEST_POINTS_CHUNK", 2)
    assert asyncio.run(_build()) == new
    monkeypatch.setattr(w, "_LATEST_POINTS_CHUNK", 2000)

    async def old_signal(db, ids, _recent):
        return await w._ids_with_nonzero_signal(db, ids)

    monkeypatch.setattr(w, "_country_nonzero_signal", old_signal)
    old = asyncio.run(_build())
    assert new == old
    codes = {item["code"] for cat in new["categories"] for item in cat["indicators"]}
    assert "de-nrg_bal_c-gwh-total" in codes
    assert "de-ext_lt_zero-total" not in codes and "de-sts_empty-total" not in codes
    by_code = {item["code"]: item for cat in new["categories"] for item in cat["indicators"]}
    assert by_code["de-une_rt_m-t-pc-act"]["last_value"] == 3.5
    assert by_code["de-une_rt_m-t-pc-act"]["prev_value"] == 3.4
    assert by_code["de-gov_10dd_edpt1-gd-pc-gdp"]["prev_value"] is None


def test_concurrent_cold_requests_build_once(auth_env, seeded, monkeypatch):
    """Повторы клиента и параллельные запросы ждут один расчёт и читают его запись."""
    import app.api.world as w

    real = w._build_country_detail_payload
    builds: list[str] = []

    async def slow_build(slug, db, cache_key):
        builds.append(slug)
        await asyncio.sleep(0.3)
        return await real(slug, db, cache_key)

    monkeypatch.setattr(w, "_build_country_detail_payload", slow_build)

    async def _one():
        async with auth_env["session_maker"]() as db:
            return await w._country_detail_payload("germany", db)

    async def _many():
        return await asyncio.gather(*(_one() for _ in range(3)))

    results = asyncio.run(_many())
    assert builds == ["germany"]
    assert results[0] == results[1] == results[2]


def test_build_proceeds_without_lock_when_redis_fails(auth_env, seeded, monkeypatch):
    import app.api.world as w

    async def broken():
        raise ConnectionError("redis down")

    monkeypatch.setattr(w, "get_redis", broken)

    async def _run():
        async with w._country_build_turn("fe:test:key") as waited:
            return waited

    assert asyncio.run(_run()) is False


def test_country_key_survives_forecast_bumps(auth_env):
    """Сдвиг `world` (прогнозный конвейер) не меняет ключ каталога; сдвиг `world-catalog` (загрузки) меняет."""
    import app.api.world as w
    import app.core.cache as cache_mod

    async def _keys():
        cache_mod._ver_local.clear()
        before = await w.country_detail_cache_key("germany")
        await auth_env["redis"].incr("fe:ver:world")
        cache_mod._ver_local.clear()
        after_world = await w.country_detail_cache_key("germany")
        await auth_env["state_redis"].incr("fe:ver:world-catalog")
        cache_mod._ver_local.clear()
        after_catalog = await w.country_detail_cache_key("germany")
        return before, after_world, after_catalog

    before, after_world, after_catalog = asyncio.run(_keys())
    assert before == after_world
    assert after_catalog != before
    assert ":country:v20:germany:" in after_catalog


def test_country_key_falls_back_to_world_generation(auth_env, monkeypatch):
    import app.api.world as w

    async def flaky(ns, rest):
        if ns == "world-catalog":
            raise ConnectionError("state redis down")
        return f"fe:{ns}:v7:{rest}"

    monkeypatch.setattr(w, "versioned_key", flaky)
    assert asyncio.run(w.country_detail_cache_key("germany")) == "fe:world:v7:country:v20:germany:ru"


def test_reliability_mart_skips_hidden_tab_timings(auth_env):
    """`hid=1` (вкладка уходила в фон) не идёт в задержку API; отказы такого запроса считаются."""
    from datetime import datetime, timezone

    from app.models import BehaviorEvent
    from app.services.analytics_marts import mart_reliability

    now = datetime.now(timezone.utc).replace(tzinfo=None)

    async def _run():
        async with auth_env["session_maker"]() as db:
            rows = [
                {"u": "/api/v1/ticker/live", "ms": ms, "st": 200, "ok": 1} for ms in (40, 50, 60)
            ] + [
                {"u": "/api/v1/ticker/live", "ms": 481343, "st": 200, "ok": 1, "hid": 1},
                {"u": "/api/v1/ticker/live", "ms": 15000, "st": 0, "ok": 0, "hid": 1},
            ]
            db.add_all([
                BehaviorEvent(event_type="api_timing", session_id_hash=f"s{i}", visitor_id_hash="v",
                              page="/", params_json=p, occurred_at=now, ingested_at=now)
                for i, p in enumerate(rows)
            ])
            await db.commit()
            return await mart_reliability(db, 1)

    out = asyncio.run(_run())
    ticker = next(x for x in out["api_slowest"] if x["endpoint"] == "/api/v1/ticker/live")
    assert ticker["calls"] == 3
    assert ticker["max_ms"] == 60
