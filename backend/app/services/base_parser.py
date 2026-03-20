"""Абстрактный базовый парсер ETL (Фаза 1 плана Forecast Economy)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FetchLog, Indicator


class BaseParser(ABC):
    """Парсер источника: fetch → parse → validate → store (в run)."""

    parser_type: ClassVar[str] = "abstract"

    @abstractmethod
    async def run(self, db: AsyncSession, indicator: Indicator, fetch_log: FetchLog) -> None:
        """Полный цикл для одного индикатора; обновляет fetch_log и делает commit при успехе/ошибке."""
