#!/usr/bin/env python3
"""Записать SEO-гипотезы круга 13 в `hypotheses` с базовыми цифрами (план измерения «до/после»).

Заголовки и описания нельзя оценить сразу: поисковики перечитывают страницы
неделями. Поэтому до выкладки фиксируем базу (доля кликов и позиция за 14 дней),
а через 14 дней после выкладки скрипт ``--measure`` печатает те же цифры рядом.
По умолчанию — сухой прогон; запись только с ``--apply``. Идемпотентен по тексту гипотезы.

    docker compose exec backend python /app/scripts/seo-register-hypotheses.py            # показать
    docker compose exec backend python /app/scripts/seo-register-hypotheses.py --apply    # записать
    docker compose exec backend python /app/scripts/seo-register-hypotheses.py --measure  # сравнить
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import date, datetime, timedelta, timezone

sys.path.insert(0, "/app")

from sqlalchemy import select, text  # noqa: E402

from app.database import analytics_session  # noqa: E402
from app.models import Hypothesis  # noqa: E402

SOURCE = "seo_circle13"
YEAR_RE = r"/(?:19|20)[0-9]{2}$"

HYPOTHESES = [
    (
        "Описание годовой страницы ряда с минимумом, максимумом и последним значением года поднимает долю кликов "
        "по запросам вида «максимальная ставка в 2025», «курс доллара в 2010»",
        "Яндекс 23.09–09.10: такие запросы стоят на позиции 5–10 при нуле кликов, прежнее описание "
        "называло только число значений и среднее.",
        YEAR_RE,
    ),
    (
        "Проверенный робот без 429 на картинках /og/ возвращает Google обычный темп обхода",
        "12.10: Googlebot-Image получал 429 в 8% запросов, Google трактует 429 как сигнал снизить обход хоста.",
        None,
    ),
]


async def window(db, a: date, b: date, pattern: str | None) -> dict:
    cond = "AND page ~ :pat" if pattern else ""
    row = (await db.execute(text(
        f"SELECT COALESCE(SUM(impressions),0) imp, COALESCE(SUM(clicks),0) clk, "
        f"COALESCE(SUM(position*impressions)/NULLIF(SUM(impressions),0),0) pos "
        f"FROM gsc_search_queries WHERE date BETWEEN :a AND :b {cond}"),
        {"a": a, "b": b, **({"pat": pattern} if pattern else {})})).one()
    imp, clk = float(row.imp), float(row.clk)
    return {"impressions": imp, "clicks": clk, "ctr_pct": round(100 * clk / imp, 3) if imp else 0.0, "position": round(float(row.pos), 1)}


async def run(apply: bool, measure: bool) -> None:
    end = date.today() - timedelta(days=3)
    base = (end - timedelta(days=13), end)
    async with analytics_session() as db:
        for statement, rationale, pattern in HYPOTHESES:
            existing = (await db.execute(select(Hypothesis).where(Hypothesis.statement == statement[:500]))).scalar_one_or_none()
            if measure:
                if existing is None:
                    print("нет записи:", statement[:70]); continue
                now = await window(db, end - timedelta(days=13), end, pattern)
                print(statement[:70], "\n  база:", existing.evidence_json, "\n  сейчас:", now)
                continue
            evidence = {"gsc_baseline_14d": await window(db, *base, pattern), "window": [base[0].isoformat(), base[1].isoformat()]}
            print(("записать" if apply else "записал бы"), "|", statement[:70], "|", evidence)
            if apply and existing is None:
                now_ = datetime.now(timezone.utc).replace(tzinfo=None)
                db.add(Hypothesis(statement=statement[:500], rationale=rationale, verdict=None, confidence=None,
                                  source=SOURCE, evidence_json=evidence, created_at=now_, updated_at=now_))
        if apply:
            await db.commit()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--measure", action="store_true")
    a = ap.parse_args()
    asyncio.run(run(a.apply, a.measure))
