"""Таксономия целей: каждое бизнес-событие → tier ценности + вес.

Одна точка истины для «что считать конверсией» во всех слоях: истинная
воронка (analytics_marts), rollup daily_goals, словарь metrika_goals,
Пульс-снапшот, скоринг посетителей во вкладке «Люди».

Иерархия (модель владельца, 2026-07-06):
- macro      — бизнес-конверсии: регистрация, подписка, обратная связь.
- micro      — ценные действия: скачивания, сравнение, калькуляторы, embed.
- engagement — вовлечение: глубокий просмотр, прогноз, поиск, навигация.
- technical  — служебные сигналы: ошибки, показы нуджей, consent. НЕ цели:
               ошибки живут в «Надёжности», показы баннеров — знаменатель CTR.

Вес — вклад события в скоринг ценности посетителя (у technical всегда 0).
Конверсия сессии: достигнута ли хоть одна micro/macro цель.
"""
from __future__ import annotations

TIER_MACRO = "macro"
TIER_MICRO = "micro"
TIER_ENGAGEMENT = "engagement"
TIER_TECHNICAL = "technical"

TIERS = (TIER_MACRO, TIER_MICRO, TIER_ENGAGEMENT, TIER_TECHNICAL)

# Веса по умолчанию на tier (используются, если у события нет override).
TIER_WEIGHTS = {TIER_MACRO: 50, TIER_MICRO: 10, TIER_ENGAGEMENT: 2, TIER_TECHNICAL: 0}

# --- macro: бизнес-конверсии ---
_MACRO = {
    "signup",
    "login_success",
    "newsletter_opt_in",
    "feedback_submit",
}

# --- micro: ценные действия с продуктом ---
_MICRO = {
    "download_csv",
    "download_excel",
    "download_ical",
    "demographics_csv",
    "chart_image_download",
    "compare_image_download",
    "compare_add",
    "compare_change",
    "region_compare_add",
    "calc_share",
    "calc_copy_result",
    "calc_mortgage",
    "calc_compound",
    "embed_code_copy",
    "oauth_start",
    "register_nudge_cta",
    "feedback_nudge_cta",
    "header_register_click",
}

# --- technical: не цели (ошибки, показы, consent, ретраи) ---
_TECHNICAL = {
    "api_load_error",
    "error_reload",
    "api_retry",
    "empty_state",
    "register_nudge_view",
    "feedback_nudge_view",
    "consent_update",
    "newsletter_opt_out",
    "download_limit",
    "compare_image_blocked",
    "chart_image_blocked",
    "compare_limit_hit",
    "experiment_exposure",
    "embed_runtime_view",
}

# Точечные override веса (сильнее дефолта tier'а).
_WEIGHT_OVERRIDES = {
    "signup": 100,
    "newsletter_opt_in": 60,
    "feedback_submit": 40,
    "login_success": 15,
    "download_csv": 12,
    "download_excel": 12,
    "chart_image_download": 8,
    "forecast_view": 4,
    "search_select": 3,
}


def tier_for_event(event_name: str) -> str:
    """Tier события. Всё неперечисленное — engagement: любое именованное
    действие пользователя в продукте по умолчанию сигнал вовлечения."""
    if event_name in _MACRO:
        return TIER_MACRO
    if event_name in _MICRO:
        return TIER_MICRO
    if event_name in _TECHNICAL:
        return TIER_TECHNICAL
    return TIER_ENGAGEMENT


def weight_for_event(event_name: str) -> int:
    return _WEIGHT_OVERRIDES.get(event_name, TIER_WEIGHTS[tier_for_event(event_name)])


def is_conversion(event_name: str) -> bool:
    """Событие считается конверсией (для воронки и «истинной конверсии»)."""
    return tier_for_event(event_name) in (TIER_MACRO, TIER_MICRO)
