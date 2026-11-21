import csv
import io
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..models import Advisory, AdvisoryHistory, AdvisoryRoute, AlertEvent, RefreshRun, Source
from ..schemas import (
    AdvisoryListResponse,
    AdvisoryResponse,
    AlertResponse,
    DashboardSummaryResponse,
    RefreshRunResponse,
    SourceResponse,
)
from ..services.notice_status import calculate_status, is_stale
from ..services.refresh import refresh_source

router = APIRouter(prefix="/api", tags=["TNTransport"])


def _advisory_response(advisory: Advisory) -> AdvisoryResponse:
    return AdvisoryResponse(
        notice_id=advisory.notice_id,
        title=advisory.title,
        summary=advisory.summary,
        full_text=advisory.full_text,
        advisory_type=advisory.advisory_type,
        area=advisory.area,
        status="stale" if advisory.status == "active" and is_stale(advisory.last_confirmed_at) else advisory.status,
        source_url=advisory.source_url,
        published_at=advisory.published_at,
        valid_from=advisory.valid_from,
        valid_to=advisory.valid_to,
        observed_at=advisory.observed_at,
        last_confirmed_at=advisory.last_confirmed_at,
        revision_id=advisory.revision_id,
        change_summary=advisory.change_summary,
        routes=[{"route_id": route.route_id} for route in advisory.routes],
        agency_name=advisory.agency.agency_name if advisory.agency else "Official Agency",
        source_name=advisory.source.source_name if advisory.source else "Official Source",
    )


@router.get("/dashboard/summary", response_model=DashboardSummaryResponse)
def dashboard_summary(db: Session = Depends(get_db)) -> DashboardSummaryResponse:
    advisories = db.scalars(select(Advisory)).all()
    for advisory in advisories:
        advisory.status = calculate_status(advisory.valid_from, advisory.valid_to, advisory.status == "withdrawn")
    sources_needing_attention = db.scalar(
        select(func.count(Source.source_id)).where(
            or_(Source.last_error.is_not(None), Source.last_successful_at.is_(None))
        )
    ) or 0
    return DashboardSummaryResponse(
        active=sum(item.status == "active" for item in advisories),
        scheduled=sum(item.status == "scheduled" for item in advisories),
        expired=sum(item.status == "expired" for item in advisories),
        recently_changed=sum(item.revision_id is not None and item.revision_id > 1 for item in advisories),
        sources_needing_attention=sources_needing_attention,
        last_checked=max((item.last_confirmed_at for item in advisories if item.last_confirmed_at), default=None),
    )


@router.get("/advisories", response_model=AdvisoryListResponse)
def list_advisories(
    search: Optional[str] = Query(None, max_length=200),
    status: Optional[str] = Query(None, max_length=20),
    route: Optional[str] = Query(None, max_length=100),
    area: Optional[str] = Query(None, max_length=255),
    advisory_type: Optional[str] = Query(None, max_length=50),
    source_id: Optional[int] = Query(None, ge=1),
    agency_id: Optional[int] = Query(None, ge=1),
    published_from: Optional[datetime] = None,
    published_to: Optional[datetime] = None,
    sort_by: str = Query("published_at", pattern="^(published_at|valid_to|title|status|observed_at)$"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> AdvisoryListResponse:
    query = select(Advisory).options(joinedload(Advisory.agency), joinedload(Advisory.source), joinedload(Advisory.routes))
    if search and isinstance(search, str):
        term = f"%{search}%"
        query = query.where(or_(
            Advisory.title.ilike(term), Advisory.summary.ilike(term),
            Advisory.full_text.ilike(term), Advisory.area.ilike(term),
        ))
    if status and isinstance(status, str):
        query = query.where(Advisory.status == status.lower())
    if area and isinstance(area, str):
        query = query.where(Advisory.area.ilike(f"%{area}%"))
    if advisory_type and isinstance(advisory_type, str):
        query = query.where(Advisory.advisory_type == advisory_type.lower())
    if source_id:
        query = query.where(Advisory.source_id == source_id)
    if agency_id:
        query = query.where(Advisory.agency_id == agency_id)
    if published_from:
        query = query.where(Advisory.published_at >= published_from)
    if published_to:
        query = query.where(Advisory.published_at <= published_to)
    if route and isinstance(route, str):
        query = query.join(AdvisoryRoute).where(AdvisoryRoute.route_id == route.upper())
    total_query = select(func.count()).select_from(query.order_by(None).subquery())
    total = db.scalar(total_query) or 0
    sort_column = getattr(Advisory, sort_by)
    sort_column = sort_column.asc() if sort_order == "asc" else sort_column.desc()
    items = db.scalars(query.order_by(sort_column, Advisory.notice_id.desc()).offset((page - 1) * page_size).limit(page_size)).unique().all()
    return AdvisoryListResponse(
        items=[_advisory_response(item) for item in items],
        page=page,
        page_size=page_size,
        total=total,
        pages=(total + page_size - 1) // page_size,
    )


@router.get("/advisories/export.csv", include_in_schema=False)
def export_advisories_csv_route(
    db: Session = Depends(get_db),
    search: Optional[str] = Query(None, max_length=200),
    status: Optional[str] = Query(None, max_length=20),
    route: Optional[str] = Query(None, max_length=100),
    area: Optional[str] = Query(None, max_length=255),
    advisory_type: Optional[str] = Query(None, max_length=50),
    source_id: Optional[int] = Query(None, ge=1),
    agency_id: Optional[int] = Query(None, ge=1),
    published_from: Optional[datetime] = None,
    published_to: Optional[datetime] = None,
) -> StreamingResponse:
    return export_advisories_csv(
        db, search, status, route, area, advisory_type, source_id, agency_id,
        published_from, published_to,
    )


@router.get("/advisories/{notice_id}", response_model=AdvisoryResponse)
def get_advisory(notice_id: int, db: Session = Depends(get_db)) -> AdvisoryResponse:
    advisory = db.scalar(
        select(Advisory)
        .options(joinedload(Advisory.agency), joinedload(Advisory.source), joinedload(Advisory.routes))
        .where(Advisory.notice_id == notice_id)
    )
    if advisory is None:
        raise HTTPException(status_code=404, detail="Advisory not found")
    return _advisory_response(advisory)


@router.get("/advisories/{notice_id}/history")
def advisory_history(
    notice_id: int, page: Optional[int] = Query(None, ge=1), page_size: Optional[int] = Query(None, ge=1, le=100),
    db: Session = Depends(get_db)
) -> dict | list[dict]:
    if db.scalar(select(Advisory.notice_id).where(Advisory.notice_id == notice_id)) is None:
        raise HTTPException(status_code=404, detail="Advisory not found")
    query = select(AdvisoryHistory).where(AdvisoryHistory.notice_id == notice_id)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    requested_page = page or 1
    requested_size = page_size or max(total, 1)
    items = [
        {
            "history_id": item.history_id,
            "revision_number": item.revision_number,
            "change_summary": item.change_summary,
            "previous_snapshot": item.previous_snapshot,
            "current_snapshot": item.current_snapshot,
            "observed_at": item.observed_at,
            "content_hash": item.content_hash,
            "previous_content_hash": item.previous_content_hash,
        }
        for item in db.scalars(query.order_by(AdvisoryHistory.revision_number.desc())
                               .offset((requested_page - 1) * requested_size).limit(requested_size))
    ]
    if page is None and page_size is None:
        return items
    return {"items": items, "page": page, "page_size": page_size, "total": total,
            "pages": (total + requested_size - 1) // requested_size}


def _freshness(source: Source) -> tuple[str, Optional[datetime]]:
    if not source.is_enabled:
        return "disabled", None
    if source.last_successful_at is None:
        return "never", None
    next_refresh = source.last_successful_at + timedelta(minutes=source.refresh_interval_minutes)
    if source.last_error:
        return "error", next_refresh
    return ("overdue" if datetime.utcnow() >= next_refresh else "fresh"), next_refresh


def _source_response(source: Source) -> SourceResponse:
    freshness, next_refresh = _freshness(source)
    return SourceResponse(
        source_id=source.source_id, source_name=source.source_name, source_url=source.source_url,
        source_type=source.source_type, is_enabled=source.is_enabled,
        refresh_interval_minutes=source.refresh_interval_minutes,
        last_attempted_at=source.last_attempted_at, last_successful_at=source.last_successful_at,
        last_error=source.last_error, notice_count=len(source.advisories),
        agency_name=source.agency.agency_name if source.agency else "Official Agency",
        freshness_status=freshness, next_refresh_at=next_refresh,
    )


@router.get("/sources", response_model=list[SourceResponse])
def list_sources(db: Session = Depends(get_db)) -> list[SourceResponse]:
    sources = db.scalars(select(Source).options(joinedload(Source.agency))).unique().all()
    return [_source_response(source) for source in sources]


@router.get("/sources/health")
def source_health(db: Session = Depends(get_db)) -> list[dict]:
    return [{"source_id": source.source_id, "source_name": source.source_name,
             "freshness_status": _freshness(source)[0],
             "last_successful_at": source.last_successful_at,
             "last_error": source.last_error}
            for source in db.scalars(select(Source).order_by(Source.source_name)).all()]


@router.get("/sources/{source_id}", response_model=SourceResponse)
def get_source(source_id: int, db: Session = Depends(get_db)) -> SourceResponse:
    source = db.scalar(select(Source).options(joinedload(Source.agency), joinedload(Source.advisories)).where(Source.source_id == source_id))
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    return _source_response(source)


@router.get("/refresh-runs", response_model=list[RefreshRunResponse])
def list_refresh_runs(db: Session = Depends(get_db)) -> list[RefreshRunResponse]:
    return list(db.scalars(select(RefreshRun).order_by(RefreshRun.started_at.desc()).limit(50)))


@router.get("/sources/{source_id}/refresh-runs", response_model=list[RefreshRunResponse])
def source_refresh_runs(source_id: int, limit: int = Query(50, ge=1, le=200),
                        db: Session = Depends(get_db)) -> list[RefreshRunResponse]:
    if db.get(Source, source_id) is None:
        raise HTTPException(status_code=404, detail="Source not found")
    return list(db.scalars(select(RefreshRun).where(RefreshRun.source_id == source_id)
                           .order_by(RefreshRun.started_at.desc()).limit(limit)))


@router.post("/refresh")
def refresh_all(db: Session = Depends(get_db)) -> dict:
    sources = db.scalars(select(Source).where(Source.is_enabled.is_(True))).all()
    runs = [refresh_source(db, source) for source in sources]
    return {"runs": [RefreshRunResponse.model_validate(run) for run in runs]}


@router.post("/sources/{source_id}/refresh", response_model=RefreshRunResponse)
def refresh_one(source_id: int, db: Session = Depends(get_db)) -> RefreshRunResponse:
    source = db.get(Source, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    return refresh_source(db, source)


@router.get("/alerts", response_model=list[AlertResponse])
def list_alerts(unread_only: bool = False, limit: int = Query(100, ge=1, le=500),
                db: Session = Depends(get_db)) -> list[AlertResponse]:
    query = select(AlertEvent)
    if unread_only:
        query = query.where(AlertEvent.read_at.is_(None))
    query = query.order_by(AlertEvent.created_at.desc()).limit(limit)
    return [AlertResponse.model_validate(alert).model_copy(update={"is_read": alert.read_at is not None})
            for alert in db.scalars(query)]


@router.post("/alerts/{alert_id}/read", response_model=AlertResponse)
def mark_alert_read(alert_id: int, db: Session = Depends(get_db)) -> AlertResponse:
    alert = db.get(AlertEvent, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert.read_at = alert.read_at or datetime.utcnow()
    alert.delivery_status = "read"
    db.commit()
    return AlertResponse.model_validate(alert).model_copy(update={"is_read": True})


@router.post("/alerts/read-all")
def mark_all_alerts_read(db: Session = Depends(get_db)) -> dict:
    count = db.query(AlertEvent).filter(AlertEvent.read_at.is_(None)).update(
        {AlertEvent.read_at: datetime.utcnow(), AlertEvent.delivery_status: "read"}
    )
    db.commit()
    return {"marked_read": count}


@router.get("/analytics")
@router.get("/analytics/summary")
def analytics_summary(db: Session = Depends(get_db)) -> dict:
    advisories = db.scalars(select(Advisory)).all()
    by_status = {status: sum(a.status == status for a in advisories)
                 for status in ("active", "scheduled", "expired", "withdrawn", "unknown")}
    by_type = {}
    for advisory in advisories:
        by_type[advisory.advisory_type] = by_type.get(advisory.advisory_type, 0) + 1
    by_source = db.execute(
        select(Source.source_name, func.count(Advisory.notice_id))
        .join(Advisory, Advisory.source_id == Source.source_id).group_by(Source.source_id, Source.source_name)
    ).all()
    return {"total_advisories": len(advisories), "by_status": by_status, "by_type": by_type,
            "by_source": [{"source_name": name, "count": count} for name, count in by_source],
            "total_revisions": db.scalar(select(func.count(AdvisoryHistory.history_id))) or 0,
            "unread_alerts": db.scalar(select(func.count(AlertEvent.alert_id)).where(AlertEvent.read_at.is_(None))) or 0}


def _csv_value(value: object) -> object:
    if not isinstance(value, str):
        return value
    return f"'{value}" if value.startswith(("=", "+", "-", "@")) else value


@router.get("/advisories/export.csv")
def export_advisories_csv(
    db: Session = Depends(get_db),
    search: Optional[str] = Query(None, max_length=200),
    status: Optional[str] = Query(None, max_length=20),
    route: Optional[str] = Query(None, max_length=100),
    area: Optional[str] = Query(None, max_length=255),
    advisory_type: Optional[str] = Query(None, max_length=50),
    source_id: Optional[int] = Query(None, ge=1),
    agency_id: Optional[int] = Query(None, ge=1),
    published_from: Optional[datetime] = None,
    published_to: Optional[datetime] = None,
) -> StreamingResponse:
    if not isinstance(search, str):
        search = None
    if not isinstance(status, str):
        status = None
    if not isinstance(route, str):
        route = None
    if not isinstance(area, str):
        area = None
    if not isinstance(advisory_type, str):
        advisory_type = None
    if not isinstance(source_id, int):
        source_id = None
    if not isinstance(agency_id, int):
        agency_id = None
    query = select(Advisory).options(
        joinedload(Advisory.agency),
        joinedload(Advisory.source),
        joinedload(Advisory.routes),
    )
    if search:
        term = f"%{search}%"
        query = query.where(or_(
            Advisory.title.ilike(term), Advisory.summary.ilike(term),
            Advisory.full_text.ilike(term), Advisory.area.ilike(term),
        ))
    if status:
        query = query.where(Advisory.status == status.lower())
    if route:
        query = query.join(AdvisoryRoute).where(AdvisoryRoute.route_id == route.upper())
    if area:
        query = query.where(Advisory.area.ilike(f"%{area}%"))
    if advisory_type:
        query = query.where(Advisory.advisory_type == advisory_type.lower())
    if source_id:
        query = query.where(Advisory.source_id == source_id)
    if agency_id:
        query = query.where(Advisory.agency_id == agency_id)
    if published_from:
        query = query.where(Advisory.published_at >= published_from)
    if published_to:
        query = query.where(Advisory.published_at <= published_to)
    advisories = db.scalars(query.order_by(Advisory.published_at.desc())).unique().all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["notice_id", "title", "agency", "route", "affected_area", "advisory_type",
                     "status", "published_at", "valid_from", "valid_to", "last_verified_at", "source_url"])
    for advisory in advisories:
        writer.writerow([_csv_value(advisory.notice_id), _csv_value(advisory.title),
                         _csv_value(advisory.agency.agency_name if advisory.agency else ""),
                         _csv_value("; ".join(route.route_id for route in advisory.routes)),
                         _csv_value(advisory.area), _csv_value(advisory.advisory_type),
                         _csv_value(advisory.status), advisory.published_at, advisory.valid_from,
                         advisory.valid_to, advisory.last_confirmed_at, _csv_value(advisory.source_url)])
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=advisories.csv"})
