"""Разбиение длинных текстов под лимит Bot API (4096 знаков).

Единственное место логики разбиения: `alerting.send_telegram` (дайджест, алерты),
`telegram_bot.send_message` (пульс, ответы кнопок) и отчёты `telegram_reports`
используют одни и те же функции. Круг 11, пакет 1 (E3): раньше разбиение
было только в `telegram_bot`, а дайджест уходил одним `sendMessage` и при росте
упирался в HTTP 400 «message is too long».
"""
from __future__ import annotations

import re

_TG_TEXT_LIMIT = 4000  # запас от жёсткого лимита Bot API (4096)
_BLOCKQUOTE_RE = re.compile(r"<blockquote(?:\s[^>]*)?>.*?</blockquote>", re.DOTALL)
_BLOCKQUOTE_OPEN_RE = re.compile(r"<blockquote(?:\s[^>]*)?>")


def _split_plain_text(text: str, limit: int) -> list[str]:
    """Режет текст без blockquote на части ≤limit по границам строк."""
    chunks: list[str] = []
    buf = ""
    for line in text.split("\n"):
        candidate = f"{buf}\n{line}" if buf else line
        if len(candidate) <= limit:
            buf = candidate
            continue
        if buf:
            chunks.append(buf)
            buf = ""
        if len(line) <= limit:
            buf = line
        else:
            # одиночная строка без переносов длиннее лимита — жёсткий разрез
            for i in range(0, len(line), limit):
                chunks.append(line[i:i + limit])
    if buf:
        chunks.append(buf)
    return chunks


def _split_blockquote(block: str, limit: int) -> list[str]:
    """Режет один `<blockquote>...</blockquote>` на части, каждая — валидный тег."""
    open_tag = _BLOCKQUOTE_OPEN_RE.match(block).group(0)
    inner = block[len(open_tag):-len("</blockquote>")]
    piece_limit = max(limit - len(open_tag) - len("</blockquote>"), 1)
    return [
        f"{open_tag}{piece}</blockquote>"
        for piece in _split_plain_text(inner, piece_limit)
    ]


def _split_telegram_text(text: str, limit: int = _TG_TEXT_LIMIT) -> list[str]:
    """Режет текст на части ≤limit для sendMessage.

    Н-23 (2026-07-08): LLM-Пульс без max_tokens (директива владельца
    2026-07-05) стал писать длиннее 4096 символов — Telegram отвечал 400
    "message is too long", отчёт и апдейты гипотез молча терялись. Первый
    хотфикс держал `<blockquote>` целиком атомарным — не помогло, если LLM
    оборачивает в один blockquote почти весь ответ (реальный кейс 2026-07-08):
    блок сам был длиннее лимита, разреза не происходило вообще. Теперь
    blockquote при необходимости режется по внутренним строкам с
    закрытием/переоткрытием тега на границе частей.
    """
    if len(text) <= limit:
        return [text]

    # Разбиваем текст на чередующиеся сегменты: обычный текст / целый blockquote.
    segments: list[str] = []
    pos = 0
    for m in _BLOCKQUOTE_RE.finditer(text):
        if m.start() > pos:
            segments.append(text[pos:m.start()])
        segments.append(m.group(0))
        pos = m.end()
    if pos < len(text):
        segments.append(text[pos:])

    chunks: list[str] = []
    buf = ""
    for seg in segments:
        is_blockquote = seg.startswith("<blockquote")
        if len(seg) > limit:
            if buf:
                chunks.append(buf)
                buf = ""
            chunks.extend(_split_blockquote(seg, limit) if is_blockquote else _split_plain_text(seg, limit))
            continue
        if buf and len(buf) + len(seg) > limit:
            chunks.append(buf)
            buf = ""
        buf += seg
    if buf:
        chunks.append(buf)
    return chunks


def split_telegram_text(text: str, limit: int = _TG_TEXT_LIMIT) -> list[str]:
    """Публичное имя для `_split_telegram_text` (используется отчётами)."""
    return _split_telegram_text(text, limit)
