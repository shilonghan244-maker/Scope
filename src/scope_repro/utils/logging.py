from __future__ import annotations

from datetime import datetime, timezone


def log_line(message: str) -> str:
    timestamp = datetime.now(timezone.utc).isoformat()
    return f"[{timestamp}] {message}"
