"""add index on indicators.category for filtered lists

Revision ID: b3c1d2e4f5a6
Revises: 8524e35ba1ee
Create Date: 2026-03-20
"""
from typing import Sequence, Union

from alembic import op

revision: str = "b3c1d2e4f5a6"
down_revision: Union[str, None] = "8524e35ba1ee"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_indicators_category",
        "indicators",
        ["category"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_indicators_category", table_name="indicators")
