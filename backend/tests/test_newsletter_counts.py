"""Analytical subscriber counts follow current consent, not historical opt-ins."""
from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import Consent, User
from app.services.identity.consents import newsletter_subscriber_count_query


def test_latest_consent_revoke_resubscribe_and_same_timestamp():
    engine = create_engine('sqlite://')
    User.__table__.create(engine)
    Consent.__table__.create(engine)
    at = datetime(2026, 9, 10)
    user_id = uuid4()
    with Session(engine) as db:
        db.add(User(id=user_id))
        db.commit()
        def add(kind, when):
            db.add(Consent(user_id=user_id, kind=kind, version='test', granted_at=when))
            db.commit()
        def count():
            return db.scalar(newsletter_subscriber_count_query())
        assert count() == 0
        add('newsletter', at)
        assert count() == 1
        add('newsletter_revoked', at + timedelta(seconds=1))
        assert count() == 0
        add('privacy', at + timedelta(seconds=2))
        assert count() == 0  # unrelated legal consent must not restore membership
        add('newsletter', at + timedelta(seconds=3))
        assert count() == 1
        add('newsletter_revoked', at + timedelta(seconds=3))
        assert count() == 0  # deterministic id tie-break, as in serialize_user
        add('newsletter', at)  # backdated inserted row must not override latest time
        assert count() == 0
    engine.dispose()
