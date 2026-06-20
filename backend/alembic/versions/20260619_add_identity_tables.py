"""add identity tables (личный кабинет Phase 1, ADR-0007)

Revision ID: 20260619_identity
Revises: 20260510_calendar_official
Create Date: 2026-06-19

users (UUID PK) + oauth_identities + email_credentials + consents + auth_audit.
Email не на users — он атрибут способа входа. Все FK user_id → users.id
с ondelete CASCADE (DELETE /account чистит каскадом). Сессии — в Redis, не тут.
"""
from alembic import op
import sqlalchemy as sa


revision = "20260619_identity"
down_revision = "20260510_calendar_official"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("display_name", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "oauth_identities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(30), nullable=False),
        sa.Column("provider_user_id", sa.String(200), nullable=False),
        sa.Column("email", sa.String(320), nullable=True),
        sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("display_name", sa.String(200), nullable=True),
        sa.Column("avatar_url", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_login_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("provider", "provider_user_id", name="uq_oauth_provider_subject"),
    )
    op.create_index("ix_oauth_identity_user", "oauth_identities", ["user_id"])

    op.create_table(
        "email_credentials",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("email", name="uq_email_credential_email"),
    )

    op.create_table(
        "consents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("version", sa.String(20), nullable=False),
        sa.Column("granted_at", sa.DateTime(), nullable=False),
        sa.Column("ip", sa.String(64), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
    )
    op.create_index("ix_consent_user", "consents", ["user_id"])

    op.create_table(
        "auth_audit",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
        sa.Column("event", sa.String(30), nullable=False),
        sa.Column("ip", sa.String(64), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column("detail", sa.String(200), nullable=True),
        sa.Column("ts", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_auth_audit_user", "auth_audit", ["user_id", "ts"])


def downgrade() -> None:
    op.drop_index("ix_auth_audit_user", table_name="auth_audit")
    op.drop_table("auth_audit")
    op.drop_index("ix_consent_user", table_name="consents")
    op.drop_table("consents")
    op.drop_table("email_credentials")
    op.drop_index("ix_oauth_identity_user", table_name="oauth_identities")
    op.drop_table("oauth_identities")
    op.drop_table("users")
