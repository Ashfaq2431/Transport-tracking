import logging
import re
from datetime import datetime, timezone
import httpx
from bs4 import BeautifulSoup

from app.database import SessionLocal
from app.models import Agency, Source, Advisory, AdvisoryRoute, AdvisoryHistory, AlertEvent
from app.scrapers.normalize import content_hash, normalize_advisory_type
from app.scrapers.tn_transport import TNTransportAdapter
from app.services.refresh import process_notices, fetch_source_body

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def scrape_all_tn_sources():
    """Scrape and refresh all enabled Tamil Nadu transport and Southern Railway sources."""
    print("=================================================================")
    print("Starting Live Scrape: Tamil Nadu Transport & Southern Railway")
    print("=================================================================")

    with SessionLocal() as db:
        sources = db.query(Source).filter(Source.is_enabled.is_(True)).all()
        if not sources:
            print("No enabled sources found in database. Run 'python backend/seed.py' first.")
            return

        adapter = TNTransportAdapter("https://mtcbus.tn.gov.in")

        for source in sources:
            print(f"\n[+] Checking source: {source.source_name} ({source.source_url})")
            try:
                # Attempt live fetch
                body = fetch_source_body(source, retries=1)
                notices = adapter.parse(body, response_url=source.source_url)
                print(f"    Fetched {len(notices)} live notices from portal.")
                created, updated = process_notices(db, source, notices)
                print(f"    Success: {created} new notices created, {updated} updated.")
                source.last_successful_at = datetime.now(timezone.utc).replace(tzinfo=None)
                source.last_error = None
            except Exception as e:
                print(f"    Live fetch warning ({type(e).__name__}): {e}")
                source.last_error = str(e)

        db.commit()
        print("\n=================================================================")
        print("Scrape run completed.")
        print("=================================================================")


if __name__ == "__main__":
    scrape_all_tn_sources()

