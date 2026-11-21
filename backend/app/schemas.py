from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class DashboardSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    active: int
    scheduled: int
    expired: int
    recently_changed: int
    sources_needing_attention: int
    last_checked: Optional[datetime] = None


class AdvisoryRouteResponse(BaseModel):
    route_id: str


class AdvisoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    notice_id: int
    title: str
    summary: Optional[str]
    full_text: Optional[str]
    advisory_type: str
    area: Optional[str]
    status: str
    source_url: Optional[str]
    published_at: Optional[datetime]
    valid_from: Optional[datetime]
    valid_to: Optional[datetime]
    observed_at: datetime
    last_confirmed_at: Optional[datetime]
    revision_id: Optional[int]
    change_summary: Optional[str]
    routes: list[AdvisoryRouteResponse]
    agency_name: str
    source_name: str


class AdvisoryListResponse(BaseModel):
    items: list[AdvisoryResponse]
    page: int
    page_size: int
    total: int
    pages: int


class SourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    source_id: int
    source_name: str
    source_url: str
    source_type: str
    is_enabled: bool
    refresh_interval_minutes: int
    last_attempted_at: Optional[datetime]
    last_successful_at: Optional[datetime]
    last_error: Optional[str]
    notice_count: int
    agency_name: str
    freshness_status: str = "unknown"
    next_refresh_at: Optional[datetime] = None


class RefreshRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    run_id: int
    source_id: int
    started_at: datetime
    finished_at: Optional[datetime]
    outcome: str
    notices_found: int
    notices_created: int
    notices_updated: int
    error_message: Optional[str]


class AlertResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    alert_id: int
    notice_id: int
    revision_id: Optional[int]
    event_type: str
    message: str
    delivery_status: str
    created_at: datetime
    read_at: Optional[datetime] = None
    is_read: bool = False
