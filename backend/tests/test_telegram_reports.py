"""Круг 11, зона H: тексты отчётов об аудитории (чистые функции, без сети и без базы)."""
import asyncio
import re
from datetime import date

import pytest

from app.config import settings
from app.services import telegram_reports as tr
from app.services.analytics_period import resolve_period
from app.services.telegram_text import split_telegram_text

SIG = {
    "total": 2,
    "locale": {"ru": 1, "en": 1},
    "method": {"email": 1, "yandex": 1},
    "origin": {"ru": 1, "foreign": 1},
    "foreign_countries": {"Германия": 1},
    "channel": {"search": 1, "direct": 1},
    "device": {"mobile": 2},
    "trigger": {"gate_download": 1, "header": 1},
    "landing_top": {"/russia/indicator/cpi": 1},
    "returned_7d": {"eligible": 0, "returned": 0, "pct": None},
    "median_days_to_signup": 0.0,
    "unknown_locale": 0,
}
USAGE = {
    "has_data": True, "days_covered": 1,
    "groups": {
        "download": {"actions": 5, "sessions": 4, "events": {"download_csv": 3, "download_excel": 2},
                     "surface": {"indicator": 4, "rating": 1}, "locale": {"ru": 5}, "device": {"desktop": 5}, "country": {}},
        "wall": {"actions": 4, "sessions": 3, "events": {"download_limit": 4}, "surface": {"indicator": 4},
                 "locale": {"ru": 3, "en": 1}, "device": {}, "country": {}},
        "compare": {"actions": 21, "sessions": 9, "events": {}, "surface": {}, "locale": {}, "device": {}, "country": {}},
        "calc": {"actions": 0, "sessions": 0, "events": {}, "surface": {}, "locale": {}, "device": {}, "country": {}},
        "share": {"actions": 3, "sessions": 3, "events": {}, "surface": {}, "locale": {}, "device": {}, "country": {}},
        "favorite": {"actions": 0, "sessions": 0, "events": {}, "surface": {}, "locale": {}, "device": {}, "country": {}},
        "subscribe": {"actions": 0, "sessions": 0, "events": {}, "surface": {}, "locale": {}, "device": {}, "country": {}},
        "language": {"actions": 2, "sessions": 2, "events": {}, "surface": {}, "locale": {}, "device": {}, "country": {}},
    },
}
FUNNEL = {
    "steps": [
        {"key": "visitors", "label": "посетители", "count": 310},
        {"key": "viewed", "label": "смотрели показатель", "count": 120},
        {"key": "wall", "label": "лимит", "count": 41},
        {"key": "register_click", "label": "кнопка", "count": 14},
        {"key": "form_open", "label": "форма", "count": 0},
        {"key": "submit", "label": "отправили", "count": 6},
        {"key": "signed_up", "label": "зарегистрировались", "count": 2},
    ],
    "dropped_at": {"wall": 27, "register_click": 8, "submit": 4},
    "weakest": {"from": "wall", "to": "register_click", "base": 41, "next": 14, "rate_pct": 34.1},
    "by_locale": {"ru": {"visitors": 200, "viewed": 80, "wall": 30, "register_click": 10, "signed_up": 1},
                  "en": {"visitors": 110, "viewed": 40, "wall": 11, "register_click": 4, "signed_up": 1}},
}
REL = {"js_errors_own": [{"error": "x", "count": 3}], "vitals_p75": {"LCP": 2400.0}, "api_p75_ms": 310.0,
       "page_device": [{"page_group": "indicator", "device": "mobile", "lcp_p75_ms": 3100.0, "lcp_samples": 12, "js_errors_own": 3}]}


def test_digest_v2_matches_the_agreed_shape():
    lines = tr.format_digest_v2(signups=SIG, usage=USAGE, funnel=FUNNEL, reliability=REL)
    text = "\n".join(lines)
    assert "🌍 Регистрации: 2 · русская версия 1, английская версия 1 · вне РФ: 1" in text
    assert "🧭 Откуда: поиск 1, прямой заход 1 · устройство: телефон 2" in text
    assert "🚪 Что подтолкнуло: скачивание данных 1, кнопка в шапке 1" in text
    assert "🎯 Что делали: выгрузки 5 (CSV 3, Excel 2) · упёрлись в лимит 4 · сравнение 21 · поделились 3 · смена языка 2" in text
    # нули не показываются: калькуляторы, избранное, подписки
    assert "калькуляторы" not in text and "избранное" not in text
    assert "🪜 Воронка: посетители 310 → смотрели показатель 120 → лимит 41 → «Регистрация» 14 → отправили 6 → зарегистрировались 2" in text
    assert "форма или соцсеть" not in text.split("🪜")[1].split("\n")[0]
    assert "⚡ Сайт: ошибок своих скриптов 3 · LCP p75 2,4 с · API p75 310 мс · медленнее всего: показатель России, телефон 3,1 с" in text
    assert "<blockquote expandable>" in text and text.count("<blockquote") == text.count("</blockquote>")
    # каждая строка в стиле существующих сообщений: начинается с эмодзи
    for line in lines[:-1]:
        assert not line[0].isalnum() and not line[0].islower()


def test_digest_v2_without_data_says_so_instead_of_zero():
    usage = {"has_data": False, "days_covered": 0, "groups": {}}
    lines = tr.format_digest_v2(signups={"total": 0}, usage=usage, funnel=None, reliability=None)
    text = "\n".join(lines)
    assert "🌍 Регистраций не было" in text
    assert "🎯 Что делали: данных нет (разрезы ещё не посчитаны)" in text
    assert "Воронка" not in text and "Сайт" not in text


def test_unknown_values_are_listed_last_and_not_hidden():
    sig = dict(SIG, locale={"unknown": 3, "ru": 1}, total=4)
    line = tr.signups_lines(sig)[0]
    assert line.endswith("русская версия 1, язык неизвестен 3") or "русская версия 1, язык неизвестен 3" in line


def test_digest_v2_has_no_personal_data():
    text = "\n".join(tr.format_digest_v2(signups=SIG, usage=USAGE, funnel=FUNNEL, reliability=REL))
    assert not re.search(r"@|\+7|\d{10,}", text)


def test_worst_case_digest_is_split_under_the_telegram_limit():
    """Даже раздутый дайджест уходит частями ≤ 4096 знаков и без разорванных спойлеров."""
    big_sig = dict(SIG, total=999, landing_top={f"/page/{i}": i for i in range(1, 9)},
                   channel={f"channel{i}": i for i in range(1, 30)})
    block = tr.format_digest_v2(signups=big_sig, usage=USAGE, funnel=FUNNEL, reliability=REL)
    text = "📊 <b>Forecast Economy — дайджест за 2026-10-08</b>\n" + "\n".join(block) + "\n" + "\n".join(
        f"• Пользователь {i} — user{i}@example.com (почта)" for i in range(120))
    chunks = split_telegram_text(text)
    assert all(len(c) <= 4096 for c in chunks)
    assert all(c.count("<blockquote") == c.count("</blockquote>") for c in chunks)


def test_period_helpers_use_moscow_calendar():
    cur, prev = tr.week_period(date(2026, 10, 4))        # воскресенье
    assert (cur.start_date, cur.end_date) == (date(2026, 9, 28), date(2026, 10, 4))
    assert (prev.start_date, prev.end_date) == (date(2026, 9, 21), date(2026, 9, 27))
    month, before = tr.month_periods(date(2026, 10, 1))
    assert (month.start_date, month.end_date) == (date(2026, 9, 1), date(2026, 9, 30))
    assert (before.start_date, before.end_date) == (date(2026, 8, 1), date(2026, 8, 31))
    jan, dec = tr.month_periods(date(2026, 1, 1))
    assert (jan.start_date, jan.end_date) == (date(2025, 12, 1), date(2025, 12, 31))


def _weekly_data():
    cur, prev = tr.week_period(date(2026, 10, 4))
    return {
        "period": cur, "prev_period": prev, "signups": dict(SIG, returned_7d={"eligible": 7, "returned": 4, "pct": 57.1},
                                                              median_days_to_signup=2.0),
        "prev_signups": {"total": 1}, "audience": {"visitors": 2310, "foreign_share_pct": 12.0},
        "prev_audience": {"visitors": 2140, "foreign_share_pct": 9.0}, "funnel": FUNNEL, "usage": USAGE,
        "prev_usage": {"has_data": True, "groups": {"compare": {"actions": 14}}}, "reliability": REL,
        "pwa": {"totals": {"installs": 3, "launch_visitors": 7}},
        "search_gaps": {"top": [{"q": "биткоин к рублю", "searches": 4, "people": 3}]},
        "visitors_by_channel": {"search": 1000, "direct": 800, "social": 5},
        "english": "посетители 110, регистрации 1, упёрлись в лимит 11",
    }


def test_weekly_report_blocks():
    text = tr.format_period_report(_weekly_data(), kind="weekly")
    assert text.startswith("📈 <b>Forecast Economy — неделя 28.09–04.10.2026</b>")
    assert "👥 Посетители (люди): 2 310 (+8%) · вне РФ: 12% (было 9%)" in text
    assert "🌍 Регистрации: 2 (+100%)" in text
    assert "📊 Конверсия «посетитель → регистрация»: 0,09%" in text
    assert "по каналам: поиск 0,1%, прямой заход 0,1%" in text
    assert "🔁 Вернулись за 7 дней: 4 из 7 (57%)" in text
    assert "📲 Установки приложения: 3 (запусков из иконки: 7)" in text
    assert "🕳 Поиск без результатов: «биткоин к рублю» ×4" in text
    assert "🇬🇧 Английская версия: посетители 110" in text
    assert "слабое звено: «Регистрация»" not in text.split("🪜")[0]
    assert "слабое звено: лимит → «Регистрация», 41 → 14 (34%)" in text
    assert "сравнение 21 (+50%)" in text
    assert text.count("<blockquote") == text.count("</blockquote>") == 1
    assert not re.search(r"@|\+7", text)


def test_monthly_report_adds_cohort_lines():
    data = _weekly_data()
    data["period"], data["prev_period"] = tr.month_periods(date(2026, 10, 1))
    data["signups"] = dict(data["signups"], returned_30d={"eligible": 5, "returned": 2, "pct": 40.0})
    text = tr.format_period_report(data, kind="monthly")
    assert "месяц 01.09–30.09.2026" in text.split("\n")[0]
    assert "за 30 дней: 2 из 5 (40%)" in text
    assert "🧲 лучшие первые страницы: /russia/indicator/cpi ×1" in text


def test_report_marks_missing_blocks_instead_of_zeros():
    data = _weekly_data()
    data.update({"signups": None, "funnel": None, "usage": None, "audience": None})
    text = tr.format_period_report(data, kind="weekly")
    assert "ℹ️ посетители: данных нет; регистрации: данных нет; воронка: данных нет; использование функций: данных нет" in text
    assert "Регистрации: 0" not in text


def test_button_replies():
    reply = tr.format_signups_reply({"7 дней": SIG, "30 дней": {"total": 0}, "Всё время": None})
    assert "7 дней: 2 · русская версия 1, английская версия 1 · вне РФ 1" in reply
    assert "30 дней: регистраций не было" in reply and "Всё время: данных нет" in reply
    funnel = tr.format_funnel_reply(FUNNEL, resolve_period("custom", date(2026, 10, 1), date(2026, 10, 7)))
    assert "🧭 <b>Воронка за 01.10–07.10.2026</b>" in funnel and "Ушли на шаге: лимит 27" in funnel
    goals = tr.format_goals_reply({"Вчера": USAGE, "7 дней": {"has_data": False, "groups": {}}})
    assert "Вчера: выгрузки 5" in goals and "7 дней: данных нет" in goals


def test_formatters_helpers():
    assert tr.fmt_int(12345) == "12 345" and tr.fmt_int(None) == "—"
    assert tr.fmt_pct(0.5) == "0,5%" and tr.fmt_pct(12.0) == "12%" and tr.fmt_pct(None) == "—"
    assert tr.fmt_seconds(2400) == "2,4 с"
    assert tr.delta_text(110, 100) == "+10%" and tr.delta_text(90, 100) == "−10%" and tr.delta_text(5, None) == ""
    assert tr.delta_text(3, 0) == "прошлый период: 0" and tr.delta_text(100, 100) == "без изменений"


# --- флаги, кнопки, расписание ----------------------------------------------------

def test_new_reports_are_off_by_default():
    for flag in ("telegram_digest_v2_enabled", "telegram_weekly_enabled", "telegram_monthly_enabled",
                 "telegram_new_alerts_enabled"):
        assert type(settings).model_fields[flag].default is False, flag


def test_menu_buttons_appear_only_with_the_flag(monkeypatch):
    from app.services.telegram_bot import main_menu_keyboard

    monkeypatch.setattr(settings, "telegram_digest_v2_enabled", False)
    off = main_menu_keyboard()["inline_keyboard"]
    monkeypatch.setattr(settings, "telegram_digest_v2_enabled", True)
    on = main_menu_keyboard()["inline_keyboard"]
    assert on[:len(off)] == off  # существующие кнопки не менялись
    added = {b["callback_data"] for row in on[len(off):] for b in row}
    assert added == {"signups", "funnel", "goals"}


def test_new_kinds_are_resendable():
    from app.services.telegram_resend import RESEND_KINDS

    for kind in ("weekly_report", "monthly_report", "audience_alert"):
        assert kind in RESEND_KINDS


def test_callback_for_new_buttons_is_ignored_when_flag_is_off(monkeypatch):
    from app.services import telegram_bot as tb

    sent = []

    async def fake_api(method, payload, files=None):
        sent.append(method)
        return {"ok": True, "result": []}

    monkeypatch.setattr(tb, "_api", fake_api)
    monkeypatch.setattr(settings, "telegram_digest_v2_enabled", False)
    monkeypatch.setattr(settings, "telegram_chat_id", "42", raising=False)
    asyncio.run(tb._handle_callback({"id": "1", "data": "signups", "message": {"chat": {"id": 42}}}))
    assert sent == ["answerCallbackQuery"]
