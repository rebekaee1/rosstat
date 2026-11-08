"""Разовая заливка истории помесячного регионального слоя из CSV (ЕМИСС 31448).

Зачем: полная история средних цен на все позиции витрины — около 12 млн точек
за 2000–2026. Парсер ``emiss_regional_parser`` догружает её сам (запрос
«год × месяц», ~320 запросов), но на сервере это полчаса через релей. Этот
загрузчик берёт ту же историю, заранее скачанную с официального источника и
разобранную тем же ``parse_grid_response``: COPY во временную таблицу
сессии, затем запись порциями.
Дальше ежемесячные обновления делает парсер.

Вход: ``gzip`` CSV ``indicator_code;region_slug;YYYYMM;value`` с заголовком.
Запись идёт порциями по 20 показателей в отдельных транзакциях (см. ``load``).
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


def iter_csv(path: Path):
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        reader = csv.reader(fh, delimiter=";")
        next(reader, None)
        for code, slug, period, value in reader:
            month = int(period)
            if not (190001 <= month <= 999912 and 1 <= month % 100 <= 12):
                raise ValueError(f"regional: неверный месяц {period!r}")
            yield code, slug, month, Decimal(value)


BATCH_INDICATORS = 20
PAUSE_SECONDS = 0.5


async def load(path: Path) -> None:
    """COPY во временную таблицу сессии, затем запись порциями по показателям.

    Каждая порция — своя короткая транзакция под региональной блокировкой писателя,
    между порциями пауза: на боевом сервере сайт продолжает отвечать во время заливки
    (одна вставка 13 млн строк на стенде 08.11.2026 упёрлась в 30-минутный лимит).
    Временная таблица живёт до конца соединения (ON COMMIT PRESERVE ROWS): у
    пользователя приложения нет права создавать постоянные таблицы, и это правильно.
    """
    written = staged = 0
    async with async_session() as db:
        await set_local_statement_timeout(db, 1_800_000)
        region_ids = dict((await db.execute(select(Region.slug, Region.id))).all())
        indicator_ids = dict((await db.execute(select(RegionIndicator.code, RegionIndicator.id))).all())
        await db.execute(text("""CREATE TEMP TABLE regional_monthly_load (
            indicator_id integer NOT NULL, region_id integer NOT NULL,
            period integer NOT NULL, value numeric(18,4) NOT NULL,
            PRIMARY KEY (indicator_id, region_id, period)) ON COMMIT PRESERVE ROWS"""))
        raw = await (await db.connection()).get_raw_connection()
        driver = raw.driver_connection
        chunk = []
        for code, slug, period, value in iter_csv(path):
            indicator_id, region_id = indicator_ids.get(code), region_ids.get(slug)
            if indicator_id is None or region_id is None:
                raise RuntimeError(f"regional: нет метаданных для {code!r}/{slug!r}")
            chunk.append((indicator_id, region_id, period, value))
            if len(chunk) >= 50_000:
                await driver.copy_records_to_table("regional_monthly_load", records=chunk,
                                                   columns=("indicator_id", "region_id", "period", "value"))
                staged += len(chunk)
                chunk = []
        if chunk:
            await driver.copy_records_to_table("regional_monthly_load", records=chunk,
                                               columns=("indicator_id", "region_id", "period", "value"))
            staged += len(chunk)
        await db.execute(text("ANALYZE regional_monthly_load"))
        ids = [row[0] for row in (await db.execute(text(
            "SELECT DISTINCT indicator_id FROM regional_monthly_load ORDER BY 1"))).all()]
        await db.commit()

        for i in range(0, len(ids), BATCH_INDICATORS):
            batch = ids[i:i + BATCH_INDICATORS]
            await set_local_statement_timeout(db, 600_000)
            await acquire_regional_write_lock(db)
            result = await db.execute(text("""
                INSERT INTO region_monthly_data AS target (indicator_id, region_id, month, value)
                SELECT source.indicator_id, source.region_id, source.period, source.value
                FROM regional_monthly_load source
                LEFT JOIN region_monthly_data stored ON stored.indicator_id = source.indicator_id
                    AND stored.region_id = source.region_id AND stored.month = source.period
                WHERE source.indicator_id = ANY(:ids) AND stored.value IS DISTINCT FROM source.value
                ON CONFLICT (indicator_id, region_id, month) DO UPDATE SET value = excluded.value
                WHERE target.value IS DISTINCT FROM excluded.value
            """), {"ids": batch})
            await update_regional_year_bounds(db, set(batch))
            await db.commit()
            written += result.rowcount
            print(f"regional monthly: показатели {i + len(batch)}/{len(ids)}, записано {written}", flush=True)
            await asyncio.sleep(PAUSE_SECONDS)
    if written:
        await publish_committed_regional_changes()
    print(f"regional monthly: прочитано {staged} точек, записано {written}")


if __name__ == "__main__":
    asyncio.run(load(Path(sys.argv[1])))
