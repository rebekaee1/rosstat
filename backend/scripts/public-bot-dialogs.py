"""Выгрузка переписки публичного бота для анализа (решение владельца 09.11.2026).

    docker compose exec backend python scripts/public-bot-dialogs.py                     # сводка за 7 дней
    docker compose exec backend python scripts/public-bot-dialogs.py --days 30 --jsonl   # все события в JSON Lines
    docker compose exec backend python scripts/public-bot-dialogs.py --chat 123456789    # один диалог текстом

Источники: public_bot_dialog (входящие с профилем Telegram, запросы к модели и её ответы)
и telegram_outbox (что бот отправил: kind bot_reply / notify). Одна лента по времени на каждый чат.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone

sys.path.insert(0, ".")

from sqlalchemy import select  # noqa: E402

from app.database import async_session  # noqa: E402
from app.models import PublicBotChat, PublicBotDialog, TelegramOutbox  # noqa: E402
from app.services.public_bot import KIND_NOTIFY, KIND_REPLY  # noqa: E402


async def collect(days: int, chat: str | None) -> list[dict]:
    since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)
    async with async_session() as db:
        q = select(PublicBotDialog).where(PublicBotDialog.occurred_at >= since)
        if chat:
            q = q.where(PublicBotDialog.chat_id == chat)
        rows = (await db.execute(q)).scalars().all()
        chats = {r.chat_id for r in rows if r.chat_id}
        chats |= set((await db.execute(select(PublicBotChat.chat_id))).scalars().all()) if not chat else {chat}
        oq = select(TelegramOutbox).where(TelegramOutbox.sent_at >= since,
                                          TelegramOutbox.kind.in_((KIND_REPLY, KIND_NOTIFY)),
                                          TelegramOutbox.chat_id.in_(chats))
        out = (await db.execute(oq)).scalars().all()
    ev = [{"ts": r.occurred_at.isoformat(timespec="seconds"), "chat_id": r.chat_id, "who": r.direction, "kind": r.kind,
           "user_id": r.user_id, "username": r.username, "name": " ".join(x for x in (r.first_name, r.last_name) if x) or None,
           "lang": r.language_code, "text": r.text,
           **({"model": (r.payload or {}).get("model"), "status": (r.payload or {}).get("status"),
               "latency_ms": (r.payload or {}).get("latency_ms"), "usage": (r.payload or {}).get("usage"),
               "llm_messages": (r.payload or {}).get("messages")} if r.direction == "llm" else {})} for r in rows]
    ev += [{"ts": o.sent_at.isoformat(timespec="seconds"), "chat_id": o.chat_id, "who": "bot", "kind": o.kind,
            "text": o.text, "ok": o.ok} for o in out]
    return sorted(ev, key=lambda e: (e["chat_id"] or "", e["ts"]))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--chat")
    ap.add_argument("--jsonl", action="store_true", help="все события построчно в JSON")
    a = ap.parse_args()
    ev = asyncio.run(collect(a.days, a.chat))
    if a.jsonl:
        for e in ev:
            print(json.dumps(e, ensure_ascii=False, default=str))
        return
    if a.chat:
        for e in ev:
            who = {"in": f"👤 {e.get('name') or e.get('username') or e['chat_id']}", "bot": "🤖 бот", "llm": "🧠 модель"}[e["who"]]
            extra = f" [{e['model']}, {e['status']}, {e['latency_ms']} мс]" if e["who"] == "llm" else ""
            print(f"{e['ts']} {who} ({e['kind']}){extra}\n{e['text'] or ''}\n")
        return
    people = {e["chat_id"] for e in ev if e["who"] == "in"}
    print(f"За {a.days} дн.: людей {len(people)}, входящих {sum(e['who'] == 'in' for e in ev)}, "
          f"ответов бота {sum(e['who'] == 'bot' for e in ev)}, запросов к модели {sum(e['who'] == 'llm' for e in ev)}")
    words = Counter((e["text"] or "").lower() for e in ev if e["who"] == "in" and e["kind"] == "message")
    print("Частые сообщения:", "; ".join(f"{w[:40]} ×{n}" for w, n in words.most_common(15)))


if __name__ == "__main__":
    main()
