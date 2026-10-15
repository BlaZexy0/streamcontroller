"""Small, provider-independent snapshot of a Windows media session."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MediaState:
    title: str = ""
    artist: str = ""
    status: str = "unavailable"
    artwork: bytes | None = None
    error: str | None = None

    @property
    def available(self) -> bool:
        return self.status != "unavailable" and self.error is None

    @property
    def playing(self) -> bool:
        return self.status == "playing"
