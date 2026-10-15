from __future__ import annotations

import io
import json
import unittest

from streamdeck_app.screens.uptime import uptime_tile
from streamdeck_app.uptime import MonitorStatus, UptimeKumaProvider


class _Response(io.BytesIO):
    def __enter__(self):  # type: ignore[no-untyped-def]
        return self

    def __exit__(self, *_args):  # type: ignore[no-untyped-def]
        self.close()


class UptimeProviderTests(unittest.TestCase):
    def test_public_status_page_is_merged_with_latest_heartbeat(self) -> None:
        payloads = iter(
            (
                {
                    "publicGroupList": [
                        {"monitorList": [{"id": 7, "name": "Jellyfin"}]}
                    ]
                },
                {
                    "heartbeatList": {
                        "7": [
                            {"status": 0, "ping": 0, "time": "old"},
                            {"status": 1, "ping": 12.6, "time": "new"},
                        ]
                    }
                },
            )
        )

        def opener(_request, timeout):  # type: ignore[no-untyped-def]
            self.assertEqual(timeout, 3)
            return _Response(json.dumps(next(payloads)).encode())

        provider = UptimeKumaProvider(
            "http://kuma.local", "home", timeout_seconds=3, opener=opener
        )
        self.assertEqual(
            provider.fetch(),
            (MonitorStatus(7, "Jellyfin", 1, 12.6, "new"),),
        )

    def test_tile_has_native_display_size(self) -> None:
        image = uptime_tile(MonitorStatus(1, "Home Assistant", 1, 4.2))
        self.assertEqual(image.size, (60, 60))


if __name__ == "__main__":
    unittest.main()
