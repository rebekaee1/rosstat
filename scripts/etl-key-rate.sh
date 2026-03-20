#!/usr/bin/env bash
# Однократный ETL ключевой ставки ЦБ (нужны переменные БД как у backend).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/backend"
export PYTHONPATH=.
if [[ -x .venv/bin/python ]]; then
  .venv/bin/python -c "import asyncio; from app.tasks.scheduler import run_etl_for_indicator; asyncio.run(run_etl_for_indicator('key-rate'))"
else
  python3 -c "import asyncio; from app.tasks.scheduler import run_etl_for_indicator; asyncio.run(run_etl_for_indicator('key-rate'))"
fi
