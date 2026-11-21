import csv
import io
from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.app.database import Base
from backend.app.models import Agency, Advisory, AlertEvent, Source
from backend.app.routers.api import (
    _freshness,
    analytics_summary,
    export_advisories_csv,
    list_advisories,
    list_alerts,
    mark_alert_read,
)


def _db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def test_advisory_search_sort_and_page_metadata():
    with _db() as db:
        agency = Agency(agency_name="Agency")
        source = Source(agency=agency, source_name="Source", source_url="https://example.test",
                        source_type="rss", refresh_interval_minutes=30)
        db.add_all([
            source,
            Advisory(agency=agency, source=source, title="Later disruption",
                     advisory_type="delay", status="active", published_at=datetime(2026, 1, 2)),
            Advisory(agency=agency, source=source, title="Earlier maintenance",
                     advisory_type="maintenance", status="active", published_at=datetime(2026, 1, 1)),
        ])
        db.commit()
        result = list_advisories(search="maintenance", source_id=None, agency_id=None,
                                 published_from=None, published_to=None,
                                 sort_by="published_at", sort_order="asc",
                                 page=1, page_size=1, db=db)
        assert result.total == 1
        assert result.pages == 1
        assert result.items[0].title == "Earlier maintenance"


def test_alert_read_status_and_unread_filter():
    with _db() as db:
        agency = Agency(agency_name="Agency")
        source = Source(agency=agency, source_name="Source", source_url="https://example.test",
                        source_type="rss")
        advisory = Advisory(agency=agency, source=source, title="Alert", advisory_type="delay", status="active")
        db.add(advisory)
        db.flush()
        alert = AlertEvent(notice_id=advisory.notice_id, event_type="new_advisory", message="Alert")
        db.add(alert)
        db.commit()
        mark_alert_read(alert.alert_id, db)
        assert list_alerts(unread_only=True, limit=100, db=db) == []
        assert list_alerts(unread_only=False, limit=100, db=db)[0].is_read is True


def test_analytics_and_csv_export_include_summary_data():
    with _db() as db:
        agency = Agency(agency_name="Agency")
        source = Source(agency=agency, source_name="Source", source_url="https://example.test",
                        source_type="rss")
        db.add(Advisory(agency=agency, source=source, title="Notice", advisory_type="delay", status="active"))
        db.commit()
        summary = analytics_summary(db)
        assert summary["total_advisories"] == 1
        response = export_advisories_csv(db)
        assert response.media_type == "text/csv"
        assert "advisories.csv" in response.headers["content-disposition"]


def test_source_freshness_reports_overdue():
    source = Source(source_name="Source", source_url="https://example.test", source_type="rss",
                    agency_id=1, is_enabled=True, refresh_interval_minutes=30,
                    last_successful_at=datetime.utcnow() - timedelta(hours=2))
    assert _freshness(source)[0] == "overdue"
