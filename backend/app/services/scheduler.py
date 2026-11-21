from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import select
from datetime import datetime, timezone
from threading import Lock

from ..database import SessionLocal
from ..models import Source
from .refresh import refresh_source


scheduler = BackgroundScheduler()
refresh_lock = Lock()


def refresh_enabled_sources() -> None:
    if not refresh_lock.acquire(blocking=False):
        return
    with SessionLocal() as db:
        try:
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            sources = db.scalars(select(Source).where(Source.is_enabled.is_(True))).all()
            for source in sources:
                if source.last_attempted_at is not None:
                    elapsed = (now - source.last_attempted_at).total_seconds() / 60
                    if elapsed < source.refresh_interval_minutes:
                        continue
                refresh_source(db, source)
        finally:
            refresh_lock.release()


def start_scheduler() -> None:
    if not scheduler.running:
        scheduler.add_job(refresh_enabled_sources, "interval", minutes=5, id="source-refresh", replace_existing=True)
        scheduler.start()


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
