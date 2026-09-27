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
}
CODE = {".py", ".js", ".jsx", ".mjs", ".ts", ".tsx", ".sh", ".sql"}
DOCS = {".md", ".mdc", ".rst"}


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True)


def inventory() -> list[dict]:
    """Include tracked and nonignored new files, stable before/after git add.

    Generated terrain files are outside their own input set. Symlinks are
    recorded without following them; private ignored files never enter it.
    """
    paths = set(git("ls-files", "-z").split("\0"))
    paths.update(git("ls-files", "--others", "--exclude-standard", "-z").split("\0"))
    rows = []
    for rel in sorted(paths - GENERATED - {""}):
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
        "schema_version": 1, "extractor": f"graphifyy=={VERSION}",
        "baseline_commit": git("rev-parse", "HEAD").strip(),
        "scope": "Working tree: Git tracked + nonignored new files; generated terrain and repo-inventory excluded",
        "unstaged_at_capture": sorted(p for p in git("diff", "--name-only").splitlines() if p not in GENERATED),
        "untracked_at_capture": sorted(p for p in git("ls-files", "--others", "--exclude-standard").splitlines() if p not in GENERATED),
        "stats": {"files": len(rows), "attempted": len(attempted),
                  "files_with_nodes": sum(r["nodes"] > 0 for r in rows),
                  "nodes": len(nodes), "symbol_edges": len(extraction["edges"]),
                  "file_edges": len(edges), "projection_omissions": dict(sorted(omitted.items())),
                  "confidence": dict(sorted(Counter(e.get("confidence", "AMBIGUOUS") for e in extraction["edges"]).items()))},
        "files": rows, "edges": edges,
    }


def markdown(data: dict) -> str:
    s = data["stats"]
    lines = ["# Рельеф проекта — автоматически извлечённый срез", "",
             "> Генерируется `scripts/build-project-terrain.py --refresh` через Graphify. Не править вручную.", "",
             "[Локальный интерактивный просмотр — после `--render`](project-terrain.html) · [JSON](project-terrain.json) · "
             "[Архитектура](architecture.md) · [Контракты](data-contracts.md) · [История решений](architecture-history.md)", "",
             f"Экстрактор: `{data['extractor']}`. Базовый commit: `{data['baseline_commit'][:12]}`; "
             "снимок включает рабочие изменения. SHA-256 каждого входного файла записан в JSON. "
             "`unstaged_at_capture` и `untracked_at_capture` фиксируют состояние входов; коммит карты сам по себе "
             "не коммитит чужие изменения кода. HTML локальный, в Git не хранится; в чистом clone сначала выполнить `--render`.", "",
             "## Покрытие", "", "| Измерение | Число |", "|---|---:|",
             f"| Файлы в инвентаризации | {s['files']} |",
             f"| Переданы структурному экстрактору | {s['attempted']} |",
             f"| Дали узлы графа | {s['files_with_nodes']} |",
             f"| Узлы / связи между символами | {s['nodes']} / {s['symbol_edges']} |",
             f"| Связи между файлами (тип и уверенность сохраняются) | {s['file_edges']} |", "",
             "Полная инвентаризация относится к Git-дереву. Наличие в списке не означает, что каждый файл "
             "прошёл содержательный аудит. `nodes` — экстрактор нашёл структуру; `no_nodes` — файл прочитан "
             "экстрактором, но сущностей не получено; `inventory_only` — учтён без разбора структуры. "
             "Бинарные материалы, конфиги и данные включены в инвентарь; визуальное содержание скриншотов не анализировалось.", "",
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
              "python scripts/build-project-terrain.py --refresh",
              "# Проверка drift, Graphify не требуется",
              "python3 scripts/build-project-terrain.py --check",
              "# Пересоздать HTML из закоммиченного JSON, без Graphify",
              "python3 scripts/build-project-terrain.py --render", "```", "",
              "Полные `extraction.json`, `graph.json` и диагностика сохраняются в "
              "`.artifacts/project-terrain/` (локальные, не Git). "
              "`graphify explain <symbol> --graph .artifacts/project-terrain/graph.json` даёт точечную навигацию. "
              "Для просмотра HTML достаточно открыть файл; сеть и CDN не нужны. "
              "Проверка `--check` отдельная: не включена в обязательные gates `check-all`/CI, "
              "поскольку этот датированный срез включает рабочие изменения параллельных задач. "
              "Команды требуют Git checkout; Python-зависимости для `--check`/`--render` не нужны.", "",
              "Смысловой граф исследовательских агентов — отдельное датированное свидетельство в "
              "`docs/architecture-knowledge.json`; он не смешивается со статическим графом и "
              "не обновляется автоматически при изменении кода. Проверяйте его ссылки и дату аудита.", ""]
    return "\n".join(lines)


def render(data: dict) -> str:
    template = (ROOT / "scripts/project-terrain-template.html").read_text()
    return template.replace("__TERRAIN_DATA__", json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c"))


def refresh() -> None:
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
    rows = inventory()
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


def check() -> int:
    if not SNAPSHOT.exists():
        print("Terrain missing: run --refresh")
        return 1
    data = json.loads(SNAPSHOT.read_text())
    old = {r["path"]: r["sha256"] for r in data["files"]}
    now = {r["path"]: r["sha256"] for r in inventory()}
    changes = [p for p in sorted(old.keys() | now.keys()) if old.get(p) != now.get(p)]
    for path in changes[:30]:
        print(f"Terrain drift: {path}")
    valid = {f["path"] for f in data["files"]}
    invalid = [e for e in data["edges"] if e["source"] not in valid or e["target"] not in valid]
    generated_ok = REPORT.exists() and REPORT.read_text() == markdown(data)
    knowledge_path = ROOT / "docs/architecture-knowledge.json"
    semantic_stale = []
    if knowledge_path.exists():
        knowledge = json.loads(knowledge_path.read_text())
        semantic_stale = [p for p, digest in knowledge.get("source_fingerprints", {}).items()
                          if now.get(p) != digest]
    for path in semantic_stale[:15]:
        print(f"Semantic evidence needs review: {path}")
    if changes or invalid or not generated_ok or semantic_stale:
        print(f"Terrain stale: {len(changes)} files, {len(invalid)} invalid edges, generated outputs match={generated_ok}; refresh structure and review semantic evidence as reported")
        return 1
    print(f"Terrain OK: {len(now)} file fingerprints, {len(data['edges'])} file edges, generated outputs match")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--refresh", action="store_true")
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--render", action="store_true", help="Render local HTML from the saved JSON (stdlib only)")
    args = parser.parse_args()
    if args.check:
        return check()
    if args.render:
        HTML.write_text(render(json.loads(SNAPSHOT.read_text())))
        print(f"Rendered {HTML.relative_to(ROOT)}")
        return 0
    refresh()
    return 0


if __name__ == "__main__":
    sys.exit(main())
