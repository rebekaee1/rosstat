"""Базовый ETL-парсер: единая обвязка fetch_log/upsert/retrain/cache/commit.

Каждый источник данных (Росстат XLSX, ЦБ HTML/XML/JSON, Минфин CSV, …) умеет
делать только одну вещь: «скачать ответ источника + распарсить его в список
точек». Всё остальное — статусы fetch_log, идемпотентный upsert, retrain
прогноза, инвалидация кэша, commit/rollback на ошибке — одинаково для всех
22+ парсеров. До рефактора эта обвязка дублировалась в каждом `run()` (~50
строк × 24 = ~1100 строк дубля), и любая правка («заменить retry policy»,
«добавить телеметрию», «унифицировать статусы») требовала прохода по всем
файлам сразу.

Сейчас обвязка живёт здесь, в `BaseParser.run()`. Конкретный парсер
переопределяет только `_fetch_and_parse(...)` и опционально один из hook'ов:

    class MySourceParser(BaseParser):
        parser_type = "my_source_v1"

        async def _fetch_and_parse(self, db, indicator, cfg, fetch_log):
            content, url = await asyncio.to_thread(my_fetch, ...)
            return my_parse(content), url

Hook'и (опциональны):
- `_post_upsert(...)` — extra точка после bulk_upsert (cbr_keyrate использует
  это для опережающей точки из пресс-релиза СД ЦБ).
- `_handle_forecasts(...)` — нестандартная политика прогноза (cbr_keyrate
  чистит current forecasts если steps==0).
- `_validate(points, cfg)` — кастомная нормализация/проверка (по умолчанию
  вызывается `data_validator.validate_points`).

Idempotency contract: `bulk_upsert` (ON CONFLICT DO UPDATE WHERE value differs)
guarantees that re-running the same parser on the same day is a no-op for
unchanged points and picks up source revisions automatically. This is the
pre-condition for the ADR-0002 invariant.

See:
- `CONTEXT.md::Parser` — domain glossary entry.
- `docs/cbr_sources.md` — inventory of all non-Rosstat parsers.
- `docs/adr/0002-derived-always-reflects-source.md` — invariant tied to upsert behavior.
- ADR (TBD) — «ETL parser as a Template Method, not 22 repeated runs».
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import ClassVar

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import cache_invalidate_indicator
from app.models import FetchLog, Indicator
from app.services.forecast_pipeline import retrain_indicator_forecast
from app.services.upsert import bulk_upsert

logger = logging.getLogger(__name__)


def _utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class BaseParser(ABC):
    """Парсер источника: fetch → parse → validate → store (в run).

    Все 24 парсера мигрированы; `_fetch_and_parse` теперь обязательный
    abstract method.
    """

    parser_type: ClassVar[str] = "abstract"

    async def run(self, db: AsyncSession, indicator: Indicator, fetch_log: FetchLog) -> None:
        """Полный цикл ETL для одного индикатора. Не переопределяй — переопределяй `_fetch_and_parse`."""
        code = indicator.code
        try:
            cfg = indicator.model_config_json or {}

            points, source_url = await self._fetch_and_parse(db, indicator, cfg, fetch_log)
            if source_url:
                fetch_log.source_url = source_url[:500]

            points = self._validate(points, cfg)

            if not points:
                logger.warning("No data points parsed for %s", code)
                fetch_log.status = "no_new_data"
                if not fetch_log.error_message:
                    fetch_log.error_message = "Parser returned 0 data points"
                fetch_log.completed_at = _utcnow_naive()
                await db.commit()
                return

            records_added, records_updated = await bulk_upsert(db, indicator.id, points)
            logger.info(
                "Upserted %d new, %d updated for '%s'",
                records_added, records_updated, code,
            )
            fetch_log.records_added = records_added

            extra_added, extra_updated = await self._post_upsert(
                db, indicator, cfg, fetch_log, points, records_added, records_updated,
            )
            if extra_added or extra_updated:
                records_added += extra_added
                records_updated += extra_updated
                fetch_log.records_added = records_added

            await self._handle_forecasts(db, indicator, cfg, records_added, records_updated)

            if records_added > 0 or records_updated > 0:
                await cache_invalidate_indicator(code)

            fetch_log.status = "success" if (records_added > 0 or records_updated > 0) else "no_new_data"
            fetch_log.completed_at = _utcnow_naive()
            await db.commit()

        except Exception as exc:
            logger.exception("ETL failed for '%s'", code)
            await db.rollback()
            fetch_log.status = "failed"
            fetch_log.error_message = str(exc)[:500]
            fetch_log.completed_at = _utcnow_naive()
            db.add(fetch_log)
            await db.commit()

    @abstractmethod
    async def _fetch_and_parse(
        self,
        db: AsyncSession,
        indicator: Indicator,
        cfg: dict,
        fetch_log: FetchLog,
    ) -> tuple[list, str]:
        """Override (обязательно). Вернуть `(points, source_url)`.

        `points` — list объектов с атрибутами `.date`/`.value` ИЛИ кортежей
        `(date, value)` (см. `bulk_upsert._split_point`). Возврат пустого
        списка обрабатывается базовым `run()` как `no_new_data`.

        `source_url` — для записи в `fetch_log.source_url`. Может быть пустой
        строкой; обрезается до 500 символов.

        Если в процессе fetch произошли «частичные» ошибки (например, один из
        chunk'ов упал, но остальные собраны), парсер может записать
        ``fetch_log.error_message`` сам — базовый `run()` сохранит его.
        """

    def _validate(self, points: list, cfg: dict) -> list:
        """Default: точки идут в upsert как есть.

        Override для кастомной нормализации/валидации. Например, парсеры
        Rosstat XLSX и cbr_keyrate возвращают объекты `DataPoint` (с
        `.value`) и применяют общий range-checker
        `data_validator.validate_points`. Tuple-based парсеры (gold/fx/
        ruonia/...) исторически валидатор не использовали.
        """
        return points

    async def _post_upsert(
        self,
        db: AsyncSession,
        indicator: Indicator,
        cfg: dict,
        fetch_log: FetchLog,
        points: list,
        records_added: int,
        records_updated: int,
    ) -> tuple[int, int]:
        """Default: ничего лишнего. Override для специальных вставок (cbr_keyrate press-release)."""
        return 0, 0

    async def _handle_forecasts(
        self,
        db: AsyncSession,
        indicator: Indicator,
        cfg: dict,
        records_added: int,
        records_updated: int,
    ) -> None:
        """Default: retrain прогноз только если есть forecast_steps > 0 И что-то изменилось.

        Override в cbr_keyrate (там steps==0 → clear_current_forecasts).
        """
        steps = int(cfg.get("forecast_steps", 0) or 0)
        if steps > 0 and (records_added > 0 or records_updated > 0):
            await retrain_indicator_forecast(db, indicator)
