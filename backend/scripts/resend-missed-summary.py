"""Досылка владельцу одной сводки «что не дошло до Telegram» (круг 13, задача T2).

По умолчанию — ПРОБНЫЙ ПРОГОН: читает архив `telegram_outbox`, печатает сводку и число
найденных событий, ничего не отправляет и ничего не пишет. Отправка — только с
`--no-dry-run` и только по слову владельца в чате.

Получатель — только владелец (`RUSTATS_TELEGRAM_CHAT_ID`). Параметр `--recipient`
принимает `owner` (по умолчанию) или тот же номер чата; любой другой номер отклоняется.
Прочим адресатам дайджеста ничего не уходит, прежние недоставленные сообщения по одному
не досылаются (в сводке нет имён, почт и телефонов).

От повторной отправки защищает проверка: если сводка за это окно уже доставлена
(`kind='missed_summary'`, `ok=true`), скрипт откажется, пока нет `--force`.

Запуск (на боевом, из контейнера backend):
    docker compose exec backend python scripts/resend-missed-summary.py
    docker compose exec backend python scripts/resend-missed-summary.py --since 2026-10-03 --until 2026-10-09
    docker compose exec backend python scripts/resend-missed-summary.py --no-dry-run     # только по слову владельца
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.config import settings  # noqa: E402
from app.database import analytics_session  # noqa: E402
from app.models import TelegramOutbox  # noqa: E402
from app.services.telegram_missed_summary import (  # noqa: E402
    MSK,
    SUMMARY_KIND,
    build_summary,
    find_missed,
    permanent_failures,
)
from app.services.telegram_resend import OutboxRow  # noqa: E402


def resolve_recipient(value: str) -> str:
    """`owner` или номер чата владельца; чужой номер — ошибка (досылка только владельцу)."""
    owner = str(settings.telegram_chat_id or "").strip()
    if not owner:
        raise SystemExit("RUSTATS_TELEGRAM_CHAT_ID не задан: получатель-владелец неизвестен.")
    if value.strip().lower() in ("owner", "владелец", owner):
        return owner
    raise SystemExit("Получатель может быть только владельцем (owner). Другие номера чатов не принимаются.")


def window_utc(since: date, until: date) -> tuple[datetime, datetime]:
    """МСК-сутки since..until включительно → границы UTC без пояса (как хранит архив)."""
    start = datetime(since.year, since.month, since.day, tzinfo=MSK).astimezone(timezone.utc)
    end = datetime(until.year, until.month, until.day, tzinfo=MSK).astimezone(timezone.utc) + timedelta(days=1)
    return start.replace(tzinfo=None), end.replace(tzinfo=None)


async def load_rows(start: datetime, end: datetime) -> list[OutboxRow]:
    """Строки архива окна. Файлы (sendDocument) не берём: сводка о тексте."""
    async with analytics_session() as db:
        result = await db.execute(
            select(TelegramOutbox.id, TelegramOutbox.sent_at, TelegramOutbox.chat_id, TelegramOutbox.kind,
                   TelegramOutbox.text, TelegramOutbox.ok, TelegramOutbox.error)
            .where(TelegramOutbox.sent_at >= start, TelegramOutbox.sent_at < end,
                   TelegramOutbox.method == "sendMessage")
            .order_by(TelegramOutbox.id)
        )
        return [OutboxRow(id=i, sent_at=at, chat_id=str(chat), kind=kind, text=text or "", ok=bool(ok), error=err)
                for i, at, chat, kind, text, ok, err in result.all()]


async def already_sent(start: datetime, end: datetime) -> bool:
    async with analytics_session() as db:
        found = await db.scalar(
            select(TelegramOutbox.id).where(TelegramOutbox.kind == SUMMARY_KIND, TelegramOutbox.ok.is_(True),
                                            TelegramOutbox.sent_at >= end).limit(1)
        )
    return found is not None


async def main(args: argparse.Namespace) -> int:
    recipient = resolve_recipient(args.recipient)
    since, until = date.fromisoformat(args.since), date.fromisoformat(args.until)
    start, end = window_utc(since, until)
    rows = await load_rows(start, end)
    missed = find_missed(rows)
    text = build_summary(missed, since=since, until=until)

    print(f"Окно: {since}..{until} по МСК, строк архива: {len(rows)}, недоставленных событий: {len(missed)}, "
          f"постоянных ошибок доставки (чат/бот): {permanent_failures(rows)}")
    print(f"Получатель: владелец (чат ...{recipient[-4:]}). Длина сводки: {len(text)} знаков.")
    print("-" * 60)
    print(text)
    print("-" * 60)

    if args.dry_run:
        print("Пробный прогон: ничего не отправлено и не записано. Для отправки нужен --no-dry-run "
              "и слово владельца в чате.")
        return 0
    if not missed:
        print("Недоставленного нет, отправлять нечего.")
        return 0
    if not args.force and await already_sent(start, end):
        print("Сводка за это окно уже была доставлена. Повтор — только с --force.")
        return 3

    from app.services.alerting import send_telegram

    ok = await send_telegram(text, chat_id=recipient, kind=SUMMARY_KIND)
    print("Отправлено." if ok else "Отправка не удалась (см. telegram_outbox, kind=missed_summary).")
    return 0 if ok else 1


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--since", default="2026-10-03", help="первый день окна (МСК), по умолчанию 2026-10-03")
    parser.add_argument("--until", default="2026-10-09", help="последний день окна (МСК), по умолчанию 2026-10-09")
    parser.add_argument("--recipient", default="owner", help="только owner (чат владельца)")
    parser.add_argument("--dry-run", action=argparse.BooleanOptionalAction, default=True,
                        help="по умолчанию включён; отправка — --no-dry-run")
    parser.add_argument("--force", action="store_true", help="отправить, даже если сводка уже была доставлена")
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main(parse_args())))
