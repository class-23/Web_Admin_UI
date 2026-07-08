from datetime import datetime, timezone
from typing import Optional, Union


def ensure_utc_datetime(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def issued_at_to_utc_datetime(issued_at: Union[int, float, datetime, None]) -> Optional[datetime]:
    if issued_at is None:
        return None
    if isinstance(issued_at, datetime):
        return ensure_utc_datetime(issued_at)
    return datetime.fromtimestamp(issued_at, tz=timezone.utc)


def is_newer_than_issued_at(
    updated_at: Optional[datetime],
    issued_at: Union[int, float, datetime, None],
) -> bool:
    normalized_updated_at = ensure_utc_datetime(updated_at)
    normalized_issued_at = issued_at_to_utc_datetime(issued_at)
    if normalized_updated_at is None or normalized_issued_at is None:
        return False
    return normalized_updated_at > normalized_issued_at
