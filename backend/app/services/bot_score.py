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

Отсутствие бот-сигнала не доказывает человека. Пустые сессии остаются
неопределёнными; веса нельзя подгонять к другому счётчику с иной популяцией.
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
    r"|meta-externalagent|meta-externalfetcher|okhttp|java/|libwww|scrapy|feedfetcher|facebookexternalhit|preview",
    re.IGNORECASE,
)

# Больше стольких сессий с одного visitor за МСК-день — машинная частота.
VISITOR_SESSION_FLOOD = 30  # within one MSK calendar day


@dataclass(frozen=True)
class SessionSignals:
    """Всё, что сессионизация знает о сессии к моменту скоринга."""
    pageviews: int
    clicks: int
    moves: int              # событий move (мышь/тач) внутри сессии
    active_ms: int          # суммарное активное время из dwell
    max_scroll_pct: int     # максимальная глубина скролла из dwell
    synthetic_clicks: int   # кликов с isTrusted=false (скриптовые)
    visitor_sessions: int   # сессий этого visitor за МСК-день
    # Портрет (behavior_sessions), может отсутствовать у старых данных:
    has_portrait: bool = False
    is_webdriver: bool = False
    ua_raw: str | None = None
    device_type: str | None = None
    touch: bool | None = None
    screen_w: int | None = None
    screen_h: int | None = None
    cpu_cores: int | None = None
    # Сколько клиентских сессий в тот же МСК-день имели ТОЧНО такой же портрет
    # устройства (`portrait_fingerprint`) — считает сессионизация по окну.
    portrait_cluster: int = 0


# Больше стольких логических ядер у потребительских устройств не бывает
# (Mac до 32, игровые/рабочие ПК до 64); 65+ — облачная VM или подмена.
SERVER_CPU_CORES = 64


def _square_desktop_screen(s: SessionSignals) -> bool:
    """Квадратный экран десктопа — окно headless-браузера, не монитор.

    Ферма 2026-09-20..29 (Alibaba Cloud SG): 1366×1366, окно == экран, UA
    подменён на обычный Chrome. За 60 дней прода — 55k сессий фермы и ни
    одного человека с квадратным десктопным экраном.
    """
    return bool(
        s.has_portrait and s.device_type == "desktop"
        and s.screen_w and s.screen_w >= 600 and s.screen_w == s.screen_h
    )


# Ферма 2026-10 (Windows Chrome 1920×1080 и 1280×1200, пояс Asia/Shanghai вне
# Китая, случайные cpu/memory): один и тот же портрет повторяется десятки раз
# за день без единого движения, клика и скролла. Измерено 23–26.10.2026: из 1828
# сессий в кластерах ≥10 следы ввода были у 11, и все 11 — из России (люди);
# в кластерах ≥10 живут 5–70% десктопных сессий дня, у русских — единицы.
PORTRAIT_CLUSTER_MIN = 10


def portrait_fingerprint(day: str, p: Any) -> tuple | None:
    """Ключ «одинаковое устройство» для десктопного портрета; None — не считать.

    День — МСК-день (строка ГГГГ-ММ-ДД). Мобильные не учитываем: у iPhone одной
    модели портрет совпадает честно. dpr/память приводим к float, чтобы ключ
    не зависел от Decimal/float драйвера.
    """
    if p is None or getattr(p, "device_type", None) != "desktop":
        return None
    def num(v):
        return None if v is None else float(v)
    return (
        str(day), getattr(p, "screen_w", None), getattr(p, "screen_h", None),
        getattr(p, "viewport_w", None), getattr(p, "viewport_h", None),
        num(getattr(p, "dpr", None)), getattr(p, "cpu_cores", None),
        num(getattr(p, "device_memory", None)), getattr(p, "conn_type", None),
        getattr(p, "color_scheme", None), getattr(p, "language", None),
        getattr(p, "timezone", None),
    )


def _no_input_traces(s: SessionSignals) -> bool:
    """Нет мыши, кликов, скролла и активного времени. Dwell сам по себе
    следом не считается — headless шлёт pagehide не хуже людей."""
    return (
        s.clicks == 0
        and s.moves == 0
        and s.max_scroll_pct == 0
        and s.active_ms == 0
    )


def _no_human_traces(s: SessionSignals) -> bool:
    """Паттерн 41% прод-сессий: зашёл на одну страницу и не оставил ни одного
    следа устройства ввода. Тач-скролл мобильных даёт scroll_pct > 0 —
    мобильный человек без мыши сюда не попадает."""
    return s.pageviews <= 1 and _no_input_traces(s)


def _ghost_crawl(s: SessionSignals) -> bool:
    """Обход многих URL подряд без ввода (скрейп каталога в одной сессии)."""
    return s.pageviews >= 4 and _no_input_traces(s)


# (имя сигнала, вес, предикат) — единая точка калибровки и разложения счёта.
HEURISTICS: tuple[tuple[str, int, Any], ...] = (
    ("webdriver", 100, lambda s: s.is_webdriver),
    ("bot_ua", 100, lambda s: is_known_bot_ua(s.ua_raw)),
    ("no_human_traces", 20, _no_human_traces),
    ("ghost_crawl", 40, _ghost_crawl),
    # Все клики сессии синтетические (isTrusted=false) — кликает скрипт.
    ("synthetic_clicks", 60, lambda s: s.synthetic_clicks > 0 and s.synthetic_clicks >= s.clicks),
    ("visitor_flood", 40, lambda s: s.visitor_sessions > VISITOR_SESSION_FLOOD),
    # Железо, которого нет у людей: сигналы не зависят от строки UA, которую
    # headless-фермы подменяют первой.
    ("square_desktop_screen", 60, _square_desktop_screen),
    ("server_cpu", 60, lambda s: s.cpu_cores is not None and s.cpu_cores > SERVER_CPU_CORES),
    # Тот же портрет ≥10 раз за день и ни одного следа ввода: клонированный
    # профиль. Сигнал не зависит от UA и IP; ввод (даже один клик) его снимает.
    ("portrait_cluster", 60, lambda s: s.portrait_cluster >= PORTRAIT_CLUSTER_MIN and _no_input_traces(s)),
    # Неконсистентность устройства: мобильный UA без touch или нулевой экран.
    ("device_mismatch", 20, lambda s: s.has_portrait and (
        (s.device_type == "mobile" and s.touch is False)
        or (s.screen_w is not None and s.screen_w <= 0)
    )),
    # Портрета нет вовсе (session_start не дошёл) при полном отсутствии следов
    # человека уже покрыто no_human_traces; сам по себе пропуск портрета не
    # штрафуем — 21% исторических сессий без портрета из-за бага доставки.
)


def is_known_bot_ua(ua: str | None) -> bool:
    """Shared explicit automation identity; no behavioural inference."""
    return bool(ua and _BOT_UA_RE.search(ua))


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
