"""Меню команд служебного бота (@forecast_bot_economy_bot) только в чате владельца (14.11.2026).

    docker compose exec backend python scripts/service-bot-commands.py           # показать, ничего не отправлять
    docker compose exec backend python scripts/service-bot-commands.py --apply   # задать
    docker compose exec backend python scripts/service-bot-commands.py --reset   # снять

Область — `BotCommandScopeChat` (чат владельца `RUSTATS_TELEGRAM_CHAT_ID` и, при включённой роли,
чаты «только отчёты»). Для остальных личных чатов меню не появляется. Используется только токен
служебного бота (`RUSTATS_TELEGRAM_BOT_TOKEN`); публичный бот (`RUSTATS_PUBLIC_BOT_TOKEN`) не трогается.
Токены не печатаются. Сообщений в чаты скрипт не отправляет.
"""
from __future__ import annotations

import asyncio
import json
import sys

sys.path.insert(0, ".")

from app.services.telegram_bot import _api, service_command_calls  # noqa: E402


async def main(argv: list[str]) -> int:
    apply_, reset = "--apply" in argv, "--reset" in argv
    calls = service_command_calls(reset=reset)
    if not calls:
        print("Нет чата владельца (RUSTATS_TELEGRAM_CHAT_ID) — делать нечего.")
        return 1
    for method, payload in calls:
        print(method, json.dumps(payload, ensure_ascii=False))
    if not (apply_ or reset):
        print("Показ без отправки. Задать: --apply, снять: --reset.")
        return 0
    failed = 0
    for method, payload in calls:
        data = await _api(method, payload)  # служебный токен по умолчанию
        print(method, "ok" if data and data.get("ok") else "FAILED")
        failed += not (data and data.get("ok"))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main(sys.argv[1:])))
