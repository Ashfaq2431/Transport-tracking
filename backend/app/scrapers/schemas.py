from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class NormalizedNotice:
    """Common notice shape produced by every source adapter."""

    external_notice_id: Optional[str]
    title: str
    summary: Optional[str]
    full_text: Optional[str]
    route_ids: list[str] = field(default_factory=list)
    area: Optional[str] = None
    advisory_type: str = "general service update"
    source_url: Optional[str] = None
    published_at: Optional[datetime] = None
    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None
    withdrawn: bool = False

