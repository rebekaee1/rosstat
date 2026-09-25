from datetime import date
from types import SimpleNamespace
import math

from dateutil.relativedelta import relativedelta

from app.data.world_forecast_policy import forecast_eligibility_for
from app.services.world_forecaster import (
    WORLD_FORECAST_METHOD_VERSION,
    is_percentage_unit,
    publishable_world_forecast,
    train_quality_gated_world_forecast,
)
from app.services.world_source_adapter import WorldSeriesRef


def _dates(start: date, count: int, months: int) -> list[date]:
    return [start + relativedelta(months=index * months) for index in range(count)]


def test_monthly_shared_methodology_passes_against_naive():
    dates = _dates(date(2018, 1, 1), 96, 1)
    values = [
        100.0 + (index % 12) * 2.0 + (index // 12) * 10.0
        for index in range(96)
    ]

    gate = train_quality_gated_world_forecast(
        dates,
        values,
        frequency="monthly",
        horizon=12,
        season=12,
        strategy="monthly_auto",
    )

    assert gate.status == "passed"
    assert gate.strategy == "monthly_auto"
    assert gate.mase is not None and gate.mase < 1
    assert gate.baseline_mase is not None and gate.baseline_mase > gate.mase
    assert gate.result is not None
    assert gate.result.model_name == "World-Monthly-Auto-MW-v1"
    assert len(gate.result.points) == 12
    assert gate.result.points[0].date == date(2026, 1, 1)


def test_gate_rejects_constant_and_irregular_series():
    dates = _dates(date(2018, 1, 1), 72, 1)
    constant = train_quality_gated_world_forecast(
        dates,
        [10.0] * 72,
        frequency="monthly",
        horizon=12,
        season=12,
        strategy="monthly_auto",
    )
    assert constant.status == "failed"
    assert constant.reason == "constant_or_unscaled_series"

    irregular_dates = [*dates[:40], dates[40] + relativedelta(months=1), *dates[41:]]
    irregular = train_quality_gated_world_forecast(
        irregular_dates,
        [float(index) for index in range(72)],
        frequency="monthly",
        horizon=12,
        season=12,
        strategy="monthly_auto",
    )
    assert irregular.status == "failed"
    assert irregular.reason == "irregular_calendar"

    # Даже одна дыра нарушает позиционную сезонность. Короткий хвост после
    # пропуска не должен выглядеть как полный 72-месячный ряд.
    full_dates = _dates(date(2018, 1, 1), 96, 1)
    one_gap = [*full_dates[:40], *full_dates[41:]]
    gapped = train_quality_gated_world_forecast(
        one_gap,
        [float(index) for index in range(95)],
        frequency="monthly",
        horizon=12,
        season=12,
        strategy="monthly_auto",
    )
    assert gapped.reason == "recent_history_gap"


def test_quarterly_auto_uses_shared_positive_and_signed_strategies():
    dates = _dates(date(2012, 1, 1), 56, 3)
    positive = train_quality_gated_world_forecast(
        dates,
        [100.0 + index * 2.0 + (index % 4) * 3.0 for index in range(56)],
        frequency="quarterly",
        horizon=4,
        season=4,
        strategy="quarterly_auto",
    )
    assert positive.strategy == "generic_quarterly"

    signed = train_quality_gated_world_forecast(
        dates,
        [-20.0 + index * 0.8 + (index % 4) * 2.0 for index in range(56)],
        frequency="quarterly",
        horizon=4,
        season=4,
        strategy="quarterly_auto",
    )
    assert signed.strategy == "signed_quarterly"


def test_annual_auto_world_forecast_publishes():
    dates = _dates(date(2000, 1, 1), 25, 12)
    values = [15.0 - 0.12 * index for index in range(25)]
    gate = train_quality_gated_world_forecast(
        dates,
        values,
        frequency="annual",
        horizon=2,
        season=1,
        strategy="annual_auto",
        strict=False,
    )
    assert gate.status in {"passed", "advisory"}
    assert gate.result is not None
    assert len(gate.result.points) == 2
    assert gate.result.points[0].date == date(2025, 1, 1)
    assert all(math.isfinite(float(point.value)) for point in gate.result.points)


def test_quality_fail_is_advisory_unless_strict(monkeypatch):
    from app.services import world_forecaster as wf
    from app.services.forecaster import ForecastPoint, ForecastResult

    dates = _dates(date(2018, 1, 1), 96, 1)
    values = [
        100.0 + (index % 12) * 2.0 + (index // 12) * 10.0
        for index in range(96)
    ]
    real_run = wf._run_primary_strategy

    def fake_run(dates, values, *, frequency, horizon, strategy_name):
        result = real_run(
            dates, values,
            frequency=frequency, horizon=horizon, strategy_name=strategy_name,
        )
        if result is None:
            return None
        if horizon != 12 or len(dates) == 96:
            return result
        poisoned = [
            ForecastPoint(
                date=point.date, value=point.value * 80.0,
                lower_bound=None, upper_bound=None,
            )
            for point in result.points
        ]
        return ForecastResult(
            model_name=result.model_name, aic=result.aic, bic=result.bic,
            points=poisoned,
        )

    monkeypatch.setattr(wf, "_run_primary_strategy", fake_run)
    advisory = wf.train_quality_gated_world_forecast(
        dates, values,
        frequency="monthly", horizon=12, season=12,
        strategy="monthly_auto", strict=False,
    )
    assert advisory.status == "advisory"
    assert advisory.result is not None
    assert len(advisory.result.points) == 12

    failed = wf.train_quality_gated_world_forecast(
        dates, values,
        frequency="monthly", horizon=12, season=12,
        strategy="monthly_auto", strict=True,
    )
    assert failed.status == "failed"
    assert failed.result is None


def test_backtest_scale_uses_only_training_prefix(monkeypatch):
    from app.services import world_forecaster as wf

    dates = _dates(date(2000, 1, 1), 24, 12)
    values = [float(index + 1) for index in range(24)]
    lengths = []
    original = wf._scale

    def observed_scale(history, season):
        lengths.append(len(history))
        return original(history, season)

    monkeypatch.setattr(wf, "_scale", observed_scale)
    wf.train_quality_gated_world_forecast(
        dates, values, frequency="annual", horizon=2, season=1,
        strategy="annual_auto", strict=True,
    )
    assert len(lengths) >= 3
    assert max(lengths) <= len(values) - 2


def test_old_gate_or_advisory_never_public():
    assert is_percentage_unit("PERCENT")
    assert is_percentage_unit("%")
    assert not publishable_world_forecast(SimpleNamespace(
        gate_status="passed", model_params={"method_version": 1},
    ))
    assert not publishable_world_forecast(SimpleNamespace(
        gate_status="advisory", model_params={"method_version": WORLD_FORECAST_METHOD_VERSION},
    ))
    assert publishable_world_forecast(SimpleNamespace(
        gate_status="passed", model_params={"method_version": WORLD_FORECAST_METHOD_VERSION},
    ))


def test_bounded_batch_advances_past_unchanged_rows():
    from app.services.world_forecast_pipeline import WorldForecastCandidate, select_forecast_batch

    rows = [WorldForecastCandidate(
        id=index, country_slug="germany", provider="eurostat",
        dataset_id=f"d{index}", code=f"de-{index}", frequency="annual",
    ) for index in range(1, 6)]
    selected, unchanged = select_forecast_batch(rows, {1, 2, 4}, 2)
    assert [row.id for row in selected] == [3, 5]
    assert unchanged == set()


def test_eurostat_forecast_requires_applied_source_revision():
    import asyncio
    from datetime import datetime

    from app.services.world_forecast_pipeline import world_forecast_source_ready

    class Db:
        def __init__(self, state):
            self.state = state

        async def get(self, _model, _key):
            return self.state

    indicator = SimpleNamespace(provider="eurostat", dataset_id="namq_10_gdp")
    forecast = SimpleNamespace(created_at=datetime(2026, 9, 24, 12))
    assert not asyncio.run(world_forecast_source_ready(Db(None), indicator))
    assert not asyncio.run(world_forecast_source_ready(
        Db(SimpleNamespace(status="pending", last_success_at=datetime(2026, 9, 23))),
        indicator,
    ))
    ready = SimpleNamespace(status="ok", last_success_at=datetime(2026, 9, 24, 11))
    assert asyncio.run(world_forecast_source_ready(Db(ready), indicator, forecast=forecast))
    revised = SimpleNamespace(status="ok", last_success_at=datetime(2026, 9, 24, 13))
    assert not asyncio.run(world_forecast_source_ready(Db(revised), indicator, forecast=forecast))


def test_policy_is_official_provider_and_freshness_fail_closed():
    base = dict(
        provider="eurostat",
        dataset_id="une_rt_m",
        unit="PC_ACT",
        frequency="monthly",
        is_listed=True,
        name_quality="curated",
        points_count=120,
        history_end=date(2026, 7, 1),
    )
    eligibility, reason = forecast_eligibility_for(
        SimpleNamespace(**base),
        today=date(2026, 8, 6),
    )
    assert reason == "eligible"
    assert eligibility is not None
    assert eligibility.registry_key == (
        "eurostat", "une_rt_m", "PC_ACT", "monthly", "monthly_auto",
    )

    eurostat_annual = SimpleNamespace(
        **{
            **base,
            "frequency": "annual",
            "points_count": 20,
            "history_end": date(2025, 1, 1),
        }
    )
    annual_el, annual_reason = forecast_eligibility_for(
        eurostat_annual, today=date(2026, 8, 6),
    )
    assert annual_reason == "eligible"
    assert annual_el is not None
    assert annual_el.strategy == "annual_auto"
    assert annual_el.horizon == 2
    assert annual_el.season == 1

    fred = SimpleNamespace(**{**base, "provider": "fred"})
    assert forecast_eligibility_for(fred, today=date(2026, 8, 6))[1] == "eligible"

    unknown = SimpleNamespace(**{**base, "provider": "news_aggregator"})
    assert forecast_eligibility_for(unknown)[1] == "provider_not_approved"

    imf_annual = SimpleNamespace(
        **{
            **base,
            "provider": "imf",
            "dataset_id": "WEO",
            "unit": "BN_USD",
            "frequency": "annual",
            "points_count": 40,
            "history_end": date(2024, 1, 1),
        }
    )
    assert forecast_eligibility_for(imf_annual)[1] == "provider_not_approved"

    stale = SimpleNamespace(**{**base, "history_end": date(2025, 1, 1)})
    assert forecast_eligibility_for(stale, today=date(2026, 8, 6))[1] == "series_is_stale"
    future = SimpleNamespace(**{**base, "history_end": date(2026, 9, 1)})
    assert forecast_eligibility_for(future, today=date(2026, 8, 6))[1] == "future_observation"


def test_series_identity_includes_provider_and_dimensions():
    common = dict(
        dataset_id="gdp",
        series_id="real",
        country_code="US",
        frequency="quarterly",
        unit_code="INDEX",
        dimensions={"adjustment": "SA"},
    )
    bea = WorldSeriesRef(provider="bea", **common)
    aggregator = WorldSeriesRef(provider="aggregator", **common)

    assert bea.slice_hash != aggregator.slice_hash
    assert bea.slice_hash == WorldSeriesRef(provider="bea", **common).slice_hash


def test_world_forecast_points_aggregate_to_annual_level():
    from app.data.world_aggregation import aggregate_forecast_points

    actual = [(date(2023, m, 1), 10.0) for m in range(1, 13)]
    actual += [(date(2024, m, 1), 12.0) for m in range(1, 7)]
    forecast = [
        (date(2024, m, 1), 12.0, 11.0, 13.0) for m in range(7, 13)
    ]
    annual = aggregate_forecast_points(
        actual, forecast,
        source_frequency="monthly",
        target_frequency="annual",
        policy="mean",
    )
    assert len(annual) == 1
    assert annual[0][0] == date(2024, 1, 1)
    assert annual[0][1] == 12.0
    assert annual[0][2] == round((12 * 6 + 11 * 6) / 12, 4)


def test_world_forecast_priority_order_puts_us_and_concepts_first():
    from dataclasses import replace
    from app.config import Settings
    from app.services.world_forecast_pipeline import (
        WorldForecastCandidate,
        parse_priority_countries,
        sort_world_forecast_candidates,
    )

    default = Settings.model_fields["world_forecast_priority_countries"].default
    assert default.startswith("united-states,germany")
    assert "south-korea" in default
    assert "korea" not in {part.strip() for part in default.split(",")}

    priority = parse_priority_countries(default)

    rows = [
        WorldForecastCandidate(
            id=50, country_slug="austria", provider="eurostat",
            dataset_id="foo", code="at-foo", frequency="annual",
        ),
        WorldForecastCandidate(
            id=3, country_slug="united-states", provider="imf",
            dataset_id="weo", code="us-weo-lur", frequency="annual",
        ),
        WorldForecastCandidate(
            id=4, country_slug="united-states", provider="fred",
            dataset_id="gdp", code="us-gdp", frequency="quarterly",
        ),
        WorldForecastCandidate(
            id=1, country_slug="united-states", provider="eurostat",
            dataset_id="une_rt_m", code="us-une", frequency="monthly",
        ),
        WorldForecastCandidate(
            id=2, country_slug="united-states", provider="bls",
            dataset_id="ln", code="us-unemployment-rate", frequency="monthly",
        ),
        WorldForecastCandidate(
            id=8, country_slug="germany", provider="eurostat",
            dataset_id="abc", code="de-abc", frequency="monthly",
        ),
        WorldForecastCandidate(
            id=7, country_slug="germany", provider="eurostat",
            dataset_id="une_rt_m", code="de-une", frequency="monthly",
        ),
    ]
    rows = [replace(row, eligible_for_training=row.provider != "imf") for row in rows]
    ordered = sort_world_forecast_candidates(rows, priority_countries=priority)
    assert [row.country_slug for row in ordered] == [
        "united-states", "united-states", "united-states",
        "germany", "germany",
        "austria", "united-states",
    ]
    us = [row.code for row in ordered if row.country_slug == "united-states"]
    assert us == ["us-unemployment-rate", "us-une", "us-gdp", "us-weo-lur"]
    de = [row.code for row in ordered if row.country_slug == "germany"]
    assert de == ["de-une", "de-abc"]


def test_world_forecast_unchanged_skip_by_fingerprint_and_force():
    from datetime import datetime

    from app.services.world_forecast_pipeline import (
        forecast_fingerprint,
        forecast_is_unchanged,
    )

    now = datetime(2026, 9, 20, 12, 0, 0)
    history_end = date(2026, 8, 1)
    latest = SimpleNamespace(
        created_at=datetime(2026, 9, 19, 8, 0, 0),
        model_params=forecast_fingerprint(history_end=history_end, points_count=120),
        gate_status="failed",
    )
    assert forecast_is_unchanged(
        latest, history_end=history_end, points_count=120,
        now=now, max_age_days=30, force=False,
    )
    assert not forecast_is_unchanged(
        latest, history_end=date(2026, 9, 1), points_count=120,
        now=now, max_age_days=30, force=False,
    )
    assert not forecast_is_unchanged(
        latest, history_end=history_end, points_count=121,
        now=now, max_age_days=30, force=False,
    )
    revised = SimpleNamespace(
        created_at=latest.created_at,
        model_params=forecast_fingerprint(
            history_end=history_end, points_count=120, history_digest="old-history",
        ),
        gate_status="passed",
    )
    assert not forecast_is_unchanged(
        revised, history_end=history_end, points_count=120,
        history_digest="revised-history", now=now, max_age_days=30, force=False,
    )
    pending_source = SimpleNamespace(
        created_at=latest.created_at,
        model_params=forecast_fingerprint(
            history_end=history_end, points_count=120, source_ready=False,
        ),
        gate_status="skipped",
    )
    assert not forecast_is_unchanged(
        pending_source, history_end=history_end, points_count=120,
        source_ready=True, now=now, max_age_days=30, force=False,
    )
    assert not forecast_is_unchanged(
        latest, history_end=history_end, points_count=120,
        now=now, max_age_days=30, force=True,
    )
    stale = SimpleNamespace(
        created_at=datetime(2026, 8, 1, 0, 0, 0),
        model_params=forecast_fingerprint(history_end=history_end, points_count=120),
        gate_status="passed",
    )
    assert not forecast_is_unchanged(
        stale, history_end=history_end, points_count=120,
        now=now, max_age_days=30, force=False,
    )


def test_eurostat_success_after_forecast_retrains_even_if_points_unchanged():
    from dataclasses import replace
    from datetime import datetime

    from app.services.world_forecast_pipeline import (
        WorldForecastCandidate,
        classify_unchanged,
        forecast_fingerprint,
    )

    history_end = date(2026, 8, 1)
    forecast = SimpleNamespace(
        created_at=datetime(2026, 9, 19, 8),
        model_params=forecast_fingerprint(
            history_end=history_end, points_count=120, history_digest="same-history",
        ),
        gate_status="passed",
    )
    candidate = WorldForecastCandidate(
        id=7, country_slug="germany", provider="eurostat",
        dataset_id="demo_test", code="de-demo-test", frequency="monthly",
        history_end=history_end, points_count=120, history_digest="same-history",
        source_last_success_at=datetime(2026, 9, 20, 8),
    )
    now = datetime(2026, 9, 21, 8)
    assert classify_unchanged([candidate], {7: forecast}, now=now, max_age_days=30, force=False) == set()
    earlier_source = replace(candidate, source_last_success_at=datetime(2026, 9, 18, 8))
    assert classify_unchanged(
        [earlier_source], {7: forecast}, now=now, max_age_days=30, force=False,
    ) == {7}


def test_world_forecast_legacy_row_without_fingerprint_retrains():
    from datetime import datetime

    from app.services.world_forecast_pipeline import forecast_is_unchanged

    now = datetime(2026, 9, 20, 12, 0, 0)
    latest = SimpleNamespace(
        created_at=datetime(2026, 9, 19, 15, 0, 0),
        model_params={"registry_key": ["eurostat"], "gate": "rolling_origin_mase"},
        gate_status="passed",
    )
    assert not forecast_is_unchanged(
        latest, history_end=date(2026, 8, 1), points_count=80,
        now=now, max_age_days=30, force=False,
    )
    assert not forecast_is_unchanged(
        latest, history_end=date(2026, 9, 20), points_count=81,
        now=now, max_age_days=30, force=False,
    )
