"""Профиль публичного бота (ADR-0027). По умолчанию — показ без отправки.

    docker compose exec backend python scripts/public-bot-setup.py                 # показать
    docker compose exec backend python scripts/public-bot-setup.py --apply         # задать публичному боту
    docker compose exec backend python scripts/public-bot-setup.py --reset-admin   # снять публичное описание со служебного

Публичный бот — `RUSTATS_PUBLIC_BOT_TOKEN` (@ForecastEconomyBot, 08.11.2026); без него — служебный бот
(прежняя общая схема). Задаёт имя, описание до старта, короткое описание и команды личных чатов.
`--reset-admin` очищает описание и команды служебного бота (@forecast_bot_economy_bot), которые были
заданы ему, пока публичный режим жил в нём. Токены берутся из настроек и не печатаются.
"""
from __future__ import annotations

import asyncio
import json
import sys

sys.path.insert(0, ".")

from app.config import settings  # noqa: E402
from app.services.telegram_bot import _api  # noqa: E402

NAME = "Forecast Economy"
DESCRIPTION = (
    "Свежие цифры экономики России из официальных источников (Росстат, Банк России) и наш расчёт: "
    "бензин и дизель, инфляция, ключевая ставка, вклады, ипотека, золото, доллар.\n\n"
    "Спросите своими словами — «почему бензин дорожает?», «сколько я потерял на инфляции?» — "
    "отвечу по свежим цифрам и объясню, что они значат для кошелька. Пришлю график и сводку недели (/week). "
    "Скажите, что прислать, — пришлю. А ещё я самоулучшаюсь: чего не хватает — передам команде."
)
SHORT = "Свежие цифры экономики России из официальных источников: бензин, курс, инфляция, ставка."
COMMANDS = [
    {"command": "start", "description": "Начать и выбрать тему"},
    {"command": "menu", "description": "Темы: бензин, инфляция, ставка…"},
    {"command": "week", "description": "Сводка: что изменилось и что это значит"},
    {"command": "subs", "description": "Мои подписки на новые данные"},
    {"command": "help", "description": "Что я умею"},
    {"command": "stop", "description": "Удалить мои данные и подписки"},
]
PRIVATE = {"type": "all_private_chats"}


def public_calls() -> list[tuple[str, dict]]:
    return [
        ("setMyName", {"name": NAME}),
        ("setMyDescription", {"description": DESCRIPTION}),
        ("setMyShortDescription", {"short_description": SHORT}),
        ("setMyCommands", {"commands": COMMANDS, "scope": PRIVATE}),
    ]


def admin_reset_calls() -> list[tuple[str, dict]]:
    return [
        ("setMyDescription", {"description": ""}),
        ("setMyShortDescription", {"short_description": ""}),
        ("deleteMyCommands", {"scope": PRIVATE}),
    ]


async def run(calls: list[tuple[str, dict]], token: str, apply: bool) -> int:
    for method, payload in calls:
        print(method, json.dumps(payload, ensure_ascii=False))
        if apply:
            res = await _api(method, payload, token=token)
            print("  →", "ok" if res else "ошибка (см. журнал)")
            if not res:
                return 1
    return 0


async def main(argv: list[str]) -> int:
    if "--reset-admin" in argv:
        if not settings.public_bot_token:
            print("Публичный бот не отделён (нет RUSTATS_PUBLIC_BOT_TOKEN) — служебный не трогаю.")
            return 1
        return await run(admin_reset_calls(), settings.telegram_bot_token, apply=True)
    apply = "--apply" in argv
    code = await run(public_calls(), settings.public_bot_token or settings.telegram_bot_token, apply)
    if not apply:
        print("\nПоказ без отправки. Для применения: --apply")
    return code


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main(sys.argv[1:])))
