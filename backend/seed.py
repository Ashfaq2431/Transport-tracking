from datetime import datetime, timedelta, timezone
from sqlalchemy import select

from app.database import SessionLocal
from app.models import Agency, Source, Advisory, AdvisoryRoute, AdvisoryHistory, AlertEvent
from app.scrapers.normalize import content_hash


AGENCIES_AND_SOURCES = [
    {
        "agency_name": "MTC Chennai (Metropolitan Transport Corporation)",
        "official_website": "https://mtcbus.tn.gov.in",
        "sources": [
            {
                "source_name": "MTC Chennai Route Diversions & Terminus Updates",
                "source_url": "https://mtcbus.tn.gov.in/Home/news",
                "source_type": "tn_transport",
                "is_enabled": True,
                "refresh_interval_minutes": 30,
            }
        ],
    },
    {
        "agency_name": "TNSTC (Tamil Nadu State Transport Corporation)",
        "official_website": "https://www.tnstc.in",
        "sources": [
            {
                "source_name": "TNSTC Intercity Operations & Festival Specials",
                "source_url": "https://www.tnstc.in/service-bulletins.html",
                "source_type": "tn_transport",
                "is_enabled": True,
                "refresh_interval_minutes": 60,
            }
        ],
    },
    {
        "agency_name": "SETC (State Express Transport Corporation)",
        "official_website": "https://www.tnstc.in",
        "sources": [
            {
                "source_name": "SETC Long-Distance Express Bulletins",
                "source_url": "https://www.tnstc.in/setc-bulletins.html",
                "source_type": "tn_transport",
                "is_enabled": True,
                "refresh_interval_minutes": 60,
            }
        ],
    },
    {
        "agency_name": "CMRL (Chennai Metro Rail Limited)",
        "official_website": "https://chennaimetrorail.org",
        "sources": [
            {
                "source_name": "CMRL Metro Corridor & Passenger Advisories",
                "source_url": "https://chennaimetrorail.org/press-release/",
                "source_type": "tn_transport",
                "is_enabled": True,
                "refresh_interval_minutes": 30,
            }
        ],
    },
    {
        "agency_name": "Southern Railway (Indian Railways - Chennai Division)",
        "official_website": "https://sr.indianrailways.gov.in",
        "sources": [
            {
                "source_name": "Southern Railway Chennai Suburban & Line Block Updates",
                "source_url": "https://sr.indianrailways.gov.in/press_releases.html",
                "source_type": "railways",
                "is_enabled": True,
                "refresh_interval_minutes": 30,
            }
        ],
    },
]

INITIAL_ADVISORIES = [
    {
        "agency_name": "MTC Chennai (Metropolitan Transport Corporation)",
        "source_url": "https://mtcbus.tn.gov.in/Home/news",
        "external_notice_id": "MTC-ADV-2026-001",
        "title": "Broadway Bus Terminus Temporarily Shifted to Island Grounds and Royapuram",
        "summary": "Due to extensive modernization and renovation works at the Broadway Bus Stand, all bus services originating from Broadway are temporarily operating from Island Grounds and Royapuram terminals.",
        "full_text": "MTC Chennai informs the travelling public that pursuant to the redevelopment of the Broadway Bus Terminus into an integrated multimodal transit hub, operations have been relocated. Passengers taking north-bound routes (11G, 17D) please board at Royapuram; south-bound and central services (102, 21G, A1) are operating from Island Grounds.",
        "routes": ["11G", "17D", "21G", "102", "A1"],
        "area": "Broadway / Island Grounds",
        "advisory_type": "route diversion",
        "status": "active",
        "hours_ago": 3,
        "valid_days": 30,
    },
    {
        "agency_name": "MTC Chennai (Metropolitan Transport Corporation)",
        "source_url": "https://mtcbus.tn.gov.in/Home/news",
        "external_notice_id": "MTC-ADV-2026-002",
        "title": "Kilambakkam (KCBT) Bus Terminal Route Extensions for Tambaram & OMR",
        "summary": "120 additional feeder and link bus trips deployed connecting Tambaram, Guindy, and OMR Sholinganallur to the newly operational Kalaignar Centenary Bus Terminus (KCBT).",
        "full_text": "To cater to passenger flow for mofussil buses at Kilambakkam, MTC routes 70C, 104, 118, and 500 will run at an enhanced frequency of every 6 minutes during peak commuter hours.",
        "routes": ["70C", "104", "118", "500"],
        "area": "Kilambakkam (KCBT) / Tambaram",
        "advisory_type": "service update",
        "status": "active",
        "hours_ago": 8,
        "valid_days": 45,
    },
    {
        "agency_name": "Southern Railway (Indian Railways - Chennai Division)",
        "source_url": "https://sr.indianrailways.gov.in/press_releases.html",
        "external_notice_id": "SR-MAS-2026-089",
        "title": "Mega Line Block between Chennai Beach and Tambaram: Suburban EMU Regulation",
        "summary": "Engineering maintenance and third line track works between Chennai Beach and Tambaram / Chengalpattu require regulated suburban EMU operations on Sunday.",
        "full_text": "Southern Railway Chennai Division has announced a 6-hour mega line block between St. Thomas Mount and Tambaram for safety signaling and track renewal. Regular suburban EMU trains between Beach and Tambaram will be replaced with passenger special trains operating every 20 minutes from Park Station.",
        "routes": ["EMU-SUBURBAN", "MSB-TBM", "EMU-4001", "EMU-4002"],
        "area": "Chennai Beach - Tambaram",
        "advisory_type": "planned maintenance",
        "status": "active",
        "hours_ago": 5,
        "valid_days": 2,
    },
    {
        "agency_name": "Southern Railway (Indian Railways - Chennai Division)",
        "source_url": "https://sr.indianrailways.gov.in/press_releases.html",
        "external_notice_id": "SR-MAS-2026-090",
        "title": "Bridge Safety Works at Avadi: Short-Term Delays on Chennai Central - Arakkonam Section",
        "summary": "Speed restrictions and 15-20 minute delays expected on suburban trains between MMC (Moore Market Complex) and Tiruvallur / Arakkonam.",
        "full_text": "Passengers traveling on the Western suburban corridor (Chennai Central to Arakkonam / Tiruttani) are advised that bridge maintenance near Avadi will result in speed restrictions of 30 km/h, leading to minor service delays.",
        "routes": ["MAS-AJJ", "EMU-4301", "EMU-4302"],
        "area": "Chennai Central - Arakkonam",
        "advisory_type": "delay",
        "status": "active",
        "hours_ago": 12,
        "valid_days": 1,
    },
    {
        "agency_name": "TNSTC (Tamil Nadu State Transport Corporation)",
        "source_url": "https://www.tnstc.in/service-bulletins.html",
        "external_notice_id": "TNSTC-FEST-2026-014",
        "title": "Festival Special Bus Operations: 4,200 Additional Buses Across All Districts",
        "summary": "TNSTC announces special intercity operations originating from Chennai (KCBT, Madhavaram, Tambaram MEPZ) to Madurai, Salem, Coimbatore, and Tiruchirappalli.",
        "full_text": "To handle high festive passenger turnout, round-the-clock control rooms are active at Kilambakkam (KCBT), Madhavaram New Bus Stand, and Koyambedu. Advance online reservations open at tnstc.in and the Arasu Bus mobile application.",
        "routes": ["TNSTC-MDU", "TNSTC-SLM", "TNSTC-CBE", "TNSTC-TRZ"],
        "area": "All Districts / Intercity",
        "advisory_type": "special service",
        "status": "active",
        "hours_ago": 18,
        "valid_days": 7,
    },
    {
        "agency_name": "CMRL (Chennai Metro Rail Limited)",
        "source_url": "https://chennaimetrorail.org/press-release/",
        "external_notice_id": "CMRL-PR-2026-042",
        "title": "Metro Rail Timings Extended up to 23:30 for Weekend Commuters",
        "summary": "Chennai Metro operations on Blue Line (Wimco Nagar to Airport) and Green Line (Central to St. Thomas Mount) will operate with 5-minute peak frequency until 23:30.",
        "full_text": "In response to increased evening ridership and weekend sports/cultural events in Chennai, CMRL extends train operating hours. Feeder mini-bus services at Alandur, Guindy, and Airport Metro stations will align with final train arrivals.",
        "routes": ["BLUE LINE", "GREEN LINE"],
        "area": "Puratchi Thalaivar Dr. MGR Central / Chennai Airport",
        "advisory_type": "service update",
        "status": "active",
        "hours_ago": 24,
        "valid_days": 14,
    },
    {
        "agency_name": "SETC (State Express Transport Corporation)",
        "source_url": "https://www.tnstc.in/setc-bulletins.html",
        "external_notice_id": "SETC-EXP-2026-008",
        "title": "New AC Sleeper Non-Stop Corridor: Chennai to Bengaluru & Coimbatore",
        "summary": "SETC introduces new ultra-deluxe multi-axle AC sleeper night buses departing Kilambakkam (KCBT) nightly at 22:30.",
        "full_text": "Equipped with live GPS tracking, emergency response systems, and ergonomic sleeper berths, SETC expands its premium express fleet connecting major industrial hubs.",
        "routes": ["SETC-BLR", "SETC-CBE"],
        "area": "Chennai / Bengaluru / Coimbatore",
        "advisory_type": "service update",
        "status": "active",
        "hours_ago": 48,
        "valid_days": 60,
    },
]


def seed_demo_configuration() -> None:
    """Seed Tamil Nadu transport and Southern Railway agencies, sources, and advisories."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with SessionLocal() as session:
        agency_map: dict[str, Agency] = {}
        source_map: dict[str, Source] = {}

        # 1. Seed Agencies and Sources
        for item in AGENCIES_AND_SOURCES:
            agency = session.scalar(select(Agency).where(Agency.agency_name == item["agency_name"]))
            if agency is None:
                agency = Agency(
                    agency_name=item["agency_name"],
                    official_website=item["official_website"],
                    created_at=now,
                )
                session.add(agency)
                session.flush()
            agency_map[item["agency_name"]] = agency

            for s_info in item["sources"]:
                source = session.scalar(select(Source).where(Source.source_url == s_info["source_url"]))
                if source is None:
                    source = Source(
                        agency_id=agency.agency_id,
                        source_name=s_info["source_name"],
                        source_url=s_info["source_url"],
                        source_type=s_info["source_type"],
                        is_enabled=s_info["is_enabled"],
                        refresh_interval_minutes=s_info["refresh_interval_minutes"],
                        last_successful_at=now,
                        created_at=now,
                    )
                    session.add(source)
                    session.flush()
                source_map[s_info["source_url"]] = source

        # 2. Seed Initial Realistic Advisories
        for adv_data in INITIAL_ADVISORIES:
            source = source_map.get(adv_data["source_url"])
            agency = agency_map.get(adv_data["agency_name"])
            if not source or not agency:
                continue

            existing = session.scalar(
                select(Advisory).where(
                    Advisory.source_id == source.source_id,
                    Advisory.external_notice_id == adv_data["external_notice_id"],
                )
            )
            if existing is None:
                pub_time = now - timedelta(hours=adv_data["hours_ago"])
                valid_until = pub_time + timedelta(days=adv_data["valid_days"])
                c_hash = content_hash(adv_data["title"], adv_data["summary"], adv_data["area"])

                advisory = Advisory(
                    agency_id=agency.agency_id,
                    source_id=source.source_id,
                    external_notice_id=adv_data["external_notice_id"],
                    area=adv_data["area"],
                    advisory_type=adv_data["advisory_type"],
                    title=adv_data["title"],
                    summary=adv_data["summary"],
                    full_text=adv_data["full_text"],
                    source_url=adv_data["source_url"],
                    published_at=pub_time,
                    valid_from=pub_time,
                    valid_to=valid_until,
                    status=adv_data["status"],
                    observed_at=now,
                    last_confirmed_at=now,
                    content_hash=c_hash,
                    revision_id=1,
                    change_summary="Initial Tamil Nadu transport advisory notice",
                )
                advisory.routes = [AdvisoryRoute(route_id=r) for r in adv_data["routes"]]
                session.add(advisory)
                session.flush()

                session.add(
                    AdvisoryHistory(
                        notice_id=advisory.notice_id,
                        revision_number=1,
                        content_hash=c_hash,
                        change_summary="Initial Tamil Nadu transport advisory notice",
                        current_snapshot=adv_data["summary"],
                        observed_at=now,
                    )
                )
                session.add(
                    AlertEvent(
                        notice_id=advisory.notice_id,
                        revision_id=1,
                        event_type="new_advisory",
                        message=adv_data["title"],
                        delivery_status="delivered",
                        created_at=pub_time,
                    )
                )

        session.commit()


if __name__ == "__main__":
    seed_demo_configuration()
    print("Tamil Nadu Transport and Southern Railway agencies, sources, and advisories seeded successfully.")
