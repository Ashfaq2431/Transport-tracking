"""deduplicate alert events by notice revision and event type

Revision ID: 0002_alert_dedup
Revises: 0001_initial_schema
"""

from typing import Sequence, Union

from alembic import op


revision: str = "0002_alert_dedup"
down_revision: Union[str, Sequence[str], None] = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_alert_notice_revision_type",
        "alert_events",
        ["notice_id", "revision_id", "event_type"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_alert_notice_revision_type", "alert_events", type_="unique")
