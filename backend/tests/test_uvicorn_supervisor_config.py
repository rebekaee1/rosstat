"""S2 (круг 13): настройка таймаута ping воркера у супервизора uvicorn.

Супервизор uvicorn (`--workers > 1`) шлёт воркеру ping и убивает его SIGKILL, если pong не пришёл за `--timeout-worker-healthcheck`
секунд. До 0.37 параметра не было (5 с зашито), на боевом это убивало воркеры под нагрузкой вместе с запросами в полёте.
Тест держит три связи: версия uvicorn с параметром, проброс настройки в compose, запуск в entrypoint (пусто = прежний запуск).
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _requirement_version(name: str) -> tuple[int, ...]:
    text = (ROOT / "backend" / "requirements.txt").read_text(encoding="utf8")
    match = re.search(rf"^{re.escape(name)}(?:\[[^\]]*\])?==([0-9.]+)\s*$", text, re.MULTILINE)
    assert match, f"{name} не закреплён в backend/requirements.txt"
    return tuple(int(part) for part in match.group(1).split("."))


def test_uvicorn_version_has_worker_healthcheck_option():
    # --timeout-worker-healthcheck появился в 0.37.0
    assert _requirement_version("uvicorn") >= (0, 37, 0)


def test_entrypoint_passes_healthcheck_timeout_only_when_set():
    script = (ROOT / "backend" / "entrypoint.sh").read_text(encoding="utf8")
    assert "UVICORN_WORKER_HEALTHCHECK_TIMEOUT" in script
    assert "--timeout-worker-healthcheck" in script
    # пустое значение не добавляет аргумент: запуск остаётся прежним
    assert 'if [ -n "${UVICORN_WORKER_HEALTHCHECK_TIMEOUT:-}" ]' in script
    # аргумент стоит в последней команде запуска web-процесса
    last_exec = [line for line in script.splitlines() if line.startswith("exec uvicorn")][-1]
    assert "$HC_ARGS" in last_exec
    assert "--workers ${UVICORN_WORKERS:-1}" in last_exec


def test_compose_and_env_example_expose_the_setting_off_by_default():
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf8")
    assert "UVICORN_WORKER_HEALTHCHECK_TIMEOUT: ${UVICORN_WORKER_HEALTHCHECK_TIMEOUT:-}" in compose
    example = (ROOT / ".env.example").read_text(encoding="utf8")
    # в примере строка закомментирована: по умолчанию поведение прежнее (5 с)
    assert re.search(r"^# UVICORN_WORKER_HEALTHCHECK_TIMEOUT=30$", example, re.MULTILINE)
    assert not re.search(r"^UVICORN_WORKER_HEALTHCHECK_TIMEOUT=", example, re.MULTILINE)
