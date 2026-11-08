"""Команды и описание бота для публичного режима (ADR-0027). По умолчанию — показ без отправки.

    docker compose exec backend python scripts/public-bot-setup.py          # показать, что будет задано
    docker compose exec backend python scripts/public-bot-setup.py --apply  # задать через Bot API

Задаёт то, что человек видит до нажатия Start и в меню команд: setMyDescription, setMyShortDescription,
setMyCommands. Запускать при включении `RUSTATS_PUBLIC_BOT_ENABLED`, не раньше: описание видят все,
кто открывает бота, включая владельца. Токен берётся из настроек и не печатается.
"""
from __future__ import annotations

import asyncio
import json
import sys

sys.path.insert(0, ".")

from app.services.telegram_bot import _api  # noqa: E402

DESCRIPTION = (
    "Свежие цифры экономики России из официальных источников и наш прогноз: бензин и дизель, "
    "инфляция, ключевая ставка, вклады, ипотека, золото, доллар. Напишите слово — например, ДИЗЕЛЬ — "
    "и я пришлю цифру, а если хотите, напомню, когда выйдут новые данные."
)
SHORT = "Цифры экономики России и прогноз: бензин, инфляция, ставка, золото, доллар."
COMMANDS = [
    {"command": "start", "description": "Начать и выбрать тему"},
    {"command": "menu", "description": "Темы: бензин, инфляция, ставка…"},
    {"command": "stop", "description": "Удалить мои данные и подписки"},
]
CALLS = [
    ("setMyDescription", {"description": DESCRIPTION}),
    ("setMyShortDescription", {"short_description": SHORT}),
    # Только для личных чатов: в группах и у админ-меню команды не меняются.
    ("setMyCommands", {"commands": COMMANDS, "scope": {"type": "all_private_chats"}}),
]


async def main(apply: bool) -> int:
    for method, payload in CALLS:
        print(method, json.dumps(payload, ensure_ascii=False))
        if apply:
            res = await _api(method, payload)
            print("  →", "ok" if res else "ошибка (см. журнал)")
            if not res:
                return 1
    if not apply:
        print("\nПоказ без отправки. Для применения: --apply")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main("--apply" in sys.argv)))
