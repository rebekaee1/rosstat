"""Narrow actual-function regressions; temporary files, no application/network import.

Run with --output to preserve a dated result. This file is evidence, not runtime.
"""
import argparse
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("dossier_terrain_review", ROOT / "scripts/build-project-terrain.py")
TERRAIN = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TERRAIN)
OBSERVATIONS = []


class TerrainOverlayTests(unittest.TestCase):
    def mcp_fixture(self, directory, with_client=False):
        root = Path(directory)
        (root / "docs").mkdir()
        (root / "mcp").mkdir()
        source = root / "mcp/fixture.ts"
        source.write_text("source unchanged\n")
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        records = [{"path": "mcp/fixture.ts", "line": n + 1, "name": f"tool{n}"} for n in range(7)]
        (root / "docs/mechanism-inventory.json").write_text(json.dumps({
            "source_files": [{"path": "mcp/fixture.ts", "sha256": digest}], "mcp_tools": records}))
        if with_client:
            (root / "docs/client-mechanism-inventory.json").write_text(json.dumps({
                "files": {"mcp/fixture.ts": {"sha256": digest, "mcp_tools": records}}}))
        return root

    def test_backend_mcp_fallback_preserves_all_tools(self):
        with tempfile.TemporaryDirectory(prefix="fe-dossier-mcp-") as directory:
            root = self.mcp_fixture(directory)
            with patch.object(TERRAIN, "ROOT", root):
                row = TERRAIN.mechanism_overlay()["mcp/fixture.ts"]
            OBSERVATIONS.append({"case": "backend_mcp_fallback", "expected": 7,
                                 "actual": len(row["records"]), "source_current": row["current"]})
            self.assertEqual(len(row["records"]), 7)
            self.assertTrue(row["current"])

    def test_client_mcp_is_not_duplicated_by_backend(self):
        with tempfile.TemporaryDirectory(prefix="fe-dossier-mcp-") as directory:
            root = self.mcp_fixture(directory, with_client=True)
            with patch.object(TERRAIN, "ROOT", root):
                row = TERRAIN.mechanism_overlay()["mcp/fixture.ts"]
            OBSERVATIONS.append({"case": "client_mcp_deduplication", "expected": 7, "actual": len(row["records"])})
            self.assertEqual(len(row["records"]), 7)

    def check_fixture(self, html_present):
        # Real snapshot/report schema and actual check/render functions. Only Git
        # enumeration is replaced by identical saved fingerprints; there is no
        # source drift. This isolates ignored HTML/overlay freshness from hashes.
        data = json.loads(TERRAIN.SNAPSHOT.read_text())
        with tempfile.TemporaryDirectory(prefix="fe-dossier-html-") as directory:
            root = Path(directory)
            (root / "docs").mkdir()
            (root / "scripts").mkdir()
            shutil.copyfile(ROOT / "scripts/project-terrain-template.html", root / "scripts/project-terrain-template.html")
            snapshot = root / "docs/project-terrain.json"
            report = root / "docs/project-terrain.md"
            html = root / "docs/project-terrain.html"
            snapshot.write_text(json.dumps(data))
            report.write_text(TERRAIN.markdown(data))
            if html_present:
                html.write_text("<html>obsolete embedded reviews/mechanisms</html>")
            output = io.StringIO()
            with patch.object(TERRAIN, "ROOT", root), patch.object(TERRAIN, "SNAPSHOT", snapshot), \
                    patch.object(TERRAIN, "REPORT", report), patch.object(TERRAIN, "HTML", html), \
                    patch.object(TERRAIN, "inventory", return_value=data["files"]), contextlib.redirect_stdout(output):
                result = TERRAIN.check(tracked_only=True)
            return result, output.getvalue().strip()

    def test_present_stale_html_is_rejected(self):
        status, output = self.check_fixture(html_present=True)
        OBSERVATIONS.append({"case": "present_stale_html", "expected_nonzero": True, "actual_exit": status, "stdout": output})
        self.assertNotEqual(status, 0)

    def test_absent_ignored_html_keeps_clean_clone_valid(self):
        status, output = self.check_fixture(html_present=False)
        OBSERVATIONS.append({"case": "clean_clone_html_absent", "expected_exit": 0, "actual_exit": status, "stdout": output})
        self.assertEqual(status, 0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="docs/code-review/final-dossier-review-probes-2026-09-30.json")
    args = parser.parse_args()
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(TerrainOverlayTests))
    record = {"basis": "Actual terrain functions; temporary files and identical inventory double; no application/network imports.",
              "source_sha256": hashlib.sha256((ROOT / "scripts/build-project-terrain.py").read_bytes()).hexdigest(),
              "tests_run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors), "observations": OBSERVATIONS}
    (ROOT / args.output).write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
    raise SystemExit(0 if result.wasSuccessful() else 1)
