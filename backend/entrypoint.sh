#!/bin/bash
set -e

echo "=== Forecast Economy Backend Entrypoint ==="

echo "[1/3] Running database migrations..."
python -m alembic upgrade head

echo "[2/5] Running idempotent seed (upsert indicators)..."
python seed_data.py

echo "[3/5] Seeding regional block (regions × indicators × years)..."
python seed_regional.py || echo "  (regional seed warning, continuing startup)"

echo "[4/5] Seeding economic calendar (rolling 12-month window)..."
python -m app.services.calendar_seed || echo "  (calendar seed warning, continuing startup)"

echo "[5/5] Starting uvicorn..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers ${UVICORN_WORKERS:-1}
