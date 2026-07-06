"""В-27: доменная валидация прогнозов перед сохранением.

Статистическая модель не знает, что цена/ставка/объём не бывают отрицательными:
широкий CI на неотрицательном ряду уходил ниже нуля и показывался пользователю.
`_save_forecast` клэмпит value/lower/upper в доменные границы: явные — из
`model_config_json.forecast_constraints`, неявный пол 0 — если вся фактическая
история ряда неотрицательна.
"""

import asyncio
import os
import tempfile
from datetime import date

from app.services.forecast_pipeline import _clamp, _save_forecast
from app.services.forecast_strategies import StrategyOutput
from app.services.forecaster import ForecastPoint, ForecastResult


def test_clamp_pure():
    assert _clamp(-1.5, 0.0, None) == 0.0
    assert _clamp(1.5, 0.0, None) == 1.5
    assert _clamp(150.0, 0.0, 100.0) == 100.0
    assert _clamp(None, 0.0, None) is None
    assert _clamp(-5.0, None, None) == -5.0


def _make_output(points) -> StrategyOutput:
    return StrategyOutput(
        result=ForecastResult(
            model_name="Test-Model",
            aic=None,
            bic=None,
            points=[ForecastPoint(date=d, value=v, lower_bound=lo, upper_bound=hi)
                    for d, v, lo, hi in points],
        ),
    )


def _run_save(indicator_kwargs, actual_values, forecast_points):
    """Герметичный прогон _save_forecast на SQLite: возвращает сохранённые точки."""
    from sqlalchemy import create_engine, select
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.models import Base, ForecastValue, Indicator, IndicatorData

    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        sync_engine = create_engine(f"sqlite:///{db_path}")
        Base.metadata.create_all(sync_engine)
        sync_engine.dispose()

        engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
        Session = async_sessionmaker(engine, expire_on_commit=False)

        async def run():
            async with Session() as db:
                ind = Indicator(
                    code="test-price", name="Тестовая цена", unit="руб.",
                    category="Тест", source="Тест", frequency="monthly",
                    parser_type="manual", is_active=True,
                    **indicator_kwargs,
                )
                db.add(ind)
                await db.flush()
                for i, v in enumerate(actual_values):
                    db.add(IndicatorData(
                        indicator_id=ind.id, date=date(2025, 1 + i, 1), value=v,
                    ))
                await db.flush()
                await _save_forecast(db, ind, _make_output(forecast_points))
                await db.commit()
                rows = (await db.execute(
                    select(ForecastValue).order_by(ForecastValue.date)
                )).scalars().all()
                out = [(r.value, r.lower_bound, r.upper_bound) for r in rows]
            await engine.dispose()
            return out

        return asyncio.run(run())
    finally:
        try:
            os.unlink(db_path)
        except OSError:
            pass


def test_non_negative_history_floors_forecast_at_zero():
    """История >= 0 → неявный пол 0: CI и точка не уходят ниже нуля."""
    saved = _run_save(
        {}, [10.0, 8.0, 5.0],
        [
            (date(2025, 6, 1), 2.0, -3.0, 7.0),   # CI ниже нуля
            (date(2025, 7, 1), -1.0, -6.0, 4.0),  # и сама точка ниже нуля
        ],
    )
    assert [float(v) for v, _, _ in saved] == [2.0, 0.0]
    assert [float(lo) for _, lo, _ in saved] == [0.0, 0.0]
    assert [float(hi) for _, _, hi in saved] == [7.0, 4.0]


def test_signed_history_keeps_negative_forecast():
    """Знакопеременный ряд (сальдо): отрицательный прогноз легитимен."""
    saved = _run_save(
        {}, [10.0, -4.0, 3.0],
        [(date(2025, 6, 1), -2.0, -5.0, 1.0)],
    )
    assert [float(v) for v, _, _ in saved] == [-2.0]
    assert [float(lo) for _, lo, _ in saved] == [-5.0]


def test_explicit_constraints_override():
    """Явные forecast_constraints из model_config_json сильнее эвристики."""
    saved = _run_save(
        {"model_config_json": {"forecast_constraints": {"min": 1.0, "max": 6.0}}},
        [10.0, 8.0, 5.0],
        [(date(2025, 6, 1), 0.5, -1.0, 8.0)],
    )
    assert [float(v) for v, _, _ in saved] == [1.0]
    assert [float(lo) for _, lo, _ in saved] == [1.0]
    assert [float(hi) for _, _, hi in saved] == [6.0]
