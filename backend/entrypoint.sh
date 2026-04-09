#!/bin/bash
set -e

echo "=== Forecast Economy Backend Entrypoint ==="

echo "[1/3] Running database migrations..."
python -m alembic upgrade head

echo "[2/3] Running idempotent seed (upsert indicators)..."
python seed_data.py

echo "[3/3] Starting uvicorn..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
