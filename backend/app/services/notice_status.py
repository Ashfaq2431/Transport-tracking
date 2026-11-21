from datetime import datetime, timezone


def calculate_status(
    valid_from: datetime | None,
    valid_to: datetime | None,
    withdrawn: bool = False,
    now: datetime | None = None,
) -> str:
    if withdrawn:
        return "withdrawn"
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    if valid_from and valid_from.tzinfo is None:
        valid_from = valid_from.replace(tzinfo=timezone.utc)
    if valid_to and valid_to.tzinfo is None:
        valid_to = valid_to.replace(tzinfo=timezone.utc)
    if valid_from and current < valid_from:
        return "scheduled"
    if valid_to and current > valid_to:
        return "expired"
    if valid_from or valid_to:
        return "active"
    return "unknown"


def is_stale(last_confirmed_at: datetime | None, freshness_minutes: int = 180) -> bool:
    if last_confirmed_at is None:
        return True
    confirmed = last_confirmed_at
    if confirmed.tzinfo is None:
        confirmed = confirmed.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - confirmed).total_seconds() > freshness_minutes * 60

