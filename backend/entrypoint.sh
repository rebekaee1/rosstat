#!/bin/bash
set -e

echo "=== Forecast Economy Backend Entrypoint ==="

echo "[1/3] Running database migrations..."
python -m alembic upgrade head

echo "[2/5] Running idempotent seed (upsert indicators)..."
python seed_data.py

# О-11/Р-13: провал регионального сидера фатален, только если региональных
# данных ещё нет (первичный seed — без него 40k SSR-страниц отдают 404/пустоту);
# при уже наполненных таблицах транзитный сбой не блокирует деплой.
echo "[3/5] Seeding regional block (regions × indicators × years)..."
if ! python seed_regional.py; then
  if python - <<'PY'
import asyncio, sys
from sqlalchemy import select, func
from app.database import async_session
from app.models import RegionDataPoint

async def main():
    async with async_session() as db:
        n = (await db.execute(select(func.count()).select_from(RegionDataPoint))).scalar()
    sys.exit(0 if n and n > 0 else 1)

asyncio.run(main())
PY
  then
    echo "  (regional seed failed, but data already present — continuing startup)"
  else
    echo "  FATAL: regional seed failed on empty tables — aborting startup"
    exit 1
  fi
fi

echo "[4/5] Seeding economic calendar (rolling 12-month window)..."
python -m app.services.calendar_seed || echo "  (calendar seed warning, continuing startup)"

echo "[5/5] Starting uvicorn..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers ${UVICORN_WORKERS:-1}
