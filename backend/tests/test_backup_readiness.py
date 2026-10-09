"""Backup freshness must survive cache eviction/FLUSHDB and rolling upgrades."""
import asyncio
import json
import os
from pathlib import Path
import subprocess
import time
from datetime import datetime, timezone

import pytest
from fastapi import Response

from app.api import system


@pytest.mark.parametrize(
    "state_age,cache_age,expected,degraded",
    [(2, None, "2.0", False), (None, 3, "3.0", False),
     (40, 1, "40.0", True), (None, None, "never", False)],
)
def test_backup_state_precedence_and_legacy_fallback(monkeypatch, state_age, cache_age, expected, degraded):
    stamp = time.time()
    class Redis:
        def __init__(self, age):
            self.age = age
        async def ping(self):
            return True
        async def get(self, key):
            assert key == "fe:ops:pg_backup_last_ok"
            return None if self.age is None else str(stamp - self.age * 3600)
    class DB:
        async def execute(self, query):
            return None
        async def scalar(self, query):
            return datetime.now(timezone.utc).replace(tzinfo=None)
    async def cache():
        return Redis(cache_age)
    async def state():
        return Redis(state_age)
    monkeypatch.setattr(system, "get_redis", cache)
    monkeypatch.setattr(system, "get_state_redis", state)
    monkeypatch.setattr(system.settings, "scheduler_enabled", False)
    result = asyncio.run(system.health_ready(Response(), DB()))
    assert result["checks"]["pg_backup_age_hours"] == expected
    assert result["degraded"] is degraded


@pytest.mark.parametrize("proxy", ["", "http://test-user:test-pass@relay.example:8888"])
def test_backup_notification_uses_telegram_route_without_cli_credentials(tmp_path, proxy):
    """Run the real backup shell with owned dump/HTTP stubs; inspect its route."""
    scripts = tmp_path / "bin"
    scripts.mkdir()
    docker = scripts / "docker"
    docker.write_text("#!/bin/sh\nprintf mock-dump\n")
    docker.chmod(0o755)
    curl = scripts / "curl"
    curl.write_text(
        "#!/usr/bin/env python3\nimport json,os,sys\n"
        "open(os.environ['ROUTE_CAPTURE'],'w').write(json.dumps("
        "{'args':sys.argv[1:],'config':sys.stdin.read()}))\n"
    )
    curl.chmod(0o755)
    (tmp_path / ".env").write_text(
        "RUSTATS_TELEGRAM_BOT_TOKEN=test-token\nRUSTATS_TELEGRAM_CHAT_ID=111\n"
        f"RUSTATS_TELEGRAM_PROXY_URL='{proxy}'\n"
    )
    env = dict(os.environ, PATH=str(scripts) + os.pathsep + os.environ["PATH"],
               COMPOSE_DIR=str(tmp_path), BACKUP_DIR=str(tmp_path / "backups"),
               ROUTE_CAPTURE=str(tmp_path / "route.json"), OFFSITE_S3_BUCKET="")
    for key in ("RUSTATS_TELEGRAM_BOT_TOKEN", "RUSTATS_TELEGRAM_CHAT_ID", "RUSTATS_TELEGRAM_PROXY_URL"):
        env.pop(key, None)
    script = Path(__file__).resolve().parents[2] / "scripts" / "pg-backup.sh"
    result = subprocess.run(["bash", str(script)], env=env, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    captured = json.loads((tmp_path / "route.json").read_text())
    assert "--config" in captured["args"]
    assert captured["config"] == (f'proxy = "{proxy}"\n' if proxy else "")
    assert "test-pass" not in " ".join(captured["args"])
    assert "test-pass" not in result.stdout + result.stderr
    assert len(list((tmp_path / "backups").glob("*"))) == 2
