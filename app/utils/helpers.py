"""
Shared utility helpers.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse


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


def save_api_response(
    *,
    method: str,
    url: str,
    status_code: int,
    headers: dict[str, str],
    body: str,
) -> Path:
    """Persist a raw API response to output/ and return the created file path."""
    output_dir = Path("output")
    output_dir.mkdir(parents=True, exist_ok=True)

    path = urlparse(url).path.strip("/") or "root"
    safe_path = path.replace("/", "_").replace(" ", "_")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    file_path = output_dir / f"{timestamp}_{method.lower()}_{safe_path}.json"

    payload = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "method": method.upper(),
        "url": url,
        "status_code": status_code,
        "headers": headers,
        "body": body,
    }

    file_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return file_path
