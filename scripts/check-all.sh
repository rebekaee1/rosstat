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

# --- Карта индикаторов (детерминированная навигация для агента) ---------------
# repo-inventory регенерируется (информационный срез «что есть в проекте»);
# indicator-index проверяется через --check: если seed/парсеры/view-mode-конфиги
# изменились, а карта не перегенерирована — падаем с ненулевым кодом, чтобы карта
# не протухала. Перегенерация: python scripts/build-indicator-index.py
echo "== indicator map (repo-inventory + indicator-index --check) =="
cd "$ROOT"
if [[ -x backend/.venv/bin/python ]]; then
  MAP_PY="backend/.venv/bin/python"
else
  MAP_PY="python3"
fi
"$MAP_PY" scripts/repo-inventory.py
"$MAP_PY" scripts/build-indicator-index.py --check
echo "== map OK =="
