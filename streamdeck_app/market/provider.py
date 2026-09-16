"""Small Yahoo chart adapter; no account, cookies, or trading access."""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from collections.abc import Callable
from typing import Any, Protocol

from .model import MarketQuote


class MarketDataError(RuntimeError):
    pass


class MarketDataProvider(Protocol):
    def fetch(self, symbol: str) -> MarketQuote: ...


def _download(url: str, timeout: float) -> bytes:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "SoomfonController/1.0"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


class YahooMarketDataProvider:
    BASE_URL = "https://query1.finance.yahoo.com/v8/finance/chart/"

    def __init__(
        self,
        *,
        timeout: float = 5.0,
        transport: Callable[[str, float], bytes] = _download,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.timeout = timeout
        self.transport = transport
        self.clock = clock

    def fetch(self, symbol: str) -> MarketQuote:
        encoded = urllib.parse.quote(symbol, safe="^.-")
        url = f"{self.BASE_URL}{encoded}?range=5d&interval=1d"
        try:
            payload = json.loads(self.transport(url, self.timeout).decode("utf-8"))
            chart = payload["chart"]
            if chart.get("error"):
                raise MarketDataError(str(chart["error"]))
            result = chart["result"][0]
            meta: dict[str, Any] = result["meta"]
            price = float(meta["regularMarketPrice"])
            previous = float(
                meta.get("chartPreviousClose")
                or meta.get("previousClose")
                or price
            )
            change = 0.0 if previous == 0 else (price - previous) / previous * 100
            market_state = str(meta.get("marketState") or "").upper()
            if not market_state:
                regular = meta.get("currentTradingPeriod", {}).get("regular", {})
                start = float(regular.get("start") or 0)
                end = float(regular.get("end") or 0)
                market_state = "REGULAR" if start <= self.clock() < end else "CLOSED"
            return MarketQuote(
                symbol=symbol,
                price=price,
                currency=str(meta.get("currency") or ""),
                change_percent=change,
                timestamp=float(meta.get("regularMarketTime") or 0),
                market_state=market_state,
            )
        except MarketDataError:
            raise
        except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise MarketDataError(f"Ungueltige Marktdaten fuer {symbol}: {exc}") from exc
        except OSError as exc:
            raise MarketDataError(f"Netzwerkfehler fuer {symbol}: {exc}") from exc
