"""Web-push subscriptions (preparation only; nothing is sent).

Revision ID: 20261005_push_subscriptions
Revises: 20261004_session_changes

Новая пустая таблица: DDL быстрый и ничего не блокирует. Адрес подписки и ключи —
персональные данные (см. модель PushSubscription); user_id → users.id ON DELETE CASCADE.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261005_push_subscriptions"
down_revision = "20261004_session_changes"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "push_subscriptions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("endpoint_hash", sa.String(64), nullable=False),
        sa.Column("endpoint", sa.Text(), nullable=False),
        sa.Column("p256dh", sa.String(255), nullable=False),
        sa.Column("auth", sa.String(255), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
        sa.Column("locale", sa.String(5), nullable=True),
        sa.Column("user_agent", sa.String(300), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("last_success_at", sa.DateTime(), nullable=True),
        sa.Column("failure_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("endpoint_hash", name="uq_push_endpoint_hash"),
    )
    op.create_index("ix_push_subscriptions_user", "push_subscriptions", ["user_id"])
    op.create_index("ix_push_subscriptions_active", "push_subscriptions", ["revoked_at"])


def downgrade():
    op.drop_index("ix_push_subscriptions_active", table_name="push_subscriptions")
    op.drop_index("ix_push_subscriptions_user", table_name="push_subscriptions")
    op.drop_table("push_subscriptions")
