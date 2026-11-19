"""Свежесть рядов, которые мы обещаем присылать (совет 19.11.2026, стратегия привлечения, п. 4.3).

Зачем. На главных страницах появляется строка «Новое значение — {дата}. Присылать?», бот и письма шлют
новое значение подписчикам. Общий сторож свежести (`app.services.freshness`) считает недельный ряд
устаревшим только через 35 дней после конца периода — для обещания «новая цена в среду» это поздно.
19.11.2026 дизель стоял на 9.11, хотя Росстат выложил цену на 16.11 ещё 18.11 (бюллетень в PDF, парсер
ждал HTML) — общий сторож молчал.

Правила по видам рядов (дни считаются от «сегодня» по Москве):

* топливо (`fuel-*`, регистрация по понедельникам, бюллетень по средам, иногда в четверг): ряд опаздывает,
  если последней точке 11 дней и больше — к пятнице нет понедельника этой недели;
* дневные ряды ЦБ (золото, курсы, ключевая ставка): 5 дней и больше — пропущено больше длинных выходных;
* месячные ряды с официальным календарём (ИПЦ, ставки по вкладам и ипотеке): если выход по календарю
  сайта был 2 дня назад или раньше, а успешной загрузки с новыми точками с этого дня нет — опоздание.
  Без календаря — 75 дней от конца месяца последней точки (как у бота, `_FRESH_DAYS`).

Список тем — `public_bot.TOPICS` (их же предлагает строка на сайте). Результат — для сообщения владельцу
(вид `promised_freshness`, уходит в утреннюю сводку спокойного режима) и для честной подписи
«Источник задерживает данные» на странице и в боте.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import func, or_, select

logger = logging.getLogger(__name__)

MSK = ZoneInfo("Europe/Moscow")
FUEL_LATE_DAYS = 11
DAILY_LATE_DAYS = 5
MONTHLY_FALLBACK_DAYS = 75
RELEASE_GRACE_DAYS = 2
RELEASE_LOOKBACK_DAYS = 45

# Темы бота, у которых есть официальный календарь выхода (тот же словарь, что `public_bot._RELEASE_CODE`).
RELEASE_CODE_BY_TOPIC = {"inflation": "cpi", "deposit": "deposit-rate", "mortgage": "mortgage-rate"}

STATUS_OK = "ok"
STATUS_LATE = "late"
STATUS_EMPTY = "empty"


@dataclass(frozen=True)
class PromisedTopic:
    key: str
    code: str        # ряд, который видит человек (`indicators.code`)
    title: str
    kind: str        # fuel | daily | monthly
    load_code: str   # ряд, чью загрузку проверяем (у производной инфляции — первоисточник ИПЦ)


@dataclass(frozen=True)
class TopicFreshness:
    topic: PromisedTopic
    status: str
    last_date: date | None
    reason: str
    release_date: date | None = None

    def as_dict(self) -> dict:
        return {
            "topic": self.topic.key, "code": self.topic.code, "title": self.topic.title,
            "status": self.status, "last_date": self.last_date.isoformat() if self.last_date else None,
            "release_date": self.release_date.isoformat() if self.release_date else None,
            "reason": self.reason,
        }


def promised_topics() -> list[PromisedTopic]:
    from app.services.public_bot import TOPICS

    out: list[PromisedTopic] = []
    for t in TOPICS.values():
        if t.indicator.startswith("fuel-"):
            kind = "fuel"
        elif t.key in RELEASE_CODE_BY_TOPIC:
            kind = "monthly"
        else:
            kind = "daily"
        out.append(PromisedTopic(t.key, t.indicator, t.title, kind, RELEASE_CODE_BY_TOPIC.get(t.key, t.indicator)))
    return out


def _month_end(d: date) -> date:
    nxt = date(d.year + (d.month == 12), d.month % 12 + 1, 1)
    return nxt - timedelta(days=1)


def judge(
    topic: PromisedTopic,
    *,
    today: date,
    last_date: date | None,
    last_load_at: datetime | None,
    last_release: date | None,
) -> TopicFreshness:
    """Чистое правило: опаздывает ли ряд, и как это сказать человеку."""
    if last_date is None:
        return TopicFreshness(topic, STATUS_EMPTY, None, "в базе нет точек")
    age = (today - last_date).days
    if topic.kind == "fuel":
        if age >= FUEL_LATE_DAYS:
            return TopicFreshness(topic, STATUS_LATE, last_date,
                                  f"последняя цена на {last_date:%d.%m}, {age} дн. назад; новая выходит еженедельно")
        return TopicFreshness(topic, STATUS_OK, last_date, f"цена на {last_date:%d.%m}")
    if topic.kind == "daily":
        if age >= DAILY_LATE_DAYS:
            return TopicFreshness(topic, STATUS_LATE, last_date, f"последнее значение {last_date:%d.%m}, {age} дн. назад")
        return TopicFreshness(topic, STATUS_OK, last_date, f"значение на {last_date:%d.%m}")
    # monthly
    if last_release is not None:
        loaded_after = last_load_at is not None and last_load_at.date() >= last_release
        if not loaded_after:
            return TopicFreshness(topic, STATUS_LATE, last_date,
                                  f"выход по календарю {last_release:%d.%m}, новых данных с тех пор нет",
                                  release_date=last_release)
        return TopicFreshness(topic, STATUS_OK, last_date, f"загружено после выхода {last_release:%d.%m}",
                              release_date=last_release)
    lag = (today - _month_end(last_date)).days
    if lag >= MONTHLY_FALLBACK_DAYS:
        return TopicFreshness(topic, STATUS_LATE, last_date,
                              f"последний месяц {last_date:%m.%Y}, {lag} дн. после его конца")
    return TopicFreshness(topic, STATUS_OK, last_date, f"месяц {last_date:%m.%Y}")


async def collect_promised_freshness(db, today: date | None = None) -> list[TopicFreshness]:
    from app.api.calendar import _public_calendar_conditions
    from app.models import EconomicEvent, FetchLog, Indicator, IndicatorData

    today = today or datetime.now(MSK).date()
    topics = promised_topics()
    view_codes = sorted({t.code for t in topics})
    load_codes = sorted({t.load_code for t in topics})

    last_dates = dict((await db.execute(
        select(Indicator.code, func.max(IndicatorData.date))
        .join(IndicatorData, IndicatorData.indicator_id == Indicator.id)
        .where(Indicator.code.in_(view_codes))
        .group_by(Indicator.code)
    )).all())
    last_loads = dict((await db.execute(
        select(Indicator.code, func.max(FetchLog.started_at))
        .join(FetchLog, FetchLog.indicator_id == Indicator.id)
        .where(Indicator.code.in_(load_codes), FetchLog.status == "success",
               or_(FetchLog.records_added > 0, FetchLog.records_updated > 0))
        .group_by(Indicator.code)
    )).all())
    release_codes = sorted(set(RELEASE_CODE_BY_TOPIC.values()))
    releases = dict((await db.execute(
        select(Indicator.code, func.max(EconomicEvent.scheduled_date))
        .join(EconomicEvent, EconomicEvent.indicator_id == Indicator.id)
        .where(Indicator.code.in_(release_codes),
               EconomicEvent.scheduled_date <= today - timedelta(days=RELEASE_GRACE_DAYS),
               EconomicEvent.scheduled_date >= today - timedelta(days=RELEASE_LOOKBACK_DAYS),
               *_public_calendar_conditions())
        .group_by(Indicator.code)
    )).all())

    return [
        judge(
            t, today=today, last_date=last_dates.get(t.code), last_load_at=last_loads.get(t.load_code),
            last_release=releases.get(t.load_code) if t.kind == "monthly" else None,
        )
        for t in topics
    ]


def format_message(rows: list[TopicFreshness]) -> str | None:
    late = [r for r in rows if r.status != STATUS_OK]
    if not late:
        return None
    lines = ["🟡 <b>Опаздывают ряды, которые мы обещаем присылать</b>"]
    lines += [f"— {r.topic.title}: {r.reason}" for r in late]
    lines.append("Подписчики не получат новое значение, пока ряд не догонит источник.")
    return "\n".join(lines)


def signature(rows: list[TopicFreshness]) -> str:
    return "|".join(f"{r.topic.key}:{r.last_date}" for r in rows if r.status != STATUS_OK)


SIGNATURE_KEY = "fe:promised_freshness:last_sent"
SIGNATURE_TTL_S = 7 * 24 * 3600


async def promised_freshness_job() -> dict:
    """Раз в сутки: одно сообщение владельцу, если опоздание новое (та же картина — не чаще раза в неделю)."""
    from app.database import async_session
    from app.services.alerting import send_telegram

    async with async_session() as db:
        rows = await collect_promised_freshness(db)
    late = [r.as_dict() for r in rows if r.status != STATUS_OK]
    logger.info("Promised freshness: %d late of %d: %s", len(late), len(rows), late)
    message = format_message(rows)
    notified = False
    if message:
        sig = signature(rows)
        previous = None
        redis = None
        try:
            from app.core.cache import get_state_redis

            redis = await get_state_redis()
            previous = await redis.get(SIGNATURE_KEY)
        except Exception:  # noqa: BLE001 — без Redis шлём, лишнее сообщение лучше пропущенного
            logger.debug("promised freshness: state redis unavailable", exc_info=True)
        if isinstance(previous, bytes):
            previous = previous.decode()
        if previous != sig:
            notified = bool(await send_telegram(message, kind="promised_freshness"))
            if notified and redis is not None:
                try:
                    await redis.set(SIGNATURE_KEY, sig, ex=SIGNATURE_TTL_S)
                except Exception:  # noqa: BLE001
                    logger.debug("promised freshness: signature not stored", exc_info=True)
    return {"late": late, "total": len(rows), "notified": notified, "at": datetime.now(timezone.utc).isoformat()}
