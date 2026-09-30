#!/usr/bin/env python3
"""Refresh known material metadata; never equate a new hash with a body review.

No server/network calls or discovery outside existing registry locations. External
entries retain their dated observations. New main inputs come only from Git's
tracked/index paths. Explicit evidence assertions require a matching SHA.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
DEFAULT = ROOT / "docs/code-review/materials-2026-09-30.json"
EXCLUDED = {
    "docs/code-review/materials-2026-09-30.json",
    "docs/code-review/materials-current.json",
    "docs/project-terrain.json", "docs/project-terrain.md", "docs/project-terrain.html",
    "docs/repo-inventory.md", "docs/code-review.md",
}
GENERATED = {
    "docs/indicator-index.json", "docs/indicator-index.md", "docs/site-inventory.json",
    "docs/code-review/coverage.json", "docs/code-review/reviews.jsonl",
    "docs/code-review/javascript-symbols.json", "docs/code-review/index.html",
    "docs/code-review/architecture-knowledge.json",
}


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True)


def metadata(name: str) -> dict:
    path = ROOT / name
    raw = str(path.readlink()).encode() if path.is_symlink() else path.read_bytes()
    return {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}


def load_reviews() -> dict:
    """Use exact-version reviewer evidence; a stale row never validates new bytes."""
    result = {}
    paths = [ROOT / "docs/code-review/reviews.jsonl"]
    paths += sorted((ROOT / "docs/code-review").glob("*-delta-reviews-2026-09-30.jsonl"))
    for path in paths:
        if not path.is_file():
            continue
        for line in path.read_text().splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            result.setdefault(row["path"], []).append((path.relative_to(ROOT).as_posix(), row))
    return result


def preserve_prior(row: dict) -> None:
    prior = {key: deepcopy(row.get(key)) for key in (
        "source_version", "review_status", "body_reviewed_in_this_pass",
        "current_delta_reviewed_in_this_pass", "review_basis",
    )}
    history = row.setdefault("prior_version_evidence", [])
    if prior not in history:
        history.append(prior)


def refresh(manifest: dict, assertions: dict) -> dict:
    tracked = set(filter(None, git("ls-files", "-z").split("\0")))
    names = {name for name in tracked
             if (name.startswith(("docs/", ".cursor/rules/")) or name in {"README.md", "AGENTS.md", "CONTEXT.md"})
             and name not in EXCLUDED}
    records = {row["repository_path"]: row for row in manifest["materials"]}
    names.update(records)
    reviews = load_reviews()
    head = git("rev-parse", "HEAD").strip()
    for name in sorted(names):
        if name in EXCLUDED or not (ROOT / name).is_file():
            continue
        current = metadata(name)
        row = records.setdefault(name, {
            "id": name, "location": str(ROOT / name), "repository_path": name,
            "format": Path(name).suffix.lower(), "role": "project material",
            "classification": ("historical_copy" if name.startswith("docs/code-review/source-documents/")
                               else "current_task_evidence" if name.startswith("docs/code-review/") else "current"),
            "canonical_source": name, "linked_mechanisms": None,
            "review_status": "metadata_only", "body_reviewed_in_this_pass": False,
            "review_basis": None,
            "update_action": "Read this version and its linked mechanism before claiming content review.",
        })
        previous_sha = row.get("source_version", {}).get("sha256")
        changed = previous_sha is not None and previous_sha != current["sha256"]
        if changed:
            preserve_prior(row)
        row["source_version"] = {
            "main": head, "scope": "tracked/index" if name in tracked else "observed working tree, not automatically main",
            "date": manifest["date_msk"], **current,
        }
        proof = next(((path, evidence) for path, evidence in reversed(reviews.get(name, []))
                      if evidence.get("sha256") == current["sha256"]), None)
        assertion = assertions.get(name)
        if assertion and assertion.get("sha256") != current["sha256"]:
            raise ValueError(f"Evidence assertion is not for current bytes: {name}")
        if assertion:
            row["body_reviewed_in_this_pass"] = False
            row["current_delta_reviewed_in_this_pass"] = False
            row.update({key: assertion[key] for key in (
                "review_status", "body_reviewed_in_this_pass", "classification"
            ) if key in assertion})
            row["review_basis"] = deepcopy(assertion)
        elif name in GENERATED or row.get("classification") == "generated":
            if row.get("review_basis") is not None and row.get("review_status") != "generated_snapshot":
                preserve_prior(row)
            row["classification"] = "generated"
            row["review_status"] = "generated_snapshot"
            row["body_reviewed_in_this_pass"] = False
            row["current_delta_reviewed_in_this_pass"] = False
            row["review_basis"] = {"method": "Current generated artifact bytes recorded; no new body/value review",
                                   "sha256": current["sha256"], "canonical_source": row.get("canonical_source")}
        elif proof:
            proposal, evidence = proof
            provenance = evidence.get("review_provenance") or evidence.get("review_basis")
            mode = (provenance or {}).get("mode", "exact_version_review_in_ledger")
            if row.get("review_basis") is not None and row.get("review_status") != mode:
                preserve_prior(row)
            row["review_status"] = mode
            row["body_reviewed_in_this_pass"] = mode in {"full_current_body", "full_current_body_read"}
            row["current_delta_reviewed_in_this_pass"] = mode == "previous_full_read_plus_reviewed_delta"
            row["review_basis"] = {"proposal": proposal, "review_provenance": provenance,
                                   "status_in_review": evidence.get("status"), "sha256": current["sha256"]}
        elif changed:
            row["review_status"] = "needs_current_review"
            row["body_reviewed_in_this_pass"] = False
            row["current_delta_reviewed_in_this_pass"] = False
            row["review_basis"] = {"method": "Only current bytes recorded; prior-version reading retained separately",
                                   "sha256": current["sha256"]}
        row["update_action"] = "Keep current metadata and reviewer proof distinct; use prior_version_evidence for old versions."
    manifest["materials"] = [records[name] for name in sorted(records)]
    manifest["metadata_refresh"] = {
        "at_utc": datetime.now(timezone.utc).isoformat(), "head": head,
        "collector": "docs/code-review/refresh-materials-2026-09-30.py",
        "tracked_docs_required": len([n for n in tracked if n.startswith("docs/") and n not in EXCLUDED]),
        "excluded_hash_paths": sorted(EXCLUDED),
        "limit": "SHA refresh does not promote review; external discovery and foreign untracked observations are unchanged.",
    }
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT)
    parser.add_argument("--evidence", type=Path, help="JSON mapping path to exact SHA and explicit reviewer/evidence status")
    parser.add_argument("--output", type=Path, help="Optional preview output; defaults to manifest")
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    evidence = json.loads(args.evidence.read_text()) if args.evidence else {}
    result = refresh(manifest, evidence)
    (args.output or args.manifest).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"materials": len(result["materials"]), "metadata_refresh": result["metadata_refresh"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
