"""Условные профили для предпросмотра без живых людей (ADR-0033).

Собраны по обезличенным суммам боевого 14.11.2026 (самые смотримые и скачиваемые ряды,
доля поиска и регионов), а не по действиям конкретного подписчика. Нужны, чтобы увидеть письмо
каждого уровня данных («много», «мало», «нет») на любом стенде.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from app.services.newsletter_personal.profile import Signal
from app.services.newsletter_personal.signals import UserSignals
from app.services.newsletter_personal.subjects import parse_key

PERSONA_IDS = {
    "rich": "00000000-0000-4000-8000-00000000a001",
    "light": "00000000-0000-4000-8000-00000000a002",
    "cold": "00000000-0000-4000-8000-00000000a003",
    "rich-en": "00000000-0000-4000-8000-00000000a011",
    "light-en": "00000000-0000-4000-8000-00000000a012",
    "cold-en": "00000000-0000-4000-8000-00000000a013",
}

# (вид сигнала, ключ предмета, дней назад)
_SIGNALS = {
    "rich": [
        ("download", "ru:fuel-diesel", 3), ("view", "ru:fuel-diesel", 3), ("view", "ru:fuel-diesel", 10),
        ("view", "ru:fuel-ai92", 4), ("download", "ru:fuel-ai92", 20),
        ("view", "ru:cpi", 2), ("view", "ru:cpi", 9), ("forecast_view", "ru:cpi", 9),
        ("search_select", "ru:key-rate", 6), ("view", "ru:key-rate", 6),
        ("view", "ru:wages-nominal", 15), ("search_select", "ru:wages-nominal", 15),
        ("view", "r:sverdlovskaya-oblast:ceni-ai95", 5), ("view", "reg:sverdlovskaya-oblast", 5),
        ("search_select", "r:sverdlovskaya-oblast:ceni-ai95", 5),
        ("view", "ru:usd-rub", 1), ("view", "ru:brent", 8), ("compare", "ru:gold", 12),
    ],
    "light": [
        ("view", "ru:usd-rub", 6), ("search_select", "ru:deposit-rate", 9), ("view", "ru:deposit-rate", 9),
        ("search_select", "ru:brent", 25),
    ],
    "cold": [],
    "rich-en": [
        ("view", "w:united-states:us-cpi-all", 2), ("download", "w:united-states:us-cpi-all", 2),
        ("view", "w:united-states:us-unemployment-rate", 5), ("search_select", "w:united-states:us-unemployment-rate", 5),
        ("view", "ru:usd-cny", 3), ("download", "ru:usd-cny", 3), ("view", "ru:eur-usd", 7), ("view", "ru:usd-rub", 7),
        ("view", "ru:brent", 4), ("forecast_view", "ru:cpi", 11), ("view", "ru:key-rate", 11),
        ("compare", "w:germany:de-ei_lmhr_m-lm-un-t-tot-sa-pc-act", 14),
    ],
    "light-en": [("view", "w:united-states:us-unemployment-rate", 9), ("search_select", "w:united-states:us-unemployment-rate", 9),
                 ("view", "ru:eur-usd", 20)],
    "cold-en": [],
}


def persona_signals(name: str, *, now: datetime) -> tuple[UserSignals, str]:
    if name not in PERSONA_IDS:
        raise ValueError(f"нет профиля {name}; есть: {', '.join(PERSONA_IDS)}")
    locale = "en" if name.endswith("-en") else "ru"
    us = UserSignals(user_id=PERSONA_IDS[name], created_at=now - timedelta(days=90), locale=locale,
                     country_code="RU" if locale == "ru" else "US", timezone="Europe/Moscow" if locale == "ru"
                     else "America/New_York", last_visit=now - timedelta(days=1))
    for kind, key, days in _SIGNALS[name.replace("-en", "") if name not in _SIGNALS else name]:
        sub = parse_key(key)
        if sub is not None:
            us.signals.append(Signal(kind, sub, now - timedelta(days=days)))
            us.events += 1
            if sub.kind == "r":
                us.signals.append(Signal(kind, parse_key(f"reg:{sub.place}"), now - timedelta(days=days)))
    if locale == "en":
        us.home_country = "united-states" if "rich" in name else None
    return us, locale
