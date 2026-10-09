"""Очистка персональных данных в тексте и в снимках для внешних потребителей.

Круг 11, зона H (152-ФЗ): в LLM (OpenRouter, через зарубежный прокси) и в
свободные поля событий не должны попадать почты, телефоны, имена. Здесь чистые
функции без обращения к БД; их используют `pulse_report` (текст для модели) и
`api.analytics.collect_event` (поле `q` поиска и другие строки событий).

Правила:
- почтоподобные фрагменты (`x@y.zz`) и телефоноподобные (от 10 цифр подряд с
  пробелами, скобками и дефисами) заменяются на «[скрыто]»;
- длинные числовые идентификаторы (карты, паспорта: 12+ цифр) тоже скрываются;
- обычный поиск по показателям («ввп 2025», «курс 90.5») не затрагивается.
"""
from __future__ import annotations

import re
from typing import Any

MASK = "[скрыто]"

_EMAIL_RE = re.compile(r"[\w.+\-]+@[\w\-]+(?:\.[\w\-]+)+", re.UNICODE)
# Телефон: необязательный «+», затем 10–15 цифр, допускаются пробелы, скобки, дефисы.
_PHONE_RE = re.compile(r"(?<![\w.])\+?\d[\d\s().\-]{8,}\d(?![\w])")
_LONG_DIGITS_RE = re.compile(r"\d{12,}")
# Номер карты «1234 5678 9012 3456» / «1234-5678-9012-3456»; четыре года подряд
# («2020 2021 2022 2023» в поиске) картой не считаем.
_CARD_RE = re.compile(r"(?<!\d)(?:\d{4}[ \-]){3}\d{4}(?!\d)")
_YEARISH_RE = re.compile(r"(?:19|20)\d{2}")


def _digits(value: str) -> int:
    return sum(ch.isdigit() for ch in value)


def scrub_text(value: Any) -> str:
    """Строка без почт и телефонов. Не строки приводятся к строке."""
    text = value if isinstance(value, str) else str(value)
    text = _EMAIL_RE.sub(MASK, text)

    def _card(match: re.Match) -> str:
        groups = re.split(r"[ \-]", match.group(0))
        if all(_YEARISH_RE.fullmatch(g) for g in groups):
            return match.group(0)
        return MASK

    text = _CARD_RE.sub(_card, text)

    def _phone(match: re.Match) -> str:
        fragment = match.group(0)
        # «2020-2025», «10.5 12.3 14.1» и подобные ряды чисел телефоном не считаем:
        # нужно 10–15 цифр и не более одной точки/запятой-разделителя дробей.
        if not 10 <= _digits(fragment) <= 15:
            return fragment
        if fragment.count(".") > 1 and not re.search(r"[()+\s\-]", fragment):
            return fragment
        return MASK

    text = _PHONE_RE.sub(_phone, text)
    return _LONG_DIGITS_RE.sub(MASK, text)


def contains_pii(value: Any) -> bool:
    text = value if isinstance(value, str) else str(value)
    return scrub_text(text) != text


def scrub_value(value: Any) -> Any:
    """Рекурсивно очищает строки в JSON-подобной структуре (ключи словарей сохраняются
    и тоже очищаются, если это строки с почтой: так поисковые фразы в `dict[str,int]`
    не оставляют почту в ключе)."""
    if isinstance(value, str):
        return scrub_text(value)
    if isinstance(value, dict):
        return {
            (scrub_text(k) if isinstance(k, str) else k): scrub_value(v)
            for k, v in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [scrub_value(v) for v in value]
    return value


def sanitize_snapshot_for_llm(snapshot: dict) -> dict:
    """Копия снимка дня для LLM без персональных данных.

    - `users.new_list` (имена и почты новых пользователей) не передаётся совсем:
      остаются число, способ входа и язык сайта (если есть); страну отдельного человека не передаём;
    - строки поиска, копирования, кликов, фраз из поиска очищаются от почт/телефонов;
    - прочие числа и коды (показатели, регионы) не меняются.
    Старые снимки в Redis (до круга 11) содержат `new_list` с именами и почтой:
    эта функция вызывается при каждой отправке в модель, поэтому они тоже не уходят.
    """
    clean = scrub_value(dict(snapshot))
    users = dict(clean.get("users") or {})
    raw_list = (snapshot.get("users") or {}).get("new_list") or []
    users["new_list"] = [
        {k: item.get(k) for k in ("method", "site_locale") if item.get(k)}
        for item in raw_list
        if isinstance(item, dict)
    ]
    clean["users"] = users
    return clean


def sanitize_memory_for_llm(memory: list[dict]) -> list[dict]:
    """Память прошлых дней: сводки модели могли пересказать почту, чистим."""
    return [scrub_value(entry) if isinstance(entry, dict) else entry for entry in memory]
