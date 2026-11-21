from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Agency(Base):
    __tablename__ = "agencies"

    agency_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    agency_name: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)
    official_website: Mapped[Optional[str]] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    sources: Mapped[list["Source"]] = relationship(back_populates="agency")
    advisories: Mapped[list["Advisory"]] = relationship(back_populates="agency")


class Source(Base):
    __tablename__ = "sources"

    source_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    agency_id: Mapped[int] = mapped_column(ForeignKey("agencies.agency_id"), nullable=False)
    source_name: Mapped[str] = mapped_column(String(200), nullable=False)
    source_url: Mapped[str] = mapped_column(String(500), unique=True, nullable=False)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    refresh_interval_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    last_attempted_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    last_successful_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    last_error: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    agency: Mapped[Agency] = relationship(back_populates="sources")
    advisories: Mapped[list["Advisory"]] = relationship(back_populates="source")
    refresh_runs: Mapped[list["RefreshRun"]] = relationship(back_populates="source")


class Advisory(Base):
    __tablename__ = "advisories"
    __table_args__ = (
        UniqueConstraint("source_id", "external_notice_id", name="uq_advisories_source_external_id"),
        Index("ix_advisories_status", "status"),
        Index("ix_advisories_published_at", "published_at"),
    )

    notice_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    agency_id: Mapped[int] = mapped_column(ForeignKey("agencies.agency_id"), nullable=False)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.source_id"), nullable=False)
    external_notice_id: Mapped[Optional[str]] = mapped_column(String(255))
    area: Mapped[Optional[str]] = mapped_column(String(255))
    advisory_type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text)
    full_text: Mapped[Optional[str]] = mapped_column(Text)
    source_url: Mapped[Optional[str]] = mapped_column(String(500))
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    valid_from: Mapped[Optional[datetime]] = mapped_column(DateTime)
    valid_to: Mapped[Optional[datetime]] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="unknown")
    observed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    last_confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    content_hash: Mapped[Optional[str]] = mapped_column(String(64))
    revision_id: Mapped[Optional[int]] = mapped_column(Integer)
    change_summary: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    agency: Mapped[Agency] = relationship(back_populates="advisories")
    source: Mapped[Source] = relationship(back_populates="advisories")
    routes: Mapped[list["AdvisoryRoute"]] = relationship(
        back_populates="advisory", cascade="all, delete-orphan"
    )
    history: Mapped[list["AdvisoryHistory"]] = relationship(
        back_populates="advisory", cascade="all, delete-orphan"
    )
    alerts: Mapped[list["AlertEvent"]] = relationship(
        back_populates="advisory", cascade="all, delete-orphan"
    )


class AdvisoryRoute(Base):
    __tablename__ = "advisory_routes"

    notice_id: Mapped[int] = mapped_column(
        ForeignKey("advisories.notice_id", ondelete="CASCADE"), primary_key=True
    )
    route_id: Mapped[str] = mapped_column(String(100), primary_key=True)

    advisory: Mapped[Advisory] = relationship(back_populates="routes")


class AdvisoryHistory(Base):
    __tablename__ = "advisory_history"

    history_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    notice_id: Mapped[int] = mapped_column(
        ForeignKey("advisories.notice_id", ondelete="CASCADE"), nullable=False
    )
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    previous_content_hash: Mapped[Optional[str]] = mapped_column(String(64))
    change_summary: Mapped[str] = mapped_column(Text, nullable=False)
    previous_snapshot: Mapped[Optional[str]] = mapped_column(Text)
    current_snapshot: Mapped[Optional[str]] = mapped_column(Text)
    observed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    advisory: Mapped[Advisory] = relationship(back_populates="history")


class RefreshRun(Base):
    __tablename__ = "refresh_runs"

    run_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.source_id"), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    outcome: Mapped[str] = mapped_column(String(20), nullable=False)
    notices_found: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    notices_created: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    notices_updated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text)

    source: Mapped[Source] = relationship(back_populates="refresh_runs")


class AlertEvent(Base):
    __tablename__ = "alert_events"
    __table_args__ = (
        UniqueConstraint("notice_id", "revision_id", "event_type", name="uq_alert_notice_revision_type"),
    )

    alert_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    notice_id: Mapped[int] = mapped_column(
        ForeignKey("advisories.notice_id", ondelete="CASCADE"), nullable=False
    )
    revision_id: Mapped[Optional[int]] = mapped_column(Integer)
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    delivery_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    advisory: Mapped[Advisory] = relationship(back_populates="alerts")
