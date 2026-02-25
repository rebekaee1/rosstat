#!/bin/bash
set -e

echo "=== RuStats Backend Entrypoint ==="

echo "[1/3] Running database migrations..."
python -m alembic upgrade head

echo "[2/3] Checking if seed is needed..."
INDICATOR_COUNT=$(python -c "
import asyncio
from app.database import async_session
from app.models import Indicator
from sqlalchemy import select, func
async def count():
    async with async_session() as db:
        r = await db.execute(select(func.count(Indicator.id)))
        print(r.scalar() or 0)
asyncio.run(count())
")

if [ "$INDICATOR_COUNT" = "0" ]; then
    echo "[2/3] Empty database detected — running seed..."
    python seed_data.py
else
    echo "[2/3] Database has $INDICATOR_COUNT indicators — skipping seed."
fi

echo "[3/3] Starting uvicorn..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
