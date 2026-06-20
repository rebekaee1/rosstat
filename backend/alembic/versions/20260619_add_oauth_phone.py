"""add phone to oauth_identities (личный кабинет Phase 2, ADR-0007)

Revision ID: 20260619_oauth_phone
Revises: 20260619_identity
Create Date: 2026-06-19

Телефон из профиля провайдера (Яндекс default_phone / VK phone) — отдельный
канал рассылки наряду с email. Колонка nullable: телефон выдаётся не всегда
(зависит от scope и согласия пользователя у провайдера).
"""
from alembic import op
import sqlalchemy as sa

revision = "20260619_oauth_phone"
down_revision = "20260619_identity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("oauth_identities", sa.Column("phone", sa.String(length=32), nullable=True))


def downgrade() -> None:
    op.drop_column("oauth_identities", "phone")
