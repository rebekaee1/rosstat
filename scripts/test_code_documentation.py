"""Evidence guard tests; no application imports, network or database access."""
import hashlib
import importlib.util
from pathlib import Path
import unittest
from tempfile import TemporaryDirectory
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    "audit_code_documentation", Path(__file__).with_name("audit-code-documentation.py")
)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class EvidenceGuardTests(unittest.TestCase):
    def fixture(self):
        source = "def outer():\n    def inner():\n        return 1\n    return inner()\n"
        digest = hashlib.sha256(source.encode()).hexdigest()
        file = {"sha256": digest, "source": source, "lines": 4, "bytes": len(source), "code": True}
        review = {"sha256": digest, "status": "reviewed", "summary": "Return nested helper result",
                  "read_ranges": [[1, 4]], "elements": [
                      {"name": "outer", "line": 1, "purpose": "Call nested helper", "verification": "body_reviewed"},
                      {"name": "outer.inner", "line": 2, "purpose": "Return constant one", "verification": "body_reviewed"}]}
        return file, review

    def evaluate(self, file, review):
        return audit.evaluate({"sample.py": file}, {"sample.py": review}, {})["files"][0]

    def test_nested_definition_requires_own_annotation(self):
        file, review = self.fixture()
        self.assertTrue(self.evaluate(file, review)["current"])
        review["elements"].pop()
        row = self.evaluate(file, review)
        self.assertEqual([d["name"] for d in row["missing_definitions"]], ["outer.inner"])
        self.assertFalse(row["current"])

    def test_changed_source_fails_even_when_names_stay(self):
        file, review = self.fixture()
        file["sha256"] = "changed"
        self.assertIn("source_changed", self.evaluate(file, review)["issues"])

    def test_purpose_without_reading_evidence_is_incomplete(self):
        file, review = self.fixture()
        review["elements"][0].pop("verification")
        self.assertIn("definitions_without_annotation", self.evaluate(file, review)["issues"])

    def test_read_range_gap_and_malformed_input_fail(self):
        self.assertTrue(audit.ranges_cover([[3, 5], [1, 2]], 5))
        for ranges in ([[1, 2], [4, 5]], [[1, 5], None], "1..5", [[True, 5]], [[0, 5]], [[1, 999999]]):
            with self.subTest(ranges=ranges):
                self.assertFalse(audit.ranges_cover(ranges, 5))

    def test_same_name_at_another_location_does_not_cover_definition(self):
        element = {"name": "C.f", "line": 1, "purpose": "Return value", "verification": "body_reviewed"}
        self.assertTrue(audit.definition_covered({"name": "C.f", "line": 1}, [element]))
        self.assertFalse(audit.definition_covered({"name": "C.f", "line": 9}, [element]))

    def test_schema_review_cannot_stand_in_for_code(self):
        file, review = self.fixture()
        review["status"] = "data_schema_reviewed"
        self.assertIn("code_needs_body_review", self.evaluate(file, review)["issues"])

    def test_missing_javascript_inventory_fails(self):
        file, review = self.fixture()
        row = audit.evaluate({"sample.js": file}, {"sample.js": review}, {})["files"][0]
        self.assertIn("javascript_inventory_stale", row["issues"])

    def test_generated_review_artifacts_do_not_recurse(self):
        self.assertFalse(audit.included("docs/code-review/reviews.jsonl"))
        self.assertFalse(audit.included("docs/project-terrain.json"))
        self.assertTrue(audit.included("scripts/audit-code-documentation.py"))
        self.assertTrue(audit.included("docs/architecture.md"))

    def test_tracked_snapshot_excludes_foreign_untracked_and_keeps_staged_new(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'existing.py').write_text('value = 1\n')
            (root / 'staged-new.py').write_text('value = 2\n')
            (root / 'other-task.md').write_text('Foreign work remains on disk\n')
            def fake_git(*args):
                return ('other-task.md\0' if '--others' in args
                        else 'existing.py\0staged-new.py\0')
            with patch.object(audit, 'ROOT', root), patch.object(audit, 'git', fake_git):
                self.assertEqual(set(audit.inventory(tracked_only=True)), {'existing.py', 'staged-new.py'})
                self.assertIn('other-task.md', audit.inventory())

    def test_new_tracked_source_requires_review_and_deleted_source_leaves_orphan(self):
        file, review = self.fixture()
        data = audit.evaluate({'new.py': file}, {'deleted.py': review}, {})
        self.assertIn('missing_review', data['files'][0]['issues'])
        self.assertEqual(data['orphan_reviews'], ['deleted.py'])


if __name__ == "__main__":
    unittest.main()
