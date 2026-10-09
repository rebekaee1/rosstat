"""Гигиена параметров бизнес-событий на приёме (152-ФЗ, круг 11, зона H).

`FrontendEventIn.params` раньше принимал любой словарь. Теперь перед записью:
- ключи только вида `[A-Za-z0-9_.-]{1,60}`, не больше 30 ключей;
- значения: строки (до 200 знаков, почты и телефоны заменяются на «[скрыто]»),
  числа, булевы; списки скаляров (до 20) и словари в один уровень (до 10 ключей);
- ключи с очевидными персональными данными (почта, телефон, пароль, токен, имя,
  адрес, IP, user-agent) отбрасываются;
- общий размер не больше 2 КБ: лишнее отбрасывается с пометкой `_truncated`;
- события входа и регистрации (и события новых функций) принимают только
  перечисленные ключи (белый список).

Поиск (`q`) остаётся единственным свободным текстом: он проходит ту же очистку.
"""
from __future__ import annotations

import json
import math
import re
from typing import Any

from app.services.pii_scrub import scrub_text

MAX_PARAMS_BYTES = 2048
MAX_KEYS = 30
MAX_STR = 200
MAX_LIST_ITEMS = 20
MAX_DICT_KEYS = 10

_KEY_RE = re.compile(r"^[A-Za-z0-9_.\-]{1,60}$")
_FORBIDDEN_EXACT = frozenset({
    "email", "e_mail", "mail", "phone", "tel", "telephone", "password", "passwd", "pwd",
    "token", "secret", "fio", "display_name", "full_name", "first_name", "last_name",
    "address", "ip", "user_agent", "ua", "cookie", "authorization",
})
_FORBIDDEN_SUFFIXES = ("_email", "_phone", "_password", "_token", "_secret")

_COMMON = frozenset({"authed"})

# Белый список ключей: события входа/регистрации и новых функций. Любой другой ключ
# в этих событиях отбрасывается. Остальные события проходят общие правила выше.
EVENT_PARAM_KEYS: dict[str, frozenset[str]] = {
    "signup": frozenset({"method", "newsletter", "site_locale", "trigger", "landing", "first_visit_days"}),
    "login_success": frozenset({"method", "site_locale"}),
    "oauth_start": frozenset({"provider", "intent"}),
    "oauth_consent_open": frozenset({"provider", "intent"}),
    "oauth_consent_cancel": frozenset({"provider", "intent"}),
    "auth_error": frozenset({"stage", "code", "provider"}),
    "auth_form_error": frozenset({"form", "field", "code"}),
    "newsletter_opt_in": frozenset({"channel"}),
    "newsletter_opt_out": frozenset({"channel"}),
    "locale_switch": frozenset({"from", "to", "surface"}),
    "share_link": frozenset({"kind", "method", "surface"}),
    "favorite_add": frozenset({"kind", "code", "surface", "storage"}),
    "favorite_remove": frozenset({"kind", "code", "surface", "storage"}),
    "compare_preset_open": frozenset({"preset", "kind"}),
    "compare_save": frozenset({"count", "storage"}),
    "compare_saved_open": frozenset({"count", "storage"}),
    "indicator_subscribe": frozenset({"indicator", "channel", "frequency"}),
    "indicator_unsubscribe": frozenset({"indicator", "channel", "frequency"}),
    "push_prompt_view": frozenset({"platform"}),
    "push_permission": frozenset({"result", "platform"}),
    "converter_use": frozenset({"from", "to", "surface"}),
    "calc_use": frozenset({"tool", "country"}),
    "export_run": frozenset({"kind", "format", "surface"}),
}


def _forbidden(key: str) -> bool:
    low = key.lower()
    return low in _FORBIDDEN_EXACT or low.endswith(_FORBIDDEN_SUFFIXES)


def _scalar(value: Any, limit: int = MAX_STR) -> tuple[bool, Any]:
    if value is None or isinstance(value, bool):
        return True, value
    if isinstance(value, int):
        return True, value
    if isinstance(value, float):
        return (True, value) if math.isfinite(value) else (False, None)
    if isinstance(value, str):
        return True, scrub_text(value[:limit])
    return False, None


def _clean_value(value: Any, depth: int = 0) -> tuple[bool, Any]:
    ok, scalar = _scalar(value)
    if ok:
        return True, scalar
    if isinstance(value, (list, tuple)) and depth < 2:
        items = []
        for item in list(value)[:MAX_LIST_ITEMS]:
            item_ok, cleaned = _clean_value(item, depth + 1)
            if item_ok:
                items.append(cleaned)
        return True, items
    if isinstance(value, dict) and depth < 1:
        out = {}
        for key, item in list(value.items())[:MAX_DICT_KEYS]:
            if not isinstance(key, str) or not _KEY_RE.match(key) or _forbidden(key):
                continue
            item_ok, cleaned = _clean_value(item, depth + 1)
            if item_ok:
                out[key] = cleaned
        return True, out
    return False, None


def sanitize_event_params(event_name: str, params: Any) -> dict[str, Any]:
    """Очищенные параметры события. Никогда не бросает."""
    if not isinstance(params, dict):
        return {}
    allowed = EVENT_PARAM_KEYS.get(event_name)
    cleaned: dict[str, Any] = {}
    for key, value in params.items():
        if len(cleaned) >= MAX_KEYS:
            break
        if not isinstance(key, str) or not _KEY_RE.match(key) or _forbidden(key):
            continue
        if allowed is not None and key not in allowed and key not in _COMMON:
            continue
        ok, item = _clean_value(value)
        if ok:
            cleaned[key] = item

    def _size(obj: dict) -> int:
        return len(json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))

    if _size(cleaned) > MAX_PARAMS_BYTES:
        trimmed: dict[str, Any] = {}
        for key, value in cleaned.items():
            trimmed[key] = value
            if _size(trimmed) > MAX_PARAMS_BYTES - 20:
                trimmed.pop(key)
        trimmed["_truncated"] = 1
        return trimmed
    return cleaned
