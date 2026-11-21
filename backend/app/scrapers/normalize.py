import hashlib
import re
from datetime import datetime, timezone
from typing import Optional

from dateutil import parser as date_parser


TYPE_ALIASES = {
    "delay": "delay",
    "delays": "delay",
    "regulated": "delay",
    "regulation": "delay",
    "diversion": "route diversion",
    "route diversion": "route diversion",
    "terminal shift": "route diversion",
    "terminus change": "route diversion",
    "suspension": "service suspension",
    "suspended": "service suspension",
    "cancellation": "service suspension",
    "cancelled": "service suspension",
    "stop closure": "stop closure",
    "planned maintenance": "planned maintenance",
    "line block": "planned maintenance",
    "power block": "planned maintenance",
    "engineering work": "planned maintenance",
    "resumption": "service resumption",
    "service resumed": "service resumption",
    "special service": "special service",
    "special bus": "special service",
    "special train": "special service",
    "festival special": "special service",
    "new service": "service update",
    "service update": "service update",
}


def clean_text(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    cleaned = re.sub(r"\s+", " ", value).strip()
    return cleaned or None


def normalize_route_ids(value: Optional[str]) -> list[str]:
    if not value:
        return []
    routes = re.split(r"[,;/|]+", value)
    return sorted({route.strip().upper() for route in routes if route.strip()})


def normalize_advisory_type(value: Optional[str]) -> str:
    normalized = (clean_text(value) or "").lower()
    return TYPE_ALIASES.get(normalized, normalized or "general service update")


def parse_datetime(value: Optional[str]) -> Optional[datetime]:
    """Parse a source timestamp and return a timezone-aware UTC datetime."""
    if not value:
        return None
    try:
        parsed = date_parser.parse(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def content_hash(*values: Optional[str]) -> str:
    canonical = "\n".join(clean_text(value) or "" for value in values)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
