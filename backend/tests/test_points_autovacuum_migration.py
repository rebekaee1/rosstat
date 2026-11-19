"""Миграция 20261119_points_autovacuum: параметры автоочистки таблиц точек (19.11.2026).

На PostgreSQL — только ALTER TABLE … SET/RESET параметров хранения двух таблиц, без VACUUM (в транзакции
миграций нельзя) и без переписывания таблиц; на SQLite — ничего.
"""
import importlib.util
import io
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "alembic" / "versions" / "20261119_points_autovacuum.py"


def _module():
    spec = importlib.util.spec_from_file_location("m20261119_points_autovacuum", PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _postgres_sql(step: str) -> str:
    mod = _module()
    buf = io.StringIO()
    ctx = MigrationContext.configure(dialect_name="postgresql", opts={"as_sql": True, "output_buffer": buf})
    with Operations.context(ctx):
        getattr(mod, step)()
    return buf.getvalue()


def test_revision_chain():
    mod = _module()
    assert mod.revision == "20261119_points_autovacuum" and len(mod.revision) <= 32
    assert mod.down_revision == "20261118_search_index"


def test_postgres_upgrade_sets_only_storage_parameters():
    sql = _postgres_sql("upgrade")
    statements = [s.strip() for s in sql.split(";") if s.strip()]
    alters = [s for s in statements if s.startswith("ALTER TABLE")]
    assert [a.split()[2] for a in alters] == ["world_data_points", "subnational_data_points"]
    for a in alters:
        assert " SET (" in a
        for option in ("autovacuum_vacuum_scale_factor = 0.01", "autovacuum_vacuum_threshold = 10000",
                       "autovacuum_vacuum_insert_scale_factor = 0.02", "autovacuum_analyze_scale_factor = 0.05",
                       "log_autovacuum_min_duration = 0"):
            assert option in a
    assert statements[0] == "SET LOCAL lock_timeout = '10s'"
    assert statements[-1] == "SET LOCAL lock_timeout TO DEFAULT"
    upper = sql.upper()
    assert "VACUUM " not in upper.replace("AUTOVACUUM_", "") and "CLUSTER" not in upper and "FULL" not in upper


def test_postgres_downgrade_resets_the_same_parameters():
    sql = _postgres_sql("downgrade")
    resets = [s.strip() for s in sql.split(";") if s.strip().startswith("ALTER TABLE")]
    assert len(resets) == 2
    for r in resets:
        assert " RESET (" in r and "autovacuum_vacuum_scale_factor" in r and "log_autovacuum_min_duration" in r


def test_sqlite_upgrade_and_downgrade_do_nothing():
    mod = _module()
    engine = sa.create_engine("sqlite://")
    with engine.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE world_data_points (id INTEGER PRIMARY KEY)")
        with Operations.context(MigrationContext.configure(conn)):
            mod.upgrade()
            mod.downgrade()
        assert sa.inspect(conn).get_table_names() == ["world_data_points"]
