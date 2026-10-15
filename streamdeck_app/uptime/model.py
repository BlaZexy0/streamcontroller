"""Provider-independent service status values."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MonitorStatus:
    monitor_id: int
    name: str
    status: int | None = None
    ping_ms: float | None = None
    updated_at: str = ""

