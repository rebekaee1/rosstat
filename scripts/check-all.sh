#!/usr/bin/env bash
# Полная проверка как в GitHub Actions: backend pytest + frontend test/lint/build.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "== backend pytest =="
cd "$ROOT/backend"
if [[ -x .venv/bin/pytest ]]; then
  PYTHONPATH=. .venv/bin/pytest -q
else
  PYTHONPATH=. python3 -m pytest -q
fi

echo "== frontend test + lint + build =="
cd "$ROOT/frontend"
npm run test
npm run lint
npm run build

echo "== OK =="
