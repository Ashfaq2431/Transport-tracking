from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from backend.app.database import Base
from backend.app.models import Agency, Advisory, AdvisoryRoute, Source


def test_advisory_can_store_multiple_routes():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        agency = Agency(agency_name="Demo Transit", official_website="https://example.test")
        source = Source(
            agency=agency,
            source_name="Local fixture",
            source_url="https://example.test/fixture.xml",
            source_type="rss",
            refresh_interval_minutes=30,
        )
        advisory = Advisory(
            agency=agency,
            source=source,
            external_notice_id="demo-001",
            advisory_type="delay",
            title="Demo delay",
            status="active",
        )
        advisory.routes.extend(
            [AdvisoryRoute(route_id="10"), AdvisoryRoute(route_id="20")]
        )
        session.add(advisory)
        session.commit()

        stored = session.scalar(select(Advisory).where(Advisory.external_notice_id == "demo-001"))

        assert stored is not None
        assert {route.route_id for route in stored.routes} == {"10", "20"}
