"""scripts/pg-backup.sh, offsite step: failure is visible, never a green heartbeat, never blocks deploy.

docker/curl/aws are stubs; the real script runs against a temp backup dir.
"""
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "pg-backup.sh"


def _stub(path: Path, body: str) -> None:
    path.write_text("#!/bin/bash\n" + body)
    path.chmod(0o755)


def _run(tmp_path, aws_body=None, bucket="s3://bucket/pg"):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    sent = tmp_path / "telegram.txt"
    _stub(bin_dir / "docker", "printf 'mock-dump'\n")
    _stub(bin_dir / "curl", f'cat >/dev/null; for a in "$@"; do case "$a" in text=*) echo "$a" >> "{sent}";; esac; done\n')
    if aws_body is not None:
        _stub(bin_dir / "aws", aws_body)
    env = {
        # /usr/bin:/bin only: no host aws can leak into the "aws is missing" case.
        "PATH": f"{bin_dir}:/usr/bin:/bin",
        "HOME": str(tmp_path),
        "COMPOSE_DIR": str(tmp_path),
        "BACKUP_DIR": str(tmp_path / "backups"),
        "RUSTATS_TELEGRAM_BOT_TOKEN": "t",
        "RUSTATS_TELEGRAM_CHAT_ID": "1",
        "OFFSITE_S3_BUCKET": bucket,
        "OFFSITE_S3_ENDPOINT": "https://s3.example",
    }
    result = subprocess.run(["bash", str(SCRIPT)], env=env, capture_output=True, text=True, timeout=30)
    texts = sent.read_text().splitlines() if sent.exists() else []
    return result, texts


# `aws s3 ls` prints "date time size name"; size is the third field.
def _aws_with_size(size_expr):
    return (
        'echo "aws $*" >> "$(dirname "$0")/aws.log"\n'
        'case "$2" in\n'
        '  cp) exit 0 ;;\n'
        f'  ls) echo "2026-10-27 04:00:00 {size_expr} $(basename "$3")" ;;\n'
        'esac\n'
    )


def test_missing_aws_is_yellow_not_green_and_does_not_fail(tmp_path):
    result, texts = _run(tmp_path, aws_body=None)
    assert result.returncode == 0, result.stderr
    assert len(texts) == 1 and texts[0].startswith("text=🟡") and "НЕ выполнен" in texts[0]
    assert not any(t.startswith("text=🟢") for t in texts)
    assert len(list((tmp_path / "backups").glob("rustats_*"))) == 2  # local copies kept


def test_upload_failure_is_yellow_and_deploy_gate_stays_open(tmp_path):
    result, texts = _run(tmp_path, aws_body="exit 1\n")
    assert result.returncode == 0, result.stderr
    assert texts and texts[-1].startswith("text=🟡") and "НЕ выполнен" in texts[-1]


def test_size_mismatch_is_not_a_success(tmp_path):
    result, texts = _run(tmp_path, aws_body=_aws_with_size("1"))
    assert result.returncode == 0, result.stderr
    assert texts[-1].startswith("text=🟡")
    assert "size mismatch" in result.stderr


def test_verified_upload_is_green_and_mentions_offsite(tmp_path):
    # mock-dump is 9 bytes; the identity file is gzip of nothing (20 bytes), so answer per name.
    body = (
        'case "$2" in\n'
        '  cp) exit 0 ;;\n'
        '  ls) n="$(basename "$3")"; f="$BACKUP_DIR/$n"; echo "2026-10-27 04:00:00 $(wc -c < "$f" | tr -d " ") $n" ;;\n'
        'esac\n'
    )
    result, texts = _run(tmp_path, aws_body=body)
    assert result.returncode == 0, result.stderr
    assert texts[-1].startswith("text=🟢") and "offsite ok" in texts[-1]


def test_no_bucket_keeps_old_green_message(tmp_path):
    result, texts = _run(tmp_path, aws_body=None, bucket="")
    assert result.returncode == 0, result.stderr
    assert texts[-1].startswith("text=🟢") and "offsite" not in texts[-1]
