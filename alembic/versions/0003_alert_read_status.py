"""track in-app notification read status"""

from alembic import op
import sqlalchemy as sa

revision = "0003_alert_read_status"
down_revision = "0002_alert_dedup"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("alert_events", sa.Column("read_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("alert_events", "read_at")
