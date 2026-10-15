"""Small client for Uptime Kuma's public status-page endpoints."""

from __future__ import annotations

import json
from typing import Any, Callable
from urllib.parse import quote
from urllib.request import Request, urlopen

from .model import MonitorStatus


class UptimeProviderError(RuntimeError):
    pass


class UptimeKumaProvider:
    def __init__(
        self,
        base_url: str,
        status_page: str,
        *,
        timeout_seconds: float = 5,
        opener: Callable[..., Any] = urlopen,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.status_page = status_page.strip().strip("/")
        self.timeout_seconds = timeout_seconds
        self.opener = opener

    def fetch(self) -> tuple[MonitorStatus, ...]:
        if not self.status_page:
            raise UptimeProviderError("Keine oeffentliche Statusseite konfiguriert")
        slug = quote(self.status_page, safe="")
        page = self._get_json(f"/api/status-page/{slug}")
        heartbeat = self._get_json(f"/api/status-page/heartbeat/{slug}")
        heartbeat_lists = heartbeat.get("heartbeatList", {})
        monitors: list[MonitorStatus] = []
        for group in page.get("publicGroupList", []):
            if not isinstance(group, dict):
                continue
            for monitor in group.get("monitorList", []):
                if not isinstance(monitor, dict):
                    continue
                try:
                    monitor_id = int(monitor["id"])
                except (KeyError, TypeError, ValueError):
                    continue
                entries = heartbeat_lists.get(str(monitor_id), [])
                latest = entries[-1] if isinstance(entries, list) and entries else {}
                status = latest.get("status") if isinstance(latest, dict) else None
                try:
                    status = int(status) if status is not None else None
                except (TypeError, ValueError):
                    status = None
                ping = latest.get("ping") if isinstance(latest, dict) else None
                try:
                    ping = float(ping) if ping is not None else None
                except (TypeError, ValueError):
                    ping = None
                monitors.append(
                    MonitorStatus(
                        monitor_id=monitor_id,
                        name=str(monitor.get("name") or f"Dienst {monitor_id}"),
                        status=status,
                        ping_ms=ping,
                        updated_at=str(latest.get("time") or "") if isinstance(latest, dict) else "",
                    )
                )
        return tuple(monitors)

    def _get_json(self, path: str) -> dict[str, Any]:
        request = Request(
            self.base_url + path,
            headers={"Accept": "application/json", "User-Agent": "SoomfonController/1"},
        )
        try:
            with self.opener(request, timeout=self.timeout_seconds) as response:
                payload = json.load(response)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            raise UptimeProviderError(str(exc)) from exc
        if not isinstance(payload, dict):
            raise UptimeProviderError("Uptime Kuma lieferte kein JSON-Objekt")
        return payload

