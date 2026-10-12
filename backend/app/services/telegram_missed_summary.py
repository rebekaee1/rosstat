"""Сводка «что не дошло до Telegram» одним сообщением владельцу (круг 13, задача T2).

Когда сервер неделю не мог соединиться с api.telegram.org, часть сообщений осталась в
архиве `telegram_outbox` как `ok=false`. Досылать каждое отдельно (десятки сообщений
всем прежним адресатам, в том числе технические и с чужими именами и почтами) нельзя и
не нужно: владельцу достаточно одной сгруппированной сводки.

Что делает модуль (чистые функции, без сети и без базы):
- находит недоставленные логические сообщения по той же логике, что и `telegram_resend`
  (вид + чат + хеш текста; доставленным считается повтор с `ok=true` не раньше первой
  неудачи), затем складывает одинаковые тексты разных чатов в одно событие;
- группирует по видам и пересказывает каждую группу числами и названиями технических
  объектов (задачи планировщика, коды показателей, группы адресов);
- **не переносит персональные данные**: имён, почт, телефонов, IP, текста регистраций нет —
  только число регистраций, способ входа и язык сайта; свободный текст проходит `scrub_text`;
- укладывает итог в один `sendMessage` (до 4000 знаков): подробности под спойлер, при
  нехватке места подробности отбрасываются, а не режутся посередине.

Отправку делает скрипт `scripts/resend-missed-summary.py` (по умолчанию пробный прогон).
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from html import escape
from typing import Iterable

from app.services.pii_scrub import scrub_text
from app.services.signup_attribution import METHOD_LABELS_RU, parse_new_user_message
from app.services.telegram_resend import OutboxRow, is_permanent_failure, logical_key

MSK = timezone(timedelta(hours=3))
SUMMARY_KIND = "missed_summary"
MESSAGE_LIMIT = 4000  # запас от жёсткого лимита Bot API (4096)

# Виды, которые в сводку не входят: ответы кнопок бота и файлы приходят по запросу человека,
# а сама сводка не должна пересказывать себя.
SKIPPED_KINDS = frozenset({"bot_reply", "bot_document", "bot_menu", SUMMARY_KIND})

_MONTHS = ("янв.", "февр.", "марта", "апр.", "мая", "июня", "июля", "авг.", "сент.", "окт.", "нояб.", "дек.")

_MONTHS_GENITIVE = ("января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа",
                    "сентября", "октября", "ноября", "декабря")

# (ключ группы, эмодзи, заголовок) в порядке показа.
CATEGORIES = (
    ("anomaly", "⚠️", "Аномалии аналитики"),
    ("spike", "🔴", "Всплески ошибок сервера (5xx)"),
    ("signup", "🌍", "Новые регистрации"),
    ("job", "🛠", "Сбои фоновых задач"),
    ("pulse", "🛰", "Пульс платформы"),
    ("etl", "📥", "Ежедневная выгрузка данных"),
    ("world", "🌐", "Обновление мировых данных"),
    ("digest", "📊", "Ежедневные дайджесты"),
    ("zero", "🟡", "Парсер вернул ноль точек"),
    ("other", "📌", "Прочее"),
)
_KIND_TO_CATEGORY = {
    "analytics_anomaly": "anomaly", "audience_alert": "anomaly",
    "http_5xx_spike": "spike",
    "new_user": "signup", "login": "signup",
    "scheduler_alert": "job",
    "pulse_digest": "pulse",
    "etl_summary": "etl", "etl_failure": "etl",
    "world_ingest_summary": "world",
    "digest": "digest",
    "zero_parse": "zero",
}


@dataclass(frozen=True)
class Missed:
    """Одно недоставленное событие (одинаковые тексты разных чатов сложены)."""
    first_id: int
    at: datetime          # UTC без пояса: когда пытались отправить впервые
    kind: str
    text: str
    chats: int

    @property
    def category(self) -> str:
        return _KIND_TO_CATEGORY.get(self.kind, "other")

    @property
    def day_msk(self) -> date:
        return (self.at.replace(tzinfo=timezone.utc).astimezone(MSK)).date()


# ---------------------------------------------------------------------------
# Что не доставлено
# ---------------------------------------------------------------------------

def find_missed(rows: Iterable[OutboxRow]) -> list[Missed]:
    """Недоставленные события. `rows` — строки архива за нужное окно, любой порядок."""
    groups: dict[str, list[OutboxRow]] = defaultdict(list)
    for row in sorted(rows, key=lambda r: r.id):
        if row.kind in SKIPPED_KINDS or not (row.text or "").strip():
            continue
        groups[logical_key(row.kind, row.chat_id, row.text)].append(row)

    merged: dict[tuple[str, str], dict] = {}
    for items in groups.values():
        failed = [r for r in items if not r.ok]
        if not failed:
            continue
        first = failed[0]
        if any(r.ok and r.sent_at >= first.sent_at for r in items):
            continue  # дошло позже
        if first.error == "redelivered by resend job":
            continue
        key = (first.kind, first.text)
        cell = merged.setdefault(key, {"first": first, "chats": set()})
        cell["chats"].add(first.chat_id)
        if first.id < cell["first"].id:
            cell["first"] = first
    out = [
        Missed(first_id=c["first"].id, at=c["first"].sent_at, kind=c["first"].kind,
               text=c["first"].text, chats=len(c["chats"]))
        for c in merged.values()
    ]
    out.sort(key=lambda m: m.first_id)
    return out


def permanent_failures(rows: Iterable[OutboxRow]) -> int:
    """Сколько строк с постоянной ошибкой (чат не тот и т.п.): для справки в отчёте скрипта."""
    return sum(1 for r in rows if not r.ok and is_permanent_failure(r.error))


# ---------------------------------------------------------------------------
# Пересказ по группам
# ---------------------------------------------------------------------------

def day_label(day: date) -> str:
    return f"{day.day} {_MONTHS[day.month - 1]}"


def days_text(days: Iterable[date]) -> str:
    """«4, 5 и 8 окт.»: те же месяцы склеиваем, разные месяцы перечисляем полностью."""
    ordered = sorted(set(days))
    if not ordered:
        return ""
    if len({(d.year, d.month) for d in ordered}) == 1:
        month = _MONTHS[ordered[0].month - 1]
        nums = [str(d.day) for d in ordered]
        head = ", ".join(nums[:-1]) + " и " + nums[-1] if len(nums) > 1 else nums[0]
        return f"{head} {month}"
    return ", ".join(day_label(d) for d in ordered)


def _plural(n: int, one: str, few: str, many: str) -> str:
    n10, n100 = n % 10, n % 100
    if n10 == 1 and n100 != 11:
        return one
    if 2 <= n10 <= 4 and not 12 <= n100 <= 14:
        return few
    return many


def _clip(text: str, limit: int = 120) -> str:
    text = scrub_text(" ".join(str(text).split()))
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _anomaly_facts(items: list[Missed]) -> list[str]:
    traffic, goals, memory, crawl, other = [], [], [], [], []
    for m in items:
        low = m.text.lower()
        if "трафик часа упал" in low:
            share = re.search(r"\((\d+)%\)", m.text)
            traffic.append((m, int(share.group(1)) if share else None))
        elif "goal_taxonomy" in low or "цели метрики разошлись" in low:
            goals.append(m)
        elif "память контейнера" in low:
            pct = re.search(r"(\d+)% лимита", m.text)
            name = re.search(r"контейнера\s+(\S+)", m.text)
            memory.append((m, int(pct.group(1)) if pct else None, name.group(1) if name else ""))
        elif "обход" in low:
            crawl.append(m)
        else:
            other.append(m)
    facts = []
    if traffic:
        shares = [s for _, s in traffic if s is not None]
        low = f", самое сильное падение до {min(shares)}% от обычного" if shares else ""
        facts.append(f"трафик часа упал {len(traffic)} {_plural(len(traffic), 'раз', 'раза', 'раз')} "
                     f"({days_text(m.day_msk for m, _ in traffic)}{low})")
    if goals:
        facts.append(f"цели Метрики расходятся с таксономией: {len(goals)} {_plural(len(goals), 'раз', 'раза', 'раз')} "
                     f"({days_text(m.day_msk for m in goals)})")
    if memory:
        names = sorted({n for _, _, n in memory if n})
        peak = max((p for _, p, _ in memory if p is not None), default=None)
        facts.append(f"память {', '.join(names) or 'контейнера'} до {peak}% лимита: {len(memory)} "
                     f"{_plural(len(memory), 'раз', 'раза', 'раз')} ({days_text(m.day_msk for m, _, _ in memory)})")
    if crawl:
        facts.append(f"обход сайта поисковиком просел {len(crawl)} {_plural(len(crawl), 'раз', 'раза', 'раз')}")
    for m in other[:3]:
        facts.append(_clip(m.text.splitlines()[-1] if m.text.splitlines() else m.text, 90))
    return facts


_PATH_RE = re.compile(r"последний путь:\s*(\S+?)\)?\s*$", re.MULTILINE)


def _spike_facts(items: list[Missed]) -> list[str]:
    from app.services.analytics_marts import server_error_group

    names = {"seo": "страницы для поисковиков", "api": "запросы к данным", "og": "картинки превью", "other": "остальное"}
    groups: Counter = Counter()
    for m in items:
        found = _PATH_RE.search(m.text.replace("\n", " \n"))
        groups[server_error_group(found.group(1) if found else None)] += 1
    where = ", ".join(f"{names[g]} {n}" for g, n in groups.most_common())
    return [f"{days_text(m.day_msk for m in items)}; затронуто: {where}"]


def _signup_facts(items: list[Missed]) -> list[str]:
    methods: Counter = Counter()
    locales: Counter = Counter()
    for m in items:
        info = parse_new_user_message(m.text)
        methods[METHOD_LABELS_RU.get(info.get("method", ""), "способ неизвестен")] += 1
        locales[{"ru": "русская версия", "en": "английская версия"}.get(info.get("site_locale", ""), "язык неизвестен")] += 1
    facts = [", ".join(f"{k} {v}" for k, v in locales.most_common()),
             "способ входа: " + ", ".join(f"{k} {v}" for k, v in methods.most_common())]
    return facts


def _job_name(text: str) -> str:
    found = re.search(r"(?:Job|Задача):\s*(?:<code>)?([\w\-.:]+)", text)
    return found.group(1) if found else "задача"


def _job_cause(text: str) -> str:
    low = text.lower()
    if "statement timeout" in low or "querycanceled" in low:
        return "запрос к базе превысил лимит времени"
    if "redis" in low and "timeout" in low:
        return "таймаут чтения из redis"
    if "timeout" in low or "timed out" in low:
        return "таймаут соединения"
    if "misfire" in low or "не запустилась" in low or "пропуск" in low:
        return "задача не запустилась в срок"
    return "ошибка выполнения"


def _job_facts(items: list[Missed]) -> list[str]:
    by_job: dict[str, list[Missed]] = defaultdict(list)
    for m in items:
        by_job[_job_name(m.text)].append(m)
    facts = []
    for job, rows in sorted(by_job.items(), key=lambda kv: -len(kv[1])):
        causes = Counter(_job_cause(m.text) for m in rows)
        cause = ", ".join(c for c, _ in causes.most_common(2))
        facts.append(f"{job} ×{len(rows)} ({days_text(m.day_msk for m in rows)}): {cause}")
    return facts


def _pulse_facts(items: list[Missed]) -> list[str]:
    reports = set()
    for m in items:
        found = re.search(r"Пульс платформы\s*[—-]\s*(\d{4}-\d{2}-\d{2})", m.text)
        if found:
            reports.add(date.fromisoformat(found.group(1)))
    dates = f"отчёты за {days_text(reports)}; " if reports else ""
    return [f"{dates}{len(items)} {_plural(len(items), 'часть', 'части', 'частей')} текста, полный текст в архиве сообщений"]


def _etl_facts(items: list[Missed]) -> list[str]:
    facts = []
    for m in items:
        total = re.search(r"(?:Total|Всего):\s*(\d+)", m.text)
        upd = re.search(r"(?:Updated|обновлено):\s*(\d+)", m.text)
        fail = re.search(r"(?:Failed|с ошибкой):\s*(\d+)", m.text)
        dur = re.search(r"(?:Duration|Длительность):\s*(\d+)", m.text)
        bit = f"{day_label(m.day_msk)}: всего {total.group(1) if total else '?'}, обновлено {upd.group(1) if upd else '?'}"
        if fail and int(fail.group(1)):
            bit += f", с ошибкой {fail.group(1)}"
        if dur and int(dur.group(1)) >= 3600:
            bit += f", шла {round(int(dur.group(1)) / 3600, 1)} ч".replace(".", ",")
        facts.append(bit)
    return facts


def _world_facts(items: list[Missed]) -> list[str]:
    facts = []
    for m in items:
        head = re.search(r"Обновление:\s*([^\n]+)", m.text)
        result = re.search(r"Итог:\s*([^\n]+)", m.text)
        errors = re.search(r"(?:Ошибок|Ошибки):\s*(\d+)", m.text)
        bit = f"{day_label(m.day_msk)}: {_clip(head.group(1), 60) if head else 'обновление'}"
        if result:
            bit += f", {result.group(1).strip().lower()}"
        if errors and int(errors.group(1)):
            bit += f", ошибок {errors.group(1)}"
        facts.append(bit)
    return facts


def _digest_facts(items: list[Missed]) -> list[str]:
    facts = []
    seen: set[str] = set()
    for m in items:
        title = re.search(r"дайджест за (\d{4}-\d{2}-\d{2})", m.text)
        label = title.group(1) if title else day_label(m.day_msk)
        if label in seen:
            continue
        seen.add(label)
        users = re.search(r"Пользователи: всего (\d+), \+(\d+) за сутки", m.text)
        search = re.search(r"Поиск:</b>\s*ввод (\d+)|Поиск: ввод (\d+)", m.text)
        bit = f"за {label}"
        if users:
            bit += f": пользователей {users.group(1)} (+{users.group(2)})"
        if search:
            bit += f", запросов в поиске {search.group(1) or search.group(2)}"
        facts.append(bit)
    return facts


def _zero_facts(items: list[Missed]) -> list[str]:
    codes = []
    for m in items:
        found = re.search(r"(?:Indicator|Показатель):\s*(?:<code>)?([\w\-]+)", m.text)
        if found:
            codes.append(found.group(1))
    return [", ".join(codes)] if codes else []


def _other_facts(items: list[Missed]) -> list[str]:
    kinds = Counter(m.kind for m in items)
    return [", ".join(f"{k} ×{n}" for k, n in kinds.most_common())]


_FACTS = {
    "anomaly": _anomaly_facts, "spike": _spike_facts, "signup": _signup_facts, "job": _job_facts,
    "pulse": _pulse_facts, "etl": _etl_facts, "world": _world_facts, "digest": _digest_facts,
    "zero": _zero_facts, "other": _other_facts,
}


# ---------------------------------------------------------------------------
# Сборка сообщения
# ---------------------------------------------------------------------------

def build_summary(missed: list[Missed], *, since: date, until: date) -> str:
    """Одно сообщение с группами. Пустых строк нет, длина ≤ `MESSAGE_LIMIT`."""
    if (since.year, since.month) == (until.year, until.month):
        period = f"с {since.day} по {until.day} {_MONTHS_GENITIVE[until.month - 1]} {until.year}"
    else:
        period = (f"с {since.day} {_MONTHS_GENITIVE[since.month - 1]} "
                  f"по {until.day} {_MONTHS_GENITIVE[until.month - 1]} {until.year}")
    if not missed:
        return f"📬 <b>Что мы пропустили {period}</b>\nНедоставленных сообщений в архиве нет."
    chats = max((m.chats for m in missed), default=1)
    head = [
        f"📬 <b>Что мы пропустили {period}</b>",
        f"Всего {len(missed)} {_plural(len(missed), 'сообщение', 'сообщения', 'сообщений')} не дошло: "
        "сервер не мог соединиться с Telegram"
        + ("; одинаковые для нескольких чатов сложены в одно." if chats > 1 else "."),
    ]
    by_cat: dict[str, list[Missed]] = defaultdict(list)
    for m in missed:
        by_cat[m.category].append(m)

    body: list[str] = []
    details: list[str] = []
    for key, icon, title in CATEGORIES:
        items = by_cat.get(key)
        if not items:
            continue
        facts = [f for f in _FACTS[key](items) if f]
        if key in ("job", "etl", "world", "digest", "anomaly") and len(facts) > 1:
            body.append(f"{icon} <b>{title}</b>: {len(items)}")
            details.extend(f"{title}: {escape(f)}" for f in facts)
        else:
            tail = "; ".join(facts)
            body.append(f"{icon} <b>{title}</b>: {len(items)}" + (f" — {escape(tail)}" if tail else ""))

    timeline = Counter(m.day_msk for m in missed)
    day_line = "По дням: " + ", ".join(f"{day_label(d)} {n}" for d, n in sorted(timeline.items()))
    if timeline:
        body.append(day_line)

    text = "\n".join(head + body)
    block = "<blockquote expandable>" + "\n".join(details) + "</blockquote>" if details else ""
    full = text + ("\n" + block if block else "")
    if len(full) <= MESSAGE_LIMIT:
        return full
    if len(text) <= MESSAGE_LIMIT:
        return text
    return text[: MESSAGE_LIMIT - 1].rsplit("\n", 1)[0]
