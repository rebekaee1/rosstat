"""
Производные индикаторы (каркас Фазы 1).
После ETL вызывается run_for_updated_sources с кодами источников, у которых появились данные.
"""

from __future__ import annotations

import logging
from typing import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

DerivedFn = Callable[[AsyncSession, list[str]], Awaitable[None]]


class CalculationEngine:
    """Реестр производных рядов и запуск пересчёта."""

    def __init__(self) -> None:
        self._derived: dict[str, DerivedFn] = {}

    def register(self, code: str, fn: DerivedFn) -> None:
        self._derived[code] = fn

    async def run_for_updated_sources(self, db: AsyncSession, source_codes: list[str]) -> None:
        """Пересчитать производные, зависящие от обновлённых источников (пока no-op)."""
        if not source_codes:
            return
        logger.debug("CalculationEngine: updated sources %s (derived registry: %d)",
                     source_codes, len(self._derived))


calculation_engine = CalculationEngine()
