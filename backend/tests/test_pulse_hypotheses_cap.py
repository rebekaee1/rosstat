"""Потолок открытых гипотез Пульса (19.11.2026): новая открытая не пишется, пока открытых не меньше, чем видит модель."""
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime

from sqlalchemy import select


def test_new_open_hypothesis_is_skipped_at_the_cap_and_closures_still_apply(auth_env, monkeypatch):
    from app.models import Hypothesis
    from app.services import pulse_report

    @asynccontextmanager
    async def session():
        async with auth_env["session_maker"]() as db:
            yield db

    monkeypatch.setattr(pulse_report, "analytics_session", session)
    monkeypatch.setattr(pulse_report, "OPEN_HYPOTHESES_IN_CONTEXT", 3)
    topics = ["палладий", "банкротства организаций", "карта регионов пенсионеров"]

    async def check():
        async with auth_env["session_maker"]() as db:
            db.add_all([Hypothesis(id=i + 1, statement=f"На сайте нет показателя {t}", created_at=datetime(2026, 9, 1),
                                   updated_at=datetime(2026, 9, 1)) for i, t in enumerate(topics)])
            await db.commit()
        first = await pulse_report._apply_hypothesis_updates([
            {"id": None, "statement": "Кнопка входа через Яндекс не отвечает на нажатие", "verdict": None},
            {"id": None, "statement": "Рост регистраций с английской версии", "verdict": True, "rationale": "факт"},
        ])
        # закрытие освобождает место: следующая новая открытая записывается
        second = await pulse_report._apply_hypothesis_updates([
            {"id": 1, "statement": "На сайте нет показателя палладий", "verdict": True, "rationale": "нет ряда"},
            {"id": None, "statement": "Кнопка входа через Яндекс не отвечает на нажатие", "verdict": None},
            {"id": None, "statement": "Календарь выпусков долго открывается на телефоне", "verdict": None},
        ])
        async with auth_env["session_maker"]() as db:
            rows = (await db.execute(select(Hypothesis).order_by(Hypothesis.id))).scalars().all()
        return first, second, [(r.statement, r.verdict) for r in rows]

    first, second, rows = asyncio.run(check())
    assert first == 1                                   # открытая пропущена, закрытая (verdict=True) записана
    assert ("Рост регистраций с английской версии", True) in rows
    assert second == 2                                  # закрытие + одна новая; вторая новая снова упёрлась в потолок
    statements = [s for s, _ in rows]
    assert "Кнопка входа через Яндекс не отвечает на нажатие" in statements
    assert "Календарь выпусков долго открывается на телефоне" not in statements
    assert sum(1 for _, v in rows if v is None) == 3
