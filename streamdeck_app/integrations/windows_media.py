"""Read Spotify metadata from the local Windows media-session API."""

from __future__ import annotations

from typing import Any

from ..media.model import MediaState

try:
    from winrt.windows.media.control import (
        GlobalSystemMediaTransportControlsSessionManager as SessionManager,
    )
    from winrt.windows.storage.streams import DataReader
except ImportError:  # Gives source checkouts without optional packages a useful state.
    SessionManager = None  # type: ignore[assignment,misc]
    DataReader = None  # type: ignore[assignment,misc]


class WindowsMediaError(RuntimeError):
    """The local Windows media-session API could not be read."""


class SpotifyMediaProvider:
    """Find Spotify's own session instead of whichever player was used last."""

    async def fetch(self) -> MediaState:
        if SessionManager is None or DataReader is None:
            raise WindowsMediaError("Windows-Medienmodule fehlen")

        manager = await SessionManager.request_async()
        session = self._spotify_session(manager)
        if session is None:
            return MediaState()

        properties = await session.try_get_media_properties_async()
        playback = session.get_playback_info()
        status = self._status_name(playback.playback_status)
        artwork = await self._read_artwork(properties.thumbnail)
        return MediaState(
            title=(properties.title or "").strip(),
            artist=(properties.artist or properties.album_artist or "").strip(),
            status=status,
            artwork=artwork,
        )

    @staticmethod
    def _spotify_session(manager: Any) -> Any | None:
        for session in manager.get_sessions():
            source = (session.source_app_user_model_id or "").lower()
            if "spotify" in source:
                return session
        return None

    @staticmethod
    def _status_name(status: Any) -> str:
        name = getattr(status, "name", str(status)).lower()
        if "playing" in name:
            return "playing"
        if "paused" in name:
            return "paused"
        if "stopped" in name or "closed" in name:
            return "stopped"
        return "inactive"

    @staticmethod
    async def _read_artwork(thumbnail: Any | None) -> bytes | None:
        if thumbnail is None:
            return None
        stream = await thumbnail.open_read_async()
        try:
            size = int(stream.size)
            if size <= 0 or size > 10 * 1024 * 1024:
                return None
            reader = DataReader(stream)
            try:
                await reader.load_async(size)
                data = bytearray(reader.unconsumed_buffer_length)
                reader.read_bytes(data)
                return bytes(data)
            finally:
                reader.close()
        finally:
            stream.close()
