"""Спокойный режим Telegram: в личку владельца — только срочное, остальное — утренней сводкой.

Решение владельца 08.11.2026: «меня очень напрягает, что в бот куча всего приходит, и у меня паника начинается,
потому что там какие-то ошибки и что-то красное». До этого технические алерты (выгрузка данных, всплески 5xx, сторож
хоста, сбои задач планировщика, просрочки рядов) приходили сразу и красным, хотя почти всегда либо проходили сами,
либо были вне проекта (Росстат на техработах, Минфин режет сеть Timeweb), и делать владельцу было нечего.

Как устроено:

* `HELD_KINDS` — технические виды. `send_telegram` их не отправляет, а кладёт в архив `telegram_outbox` строкой
  `method="held"` (досылка смотрит только `sendMessage`, поэтому отложенное не уходит повтором). Архив по-прежнему
  полный: агент читает его так же, как раньше, а `analytics_marts._server_5xx_spikes` считает всплески по `kind`.
* Срочное идёт сразу: `site_down` / `site_up` (сайт отдаёт ошибки людям дольше `SITE_DOWN_AFTER_SECONDS` и снова
  работает), `disk_space` (кончается место — нужен человек), `prod_config_alert` (небезопасная настройка после выкладки).
  Люди и отчёты (регистрации, обратная связь, дайджест, Пульс, недельные отчёты) не трогаются.
* `calm_morning_summary_job` в 09:10 МСК присылает одно сообщение за сутки: первой строкой — нужно ли что-то делать,
  потом сайт, данные и свёрнутые подробности. Без красного: красный цвет только у срочного.

Выключатель — `settings.telegram_calm_mode` (по умолчанию включён). Отложенное отправляется только в главный чат
(`telegram_chat_id`): сообщения в чаты получателей отчётов не откладываются.
"""
from __future__ import annotations

import logging
import re
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from html import escape
from typing import Iterable

from app.config import settings

logger = logging.getLogger(__name__)

MSK = timezone(timedelta(hours=3))
HELD_METHOD = "held"
HELD_ERROR = "held: утренняя сводка"
SUMMARY_KIND = "calm_summary"
MESSAGE_LIMIT = 4000

# Технические виды: в личку не идут, попадают в утреннюю сводку.
HELD_KINDS = frozenset({
    "alert",  # вид по умолчанию у `send_telegram`
    "etl_failure", "etl_alert", "etl_summary", "world_ingest_summary", "zero_parse",
    "staleness", "freshness_watchdog", "forecast_issue",
    "scheduler_alert", "job_lease_lost", "ticker_stale",
    "http_5xx_spike", "load_shed", "rate_limit_alert",
    "host_pressure", "host_memory",
    "acquisition_alert", "recrawl_alert", "analytics_anomaly", "audience_alert",
})
# Срочное: сразу в личку (перечислено для документации и тестов; всё не из HELD_KINDS и так идёт сразу).
URGENT_KINDS = frozenset({"site_down", "site_up", "disk_space", "prod_config_alert"})

assert not HELD_KINDS & URGENT_KINDS

# Порог «сайт лежит»: настоящие ошибки 5xx (не намеренный сброс нагрузки) идут без перерыва дольше 3 минут
# и в сумме держатся дольше 10 минут.
SITE_DOWN_AFTER_SECONDS = 600
SITE_DOWN_GAP_SECONDS = 180


def should_hold(kind: str, chat_id: str | None) -> bool:
    """True — не слать сейчас, отложить в утреннюю сводку."""
    if not getattr(settings, "telegram_calm_mode", False) or kind not in HELD_KINDS:
        return False
    primary = str(settings.telegram_chat_id or "")
    return chat_id is None or str(chat_id) == primary


async def hold(message: str, chat_id: str | None, kind: str) -> bool:
    """Записать отложенное сообщение в архив. True — запись есть (для вызывающих это «доставлено»)."""
    from app.services.telegram_outbox import archive

    await archive(
        chat_id=str(chat_id or settings.telegram_chat_id or ""), method=HELD_METHOD, kind=kind,
        text=message, ok=False, error=HELD_ERROR,
    )
    logger.info("Telegram: %s отложено в утреннюю сводку (спокойный режим)", kind)
    return True


# ---------------------------------------------------------------------------
# «Сайт не открывается» по настоящим 5xx
# ---------------------------------------------------------------------------

_DOWN_SINCE_KEY = "fe:site_down:since"
_DOWN_ALERTED_KEY = "fe:site_down:alerted"


async def note_error_spike(now: float, count: int, path: str) -> None:
    """Вызывается на каждый ответ 5xx, пока сумма за окно выше порога. Шлёт «сайт не открывается» один раз.

    Перерыв в ошибках дольше `SITE_DOWN_GAP_SECONDS` начинает отсчёт заново.
    """
    from app.core.cache import get_state_redis
    from app.services.alerting import send_telegram

    r = await get_state_redis()
    since = now
    raw = await r.get(_DOWN_SINCE_KEY)
    if raw:
        try:
            prev_since, prev_last = (float(x) for x in str(raw).split(":", 1))
        except ValueError:
            prev_since, prev_last = now, now
        if 0 <= now - prev_last <= SITE_DOWN_GAP_SECONDS:
            since = prev_since
    # Значение «начало:последняя ошибка»; ключ сам исчезает после перерыва (его ждёт `check_site_recovered`).
    await r.set(_DOWN_SINCE_KEY, f"{since}:{now}", ex=SITE_DOWN_GAP_SECONDS + 60)
    minutes = int((now - since) // 60)
    if now - since < SITE_DOWN_AFTER_SECONDS:
        return
    # Флаг «писали» живёт, пока не пришло «снова работает» (его снимает `check_site_recovered`); сутки — страховка.
    if not await r.set(_DOWN_ALERTED_KEY, str(since), nx=True, ex=24 * 3600):
        return
    await send_telegram(site_down_text(minutes, count, path), kind="site_down")


async def check_site_recovered() -> None:
    """Раз в минуту (сторож хоста): писали «не открывается», а ошибок больше нет — пишем «снова работает»."""
    from app.core.cache import get_state_redis
    from app.services.alerting import send_telegram

    r = await get_state_redis()
    alerted = await r.get(_DOWN_ALERTED_KEY)
    if not alerted or await r.exists(_DOWN_SINCE_KEY):
        return
    await r.delete(_DOWN_ALERTED_KEY)
    minutes = max(1, int((datetime.now(timezone.utc).timestamp() - float(alerted)) // 60))
    await send_telegram(site_up_text(minutes), kind="site_up")


def site_down_text(minutes: int, count: int, path: str) -> str:
    return (
        "🔴 <b>Сайт не открывается у части людей</b>\n"
        f"Уже около {minutes} мин сервер отвечает ошибкой ({count} ошибок за последние 5 мин). "
        "Сам не прошёл, поэтому пишу сразу.\n"
        "Что сделать: открой Claude и напиши «сайт лежит, разберись». "
        "Когда сайт снова заработает, пришлю отдельное сообщение."
        f"\n<i>последний адрес: {escape(path[:120])}</i>"
    )


def site_up_text(minutes: int) -> str:
    return f"🟢 <b>Сайт снова работает</b>\nПерерыв длился около {minutes} мин. Делать ничего не нужно."


# ---------------------------------------------------------------------------
# Утренняя сводка
# ---------------------------------------------------------------------------

_MONTHS_GENITIVE = ("января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа",
                    "сентября", "октября", "ноября", "декабря")
_TAG_RE = re.compile(r"<[^>]+>")
_EMOJI_RE = re.compile(r"^[\W_]+", re.UNICODE)

# Группы сводки: (ключ, заголовок, виды). Порядок — порядок показа.
GROUPS = (
    ("site", "Сайт", ("http_5xx_spike", "load_shed", "host_pressure", "host_memory", "rate_limit_alert")),
    ("data", "Данные", ("etl_summary", "etl_failure", "etl_alert", "world_ingest_summary", "zero_parse",
                        "staleness", "freshness_watchdog", "forecast_issue")),
    ("jobs", "Фоновые задачи", ("scheduler_alert", "job_lease_lost", "ticker_stale")),
    ("stats", "Статистика и поиск", ("acquisition_alert", "recrawl_alert", "analytics_anomaly", "audience_alert")),
)
_KIND_GROUP = {kind: key for key, _, kinds in GROUPS for kind in kinds}

# Понятное название каждого вида (без «ETL», «5xx» и имён задач).
KIND_LABELS = {
    "http_5xx_spike": "короткие всплески ошибок сервера",
    "load_shed": "сервер отбивал лишнюю нагрузку (роботы)",
    "host_pressure": "диск сервера притормаживал",
    "host_memory": "серверу не хватало памяти",
    "rate_limit_alert": "защита от флуда ненадолго отключалась",
    "etl_summary": "плановые обновления данных",
    "etl_failure": "показатели не обновились",
    "etl_alert": "сбои у отдельных источников",
    "world_ingest_summary": "обновления мировых данных",
    "zero_parse": "источник вернул пустой ответ",
    "staleness": "показатели давно не обновлялись",
    "freshness_watchdog": "проверка свежести данных",
    "forecast_issue": "заминки с прогнозами",
    "scheduler_alert": "сбои фоновых задач",
    "job_lease_lost": "задача запускалась дважды",
    "ticker_stale": "бегущая строка котировок обновлялась с задержкой",
    "acquisition_alert": "неполная выгрузка из Метрики",
    "recrawl_alert": "заминки с переобходом Вебмастера",
    "analytics_anomaly": "необычные колебания в аналитике",
    "audience_alert": "необычные колебания аудитории",
    "alert": "прочие технические заметки",
}
# «Хорошие» отложенные сообщения (всё вернулось в норму) не считаем проблемой.
_RECOVERY_RE = re.compile(r"снова в норме|🟢", re.IGNORECASE)


def _plain(text: str) -> str:
    return " ".join(_TAG_RE.sub("", text or "").split())


def _headline(text: str) -> str:
    """Первая строка без разметки и без эмодзи-светофора в начале."""
    first = _TAG_RE.sub("", (text or "").strip().splitlines()[0] if (text or "").strip() else "")
    return _EMOJI_RE.sub("", first).strip()


def _plural(n: int, one: str, few: str, many: str) -> str:
    n10, n100 = n % 10, n % 100
    if n10 == 1 and n100 != 11:
        return one
    if 2 <= n10 <= 4 and not 12 <= n100 <= 14:
        return few
    return many


def _times(n: int) -> str:
    return f"{n} {_plural(n, 'раз', 'раза', 'раз')}"


def _etl_line(texts: list[str]) -> str | None:
    """Последняя плановая выгрузка: сколько обновлено и что ждём от источников."""
    if not texts:
        return None
    last = _plain(texts[-1])
    total = re.search(r"(?:Total|Всего):\s*(\d+)", last)
    upd = re.search(r"(?:Updated|обновлено):\s*(\d+)", last, re.IGNORECASE)
    down = re.search(r"недоступен:\s*(\d+)", last, re.IGNORECASE)
    if not (total or upd):
        return None
    bit = f"последнее обновление: обновлено {upd.group(1) if upd else '?'} из {total.group(1) if total else '?'}"
    if down and int(down.group(1)):
        bit += f"; {down.group(1)} ждут, пока источник снова откроется (это у источника, не у нас)"
    return bit


def build_summary(rows: Iterable[tuple[str, str]], *, day: date, urgent_sent: int = 0) -> str:
    """Текст утренней сводки. `rows` — (kind, text) отложенных за сутки, в порядке времени."""
    by_kind: dict[str, list[str]] = defaultdict(list)
    for kind, text in rows:
        if kind in HELD_KINDS:
            by_kind[kind].append(text or "")

    head = f"☀️ <b>Утренняя сводка, {day.day} {_MONTHS_GENITIVE[day.month - 1]}</b>"
    if urgent_sent:
        todo = (f"Срочное за сутки: {urgent_sent} — я писал отдельно. "
                "Если сайт уже снова работает, больше ничего делать не нужно.")
    else:
        todo = "Тебе ничего делать не нужно."
    lines = [head, f"<b>{todo}</b>"]

    if not by_kind:
        lines.append("Технических заметок за сутки нет." if urgent_sent
                     else "Сайт работал, технических заметок за сутки нет.")
        return "\n".join(lines)

    details: list[str] = []
    for key, title, kinds in GROUPS:
        present = [k for k in kinds if by_kind.get(k)]
        if not present:
            if key == "site" and not urgent_sent:
                lines.append(f"<b>{title}:</b> работал спокойно.")
            continue
        bits: list[str] = []
        for kind in present:
            texts = by_kind[kind]
            problems = [t for t in texts if not _RECOVERY_RE.search(t)]
            if kind == "etl_summary":
                line = _etl_line(texts)
                if line:
                    bits.append(line)
                continue
            if not problems:
                continue
            bits.append(f"{KIND_LABELS.get(kind, kind)} — {_times(len(problems))}")
            for t in problems[-3:]:
                h = _headline(t)
                if h:
                    details.append(f"{KIND_LABELS.get(kind, kind)}: {h[:140]}")
        if key == "site":
            if bits:
                lines.append(f"<b>{title}:</b> {escape('; '.join(bits))}. Всё прошло само.")
            elif not urgent_sent:
                lines.append(f"<b>{title}:</b> работал спокойно.")
        elif bits:
            lines.append(f"<b>{title}:</b> {escape('; '.join(bits))}.")

    other = [k for k in by_kind if k not in _KIND_GROUP]
    if other:
        lines.append(f"<b>Прочее:</b> {escape(KIND_LABELS['alert'])} — {_times(sum(len(by_kind[k]) for k in other))}.")

    lines.append("Полные тексты лежат в журнале: агент прочитает их сам, если попросишь разобраться.")
    text = "\n".join(lines)
    seen: list[str] = []
    for d in details:
        if d not in seen:
            seen.append(d)
    block = "<blockquote expandable>" + escape("\n".join(seen)) + "</blockquote>" if seen else ""
    full = text + ("\n" + block if block else "")
    if len(full) <= MESSAGE_LIMIT:
        return full
    return text[:MESSAGE_LIMIT]


async def calm_morning_summary_job() -> bool:
    """09:10 МСК: одна сводка за прошедшие сутки в главный чат."""
    from sqlalchemy import select

    from app.database import async_session
    from app.models import TelegramOutbox
    from app.services.alerting import send_telegram

    if not getattr(settings, "telegram_calm_mode", False):
        return False
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    since = now - timedelta(hours=24)
    try:
        async with async_session() as db:
            held = (await db.execute(
                select(TelegramOutbox.kind, TelegramOutbox.text)
                .where(TelegramOutbox.method == HELD_METHOD, TelegramOutbox.sent_at >= since)
                .order_by(TelegramOutbox.id)
            )).all()
            urgent = (await db.execute(
                select(TelegramOutbox.id)
                .where(TelegramOutbox.method == "sendMessage", TelegramOutbox.ok.is_(True),
                       TelegramOutbox.kind.in_(tuple(URGENT_KINDS - {"site_up"})),
                       TelegramOutbox.sent_at >= since)
            )).all()
    except Exception:  # noqa: BLE001 — без базы сводки не будет, но и падать нечему
        logger.warning("calm summary: outbox read failed", exc_info=True)
        return False
    today = datetime.now(MSK).date()
    text = build_summary([(k, t) for k, t in held], day=today, urgent_sent=len(urgent))
    return await send_telegram(text, kind=SUMMARY_KIND)
