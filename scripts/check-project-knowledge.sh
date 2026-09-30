#!/usr/bin/env bash
# Read-only knowledge gates; no app, network, production access or artifact rewrite.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [[ -x backend/.venv/bin/python ]]; then
  KNOWLEDGE_PY="backend/.venv/bin/python"
else
  KNOWLEDGE_PY="python3"
fi
"$KNOWLEDGE_PY" - <<'PY'
from pathlib import Path
entry = Path('AGENTS.md')
limit = 16 * 1024  # Project budget, intentionally below the earlier 84.6 KB entry.
size = entry.stat().st_size
if size > limit:
    raise SystemExit(f'AGENTS entry exceeds project budget: {size} > {limit}; disclose reference behind topic links')
required = ['docs/knowledge-workflow.md', 'docs/agent-recipes.md', 'docs/architecture.md',
            'docs/data-contracts.md', 'docs/architecture-history.md', 'docs/code-review/readiness-criteria.md']
body = entry.read_text()
for name in required:
    if not Path(name).is_file() or name not in body:
        raise SystemExit(f'Missing AGENTS knowledge route: {name}')
print(f'AGENTS routes OK, {size} bytes')
PY
"$KNOWLEDGE_PY" scripts/audit-code-documentation.py --check --tracked-only
"$KNOWLEDGE_PY" scripts/build-mechanism-inventory.py --check
"$KNOWLEDGE_PY" scripts/build-project-terrain.py --check --tracked-only
"$KNOWLEDGE_PY" scripts/classify-graph-omissions.py --check
"$KNOWLEDGE_PY" scripts/audit-knowledge-materials.py --check
