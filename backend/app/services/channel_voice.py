"""Словарь автора Telegram-канала: какими словами он пишет и чего не пишет (17.11.2026, ADR-0035).

Слова владельца 17.11.2026: «согласовать, какие именно слова он будет писать в телеграме». Согласование идёт по
настоящим постам в показе; ответы владельца («это — да, это — нет») должны стать правилами автора. Здесь — место,
куда они ложатся, и то, как автор их соблюдает:

* основа — `app/data/channel_voice.yaml`: разделы `use` (как начинать пост, называть число, говорить об изменении,
  прогнозе, источнике, чем заканчивать) и `ban` (чего не пишем);
* ответы владельца — таблица `channel_voice_rules`: приходят в служебный бот командой `/voice` (можно вставить
  целиком блок, скопированный из показа: строки «да: …», «нет: …», «правило: …»); они важнее файла;
* соблюдение — двумя способами: всё это попадает в системный промпт (раздел `words`), а список «не пишем» проверяет
  сторож `channel_facts.check_post`: пост с таким словом возвращается автору на исправление и без исправления
  не получает кнопку публикации.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from html import escape
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

VOICE_PATH = Path(__file__).resolve().parent.parent / "data" / "channel_voice.yaml"
SECTION_TITLES = {
    "start": "Как пост начинается", "number": "Как называется число", "change": "Как сказано об изменении",
    "compare": "С чем сравниваем", "forecast": "О прогнозе", "source": "Об источнике", "ending": "Чем пост заканчивается",
}
KINDS = {"ban": "нет", "use": "да", "rule": "правило"}
MAX_RULE = 300
MAX_OWNER_RULES = 80


def load_base(path: Path = VOICE_PATH) -> dict:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:  # noqa: BLE001 — без файла автор работает на правилах из промпта
        logger.warning("channel voice: словарь не прочитан", exc_info=True)
        data = {}
    use = {k: [str(x) for x in (v or [])] for k, v in (data.get("use") or {}).items()}
    return {"use": use, "ban": [str(x) for x in (data.get("ban") or [])]}


async def owner_rules(db) -> list:
    """Правила владельца из служебного бота, от старых к новым."""
    from sqlalchemy import select

    from app.models import ChannelVoiceRule

    try:
        return list((await db.execute(
            select(ChannelVoiceRule).where(ChannelVoiceRule.deleted.is_(False))
            .order_by(ChannelVoiceRule.id).limit(MAX_OWNER_RULES))).scalars().all())
    except Exception:  # noqa: BLE001 — таблицы может ещё не быть (показ на базе до миграции)
        await db.rollback()
        return []


def words_block(base: dict, rules: list | None = None) -> str:
    """Раздел words системного промпта."""
    lines = ["Слова, согласованные с владельцем. Это устойчивая часть голоса: формулы ниже — способ сказать, "
             "а не готовые фразы, и подставлять в них нужно сегодняшние числа."]
    for key, title in SECTION_TITLES.items():
        items = base["use"].get(key) or []
        if items:
            lines.append(f"{title}:")
            lines += [f"— {x}" for x in items]
    owner_use = [r.text for r in (rules or []) if r.kind == "use"]
    owner_rule = [r.text for r in (rules or []) if r.kind == "rule"]
    if owner_use:
        lines.append("Владелец отметил «так писать можно» (это его вкус, держись его):")
        lines += [f"— {x}" for x in owner_use]
    if owner_rule:
        lines.append("Правила владельца, сказанные его словами (они важнее всего остального в этом разделе):")
        lines += [f"— {x}" for x in owner_rule]
    ban = banned_list(base, rules)
    if ban:
        lines.append("Не пишем никогда (программа-сторож вернёт пост с любым из этих слов): " + "; ".join(f"«{x}»" for x in ban) + ".")
    return "\n".join(lines)


def banned_list(base: dict, rules: list | None = None) -> list[str]:
    """Список «не пишем»: файл + запреты владельца, минус то, что владелец вернул в оборот («да: слово»)."""
    allowed = {r.text.strip().lower().replace("ё", "е") for r in (rules or []) if r.kind == "use"}
    merged = list(dict.fromkeys([*base["ban"], *[r.text for r in (rules or []) if r.kind == "ban"]]))
    return [w for w in merged if w.strip().lower().replace("ё", "е") not in allowed]


def find_banned(text_plain: str, banned: list[str]) -> list[str]:
    """Слова и обороты из списка «не пишем», которые есть в тексте. Сравнение без регистра и без разницы е/ё;
    одно слово ищется как целое слово с любым окончанием того же корня не ищется — список ведётся дословно."""
    low = (text_plain or "").lower().replace("ё", "е")
    found = []
    for phrase in banned:
        p = phrase.strip().lower().replace("ё", "е")
        if p and re.search(r"(?<![a-zа-я0-9])" + re.escape(p) + r"(?![a-zа-я0-9])", low):
            found.append(phrase)
    return found


async def load_voice(db) -> tuple[str, list[str]]:
    """(раздел words для промпта, список «не пишем» для сторожа)."""
    base = load_base()
    rules = await owner_rules(db)
    return words_block(base, rules), banned_list(base, rules)


# ---------------------------------------------------------------------------
# Команда владельца в служебном боте
# ---------------------------------------------------------------------------

_LINE = re.compile(r"^\s*(да|нет|правило)\s*[:—-]\s*(.+)$", re.I)
_CMD = re.compile(r"^\s*(/voice|слова канала|словарь канала)\b[:\s]*", re.I)


def is_voice_command(text: str) -> bool:
    return bool(_CMD.match(text or ""))


def parse_lines(raw: str) -> list[tuple[str, str]]:
    """Строки «да: …», «нет: …», «правило: …» → [(kind, текст)]. Кавычки-ёлочки вокруг фразы снимаются."""
    out = []
    for line in (raw or "").splitlines():
        m = _LINE.match(line)
        if not m:
            continue
        kind = {"да": "use", "нет": "ban", "правило": "rule"}[m.group(1).lower()]
        text = m.group(2).strip().strip("«»\"“”").strip()[:MAX_RULE]
        if text:
            out.append((kind, text))
    return out


async def handle_owner_command(raw: str) -> str | None:
    """`/voice` — показать словарь; `/voice` + строки «да/нет/правило: …» — записать; `/voice убрать N` — снять.
    Возвращает HTML-ответ или None, если это не команда словаря."""
    from sqlalchemy import select

    from app.database import async_session
    from app.models import ChannelVoiceRule

    if not is_voice_command(raw):
        return None
    body = _CMD.sub("", raw, count=1).strip()
    async with async_session() as db:
        drop = re.match(r"^(убрать|удалить)\s+(\d+)$", body, re.I)
        if drop:
            row = await db.get(ChannelVoiceRule, int(drop.group(2)))
            if row is None or row.deleted:
                return "Такого правила нет. Список: /voice"
            row.deleted = True
            await db.commit()
            return f"Убрал правило {row.id}: «{escape(row.text)}»."
        items = parse_lines(body)
        if items:
            existing = {(r.kind, r.text.lower()) for r in await owner_rules(db)}
            added = 0
            for kind, text in items:
                if (kind, text.lower()) in existing:
                    continue
                db.add(ChannelVoiceRule(kind=kind, text=text, created_at=datetime.now(timezone.utc).replace(tzinfo=None)))
                existing.add((kind, text.lower()))
                added += 1
            await db.commit()
            n_ban = sum(1 for k, _ in items if k == "ban")
            return (f"Записал: {added} из {len(items)} (остальные уже были). "
                    + (f"«Не пишем» — {n_ban}: редактор перестанет употреблять эти слова со следующего поста, "
                       "а программа не пропустит пост с ними. " if n_ban else "")
                    + "Весь словарь: /voice")
        if body:
            return ("Не разобрал. Каждое правило — с новой строки и с пометкой в начале:\n"
                    "<code>нет: занятно, что</code>\n<code>да: Наш расчёт: 6,26 %</code>\n"
                    "<code>правило: заголовок без тире</code>\nСнять правило: <code>/voice убрать 3</code>")
        rules = await owner_rules(db)
    base = load_base()
    lines = ["🖋 <b>Словарь редактора канала</b>",
             f"Основа: {sum(len(v) for v in base['use'].values())} формул и {len(base['ban'])} слов «не пишем»."]
    if rules:
        lines.append("<b>Ваши правила:</b>")
        lines += [f"{r.id}. {KINDS.get(r.kind, r.kind)}: {escape(r.text)}" for r in rules]
    else:
        lines.append("Ваших правил пока нет.")
    lines.append("Добавить — строками <code>да: …</code>, <code>нет: …</code>, <code>правило: …</code> после /voice "
                 "(можно вставить блок из показа целиком). Снять — <code>/voice убрать N</code>.")
    return "\n".join(lines)
