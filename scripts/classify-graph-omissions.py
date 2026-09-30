#!/usr/bin/env python3
"""Explain every omitted Graphify edge without inventing a resolved runtime call."""
import argparse
import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def normalized(value):
    """Graphify-style path vocabulary; collisions remain explicit."""
    return re.sub(r"[^a-z0-9]+", "_", str(value).lower()).strip("_")


def import_sites(file):
    """Read imports without importing the application or optional packages."""
    if file.suffix != ".py":
        return []
    try:
        tree = ast.parse(file.read_text())
    except (SyntaxError, UnicodeDecodeError):
        return []
    sites = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            modules = [a.name for a in n.names]
        elif isinstance(n, ast.ImportFrom):
            modules = ["." * n.level + (n.module or "")]
        else:
            continue
        sites.append((n.lineno, n.end_lineno, modules))
    return sites


def classify(extraction, terrain, owned_paths):
    """Preserve original ids/anchors and classify only observable source structure."""
    nodes = {n["id"]: n for n in extraction["nodes"]}
    files = {r["path"] for r in terrain["files"]}
    vocabulary = {}
    artifact_reference_vocabulary = {}
    for p in sorted(owned_paths):
        for key in {normalized(Path(p).with_suffix("")), normalized(ROOT / Path(p).with_suffix("")),
                    normalized(p), normalized(ROOT / p)}:
            vocabulary.setdefault(key, []).append(p)
        candidates = [Path(p)] if not Path(p).suffix else []
        candidates += [d for d in Path(p).parents if str(d) != "."]
        for candidate in candidates:
            for key in {normalized(str(candidate) + ".md"), normalized(str(ROOT / candidate) + ".md")}:
                artifact_reference_vocabulary.setdefault(key, set()).add(str(candidate))
    cache = {}
    result = []
    for index, edge in enumerate(extraction["edges"]):
        a, b = nodes.get(edge.get("source")), nodes.get(edge.get("target"))
        if a and b and a.get("source_file") in files and b.get("source_file") in files:
            continue
        file = edge.get("source_file", "")
        if file not in cache:
            source = ROOT / file
            cache[file] = (source.read_text(errors="replace").splitlines(), import_sites(source)) if source.is_file() else ([], [])
        lines, imports = cache[file]
        found = re.search(r"\d+", str(edge.get("source_location", "")))
        line = int(found.group()) if found else 0
        modules = [m for start, end, mods in imports if start <= line <= end for m in mods]
        target_paths = sorted(set(vocabulary.get(edge.get("target"), [])))
        relation = edge.get("relation", "unknown")
        excerpt = lines[line - 1] if 0 < line <= len(lines) else ""
        category = "symbol_without_owned_file"
        explanation = "Extractor endpoint has no repository source file; label/dispatch is retained, runtime callee is not asserted."
        if relation in {"imports", "imports_from"} and modules:
            tops = {m.lstrip(".").split(".")[0] for m in modules}
            if all(m in sys.stdlib_module_names for m in tops):
                category, explanation = "python_standard_library", "Import is outside the project source inventory."
            elif any(m.startswith(".") or m.split(".")[0] in {"app", "scripts", "tests"} for m in modules):
                category, explanation = "local_import_without_extracted_endpoint", "Local import declaration is preserved; module/symbol resolution is not supplied by this endpoint."
            else:
                category, explanation = "python_package_import", "Import refers to a dependency; installation/version is governed by requirements/constraints, not a repository function node."
        elif relation in {"references", "inherits"} and b and not b.get("source_file"):
            category, explanation = "external_type_or_symbol_reference", "Type/base/symbol endpoint is outside owned files; imported or dynamic identity remains at the source anchor."
        elif target_paths:
            category = "owned_target_excluded_or_not_extracted" if len(target_paths) == 1 else "ambiguous_owned_target"
            explanation = "Owned path exists in Git; generated/evidence/data documents may be excluded from the graph. No synthetic edge is added."
        elif relation == "references":
            category, explanation = "document_reference_without_endpoint", "Historical, external or unmatched document reference; original id and source anchor retained for inspection."
            artifact_paths = sorted(artifact_reference_vocabulary.get(edge.get("target"), set()))
            if artifact_paths:
                target_paths = artifact_paths
                category, explanation = "directory_or_extensionless_reference_encoding", "Graphify encodes a directory/extensionless document link as .md; source paths exist, encoded node id does not."
        elif relation == "dynamic_import":
            category, explanation = "dynamic_import_endpoint", "Dynamic module/fixture import is retained; source endpoint is external or generated at execution. No callee is invented."
        elif relation in {"imports", "imports_from", "re_exports"}:
            category, explanation = "non_python_import_without_endpoint", "Module import/export is retained; consult independent client import inventory for exact source/dependency resolution."
            match = re.search(r"(?:from\s+|import\s*)['\"]([^'\"]+)['\"]", excerpt)
            if match:
                modules = [match.group(1)]
                if modules[0].startswith("node:"):
                    category, explanation = "node_standard_library", "Node built-in module, not an owned project source."
                elif modules[0].startswith("."):
                    category, explanation = "client_local_import_without_symbol_endpoint", "Local module import is resolved separately in the client inventory; this extracted symbol endpoint is absent."
                else:
                    category, explanation = "client_package_import", "External package import; package-lock records version/integrity."
        row = {"edge_index": index, "projection_reason": "missing_endpoint" if not a or not b else "external_or_unresolved_file",
               "category": category, "explanation": explanation, "edge": edge,
               "source_endpoint": {k: a.get(k) for k in ("label", "source_file", "source_location")} if a else None,
               "target_endpoint": {k: b.get(k) for k in ("label", "source_file", "source_location")} if b else None,
               "owned_target_candidates": target_paths, "import_modules_at_anchor": modules,
               "current_anchor_excerpt": excerpt or None}
        result.append(row)
    return result


def check_identity(report, terrain_raw):
    """Check portable projection identity and preserved totals without local raw graph."""
    terrain = json.loads(terrain_raw)
    expected = {k: v for k, v in terrain["stats"]["projection_omissions"].items() if k != "within_file"}
    records = report["records"]
    failures = []
    if report.get("terrain_sha256") != hashlib.sha256(terrain_raw).hexdigest():
        failures.append("terrain source changed")
    if report["counts"] != expected or dict(Counter(r["projection_reason"] for r in records)) != expected:
        failures.append("omission totals differ")
    if report["categories"] != dict(sorted(Counter(r["category"] for r in records).items())):
        failures.append("category totals differ")
    return failures


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default=".artifacts/project-terrain/extraction.json")
    parser.add_argument("--output", default="docs/code-review/graph-omission-classification-2026-09-30.json")
    parser.add_argument("--check", action="store_true", help="Read-only portable terrain SHA/count guard; raw .artifacts not required")
    args = parser.parse_args()
    terrain_raw = (ROOT / "docs/project-terrain.json").read_bytes()
    if args.check:
        report = json.loads((ROOT / args.output).read_text())
        failures = check_identity(report, terrain_raw)
        if failures:
            raise SystemExit("Omission classification stale: " + "; ".join(failures))
        print("Omission classification OK: " + str(len(report["records"])) + " preserved edges; terrain SHA current")
        return
    input_path = ROOT / args.input
    raw = input_path.read_bytes()
    extraction = json.loads(raw)
    terrain = json.loads(terrain_raw)
    paths = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode().split("\0")
    rows = classify(extraction, terrain, {p for p in paths if p})
    reasons = Counter(r["projection_reason"] for r in rows)
    expected = {k: v for k, v in terrain["stats"]["projection_omissions"].items() if k != "within_file"}
    if dict(reasons) != expected:
        raise SystemExit(f"Input/projection mismatch: {dict(reasons)} != {expected}; refresh terrain first")
    data = {"schema_version": 1, "terrain_sha256": hashlib.sha256(terrain_raw).hexdigest(), "extraction_sha256": hashlib.sha256(raw).hexdigest(),
            "terrain_baseline_commit": terrain["baseline_commit"], "counts": dict(sorted(reasons.items())),
            "categories": dict(sorted(Counter(r["category"] for r in rows).items())),
            "limits": ["Classification is structural, not proof of runtime resolution or absence of bugs.",
                       "Every omitted endpoint has its original evidence. within_file edges remain in the symbol graph.",
                       "Current excerpts can differ from an older extraction: original source fingerprint and fresh terrain check are authoritative."],
            "records": rows}
    (ROOT / args.output).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"counts": data["counts"], "categories": data["categories"]}))


if __name__ == "__main__":
    main()
