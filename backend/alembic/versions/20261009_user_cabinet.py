"""User cabinet tables: saved items, watches, export history, preferences.

Revision ID: 20261009_user_cabinet
Revises: 20261005_push_subscriptions

Только CREATE TABLE / CREATE INDEX на новых пустых таблицах: существующие таблицы
(users и остальные) не меняются, блокировок нет, старый код продолжает работать на
новой схеме. Все четыре таблицы — персональные данные: user_id → users.id
ON DELETE CASCADE.

Downgrade УДАЛЯЕТ таблицы вместе с данными людей (избранное, слежения, история
выгрузок, настройки): на пустых таблицах чисто, на заполненных — только по решению
владельца и после свежего pg-backup.sh (docs/workflow.md).
"""
from alembic import op
import sqlalchemy as sa

revision = "20261009_user_cabinet"
down_revision = "20261005_push_subscriptions"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "user_saved_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(24), nullable=False),
        sa.Column("item_key", sa.String(300), nullable=False),
        sa.Column("title", sa.String(200), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "kind", "item_key", name="uq_user_saved_item"),
    )
    op.create_index(
        "ix_user_saved_items_user_kind", "user_saved_items", ["user_id", "kind", "created_at"]
    )

    op.create_table(
        "user_watches",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("subject_kind", sa.String(24), nullable=False),
        sa.Column("subject_key", sa.String(300), nullable=False),
        sa.Column("channel", sa.String(16), nullable=False, server_default="inapp"),
        sa.Column("last_seen_date", sa.Date(), nullable=True),
        sa.Column("last_notified_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "subject_kind", "subject_key", "channel", name="uq_user_watch"
        ),
    )
    op.create_index("ix_user_watches_subject", "user_watches", ["subject_kind", "subject_key"])

    op.create_table(
        "user_exports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source", sa.String(24), nullable=False),
        sa.Column("subject_key", sa.String(300), nullable=False, server_default=""),
        sa.Column("format", sa.String(8), nullable=False),
        sa.Column("params", sa.JSON(), nullable=True),
        sa.Column("rows_count", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_user_exports_user_created", "user_exports", ["user_id", "created_at"])

    op.create_table(
        "user_preferences",
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("feed_token_hash", sa.String(64), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("user_id"),
    )
    op.create_index(
        "ix_user_preferences_feed_token", "user_preferences", ["feed_token_hash"], unique=True
    )


def downgrade():
    op.drop_index("ix_user_preferences_feed_token", table_name="user_preferences")
    op.drop_table("user_preferences")
    op.drop_index("ix_user_exports_user_created", table_name="user_exports")
    op.drop_table("user_exports")
    op.drop_index("ix_user_watches_subject", table_name="user_watches")
    op.drop_table("user_watches")
    op.drop_index("ix_user_saved_items_user_kind", table_name="user_saved_items")
    op.drop_table("user_saved_items")
