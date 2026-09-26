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

    def test_rollback_snapshots_logs_then_invalidates_ssr_after_old_images_up(self):
        result = self.run_shell('''
PREV_SHA=prev
NEW_SHA=new
DEPLOY_LOG_DIR="$PWD"
PREV_BACKEND_IMAGE=sha256:old-backend
PREV_FRONTEND_IMAGE=sha256:old-frontend
ASSET_WORK="$PWD"
ASSET_ARCHIVE="$PWD/archive"
git() { printf 'git %s\\n' "$*"; }
docker() { printf 'docker %s\\n' "$*"; }
publish_frontend_assets() { printf 'publish %s\\n' "$*"; }
python3() { printf 'python %s\\n' "$*"; }
stop_backend_log() { printf 'stop-log\\n'; }
invalidate_release_cache() { printf 'invalidate\\n'; return 1; }
''' + ROLLBACK + '\nrollback\n')
        self.assertEqual(result.returncode, 1, result.stderr)
        out = result.stdout
        up = out.index('docker compose up -d frontend backend')
        self.assertLess(out.index('stop-log'), up)
        self.assertLess(up, out.index('invalidate'))
        # Провал инвалидации не прерывает откат.
        self.assertIn('WARN: не удалось инвалидировать', out)
        self.assertIn('publish sha256:old-frontend', out)

    def test_release_cache_is_targeted_scan_unlink_not_flushdb(self):
        self.assertNotIn('FLUSHDB', SCRIPT.replace('вместо FLUSHDB', '').replace('FLUSHDB обнулял', ''))
        fn = SCRIPT.split('invalidate_release_cache() {', 1)[1].split('\n}\n', 1)[0]
        self.assertIn('--scan --pattern', fn)
        self.assertIn('UNLINK', fn)
        self.assertNotIn(' KEYS ', fn)
        self.assertIn('fe:*:ssr:*', fn)
        self.assertIn('set -f', fn)
        self.assertIn('fe:ver:*', fn)  # guarded as unsafe

    def test_backend_log_follower_starts_after_up_and_stops_after_watch(self):
        up = SCRIPT.index('docker compose up -d\n', SCRIPT.index('# ── 4. Up'))
        self.assertLess(up, SCRIPT.index('start_backend_log\n', up))
        self.assertLess(SCRIPT.index('echo "    watch ok"'), SCRIPT.index('stop_backend_log\n', SCRIPT.index('echo "    watch ok"')))
        self.assertIn('home[${HOME_DIAG}] ready[${READY_DIAG}]', SCRIPT)

    ROLLBACK_FAKES = '''
PREV_SHA=prev
NEW_SHA=new
DEPLOY_LOG_DIR="$PWD"
PREV_BACKEND_IMAGE=sha256:old-backend
PREV_FRONTEND_IMAGE=sha256:old-frontend
ASSET_WORK="$PWD"
ASSET_ARCHIVE="$PWD/archive"
git() { printf 'git %s\\n' "$*"; }
docker() {
  if [ "$*" = "compose ps -aq scheduler" ]; then printf 'sched-cid\\n'; return; fi
  printf 'docker %s\\n' "$*"
}
publish_frontend_assets() { printf 'publish %s\\n' "$*"; }
python3() { printf 'python %s\\n' "$*"; }
stop_backend_log() { printf 'stop-log\\n'; }
invalidate_release_cache() { printf 'invalidate\\n'; }
backend_services() { printf 'backend scheduler'; }
'''

    def test_rollback_to_pre_split_release_removes_orphan_scheduler_first(self):
        # Старый compose без сервиса scheduler: backend старого образа сам
        # запускает планировщик — осиротевший scheduler убрать до `up`.
        result = self.run_shell(self.ROLLBACK_FAKES + '''
has_scheduler_service() { return 1; }
''' + ROLLBACK + '\nrollback\n')
        self.assertEqual(result.returncode, 1, result.stderr)
        out = result.stdout
        up = out.index('docker compose up -d frontend backend\n')
        self.assertLess(out.index('docker rm -f sched-cid'), up)
        self.assertNotIn('up -d frontend backend scheduler', out)
        # Логи (включая scheduler) снимаются до git reset на старый compose.
        self.assertLess(ROLLBACK.index('docker compose logs --no-color --timestamps $(backend_services)'),
                        ROLLBACK.index('git reset --hard'))

    def test_rollback_to_split_release_recreates_scheduler(self):
        result = self.run_shell(self.ROLLBACK_FAKES + '''
has_scheduler_service() { return 0; }
''' + ROLLBACK + '\nrollback\n')
        self.assertEqual(result.returncode, 1, result.stderr)
        out = result.stdout
        self.assertIn('docker compose up -d frontend backend scheduler', out)
        self.assertNotIn('docker rm -f', out)
        self.assertLess(out.index('docker tag sha256:old-backend rosstat-backend'),
                        out.index('docker compose up -d frontend backend scheduler'))

    def test_scheduler_is_waited_logged_and_watched(self):
        start = SCRIPT.split('start_backend_log() {', 1)[1].split('\n}\n', 1)[0]
        self.assertIn('$(backend_services)', start)
        up = SCRIPT.index('docker compose up -d\n', SCRIPT.index('# ── 4. Up'))
        wait = SCRIPT.index('waiting for scheduler healthy', up)
        self.assertLess(SCRIPT.index('FAIL: backend не стал ready'), wait)
        self.assertLess(wait, SCRIPT.index('==> smoke: data endpoint'))
        self.assertIn('if [ "${SOOM}" = "true" ]; then WATCH_FAIL=1; fi', SCRIPT)
        # pipefail-safe detection (no `| grep -q` on compose output).
        self.assertNotIn('--services | grep', SCRIPT)
        self.assertNotIn('--services 2>/dev/null | grep', SCRIPT)


if __name__ == '__main__':
    unittest.main()
