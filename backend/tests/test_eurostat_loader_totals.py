"""Итог загрузчика Eurostat без точного COUNT(*) по world_data_points (14.11.2026)."""
import asyncio
import importlib.util
from datetime import date
from pathlib import Path

from app.models import WorldCountry, WorldDataPoint, WorldIndicator

from tests.test_analytics2 import _run_with_db

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "load-world-eurostat.py"


def _loader():
    spec = importlib.util.spec_from_file_location("load_world_eurostat_totals", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_totals_are_exact_on_small_tables():
    mod = _loader()

    async def scenario(maker):
        async with maker() as db:
            db.add_all([
                WorldCountry(id=1, code="DE", slug="germany", name_ru="Германия", name_en="Germany"),
                WorldCountry(id=2, code="FR", slug="france", name_ru="Франция", name_en="France", is_active=False),
                WorldIndicator(id=1, country_id=1, code="de-a", name_ru="A", name_en="A", provider="eurostat",
                               dataset_id="x", slice_hash="1", frequency="annual"),
            ])
            db.add_all([WorldDataPoint(indicator_id=1, date=date(2000 + i, 1, 1), value=i) for i in range(3)])
            await db.commit()
        async with maker() as db:
            return await mod._db_totals(db)

    assert _run_with_db(scenario) == (1, 1, 3)


def test_big_tables_use_postgres_estimate_not_full_count():
    mod = _loader()
    seen = []

    class Bind:
        class dialect:
            name = "postgresql"

    class Result:
        def __init__(self, value):
            self.value = value

        def scalar(self):
            return self.value

    class FakeDb:
        bind = Bind

        async def execute(self, stmt, params=None):
            seen.append(str(stmt))
            return Result(55)

        async def scalar(self, stmt, params=None):
            sql = str(stmt)
            seen.append(sql)
            assert "count(*)" not in sql.lower() or "world_countries" in sql, sql
            return 16_000_000 if (params or {}).get("n") == "world_data_points" else 300_000

    totals = asyncio.run(mod._db_totals(FakeDb()))
    assert totals == (55, 300_000, 16_000_000)
    assert not any("FROM world_data_points" in s for s in seen)
    assert sum("pg_class" in s for s in seen) == 2
