"""The terrain must detect stale inputs and preserve direction/uncertainty."""
import importlib.util
import json
from pathlib import Path
import subprocess

import pytest


SCRIPT = Path(__file__).resolve().parents[2] / "scripts/build-project-terrain.py"


@pytest.fixture
def terrain(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("project_terrain", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    monkeypatch.setattr(module, "ROOT", tmp_path)
    for name, filename in [("SNAPSHOT", "project-terrain.json"), ("REPORT", "project-terrain.md"), ("HTML", "project-terrain.html")]:
        monkeypatch.setattr(module, name, tmp_path / "docs" / filename)
    (tmp_path / "docs").mkdir()
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts/project-terrain-template.html").write_text("<script>__TERRAIN_DATA__</script>")
    (tmp_path / ".gitignore").write_text(".env\n.artifacts/\n")
    (tmp_path / "source.py").write_text("value = 1\n")
    (tmp_path / ".env").write_text("PRIVATE=do-not-read\n")
    return module


def save_snapshot(module):
    data = {"files": module.inventory(), "edges": []}
    module.SNAPSHOT.write_text(json.dumps(data))
    module.REPORT.write_text("report")
    module.HTML.write_text(module.render(data))
    return data


def test_inventory_excludes_private_ignored_files_and_generated_outputs(terrain):
    before = terrain.inventory()
    terrain.SNAPSHOT.write_text("generated")
    (terrain.ROOT / "docs/repo-inventory.md").write_text("self-count")
    assert terrain.inventory() == before
    assert ".env" not in {f["path"] for f in before}
    subprocess.run(["git", "add", "."], cwd=terrain.ROOT, check=True)
    assert terrain.inventory() == before  # same snapshot before and after staging


@pytest.mark.parametrize("change", ["modify", "add", "delete"])
def test_check_fails_when_checkout_changes(terrain, monkeypatch, change):
    monkeypatch.setattr(terrain, "markdown", lambda _: "report")
    monkeypatch.setattr(terrain, "render", lambda _: "html")
    save_snapshot(terrain)
    assert terrain.check() == 0
    if change == "modify":
        (terrain.ROOT / "source.py").write_text("value = 2\n")
    elif change == "add":
        (terrain.ROOT / "new.py").write_text("value = 3\n")
    else:
        (terrain.ROOT / "source.py").unlink()
    assert terrain.check() == 1


def test_symlink_does_not_read_outside_repository(terrain, tmp_path):
    external = tmp_path.parent / "terrain-private.txt"
    external.write_text("private payload")
    (terrain.ROOT / "outside-link").symlink_to(external)
    row = next(f for f in terrain.inventory() if f["path"] == "outside-link")
    assert row["symlink"] is True
    assert row["bytes"] == len(str(external).encode())


def test_structural_refresh_does_not_silently_approve_old_semantics(terrain, monkeypatch):
    monkeypatch.setattr(terrain, "markdown", lambda _: "report")
    monkeypatch.setattr(terrain, "render", lambda _: "html")
    original = next(f for f in terrain.inventory() if f["path"] == "source.py")
    (terrain.ROOT / "docs/architecture-knowledge.json").write_text(json.dumps({
        "source_fingerprints": {"source.py": original["sha256"]}}))
    save_snapshot(terrain)
    assert terrain.check() == 0
    (terrain.ROOT / "source.py").write_text("value = 2\n")
    save_snapshot(terrain)  # Structural hashes updated, semantic review still old.
    assert terrain.check() == 1


def test_explicitly_historical_evidence_is_preserved_without_claiming_current(terrain, monkeypatch):
    monkeypatch.setattr(terrain, "markdown", lambda _: "report")
    source = terrain.ROOT / "source.py"
    original = next(f for f in terrain.inventory() if f["path"] == "source.py")
    historical = {"status": "historical", "source_fingerprints": {"source.py": original["sha256"]}}
    knowledge = terrain.ROOT / "docs/architecture-knowledge.json"
    knowledge.write_text(json.dumps(historical))
    source.write_text("value = 2\n")
    save_snapshot(terrain)
    assert terrain.check() == 0
    assert json.loads(knowledge.read_text()) == historical
    row = next(f for f in terrain.inventory() if f["path"] == "source.py")
    row["nodes"] = 1
    overview = terrain.overview([row], [])
    assert overview["semantic_stale"] == ["source.py"]


def test_projection_preserves_direction_and_confidence(terrain, monkeypatch):
    monkeypatch.setattr(terrain, "git", lambda *args: "baseline")
    nodes = [{"id": key, "label": key, "source_file": path} for key, path in
             [("a", "a.py"), ("b", "b.py"), ("external", "outside.py")]]
    edges = [dict(source=a, target=b, relation="calls", confidence=confidence)
             for a, b, confidence in [("a", "b", "EXTRACTED"), ("b", "a", "INFERRED"),
                                      ("a", "external", "INFERRED"), ("a", "a", "EXTRACTED"),
                                      ("a", "missing", "INFERRED")]]
    rows = [{"path": path} for path in ("a.py", "b.py", "empty.py", "data.csv")]
    data = terrain.projection({"nodes": nodes, "edges": edges}, rows, ["a.py", "b.py", "empty.py"])
    assert [(e["source"], e["target"], e["confidence"]) for e in data["edges"]] == [
        ("a.py", "b.py", "EXTRACTED"), ("b.py", "a.py", "INFERRED")]
    assert [r["extraction"] for r in rows] == ["nodes", "nodes", "no_nodes", "inventory_only"]
    assert data["stats"]["projection_omissions"] == {
        "within_file": 1, "external_or_unresolved_file": 1, "missing_endpoint": 1}


def test_overview_is_a_complete_partition_and_preserves_relation_totals(terrain):
    paths = ["frontend/src/pages/Home.jsx", "frontend/src/lib/api.js", "backend/app/api/world.py",
             "backend/app/services/world.py", "backend/tests/test_world.py", "unknown/deep/file.css"]
    rows = [dict(path=p, kind="code", nodes=1, sha256="current") for p in paths]
    rows.append(dict(path="docs/old.md", kind="document", nodes=2, sha256="new"))
    (terrain.ROOT / "docs/architecture-knowledge.json").write_text(json.dumps({
        "source_fingerprints": {paths[2]: "current", "docs/old.md": "old"}}))
    edges = [dict(source=paths[0], target=paths[1], count=3),
             dict(source=paths[2], target=paths[3], count=7)]
    overview = terrain.overview(rows, edges)
    assert sum(g["files"] for g in overview["layers"]) == len(rows)
    assert [r["layer"] for r in rows] == ["browser", "client", "api", "services", "tests", "other", "docs"]
    assert sum(e["file_relations"] for e in overview["links"]) == len(edges)
    assert sum(e["symbol_relations"] for e in overview["links"]) == 10
    assert overview["semantic_files"] == 2
    assert overview["semantic_stale"] == ["docs/old.md"]
    assert overview["code_file_node_only"] == 6


def test_inventory_counts_templates_and_styles_as_source(terrain):
    for name in ["page.html", "theme.css", "migration.mako"]:
        (terrain.ROOT / name).write_text("source")
    rows = {r["path"]: r for r in terrain.inventory()}
    assert all(rows[p]["kind"] == "code" for p in ["page.html", "theme.css", "migration.mako"])
