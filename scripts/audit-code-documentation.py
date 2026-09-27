#!/usr/bin/env python3
"""Build/check the evidence ledger for a source review; never mark code reviewed.

The ledger is written by reviewers after reading source. This tool checks hashes,
read ranges and named Python definitions. JavaScript symbols are supplied by the
separate Babel inventory. Generated review artifacts are excluded from recursion.
No application import, database access, network call or production mutation.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
REVIEW_DIR = ROOT / "docs/code-review"
LEDGER = REVIEW_DIR / "reviews.jsonl"
SYMBOLS = REVIEW_DIR / "javascript-symbols.json"
SNAPSHOT = REVIEW_DIR / "coverage.json"
REPORT = ROOT / "docs/code-review.md"
EXCLUDED_FILES = {
    "docs/project-terrain.json", "docs/project-terrain.md", "docs/project-terrain.html",
    "docs/repo-inventory.md", "docs/code-review.md",
}
TEXT_REVIEW = {"reviewed", "body_reviewed"}
DATA_REVIEW = {"data_schema_reviewed", "artifact_schema_reviewed"}
ASSET_REVIEW = {"asset_metadata_reviewed", "binary_asset"}
ACCEPTED = TEXT_REVIEW | DATA_REVIEW | ASSET_REVIEW
CODE_EXTENSIONS = {".py", ".js", ".jsx", ".mjs", ".ts", ".tsx", ".sh", ".sql", ".html", ".css", ".mako"}
JS_EXTENSIONS = {".js", ".jsx", ".mjs", ".ts", ".tsx"}


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True)


def included(path: str) -> bool:
    return path not in EXCLUDED_FILES and not path.startswith("docs/code-review/")


def inventory() -> dict[str, dict]:
    """Use tracked/nonignored paths, without following symlinks or ignored envs."""
    paths = set(git("ls-files", "-z").split("\0"))
    paths.update(git("ls-files", "--others", "--exclude-standard", "-z").split("\0"))
    result = {}
    for name in sorted(filter(None, paths)):
        path = ROOT / name
        if not included(name) or not (path.is_file() or path.is_symlink()):
            continue
        raw = str(path.readlink()).encode() if path.is_symlink() else path.read_bytes()
        try:
            source = raw.decode("utf-8")
        except UnicodeDecodeError:
            source = None
        result[name] = {
            "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw),
            "lines": len(source.splitlines()) if source is not None else None,
            "code": path.suffix in CODE_EXTENSIONS, "source": source,
            "symlink": path.is_symlink(),
        }
    return result


def python_definitions(source: str) -> list[dict]:
    """Include nested functions/methods/classes; lambdas belong to their statement."""
    result = []

    def visit(node: ast.AST, prefix: str = "") -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                name = prefix + child.name
                result.append({"name": name, "line": child.lineno,
                               "end_line": child.end_lineno, "kind": type(child).__name__})
                visit(child, name + ".")
            else:
                visit(child, prefix)

    visit(ast.parse(source))
    return result


def ranges_cover(ranges: list, line_count: int) -> bool:
    if not isinstance(ranges, list) or any(
        not isinstance(pair, list) or len(pair) != 2
        or not all(isinstance(n, int) and not isinstance(n, bool) for n in pair)
        for pair in ranges
    ):
        return False
    if line_count == 0:
        return True
    end = 0
    for pair in sorted(ranges):
        start, stop = pair
        if start < 1 or stop < start or stop > line_count or start > end + 1:
            return False
        end = max(end, stop)
    return end >= line_count


def meaningful(value: object) -> bool:
    if isinstance(value, list):
        return any(meaningful(item) for item in value)
    return isinstance(value, str) and len(value.strip()) > 5 and value.strip().lower() not in {
        "не аннотировано", "pending", "unreviewed", "not reviewed", "indexed",
    }


def definition_covered(definition: dict, elements: list[dict]) -> bool:
    """A line/name match locates evidence; reading a parent alone is insufficient."""
    for element in elements:
        if not meaningful(element.get("purpose")):
            continue
        if not meaningful(element.get("verification")):
            continue
        name = str(element.get("name", ""))
        if name == definition["name"] and element.get("line") == definition["line"]:
            return True
        if (element.get("line") == definition["line"]
                and name.split(".")[-1] == definition["name"].split(".")[-1]):
            return True
    return False


def read_ledger(path: Path = LEDGER) -> tuple[dict[str, dict], list[str]]:
    rows, duplicates = {}, []
    if not path.exists():
        return rows, ["Missing review ledger"]
    for number, line in enumerate(path.read_text().splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        name = row["path"]
        if name in rows:
            duplicates.append(f"Duplicate review at line {number}: {name}")
        rows[name] = row
    return rows, duplicates


def evaluate(files: dict[str, dict], reviews: dict[str, dict], js: dict) -> dict:
    rows = []
    for name, file in files.items():
        review = reviews.get(name, {})
        status = review.get("status", "missing")
        issues = []
        if not review:
            issues.append("missing_review")
        elif review.get("sha256") != file["sha256"]:
            issues.append("source_changed")
        if status not in ACCEPTED:
            issues.append("review_incomplete")
        if review and not meaningful(review.get("summary") or review.get("role")):
            issues.append("missing_purpose")
        if file["code"] and status not in TEXT_REVIEW:
            issues.append("code_needs_body_review")
        if status in TEXT_REVIEW and file["lines"] is not None:
            if not ranges_cover(review.get("read_ranges", []), file["lines"]):
                issues.append("read_range_gap")
        definitions = []
        suffix = Path(name).suffix
        try:
            if suffix == ".py" and file["source"] is not None:
                definitions = python_definitions(file["source"])
            elif suffix in JS_EXTENSIONS:
                symbol_file = js.get(name, {})
                if symbol_file.get("sha256") != file["sha256"]:
                    issues.append("javascript_inventory_stale")
                if symbol_file.get("error"):
                    issues.append("javascript_parse_error")
                definitions = symbol_file.get("definitions", [])
        except SyntaxError as error:
            issues.append(f"python_parse_error:{error.lineno}")
        missing = [d for d in definitions if not definition_covered(d, review.get("elements", []))]
        if missing:
            issues.append("definitions_without_annotation")
        rows.append({"path": name, "sha256": file["sha256"], "bytes": file["bytes"],
                     "lines": file["lines"], "code": file["code"], "status": status,
                     "current": not issues, "issues": issues,
                     "definitions": len(definitions), "annotated_definitions": len(definitions) - len(missing),
                     "missing_definitions": missing})
    counts = Counter(r["status"] for r in rows)
    return {
        "schema_version": 1,
        "scope": "Git tracked and nonignored worktree files, excluding explicit generated review/terrain outputs",
        "excluded_files": sorted(EXCLUDED_FILES), "excluded_prefixes": ["docs/code-review/"],
        "limitations": [
            "A substantive source review is not proof of every runtime path or absence of defects.",
            "Data schema and asset metadata review do not claim verification of every observation or image pixel.",
            "Python/JavaScript named definitions have machine coverage checks; anonymous callbacks and declarative statements are described by their containing reviewed blocks.",
            "Third-party dependencies, ignored local files and runtime secrets are not repository source scope.",
            "Production evidence is dated separately in runtime-inventory.json; local main is not deployed automatically.",
        ],
        "counts": {"files": len(rows), "code_files": sum(r["code"] for r in rows),
                   "current_reviews": sum(r["current"] for r in rows),
                   "statuses": dict(sorted(counts.items())),
                   "definitions": sum(r["definitions"] for r in rows),
                   "annotated_definitions": sum(r["annotated_definitions"] for r in rows),
                   "files_needing_attention": sum(bool(r["issues"]) for r in rows)},
        "orphan_reviews": sorted(set(reviews) - set(files)), "files": rows,
    }


def markdown(data: dict) -> str:
    counts = data["counts"]
    lines = ["# Содержательный разбор локальной main", "",
             "> Генерируется из рецензий, написанных после чтения исходников. Генератор не присваивает статус «прочитано».", "",
             f"Базовый commit: `{data['baseline_commit']}`. SHA-256 каждого файла фиксирует также рабочие изменения.", "",
             "[Просмотрщик](project-terrain.html) · [Архитектура](architecture.md) · [Контракты](data-contracts.md) · "
             "[Сервер и локальная среда](runtime-inventory.json) · [История решений](architecture-history.md) · "
             "[Рецензии JSONL](code-review/reviews.jsonl) · [Покрытие JSON](code-review/coverage.json)", "",
             "## Измеряемое покрытие", "", "| Проверка | Число |", "|---|---:|",
             f"| Файлы в явно определённом scope | {counts['files']} |",
             f"| Код, шаблоны и стили | {counts['code_files']} |",
             f"| Актуальные рецензии без пропусков guard | {counts['current_reviews']} |",
             f"| Именованные определения Python/JS: с аннотацией / всего | {counts['annotated_definitions']} / {counts['definitions']} |",
             f"| Файлы, требующие внимания | {counts['files_needing_attention']} |", "",
             "Полное чтение кода, проверка схем данных и проверка метаданных ресурсов учитываются отдельно. "
             "Рецензия описывает назначение, вход/выход, побочные эффекты, ошибки, связи и границы тестов. "
             "Это не доказательство всех runtime-сценариев, отсутствия ошибок или достоверности каждой точки данных.", "",
             "## Обновление", "", "```bash", "# После изменения исходников — перепрочитать изменённые функции и обновить соответствующую рецензию",
             "node scripts/code-review-symbols.mjs", "python3 scripts/audit-code-documentation.py --build",
             "python3 scripts/audit-code-documentation.py --check", "python3 scripts/build-project-terrain.py --render", "```", "",
             "`--build` не устраняет пропуски: они остаются в отчёте. `--check` возвращает ненулевой код при изменённом SHA, "
             "непрочитанном файле или определении без аннотации. Нельзя просто заменить hash, не проверив diff и затронутые контракты.", "",
             "Scope исключает только генерируемые terrain/review outputs и repo-inventory; перечень исключений сохранён в JSON. "
             "Игнорируемые `.env`, данные локальных томов и сторонний `node_modules` не входят в кодовую рецензию. "
             "Фактическая серверная конфигурация документируется отдельным разрешённым списком полей, без секретов.", "",
             "## Файлы", "", "| Файл | Статус | Определения | Проверка |", "|---|---|---:|---|"]
    for row in data["files"]:
        issue = ", ".join(row["issues"]) or "актуально"
        lines.append(f"| [{row['path']}](../{row['path']}) | {row['status']} | {row['annotated_definitions']}/{row['definitions']} | {issue} |")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--build", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    reviews, errors = read_ledger()
    js = json.loads(SYMBOLS.read_text()) if SYMBOLS.exists() else {}
    data = evaluate(inventory(), reviews, js)
    errors.extend(f"Review outside current scope: {path}" for path in data["orphan_reviews"])
    data["ledger_sha256"] = hashlib.sha256(LEDGER.read_bytes()).hexdigest() if LEDGER.exists() else None
    data["javascript_inventory_sha256"] = hashlib.sha256(SYMBOLS.read_bytes()).hexdigest() if SYMBOLS.exists() else None
    if args.build:
        data["baseline_commit"] = git("rev-parse", "HEAD").strip()
        data["branch"] = git("branch", "--show-current").strip()
        data["unstaged_at_capture"] = [p for p in git("diff", "--name-only").splitlines() if included(p)]
        REVIEW_DIR.mkdir(parents=True, exist_ok=True)
        SNAPSHOT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
        REPORT.write_text(markdown(data))
    else:
        if not SNAPSHOT.exists():
            errors.append("Missing coverage snapshot: run --build after updating reviews")
        else:
            old = json.loads(SNAPSHOT.read_text())
            if any(old.get(key) != data.get(key) for key in (
                "files", "counts", "ledger_sha256", "javascript_inventory_sha256", "orphan_reviews"
            )):
                errors.append("Coverage snapshot differs from current source/reviews")
            if not REPORT.exists() or REPORT.read_text() != markdown(old):
                errors.append("Generated code-review.md differs from coverage snapshot")
    for row in [r for r in data["files"] if r["issues"]][:30]:
        print(row["path"] + ": " + ", ".join(row["issues"]))
    for error in errors:
        print(error)
    print(json.dumps(data["counts"], ensure_ascii=False))
    return 1 if errors or data["counts"]["files_needing_attention"] else 0


if __name__ == "__main__":
    sys.exit(main())
