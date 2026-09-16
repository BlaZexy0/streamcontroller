"""Single low-frequency worker with cache and bounded error backoff."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable

from .model import MarketResult, WatchItem
from .provider import MarketDataError, MarketDataProvider


class MarketDataWorker:
    def __init__(
        self,
        provider: MarketDataProvider,
        watchlist: tuple[WatchItem, ...],
        *,
        refresh_seconds: float,
        closed_refresh_seconds: float = 1800.0,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.provider = provider
        self.watchlist = watchlist
        self.refresh_seconds = refresh_seconds
        self.closed_refresh_seconds = closed_refresh_seconds
        self.clock = clock
        self._results = {item.symbol: MarketResult() for item in watchlist}
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.revision = 0
        self.failure_count = 0

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="market-data",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)

    def snapshot(self) -> tuple[int, dict[str, MarketResult]]:
        with self._lock:
            return self.revision, dict(self._results)

    def refresh_once(self) -> float:
        fetched_at = self.clock()
        failures = 0
        updated: dict[str, MarketResult] = {}
        with self._lock:
            previous_results = dict(self._results)
        for item in self.watchlist:
            try:
                quote = self.provider.fetch(item.symbol)
                updated[item.symbol] = MarketResult(quote=quote, fetched_at=fetched_at)
            except (MarketDataError, OSError, ValueError) as exc:
                failures += 1
                previous = previous_results[item.symbol]
                updated[item.symbol] = MarketResult(
                    quote=previous.quote,
                    error=str(exc),
                    fetched_at=previous.fetched_at,
                )

        with self._lock:
            self._results.update(updated)
            self.revision += 1

        if self.watchlist and failures == len(self.watchlist):
            self.failure_count += 1
        else:
            self.failure_count = 0
        if self.failure_count:
            return min(self.refresh_seconds * (2 ** self.failure_count), 900.0)
        market_open = any(
            result.quote is not None
            and result.quote.market_state in {"REGULAR", "OPEN"}
            for result in updated.values()
        )
        return self.refresh_seconds if market_open else self.closed_refresh_seconds

    def _run(self) -> None:
        while not self._stop.is_set():
            delay = self.refresh_once()
            if self._stop.wait(delay):
                return
