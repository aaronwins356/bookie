from __future__ import annotations

"""
Kalshi REST client — read-only, GET requests only.

Does NOT submit orders. DATA_CAPTURE_ONLY.
"""

from typing import Any, Dict, Optional

from src.live.env import LiveEnv, DEFAULT_REST_BASE

_TIMEOUT_SECONDS = 10


class KalshiRestClient:
    """
    Thin wrapper around the Kalshi REST API for data-capture use.
    Only GET is implemented; no order submission methods exist.
    """

    def __init__(self, env: LiveEnv, signer=None) -> None:
        self._base = env.api_base_url.rstrip("/")
        self._signer = signer

    def get(
        self, path: str, params: Optional[Dict[str, Any]] = None, authenticated: bool = True
    ) -> Dict[str, Any]:
        """
        Perform a signed GET request. Returns parsed JSON body.
        Raises RuntimeError on HTTP errors; ImportError if 'requests' is missing.
        """
        try:
            import requests as _req
        except ImportError as exc:
            raise ImportError(
                "Install 'requests' to use the REST client: pip install requests"
            ) from exc

        url = self._base + path
        headers: Dict[str, str] = {"Content-Type": "application/json"}
        if authenticated and self._signer is not None:
            headers.update(self._signer.make_headers("GET", path))

        resp = _req.get(url, headers=headers, params=params, timeout=_TIMEOUT_SECONDS)
        if not resp.ok:
            raise RuntimeError(
                f"Kalshi REST error {resp.status_code} on GET {path}: {resp.text[:200]}"
            )
        return resp.json()

    def get_markets(
        self,
        series_ticker: Optional[str] = None,
        event_ticker: Optional[str] = None,
        ticker: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Query markets from Kalshi API.

        Standard params:
          series_ticker: Filter by series (e.g., "KXATP")
          event_ticker: Filter by event
          ticker: Filter by exact ticker
          status: Filter by status (e.g., "open")
          limit: Max results (default 100)

        Additional params can be passed as kwargs:
          category: "sports", "bundled_product", etc.
          sport: "tennis", "basketball", etc.
          Other Kalshi API parameters
        """
        params: Dict[str, Any] = {"limit": limit}
        if series_ticker:
            params["series_ticker"] = series_ticker
        if event_ticker:
            params["event_ticker"] = event_ticker
        if ticker:
            params["tickers"] = ticker
        if status:
            params["status"] = status
        # Pass through any additional API parameters
        params.update(kwargs)
        return self.get("/markets", params=params, authenticated=True)

    def get_orderbook(self, ticker: str, depth: int = 10) -> Dict[str, Any]:
        return self.get(f"/markets/{ticker}/orderbook", params={"depth": depth}, authenticated=True)

    def get_market(self, ticker: str) -> Dict[str, Any]:
        return self.get(f"/markets/{ticker}", authenticated=True)

    def search_markets(
        self,
        q: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Search markets by query string.

        Args:
          q: Search query (e.g., "Gaston", "French Open", "tennis")
          status: Filter by status
          limit: Max results
          **kwargs: Additional API parameters

        Returns:
          API response with matching markets
        """
        params: Dict[str, Any] = {"limit": limit}
        if q:
            params["q"] = q
        if status:
            params["status"] = status
        params.update(kwargs)
        return self.get("/markets", params=params, authenticated=True)

    def get_events(
        self,
        status: Optional[str] = None,
        limit: int = 100,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Get all events.

        Args:
          status: Filter by status
          limit: Max results
          **kwargs: Additional API parameters

        Returns:
          API response with events
        """
        params: Dict[str, Any] = {"limit": limit}
        if status:
            params["status"] = status
        params.update(kwargs)
        return self.get("/events", params=params, authenticated=True)

    def get_series(
        self,
        status: Optional[str] = None,
        limit: int = 100,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Get all series.

        Args:
          status: Filter by status
          limit: Max results
          **kwargs: Additional API parameters

        Returns:
          API response with series
        """
        params: Dict[str, Any] = {"limit": limit}
        if status:
            params["status"] = status
        params.update(kwargs)
        return self.get("/series", params=params, authenticated=True)
