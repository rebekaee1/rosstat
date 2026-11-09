"""Истёкший токен Яндекса — одно понятное сообщение вместо четырёх разных (09.11.2026).

С 06.11.2026 токен Вебмастера (`RUSTATS_YANDEX_WEBMASTER_TOKEN`) истёк: login.yandex.ru отвечает `expired_token`,
API Вебмастера — 403 `INVALID_OAUTH_TOKEN`. Каждый день это давало «Сбой фоновой задачи webmaster_queries_daily»,
два «Webmaster recrawl: квота/пользователь недоступны» и в Пульсе «SEO-отчёт недоступен (fetch failed)». Причина одна,
и чинит её только человек: токен выдаётся входом в аккаунт Яндекса в браузере.

`is_token_expired` узнаёт такой отказ, `report_token_expired` пишет одно сообщение `token_expired` на каждый
истёкший токен: владелец 09.11.2026 — «токен вебмастера я не смогу, они больше не показывают ничего нормально».
Повторять напоминание каждый день бессмысленно; новое сообщение придёт, только если в настройках появится другой
токен и он тоже истечёт. Ключ — отпечаток токена (sha256, не сам токен).
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

KIND = "token_expired"
# Год: фактически «один раз на токен» (state-Redis не вечен, через год напомнить не лишне).
REPEAT_SECONDS = 365 * 24 * 3600
_EXPIRED_CODES = ("INVALID_OAUTH_TOKEN", "EXPIRED_TOKEN")

SERVICE_LABELS = {
    "webmaster": "Яндекс Вебмастеру",
    "metrika": "Яндекс Метрике",
}
SERVICE_EFFECTS = {
    "webmaster": "не обновляются поисковые запросы из Яндекса, индексация и переобход страниц",
    "metrika": "не обновляются визиты и источники трафика",
}


def is_token_expired(exc: BaseException | None) -> bool:
    """Отказ Яндекса из-за просроченного или отозванного токена (не нехватка прав, не сеть)."""
    if exc is None:
        return False
    from app.services.yandex_client import YandexApiError

    if not isinstance(exc, YandexApiError) or exc.status_code not in (401, 403):
        return False
    payload = exc.payload
    text = str(payload).upper() if payload is not None else ""
    return any(code in text for code in _EXPIRED_CODES) or "EXPIRED" in text


def service_for(exc: BaseException) -> str:
    """Какой сервис отказал: пути API Вебмастера начинаются с /v4/, остальное у нас - Метрика (management/stat)."""
    return "webmaster" if "/v4/" in str(exc) else "metrika"


def expired_text(service: str) -> str:
    label = SERVICE_LABELS.get(service, service)
    effect = SERVICE_EFFECTS.get(service, "данные этого сервиса не обновляются")
    return (
        f"🟠 <b>Истёк доступ к {label}</b>\n"
        f"Пока токен не обновлён, {effect}. Сайт работает как обычно, остальная статистика собирается.\n"
        f"Это сообщение больше не повторится. Если появится новый токен — напиши Claude, он его подключит."
    )


def _token_fingerprint(service: str) -> str:
    import hashlib

    from app.config import settings

    token = {
        "webmaster": getattr(settings, "yandex_webmaster_token", ""),
        "metrika": getattr(settings, "yandex_metrika_read_token", ""),
    }.get(service, "") or ""
    return hashlib.sha256(token.encode()).hexdigest()[:16]


async def report_token_expired(service: str = "webmaster") -> bool:
    """Одно сообщение на истёкший токен сервиса. True — отправлено сейчас."""
    from app.services.alerting import alert_muted, send_telegram

    if await alert_muted(f"{KIND}:{service}:{_token_fingerprint(service)}", REPEAT_SECONDS):
        return False
    logger.error("Yandex %s token expired", service)
    await send_telegram(expired_text(service), kind=KIND)
    return True
