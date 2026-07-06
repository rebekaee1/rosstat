"""Регрессия В-1: hero «Год к году» считается по дате, а не по позиции.

Старый код брал rows[12] как «год назад»: дыра в месячном ряду молча
сравнивала с 13-месячной давностью, weekly дрейфовал на 53-недельных годах.
Новый: точный date-lookup для monthly/quarterly/annual, ближайшая точка в
допуске ±6 дней для weekly/daily; при дыре — честное None вместо чужого
периода.
"""
import asyncio
import os
import tempfile
from datetime import date

from app.api.indicators import _hero_yoy_pct, _lookup_year_ago, _year_ago_target


def test_year_ago_target_by_frequency():
    assert _year_ago_target(date(2026, 5, 1), "monthly") == date(2025, 5, 1)
    assert _year_ago_target(date(2026, 4, 1), "quarterly") == date(2025, 4, 1)
    assert _year_ago_target(date(2026, 1, 1), "annual") == date(2025, 1, 1)
    assert _year_ago_target(date(2024, 2, 29), "monthly") == date(2023, 2, 28)
    assert _year_ago_target(date(2026, 6, 30), "weekly") == date(2025, 7, 1)
    assert _year_ago_target(date(2026, 5, 1), "5min") is None


def test_lookup_exact_for_monthly():
    points = [(date(2025, 5, 1), 100.0), (date(2025, 4, 1), 98.0)]
    assert _lookup_year_ago(points, date(2026, 5, 1), "monthly") == 100.0
    # Дыра: точки за май-2025 нет — None, а не соседний месяц
    assert _lookup_year_ago([(date(2025, 4, 1), 98.0)], date(2026, 5, 1), "monthly") is None


def test_lookup_nearest_for_weekly_within_tolerance():
    # Недельные даты плавают: точка в 3 днях от «минус 364» находится
    points = [(date(2025, 6, 28), 55.0), (date(2025, 6, 21), 54.0)]
    assert _lookup_year_ago(points, date(2026, 6, 29), "weekly") == 55.0
    # А вне допуска ±6 дней — нет
    far = [(date(2025, 6, 10), 50.0)]
    assert _lookup_year_ago(far, date(2026, 6, 29), "weekly") is None


def _run_hero(rows):
    """_hero_yoy_pct против герметичной SQLite с заданным рядом."""
    from sqlalchemy import create_engine
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.models import Base, Indicator, IndicatorData

    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        sync_engine = create_engine(f"sqlite:///{db_path}")
        Base.metadata.create_all(sync_engine)
        sync_engine.dispose()
        engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
        Session = async_sessionmaker(engine, expire_on_commit=False)

        async def run():
            async with Session() as db:
                ind = Indicator(
                    code="test-idx", name="Тест", unit="индекс",
                    frequency="monthly", parser_type="manual", is_active=True,
                )
                db.add(ind)
                await db.flush()
                for d, v in rows:
                    db.add(IndicatorData(indicator_id=ind.id, date=d, value=v))
                await db.commit()
                current = float(rows[0][1])
                res = await _hero_yoy_pct(db, ind.id, "monthly", current)
            await engine.dispose()
            return res

        return asyncio.run(run())
    finally:
        try:
            os.unlink(db_path)
        except OSError:
            pass


def test_hero_yoy_clean_series():
    rows = [(date(2025 + (m - 1) // 12, (m - 1) % 12 + 1, 1), 100.0 + m) for m in range(1, 18)]
    rows.sort(reverse=True)
    hero, unit, label, change = _run_hero(rows)
    # Последняя точка 2026-05 (m=17, v=117), год назад 2025-05 (m=5, v=105)
    assert hero == round((117 - 105) / 105 * 100, 2)
    assert unit == "%" and label == "Год к году"
    assert change is not None


def test_hero_yoy_gap_returns_none_not_wrong_period():
    """Дыра на месте «год назад» — None, а не сравнение с 13-месячной давностью."""
    rows = [(date(2025 + (m - 1) // 12, (m - 1) % 12 + 1, 1), 100.0 + m)
            for m in range(1, 18) if m != 5]  # выбит 2025-05
    rows.sort(reverse=True)
    hero, *_ = _run_hero(rows)
    assert hero is None


def test_listing_batch_hero_matches_detail(monkeypatch):
    """П-8: батч-hero листинга даёт те же значения, что и per-indicator путь.

    Листинг считает hero одним запросом по объединению окон «год назад»;
    регрессия — расхождение с _hero_yoy_pct (точечный путь detail-endpoint'а)."""
    from sqlalchemy import create_engine, select
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    import app.api.indicators as api_ind
    from app.models import Base, Indicator, IndicatorData

    async def _no_cache_get(key):
        return None

    async def _no_cache_set(key, value, ttl=None):
        return None

    monkeypatch.setattr(api_ind, "cache_get", _no_cache_get)
    monkeypatch.setattr(api_ind, "cache_set", _no_cache_set)

    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        sync_engine = create_engine(f"sqlite:///{db_path}")
        Base.metadata.create_all(sync_engine)
        sync_engine.dispose()
        engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
        Session = async_sessionmaker(engine, expire_on_commit=False)

        monthly_rows = [
            (date(2025 + (m - 1) // 12, (m - 1) % 12 + 1, 1), 100.0 + m)
            for m in range(1, 18)
        ]
        gap_rows = [r for r in monthly_rows if r[0] != date(2025, 5, 1)]

        async def run():
            async with Session() as db:
                specs = [
                    ("hero-clean", monthly_rows, {"hero_view": "yoy_pct"}),
                    ("hero-gap", gap_rows, {"hero_view": "yoy_pct"}),
                    ("plain", monthly_rows, {}),
                ]
                for code, rows, mcfg in specs:
                    ind = Indicator(
                        code=code, name=code, unit="индекс", frequency="monthly",
                        parser_type="manual", is_active=True, is_listed=True,
                        model_config_json=mcfg,
                    )
                    db.add(ind)
                    await db.flush()
                    for d, v in rows:
                        db.add(IndicatorData(indicator_id=ind.id, date=d, value=v))
                await db.commit()

                listing = await api_ind.list_indicators(
                    db=db, category=None,
                    include_inactive=False, include_unlisted=False,
                )
                by_code = {s.code: s for s in listing}

                inds = {c: (await db.execute(
                    select(Indicator).where(Indicator.code == c)
                )).scalar_one() for c in ("hero-clean", "hero-gap")}
                detail = {}
                for c, ind in inds.items():
                    detail[c] = await api_ind._hero_yoy_pct(
                        db, ind.id, "monthly", by_code[c].current_value,
                    )
            await engine.dispose()
            return by_code, detail

        by_code, detail = asyncio.run(run())
        # Чистый ряд: значения листинга и detail совпадают
        assert by_code["hero-clean"].hero_value == detail["hero-clean"][0] is not None
        assert by_code["hero-clean"].hero_change == detail["hero-clean"][3]
        # Дыра «год назад»: оба пути честно отдают None
        assert by_code["hero-gap"].hero_value is None and detail["hero-gap"][0] is None
        # Не-hero индикатор hero не получает
        assert by_code["plain"].hero_value is None
    finally:
        try:
            os.unlink(db_path)
        except OSError:
            pass
