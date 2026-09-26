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
PG_BLOCKER = SCRIPT.split("pg_restart_blocker() {", 1)[1].split("\n}\n", 1)[0]
PG_BLOCKER = "pg_restart_blocker() {" + PG_BLOCKER + "\n}\n"


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


    def test_rollback_restores_recreated_infra_before_old_app(self):
        # perf batch 3: postgres/redis, пересозданные деплоем, возвращаются к
        # прежнему compose-конфигу после git reset и до старта старого backend.
        result = self.run_shell(self.ROLLBACK_FAKES + '''
has_scheduler_service() { return 0; }
INFRA_RECREATE="postgres redis"
''' + ROLLBACK + '\nrollback\n')
        self.assertEqual(result.returncode, 1, result.stderr)
        out = result.stdout
        infra = out.index('docker compose up -d --wait postgres redis')
        self.assertLess(out.index('git reset --hard prev'), infra)
        self.assertLess(infra, out.index('docker compose up -d frontend backend scheduler'))

    def test_rollback_without_infra_change_does_not_touch_postgres(self):
        result = self.run_shell(self.ROLLBACK_FAKES + '''
has_scheduler_service() { return 0; }
INFRA_RECREATE=""
''' + ROLLBACK + '\nrollback\n')
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertNotIn('--wait', result.stdout)
        self.assertNotIn('postgres', result.stdout)

    def _blocker(self, now, locks='', allow='0'):
        fakes = (
            'DEPLOY_ALLOW_PG_RESTART=%s\n'
            'date() { if [ "$1" = "+%%H%%M" ]; then echo %s; else echo %s:%s; fi; }\n'
            'grep() { return 1; }\n'
            'docker() { case "$*" in *redis-state*) printf "%%s" "%s";; esac; }\n'
        ) % (allow, now, now[:2], now[2:], locks)
        return self.run_shell(fakes + PG_BLOCKER + '''
if reason=$(pg_restart_blocker); then echo "BLOCKED: $reason"; else echo FREE; fi
''')

    def test_pg_restart_blocked_during_etl_windows_and_live_job_locks(self):
        for now in ('0545', '0700', '1930', '2005', '2229'):
            r = self._blocker(now)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn('BLOCKED: окно ETL', r.stdout, now)
        for now in ('0100', '0730', '1500', '1929', '2230'):
            r = self._blocker(now)
            self.assertIn('FREE', r.stdout, now)
        r = self._blocker('1500', locks='sched:lock:daily_etl')
        self.assertIn('BLOCKED: идут фоновые джобы', r.stdout)
        self.assertIn('sched:lock:daily_etl', r.stdout)
        r = self._blocker('2005', locks='sched:lock:daily_etl', allow='1')
        self.assertIn('FREE', r.stdout)

    def test_pg_recreate_guard_before_build_checkpoint_before_up(self):
        guard = SCRIPT.index('if reason=$(pg_restart_blocker); then')
        build = SCRIPT.index('# ── 3. Build')
        self.assertLess(SCRIPT.index('INFRA_RECREATE=""'), guard)
        self.assertLess(guard, build)
        # Блок деплоя до сборки откатывает merge, как scope guard.
        self.assertIn('git reset --hard "${PREV_SHA}"', SCRIPT[guard:build])
        up = SCRIPT.index('docker compose up -d\n', SCRIPT.index('# ── 4. Up'))
        self.assertLess(SCRIPT.index("-qc 'CHECKPOINT'"), up)
        ext = SCRIPT.index('CREATE EXTENSION IF NOT EXISTS pg_stat_statements')
        self.assertLess(up, ext)
        self.assertLess(ext, SCRIPT.index('==> smoke: data endpoint'))

if __name__ == '__main__':
    unittest.main()
