"""Таргеты дерева метрик BI (этап 3 плана «Аналитика 2.0», 2026-07-06).

Вычислены из фактических данных первой недели (1 398 визитов за 7 дней,
~200/день; вовлечение 56%; micro-конверсия 1,1%; macro 0,9%; возвраты 20,6%)
и траектории владельца 10k → 40k → 100k → 1M визитов/день.

Пересматриваются ежемесячно — это конфиг, не код: правишь числа, экраны
подхватывают. Статус узла: зелёный ≥ 95% таргета, жёлтый 70–95%, красный <70%.
"""

# Вехи North Star (визиты/день, 7-дневное среднее) на пути к 10k.
NORTH_STAR_MILESTONES = [200, 500, 1_000, 3_000, 10_000]

TARGETS = {
    # North Star: визиты/день (наши серверные сессии; сверка — визиты Метрики)
    "visits_per_day": 500,
    # Драйвер 1 — Привлечение: визиты/день по каналам (сумма = North Star)
    "acquisition_search_share": 0.5,   # доля поиска — фундамент органики
    # Драйвер 2 — Вовлечение: % сессий с активным dwell>15с / скроллом>50% / 2+ страниц
    "engagement_rate": 0.65,
    # Драйвер 3 — Конверсия
    "micro_conversion_rate": 0.04,     # micro-цели / вовлечённые сессии
    "macro_conversion_rate": 0.015,    # macro-цели / вовлечённые сессии
    # Драйвер 4 — Удержание: % посетителей, вернувшихся в течение 7 дней
    "retention_7d": 0.30,
}

GREEN_AT = 0.95   # ≥95% таргета — зелёный
YELLOW_AT = 0.70  # 70–95% — жёлтый; ниже — красный


def status_for(value: float, target: float) -> str:
    if target <= 0:
        return "green"
    ratio = value / target
    if ratio >= GREEN_AT:
        return "green"
    if ratio >= YELLOW_AT:
        return "yellow"
    return "red"


def next_milestone(current: float) -> int:
    for m in NORTH_STAR_MILESTONES:
        if current < m:
            return m
    return NORTH_STAR_MILESTONES[-1]
