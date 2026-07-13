"""Яндекс.Партнёр (РСЯ) Statistics API → таблица partner_revenue.

Доход площадки: видимые показы / hits / partner_wo_nds (₽ без НДС) по дням.
Auth: ``Authorization: OAuth <token>`` (токен с правом партнёрского интерфейса).

Док: https://yandex.ru/dev/partner-statistics/doc/ru/
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any

import httpx
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import PartnerRevenue

logger = logging.getLogger(__name__)

_STATS_URL = "https://partner.yandex.ru/api/statistics2/get.json"
# Preset'ы API: today / yesterday / 7days / 30days / thismonth / …
_DEFAULT_PERIOD = "30days"


def partner_token() -> str:
    """Рабочий OAuth-токен партнёрки (явный PARTNER_TOKEN, иначе DIRECT как legacy)."""
    return (
        (settings.yandex_partner_token or "").strip()
        or (settings.direct_api_token or "").strip()
    )


def partner_configured() -> bool:
    return bool(partner_token())


def _parse_day_points(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Разбор statistics2/get → [{day, shows, hits, revenue_rub}, …]."""
    data = payload.get("data") or {}
    points_out: list[dict[str, Any]] = []
    for pt in data.get("points") or []:
        dims = pt.get("dimensions") or {}
        date_dim = dims.get("date")
        if isinstance(date_dim, list) and date_dim:
            day_raw = date_dim[0]
        elif isinstance(date_dim, str):
            day_raw = date_dim
        else:
            continue
        try:
            day = date.fromisoformat(str(day_raw)[:10])
        except ValueError:
            continue
        measures_list = pt.get("measures") or []
        # API отдаёт measures как список словарей [{shows, hits, partner_wo_nds}]
        merged: dict[str, Any] = {}
        if isinstance(measures_list, list):
            for m in measures_list:
                if isinstance(m, dict):
                    merged.update(m)
        elif isinstance(measures_list, dict):
            merged = measures_list
        shows = int(float(merged.get("shows") or 0))
        hits = int(float(merged.get("hits") or 0))
        revenue = float(merged.get("partner_wo_nds") or 0)
        points_out.append({
            "day": day,
            "shows": shows,
            "hits": hits,
            "revenue_rub": round(revenue, 2),
        })
    return points_out


async def fetch_partner_stats(period: str = _DEFAULT_PERIOD) -> list[dict[str, Any]]:
    """GET statistics2 по дням. Пустой список если токена нет."""
    token = partner_token()
    if not token:
        logger.info("Partner stats skip: no RUSTATS_YANDEX_PARTNER_TOKEN")
        return []
    params = [
        ("lang", "ru"),
        ("period", period),
        ("field", "shows"),
        ("field", "hits"),
        ("field", "partner_wo_nds"),
        ("dimension_field", "date|day"),
    ]
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.get(
            _STATS_URL,
            params=params,
            headers={"Authorization": f"OAuth {token}"},
        )
    if resp.status_code == 401:
        raise RuntimeError(
            "Partner Statistics 401: токен без права партнёрки (pi:all) "
            "или отозван — выдать заново в partner.yandex.ru"
        )
    resp.raise_for_status()
    payload = resp.json()
    if isinstance(payload, dict) and payload.get("errors"):
        raise RuntimeError(f"Partner Statistics errors: {payload['errors'][:2]}")
    return _parse_day_points(payload if isinstance(payload, dict) else {})


async def upsert_partner_revenue(
    db: AsyncSession,
    rows: list[dict[str, Any]],
) -> int:
    """Идемпотентный upsert по day. Возвращает число затронутых строк."""
    if not rows:
        return 0
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    values = [
        {
            "day": r["day"],
            "shows": int(r["shows"]),
            "hits": int(r["hits"]),
            "revenue_rub": float(r["revenue_rub"]),
            "synced_at": now,
        }
        for r in rows
    ]
    stmt = pg_insert(PartnerRevenue).values(values)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_partner_revenue_day",
        set_={
            "shows": stmt.excluded.shows,
            "hits": stmt.excluded.hits,
            "revenue_rub": stmt.excluded.revenue_rub,
            "synced_at": stmt.excluded.synced_at,
        },
    )
    await db.execute(stmt)
    return len(values)


async def sync_partner_revenue(period: str = _DEFAULT_PERIOD) -> dict[str, Any]:
    """Скачать статистику и записать в БД. Для планировщика и ручного прогона."""
    from app.database import async_session

    if not partner_configured():
        return {"ok": False, "reason": "token_missing", "rows": 0}
    rows = await fetch_partner_stats(period=period)
    async with async_session() as db:
        n = await upsert_partner_revenue(db, rows)
        await db.commit()
    logger.info("Partner revenue sync: %d day(s) period=%s", n, period)
    return {"ok": True, "rows": n, "period": period}
