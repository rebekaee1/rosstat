"""Regression checks for omitted evidence and anonymous/dynamic client mechanisms."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("omissions", ROOT / "scripts/classify-graph-omissions.py")
omissions = importlib.util.module_from_spec(spec)
spec.loader.exec_module(omissions)


class RepositoryScopeTests(unittest.TestCase):
    def test_both_generators_default_to_index_and_untracked_is_explicit(self):
        with tempfile.TemporaryDirectory(prefix="fe-map-scope-") as directory:
            repo = Path(directory)
            (repo / "tracked.py").write_text("# tracked\n")
            (repo / "new-indexed.py").write_text("# new index entry\n")
            (repo / "untracked.py").write_text("# unrelated working file\n")
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            subprocess.run(["git", "add", "tracked.py"], cwd=repo, check=True)
            modules = []
            for script in ("build-indicator-index.py", "repo-inventory.py"):
                spec = importlib.util.spec_from_file_location("scope_" + script.replace("-", "_"), ROOT / "scripts" / script)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                module.ROOT = repo
                self.assertEqual([p.name for p in module._git_tracked()], ["tracked.py"])
                modules.append((script, module))
            # No commit is needed: git add makes new main inputs visible.
            subprocess.run(["git", "add", "new-indexed.py"], cwd=repo, check=True)
            for script, module in modules:
                with self.subTest(generator=script):
                    self.assertEqual({p.name for p in module._git_tracked()}, {"tracked.py", "new-indexed.py"})
                    self.assertEqual({p.name for p in module._git_tracked(include_untracked=True)},
                                     {"tracked.py", "new-indexed.py", "untracked.py"})


class OmissionClassificationTests(unittest.TestCase):
    def test_no_fabricated_owned_runtime_target(self):
        extraction = {"nodes": [{"id": "source", "source_file": "backend/app/api/auth.py"},
                                 {"id": "type", "label": "BaseModel", "source_file": ""}],
                      "edges": [{"source": "source", "target": "type", "relation": "inherits",
                                 "source_file": "backend/app/api/auth.py", "source_location": "L1"}]}
        result = omissions.classify(extraction, {"files": [{"path": "backend/app/api/auth.py"}]}, set())
        self.assertEqual(result[0]["category"], "external_type_or_symbol_reference")
        self.assertEqual(result[0]["target_endpoint"]["source_file"], "")
        self.assertEqual(result[0]["edge"], extraction["edges"][0])

    def test_excluded_document_path_collision_is_not_guessed(self):
        extraction = {"nodes": [{"id": "source", "source_file": "AGENTS.md"}],
                      "edges": [{"source": "source", "target": "docs_project_terrain", "relation": "references",
                                 "source_file": "AGENTS.md", "source_location": "L13"}]}
        result = omissions.classify(extraction, {"files": [{"path": "AGENTS.md"}]},
                                    {"docs/project-terrain.md", "docs/project-terrain.json"})
        self.assertEqual(result[0]["category"], "ambiguous_owned_target")
        self.assertEqual(len(result[0]["owned_target_candidates"]), 2)
        self.assertIsNone(result[0]["target_endpoint"])

    def test_omission_portable_identity_and_counts_detect_drift(self):
        import hashlib
        terrain_raw = json.dumps({"stats": {"projection_omissions": {"missing_endpoint": 1, "within_file": 8}}}).encode()
        report = {"terrain_sha256": hashlib.sha256(terrain_raw).hexdigest(),
                  "counts": {"missing_endpoint": 1}, "categories": {"external_type_or_symbol_reference": 1},
                  "records": [{"projection_reason": "missing_endpoint", "category": "external_type_or_symbol_reference"}]}
        self.assertEqual(omissions.check_identity(report, terrain_raw), [])
        self.assertIn("terrain source changed", omissions.check_identity(report, terrain_raw + b" "))
        report["records"] = []
        self.assertIn("omission totals differ", omissions.check_identity(report, terrain_raw))


class ClientInventoryTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node") and (ROOT / "frontend/node_modules/@babel/parser").exists(),
                         "Node and frontend Babel dependencies required")
    def test_route_callback_storage_import_and_drift(self):
        with tempfile.TemporaryDirectory(prefix="fe-client-inventory-") as directory:
            repo = Path(directory)
            (repo / "scripts").mkdir()
            (repo / "docs").mkdir()
            (repo / "frontend/src").mkdir(parents=True)
            shutil.copyfile(ROOT / "scripts/build-client-mechanism-inventory.mjs", repo / "scripts/build-client-mechanism-inventory.mjs")
            (repo / "frontend/package.json").write_text('{}\n')
            (repo / "frontend/node_modules").symlink_to(ROOT / "frontend/node_modules", target_is_directory=True)
            source = repo / "frontend/src/App.jsx"
            source.write_text('import { Route } from "react-router-dom";\nimport data from "./data.json";\n'
                              'export function App() { return <Route path="/fixture" element={<button onClick={() => localStorage.setItem("fixture", data)}>OK</button>} />; }\n')
            (repo / "frontend/src/data.json").write_text('{}\n')
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            subprocess.run(["git", "add", "scripts", "frontend/package.json", "frontend/src"], cwd=repo, check=True)
            command = ["node", "scripts/build-client-mechanism-inventory.mjs"]
            subprocess.run(command + ["--build"], cwd=repo, capture_output=True, check=True)
            row = json.loads((repo / "docs/client-mechanism-inventory.json").read_text())["files"]["frontend/src/App.jsx"]
            self.assertEqual(row["routes"][0]["attributes"]["path"], '"/fixture"')
            self.assertEqual(row["jsx_handlers"][0]["event"], "onClick")
            self.assertEqual(row["storage"][0]["owner"], "App.<callback@3>")
            self.assertEqual(row["imports"][1]["targets"], ["frontend/src/data.json"])
            self.assertTrue(any(f["name"] is None and f["owner"] == "App" for f in row["functions"]))
            subprocess.run(command + ["--check"], cwd=repo, capture_output=True, check=True)
            source.write_text(source.read_text().replace('/fixture', '/changed'))
            self.assertNotEqual(subprocess.run(command + ["--check"], cwd=repo, capture_output=True).returncode, 0)


class TerrainArtifactTests(unittest.TestCase):
    def load(self):
        spec = importlib.util.spec_from_file_location("terrain_mechanism_test", ROOT / "scripts/build-project-terrain.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_refresh_html_uses_saved_snapshot_order(self):
        import ast
        module = self.load()
        # Execute the actual refresh artifact writes, without Graphify/network.
        tree = ast.parse((ROOT / "scripts/build-project-terrain.py").read_text())
        refresh = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "refresh")
        writes = [n for n in refresh.body if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call)
                  and isinstance(n.value.func, ast.Attribute) and n.value.func.attr == "write_text"
                  and isinstance(n.value.func.value, ast.Name)
                  and n.value.func.value.id in {"SNAPSHOT", "REPORT", "HTML"}]
        self.assertEqual(len(writes), 3)
        with tempfile.TemporaryDirectory(prefix="fe-refresh-order-") as directory:
            module.ROOT = Path(directory)
            (module.ROOT / "scripts").mkdir()
            (module.ROOT / "scripts/project-terrain-template.html").write_text("__TERRAIN_DATA__")
            module.SNAPSHOT = module.ROOT / "snapshot.json"
            module.REPORT = module.ROOT / "report.md"
            module.HTML = module.ROOT / "report.html"
            data = {"files": [], "edges": [], "input_scope": "tracked"}
            saved = {"input_scope": "tracked", "files": [], "edges": []}
            namespace = {"data": data, "payload": json.dumps(saved)[:-1], "json": json,
                         "SNAPSHOT": module.SNAPSHOT, "REPORT": module.REPORT, "HTML": module.HTML,
                         "markdown": lambda _: "report", "render": module.render}
            exec(compile(ast.Module(body=writes, type_ignores=[]), "actual_refresh_writes", "exec"), namespace)
            self.assertEqual(module.HTML.read_text(), module.render(json.loads(module.SNAPSHOT.read_text())))

    def test_backend_mcp_fallback_preserves_all_tools(self):
        module = self.load()
        with tempfile.TemporaryDirectory(prefix="fe-overlay-") as directory:
            module.ROOT = Path(directory)
            (module.ROOT / "docs").mkdir()
            source = module.ROOT / "mcp.ts"
            source.write_text("fixture")
            import hashlib
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            inventory = {"source_files": [{"path": "mcp.ts", "sha256": digest}],
                         "mcp_tools": [{"path": "mcp.ts", "name": "tool" + str(i)} for i in range(7)]}
            (module.ROOT / "docs/mechanism-inventory.json").write_text(json.dumps(inventory))
            result = module.mechanism_overlay()["mcp.ts"]
            self.assertTrue(result["current"])
            self.assertEqual(len(result["records"]), 7)
            # Client has the complete MCP list; backend copies must not duplicate it.
            (module.ROOT / "docs/client-mechanism-inventory.json").write_text(json.dumps({"files": {
                "mcp.ts": {"sha256": digest, "mcp_tools": inventory["mcp_tools"]}}}))
            self.assertEqual(len(module.mechanism_overlay()["mcp.ts"]["records"]), 7)

    def test_existing_html_drift_fails_but_clean_clone_needs_no_ignored_html(self):
        module = self.load()
        with tempfile.TemporaryDirectory(prefix="fe-html-guard-") as directory:
            module.ROOT = Path(directory)
            module.SNAPSHOT = module.ROOT / "snapshot.json"
            module.REPORT = module.ROOT / "report.md"
            module.HTML = module.ROOT / "report.html"
            module.SNAPSHOT.write_text(json.dumps({"input_scope": "tracked", "files": [], "edges": []}))
            module.inventory = lambda **_: []
            module.markdown = lambda _: "current report"
            module.render = lambda _: "current overlays"
            module.REPORT.write_text("current report")
            self.assertEqual(module.check(), 0)
            module.HTML.write_text("obsolete overlays")
            self.assertEqual(module.check(), 1)
            module.HTML.write_text("current overlays")
            self.assertEqual(module.check(), 0)


if __name__ == "__main__":
    unittest.main()
