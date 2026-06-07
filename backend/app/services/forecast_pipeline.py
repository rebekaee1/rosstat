"""Пересчёт прогнозов после обновления ряда.

После рефакторинга (Шаг 8): диспетчеризация стратегий вынесена в
`forecast_strategies/registry.py`. Этот модуль отвечает только за:
1. Загрузку исторических данных индикатора и approved/derived контекста.
2. Выбор стратегии (по `model_config.forecast_strategy` или legacy-fallback).
3. Сохранение всех `StrategyOutput` через `_save_forecast`.
"""

import asyncio
import logging
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Forecast, ForecastValue, Indicator, IndicatorData
from app.services.forecast_strategies import (
    STRATEGIES,
    StrategyContext,
    StrategyOutput,
    resolve,
)
from app.services.forecast_strategies.cpi_combined import (
    CPI_DERIVED_CODES,
    CPI_DERIVED_TARGETS,
)
from app.services.forecaster import CPI_INDICATOR_CODES

logger = logging.getLogger(__name__)


# Re-exported for backwards compatibility (used by tests and other modules).
CPI_DERIVED_FORECAST_CODES = CPI_DERIVED_CODES
CPI_DERIVED_FORECAST_TARGETS = CPI_DERIVED_TARGETS


# ---------------------------------------------------------------------------
#  DB helpers
# ---------------------------------------------------------------------------

async def clear_current_forecasts(db: AsyncSession, indicator: Indicator) -> int:
    old_q = await db.execute(
        select(Forecast).where(
            Forecast.indicator_id == indicator.id,
            Forecast.is_current.is_(True),
        )
    )
    old = old_q.scalars().all()
    for fc in old:
        await db.delete(fc)
    return len(old)


async def _save_forecast(
    db: AsyncSession,
    indicator: Indicator,
    output: StrategyOutput,
) -> None:
    """Deactivate old forecasts with matching model prefix and save new one."""
    result = output.result
    prefix = output.model_name_prefix

    old_q = select(Forecast).where(
        Forecast.indicator_id == indicator.id,
        Forecast.is_current.is_(True),
    )
    if prefix:
        old_q = old_q.where(Forecast.model_name.like(f"{prefix}%"))
    else:
        old_q = old_q.where(~Forecast.model_name.like("Inflation-12M%"))

    old = (await db.execute(old_q)).scalars().all()
    for fc in old:
        fc.is_current = False

    new_forecast = Forecast(
        indicator_id=indicator.id,
        model_name=result.model_name,
        model_params={"cumulative_12m": result.cumulative_12m},
        aic=result.aic,
        bic=result.bic,
        is_current=True,
    )
    db.add(new_forecast)
    await db.flush()

    for fp in result.points:
        db.add(ForecastValue(
            forecast_id=new_forecast.id,
            date=fp.date,
            value=fp.value,
            lower_bound=fp.lower_bound,
            upper_bound=fp.upper_bound,
        ))

    logger.info(
        "Saved forecast '%s' for %s (%d points)",
        result.model_name, indicator.code, len(result.points),
    )


# ---------------------------------------------------------------------------
#  Strategy selection (with legacy fallback)
# ---------------------------------------------------------------------------

def _legacy_resolve_name(indicator: Indicator, cfg: dict) -> str:
    """Старая if-цепочка из forecast_pipeline.py — используется когда у
    индикатора не задан `forecast_strategy` в model_config_json.

    Возвращает имя стратегии, под которым старая логика продолжает
    работать. После полной миграции seed_data → каждый индикатор имеет
    явное имя — этот fallback можно убрать.
    """
    if cfg.get("approved_forecast_values"):
        return "approved"
    if indicator.code in CPI_INDICATOR_CODES:
        return "cpi_combined"
    if cfg.get("forecast_model") == "housing_quarterly":
        return "housing_quarterly"
    return "generic_ols"


# ---------------------------------------------------------------------------
#  Helpers for derived strategy: load source actuals + forecast
# ---------------------------------------------------------------------------

async def _load_indicator_full_series(
    db: AsyncSession, indicator_code: str,
) -> list[tuple[date, float]]:
    """actuals + active forecast points для одного индикатора по коду.

    Когда у индикатора одновременно живут несколько активных моделей (CPI имеет
    `CPI-Monthly-MW` + `Inflation-12M-MW`, оба is_current=true), мы должны
    собрать прогноз ТОЛЬКО в той же системе единиц, что и actuals — иначе
    derived-aggregator перемешает уровни цен с %-инфляцией. Простейшая
    fix-эвристика: исключаем Inflation-12M* (та же логика, что в api/forecasts.py
    при отдаче forecast endpoint'а).
    """
    src_q = await db.execute(
        select(Indicator).where(Indicator.code == indicator_code)
    )
    src = src_q.scalar_one_or_none()
    if src is None:
        return [], set()

    actual_q = await db.execute(
        select(IndicatorData)
        .where(IndicatorData.indicator_id == src.id)
        .order_by(IndicatorData.date)
    )
    actuals = [(d.date, float(d.value)) for d in actual_q.scalars().all()]
    actual_dates = {d for d, _ in actuals}

    fc_q = await db.execute(
        select(ForecastValue)
        .join(Forecast, Forecast.id == ForecastValue.forecast_id)
        .where(
            Forecast.indicator_id == src.id,
            Forecast.is_current.is_(True),
            ~Forecast.model_name.like("Inflation-12M%"),
        )
        .order_by(ForecastValue.date)
    )
    forecasts = [(fv.date, float(fv.value)) for fv in fc_q.scalars().all()]

    actuals_dict = dict(actuals)
    for d, v in forecasts:
        if d not in actuals_dict:
            actuals_dict[d] = v
    return sorted(actuals_dict.items()), actual_dates


async def _maybe_inject_source_for_derived(
    db: AsyncSession, ctx_cfg: dict,
) -> dict:
    """Если стратегия — derived_from_source, подгружаем ряд источника."""
    derived_cfg = ctx_cfg.get("derived_forecast") or {}
    source_code = derived_cfg.get("source_code")
    if not source_code:
        return ctx_cfg
    series, actual_dates = await _load_indicator_full_series(db, source_code)
    new_cfg = dict(ctx_cfg)
    new_cfg["_source_data"] = series
    new_cfg["_source_actual_dates"] = sorted(actual_dates)
    return new_cfg


# ---------------------------------------------------------------------------
#  Public API
# ---------------------------------------------------------------------------

async def retrain_indicator_forecast(
    db: AsyncSession,
    indicator: Indicator,
    _retrain_chain: set[str] | None = None,
) -> None:
    """Пересчитать прогноз для одного индикатора и каскадно — для зависимых.

    `_retrain_chain` — внутренний параметр защиты от циклов в каскаде:
    содержит коды индикаторов, уже находящихся в текущей цепочке retrain.
    Внешние вызовы передают `None`.
    """
    cfg = indicator.model_config_json or {}
    forecast_steps = int(cfg.get("forecast_steps", settings.forecast_steps) or 0)

    if forecast_steps <= 0:
        if indicator.code in CPI_DERIVED_FORECAST_TARGETS:
            logger.info(
                "'%s' is populated by CPI source retrain; skipping direct retrain",
                indicator.code,
            )
            return
        removed = await clear_current_forecasts(db, indicator)
        logger.info(
            "forecast_steps<=0 for '%s', skipping retrain and removed %d stale forecast(s)",
            indicator.code, removed,
        )
        return

    strategy_name = cfg.get("forecast_strategy") or _legacy_resolve_name(indicator, cfg)
    strategy = resolve(strategy_name)
    if strategy is None:
        logger.error(
            "No strategy resolved for '%s' (name=%s); skipping",
            indicator.code, strategy_name,
        )
        return

    # Derived стратегия требует данные источника — подгружаем заранее.
    enriched_cfg = await _maybe_inject_source_for_derived(db, cfg)

    data_q = await db.execute(
        select(IndicatorData)
        .where(IndicatorData.indicator_id == indicator.id)
        .order_by(IndicatorData.date)
    )
    all_data = data_q.scalars().all()

    # Approved/derived стратегии могут работать без 36 точек истории.
    requires_history = strategy_name not in ("approved", "derived_from_source")
    if requires_history and len(all_data) < 36:
        removed = await clear_current_forecasts(db, indicator)
        logger.warning(
            "Not enough data for forecast (%d points), removed %d stale forecast(s)",
            len(all_data), removed,
        )
        return

    dates = [d.date for d in all_data]
    values = [float(d.value) for d in all_data]

    ctx = StrategyContext(
        indicator_code=indicator.code,
        indicator_frequency=indicator.frequency or "monthly",
        forecast_steps=forecast_steps,
        cfg=enriched_cfg,
    )

    outputs = await asyncio.to_thread(strategy, dates, values, ctx)

    if not outputs:
        # Стратегия может явно вернуть [] (например, derived без источника):
        # в этом случае чистим существующий прогноз, чтобы не было stale.
        removed = await clear_current_forecasts(db, indicator)
        logger.warning(
            "Strategy '%s' returned 0 outputs for '%s'; cleared %d stale forecast(s)",
            strategy_name, indicator.code, removed,
        )
        return

    target_cache: dict[str, Indicator] = {indicator.code: indicator}

    for output in outputs:
        target_code = output.target_indicator_code or indicator.code
        target = target_cache.get(target_code)
        if target is None:
            target_q = await db.execute(
                select(Indicator).where(Indicator.code == target_code)
            )
            target = target_q.scalar_one_or_none()
            if target is None:
                logger.warning(
                    "Target indicator '%s' not found; skipping output for strategy '%s'",
                    target_code, strategy_name,
                )
                continue
            target_cache[target_code] = target

        await _save_forecast(db, target, output)

    logger.info(
        "Retrain complete for '%s' (strategy=%s, %d outputs)",
        indicator.code, strategy_name, len(outputs),
    )

    chain = (_retrain_chain or set()) | {indicator.code}
    await _retrain_dependents(db, indicator, chain)


async def _retrain_dependents(
    db: AsyncSession,
    source: Indicator,
    chain: set[str],
) -> None:
    """Каскадный retrain: после успешного retrain индикатора-источника
    пересчитываем все индикаторы, у которых
    `model_config.derived_forecast.source_code == source.code`.

    `chain` хранит коды индикаторов уже в текущей retrain-цепочке —
    защищает от бесконечной рекурсии при взаимных зависимостях.
    """
    candidates_q = await db.execute(select(Indicator).where(Indicator.is_active.is_(True)))
    candidates = candidates_q.scalars().all()

    for cand in candidates:
        if cand.code in chain:
            continue
        cfg = cand.model_config_json or {}
        derived_cfg = cfg.get("derived_forecast") or {}
        if derived_cfg.get("source_code") != source.code:
            continue
        logger.info("Cascading retrain: %s → %s", source.code, cand.code)
        try:
            await retrain_indicator_forecast(db, cand, _retrain_chain=chain)
        except Exception:  # pragma: no cover — каскад не должен ронять основной retrain
            logger.exception("Cascading retrain failed for '%s'", cand.code)
