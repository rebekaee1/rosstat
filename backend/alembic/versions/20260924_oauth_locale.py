"""Persist the optional language returned by an OAuth identity provider.

Revision ID: 20260924_oauth_locale
Revises: 20260924_countries_idx
"""
from alembic import op
import sqlalchemy as sa

revision = "20260924_oauth_locale"
down_revision = "20260924_countries_idx"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("oauth_identities", sa.Column("locale", sa.String(length=35), nullable=True))


def downgrade() -> None:
    op.drop_column("oauth_identities", "locale")
