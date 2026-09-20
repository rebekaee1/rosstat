from datetime import date
from types import SimpleNamespace
import math

from dateutil.relativedelta import relativedelta

from app.data.world_forecast_policy import forecast_eligibility_for
from app.services.world_forecaster import train_quality_gated_world_forecast
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

    # Одна дыра в месячном календаре (как FRED CPI 2025-10) — не отказ.
    one_gap = [*dates[:40], *dates[41:]]
    gapped = train_quality_gated_world_forecast(
        one_gap,
        [float(index) for index in range(71)],
        frequency="monthly",
        horizon=12,
        season=12,
        strategy="monthly_auto",
    )
    assert gapped.reason != "irregular_calendar"


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
        if horizon != 3:
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
