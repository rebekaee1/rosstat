"""Миграция 20261009_user_cabinet: цепочка, схема совпадает с моделями, откат чистый.

PostgreSQL здесь нет: схему накатываем на SQLite через alembic Operations и сверяем с
Base.metadata (то же сравнение, что CI-guard scripts/check-migration-drift.py на Postgres).
Что это НЕ доказывает: поведение на PostgreSQL (типы Uuid/JSON, блокировки) и работу
`alembic upgrade head` по всей цепочке — это проверяется в CI и на стенде."""
import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory

from app.models import Base

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "alembic" / "versions" / "20261009_user_cabinet.py"
TABLES = {"user_saved_items", "user_watches", "user_exports", "user_preferences"}


def _module():
    spec = importlib.util.spec_from_file_location("m20261009", MIGRATION)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_revision_ids_and_single_chain():
    mod = _module()
    assert mod.revision == "20261009_user_cabinet"
    assert mod.down_revision == "20261005_push_subscriptions"
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "alembic"))
    script = ScriptDirectory.from_config(cfg)
    heads = script.get_heads()
    # Параллельная зона аналитики добавит 20261009b_analytics_signups поверх нашей ревизии,
    # поэтому допускаем голову = наша ИЛИ следующая за нашей; ветвления быть не должно.
    assert len(heads) == 1, heads
    assert script.get_revision("20261009_user_cabinet").down_revision == "20261005_push_subscriptions"


def test_migration_only_creates_new_tables():
    text = MIGRATION.read_text(encoding="utf-8")
    forbidden = ("alter_table", "add_column", "drop_column", "rename_table", "alter_column", "execute(")
    assert not [w for w in forbidden if w in text]
    for existing in ("users", "indicators", "consents"):
        assert f'"{existing}"' not in text.replace('"users.id"', "")  # users — только как цель внешнего ключа


def test_upgrade_matches_models_and_downgrade_is_clean():
    engine = sa.create_engine("sqlite://")
    mod = _module()
    with engine.begin() as conn:
        Base.metadata.tables["users"].create(conn)
        ctx = MigrationContext.configure(conn)
        with Operations.context(ctx):
            mod.upgrade()
        names = set(sa.inspect(conn).get_table_names())
        assert TABLES <= names

        diffs = compare_metadata(
            MigrationContext.configure(conn, opts={"include_object": lambda obj, name, type_, reflected, compare_to:
                                                   (name in TABLES) if type_ == "table" else True}),
            Base.metadata,
        )
        # включаем только наши таблицы, остальное в metadata (не созданное в этом тесте) отфильтровано
        ours = [d for d in diffs if "user_" in repr(d) and any(t in repr(d) for t in TABLES)]
        assert ours == [], ours

        insp = sa.inspect(conn)
        assert {i["name"] for i in insp.get_indexes("user_saved_items")} == {"ix_user_saved_items_user_kind"}
        assert {i["name"] for i in insp.get_indexes("user_watches")} == {"ix_user_watches_subject"}
        assert {i["name"] for i in insp.get_indexes("user_exports")} == {"ix_user_exports_user_created"}
        pref_idx = insp.get_indexes("user_preferences")
        assert [(i["name"], bool(i["unique"])) for i in pref_idx] == [("ix_user_preferences_feed_token", True)]
        for table in TABLES:
            fks = insp.get_foreign_keys(table)
            assert fks and fks[0]["referred_table"] == "users"
            assert fks[0]["options"].get("ondelete") == "CASCADE"

        with Operations.context(ctx):
            mod.downgrade()
        assert not (TABLES & set(sa.inspect(conn).get_table_names()))
        assert "users" in sa.inspect(conn).get_table_names()
