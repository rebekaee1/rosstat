"""Current newsletter membership from the append-only consent journal."""
from sqlalchemy import func, select
from app.models import Consent

NEWSLETTER_KINDS = ("newsletter", "newsletter_revoked")


def newsletter_subscriber_count_query():
    """Latest timestamp wins; id breaks ties, matching serialize_user."""
    latest = select(
        Consent.kind,
        func.row_number().over(
            partition_by=Consent.user_id,
            order_by=(Consent.granted_at.desc(), Consent.id.desc()),
        ).label("position"),
    ).where(Consent.kind.in_(NEWSLETTER_KINDS)).subquery()
    return select(func.count()).select_from(latest).where(
        latest.c.position == 1, latest.c.kind == "newsletter",
    )
