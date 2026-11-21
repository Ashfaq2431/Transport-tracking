from datetime import datetime, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from backend.app.database import Base
from backend.app.models import Agency, Advisory, AdvisoryHistory, AlertEvent, Source
from backend.app.scrapers.schemas import NormalizedNotice
from backend.app.services.notice_status import calculate_status
from backend.app.services.refresh import process_notices


def _database():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


def test_status_calculation_never_marks_expired_notice_active():
    now = datetime(2026, 11, 3, 12, tzinfo=timezone.utc)

    assert calculate_status(None, datetime(2026, 11, 3, 11, tzinfo=timezone.utc), now=now) == "expired"
    assert calculate_status(datetime(2026, 11, 3, 13, tzinfo=timezone.utc), None, now=now) == "scheduled"


def test_identical_refresh_creates_no_duplicate_history_or_alerts():
    with Session(_database()) as db:
        agency = Agency(agency_name="Test Agency")
        source = Source(
            agency=agency,
            source_name="Fixture",
            source_url="https://example.invalid/feed",
            source_type="rss",
            is_enabled=False,
            refresh_interval_minutes=60,
        )
        db.add(source)
        db.flush()
        notice = NormalizedNotice(
            external_notice_id="same-1",
            title="Service update",
            summary="No change",
            full_text="No change",
            route_ids=["10"],
            advisory_type="delay",
        )

        assert process_notices(db, source, [notice]) == (1, 0)
        db.commit()
        assert process_notices(db, source, [notice]) == (0, 0)
        db.commit()

        assert db.scalar(select(Advisory).where(Advisory.external_notice_id == "same-1")) is not None
        assert db.scalar(select(AdvisoryHistory)) is not None
        assert len(db.scalars(select(AdvisoryHistory)).all()) == 1
        assert len(db.scalars(select(AlertEvent)).all()) == 1


def test_revised_notice_updates_existing_record_and_history():
    with Session(_database()) as db:
        agency = Agency(agency_name="Test Agency")
        source = Source(
            agency=agency,
            source_name="Fixture",
            source_url="https://example.invalid/feed",
            source_type="rss",
            is_enabled=False,
            refresh_interval_minutes=60,
        )
        db.add(source)
        db.flush()
        first = NormalizedNotice(
            external_notice_id="rev-1",
            title="Maintenance",
            summary="Until 10:00",
            full_text="Until 10:00",
            valid_to=datetime(2026, 11, 3, 10),
        )
        revised = NormalizedNotice(
            external_notice_id="rev-1",
            title="Maintenance",
            summary="Until 12:00",
            full_text="Until 12:00",
            valid_to=datetime(2026, 11, 3, 12),
        )
        process_notices(db, source, [first])
        db.commit()
        assert process_notices(db, source, [revised]) == (0, 1)
        db.commit()

        advisory = db.scalar(select(Advisory).where(Advisory.external_notice_id == "rev-1"))
        assert advisory is not None
        assert advisory.revision_id == 2
        assert advisory.summary == "Until 12:00"
        assert len(db.scalars(select(AdvisoryHistory)).all()) == 2
