from __future__ import annotations

"""
Kalshi adapter stub — NOT connected to any live exchange.

Replace the NotImplementedError bodies with real Kalshi REST/WS calls
once API keys and exchange access are available. See docs/SECRETS.md
for the environment-variable naming convention.
"""

from src.models import MarketState, OrderIntent, ExecutionResult


class KalshiAdapterStub:
    """Stub only — raises NotImplementedError on every call."""

    def __init__(self) -> None:
        # Future: load from env KALSHI_API_KEY, KALSHI_API_SECRET
        raise NotImplementedError("KalshiAdapterStub is not yet wired up.")

    def fetch_market(self, market_id: str) -> MarketState:
        raise NotImplementedError

    def submit_order(self, intent: OrderIntent) -> ExecutionResult:
        raise NotImplementedError

    def cancel_order(self, order_id: str) -> bool:
        raise NotImplementedError
