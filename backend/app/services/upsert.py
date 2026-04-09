"""Shared upsert helper for IndicatorData — on_conflict_do_update ensures revisions are captured."""

from datetime import date as _date

from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.models import IndicatorData


def upsert_indicator_data(indicator_id: int, dt: _date, val: float):
    """INSERT … ON CONFLICT (indicator_id, date) DO UPDATE SET value = excluded.value."""
    stmt = pg_insert(IndicatorData).values(
        indicator_id=indicator_id, date=dt, value=val,
    )
    return stmt.on_conflict_do_update(
        constraint="uq_indicator_date",
        set_={"value": stmt.excluded.value},
    )
