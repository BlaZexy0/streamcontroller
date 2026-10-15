"""Spotify controls with local title, artist, cover and playback state."""

from ..integrations.windows_media import SpotifyMediaProvider
from ..media import MediaSessionWorker
from ..screens.spotify import spotify_tiles
from .helpers import key
from .model import Button, Profile, ProfileContext, ProfileLifecycle


class SpotifyLifecycle(ProfileLifecycle):
    def __init__(self) -> None:
        self.worker = MediaSessionWorker(SpotifyMediaProvider())
        self.last_revision = -1

    def on_activate(self, context: ProfileContext) -> None:
        self.last_revision = -1
        self.worker.start()
        self._render(context)

    def on_deactivate(self, context: ProfileContext) -> None:
        self.worker.stop()

    def on_tick(self, context: ProfileContext, now: float) -> None:
        revision, _state = self.worker.snapshot()
        if revision != self.last_revision:
            self._render(context)

    def _render(self, context: ProfileContext) -> None:
        revision, state = self.worker.snapshot()
        for index, image in enumerate(spotify_tiles(state)):
            context.set_key_image(index, image)
        self.last_revision = revision


PROFILE = Profile(
    name="Spotify",
    processes=("spotify.exe",),
    order=40,
    lifecycle_factory=SpotifyLifecycle,
    buttons=(
        Button("PREV", (25, 145, 75), key("media_prev")),
        Button("PLAY", (30, 185, 95), key("media_play_pause")),
        Button("NEXT", (25, 145, 75), key("media_next")),
        Button("VOL-", (45, 65, 75), key("volume_down")),
        Button("MUTE", (175, 50, 60), key("volume_mute")),
        Button("VOL+", (45, 65, 75), key("volume_up")),
    ),
)
