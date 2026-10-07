"""Страж: сетевой fetch парсера не выполняется синхронно в event loop.

07.10.2026 `RosstatIndParser` качал xlsx Росстата через синхронный requests
прямо в `async _fetch_and_parse`; Росстат не отвечал, ретраи шли час, и весь
AsyncIOScheduler стоял — утренние дайджест и Пульс ушли в misfire. Сетевые
вызовы обязаны идти через `asyncio.to_thread` (или async-клиент).
"""
from __future__ import annotations

import ast
from pathlib import Path

SERVICES = Path(__file__).resolve().parents[1] / "app" / "services"
BLOCKING_NAMES = {"create_session", "resolve_mediabank_file"}
BLOCKING_ATTRS = {"get", "post", "head", "request"}
BLOCKING_OWNERS = {"session", "requests"}


def _blocking_calls(fn: ast.AsyncFunctionDef) -> list[str]:
    found = []
    for node in ast.walk(fn):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        if isinstance(f, ast.Name) and (f.id in BLOCKING_NAMES or f.id.startswith("_fetch_")):
            found.append(f"{f.id}() line {node.lineno}")
        elif (
            isinstance(f, ast.Attribute)
            and f.attr in BLOCKING_ATTRS
            and isinstance(f.value, ast.Name)
            and f.value.id in BLOCKING_OWNERS
        ):
            found.append(f"{f.value.id}.{f.attr}() line {node.lineno}")
    return found




def test_parser_fetch_and_parse_does_not_block_event_loop():
    offenders = []
    for path in sorted(SERVICES.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef) and node.name == "_fetch_and_parse":
                calls = _blocking_calls(node)
                if calls:
                    offenders.append(f"{path.name}:{node.lineno}: {', '.join(calls)}")
    assert not offenders, (
        "Синхронный сетевой fetch в async _fetch_and_parse блокирует планировщик; "
        "оберни в asyncio.to_thread:\n" + "\n".join(offenders)
    )
