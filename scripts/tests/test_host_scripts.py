"""Проверки скриптов подготовки хоста прода (круг починки 27.10.2026).

Скрипты на хосте не запускаются: здесь — синтаксис bash, режим --dry-run с заглушками системных
команд и инварианты, нарушение которых отрезало бы доступ или сломало Tor-маршрут контейнеров.
"""
import os
import stat
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = [
    "scripts/host-firewall-ufw.sh",
    "scripts/host-tor-bridge-f10.sh",
    "scripts/host-zabbix-denykey.sh",
    "scripts/install-host-disk-hygiene.sh",
    "scripts/install-host-logrotate.sh",
    "scripts/docker-cleanup.sh",
]


def _stub_bin(tmp_path: Path, extra: dict[str, str] | None = None) -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    stubs = {
        "docker": (
            '#!/bin/bash\n'
            'if [[ "$1" == exec ]]; then exit 0; fi\n'
            'if [[ "$*" == *Subnet* ]]; then echo 172.18.0.0/16; '
            'elif [[ "$*" == *Gateway* ]]; then echo 172.18.0.1; else exit 1; fi\n'
        ),
        "ufw": '#!/bin/bash\necho "Status: inactive"\n',
        "sshd": '#!/bin/bash\necho "port 22"\n',
        "systemctl": '#!/bin/bash\nexit 0\n',
    }
    stubs.update(extra or {})
    for name, body in stubs.items():
        path = bin_dir / name
        path.write_text(body)
        path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return bin_dir


def _run(script: str, arg: str, bin_dir: Path, env_extra: dict[str, str] | None = None):
    env = {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}", **(env_extra or {})}
    return subprocess.run(["bash", str(ROOT / script), arg], capture_output=True, text=True, env=env, timeout=60)


def test_all_host_scripts_parse_and_are_executable():
    for rel in SCRIPTS:
        path = ROOT / rel
        assert path.exists(), rel
        assert os.access(path, os.X_OK), f"{rel} не исполняемый"
        assert subprocess.run(["bash", "-n", str(path)]).returncode == 0, rel


def test_firewall_dry_run_keeps_every_needed_port(tmp_path):
    result = _run("scripts/host-firewall-ufw.sh", "--dry-run", _stub_bin(tmp_path))
    out = result.stdout
    assert result.returncode == 0, result.stderr
    # публичные порты: ssh, Caddy http/https и HTTP/3 (udp)
    for rule in ("ufw allow 22/tcp", "ufw allow 80/tcp", "ufw allow 443/tcp", "ufw allow 443/udp"):
        assert rule in out, rule
    # zabbix — только с трёх адресов сервера мониторинга, не со всего мира
    for ip in ("92.53.116.12", "92.53.116.111", "92.53.116.119"):
        assert f"ufw allow from {ip} to any port 10050 proto tcp" in out
    assert "ufw allow 10050" not in out
    # контейнеры -> хост: Tor SOCKS ETL и резервный мост, только из сети compose
    assert "ufw allow from 172.18.0.0/16 to 172.18.0.1 port 9050 proto tcp" in out
    assert "ufw allow from 172.18.0.0/16 to 172.18.0.1 port 8888 proto tcp" in out
    # пересылку контейнеров ufw не режет; входящее закрыто по умолчанию; страховка есть
    assert "ufw default allow routed" in out
    assert "ufw default deny incoming" in out
    assert "systemd-run --unit=fe-ufw-failsafe" in out


def test_firewall_apply_refuses_without_root_and_unknown_mode(tmp_path):
    bin_dir = _stub_bin(tmp_path)
    if os.geteuid() != 0:
        assert _run("scripts/host-firewall-ufw.sh", "--apply", bin_dir).returncode == 1
    assert _run("scripts/host-firewall-ufw.sh", "--nonsense", bin_dir).returncode == 2


def test_firewall_stops_when_sshd_port_differs(tmp_path):
    # sshd на 2222, а правило открывает 22: включение ufw отрезало бы ssh — предпроверка обязана остановить
    bin_dir = _stub_bin(tmp_path, {"sshd": '#!/bin/bash\necho "port 2222"\n'})
    result = _run("scripts/host-firewall-ufw.sh", "--dry-run", bin_dir)
    assert result.returncode == 1
    assert "2222" in result.stderr


def test_zabbix_denykey_dry_run_lists_only_file_read_keys(tmp_path):
    conf = tmp_path / "zabbix_agentd.conf"
    conf.write_text("Server=92.53.116.12\nDenyKey=system.run[*]\n")
    result = _run("scripts/host-zabbix-denykey.sh", "--dry-run", _stub_bin(tmp_path),
                  {"ZABBIX_CONF": str(conf)})
    assert result.returncode == 0, result.stderr
    for key in ("vfs.file.contents[*]", "vfs.file.regexp[*]", "vfs.file.regmatch[*]"):
        assert f"DenyKey={key}" in result.stdout
    assert "DenyKey=vfs.file.*" not in result.stdout  # не режем vfs.file.exists/size без нужды
    assert conf.read_text() == "Server=92.53.116.12\nDenyKey=system.run[*]\n"  # dry-run ничего не пишет


def test_tor_bridge_dry_run_changes_nothing(tmp_path):
    env = {"REPO": str(ROOT), "DST_DIR": str(tmp_path / "opt"), "DST_UNIT": str(tmp_path / "unit"),
           "ENV_FILE": str(tmp_path / "bridge.env")}
    result = _run("scripts/host-tor-bridge-f10.sh", "--dry-run", _stub_bin(tmp_path, {
        "journalctl": '#!/bin/bash\necho ""\n'}), env)
    assert result.returncode == 0, result.stderr
    assert not (tmp_path / "bridge.env").exists()
    assert "openssl rand -hex 24" in result.stdout and "--purge-journal" in result.stdout


def test_nginx_logrotate_never_copies_big_log_and_compresses_at_idle_priority():
    text = (ROOT / "deploy/fail2ban/logrotate-rosstat-nginx").read_text()
    active = [line.strip() for line in text.splitlines() if line.strip() and not line.strip().startswith("#")]
    # copytruncate копирует ~360 МБ и держал I/O общего с Postgres диска — запрещён
    assert "copytruncate" not in active
    assert "delaycompress" in active and "compress" in active
    assert any(line.startswith("compresscmd /usr/bin/ionice") for line in active)
    assert any("-c3" in line and "nice -n19" in line for line in active if line.startswith("compressoptions"))
    assert "compressext .gz" in active
    assert "create 0644 101 101" in active  # nginx внутри контейнера пишет под uid 101
    assert any("USR1" in line and "rosstat-frontend-1" in line for line in active)


def test_docker_cleanup_prunes_all_unused_build_cache():
    text = (ROOT / "scripts/docker-cleanup.sh").read_text()
    assert "docker builder prune -a -f" in text  # без -a остаётся неиспользуемый кэш слоёв (16 ГБ на проде)
    assert "/var/lock/rosstat-deploy.lock" in text  # не мешать выкатке


def test_secret_mode_contract_matches_documented_owner():
    # Владельцем gsc-oauth.json должен быть uid контейнера, пока приложение требует режим 0600.
    source = (ROOT / "backend/app/services/gsc_client.py").read_text()
    assert "st_mode & 0o077" in source and "must have mode 0600" in source
