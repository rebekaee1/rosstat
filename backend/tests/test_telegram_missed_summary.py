"""Круг 13, T2: сводка «что не дошло до Telegram» (чистые функции) и защита скрипта досылки."""
import importlib.util
import re
from datetime import date, datetime
from pathlib import Path

import pytest

from app.config import settings
from app.services import telegram_missed_summary as ms
from app.services.telegram_resend import OutboxRow

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "resend-missed-summary.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("resend_missed_summary", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_ID = iter(range(1, 10_000))


def row(kind, text, at, *, chat="1111", ok=False, error="ConnectTimeout"):
    return OutboxRow(id=next(_ID), sent_at=at, chat_id=chat, kind=kind, text=text, ok=ok, error=error)


NEW_USER = ("🆕 <b>Новый пользователь</b>\nВерсия сайта: английская\nСпособ входа: vk\n"
            "Email: person.one@example.org\nТелефон: +7 900 000-00-00\nИмя: Иван Тестов\nРассылка: да\n"
            "ID: <code>0b6d2f6e-1111-4222-8333-444455556666</code>")


def _rows():
    return [
        row("analytics_anomaly", "⚠️ <b>Аномалия аналитики</b>\nТрафик часа упал: 96 просмотров против 322 (30%).",
            datetime(2026, 10, 4, 1, 32)),
        row("analytics_anomaly", "⚠️ <b>Аномалия аналитики</b>\nТрафик часа упал: 117 просмотров против 2030 (6%).",
            datetime(2026, 10, 5, 18, 47)),
        row("analytics_anomaly", "⚠️ <b>Аномалия аналитики</b>\nПамять контейнера scheduler 99% лимита (порог 85%).",
            datetime(2026, 10, 8, 6, 21)),
        row("http_5xx_spike", "🔴 <b>5xx spike</b>\n10 ответов 5xx за 5 мин (последний путь: /seo/world/x/y/2024)",
            datetime(2026, 10, 7, 8, 18)),
        row("http_5xx_spike", "🔴 <b>Всплеск ошибок сервера (5xx)</b>\n10 ответов 5xx за 5 мин (последний путь: /api/v1/regions)",
            datetime(2026, 10, 9, 6, 53)),
        # два чата, один и тот же текст — одно событие
        row("new_user", NEW_USER, datetime(2026, 10, 6, 12, 55), chat="1111"),
        row("new_user", NEW_USER, datetime(2026, 10, 6, 12, 55), chat="2222"),
        row("scheduler_alert", "🔴 <b>Scheduler job failed</b>\nJob: <code>telegram_poll</code>\nTimeout connecting to server",
            datetime(2026, 10, 7, 12, 39)),
        row("scheduler_alert", "🔴 <b>Сбой фоновой задачи</b>\nЗадача: <code>sitemap_build</code>\ncanceling statement due to statement timeout",
            datetime(2026, 10, 9, 0, 12)),
        row("etl_summary", "🔴 <b>Daily ETL Complete</b>\nTotal: 117 | Updated: 14 | Failed: 23 | Problems: 3\nDuration: 33100s",
            datetime(2026, 10, 7, 12, 11)),
        row("digest", "📊 <b>Forecast Economy — дайджест за 2026-10-07</b>\n👤 Пользователи: всего 128, +3 за сутки, подписка на рассылку 83\n"
            "🆕 <b>Новые за сутки:</b>\n• Иван Тестов — person.one@example.org (vk)\n🔎 <b>Поиск:</b> ввод 71, выбрано 4, брошено 5",
            datetime(2026, 10, 8, 6, 1)),
        row("zero_parse", "🟡 <b>Zero-parse regression</b>\nIndicator: <code>fuel-ai92</code>\nПарсер вернул 0 точек",
            datetime(2026, 10, 9, 3, 2)),
        # доставлено позже — в сводку не попадает
        row("analytics_anomaly", "⚠️ уже доставлено", datetime(2026, 10, 5, 9, 0)),
        row("analytics_anomaly", "⚠️ уже доставлено", datetime(2026, 10, 5, 9, 20), ok=True, error=None),
        # ответ кнопки и сама сводка — пропускаются
        row("bot_reply", "ответ кнопки", datetime(2026, 10, 5, 9, 0)),
    ]


def test_find_missed_merges_chats_and_skips_delivered():
    missed = ms.find_missed(_rows())
    assert len(missed) == 11
    assert not any("уже доставлено" in m.text or m.kind == "bot_reply" for m in missed)
    signup = [m for m in missed if m.kind == "new_user"]
    assert len(signup) == 1 and signup[0].chats == 2


def test_summary_is_one_message_without_personal_data():
    missed = ms.find_missed(_rows())
    text = ms.build_summary(missed, since=date(2026, 10, 3), until=date(2026, 10, 9))
    assert len(text) <= 4000
    assert text.startswith("📬 <b>Что мы пропустили с 3 по 9 октября 2026</b>")
    assert "Всего 11 сообщений не дошло" in text
    for needle in ("person.one", "@", "+7", "Иван", "Тестов", "0b6d2f6e", "9" * 10):
        assert needle not in text, needle
    assert "\n\n" not in text and not any(not line.strip() for line in text.split("\n"))
    # группы и факты
    assert "⚠️ <b>Аномалии аналитики</b>: 3" in text
    assert "до 6% от обычного" in text
    assert "память scheduler до 99% лимита" in text
    assert "🔴 <b>Всплески ошибок сервера (5xx)</b>: 2" in text and "страницы для поисковиков 1" in text
    assert "запросы к данным 1" in text
    assert "🌍 <b>Новые регистрации</b>: 1" in text and "английская версия 1" in text and "VK 1" in text
    assert "telegram_poll" in text and "sitemap_build" in text
    assert "запрос к базе превысил лимит времени" in text
    assert "с ошибкой 23" in text and "шла 9,2 ч" in text
    assert "пользователей 128 (+3)" in text and "запросов в поиске 71" in text
    assert "fuel-ai92" in text
    assert text.count("<blockquote") == text.count("</blockquote>")


def test_summary_stays_under_the_limit_even_for_huge_input():
    rows = [row("scheduler_alert", f"🔴 <b>Сбой фоновой задачи</b>\nЗадача: <code>job_{i}</code>\nTimeout",
                datetime(2026, 10, 4, 1, 0) + (datetime(2026, 10, 4) - datetime(2026, 10, 4)))
            for i in range(600)]
    text = ms.build_summary(ms.find_missed(rows), since=date(2026, 10, 3), until=date(2026, 10, 9))
    assert len(text) <= 4000
    assert text.count("<blockquote") == text.count("</blockquote>")


def test_empty_summary_says_so():
    text = ms.build_summary([], since=date(2026, 10, 3), until=date(2026, 10, 9))
    assert "Недоставленных сообщений в архиве нет" in text


def test_days_text_and_plural():
    assert ms.days_text([date(2026, 10, 4), date(2026, 10, 5), date(2026, 10, 8)]) == "4, 5 и 8 окт."
    assert ms.days_text([date(2026, 9, 30), date(2026, 10, 1)]) == "30 сент., 1 окт."
    assert ms._plural(1, "раз", "раза", "раз") == "раз" and ms._plural(3, "раз", "раза", "раз") == "раза"
    assert ms._plural(11, "сообщение", "сообщения", "сообщений") == "сообщений"


def test_script_is_dry_run_by_default_and_owner_only(monkeypatch):
    script = _load_script()
    args = script.parse_args([])
    assert args.dry_run is True and args.recipient == "owner" and args.force is False
    assert script.parse_args(["--no-dry-run"]).dry_run is False
    monkeypatch.setattr(settings, "telegram_chat_id", "424242", raising=False)
    assert script.resolve_recipient("owner") == "424242"
    assert script.resolve_recipient("424242") == "424242"
    with pytest.raises(SystemExit):
        script.resolve_recipient("999999")
    monkeypatch.setattr(settings, "telegram_chat_id", "", raising=False)
    with pytest.raises(SystemExit):
        script.resolve_recipient("owner")


def test_script_window_is_moscow_days():
    script = _load_script()
    start, end = script.window_utc(date(2026, 10, 3), date(2026, 10, 9))
    assert start == datetime(2026, 10, 2, 21, 0) and end == datetime(2026, 10, 9, 21, 0)


def test_dry_run_never_sends(monkeypatch, capsys):
    script = _load_script()
    monkeypatch.setattr(settings, "telegram_chat_id", "424242", raising=False)
    rows = _rows()

    async def fake_rows(start, end):
        return rows

    async def boom(*a, **k):
        raise AssertionError("в пробном прогоне отправлять нельзя")

    monkeypatch.setattr(script, "load_rows", fake_rows)
    import app.services.alerting as alerting
    monkeypatch.setattr(alerting, "send_telegram", boom)
    import asyncio
    code = asyncio.run(script.main(script.parse_args([])))
    out = capsys.readouterr().out
    assert code == 0 and "Пробный прогон" in out and "Что мы пропустили" in out
    assert not re.search(r"person\.one|Иван", out)


def test_render_script_masks_people_and_refuses_to_send():
    spec = importlib.util.spec_from_file_location(
        "render_telegram_reports", Path(__file__).resolve().parents[1] / "scripts" / "render-telegram-reports.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    masked = module.mask_personal("📊 x\n• Иван Тестов — person.one@example.org (yandex)\n• Имя — +7 900 000-00-00 (vk)")
    assert "Иван" not in masked and "@" not in masked and "900" not in masked
    assert "(yandex)" in masked and "(vk)" in masked
    args = module.parse_args([])
    assert args.what == "all" and args.show_personal is False and args.no_v2 is False


def test_same_text_delivered_next_day_does_not_hide_the_lost_one():
    text = "⚠️ <b>Аномалия аналитики</b>\nЦели Метрики разошлись с goal_taxonomy (не macro/micro): a, b"
    rows = [
        row("analytics_anomaly", text, datetime(2026, 10, 6, 1, 55)),                         # потеряно
        row("analytics_anomaly", text, datetime(2026, 10, 7, 1, 55), ok=True, error=None),    # завтрашний повтор
        row("analytics_anomaly", text, datetime(2026, 10, 8, 1, 55)),                         # потеряно
        row("analytics_anomaly", text, datetime(2026, 10, 8, 1, 58), ok=True, error=None),    # досылка через 3 мин
    ]
    missed = ms.find_missed(rows)
    assert [m.at.day for m in missed] == [6]


def test_pulse_headlines_and_clean_world_titles():
    rows = [
        row("pulse_digest", "🛰 Пульс платформы — 2026-10-03\n\n3 октября, пятница — обычный день, два технических сигнала\nДальше",
            datetime(2026, 10, 4, 6, 6)),
        row("world_ingest_summary", "🟡 <b>Обновление: Европа: Eurostat</b>\nИтог: частично\nОшибок: 1", datetime(2026, 10, 6, 0, 4)),
    ]
    text = ms.build_summary(ms.find_missed(rows), since=date(2026, 10, 3), until=date(2026, 10, 9))
    assert "Пульс: 3 окт.: 3 октября, пятница — обычный день, два технических сигнала" in text
    assert "&lt;" not in text and "&amp;" not in text
