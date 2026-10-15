from __future__ import annotations

import asyncio
import unittest
from io import BytesIO

from PIL import Image
from winrt.windows.storage.streams import DataWriter, InMemoryRandomAccessStream

from streamdeck_app.integrations.windows_media import SpotifyMediaProvider
from streamdeck_app.media import MediaSessionWorker, MediaState
from streamdeck_app.screens.spotify import spotify_tiles


class SpotifyProviderTests(unittest.TestCase):
    def test_spotify_session_is_selected_instead_of_current_browser(self) -> None:
        class Session:
            def __init__(self, source: str) -> None:
                self.source_app_user_model_id = source

        spotify = Session("SpotifyAB.SpotifyMusic_zpdnekdrzrea0!Spotify")

        class Manager:
            def get_sessions(self) -> tuple[Session, ...]:
                return (Session("chrome.exe"), spotify)

        self.assertIs(SpotifyMediaProvider._spotify_session(Manager()), spotify)

    def test_playback_status_is_normalized(self) -> None:
        class Status:
            name = "PLAYING"

        self.assertEqual(SpotifyMediaProvider._status_name(Status()), "playing")
        self.assertEqual(SpotifyMediaProvider._status_name("PAUSED"), "paused")

    def test_artwork_bytes_are_read_from_a_winrt_stream(self) -> None:
        async def read_test_data() -> bytes | None:
            stream = InMemoryRandomAccessStream()
            writer = DataWriter(stream)
            writer.write_bytes(b"test-artwork")
            await writer.store_async()
            writer.detach_stream()
            stream.seek(0)

            class Thumbnail:
                async def open_read_async(self) -> InMemoryRandomAccessStream:
                    return stream

            return await SpotifyMediaProvider._read_artwork(Thumbnail())

        self.assertEqual(asyncio.run(read_test_data()), b"test-artwork")


class MediaWorkerTests(unittest.TestCase):
    def test_worker_only_changes_revision_for_new_content(self) -> None:
        class Provider:
            async def fetch(self) -> MediaState:
                return MediaState("Song", "Artist", "playing")

        worker = MediaSessionWorker(Provider())
        worker.refresh_once()
        self.assertEqual(worker.snapshot(), (1, MediaState("Song", "Artist", "playing")))
        worker.refresh_once()
        self.assertEqual(worker.snapshot()[0], 1)

    def test_provider_failure_becomes_visible_state(self) -> None:
        class Provider:
            async def fetch(self) -> MediaState:
                raise OSError("simulierter Medienfehler")

        worker = MediaSessionWorker(Provider())
        worker.refresh_once()
        revision, state = worker.snapshot()
        self.assertEqual(revision, 1)
        self.assertEqual(state.error, "simulierter Medienfehler")


class SpotifyScreenTests(unittest.TestCase):
    def test_title_artist_status_and_cover_are_renderable(self) -> None:
        buffer = BytesIO()
        Image.new("RGB", (100, 50), "purple").save(buffer, format="PNG")
        state = MediaState(
            title="Ein sehr langer Testtitel fuer alle drei Displays",
            artist="Testinterpret",
            status="playing",
            artwork=buffer.getvalue(),
        )

        tiles = spotify_tiles(state)

        self.assertEqual(len(tiles), 6)
        self.assertTrue(all(tile.size == (60, 60) for tile in tiles))
        self.assertNotEqual(tiles[1].getpixel((10, 10)), (19, 31, 25))
        self.assertNotEqual(tiles[3].tobytes(), tiles[4].tobytes())

    def test_missing_session_has_a_complete_fallback_screen(self) -> None:
        tiles = spotify_tiles(MediaState())
        self.assertEqual(len(tiles), 6)
        self.assertTrue(all(tile.mode == "RGB" for tile in tiles))


if __name__ == "__main__":
    unittest.main()
