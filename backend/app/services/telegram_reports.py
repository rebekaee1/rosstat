"""Отчёты об аудитории в Telegram (круг 11, зона H): дайджест v2, недельный и месячный
отчёты, ответы кнопок «Регистрации», «Воронка», «Цели».

Устройство:
- формат — чистые функции от словарей витрин (тестируются без сети и без базы);
- данные — только из `analytics_marts` (инвариант «одна цифра — одна функция»), период
  задаётся `Period` по МСК; роботы и своя активность исключены внутри витрин;
- сборщики (`collect_*`) оборачивают каждую витрину в `try/except` + `wait_for`: сбой или
  медленный запрос одного блока не отменяет отчёт, блок просто пропускается;
- отправка — через общие `send_telegram` / `send_message` (разбиение длинного текста,
  архив `telegram_outbox`, досылка по виду `kind`).

Оформление как у существующих сообщений: эмодзи и заглавная буква в начале, заголовок
`<b>…</b>`, «Метка: значение», разделитель «·» внутри строки, подробности в
`<blockquote expandable>`. Нули не показываем; «данных нет» не равно нулю. Имён, почт и
телефонов в отчётах нет, в Пульс-LLM они тоже не уходят.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date, timedelta
from html import escape
from typing import Any, Awaitable, Callable

from app.config import settings
from app.database import analytics_session
from app.services.analytics_period import Period, resolve_period
from app.services.display import today_msk
from app.services.goal_taxonomy import GROUP_LABELS_RU, REPORT_GROUPS

logger = logging.getLogger(__name__)

# Потолок на один блок отчёта (секунд): тяжёлый запрос не задерживает весь отчёт.
BLOCK_TIMEOUT_S = 75

LOCALE_LABELS = {"ru": "русская версия", "en": "английская версия", "unknown": "язык неизвестен"}
METHOD_LABELS = {"email": "почта", "yandex": "Яндекс", "vk": "VK", "google": "Google", "unknown": "способ неизвестен"}
CHANNEL_LABELS = {
    "search": "поиск", "direct": "прямой заход", "social": "соцсети", "referral": "переход с сайта",
    "ad": "реклама", "campaign": "рассылка", "internal": "внутренний переход", "unknown": "канал неизвестен",
}
DEVICE_LABELS = {
    "mobile": "телефон", "desktop": "компьютер", "tablet": "планшет", "bot": "робот", "unknown": "устройство неизвестно",
}
TRIGGER_LABELS = {
    "gate_download": "скачивание данных", "gate_chart_image": "картинка графика",
    "gate_compare": "сравнение", "gate_gif": "анимированная карта", "nudge": "приглашение на странице",
    "header": "кнопка в шапке", "direct": "сам, без подсказки", "unknown": "неизвестно",
}
ORIGIN_LABELS = {"ru": "Россия", "foreign": "вне РФ", "unknown": "страна неизвестна"}
SURFACE_LABELS = {
    "indicator": "показатель России", "world_indicator": "показатель страны", "region": "регион",
    "rating": "рейтинг", "compare": "сравнение", "country": "страница страны", "calculator": "калькулятор",
    "home": "главная", "world_home": "мировой раздел", "embed": "виджеты", "chart_menu": "меню графика",
    "category": "категория", "demographics": "демография", "calendar": "календарь", "today": "сегодня",
    "other": "другое",
}
FUNNEL_SHORT = {
    "visitors": "посетители", "viewed": "смотрели показатель", "wall": "лимит",
    "register_click": "«Регистрация»", "form_open": "форма или соцсеть",
    "submit": "отправили", "signed_up": "зарегистрировались",
}


# ---------------------------------------------------------------------------
# Мелкие форматтеры
# ---------------------------------------------------------------------------

def fmt_int(value: int | float | None) -> str:
    """Целое с пробелом-разделителем тысяч: 12 345."""
    if value is None:
        return "—"
    return f"{int(round(value)):,}".replace(",", " ")


def fmt_pct(value: float | None, digits: int = 1) -> str:
    if value is None:
        return "—"
    text = f"{value:.{digits}f}".replace(".", ",")
    if "," in text:
        text = text.rstrip("0").rstrip(",")
    return f"{text}%"


def fmt_seconds(ms: float | None) -> str:
    if ms is None:
        return "—"
    return f"{ms / 1000:.1f}".replace(".", ",") + " с"


def delta_text(cur: int | float | None, prev: int | float | None) -> str:
    """«+8% к прошлому» / «−12%» / «было 0»; пусто, если сравнивать не с чем."""
    if cur is None or prev is None:
        return ""
    if prev == 0:
        return "прошлый период: 0" if cur else ""
    change = round(100 * (cur - prev) / prev)
    if change == 0:
        return "без изменений"
    sign = "+" if change > 0 else "−"
    return f"{sign}{abs(change)}%"


def count_list(
    counts: dict[str, int] | None, labels: dict[str, str] | None = None, *, limit: int = 4,
    show_unknown: bool = True,
) -> str:
    """«поиск 6, прямой заход 5»: по убыванию, нули скрыты, «неизвестно» в конце."""
    if not counts:
        return ""
    known = [(k, v) for k, v in counts.items() if v and k != "unknown"]
    known.sort(key=lambda kv: -kv[1])
    items = known[:limit]
    unknown = counts.get("unknown", 0)
    if show_unknown and unknown:
        items.append(("unknown", unknown))
    labels = labels or {}
    return ", ".join(f"{escape(str(labels.get(k, k)))} {fmt_int(v)}" for k, v in items)


def _line(*parts: str) -> str:
    return " · ".join(p for p in parts if p)


def period_title(period: Period) -> str:
    if period.start_date == period.end_date:
        return period.start_date.strftime("%d.%m.%Y")
    return f"{period.start_date.strftime('%d.%m')}–{period.end_date.strftime('%d.%m.%Y')}"


# ---------------------------------------------------------------------------
# Блоки текста из витрин (чистые функции)
# ---------------------------------------------------------------------------

def signups_lines(sig: dict | None, prev: dict | None = None) -> list[str]:
    """Блок «Регистрации»: сколько, язык, откуда, устройство, что подтолкнуло."""
    if not sig:
        return []
    total = int(sig.get("total") or 0)
    if total == 0:
        return ["🌍 Регистраций не было"] if prev is None else [
            _line("🌍 Регистраций не было", f"прошлый период: {fmt_int(prev.get('total'))}" if prev.get("total") else "")
        ]
    head = f"🌍 Регистрации: {fmt_int(total)}"
    change = delta_text(total, prev.get("total") if prev else None)
    if change:
        head += f" ({change})"
    known_origin = sig.get("origin", {})
    foreign = int(known_origin.get("foreign", 0))
    lines = [_line(
        head,
        count_list(sig.get("locale"), LOCALE_LABELS, limit=3),
        f"вне РФ: {fmt_int(foreign)}" if foreign else "",
    )]
    where = _line(
        count_list(sig.get("channel"), CHANNEL_LABELS, limit=4),
        ("устройство: " + count_list(sig.get("device"), DEVICE_LABELS, limit=3)) if sig.get("device") else "",
    )
    if where:
        lines.append("🧭 Откуда: " + where)
    trig = count_list(sig.get("trigger"), TRIGGER_LABELS, limit=4)
    if trig:
        lines.append("🚪 Что подтолкнуло: " + trig)
    method = count_list(sig.get("method"), METHOD_LABELS, limit=4)
    if method:
        lines.append("🔑 Способ: " + method)
    return lines


def usage_lines(usage: dict | None, prev: dict | None = None) -> list[str]:
    """Блок «Что делали»: по строке-перечислению на сутки; только ненулевые группы."""
    if not usage:
        return []
    if not usage.get("has_data"):
        return ["🎯 Что делали: данных нет (разрезы ещё не посчитаны)"]
    parts: list[str] = []
    for group in REPORT_GROUPS:
        bucket = (usage.get("groups") or {}).get(group) or {}
        actions = int(bucket.get("actions") or 0)
        if not actions:
            continue
        text = f"{GROUP_LABELS_RU[group]} {fmt_int(actions)}"
        if group == "download":
            events = bucket.get("events") or {}
            csv = events.get("download_csv", 0)
            xls = events.get("download_excel", 0)
            if csv or xls:
                text += f" (CSV {fmt_int(csv)}, Excel {fmt_int(xls)})"
        if prev and prev.get("has_data"):
            before = (prev.get("groups") or {}).get(group, {}).get("actions")
            change = delta_text(actions, before)
            if change and group != "download":
                text += f" ({change})"
        parts.append(text)
    if not parts:
        return ["🎯 Что делали: действий в этих разделах не было"]
    return ["🎯 Что делали: " + " · ".join(parts)]


def funnel_line(funnel: dict | None) -> str:
    """Одна строка шагов: нули в середине цепочки не показываем, последний шаг всегда."""
    if not funnel:
        return ""
    steps = funnel.get("steps") or []
    shown = []
    for index, step in enumerate(steps):
        count = int(step.get("count") or 0)
        if count == 0 and index != len(steps) - 1:
            continue
        shown.append(f"{FUNNEL_SHORT.get(step['key'], step['label'])} {fmt_int(count)}")
    return "🪜 Воронка: " + " → ".join(shown) if shown else ""


def weakest_text(funnel: dict | None) -> str:
    weak = (funnel or {}).get("weakest")
    if not weak:
        return ""
    return (f"слабое звено: {FUNNEL_SHORT.get(weak['from'], weak['from'])} → "
            f"{FUNNEL_SHORT.get(weak['to'], weak['to'])}, {fmt_int(weak['base'])} → {fmt_int(weak['next'])} "
            f"({fmt_pct(weak['rate_pct'], 0)})")


def dropped_text(funnel: dict | None) -> str:
    dropped = (funnel or {}).get("dropped_at") or {}
    if not dropped:
        return ""
    ordered = ["wall", "register_click", "form_open", "submit"]
    pieces = [f"{FUNNEL_SHORT[k]} {fmt_int(dropped[k])}" for k in ordered if dropped.get(k)]
    return "ушли на шаге: " + ", ".join(pieces) if pieces else ""


def reliability_line(rel: dict | None) -> str:
    if not rel:
        return ""
    own_errors = sum(int(item.get("count", 0)) for item in rel.get("js_errors_own", []))
    lcp = (rel.get("vitals_p75") or {}).get("LCP")
    api = rel.get("api_p75_ms")
    worst = next((c for c in rel.get("page_device", []) if (c.get("lcp_samples") or 0) >= 5 and c.get("lcp_p75_ms")), None)
    bits = []
    if own_errors:
        bits.append(f"ошибок своих скриптов {fmt_int(own_errors)}")
    if lcp is not None:
        bits.append(f"LCP p75 {fmt_seconds(lcp)}")
    if api is not None:
        bits.append(f"API p75 {fmt_int(api)} мс")
    if worst and worst["lcp_p75_ms"] >= 2500:
        group = SURFACE_LABELS.get(worst["page_group"], worst["page_group"])
        device = DEVICE_LABELS.get(worst["device"], worst["device"])
        bits.append(f"медленнее всего: {group}, {device} {fmt_seconds(worst['lcp_p75_ms'])}")
    return "⚡ Сайт: " + " · ".join(bits) if bits else ""


def _split_block(title: str, mapping: dict | None, labels: dict[str, str], limit: int = 6) -> str:
    text = count_list(mapping, labels, limit=limit)
    return f"{title}: {text}" if text else ""


def detail_lines_for_day(sig: dict | None, usage: dict | None, funnel: dict | None) -> list[str]:
    """Подробности под спойлер: каналы, поверхности упоров и выгрузок, ушедшие, языки воронки."""
    out: list[str] = []
    if sig and sig.get("total"):
        for title, key, labels in (("Каналы", "channel", CHANNEL_LABELS), ("Устройства", "device", DEVICE_LABELS),
                                   ("Страны вне РФ", "foreign_countries", {})):
            line = _split_block(title, sig.get(key), labels, 6)
            if line:
                out.append(line)
        landing = ", ".join(f"{escape(page)} ×{n}" for page, n in (sig.get("landing_top") or {}).items())
        if landing:
            out.append(f"Первые страницы: {landing}")
    if usage and usage.get("has_data"):
        for group, label in (("download", "Выгрузки по разделам"), ("wall", "Упоры в лимит по разделам")):
            surface = ((usage["groups"].get(group) or {}).get("surface")) or {}
            line = _split_block(label, surface, SURFACE_LABELS, 6)
            if line:
                out.append(line)
    if funnel:
        for item in (dropped_text(funnel), weakest_text(funnel)):
            if item:
                out.append(item[0].upper() + item[1:])
        for locale, label in (("ru", "Русская версия"), ("en", "Английская версия")):
            cell = (funnel.get("by_locale") or {}).get(locale) or {}
            if any(cell.values()):
                out.append(f"{label}: " + ", ".join(
                    f"{FUNNEL_SHORT[k]} {fmt_int(v)}" for k, v in cell.items() if v))
    return out


def expandable(lines: list[str]) -> str:
    return "<blockquote expandable>" + "\n".join(lines) + "</blockquote>" if lines else ""


def format_digest_v2(
    *, signups: dict | None, usage: dict | None, funnel: dict | None, reliability: dict | None,
) -> list[str]:
    """Строки блоков v2 для ежедневного дайджеста (вставляются после блока пользователей)."""
    lines: list[str] = []
    lines += signups_lines(signups)
    lines += usage_lines(usage)
    funnel_text = funnel_line(funnel)
    if funnel_text:
        lines.append(funnel_text)
    site = reliability_line(reliability)
    if site:
        lines.append(site)
    details = expandable(detail_lines_for_day(signups, usage, funnel))
    if details:
        lines.append(details)
    return lines


# ---------------------------------------------------------------------------
# Недельный и месячный отчёты
# ---------------------------------------------------------------------------

def conversion_by_channel(sig: dict | None, visitors_by_channel: dict[str, int] | None, min_visitors: int = 20) -> str:
    """Конверсия «посетитель → регистрация» по каналам; каналы с малой базой не показываем."""
    if not sig or not visitors_by_channel:
        return ""
    reg = sig.get("channel") or {}
    parts = []
    for channel, visitors in sorted(visitors_by_channel.items(), key=lambda kv: -kv[1]):
        if visitors < min_visitors or channel == "unknown":
            continue
        parts.append(f"{CHANNEL_LABELS.get(channel, channel)} {fmt_pct(100 * reg.get(channel, 0) / visitors, 1)}")
    return ", ".join(parts[:5])


def format_period_report(data: dict[str, Any], *, kind: str) -> str:
    """Текст недельного (`kind='weekly'`) или месячного (`'monthly'`) отчёта."""
    period: Period = data["period"]
    prev: Period | None = data.get("prev_period")
    sig = data.get("signups")
    prev_sig = data.get("prev_signups")
    audience = data.get("audience")
    prev_audience = data.get("prev_audience")
    funnel = data.get("funnel")
    usage = data.get("usage")
    prev_usage = data.get("prev_usage")
    rel = data.get("reliability")

    title = "неделя" if kind == "weekly" else "месяц"
    head = f"📈 <b>Forecast Economy — {title} {period_title(period)}</b>"
    parts: list[str] = [head]
    notes: list[str] = []

    if audience:
        visitors = int(audience.get("visitors") or 0)
        change = delta_text(visitors, (prev_audience or {}).get("visitors"))
        share = audience.get("foreign_share_pct")
        prev_share = (prev_audience or {}).get("foreign_share_pct")
        parts.append(_line(
            f"👥 Посетители (люди): {fmt_int(visitors)}" + (f" ({change})" if change else ""),
            (f"вне РФ: {fmt_pct(share)}" + (f" (было {fmt_pct(prev_share)})" if prev_share is not None else ""))
            if share is not None else "",
        ))
    else:
        notes.append("посетители: данных нет")

    if sig is not None:
        parts += signups_lines(sig, prev_sig)
        visitors_total = int((audience or {}).get("visitors") or 0)
        if visitors_total and sig.get("total"):
            conv = 100 * sig["total"] / visitors_total
            prev_conv = None
            if prev_audience and prev_audience.get("visitors") and prev_sig:
                prev_conv = 100 * prev_sig.get("total", 0) / prev_audience["visitors"]
            parts.append(_line(
                f"📊 Конверсия «посетитель → регистрация»: {fmt_pct(conv, 2)}"
                + (f" (прошлый период {fmt_pct(prev_conv, 2)})" if prev_conv is not None else ""),
                ("по каналам: " + conversion_by_channel(sig, data.get("visitors_by_channel")))
                if conversion_by_channel(sig, data.get("visitors_by_channel")) else "",
            ))
        back7 = sig.get("returned_7d") or {}
        if back7.get("eligible"):
            back_line = f"🔁 Вернулись за 7 дней: {fmt_int(back7['returned'])} из {fmt_int(back7['eligible'])} ({fmt_pct(back7['pct'], 0)})"
            if kind == "monthly":
                back30 = sig.get("returned_30d") or {}
                if back30.get("eligible"):
                    back_line += f" · за 30 дней: {fmt_int(back30['returned'])} из {fmt_int(back30['eligible'])} ({fmt_pct(back30['pct'], 0)})"
            parts.append(back_line)
        if sig.get("median_days_to_signup") is not None:
            parts.append(f"⏳ Дней от первого визита до регистрации (медиана): {fmt_pct(sig['median_days_to_signup'], 1).rstrip('%')}")
    else:
        notes.append("регистрации: данных нет")

    if funnel:
        text = funnel_line(funnel)
        if text:
            weak = weakest_text(funnel)
            parts.append(text + (f" ({weak})" if weak else ""))
    else:
        notes.append("воронка: данных нет")

    if usage is not None:
        parts += usage_lines(usage, prev_usage)
    else:
        notes.append("использование функций: данных нет")

    pwa = data.get("pwa")
    if pwa:
        totals = pwa.get("totals") or {}
        if totals.get("installs") or totals.get("launch_visitors"):
            parts.append(f"📲 Установки приложения: {fmt_int(totals.get('installs'))} "
                         f"(запусков из иконки: {fmt_int(totals.get('launch_visitors'))})")

    gaps = data.get("search_gaps")
    if gaps and gaps.get("top"):
        top = ", ".join(f"«{escape(item['q'])}» ×{item['searches']}" for item in gaps["top"][:5])
        parts.append(f"🕳 Поиск без результатов: {top}")

    site = reliability_line(rel)
    if site:
        parts.append(site)

    en = data.get("english")
    if en:
        parts.append("🇬🇧 Английская версия: " + en)

    if kind == "monthly" and sig:
        cohort_bits = []
        landing = ", ".join(f"{escape(page)} ×{n}" for page, n in list((sig.get("landing_top") or {}).items())[:5])
        if landing:
            cohort_bits.append(f"лучшие первые страницы: {landing}")
        if cohort_bits:
            parts.append("🧲 " + "; ".join(cohort_bits))

    if notes:
        parts.append("ℹ️ " + "; ".join(notes))

    details = detail_lines_for_day(sig, usage, funnel)
    if kind == "monthly" and usage and usage.get("has_data"):
        for group in ("share", "favorite", "subscribe"):
            bucket = (usage["groups"].get(group) or {}).get("surface") or {}
            line = _split_block(f"{GROUP_LABELS_RU[group].capitalize()} по разделам", bucket, SURFACE_LABELS, 5)
            if line:
                details.append(line)
    if prev is not None:
        details.append(f"Сравнение с периодом {period_title(prev)}")
    block = expandable(details)
    if block:
        parts.append(block)
    return "\n".join(parts)


def format_signups_reply(windows: dict[str, dict | None]) -> str:
    """Ответ кнопки «Регистрации»: 7 дней, 30 дней и всё время."""
    lines = ["🌍 <b>Регистрации</b>"]
    details: list[str] = []
    for label, sig in windows.items():
        if sig is None:
            lines.append(f"{label}: данных нет")
            continue
        total = int(sig.get("total") or 0)
        if not total:
            lines.append(f"{label}: регистраций не было")
            continue
        foreign = int((sig.get("origin") or {}).get("foreign", 0))
        lines.append(_line(
            f"{label}: {fmt_int(total)}",
            count_list(sig.get("locale"), LOCALE_LABELS, limit=3),
            f"вне РФ {fmt_int(foreign)}" if foreign else "",
        ))
        for title, key, labels in (("Канал", "channel", CHANNEL_LABELS), ("Устройство", "device", DEVICE_LABELS),
                                   ("Что подтолкнуло", "trigger", TRIGGER_LABELS), ("Способ", "method", METHOD_LABELS),
                                   ("Страны вне РФ", "foreign_countries", {})):
            text = count_list(sig.get(key), labels, limit=6)
            if text:
                details.append(f"{label} — {title.lower()}: {text}")
        unknown = int(sig.get("unknown_locale") or 0)
        if unknown:
            details.append(f"{label}: у {fmt_int(unknown)} из {fmt_int(total)} язык сайта не определён")
    out = "\n".join(lines)
    block = expandable(details)
    return out + ("\n" + block if block else "")


def format_funnel_reply(funnel: dict | None, period: Period) -> str:
    if not funnel:
        return "🧭 <b>Воронка</b>\nДанных нет."
    lines = [f"🧭 <b>Воронка за {period_title(period)}</b>", funnel_line(funnel) or "Шагов с данными нет."]
    for text in (dropped_text(funnel), weakest_text(funnel)):
        if text:
            lines.append(text[0].upper() + text[1:])
    details = []
    for locale, label in (("ru", "Русская версия"), ("en", "Английская версия")):
        cell = (funnel.get("by_locale") or {}).get(locale) or {}
        if any(cell.values()):
            details.append(f"{label}: " + ", ".join(f"{FUNNEL_SHORT[k]} {fmt_int(v)}" for k, v in cell.items() if v))
    block = expandable(details)
    return "\n".join(lines) + ("\n" + block if block else "")


def format_goals_reply(windows: dict[str, dict | None]) -> str:
    """Ответ кнопки «Цели»: группы действий за вчера, 7 и 30 дней."""
    lines = ["🎯 <b>Что делали на сайте</b> (без роботов и своих)"]
    for label, usage in windows.items():
        if usage is None or not usage.get("has_data"):
            lines.append(f"{label}: данных нет")
            continue
        text = usage_lines(usage)[0].replace("🎯 Что делали: ", "")
        lines.append(f"{label}: {text}")
    details: list[str] = []
    last = next((u for u in reversed(list(windows.values())) if u and u.get("has_data")), None)
    if last:
        for group in REPORT_GROUPS:
            bucket = last["groups"].get(group) or {}
            if not bucket.get("actions"):
                continue
            by_locale = count_list(bucket.get("locale"), {"ru": "русский", "en": "английский", "unknown": "язык неизвестен"}, limit=3)
            by_surface = count_list(bucket.get("surface"), SURFACE_LABELS, limit=4)
            by_device = count_list(bucket.get("device"), DEVICE_LABELS, limit=3)
            details.append(f"{GROUP_LABELS_RU[group].capitalize()}: " + _line(by_locale, by_device, by_surface))
    block = expandable(details)
    return "\n".join(lines) + ("\n" + block if block else "")


# ---------------------------------------------------------------------------
# Сборка данных
# ---------------------------------------------------------------------------

async def _guarded(name: str, factory: Callable[[Any], Awaitable[Any]], timeout: float = BLOCK_TIMEOUT_S) -> Any:
    """Одна витрина в своей сессии: сбой и таймаут дают None, отчёт продолжается."""
    async def run():
        async with analytics_session() as db:
            return await factory(db)

    try:
        return await asyncio.wait_for(run(), timeout)
    except Exception:  # noqa: BLE001 — в т.ч. asyncio.TimeoutError
        logger.warning("Telegram report block %s failed", name, exc_info=True)
        return None


def day_period(day: date) -> Period:
    return resolve_period("custom", day, day)


def week_period(end_day: date) -> tuple[Period, Period]:
    """Неделя МСК, закончившаяся в `end_day` (включительно), и предыдущая."""
    cur = resolve_period("custom", end_day - timedelta(days=6), end_day)
    prev = resolve_period("custom", end_day - timedelta(days=13), end_day - timedelta(days=7))
    return cur, prev


def month_periods(today: date) -> tuple[Period, Period]:
    """Предыдущий календарный месяц (МСК) и месяц перед ним."""
    first_this = today.replace(day=1)
    last_prev = first_this - timedelta(days=1)
    first_prev = last_prev.replace(day=1)
    last_before = first_prev - timedelta(days=1)
    first_before = last_before.replace(day=1)
    return (resolve_period("custom", first_prev, last_prev),
            resolve_period("custom", first_before, last_before))


async def collect_digest_v2(day: date) -> dict[str, Any]:
    from app.services import analytics_marts as m

    period = day_period(day)
    signups, usage, funnel, reliability = await asyncio.gather(
        _guarded("signups", lambda db: m.mart_signups(db, period)),
        _guarded("usage", lambda db: m.mart_goal_usage(db, period)),
        _guarded("funnel", lambda db: m.mart_signup_funnel(db, period)),
        _guarded("reliability", lambda db: m.mart_reliability(db, period)),
    )
    return {"signups": signups, "usage": usage, "funnel": funnel, "reliability": reliability}


async def digest_v2_lines(day: date) -> list[str]:
    """Блоки v2 для дайджеста за `day`; пусто, если ни одна витрина не ответила."""
    data = await collect_digest_v2(day)
    if not any(v is not None for v in data.values()):
        return []
    return format_digest_v2(**data)


async def _visitors_by_channel(db, period: Period) -> dict[str, int]:
    from sqlalchemy import func, select

    from app.models import ServerSession

    rows = (await db.execute(
        select(ServerSession.channel, func.count(func.distinct(ServerSession.visitor_id_hash)))
        .where(ServerSession.day >= period.start_date, ServerSession.day <= period.end_date,
               ServerSession.is_bot.is_(False), ServerSession.is_internal.is_(False))
        .group_by(ServerSession.channel)
    )).all()
    return {(channel or "unknown"): int(n) for channel, n in rows}


def _english_summary(sig: dict | None, funnel: dict | None, audience: dict | None) -> str:
    bits = []
    en_visitors = ((funnel or {}).get("by_locale") or {}).get("en", {})
    if en_visitors.get("visitors"):
        bits.append(f"посетители {fmt_int(en_visitors['visitors'])}")
    en_signups = ((sig or {}).get("locale") or {}).get("en")
    if en_signups:
        bits.append(f"регистрации {fmt_int(en_signups)}")
    if en_visitors.get("wall"):
        bits.append(f"упёрлись в лимит {fmt_int(en_visitors['wall'])}")
    return ", ".join(bits)


async def collect_period_report(period: Period, prev: Period) -> dict[str, Any]:
    from app.services import analytics_marts as m

    (signups, prev_signups, audience, prev_audience, funnel, usage, prev_usage, reliability, pwa, gaps, by_channel
     ) = await asyncio.gather(
        _guarded("signups", lambda db: m.mart_signups(db, period)),
        _guarded("prev_signups", lambda db: m.mart_signups(db, prev)),
        _guarded("audience", lambda db: m.mart_audience_geo(db, period)),
        _guarded("prev_audience", lambda db: m.mart_audience_geo(db, prev)),
        _guarded("funnel", lambda db: m.mart_signup_funnel(db, period)),
        _guarded("usage", lambda db: m.mart_goal_usage(db, period)),
        _guarded("prev_usage", lambda db: m.mart_goal_usage(db, prev)),
        _guarded("reliability", lambda db: m.mart_reliability(db, period.tail(7))),
        _guarded("pwa", lambda db: m.mart_pwa_installs(db, period)),
        _guarded("search_gaps", lambda db: m.mart_search_gaps(db, period)),
        _guarded("visitors_by_channel", lambda db: _visitors_by_channel(db, period)),
    )
    return {
        "period": period, "prev_period": prev, "signups": signups, "prev_signups": prev_signups,
        "audience": audience, "prev_audience": prev_audience, "funnel": funnel, "usage": usage,
        "prev_usage": prev_usage, "reliability": reliability, "pwa": pwa, "search_gaps": gaps,
        "visitors_by_channel": by_channel, "english": _english_summary(signups, funnel, audience),
    }


async def build_weekly_report(today: date | None = None) -> str:
    """Неделя МСК, закончившаяся вчера (отчёт идёт в понедельник утром)."""
    today = today or today_msk()
    cur, prev = week_period(today - timedelta(days=1))
    return format_period_report(await collect_period_report(cur, prev), kind="weekly")


async def build_monthly_report(today: date | None = None) -> str:
    today = today or today_msk()
    cur, prev = month_periods(today)
    return format_period_report(await collect_period_report(cur, prev), kind="monthly")


async def _send_to_recipients(text: str, kind: str) -> dict[str, bool]:
    """Всем получателям дайджеста; `kind` различает виды сообщений для досылки и архива."""
    from app.services.alerting import digest_recipients, send_telegram

    return {cid: await send_telegram(text, chat_id=cid, kind=kind) for cid in digest_recipients()}


async def weekly_report_job() -> None:
    """Недельный отчёт (понедельник 09:20 МСК). Выключен флагом `telegram_weekly_enabled`."""
    if not (settings.telegram_bot_token and settings.telegram_chat_id):
        return
    text = await build_weekly_report()
    results = await _send_to_recipients(text, "weekly_report")
    logger.info("Weekly report delivered: %s", results)


async def monthly_report_job() -> None:
    """Месячный отчёт (1-е число 09:45 МСК). Выключен флагом `telegram_monthly_enabled`."""
    if not (settings.telegram_bot_token and settings.telegram_chat_id):
        return
    text = await build_monthly_report()
    results = await _send_to_recipients(text, "monthly_report")
    logger.info("Monthly report delivered: %s", results)


# ---------------------------------------------------------------------------
# Ответы кнопок бота
# ---------------------------------------------------------------------------

async def signups_button_text() -> str:
    from app.services import analytics_marts as m

    today = today_msk()
    windows = {
        "7 дней": resolve_period("custom", today - timedelta(days=6), today),
        "30 дней": resolve_period("custom", today - timedelta(days=29), today),
        "Всё время": resolve_period("custom", date(2026, 1, 1), today),
    }
    results = {}
    for label, period in windows.items():
        results[label] = await _guarded(f"signups:{label}", lambda db, p=period: m.mart_signups(db, p))
    return format_signups_reply(results)


async def funnel_button_text() -> str:
    from app.services import analytics_marts as m

    today = today_msk()
    period = resolve_period("custom", today - timedelta(days=6), today)
    funnel = await _guarded("funnel", lambda db: m.mart_signup_funnel(db, period))
    return format_funnel_reply(funnel, period)


async def goals_button_text() -> str:
    from app.services import analytics_marts as m

    today = today_msk()
    windows = {
        "Вчера": day_period(today - timedelta(days=1)),
        "7 дней": resolve_period("custom", today - timedelta(days=6), today),
        "30 дней": resolve_period("custom", today - timedelta(days=29), today),
    }
    results = {}
    for label, period in windows.items():
        results[label] = await _guarded(f"goals:{label}", lambda db, p=period: m.mart_goal_usage(db, p))
    return format_goals_reply(results)
