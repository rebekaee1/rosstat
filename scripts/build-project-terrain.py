#!/usr/bin/env python3
"""Reproducible Graphify projection + complete Git file inventory.

--refresh: run locally installed graphifyy==0.9.69, write raw graph outside Git,
           then generate portable JSON/Markdown/HTML navigation.
--check:   stdlib-only drift check; never imports application code or Graphify.

Architecture edges are produced by Graphify, not by this renderer. A file-level
edge aggregates symbol edges with their original relation/confidence/evidence.
No runtime call, deployment or test coverage is inferred from static reachability.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / ".artifacts/project-terrain"
SNAPSHOT = ROOT / "docs/project-terrain.json"
REPORT = ROOT / "docs/project-terrain.md"
HTML = ROOT / "docs/project-terrain.html"
VERSION = "0.9.69"
GENERATED = {
    "docs/project-terrain.json", "docs/project-terrain.md", "docs/project-terrain.html",
    "docs/repo-inventory.md",  # timestamp/own size changes on every check-all
    "docs/code-review.md",
}
CODE = {".py", ".js", ".jsx", ".mjs", ".ts", ".tsx", ".sh", ".sql", ".html", ".css", ".mako"}
DOCS = {".md", ".mdc", ".rst"}

# Physical layers, derived only from visible repository paths. These are not
# inferred business domains or a runtime call graph. Every file gets one group.
LAYERS = [
    ("browser", "Браузер: страницы и компоненты"),
    ("client", "Клиент: данные, hooks и состояние"),
    ("embed", "Встраиваемые виджеты"),
    ("locale", "Языки и локализация"),
    ("api", "HTTP API"), ("services", "Сервисы и расчёты"),
    ("jobs", "Планировщик и фоновые задачи"),
    ("model", "Модели, ядро и запуск backend"),
    ("registry", "Реестры и исходные данные"),
    ("migration", "Миграции БД"),
    ("operations", "Операционные скрипты"),
    ("infra", "Инфраструктура и конфигурация"),
    ("tests", "Тесты и fixtures"),
    ("docs", "Документация и правила"),
    ("research", "Исследования и артефакты"),
    ("assets", "Статические ресурсы"),
    ("other", "Другие файлы"),
]


def layer_for(row: dict) -> str:
    p = row["path"]
    name = Path(p).name
    if (p.startswith(("backend/tests/", "scripts/e2e/", "frontend/src/test/"))
            or ".test." in name or ".spec." in name):
        return "tests"
    if row.get("kind") == "document" or p.startswith(".tours/"):
        return "docs"
    if p.startswith("docs/"):
        return "research"
    if p.startswith("frontend/src/embed/"):
        return "embed"
    if p.startswith("frontend/src/i18n/"):
        return "locale"
    if p.startswith(("frontend/src/pages/", "frontend/src/components/")) or p in {
        "frontend/src/App.jsx", "frontend/src/main.jsx", "frontend/index.html"}:
        return "browser"
    if p.startswith(("frontend/src/lib/", "frontend/src/hooks/", "frontend/src/context/")):
        return "client"
    if p.startswith("frontend/src/") and not p.startswith("frontend/src/assets/"):
        return "browser"
    if p.startswith("backend/app/api/"):
        return "api"
    if p.startswith("backend/app/services/"):
        return "services"
    if p.startswith("backend/app/tasks/"):
        return "jobs"
    if p.startswith("backend/alembic/"):
        return "migration"
    if p.startswith(("backend/app/data/", "frontend/src/data/")):
        return "registry"
    if p.startswith(("backend/app/assets/", "frontend/public/", "frontend/src/assets/", "backend/certs/")):
        return "assets"
    if p.startswith("backend/app/") or name.startswith("seed_"):
        return "model"
    if p.startswith(("scripts/", "backend/scripts/", "frontend/scripts/", "mcp/")):
        return "operations"
    if p.startswith(("deploy/", ".github/", "clickhouse/")) or name in {
        "Dockerfile", "entrypoint.sh", "docker-compose.yml", "Caddyfile"} or Path(p).suffix in {
        ".conf", ".ini", ".yaml", ".yml"} or "/" not in p or p.count("/") == 1:
        return "infra"
    return "other"


def overview(rows: list[dict], edges: list[dict]) -> dict:
    knowledge = ROOT / "docs/architecture-knowledge.json"
    reviewed = json.loads(knowledge.read_text()).get("source_fingerprints", {}) if knowledge.exists() else {}
    groups = defaultdict(list)
    paths = {}
    for row in rows:
        row["layer"] = layer_for(row)
        row["semantic_evidence"] = row["path"] in reviewed
        row["semantic_current"] = reviewed.get(row["path"]) == row.get("sha256") if row["semantic_evidence"] else None
        groups[row["layer"]].append(row)
        paths[row["path"]] = row["layer"]
    links = defaultdict(lambda: {"file_relations": 0, "symbol_relations": 0})
    for edge in edges:
        key = paths[edge["source"]], paths[edge["target"]]
        links[key]["file_relations"] += 1
        links[key]["symbol_relations"] += edge["count"]
    return {"basis": "Deterministic path groups; static relations only; no runtime or complete semantic audit claim",
            "layers": [dict(id=key, label=label, files=len(groups[key]),
                            code=sum(r.get("kind") == "code" for r in groups[key]),
                            with_nodes=sum(r.get("nodes", 0) > 0 for r in groups[key]),
                            file_node_only=sum(r.get("nodes", 0) == 1 for r in groups[key]),
                            semantic_evidence=sum(r["semantic_evidence"] for r in groups[key]))
                       for key, label in LAYERS if groups[key]],
            "links": [dict(source=a, target=b, **value) for (a, b), value in sorted(links.items())],
            "semantic_files": sum(r["semantic_evidence"] for r in rows),
            "semantic_stale": [r["path"] for r in rows if r["semantic_current"] is False],
            "code_files": sum(r.get("kind") == "code" for r in rows),
            "code_with_nodes": sum(r.get("kind") == "code" and r.get("nodes", 0) > 0 for r in rows),
            "code_file_node_only": sum(r.get("kind") == "code" and r.get("nodes", 0) == 1 for r in rows)}


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True)


def inventory(tracked_only: bool = False) -> list[dict]:
    """Include tracked/index paths; optionally include nonignored new files.

    Generated terrain files are outside their own input set. Symlinks are
    recorded without following them; private ignored files never enter it.
    """
    paths = set(git("ls-files", "-z").split("\0"))
    if not tracked_only:
        paths.update(git("ls-files", "--others", "--exclude-standard", "-z").split("\0"))
    rows = []
    for rel in sorted(paths - GENERATED - {""}):
        if rel.startswith("docs/code-review/"):
            continue
        path = ROOT / rel
        if not path.is_file() and not path.is_symlink():
            continue
        data = str(path.readlink()).encode() if path.is_symlink() else path.read_bytes()
        kind = "code" if path.suffix in CODE else "document" if path.suffix in DOCS else "asset/data/config"
        try:
            content = data.decode("utf-8")
            lines = len(content.splitlines())
        except UnicodeDecodeError:
            lines = None
        rows.append({"path": rel, "kind": kind, "bytes": len(data), "lines": lines,
                     "sha256": hashlib.sha256(data).hexdigest(), "symlink": path.is_symlink()})
    return rows


def projection(extraction: dict, rows: list[dict], attempted: list[str]) -> dict:
    """Project only resolved in-repository endpoints; report everything omitted."""
    files = {r["path"]: r for r in rows}
    nodes = {n["id"]: n for n in extraction["nodes"]}
    node_counts = Counter(n.get("source_file") for n in nodes.values())
    links = defaultdict(lambda: {"count": 0, "evidence": []})
    omitted = Counter()
    for e in extraction["edges"]:
        a, b = nodes.get(e.get("source")), nodes.get(e.get("target"))
        if not a or not b:
            omitted["missing_endpoint"] += 1
            continue
        src, dst = a.get("source_file"), b.get("source_file")
        if src not in files or dst not in files:
            omitted["external_or_unresolved_file"] += 1
            continue
        if src == dst:
            omitted["within_file"] += 1
            continue
        key = src, dst, e.get("relation", "unknown"), e.get("confidence", "AMBIGUOUS")
        item = links[key]
        item["count"] += 1
        if not item["evidence"]:
            item["evidence"].append({"file": e.get("source_file"), "line": e.get("source_location"),
                                     "source": a.get("label"), "target": b.get("label")})
    attempted_set = set(attempted)
    for row in rows:
        row["nodes"] = node_counts[row["path"]]
        row["extraction"] = "nodes" if row["nodes"] else "no_nodes" if row["path"] in attempted_set else "inventory_only"
    edges = [dict(source=a, target=b, relation=rel, confidence=conf, **value)
             for (a, b, rel, conf), value in sorted(links.items())]
    return {
        "schema_version": 2, "extractor": f"graphifyy=={VERSION}",
        "baseline_commit": git("rev-parse", "HEAD").strip(),
        "scope": "Working tree: Git tracked + nonignored new files; generated maps and docs/code-review evidence directory excluded",
        "unstaged_at_capture": sorted(p for p in git("diff", "--name-only").splitlines() if p not in GENERATED),
        "untracked_at_capture": sorted(p for p in git("ls-files", "--others", "--exclude-standard").splitlines() if p not in GENERATED),
        "stats": {"files": len(rows), "attempted": len(attempted),
                  "files_with_nodes": sum(r["nodes"] > 0 for r in rows),
                  "nodes": len(nodes), "symbol_edges": len(extraction["edges"]),
                  "file_edges": len(edges), "projection_omissions": dict(sorted(omitted.items())),
                  "confidence": dict(sorted(Counter(e.get("confidence", "AMBIGUOUS") for e in extraction["edges"]).items()))},
        "overview": overview(rows, edges), "files": rows, "edges": edges,
    }


def markdown(data: dict) -> str:
    s = data["stats"]
    o = data["overview"]
    lines = ["# Рельеф проекта — автоматически извлечённый срез", "",
             "> Генерируется `scripts/build-project-terrain.py --refresh` через Graphify. Не править вручную.", "",
             "[Локальный интерактивный просмотр — после `--render`](project-terrain.html) · [JSON](project-terrain.json) · "
             "[Архитектура](architecture.md) · [Контракты](data-contracts.md) · [История решений](architecture-history.md)", "",
             f"Экстрактор: `{data['extractor']}`. Базовый commit: `{data['baseline_commit'][:12]}`; "
             "снимок включает рабочие изменения. SHA-256 каждого входного файла записан в JSON. "
             "`unstaged_at_capture` и `untracked_at_capture` фиксируют состояние входов; коммит карты сам по себе "
             "не коммитит чужие изменения кода. HTML локальный, в Git не хранится; в чистом clone сначала выполнить `--render`.", "",
             f"Input scope: `{data.get('input_scope', 'worktree')}`. Для публикуемой main-карты используются Git tracked/index пути; новые файлы задачи сначала добавляются в index. "
             "Чужие untracked материалы остаются вне main-снимка и сохраняются на диске.", "",
             "## Покрытие", "", "| Измерение | Число |", "|---|---:|",
             f"| Файлы в инвентаризации | {s['files']} |",
             f"| Переданы структурному экстрактору | {s['attempted']} |",
             f"| Дали узлы графа | {s['files_with_nodes']} |",
             f"| Узлы / связи между символами | {s['nodes']} / {s['symbol_edges']} |",
             f"| Связи между файлами (тип и уверенность сохраняются) | {s['file_edges']} |", "",
             f"Исходники, шаблоны и стили: **{o['code_files']}** файлов; узлы есть у **{o['code_with_nodes']}**, "
             f"из них **{o['code_file_node_only']}** дали только один файловый узел. "
             f"Исторический смысловой граф содержит основания для **{o['semantic_files']}** файлов. "
             "Это прежний выборочный срез; его изменившиеся основания показаны в HTML отдельно. "
             "Текущий содержательный разбор каждого файла и именованного определения находится в "
             "[реестре рецензий](code-review.md), с отдельным guard по SHA и аннотациям. "
             "Успешный прогон тестов не измеряет полноту этого разбора.", "",
             "Полная инвентаризация относится к Git-дереву. Наличие в списке не означает, что каждый файл "
             "прошёл содержательный аудит. `nodes` — экстрактор нашёл структуру; `no_nodes` — файл прочитан "
             "экстрактором, но сущностей не получено; `inventory_only` — учтён без разбора структуры. "
             "Бинарные материалы, конфиги и данные включены в инвентарь; визуальное содержание скриншотов не анализировалось.", "",
             "## Общая структура", "",
             "Просмотрщик начинается с групп исходников и матрицы связей между ними. Группировка "
             "детерминированная по путям файлов (`layer_for`); каждый файл входит ровно в одну группу, "
             "остаток виден в «Других файлах». Это технические слои, а не автоматически доказанные бизнес-домены. "
             "Ячейки матрицы суммируют только извлечённые связи; отсутствие ребра frontend→API не отменяет HTTP-вызов. "
             "Сквозные потоки через HTTP, БД, Redis и расписания описаны в архитектуре и контрактах.", "",
             "| Группа | Файлов | Исходников | С узлами | Оснований в историческом смысловом графе |",
             "|---|---:|---:|---:|---:|",
             *[f"| {g['label']} | {g['files']} | {g['code']} | {g['with_nodes']} | {g['semantic_evidence']} |" for g in o['layers']], "",
             "## Что означает связь", "",
             "`EXTRACTED` и `INFERRED` — метки Graphify. Даже EXTRACTED означает статическую конструкцию, "
             "а не выполненный вызов. JSON сохраняет направление, тип, количество и примеры исходных строк. "
             "Внутрифайловые отношения остаются в полном Graphify-графе; внешние/неразрешённые endpoints "
             "не превращаются в выдуманные файлы. Отсутствие входящих связей не доказывает мёртвый код. "
             "Динамические реестры, HTTP, SQL, Redis и scheduler требуют контрактов из отдельных документов.", "",
             f"Метки связей: `{json.dumps(s['confidence'], ensure_ascii=False)}`.",
             f"Не включены в проекцию между файлами: `{json.dumps(s['projection_omissions'], ensure_ascii=False)}`.", "",
             "## Слои файлов", "", "| Папка | Файлов | С узлами |", "|---|---:|---:|"]
    groups = defaultdict(list)
    for f in data["files"]:
        groups[f["path"].split("/")[0] if "/" in f["path"] else "(root)"].append(f)
    for group, rows in sorted(groups.items()):
        lines.append(f"| `{group}` | {len(rows)} | {sum(r['nodes'] > 0 for r in rows)} |")
    lines += ["", "## Документы и правила", "",
              "Ниже весь реестр текстовой документации и правил, включая старые материалы. "
              "Исторический статус и решения — в [индексе истории](architecture-history.md).", "",
              "| Документ | Строк | Извлечение |", "|---|---:|---|"]
    for f in data["files"]:
        if f["kind"] == "document":
            lines.append(f"| [{f['path']}](../{f['path']}) | {f['lines']} | {f['extraction']} |")
    lines += ["", "## Обновление и проверка", "", "```bash",
              "# В окружении с graphifyy==0.9.69; не импортирует backend и не обращается к БД",
              "python scripts/build-project-terrain.py --refresh --tracked-only",
              "# Проверка drift, Graphify не требуется",
              "python3 scripts/build-project-terrain.py --check",
              "# Пересоздать HTML из закоммиченного JSON, без Graphify",
              "python3 scripts/build-project-terrain.py --render", "```", "",
              "Полные `extraction.json`, `graph.json` и диагностика сохраняются в "
              "`.artifacts/project-terrain/` (локальные, не Git). "
              "`graphify explain <symbol> --graph .artifacts/project-terrain/graph.json` даёт точечную навигацию. "
              "Для просмотра HTML достаточно открыть файл; сеть и CDN не нужны. "
              "Проверка `--check --tracked-only` включена в `check-project-knowledge.sh`, `check-all.sh` и CI knowledge job. "
              "Она читает сохранённый срез без перезаписи и требует актуальной main-карты. "
              "Команды требуют Git checkout; Python-зависимости для `--check`/`--render` не нужны.", "",
              "Смысловой граф исследовательских агентов — отдельное датированное свидетельство в "
              "`docs/architecture-knowledge.json`; он не смешивается со статическим графом и "
              "не обновляется автоматически при изменении кода. Проверяйте его ссылки и дату аудита.", ""]
    return "\n".join(lines)


def review_overlay() -> dict:
    """Attach separately authored reviews; never infer review from graph nodes."""
    folder = ROOT / "docs/code-review"
    ledger, coverage = folder / "reviews.jsonl", folder / "coverage.json"
    if not ledger.exists() or not coverage.exists():
        return {"available": False, "files": {}}
    audit = json.loads(coverage.read_text())
    ledger_current = audit.get("ledger_sha256") == hashlib.sha256(ledger.read_bytes()).hexdigest()
    symbols = folder / "javascript-symbols.json"
    symbols_current = symbols.exists() and audit.get("javascript_inventory_sha256") == hashlib.sha256(symbols.read_bytes()).hexdigest()
    checked = {r["path"]: r for r in audit["files"]}
    current = {r["path"]: r["sha256"] for r in inventory()}
    reviews = {}
    for line in ledger.read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        evidence = checked.get(row["path"], {})
        row["current"] = bool(ledger_current and symbols_current and evidence.get("current") and
                              row.get("sha256") == evidence.get("sha256") == current.get(row["path"]))
        row["issues"] = list(evidence.get("issues", ["coverage_missing"]))
        if not ledger_current or not symbols_current:
            row["issues"].append("coverage_inputs_changed")
        if row.get("sha256") != current.get(row["path"]):
            row["issues"] = sorted(set(row["issues"] + ["source_changed"]))
        reviews[row["path"]] = row
    return {"available": True, "baseline_commit": audit["baseline_commit"],
            "counts": audit["counts"], "current_now": sum(r["current"] for r in reviews.values()),
            "limitations": audit["limitations"], "files": reviews}


def render(data: dict) -> str:
    template = (ROOT / "scripts/project-terrain-template.html").read_text()
    display = {**data, "code_review": review_overlay()}
    return template.replace("__TERRAIN_DATA__", json.dumps(display, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c"))


def refresh(tracked_only: bool = False) -> None:
    try:
        version = importlib.metadata.version("graphifyy")
    except importlib.metadata.PackageNotFoundError:
        raise SystemExit(f"Need isolated Python environment with graphifyy=={VERSION}; see docs/architecture.md")
    if version != VERSION:
        raise SystemExit(f"Expected graphifyy=={VERSION}, found {version}. Review extractor changes before updating pin.")
    from graphify.extract import collect_files, extract
    from graphify.build import build_from_json
    from graphify.cluster import cluster
    from graphify.export import to_json
    from graphify.diagnostics import diagnose_extraction
    rows = inventory(tracked_only=tracked_only)
    allowed = {r["path"] for r in rows if not r["symlink"]}
    new_files = [p for p in git("ls-files", "--others", "--exclude-standard").splitlines() if p in allowed]
    if new_files:
        print("Nonignored untracked inputs (review before publishing snapshot): " + ", ".join(new_files), flush=True)
    paths = [p for p in collect_files(ROOT) if str(p.relative_to(ROOT)) in allowed]
    RAW.mkdir(parents=True, exist_ok=True)
    print(f"Graphify: {len(paths)} supported inputs / {len(rows)} inventoried files", flush=True)
    # Avoid macOS multiprocessing spawn-from-stdin failures and bound laptop RAM.
    extraction = extract(paths, root=ROOT, cache_root=RAW, parallel=False)
    (RAW / "extraction.json").write_text(json.dumps(extraction, ensure_ascii=False))
    diagnostics = diagnose_extraction(extraction, directed=True, root=str(ROOT))
    (RAW / "diagnostics.json").write_text(json.dumps(diagnostics, indent=2, ensure_ascii=False))
    graph = build_from_json(extraction, root=str(ROOT), directed=True)
    if not graph.number_of_nodes():
        raise SystemExit("Empty Graphify graph: existing portable snapshot was preserved")
    # A new extraction may legitimately shrink after deletions; keep previous graph recoverable.
    graph_path = RAW / "graph.json"
    if graph_path.exists():
        graph_path.replace(RAW / "graph.previous.json")
    to_json(graph, cluster(graph), str(graph_path))
    data = projection(extraction, rows, [str(p.relative_to(ROOT)) for p in paths])
    data["input_scope"] = "tracked" if tracked_only else "worktree"
    if tracked_only:
        data["scope"] = "Git tracked/index files in local main; generated maps and docs/code-review evidence directory excluded; evidence identities checked separately; foreign untracked inputs are outside main"
        data["untracked_at_capture"] = []
    # One JSON record per line: smaller than pretty JSON, reviewable Git diffs.
    header = {k: v for k, v in data.items() if k not in {"files", "edges"}}
    payload = json.dumps(header, ensure_ascii=False, indent=2)[:-2]
    for key in ("files", "edges"):
        payload += ',\n  "' + key + '": [\n'
        payload += ",\n".join("    " + json.dumps(row, ensure_ascii=False) for row in data[key])
        payload += "\n  ]"
    SNAPSHOT.write_text(payload + "\n}\n")
    REPORT.write_text(markdown(data))
    HTML.write_text(render(data))
    print(json.dumps(data["stats"], ensure_ascii=False))


def check(tracked_only: bool | None = None) -> int:
    if not SNAPSHOT.exists():
        print("Terrain missing: run --refresh")
        return 1
    data = json.loads(SNAPSHOT.read_text())
    if tracked_only is None:
        tracked_only = data.get("input_scope") == "tracked"
    expected_scope = "tracked" if tracked_only else "worktree"
    scope_matches = data.get("input_scope", "worktree") == expected_scope
    old = {r["path"]: r["sha256"] for r in data["files"]}
    now = {r["path"]: r["sha256"] for r in inventory(tracked_only=tracked_only)}
    changes = [p for p in sorted(old.keys() | now.keys()) if old.get(p) != now.get(p)]
    for path in changes[:30]:
        print(f"Terrain drift: {path}")
    valid = {f["path"] for f in data["files"]}
    invalid = [e for e in data["edges"] if e["source"] not in valid or e["target"] not in valid]
    generated_ok = REPORT.exists() and REPORT.read_text() == markdown(data)
    knowledge_path = ROOT / "docs/architecture-knowledge.json"
    semantic_stale = []
    historical = False
    if knowledge_path.exists():
        knowledge = json.loads(knowledge_path.read_text())
        historical = knowledge.get("status") == "historical"
        semantic_stale = [p for p, digest in knowledge.get("source_fingerprints", {}).items()
                          if now.get(p) != digest]
    if semantic_stale:
        if historical:
            print(f"Historical semantic graph: {len(semantic_stale)} changed source fingerprints; preserved as dated evidence. Current reviews have a separate audit-code-documentation.py --check gate.")
        else:
            print(f"Current semantic evidence needs review: {len(semantic_stale)} changed source fingerprints")
    if changes or invalid or not generated_ok or not scope_matches or (semantic_stale and not historical):
        print(f"Terrain stale: {len(changes)} files, {len(invalid)} invalid edges, generated outputs match={generated_ok}, input scope match={scope_matches}; refresh structure as reported")
        return 1
    print(f"Terrain OK: {len(now)} file fingerprints, {len(data['edges'])} file edges, generated outputs match")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--refresh", action="store_true")
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--render", action="store_true", help="Render local HTML from the saved JSON (stdlib only)")
    parser.add_argument("--tracked-only", action="store_true", default=None,
                        help="Use Git tracked/index inputs for a reproducible main/CI snapshot")
    args = parser.parse_args()
    if args.check:
        return check(tracked_only=args.tracked_only)
    if args.render:
        HTML.write_text(render(json.loads(SNAPSHOT.read_text())))
        print(f"Rendered {HTML.relative_to(ROOT)}")
        return 0
    refresh(tracked_only=bool(args.tracked_only))
    return 0


if __name__ == "__main__":
    sys.exit(main())
