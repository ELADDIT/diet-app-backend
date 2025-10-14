"""Migration script to add subscription related tables."""

from typing import Sequence

from sqlalchemy import Table

from database import engine
from models import SubscriptionPlan, UserSubscription


TABLES: Sequence[Table] = (
    SubscriptionPlan.__table__,
    UserSubscription.__table__,
)


def upgrade() -> None:
    """Create subscription tables if they do not already exist."""
    for table in TABLES:
        table.create(bind=engine, checkfirst=True)


def downgrade() -> None:
    """Drop subscription tables."""
    for table in reversed(TABLES):
        table.drop(bind=engine, checkfirst=True)
