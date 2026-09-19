"""Exercise deploy functions with fake Docker/Git; never contact production."""
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).with_name("deploy.sh").read_text()
PUBLISH = SCRIPT.split("publish_frontend_assets() {", 1)[1].split("\n# Complete old+new", 1)[0]
PUBLISH = "publish_frontend_assets() {" + PUBLISH
ROLLBACK = SCRIPT.split("rollback() {", 1)[1].split("\n# ERR catches", 1)[0]
ROLLBACK = "rollback() {" + ROLLBACK


class DeployAssetFlowTests(unittest.TestCase):
    def run_shell(self, body):
        with tempfile.TemporaryDirectory() as temp:
            return subprocess.run(["bash", "-euc", body], cwd=temp, capture_output=True, text=True)

    def test_copy_failure_removes_temporary_container_without_publication(self):
        result = self.run_shell('''
ASSET_WORK="$PWD/work"
ASSET_ARCHIVE="$PWD/archive"
mkdir "$ASSET_WORK"
docker() {
  case "$1" in
    create) printf 'temporary-container';;
    cp) return 1;;
    rm) printf 'removed' > removed;;
  esac
}
python3() { printf 'unexpected publish' > published; }
''' + PUBLISH + '''
if publish_frontend_assets image; then exit 10; fi
[ -f removed ]
[ ! -f published ]
[ ! -d "$ASSET_WORK/html" ]
''')
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_rollback_uses_running_image_ids_even_for_same_sha_rebuild(self):
        result = self.run_shell('''
PREV_SHA=same-sha
PREV_BACKEND_IMAGE=sha256:old-backend
PREV_FRONTEND_IMAGE=sha256:old-frontend
ASSET_WORK="$PWD"
ASSET_ARCHIVE="$PWD/archive"
git() { printf 'git %s\\n' "$*"; }
docker() { printf 'docker %s\\n' "$*"; }
publish_frontend_assets() { printf 'publish %s\\n' "$*"; }
python3() { printf 'python %s\\n' "$*"; }
''' + ROLLBACK + '\nrollback\n')
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn('docker tag sha256:old-backend rosstat-backend', result.stdout)
        self.assertIn('docker tag sha256:old-frontend rosstat-frontend', result.stdout)
        self.assertLess(result.stdout.index('publish sha256:old-frontend'), result.stdout.index(' prune '))
        self.assertNotIn('down', result.stdout)

    def test_publish_before_up_prune_after_acceptance(self):
        start = SCRIPT.index('# ── 3. Build')
        publish = SCRIPT.index('PREV_ASSET_RELEASE=$(publish_frontend_assets', start)
        up = SCRIPT.index('docker compose up -d\n', SCRIPT.index('# ── 4. Up'))
        prune = SCRIPT.index('echo "==> assets: retain')
        self.assertLess(publish, up)
        self.assertLess(SCRIPT.index('echo "    watch ok"'), prune)
        self.assertIn('flock -n 9', SCRIPT)
        self.assertIn('cmp -s "${ASSET_WORK}/retained-probe"', SCRIPT)


if __name__ == '__main__':
    unittest.main()
