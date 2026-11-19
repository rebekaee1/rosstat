"""Привлечение (совет 19.11.2026): публичные флаги строки «присылать» и «первого экрана».

GET /api/v1/site-acq/config отдаёт фронту, что показывать на странице показателя:
- `line` — строка «Присылать в Telegram» (ссылка в публичного бота `?start=site_<тема>`);
- `topics` — темы бота, на которых строка разрешена (топливо добавляется, когда загрузка свежая);
- `bot` — имя публичного бота для ссылки (не секрет: оно в адресе t.me);
- `first_screen` — «Следующее обновление — {дата}» и «Скачать таблицу за все годы» на первом экране.

Строка не обещает подписку, если бот выключен: `line` = флаг строки И флаг публичного бота.
"""
from __future__ import annotations

from fastapi import APIRouter, Response

from app.config import settings
from app.services.public_bot import TOPICS

router = APIRouter(prefix="/site-acq", tags=["site-acq"])


def line_topics(raw: str | None = None) -> list[str]:
    """Темы из настройки: только известные боту, без повторов, в порядке настройки."""
    out: list[str] = []
    for part in (settings.acq_site_line_topics if raw is None else raw).split(","):
        key = part.strip().lower()
        if key in TOPICS and key not in out:
            out.append(key)
    return out


@router.get("/config")
async def site_acq_config(response: Response):
    response.headers["Cache-Control"] = "no-store"
    line = bool(settings.acq_site_line_enabled and settings.public_bot_enabled and settings.public_bot_username)
    return {
        "line": line,
        "topics": line_topics() if line else [],
        "bot": settings.public_bot_username if line else "",
        "first_screen": bool(settings.acq_site_first_screen_enabled),
    }
