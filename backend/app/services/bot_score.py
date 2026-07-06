"""Антибот-скоринг серверных сессий (BI 2.1, этап 3).

Проблема, измеренная CTO-аудитом 2026-07-06: 41% наших сессий — боты
(1 pageview, ноль кликов, ноль движений мыши, ноль dwell), из-за чего наши
сессии превышали визиты Метрики в 2,0–2,2 раза (Метрика роботов фильтрует).
Пока счётчик не очищен, он не может быть первоисточником истины BI.

Дизайн: чистая функция `score_session` возвращает счёт 0..100 по аддитивным
эвристикам; `is_bot = score >= BOT_THRESHOLD`. Эвристики — таблица
(имя, вес, предикат), чтобы калибровка сводилась к правке весов, а витрина
роботности могла разложить счёт по сигналам. Вызывается из сессионизации
(analytics_rollups.sessionize) на каждый пересчёт окна — пересчёт истории
автоматически перечищает все витрины (они фильтруют по is_bot).

Калибровка: веса подобраны так, чтобы небот-сессии попадали в коридор ±15%
к визитам Метрики (ежедневная сверка — analytics_alerts.check_bot_calibration).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

# Порог «это бот». Сигналы-неопровержимости (webdriver, bot-UA) весят >= порога
# сами по себе; поведенческие складываются.
BOT_THRESHOLD = 60

# Явные боты по User-Agent (Метрика их тоже отсекает).
_BOT_UA_RE = re.compile(
    r"bot|spider|crawl|slurp|headless|phantom|selenium|puppeteer|playwright"
    r"|python-requests|python/|aiohttp|httpx|curl/|wget/|go-http-client"
    r"|okhttp|java/|libwww|scrapy|feedfetcher|facebookexternalhit|preview",
    re.IGNORECASE,
)

# Больше стольких сессий с одного visitor за окно пересчёта — машинная частота.
VISITOR_SESSION_FLOOD = 30


@dataclass(frozen=True)
class SessionSignals:
    """Всё, что сессионизация знает о сессии к моменту скоринга."""
    pageviews: int
    clicks: int
    moves: int              # событий move (мышь/тач) внутри сессии
    active_ms: int          # суммарное активное время из dwell
    max_scroll_pct: int     # максимальная глубина скролла из dwell
    synthetic_clicks: int   # кликов с isTrusted=false (скриптовые)
    visitor_sessions: int   # сессий этого visitor в окне пересчёта
    # Портрет (behavior_sessions), может отсутствовать у старых данных:
    has_portrait: bool = False
    is_webdriver: bool = False
    ua_raw: str | None = None
    device_type: str | None = None
    touch: bool | None = None
    screen_w: int | None = None
    screen_h: int | None = None


def _no_human_traces(s: SessionSignals) -> bool:
    """Паттерн 41% прод-сессий: зашёл на одну страницу и не оставил ни одного
    следа устройства ввода. Сам факт доставки dwell следом НЕ считается —
    headless-браузеры доставляют dwell на pagehide не хуже людей (проверено
    на калибровке 04–05.07); человеческие следы внутри dwell — скролл и
    активное время. Тач-скролл мобильных даёт scroll_pct > 0 — мобильный
    человек без мыши и кликов сюда не попадает."""
    return (
        s.pageviews <= 1
        and s.clicks == 0
        and s.moves == 0
        and s.max_scroll_pct == 0
        and s.active_ms == 0
    )


# (имя сигнала, вес, предикат) — единая точка калибровки и разложения счёта.
HEURISTICS: tuple[tuple[str, int, Any], ...] = (
    ("webdriver", 100, lambda s: s.is_webdriver),
    ("bot_ua", 100, lambda s: bool(s.ua_raw and _BOT_UA_RE.search(s.ua_raw))),
    ("no_human_traces", 70, _no_human_traces),
    # Все клики сессии синтетические (isTrusted=false) — кликает скрипт.
    ("synthetic_clicks", 60, lambda s: s.synthetic_clicks > 0 and s.synthetic_clicks >= s.clicks),
    ("visitor_flood", 40, lambda s: s.visitor_sessions > VISITOR_SESSION_FLOOD),
    # Неконсистентность устройства: мобильный UA без touch или нулевой экран.
    ("device_mismatch", 20, lambda s: s.has_portrait and (
        (s.device_type == "mobile" and s.touch is False)
        or (s.screen_w is not None and s.screen_w <= 0)
    )),
    # Портрета нет вовсе (session_start не дошёл) при полном отсутствии следов
    # человека уже покрыто no_human_traces; сам по себе пропуск портрета не
    # штрафуем — 21% исторических сессий без портрета из-за бага доставки.
)


def score_session(s: SessionSignals) -> int:
    """Аддитивный счёт 0..100 по таблице эвристик."""
    score = 0
    for _name, weight, pred in HEURISTICS:
        if pred(s):
            score += weight
    return min(score, 100)


def signal_breakdown(s: SessionSignals) -> list[str]:
    """Имена сработавших сигналов — для витрины роботности."""
    return [name for name, _w, pred in HEURISTICS if pred(s)]
