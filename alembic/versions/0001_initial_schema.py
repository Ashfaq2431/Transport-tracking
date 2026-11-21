"""create initial TransitNotice schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-11-03
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0001_initial_schema"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agencies",
        sa.Column("agency_id", sa.Integer(), primary_key=True),
        sa.Column("agency_name", sa.String(length=150), nullable=False),
        sa.Column("official_website", sa.String(length=500)),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("agency_name"),
    )
    op.create_table(
        "sources",
        sa.Column("source_id", sa.Integer(), primary_key=True),
        sa.Column("agency_id", sa.Integer(), sa.ForeignKey("agencies.agency_id"), nullable=False),
        sa.Column("source_name", sa.String(length=200), nullable=False),
        sa.Column("source_url", sa.String(length=500), nullable=False),
        sa.Column("source_type", sa.String(length=20), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        sa.Column("refresh_interval_minutes", sa.Integer(), nullable=False),
        sa.Column("last_attempted_at", sa.DateTime()),
        sa.Column("last_successful_at", sa.DateTime()),
        sa.Column("last_error", sa.Text()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("source_url"),
    )
    op.create_table(
        "advisories",
        sa.Column("notice_id", sa.Integer(), primary_key=True),
        sa.Column("agency_id", sa.Integer(), sa.ForeignKey("agencies.agency_id"), nullable=False),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("sources.source_id"), nullable=False),
        sa.Column("external_notice_id", sa.String(length=255)),
        sa.Column("area", sa.String(length=255)),
        sa.Column("advisory_type", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("summary", sa.Text()),
        sa.Column("full_text", sa.Text()),
        sa.Column("source_url", sa.String(length=500)),
        sa.Column("published_at", sa.DateTime()),
        sa.Column("valid_from", sa.DateTime()),
        sa.Column("valid_to", sa.DateTime()),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("observed_at", sa.DateTime(), nullable=False),
        sa.Column("last_confirmed_at", sa.DateTime()),
        sa.Column("content_hash", sa.String(length=64)),
        sa.Column("revision_id", sa.Integer()),
        sa.Column("change_summary", sa.Text()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("source_id", "external_notice_id", name="uq_advisories_source_external_id"),
    )
    op.create_index("ix_advisories_status", "advisories", ["status"])
    op.create_index("ix_advisories_published_at", "advisories", ["published_at"])
    op.create_table(
        "advisory_routes",
        sa.Column("notice_id", sa.Integer(), sa.ForeignKey("advisories.notice_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("route_id", sa.String(length=100), primary_key=True),
    )
    op.create_table(
        "advisory_history",
        sa.Column("history_id", sa.Integer(), primary_key=True),
        sa.Column("notice_id", sa.Integer(), sa.ForeignKey("advisories.notice_id", ondelete="CASCADE"), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_content_hash", sa.String(length=64)),
        sa.Column("change_summary", sa.Text(), nullable=False),
        sa.Column("previous_snapshot", sa.Text()),
        sa.Column("current_snapshot", sa.Text()),
        sa.Column("observed_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "refresh_runs",
        sa.Column("run_id", sa.Integer(), primary_key=True),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("sources.source_id"), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime()),
        sa.Column("outcome", sa.String(length=20), nullable=False),
        sa.Column("notices_found", sa.Integer(), nullable=False),
        sa.Column("notices_created", sa.Integer(), nullable=False),
        sa.Column("notices_updated", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text()),
    )
    op.create_table(
        "alert_events",
        sa.Column("alert_id", sa.Integer(), primary_key=True),
        sa.Column("notice_id", sa.Integer(), sa.ForeignKey("advisories.notice_id", ondelete="CASCADE"), nullable=False),
        sa.Column("revision_id", sa.Integer()),
        sa.Column("event_type", sa.String(length=30), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("delivery_status", sa.String(length=20), nullable=False),
        sa.Column("read_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("alert_events")
    op.drop_table("refresh_runs")
    op.drop_table("advisory_history")
    op.drop_table("advisory_routes")
    op.drop_index("ix_advisories_published_at", table_name="advisories")
    op.drop_index("ix_advisories_status", table_name="advisories")
    op.drop_table("advisories")
    op.drop_table("sources")
    op.drop_table("agencies")
