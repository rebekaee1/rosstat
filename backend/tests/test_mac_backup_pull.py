"""scripts/mac/fe-backup-pull.sh: resume, no-op when fresh, quiet unless the copy is stale.

The script is for the owner's Mac (BSD stat/date), so it is skipped elsewhere. ssh,
rsync, pg_restore, osascript and caffeinate are replaced by stubs; nothing touches
the network or the real ~/Backups.
"""
import gzip
import hashlib
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "darwin", reason="BSD stat/date: macOS-only script")

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "mac" / "fe-backup-pull.sh"
PAYLOAD = b"x" * 5000
IDENT = gzip.compress(b"identity")


def _expected_date() -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=4, minutes=10)).strftime("%Y%m%d")


def _stub(path: Path, body: str) -> None:
    path.write_text("#!/bin/bash\n" + body)
    path.chmod(0o755)


@pytest.fixture
def env(tmp_path):
    bin_dir, dest, remote = tmp_path / "bin", tmp_path / "dest", tmp_path / "remote"
    for d in (bin_dir, dest, remote):
        d.mkdir()
    base = f"rustats_{_expected_date()}_040001"
    (remote / f"{base}.dump").write_bytes(PAYLOAD)
    (remote / f"{base}.identity.sql.gz").write_bytes(IDENT)
    calls = tmp_path / "calls.log"
    # ssh: last arg is the remote command. find -> base name; checksums -> stat/sha lines.
    sums = "".join(
        f"echo '{len(data)} {name}'; "
        for name, data in ((f"{base}.dump", PAYLOAD), (f"{base}.identity.sql.gz", IDENT))
    ) + "".join(
        f"echo '{hashlib.sha256(data).hexdigest()}  {name}'; "
        for name, data in ((f"{base}.dump", PAYLOAD), (f"{base}.identity.sql.gz", IDENT))
    )
    _stub(bin_dir / "ssh", f"""
echo "ssh $*" >> "{calls}"
[ -f "{tmp_path}/ssh_down" ] && exit 255
cmd="${{@: -1}}"
case "$cmd" in
  *sha256sum*) {sums} ;;
  *"find ."*) echo {base} ;;
esac
""")
    # rsync: first FAILS run leaves half a file (like a dropped link), then copies.
    _stub(bin_dir / "rsync", f"""
echo "rsync $*" >> "{calls}"
src="${{@: -2:1}}"; dst="${{@: -1}}"; name="$(basename "${{src#*:}}")"
n=$(cat "{tmp_path}/fail_left" 2>/dev/null || echo 0)
if [ "$n" -gt 0 ] && [ "$name" = "{base}.dump" ]; then
  echo $((n-1)) > "{tmp_path}/fail_left"
  head -c 2000 "{remote}/$name" > "$dst"
  exit 12
fi
cp "{remote}/$name" "$dst"
""")
    _stub(bin_dir / "pg_restore", 'echo "; header"; echo "1; 1 TABLE DATA public t u"; echo "2; 2 TABLE DATA public v u"\n')
    _stub(bin_dir / "osascript", f'echo "osascript $*" >> "{calls}"\n')
    _stub(bin_dir / "caffeinate", f'echo "caffeinate $*" >> "{calls}"\n')
    environment = dict(
        os.environ, FE_PATH_PREPEND=str(bin_dir), FE_BACKUP_DEST=str(dest), FE_HOST="stub-host",
        FE_REMOTE_DIR=str(remote), FE_RETRY_SLEEP="0", FE_RSYNC_TRIES="4", FE_SSH_TRIES="2",
    )
    return {"env": environment, "dest": dest, "calls": calls, "base": base, "tmp": tmp_path, "remote": remote}


def _run(env):
    return subprocess.run(["bash", str(SCRIPT)], env=env["env"], capture_output=True, text=True, timeout=60)


def _calls(env):
    return env["calls"].read_text().splitlines() if env["calls"].exists() else []


def test_today_verified_means_no_ssh(env):
    (env["dest"] / f"{env['base']}.verified").write_text("ok")
    assert _run(env).returncode == 0
    assert not any(c.startswith("ssh ") for c in _calls(env))


def test_resumes_after_dropped_connection_and_cleans_old_partials(env):
    (env["tmp"] / "fail_left").write_text("2")
    stale = env["dest"] / "rustats_20200101_040001.dump.part"
    stale.write_bytes(b"old")
    result = _run(env)
    assert result.returncode == 0, (result.stdout, result.stderr, (env["dest"] / "pull.log").read_text())
    dest, base = env["dest"], env["base"]
    assert (dest / f"{base}.dump").read_bytes() == PAYLOAD
    assert (dest / f"{base}.verified").exists()
    assert not stale.exists()
    assert not list(dest.glob("*.part"))
    assert len([c for c in _calls(env) if c.startswith("rsync ") and f"{base}.dump" in c]) == 3
    assert any(c.startswith("caffeinate -i") for c in _calls(env))
    assert "interrupted" in (dest / "pull.log").read_text()


def test_ssh_failure_is_quiet_while_copy_is_fresh_and_loud_once_when_stale(env):
    (env["tmp"] / "ssh_down").write_text("")
    fresh = env["dest"] / "rustats_20200101_040001.verified"
    fresh.write_text("ok")
    assert _run(env).returncode == 1
    assert not any(c.startswith("osascript") for c in _calls(env))
    old = time.time() - 50 * 3600
    os.utime(fresh, (old, old))
    assert _run(env).returncode == 1
    assert len([c for c in _calls(env) if c.startswith("osascript")]) == 1
    assert _run(env).returncode == 1  # within NOTIFY_EVERY_HOURS: no second banner
    assert len([c for c in _calls(env) if c.startswith("osascript")]) == 1


def test_checksum_mismatch_drops_partial(env):
    base = env["base"]
    env["remote"].joinpath(f"{base}.dump").write_bytes(b"y" * 5000)
    result = _run(env)
    assert result.returncode == 1
    assert not (env["dest"] / f"{base}.dump.part").exists()
    assert not (env["dest"] / f"{base}.verified").exists()
