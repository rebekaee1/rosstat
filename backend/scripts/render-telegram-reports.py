"""Показать тексты отчётов Telegram на данных базы, НИЧЕГО НЕ ОТПРАВЛЯЯ (круг 13, T1).

Для шага «посмотреть до включения»: дайджест (с блоками v2), недельный и месячный отчёты,
ответы кнопок «Регистрации», «Воронка», «Цели» и пороги новых алертов печатаются в терминал.
Отправка Telegram в процессе заблокирована (вызов `send_telegram` падает), токен не нужен.
Читаются только витрины и архив, база не меняется.

Имена, почты и телефоны новых пользователей в старом блоке дайджеста по умолчанию скрыты
(`--show-personal` отключает маску: только для себя, в терминал).

Запуск (боевой, из контейнера backend; тяжёлые витрины читают базу до 2 минут на отчёт):
    docker compose exec backend python scripts/render-telegram-reports.py --what weekly
    docker compose exec backend python scripts/render-telegram-reports.py --what all --date 2026-10-12
"""
from __future__ import annotations

import argparse
import asyncio
import re
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings  # noqa: E402

TELEGRAM_LIMIT = 4096
_BULLET_RE = re.compile(r"^• .*$", re.MULTILINE)


def mask_personal(text: str) -> str:
    """Строки «• Имя — почта (способ)» старого блока дайджеста → без имени и почты."""
    from app.services.pii_scrub import scrub_text

    def _bullet(match: re.Match) -> str:
        line = match.group(0)
        method = line[line.rfind("("):] if "(" in line else ""
        return ("• [имя скрыто] — [контакт скрыт] " + method).rstrip()

    return scrub_text(_BULLET_RE.sub(_bullet, text))


def describe(title: str, text: str, seconds: float) -> None:
    from app.services.telegram_text import split_telegram_text

    parts = split_telegram_text(text)
    blank = sum(1 for line in text.split("\n") if not line.strip())
    print("=" * 78)
    print(f"{title}: {len(text)} знаков, частей для Telegram: {len(parts)} "
          f"(макс. {max(len(p) for p in parts)}), пустых строк: {blank}, расчёт {seconds:.1f} с")
    print("=" * 78)
    print(text)
    print()


async def render_digest(day_today: date, show_personal: bool, with_metrika: bool, v2: bool) -> None:
    from app.services import alerting
    from app.tasks import analytics_scheduler as sched

    captured: list[str] = []

    async def fake_digest(message, reply_markup=None):
        captured.append(message)
        return {}

    sched.send_telegram_digest = fake_digest
    sched.today_msk = lambda: day_today
    settings.telegram_digest_v2_enabled = v2
    if not with_metrika:
        settings.yandex_metrika_read_token = ""
    started = time.monotonic()
    await sched.telegram_daily_digest_job()
    text = captured[0] if captured else "(дайджест не собран)"
    describe(f"Ежедневный дайджест за {day_today - timedelta(days=1)}" + (" + блоки v2" if v2 else ""),
             text if show_personal else mask_personal(text), time.monotonic() - started)


async def render_period(kind: str, day_today: date) -> None:
    from app.services import telegram_reports as tr

    started = time.monotonic()
    text = await (tr.build_weekly_report(day_today) if kind == "weekly" else tr.build_monthly_report(day_today))
    describe("Недельный отчёт" if kind == "weekly" else "Месячный отчёт", text, time.monotonic() - started)


async def render_buttons() -> None:
    from app.services import telegram_reports as tr

    for title, factory in (("Кнопка «Регистрации»", tr.signups_button_text), ("Кнопка «Воронка»", tr.funnel_button_text),
                           ("Кнопка «Цели»", tr.goals_button_text)):
        started = time.monotonic()
        describe(title, await factory(), time.monotonic() - started)


async def render_alerts(now: datetime) -> None:
    from app.services import analytics_alerts as aa

    sent: list[str] = []

    async def fake_alert(key, text, kind="analytics_anomaly"):
        sent.append(f"[{key}] {text}")
        return True

    aa._alert = fake_alert
    settings.telegram_new_alerts_enabled = True
    await aa.check_audience_alerts(now)
    print("=" * 78)
    print(f"Новые алерты на {now:%Y-%m-%d %H:%M} UTC (пороги: {aa.SIGNUP_DROP_AFTER.total_seconds() / 3600:.0f} ч без регистраций "
          f"при ≥{aa.SIGNUP_DROP_MIN_PAGEVIEWS_24H} просмотров за сутки; ≥{aa.AUTH_ERROR_SPIKE_MIN} ошибок входа за час)")
    print("=" * 78)
    print("\n".join(sent) if sent else "Сейчас ни один из новых алертов не сработал бы.")
    print()


async def main(args: argparse.Namespace) -> None:
    # Защита: отчёты только показываем.
    from app.services import alerting

    async def forbidden(*_a, **_k):
        raise RuntimeError("Скрипт показа отчётов ничего не отправляет")

    alerting.send_telegram = forbidden
    settings.telegram_bot_token = settings.telegram_bot_token or "render-only"
    settings.telegram_chat_id = settings.telegram_chat_id or "0"

    today = date.fromisoformat(args.date) if args.date else (datetime.now(timezone.utc) + timedelta(hours=3)).date()
    what = args.what
    if what in ("digest", "all"):
        await render_digest(today, args.show_personal, args.metrika, v2=not args.no_v2)
    if what in ("weekly", "all"):
        await render_period("weekly", today)
    if what in ("monthly", "all"):
        await render_period("monthly", today)
    if what in ("buttons", "all"):
        await render_buttons()
    if what in ("alerts", "all"):
        await render_alerts(datetime.combine(today, datetime.min.time()) + timedelta(hours=12) - timedelta(hours=3))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--what", choices=("digest", "weekly", "monthly", "buttons", "alerts", "all"), default="all")
    parser.add_argument("--date", help="«сегодня» по МСК (ГГГГ-ММ-ДД); отчёты строятся за предыдущие сутки/неделю/месяц")
    parser.add_argument("--no-v2", action="store_true", help="дайджест без блоков v2")
    parser.add_argument("--metrika", action="store_true", help="не отключать запрос к Метрике (нужен токен чтения)")
    parser.add_argument("--show-personal", action="store_true", help="не скрывать имена и почты в блоке новых пользователей")
    return parser.parse_args(argv)


if __name__ == "__main__":
    asyncio.run(main(parse_args()))
