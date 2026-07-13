"""partner_revenue: дневной доход РСЯ (Partner Statistics API).

Доход площадки (показы / hits / partner_wo_nds), не расход Директа.
Таблица direct_costs остаётся каркасом под spend.
"""
from alembic import op
import sqlalchemy as sa

revision = "20260713_partner_rev"
down_revision = "20260707_beh_synth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "partner_revenue",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("shows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("hits", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("revenue_rub", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column(
            "synced_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint("day", name="uq_partner_revenue_day"),
    )
    op.create_index("ix_partner_revenue_day", "partner_revenue", ["day"])


def downgrade() -> None:
    op.drop_index("ix_partner_revenue_day", table_name="partner_revenue")
    op.drop_table("partner_revenue")
