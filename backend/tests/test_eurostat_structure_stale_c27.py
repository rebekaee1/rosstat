"""Круг починки 27.10.2026: карточки, чей ряд закончился у источника ДО смены структуры, не держат набор в карантине.

`ei_isin_m`: Германия, Люксембург, Румыния, Словакия, Финляндия, Исландия перестали сдавать индексы
заработной платы, часов и занятости после 2023 года; их 14 публичных карточек («Устарело» с декабря 2023)
превысили порог 20 % и держали в карантине весь набор вместе с 36 живыми рядами.
"""
from datetime import date

from app.services.eurostat_structure import ExistingSlice, plan_structure_migration


def _monthly(start: date, months: int):
    out = []
    y, m = start.year, start.month
    for i in range(months):
        out.append((date(y, m, 1), 100.0 + i))
        m += 1
        if m > 12:
            m, y = 1, y + 1
    return out


def _slice(indic: str, unit: str = "I2021", freq: str = "M"):
    return {"freq": freq, "unit": unit, "indic": indic, "nace_r2": "B-D"}


def test_cards_ended_long_before_structure_change_do_not_block_the_dataset():
    live_slice = _slice("IS-IP")
    dead = [_slice(f"IS-X{i}", unit="I2015") for i in range(14)]
    existing = [ExistingSlice(100, "FR", live_slice, "h_live", True)]
    existing += [ExistingSlice(i, "DE", s, f"h_dead{i}", True) for i, s in enumerate(dead)]
    new = {("FR", "h_live"): (live_slice, _monthly(date(2020, 1, 1), 80))}  # до 2026-08
    # прежние точки мёртвых карточек заканчиваются в декабре 2023
    old_points = {i: _monthly(date(2020, 1, 1), 48) for i in range(14)}
    verdict = plan_structure_migration(existing, new, old_points=old_points)
    assert verdict.accept, verdict.reason
    assert verdict.orphans_listed == 0
    assert verdict.orphans_stale == 14
    assert verdict.as_dict()["orphans_stale"] == 14
    assert "уже устаревших" in verdict.reason


def test_recently_live_orphans_still_trigger_quarantine():
    """Если пропавшие срезы были живы (последняя точка у свежей границы), это разлом и карантин сохраняется."""
    live_slice = _slice("IS-IP")
    lost = [_slice(f"IS-X{i}") for i in range(10)]
    existing = [ExistingSlice(100, "FR", live_slice, "h_live", True)]
    existing += [ExistingSlice(i, "DE", s, f"h_lost{i}", True) for i, s in enumerate(lost)]
    new = {("FR", "h_live"): (live_slice, _monthly(date(2020, 1, 1), 80))}
    old_points = {i: _monthly(date(2020, 1, 1), 78) for i in range(10)}  # до 2026-06
    verdict = plan_structure_migration(existing, new, old_points=old_points)
    assert not verdict.accept
    assert verdict.orphans_listed == 10 and verdict.orphans_stale == 0


def test_annual_dataset_one_year_behind_is_not_stale():
    """Годовой ряд, отстающий на один период, не «мёртвый»: годовые данные у источника всегда запаздывают."""
    live_slice = {"freq": "A", "unit": "EUR", "c_dest": "DOM"}
    lost = [{"freq": "A", "unit": "EUR", "c_dest": f"X{i}"} for i in range(5)]
    existing = [ExistingSlice(100, "FR", live_slice, "h_live", True)]
    existing += [ExistingSlice(i, "DE", s, f"h_lost{i}", True) for i, s in enumerate(lost)]
    new = {("FR", "h_live"): (live_slice, [(date(y, 1, 1), 1.0) for y in range(2015, 2026)])}
    old_points = {i: [(date(y, 1, 1), 1.0) for y in range(2015, 2025)] for i in range(5)}
    verdict = plan_structure_migration(existing, new, old_points=old_points)
    assert verdict.orphans_stale == 0 and verdict.orphans_listed == 5
    assert not verdict.accept


def test_no_history_is_treated_as_live_conservatively():
    live_slice = _slice("IS-IP")
    lost = [_slice(f"IS-X{i}") for i in range(10)]
    existing = [ExistingSlice(100, "FR", live_slice, "h_live", True)]
    existing += [ExistingSlice(i, "DE", s, f"h_lost{i}", True) for i, s in enumerate(lost)]
    new = {("FR", "h_live"): (live_slice, _monthly(date(2020, 1, 1), 80))}
    verdict = plan_structure_migration(existing, new, old_points={})
    assert not verdict.accept and verdict.orphans_stale == 0
