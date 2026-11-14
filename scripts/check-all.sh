#!/usr/bin/env bash
# Основные локальные проверки: pytest + frontend test/lint/build + guards.
# Не заменяет отдельные CI jobs migrations, docker и e2e.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "== project knowledge (read-only) =="
./scripts/check-project-knowledge.sh

echo "== backend pytest =="
cd "$ROOT/backend"
# Python бэкенда (14.11.2026): своя backend/.venv, иначе .venv основного checkout (у git worktree её нет - она не в Git),
# иначе системный python3. Системный python3 без dev-зависимостей (lupa для Lua в fakeredis, xlwt, закреплённый
# fakeredis 2.26.2) даёт 21 ложное падение и 2 ошибки сбора - поэтому без них останавливаемся с понятной причиной.
BACKEND_PY=""
COMMON_ROOT="$(cd "$(git -C "$ROOT" rev-parse --path-format=absolute --git-common-dir 2>/dev/null)/.." 2>/dev/null && pwd || true)"
for cand in "$ROOT/backend/.venv/bin/python" "${COMMON_ROOT:+$COMMON_ROOT/backend/.venv/bin/python}"; do
  if [[ -n "$cand" && -x "$cand" ]]; then BACKEND_PY="$cand"; break; fi
done
BACKEND_PY="${BACKEND_PY:-python3}"
echo "python: $BACKEND_PY"
if ! "$BACKEND_PY" -c "import lupa, xlwt, fakeredis" >/dev/null 2>&1; then
  echo "Нет dev-зависимостей backend у $BACKEND_PY (lupa, xlwt, fakeredis): тесты Redis-блокировок, лимитов и кэша мира"
  echo "упадут ложно. Окружение (CI - Python 3.12): python3 -m venv backend/.venv && backend/.venv/bin/pip install"
  echo "-r backend/requirements-dev.txt -c backend/constraints.txt (в git worktree подходит .venv основного checkout)"
  exit 1
fi
PYTHONPATH=. "$BACKEND_PY" -m pytest -q

echo "== frontend test + lint + build =="
cd "$ROOT/frontend"
if [[ ! -d node_modules ]]; then
  echo "Нет frontend/node_modules (у git worktree их нет): cd frontend && npm ci"
  exit 1
fi
node ../scripts/code-review-symbols.mjs --check --tracked-only
node ../scripts/build-client-mechanism-inventory.mjs --check
node ../scripts/test_project_terrain.mjs
npm run test
npm run lint
npm run build

# --- Карта индикаторов (детерминированная навигация для агента) ---------------
# repo-inventory регенерируется (информационный срез «что есть в проекте»);
# indicator-index проверяется через --check: если seed/парсеры/view-mode-конфиги
# изменились, а карта не перегенерирована — падаем с ненулевым кодом, чтобы карта
# не протухала. Перегенерация: python scripts/build-indicator-index.py
echo "== indicator map (repo-inventory + indicator-index --check) =="
cd "$ROOT"
MAP_PY="$BACKEND_PY"
"$MAP_PY" scripts/repo-inventory.py
"$MAP_PY" scripts/build-indicator-index.py --check
"$MAP_PY" scripts/audit-doc-counters.py
"$MAP_PY" scripts/export-page-meta.py --check
echo "== public language audit =="
"$MAP_PY" scripts/audit-public-language.py

# --- nginx (14.11.2026): быстрые проверки, если доступен Docker -----------------
# Полный поведенческий набор (~5 минут) идёт в CI job nginx и вручную: bash deploy/test-nginx-all.sh.
echo "== nginx quick (deploy/test-nginx-all.sh --quick) =="
if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
  bash "$ROOT/deploy/test-nginx-all.sh" --quick
else
  echo "nginx-тесты пропущены: нет Docker"
fi
echo "== map OK =="
echo "== ALL CHECKS OK =="
