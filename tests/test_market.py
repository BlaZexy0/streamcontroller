from __future__ import annotations

import json
import unittest
from pathlib import Path

from streamdeck_app.core.foreground import ForegroundWindow
from streamdeck_app.market import (
    MarketDataError,
    MarketDataWorker,
    MarketQuote,
    MarketResult,
    WatchItem,
    YahooMarketDataProvider,
)
from streamdeck_app.screens import market_tile
from streamdeck_app.service import ControllerService
from streamdeck_app.settings import load_settings
from streamdeck_app.testing import MockDeck


ROOT = Path(__file__).resolve().parent.parent
WATCHLIST = (
    WatchItem("AAPL", "APPLE"),
    WatchItem("MSFT", "MSFT"),
    WatchItem("NVDA", "NVIDIA"),
)


class YahooProviderTests(unittest.TestCase):
    def test_recorded_chart_payload_is_parsed_without_live_network(self) -> None:
        captured: list[tuple[str, float]] = []
        payload = {
            "chart": {
                "error": None,
                "result": [
                    {
                        "meta": {
                            "currency": "USD",
                            "regularMarketPrice": 190.0,
                            "chartPreviousClose": 185.0,
                            "regularMarketTime": 1_700_000_000,
                            "marketState": "REGULAR",
                        }
                    }
                ],
            }
        }

        def transport(url: str, timeout: float) -> bytes:
            captured.append((url, timeout))
            return json.dumps(payload).encode("utf-8")

        quote = YahooMarketDataProvider(timeout=3, transport=transport).fetch("AAPL")

        self.assertEqual(quote.price, 190.0)
        self.assertEqual(quote.currency, "USD")
        self.assertAlmostEqual(quote.change_percent, 2.7027, places=3)
        self.assertIn("/AAPL?", captured[0][0])
        self.assertEqual(captured[0][1], 3)

    def test_invalid_payload_becomes_provider_error(self) -> None:
        provider = YahooMarketDataProvider(transport=lambda _url, _timeout: b"{}")
        with self.assertRaises(MarketDataError):
            provider.fetch("AAPL")

    def test_market_state_is_inferred_from_regular_trading_period(self) -> None:
        payload = {
            "chart": {
                "error": None,
                "result": [{
                    "meta": {
                        "currency": "USD",
                        "regularMarketPrice": 190.0,
                        "chartPreviousClose": 185.0,
                        "currentTradingPeriod": {
                            "regular": {"start": 900, "end": 1100}
                        },
                    }
                }],
            }
        }
        provider = YahooMarketDataProvider(
            transport=lambda _url, _timeout: json.dumps(payload).encode("utf-8"),
            clock=lambda: 1_000,
        )
        self.assertEqual(provider.fetch("AAPL").market_state, "REGULAR")

        provider.clock = lambda: 1_200
        self.assertEqual(provider.fetch("AAPL").market_state, "CLOSED")


class MarketWorkerTests(unittest.TestCase):
    def test_worker_caches_quotes_and_backs_off_on_total_failure(self) -> None:
        class Provider:
            fail = False

            def fetch(self, symbol: str) -> MarketQuote:
                if self.fail:
                    raise MarketDataError("offline")
                return MarketQuote(symbol, 100.0, "USD", 1.0, 900.0, "REGULAR")

        provider = Provider()
        worker = MarketDataWorker(
            provider,
            WATCHLIST,
            refresh_seconds=60,
            clock=lambda: 1_000.0,
        )
        self.assertEqual(worker.refresh_once(), 60)
        revision, first = worker.snapshot()
        self.assertEqual(revision, 1)
        self.assertTrue(all(result.quote is not None for result in first.values()))

        provider.fail = True
        self.assertEqual(worker.refresh_once(), 120)
        revision, stale = worker.snapshot()
        self.assertEqual(revision, 2)
        self.assertTrue(all(result.quote is not None for result in stale.values()))
        self.assertTrue(all(result.error == "offline" for result in stale.values()))

    def test_closed_market_uses_long_refresh_interval(self) -> None:
        class Provider:
            def fetch(self, symbol: str) -> MarketQuote:
                return MarketQuote(symbol, 100.0, "USD", 0.0, 900.0, "CLOSED")

        worker = MarketDataWorker(
            Provider(),
            WATCHLIST,
            refresh_seconds=15,
            closed_refresh_seconds=1800,
        )
        self.assertEqual(worker.refresh_once(), 1800)


class MarketScreenTests(unittest.TestCase):
    def test_positive_negative_and_stale_tiles_are_renderable(self) -> None:
        positive = MarketResult(
            MarketQuote("AAPL", 190.12, "USD", 2.4, 900, "REGULAR"),
            fetched_at=1_000,
        )
        negative = MarketResult(
            MarketQuote("AAPL", 188.25, "USD", -1.3, 900, "CLOSED"),
            fetched_at=1_000,
        )
        stale = MarketResult(positive.quote, error="offline", fetched_at=1_000)
        images = [
            market_tile(WATCHLIST[0], result, stale_seconds=180, now=1_050)
            for result in (positive, negative, stale)
        ]
        self.assertTrue(all(image.size == (60, 60) for image in images))
        self.assertTrue(all(image.getpixel((30, 1)) != image.getpixel((30, 3)) for image in images))
        self.assertTrue(all(image.getpixel((1, 30)) != image.getpixel((3, 30)) for image in images))
        self.assertTrue(all(image.getpixel((58, 30)) != image.getpixel((56, 30)) for image in images))
        self.assertTrue(all(image.getpixel((30, 58)) != image.getpixel((30, 56)) for image in images))
        self.assertEqual(len({image.tobytes() for image in images}), 3)

    def test_service_places_market_tiles_only_in_screensaver_bottom_row(self) -> None:
        configured_watchlist = load_settings(ROOT / "config.json").market_watchlist

        class Worker:
            def snapshot(self) -> tuple[int, dict[str, MarketResult]]:
                return 1, {
                    item.symbol: MarketResult(
                        MarketQuote(item.symbol, 100 + index, "USD", index - 1, 0, "REGULAR"),
                        fetched_at=10**10,
                    )
                    for index, item in enumerate(configured_watchlist)
                }

        service = ControllerService(
            ROOT / "config.json",
            deck_factory=MockDeck,
            foreground_provider=lambda: ForegroundWindow("code.exe", "Test", 1),
            market_worker=Worker(),  # type: ignore[arg-type]
        )
        deck = MockDeck()
        service.activate_profile(deck, service.resolve_profile("code.exe"))
        profile_images = tuple(deck.images[3:6])

        service.start_screensaver(deck, now=1.0)

        self.assertTrue(all(deck.images[index] is not None for index in range(3, 6)))
        self.assertNotEqual(tuple(deck.images[3:6]), profile_images)
        self.assertEqual(service.market_revision, 1)


if __name__ == "__main__":
    unittest.main()
