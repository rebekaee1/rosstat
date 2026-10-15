"""Круг 14: прогноз нашей модели на всех рядах стран (``world_forecast_publish_all``).

Решение владельца 15.10: ряд, не прошедший проверку на прошлых данных или слишком
короткий для неё, получает прогноз главной модели со статусом ``advisory``; порог
проверки не меняется, витрина остаётся только с проверенными, технические отказы,
выход за границы и взрывная экстраполяция — по-прежнему без прогноза.
"""
from datetime import date, datetime
from types import SimpleNamespace

from dateutil.relativedelta import relativedelta

from app.config import settings
from app.data.world_forecast_policy import forecast_eligibility_for
from app.services import world_forecaster as wf
from app.services.forecaster import ForecastPoint, ForecastResult
from app.services.world_forecast_gate import (
    CHECKED_GATE_STATUSES,
    PUBLISHED_GATE_STATUSES,
    WORLD_FORECAST_METHOD_VERSION,
    publishable_world_forecast,
)


def _dates(start: date, count: int, months: int) -> list[date]:
    return [start + relativedelta(months=index * months) for index in range(count)]


def _monthly(count: int) -> tuple[list[date], list[float]]:
    return (
        _dates(date(2010, 1, 1), count, 1),
        [100.0 + (index % 12) * 2.0 + (index // 12) * 10.0 for index in range(count)],
    )


def _poison_backtest(monkeypatch, *, full_length: int, factor: float = 80.0):
    """Главная модель врёт на окнах проверки, но честна на всей истории."""
    real_run = wf._run_primary_strategy

    def fake_run(dates, values, *, frequency, horizon, strategy_name):
        result = real_run(dates, values, frequency=frequency, horizon=horizon, strategy_name=strategy_name)
        if result is None or len(dates) == full_length:
            return result
        return ForecastResult(
            model_name=result.model_name, aic=result.aic, bic=result.bic,
            points=[
                ForecastPoint(date=p.date, value=p.value * factor, lower_bound=None, upper_bound=None)
                for p in result.points
            ],
        )

    monkeypatch.setattr(wf, "_run_primary_strategy", fake_run)


def test_quality_failure_publishes_primary_model_as_advisory(monkeypatch):
    dates, values = _monthly(96)
    _poison_backtest(monkeypatch, full_length=96)
    strict = wf.train_quality_gated_world_forecast(
        dates, values, frequency="monthly", horizon=12, season=12,
        strategy="monthly_auto", candidates=False,
    )
    assert strict.status == "failed" and strict.result is None

    gate = wf.train_quality_gated_world_forecast(
        dates, values, frequency="monthly", horizon=12, season=12,
        strategy="monthly_auto", candidates=False, publish_all=True,
    )
    assert gate.status == "advisory"
    assert gate.reason == strict.reason  # причина отказа проверки сохраняется для аудита
    assert gate.mase == strict.mase
    assert gate.details["publication"] == "unchecked"
    assert len(gate.result.points) == 12
    assert gate.result.points[0].date == date(2018, 1, 1)
    # Честная модель на полной истории, без «отравленных» значений и без диапазона.
    assert all(p.value < 1000 for p in gate.result.points)
    assert all(p.lower_bound == p.value == p.upper_bound for p in gate.result.points)


def test_checked_model_still_wins_over_unchecked(monkeypatch):
    dates, values = _monthly(96)
    gate = wf.train_quality_gated_world_forecast(
        dates, values, frequency="monthly", horizon=12, season=12,
        strategy="monthly_auto", publish_all=True,
    )
    plain = wf.train_quality_gated_world_forecast(
        dates, values, frequency="monthly", horizon=12, season=12, strategy="monthly_auto",
    )
    assert gate.status == plain.status
    if plain.status == "passed":
        assert "publication" not in (gate.details or {})


def test_short_history_gets_forecast_without_backtest():
    # 40 месяцев: короче проверки (72), но наша месячная модель считает от 36.
    dates, values = _monthly(40)
    strict = wf.train_quality_gated_world_forecast(
        dates, values, frequency="monthly", horizon=12, season=12, strategy="monthly_auto",
    )
    assert strict.result is None and strict.reason == "history_too_short"
    gate = wf.train_quality_gated_world_forecast(
        dates, values, frequency="monthly", horizon=12, season=12,
        strategy="monthly_auto", publish_all=True,
    )
    assert gate.status == "advisory" and gate.reason == "history_too_short"
    assert gate.mase is None and gate.origins == 0
    assert len(gate.result.points) == 12

    annual_dates = _dates(date(2014, 1, 1), 11, 12)
    annual_values = [50.0 + index * 1.5 + (index % 3) for index in range(11)]
    annual = wf.train_quality_gated_world_forecast(
        annual_dates, annual_values, frequency="annual", horizon=1, season=1,
        strategy="annual_auto", publish_all=True,
    )
    assert annual.status == "advisory"
    assert annual.result.points[0].date == date(2025, 1, 1)


def test_unchecked_keeps_safety_rejections(monkeypatch):
    # Короче минимума самой модели — прогноза нет.
    dates, values = _monthly(30)
    gate = wf.train_quality_gated_world_forecast(
        dates, values, frequency="monthly", horizon=12, season=12,
        strategy="monthly_auto", publish_all=True,
    )
    assert gate.result is None

    # Выход за границы процента и взрывная экстраполяция не публикуются.
    dates, values = _monthly(48)
    real_run = wf._run_primary_strategy

    def exploding(dates, values, *, frequency, horizon, strategy_name):
        result = real_run(dates, values, frequency=frequency, horizon=horizon, strategy_name=strategy_name)
        return ForecastResult(
            model_name=result.model_name, aic=None, bic=None,
            points=[ForecastPoint(date=p.date, value=p.value * 100, lower_bound=None, upper_bound=None)
                    for p in result.points],
        )

    monkeypatch.setattr(wf, "_run_primary_strategy", exploding)
    gate = wf.train_quality_gated_world_forecast(
        dates, values, frequency="monthly", horizon=12, season=12,
        strategy="monthly_auto", publish_all=True,
    )
    assert gate.result is None

    monkeypatch.setattr(wf, "_run_primary_strategy", real_run)
    percent = [min(99.0, v / 3) for v in values]
    gate = wf.train_quality_gated_world_forecast(
        dates, percent, frequency="monthly", horizon=12, season=12,
        strategy="monthly_auto", publish_all=True, bounds=(0.0, 1.0),
    )
    assert gate.result is None

    irregular = [date(2020, 1, 1), date(2020, 1, 15)] + _dates(date(2020, 2, 1), 46, 1)
    gate = wf.train_quality_gated_world_forecast(
        irregular, values, frequency="monthly", horizon=12, season=12,
        strategy="monthly_auto", publish_all=True,
    )
    assert gate.result is None


def test_publication_follows_flag(monkeypatch):
    advisory = SimpleNamespace(gate_status="advisory", model_params={"method_version": WORLD_FORECAST_METHOD_VERSION})
    passed = SimpleNamespace(gate_status="passed", model_params={"method_version": WORLD_FORECAST_METHOD_VERSION})
    monkeypatch.setattr(settings, "world_forecast_publish_all", True)
    assert publishable_world_forecast(advisory) and publishable_world_forecast(passed)
    assert not publishable_world_forecast(SimpleNamespace(gate_status="advisory", model_params={"method_version": 1}))
    assert not publishable_world_forecast(SimpleNamespace(
        gate_status="failed", model_params={"method_version": WORLD_FORECAST_METHOD_VERSION},
    ))
    monkeypatch.setattr(settings, "world_forecast_publish_all", False)  # откат прячет advisory сразу
    assert not publishable_world_forecast(advisory) and publishable_world_forecast(passed)
    assert "advisory" in PUBLISHED_GATE_STATUSES and CHECKED_GATE_STATUSES == frozenset({"passed"})


def test_short_history_policy_follows_flag():
    base = dict(
        provider="eurostat", dataset_id="une_rt_m", unit="PC_ACT", frequency="monthly", is_listed=True,
        name_quality="curated", history_end=date(2026, 7, 1),
    )
    for frequency, points, history_end in (
        ("monthly", 36, date(2026, 7, 1)), ("quarterly", 24, date(2026, 4, 1)), ("annual", 10, date(2025, 1, 1)),
    ):
        row = SimpleNamespace(**{**base, "frequency": frequency, "points_count": points, "history_end": history_end})
        assert forecast_eligibility_for(row, today=date(2026, 8, 6), publish_all=True)[1] == "eligible"
        assert forecast_eligibility_for(row, today=date(2026, 8, 6), publish_all=False)[1] == "history_too_short"
        shorter = SimpleNamespace(**{**vars(row), "points_count": points - 1})
        assert forecast_eligibility_for(shorter, today=date(2026, 8, 6), publish_all=True)[1] == "history_too_short"
    # Устаревший ряд и неутверждённый источник по-прежнему без прогноза.
    stale = SimpleNamespace(**{**base, "points_count": 120, "history_end": date(2025, 1, 1)})
    assert forecast_eligibility_for(stale, today=date(2026, 8, 6), publish_all=True)[1] == "series_is_stale"
    imf = SimpleNamespace(**{**base, "provider": "imf", "points_count": 120})
    assert forecast_eligibility_for(imf, today=date(2026, 8, 6), publish_all=True)[1] == "provider_not_approved"


def test_old_failures_retrain_once_under_new_rule(monkeypatch):
    from app.services.world_forecast_pipeline import (
        WORLD_FORECAST_PUBLICATION_POLICY,
        _model_params_for,
        forecast_fingerprint,
        forecast_is_unchanged,
    )

    monkeypatch.setattr(settings, "world_forecast_candidates_enabled", False)
    now = datetime(2026, 10, 15, 12, 0, 0)
    history_end = date(2026, 8, 1)
    fingerprint = forecast_fingerprint(history_end=history_end, points_count=120)

    def unchanged(status, params):
        latest = SimpleNamespace(created_at=datetime(2026, 10, 14), model_params=params, gate_status=status)
        return forecast_is_unchanged(
            latest, history_end=history_end, points_count=120, now=now, max_age_days=30, force=False,
        )

    monkeypatch.setattr(settings, "world_forecast_publish_all", True)
    assert not unchanged("failed", fingerprint)
    assert not unchanged("skipped", fingerprint)
    assert unchanged("passed", fingerprint)  # опубликованное не пересчитывается
    marked = {**fingerprint, "publication_policy": WORLD_FORECAST_PUBLICATION_POLICY}
    assert unchanged("failed", marked) and unchanged("advisory", marked)

    indicator = SimpleNamespace(history_end=history_end, points_count=120, frequency="monthly")
    assert _model_params_for(indicator, None)["publication_policy"] == WORLD_FORECAST_PUBLICATION_POLICY
    monkeypatch.setattr(settings, "world_forecast_publish_all", False)
    assert "publication_policy" not in _model_params_for(indicator, None)
    assert unchanged("failed", fingerprint)


def test_subnational_state_forecast_follows_flag(monkeypatch):
    import asyncio

    from app.services.world_subnational_forecast import state_forecast

    dates = _dates(date(2014, 1, 1), 11, 12)
    values = [50.0 + index * 1.5 + (index % 3) for index in range(11)]
    today = date(2025, 6, 1)
    monkeypatch.setattr(settings, "world_forecast_publish_all", False)
    off = asyncio.run(state_forecast(dates, values, frequency="annual", unit="USD", locale="ru", today=today))
    assert off["available"] is False and off["reason"] == "history_too_short"
    monkeypatch.setattr(settings, "world_forecast_publish_all", True)
    on = asyncio.run(state_forecast(dates, values, frequency="annual", unit="USD", locale="ru", today=today))
    assert on["available"] is True
    assert on["quality"]["gate_status"] == "advisory"
    assert on["methodology"] is None  # о качестве прогноза на странице не пишем
    assert len(on["points"]) == 1
