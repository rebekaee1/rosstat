"""«Фальшивая дверь» платного API: замер спроса на «API и выгрузку с прогнозами».

Фронт показывает точки входа только при `api_interest_enabled` (флаг отдаёт
GET /api-interest/config), гость или пользователь оставляет почту + цель
использования, владелец получает заявку в Telegram («Заявка на API»).

Хранения заявок в БД нет: новой схемы/миграции нет сознательно — заявка идёт
в уже существующий outbox Telegram (`telegram_outbox`, как обратная связь) и
досылается тем же job'ом при сбое доставки. Почта не пишется в логи и в
frontend_events (события трекинга несут только use_case/source).

Защита (эндпоинт открыт гостям, поэтому CSRF-сессии нет, как у /auth/login и
/analytics/events): honeypot-поле, лимит заявок на IP в state-Redis (поверх
общего RateLimitMiddleware), антидубль по хэшу почты, отсев шумовых UA.
"""
from __future__ import annotations

import hashlib
import logging
import re

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, field_validator

from app.config import settings
from app.core.cache import get_state_redis
from app.services.alerting import API_INTEREST_USE_CASES, notify_api_interest
from app.services.api_i18n import api_detail
from app.services.locale import get_locale
from app.services.scrape_guard import is_noise_client_ua

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api-interest", tags=["api-interest"])

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_CODE_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,79}$")
SOURCES = ("indicator", "limit_modal")

_IP_LIMIT = 5                  # заявок с одного IP …
_IP_WINDOW_SECONDS = 3600      # … в час
_DUP_TTL_SECONDS = 24 * 3600   # повтор той же почты за сутки — не шлём второй раз
_PREFIX = "fe:api_interest:"


class ApiInterestIn(BaseModel):
    email: str
    use_case: str
    comment: str | None = None
    source: str = "indicator"
    indicator_code: str | None = None
    # Honeypot: человек поле не видит (скрыто CSS, tabindex=-1), бот заполняет.
    website: str | None = None

    @field_validator("email")
    @classmethod
    def _email_ok(cls, v: str) -> str:
        v = (v or "").strip()
        if len(v) > 254 or not _EMAIL_RE.match(v):
            raise ValueError(api_detail("Некорректный email", "Invalid email"))
        return v

    @field_validator("use_case")
    @classmethod
    def _use_case_ok(cls, v: str) -> str:
        if v not in API_INTEREST_USE_CASES:
            raise ValueError(api_detail("Выберите, для чего нужны данные", "Choose what you need the data for"))
        return v

    @field_validator("comment")
    @classmethod
    def _comment_ok(cls, v: str | None) -> str | None:
        v = (v or "").strip()
        if len(v) > 1000:
            raise ValueError(api_detail("Комментарий слишком длинный", "Comment is too long"))
        return v or None

    @field_validator("source")
    @classmethod
    def _source_ok(cls, v: str) -> str:
        return v if v in SOURCES else "indicator"

    @field_validator("indicator_code")
    @classmethod
    def _code_ok(cls, v: str | None) -> str | None:
        v = (v or "").strip().lower()
        return v if _CODE_RE.match(v) else None


def _client_ip(request: Request) -> str:
    from app.main import pick_client_ip  # лениво: app.main импортирует роутеры

    return pick_client_ip(
        request.headers.get("x-forwarded-for", ""),
        request.client.host if request.client else "unknown",
    )


def _telegram_configured() -> bool:
    return bool(settings.telegram_bot_token and settings.telegram_chat_id)


@router.get("/config")
async def api_interest_config(response: Response):
    """Публичный флаг для фронта (по образцу /analytics/replay/config)."""
    response.headers["Cache-Control"] = "no-store"
    return {"enabled": bool(settings.api_interest_enabled)}


@router.post("")
async def submit_api_interest(body: ApiInterestIn, request: Request):
    if not settings.api_interest_enabled:
        raise HTTPException(status_code=404, detail="Not found")
    if is_noise_client_ua(request.headers.get("user-agent")):
        return {"ok": True}
    if body.website:
        # Бот: изображаем успех, ничего не отправляем и не логируем содержимое.
        return {"ok": True}

    ip = _client_ip(request)
    email_hash = hashlib.sha256(body.email.strip().lower().encode("utf-8")).hexdigest()
    try:
        redis = await get_state_redis()
        ip_key = f"{_PREFIX}ip:{ip}"
        count = await redis.incr(ip_key)
        if count == 1:
            await redis.expire(ip_key, _IP_WINDOW_SECONDS)
        if count > _IP_LIMIT:
            raise HTTPException(
                status_code=429,
                detail=api_detail(
                    "Слишком много заявок. Попробуйте позже",
                    "Too many requests. Try again later",
                ),
                headers={"Retry-After": str(_IP_WINDOW_SECONDS)},
            )
        if not await redis.set(f"{_PREFIX}dup:{email_hash}", "1", nx=True, ex=_DUP_TTL_SECONDS):
            return {"ok": True}  # уже приняли — повторно владельцу не шлём
    except HTTPException:
        raise
    except Exception:  # noqa: BLE001
        # fail-open как у lockout: недоступный Redis не должен ронять форму.
        # Ни почту, ни тело в лог не пишем.
        logger.warning("api_interest: state-Redis unavailable, limits skipped")

    delivered = False
    try:
        delivered = await notify_api_interest({
            "email": body.email,
            "use_case": body.use_case,
            "comment": body.comment,
            "source": body.source,
            "indicator_code": body.indicator_code,
            "locale": get_locale(),
        })
    except Exception as exc:  # noqa: BLE001
        logger.warning("api_interest: notify failed (%s)", type(exc).__name__)
    if not delivered and not _telegram_configured():
        # Принять заявку некуда: честная ошибка лучше «спасибо» в пустоту.
        # Метку «уже приняли» снимаем, чтобы повтор не считался дублем.
        try:
            await (await get_state_redis()).delete(f"{_PREFIX}dup:{email_hash}")
        except Exception:  # noqa: BLE001
            pass
        raise HTTPException(
            status_code=503,
            detail=api_detail("Сервис временно недоступен", "Service temporarily unavailable"),
        )
    # Доставка не удалась при настроенном Telegram — сообщение лежит в outbox
    # и будет досланo job'ом; пользователю это не показываем.
    return {"ok": True}
