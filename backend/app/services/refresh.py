import json
import logging
import time
from datetime import datetime, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Advisory, AdvisoryHistory, AdvisoryRoute, AlertEvent, RefreshRun, Source
from ..scrapers.html import HtmlNoticeAdapter
from ..scrapers.rss import RssNoticeAdapter
from ..scrapers.tn_transport import TNTransportAdapter
from ..scrapers.schemas import NormalizedNotice
from ..scrapers.normalize import content_hash
from .notice_status import calculate_status

logger = logging.getLogger(__name__)
MAX_BODY_BYTES = 2_000_000


def _adapter(source: Source):
    stype = (source.source_type or "").lower()
    if stype in {"rss", "atom"}:
        return RssNoticeAdapter(source.source_url)
    if stype in {"html", "tn_transport", "tamilnadu", "mtc", "tnstc", "cmrl", "railways", "southern_railway"}:
        return TNTransportAdapter(source.source_url)
    raise ValueError(f"Unsupported source type: {source.source_type}")


def fetch_source_body(source: Source, retries: int = 2) -> str:
    headers = {"User-Agent": "TNTransitTracker/1.0 (Tamil Nadu Transport and Railway Monitor)"}
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            with httpx.Client(timeout=10.0, follow_redirects=True) as client:
                response = client.get(source.source_url, headers=headers)
                response.raise_for_status()
                body = response.content
                if len(body) > MAX_BODY_BYTES:
                    raise ValueError("source response exceeds the 2 MB limit")
                return body.decode(response.encoding or "utf-8", errors="replace")
        except (httpx.HTTPError, UnicodeError, ValueError) as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(2**attempt)
    raise RuntimeError(f"source fetch failed: {last_error}") from last_error


def _snapshot(notice: NormalizedNotice) -> str:
    return json.dumps(
        {
            "title": notice.title,
            "summary": notice.summary,
            "full_text": notice.full_text,
            "routes": notice.route_ids,
            "area": notice.area,
            "type": notice.advisory_type,
            "valid_from": notice.valid_from.isoformat() if notice.valid_from else None,
            "valid_to": notice.valid_to.isoformat() if notice.valid_to else None,
            "withdrawn": notice.withdrawn,
        },
        sort_keys=True,
    )


def _find_existing(db: Session, source_id: int, notice: NormalizedNotice) -> Advisory | None:
    if notice.external_notice_id:
        return db.scalar(
            select(Advisory).where(
                Advisory.source_id == source_id,
                Advisory.external_notice_id == notice.external_notice_id,
            )
        )
    return db.scalar(
        select(Advisory).where(
            Advisory.source_id == source_id,
            Advisory.title == notice.title,
            Advisory.source_url == notice.source_url,
        )
    )


def _change_summary(old: Advisory, notice: NormalizedNotice) -> str:
    changed = []
    if old.title != notice.title:
        changed.append("title")
    if old.summary != notice.summary:
        changed.append("summary")
    if old.valid_to != notice.valid_to:
        changed.append("validity")
    if old.area != notice.area or old.advisory_type != notice.advisory_type:
        changed.append("classification")
    return "Updated " + ", ".join(changed) if changed else "Notice content revised"


def process_notices(db: Session, source: Source, notices: list[NormalizedNotice]) -> tuple[int, int]:
    created = updated = 0
    observed = datetime.now(timezone.utc).replace(tzinfo=None)
    for notice in notices:
        current_hash = content_hash(_snapshot(notice))
        existing = _find_existing(db, source.source_id, notice)
        if existing is None:
            existing = Advisory(
                agency_id=source.agency_id,
                source_id=source.source_id,
                external_notice_id=notice.external_notice_id,
                area=notice.area,
                advisory_type=notice.advisory_type,
                title=notice.title,
                summary=notice.summary,
                full_text=notice.full_text,
                source_url=notice.source_url,
                published_at=notice.published_at,
                valid_from=notice.valid_from,
                valid_to=notice.valid_to,
                status=calculate_status(notice.valid_from, notice.valid_to, notice.withdrawn),
                observed_at=observed,
                last_confirmed_at=observed,
                content_hash=current_hash,
                revision_id=1,
                change_summary="New advisory",
            )
            existing.routes = [AdvisoryRoute(route_id=route) for route in notice.route_ids]
            db.add(existing)
            db.flush()
            db.add(
                AdvisoryHistory(
                    notice_id=existing.notice_id,
                    revision_number=1,
                    content_hash=current_hash,
                    change_summary="New advisory",
                    current_snapshot=_snapshot(notice),
                    observed_at=observed,
                )
            )
            db.add(
                AlertEvent(
                    notice_id=existing.notice_id,
                    revision_id=1,
                    event_type="new_advisory",
                    message=notice.title,
                    delivery_status="pending",
                )
            )
            created += 1
            continue
        existing.observed_at = observed
        existing.last_confirmed_at = observed
        if existing.content_hash == current_hash:
            continue
        summary = _change_summary(existing, notice)
        previous_hash = existing.content_hash
        previous_snapshot = _snapshot(
            NormalizedNotice(
                external_notice_id=existing.external_notice_id,
                title=existing.title,
                summary=existing.summary,
                full_text=existing.full_text,
                route_ids=[route.route_id for route in existing.routes],
                area=existing.area,
                advisory_type=existing.advisory_type,
                source_url=existing.source_url,
                published_at=existing.published_at,
                valid_from=existing.valid_from,
                valid_to=existing.valid_to,
            )
        )
        existing.title = notice.title
        existing.summary = notice.summary
        existing.full_text = notice.full_text
        existing.area = notice.area
        existing.advisory_type = notice.advisory_type
        existing.source_url = notice.source_url
        existing.published_at = notice.published_at
        existing.valid_from = notice.valid_from
        existing.valid_to = notice.valid_to
        existing.status = calculate_status(notice.valid_from, notice.valid_to, notice.withdrawn)
        existing.content_hash = current_hash
        existing.revision_id = (existing.revision_id or 0) + 1
        existing.change_summary = summary
        existing.routes = [AdvisoryRoute(route_id=route) for route in notice.route_ids]
        db.add(
            AdvisoryHistory(
                notice_id=existing.notice_id,
                revision_number=existing.revision_id,
                content_hash=current_hash,
                previous_content_hash=previous_hash,
                change_summary=summary,
                previous_snapshot=previous_snapshot,
                current_snapshot=_snapshot(notice),
                observed_at=observed,
            )
        )
        db.add(
            AlertEvent(
                notice_id=existing.notice_id,
                revision_id=existing.revision_id,
                event_type="revised_advisory",
                message=summary,
                delivery_status="pending",
            )
        )
        updated += 1
    return created, updated


def refresh_source(db: Session, source: Source) -> RefreshRun:
    started = datetime.now(timezone.utc).replace(tzinfo=None)
    run = RefreshRun(source_id=source.source_id, started_at=started, outcome="running")
    db.add(run)
    source.last_attempted_at = started
    try:
        body = fetch_source_body(source)
        notices = _adapter(source).parse(body, response_url=source.source_url)
        run.notices_found = len(notices)
        run.notices_created, run.notices_updated = process_notices(db, source, notices)
        run.outcome = "success"
        source.last_successful_at = datetime.now(timezone.utc).replace(tzinfo=None)
        source.last_error = None
    except Exception as exc:
        logger.exception("Refresh failed for source %s", source.source_id)
        run.outcome = "failed"
        run.error_message = str(exc)
        source.last_error = str(exc)
    run.finished_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.add(run)
    db.commit()
    return run
