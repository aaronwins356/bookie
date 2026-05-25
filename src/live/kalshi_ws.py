from __future__ import annotations

"""
Kalshi WebSocket client — subscribe to market data, record messages.

Does NOT submit orders. DATA_CAPTURE_ONLY.

Usage (sync entry point):
    client = KalshiWsClient(env, signer, on_message=handler)
    client.run(tickers=["KXBTC15M-25MAY-BTC15T32000"], seconds=60)
"""

import asyncio
import json
import logging
import time
from typing import Callable, List, Optional

from src.live.env import LiveEnv

logger = logging.getLogger(__name__)

_CHANNELS = ["orderbook_delta", "ticker", "trade"]
_RECONNECT_DELAY = 3.0
_PING_INTERVAL = 20


class KalshiWsClient:
    """
    Subscribes to Kalshi WS channels for the given tickers.
    Calls on_message(ticker, raw_dict) for each received message.
    Never sends order commands.
    """

    def __init__(
        self,
        env: LiveEnv,
        signer=None,
        on_message: Optional[Callable[[str, dict], None]] = None,
    ) -> None:
        self._ws_url = env.ws_url
        self._signer = signer
        self._on_message = on_message or (lambda ticker, msg: None)

    def run(self, tickers: List[str], seconds: float = 60.0) -> int:
        """Blocking entry point. Returns count of messages received."""
        return asyncio.run(self._run_async(tickers, seconds))

    async def _run_async(self, tickers: List[str], seconds: float) -> int:
        deadline = time.monotonic() + seconds
        count = 0
        while time.monotonic() < deadline:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            try:
                count += await self._connect_once(tickers, remaining)
            except Exception as exc:  # noqa: BLE001
                logger.warning("WS connection error: %s — reconnecting in %.1fs", exc, _RECONNECT_DELAY)
                await asyncio.sleep(min(_RECONNECT_DELAY, max(0, deadline - time.monotonic())))
        return count

    async def _connect_once(self, tickers: List[str], seconds: float) -> int:
        try:
            import websockets
        except ImportError as exc:
            raise ImportError(
                "Install 'websockets' to use the WS client: pip install websockets"
            ) from exc

        ws_url = self._ws_url
        extra_headers = {}
        if self._signer is not None:
            path = "/trade-api/ws/v2"
            extra_headers = self._signer.make_headers("GET", path)

        count = 0
        async with websockets.connect(
            ws_url,
            additional_headers=extra_headers,
            ping_interval=_PING_INTERVAL,
            close_timeout=5,
        ) as ws:
            # Subscribe to channels for all tickers
            sub_msg = {
                "id": 1,
                "cmd": "subscribe",
                "params": {
                    "channels": _CHANNELS,
                    "market_tickers": tickers,
                },
            }
            await ws.send(json.dumps(sub_msg))
            deadline = time.monotonic() + seconds
            while time.monotonic() < deadline:
                try:
                    remaining = deadline - time.monotonic()
                    raw = await asyncio.wait_for(ws.recv(), timeout=min(5.0, remaining))
                except asyncio.TimeoutError:
                    break
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    logger.debug("Non-JSON WS message: %s", raw[:80])
                    continue
                ticker = _extract_ticker(msg, tickers)
                self._on_message(ticker, msg)
                count += 1
        return count


def _extract_ticker(msg: dict, tickers: List[str]) -> str:
    """Best-effort extraction of ticker from a WS message."""
    msg_data = msg.get("msg", {})
    if isinstance(msg_data, dict):
        t = msg_data.get("market_ticker") or msg_data.get("ticker") or ""
        if t:
            return t
    return tickers[0] if tickers else "UNKNOWN"
