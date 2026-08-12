"""Таксономия целей: каждое бизнес-событие → tier ценности + вес.

Одна точка истины для «что считать конверсией» во всех слоях: истинная
воронка (analytics_marts), rollup daily_goals, словарь metrika_goals,
Пульс-снапшот, скоринг посетителей во вкладке «Люди».

Иерархия (модель владельца, 2026-07-06; ревизия intent 2026-07-06 вечер):
- macro      — бизнес-конверсии: регистрация, подписка, обратная связь.
- micro      — ценные действия: скачивания, сравнение, калькуляторы, embed.
- intent     — намерение (клик «Регистрация», старт OAuth, CTA нуджа):
               НЕ конверсия (иначе клик по кнопке = достижение — болезнь,
               которую чинили в Метрике), но участвует в скоринге и воронках.
- engagement — вовлечение: глубокий просмотр, прогноз, поиск, навигация.
- technical  — служебные сигналы: ошибки, показы нуджей, consent,
               негативные сигналы (search_abandon, outbound_link). НЕ цели:
               ошибки живут в «Надёжности», показы баннеров — знаменатель CTR.

Все события реестра track.js перечислены ЯВНО — «engagement по умолчанию»
оставлен только как страховка для будущих событий, тест
test_taxonomy_covers_frontend_registry требует явной классификации.

Вес — вклад события в скоринг ценности посетителя (у technical всегда 0).
Конверсия сессии: достигнута ли хоть одна micro/macro цель (intent — нет).
"""
from __future__ import annotations

TIER_MACRO = "macro"
TIER_MICRO = "micro"
TIER_INTENT = "intent"
TIER_ENGAGEMENT = "engagement"
TIER_TECHNICAL = "technical"

TIERS = (TIER_MACRO, TIER_MICRO, TIER_INTENT, TIER_ENGAGEMENT, TIER_TECHNICAL)

# Веса по умолчанию на tier (используются, если у события нет override).
TIER_WEIGHTS = {
    TIER_MACRO: 50,
    TIER_MICRO: 10,
    TIER_INTENT: 3,
    TIER_ENGAGEMENT: 2,
    TIER_TECHNICAL: 0,
}

# --- macro: бизнес-конверсии (приобретение/удержание отношений) ---
_MACRO = {
    "signup",
    "newsletter_opt_in",
    "feedback_submit",
}

# --- micro: ценные действия с продуктом ---
_MICRO = {
    "login_success",          # возвратный вход ≠ приобретение → micro
    "download_csv",
    "download_excel",
    "download_ical",
    "demographics_csv",
    "chart_image_download",
    "compare_image_download",
    "regions_map_gif_download",
    "compare_add",
    "compare_change",
    "region_compare_add",
    "calc_share",
    "calc_copy_result",
    "calc_mortgage",
    "calc_compound",
    "embed_code_copy",
    "contact_email",          # интент связи — ценное действие
}

# --- intent: намерение, НЕ конверсия ---
_INTENT = {
    "oauth_start",
    "header_register_click",
    "header_login_click",
    "register_nudge_cta",
    "feedback_nudge_cta",
    "register_nudge_expand",
    "feedback_nudge_expand",
}

# --- engagement: вовлечение в контент и инструменты ---
_ENGAGEMENT = {
    "indicator_view",
    "region_indicator_view",
    "forecast_view",
    "forecast_toggle",
    "search_query",
    "search_select",
    "compare_open",
    "compare_search",
    "compare_range",
    "chart_mode_change",
    "chart_range_change",
    "chart_zoom",
    "frequency_switch",
    "methodology_click",
    "scroll_depth",
    "faq_toggle",
    "breadcrumb_click",
    "category_tile_click",
    "home_category_click",
    "home_indicator_click",
    "home_today_click",
    "home_workbench_tab",
    "home_regions_metric",
    "home_regions_cta",
    "home_countries_metric",
    "home_countries_macroregion",
    "home_countries_cta",
    "home_countries_map_select",
    "nav_category_open",
    "nav_link_click",
    "nav_mobile_toggle",
    "related_indicator_click",
    "related_link_click",
    "source_link_click",
    "region_crosslink_click",
    "regions_map_metric",
    "regions_map_select",
    "regions_map_timeline",
    "regions_view_toggle",
    "regions_contrasts_shuffle",
    "calendar_day_select",
    "calendar_clear_day",
    "calendar_month_nav",
    "calendar_source_filter",
    "calc_breakdown",
    "calc_chart_mode",
    "calc_direction",
    "calc_preset",
    "demographics_chart_type",
    "table_page",
    "table_search",
    "table_sort",
    "embed_code_tab",
    "embed_indicator_select",
    "embed_option_toggle",
    "embed_period_change",
    "embed_size_change",
    "embed_theme_change",
    "embed_type_change",
}

# --- technical: не цели (ошибки, показы, consent, негативные сигналы) ---
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
    "regions_map_gif_blocked",
    "compare_limit_hit",
    "experiment_exposure",
    "embed_runtime_view",   # сигнал дистрибуции — своя карточка, не конверсия
    "search_abandon",       # негативный сигнал «искал и не нашёл»
    "outbound_link",        # уход с сайта — не вовлечение
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
    "regions_map_gif_download": 8,
    "oauth_start": 5,
    "header_register_click": 4,
    "forecast_view": 4,
    "search_select": 3,
}

# Скоринг: одно событие учитывается максимум N раз на посетителя за окно —
# иначе scroll_depth (4 выстрела на страницу) и indicator_view (авто-событие)
# делают «начитавшего» бота ценнее человека со скачиванием.
SCORE_EVENT_CAP = 3


def tier_for_event(event_name: str) -> str:
    """Tier события. Неперечисленное — engagement (страховка для будущих
    событий; тест требует явной классификации всего реестра track.js)."""
    if event_name in _MACRO:
        return TIER_MACRO
    if event_name in _MICRO:
        return TIER_MICRO
    if event_name in _INTENT:
        return TIER_INTENT
    if event_name in _TECHNICAL:
        return TIER_TECHNICAL
    return TIER_ENGAGEMENT


def weight_for_event(event_name: str) -> int:
    return _WEIGHT_OVERRIDES.get(event_name, TIER_WEIGHTS[tier_for_event(event_name)])


def is_conversion(event_name: str) -> bool:
    """Событие считается конверсией (для воронки и «истинной конверсии»).
    intent намеренно исключён: клик по кнопке «Регистрация» — не достижение."""
    return tier_for_event(event_name) in (TIER_MACRO, TIER_MICRO)


def explicit_events() -> set[str]:
    """Все явно классифицированные события (для теста полноты реестра)."""
    return _MACRO | _MICRO | _INTENT | _ENGAGEMENT | _TECHNICAL
