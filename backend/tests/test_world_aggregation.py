"""Трёхуровневая политика агрегации мировых рядов: curated → passport → fallback."""

from __future__ import annotations

from datetime import date

from app.data.world_aggregation import (
    aggregation_decision_for,
    aggregation_policy_for,
    reset_passport_policy_cache,
)


class _Ind:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def test_curated_policy_still_wins():
    decision = aggregation_decision_for(_Ind(dataset_id="prc_hicp_midx", unit="I15"))
    assert decision.policy == "mean"
    assert decision.source == "curated"
    assert aggregation_policy_for(_Ind(dataset_id="nrg_cb_em", unit="GWH")) == "sum"


def test_passport_policy_from_yaml():
    reset_passport_policy_cache()
    payrolls = aggregation_decision_for(
        _Ind(provider="fred", dataset_id="PAYEMS", unit="THOUSANDS"),
    )
    assert payrolls.policy == "mean"
    assert payrolls.source == "passport"

    retail = aggregation_decision_for(
        _Ind(provider="fred", dataset_id="RSAFS", unit="USD_MN"),
    )
    assert retail.policy == "sum"
    assert retail.source == "passport"

    gdp = aggregation_decision_for(
        _Ind(provider="fred", dataset_id="GDPC1", unit="USD_BN_CHAINED"),
    )
    assert gdp.policy == "mean"
    assert gdp.source == "passport"

    money = aggregation_decision_for(
        _Ind(provider="boc_valet", dataset_id="V41552798", unit="CAD_MN"),
    )
    assert money.policy == "last"
    assert money.source == "passport"


def test_fallback_flow_sum_and_index_mean():
    flow = aggregation_decision_for(
        _Ind(provider="eurostat", dataset_id="ext_fake_m", unit="MIO_EUR"),
    )
    assert flow.policy == "sum"
    assert flow.source == "fallback"

    idx = aggregation_decision_for(
        _Ind(provider="eurostat", dataset_id="unknown_idx_m", unit="I15"),
    )
    assert idx.policy == "mean"
    assert idx.source == "fallback"

    stock = aggregation_decision_for(
        _Ind(provider="eurostat", dataset_id="nrg_stk_oam", unit="THS_T"),
    )
    assert stock.policy == "last"
    assert stock.source == "fallback"


def test_fallback_always_returns_a_policy():
    decision = aggregation_decision_for(_Ind(dataset_id="zz_unknown", unit=""))
    assert decision.policy == "mean"
    assert decision.source == "fallback"
    assert aggregation_policy_for(_Ind()) == "mean"


def test_invalid_passport_key_falls_back():
    reset_passport_policy_cache()
    # Нет такого ключа в YAML — не падаем, берём семантический фолбэк.
    decision = aggregation_decision_for(
        _Ind(provider="fred", dataset_id="NOT_A_SERIES", unit="INDEX"),
    )
    assert decision.source == "fallback"
    assert decision.policy == "mean"


def test_curated_empty_unit_covers_localized_unit_label():
    decision = aggregation_decision_for(
        _Ind(dataset_id="nrg_cb_cosm", unit="тыс. баррелей"),
    )
    assert decision.policy == "sum"
    assert decision.source == "curated"


def _saturdays(year: int, month: int) -> list[date]:
    from datetime import timedelta

    d = date(year, month, 1)
    while d.weekday() != 5:
        d += timedelta(days=1)
    out = []
    while d.month == month:
        out.append(d)
        d += timedelta(days=7)
    return out


def test_weekly_mean_to_monthly_keeps_weekly_level():
    from app.data.world_aggregation import aggregate_series

    saturdays = _saturdays(2024, 1) + _saturdays(2024, 2) + _saturdays(2024, 3)[:2]
    series = [(d, 220_000.0 + i * 100) for i, d in enumerate(saturdays)]
    monthly = aggregate_series(
        series, source_frequency="weekly", target_frequency="monthly", policy="mean",
    )
    assert [d for d, _ in monthly] == [date(2024, 1, 1), date(2024, 2, 1)]
    jan = [v for d, v in series if d.month == 1]
    assert monthly[0][1] == round(sum(jan) / len(jan), 4)
    assert monthly[0][1] < 300_000


def test_weekly_sum_when_passport_asks_for_sum():
    from app.data.world_aggregation import aggregate_series

    saturdays = _saturdays(2024, 1)
    series = [(d, 10.0) for d in saturdays]
    monthly = aggregate_series(
        series, source_frequency="weekly", target_frequency="monthly", policy="sum",
    )
    assert monthly == [(date(2024, 1, 1), round(10.0 * len(saturdays), 4))]


def test_weekly_to_annual_requires_twelve_complete_months():
    from app.data.world_aggregation import aggregate_series
    from datetime import timedelta

    series = []
    d = date(2024, 1, 6)
    while d.year == 2024:
        series.append((d, 100.0))
        d += timedelta(days=7)
    annual = aggregate_series(
        series, source_frequency="weekly", target_frequency="annual", policy="mean",
    )
    assert annual == [(date(2024, 1, 1), 100.0)]


def test_daily_to_monthly_drops_incomplete_tail():
    from app.data.world_aggregation import aggregate_series
    from datetime import timedelta

    series = []
    d = date(2024, 1, 1)
    while d < date(2024, 3, 10):
        if d.weekday() < 5:
            series.append((d, 1.10))
        d += timedelta(days=1)
    monthly = aggregate_series(
        series, source_frequency="daily", target_frequency="monthly", policy="mean",
    )
    assert [d for d, _ in monthly] == [date(2024, 1, 1), date(2024, 2, 1)]


def test_aggregate_forecast_fills_partial_year_and_drops_stub():
    from app.data.world_aggregation import aggregate_forecast_points

    actual = [(date(2024, m, 1), 100.0 + m) for m in range(1, 13)]
    actual += [(date(2025, m, 1), 120.0 + m) for m in range(1, 9)]
    forecast = [
        (date(2025, m, 1), 200.0 + m, 190.0 + m, 210.0 + m)
        for m in range(9, 13)
    ]
    forecast += [
        (date(2026, m, 1), 300.0 + m, 290.0 + m, 310.0 + m)
        for m in range(1, 9)
    ]
    annual = aggregate_forecast_points(
        actual, forecast,
        source_frequency="monthly", target_frequency="annual", policy="mean",
    )
    assert [d for d, *_ in annual] == [date(2025, 1, 1)]
    expected = sum([120.0 + m for m in range(1, 9)] + [200.0 + m for m in range(9, 13)]) / 12
    assert annual[0][1] == round(expected, 4)
    assert annual[0][2] is not None
    assert annual[0][3] is not None


def test_aggregate_forecast_quarterly_mean_bounds():
    from app.data.world_aggregation import aggregate_forecast_points

    actual = [(date(2024, m, 1), float(m)) for m in range(1, 8)]
    forecast = [
        (date(2024, 8, 1), 8.0, 7.0, 9.0),
        (date(2024, 9, 1), 9.0, 8.0, 10.0),
    ]
    quarterly = aggregate_forecast_points(
        actual, forecast,
        source_frequency="monthly", target_frequency="quarterly", policy="mean",
    )
    assert [d for d, *_ in quarterly] == [date(2024, 7, 1)]
    assert quarterly[0][1] == round((7 + 8 + 9) / 3, 4)
    assert quarterly[0][2] == round((7 + 7 + 8) / 3, 4)
    assert quarterly[0][3] == round((7 + 9 + 10) / 3, 4)
