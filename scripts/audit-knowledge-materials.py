#!/usr/bin/env python3
"""Check identity of tracked knowledge materials, without assigning review status.

The active pointer names an authored materials manifest. SHA-256 detects content
drift; it does not establish body reading, correctness, or runtime acceptance.
Only Git tracked/index paths are read. No refresh, application import or network.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
POINTER = "docs/code-review/materials-current.json"
GENERATED = {
    "docs/project-terrain.json", "docs/project-terrain.md", "docs/project-terrain.html",
    "docs/repo-inventory.md", "docs/code-review.md",
}
ROOT_MATERIALS = {"README.md", "AGENTS.md", "CONTEXT.md"}
SHA256 = re.compile(r"[0-9a-fA-F]{64}\Z")


def repository_path(value: object) -> str:
    """Require a canonical relative Git-style path, never a location outside ROOT."""
    if not isinstance(value, str) or not value or "\x00" in value:
        raise ValueError("repository_path must be a nonempty string")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or str(path) != value:
        raise ValueError(f"noncanonical repository_path: {value!r}")
    return value


def tracked_paths(root: Path) -> set[str]:
    """Include staged additions; exclude all nonignored/ignored untracked files."""
    output = subprocess.check_output(
        ["git", "ls-files", "-z"], cwd=root, text=True,
    )
    return set(filter(None, output.split("\0")))


def required_material(path: str) -> bool:
    return path.startswith(("docs/", ".cursor/rules/")) or path in ROOT_MATERIALS


def excluded_material(path: str, manifest_path: str) -> bool:
    """Exclude active manifest/pointer self references and known generated maps."""
    return path in GENERATED or path in {POINTER, manifest_path}


def source_sha256(root: Path, path: str) -> str:
    """Hash a symlink's target spelling; do not follow it to external contents."""
    source = root / path
    raw = str(source.readlink()).encode() if source.is_symlink() else source.read_bytes()
    return hashlib.sha256(raw).hexdigest()


def evaluate_materials(
    root: Path, tracked: set[str], manifest_path: str, materials: list,
) -> dict:
    """Compare identities/coverage, preserving every authored semantic status."""
    errors: list[str] = []
    records: dict[str, dict] = {}
    for number, row in enumerate(materials, 1):
        if not isinstance(row, dict):
            errors.append(f"Invalid material row {number}: expected object")
            continue
        try:
            path = repository_path(row.get("repository_path"))
        except ValueError as exc:
            errors.append(f"Invalid material row {number}: {exc}")
            continue
        if path in records:
            errors.append(f"Duplicate material: {path}")
        else:
            records[path] = row

    expected = {
        path for path in tracked
        if required_material(path) and not excluded_material(path, manifest_path)
    }
    for path in sorted(expected - records.keys()):
        errors.append(f"Missing material entry: {path}")

    checked = 0
    skipped_untracked = 0
    for path, row in sorted(records.items()):
        if excluded_material(path, manifest_path):
            continue
        version = row.get("source_version")
        if path not in tracked:
            # The manifest can preserve explicitly observed foreign working-tree
            # materials. They are outside main and must never become "reviewed"
            # merely because their metadata are retained.
            scope = version.get("scope") if isinstance(version, dict) else None
            observed_untracked = scope == "observed working tree, not automatically main"
            if not observed_untracked:
                errors.append(f"Material no longer tracked: {path}")
            else:
                skipped_untracked += 1
            continue
        digest = version.get("sha256") if isinstance(version, dict) else None
        if not isinstance(digest, str) or not SHA256.fullmatch(digest):
            errors.append(f"Missing/invalid material SHA-256: {path}")
            continue
        try:
            actual = source_sha256(root, path)
        except OSError as exc:
            errors.append(f"Material file unavailable: {path}: {exc.__class__.__name__}")
            continue
        checked += 1
        if actual != digest.lower():
            errors.append(f"Material source changed: {path}")
    return {
        "errors": errors, "required": len(expected), "checked": checked,
        "skipped_untracked": skipped_untracked,
        "meaning": "Content identity only; review_status and body-read claims are not assigned or upgraded.",
    }


def check(root: Path = ROOT) -> int:
    """Resolve tracked active manifest and report drift without writing artifacts."""
    try:
        tracked = tracked_paths(root)
        if POINTER not in tracked:
            raise ValueError(f"Active materials pointer is not tracked/indexed: {POINTER}")
        pointer = json.loads((root / POINTER).read_text())
        if not isinstance(pointer, dict):
            raise ValueError("Active materials pointer must be an object")
        manifest_path = repository_path(pointer.get("manifest"))
        if manifest_path not in tracked:
            raise ValueError(f"Active materials manifest is not tracked/indexed: {manifest_path}")
        manifest = json.loads((root / manifest_path).read_text())
        if not isinstance(manifest, dict) or not isinstance(manifest.get("materials"), list):
            raise ValueError("Active manifest must contain a materials list")
        result = evaluate_materials(root, tracked, manifest_path, manifest["materials"])
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"Knowledge materials check failed: {exc}")
        return 1
    for error in result["errors"][:30]:
        print(error)
    print(json.dumps({key: value for key, value in result.items() if key != "errors"}, ensure_ascii=False))
    return 1 if result["errors"] else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", required=True,
                        help="Read-only identity/coverage check of the active tracked manifest")
    parser.parse_args()
    return check()


if __name__ == "__main__":
    sys.exit(main())
