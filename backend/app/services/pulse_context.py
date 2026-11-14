"""Контекст проекта для аналитика Пульса (14.11.2026, слова владельца: «аналитик… чтобы он в курсе был всего, что
происходит»).

До этого модель видела только снимок дня, память 7 дней и открытые гипотезы: выпуски, флаги, решения, эксперименты
и смены счёта метрик она не знала и называла обвалом то, что было фильтром роботов. Три слоя:

* **Записи** `app/data/pulse_context.yaml` — пишут агенты вместе с правкой (цикл знаний): что сделано и что ждать в
  цифрах, дата, срок показа, коммит. Дата выпуска коммита берётся из журнала выпусков, если он там есть.
* **Журнал выпусков** `app/data/release_log.json` — пишет `scripts/deploy.sh` перед сборкой образа
  (`scripts/release-log.py`): короткий SHA, дата и заголовки коммитов выпуска, без тел и авторов, до 15 строк.
  Файла нет (локально, тесты) — слой пуст.
* **Живые факты** — режимы и флаги по белому списку (только имена и значения) и остаток счёта OpenRouter (только
  число и «мало», ключ не пишется в журнал).

Блок ограничен `MAX_BLOCK_CHARS`; каждая запись — `MAX_ENTRY_CHARS`. Текст проходит ту же очистку от ПДн, что и
остальной ввод модели (`scrub_value`).
* **Заметки владельца** — служебный бот: /context текст [до ДД.ММ] или «контекст …» в чате владельца,
  /context — список, /context удалить N. Таблица `pulse_context_notes`, в блок — до NOTES_IN_BLOCK свежих.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import yaml

from app.config import settings

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
ENTRIES_PATH = DATA_DIR / "pulse_context.yaml"
RELEASE_LOG_PATH = DATA_DIR / "release_log.json"

MAX_BLOCK_CHARS = 5200
MAX_ENTRY_CHARS = 260
LOOKBACK_DAYS = 45
MAX_RELEASES = 2
MAX_RELEASE_LINES = 15
RELEASE_LINE_CHARS = 100
# Выпуски - не больше этой доли блока: записи «что ждать в цифрах» важнее заголовков коммитов.
MAX_RELEASES_CHARS = 1100
LOW_BALANCE_USD = 3.0

# Имена настроек, значения которых модель может видеть: режимы и флаги без секретов. Отсутствующие пропускаются.
FLAG_WHITELIST = (
    "telegram_calm_mode",
    "public_bot_enabled",
    "public_bot_llm_enabled",
    "ru_google_short_sitemap",
    "ru_google_noindex_world_years",
    "ru_google_disallow_world_years",
    "apex_google_short_sitemap",
    "apex_google_noindex_years_without_demand",
    "analytics_sessionize_incremental_enabled",
)
_SECRET_HINTS = ("secret", "token", "key", "password", "dsn", "url")


@dataclass(frozen=True)
class Entry:
    id: str
    date: date
    kind: str
    title: str
    expect: str
    until: date | None
    commit: str | None


def _as_date(value) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def load_entries(path: Path = ENTRIES_PATH) -> list[Entry]:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except FileNotFoundError:
        return []
    out = []
    for item in raw.get("entries") or []:
        out.append(Entry(
            id=str(item["id"]),
            date=_as_date(item["date"]),
            kind=str(item.get("kind", "")),
            title=str(item.get("title", "")).strip(),
            expect=str(item.get("expect", "")).strip(),
            until=_as_date(item.get("until")),
            commit=(str(item["commit"])[:12] if item.get("commit") else None),
        ))
    return out


def load_release_log(path: Path = RELEASE_LOG_PATH) -> list[dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return []
    releases = data.get("releases") if isinstance(data, dict) else None
    return [r for r in (releases or []) if isinstance(r, dict) and r.get("sha") and r.get("date")]


def release_date_of(commit: str | None, releases: list[dict]) -> date | None:
    """Дата выпуска, в который вошёл коммит (по коротким SHA в строках журнала)."""
    if not commit:
        return None
    for rel in releases:
        for line in rel.get("lines") or []:
            if str(line).split(" ", 1)[0].startswith(commit[:7]):
                return _as_date(rel["date"])
    return None


def _clip(text: str, limit: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def flag_lines() -> list[str]:
    parts = []
    for name in FLAG_WHITELIST:
        if any(h in name for h in _SECRET_HINTS):
            continue
        value = getattr(settings, name, None)
        if value is None or not isinstance(value, (bool, int, str)) or (isinstance(value, str) and len(value) > 40):
            continue
        parts.append(f"{name}={str(value).lower() if isinstance(value, bool) else value}")
    return parts


async def openrouter_balance() -> float | None:
    """Остаток счёта OpenRouter в долларах или None. Ключ уходит только в заголовок запроса и не логируется."""
    if not settings.openrouter_api_key:
        return None
    try:
        import httpx

        async with httpx.AsyncClient(timeout=15, proxy=settings.openrouter_proxy_url or None) as client:
            resp = await client.get("https://openrouter.ai/api/v1/credits",
                                    headers={"Authorization": f"Bearer {settings.openrouter_api_key}"})
        if resp.status_code != 200:
            logger.info("OpenRouter credits: HTTP %d", resp.status_code)
            return None
        data = (resp.json() or {}).get("data") or {}
        return round(float(data.get("total_credits", 0)) - float(data.get("total_usage", 0)), 2)
    except Exception:  # noqa: BLE001 - остаток не обязателен для отчёта
        logger.info("OpenRouter credits: недоступно")
        return None


def _release_lines(releases: list[dict]) -> list[str]:
    """Выпуски (старые -> новые) в бюджете MAX_RELEASES_CHARS: лишние строки старого выпуска уходят в «и ещё N»."""
    blocks = []
    for rel in releases:
        all_lines = [str(x) for x in (rel.get("lines") or [])]
        blocks.append([rel, all_lines[:MAX_RELEASE_LINES],
                       int(rel.get("more") or 0) + max(0, len(all_lines) - MAX_RELEASE_LINES)])

    def render() -> list[str]:
        out = ["Последние выпуски на боевом (старые → новые):"]
        for rel, shown, more in blocks:
            out.append(f"- {rel['date']} выпуск {rel['sha']}:")
            out.extend(f"  · {_clip(x, RELEASE_LINE_CHARS)}" for x in shown)
            if more:
                out.append(f"  · и ещё {more}")
        return out

    out = render()
    while len("\n".join(out)) > MAX_RELEASES_CHARS:
        block = next((b for b in blocks if b[1]), None)  # сначала укорачивается самый старый выпуск
        if block is None:
            break
        block[1].pop()
        block[2] += 1
        out = render()
    return out


def build_block(today: date, *, entries: list[Entry] | None = None, releases: list[dict] | None = None,
                flags: list[str] | None = None, balance: float | None = None, notes: list | None = None) -> str:
    """Текст блока «Контекст проекта» для модели; пусто, если знать нечего."""
    from app.services.pii_scrub import scrub_value

    entries = load_entries() if entries is None else entries
    releases = load_release_log() if releases is None else releases
    flags = flag_lines() if flags is None else flags
    lines: list[str] = []

    if releases:
        lines.extend(_release_lines(releases[-MAX_RELEASES:]))
    if flags:
        lines.append("Режимы и флаги сейчас: " + ", ".join(flags))
    if balance is not None:
        lines.append(f"Остаток счёта OpenRouter: ${balance:.2f}" + (" — мало" if balance < LOW_BALANCE_USD else ""))

    active = []
    for e in entries:
        when = release_date_of(e.commit, releases) or e.date
        if e.until and e.until < today:
            continue
        if when < today - timedelta(days=LOOKBACK_DAYS) and not (e.until and e.until >= today):
            continue
        released = release_date_of(e.commit, releases)
        status = f"выпущено {released:%d.%m.%Y}" if released else f"{e.date:%d.%m.%Y}"
        text = f"[{e.id}] {status} · {e.kind} · {e.title}" + (f" Что ждать: {e.expect}" if e.expect else "")
        active.append((when, _clip(text, MAX_ENTRY_CHARS)))
    if active:
        lines.append("События и решения (id для ссылок в гипотезах):")
        lines.extend(f"- {t}" for _, t in sorted(active))
    if notes:
        lines.append("Заметки владельца (свежие внизу):")
        lines.extend(note_lines(notes))

    if not lines:
        return ""
    block = "\n".join(scrub_value(lines))
    while len(block) > MAX_BLOCK_CHARS and lines:
        # Сначала уходят строки выпусков (заголовки коммитов), потом «что ждать» у старых записей, потом сами
        # старые записи: записи о смене счёта и авариях важнее перечня коммитов.
        idx = next((i for i in range(len(lines) - 1, -1, -1) if lines[i].startswith("  · ")), None)
        if idx is not None:
            lines.pop(idx)
        else:
            idx = next((i for i, x in enumerate(lines) if x.startswith("- [") and "Что ждать:" in x), None)
            if idx is not None:
                lines[idx] = lines[idx].split(" Что ждать:", 1)[0]
            else:
                idx = next((i for i, x in enumerate(lines) if x.startswith("- [")), None)
                if idx is None:
                    break
                lines.pop(idx)
        block = "\n".join(scrub_value(lines))
    return block[:MAX_BLOCK_CHARS]


def count_active(today: date) -> int:
    releases = load_release_log()
    return sum(1 for e in load_entries()
               if not (e.until and e.until < today)
               and ((release_date_of(e.commit, releases) or e.date) >= today - timedelta(days=LOOKBACK_DAYS)
                    or (e.until and e.until >= today)))


# --- Заметки владельца из служебного бота (/context, «контекст …») -------------------------------------------------

NOTE_MAX_CHARS = 600
NOTES_IN_BLOCK = 10


def parse_command(raw: str) -> tuple[str, str | int | None, date | None] | None:
    """Разбор команды владельца: ("add", текст, срок) / ("list", None, None) / ("delete", номер, None) или None.

    Telegram не принимает кириллицу в именах команд, поэтому команда - /context; в чате владельца работает и текст
    «контекст …». «… до 25.11» или «… до 25.11.2026» в конце - срок показа.
    """
    import re

    text = (raw or "").strip()
    m = re.match(r"^(?:/context(?:@\w+)?|контекст)\b[:\s]*(.*)$", text, re.IGNORECASE | re.DOTALL)
    if not m:
        return None
    body = m.group(1).strip()
    if not body or body.lower() in ("список", "list"):
        return ("list", None, None)
    d = re.match(r"^(?:удалить|delete)\s+(\d+)$", body, re.IGNORECASE)
    if d:
        return ("delete", int(d.group(1)), None)
    until = None
    u = re.search(r"\s+до\s+(\d{1,2})\.(\d{1,2})(?:\.(\d{4}))?\s*$", body, re.IGNORECASE)
    if u:
        today = date.today()
        year = int(u.group(3)) if u.group(3) else today.year
        try:
            until = date(year, int(u.group(2)), int(u.group(1)))
            if not u.group(3) and until < today:
                until = date(year + 1, until.month, until.day)
            body = body[: u.start()].strip()
        except ValueError:
            until = None
    return ("add", body[:NOTE_MAX_CHARS], until)


async def add_note(db, text: str, until: date | None):
    from datetime import datetime, timezone

    from app.models import PulseContextNote
    from app.services.pii_scrub import scrub_text

    note = PulseContextNote(created_at=datetime.now(timezone.utc).replace(tzinfo=None),
                            text=scrub_text(text)[:NOTE_MAX_CHARS], until=until, deleted=False)
    db.add(note)
    await db.commit()
    return note


async def active_notes(db, today: date, limit: int = NOTES_IN_BLOCK) -> list:
    from sqlalchemy import or_, select

    from app.models import PulseContextNote

    rows = (await db.execute(
        select(PulseContextNote)
        .where(PulseContextNote.deleted.is_(False),
               or_(PulseContextNote.until.is_(None), PulseContextNote.until >= today))
        .order_by(PulseContextNote.id.desc()).limit(limit)
    )).scalars().all()
    return list(reversed(rows))


async def delete_note(db, note_id: int) -> bool:
    from app.models import PulseContextNote

    note = await db.get(PulseContextNote, note_id)
    if note is None or note.deleted:
        return False
    note.deleted = True
    await db.commit()
    return True


def note_lines(notes: list) -> list[str]:
    return [f"- [заметка {n.id}] {n.created_at:%d.%m.%Y} · заметка владельца · {_clip(n.text, MAX_ENTRY_CHARS)}"
            + (f" (до {n.until:%d.%m.%Y})" if n.until else "") for n in notes]


async def handle_owner_command(raw: str) -> str | None:
    """Ответ бота на команду владельца; None - это не команда контекста."""
    from html import escape

    from app.database import async_session

    cmd = parse_command(raw)
    if cmd is None:
        return None
    action, arg, until = cmd
    today = date.today()
    async with async_session() as db:
        if action == "add":
            if not arg:
                return "Напишите текст после команды: <code>/context что произошло … до 25.11</code>"
            note = await add_note(db, str(arg), until)
            tail = f", показывать до {until:%d.%m.%Y}" if until else ""
            return f"🧭 Записал для аналитика (заметка {note.id}{tail}). Учтёт в ближайшем Пульсе."
        if action == "delete":
            ok = await delete_note(db, int(arg))
            return f"🧭 Заметка {arg} удалена." if ok else f"Заметки {arg} нет."
        notes = await active_notes(db, today, limit=30)
    if not notes:
        return ("🧭 Заметок для аналитика нет. Добавить: <code>/context текст</code> или «контекст текст», "
                "срок — «… до 25.11». Удалить: <code>/context удалить 3</code>.")
    body = "\n".join(escape(x[2:]) for x in note_lines(notes))
    return f"🧭 <b>Заметки для аналитика</b> ({len(notes)}):\n{body}\n\nУдалить: <code>/context удалить N</code>."
