"""
Shared utility helpers.
"""

from datetime import datetime, timezone


def utc_now() -> datetime:
    """Return the current UTC datetime (timezone-aware)."""
    return datetime.now(timezone.utc)


def safe_get(data: dict, *keys: str, default=None):
    """
    Safely traverse nested dicts.

    Usage:
        safe_get(payload, "meta", "pagination", "next_cursor")
    """
    current = data
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key, default)
    return current
