#!/bin/bash
set -e

echo "=== Forecast Economy Backend Entrypoint ==="

echo "[1/3] Running database migrations..."
python -m alembic upgrade head

echo "[2/4] Running idempotent seed (upsert indicators)..."
python seed_data.py

echo "[3/4] Seeding economic calendar (rolling 12-month window)..."
python -m app.services.calendar_seed || echo "  (calendar seed warning, continuing startup)"

echo "[4/4] Starting uvicorn..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers ${UVICORN_WORKERS:-1}
