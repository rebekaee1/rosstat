"""Тесты card_key, mode-резолвера и честности aggregated."""

from __future__ import annotations

from datetime import date

import pytest

from app.data.eurostat_listing import (
    card_key,
    dataset_stem,
    extra_dims_frozen,
    national_counterpart_dataset,
)
from app.data.eurostat_titles_ru import slice_reflected_in_name
from app.services.world_cards import (
    apply_resolved,
    build_modes_matrix,
    members_by_freq,
    parse_mode_token,
    resolve_series_for_mode,
)
from app.services.world_view_modes import transform_yoy


class _Ind:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def test_dataset_stem_strips_freq():
    assert dataset_stem("une_rt_m") == "une_rt"
    assert dataset_stem("une_rt_q") == "une_rt"
    assert dataset_stem("une_rt_a") == "une_rt"
    assert dataset_stem("sts_inpr_m") == "sts_inpr"
    assert dataset_stem("demo_minfind") == "demo_minfind"


def test_card_key_same_across_frequencies():
    sl_m = {"age": "TOTAL", "sex": "T", "freq": "M", "unit": "PC_ACT", "s_adj": "SA"}
    sl_q = {"age": "Y15-74", "sex": "T", "freq": "Q", "unit": "PC_ACT", "s_adj": "SA"}
    k_m = card_key(
        country_id=1, dataset_id="une_rt_m", unit="PC_ACT",
        unit_ru="% экономически активного населения", slice_json=sl_m,
    )
    k_q = card_key(
        country_id=1, dataset_id="une_rt_q", unit="PC_ACT",
        unit_ru="% экономически активного населения", slice_json=sl_q,
    )
    assert k_m == k_q
    assert k_m[1] == "une_rt"


def test_card_key_anti_merge_extra_dims():
    """Разные extra_dims (isced11) — разные карточки."""
    base = {"age": "Y15-74", "sex": "T", "freq": "A", "unit": "PC_ACT"}
    k1 = card_key(
        country_id=1, dataset_id="une_educ_a", unit="PC_ACT",
        unit_ru="%", slice_json={**base, "isced11": "ED0-2"},
    )
    k2 = card_key(
        country_id=1, dataset_id="une_educ_a", unit="PC_ACT",
        unit_ru="%", slice_json={**base, "isced11": "ED5-8"},
    )
    k3 = card_key(
        country_id=1, dataset_id="une_rt_a", unit="PC_ACT",
        unit_ru="%", slice_json=base,
    )
    assert k1 != k2
    assert k1 != k3  # другой stem
    assert extra_dims_frozen({**base, "isced11": "ED0-2"}) == (("isced11", "ED0-2"),)


def test_card_key_anti_merge_measure():
    k_pct = card_key(
        country_id=1, dataset_id="une_rt_m", unit="PC_ACT",
        unit_ru="% экономически активного населения",
        slice_json={"age": "TOTAL", "sex": "T", "unit": "PC_ACT"},
    )
    k_ths = card_key(
        country_id=1, dataset_id="une_rt_m", unit="THS_PER",
        unit_ru="тысяч человек",
        slice_json={"age": "TOTAL", "sex": "T", "unit": "THS_PER"},
    )
    assert k_pct != k_ths


def test_national_counterpart():
    assert national_counterpart_dataset("demo_r_minfind") == "demo_minfind"
    assert national_counterpart_dataset("demo_minfind") is None


def test_slice_reflected_in_name_age():
    assert slice_reflected_in_name(
        "Младенческая смертность, младше 1 дня, человек",
        {"age": "D0", "sex": "T"},
    )
    assert not slice_reflected_in_name(
        "Младенческая смертность по полу и возрасту, человек",
        {"age": "D0", "sex": "T"},
    )


def test_parse_mode_legacy_and_composite():
    p = parse_mode_token("yoy-quarterly", native_freq="monthly")
    assert p.type == "yoy" and p.freq == "quarterly" and p.id == "yoy-quarterly"

    p2 = parse_mode_token("mom", native_freq="monthly")
    assert p2.id == "step-monthly" and p2.legacy

    p3 = parse_mode_token("level", native_freq="quarterly")
    assert p3.id == "level-quarterly"

    p4 = parse_mode_token("avg_year", native_freq="monthly")
    assert p4.id == "level-annual" and p4.legacy

    p5 = parse_mode_token("yoy_abs", native_freq="monthly")
    assert p5.id == "yoyabs-monthly"


def test_resolve_official_vs_aggregated():
    monthly = _Ind(
        code="de-une_rt_m", frequency="monthly", points_count=400,
        history_start=date(1990, 1, 1), history_end=date(2026, 1, 1),
    )
    quarterly = _Ind(
        code="de-une_rt_q", frequency="quarterly", points_count=100,
        history_start=date(1990, 1, 1), history_end=date(2026, 1, 1),
    )
    by_freq = members_by_freq([monthly, quarterly])

    parsed = parse_mode_token("yoy-quarterly", native_freq="monthly")
    r = resolve_series_for_mode(parsed=parsed, by_freq=by_freq, signed=False)
    assert r is not None
    assert r.source_code == "de-une_rt_q"
    assert r.aggregated is False
    assert r.official is True

    # только monthly → level-quarterly агрегируется
    by_m = members_by_freq([monthly])
    parsed2 = parse_mode_token("level-quarterly", native_freq="monthly")
    r2 = resolve_series_for_mode(parsed=parsed2, by_freq=by_m, signed=False)
    assert r2 is not None
    assert r2.aggregated is True
    assert r2.source_code == "de-une_rt_m"


def test_apply_resolved_aggregated_then_yoy():
    series = []
    for y in (2024, 2025):
        for m in range(1, 13):
            series.append((date(y, m, 1), 100.0 + m + (y - 2024) * 12))
    from app.services.world_cards import ResolvedSeries
    resolved = ResolvedSeries(
        source_code="x", frequency="quarterly",
        transform="agg:quarterly:yoy", aggregated=True, official=False,
    )
    out = apply_resolved(series, resolved)
    # есть точки г/г на квартальных средних
    assert len(out) >= 1
    assert all(isinstance(v, float) for _, v in out)


def test_modes_matrix_marks_unavailable():
    monthly = _Ind(
        code="m", frequency="monthly", points_count=60,
        history_start=date(2020, 1, 1), history_end=date(2025, 1, 1),
    )
    by_freq = members_by_freq([monthly])
    modes = build_modes_matrix(by_freq=by_freq, series_by_code=None, unit="%")
    by_id = {m["id"]: m for m in modes}
    assert by_id["level-monthly"]["available"] is True
    assert by_id["level-monthly"]["official"] is True
    assert by_id["level-quarterly"]["available"] is True
    assert by_id["level-quarterly"]["official"] is False  # aggregated path
    assert by_id["step-monthly"]["available"] is True
    assert by_id["yoy-monthly"]["available"] is True


def test_modes_matrix_sub_labels_unique_within_group():
    """Нижний ряд различает частоты: подписи внутри группы не повторяются."""
    quarterly = _Ind(
        code="q", frequency="quarterly", points_count=40,
        history_start=date(2015, 1, 1), history_end=date(2026, 1, 1),
    )
    modes = build_modes_matrix(
        by_freq=members_by_freq([quarterly]),
        series_by_code={"q": [(date(2015, 1, 1), 10.0), (date(2015, 4, 1), 11.0)]},
        unit="тысяч человек",
    )
    by_group: dict[str, list[str]] = {}
    for m in modes:
        by_group.setdefault(m["group"], []).append(m["label"])
    for group, labels in by_group.items():
        assert len(labels) == len(set(labels)), f"дубли подписей в «{group}»: {labels}"


@pytest.mark.parametrize(
    ("points", "expected", "forbidden"),
    [
        ([(date(2020, 1, 1), 10.0), (date(2020, 4, 1), 12.0)], "yoy", "yoyabs"),
        ([(date(2020, 1, 1), -3.0), (date(2020, 4, 1), 2.0)], "yoyabs", "yoy"),
    ],
)
def test_modes_matrix_single_yoy_variant(points, expected, forbidden):
    """«К году» — либо процент, либо единицы, но не оба сразу."""
    quarterly = _Ind(
        code="q", frequency="quarterly", points_count=40,
        history_start=date(2015, 1, 1), history_end=date(2026, 1, 1),
    )
    modes = build_modes_matrix(
        by_freq=members_by_freq([quarterly]),
        series_by_code={"q": points},
        unit="млрд евро",
    )
    types = {m["type"] for m in modes}
    assert expected in types
    assert forbidden not in types


# --- API integration --------------------------------------------------------


@pytest.fixture
def world_card_client(auth_env):
    import asyncio
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

            def add_unemp(freq, code, pts, age="TOTAL", unit="PC_ACT"):
                sl = {"age": age, "sex": "T", "unit": unit, "s_adj": "SA"}
                if freq == "monthly":
                    sl["freq"] = "M"
                    ds = "une_rt_m"
                elif freq == "quarterly":
                    sl["freq"] = "Q"
                    sl["age"] = "Y15-74" if age == "TOTAL" else age
                    ds = "une_rt_q"
                else:
                    sl["freq"] = "A"
                    sl["age"] = "Y15-74" if age == "TOTAL" else age
                    ds = "une_rt_a"
                ind = WorldIndicator(
                    country_id=de.id,
                    code=code,
                    dataset_id=ds,
                    slice_json=sl,
                    slice_hash=code,
                    name_ru=f"Безработица, %, {freq}",
                    name_quality="curated",
                    unit=unit,
                    unit_ru="% экономически активного населения",
                    frequency=freq,
                    category_ru="Рынок труда",
                    source="Евростат",
                    history_start=date(2020, 1, 1),
                    history_end=date(2025, 6, 1),
                    points_count=pts,
                    is_listed=(freq == "monthly"),
                )
                db.add(ind)
                return ind

            m = add_unemp("monthly", "de-une_rt_m-total", 72)
            q = add_unemp("quarterly", "de-une_rt_q-total", 24)
            a = add_unemp("annual", "de-une_rt_a-total", 12)
            await db.flush()
            # monthly points 2020-01 .. 2025-12 (72)
            iid = m.id
            i = 0
            for y in range(2020, 2026):
                for mo in range(1, 13):
                    db.add(WorldDataPoint(
                        indicator_id=iid, date=date(y, mo, 1), value=3.0 + i * 0.01,
                    ))
                    i += 1
            # quarterly
            for y in range(2020, 2026):
                for mo in (1, 4, 7, 10):
                    db.add(WorldDataPoint(
                        indicator_id=q.id, date=date(y, mo, 1),
                        value=3.5 + y * 0.01,
                    ))
            for y in range(2014, 2026):
                db.add(WorldDataPoint(
                    indicator_id=a.id, date=date(y, 1, 1), value=4.0 + (y - 2014) * 0.1,
                ))
            await db.commit()

    asyncio.run(_seed())
    with TestClient(auth_env["app"]) as tc:
        yield tc


def test_api_card_frequencies_and_yoy_quarterly(world_card_client):
    meta = world_card_client.get(
        "/api/v1/world/indicators/germany/de-une_rt_m-total"
    )
    assert meta.status_code == 200
    body = meta.json()
    assert body["primary_code"] == "de-une_rt_m-total"
    freqs = {f["freq"] for f in body["frequencies"]}
    assert freqs == {"monthly", "quarterly", "annual"}
    assert all(f["official"] for f in body["frequencies"])

    mode_ids = {m["id"]: m for m in body["modes"]}
    assert mode_ids["yoy-quarterly"]["available"] is True
    assert mode_ids["yoy-quarterly"]["official"] is True

    data = world_card_client.get(
        "/api/v1/world/indicators/germany/de-une_rt_m-total/data",
        params={"mode": "yoy-quarterly"},
    )
    assert data.status_code == 200
    payload = data.json()
    assert payload["aggregated"] is False
    assert payload["source_code"] == "de-une_rt_q-total"
    assert payload["frequency"] == "quarterly"
    assert payload["mode"] == "yoy-quarterly"
    assert len(payload["points"]) >= 1


def test_api_legacy_mode_still_works(world_card_client):
    data = world_card_client.get(
        "/api/v1/world/indicators/germany/de-une_rt_m-total/data",
        params={"mode": "mom"},
    )
    assert data.status_code == 200
    assert data.json()["mode"] == "step-monthly"
    assert data.json()["aggregated"] is False
