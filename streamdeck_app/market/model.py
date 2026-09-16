"""Provider-independent read-only market data structures."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WatchItem:
    symbol: str
    label: str


@dataclass(frozen=True)
class MarketQuote:
    symbol: str
    price: float
    currency: str
    change_percent: float
    timestamp: float
    market_state: str


@dataclass(frozen=True)
class MarketResult:
    quote: MarketQuote | None = None
    error: str | None = None
    fetched_at: float = 0.0
