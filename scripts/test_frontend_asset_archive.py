import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("archive", Path(__file__).with_name("frontend-asset-archive.py"))
archive_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(archive_module)


class AssetArchiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.archive = self.root / "archive"
        (self.archive / "assets").mkdir(parents=True)
        (self.archive / "releases").mkdir()

    def build(self, label):
        dist = self.root / label
        (dist / "assets").mkdir(parents=True)
        (dist / "index.html").write_text(label)
        for name, body in {
            f"lazy-{label:0>8}.js": label,
            "shared-01234567.css": "shared",
            "behavior-standalone.js": "fixed",
            "lazy-01234567.js.map": "private map",
        }.items():
            (dist / "assets" / name).write_text(body)
        return dist

    def test_three_releases_and_shared_assets_retained(self):
        for label in ("a", "b", "c", "d"):
            archive_module.publish(self.build(label), self.archive)
        self.assertTrue((self.archive / "assets/lazy-0000000a.js").exists())
        archive_module.prune(self.archive, 3)
        self.assertFalse((self.archive / "assets/lazy-0000000a.js").exists())
        for label in ("b", "c", "d"):
            self.assertTrue((self.archive / f"assets/lazy-{label:0>8}.js").exists())
        self.assertTrue((self.archive / "assets/shared-01234567.css").exists())
        self.assertFalse((self.archive / "assets/behavior-standalone.js").exists())
        self.assertFalse((self.archive / "assets/lazy-01234567.js.map").exists())
        self.assertEqual(len(list((self.archive / "releases").glob("*.json"))), 3)

    def test_immutable_collision_does_not_replace_existing_bytes(self):
        first = self.build("a")
        archive_module.publish(first, self.archive)
        (first / "assets/lazy-0000000a.js").write_text("different")
        with self.assertRaisesRegex(ValueError, "collision"):
            archive_module.publish(first, self.archive)
        self.assertEqual((self.archive / "assets/lazy-0000000a.js").read_text(), "a")

    def test_rollback_refreshes_release_and_prunes_orphans(self):
        builds = [self.build(label) for label in ("a", "b", "c", "d")]
        for dist in builds:
            archive_module.publish(dist, self.archive)
        archive_module.publish(builds[0], self.archive)
        (self.archive / "assets/orphan-01234567.js").write_text("interrupted publication")
        archive_module.prune(self.archive, 3)
        self.assertTrue((self.archive / "assets/lazy-0000000a.js").exists())
        self.assertFalse((self.archive / "assets/lazy-0000000b.js").exists())
        self.assertFalse((self.archive / "assets/orphan-01234567.js").exists())
        for manifest in (self.archive / "releases").glob("*.json"):
            for name in json.loads(manifest.read_text()):
                self.assertTrue((self.archive / "assets" / name).exists())


if __name__ == "__main__":
    unittest.main()
