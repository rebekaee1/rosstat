"""Knowledge-material identity/coverage and terrain scope regressions; no app/DB."""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch


def load_script(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


materials = load_script("knowledge_materials", "audit-knowledge-materials.py")
terrain = load_script("knowledge_terrain", "build-project-terrain.py")


class KnowledgeMaterialsTests(unittest.TestCase):
    def setUp(self):
        self.folder = TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.manifest_path = "docs/code-review/materials-test.json"
        self.paths = {
            "README.md", "AGENTS.md", "CONTEXT.md", ".cursor/rules/current.mdc",
            "docs/architecture.md", "docs/code-review/readiness-criteria.md",
            "docs/code-review/reviews.jsonl", "docs/code-review/probes.json",
            "backend/app/data/example.txt",
        }
        self.rows = []
        for path in sorted(self.paths):
            target = self.root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("Actual content of " + path + "\n")
            self.rows.append({
                "repository_path": path,
                "source_version": {"scope": "tracked/index", "sha256": materials.source_sha256(self.root, path)},
                "review_status": "unknown_body", "body_reviewed_in_this_pass": False,
            })

    def test_current_hashes_pass_without_upgrading_unknown_body(self):
        before = copy.deepcopy(self.rows)
        result = materials.evaluate_materials(self.root, self.paths, self.manifest_path, self.rows)
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["checked"], len(self.paths))
        self.assertEqual(self.rows, before)
        self.assertEqual({row["review_status"] for row in self.rows}, {"unknown_body"})

    def test_new_tracked_document_requires_entry(self):
        result = materials.evaluate_materials(self.root, self.paths | {"docs/new.md"}, self.manifest_path, self.rows)
        self.assertIn("Missing material entry: docs/new.md", result["errors"])

    def test_changed_manual_evidence_hash_fails(self):
        (self.root / "docs/code-review/readiness-criteria.md").write_text("Changed acceptance criteria\n")
        result = materials.evaluate_materials(self.root, self.paths, self.manifest_path, self.rows)
        self.assertIn("Material source changed: docs/code-review/readiness-criteria.md", result["errors"])

    def test_deleted_git_path_and_missing_worktree_file_fail(self):
        path = "docs/code-review/probes.json"
        result = materials.evaluate_materials(self.root, self.paths - {path}, self.manifest_path, self.rows)
        self.assertIn("Material no longer tracked: " + path, result["errors"])
        (self.root / path).unlink()
        result = materials.evaluate_materials(self.root, self.paths, self.manifest_path, self.rows)
        self.assertTrue(any(error.startswith("Material file unavailable: " + path) for error in result["errors"]))

    def test_self_and_generated_maps_do_not_require_hashes(self):
        excluded = materials.GENERATED | {materials.POINTER, self.manifest_path}
        rows = self.rows + [{"repository_path": path, "source_version": {"sha256": None}} for path in sorted(excluded)]
        result = materials.evaluate_materials(self.root, self.paths | excluded, self.manifest_path, rows)
        self.assertEqual(result["errors"], [])

    def test_foreign_untracked_material_does_not_enter_main_or_get_read(self):
        rows = self.rows + [{
            "repository_path": "docs/foreign.md",
            "source_version": {"scope": "observed working tree, not automatically main", "sha256": "stale"},
            "review_status": "metadata_only",
        }]
        result = materials.evaluate_materials(self.root, self.paths, self.manifest_path, rows)
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["skipped_untracked"], 1)
        self.assertFalse((self.root / "docs/foreign.md").exists())

    def test_duplicate_entry_and_invalid_sha_fail(self):
        rows = copy.deepcopy(self.rows)
        rows[0]["source_version"]["sha256"] = "not-a-hash"
        rows.append(copy.deepcopy(rows[1]))
        result = materials.evaluate_materials(self.root, self.paths, self.manifest_path, rows)
        self.assertTrue(any(error.startswith("Missing/invalid material SHA-256:") for error in result["errors"]))
        self.assertTrue(any(error.startswith("Duplicate material:") for error in result["errors"]))

    def test_pointer_selects_tracked_manifest_and_reports_drift(self):
        pointer = self.root / materials.POINTER
        pointer.parent.mkdir(parents=True, exist_ok=True)
        pointer.write_text(json.dumps({"manifest": self.manifest_path}))
        manifest = self.root / self.manifest_path
        manifest.write_text(json.dumps({"materials": self.rows}))
        tracked = self.paths | {materials.POINTER, self.manifest_path}
        with patch.object(materials, "tracked_paths", return_value=tracked):
            self.assertEqual(materials.check(self.root), 0)
            (self.root / "AGENTS.md").write_text("Changed entry\n")
            self.assertEqual(materials.check(self.root), 1)
        with patch.object(materials, "tracked_paths", return_value=self.paths):
            self.assertEqual(materials.check(self.root), 1)

    def test_pointer_cannot_escape_repository_and_bad_json_fails(self):
        pointer = self.root / materials.POINTER
        pointer.parent.mkdir(parents=True, exist_ok=True)
        with patch.object(materials, "tracked_paths", return_value=self.paths | {materials.POINTER}):
            pointer.write_text(json.dumps({"manifest": "../other.json"}))
            self.assertEqual(materials.check(self.root), 1)
            pointer.write_text("not JSON")
            self.assertEqual(materials.check(self.root), 1)


class TerrainScopeTests(unittest.TestCase):
    def test_requested_tracked_scope_rejects_worktree_snapshot(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            snapshot, report = root / "terrain.json", root / "terrain.md"
            with patch.object(terrain, "ROOT", root), patch.object(terrain, "git", return_value="testsha\n"):
                data = terrain.projection({"nodes": [], "edges": []}, [], [])
            data["input_scope"] = "worktree"
            snapshot.write_text(json.dumps(data))
            report.write_text(terrain.markdown(data))
            with patch.object(terrain, "ROOT", root), patch.object(terrain, "SNAPSHOT", snapshot), \
                    patch.object(terrain, "REPORT", report), patch.object(terrain, "inventory", return_value=[]):
                self.assertEqual(terrain.check(tracked_only=True), 1)
                self.assertEqual(terrain.check(tracked_only=False), 0)
                data["input_scope"] = "tracked"
                snapshot.write_text(json.dumps(data))
                report.write_text(terrain.markdown(data))
                self.assertEqual(terrain.check(tracked_only=True), 0)


if __name__ == "__main__":
    unittest.main()
