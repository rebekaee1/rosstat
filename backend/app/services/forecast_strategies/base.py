"""Контракт forecast-стратегии.

Стратегия — чистая функция, которая для одного индикатора возвращает
один или несколько `ForecastResult`. Каждый `ForecastResult` будет
сохранён через `_save_forecast` в `forecast_pipeline.py`.

Несколько результатов нужны, когда у одного индикатора параллельно
живут разные модели прогноза. Пример: cpi имеет одновременно
`CPI-Monthly-MW` (помесячный) и `Inflation-12M-MW` (накопленная за 12 мес.) —
обе считаются от одного и того же ряда, обе нужны на разных страницах.

Контракт реализован как `Protocol`, чтобы стратегии могли быть
обычными функциями (без классов и наследования). Это держит файлы
стратегий «тонкими» и тестируемыми.
"""

from dataclasses import dataclass
from datetime import date
from typing import Protocol, Sequence

from app.services.forecaster import ForecastResult


@dataclass(frozen=True)
class StrategyContext:
    """Контекст одного запуска стратегии.

    Содержит всё, что стратегии может понадобиться, но не хочется
    тащить через сигнатуру в виде отдельных аргументов.
    """

    indicator_code: str
    indicator_frequency: str
    forecast_steps: int
    cfg: dict


@dataclass(frozen=True)
class StrategyOutput:
    """Один результат стратегии: куда сохранять и что сохранять.

    `target_indicator_code is None` означает «сохранить под тот же
    индикатор, для которого запущена стратегия» (общий случай).
    Если стратегия порождает прогноз для производного индикатора
    (как CPI → cpi-services-quarterly), `target_indicator_code` ставится
    явно — pipeline найдёт индикатор по коду.
    """

    result: ForecastResult
    target_indicator_code: str | None = None
    model_name_prefix: str | None = None


class ForecastStrategy(Protocol):
    """Сигнатура forecast-стратегии.

    Стратегия:
    1. Принимает исторические `(dates, values)` ряд индикатора и `ctx`.
    2. Возвращает кортеж `StrategyOutput` (один или несколько).
    3. Является **чистой функцией** (никаких побочных эффектов кроме
       логирования). Запуск в `asyncio.to_thread` остаётся обязанностью
       pipeline — стратегия синхронная, как и `train_*` в `forecaster.py`.
    """

    def __call__(
        self,
        dates: Sequence[date],
        values: Sequence[float],
        ctx: StrategyContext,
    ) -> Sequence[StrategyOutput]: ...
