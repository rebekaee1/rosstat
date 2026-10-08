"""Live ticker API endpoint.

`GET /api/v1/ticker/live` — returns the most recent snapshots stored by
`ticker_worker` in Redis. Lightweight (Redis read only, no external API
hops), suitable for client polling at 3-5 second cadence.

FX and BTC are live (MOEX / CBR / Binance). Brent and gold are the same
daily series as their indicator cards (`brent`, `gold-price`), with
`market_open=false` and `as_of_date`.

Response shape:
{
  "lane": "russia",
  "snapshots": [
    {
      "code": "usd-rub-live",
      "price": 71.4775,
      "change_pct": 0.04,
      "market_open": true,
      "fetched_at": "2026-05-22T08:40:26+00:00",
      "source": "MOEX",
      "source_kind": "market",          // market | central_bank | ecb | official
      "source_label": "Биржа",          // «Биржа» / «ЦБ» / «ЕЦБ» по языку хоста
      "as_of": "2026-05-22T08:40:26+00:00",
      "as_of_day": "2026-05-22",        // дата значения одним форматом для живых и дневных рядов
      "age_days": 0,                    // сколько суток значению на момент ответа
      "stale": false                    // true, если значение старше STALE_AFTER_DAYS суток
    },
    {
      "code": "brent",
      "price": 93.26,
      "change_pct": -0.5,
      "market_open": false,
      "fetched_at": "2026-08-15T12:00:00+00:00",
      "source": "EIA",
      "as_of_date": "2026-08-14"
    },
    ...
  ],
  "server_time": "2026-05-22T08:42:11+00:00"
}

`snapshots` is filtered to the fixed set of codes the UI currently uses
(in fixed order) so the client doesn't need to re-sort.
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import get_redis
from app.database import get_db
from app.services.locale import get_locale
from app.services.ticker_sources import source_kind, source_label
from app.tasks.ticker_worker import REDIS_KEY_PREFIX

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ticker", tags=["ticker"])

# Два набора ленты: `russia` — рублевые пары и учётное золото ЦБ;
# `world` — справочные курсы ЕЦБ к доллару и учётное золото ЦБ в ₽/г. Клиент выбирает lane по locale
# (ru → russia, en → world), не по path.
# Золото в долларах за унцию в ленту не ставим: дневной LBMA-ряд нельзя
# перепубликовать без лицензии IBA.
TICKER_SET_RUSSIA = (
    "usd-rub-live",
    "eur-rub-live",
    "cny-rub-live",
    "btc-usd",
    "brent",
    "gold-rub-live",
)
TICKER_SET_WORLD = (
    "eur-usd",
    "gbp-usd",
    "usd-cny",
    "btc-usd",
    "brent",
    "gold-rub-live",
)
TICKER_SETS = {
    "russia": TICKER_SET_RUSSIA,
    "world": TICKER_SET_WORLD,
}
# Совместимость: старый импорт ждал плоский список российского набора.
TICKER_CODES = list(TICKER_SET_RUSSIA)


# Значение старше этого числа суток лента подписывает «не обновлялось». Нефть
# и золото — дневные ряды с задержкой публикации в пару дней, поэтому порог не 1.
STALE_AFTER_DAYS = 3


def _as_of_day(snap: dict) -> date | None:
    """Дата значения (UTC) из `as_of_date`, `as_of` или `fetched_at`, если её можно разобрать."""
    for key in ("as_of_date", "as_of", "fetched_at"):
        raw = snap.get(key)
        if not raw:
            continue
        text = str(raw).strip()
        try:
            if len(text) <= 10:
                return date.fromisoformat(text)
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            if parsed.tzinfo is not None:
                parsed = parsed.astimezone(timezone.utc)
            return parsed.date()
        except ValueError:
            continue
    return None


def add_freshness(snap: dict, now: datetime) -> None:
    """Добавить в снимок единый формат даты и признак давности (поля только дописываются).

    Живые котировки несут время, дневные ряды (нефть, золото ЦБ) только дату:
    клиент подписывал их по-разному, а девятидневное значение нефти выглядело живым.
    `as_of_day` — дата одним форматом, `age_days` — целые сутки до `now`,
    `stale` — старше `STALE_AFTER_DAYS`."""
    day = _as_of_day(snap)
    if day is None:
        snap["as_of_day"] = None
        snap["age_days"] = None
        snap["stale"] = False
        return
    age = max((now.astimezone(timezone.utc).date() - day).days, 0)
    snap["as_of_day"] = day.isoformat()
    snap["age_days"] = age
    snap["stale"] = age > STALE_AFTER_DAYS


# Рублёвые пары, у которых есть и биржевая котировка (лента), и официальный курс ЦБ (страница, конвертер).
_RUB_PAIRS = {
    "usd-rub": "usd-rub-live",
    "eur-rub": "eur-rub-live",
    "cny-rub": "cny-rub-live",
}


def _rate_entry(
    *, price: float, change_pct: float | None, source: str, as_of: str | None, locale: str,
) -> dict:
    kind = source_kind(source)
    return {
        "price": price,
        "change_pct": change_pct,
        "source": source,
        "source_kind": kind,
        "source_label": source_label(kind, source, locale),
        "as_of": as_of,
    }


@router.get("/rates/{pair}")
async def get_rate_basis(
    pair: str, response: Response, db: AsyncSession = Depends(get_db),
) -> dict:
    """Один курс двумя честными числами: «Биржа» (живая котировка) и «ЦБ» (официальный курс на дату).

    Лента показывает биржевое число, страница курса и конвертер считают по официальному курсу ЦБ,
    и они расходятся на 2–3 рубля. Источники не склеиваем: каждое число идёт со своим типом
    источника и датой, а интерфейс подписывает их по этим полям. `market` бывает `null`:
    биржа закрыта или недоступна, остаётся только официальный курс.
    """
    from fastapi import HTTPException
    from sqlalchemy import desc, select

    from app.models import Indicator, IndicatorData

    response.headers["Vary"] = "Host"
    code = (pair or "").strip().lower()
    live_code = _RUB_PAIRS.get(code)
    if live_code is None:
        raise HTTPException(status_code=404, detail="Unsupported pair")
    locale = "en" if get_locale() == "en" else "ru"

    central_bank = None
    ind = (await db.execute(select(Indicator).where(Indicator.code == code))).scalar_one_or_none()
    if ind is not None:
        rows = (
            await db.execute(
                select(IndicatorData.date, IndicatorData.value)
                .where(IndicatorData.indicator_id == ind.id)
                .order_by(desc(IndicatorData.date))
                .limit(2)
            )
        ).all()
        if rows:
            last_date, last_value = rows[0]
            change = None
            if len(rows) > 1 and float(rows[1][1]):
                change = round((float(last_value) - float(rows[1][1])) / float(rows[1][1]) * 100, 2)
            central_bank = _rate_entry(
                price=float(last_value),
                change_pct=change,
                source="Банк России",
                as_of=last_date.isoformat(),
                locale=locale,
            )

    market = None
    try:
        r = await get_redis()
        raw = await r.get(f"{REDIS_KEY_PREFIX}{live_code}")
        if raw is not None:
            snap = json.loads(raw)
            # Если биржа недоступна, воркер подставляет курс ЦБ: это не рыночное число.
            if source_kind(snap.get("source")) == "market":
                market = _rate_entry(
                    price=float(snap["price"]),
                    change_pct=snap.get("change_pct"),
                    source=str(snap.get("source")),
                    as_of=snap.get("as_of") or snap.get("fetched_at"),
                    locale=locale,
                )
    except Exception:
        logger.warning("Rate basis: Redis unavailable, market quote omitted", exc_info=True)

    return {"pair": code, "central_bank": central_bank, "market": market}


@router.get("/live")
async def get_live_ticker(response: Response, lane: str = "world") -> dict:
    # Подписи источника зависят от языка хоста.
    response.headers["Vary"] = "Host"
    codes = TICKER_SETS.get(lane, TICKER_SET_WORLD)
    snapshots: list[dict] = []
    try:
        r = await get_redis()
        keys = [f"{REDIS_KEY_PREFIX}{c}" for c in codes]
        raw_values = await r.mget(*keys)
        for raw in raw_values:
            if raw is None:
                continue
            try:
                snapshots.append(json.loads(raw))
            except (TypeError, ValueError):
                continue
    except Exception:
        # If Redis is unreachable, return an empty list — the UI shows
        # nothing rather than half-broken state. Логируем (Н-19): пустой
        # тикер у всех посетителей не должен быть невидимым для оператора.
        logger.warning("Live ticker: Redis unavailable, returning empty snapshot list")
        snapshots = []

    # Подписи источника не хранятся в Redis: добавляем при выдаче (старые снимки их не имеют).
    # Лента показывает «Биржа» или «ЦБ», страница курса и конвертер берут официальный курс ЦБ на дату:
    # эти числа разные по смыслу, и API называет каждое своим именем, а не склеивает.
    locale = "en" if get_locale() == "en" else "ru"
    now = datetime.now(timezone.utc)
    for snap in snapshots:
        kind = snap.get("source_kind") or source_kind(snap.get("source"))
        snap["source_kind"] = kind
        snap["source_label"] = source_label(kind, snap.get("source"), locale)
        snap.setdefault("as_of", snap.get("as_of_date") or snap.get("fetched_at"))
        add_freshness(snap, now)

    return {
        "lane": lane if lane in TICKER_SETS else "world",
        "snapshots": snapshots,
        "server_time": now.isoformat(),
    }
