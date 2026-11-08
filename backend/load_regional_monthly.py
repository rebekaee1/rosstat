"""Разовая заливка истории помесячного регионального слоя из CSV (ЕМИСС 31448).

Зачем: полная история средних цен на все позиции витрины — около 12 млн точек
за 2000–2026. Парсер ``emiss_regional_parser`` догружает её сам (запрос
«год × месяц», ~320 запросов), но на сервере это полчаса через релей. Этот
загрузчик берёт ту же историю, заранее скачанную с официального источника и
разобранную тем же ``parse_grid_response``, и пишет её пачками через COPY.
Дальше ежемесячные обновления делает парсер.

Вход: ``gzip`` CSV ``indicator_code;region_slug;YYYYMM;value`` с заголовком.
Права записи — как у EMISS-писателя (ADR-0008, F03): значения из источника
обновляют сохранённые, отсутствующие в файле точки не удаляются.

    python load_regional_monthly.py /tmp/price_points.csv.gz
"""

from __future__ import annotations

import asyncio
import csv
import gzip
import sys
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select, text

sys.path.insert(0, str(Path(__file__).parent))

from app.core.cache import publish_committed_regional_changes  # noqa: E402
from app.database import async_session, set_local_statement_timeout  # noqa: E402
from app.models import Region, RegionIndicator  # noqa: E402
from app.services.regional_storage import acquire_regional_write_lock, update_regional_year_bounds  # noqa: E402
from seed_regional import _stage_points  # noqa: E402


def iter_csv(path: Path):
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        reader = csv.reader(fh, delimiter=";")
        next(reader, None)
        for code, slug, period, value in reader:
            month = int(period)
            if not (190001 <= month <= 999912 and 1 <= month % 100 <= 12):
                raise ValueError(f"regional: неверный месяц {period!r}")
            yield code, slug, month, Decimal(value)


async def load(path: Path) -> None:
    async with async_session() as db:
        await set_local_statement_timeout(db, 1_800_000)
        await acquire_regional_write_lock(db)
        region_ids = dict((await db.execute(select(Region.slug, Region.id))).all())
        indicator_ids = dict((await db.execute(select(RegionIndicator.code, RegionIndicator.id))).all())
        staged = await _stage_points(db, "regional_seed_monthly", iter_csv(path), indicator_ids, region_ids)
        result = await db.execute(text("""
            INSERT INTO region_monthly_data AS target (indicator_id, region_id, month, value)
            SELECT source.indicator_id, source.region_id, source.period, source.value
            FROM regional_seed_monthly source
            LEFT JOIN region_monthly_data stored ON stored.indicator_id = source.indicator_id
                AND stored.region_id = source.region_id AND stored.month = source.period
            WHERE stored.value IS DISTINCT FROM source.value
            ON CONFLICT (indicator_id, region_id, month) DO UPDATE SET value = excluded.value
            WHERE target.value IS DISTINCT FROM excluded.value
        """))
        bounds = await update_regional_year_bounds(db)
        await db.commit()
    if result.rowcount or bounds:
        await publish_committed_regional_changes()
    print(f"regional monthly: прочитано {staged} точек, записано {result.rowcount}, диапазонов {bounds}")


if __name__ == "__main__":
    asyncio.run(load(Path(sys.argv[1])))
