"""Персональный выпуск рассылки (ADR-0033, 15.11.2026).

Revision ID: 20261115_newsletter_personal
Revises: 20261114_mail_outbox

Только добавляющая миграция, четыре таблицы:
- `newsletter_profiles` — профиль интересов подписчика (ключи рядов/тем с весами, без адреса и текста запросов);
- `newsletter_personal_issues` — снимок личного выпуска на человека (что уйдёт в письме) и разметка блоков;
- `newsletter_related` — связанные ряды по совместным просмотрам (обезличено);
- `newsletter_query_map` — хэш поискового запроса → ряд (обезличено).
Первые две — ПДн: CASCADE по `users.id`. Откат — удаление таблиц; профили пересчитываются заново.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261115_newsletter_personal"
down_revision = "20261114_mail_outbox"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "newsletter_profiles",
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("computed_at", sa.DateTime(), nullable=False),
        sa.Column("tier", sa.String(10), nullable=False),
        sa.Column("locale", sa.String(2), nullable=False),
        sa.Column("timezone", sa.String(60), nullable=True),
        sa.Column("topics", sa.JSON(), nullable=True),
        sa.Column("subjects", sa.JSON(), nullable=True),
        sa.Column("geo", sa.JSON(), nullable=True),
        sa.Column("stats", sa.JSON(), nullable=True),
    )
    op.create_table(
        "newsletter_personal_issues",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("campaign", sa.String(80), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("locale", sa.String(2), nullable=False),
        sa.Column("arm", sa.String(20), nullable=False),
        sa.Column("subject_arm", sa.String(20), nullable=True),
        sa.Column("tier", sa.String(10), nullable=False),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("error", sa.String(120), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("blocks_meta", sa.JSON(), nullable=True),
        sa.Column("data_as_of", sa.Date(), nullable=True),
        sa.Column("built_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("campaign", "user_id", name="uq_newsletter_personal_issue"),
    )
    op.create_index("ix_newsletter_personal_issue_user", "newsletter_personal_issues", ["user_id", "built_at"])
    op.create_table(
        "newsletter_related",
        sa.Column("subject", sa.String(200), primary_key=True),
        sa.Column("related", sa.String(200), primary_key=True),
        sa.Column("score", sa.Numeric(8, 4), nullable=False),
        sa.Column("visitors", sa.Integer(), nullable=False),
        sa.Column("computed_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "newsletter_query_map",
        sa.Column("q_hash", sa.String(64), primary_key=True),
        sa.Column("subject", sa.String(200), nullable=False),
        sa.Column("selects", sa.Integer(), nullable=False),
        sa.Column("share", sa.Numeric(5, 4), nullable=False),
        sa.Column("computed_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("newsletter_query_map")
    op.drop_table("newsletter_related")
    op.drop_index("ix_newsletter_personal_issue_user", table_name="newsletter_personal_issues")
    op.drop_table("newsletter_personal_issues")
    op.drop_table("newsletter_profiles")
